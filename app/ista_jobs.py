"""ECU job files as the primary source for faults and service status (D-61, M4).

``JobBackend`` loads an identified ECU variant's job file from the data source
(bundle first, then the user's ISTA folder) and runs named jobs through
``JobEngine`` over the existing protocol owner. Each run uses a per-run
connection view that:

1. records every request/reply pair the job exchanged;
2. refuses a telegram for any ECU other than the one the job was started for;
3. refuses any granted (non-read) service whose bytes are not exactly one of the
   caller's expected requests.

A job therefore cannot send a write other than the one the caller recorded in its
journal before the run. Callers fall back to the app's own requests and decoders
when no interpreter, data source or job file is available, and label the source.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, Lock
from typing import Any

from PySide6.QtCore import QCoreApplication, QThread

from app.ediabas import JobEngine, JobError, JobResult, JobUncertain
from app.ista_data import (
    DataFormatError,
    IstaDataSource,
    bundle_root,
    read_job_table,
    saved_ista_folder,
)
from app.protocol.contracts import TransportKind

logger = logging.getLogger(__name__)

APP_SOURCE = "app decoder"
# Replies that state a service or identifier is not implemented by the ECU.
UNSUPPORTED_NRCS = frozenset({0x11, 0x12, 0x31})


_source_lock = Lock()
_saved_folder: str | None = None
_source_cache: tuple[str, IstaDataSource] | None = None


def _on_gui_thread() -> bool:
    app = QCoreApplication.instance()
    return app is None or QThread.currentThread() == app.thread()


def remember_ista_folder() -> None:
    """Cache the saved ISTA folder; call on the GUI thread at startup and after changes.

    QSettings is a QObject; creating one in a CarWorker would leave its deletion to
    the GUI thread while it belongs to the worker, so workers use this cache.
    """
    global _saved_folder
    folder = saved_ista_folder()
    with _source_lock:
        _saved_folder = folder


def data_source() -> IstaDataSource:
    """Shared job data source: the bundle, then the remembered ISTA folder."""
    global _source_cache
    with _source_lock:
        folder = _saved_folder
    if folder is None:
        folder = saved_ista_folder() if _on_gui_thread() else ""
    with _source_lock:
        if _source_cache is not None and _source_cache[0] == folder:
            return _source_cache[1]
    source = IstaDataSource.from_paths(bundle_root(), folder or None)
    with _source_lock:
        _source_cache = (folder, source)
    return source


class JobRequestMismatch(PermissionError):
    """A job tried to send a write other than the recorded one; nothing was sent."""


class JobWriteRepeated(JobRequestMismatch):
    """A job tried to resend a write (e.g. its own NRC 0x21 retry); nothing was sent."""


@dataclass
class JobRun:
    """One job execution: its results, every exchange, and any failure.

    Attributes:
        sgbd: Job file that ran.
        job: Job name.
        result: Result sets, when the interpreter completed the job.
        exchanges: ``(request, reply)`` pairs in order; negative replies included.
        error: Failure raised by the run, if any.
    """

    sgbd: str
    job: str
    result: JobResult | None = None
    exchanges: list[tuple[bytes, bytes]] = field(default_factory=list)
    error: BaseException | None = None
    repeat_refused: bool = False

    @property
    def source(self) -> str:
        """User-facing label of this run's origin."""
        return f"ISTA job {self.job} ({self.sgbd})"

    @property
    def status(self) -> str:
        """JOB_STATUS reported by the job, or empty."""
        return self.result.status if self.result is not None else ""

    @property
    def ok(self) -> bool:
        """The job completed and reported OKAY."""
        return self.error is None and self.status == "OKAY"

    @property
    def interpreter_failed(self) -> bool:
        """The interpreter or job file failed; no vehicle outcome is implied."""
        return isinstance(self.error, JobError)

    def reply(self, request: bytes | None = None) -> bytes:
        """Last reply, or the last reply to an exact request; empty if none."""
        for sent, received in reversed(self.exchanges):
            if request is None or sent == request:
                return received
        return b""

    def sent(self, request: bytes) -> bool:
        """Whether this exact request reached the vehicle (or its outcome is unknown)."""
        if isinstance(self.error, JobUncertain):
            return True
        return any(sent == request for sent, _ in self.exchanges)

    def write_rejected(self, request: bytes) -> bool:
        """The write was sent once, the ECU gave a final negative reply, and the job's
        resend was refused: the request was not applied, so this is a rejection."""
        replies = [received for sent, received in self.exchanges if sent == request]
        return (
            self.repeat_refused
            and len(replies) == 1
            and len(replies[0]) == 3
            and replies[0][0] == 0x7F
            and replies[0][2] != 0x78
        )

    def response(self) -> bytes:
        """The job's own ``_RESPONSE`` result, else the last recorded reply."""
        if self.result is not None:
            for values in [self.result.system, *self.result.sets]:
                raw = values.get("_RESPONSE")
                if isinstance(raw, bytes) and raw:
                    return raw
        return self.reply()

    def state(self) -> str:
        """Coverage state of a run that did not read successfully."""
        error = self.error
        if self.repeat_refused and any(self.write_rejected(sent) for sent, _ in self.exchanges):
            return "rejected"
        if isinstance(error, JobUncertain):
            return "outcome-uncertain"
        if isinstance(error, JobRequestMismatch):
            return "refused-unexpected-request"
        if isinstance(error, TimeoutError):
            return "timeout"
        if isinstance(error, PermissionError):
            return "policy-blocked"
        if isinstance(error, ConnectionError):
            return "cancelled" if "cancel" in str(error).lower() else "failed"
        if isinstance(error, JobError):
            return "job-failed"
        if error is not None:
            return "invalid"
        reply = self.reply()
        if len(reply) == 3 and reply[0] == 0x7F:
            return "unsupported" if reply[2] in UNSUPPORTED_NRCS else "rejected"
        return "read" if self.ok else "invalid"


class _JobConnection:
    """Per-run view of the protocol owner used by ``JobEngine`` (see module doc)."""

    def __init__(
        self, connection: Any, address: int, expected: frozenset[bytes], run: JobRun
    ) -> None:
        self.connection = connection
        self.address = address
        self.expected = expected
        self.run = run
        self.used: set[bytes] = set()

    @property
    def trace_id(self) -> str:
        return str(getattr(self.connection, "trace_id", ""))

    def context(self, timeout: float = 30.0, cancelled: Event | None = None) -> Any:
        return self.connection.context(timeout, cancelled)

    def send_uds(
        self,
        ecu_addr: int,
        payload: bytes,
        timeout: float = 30.0,
        *,
        context: Any = None,
        raw: bool = False,
        grant: frozenset[int] = frozenset(),
    ) -> bytes:
        if ecu_addr != self.address:
            raise ValueError("Job telegram addressed a different ECU than the identified one")
        if payload[:1] and payload[0] in grant:
            if payload not in self.expected:
                raise JobRequestMismatch("Job write does not match the recorded request")
            if payload in self.used:
                # D-28: each write is sent once; the job's own retry loop is not replayed.
                self.run.repeat_refused = True
                raise JobWriteRepeated("Job tried to resend a write; not sent again")
            self.used.add(payload)
        reply = bytes(
            self.connection.send_uds(
                ecu_addr, payload, timeout, context=context, raw=raw, grant=grant
            )
        )
        self.run.exchanges.append((bytes(payload), reply))
        return reply


class JobBackend:
    """Job files of identified ECU variants, run over one diagnostic connection.

    Confined to one CarWorker; engines are created on first use and reused.
    """

    def __init__(
        self,
        connection: Any,
        source: IstaDataSource | None = None,
        *,
        reason: str = "",
    ) -> None:
        """Bind to a connection; ``reason`` disables the backend (app path only).

        Args:
            connection: Live ``DiagnosticConnection`` (HSFZ only).
            source: Job file data source; defaults to the bundle plus saved folder.
            reason: Non-empty to disable job use, e.g. for DEMO data.
        """
        self.connection = connection
        self.reason = reason
        self.source = source
        self._engines: dict[str, JobEngine | None] = {}
        self._paths: dict[str, Path] = {}
        self._jobs: dict[str, frozenset[str]] = {}
        if not self.reason and getattr(connection, "kind", None) != TransportKind.HSFZ:
            self.reason = "job files run over HSFZ only"
        if not self.reason and self.source is None:
            try:
                self.source = data_source()
            except (OSError, DataFormatError) as exc:
                self.reason = f"job data unavailable ({exc})"
        if not self.reason and self.source is not None and not self.source.providers:
            self.reason = "no job data (bundle or ISTA folder) is available"

    @classmethod
    def disabled(cls, connection: Any, reason: str) -> "JobBackend":
        """A backend that always defers to the app's own requests."""
        return cls(connection, IstaDataSource([]), reason=reason)

    @property
    def available(self) -> bool:
        """Whether job files can be used at all in this session."""
        return not self.reason

    def fallback_source(self, name: str = "") -> str:
        """Label for results produced without a job, with the reason."""
        if self.reason:
            return f"{APP_SOURCE} (jobs unavailable: {self.reason})"
        if name and self.engine(name) is None:
            return f"{APP_SOURCE} (no job file for {name})"
        return APP_SOURCE

    def engine(self, name: str) -> JobEngine | None:
        """Engine with the variant's job file loaded, or ``None``."""
        key = name.upper()
        if key in self._engines:
            return self._engines[key]
        engine: JobEngine | None = None
        if self.available and self.source is not None:
            located = self.source.locate(name)
            # Only a variant file: the variant is already identified by the app.
            if located is not None and located[0].suffix.lower() == ".prg":
                try:
                    engine = JobEngine(self.connection)
                    engine.load(located[0], ecu_dir=located[1])
                    self._paths[key] = located[0]
                    self._jobs[key] = frozenset(job.upper() for job in engine.jobs())
                except JobError as exc:
                    if engine is None:
                        # The interpreter library itself is missing or incompatible.
                        self.reason = str(exc)
                    else:
                        engine.close()
                    logger.warning("Job file for %s unusable: %s", name, exc)
                    engine = None
        self._engines[key] = engine
        return engine

    def has_job(self, name: str, job: str) -> bool:
        """Whether the variant's job file defines ``job``."""
        return self.engine(name) is not None and job.upper() in self._jobs[name.upper()]

    def job_file(self, name: str) -> Path | None:
        """Loaded job file path of a variant."""
        return self._paths.get(name.upper()) if self.engine(name) is not None else None

    def file_sha256(self, name: str) -> str:
        """SHA-256 of the variant's job file (recorded in write journals)."""
        path = self.job_file(name)
        return hashlib.sha256(path.read_bytes()).hexdigest() if path is not None else ""

    def table(self, name: str, table: str) -> tuple[list[str], list[list[str]]] | None:
        """One table of the variant's job file, or ``None``."""
        path = self.job_file(name)
        if path is None:
            return None
        try:
            return read_job_table(path, table)
        except (OSError, DataFormatError):
            logger.warning("Job table %s.%s unreadable", name, table, exc_info=True)
            return None

    def run(
        self,
        name: str,
        address: int,
        job: str,
        args: str = "",
        *,
        timeout: float = 30.0,
        cancelled: Event | None = None,
        grant: frozenset[int] = frozenset(),
        expected: frozenset[bytes] = frozenset(),
    ) -> JobRun:
        """Run one job on the identified ECU; failures are returned in ``JobRun.error``.

        Args:
            name: Identified variant name (job file stem).
            address: The ECU's diagnostic address; other targets are refused.
            job: Job name.
            args: Semicolon-separated job arguments.
            timeout: Overall job budget in seconds.
            cancelled: Cancellation token.
            grant: Non-read services the job may send.
            expected: Exact requests allowed for the granted services.

        Raises:
            JobError: No job file is loaded for ``name``.
        """
        engine = self.engine(name)
        if engine is None:
            raise JobError(f"No job file is available for {name}")
        run = JobRun(engine.sgbd, job.upper())
        engine.connection = _JobConnection(self.connection, address, expected, run)
        try:
            run.result = engine.run_job(
                job, args, timeout=timeout, cancelled=cancelled, grant=grant
            )
        except (JobError, PermissionError, TimeoutError, ConnectionError, ValueError) as exc:
            run.error = exc
        logger.debug(
            "Job run sgbd=%s job=%s status=%s exchanges=%d error=%r",
            run.sgbd,
            run.job,
            run.status,
            len(run.exchanges),
            run.error,
        )
        return run

    def close(self) -> None:
        """Release every native engine."""
        for engine in self._engines.values():
            if engine is not None:
                engine.close()
        self._engines.clear()


def fault_records(run: JobRun) -> list[dict[str, Any]]:
    """Map FS_LESEN/IS_LESEN result sets to fault records.

    Each record carries the 24-bit fault code, the ISO 14229 status byte (from
    ``F_STATUSBYTE``, else the last byte of ``F_HEX_CODE``) and the job's German
    location and presence texts.

    Raises:
        ValueError: The job did not complete or a record lacks its code or status.
    """
    if run.result is None:
        raise ValueError("Fault job produced no results")
    records: list[dict[str, Any]] = []
    for values in run.result.sets:
        if "F_ORT_NR" not in values:
            continue
        code, status = values.get("F_ORT_NR"), values.get("F_STATUSBYTE")
        raw = values.get("F_HEX_CODE")
        if not isinstance(status, int) and isinstance(raw, bytes) and len(raw) == 4:
            status = raw[3]
        if (
            not isinstance(code, int)
            or not 0 <= code <= 0xFFFFFF
            or not isinstance(status, int)
            or not 0 <= status <= 0xFF
        ):
            raise ValueError("Fault job record lacks its code or status")
        text, presence = values.get("F_ORT_TEXT"), values.get("F_VORHANDEN_TEXT")
        records.append(
            {
                "code": code,
                "status": status,
                "text": text.strip() if isinstance(text, str) else "",
                "presence": presence.strip() if isinstance(presence, str) else "",
            }
        )
    return records
