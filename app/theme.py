"""Dark theme loader for the BMW Self Service.

Loads QSS from assets/theme.qss and applies it to a QApplication.
Also provides color constants for use in Python code when QSS is insufficient.

Reference: AGENTS.md#implementation-rules (one QSS file).
"""

import os
from pathlib import Path

from PySide6.QtCore import QDir, QEvent, QObject, Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QAbstractButton, QApplication

# BMW M colour palette — use these for programmatic styling only
# (e.g. status dots, dynamic colour changes). Prefer QSS for static styles.
COLOR_BG_DARK = "#0a0e17"
COLOR_SURFACE = "#0f131c"
COLOR_BORDER = "#424753"
COLOR_PRIMARY = "#1c69d2"
COLOR_PRIMARY_HOVER = "#005bc0"
COLOR_PRIMARY_PRESSED = "#004493"
COLOR_DANGER = "#93000a"
COLOR_DANGER_HOVER = "#690005"
COLOR_SUCCESS = "#10b981"
COLOR_SUCCESS_HOVER = "#10b981"
COLOR_WARNING = "#f59e0b"
COLOR_TEXT_PRIMARY = "#dfe2ef"
COLOR_TEXT_SECONDARY = "#c2c6d5"
COLOR_TEXT_DISABLED = "#8c909e"
COLOR_BG_TOP_BAR = "#181c25"


def _set_button_cursor(button: QAbstractButton) -> None:
    shape = Qt.CursorShape.PointingHandCursor if button.isEnabled() else Qt.CursorShape.ArrowCursor
    button.setCursor(shape)


class _ButtonCursorFilter(QObject):
    """Apply the shared cursor policy to existing and dynamically created buttons."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Refresh button cursors on display and enabled-state changes without consuming events."""
        if isinstance(watched, QAbstractButton) and event.type() in (
            QEvent.Type.Polish,
            QEvent.Type.Show,
            QEvent.Type.EnabledChange,
        ):
            _set_button_cursor(watched)
        return super().eventFilter(watched, event)


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
    if not app.property("cockpitFontsLoaded"):
        QDir.addSearchPath("cockpit", str(_find_theme_qss().parent))
        for font in sorted((_find_theme_qss().parent / "fonts").glob("*.ttf")):
            QFontDatabase.addApplicationFont(str(font))
        app.setProperty("cockpitFontsLoaded", True)
    app.setFont(QFont("Geist", 11))
    stylesheet = load_theme()
    app.setStyleSheet(stylesheet)
    if app.findChild(_ButtonCursorFilter, "cockpitButtonCursors") is None:
        cursor_filter = _ButtonCursorFilter(app)
        cursor_filter.setObjectName("cockpitButtonCursors")
        app.installEventFilter(cursor_filter)
    for widget in app.allWidgets():
        if isinstance(widget, QAbstractButton):
            _set_button_cursor(widget)
