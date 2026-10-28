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
import uuid
from dataclasses import dataclass

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
        logger.debug("Discovery TX local=%s data=%s", disc_sock.getsockname(), request.hex(" "))

        try:
            data, addr = disc_sock.recvfrom(1024)
        except TimeoutError:
            logger.debug("Vehicle discovery timed out after %.1fs", timeout)
            return None

        logger.debug("Discovery RX peer=%s bytes=%d data=%s", addr, len(data), data.hex(" "))
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


# ── Stream helpers ───────────────────────────────────────────────────────────

MAX_FRAME_BODY = 16 * 1024 * 1024


class _DeadlineExpired(TimeoutError):
    """Budget elapsed before initiating the next socket operation."""


def _check_read_only(payload: bytes) -> None:
    """Allow existing read services plus default/extended session maintenance.

    This is a service boundary, not evidence that a BMW-specific DID/decoder is
    supported. RoutineControl, security access, writes, reset and clears fail
    closed before any socket activity.
    """
    sid = payload[0]
    allowed = sid in (0x01, 0x19, 0x1A, 0x22)
    if sid == 0x10:
        allowed = len(payload) == 2 and payload[1] in (0x01, 0x03)
    elif sid == 0x3E:
        allowed = len(payload) == 2 and payload[1] in (0x00, 0x80)
    if not allowed:
        logger.warning("READ ONLY blocked request before send: %s", payload.hex(" "))
        raise PermissionError("This operation is disabled in the read-only session")


def _remaining(deadline: float) -> float:
    """Return the remaining operation budget without extending its deadline."""
    remaining = deadline - _time.monotonic()
    if remaining <= 0:
        raise _DeadlineExpired("Vehicle operation timed out")
    return remaining


def _fill_receive_buffer(
    sock: socket.socket, buffer: bytearray, size: int, deadline: float, trace_id: str
) -> None:
    """Retain every received fragment, including when a short poll times out."""
    while len(buffer) < size:
        sock.settimeout(_remaining(deadline))
        try:
            chunk = sock.recv(size - len(buffer))
        except TimeoutError:
            logger.debug(
                "RX poll/deadline conn=%s retained=%d target=%d", trace_id, len(buffer), size
            )
            raise
        logger.debug(
            "RX fragment conn=%s bytes=%d retained=%d target=%d data=%s",
            trace_id,
            len(chunk),
            len(buffer) + len(chunk),
            size,
            chunk.hex(" "),
        )
        if not chunk:
            raise ConnectionError("Connection closed by vehicle")
        buffer.extend(chunk)


def _matches_uds(request: bytes, response: bytes) -> bool:
    """Match standard response identity; leave ECU-specific body decoding to callers."""
    if not response:
        return False
    if response[0] == 0x7F:
        return len(response) >= 3 and response[1] == request[0]
    if response[0] != request[0] + 0x40:
        return False
    if request[0] in (0x22, 0x2E):
        return len(response) >= 3 and response[1:3] == request[1:3]
    if request[0] == 0x31:
        return (
            len(request) >= 4
            and len(response) >= 4
            and response[1] == request[1] & 0x7F
            and response[2:4] == request[2:4]
        )
    if request[0] == 0x01:
        return len(request) >= 2 and len(response) >= 2 and response[1] == request[1]
    if request[0] in (0x10, 0x19, 0x27, 0x3E):
        return len(request) >= 2 and len(response) >= 2 and response[1] == request[1] & 0x7F
    return True


# ── HSFZ transport ───────────────────────────────────────────────────────────


class HSFZConnection:
    """Serialized HSFZ transactions with buffered control-frame handling.

    Keepalive results are True for a completed send/drain, None when another
    transaction owns the stream, and False for an actual transport failure.
    These results do not certify ECU session state or vehicle write success.
    """

    def __init__(self, host: str, port: int = HSFZ_DATA_PORT, *, read_only: bool = False) -> None:
        """Create a transport for the selected gateway."""
        self.host = host
        self.port = port
        self.read_only = read_only
        self.trace_id = uuid.uuid4().hex[:12]
        self.sock: socket.socket | None = None
        self._lock = threading.Lock()
        self._alive_failures = 0
        self._receive_buffer = bytearray()
        self._pending_request: tuple[int, bytes] | None = None

    def connect(self) -> bool:
        """Connect to the gateway, releasing the socket on failure."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.settimeout(5.0)
            sock.connect((self.host, self.port))
        except OSError:
            sock.close()
            logger.warning("HSFZ connect failed: %s:%d", self.host, self.port, exc_info=True)
            return False
        logger.info(
            "TCP connected transport=HSFZ conn=%s local=%s peer=%s read_only=%s",
            self.trace_id,
            sock.getsockname(),
            sock.getpeername(),
            self.read_only,
        )
        self.sock = sock
        self._receive_buffer.clear()
        self._pending_request = None
        self._alive_failures = 0
        return True

    def disconnect(self) -> None:
        """Interrupt in-flight I/O before locking to release the captured socket."""
        sock = self.sock
        if sock is not None:
            with contextlib.suppress(OSError):
                sock.shutdown(socket.SHUT_RDWR)
        with self._lock:
            if self.sock is sock:
                self._close_locked()

    def _close_locked(self) -> None:
        """Close the owned stream and clear transaction state while holding its lock."""
        if self.sock is not None:
            logger.info(
                "TCP closing conn=%s retained=%d pending=%s",
                self.trace_id,
                len(self._receive_buffer),
                self._pending_request,
            )
            with contextlib.suppress(OSError):
                self.sock.close()
            self.sock = None
        self._receive_buffer.clear()
        self._pending_request = None
        self._alive_failures = 3

    def send_uds(self, ecu_addr: int, payload: bytes, timeout: float = 30.0) -> bytes:
        """Return a matching UDS reply within one queue/send/receive deadline.

        A receive timeout preserves the socket and outstanding request. Before
        another request is sent, its late reply must be consumed within the next
        operation's budget. Requests are never replayed automatically. A transport
        error invalidates the stream; well-framed negative replies do not.
        """
        if not payload:
            raise ValueError("UDS request cannot be empty")
        if self.read_only:
            _check_read_only(payload)
        request_id = uuid.uuid4().hex[:12]
        started = _time.monotonic()
        logger.debug(
            "UDS request begin conn=%s request=%s ecu=0x%04X budget=%.3fs data=%s",
            self.trace_id,
            request_id,
            ecu_addr,
            timeout,
            payload.hex(" "),
        )
        deadline = started + timeout
        frame = build_uds(ecu_addr, payload[0], payload[1:])
        if not self._lock.acquire(timeout=_remaining(deadline)):
            logger.warning(
                "UDS queue timeout conn=%s request=%s budget=%.3fs",
                self.trace_id,
                request_id,
                timeout,
            )
            raise TimeoutError("Vehicle operation timed out waiting for transport")
        try:
            if self.sock is None:
                raise ConnectionError("Not connected")
            try:
                if self._pending_request is not None:
                    logger.debug(
                        "Consume outstanding reply before send conn=%s request=%s old=%s retained=%d",
                        self.trace_id,
                        request_id,
                        self._pending_request,
                        len(self._receive_buffer),
                    )
                    self._read_response(*self._pending_request, deadline)
                try:
                    self.sock.settimeout(_remaining(deadline))
                    self.sock.sendall(frame)
                    logger.debug("HSFZ TX conn=%s frame=%s", self.trace_id, frame.hex(" "))
                except _DeadlineExpired:
                    raise
                except OSError:
                    self._close_locked()  # A partial send cannot safely be retried.
                    raise
                self._pending_request = (ecu_addr, payload)
                logger.debug("UDS tx ECU=0x%02X: %s", ecu_addr, payload.hex(" "))
                return self._read_response(ecu_addr, payload, deadline)
            except TimeoutError:
                logger.warning(
                    "UDS timeout conn=%s request=%s retained=%d pending=%s",
                    self.trace_id,
                    request_id,
                    len(self._receive_buffer),
                    self._pending_request,
                    exc_info=True,
                )
                raise  # Retain buffered bytes and the outstanding request.
            except OSError:
                logger.exception(
                    "UDS transport failure conn=%s request=%s", self.trace_id, request_id
                )
                self._close_locked()
                raise
        finally:
            logger.debug(
                "UDS request end conn=%s request=%s elapsed=%.3fs pending=%s",
                self.trace_id,
                request_id,
                _time.monotonic() - started,
                self._pending_request,
            )
            self._lock.release()

    def _read_response(self, ecu_addr: int, request: bytes, deadline: float) -> bytes:
        while True:
            msg_type, src, dst, response = self._recv_hsfz_message(deadline)
            if msg_type in (TYPE_ACK_TRANSFER, TYPE_ALIVE_CHECK):
                continue
            if msg_type in HSFZ_ERROR_TYPES:
                raise ConnectionError(f"Gateway error: {HSFZ_ERROR_TYPES[msg_type]}")
            if msg_type != TYPE_DIAG_REQ_RES:
                raise ConnectionError(f"Unexpected HSFZ control word: 0x{msg_type:04X}")
            if src != ecu_addr or dst != TESTER_ADDR or not _matches_uds(request, response):
                logger.debug("Ignoring unrelated HSFZ diagnostic reply from 0x%02X", src)
                continue
            logger.debug("UDS rx ECU=0x%02X: %s", src, response.hex(" "))
            if response[:3] == bytes((0x7F, request[0], 0x78)):
                continue
            self._pending_request = None
            self._alive_failures = 0
            return response

    def alive_check(self) -> bool | None:
        """Run the existing HSFZ heartbeat under the stream lock, off the GUI.

        Its vehicle-specific initiation/timing still needs capture validation.
        """
        frame = struct.pack(">IHBB", 2, TYPE_ALIVE_CHECK, TESTER_ADDR, ZGW_ADDR)
        return self._keepalive(frame, 0.05)

    def tester_present(self) -> bool | None:
        """Send suppressed-positive TesterPresent and drain optional replies."""
        return self._keepalive(build_uds(ZGW_ADDR, 0x3E, b"\x80"), 1.0, requires_idle=True)

    def _keepalive(
        self, frame: bytes, receive_timeout: float, *, requires_idle: bool = False
    ) -> bool | None:
        """Send fixed heartbeat traffic and retain fragmented replies under the stream lock."""
        if not self._lock.acquire(blocking=False):
            return None
        try:
            if self.sock is None:
                return False
            if requires_idle and self._pending_request is not None:
                return None
            sent = False
            try:
                self.sock.settimeout(1.0)
                self.sock.sendall(frame)
                logger.debug("HSFZ keepalive TX conn=%s frame=%s", self.trace_id, frame.hex(" "))
                sent = True
                deadline = _time.monotonic() + receive_timeout
                while True:
                    msg_type, src, dst, payload = self._recv_hsfz_message(deadline)
                    if msg_type in HSFZ_ERROR_TYPES:
                        raise ConnectionError(f"Gateway error: {HSFZ_ERROR_TYPES[msg_type]}")
                    if msg_type == TYPE_DIAG_REQ_RES:
                        pending = self._pending_request
                        if (
                            pending is not None
                            and src == pending[0]
                            and dst == TESTER_ADDR
                            and _matches_uds(pending[1], payload)
                            and payload[:3] != bytes((0x7F, pending[1][0], 0x78))
                        ):
                            self._pending_request = None
                        logger.debug("Keepalive UDS reply: %s", payload.hex(" "))
            except TimeoutError:
                # Suppressed positive responses may be absent. Partial frame
                # bytes remain buffered for the next reader under this lock.
                if sent:
                    self._alive_failures = 0
                else:
                    self._alive_failures += 1
                return sent
            except OSError:
                self._alive_failures += 1
                logger.debug("HSFZ keepalive failed", exc_info=True)
                return False
        finally:
            self._lock.release()

    @property
    def alive_ok(self) -> bool:
        """Whether the socket remains usable without repeated keepalive failures."""
        return self.sock is not None and self._alive_failures < 3

    def _recv_hsfz_message(self, deadline: float) -> tuple[int, int, int, bytes]:
        """Read one bounded HSFZ frame, retaining partial bytes when the deadline expires."""
        sock = self.sock
        if sock is None:
            raise ConnectionError("Not connected")
        buffer = self._receive_buffer
        _fill_receive_buffer(sock, buffer, 6, deadline, self.trace_id)
        length, control = struct.unpack(">IH", buffer[:6])
        if length > MAX_FRAME_BODY:
            raise ConnectionError("HSFZ frame exceeds supported size")
        addressed = control in (TYPE_DIAG_REQ_RES, TYPE_ACK_TRANSFER) or (
            control == TYPE_ALIVE_CHECK and length == 2
        )
        if addressed and length < 2:
            raise ConnectionError("HSFZ address fields are truncated")
        _fill_receive_buffer(sock, buffer, 6 + length, deadline, self.trace_id)
        logger.debug(
            "HSFZ RX conn=%s control=0x%04X length=%d frame=%s",
            self.trace_id,
            control,
            length,
            buffer[: 6 + length].hex(" "),
        )
        body = bytes(buffer[6 : 6 + length])
        del buffer[: 6 + length]
        if addressed:
            return control, body[0], body[1], body[2:]
        return control, 0, 0, body

    def __enter__(self) -> "HSFZConnection":
        self.connect()
        return self

    def __exit__(self, *args: object) -> None:
        self.disconnect()


# ── DoIP transport ───────────────────────────────────────────────────────────


class DoIPConnection:
    """Serialized DoIP control/diagnostic exchanges with explicit health results."""

    def __init__(self, host: str, port: int = DOIP_DATA_PORT, *, read_only: bool = False) -> None:
        """Create a transport for the selected DoIP entity."""
        self.host = host
        self.port = port
        self.read_only = read_only
        self.trace_id = uuid.uuid4().hex[:12]
        self.sock: socket.socket | None = None
        self.source_addr = DOIP_TESTER_LOGICAL_ADDR
        self.activated = False
        self._lock = threading.Lock()
        self._alive_failures = 0
        self._receive_buffer = bytearray()
        self._pending_request: tuple[int, bytes] | None = None

    def connect(self) -> bool:
        """Connect TCP; routing activation is required before diagnostic sends."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.settimeout(5.0)
            sock.connect((self.host, self.port))
        except OSError:
            sock.close()
            logger.warning("DoIP connect failed: %s:%d", self.host, self.port, exc_info=True)
            return False
        logger.info(
            "TCP connected transport=DoIP conn=%s local=%s peer=%s read_only=%s",
            self.trace_id,
            sock.getsockname(),
            sock.getpeername(),
            self.read_only,
        )
        self.sock = sock
        self.activated = False
        self._receive_buffer.clear()
        self._pending_request = None
        self._alive_failures = 0
        return True

    def activate_routing(
        self, source_addr: int = DOIP_TESTER_LOGICAL_ADDR, activation_type: int = 0x00
    ) -> bool:
        """Activate routing with the seven-byte standard request payload."""
        deadline = _time.monotonic() + 5.0
        if not self._lock.acquire(timeout=_remaining(deadline)):
            raise TimeoutError("Routing activation timed out waiting for transport")
        try:
            if self.sock is None:
                raise ConnectionError("Not connected")
            self.activated = False
            self.source_addr = source_addr
            self._send_doip(
                DOIP_ROUTING_ACTIVATION_REQUEST,
                struct.pack(">HBI", source_addr, activation_type, 0),
                deadline,
            )
            while True:
                kind, payload = self._recv_doip_message(deadline)
                if self._handle_control(kind, payload, deadline):
                    continue
                if kind != DOIP_ROUTING_ACTIVATION_RESPONSE or len(payload) < 9:
                    raise ConnectionError("Invalid DoIP routing activation response")
                tester, _entity, code = struct.unpack(">HHB", payload[:5])
                self.activated = tester == source_addr and code == 0x10
                return self.activated
        except OSError:
            self._close_locked()
            raise
        finally:
            self._lock.release()

    def send_uds(self, ecu_addr: int, payload: bytes, timeout: float = 30.0) -> bytes:
        """Read through control frames until a correlated diagnostic reply arrives."""
        if not payload:
            raise ValueError("UDS request cannot be empty")
        if self.read_only:
            _check_read_only(payload)
        request_id = uuid.uuid4().hex[:12]
        started = _time.monotonic()
        logger.debug(
            "UDS request begin conn=%s request=%s ecu=0x%04X budget=%.3fs data=%s",
            self.trace_id,
            request_id,
            ecu_addr,
            timeout,
            payload.hex(" "),
        )
        deadline = started + timeout
        if not self._lock.acquire(timeout=_remaining(deadline)):
            logger.warning(
                "UDS queue timeout conn=%s request=%s budget=%.3fs",
                self.trace_id,
                request_id,
                timeout,
            )
            raise TimeoutError("Vehicle operation timed out waiting for transport")
        try:
            if self.sock is None or not self.activated:
                raise ConnectionError("DoIP routing is not active")
            try:
                if self._pending_request is not None:
                    logger.debug(
                        "Consume outstanding reply before send conn=%s request=%s old=%s retained=%d",
                        self.trace_id,
                        request_id,
                        self._pending_request,
                        len(self._receive_buffer),
                    )
                    self._read_response(*self._pending_request, deadline)
                try:
                    self._send_doip(
                        DOIP_DIAG_MESSAGE,
                        struct.pack(">HH", self.source_addr, ecu_addr) + payload,
                        deadline,
                    )
                except _DeadlineExpired:
                    raise
                except OSError:
                    self._close_locked()
                    raise
                self._pending_request = (ecu_addr, payload)
                logger.debug("UDS tx ECU=0x%04X: %s", ecu_addr, payload.hex(" "))
                return self._read_response(ecu_addr, payload, deadline)
            except TimeoutError:
                logger.warning(
                    "UDS timeout conn=%s request=%s retained=%d pending=%s",
                    self.trace_id,
                    request_id,
                    len(self._receive_buffer),
                    self._pending_request,
                    exc_info=True,
                )
                raise
            except OSError:
                logger.exception(
                    "UDS transport failure conn=%s request=%s", self.trace_id, request_id
                )
                self._close_locked()
                raise
        finally:
            logger.debug(
                "UDS request end conn=%s request=%s elapsed=%.3fs pending=%s",
                self.trace_id,
                request_id,
                _time.monotonic() - started,
                self._pending_request,
            )
            self._lock.release()

    def _read_response(self, ecu_addr: int, request: bytes, deadline: float) -> bytes:
        while True:
            kind, body = self._recv_doip_message(deadline)
            if self._handle_control(kind, body, deadline):
                continue
            if kind != DOIP_DIAG_MESSAGE or len(body) < 5:
                raise ConnectionError("Invalid DoIP diagnostic response")
            src, dst = struct.unpack(">HH", body[:4])
            response = body[4:]
            if src != ecu_addr or dst != self.source_addr or not _matches_uds(request, response):
                logger.debug("Ignoring unrelated DoIP diagnostic reply from 0x%04X", src)
                continue
            logger.debug("UDS rx ECU=0x%04X: %s", src, response.hex(" "))
            if response[:3] == bytes((0x7F, request[0], 0x78)):
                continue
            self._pending_request = None
            self._alive_failures = 0
            return response

    def alive_check(self) -> bool | None:
        """Poll gateway control traffic and answer its alive-check requests.

        None means idle or skipped; an idle poll alone is not proof of liveness.
        """
        return self._keepalive(send_tester_present=False)

    def tester_present(self) -> bool | None:
        """Send suppressed-positive TesterPresent and consume its transport ACK."""
        return self._keepalive(send_tester_present=True)

    def _keepalive(self, *, send_tester_present: bool) -> bool | None:
        """Send fixed heartbeat traffic and retain fragmented replies under the stream lock."""
        if not self._lock.acquire(blocking=False):
            return None
        try:
            if self.sock is None or not self.activated:
                return False
            if send_tester_present and self._pending_request is not None:
                return None
            sent = False
            deadline = _time.monotonic() + (1.0 if send_tester_present else 0.05)
            try:
                if send_tester_present:
                    body = struct.pack(">HH", self.source_addr, ZGW_ADDR) + b"\x3e\x80"
                    self._send_doip(DOIP_DIAG_MESSAGE, body, deadline)
                    sent = True
                while True:
                    try:
                        kind, body = self._recv_doip_message(deadline)
                    except TimeoutError:
                        if not sent:
                            return None  # Idle polls are not failed transmissions.
                        self._alive_failures += 1
                        return False
                    if self._handle_control(kind, body, deadline):
                        self._alive_failures = 0
                        if sent and kind == DOIP_DIAG_MESSAGE_ACK:
                            self._alive_failures = 0
                            return True
                        continue
                    if kind != DOIP_DIAG_MESSAGE or len(body) < 5:
                        raise ConnectionError("Unexpected DoIP keepalive frame")
                    src, dst = struct.unpack(">HH", body[:4])
                    response = body[4:]
                    pending = self._pending_request
                    if (
                        pending is not None
                        and src == pending[0]
                        and dst == self.source_addr
                        and _matches_uds(pending[1], response)
                        and response[:3] != bytes((0x7F, pending[1][0], 0x78))
                    ):
                        self._pending_request = None
                    self._alive_failures = 0
                    logger.debug("Keepalive UDS reply: %s", response.hex(" "))
            except OSError:
                self._alive_failures += 1
                logger.debug("DoIP keepalive failed", exc_info=True)
                return False
        finally:
            self._lock.release()

    @property
    def alive_ok(self) -> bool:
        """Whether transport operations have avoided repeated actual failures."""
        return self.sock is not None and self._alive_failures < 3

    def disconnect(self) -> None:
        """Unblock I/O before taking ownership of socket cleanup."""
        sock = self.sock
        if sock is not None:
            with contextlib.suppress(OSError):
                sock.shutdown(socket.SHUT_RDWR)
        with self._lock:
            if self.sock is sock:
                self._close_locked()

    def _close_locked(self) -> None:
        """Close the owned stream and clear transaction state while holding its lock."""
        if self.sock is not None:
            logger.info(
                "TCP closing conn=%s retained=%d pending=%s",
                self.trace_id,
                len(self._receive_buffer),
                self._pending_request,
            )
            with contextlib.suppress(OSError):
                self.sock.close()
            self.sock = None
        self.activated = False
        self._receive_buffer.clear()
        self._pending_request = None
        self._alive_failures = 3

    def _send_doip(self, kind: int, payload: bytes, deadline: float) -> None:
        # Guard the final TCP send as well as the public UDS entry point.
        # Routing activation and alive responses maintain transport only.
        """Enforce read-only message policy before sending a DoIP frame on the owned socket."""
        if self.read_only:
            if kind == DOIP_DIAG_MESSAGE:
                if len(payload) < 5:
                    raise ValueError("DoIP diagnostic request is missing addresses or UDS payload")
                _check_read_only(payload[4:])
            elif kind not in (DOIP_ROUTING_ACTIVATION_REQUEST, DOIP_ALIVE_CHECK_RESPONSE):
                logger.warning("READ ONLY blocked DoIP message type=0x%04X", kind)
                raise PermissionError("This DoIP message is disabled in the read-only session")
        if self.sock is None:
            raise ConnectionError("Not connected")
        self.sock.settimeout(_remaining(deadline))
        frame = _build_doip_header(kind, payload)
        self.sock.sendall(frame)
        logger.debug("DoIP TX conn=%s type=0x%04X frame=%s", self.trace_id, kind, frame.hex(" "))

    def _handle_control(self, kind: int, body: bytes, deadline: float) -> bool:
        if kind == DOIP_ALIVE_CHECK_REQUEST:
            if body:
                raise ConnectionError("Invalid DoIP alive-check request")
            self._send_doip(
                DOIP_ALIVE_CHECK_RESPONSE, struct.pack(">H", self.source_addr), deadline
            )
            return True
        if kind in (DOIP_DIAG_MESSAGE_ACK, DOIP_DIAG_MESSAGE_NACK):
            if len(body) < 5:
                raise ConnectionError("Truncated DoIP diagnostic acknowledgement")
            _source, target, code = struct.unpack(">HHB", body[:5])
            if target != self.source_addr or kind == DOIP_DIAG_MESSAGE_NACK or code != 0:
                raise ConnectionError(f"DoIP diagnostic acknowledgement rejected: 0x{code:02X}")
            return True
        if kind == 0x0000:
            raise ConnectionError("DoIP header rejected by vehicle")
        return False

    def _recv_doip_message(self, deadline: float) -> tuple[int, bytes]:
        """Read and validate a complete DoIP frame within the current operation deadline."""
        sock = self.sock
        if sock is None:
            raise ConnectionError("Not connected")
        buffer = self._receive_buffer
        _fill_receive_buffer(sock, buffer, 8, deadline, self.trace_id)
        version, inverse, kind, length = struct.unpack(">BBHI", buffer[:8])
        if version != DOIP_PROTOCOL_VERSION or inverse != version ^ 0xFF:
            raise ConnectionError("Invalid DoIP protocol version")
        if length > MAX_FRAME_BODY:
            raise ConnectionError("DoIP frame exceeds supported size")
        _fill_receive_buffer(sock, buffer, 8 + length, deadline, self.trace_id)
        logger.debug(
            "DoIP RX conn=%s type=0x%04X length=%d frame=%s",
            self.trace_id,
            kind,
            length,
            buffer[: 8 + length].hex(" "),
        )
        body = bytes(buffer[8 : 8 + length])
        del buffer[: 8 + length]
        return kind, body

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
