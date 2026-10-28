"""BMW Self Service — entry point.

Cross-platform desktop app for BMW diagnostics, coding, and service history
via ENET cable (F/G/U/I-series, 2011+).

Usage:
    python main.py              # normal mode (logs errors only)
    python main.py --debug      # verbose mode (logs all UDS traffic)
    python main.py --no-log     # no log file (console only)
"""

import argparse
import logging
import logging.handlers
import os
import platform as platform_module
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

from PySide6.QtCore import QMessageLogContext, QtMsgType, qInstallMessageHandler
from PySide6.QtWidgets import QApplication

from app.theme import apply_theme
from ui.main_window import MainWindow


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="BMW Self Service — BMW diagnostics via ENET cable",
    )
    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Enable verbose debug logging (UDS traffic, connection details)",
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
    File: a unique UTC timestamp/PID session in ~/BMW-Tool/logs, 10 MiB
    per segment plus five rotated segments. DEBUG only when --debug is selected.
    Existing session files are preserved. Returns the file path or None.
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
        log_dir = Path.home() / "BMW-Tool" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        log_path = log_dir / f"session-{stamp}-{os.getpid()}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG if debug else logging.WARNING)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

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
    """Emit startup diagnostics at INFO level."""
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

    try:
        import netifaces

        from app.connection import list_interfaces_detailed

        for interface in list_interfaces_detailed():
            log.info(
                "Adapter candidate=%s IPv4=%s MAC=%s description=%s",
                interface.name,
                interface.ip,
                interface.mac,
                interface.description,
            )
            log.debug(
                "Adapter %s IPv4 configuration=%s",
                interface.name,
                netifaces.ifaddresses(interface.name).get(netifaces.AF_INET, []),
            )
    except Exception as e:
        log.warning("Interface scan failed: %s", e)


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

    window = MainWindow(read_only=args.read_only)
    window.showMaximized()
    log.info("MainWindow shown, entering event loop")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
