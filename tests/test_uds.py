"""Tests for app.uds — UDS message building and parsing."""

import pytest
from app.uds import (
    build_uds,
    parse_uds_response,
    is_negative_response,
    get_negative_code,
    build_uds_payload,
    TESTER_ADDR,
    TYPE_DIAG_REQ_RES,
    UDS_NEGATIVE_RESPONSE,
    NRC_SERVICE_NOT_SUPPORTED,
    NRC_REQUEST_OUT_OF_RANGE,
)


# ── build_uds ────────────────────────────────────────────────────────────────

def test_build_uds_read_vin():
    """build_uds(0x63, 0x22, F190) produces valid HSFZ-framed VIN request."""
    msg = build_uds(0x63, 0x22, bytes([0xF1, 0x90]))
    # 8-byte HSFZ header + 3-byte UDS payload = 11 bytes
    assert len(msg) == 11

    # HSFZ header fields
    import struct
    hsfz_len, hsfz_type, hsfz_src, hsfz_dst = struct.unpack(">IHBB", msg[:8])

    # Length field = UDS payload (3) + 2 = 5
    assert hsfz_len == 5
    assert hsfz_type == TYPE_DIAG_REQ_RES  # 0x0001
    assert hsfz_src == TESTER_ADDR  # 0xF4
    assert hsfz_dst == 0x63  # headunit

    # UDS payload
    assert msg[8] == 0x22  # ReadDataByIdentifier
    assert msg[9] == 0xF1
    assert msg[10] == 0x90


def test_build_uds_diag_session():
    """build_uds with DiagnosticSessionControl (0x10 0x03)."""
    msg = build_uds(0x10, 0x10, bytes([0x03]))
    assert len(msg) == 10  # 8 header + 2 UDS

    import struct
    hsfz_len, hsfz_type, hsfz_src, hsfz_dst = struct.unpack(">IHBB", msg[:8])
    assert hsfz_len == 4  # UDS 2 + 2
    assert hsfz_type == 0x0001
    assert hsfz_src == 0xF4
    assert hsfz_dst == 0x10
    assert msg[8] == 0x10
    assert msg[9] == 0x03


def test_build_uds_empty_payload():
    """build_uds with no extra payload (service-only message like TesterPresent)."""
    msg = build_uds(0x10, 0x3E, bytes([0x00]))
    import struct
    hsfz_len, _, _, _ = struct.unpack(">IHBB", msg[:8])
    assert hsfz_len == 4  # 2-byte UDS + 2


# ── parse_uds_response ──────────────────────────────────────────────────────

def test_parse_positive_response():
    """parse_uds_response on positive ReadDataByIdentifier response."""
    # 62 F1 90 57 42 41 ... (positive response to 22 F1 90)
    data = bytes([0x62, 0xF1, 0x90, 0x57, 0x42, 0x41])
    sid, payload = parse_uds_response(data)
    assert sid == 0x62
    assert payload == bytes([0xF1, 0x90, 0x57, 0x42, 0x41])


def test_parse_negative_response():
    """parse_uds_response on a negative response returns (0x7F, error_bytes)."""
    data = bytes([0x7F, 0x22, 0x11])
    sid, payload = parse_uds_response(data)
    assert sid == 0x7F
    assert payload == bytes([0x22, 0x11])


def test_parse_empty_response():
    """parse_uds_response on empty data raises ValueError."""
    with pytest.raises(ValueError, match="empty"):
        parse_uds_response(b"")


# ── is_negative_response ────────────────────────────────────────────────────

def test_is_negative_true():
    """7F 22 11 is a negative response."""
    assert is_negative_response(bytes([0x7F, 0x22, 0x11])) is True


def test_is_negative_false():
    """62 F1 90 is not a negative response."""
    assert is_negative_response(bytes([0x62, 0xF1, 0x90])) is False


def test_is_negative_empty():
    """Empty data is not a negative response."""
    assert is_negative_response(b"") is False


# ── get_negative_code ───────────────────────────────────────────────────────

def test_get_negative_code_service_not_supported():
    """Extract NRC 0x11 (serviceNotSupported) from negative response."""
    data = bytes([0x7F, 0x22, 0x11])
    assert get_negative_code(data) == NRC_SERVICE_NOT_SUPPORTED


def test_get_negative_code_out_of_range():
    """Extract NRC 0x31 (requestOutOfRange)."""
    data = bytes([0x7F, 0x22, 0x31])
    assert get_negative_code(data) == NRC_REQUEST_OUT_OF_RANGE


def test_get_negative_code_wrong_sid():
    """get_negative_code on non-negative response raises ValueError."""
    with pytest.raises(ValueError, match="Not a negative response"):
        get_negative_code(bytes([0x62, 0xF1, 0x90]))


def test_get_negative_code_too_short():
    """get_negative_code on too-short data raises ValueError."""
    with pytest.raises(ValueError, match="too short"):
        get_negative_code(bytes([0x7F]))


# ── build_uds_payload ───────────────────────────────────────────────────────

def test_build_uds_payload():
    """build_uds_payload builds just the UDS portion without framing."""
    result = build_uds_payload(0x22, bytes([0xF1, 0x90]))
    assert result == bytes([0x22, 0xF1, 0x90])


def test_build_uds_payload_no_extra():
    """build_uds_payload with no extra payload works for single-byte messages."""
    result = build_uds_payload(0x10, bytes([0x03]))
    assert result == bytes([0x10, 0x03])