"""Tests for app.connection - HSFZ, DoIP, interface detection, DHCP.

Tests use mock sockets to avoid needing a real car.
"""

import socket
import struct
from unittest.mock import patch, MagicMock

import pytest

from app.connection import (
    list_interfaces,
    discover_zgw,
    HSFZConnection,
    DoIPConnection,
    HSFZ_DATA_PORT,
    DOIP_DATA_PORT,
    TYPE_DIAG_REQ_RES,
    ZGW_ADDR,
    _build_doip_header,
    DOIP_DIAG_MESSAGE,
    DOIP_DIAG_MESSAGE_ACK,
)
from app.uds import TESTER_ADDR


# ---- T-4: Interface detection -------------------------------------------------


def test_list_interfaces_returns_list():
    """list_interfaces() returns a list of interface names."""
    ifaces = list_interfaces()
    assert isinstance(ifaces, list)
    import platform
    if platform.system() == "Darwin":
        assert any(i.startswith("en") for i in ifaces), (
            f"Expected at least one 'enX' interface on macOS, got {ifaces}"
        )


def test_list_interfaces_no_loopback():
    """list_interfaces() filters out loopback."""
    ifaces = list_interfaces()
    assert "lo0" not in ifaces


# ---- T-5: HSFZConnection with mock socket ------------------------------------


class MockSocket:
    """Simulates a TCP socket for HSFZ testing."""

    def __init__(self, expected_response=b""):
        self.sent_data = b""
        self.expected_response = expected_response
        self._closed = False

    def setsockopt(self, level, optname, value):
        pass

    def settimeout(self, timeout):
        pass

    def connect(self, address):
        pass

    def sendall(self, data):
        self.sent_data += data

    def recv(self, bufsize):
        if self._closed:
            return b""
        if not self.expected_response:
            return b""
        chunk = self.expected_response[:bufsize]
        self.expected_response = self.expected_response[bufsize:]
        return chunk

    def close(self):
        self._closed = True


def test_hsfz_connect():
    """HSFZConnection.connect() creates and connects a TCP socket."""
    conn = HSFZConnection("169.254.1.1")
    with patch("socket.socket") as mock_socket_class:
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        result = conn.connect()
        assert result is True
        mock_sock.settimeout.assert_called()
        mock_sock.connect.assert_called_with(("169.254.1.1", HSFZ_DATA_PORT))


def test_hsfz_send_uds():
    """HSFZConnection.send_uds() builds correct HSFZ frame and parses response."""
    uds_response = bytes([0x62, 0xF1, 0x90]) + bytes(range(17))
    hsfz_len = len(uds_response) + 2
    hsfz_response = struct.pack(
        ">IHBB", hsfz_len, TYPE_DIAG_REQ_RES, 0x63, TESTER_ADDR
    ) + uds_response
    conn = HSFZConnection("169.254.1.1")
    mock_sock = MockSocket(hsfz_response)
    conn.sock = mock_sock
    resp = conn.send_uds(0x63, bytes([0x22, 0xF1, 0x90]))
    assert len(mock_sock.sent_data) >= 8
    hdr = mock_sock.sent_data[:8]
    hsfz_len_out, hsfz_type, hsfz_src, hsfz_dst = struct.unpack(">IHBB", hdr)
    assert hsfz_type == TYPE_DIAG_REQ_RES
    assert hsfz_src == TESTER_ADDR
    assert hsfz_dst == 0x63
    assert hsfz_len_out == 5
    assert mock_sock.sent_data[8:] == bytes([0x22, 0xF1, 0x90])
    assert resp == uds_response


def test_hsfz_send_uds_not_connected():
    """HSFZConnection.send_uds() raises ConnectionError when not connected."""
    conn = HSFZConnection("169.254.1.1")
    with pytest.raises(ConnectionError, match="Not connected"):
        conn.send_uds(0x63, bytes([0x22, 0xF1, 0x90]))


def test_hsfz_disconnect():
    """HSFZConnection.disconnect() closes the socket."""
    conn = HSFZConnection("169.254.1.1")
    mock_sock = MagicMock()
    conn.sock = mock_sock
    conn.disconnect()
    mock_sock.close.assert_called_once()
    assert conn.sock is None


def test_hsfz_alive_check():
    """HSFZConnection.alive_check() sends keep-alive frame."""
    conn = HSFZConnection("169.254.1.1")
    mock_sock = MagicMock()
    conn.sock = mock_sock
    conn.alive_check()
    mock_sock.sendall.assert_called_once()
    sent = mock_sock.sendall.call_args[0][0]
    hsfz_len, hsfz_type, hsfz_src, hsfz_dst = struct.unpack(">IHBB", sent)
    assert hsfz_len == 2
    assert hsfz_type == 0x0012
    assert hsfz_src == TESTER_ADDR
    assert hsfz_dst == ZGW_ADDR


# ---- T-6: DoIP header --------------------------------------------------------


def test_build_doip_header():
    """_build_doip_header() produces a valid 8-byte DoIP header."""
    payload = bytes([0x22, 0xF1, 0x90])
    frame = _build_doip_header(DOIP_DIAG_MESSAGE, payload)
    version, inv_version, ptype, length = struct.unpack(">BBHI", frame[:8])
    assert version == 0x02
    assert inv_version == 0x02 ^ 0xFF
    assert ptype == DOIP_DIAG_MESSAGE
    assert length == len(payload)
    assert frame[8:] == payload


def test_build_doip_header_empty():
    """_build_doip_header() with empty payload returns 8 bytes."""
    frame = _build_doip_header(DOIP_DIAG_MESSAGE_ACK, b"")
    _, _, _, length = struct.unpack(">BBHI", frame[:8])
    assert length == 0
    assert len(frame) == 8


# ---- T-6: DoIPConnection -----------------------------------------------------


def test_doip_connect():
    """DoIPConnection.connect() creates TCP socket."""
    conn = DoIPConnection("169.254.1.1")
    with patch("socket.socket") as mock_socket_class:
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        result = conn.connect()
        assert result is True
        mock_sock.connect.assert_called_with(("169.254.1.1", DOIP_DATA_PORT))


def test_doip_disconnect():
    """DoIPConnection.disconnect() cleans up."""
    conn = DoIPConnection("169.254.1.1")
    mock_sock = MagicMock()
    conn.sock = mock_sock
    conn.activated = True
    conn.disconnect()
    mock_sock.close.assert_called_once()
    assert conn.sock is None
    assert conn.activated is False


# ---- T-4: Vehicle discovery --------------------------------------------------


def test_discover_zgw_timeout():
    """discover_zgw() returns None on timeout."""
    with patch("socket.socket") as mock_socket_class:
        mock_sock = MagicMock()
        mock_sock.recvfrom.side_effect = socket.timeout()
        mock_socket_class.return_value = mock_sock
        result = discover_zgw("en0", timeout=0.1)
        assert result is None


def test_discover_zgw_response():
    """discover_zgw() parses a valid discovery response."""
    resp_body = b"DIAGADR10BMWMAC0A0B0C0D0E0FBMWVINWBAJG7101XXXXXXX"
    hdr = struct.pack(">IH", len(resp_body), 0x0011)
    response = hdr + resp_body
    with patch("socket.socket") as mock_socket_class:
        mock_sock = MagicMock()
        mock_sock.recvfrom.return_value = (response, ("169.254.1.1", 6811))
        mock_socket_class.return_value = mock_sock
        result = discover_zgw("en0", timeout=1.0)
        assert result is not None
        assert result["ip"] == "169.254.1.1"
        assert result["vin"] == "WBAJG7101XXXXXXX"
        assert result["mac"] == "0A0B0C0D0E0F"