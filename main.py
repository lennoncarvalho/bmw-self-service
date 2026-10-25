"""BMW Self Service — entry point.

Cross-platform desktop app for BMW diagnostics, coding, and service history
via ENET cable (F/G/U/I-series, 2011+).

Usage:
    python main.py
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.theme import apply_theme
from ui.main_window import MainWindow


def setup_logging() -> None:
    """Configure UDS debug logging to rotating files.

    Writes to ~/BMW-Tool/logs/uds.log with 5 MB max size, 3 backup files.
    """
    log_dir = Path.home() / "BMW-Tool" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    handler = logging.handlers.RotatingFileHandler(
        log_dir / "uds.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)

    # Also log to stdout at INFO level for development
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    root.addHandler(console)


def main() -> None:
    """Launch the BMW Self Service application."""
    setup_logging()

    app = QApplication(sys.argv)
    app.setApplicationName("BMW Self Service")
    app.setOrganizationName("BMWSelfService")

    apply_theme(app)

    window = MainWindow()
    window.showMaximized()

    logging.getLogger(__name__).info("Application started")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()