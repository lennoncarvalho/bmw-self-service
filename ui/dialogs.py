"""Shared Qt dialog surfaces, spacing and action roles for the cockpit theme."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.cockpit import caption, match_button_widths


def style_dialog_buttons(buttons: QDialogButtonBox, *, destructive: bool = False) -> None:
    """Distinguish dismissive actions from primary or destructive confirmations."""
    for button in buttons.buttons():
        role = buttons.buttonRole(button)
        if role in (
            QDialogButtonBox.ButtonRole.RejectRole,
            QDialogButtonBox.ButtonRole.NoRole,
        ):
            button.setProperty("class", "secondary")
        elif destructive and role in (
            QDialogButtonBox.ButtonRole.AcceptRole,
            QDialogButtonBox.ButtonRole.YesRole,
        ):
            button.setProperty("class", "dangerOutline")
        style = button.style()
        style.unpolish(button)
        style.polish(button)
        button.update()
    match_button_widths(buttons.buttons())


class CockpitDialog(QDialog):
    """A titled, scrollable dialog body with a persistent action footer."""

    def __init__(
        self,
        title: str,
        parent: QWidget | None = None,
        *,
        width: int = 680,
        height: int = 600,
    ) -> None:
        """Keep long forms within the screen while leaving actions outside the scroll area."""
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setObjectName("cockpitDialog")
        self.setMinimumWidth(480)
        self._shell = QVBoxLayout(self)
        self._shell.setContentsMargins(24, 24, 24, 20)
        self._shell.setSpacing(16)
        self._shell.addWidget(caption(title, "dialogTitle"))
        self.body_scroll = QScrollArea()
        self.body_scroll.setObjectName("dialogScroll")
        self.body_scroll.setWidgetResizable(True)
        self.body_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("dialogContent")
        self.body = QVBoxLayout(content)
        self.body.setContentsMargins(0, 0, 8, 0)
        self.body.setSpacing(16)
        self.body.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.body_scroll.setWidget(content)
        self._shell.addWidget(self.body_scroll, 1)
        self.resize(width, height)

    def add_notice(self, notice: QWidget) -> None:
        """Keep a wrapping validation or status notice outside the scrollable body."""
        self._shell.addWidget(notice)

    def add_buttons(self, buttons: QDialogButtonBox, *, destructive: bool = False) -> None:
        """Place standard Qt actions in the fixed footer without changing their signals."""
        style_dialog_buttons(buttons, destructive=destructive)
        self._shell.addWidget(buttons)

    def showEvent(self, event: QShowEvent) -> None:
        """Fit the dialog to the available screen, including shorter desktop displays."""
        screen = self.screen()
        if screen is not None:
            available = screen.availableGeometry().adjusted(24, 40, -24, -40)
            self.resize(
                min(self.width(), available.width()), min(self.height(), available.height())
            )
        super().showEvent(event)


class MessageBox:
    """Standard Qt message boxes with the same padding, typography and action hierarchy."""

    StandardButton = QMessageBox.StandardButton

    @staticmethod
    def _show(
        parent: QWidget | None,
        title: str,
        text: str,
        icon: QMessageBox.Icon,
        buttons: QMessageBox.StandardButton,
        default: QMessageBox.StandardButton,
        *,
        destructive: bool = False,
        action_text: str | None = None,
    ) -> QMessageBox.StandardButton:
        dialog = CockpitDialog(title, parent, width=640, height=440)
        dialog.setProperty("tone", "warning" if icon == QMessageBox.Icon.Warning else "default")
        message = caption(text)
        message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        dialog.body.addWidget(message)
        dialog.body.addStretch()
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton(buttons.value))
        dialog.add_buttons(button_box, destructive=destructive)
        default_button = button_box.button(QDialogButtonBox.StandardButton(default.value))
        if default_button is not None:
            default_button.setDefault(True)
            default_button.setFocus()
        for button in button_box.buttons():
            code = button_box.standardButton(button)
            button.clicked.connect(lambda checked=False, result=code: dialog.done(result.value))
        affirmative = button_box.button(QDialogButtonBox.StandardButton.Yes)
        if action_text is not None and affirmative is not None:
            affirmative.setText(action_text)
        negative = button_box.button(QDialogButtonBox.StandardButton.No)
        if destructive and negative is not None:
            negative.setText("Cancel")
        match_button_widths(button_box.buttons())
        # Match the normal escape action without turning window close into consent.
        escape = QMessageBox.StandardButton.NoButton
        if buttons & QMessageBox.StandardButton.Cancel:
            escape = QMessageBox.StandardButton.Cancel
        elif buttons & QMessageBox.StandardButton.No:
            escape = QMessageBox.StandardButton.No
        elif len(button_box.buttons()) == 1:
            escape = QMessageBox.StandardButton(buttons.value)
        dialog.ensurePolished()
        dialog.resize(640, max(230, min(620, message.heightForWidth(576) + 160)))
        result = dialog.exec()
        dialog.deleteLater()
        return QMessageBox.StandardButton(result) if result else escape

    @staticmethod
    def information(parent: QWidget | None, title: str, text: str) -> QMessageBox.StandardButton:
        """Show a themed informational result using Qt's normal modal lifecycle."""
        return MessageBox._show(
            parent,
            title,
            text,
            QMessageBox.Icon.Information,
            QMessageBox.StandardButton.Ok,
            QMessageBox.StandardButton.Ok,
        )

    @staticmethod
    def warning(
        parent: QWidget | None,
        title: str,
        text: str,
        buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
        default: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
    ) -> QMessageBox.StandardButton:
        """Show a themed warning while retaining the requested buttons and default."""
        return MessageBox._show(parent, title, text, QMessageBox.Icon.Warning, buttons, default)

    @staticmethod
    def question(
        parent: QWidget | None,
        title: str,
        text: str,
        buttons: QMessageBox.StandardButton = (
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ),
        default: QMessageBox.StandardButton = QMessageBox.StandardButton.No,
        *,
        destructive: bool = False,
        action_text: str | None = None,
    ) -> QMessageBox.StandardButton:
        """Keep explicit confirmation defaults and optionally label a destructive action."""
        return MessageBox._show(
            parent,
            title,
            text,
            QMessageBox.Icon.Question,
            buttons,
            default,
            destructive=destructive,
            action_text=action_text,
        )

    @staticmethod
    def about(parent: QWidget | None, title: str, text: str) -> None:
        """Show the application information through the shared message surface."""
        MessageBox.information(parent, title, text)
