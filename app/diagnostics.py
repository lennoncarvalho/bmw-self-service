"""Variant-scoped diagnostic memories and Clear All with per-target outcomes.

D-61/M4: where the identified variant's job file is available, its own jobs
(FS_LESEN/IS_LESEN, FS_LOESCHEN/IS_LOESCHEN) are the primary source; otherwise
the app's recovered requests (docs/evidence/task-b-recovered-contracts.md) are
used. Every coverage row names its source. Clear jobs may only send the exact
recovered clear request. Each ECU/memory has a 30-second absolute queued
operation budget within a five-minute batch budget. No automatic retry follows a
timeout or ambiguous stream; later targets remain not attempted.
"""

import json
import logging
import time
from functools import cache
from typing import Any, cast

from app.ista_jobs import APP_SOURCE, JobBackend, fault_records
from app.protocol.contracts import FailureKind
from app.resources import resource_path
from app.uds import decode_dtc_records
from app.vehicle import DiagnosticCatalog, did_data, fault_state
from app.worker import CarWorker

logger = logging.getLogger(__name__)
MEMORIES = {"Fault": b"\x19\x02\x0c", "Information": b"\x22\x20\x00", "Permanent": b"\x19\x15"}
INFO_CLEAR = b"\x31\x01\x0f\x06"
FAULT_CLEAR = b"\x14\xff\xff\xff"
READ_JOBS = {"Fault": "FS_LESEN", "Information": "IS_LESEN"}
# Clear job, the only request it may send, and the exact final reply that confirms it.
CLEAR_JOBS = {
    "Fault": ("FS_LOESCHEN", FAULT_CLEAR, b"\x54"),
    "Information": ("IS_LOESCHEN", INFO_CLEAR, b"\x71\x01\x0f\x06"),
}


@cache
def memory_variants() -> dict[str, dict[str, Any]]:
    """Per-variant memory requests from the PRG scan (scripts/recover_diagnostic_memory_variants)."""
    path = resource_path("coding_data/diagnostic_memory_variants.json")
    with path.open("rb") as stream:
        raw = stream.read(1048577)
    if len(raw) > 1048576:
        raise ValueError("Diagnostic memory definitions exceed their supported size")
    data = json.loads(raw)
    if data.get("schema") != 1 or not isinstance(data.get("variants"), dict):
        raise ValueError("Unsupported diagnostic memory definition format")
    return cast(dict[str, dict[str, Any]], data["variants"])


def memory_requests(name: str) -> tuple[dict[str, bytes | None], bool]:
    """Return each memory's read request (None = not defined) and whether a PRG decided it.

    Variants without a supplied PRG keep the diagnostics application's uniform requests.
    """
    row = memory_variants().get(name)
    if row is None:
        return dict(MEMORIES), False
    info = row["info"]
    return {
        "Fault": MEMORIES["Fault"],
        "Information": bytes.fromhex(info) if info else None,
        "Permanent": MEMORIES["Permanent"] if row["permanent"] else None,
    }, True


def info_clear_request(name: str) -> bytes | None:
    """Information-memory clear routine, unless the variant's PRG defines none."""
    row = memory_variants().get(name)
    return INFO_CLEAR if row is None or row["info_clear"] else None


def decode_memory(response: bytes, memory: str) -> list[tuple[int, int]]:
    """Validate echoes and complete records, retaining raw status per memory."""
    if memory == "Fault":
        if len(response) < 3 or response[:2] != b"\x59\x02" or (len(response) - 3) % 4:
            raise ValueError("Invalid fault-memory records or echo")
        return decode_dtc_records(response)
    if memory == "Information" and response[:2] == b"\x59\x17":
        # IS_LESEN 19 17 0C 01: memory-selection echo and availability mask precede records.
        if len(response) < 4 or response[2] != 0x01:
            raise ValueError("Invalid information-memory response")
        records = response[4:]
    elif memory == "Information":
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


def memory_applicable(backend: JobBackend, name: str, memory: str, payload: bytes | None) -> bool:
    """A variant's job file decides Fault/Information; otherwise the recovered request does."""
    job = READ_JOBS.get(memory)
    if job is not None and backend.engine(name) is not None:
        return backend.has_job(name, job) or (memory == "Fault" and payload is not None)
    return payload is not None


def read_memory(
    connection: Any,
    backend: JobBackend,
    name: str,
    address: int,
    memory: str,
    payload: bytes | None,
    deadline: float,
) -> tuple[list[dict[str, Any]] | None, str, str]:
    """Read one memory via the variant's job, else the recovered request.

    Returns:
        ``(records, state, source)``; ``records`` is ``None`` unless ``state`` is read.
    """
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return None, "not-attempted-budget-exhausted", APP_SOURCE
    source = backend.fallback_source(name)
    job = READ_JOBS.get(memory)
    if job is not None and backend.has_job(name, job):
        run = backend.run(name, address, job, timeout=min(30.0, remaining))
        if not run.interpreter_failed:
            if not run.ok:
                logger.warning(
                    "Diagnostic job target=%04X job=%s state=%s error=%r",
                    address,
                    job,
                    run.state(),
                    run.error,
                )
                return None, run.state(), run.source
            try:
                return fault_records(run), "read", run.source
            except ValueError:
                logger.warning("Invalid job records address=%04X job=%s", address, job)
                return None, "invalid", run.source
        # Interpreter-level failure: no vehicle outcome is implied; use the app read.
        source = f"{APP_SOURCE} (job {job} failed: {run.error})"
    if payload is None:
        return None, "not-applicable", source
    response, state = exchange(connection, address, payload, deadline)
    if response is None:
        return None, state, source
    try:
        decoded = decode_memory(response, memory)
    except ValueError:
        logger.warning("Invalid memory address=%04X memory=%s", address, memory, exc_info=True)
        return None, "invalid", source
    records = [{"code": c, "status": st, "text": "", "presence": ""} for c, st in decoded]
    return records, "read", source


class DiagnosticReadWorker(CarWorker):
    """Read each identified UDS ECU's normal, information and permanent memory."""

    def __init__(
        self,
        connection: Any,
        ecus: list[dict],
        *,
        coverage_known: bool = True,
        backend: JobBackend | None = None,
    ) -> None:
        super().__init__(connection)
        self.ecus = [dict(ecu) for ecu in ecus]
        self.backend = backend
        self.coverage_known = coverage_known and all(
            ecu.get("origin") != "catalogue" for ecu in self.ecus
        )

    def do_work(self) -> dict:
        """Publish one settled scan, including every target's coverage disposition."""
        backend = self.backend or JobBackend(self.connection)
        try:
            return self._scan(backend)
        finally:
            if self.backend is None:
                backend.close()

    def _scan(self, backend: JobBackend) -> dict:
        deadline = time.monotonic() + 300.0
        catalog = DiagnosticCatalog()
        dtcs: list[dict] = []
        coverage: list[dict] = []
        for ecu in self.ecus:
            address = int(str(ecu["addr"]), 0)
            name = str(ecu.get("name", f"ECU {address:02X}"))
            supported = bool(ecu.get("identified") and ecu.get("uds"))
            requests, decided = memory_requests(name)
            # A job file decides Fault/Information; Permanent stays on the app request.
            job_decided = supported and backend.engine(name) is not None
            for memory, payload in requests.items():
                row = {
                    "name": name,
                    "addr": address,
                    "memory": memory,
                    "state": "not-attempted",
                    "origin": ecu.get("origin", "gateway"),
                    "source": "",
                }
                row["prg_decided"] = decided or (job_decided and memory != "Permanent")
                coverage.append(row)
                if supported and not memory_applicable(backend, name, memory, payload):
                    row["state"] = "not-applicable"
                    continue
                if not supported:
                    row["state"] = (
                        "unidentified" if not ecu.get("identified") else "unsupported-protocol"
                    )
                    continue
                if self.isInterruptionRequested() or not self.connection.alive_ok:
                    continue
                self.progress.emit(f"Reading {name}: {memory.lower()} memory...")
                records, row["state"], row["source"] = read_memory(
                    self.connection, backend, name, address, memory, payload, deadline
                )
                for record in records or []:
                    code_text = f"{record['code']:06X}"
                    description = catalog.describe(name, code_text, memory)
                    if description is None and record["text"]:
                        description = f"{record['text']} (German text from the ECU job file)"
                    dtcs.append(
                        {
                            "code": code_text,
                            "status_byte": record["status"],
                            "state": fault_state(record["status"]),
                            "ecu_name": name,
                            "ecu_addr": address,
                            "memory": memory,
                            "description": description or "English description unavailable",
                            "job_text": record["text"],
                            "job_presence": record["presence"],
                            "source": row["source"],
                        }
                    )
        complete = (
            self.coverage_known
            and bool(self.ecus)
            and all(
                row["state"] in ("read", "not-applicable")
                # Without a PRG the memory's existence is unknown; with one, a
                # rejection means that defined memory was not read.
                or (
                    row["memory"] != "Fault"
                    and row["state"] == "unsupported"
                    and not row["prg_decided"]
                )
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

    def __init__(
        self,
        connection: Any,
        ecus: list[dict],
        coverage: list[dict],
        *,
        backend: JobBackend | None = None,
    ) -> None:
        super().__init__(connection)
        self.ecus = [dict(ecu) for ecu in ecus]
        self.coverage = [dict(row) for row in coverage]
        self.backend = backend

    def do_work(self) -> dict:
        """Continue after definite ECU rejections; stop sending on lost transport."""
        backend = self.backend or JobBackend(self.connection)
        try:
            return self._clear(backend)
        finally:
            if self.backend is None:
                backend.close()

    def _clear(self, backend: JobBackend) -> dict:
        deadline = time.monotonic() + 300.0
        outcomes = []
        for ecu in self.ecus:
            if not ecu.get("identified") or not ecu.get("uds"):
                continue
            address = int(str(ecu["addr"]), 0)
            name = str(ecu["name"])
            reads, _decided = memory_requests(name)
            has_file = backend.engine(name) is not None
            for memory, app_payload in (
                ("Fault", FAULT_CLEAR),
                ("Information", info_clear_request(name)),
            ):
                job, job_payload, expected = CLEAR_JOBS[memory]
                use_job = backend.has_job(name, job)
                # With a job file, the file decides whether a clear exists.
                payload = job_payload if use_job else None if has_file else app_payload
                if payload is None:
                    if memory == "Fault":
                        outcomes.append(
                            {
                                "name": name,
                                "addr": address,
                                "memory": memory,
                                "response": "no-clear-job-in-job-file",
                                "observed": "not-read",
                                "source": backend.fallback_source(name),
                            }
                        )
                    continue
                if memory == "Information" and not any(
                    row["addr"] == address and row["memory"] == memory and row["state"] == "read"
                    for row in self.coverage
                ):
                    continue
                row = {
                    "name": name,
                    "addr": address,
                    "memory": memory,
                    "response": "not-attempted",
                    "observed": "not-read",
                    "source": "",
                }
                outcomes.append(row)
                if not self.connection.alive_ok:
                    continue
                self.progress.emit(f"Clearing {name}: {memory.lower()} memory...")
                if use_job:
                    row["response"], row["source"] = self._clear_by_job(
                        backend, name, address, job, payload, expected, deadline
                    )
                else:
                    row["source"] = backend.fallback_source(name)
                    response, state = exchange(self.connection, address, payload, deadline)
                    row["response"] = (
                        "accepted"
                        if response == expected
                        else state
                        if response is None
                        else "invalid"
                    )
                if row["response"] != "accepted" or not self.connection.alive_ok:
                    continue
                records, state, _source = read_memory(
                    self.connection, backend, name, address, memory, reads[memory], deadline
                )
                row["observed"] = (
                    state if records is None else "still-present" if records else "empty"
                )
        return {"outcomes": outcomes}

    @staticmethod
    def _clear_by_job(
        backend: JobBackend,
        name: str,
        address: int,
        job: str,
        payload: bytes,
        expected: bytes,
        deadline: float,
    ) -> tuple[str, str]:
        """Run one clear job limited to ``payload``; classify its final reply exactly."""
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return "not-attempted-budget-exhausted", APP_SOURCE
        run = backend.run(
            name,
            address,
            job,
            timeout=min(30.0, remaining),
            grant=frozenset({payload[0]}),
            expected=frozenset({payload}),
        )
        if run.write_rejected(payload):
            return "rejected", run.source
        if run.error is not None:
            logger.warning("Clear job target=%04X job=%s error=%r", address, job, run.error)
            return run.state(), run.source
        reply = run.reply(payload)
        if not run.sent(payload):
            return "not-sent", run.source
        if reply == expected:
            # A positive reply with a failed job status is not a confirmed clear.
            return ("accepted" if run.status == "OKAY" else "inconsistent-job-status"), run.source
        if len(reply) == 3 and reply[0] == 0x7F:
            return run.state(), run.source
        return "invalid", run.source
