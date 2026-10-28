"""Dark theme loader for the BMW Self Service.

Loads QSS from assets/theme.qss and applies it to a QApplication.
Also provides color constants for use in Python code when QSS is insufficient.

Reference: docs/17-ui-decisions.md (Decision #8: one QSS file, no per-widget styling)
"""

import os
from pathlib import Path

from PySide6.QtWidgets import QApplication

# BMW M colour palette — use these for programmatic styling only
# (e.g. status dots, dynamic colour changes). Prefer QSS for static styles.
COLOR_BG_DARK = "#1a1a2e"
COLOR_SURFACE = "#16213e"
COLOR_BORDER = "#2a2a4a"
COLOR_PRIMARY = "#1C69D4"
COLOR_PRIMARY_HOVER = "#0653B6"
COLOR_PRIMARY_PRESSED = "#0442A0"
COLOR_DANGER = "#E30B1F"
COLOR_DANGER_HOVER = "#C40A1A"
COLOR_SUCCESS = "#2ECC71"
COLOR_SUCCESS_HOVER = "#27AE60"
COLOR_WARNING = "#F39C12"
COLOR_TEXT_PRIMARY = "#e0e0e0"
COLOR_TEXT_SECONDARY = "#a0a0a0"
COLOR_TEXT_DISABLED = "#888888"
COLOR_BG_TOP_BAR = "#0f0f23"


def _find_theme_qss() -> Path:
    """Locate theme.qss relative to this module.

    Development: app/theme.py  → ../assets/theme.qss
    PyInstaller: _MEIPASS/assets/theme.qss → relative to bundle
    """
    # Try relative path first (both development and bundle)
    module_dir = Path(__file__).resolve().parent
    for candidate in [
        module_dir / ".." / "assets" / "theme.qss",
        module_dir.parent / "assets" / "theme.qss",
        # PyInstaller bundle: sys._MEIPASS + assets/theme.qss
        Path(getattr(os, "_MEIPASS", "")) / "assets" / "theme.qss",
    ]:
        try:
            resolved = candidate.resolve()
            if resolved.is_file():
                return resolved
        except (OSError, FileNotFoundError):
            pass
    raise FileNotFoundError(f"Cannot find theme.qss. Searched from module_dir={module_dir}")


def load_theme() -> str:
    """Read theme.qss and return the stylesheet string.

    Returns:
        CSS-like Qt Style Sheet string (~150 lines).

    Raises:
        FileNotFoundError: If theme.qss can't be found.
    """
    path = _find_theme_qss()
    with open(path, encoding="utf-8") as f:
        return f.read()


def apply_theme(app: QApplication) -> None:
    """Apply the dark theme to a QApplication.

    Loads theme.qss and sets it as the application's stylesheet.
    Must be called once, before showing any windows.

    Args:
        app: QApplication instance.
    """
    stylesheet = load_theme()
    app.setStyleSheet(stylesheet)
