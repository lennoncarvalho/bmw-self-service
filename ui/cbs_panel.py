"""Condition Based Service section of the vehicle page (B-CBS-R / B-CBS-W).

Displays service intervals and explicit unavailable states without technical
provenance. All vehicle I/O belongs to CarWorkers started by the main window.
"""

from copy import deepcopy
from typing import Any

from PySide6.QtCore import QDate, QLocale, Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.cockpit import CardGrid, CockpitCard, DangerButton, PageHeader, StatusLabel, caption
from ui.regional import regional_locale


class CbsPanel(QWidget):
    """Manually read service-due list with one confirmed reset action per item."""

    read_requested = Signal()
    reset_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the read action and initially empty service record container."""
        super().__init__(parent)
        self.setObjectName("cbsPage")
        self._resets_allowed = False
        self._busy = False
        self._selection = 0
        self._has_result = False
        self._items: list[dict[str, Any]] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(14)
        header = PageHeader(
            "Service & maintenance",
            "Read supported service intervals and review each item before resetting.",
        )
        self.read_button = QPushButton("Read service status")
        self.read_button.clicked.connect(self.read_requested)
        header.action_layout.addWidget(self.read_button)
        layout.addWidget(header)
        self.message_label = StatusLabel()
        self.message_label.setWordWrap(True)
        self.message_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.message_label)
        self.outcome_label = StatusLabel()
        self.outcome_label.setWordWrap(True)
        self.outcome_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.outcome_label)
        self.status_label = StatusLabel()
        layout.addWidget(self.status_label)
        self.container = QWidget()
        body = QVBoxLayout(self.container)
        body.setContentsMargins(0, 0, 0, 0)
        self.service_grid = CardGrid()
        self.service_grid.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.rows = self.service_grid.box
        body.addWidget(self.service_grid)
        layout.addWidget(self.container)
        self.clear("Service status not read in this session")

    def set_busy(self, busy: bool, text: str = "") -> None:
        """Disable actions while a CBS read/reset or another mutation runs."""
        self._busy = busy
        self.read_button.setEnabled(not busy)
        self.read_button.setText(
            "Reading service status…" if busy and text else "Read service status"
        )
        for button in self.container.findChildren(QPushButton):
            button.setEnabled(not busy and self._resets_allowed)

    def invalidate_resets(self, text: str = "") -> None:
        """Keep the settled display but revoke every previous reset selection."""
        self._selection += 1
        self._resets_allowed = False
        for button in self.container.findChildren(QPushButton):
            button.setEnabled(False)
        if text:
            self.message_label.setText(text)

    def show_error(self, text: str) -> None:
        """Retain previous values as stale and keep the failure visible."""
        self.invalidate_resets(text + "\nPrevious values may be stale; read service status again.")

    def show_outcome(self, report: dict[str, Any]) -> None:
        """Retain completion separately from the subsequent refresh and its errors."""
        detail = f"Reset {report['state']}: {report['detail']}\n{report['instructions']}"
        if report.get("persistence_failed"):
            detail += "\nThe local operation record could not be saved; see the session log."
        elif report.get("path"):
            detail += f"\nRecord: {report['path']}"
        self.invalidate_resets()
        self.outcome_label.setText(detail)

    def clear(self, text: str) -> None:
        """Discard displayed records (new session, disconnect or stale state)."""
        self._clear_rows()
        self._has_result = False
        self._items.clear()
        self.invalidate_resets()
        self.message_label.clear()
        self.outcome_label.clear()
        self.status_label.setText(text)
        self.container.hide()
        self.set_busy(False)

    def _clear_rows(self) -> None:
        self.service_grid.clear()

    @staticmethod
    def _due_summary(item: dict[str, Any]) -> str:
        """Show only reported remaining units and valid dates, without inventing precision."""
        locale = regional_locale()
        parts = []
        remaining, unit = item.get("remaining"), item.get("unit")
        if isinstance(remaining, int) and unit in ("km", "days", "%"):
            amount = locale.toString(abs(remaining))
            parts.append(
                f"{amount} {unit} remaining" if remaining >= 0 else f"overdue by {amount} {unit}"
            )
        if item.get("due_month") and item.get("due_year"):
            date = QDate(item["due_year"], item["due_month"], item.get("due_day") or 1)
            if date.isValid():
                formatted = (
                    locale.toString(date, QLocale.FormatType.ShortFormat)
                    if item.get("due_day")
                    else locale.toString(date, "MM/yyyy")
                )
                parts.append(f"Due {formatted}")
        return " · ".join(parts) or "Due information unavailable"

    @staticmethod
    def _details(item: dict[str, Any]) -> str:
        """Keep reset counts and forecast intervals separate from current due values."""
        locale = regional_locale()
        lines = []
        if item.get("count") is not None:
            lines.append(f"Reset count: {locale.toString(item['count'])}")
        forecast = []
        for key, unit in (("forecast_km", "km"), ("forecast_months", "months")):
            if isinstance(item.get(key), int) and item[key] > 0:
                forecast.append(f"{locale.toString(item[key])} {unit}")
        if forecast:
            lines.append("Forecast interval: " + " / ".join(forecast))
        return "\n".join(lines)

    @staticmethod
    def _warnings(item: dict[str, Any]) -> str:
        """Retain actionable quality/reset warnings while keeping raw job text out of cards."""
        lines = []
        status_text = str(item.get("status_text") or "").lower()
        if item.get("status") not in (None, 0) and not status_text.startswith("status ok"):
            lines.append("The vehicle reported a warning for this service measurement.")
        translations = (
            ("Stale value:", "Previous value — refresh failed. Read service status again."),
            ("Software identity unavailable", "Read service status again before resetting."),
            ("This ECU returned repeated records", "Conflicting service records were returned."),
            ("Not every CBS owner could be read", "Some services could not be read."),
            ("Invalid target calendar date", "The reported due date is invalid."),
        )
        informational = (
            "Remaining:",
            "Remaining value",
            "Remaining distance",
            "Service count not available",
            "Availability",
        )
        for note in item.get("notes", []):
            for prefix, message in translations:
                if note.startswith(prefix):
                    lines.append(message)
                    break
            else:
                if item.get("resettable") and not note.startswith(informational):
                    lines.append("Some service data could not be verified.")
        if not item.get("resettable"):
            lines.append("Reset unavailable for this service.")
        return "\n".join(dict.fromkeys(lines))

    def show_result(self, result: dict[str, Any], *, resets_allowed: bool, note: str = "") -> None:
        """Publish due values and per-item actions, retaining technical provenance in data."""
        owners = result.get("owners", [])
        self.status_label.setText(note)
        failed = {
            (owner["name"], owner["address"])
            for owner in owners
            if owner["state"] not in ("read", "not-held", "DEMO")
        }
        items = deepcopy(
            [
                item
                for item in result.get("items", [])
                if (item["owner"]["name"], item["owner"]["address"]) not in failed
            ]
        )
        stale_note = "Stale value: this ECU could not be refreshed; reset disabled"
        for previous in self._items:
            owner = previous["owner"]
            if (owner["name"], owner["address"]) in failed:
                retained = deepcopy(previous)
                retained["resettable"] = False
                notes = retained.setdefault("notes", [])
                if stale_note not in notes:
                    notes.append(stale_note)
                items.append(retained)
        self._clear_rows()
        self._items = items
        self._has_result = bool(items)
        self._selection += 1
        self._resets_allowed = resets_allowed
        self.message_label.clear()
        if failed:
            self.message_label.setText(
                "Some service information could not be refreshed. "
                "Any retained values are stale; their resets are disabled."
            )
        for item in items:
            frame = CockpitCard(str(item["label"]), context=self._due_summary(item))
            row = frame.box
            availability = item.get("availability")
            if isinstance(availability, (int, float)) and 0 <= availability <= 100:
                row.addWidget(caption(f"Service availability · {availability}%", "supporting"))
                progress = QProgressBar()
                progress.setRange(0, 100)
                progress.setValue(int(availability))
                progress.setTextVisible(False)
                progress.setFixedHeight(6)
                progress.setAccessibleName(f"Service availability {availability}%")
                row.addWidget(progress)
            details = self._details(item)
            if details:
                label = caption(details, "supporting")
                label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                row.addWidget(label)
            warnings = self._warnings(item)
            if warnings:
                row.addWidget(caption(warnings, "notice"))
            row.addStretch()
            if item.get("resettable"):
                button = DangerButton("Reset…")
                button.setEnabled(resets_allowed and not self._busy)
                button.setToolTip(note if not resets_allowed else "Reset this service item")
                selection = self._selection
                button.clicked.connect(
                    lambda _=False, chosen=item, generation=selection: self._request_reset(
                        chosen, generation
                    )
                )
                row.addWidget(button, 0, Qt.AlignmentFlag.AlignTop)
            self.service_grid.add_card(frame)
        if not items:
            empty = QLabel("No CBS records were returned")
            self.service_grid.add_card(empty)
        self.container.show()

    def _request_reset(self, item: dict[str, Any], selection: int) -> None:
        """Reject stale queued clicks after refresh, failure or another operation."""
        if selection != self._selection or self._busy or not self._resets_allowed:
            self.message_label.setText("Reset selection expired — read service status again.")
            return
        self.reset_requested.emit(item)
