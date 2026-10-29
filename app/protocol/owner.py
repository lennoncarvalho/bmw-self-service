"""Single-executor operation queue for staged protocol migration (spec 25).

Adapters execute only inside run(), hosted by ProtocolWorker. Idle controls,
sessions and complete UDS transactions share this executor and absolute budgets.
"""

import logging
import time
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass
from queue import Empty, Queue
from threading import Event, Lock, get_ident

from app.protocol.contracts import (
    FailureKind,
    OperationCancelled,
    OperationContext,
    OperationOutcome,
    ProtocolFailure,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OperationHandle:
    """Submission identity and asynchronous completion; never wait on the GUI."""

    context: OperationContext
    completion: Future[OperationOutcome]

    def cancel(self) -> None:
        """Signal cooperative cancellation without socket or Qt calls."""
        self.context.cancelled.set()


@dataclass(frozen=True)
class _Command:
    handle: OperationHandle
    operation: Callable[[OperationContext], bytes]


class ProtocolOwner:
    """Serialize operations on one executor, including final resource cleanup.

    Submission and close are nonblocking and thread safe. Each context is used
    once. Operations must use bounded I/O and cancellation checks; this class
    cannot safely interrupt an arbitrary blocking third-party function.
    """

    def __init__(
        self,
        generation: str,
        close_transport: Callable[[], None],
        idle: Callable[[], None] | None = None,
    ) -> None:
        """Prepare an unopened owner; construction never starts threads or I/O."""
        if not generation:
            raise ValueError("Connection generation is required")
        self.generation = generation
        self._close_transport = close_transport
        self._idle = idle
        self._queue: Queue[_Command | None] = Queue()
        self._lock = Lock()
        self._closing = False
        self.stop_event = Event()
        self._started = False
        self._executor: int | None = None
        self._active: OperationHandle | None = None
        self._submitted: set[str] = set()

    def submit(
        self, operation: Callable[[OperationContext], bytes], context: OperationContext
    ) -> OperationHandle:
        """Queue work with its existing budget, or reject a closed/stale owner."""
        completion: Future[OperationOutcome] = Future()
        completion.set_running_or_notify_cancel()
        handle = OperationHandle(context, completion)
        with self._lock:
            if self._executor == get_ident():
                raise RuntimeError("Owner operations must execute nested work inline")
            if context.generation != self.generation:
                raise ValueError("Operation belongs to another connection generation")
            if context.operation_id in self._submitted:
                raise ValueError("An operation context may only be submitted once")
            self._submitted.add(context.operation_id)
            closing = self._closing
            if not closing:
                self._queue.put(_Command(handle, operation))
        if closing:
            self._complete(handle, FailureKind.CLOSED)
        return handle

    def request_close(self) -> None:
        """Cancel active/queued work; the executor performs actual socket cleanup."""
        with self._lock:
            if self._closing:
                return
            self._closing = True
            self.stop_event.set()
            if self._active is not None:
                self._active.cancel()
            self._queue.put(None)

    @staticmethod
    def _complete(handle: OperationHandle, failure: FailureKind) -> None:
        context = handle.context
        if context.sent and context.mutation:
            failure = FailureKind.UNCERTAIN
        logger.debug(
            "Operation failure conn=%s operation=%s kind=%s sent=%s",
            context.generation,
            context.operation_id,
            failure,
            context.sent,
        )
        handle.completion.set_result(
            OperationOutcome(
                context.operation_id,
                context.generation,
                failure=failure,
                sent=context.sent,
                ecu=context.ecu,
                request_id=context.request_id,
            )
        )

    def run(self) -> None:
        """Execute once on a background worker and settle every accepted handle."""
        with self._lock:
            if self._started:
                raise RuntimeError("Protocol owner cannot be restarted")
            self._started = True
            self._executor = get_ident()
        try:
            while True:
                try:
                    command = self._queue.get(timeout=0.05)
                except Empty:
                    if self._idle is not None:
                        self._idle()
                    continue
                if command is None:
                    break
                handle = command.handle
                with self._lock:
                    closing = self._closing
                    self._active = handle
                if closing:
                    self._complete(handle, FailureKind.CLOSED)
                    continue
                context = handle.context
                logger.debug(
                    "Operation begin conn=%s operation=%s remaining=%.3f",
                    context.generation,
                    context.operation_id,
                    context.deadline - time.monotonic(),
                )
                try:
                    context.remaining()
                    payload = command.operation(context)
                    context.remaining()
                    if not isinstance(payload, bytes):
                        raise TypeError("Protocol operation must return immutable bytes")
                    handle.completion.set_result(
                        OperationOutcome(
                            context.operation_id,
                            context.generation,
                            payload=payload,
                            sent=context.sent,
                            ecu=context.ecu,
                            request_id=context.request_id,
                        )
                    )
                except ProtocolFailure as exc:
                    logger.debug(
                        "Service failure conn=%s operation=%s kind=%s",
                        context.generation,
                        context.operation_id,
                        exc.kind,
                        exc_info=True,
                    )
                    if exc.reconnect:
                        self.request_close()
                    handle.completion.set_result(
                        OperationOutcome(
                            context.operation_id,
                            context.generation,
                            payload=exc.raw,
                            failure=(
                                FailureKind.UNCERTAIN
                                if exc.reconnect and context.mutation
                                else exc.kind
                            ),
                            sent=context.sent,
                            ecu=context.ecu,
                            request_id=context.request_id,
                        )
                    )
                except PermissionError:
                    self._complete(handle, FailureKind.POLICY)
                except ValueError:
                    if context.sent:
                        self.request_close()
                    self._complete(
                        handle, FailureKind.INVALID if context.sent else FailureKind.UNSUPPORTED
                    )
                except OperationCancelled:
                    if context.sent:
                        self.request_close()
                    self._complete(handle, FailureKind.CANCELLED)
                except TimeoutError:
                    if context.sent:
                        self.request_close()
                    self._complete(handle, FailureKind.TIMEOUT)
                except ConnectionError:
                    self.request_close()
                    logger.debug("Transport lost operation=%s", context.operation_id, exc_info=True)
                    self._complete(handle, FailureKind.CONNECTION_LOST)
                except Exception:
                    if context.sent:
                        self.request_close()
                    logger.exception(
                        "Protocol operation failed operation=%s generation=%s",
                        context.operation_id,
                        context.generation,
                    )
                    self._complete(handle, FailureKind.FAILED)
                finally:
                    logger.debug(
                        "Operation end conn=%s operation=%s elapsed=%.3f sent=%s",
                        context.generation,
                        context.operation_id,
                        time.monotonic() - context.created_at,
                        context.sent,
                    )
                    with self._lock:
                        self._active = None
        finally:
            self.request_close()
            try:
                self._close_transport()
            finally:
                while not self._queue.empty():
                    pending = self._queue.get_nowait()
                    if pending is not None:
                        self._complete(pending.handle, FailureKind.CLOSED)
