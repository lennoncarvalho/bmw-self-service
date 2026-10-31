"""ECU job files (PRG/GRP) run by the native job interpreter over the protocol owner.

D-61: diagnostics execute an ECU description file's jobs by name. The interpreter
(`native/build/libedx`, built by ``scripts/build_native.sh``) performs no I/O. Each
telegram a job sends is converted from BMW-FAST framing to a target address plus UDS
payload and sent through ``DiagnosticConnection.send_uds(raw=True)``. It therefore
shares the owner's single stream, absolute deadline, late-reply quarantine,
read-only policy, mutation flagging and TX/RX logging. Job files are untrusted data.
"""

import ctypes
import logging
import math
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, Lock
from typing import Any

from PySide6.QtCore import QCoreApplication, QThread

from app.protocol.contracts import OperationContext

logger = logging.getLogger(__name__)

API_VERSION = 1
# BMW-FAST framing, as used by job files for KWP2000/UDS over D-CAN/ENET.
BMW_FAST_CONCEPTS = frozenset({0x010F, 0x0110})
TESTER_ADDRESS = 0xF1
# Functional/broadcast targets need multi-response handling the owner lacks.
FUNCTIONAL_TARGETS = frozenset({0xDF, 0xEF, 0xF0})

_OK, _ERR_VM, _ERR_ABORT, _ERR_DEADLINE, _ERR_BREAK, _ERR_ARG, _ERR_LOAD, _ERR_NOMEM = range(8)
_SEND_OK, _SEND_ERROR, _SEND_ABORT = range(3)
_TYPE_NAMES = ("INT", "LONG", "FLOAT", "STRING", "BINARY", "CHAR", "WORD", "DWORD", "BYTE")
_VM_ERRORS = (
    "ok",
    "out of memory",
    "invalid job file",
    "job not found",
    "illegal opcode",
    "stack overflow",
    "stack underflow",
    "division by zero",
    "interface error",
    "table error",
    "file error",
    "operand error",
    "break",
    "error trap",
    "job-raised error",
    "invalid float",
)

_SendCallback = ctypes.CFUNCTYPE(
    ctypes.c_int,
    ctypes.c_void_p,
    ctypes.c_uint32,
    ctypes.POINTER(ctypes.c_uint8),
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_uint8),
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
)

ResultValue = int | float | str | bytes


class JobUncertain(ConnectionError):
    """A job failed after at least one write telegram was sent; outcome unknown."""


class JobError(Exception):
    """A job could not run or did not complete inside the interpreter."""


class _InterfaceRefusal(Exception):
    """A telegram this interface cannot carry; nothing was sent to the vehicle.

    Group files probe older concepts (DS2, KWP) before BMW-FAST under their own
    error trap, so this is reported to the job as an interface error, like an
    interface that does not accept the concept, instead of aborting it.
    """


@dataclass(frozen=True)
class JobResult:
    """Materialised result sets of one job.

    Attributes:
        sgbd: Job file that ran (the resolved variant for a group file).
        job: Job name.
        system: System set (VARIANTE, JOBNAME, SAETZE, INFO metadata, ...).
        sets: Data sets in emission order; one per record for multi-record jobs.
        types: Result type names parallel to ``sets`` (e.g. ``"WORD"``).
        telegrams: Number of telegrams exchanged with the vehicle.
    """

    sgbd: str
    job: str
    system: dict[str, ResultValue]
    sets: list[dict[str, ResultValue]]
    types: list[dict[str, str]] = field(default_factory=list)
    telegrams: int = 0
    mutated: bool = False

    @property
    def status(self) -> str:
        """JOB_STATUS of the last data set that reports one, else the system set's."""
        for values in reversed(self.sets):
            status = values.get("JOB_STATUS")
            if isinstance(status, str):
                return status
        status = self.system.get("JOB_STATUS")
        return status if isinstance(status, str) else ""


def checksum(data: bytes) -> int:
    """BMW-FAST additive checksum over every preceding telegram byte."""
    return sum(data) & 0xFF


def parse_bmw_fast(telegram: bytes) -> tuple[int, int, bytes]:
    """Split a physically addressed BMW-FAST request into target, source and data.

    Args:
        telegram: Request as built by the job, with or without its checksum byte.

    Returns:
        ``(target, source, data)``.

    Raises:
        ValueError: Malformed, functional or truncated telegram.
    """
    if len(telegram) < 3:
        raise ValueError("Job telegram is too short")
    if telegram[0] & 0xC0 != 0x80:
        raise ValueError("Only physically addressed job telegrams are supported")
    length, offset = telegram[0] & 0x3F, 3
    if length == 0:
        if len(telegram) < 4:
            raise ValueError("Job telegram is too short")
        length, offset = telegram[3], 4
        if length == 0:
            if len(telegram) < 6:
                raise ValueError("Job telegram is too short")
            length, offset = int.from_bytes(telegram[4:6], "big"), 6
    if length == 0 or len(telegram) < offset + length:
        raise ValueError("Job telegram length does not match its header")
    if len(telegram) > offset + length + 1:
        raise ValueError("Job telegram has trailing bytes")
    if len(telegram) == offset + length + 1 and telegram[-1] != checksum(telegram[:-1]):
        # A wrong checksum usually means a header length one byte short.
        raise ValueError("Job telegram checksum does not match its header length")
    return telegram[1], telegram[2], telegram[offset : offset + length]


def build_bmw_fast(target: int, source: int, data: bytes) -> bytes:
    """Frame an ECU reply as the BMW-FAST response telegram a job expects."""
    if not data:
        raise ValueError("Empty diagnostic reply")
    if len(data) < 0x40:
        header = bytes((0x80 | len(data), target, source))
    elif len(data) <= 0xFF:
        header = bytes((0x80, target, source, len(data)))
    elif len(data) <= 0xFFFF:
        header = bytes((0x80, target, source, 0)) + len(data).to_bytes(2, "big")
    else:
        raise ValueError("Diagnostic reply is too long for a job telegram")
    telegram = header + data
    return telegram + bytes((checksum(telegram),))


def library_path() -> Path:
    """Locate the interpreter library in a bundle or the source tree."""
    name = "libedx.dylib" if sys.platform == "darwin" else "libedx.so"
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle is not None:
        return Path(bundle) / name
    return Path(__file__).resolve().parents[1] / "native" / "build" / name


_lib: ctypes.CDLL | None = None
_lib_lock = Lock()


def _library() -> ctypes.CDLL:
    global _lib
    with _lib_lock:
        if _lib is not None:
            return _lib
        path = library_path()
        if not path.is_file():
            raise JobError("Job interpreter is not built; run scripts/build_native.sh")
        lib = ctypes.CDLL(str(path))
        p, size = ctypes.c_void_p, ctypes.c_size_t
        signatures: dict[str, tuple[Any, list[Any]]] = {
            "edx_api_version": (ctypes.c_int, []),
            "edx_create": (p, []),
            "edx_destroy": (None, [p]),
            "edx_set_send": (None, [p, _SendCallback, p]),
            "edx_set_ecu_dir": (ctypes.c_int, [p, ctypes.c_char_p]),
            "edx_load_file": (ctypes.c_int, [p, ctypes.c_char_p]),
            "edx_run_job": (
                ctypes.c_int,
                [p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, size, ctypes.c_uint32],
            ),
            "edx_request_break": (None, [p]),
            "edx_vm_error": (ctypes.c_int, [p]),
            "edx_sgbd_name": (ctypes.c_char_p, [p]),
            "edx_is_group": (ctypes.c_int, [p]),
            "edx_job_count": (size, [p]),
            "edx_job_name": (ctypes.c_char_p, [p, size]),
            "edx_set_count": (size, [p]),
            "edx_result_count": (size, [p, size]),
            "edx_result_name": (ctypes.c_char_p, [p, size, size]),
            "edx_result_type": (ctypes.c_int, [p, size, size]),
            "edx_result_int": (ctypes.c_int64, [p, size, size]),
            "edx_result_float": (ctypes.c_double, [p, size, size]),
            "edx_result_data": (
                ctypes.POINTER(ctypes.c_uint8),
                [p, size, size, ctypes.POINTER(size)],
            ),
        }
        for name, (restype, argtypes) in signatures.items():
            function = getattr(lib, name)
            function.restype = restype
            function.argtypes = argtypes
        if lib.edx_api_version() != API_VERSION:
            raise JobError("Job interpreter library version does not match the app")
        _lib = lib
        return lib


def _check_worker() -> None:
    app = QCoreApplication.instance()
    if app is not None and QThread.currentThread() == app.thread():
        raise RuntimeError("Vehicle jobs must run in CarWorker")


def _text(raw: bytes | None) -> str:
    return (raw or b"").decode("cp1252", errors="replace")


class JobEngine:
    """Run one loaded job file's jobs over a ``DiagnosticConnection``.

    The engine is confined to the calling CarWorker; jobs are serialized. A group
    file (GRP) is resolved to its variant by the interpreter's own identification
    job on the first job run, loading the variant from ``ecu_dir``.
    """

    def __init__(self, connection: Any) -> None:
        """Bind an engine to a live diagnostic connection.

        Args:
            connection: A connected ``DiagnosticConnection`` (HSFZ).
        """
        self.connection = connection
        self._lib = _library()
        self._ctx = self._lib.edx_create()
        if not self._ctx:
            raise JobError("Job interpreter could not be created")
        self._callback = _SendCallback(self._send)
        self._lib.edx_set_send(self._ctx, self._callback, None)
        self._lock = Lock()
        self._path: Path | None = None
        self._ecu_dir: Path | None = None
        self._stale = False
        self._job: OperationContext | None = None
        self._job_name = ""
        self._failure: BaseException | None = None
        self._telegrams = 0
        self._mutated = False
        self._grant: frozenset[int] = frozenset()
        self._ctx_lock = Lock()

    def close(self) -> None:
        """Release the native context; the engine cannot be used afterwards."""
        with self._lock, self._ctx_lock:
            if self._ctx:
                self._lib.edx_destroy(self._ctx)
                self._ctx = None

    def __del__(self) -> None:
        ctx = getattr(self, "_ctx", None)
        if ctx:
            self._lib.edx_destroy(ctx)
            self._ctx = None

    @property
    def sgbd(self) -> str:
        """Name of the loaded job file (the variant once a group is resolved)."""
        return _text(self._lib.edx_sgbd_name(self._ctx))

    @property
    def is_group(self) -> bool:
        """Whether the loaded file is a still-unresolved group file."""
        return bool(self._lib.edx_is_group(self._ctx))

    def jobs(self) -> list[str]:
        """Job names of the loaded file."""
        count = self._lib.edx_job_count(self._ctx)
        return [_text(self._lib.edx_job_name(self._ctx, i)) for i in range(count)]

    def load(self, path: str | Path, ecu_dir: str | Path | None = None) -> None:
        """Load a PRG/GRP; GRP variants and external tables come from ``ecu_dir``.

        Args:
            path: Job file path.
            ecu_dir: Directory of job files; defaults to the file's directory.

        Raises:
            JobError: The file is missing or is not a job file.
        """
        file = Path(path)
        directory = Path(ecu_dir) if ecu_dir is not None else file.parent
        with self._lock:
            self._load(file, directory)

    def _load(self, file: Path, directory: Path) -> None:
        if not file.is_file() or not directory.is_dir():
            raise JobError("Job file or job directory is missing")
        if self._lib.edx_set_ecu_dir(self._ctx, str(directory).encode()) != _OK:
            raise JobError("Job directory could not be set")
        if self._lib.edx_load_file(self._ctx, str(file).encode()) != _OK:
            raise JobError(f"{file.name} is not a readable job file")
        self._path, self._ecu_dir, self._stale = file, directory, False

    def resolve_variant(self, *, timeout: float = 30.0, cancelled: Event | None = None) -> str:
        """Identify a group file's ECU variant through the interpreter.

        Runs ``INFO``, which makes the interpreter run INITIALISIERUNG and
        IDENTIFIKATION on the group and swap in the identified variant.

        Returns:
            The variant name. Raises ``JobError`` if no variant was identified.
        """
        self.run_job("INFO", timeout=timeout, cancelled=cancelled)
        return self.sgbd

    def run_job(
        self,
        job: str,
        args: str = "",
        *,
        data: bytes = b"",
        timeout: float = 30.0,
        cancelled: Event | None = None,
        grant: frozenset[int] = frozenset(),
    ) -> JobResult:
        """Run a job; one absolute deadline covers queueing and every telegram.

        Args:
            job: Job name, e.g. ``"FS_LESEN"``.
            args: Semicolon-separated job arguments.
            data: Binary job argument (apiJobData), if the job takes one.
            timeout: Overall job budget in seconds.
            cancelled: Optional cancellation token checked at every telegram.
            grant: Non-read services this job may send (from a write contract).

        Returns:
            The job's result sets.

        Raises:
            PermissionError: A telegram was refused by the read-only policy.
            TimeoutError: The job budget expired.
            ConnectionError: The vehicle exchange failed or was cancelled.
            ValueError: A telegram was malformed or unsupported.
            JobError: The interpreter or job file failed.
        """
        _check_worker()
        with self._lock:
            if not self._ctx or self._path is None or self._ecu_dir is None:
                raise JobError("No job file is loaded")
            if self._stale:
                # A failed job can leave a half-identified group or partial state.
                self._load(self._path, self._ecu_dir)
            context = self.connection.context(timeout, cancelled)
            self._job, self._job_name = context, job
            self._failure, self._telegrams, self._mutated = None, 0, False
            self._grant = grant
            remaining = context.deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Vehicle operation timed out")
            started = time.monotonic()
            try:
                code = self._lib.edx_run_job(
                    self._ctx,
                    job.encode("cp1252"),
                    args.encode("cp1252"),
                    data or None,
                    len(data),
                    math.ceil(remaining * 1000),
                )
            finally:
                self._job = None
            logger.debug(
                "Job end sgbd=%s job=%s code=%d telegrams=%d elapsed=%.3f conn=%s",
                self.sgbd,
                job,
                code,
                self._telegrams,
                time.monotonic() - started,
                getattr(self.connection, "trace_id", ""),
            )
            unresolved = self.is_group and job.upper() != "IDENTIFIKATION"
            if code != _OK or unresolved:
                self._stale = True
                if self._mutated:
                    # A write already reached the ECU; never report a plain failure.
                    raise JobUncertain(
                        f"Job {job} stopped after a write was sent; reconnect and reread"
                    )
                if code in (_OK, _ERR_VM) and unresolved:
                    # The interpreter ignores a failed identification and stays on the group.
                    raise JobError("The ECU variant could not be identified from its group file")
                self._raise(code, job)
            return self._result(job)

    def request_break(self) -> None:
        """Ask a running job to stop at its next interpreter step (any thread)."""
        with self._ctx_lock:
            if self._ctx:
                self._lib.edx_request_break(self._ctx)

    def _raise(self, code: int, job: str) -> None:
        failure = self._failure
        if code == _ERR_ABORT and failure is not None:
            raise failure
        if code == _ERR_DEADLINE:
            raise TimeoutError("Vehicle operation timed out")
        if code == _ERR_BREAK:
            raise ConnectionError("Vehicle operation cancelled")
        detail = self._lib.edx_vm_error(self._ctx)
        reason = _VM_ERRORS[detail] if 0 <= detail < len(_VM_ERRORS) else "unknown error"
        raise JobError(f"Job {job} failed in the interpreter ({reason})")

    def _result(self, job: str) -> JobResult:
        lib, ctx = self._lib, self._ctx
        sets: list[dict[str, ResultValue]] = []
        types: list[dict[str, str]] = []
        for index in range(lib.edx_set_count(ctx)):
            values: dict[str, ResultValue] = {}
            kinds: dict[str, str] = {}
            for entry in range(lib.edx_result_count(ctx, index)):
                name = _text(lib.edx_result_name(ctx, index, entry))
                kind = lib.edx_result_type(ctx, index, entry)
                value: ResultValue
                if kind in (3, 4):
                    length = ctypes.c_size_t()
                    pointer = lib.edx_result_data(ctx, index, entry, ctypes.byref(length))
                    raw = ctypes.string_at(pointer, length.value) if pointer else b""
                    value = _text(raw.split(b"\0", 1)[0]) if kind == 3 else raw
                elif kind == 2:
                    value = float(lib.edx_result_float(ctx, index, entry))
                else:
                    value = int(lib.edx_result_int(ctx, index, entry))
                values[name] = value
                kinds[name] = _TYPE_NAMES[kind] if 0 <= kind < len(_TYPE_NAMES) else "UNKNOWN"
            sets.append(values)
            types.append(kinds)
        system = sets[0] if sets else {}
        return JobResult(
            self.sgbd, job, system, sets[1:], types[1:], self._telegrams, self._mutated
        )

    def _send(
        self,
        _user: Any,
        concept: int,
        request: Any,
        request_length: int,
        reply: Any,
        reply_capacity: int,
        reply_length: Any,
    ) -> int:
        """Native callback: exchange one telegram; any failure aborts the job."""
        try:
            telegram = ctypes.string_at(request, request_length)
            response = self._exchange(concept, telegram)
            if len(response) > reply_capacity:
                raise JobError("ECU reply exceeds the interpreter's telegram buffer")
            ctypes.memmove(reply, response, len(response))
            reply_length[0] = len(response)
            return _SEND_OK
        except _InterfaceRefusal as exc:
            logger.debug("Job telegram refused job=%s reason=%s", self._job_name, exc)
            return _SEND_ERROR
        except BaseException as exc:  # noqa: BLE001 - must not unwind through C
            if self._failure is None:
                self._failure = exc
            logger.debug("Job telegram failed job=%s error=%r", self._job_name, exc)
            return _SEND_ABORT

    def _exchange(self, concept: int, telegram: bytes) -> bytes:
        job = self._job
        if job is None:
            raise JobError("Telegram outside a running job")
        if concept not in BMW_FAST_CONCEPTS:
            raise _InterfaceRefusal(f"interface concept 0x{concept:04X} is not supported")
        target, source, data = parse_bmw_fast(telegram)
        if target in FUNCTIONAL_TARGETS:
            raise ValueError("Functional job telegrams are not supported")
        if source != TESTER_ADDRESS:
            raise ValueError("Job telegram has an unexpected tester address")
        job.remaining()
        self._telegrams += 1
        logger.debug(
            "Job TX sgbd=%s job=%s ecu=0x%02X telegram=%s",
            self.sgbd,
            self._job_name,
            target,
            telegram.hex(" "),
        )
        # One owner submission per telegram, all bounded by the job's deadline.
        context = OperationContext(job.generation, job.deadline, cancelled=job.cancelled)
        try:
            payload = self.connection.send_uds(
                target, data, context=context, raw=True, grant=self._grant
            )
        finally:
            # The adapter marks sent/mutation on this context even when the call raises.
            self._mutated |= context.sent and context.mutation
        response = build_bmw_fast(TESTER_ADDRESS, target, payload)
        logger.debug(
            "Job RX sgbd=%s job=%s ecu=0x%02X telegram=%s",
            self.sgbd,
            self._job_name,
            target,
            response.hex(" "),
        )
        return response
