"""Single-executor operation queue for staged protocol migration (spec 25).

This foundation is not connected to live transports. Future adapters execute
only inside run(), hosted by ProtocolWorker, and must honor context deadlines.
"""

import logging
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass
from queue import Queue
from threading import Lock, get_ident

from app.protocol.contracts import (
    FailureKind,
    OperationCancelled,
    OperationContext,
    OperationOutcome,
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

    def __init__(self, generation: str, close_transport: Callable[[], None]) -> None:
        """Prepare an unopened owner; construction never starts threads or I/O."""
        if not generation:
            raise ValueError("Connection generation is required")
        self.generation = generation
        self._close_transport = close_transport
        self._queue: Queue[_Command | None] = Queue()
        self._lock = Lock()
        self._closing = False
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
            if self._active is not None:
                self._active.cancel()
            self._queue.put(None)

    @staticmethod
    def _complete(handle: OperationHandle, failure: FailureKind) -> None:
        context = handle.context
        if context.sent and context.mutation:
            failure = FailureKind.UNCERTAIN
        handle.completion.set_result(
            OperationOutcome(
                context.operation_id, context.generation, failure=failure, sent=context.sent
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
                command = self._queue.get()
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
                        )
                    )
                except OperationCancelled:
                    if context.sent:
                        self.request_close()
                    self._complete(handle, FailureKind.CANCELLED)
                except TimeoutError:
                    if context.sent:
                        self.request_close()
                    self._complete(handle, FailureKind.TIMEOUT)
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
