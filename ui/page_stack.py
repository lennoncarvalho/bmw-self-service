"""Page sizing for the application's single scrolling content viewport."""

from PySide6.QtCore import QEvent, QSize, Slot
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QLayout, QStackedWidget, QWidget


class PageStack(QStackedWidget):
    """Size only the visible page, including its full wrapped/expanded content.

    QStackedWidget normally reserves the largest minimum size of all its pages.
    Inside a scroll area that would leave another page's expanded content as
    empty scrolling space. Nested page stacks use this same sizing contract.
    """

    def __init__(self, parent: QWidget | None = None, *, content_height: bool = False) -> None:
        """Propagate active-page layout changes to the outer scroll area."""
        super().__init__(parent)
        self._content_height = content_height
        layout = self.layout()
        if layout is not None:
            layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.currentChanged.connect(self._page_changed)

    @Slot(int)
    def _page_changed(self, index: int) -> None:
        layout = self.layout()
        if layout is not None:
            layout.invalidate()
        self._refresh_height()
        self.updateGeometry()

    def _refresh_height(self) -> None:
        if self._content_height:
            # Parent layouts otherwise query the native stacked layout's
            # height-for-width, which includes inactive pages. This tracks the
            # current content, rather than imposing a fixed viewport cap.
            self.setFixedHeight(self.heightForWidth(self.width()))

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Recalculate a nested stack's content height after width changes."""
        super().resizeEvent(event)
        self._refresh_height()

    def hasHeightForWidth(self) -> bool:
        """Reflow the active page at the viewport's available width."""
        return True

    def heightForWidth(self, width: int) -> int:
        """Return all visible content's natural height without a viewport cap."""
        page = self.currentWidget()
        if page is None:
            return 0
        height = (
            page.heightForWidth(width) if page.hasHeightForWidth() else page.sizeHint().height()
        )
        return max(page.minimumSizeHint().height(), height)

    def sizeHint(self) -> QSize:
        """Ignore inactive pages when suggesting the stack's size."""
        page = self.currentWidget()
        return page.sizeHint() if page is not None else QSize(0, 0)

    def minimumSizeHint(self) -> QSize:
        """Keep all current-page rows visible at the stack's actual width."""
        page = self.currentWidget()
        if page is None:
            return QSize(0, 0)
        return QSize(page.minimumSizeHint().width(), self.heightForWidth(self.width()))

    def event(self, event: QEvent) -> bool:
        """Refresh outer geometry when cards, rows or wrapped text change."""
        handled = super().event(event)
        if event.type() == QEvent.Type.LayoutRequest:
            self._refresh_height()
            self.updateGeometry()
        return handled
