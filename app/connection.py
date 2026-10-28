"""ENET cable detection and car connection (HSFZ + DoIP transport).

Provides:
  - list_interfaces() — enumerate Ethernet adapters via netifaces
  - discover_zgw() — UDP vehicle discovery
  - start_dhcp_server() / stop_dhcp_server() — DHCP fallback
  - HSFZConnection — HSFZ transport (F-series, TCP 6801)
  - DoIPConnection — DoIP transport (G/U/I-series, TCP 13400)

Live socket I/O, UDS services and keepalive run on one protocol owner.
Transport selection uses discovery evidence rather than a chassis heuristic.

Reference: docs/10-hsfz-protocol.md, docs/05-protocol-reference.md
"""

import logging
import os
import platform
import socket
import subprocess
from dataclasses import dataclass

import netifaces

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

HSFZ_DATA_PORT = 6801
HSFZ_DISCOVERY_PORT = 6811
DOIP_DATA_PORT = 13400
DOIP_DISCOVERY_PORT = 13400

HSFZ_DISCOVERY_BROADCAST = "169.254.255.255"

TYPE_VEHICLE_IDENT = 0x0011
TYPE_DIAG_REQ_RES = 0x0001
TYPE_ALIVE_CHECK = 0x0012
TYPE_ACK_TRANSFER = 0x0002

# HSFZ error type descriptions
HSFZ_ERROR_TYPES: dict[int, str] = {
    0x0040: "Incorrect tester address",
    0x0041: "Incorrect control word",
    0x0042: "Incorrect format",
    0x0043: "Incorrect destination address",
    0x0044: "Message too large",
    0x0045: "Diagnostic application not ready",
    0x00FF: "ZGW out of memory",
}

ZGW_ADDR = 0x10

# DoIP payload types
DOIP_VEHICLE_ID_REQUEST = 0x0001
DOIP_VEHICLE_ID_RESPONSE = 0x0004
DOIP_ROUTING_ACTIVATION_REQUEST = 0x0005
DOIP_ROUTING_ACTIVATION_RESPONSE = 0x0006
DOIP_DIAG_MESSAGE = 0x8001
DOIP_DIAG_MESSAGE_ACK = 0x8002
DOIP_DIAG_MESSAGE_NACK = 0x8003
DOIP_ALIVE_CHECK_REQUEST = 0x0007
DOIP_ALIVE_CHECK_RESPONSE = 0x0008

DOIP_PROTOCOL_VERSION = 0x02

# Tester addresses
DOIP_TESTER_LOGICAL_ADDR = 0x0E00


# ── Interface Detection (T-4) ────────────────────────────────────────────────


def list_interfaces() -> list[str]:
    """Return all Ethernet adapter names on this machine.

    Uses netifaces to enumerate interfaces. Filters to Ethernet adapters only.
    On macOS: returns enX interfaces (en0, en7, etc.).
    On Windows: returns physical Ethernet adapters (Ethernet, Ethernet 2, etc.).
    On Linux: returns ethX and enpXsY interfaces.

    Returns:
        Sorted list of interface name strings.

    Example:
        >>> ifaces = list_interfaces()
        >>> [i for i in ifaces if i.startswith('en') or i.startswith('eth')]
    """
    return sorted(info.name for info in list_interfaces_detailed())


# ── Rich interface info for UI ────────────────────────────────────────────


@dataclass(slots=True)
class _InterfaceInfo:
    """Adapter candidate; an assigned IPv4 address does not prove physical link."""

    name: str
    ip: str
    mac: str
    connected: bool
    description: str

    def display_text(self) -> str:
        """Rich one-line label for use in a QComboBox."""
        if self.connected:
            return f"{self.name} — {self.ip}  ({self.description})"
        return f"{self.name} — disconnected  ({self.description})"

    def sort_key(self) -> tuple[int, str]:
        """Sort key: connected first, then by name."""
        return (0 if self.connected else 1, self.name)


def list_interfaces_detailed() -> list[_InterfaceInfo]:
    """Return all Ethernet adapters with IP, MAC, and connected status.

    Uses ``netifaces`` to enumerate every adapter, then enriches each
    entry with the assigned IPv4 address and a human-readable
    description.  Connected adapters appear first in the result.

    Returns:
        List of ``_InterfaceInfo``, connected-first.

    Example:
        >>> for info in list_interfaces_detailed():
        ...     print(info.display_text())
        en15 — 169.254.244.220  (USB Ethernet Adapter)
        en0 — disconnected  (Built-in Ethernet)
    """
    results: list[_InterfaceInfo] = []

    for iface in netifaces.interfaces():
        # Skip loopback
        if iface.startswith("lo"):
            continue

        addrs = netifaces.ifaddresses(iface)

        # Must have a link-layer address (real hardware)
        if netifaces.AF_LINK not in addrs:
            continue

        link_addr = addrs[netifaces.AF_LINK][0].get("addr", "")
        if not link_addr or link_addr == "00:00:00:00:00:00":
            continue

        if platform.system() == "Darwin":
            virtual_prefixes = (
                "bridge",
                "gif",
                "stf",
                "utun",
                "ap",
                "awdl",
                "llw",
                "pdp_ip",
                "anpi",
                "vmnet",
                "fw",
            )
            if any(iface.startswith(p) for p in virtual_prefixes):
                continue
            if not iface.startswith("en"):
                continue

        elif platform.system() == "Linux":
            if not (iface.startswith("en") or iface.startswith("eth")):
                continue

        # Extract IPv4 address
        ip = ""
        connected = False
        if netifaces.AF_INET in addrs:
            for entry in addrs[netifaces.AF_INET]:
                addr = entry.get("addr", "")
                if addr and addr != "0.0.0.0" and not addr.startswith("127."):
                    ip = addr
                    connected = True
                    break

        # Build human-readable description
        description = _describe_interface(iface)

        results.append(
            _InterfaceInfo(
                name=iface,
                ip=ip,
                mac=link_addr.lower(),
                connected=connected,
                description=description,
            )
        )

    results.sort(key=lambda i: i.sort_key())
    return results


def _describe_interface(name: str) -> str:
    """Return a human-readable label for an interface name.

    Uses platform heuristics and common naming patterns.
    """
    system = platform.system()

    if system == "Darwin":
        # en0/en1 are typically built-in (Wi-Fi or Ethernet)
        # en2+ are often Thunderbolt or USB adapters
        num = 0
        for ch in name:
            if ch.isdigit():
                num = num * 10 + int(ch)
            elif num > 0:
                break

        if num <= 1:
            return "Built-in Ethernet"
        elif num <= 5:
            return "Thunderbolt Bridge"
        else:
            return "USB Ethernet Adapter"

    if system == "Linux":
        if name.startswith("enp") or name.startswith("ens"):
            return "PCI Ethernet"
        if name.startswith("eth"):
            return "Built-in Ethernet"
        return "Network Adapter"

    if system == "Windows":
        # Windows netifaces names are already descriptive (e.g. "Ethernet 2")
        return ""

    return "Network Adapter"


def _bind_to_interface(sock: socket.socket, interface: str) -> None:
    """Bind a UDP socket to a specific network interface.

    On macOS: uses IP_BOUND_IF (scope ID) to steer broadcasts.
    On Linux/Windows: binds to the interface's IP address.

    This is best-effort — failures are logged but not fatal because
    the broadcast may still work on the default route.
    """
    try:
        addrs = netifaces.ifaddresses(interface)
        if netifaces.AF_INET in addrs:
            ip = addrs[netifaces.AF_INET][0].get("addr", "")
            if ip:
                sock.bind((ip, 0))
                logger.debug("Bound discovery socket to %s (%s)", interface, ip)
                return
    except (ValueError, KeyError, OSError) as e:
        logger.debug("Could not bind to interface %s: %s", interface, e)


# ── Vehicle Discovery (T-4) ──────────────────────────────────────────────────


def discover_zgw(interface: str, timeout: float = 5.0) -> dict[str, str] | None:
    """Compatibility entry using validated, source-bound discovery of both transports."""
    from app.protocol.contracts import OperationContext
    from app.protocol.discovery import discover_vehicle

    return discover_vehicle(interface, OperationContext.create("discovery", timeout))


# ── DHCP Server (T-6) ────────────────────────────────────────────────────────


def start_dhcp_server(interface: str) -> bool:
    """Start a DHCP server on the given interface.

    macOS: uses bootpd (requires sudo).
    Windows: uses simple-dhcp-server pip package.
    Linux: uses dnsmasq.

    Args:
        interface: Network interface name.

    Returns:
        True if server started successfully, False otherwise.
    """
    system = platform.system()

    if system == "Darwin":
        return _start_dhcp_macos(interface)
    elif system == "Windows":
        return _start_dhcp_windows(interface)
    elif system == "Linux":
        return _start_dhcp_linux(interface)
    else:
        logger.warning("DHCP server not supported on %s", system)
        return False


def stop_dhcp_server() -> bool:
    """Stop any running DHCP server process."""
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run(
                ["sudo", "killall", "bootpd"],
                capture_output=True,
                timeout=5,
            )
        elif system == "Windows":
            subprocess.run(
                ["taskkill", "/F", "/IM", "simple-dhcp-server.exe"],
                capture_output=True,
                timeout=5,
            )
        elif system == "Linux":
            subprocess.run(
                ["sudo", "pkill", "dnsmasq"],
                capture_output=True,
                timeout=5,
            )
        return True
    except subprocess.TimeoutExpired:
        logger.warning("DHCP server stop timed out")
        return False
    except Exception as e:
        logger.warning("Failed to stop DHCP server: %s", e)
        return False


def _start_dhcp_macos(interface: str) -> bool:
    """Start bootpd on macOS."""
    try:
        # Verify bootpd exists
        result = subprocess.run(
            ["which", "bootpd"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode != 0:
            logger.warning("bootpd not found on macOS")
            return False

        subprocess.run(
            ["sudo", "bootpd", "-i", interface],
            capture_output=True,
            timeout=5,
        )
        logger.info("DHCP server (bootpd) started on %s", interface)
        return True
    except subprocess.TimeoutExpired:
        logger.warning("bootpd startup timed out")
        return False
    except PermissionError:
        logger.warning("DHCP server requires admin privileges")
        return False
    except Exception as e:
        logger.warning("Failed to start DHCP server on macOS: %s", e)
        return False


def _start_dhcp_windows(interface: str) -> bool:
    """Start DHCP server on Windows using simple-dhcp-server.

    Creates a dhcpd.conf config file and attempts to start the server.
    Requires simple-dhcp-server pip package installed.
    """
    try:
        import importlib

        try:
            importlib.import_module("simple_dhcp_server")
        except ImportError:
            logger.warning(
                "simple-dhcp-server not installed. Install with: pip install simple-dhcp-server"
            )
            return False

        temp_dir = os.path.join(os.path.expanduser("~"), "BMW-Tool", "dhcp")
        os.makedirs(temp_dir, exist_ok=True)

        config_path = os.path.join(temp_dir, "dhcpd.conf")
        with open(config_path, "w") as f:
            f.write(
                "subnet 169.254.0.0 netmask 255.255.0.0 {\n"
                "    range 169.254.1.10 169.254.1.250;\n"
                "    option routers 169.254.1.1;\n"
                "    option subnet-mask 255.255.0.0;\n"
                "    default-lease-time 86400;\n"
                "    max-lease-time 86400;\n"
                "}\n"
            )

        logger.info(
            "DHCP config written to %s (server start requires manual step)",
            config_path,
        )
        # Full automated DHCP server start on Windows requires process
        # management that depends on the specific package version.
        return False

    except Exception as e:
        logger.warning("Failed to configure DHCP server on Windows: %s", e)
        return False


def _start_dhcp_linux(interface: str) -> bool:
    """Start dnsmasq on Linux for DHCP."""
    try:
        subprocess.run(
            [
                "sudo",
                "dnsmasq",
                "--interface=" + interface,
                "--dhcp-range=169.254.1.10,169.254.1.250,255.255.0.0,24h",
                "--port=0",  # Disable DNS, DHCP only
            ],
            capture_output=True,
            timeout=5,
        )
        logger.info("DHCP server (dnsmasq) started on %s", interface)
        return True
    except PermissionError:
        logger.warning("DHCP server requires root privileges")
        return False
    except Exception as e:
        logger.warning("Failed to start DHCP server on Linux: %s", e)
        return False


# ── Stream helpers ───────────────────────────────────────────────────────────

MAX_FRAME_BODY = 16 * 1024 * 1024


# Public compatibility names; all live transactions use the protocol owner.
from app.protocol.facade import DoIPConnection, HSFZConnection  # noqa: E402, F401
