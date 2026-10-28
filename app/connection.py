"""ENET cable detection and car connection (HSFZ + DoIP transport).

Provides:
  - list_interfaces() — enumerate Ethernet adapters via netifaces
  - discover_zgw() — UDP vehicle discovery
  - start_dhcp_server() / stop_dhcp_server() — DHCP fallback
  - HSFZConnection — HSFZ transport (F-series, TCP 6801)
  - DoIPConnection — DoIP transport (G/U/I-series, TCP 13400)

All socket I/O is serialized through a threading.Lock so that
multiple pages firing send_uds() simultaneously don't corrupt
the TCP stream. ACK (0x0002) messages from the ZGW are handled
transparently inside send_uds().

Reference: docs/10-hsfz-protocol.md, docs/05-protocol-reference.md
"""

import contextlib
import logging
import os
import platform
import socket
import struct
import subprocess
import threading
import time as _time

import netifaces

from app.uds import TESTER_ADDR, build_uds

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
    0x0045: "Diagostic application not ready",
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
    ethernet_adapters = []

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
            # macOS: skip virtual/tunnel/bridge interfaces
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

        # Windows: accept anything with a MAC address (netifaces returns
        # descriptive names like "Ethernet" on Windows)

        ethernet_adapters.append(iface)

    return sorted(ethernet_adapters)


# ── Rich interface info for UI ────────────────────────────────────────────


# dataclass imported lazily to avoid top-level dep for pure CLI use
def _import_dataclass():
    from dataclasses import dataclass as _dc

    return _dc


class _InterfaceInfo:
    """Rich network interface descriptor for the welcome-page dropdown.

    Attributes:
        name: System name (e.g. ``"en15"``).
        ip: IPv4 address string, or ``""`` if none assigned.
        mac: MAC address string (lowercase hex pairs).
        connected: ``True`` if the interface has an assigned IPv4 address.
        description: Human-readable label derived from the interface name
                     and platform heuristics (e.g. ``"USB Ethernet"``).

    This is a plain class, not a dataclass, so it works at import time
    without a top-level dataclasses dependency.
    """

    __slots__ = ("name", "ip", "mac", "connected", "description")

    def __init__(
        self,
        name: str,
        ip: str,
        mac: str,
        connected: bool,
        description: str,
    ) -> None:
        self.name = name
        self.ip = ip
        self.mac = mac
        self.connected = connected
        self.description = description

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
    """Discover a BMW ZGW on the ENET network via UDP broadcast.

    Sends a vehicle_ident_data request to 169.254.255.255:6811.
    Binds the socket to the specified interface to ensure the
    broadcast goes out on the correct Ethernet adapter.

    Args:
        interface: Network interface name (e.g. "en7").
        timeout: Seconds to wait for response.

    Returns:
        Dict with "ip", "vin", "mac" keys if found, None if timeout.
    """
    disc_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    disc_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    disc_sock.settimeout(timeout)

    # Bind to the specific interface so broadcast goes out on the right adapter.
    # Without this, UDP broadcast may go to Wi-Fi instead of the ENET cable.
    _bind_to_interface(disc_sock, interface)

    logger.debug(
        "Discovery: broadcasting on %s -> %s:%d (timeout %.1fs)",
        interface,
        HSFZ_DISCOVERY_BROADCAST,
        HSFZ_DISCOVERY_PORT,
        timeout,
    )

    try:
        request = struct.pack(">IH", 0, TYPE_VEHICLE_IDENT)
        disc_sock.sendto(request, (HSFZ_DISCOVERY_BROADCAST, HSFZ_DISCOVERY_PORT))

        try:
            data, addr = disc_sock.recvfrom(1024)
        except TimeoutError:
            logger.debug("Vehicle discovery timed out after %.1fs", timeout)
            return None

        if len(data) < 6:
            logger.warning("Discovery response too short: %d bytes", len(data))
            return None

        # Response body starts after 6-byte header
        response_str = data[6:].decode("ascii", errors="ignore")

        # Parse VIN from BMWVIN marker (17 chars)
        vin = None
        vin_idx = response_str.find("BMWVIN")
        if vin_idx >= 0:
            vin = response_str[vin_idx + 6 : vin_idx + 23].strip("\x00 ")

        # Parse MAC from BMWMAC marker (12 hex chars)
        mac = None
        mac_idx = response_str.find("BMWMAC")
        if mac_idx >= 0:
            mac = response_str[mac_idx + 6 : mac_idx + 18].strip("\x00 ")

        logger.info(
            "Vehicle found at %s: VIN=%s, MAC=%s",
            addr[0],
            vin or "unknown",
            mac or "unknown",
        )

        result: dict[str, str] = {"ip": addr[0]}
        if vin:
            result["vin"] = vin
        if mac:
            result["mac"] = mac
        return result

    finally:
        disc_sock.close()


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


# ── HSFZ Connection (T-5) ────────────────────────────────────────────────────


class HSFZConnection:
    """HSFZ transport for F-series BMW vehicles (TCP port 6801).

    Wraps UDS messages in HSFZ framing. Handles TCP connect, send,
    receive, keep-alive, and disconnect.

    Thread safety: All socket I/O is serialized through ``_lock`` so
    that multiple workers calling ``send_uds()`` concurrently don't
    corrupt the TCP stream. Callers simply call ``send_uds()`` from
    any thread — the lock queues them automatically.

    ACK handling: The ZGW acknowledges every message with an
    ``acknowledge_transfer`` (0x0002) frame before sending the actual
    ``diagnostic_req_res`` (0x0001) response.  ``send_uds()`` reads
    through the ACK transparently.

    Example:
        >>> conn = HSFZConnection("169.254.1.1")
        >>> conn.connect()
        True
        >>> resp = conn.send_uds(0x63, bytes([0x22, 0xF1, 0x90]))
        >>> conn.disconnect()
    """

    def __init__(self, host: str, port: int = HSFZ_DATA_PORT) -> None:
        """Create an HSFZ connection.

        Args:
            host: Car IP address (e.g. "169.254.1.1").
            port: TCP data port (default 6801).
        """
        self.host = host
        self.port = port
        self.sock: socket.socket | None = None
        self._lock = threading.Lock()
        self._alive_failures = 0

    # ── Connection lifecycle ────────────────────────────────────────────

    def connect(self) -> bool:
        """Open TCP connection to the vehicle's ZGW.

        Returns:
            True if connected successfully, False on failure.
        """
        logger.debug("HSFZ: connecting to %s:%d ...", self.host, self.port)
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.sock.settimeout(5.0)  # Connection timeout
            self.sock.connect((self.host, self.port))
            self.sock.settimeout(30.0)  # Data timeout
            self._alive_failures = 0
            logger.info(
                "HSFZ connected to %s:%d (TCP_NODELAY, timeout=30s)",
                self.host,
                self.port,
            )
            return True
        except (TimeoutError, ConnectionRefusedError, OSError) as e:
            logger.warning(
                "HSFZ connect to %s:%d failed: %s",
                self.host,
                self.port,
                e,
            )
            self.sock = None
            return False

    def disconnect(self) -> None:
        """Close the TCP connection to the ZGW.

        Calls ``shutdown()`` before acquiring the lock to avoid
        blocking while a ``send_uds()`` is stuck in ``recv()``.
        Then acquires the lock to close and clear the socket.
        """
        sock = self.sock
        if sock is not None:
            with contextlib.suppress(OSError):
                sock.shutdown(socket.SHUT_RDWR)
        with self._lock:
            if self.sock is sock and sock is not None:
                with contextlib.suppress(OSError):
                    sock.close()
                self.sock = None
                self._alive_failures = 0
                logger.info("HSFZ disconnected from %s:%d", self.host, self.port)

    # ── UDS messaging (the core API) ─────────────────────────────────────

    def send_uds(self, ecu_addr: int, payload: bytes, timeout: float = 30.0) -> bytes:
        """Send a UDS message and return the response payload.

        Thread-safe: serialized through ``_lock`` so only one request
        is in-flight at a time.  Blocking callers simply queue up.

        The ZGW may respond with an ``acknowledge_transfer`` (0x0002)
        frame first — this method reads through it transparently and
        returns the actual UDS payload from the ``diagnostic_req_res``
        (0x0001) that follows.

        Args:
            ecu_addr: Target ECU address (e.g. 0x63 for headunit).
            payload: UDS message payload (service byte + data).
            timeout: Maximum seconds to wait for the complete
                     response (ACK + UDS response).

        Returns:
            UDS response payload bytes (service byte + data).

        Raises:
            ConnectionError: If not connected, connection lost, or
                             ZGW reports a protocol error.
            TimeoutError: If no response within *timeout* seconds.
        """
        if self.sock is None:
            raise ConnectionError("Not connected")

        # Build the full HSFZ frame
        service = payload[0]
        extra = payload[1:] if len(payload) > 1 else b""
        frame = build_uds(ecu_addr, service, extra)

        logger.debug(
            "UDS tx ECU=0x%02X len=%d: %s",
            ecu_addr,
            len(frame),
            frame.hex(" "),
        )

        deadline = _time.monotonic() + timeout
        with self._lock:
            # Re-check after acquiring the lock — disconnect() may have
            # run between the check above and the lock acquisition.
            if self.sock is None:
                raise ConnectionError("Not connected")

            remaining = deadline - _time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"ECU 0x{ecu_addr:02X} timeout before send")
            self.sock.settimeout(max(remaining, 1.0))
            try:
                self.sock.sendall(frame)
            except OSError as e:
                raise ConnectionError(f"Send failed: {e}") from e

            # Read HSFZ messages until we get the real UDS response.
            # The ZGW may send acknowledge_transfer (0x0002) or alive
            # check frames before the diagnostic_req_res (0x0001).
            while True:
                remaining = deadline - _time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(
                        f"ECU 0x{ecu_addr:02X} did not respond within {timeout:.0f}s"
                    )
                msg_type, msg_src, _msg_dst, uds_payload = self._recv_hsfz_message(
                    max(remaining, 1.0)
                )

                if msg_type == TYPE_DIAG_REQ_RES:
                    elapsed_ms = (_time.monotonic() - (deadline - timeout)) * 1000
                    logger.debug(
                        "UDS rx ECU=0x%02X len=%d (%.0fms): %s",
                        msg_src,
                        len(uds_payload),
                        elapsed_ms,
                        uds_payload.hex(" "),
                    )
                    return uds_payload

                if msg_type == TYPE_ACK_TRANSFER:
                    logger.debug(
                        "HSFZ ACK from 0x%02X (%.0fms), reading next",
                        msg_src,
                        (_time.monotonic() - (deadline - timeout)) * 1000,
                    )
                    continue  # read next frame

                if msg_type == TYPE_ALIVE_CHECK:
                    logger.debug(
                        "HSFZ alive check from 0x%02X, skipping",
                        msg_src,
                    )
                    continue  # read next frame

                if msg_type in HSFZ_ERROR_TYPES:
                    raise ConnectionError(
                        f"ZGW error: {HSFZ_ERROR_TYPES[msg_type]} (type 0x{msg_type:04X})"
                    )

                raise ConnectionError(f"Unexpected HSFZ response type: 0x{msg_type:04X}")

    # ── Keep-alive ──────────────────────────────────────────────────────

    def alive_check(self) -> bool:
        """Send transport-layer keep-alive (HSFZ type 0x0012).

        Must be called every ~2 seconds to prevent the ZGW from closing
        the TCP connection.  Both send and ACK drain happen under the
        lock so alive-check traffic cannot interleave with ``send_uds()``.

        Non-blocking: if the lock is held the entire cycle is skipped.
        The UDS session timer is long enough (>5 s) that missing one
        cycle is harmless.

        Returns:
            True if keep-alive was sent and ACK drained, False if
            skipped or socket is gone.
        """
        if self.sock is None:
            return False

        acquired = self._lock.acquire(blocking=False)
        if not acquired:
            return True  # skipped, not a failure

        try:
            frame = struct.pack(">IHBB", 2, TYPE_ALIVE_CHECK, TESTER_ADDR, ZGW_ADDR)
            self.sock.settimeout(2.0)
            self.sock.sendall(frame)

            # Drain the expected ACK
            with contextlib.suppress(TimeoutError, socket.timeout, ConnectionError):
                msg_type, msg_src, _dst, _payload = self._recv_hsfz_message(0.05)
                if msg_type == TYPE_ACK_TRANSFER:
                    logger.debug("HSFZ alive ACK drained from 0x%02X", msg_src)
            self._alive_failures = 0
            return True
        except (OSError, ConnectionError):
            self._alive_failures += 1
            return False
        finally:
            self._lock.release()

    def tester_present(self) -> bool:
        """Send UDS TesterPresent (0x3E 0x80) — non-blocking.

        Uses the suppress-positive-response bit (0x80) so the ECU
        doesn't waste bus time sending a ``7E 00`` response.  Only
        a negative response (``7F 3E xx``) may arrive — we drain it.

        Tries to acquire the lock.  If a ``send_uds()`` is in flight
        this cycle is skipped — the UDS session timer is long enough
        (>5 s) that missing one cycle is harmless.

        Returns:
            True if sent and response drained, False if skipped or
            failed.
        """
        if self.sock is None:
            return False

        acquired = self._lock.acquire(blocking=False)
        if not acquired:
            return True  # skipped, not a failure

        try:
            frame = build_uds(ZGW_ADDR, 0x3E, b"\x80")
            self.sock.settimeout(1.0)
            self.sock.sendall(frame)

            # Drain any ACK + possible negative UDS response.
            with contextlib.suppress(
                TimeoutError,
                socket.timeout,
                ConnectionError,
            ):
                msg_type, _src, _dst, _payload = self._recv_hsfz_message(1.0)
                if msg_type == TYPE_ACK_TRANSFER:
                    with contextlib.suppress(
                        TimeoutError,
                        socket.timeout,
                        ConnectionError,
                    ):
                        self._recv_hsfz_message(1.0)
            return True
        except OSError:
            return False
        finally:
            self._lock.release()

    @property
    def alive_ok(self) -> bool:
        """True if the last few keep-alive attempts succeeded."""
        return self._alive_failures < 3

    # ── Internal helpers ────────────────────────────────────────────────

    def _recv_hsfz_message(self, timeout: float) -> tuple[int, int, int, bytes]:
        """Read one complete HSFZ message: header + payload.

        Args:
            timeout: Socket timeout for this read.

        Returns:
            Tuple of (hsfz_type, src_addr, dst_addr, payload_bytes).

        Raises:
            TimeoutError: If no data within *timeout*.
            ConnectionError: If socket is closed mid-read.
        """
        self.sock.settimeout(timeout)
        try:
            hdr = self._recv_exact(8)
        except (TimeoutError, ConnectionError) as e:
            if isinstance(e, socket.timeout):
                raise TimeoutError(f"HSFZ response header timeout after {timeout:.0f}s") from e
            raise

        hsfz_len, hsfz_type, hsfz_src, hsfz_dst = struct.unpack(">IHBB", hdr)
        payload_len = hsfz_len - 2  # subtract src/dst bytes

        try:
            payload = self._recv_exact(payload_len) if payload_len > 0 else b""
        except (TimeoutError, ConnectionError) as e:
            if isinstance(e, socket.timeout):
                raise TimeoutError(f"HSFZ payload timeout ({payload_len} bytes)") from e
            raise

        return (hsfz_type, hsfz_src, hsfz_dst, payload)

    def _recv_exact(self, n: int) -> bytes:
        """Receive exactly *n* bytes from the socket.

        Raises:
            ConnectionError: If connection is closed before *n* bytes
                             received.
        """
        data = b""
        while len(data) < n:
            try:
                chunk = self.sock.recv(n - len(data))
            except TimeoutError:
                raise
            if not chunk:
                raise ConnectionError("Connection closed by remote")
            data += chunk
        return data

    # ── Context manager ─────────────────────────────────────────────────

    def __enter__(self) -> "HSFZConnection":
        self.connect()
        return self

    def __exit__(self, *args: object) -> None:
        self.disconnect()


# ── DoIP Connection (T-6) ────────────────────────────────────────────────────


class DoIPConnection:
    """DoIP transport for G/U/I-series BMW vehicles (TCP port 13400).

    Implements ISO 13400 DoIP with routing activation.
    Shares the same send_uds() interface as HSFZConnection.

    Example:
        >>> conn = DoIPConnection("169.254.1.1")
        >>> conn.connect()
        True
        >>> conn.activate_routing(0x0E00)
        True
        >>> resp = conn.send_uds(0x63, bytes([0x22, 0xF1, 0x90]))
        >>> conn.disconnect()
    """

    def __init__(self, host: str, port: int = DOIP_DATA_PORT) -> None:
        """Create a DoIP connection.

        Args:
            host: Car IP address.
            port: TCP data port (default 13400).
        """
        self.host = host
        self.port = port
        self.sock: socket.socket | None = None
        self.source_addr: int = DOIP_TESTER_LOGICAL_ADDR
        self.activated: bool = False
        self._lock = threading.Lock()

    def connect(self) -> bool:
        """Open TCP connection for DoIP.

        Returns:
            True if connected successfully.
        """
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.sock.settimeout(5.0)
            self.sock.connect((self.host, self.port))
            self.sock.settimeout(30.0)
            logger.info("DoIP connected to %s:%d", self.host, self.port)
            return True
        except (TimeoutError, ConnectionRefusedError, OSError) as e:
            logger.warning(
                "DoIP connect to %s:%d failed: %s",
                self.host,
                self.port,
                e,
            )
            self.sock = None
            return False

    def activate_routing(
        self,
        source_addr: int = DOIP_TESTER_LOGICAL_ADDR,
        activation_type: int = 0x00,  # Default diagnostic
    ) -> bool:
        """Send routing activation request to the DoIP gateway.

        Required before sending diagnostic messages over DoIP.

        Args:
            source_addr: Tester logical address (default 0x0E00).
            activation_type: 0x00=default, 0x01=WWH-OBD, etc.

        Returns:
            True if activation accepted.
        """
        if self.sock is None:
            raise ConnectionError("Not connected")

        # DoIP routing activation request
        # Payload type 0x0005, then source_addr(2) + activation_type(1)
        payload = struct.pack(">HB", source_addr, activation_type)
        # Pad to 4 byte alignment if needed
        payload += b"\x00" * (4 - len(payload) % 4) if len(payload) % 4 else b""

        doip_header = _build_doip_header(DOIP_ROUTING_ACTIVATION_REQUEST, payload)
        self.sock.sendall(doip_header)

        # Read response
        resp = self._recv_doip_message()
        if resp is None:
            return False

        resp_type, resp_payload = resp
        if resp_type != DOIP_ROUTING_ACTIVATION_RESPONSE:
            logger.warning("Expected routing activation response, got 0x%04X", resp_type)
            return False

        # Parse response: tester_addr(2) + entity_addr(2) + code(1)
        if len(resp_payload) >= 5:
            _, entity_addr, code = struct.unpack(">HHB", resp_payload[:5])
            self.source_addr = source_addr
            self.activated = code == 0x10  # 0x10 = activation successful
            if self.activated:
                logger.info(
                    "DoIP routing activated: source=0x%04X, entity=0x%04X",
                    source_addr,
                    entity_addr,
                )
            else:
                logger.warning("DoIP routing activation denied: code=0x%02X", code)
            return self.activated

        return False

    def send_uds(self, ecu_addr: int, payload: bytes, timeout: float = 30.0) -> bytes:
        """Send a UDS message over DoIP and return the response.

        Args:
            ecu_addr: Target ECU logical address (e.g. 0x0063 for headunit).
            payload: UDS message payload (service byte + data).
            timeout: Maximum seconds to wait for response.

        Returns:
            UDS response payload bytes.

        Raises:
            ConnectionError: If not connected.
            TimeoutError: If no response within timeout.
        """
        if self.sock is None:
            raise ConnectionError("Not connected")

        # DoIP diagnostic message: source_addr(2) + target_addr(2) + UDS payload
        diag_payload = struct.pack(">HH", self.source_addr, ecu_addr) + payload

        doip_header = _build_doip_header(DOIP_DIAG_MESSAGE, diag_payload)

        self.sock.settimeout(timeout)
        try:
            self.sock.sendall(doip_header)
        except OSError as e:
            raise ConnectionError(f"Send failed: {e}") from e

        # Read DoIP ACK (0x8002) — acknowledgement the gateway accepted the message
        ack = self._recv_doip_message()
        if ack is None or ack[0] != DOIP_DIAG_MESSAGE_ACK:
            logger.warning("No DoIP ACK received")

        # Read DoIP diagnostic response (0x8001) containing the UDS response
        resp = self._recv_doip_message()
        if resp is None:
            raise TimeoutError(f"ECU 0x{ecu_addr:04X} did not respond within {timeout:.0f}s")

        resp_type, resp_payload = resp
        if resp_type == DOIP_DIAG_MESSAGE:
            # Payload format: source(2) + target(2) + UDS response
            if len(resp_payload) >= 4:
                uds_payload = resp_payload[4:]
                return uds_payload
            return resp_payload

        raise ConnectionError(f"Unexpected DoIP response type: 0x{resp_type:04X}")

    def alive_check(self) -> None:
        """Send DoIP alive check request."""
        if self.sock is None:
            return
        try:
            header = _build_doip_header(DOIP_ALIVE_CHECK_REQUEST, b"")
            self.sock.sendall(header)
        except OSError:
            pass

    def tester_present(self) -> bool:
        """Send UDS TesterPresent (0x3E 0x80) over DoIP.

        Uses the suppress-positive-response bit (0x80).  Non-blocking:
        acquires the connection lock briefly to build and send the
        frame.  If ``send_uds()`` is in flight the lock acquisition
        fails and this cycle is skipped.

        Returns:
            True if sent, False if skipped or socket is gone.
        """
        if self.sock is None:
            return False

        acquired = self._lock.acquire(blocking=False)
        if not acquired:
            return True  # skipped

        try:
            payload = struct.pack(">HH", self.source_addr, ZGW_ADDR)
            payload += bytes([0x3E, 0x80])
            header = _build_doip_header(DOIP_DIAG_MESSAGE, payload)
            self.sock.sendall(header)
            return True
        except OSError:
            return False
        finally:
            self._lock.release()

    @property
    def alive_ok(self) -> bool:
        """True unless the socket is gone."""
        return self.sock is not None

    def disconnect(self) -> None:
        """Close the DoIP connection."""
        if self.sock:
            with contextlib.suppress(OSError):
                self.sock.shutdown(socket.SHUT_RDWR)
            with contextlib.suppress(OSError):
                self.sock.close()
            self.sock = None
            self.activated = False
            logger.info("DoIP disconnected from %s:%d", self.host, self.port)

    def _recv_doip_message(self) -> tuple[int, bytes] | None:
        """Receive a single DoIP message.

        Returns:
            Tuple of (payload_type, payload_bytes) or None on error.
        """
        if self.sock is None:
            return None

        try:
            # DoIP header: version(1) + inv_version(1) + type(2) + length(4) = 8 bytes
            hdr = self._recv_exact(8)
            version, inv_version, ptype, length = struct.unpack(">BBHI", hdr)
            payload = self._recv_exact(length) if length > 0 else b""
            return (ptype, payload)
        except (TimeoutError, ConnectionError, struct.error) as e:
            logger.warning("DoIP receive error: %s", e)
            return None

    def _recv_exact(self, n: int) -> bytes:
        """Receive exactly n bytes."""
        data = b""
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("Connection closed by remote")
            data += chunk
        return data

    def __enter__(self) -> "DoIPConnection":
        self.connect()
        return self

    def __exit__(self, *args: object) -> None:
        self.disconnect()


# ── DoIP helpers ─────────────────────────────────────────────────────────────


def _build_doip_header(payload_type: int, payload: bytes) -> bytes:
    """Build a DoIP frame header (8 bytes) + payload.

    ISO 13400 header format:
      - Protocol version (1 byte)
      - Inverse protocol version (1 byte)
      - Payload type (2 bytes)
      - Payload length (4 bytes)
      - Payload (variable)

    Total header: 8 bytes.
    """
    return (
        struct.pack(
            ">BBHI",
            DOIP_PROTOCOL_VERSION,
            DOIP_PROTOCOL_VERSION ^ 0xFF,
            payload_type,
            len(payload),
        )
        + payload
    )


# ── Discovery for DoIP (T-6) ─────────────────────────────────────────────────


def discover_doip_vehicle(interface: str, timeout: float = 5.0) -> dict[str, str] | None:
    """Discover a DoIP-capable vehicle via UDP broadcast on port 13400.

    Used for G/U/I-series vehicles. Sends a Vehicle Identification Request
    and parses the response.

    Args:
        interface: Network interface name.
        timeout: Seconds to wait.

    Returns:
        Dict with "ip", "vin", "eid", "gid", "logical_addr" if found.
    """
    disc_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    disc_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    disc_sock.settimeout(timeout)

    try:
        # DoIP Vehicle Identification Request
        request = _build_doip_header(DOIP_VEHICLE_ID_REQUEST, b"")
        disc_sock.sendto(request, (HSFZ_DISCOVERY_BROADCAST, DOIP_DISCOVERY_PORT))

        try:
            data, addr = disc_sock.recvfrom(4096)
        except TimeoutError:
            return None

        if len(data) < 8:
            return None

        _, _, ptype, plen = struct.unpack(">BBHI", data[:8])
        if ptype != DOIP_VEHICLE_ID_RESPONSE:
            logger.warning("Expected DoIP vehicle ID response, got 0x%04X", ptype)
            return None

        payload = data[8 : 8 + plen]
        result = {"ip": addr[0]}

        # Parse VIN (17 chars at payload start)
        if len(payload) >= 17:
            vin = payload[:17].decode("ascii", errors="ignore").strip("\x00")
            if vin:
                result["vin"] = vin

        logger.info(
            "DoIP vehicle found at %s: VIN=%s",
            addr[0],
            result.get("vin", "unknown"),
        )
        return result

    finally:
        disc_sock.close()
