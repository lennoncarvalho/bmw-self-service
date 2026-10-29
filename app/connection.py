"""ENET cable detection and car connection (HSFZ + DoIP transport).

Provides:
  - list_interfaces() — enumerate native Ethernet interface types
  - discover_zgw() — UDP vehicle discovery
  - start_dhcp_server() / stop_dhcp_server() — DHCP fallback
  - HSFZConnection — HSFZ transport (TCP 6801)
  - DoIPConnection — DoIP transport (TCP 13400)

Live socket I/O, UDS services and keepalive run on one protocol owner.
Transport selection uses discovery evidence rather than a chassis heuristic.

Reference: docs/10-hsfz-protocol.md, docs/05-protocol-reference.md
"""

import ipaddress
import logging
import os
import platform
import subprocess
from dataclasses import dataclass

from PySide6.QtNetwork import QNetworkInterface

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
    """Return native names of Ethernet candidates, without Wi-Fi/virtual fallback."""
    return sorted(info.name for info in list_interfaces_detailed())


# ── Rich interface info for UI ────────────────────────────────────────────


@dataclass(slots=True)
class _InterfaceInfo:
    """Native Ethernet candidate; configured IPv4 does not prove vehicle reachability."""

    name: str
    ip: str
    mac: str
    connected: bool
    description: str

    def display_text(self) -> str:
        """Rich one-line label for use in a QComboBox."""
        if self.connected:
            return f"{self.name} — {self.ip} · IPv4 configured ({self.description})"
        return f"{self.name} — IPv4 unavailable ({self.description})"

    def sort_key(self) -> tuple[int, str]:
        """Sort key: connected first, then by name."""
        return (0 if self.connected else 1, self.name)


def list_interfaces_detailed() -> list[_InterfaceInfo]:
    """List native Ethernet interfaces, with their actual names and IPv4 readiness.

    Qt reports interface type across platforms. Neither an enX name nor an IP
    address identifies Ethernet. No host configuration or subprocess is needed.
    Internal macOS auxiliary interfaces remain excluded. An assigned address is
    explicitly labelled configuration, never physical link or car detection.
    """
    results: list[_InterfaceInfo] = []
    for interface in QNetworkInterface.allInterfaces():
        if interface.type() != QNetworkInterface.InterfaceType.Ethernet:
            continue
        name = interface.name()
        if platform.system() == "Darwin" and name.startswith("anpi"):
            continue
        addresses = []
        for entry in interface.addressEntries():
            try:
                address = ipaddress.IPv4Address(entry.ip().toString())
            except ipaddress.AddressValueError:
                continue
            if not (address.is_unspecified or address.is_loopback or address.is_multicast):
                addresses.append(str(address))
        # Discovery requires exactly one IPv4. Do not silently choose one from
        # a multiply configured adapter and imply it is ready for connection.
        ip = addresses[0] if len(addresses) == 1 else ""
        description = interface.humanReadableName() or name
        if len(addresses) > 1:
            description += "; multiple IPv4 addresses — select one configuration"
        results.append(
            _InterfaceInfo(
                name=name,
                ip=ip,
                mac=interface.hardwareAddress().lower(),
                connected=bool(ip),
                description=description,
            )
        )
    return sorted(results, key=lambda candidate: candidate.sort_key())


def ethernet_ipv4(name: str) -> tuple[str, str]:
    """Validate one native Ethernet interface and return its sole IPv4/netmask.

    Recheck at discovery time: selection may outlive an adapter or configuration
    change. A wireless/virtual interface never becomes an ENET candidate by name.
    """
    interface = QNetworkInterface.interfaceFromName(name)
    if (
        not interface.isValid()
        or interface.type() != QNetworkInterface.InterfaceType.Ethernet
        or (platform.system() == "Darwin" and name.startswith("anpi"))
    ):
        raise ConnectionError("Select an Ethernet interface with one configured IPv4 address")
    addresses = []
    for entry in interface.addressEntries():
        try:
            address = ipaddress.IPv4Address(entry.ip().toString())
        except ipaddress.AddressValueError:
            continue
        if address.is_unspecified or address.is_loopback or address.is_multicast:
            continue
        mask = entry.netmask().toString()
        if not mask:
            raise ConnectionError("Select an Ethernet interface with one configured IPv4 address")
        ipaddress.IPv4Interface(f"{address}/{mask}")
        addresses.append((str(address), mask))
    if len(addresses) != 1:
        raise ConnectionError("Select an Ethernet interface with one configured IPv4 address")
    return addresses[0]


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
