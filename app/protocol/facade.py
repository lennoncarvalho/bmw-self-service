"""Public synchronous worker API over a single background protocol executor."""

import contextlib
import logging
import time
import uuid
from collections.abc import Callable, Iterator
from threading import Event, Lock, get_ident, local

from PySide6.QtCore import QCoreApplication, Qt, QThread

from app.protocol.contracts import (
    ConnectionConfig,
    EcuIdentity,
    FailureKind,
    OperationContext,
    OperationOutcome,
    TransportKind,
)
from app.protocol.doip import DoipAdapter
from app.protocol.hsfz import HsfzAdapter
from app.protocol.owner import OperationHandle, ProtocolOwner
from app.protocol.stream import BoundedStream
from app.protocol.udsoncan_connection import UdsConnection
from app.uds import UdsServices

logger = logging.getLogger(__name__)
_live: set["DiagnosticConnection"] = set()
_live_lock = Lock()


def protocol_workers() -> tuple[QThread, ...]:
    """Snapshot retained owners so application shutdown can settle setup races."""
    with _live_lock:
        return tuple(connection.worker for connection in _live)


class DiagnosticConnection:
    """Own one adapter/client executor; GUI close requests never wait for locks."""

    kind = TransportKind.HSFZ
    default_port = 6801

    def __init__(
        self,
        host: str,
        port: int | None = None,
        *,
        read_only: bool = False,
        local_ip: str,
        entity: int = 0x10,
    ) -> None:
        self.host = host
        self.port = port or self.default_port
        self.config = ConnectionConfig(self.kind, host, local_ip, self.port, entity)
        self.local_ip = local_ip
        self.entity = entity
        self.read_only = read_only
        self.trace_id = uuid.uuid4().hex
        self.adapter: HsfzAdapter | DoipAdapter | None = None
        self._services: dict[int, UdsServices] = {}
        self._last_session: dict[int, float] = {}
        self._executor: int | None = None
        self._active: OperationContext | None = None
        self._caller = local()
        self._closed = Event()
        self._owner = ProtocolOwner(self.trace_id, self._close, self._idle)
        from app.worker import ProtocolWorker

        self.worker = ProtocolWorker(self._owner)
        app = QCoreApplication.instance()
        if app is not None:
            # A connection may be created by ConnectWorker; keep the QThread
            # object on the GUI loop so later deleteLater() can be delivered.
            self.worker.moveToThread(app.thread())
        self.worker.finished.connect(self._finished, Qt.ConnectionType.DirectConnection)
        with _live_lock:
            _live.add(self)
        self.worker.start()

    def _finished(self) -> None:
        self._closed.set()
        with _live_lock:
            _live.discard(self)

    @staticmethod
    def _check_worker() -> None:
        app = QCoreApplication.instance()
        if app is not None and QThread.currentThread() == app.thread():
            raise RuntimeError("Live diagnostic waits must run in CarWorker")

    def context(self, timeout: float = 30.0, cancelled: Event | None = None) -> OperationContext:
        """Create an operation budget at submission, including queue time."""
        ctx = OperationContext.create(self.trace_id, timeout)
        if cancelled is not None:
            ctx.cancelled = cancelled
        elif getattr(self._caller, "cancelled", None) is not None:
            ctx.cancelled = self._caller.cancelled
        return ctx

    @contextlib.contextmanager
    def operation_scope(self, timeout: float = 30.0) -> Iterator[None]:
        """Share one deadline across compatibility fallbacks in this caller only."""
        previous = getattr(self._caller, "scope", None)
        self._caller.scope = self.context(timeout)
        try:
            yield
        finally:
            self._caller.scope = previous

    def set_caller_cancel(self, cancelled: Event) -> None:
        """Bind this worker's cancellation token without sharing caller state."""
        self._caller.cancelled = cancelled

    def _call(
        self,
        operation: Callable[[OperationContext], bytes],
        ctx: OperationContext,
        *,
        accept_negative: bool = False,
    ) -> bytes:
        self._check_worker()
        if self._executor == get_ident():
            return operation(self._active or ctx)
        handle = self._owner.submit(operation, ctx)
        # The operation owner also checks the context; caller cancellation wakes
        # bounded socket reads rather than releasing stream ownership prematurely.
        result = handle.completion.result()
        if accept_negative and result.failure == FailureKind.NEGATIVE:
            return result.payload or b""
        if result.failure is not None:
            if result.failure == FailureKind.TIMEOUT:
                raise TimeoutError("Vehicle operation timed out")
            if result.failure == FailureKind.CANCELLED:
                raise ConnectionError("Vehicle operation cancelled")
            if result.failure == FailureKind.UNCERTAIN:
                raise ConnectionError(
                    "Vehicle outcome is uncertain; reconnect and reread before recovery"
                )
            raise ConnectionError("Vehicle operation failed; reconnect if the connection was lost")
        return result.payload or b""

    def connect(self, context: OperationContext | None = None) -> bool:
        """Open source-bound TCP on the owner, using the setup deadline."""
        ctx = context or self.context(5.0)
        ctx.deadline = min(ctx.deadline, time.monotonic() + 5.0)

        def open_transport(active: OperationContext) -> bytes:
            self._executor = get_ident()
            stream = BoundedStream.connect(self.host, self.port, self.local_ip, active)
            self.adapter = (
                HsfzAdapter(stream, self.read_only)
                if self.kind == TransportKind.HSFZ
                else DoipAdapter(stream, self.read_only)
            )
            return b""

        self._call(open_transport, ctx)
        return True

    def activate_routing(self, context: OperationContext | None = None) -> bool:
        """Perform library-encoded routing activation on the same owner."""

        def activate(ctx: OperationContext) -> bytes:
            if not isinstance(self.adapter, DoipAdapter):
                raise ConnectionError("No DoIP adapter")
            self.adapter.activate(ctx, self.entity)
            return b""

        ctx = context or self.context(5.0)
        ctx.deadline = min(ctx.deadline, time.monotonic() + 5.0)
        self._call(activate, ctx)
        return True

    def _service(self, address: int) -> UdsServices:
        if self.adapter is None:
            raise ConnectionError("Vehicle is not connected")
        if address not in self._services:
            ecu = EcuIdentity(self.trace_id, self.kind, address)
            self._services[address] = UdsServices(UdsConnection(self.adapter, ecu))
        return self._services[address]

    def submit_operation(
        self,
        ecu: int,
        operation: Callable[[UdsServices, OperationContext], bytes],
        *,
        context: OperationContext,
    ) -> OperationHandle:
        """Submit without blocking; callbacks execute on the owner, never the GUI."""

        def execute(ctx: OperationContext) -> bytes:
            self._active = ctx
            try:
                return operation(self._service(ecu), ctx)
            finally:
                self._active = None

        return self._owner.submit(execute, context)

    def run_operation(
        self,
        ecu: int,
        operation: Callable[[UdsServices, OperationContext], bytes],
        *,
        context: OperationContext,
    ) -> bytes:
        """Execute a complete service sequence synchronously from a CarWorker."""

        def execute(ctx: OperationContext) -> bytes:
            self._active = ctx
            try:
                return operation(self._service(ecu), ctx)
            finally:
                self._active = None

        return self._call(execute, context)

    def register_ecu(self, identity: EcuIdentity, *, context: OperationContext) -> None:
        """Refine an unknown identity before registering versioned Task B codecs."""

        def register(ctx: OperationContext) -> bytes:
            ctx.remaining()
            if identity.generation != self.trace_id or identity.transport != self.kind:
                raise ValueError("ECU identity belongs to another connection")
            service = self._service(identity.address)
            previous = service.bridge.ecu
            if previous != identity and (
                previous.variant is not None or previous.software is not None
            ):
                raise ValueError("ECU identity changed; reconnect before replacing definitions")
            service.bridge.ecu = identity
            return b""

        self._call(register, context)

    def request(self, ecu: int, payload: bytes, *, context: OperationContext) -> OperationOutcome:
        """Return raw bytes and a classified outcome from one generic operation."""
        self._check_worker()
        handle = self.submit_operation(
            ecu, lambda service, ctx: service.invoke(payload, ctx), context=context
        )
        return handle.completion.result()

    def send_uds(
        self,
        ecu_addr: int,
        payload: bytes,
        timeout: float = 30.0,
        *,
        context: OperationContext | None = None,
    ) -> bytes:
        """Temporary raw compatibility through the owner's sole udsoncan client."""
        ctx = (
            context
            or (self._active if self._executor == get_ident() else None)
            or self.context(timeout)
        )

        scope = getattr(self._caller, "scope", None)
        if scope is not None:
            ctx.deadline = min(ctx.deadline, scope.deadline)
            ctx.cancelled = scope.cancelled

        def exchange(active: OperationContext) -> bytes:
            response = self._service(ecu_addr).invoke(payload, active)
            if payload[:1] == b"\x10" and response[:1] == b"\x50":
                self._last_session[ecu_addr] = time.monotonic()
            return response

        return self._call(exchange, ctx, accept_negative=True)

    def _idle(self) -> None:
        if self.adapter is None:
            return
        for services in list(self._services.values()):
            if services.session != 1 and time.monotonic() - services.last_activity >= 2.5:
                ctx = self.context(1.0, self._owner.stop_event)
                services.tester_present(ctx)
        # Preserve fragments across idle poll expiry.
        with contextlib.suppress(TimeoutError):
            self.adapter.poll(self.context(0.02, self._owner.stop_event))

    @property
    def alive_ok(self) -> bool:
        """Whether the executor remains open; not proof of ECU session health."""
        return not self._closed.is_set() and not self._owner.stop_event.is_set()

    def disconnect(self) -> None:
        """Request asynchronous shutdown without GUI-thread socket/lock waits."""
        self._owner.request_close()

    request_close = disconnect

    def _close(self) -> None:
        if self.adapter is not None:
            self.adapter.close()
            self.adapter = None
        self._services.clear()
        self._closed.set()


class HSFZConnection(DiagnosticConnection):
    """HSFZ facade; transport choice comes from validated discovery."""


class DoIPConnection(DiagnosticConnection):
    """DoIP facade with full logical addressing and routing activation."""

    kind = TransportKind.DOIP
    default_port = 13400
