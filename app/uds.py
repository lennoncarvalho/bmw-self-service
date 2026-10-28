"""UDS message building and parsing (ISO 14229).

Pure functions with no network I/O. Unit-testable.
Supports HSFZ framing for F-series BMW vehicles.

Reference: docs/10-hsfz-protocol.md, ISO 14229-5 (UDSonIP).
"""

import struct

# HSFZ constants
TESTER_ADDR: int = 0xF4
TYPE_DIAG_REQ_RES: int = 0x0001

# UDS constants
UDS_NEGATIVE_RESPONSE: int = 0x7F


def build_uds(ecu_addr: int, service: int, payload: bytes = b"") -> bytes:
    """Build a complete HSFZ-framed UDS request message.

    Wraps the UDS message in an 8-byte HSFZ header:
      - 4 bytes: payload length + 2 (big-endian)
      - 2 bytes: message type (0x0001 = diagnostic_req_res)
      - 1 byte:  source address (tester = 0xF4)
      - 1 byte:  target address (ECU)

    Args:
        ecu_addr: Target ECU physical address (e.g. 0x63 for headunit).
        service: UDS service ID (e.g. 0x22 for ReadDataByIdentifier).
        payload: Service-specific data (e.g. identifier bytes after SID).

    Returns:
        Complete HSFZ-framed message ready to send over TCP.

    Example:
        >>> msg = build_uds(0x63, 0x22, bytes([0xF1, 0x90]))
        >>> len(msg)  # 8-byte header + 3-byte UDS payload
        11
        >>> msg[4:6]  # type field
        b'\\x00\\x01'
        >>> msg[6]  # source = tester
        244
        >>> msg[7]  # target = headunit
        99
    """
    uds_msg = bytes([service]) + payload
    hsfz_len = len(uds_msg) + 2  # +2 accounts for src/dst in HSFZ header
    header = struct.pack(">IHBB", hsfz_len, TYPE_DIAG_REQ_RES, TESTER_ADDR, ecu_addr)
    return header + uds_msg


def parse_uds_response(data: bytes) -> tuple[int, bytes]:
    """Parse UDS payload bytes into (service_id, payload).

    For a positive response, service_id is the request SID + 0x40.
    For a negative response, service_id is 0x7F.

    Args:
        data: Raw UDS payload bytes (after stripping HSFZ header).

    Returns:
        Tuple of (service_id, payload_bytes).
        For positive: (0x62, b'\\xf1\\x90...').
        For negative: (0x7F, b'\\x22\\x11').

    Raises:
        ValueError: If data is empty.

    Example:
        >>> parse_uds_response(bytes([0x62, 0xF1, 0x90, 0x57, 0x42, 0x41]))
        (98, b'\\xf1\\x90WBA')
        >>> parse_uds_response(bytes([0x7F, 0x22, 0x11]))
        (127, b'\\x22\\x11')
    """
    if not data:
        raise ValueError("Response data is empty")
    return (data[0], data[1:])


def is_negative_response(data: bytes) -> bool:
    """Check if UDS payload represents a negative response (first byte == 0x7F).

    Args:
        data: Raw UDS payload bytes (after stripping HSFZ header).

    Returns:
        True if the response is a UDS negative response.

    Example:
        >>> is_negative_response(bytes([0x7F, 0x22, 0x11]))
        True
        >>> is_negative_response(bytes([0x62, 0xF1, 0x90]))
        False
    """
    return len(data) > 0 and data[0] == UDS_NEGATIVE_RESPONSE


def get_negative_code(data: bytes) -> int:
    """Extract the NRC (Negative Response Code) from a UDS negative response.

    Args:
        data: Raw UDS payload bytes of a negative response.

    Returns:
        The NRC byte (third byte of the UDS payload).

    Raises:
        ValueError: If data is not a valid negative response.

    Example:
        >>> get_negative_code(bytes([0x7F, 0x22, 0x11]))
        17
        >>> get_negative_code(bytes([0x7F, 0x22, 0x31]))
        49
    """
    if len(data) < 3:
        raise ValueError(f"Negative response too short: expected 3 bytes, got {len(data)}")
    if data[0] != UDS_NEGATIVE_RESPONSE:
        raise ValueError(f"Not a negative response: first byte is 0x{data[0]:02X}, expected 0x7F")
    return data[2]


def build_uds_payload(service: int, payload: bytes = b"") -> bytes:
    """Build a UDS payload without HSFZ framing (service byte + data).

    Useful for testing and for DoIP connections that handle their own framing.

    Args:
        service: UDS service ID.
        payload: Service-specific data.

    Returns:
        UDS message bytes (no HSFZ header).

    Example:
        >>> build_uds_payload(0x22, bytes([0xF1, 0x90]))
        b'"\\xf1\\x90'
    """
    return bytes([service]) + payload


# UDS service ID constants for reference
SID_DIAGNOSTIC_SESSION_CONTROL = 0x10
SID_ECU_RESET = 0x11
SID_CLEAR_DTC = 0x14
SID_READ_DTC = 0x19
SID_READ_DATA_BY_ID = 0x22
SID_READ_MEMORY_BY_ADDRESS = 0x23
SID_SECURITY_ACCESS = 0x27
SID_WRITE_DATA_BY_ID = 0x2E
SID_IO_CONTROL_BY_ID = 0x2F
SID_ROUTINE_CONTROL = 0x31
SID_REQUEST_DOWNLOAD = 0x34
SID_REQUEST_UPLOAD = 0x35
SID_TRANSFER_DATA = 0x36
SID_REQUEST_TRANSFER_EXIT = 0x37
SID_TESTER_PRESENT = 0x3E


# Common NRC codes
NRC_GENERAL_REJECT = 0x10
NRC_SERVICE_NOT_SUPPORTED = 0x11
NRC_SUB_FUNCTION_NOT_SUPPORTED = 0x12
NRC_INCORRECT_MESSAGE_LENGTH = 0x13
NRC_CONDITIONS_NOT_CORRECT = 0x22
NRC_REQUEST_OUT_OF_RANGE = 0x31
NRC_SECURITY_ACCESS_DENIED = 0x33
NRC_INVALID_KEY = 0x35
NRC_EXCEEDED_ATTEMPTS = 0x36
NRC_TIME_DELAY_NOT_EXPIRED = 0x37
NRC_SUB_FUNC_NOT_SUPPORTED_IN_SESSION = 0x7E
NRC_SERVICE_NOT_SUPPORTED_IN_SESSION = 0x7F

NRC_NAMES: dict[int, str] = {
    0x10: "generalReject",
    0x11: "serviceNotSupported",
    0x12: "subFunctionNotSupported",
    0x13: "incorrectMessageLengthOrInvalidFormat",
    0x22: "conditionsNotCorrect",
    0x31: "requestOutOfRange",
    0x33: "securityAccessDenied",
    0x35: "invalidKey",
    0x36: "exceededNumberOfAttempts",
    0x37: "requiredTimeDelayNotExpired",
    0x7E: "subFunctionNotSupportedInActiveSession",
    0x7F: "serviceNotSupportedInActiveSession",
}
