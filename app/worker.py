"""CarWorker — QThread base class for all background car I/O.

Every operation that talks to the car runs on a background thread via
CarWorker subclasses. This ensures the Qt UI stays responsive.

Reference: docs/17-ui-decisions.md (Decision #4: one reusable CarWorker pattern)
"""

import logging
from typing import Any, Optional

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
