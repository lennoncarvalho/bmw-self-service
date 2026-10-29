"""Variant-scoped diagnostic memories and Clear All with per-target outcomes.

Source contracts and byte provenance: docs/evidence/task-b-recovered-contracts.md.
Each ECU/memory has a 30-second absolute queued operation budget within a
five-minute batch budget. No automatic
retry follows a timeout or ambiguous stream; later targets remain not attempted.
"""

import logging
import time
from typing import Any

from app.protocol.contracts import FailureKind
from app.uds import decode_dtc_records
from app.vehicle import DiagnosticCatalog, did_data
from app.worker import CarWorker

logger = logging.getLogger(__name__)
MEMORIES = {"Fault": b"\x19\x02\x0c", "Information": b"\x22\x20\x00", "Permanent": b"\x19\x15"}


def decode_memory(response: bytes, memory: str) -> list[tuple[int, int]]:
    """Validate echoes and complete records, retaining raw status per memory."""
    if memory == "Fault":
        if len(response) < 3 or response[:2] != b"\x59\x02" or (len(response) - 3) % 4:
            raise ValueError("Invalid fault-memory records or echo")
        return decode_dtc_records(response)
    if memory == "Information":
        records = did_data(response, 0x2000)
    elif memory == "Permanent":
        if response[:2] != b"\x59\x15":
            raise ValueError("Invalid permanent-memory response")
        # Both layouts are present in the source decoder: legacy omits the
        # availability byte; standard includes it. Exact alignment disambiguates.
        if len(response) >= 3 and (len(response) - 3) % 4 == 0:
            records = response[3:]
        elif len(response) >= 2 and (len(response) - 2) % 4 == 0:
            records = response[2:]
        else:
            raise ValueError("Incomplete permanent-memory records")
    else:
        raise ValueError("Unknown diagnostic memory")
    if len(records) % 4:
        raise ValueError("Incomplete diagnostic records")
    return [
        (int.from_bytes(records[i : i + 3], "big"), records[i + 3])
        for i in range(0, len(records), 4)
    ]


def exchange(
    connection: Any, address: int, payload: bytes, deadline: float
) -> tuple[bytes | None, str]:
    """Return explicit operation disposition; preserve local rejection vs lost stream."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return None, "not-attempted-budget-exhausted"
    result = connection.request(address, payload, context=connection.context(min(30.0, remaining)))
    if result.failure is None:
        return result.payload, "read"
    logger.warning(
        "Diagnostic target=%04X request=%s outcome=%s", address, payload.hex(), result.failure
    )
    if result.failure == FailureKind.NEGATIVE:
        return None, "unsupported" if result.nrc in (0x11, 0x12, 0x31) else "rejected"
    return None, result.failure.value


class DiagnosticReadWorker(CarWorker):
    """Read each identified UDS ECU's normal, information and permanent memory."""

    def __init__(self, connection: Any, ecus: list[dict], *, coverage_known: bool = True) -> None:
        super().__init__(connection)
        self.ecus = [dict(ecu) for ecu in ecus]
        self.coverage_known = coverage_known and all(
            ecu.get("origin") != "catalogue" for ecu in self.ecus
        )

    def do_work(self) -> dict:
        """Publish one settled scan, including every target's coverage disposition."""
        deadline = time.monotonic() + 300.0
        catalog = DiagnosticCatalog()
        dtcs: list[dict] = []
        coverage: list[dict] = []
        for ecu in self.ecus:
            address = int(str(ecu["addr"]), 0)
            name = str(ecu.get("name", f"ECU {address:02X}"))
            supported = bool(ecu.get("identified") and ecu.get("uds"))
            for memory, payload in MEMORIES.items():
                row = {
                    "name": name,
                    "addr": address,
                    "memory": memory,
                    "state": "not-attempted",
                    "origin": ecu.get("origin", "gateway"),
                }
                coverage.append(row)
                if not supported:
                    row["state"] = (
                        "unidentified" if not ecu.get("identified") else "unsupported-protocol"
                    )
                    continue
                if self.isInterruptionRequested() or not self.connection.alive_ok:
                    continue
                self.progress.emit(f"Reading {name}: {memory.lower()} memory...")
                response, state = exchange(self.connection, address, payload, deadline)
                row["state"] = state
                if response is None:
                    continue
                try:
                    records = decode_memory(response, memory)
                except ValueError:
                    logger.warning(
                        "Invalid memory address=%04X memory=%s", address, memory, exc_info=True
                    )
                    row["state"] = "invalid"
                    continue
                for code, status in records:
                    code_text = f"{code:06X}"
                    dtcs.append(
                        {
                            "code": code_text,
                            "status_byte": status,
                            "ecu_name": name,
                            "ecu_addr": address,
                            "memory": memory,
                            "description": catalog.describe(name, code_text, memory)
                            or "English description unavailable",
                        }
                    )
        complete = (
            self.coverage_known
            and bool(self.ecus)
            and all(
                row["state"] == "read"
                or (row["memory"] != "Fault" and row["state"] == "unsupported")
                for row in coverage
            )
        )
        return {
            "dtcs": dtcs,
            "coverage": coverage,
            "complete": complete,
            "topology_known": self.coverage_known,
            "mil": None,
        }


class DiagnosticClearWorker(CarWorker):
    """Clear all supported normal/information targets and reread each memory.

    Fault clearing intentionally saves no report/backup. A final positive reply
    and the observed memory are distinct, including faults that recur immediately.
    """

    def __init__(self, connection: Any, ecus: list[dict], coverage: list[dict]) -> None:
        super().__init__(connection)
        self.ecus = [dict(ecu) for ecu in ecus]
        self.coverage = [dict(row) for row in coverage]

    def do_work(self) -> dict:
        """Continue after definite ECU rejections; stop sending on lost transport."""
        deadline = time.monotonic() + 300.0
        outcomes = []
        for ecu in self.ecus:
            if not ecu.get("identified") or not ecu.get("uds"):
                continue
            address = int(str(ecu["addr"]), 0)
            for memory, payload in (
                ("Fault", b"\x14\xff\xff\xff"),
                ("Information", b"\x31\x01\x0f\x06"),
            ):
                if memory == "Information" and not any(
                    row["addr"] == address and row["memory"] == memory and row["state"] == "read"
                    for row in self.coverage
                ):
                    continue
                row = {
                    "name": ecu["name"],
                    "addr": address,
                    "memory": memory,
                    "response": "not-attempted",
                    "observed": "not-read",
                }
                outcomes.append(row)
                if not self.connection.alive_ok:
                    continue
                self.progress.emit(f"Clearing {ecu['name']}: {memory.lower()} memory...")
                response, state = exchange(self.connection, address, payload, deadline)
                expected = b"\x54" if memory == "Fault" else b"\x71\x01\x0f\x06"
                row["response"] = (
                    "accepted" if response == expected else state if response is None else "invalid"
                )
                if row["response"] != "accepted" or not self.connection.alive_ok:
                    continue
                observed, state = exchange(self.connection, address, MEMORIES[memory], deadline)
                row["observed"] = state
                if observed is not None:
                    try:
                        row["observed"] = (
                            "still-present" if decode_memory(observed, memory) else "empty"
                        )
                    except ValueError:
                        row["observed"] = "invalid"
        return {"outcomes": outcomes}
