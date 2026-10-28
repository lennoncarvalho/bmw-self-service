"""CarWorker — QThread base class for all background car I/O.

Every operation that talks to the car runs on a background thread via
CarWorker subclasses. This ensures the Qt UI stays responsive.

Reference: docs/17-ui-decisions.md (Decision #4: one reusable CarWorker pattern)
"""

import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


class CarWorker(QThread):
    """Base class for all car I/O operations.

    Subclass and override do_work(). The worker automatically handles
    started/progress/finished/error signal emission and TimeoutError handling.

    Signals:
        started: Emitted when the thread begins execution.
        progress: Emitted with a status message for the UI spinner.
        finished: Emitted with the result of do_work() on success.
        error: Emitted with a user-friendly error message on failure.

    Example:
        >>> worker = DtcReadWorker(connection, ecus)
        >>> worker.progress.connect(spinner.set_label)
        >>> worker.finished.connect(show_dtc_list)
        >>> worker.error.connect(show_error)
        >>> worker.start()
    """

    started = Signal()
    progress = Signal(str)
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, connection: Any) -> None:
        """Create a CarWorker bound to a connection.

        Args:
            connection: An HSFZConnection, DoIPConnection, or MockConnection.
        """
        super().__init__()
        self.connection = connection

    def run(self) -> None:
        """Execute the worker on the background thread.

        Emits started, then calls do_work(). On success emits finished(result).
        On TimeoutError emits a friendly error message.
        On any other exception emits the error string.
        """
        self.started.emit()
        try:
            result = self.do_work()
            self.finished.emit(result)
        except TimeoutError as e:
            msg = str(e) if str(e) else "Car operation timed out"
            logger.warning("CarWorker timeout: %s", msg)
            self.error.emit(msg)
        except Exception as e:
            msg = str(e) if str(e) else "An unexpected error occurred"
            logger.error("CarWorker error: %s", e, exc_info=True)
            self.error.emit(msg)

    def do_work(self) -> Any:
        """Override in subclasses — performs the actual car I/O.

        Returns:
            Any result data that will be passed to the finished signal.

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
    str,                       # label for progress (e.g. "VIN")
    Callable[[Any], object],   # fn(connection) -> parsed value
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
        errors: dict[str, str] = {}

        for i, (label, task_fn) in enumerate(self.tasks, start=1):
            self.progress.emit(f"Reading {label}... ({i}/{total})")

            try:
                value = task_fn(self.connection)
                results[label.lower().replace(" ", "_")] = value
                logger.debug(
                    "PostConnect: %s OK (%d/%d)", label, i, total,
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
                    "PostConnect: %s — %s", label, e,
                )
                errors[label.lower().replace(" ", "_")] = str(e)

        if errors:
            logger.info(
                "PostConnect done: %d/%d succeeded, %d errors",
                len(results), total, len(errors),
            )
        else:
            logger.info(
                "PostConnect done: all %d requests succeeded", total,
            )

        return {"results": results, "errors": errors}
