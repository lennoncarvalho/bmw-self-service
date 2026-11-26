"""Reusable presentation components for the desktop cockpit."""

from collections.abc import Iterable

from PySide6.QtCore import QEvent, Qt, Signal, Slot
from PySide6.QtGui import QIcon, QPainter, QPixmap, QResizeEvent, QShowEvent
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# Small line symbols share one stroke and viewport throughout the shell.
_PATHS = {
    "overview": '<path d="M4 17a9 9 0 1 1 16 0M12 13l5-6M4 18h16"/><circle cx="12" cy="13" r="2"/>',
    "faults": '<path d="M6 3v6a6 6 0 0 0 12 0V3M3 3h6M15 3h6M12 15v3a3 3 0 0 0 6 0v-2"/><circle cx="18" cy="13" r="2"/>',
    "service": '<circle cx="12" cy="12" r="9"/><path d="m8 7 2 5 5 3M16 5l-3 5"/>',
    "coding": '<path d="M4 6h16M4 12h16M4 18h16M8 3v6M16 9v6M10 15v6"/>',
    "history": '<path d="M6 4h12v16H6zM9 8h6M9 12h6M9 16h4"/>',
    "backups": '<path d="M5 3h12l3 3v15H4V3zM8 3v6h8V3M8 21v-8h8v8"/>',
    "settings": '<path d="M10 2h4l.5 3 2 .9 2.5-1.5 2 3.4-2.1 2v2.4l2.1 2-2 3.4-2.5-1.5-2 .9-.5 3h-4l-.5-3-2-.9-2.5 1.5-2-3.4 2.1-2V9.8l-2.1-2 2-3.4L7.5 5.9l2-.9z"/><circle cx="12" cy="11" r="3"/>',
    "github": '<path d="M8 20v-3c-5 1-4-3-6-3M16 20v-4c0-1-1-2-1-2 4-1 5-3 5-6 0-2-1-3-1-3V2l-4 2a12 12 0 0 0-6 0L5 2v3S4 6 4 8c0 3 1 5 5 6"/>',
    "coffee": '<path d="M4 7h13v8a5 5 0 0 1-10 0V7M17 8h2a3 3 0 0 1 0 6h-2M3 22h17M8 2v2M13 2v2"/>',
}


def cockpit_icon(name: str) -> QIcon:
    """Render a consistent local line icon without network dependencies."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        'viewBox="0 0 24 24"><g fill="none" stroke="#c2c6d5" stroke-width="1.7" '
        'stroke-linecap="round" stroke-linejoin="round">' + _PATHS[name] + "</g></svg>"
    )
    pixmap = QPixmap(48, 48)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(svg.encode()).render(painter)
    painter.end()
    return QIcon(pixmap)


def caption(text: str, role: str = "caption") -> QLabel:
    """Create a wrapped plain-text label with a reusable style role."""
    label = QLabel(text)
    label.setProperty("role", role)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


def set_lamp_state(label: QLabel, on: object) -> str:
    """Apply shared MIL colors and return the matching state label."""
    state = "on" if on is True else "off" if on is False else "unknown"
    label.setObjectName("milStatus")
    label.setProperty("milState", state)
    label.style().unpolish(label)
    label.style().polish(label)
    return {"on": "On", "off": "Off", "unknown": "Unavailable"}[state]


def match_button_widths(buttons: Iterable[QAbstractButton]) -> None:
    """Give sibling command buttons the width required by their longest label."""
    group = list(buttons)
    for button in group:
        button.ensurePolished()
    width = max((button.sizeHint().width() for button in group), default=0)
    for button in group:
        button.setFixedWidth(width)


class DangerButton(QPushButton):
    """Shared red action button for vehicle mutations and destructive actions."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        """Apply the common danger role without changing standard Qt button behavior."""
        super().__init__(text, parent)
        self.setProperty("class", "dangerOutline")


class ElidedLabel(QLabel):
    """Single-line context that yields space while retaining its full accessible text."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        """Keep long context out of neighbouring titles and action groups."""
        super().__init__(parent)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setProperty("role", "caption")
        self.setText(text)

    def setText(self, text: str) -> None:
        """Retain full context for accessibility, search and the tooltip."""
        self._full_text = text
        self.setAccessibleName(text)
        self.setToolTip(text)
        self._refresh()

    def text(self) -> str:
        """Return the full value even when the visible presentation is shortened."""
        return self._full_text

    def _refresh(self) -> None:
        super().setText(
            self.fontMetrics().elidedText(
                self._full_text, Qt.TextElideMode.ElideRight, self.contentsRect().width()
            )
        )

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Recalculate the visible context at the new available width."""
        super().resizeEvent(event)
        self._refresh()

    def changeEvent(self, event: QEvent) -> None:
        """Refresh after font or theme changes without losing the full value."""
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange) and hasattr(
            self, "_full_text"
        ):
            self._refresh()


class CockpitCard(QFrame):
    """Shared graphite surface with consistent padding and label hierarchy."""

    def __init__(
        self, title: str, parent: QWidget | None = None, *, context: str | None = None
    ) -> None:
        """Build a titled, vertically laid out cockpit surface."""
        super().__init__(parent)
        self.setProperty("class", "cockpitCard")
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(18, 16, 18, 16)
        self.box.setSpacing(10)
        if context is not None:
            self.box.addWidget(caption(context))
        self.box.addWidget(caption(title, "cardTitle"))


class ReviewItem(QFrame):
    """Separate a selected setting and its target value from review guidance."""

    def __init__(self, title: str, value: str, parent: QWidget | None = None) -> None:
        """Build a compact, wrapping review row with a highlighted target value."""
        super().__init__(parent)
        self.setProperty("class", "reviewItem")
        box = QVBoxLayout(self)
        box.setContentsMargins(12, 8, 12, 8)
        box.setSpacing(4)
        box.addWidget(caption(title, "identity"))
        box.addWidget(caption(f"Selected: {value}", "selectedValue"))


class PageHeader(QFrame):
    """Shared page title, context and action surface."""

    def __init__(self, title: str, description: str, parent: QWidget | None = None) -> None:
        """Lay out a wrapping title and a compact trailing action group."""
        super().__init__(parent)
        self.setProperty("class", "pageHeader")
        box = QVBoxLayout(self)
        box.setContentsMargins(18, 16, 18, 16)
        box.setSpacing(8)
        row = QHBoxLayout()
        row.addWidget(caption(title, "pageTitle"), 1)
        self.action_layout = QHBoxLayout()
        self.action_layout.setSpacing(8)
        row.addLayout(self.action_layout)
        box.addLayout(row)
        box.addWidget(caption(description))

    def showEvent(self, event: QShowEvent) -> None:
        """Match action widths once their labels and shared theme are available."""
        match_button_widths(
            button
            for index in range(self.action_layout.count())
            if (item := self.action_layout.itemAt(index)) is not None
            and isinstance(button := item.widget(), QPushButton)
        )
        super().showEvent(event)


class ResponsiveColumns(QWidget):
    """Two content columns that stack within the page's one outer viewport."""

    def __init__(
        self,
        left: QWidget,
        right: QWidget,
        *,
        ratio: tuple[int, int] = (2, 1),
        breakpoint: int = 1150,
    ) -> None:
        """Keep both columns top aligned and stack when the viewport is narrow."""
        super().__init__()
        self.setProperty("class", "transparent")
        self._left, self._right = left, right
        self._ratio = ratio
        self._breakpoint = breakpoint
        self._wide: bool | None = None
        self.box = QGridLayout(self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(16)
        self._reflow()

    def _reflow(self) -> None:
        wide = self.width() >= self._breakpoint
        if wide == self._wide:
            return
        self._wide = wide
        self.box.addWidget(self._left, 0, 0, Qt.AlignmentFlag.AlignTop)
        self.box.addWidget(
            self._right, 0 if wide else 1, 1 if wide else 0, Qt.AlignmentFlag.AlignTop
        )
        self.box.setColumnStretch(0, self._ratio[0] if wide else 1)
        self.box.setColumnStretch(1, self._ratio[1] if wide else 0)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Reflow content after a viewport width change."""
        super().resizeEvent(event)
        self._reflow()


class CardGrid(QWidget):
    """Responsive cards with stable source order and an optional wide lead card."""

    def __init__(self) -> None:
        """Build a transparent grid for independently owned service cards."""
        super().__init__()
        self.setProperty("class", "transparent")
        self.box = QGridLayout(self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(16)
        self._cards: list[QWidget] = []
        self._columns = 0

    def add_card(self, card: QWidget) -> None:
        """Append a source-ordered card without changing its operation signals."""
        self._cards.append(card)
        self._reflow(force=True)

    def clear(self) -> None:
        """Retire the previous settled batch of card widgets."""
        self._cards.clear()
        while self.box.count():
            item = self.box.takeAt(0)
            child = item.widget() if item is not None else None
            if child is not None:
                child.hide()
                child.deleteLater()

    def _reflow(self, *, force: bool = False) -> None:
        columns = 3 if self.width() >= 1400 else 2 if self.width() >= 820 else 1
        if columns == self._columns and not force:
            return
        self._columns = columns
        for index, card in enumerate(self._cards):
            self.box.addWidget(card, index // columns, index % columns)
        for column in range(3):
            self.box.setColumnStretch(column, 1 if column < columns else 0)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Adjust the number of service columns at the current viewport width."""
        super().resizeEvent(event)
        self._reflow()


class CardSearch(QLineEdit):
    """Local search over already rendered cards, with no vehicle requests."""

    matches_changed = Signal(int)

    def __init__(self, target: QWidget, placeholder: str) -> None:
        """Filter tagged cards using their visible text and optional search terms."""
        super().__init__()
        self._target = target
        self.setPlaceholderText(placeholder)
        self.setAccessibleName(placeholder)
        self.setClearButtonEnabled(True)
        self.textChanged.connect(self.apply)

    @Slot()
    def apply(self) -> None:
        """Apply the current query after edits or a settled page render."""
        query = self.text().strip().casefold()
        matches = 0
        for card in self._target.findChildren(QFrame, "recordCard"):
            parent = card.parentWidget()
            owner = parent.layout() if parent is not None else None
            if owner is None or owner.indexOf(card) < 0:
                continue
            text = str(card.property("searchText") or "")
            text += " ".join(label.text() for label in card.findChildren(QLabel))
            matched = not query or query in text.casefold()
            card.setVisible(matched)
            matches += matched
        self.matches_changed.emit(matches)


class StatusLabel(QLabel):
    """A plain-text status message that occupies space only when populated."""

    def __init__(self) -> None:
        """Keep empty operation notices out of the page layout."""
        super().__init__()
        self.setWordWrap(True)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setProperty("role", "notice")
        self.hide()

    def setText(self, text: str) -> None:
        """Display the complete current notice, including wrapped failure details."""
        super().setText(text)
        self.setVisible(bool(text))

    def clear(self) -> None:
        """Remove the notice and release its layout space."""
        self.setText("")
