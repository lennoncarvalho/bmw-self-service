"""SecurityAccess (UDS 0x27) — seed/key authentication for protected ECUs.

22 of ~139 BMW ECUs require SecurityAccess before accepting diagnostic writes
(0x2E WriteDataByIdentifier, 0x31 RoutineControl, etc.). This module defines
which ECUs are protected and provides the framework for the seed/key exchange.

Reference: docs/01-bmw-protocol-research.md (FDL coding section),
           docs/13-replacement-app-architecture.md
"""

import logging

logger = logging.getLogger(__name__)

# ECU families that require SecurityAccess before writes.
# Source: coding-ecu-infos.enc expertMode flags + BimmerCode source analysis.
# These ECUs are safety-critical; incorrect writes can prevent the car from
# starting or disable safety systems.
PROTECTED_ECUS: set[str] = {
    "ACSM",  # Airbag Control Unit
    "ACSM2",  # Airbag Control Unit v2
    "ACSM2CD",  # Airbag Control Unit (convertible)
    "ACSM_3",  # Airbag Control Unit gen 3
    "ACSM_4B",  # Airbag Control Unit gen 4B
    "ACSM_4C",  # Airbag Control Unit gen 4C
    "ACSM_4i",  # Airbag Control Unit gen 4i
    "ACSM_5",  # Airbag Control Unit gen 5
    "DME",  # Digital Motor Electronics (engine ECU)
    "DME2",  # Digital Motor Electronics v2
    "EDME",  # Electric DME
    "DSC",  # Dynamic Stability Control
    "DSC_60",  # Dynamic Stability Control (E60)
    "DSC_87",  # Dynamic Stability Control (E87)
    "DSC_56",  # Dynamic Stability Control (R56)
    "DSC_E65",  # Dynamic Stability Control (E65)
    "SAS",  # Steering Angle Sensor (when integrated with DSC)
    "ZGW",  # Central Gateway (sometimes locked, depends on firmware)
    "AIRBAG",  # Generic airbag module
    "ABG",  # Airbag (German: AirBag Gerät)
    "MRS",  # Multiple Restraint System
    "MRS5",  # Multiple Restraint System v5
    "MRS6",  # Multiple Restraint System v6
    "MRS7",  # Multiple Restraint System v7
    "MRS8",  # Multiple Restraint System v8
    "SRS",  # Supplemental Restraint System
}


def is_protected(ecu_name: str) -> bool:
    """Check whether an ECU requires SecurityAccess before writes.

    Args:
        ecu_name: ECU short name from SVT (e.g. "DME", "ACSM_4C").

    Returns:
        True if the ECU is in the protected list.
    """
    name_upper = ecu_name.upper()
    # Check exact match
    if name_upper in PROTECTED_ECUS:
        return True
    # Check prefix match (e.g. "ACSM" matches "ACSM_4C")
    return any(name_upper.startswith(p) for p in PROTECTED_ECUS)


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


# NOTE: Seed/key algorithms are ECU-specific and not publicly documented.
# BimmerCode implements them in native libraries (libbimmercode.so, etc.).
# Known algorithm families:
#
#   BMW Level 1:  Used by older ECUs (E-series). Simple XOR/key table.
#                  Not needed for F/G/U/I-series (2011+).
#
#   BMW Level 3:  Used by FEM, REM, KOMBI, etc. on F-series.
#                  Algorithm found in multiple public ECU tuning tools.
#
#   BMW Level 5:  Used by DME, DSC, ACSM on F/G-series.
#                  More complex, varies by ECU software version.
#
#   BMW Level 7:  Used by latest G/U/I-series ECUs.
#                  Not yet fully reverse-engineered.
#
# TODO: Extract algorithms from BimmerCode's native libraries via REA
#       (libbimmercode.so in the APK's lib/ directory).
#       Until then, protected ECUs must remain read-only.
