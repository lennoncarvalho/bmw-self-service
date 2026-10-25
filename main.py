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
import platform as platform_module
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.theme import apply_theme
from ui.main_window import MainWindow


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="BMW Self Service — BMW diagnostics via ENET cable",
    )
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Enable verbose debug logging (UDS traffic, connection details)",
    )
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="Skip writing the log file (console only)",
    )
    return parser.parse_args()


def setup_logging(debug: bool = False, no_log: bool = False) -> None:
    """Configure logging.

    Console: always INFO level (DEBUG if --debug).
    File:    rotates at ~/BMW-Tool/logs/uds.log, 5 MB x 3 files.
             DEBUG level when --debug, WARNING level otherwise.
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG if debug else logging.INFO)
    console.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))
    root.addHandler(console)

    # File handler
    if not no_log:
        log_dir = Path.home() / "BMW-Tool" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "uds.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
        )
        file_handler.setLevel(logging.DEBUG if debug else logging.WARNING)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        root.addHandler(file_handler)


def log_startup(log: logging.Logger) -> None:
    """Emit startup diagnostics at INFO level."""
    log.info("=== BMW Self Service starting ===")
    log.info("Python %s on %s %s",
             platform_module.python_version(),
             platform_module.system(),
             platform_module.release())
    log.info("Platform: %s", platform_module.platform())

    try:
        import PySide6
        from PySide6.QtCore import qVersion
        log.info("PySide6 %s / Qt %s", PySide6.__version__, qVersion())
    except ImportError:
        log.warning("PySide6 version unknown")

    try:
        from app.connection import list_interfaces
        ifaces = list_interfaces()
        log.info("Ethernet interfaces: %s", ", ".join(ifaces) if ifaces else "(none)")
    except Exception as e:
        log.warning("Interface scan failed: %s", e)


def main() -> None:
    """Launch the BMW Self Service application."""
    args = parse_args()
    setup_logging(debug=args.debug, no_log=args.no_log)

    log = logging.getLogger(__name__)
    log_startup(log)

    app = QApplication(sys.argv)
    app.setApplicationName("BMW Self Service")
    app.setOrganizationName("BMWSelfService")

    apply_theme(app)
    log.info("Theme applied")

    window = MainWindow()
    window.showMaximized()
    log.info("MainWindow shown, entering event loop")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()