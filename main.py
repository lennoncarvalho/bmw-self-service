"""BMW Self Service — entry point.

Cross-platform desktop app for BMW diagnostics, coding, and service history
via ENET cable (F/G/U/I-series, 2011+).

Usage:
    python3 main.py             # normal console, full session log
    python3 main.py --debug     # verbose console as well
    python3 main.py --no-log    # no log file (console only)
"""

import argparse
import gc
import logging
import logging.handlers
import os
import platform as platform_module
import subprocess
import sys
import time
from datetime import UTC, datetime
from io import TextIOWrapper
from pathlib import Path
from types import TracebackType

from PySide6.QtCore import QMessageLogContext, QTimer, QtMsgType, qInstallMessageHandler
from PySide6.QtWidgets import QApplication

from app.theme import apply_theme
from ui.main_window import MainWindow


class _PrivateRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """Keep session files private on creation, reopening and rotation."""

    def _open(self) -> TextIOWrapper:
        """Open with owner-only access without changing the process-wide umask."""

        def private_open(path: str, flags: int) -> int:
            """Restrict new and existing files before the logging stream can write."""
            descriptor = os.open(path, flags, 0o600)
            try:
                os.fchmod(descriptor, 0o600)
            except OSError:
                os.close(descriptor)
                raise
            return descriptor

        return open(
            self.baseFilename, "a", encoding=self.encoding, errors=self.errors, opener=private_open
        )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="BMW Self Service — BMW diagnostics via ENET cable",
    )
    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Show debug logging on the console (session files always retain full details)",
    )
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="Skip writing the log file (console only)",
    )
    parser.add_argument(
        "--read-only",
        action="store_true",
        help="Block vehicle writes, clears, resets and routines; disable automatic network changes",
    )
    return parser.parse_args()


def setup_logging(debug: bool = False, no_log: bool = False) -> Path | None:
    """Configure logging.

    Console: always INFO level (DEBUG if --debug).
    File: a unique UTC timestamp/PID session in the app root's logs/ folder,
    10 MiB per segment plus five rotated segments. Always retains DEBUG traffic.
    Falls back to ~/BMW-Tool/logs or console-only logging if storage is unavailable.
    Directories and files have owner-only permissions. Existing sessions are
    preserved. Returns the file path or None.
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03dZ +%(relativeCreated).0fms "
        "%(levelname)-7s [%(threadName)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    formatter.converter = time.gmtime
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG if debug else logging.INFO)
    console.setFormatter(formatter)
    root.addHandler(console)

    log_path: Path | None = None
    if not no_log:
        preferred_dir = Path(__file__).resolve().parent / "logs"
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        for log_dir in (preferred_dir, Path.home() / "BMW-Tool" / "logs"):
            try:
                log_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
                log_dir.chmod(0o700)
                candidate = log_dir / f"session-{stamp}-{os.getpid()}.log"
                file_handler = _PrivateRotatingFileHandler(
                    candidate, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
                )
            except OSError as exc:
                root.warning("Session log directory unavailable: %s (%s)", log_dir, exc)
                continue
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
            log_path = candidate
            if log_dir != preferred_dir:
                root.warning("Using fallback session log: %s", log_path)
            break
        else:
            root.warning("File logging unavailable; continuing with console logging only")

    def log_qt(kind: QtMsgType, context: QMessageLogContext, message: str) -> None:
        """Record Qt diagnostic messages in the active session log without calling back into Qt."""
        levels = {
            QtMsgType.QtDebugMsg: logging.DEBUG,
            QtMsgType.QtInfoMsg: logging.INFO,
            QtMsgType.QtWarningMsg: logging.WARNING,
            QtMsgType.QtCriticalMsg: logging.ERROR,
            QtMsgType.QtFatalMsg: logging.CRITICAL,
        }
        logging.getLogger("qt").log(
            levels.get(kind, logging.WARNING), "%s (%s:%s)", message, context.file, context.line
        )

    qInstallMessageHandler(log_qt)

    def log_uncaught(
        exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None
    ) -> None:
        """Preserve uncaught Python exception tracebacks in the session handlers."""
        logging.getLogger(__name__).critical(
            "Unhandled application exception", exc_info=(exc_type, exc, tb)
        )

    # Preserve tracebacks from uncaught main-thread/Qt Python callbacks in the
    # same session file. Worker exceptions are already handled by CarWorker.
    sys.excepthook = log_uncaught
    return log_path


def log_startup(log: logging.Logger) -> None:
    """Log environment diagnostics; the welcome worker logs adapter inventory."""
    log.info("=== BMW Self Service starting ===")
    log.info(
        "Python %s on %s %s",
        platform_module.python_version(),
        platform_module.system(),
        platform_module.release(),
    )
    log.info("Platform: %s", platform_module.platform())
    log.info("Executable=%s cwd=%s", sys.executable, Path.cwd())
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        ).stdout.strip()
        log.info("Source revision=%s", revision)
    except (OSError, subprocess.SubprocessError):
        log.info("Source revision unavailable (packaged build or Git not installed)")

    try:
        import PySide6
        from PySide6.QtCore import qVersion

        log.info("PySide6 %s / Qt %s", PySide6.__version__, qVersion())
    except ImportError:
        log.warning("PySide6 version unknown")


def main() -> None:
    """Launch the BMW Self Service application."""
    args = parse_args()
    log_path = setup_logging(debug=args.debug, no_log=args.no_log)

    log = logging.getLogger(__name__)
    log.info("Session log=%s debug=%s read_only=%s", log_path, args.debug, args.read_only)
    log_startup(log)

    app = QApplication(sys.argv)
    app.setApplicationName("BMW Self Service")
    app.setOrganizationName("BMWSelfService")

    apply_theme(app)
    log.info("Theme applied")

    # A cyclic collection triggered on a worker thread can free Qt objects off the GUI
    # thread and crash PySide. Collect only on the GUI thread instead.
    gc.disable()
    collector = QTimer(app)
    collector.timeout.connect(gc.collect)
    collector.start(5000)

    window = MainWindow(read_only=args.read_only)
    window.showMaximized()
    log.info("MainWindow shown, entering event loop")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
