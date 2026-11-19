"""Shared Qt form inputs; behavior stays native to Qt and visuals live in theme.qss."""

from collections.abc import Iterable
from typing import Any

from PySide6.QtCore import QDate, QLocale, QPoint, QSize, Qt
from PySide6.QtGui import QTextCharFormat
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCalendarWidget,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QListView,
    QSizePolicy,
    QStyledItemDelegate,
    QWidget,
)

from ui.regional import regional_locale


class CheckInput(QCheckBox):
    """A standard checkbox with a wrapping label and a fully clickable option row."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        """Keep lengthy acknowledgements readable without widening their dialog."""
        super().__init__(parent)
        self.setAccessibleName(text)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(32, 0, 0, 0)
        self._label = QLabel(text)
        self._label.setTextFormat(Qt.TextFormat.PlainText)
        self._label.setWordWrap(True)
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._label.setProperty("role", "caption")
        self._row.addWidget(self._label)

    def sizeHint(self) -> QSize:
        """Account for the wrapped label rather than Qt's empty native text."""
        return self._row.sizeHint().expandedTo(super().sizeHint())

    def minimumSizeHint(self) -> QSize:
        """Allow the label to wrap down to its longest word."""
        return self._row.minimumSize().expandedTo(super().minimumSizeHint())

    def hitButton(self, position: QPoint) -> bool:
        """Use normal checkbox interaction anywhere on the labelled row."""
        return self.rect().contains(position)


class SelectInput(QComboBox):
    """Standard Qt selection with one themed, scrollable list popup."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        options: Iterable[tuple[str, Any]] = (),
        max_visible_items: int = 10,
        compact: bool = False,
    ) -> None:
        """Configure reusable options, visible-row limit and optional table density."""
        if max_visible_items < 1:
            raise ValueError("A select input must show at least one option")
        super().__init__(parent)
        self.setProperty("formInput", True)
        self.setProperty("compact", compact)
        view = QListView(self)
        view.setObjectName("formSelectPopup")
        view.viewport().setObjectName("formSelectViewport")
        view.setUniformItemSizes(True)
        view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerItem)
        self.setView(view)
        self.setItemDelegate(QStyledItemDelegate(view))
        self.setMaxVisibleItems(max_visible_items)
        for label, value in options:
            self.addItem(label, value)


class DateInput(QDateEdit):
    """Standard Qt date editor with a shared calendar, bounds and regional format."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        value: QDate | None = None,
        minimum: QDate | None = None,
        maximum: QDate | None = None,
        locale: QLocale | None = None,
        display_format: str | None = None,
    ) -> None:
        """Configure date bounds and formatting without rebuilding a calendar per form."""
        super().__init__(parent)
        self.setProperty("formInput", True)
        region = locale if locale is not None else regional_locale()
        self.setLocale(region)
        self.setDisplayFormat(display_format or region.dateFormat(QLocale.FormatType.ShortFormat))
        self.setCalendarPopup(True)
        self.setKeyboardTracking(False)
        calendar = QCalendarWidget(self)
        calendar.setObjectName("formCalendar")
        calendar.setLocale(QLocale(QLocale.Language.English))
        calendar.setFirstDayOfWeek(region.firstDayOfWeek())
        calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        calendar.setGridVisible(False)
        calendar.setMinimumSize(336, 300)
        for day in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday):
            calendar.setWeekdayTextFormat(day, QTextCharFormat())
        self.setCalendarWidget(calendar)
        if minimum is not None:
            self.setMinimumDate(minimum)
        if maximum is not None:
            self.setMaximumDate(maximum)
        self.setDate(value if value is not None else QDate.currentDate())
