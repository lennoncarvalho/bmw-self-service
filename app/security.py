"""SecurityAccess (UDS 0x27) — seed/key authentication for protected ECUs.

This legacy helper does not establish write capability or ECU-specific levels
and algorithms. Unverified family classifications grant no authorization.
No recovered security algorithm or live coding write path is implemented here.
"""

import logging

logger = logging.getLogger(__name__)


def request_seed(connection, ecu_addr: int) -> bytes:
    """Request a security seed from an ECU.

    UDS flow:
      Tester: 0x27 0x01  →  ECU: 0x67 0x01 [seed bytes]

    Args:
        connection: HSFZConnection or DoIPConnection.
        ecu_addr: ECU address.

    Returns:
        Seed bytes from the ECU response.

    Raises:
        ConnectionError: If ECU rejects the request.
    """
    resp = connection.send_uds(ecu_addr, bytes([0x27, 0x01]))
    if len(resp) < 1:
        raise ConnectionError("Empty security response")
    if resp[0] == 0x7F:
        nrc = resp[2] if len(resp) > 2 else 0
        raise ConnectionError(f"SecurityAccess rejected: NRC 0x{nrc:02X}")
    if len(resp) < 2 or resp[0] != 0x67 or resp[1] != 0x01:
        raise ConnectionError(f"Unexpected security response: 0x{resp[0]:02X}")
    seed: bytes = resp[2:]
    return seed  # seed bytes


def send_key(connection, ecu_addr: int, key: bytes) -> bool:
    """Send a computed key to unlock an ECU.

    UDS flow:
      Tester: 0x27 0x02 [key]  →  ECU: 0x67 0x02 (accepted) or 0x7F (rejected)

    Args:
        connection: HSFZConnection or DoIPConnection.
        ecu_addr: ECU address.
        key: Computed key bytes.

    Returns:
        True if the ECU accepted the key.
    """
    payload = bytes([0x27, 0x02]) + key
    resp = connection.send_uds(ecu_addr, payload)
    if len(resp) < 2:
        return False
    if resp[0] == 0x67 and resp[1] == 0x02:
        logger.info("SecurityAccess unlocked ECU 0x%02X", ecu_addr)
        return True
    if resp[0] == 0x7F:
        nrc = resp[2] if len(resp) > 2 else 0
        logger.warning(
            "SecurityAccess key rejected for ECU 0x%02X: NRC 0x%02X",
            ecu_addr,
            nrc,
        )
    return False
