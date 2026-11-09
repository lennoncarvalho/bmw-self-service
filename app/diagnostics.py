"""Variant-scoped diagnostic memories and Clear All with per-target outcomes.

D-61/M4: where the identified variant's job file is available, its own jobs
(FS_LESEN/IS_LESEN, FS_LOESCHEN/IS_LOESCHEN) are the primary source; otherwise
the app's recovered requests (docs.md#identity-configuration-and-diagnostics) are
used. Every coverage row names its source. Clear jobs may only send the exact
recovered clear request. Each ECU/memory has a 30-second absolute queued
operation budget within a five-minute batch budget. No automatic retry follows a
timeout or ambiguous stream; later targets remain not attempted.
"""

import json
import logging
import time
from collections import Counter
from functools import cache
from typing import Any, cast

from app.fault_details import DETAIL_JOBS, decode_fault_details
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
READ_JOBS = {"Fault": "FS_LESEN", "Information": "IS_LESEN", "Permanent": "FS_LESEN_PERMANENT"}
# Clear job, the only request it may send, and the exact final reply that confirms it.
CLEAR_JOBS = {
    "Fault": ("FS_LOESCHEN", FAULT_CLEAR, b"\x54"),
    "Information": ("IS_LOESCHEN", INFO_CLEAR, b"\x71\x01\x0f\x06"),
}
STREAM_FAILURES = frozenset(
    {
        "timeout",
        "failed",
        "cancelled",
        "outcome-uncertain",
        "connection-closed",
        "connection-lost",
        "invalid-response",
        "unexpected-response",
        "transport-rejected",
    }
)


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
    """A variant's job file decides memory support; otherwise use the recovered requests."""
    job = READ_JOBS.get(memory)
    if job is not None and backend.engine(name) is not None:
        return backend.has_job(name, job) or (memory == "Fault" and payload is not None)
    return payload is not None


def coverage_complete(row: dict[str, Any]) -> bool:
    """Whether a memory was read or is explicitly outside the available contract."""
    return row["state"] in ("read", "not-applicable") or (
        row["memory"] != "Fault"
        and row["state"] == "unsupported"
        and not row.get("prg_decided", False)
    )


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
        ``(records, state, source)``; partial results retain valid records but
        never count as complete coverage.
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
            record_error = False
            try:
                records = fault_records(run)
            except ValueError:
                logger.warning("Invalid job records address=%04X job=%s", address, job)
                records, record_error = [], True
            try:
                wire_records = decode_memory(run.response(), memory)
            except ValueError:
                logger.warning("Invalid job response address=%04X job=%s", address, job)
                return records or None, "partial" if records else "invalid", run.source
            if record_error or Counter((r["code"], r["status"]) for r in records) != Counter(
                wire_records
            ):
                logger.warning("Job record accounting mismatch address=%04X job=%s", address, job)
                return (
                    [
                        {"code": c, "status": st, "text": "", "presence": ""}
                        for c, st in wire_records
                    ],
                    "partial",
                    f"{APP_SOURCE} (job record accounting mismatch)",
                )
            return records, "read", run.source
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
        """Collect memory lists and bounded details with explicit per-target coverage."""
        deadline = time.monotonic() + 300.0
        catalog = DiagnosticCatalog()
        dtcs: list[dict] = []
        coverage: list[dict] = []
        stopped = False
        for ecu in self.ecus:
            address = int(str(ecu["addr"]), 0)
            name = str(ecu.get("name", f"ECU {address:02X}"))
            supported = bool(ecu.get("identified") and ecu.get("uds"))
            requests, decided = memory_requests(name)
            # A loaded exact variant also decides permanent-memory applicability.
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
                row["prg_decided"] = decided or job_decided
                coverage.append(row)
                if supported and not memory_applicable(backend, name, memory, payload):
                    row["state"] = "not-applicable"
                    continue
                if not supported:
                    row["state"] = (
                        "unidentified" if not ecu.get("identified") else "unsupported-protocol"
                    )
                    continue
                if self._cancelled.is_set():
                    row["state"] = "not-attempted-cancelled"
                    continue
                if stopped or not self.connection.alive_ok:
                    row["state"] = "not-attempted-connection"
                    continue
                self.progress.emit(f"Reading {name}: {memory.lower()} memory...")
                records, row["state"], row["source"] = read_memory(
                    self.connection, backend, name, address, memory, payload, deadline
                )
                stopped = row["state"] in STREAM_FAILURES
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
                            "description": description or "Description unavailable",
                            "job_text": record["text"],
                            "job_presence": record["presence"],
                            "source": row["source"],
                        }
                    )
        self._read_details(backend, dtcs, coverage, deadline)
        complete = (
            self.coverage_known
            and bool(self.ecus)
            and all(coverage_complete(row) for row in coverage)
        )
        return {
            "dtcs": dtcs,
            "coverage": coverage,
            "complete": complete,
            "topology_known": self.coverage_known,
            "mil": None,
        }

    def _read_details(
        self, backend: JobBackend, dtcs: list[dict], coverage: list[dict], deadline: float
    ) -> None:
        """Read recorded conditions after all basic lists; retain independent failures.

        Each ECU/memory detail batch shares 30 seconds, including all its native
        jobs, within the scan's original five-minute deadline. Expansion performs
        no I/O. Permanent-memory faults never borrow normal-memory snapshots.
        """
        stream_failed = any(row.get("state") in STREAM_FAILURES for row in coverage)
        for row in coverage:
            selected = [
                dtc
                for dtc in dtcs
                if (dtc["ecu_name"], dtc["ecu_addr"], dtc["memory"])
                == (row["name"], row["addr"], row["memory"])
            ]
            counts = Counter(dtc["code"] for dtc in selected)
            detail_deadline = min(deadline, time.monotonic() + 30.0)
            job = DETAIL_JOBS.get(row["memory"])
            for dtc in selected:
                details: dict[str, Any] = {"state": "not-defined", "records": []}
                dtc["details"] = details
                if job is None or not backend.has_job(row["name"], job):
                    continue
                details["source"] = f"ECU job {job} ({row['name']})"
                if counts[dtc["code"]] != 1:
                    details["state"] = "ambiguous-record"
                    continue
                if self._cancelled.is_set():
                    details["state"] = "not-attempted-cancelled"
                    continue
                if stream_failed or not self.connection.alive_ok:
                    details["state"] = "not-attempted-connection"
                    continue
                remaining = detail_deadline - time.monotonic()
                if remaining <= 0:
                    details["state"] = "not-attempted-budget-exhausted"
                    continue
                self.progress.emit(
                    f"Reading {row['name']}: {row['memory'].lower()} details {dtc['code']}..."
                )
                code = int(dtc["code"], 16)
                # The job takes F_CODE; legacy information jobs find their own
                # current position. Never derive F_POS from scan/list order.
                run = backend.run(
                    row["name"],
                    row["addr"],
                    job,
                    str(code),
                    timeout=remaining,
                    cancelled=self._cancelled,
                )
                if not run.ok:
                    details["state"] = run.state()
                    stream_failed = run.state() in STREAM_FAILURES
                    continue
                try:
                    dtc["details"] = decode_fault_details(run, code)
                except ValueError:
                    details["state"] = "invalid"
                    logger.warning(
                        "Invalid fault details address=%04X memory=%s code=%06X",
                        row["addr"],
                        row["memory"],
                        code,
                        exc_info=True,
                    )
            row["details"] = dict(Counter(dtc["details"]["state"] for dtc in selected))


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
        self._executed = False

    def do_work(self) -> dict:
        """Continue after definite ECU rejections; stop sending on lost transport."""
        if self._executed:
            raise PermissionError("A fault-clearing operation cannot be replayed")
        self._executed = True
        backend = self.backend or JobBackend(self.connection)
        try:
            return self._clear(backend)
        finally:
            if self.backend is None:
                backend.close()

    def _clear(self, backend: JobBackend) -> dict:
        """Account for every target; never continue mutations after uncertain communication."""
        deadline = time.monotonic() + 300.0
        outcomes = []
        stopped = ""
        for ecu in self.ecus:
            address = int(str(ecu["addr"]), 0)
            name = str(ecu["name"])
            reads, _decided = memory_requests(name)
            supported = bool(ecu.get("identified") and ecu.get("uds"))
            has_file = supported and backend.engine(name) is not None
            for memory, app_payload in (
                ("Fault", FAULT_CLEAR),
                ("Information", info_clear_request(name)),
                ("Permanent", None),
            ):
                row = {
                    "name": name,
                    "addr": address,
                    "memory": memory,
                    "response": "not-attempted",
                    "observed": "not-read",
                    "source": "",
                }
                outcomes.append(row)
                if not supported:
                    row["response"] = (
                        "unidentified" if not ecu.get("identified") else "unsupported-protocol"
                    )
                    continue
                if memory == "Permanent":
                    row["response"] = (
                        "not-cleared-permanent"
                        if memory_applicable(backend, name, memory, reads[memory])
                        else "not-applicable"
                    )
                    continue
                job, job_payload, expected = CLEAR_JOBS[memory]
                use_job = backend.has_job(name, job)
                # A failed initial read never removes a source-supported clear target.
                payload = job_payload if use_job else None if has_file else app_payload
                if payload is None:
                    row["response"] = "no-clear-job-in-job-file" if has_file else "not-applicable"
                    continue
                if getattr(self.connection, "read_only", False):
                    row["response"] = "policy-blocked"
                    continue
                if stopped:
                    row["response"] = f"not-attempted-{stopped}"
                    continue
                if self._cancelled.is_set():
                    stopped = "cancelled"
                    row["response"] = "not-attempted-cancelled"
                    continue
                if not self.connection.alive_ok:
                    stopped = "connection"
                    row["response"] = "not-attempted-connection"
                    continue
                if time.monotonic() >= deadline:
                    stopped = "budget-exhausted"
                    row["response"] = "not-attempted-budget-exhausted"
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
                if row["response"] in STREAM_FAILURES or row["response"] in (
                    "invalid",
                    "inconsistent-job-status",
                ):
                    stopped = "connection"
                if row["response"] != "accepted" or not self.connection.alive_ok:
                    continue
                records, state, _source = read_memory(
                    self.connection, backend, name, address, memory, reads[memory], deadline
                )
                row["observed"] = (
                    state if state != "read" else "still-present" if records else "empty"
                )
                row["read_state"] = state
                row["remaining_count"] = len(records) if records is not None else None
                if state in STREAM_FAILURES:
                    stopped = "connection"
        if stopped == "connection":
            # A local job failure can leave the socket nominally open after a
            # sent clear. Close it before the UI can schedule other operations.
            self.connection.request_close()
        return {"outcomes": outcomes, "stopped": stopped}

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
        reply = run.reply(payload)
        if len(reply) == 3 and reply[:2] == bytes((0x7F, payload[0])) and reply[2] != 0x78:
            return ("unsupported" if reply[2] in (0x11, 0x12, 0x31) else "rejected"), run.source
        if run.error is not None:
            logger.warning("Clear job target=%04X job=%s error=%r", address, job, run.error)
            if run.sent(payload):
                return "outcome-uncertain", run.source
            return run.state(), run.source
        if not run.sent(payload):
            return "not-sent", run.source
        if reply == expected:
            # A positive reply with a failed job status is not a confirmed clear.
            return ("accepted" if run.status == "OKAY" else "inconsistent-job-status"), run.source
        return "outcome-uncertain", run.source
