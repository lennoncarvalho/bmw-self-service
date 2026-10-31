"""Condition Based Service section of the vehicle page (B-CBS-R / B-CBS-W).

Displays decoded per-owner CBS records with raw bytes and explicit unavailable
states. All vehicle I/O belongs to CarWorkers started by the main window.
"""

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.regional import regional_locale


class CbsPanel(QWidget):
    """Collapsible service-due list with one confirmed reset action per item."""

    read_requested = Signal()
    reset_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._resets_allowed = False
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
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status_label)
        self.items_area = QScrollArea()
        self.items_area.setWidgetResizable(True)
        self.items_area.setMaximumHeight(260)
        self.container = QWidget()
        self.rows = QVBoxLayout(self.container)
        self.items_area.setWidget(self.container)
        layout.addWidget(self.items_area)
        self.clear("Service status not read in this session")
        self._toggle(False)

    def _toggle(self, visible: bool) -> None:
        self.items_area.setVisible(visible)
        self.status_label.setVisible(visible)
        self.toggle_button.setText(
            "Hide service status (CBS)" if visible else "Show service status (CBS)"
        )

    def set_busy(self, busy: bool, text: str = "") -> None:
        """Disable actions while a CBS read/reset or another mutation runs."""
        self.read_button.setEnabled(not busy)
        self.read_button.setText(
            "Reading service status…" if busy and text else "Read service status"
        )
        for button in self.container.findChildren(QPushButton):
            button.setEnabled(not busy and self._resets_allowed)

    def clear(self, text: str) -> None:
        """Discard displayed records (new session, disconnect or stale state)."""
        self._clear_rows()
        self.status_label.setText(text)
        self.rows.addStretch()

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
        if item.get("notes"):
            lines.append("; ".join(item["notes"]))
        if owner.get("reset") == "demo":
            lines.append("DEMO record — reset is not simulated")
        elif not item.get("resettable"):
            lines.append("Reset not available for this item/ECU in the recovered sources")
        return "\n".join(lines)

    def show_result(self, result: dict[str, Any], *, resets_allowed: bool, note: str = "") -> None:
        """Publish one settled read with per-owner coverage and per-item actions."""
        self._clear_rows()
        self._resets_allowed = resets_allowed
        owners = result.get("owners", [])
        coverage = (
            "\n".join(
                f"{o['name']} 0x{o['address']:02X}: {o['state']}"
                + (f" — {o['source']}" if o.get("source") else "")
                for o in owners
            )
            or "no ECU with a CBS reader was identified"
        )
        self.status_label.setText((note + "\n" if note else "") + f"Sources:\n{coverage}")
        for item in result.get("items", []):
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
                button.setEnabled(resets_allowed)
                button.clicked.connect(
                    lambda _=False, chosen=item: self.reset_requested.emit(chosen)
                )
                row.addWidget(button, 0, Qt.AlignmentFlag.AlignTop)
            self.rows.addWidget(frame)
        if not result.get("items"):
            empty = QLabel("No CBS records were returned")
            self.rows.addWidget(empty)
        self.rows.addStretch()
        self.toggle_button.setChecked(True)
