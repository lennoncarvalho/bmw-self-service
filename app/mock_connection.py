"""Mock connection for DEMO mode development.

Implements the same interface as HSFZConnection but returns canned UDS
responses from mock_data/ files instead of talking to a real car.

Reference: SPEC-INFRASTRUCTURE.md Section 5 (Mock connection)
"""

import json
import logging
import struct
from pathlib import Path
from typing import Optional

from app.uds import UDS_NEGATIVE_RESPONSE

logger = logging.getLogger(__name__)


class MockConnection:
    """Demo-mode connection that returns canned UDS responses.

    Implements the same interface as HSFZConnection:
      - connect() -> bool
      - send_uds(ecu_addr, payload, timeout) -> bytes
      - disconnect()

    Routes known UDS requests to canned data from the mock data file.
    Unknown requests get a generic negative response.
    """

    SID_DIAG_SESSION_CONTROL = 0x10
    SID_ECU_RESET = 0x11
    SID_CLEAR_DTC = 0x14
    SID_READ_DTC = 0x19
    SID_READ_DATA_BY_ID = 0x22
    SID_READ_MEMORY_BY_ADDRESS = 0x23
    SID_WRITE_DATA_BY_ID = 0x2E
    SID_ROUTINE_CONTROL = 0x31
    SID_TESTER_PRESENT = 0x3E

    NRC_SERVICE_NOT_SUPPORTED = 0x11
    NRC_SUB_FUNCTION_NOT_SUPPORTED = 0x12
    NRC_REQUEST_OUT_OF_RANGE = 0x31

    def __init__(self, mock_data_path: Optional[str] = None) -> None:
        if mock_data_path is None:
            project_root = Path(__file__).resolve().parent.parent
            mock_data_path = str(project_root / "mock_data" / "f48_x1.json")
        self.mock_data_path = mock_data_path
        self.data: dict = {}

    def connect(self) -> bool:
        try:
            with open(self.mock_data_path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
            logger.info(
                "MockConnection ready: VIN=%s, model=%s",
                self.data.get("vehicle", {}).get("vin", ""),
                self.data.get("vehicle", {}).get("model", ""),
            )
            return True
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning("Mock data error at %s: %s", self.mock_data_path, e)
            self.data = {}
            return True

    def send_uds(
        self, ecu_addr: int, payload: bytes, timeout: float = 30.0
    ) -> bytes:
        service = payload[0] if payload else 0

        if service == self.SID_DIAG_SESSION_CONTROL:
            return bytes([0x50, payload[1] if len(payload) > 1 else 0x01])

        elif service == self.SID_TESTER_PRESENT:
            return bytes([0x7E, 0x00])

        elif service == self.SID_READ_DATA_BY_ID:
            return self._handle_read_data_by_id(ecu_addr, payload)

        elif service == self.SID_READ_DTC:
            return self._handle_read_dtc(ecu_addr, payload)

        elif service == self.SID_CLEAR_DTC:
            return bytes([0x54])

        elif service == self.SID_ECU_RESET:
            return bytes([0x51, payload[1] if len(payload) > 1 else 0x01])

        elif service == self.SID_ROUTINE_CONTROL:
            if len(payload) >= 4:
                return bytes([0x71, payload[1], payload[2], payload[3]])
            return bytes([0x71, 0x00, 0x00, 0x00])

        elif service == self.SID_WRITE_DATA_BY_ID:
            return bytes([0x6E]) + payload[1:3] if len(payload) >= 3 else bytes([0x6E])

        elif service == self.SID_READ_MEMORY_BY_ADDRESS:
            return bytes([0x63]) + bytes(4)

        # Unknown service: negative response
        return bytes([
            UDS_NEGATIVE_RESPONSE, service, self.NRC_SERVICE_NOT_SUPPORTED
        ])

    def _handle_read_data_by_id(self, ecu_addr: int, payload: bytes) -> bytes:
        if len(payload) < 3:
            return bytes([UDS_NEGATIVE_RESPONSE, 0x22, 0x13])

        did_high = payload[1]
        did_low = payload[2]

        # VIN: DID 0xF190
        if did_high == 0xF1 and did_low == 0x90:
            vin = self.data.get("vehicle", {}).get("vin", "")
            vin_bytes = vin.encode("ascii", errors="ignore")
            return bytes([0x62, 0xF1, 0x90]) + vin_bytes

        # I-Level: DID 0xF18A
        if did_high == 0xF1 and did_low == 0x8A:
            ilevel = b"F056-18-07-530"
            return bytes([0x62, 0xF1, 0x8A]) + ilevel

        # Mileage: any F4xx DID
        if did_high == 0xF4:
            mileage_km = self.data.get("vehicle", {}).get("mileage_km", 66000)
            mileage_raw = mileage_km * 10
            mileage_bytes = struct.pack(">I", mileage_raw)
            return bytes([0x62, did_high, did_low]) + mileage_bytes

        # Unknown DID
        return bytes([
            UDS_NEGATIVE_RESPONSE, self.SID_READ_DATA_BY_ID,
            self.NRC_REQUEST_OUT_OF_RANGE,
        ])

    def _handle_read_dtc(self, ecu_addr: int, payload: bytes) -> bytes:
        if len(payload) < 2:
            return bytes([
                UDS_NEGATIVE_RESPONSE, self.SID_READ_DTC,
                self.NRC_SUB_FUNCTION_NOT_SUPPORTED,
            ])

        sub_function = payload[1]

        if sub_function == 0x02:
            # Report DTCs by status mask
            dtcs = self.data.get("dtcs", [])
            result = bytes([0x59, 0x02, 0x08])  # status availability mask
            for dtc in dtcs:
                code_hex = dtc.get("code", "000000")
                try:
                    code_bytes = bytes.fromhex(code_hex)
                except ValueError:
                    code_bytes = bytes(3)
                status_byte = 0x08  # confirmed DTC
                result += code_bytes + bytes([status_byte])
            return result

        elif sub_function == 0x01:
            # Report DTC count
            dtcs = self.data.get("dtcs", [])
            count = len(dtcs)
            status_mask = payload[2] if len(payload) > 2 else 0x08
            return bytes([0x59, 0x01, status_mask, 0x01, count >> 8, count & 0xFF])

        else:
            return bytes([
                UDS_NEGATIVE_RESPONSE, self.SID_READ_DTC,
                self.NRC_SUB_FUNCTION_NOT_SUPPORTED,
            ])

    def disconnect(self) -> None:
        """No-op for mock connection."""
        pass

    def __enter__(self) -> "MockConnection":
        self.connect()
        return self

    def __exit__(self, *args: object) -> None:
        self.disconnect()
