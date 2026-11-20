"""Dark theme loader for the BMW Self Service.

Loads QSS from assets/theme.qss and applies it to a QApplication.

Reference: AGENTS.md#implementation-rules (one QSS file).
"""

from pathlib import Path

from PySide6.QtCore import QDir, QEvent, QObject, Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QAbstractButton, QApplication

from app.resources import resource_path


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
    """Locate the shared theme through the same source/bundle owner as other assets."""
    path = resource_path("assets/theme.qss")
    if not path.is_file():
        raise FileNotFoundError(f"Cannot find theme.qss at {path}")
    return path


def load_theme() -> str:
    """Read theme.qss and return the stylesheet string.

    Returns:
        CSS-like Qt Style Sheet string.

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
