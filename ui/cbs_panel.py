"""Condition Based Service section of the vehicle page (B-CBS-R / B-CBS-W).

Displays decoded per-owner CBS records with raw bytes and explicit unavailable
states. All vehicle I/O belongs to CarWorkers started by the main window.
"""

from copy import deepcopy
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.regional import regional_locale


class CbsPanel(QWidget):
    """Collapsible service-due list with one confirmed reset action per item."""

    read_requested = Signal()
    reset_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the service-status toggle and expanding record container."""
        super().__init__(parent)
        self._resets_allowed = False
        self._busy = False
        self._selection = 0
        self._has_result = False
        self._items: list[dict[str, Any]] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        self.toggle_button = QPushButton("Show service status (CBS)")
        self.toggle_button.setCheckable(True)
        self.toggle_button.toggled.connect(self._toggle)
        header.addWidget(self.toggle_button, 1)
        self.read_button = QPushButton("Read service status")
        self.read_button.clicked.connect(self.read_requested)
        header.addWidget(self.read_button)
        layout.addLayout(header)
        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        self.message_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.message_label)
        self.outcome_label = QLabel()
        self.outcome_label.setWordWrap(True)
        self.outcome_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.outcome_label)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status_label)
        self.container = QWidget()
        self.rows = QVBoxLayout(self.container)
        layout.addWidget(self.container)
        self.clear("Service status not read in this session")
        self._toggle(False)

    def _toggle(self, visible: bool) -> None:
        """Show the complete service list and its source status together."""
        self.container.setVisible(visible)
        self.status_label.setVisible(visible)
        self.toggle_button.setText(
            "Hide service status (CBS)" if visible else "Show service status (CBS)"
        )

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
        """Retain previous values as stale and keep the failure visible when collapsed."""
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
        self.rows.addStretch()
        self.set_busy(False)

    def _clear_rows(self) -> None:
        while self.rows.count():
            item = self.rows.takeAt(0)
            child = item.widget() if item is not None else None
            if child is not None:
                child.hide()
                child.deleteLater()

    @staticmethod
    def _describe(item: dict[str, Any]) -> str:
        locale = regional_locale()
        parts = [str(item["label"])]
        remaining, unit = item.get("remaining"), item.get("unit")
        if isinstance(remaining, int):
            amount = locale.toString(abs(remaining))
            parts.append(
                f"{amount} {unit} remaining" if remaining >= 0 else f"overdue by {amount} {unit}"
            )
        if item.get("due_month") and item.get("due_year"):
            day = f"{item['due_day']:02d}/" if item.get("due_day") else ""
            parts.append(f"due {day}{item['due_month']:02d}/{item['due_year']}")
        if item.get("availability") is not None:
            parts.append(f"availability {item['availability']} %")
        if item.get("count") is not None:
            parts.append(f"services done {item['count']}")
        for key, unit in (("forecast_km", "km"), ("forecast_months", "months")):
            if item.get(key) is not None:
                parts.append(f"forecast interval {locale.toString(item[key])} {unit}")
        if item.get("status") is not None:
            parts.append(f"status 0x{item['status']:X}")
        owner = item["owner"]
        version = (
            f", CBS {owner['version']}" if owner.get("version") not in (None, "unknown") else ""
        )
        lines = [
            " · ".join(parts),
            f"Owner: {owner['name']} (0x{owner['address']:02X}{version}) · "
            f"record {item.get('raw') or 'unavailable'}",
        ]
        if item.get("job_text") and item["job_text"] != item["label"]:
            lines.append(f"ECU job text: {item['job_text']}")
        if item.get("status_text"):
            lines.append(f"ECU status: {item['status_text']}")
        if item.get("notes"):
            lines.append("; ".join(item["notes"]))
        if owner.get("reset") == "demo":
            lines.append("DEMO record — reset is not simulated")
        elif not item.get("resettable"):
            lines.append("Reset not available for this item/ECU in the recovered sources")
        return "\n".join(lines)

    def show_result(self, result: dict[str, Any], *, resets_allowed: bool, note: str = "") -> None:
        """Publish one settled read with per-owner coverage and per-item actions."""
        owners = result.get("owners", [])
        coverage = (
            "\n".join(
                f"{o['name']} 0x{o['address']:02X}: {o['state']}"
                + (f" — software {o['software_state']}" if o.get("software_state") else "")
                + (f" — {o['source']}" if o.get("source") else "")
                for o in owners
            )
            or "no ECU with a CBS reader was identified"
        )
        self.status_label.setText((note + "\n" if note else "") + f"Sources:\n{coverage}")
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
                "Service status refresh failed for some sources. "
                "Any retained values are stale; their resets are disabled."
            )
        for item in items:
            frame = QFrame()
            frame.setObjectName("card")
            row = QHBoxLayout(frame)
            label = QLabel(self._describe(item))
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row.addWidget(label, 1)
            if item.get("resettable"):
                button = QPushButton("Reset…")
                button.setEnabled(resets_allowed and not self._busy)
                button.setToolTip(note if not resets_allowed else "Reset this service item")
                selection = self._selection
                button.clicked.connect(
                    lambda _=False, chosen=item, generation=selection: self._request_reset(
                        chosen, generation
                    )
                )
                row.addWidget(button, 0, Qt.AlignmentFlag.AlignTop)
            self.rows.addWidget(frame)
        if not items:
            empty = QLabel("No CBS records were returned")
            self.rows.addWidget(empty)
        self.rows.addStretch()
        self.toggle_button.setChecked(True)

    def _request_reset(self, item: dict[str, Any], selection: int) -> None:
        """Reject stale queued clicks after refresh, failure or another operation."""
        if selection != self._selection or self._busy or not self._resets_allowed:
            self.message_label.setText("Reset selection expired — read service status again.")
            return
        self.reset_requested.emit(item)
