"""CarWorker — QThread base class for all background car I/O.

Every operation that talks to the car runs on a background thread via
CarWorker subclasses. This ensures the Qt UI stays responsive.

Reference: docs/17-ui-decisions.md (Decision #4: one reusable CarWorker pattern)
"""

import logging
import time
from collections.abc import Callable
from contextlib import nullcontext
from threading import Event
from typing import Any

from PySide6.QtCore import QThread, Signal

from app.protocol.contracts import OperationCancelled
from app.protocol.owner import ProtocolOwner

logger = logging.getLogger(__name__)


class CarWorker(QThread):
    """Base class for all car I/O operations.

    Subclass and override do_work(). The worker automatically handles
    started/progress/result_ready/error signal emission and TimeoutError handling.

    Signals:
        started: Emitted when the thread begins execution.
        progress: Emitted with a status message for the UI spinner.
        result_ready: Emitted with the result of do_work() on success.
        error: Emitted with a user-friendly error message on failure.

    Example:
        >>> worker = DtcReadWorker(connection, ecus)
        >>> worker.progress.connect(spinner.set_label)
        >>> worker.result_ready.connect(show_dtc_list)
        >>> worker.error.connect(show_error)
        >>> worker.start()
    """

    started = Signal()
    progress = Signal(str)
    result_ready = Signal(object)
    error = Signal(str)

    def __init__(self, connection: Any) -> None:
        """Create a CarWorker bound to a connection.

        Args:
            connection: An HSFZConnection, DoIPConnection, or MockConnection.
        """
        super().__init__()
        self.connection = connection
        self._cancelled = Event()

    def run(self) -> None:
        """Execute the worker on the background thread.

        Emits started, then calls do_work(). On success emits result_ready(result).
        On TimeoutError emits a friendly error message.
        On any other exception emits the error string.
        """
        self.started.emit()
        started = time.monotonic()
        logger.info(
            "Worker start operation=%s conn=%s",
            type(self).__name__,
            getattr(self.connection, "trace_id", "demo/setup"),
        )
        try:
            if hasattr(self.connection, "set_caller_cancel"):
                self.connection.set_caller_cancel(self._cancelled)
            result = self.do_work()
            self.result_ready.emit(result)
        except TimeoutError as e:
            msg = str(e) if str(e) else "Car operation timed out"
            logger.warning("CarWorker timeout: %s", msg)
            self.error.emit(msg)
        except Exception as e:
            msg = str(e) if str(e) else "An unexpected error occurred"
            logger.error("CarWorker error: %s", e, exc_info=True)
            self.error.emit(msg)
        finally:
            logger.info(
                "Worker end operation=%s conn=%s elapsed=%.3fs",
                type(self).__name__,
                getattr(self.connection, "trace_id", "demo/setup"),
                time.monotonic() - started,
            )

    def requestInterruption(self) -> None:
        """Propagate interruption into bounded live transport operations."""
        self._cancelled.set()
        super().requestInterruption()

    def do_work(self) -> Any:
        """Override in subclasses — performs the actual car I/O.

        Returns:
            Any result data delivered by result_ready; native finished marks thread exit.

        Raises:
            TimeoutError: Raised by connection on 30s timeout.
            ConnectionError: Raised if connection is lost.
        """
        raise NotImplementedError("Subclasses must override do_work()")


# ── Post-connect data loading ────────────────────────────────────────────────

# A task in the post-connect queue.
# Each task has a human label and a callable that receives the connection
# and returns the parsed value.  The callable may send multiple UDS
# requests internally (e.g. try KOMBI for mileage, then fall back to ZGW).
PostConnectTask = tuple[
    str,  # label for progress (e.g. "VIN")
    Callable[[Any], object],  # fn(connection) -> parsed value
]


class PostConnectWorker(CarWorker):
    """Sequential post-connect data loader.

    Processes a queue of data-loading tasks one at a time on a
    background thread.  Each task receives the connection and may
    make multiple ``send_uds()`` calls internally (with fallbacks
    for different ECUs or DIDs).

    Emits ``progress`` with labels like ``"Reading VIN... (2/8)"``
    so the UI can show a spinner with queue status.

    Results are returned as a dict::

        {
            "results": {
                "vin": "WBA...",
                "mileage": "66,000 km",
                ...
            },
            "errors": {
                "battery": "ECU 0x12 did not respond within 5s",
                ...
            },
        }

    The ``results`` dict maps task labels (lowercased, underscored)
    to their parsed values.  The ``errors`` dict maps labels that
    failed to friendly error strings.
    """

    def __init__(
        self,
        connection: Any,
        tasks: list[PostConnectTask],
    ) -> None:
        """Create a post-connect worker.

        Args:
            connection: An HSFZConnection, DoIPConnection, or MockConnection.
            tasks: List of (label, fn) tuples.
        """
        super().__init__(connection)
        self.tasks = tasks

    def do_work(self) -> dict[str, dict[str, object]]:
        """Process all tasks sequentially.

        Returns:
            Dict with ``results`` and ``errors`` keys.
        """
        total = len(self.tasks)
        results: dict[str, object] = {}
        errors: dict[str, object] = {}

        for i, (label, task_fn) in enumerate(self.tasks, start=1):
            if self.isInterruptionRequested():
                break
            self.progress.emit(f"Reading {label}... ({i}/{total})")

            try:
                scope = (
                    self.connection.operation_scope(30.0)
                    if hasattr(self.connection, "operation_scope")
                    else nullcontext()
                )
                with scope:
                    value = task_fn(self.connection)
                results[label.lower().replace(" ", "_")] = value
                logger.debug("PostConnect result label=%s value=%r", label, value)
                logger.debug(
                    "PostConnect: %s OK (%d/%d)",
                    label,
                    i,
                    total,
                )
            except TimeoutError as e:
                msg = str(e) if str(e) else f"{label} timed out"
                logger.warning("PostConnect: %s — timeout", label)
                errors[label.lower().replace(" ", "_")] = msg
            except ConnectionError as e:
                msg = str(e) if str(e) else f"Connection lost while reading {label}"
                logger.warning("PostConnect: %s — %s", label, msg)
                errors[label.lower().replace(" ", "_")] = msg
            except Exception as e:
                logger.warning(
                    "PostConnect: %s — %s",
                    label,
                    e,
                    exc_info=True,
                )
                errors[label.lower().replace(" ", "_")] = str(e)

        if errors:
            logger.info(
                "PostConnect done: %d/%d succeeded, %d errors",
                len(results),
                total,
                len(errors),
            )
        else:
            logger.info(
                "PostConnect done: all %d requests succeeded",
                total,
            )

        return {"results": results, "errors": errors}


class ConnectWorker(CarWorker):
    """Run connection setup with an interruptible wait/cancellation token."""

    def __init__(self, fn: Callable[[Event], object], series: str) -> None:
        """Retain setup work and the selected series for result delivery."""
        super().__init__(None)
        self.fn = fn
        self.series = series
        self._cancelled = Event()

    @property
    def cancelled(self) -> bool:
        """Whether this attempt was cancelled by disconnect, retry or shutdown."""
        return self._cancelled.is_set()

    def stop(self) -> None:
        """Wake connection waits and request cancellation at the next boundary."""
        self._cancelled.set()
        self.requestInterruption()

    def do_work(self) -> object:
        """Execute the connection attempt with the cancellation event."""
        return self.fn(self._cancelled)


class ProtocolWorker(CarWorker):
    """Host the staged protocol owner on a QThread without opening a transport."""

    def __init__(self, owner: ProtocolOwner) -> None:
        """Bind one owner; callers retain the worker until native finished()."""
        super().__init__(None)
        self.owner = owner

    def do_work(self) -> None:
        """Run all queued operations and resource cleanup on this thread."""
        try:
            self.owner.run()
        except OperationCancelled:
            if not self.owner.stop_event.is_set():
                raise
        except Exception as exc:
            logger.debug("Protocol owner stopped", exc_info=True)
            raise ConnectionError(
                "Vehicle connection lost. Check the cable and reconnect."
            ) from exc

    def stop(self) -> None:
        """Request cooperative shutdown without waiting on the GUI thread."""
        self.owner.request_close()
