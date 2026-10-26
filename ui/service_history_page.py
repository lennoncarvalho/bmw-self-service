"""Service History page — timeline of maintenance records.

Displays service entries sorted by date descending. Tap to expand
and see full work descriptions. Add new entries via QDialog form.

Reference: docs/16-ui-spec.md Screen 6
"""

import logging
from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.worker import CarWorker

logger = logging.getLogger(__name__)


class AddServiceDialog(QDialog):
    """Modal form for adding a new service entry."""

    SERVICE_ITEMS = [
        ("Engine oil change", 0x01),
        ("Oil filter", 0x04),
        ("Cabin filter / microfilter", 0x04),
        ("Engine air filter", 0x0B),
        ("Spark plugs", 0x0A),
        ("Front brake pads", 0x02),
        ("Rear brake pads", 0x06),
        ("Brake fluid", 0x03),
        ("Vehicle check (standard)", 0x64),
        ("Coolant", 0x12),
        ("Transmission fluid", 0x23),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Service Entry")
        self.setMinimumWidth(420)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        form.addRow("Date:", self.date_edit)

        self.mileage_spin = QSpinBox()
        self.mileage_spin.setRange(0, 999999)
        self.mileage_spin.setSuffix(" km")
        self.mileage_spin.setValue(66000)
        form.addRow("Mileage:", self.mileage_spin)

        self.dealer_edit = QLineEdit()
        self.dealer_edit.setPlaceholderText("e.g. BMW Munich")
        form.addRow("Dealer:", self.dealer_edit)

        layout.addLayout(form)

        # Service items checkboxes
        items_label = QLabel("Services performed:")
        items_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(items_label)

        self.checkboxes: dict[str, QCheckBox] = {}
        for label_text, _ in self.SERVICE_ITEMS:
            cb = QCheckBox(label_text)
            cb.toggled.connect(self._on_item_toggled)
            self.checkboxes[label_text] = cb
            layout.addWidget(cb)

        layout.addSpacing(8)

        # Buttons
        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self._button_box.accepted.connect(self.accept)
        self._button_box.rejected.connect(self.reject)
        layout.addWidget(self._button_box)

    def get_data(self) -> dict:
        """Collect form data as a service entry dict."""
        selected = [label for label, cb in self.checkboxes.items() if cb.isChecked()]
        return {
            "date": self.date_edit.date().toString("yyyy-MM-dd"),
            "mileage_km": self.mileage_spin.value(),
            "dealer": self.dealer_edit.text() or None,
            "items": selected,
        }

    def _on_item_toggled(self) -> None:
        """Enable OK only when at least one service item is checked."""
        any_checked = any(cb.isChecked() for cb in self.checkboxes.values())
        ok_btn = self._button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn is not None:
            ok_btn.setEnabled(any_checked)


class ServiceHistoryPage(QWidget):
    """Service history tab — timeline of past and upcoming maintenance."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._connection: Any = None
        self._entries: list[dict] = []
        self._worker: CarWorker | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        # Title
        title = QLabel("Service History")
        title.setObjectName("titleLabel")
        title.setStyleSheet("font-size: 19px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title)

        # Scrollable entry list
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )
        self.entry_container = QWidget()
        self.entry_layout = QVBoxLayout(self.entry_container)
        self.entry_layout.setSpacing(8)
        self.entry_layout.addStretch()
        self.scroll.setWidget(self.entry_container)
        layout.addWidget(self.scroll, stretch=1)

        # Add button
        self.add_btn = QPushButton("+ Add New Service Entry")
        self.add_btn.setObjectName("successButton")
        self.add_btn.setStyleSheet(
            "QPushButton { background: #2ECC71; color: white; border-radius: 8px; "
            "padding: 10px 24px; font-size: 14px; font-weight: bold; }"
            "QPushButton:hover { background: #27AE60; }"
        )
        self.add_btn.clicked.connect(self._on_add_clicked)
        layout.addWidget(self.add_btn, alignment=Qt.AlignCenter)

    def set_connection(self, connection: Any) -> None:
        """Set the active connection and load service history."""
        self._connection = connection
        self._load_history()

    def _load_history(self) -> None:
        """Load service entries from mock data or car."""
        entries: list[dict] = []

        if hasattr(self._connection, "data") and self._connection.data:
            entries = self._connection.data.get("service_history", [])
            self._entries = sorted(
                entries, key=lambda e: e.get("date", ""), reverse=True
            )
            self._render()
            return

        # G-6: Real car — read via UDS 0x31 RoutineControl RID 0xA081 from headunit
        self.add_btn.setEnabled(False)
        self._worker = ServiceHistoryReadWorker(self._connection)
        self._worker.progress.connect(lambda msg: logger.debug("Service: %s", msg))
        self._worker.finished.connect(self._on_history_loaded)
        self._worker.error.connect(self._on_history_error)
        self._worker.start()

    def _on_history_loaded(self, entries: list[dict]) -> None:
        """Display service entries read from the car."""
        self.add_btn.setEnabled(True)
        self._entries = sorted(
            entries, key=lambda e: e.get("date", ""), reverse=True
        )
        self._render()

    def _on_history_error(self, msg: str) -> None:
        """Handle service history read failure."""
        self.add_btn.setEnabled(True)
        logger.warning("Service history read failed: %s", msg)
        self._entries = []
        self._render()

    def _render(self) -> None:
        """Rebuild the entry cards."""

        # Clear existing
        while self.entry_layout.count() > 1:
            item = self.entry_layout.takeAt(0)
            child = item.widget()
            if child is not None:
                child.deleteLater()
            elif item.layout() is not None:
                self._clear_layout(item.layout())

        if not self._entries:
            empty = QLabel("No service records found.")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("font-size: 14px; color: #a0a0a0; padding: 32px;")
            self.entry_layout.insertWidget(self.entry_layout.count() - 1, empty)
            return

        for entry in self._entries:
            date_str = entry.get("date", "Unknown")
            km = entry.get("mileage_km")
            items = entry.get("items", [])
            dealer = entry.get("dealer")

            card = QFrame()
            card.setObjectName("card")
            card.setCursor(Qt.PointingHandCursor)
            card.setStyleSheet(
                "QFrame#card { background: #16213e; border: 1px solid #2a2a4a; "
                "border-radius: 8px; padding: 12px; }"
                "QFrame#card:hover { border-color: #2ECC71; }"
            )

            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(4)

            top_row = QHBoxLayout()
            date_label = QLabel(date_str)
            date_label.setStyleSheet(
                "font-size: 14px; font-weight: bold; color: #2ECC71; background: transparent;"
            )
            top_row.addWidget(date_label)
            if km is not None:
                km_label = QLabel(f"  {km:,} km")
                km_label.setStyleSheet("font-size: 13px; color: #a0a0a0; background: transparent;")
                top_row.addWidget(km_label)
            top_row.addStretch()

            # Toggle button for expand/collapse
            toggle_btn = QPushButton("\u25b6")
            toggle_btn.setFlat(True)
            toggle_btn.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            toggle_btn.setStyleSheet(
                "QPushButton { font-size: 12px; color: #a0a0a0; background: transparent; "
                "border: none; padding: 4px; }"
                "QPushButton:hover { color: #2ECC71; }"
                "QPushButton:focus { border: 1px solid #2ECC71; border-radius: 4px; }"
            )
            top_row.addWidget(toggle_btn)
            card_layout.addLayout(top_row)

            # Summary line
            if items:
                summary = QLabel(", ".join(items[:3]) + (
                    f" + {len(items) - 3} more" if len(items) > 3 else ""
                ))
                summary.setStyleSheet("font-size: 13px; color: #e0e0e0; background: transparent;")
                summary.setWordWrap(True)
                card_layout.addWidget(summary)

            # Detail section (hidden)
            detail = QWidget()
            detail.setVisible(False)
            detail_layout = QVBoxLayout(detail)
            detail_layout.setContentsMargins(0, 8, 0, 0)

            if dealer:
                dlr = QLabel(f"Dealer: {dealer}")
                dlr.setStyleSheet("font-size: 12px; color: #a0a0a0; background: transparent;")
                detail_layout.addWidget(dlr)

            full_label = QLabel("Work carried out:")
            full_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #a0a0a0; background: transparent;")
            detail_layout.addWidget(full_label)
            for item in items:
                bullet = QLabel(f"  \u2713 {item}")
                bullet.setStyleSheet("font-size: 12px; color: #e0e0e0; background: transparent;")
                detail_layout.addWidget(bullet)

            card_layout.addWidget(detail)

            # Toggle detail on button click
            toggle_btn.clicked.connect(
                lambda checked, d=detail, b=toggle_btn: (
                    d.setVisible(not d.isVisible()),
                    b.setText("▼" if d.isVisible() else "▶"),
                )
            )

            self.entry_layout.insertWidget(self.entry_layout.count() - 1, card)

    def _on_add_clicked(self) -> None:
        dialog = AddServiceDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        data = dialog.get_data()
        if not data.get("items"):
            return

        # Prepend and re-sort by date descending, then re-render
        self._entries.append(data)
        self._entries.sort(key=lambda e: e.get("date", ""), reverse=True)
        self._render()

        # Persist to mock data if in DEMO mode
        if hasattr(self._connection, "data") and self._connection.data:
            history = self._connection.data.setdefault("service_history", [])
            history.append(data)
            if hasattr(self._connection, "save"):
                self._connection.save()
            return

        # G-7: Real car — write via UDS 0x31 RoutineControl RID 0xA081 to headunit
        self.add_btn.setEnabled(False)
        self._worker = ServiceHistoryWriteWorker(self._connection, data)
        self._worker.finished.connect(self._on_entry_written)
        self._worker.error.connect(self._on_history_error)
        self._worker.start()

    def _on_entry_written(self, _result: object = None) -> None:
        """Re-load history after a successful write."""
        self.add_btn.setEnabled(True)
        self._load_history()

    @staticmethod
    def _clear_layout(layout: QLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                continue
            child = item.widget()
            if child is not None:
                child.deleteLater()
            else:
                child_layout = item.layout()
                if child_layout is not None:
                    ServiceHistoryPage._clear_layout(child_layout)


# ---- Workers ----

class ServiceHistoryReadWorker(CarWorker):
    """Read service history from headunit via UDS 0x31 RoutineControl RID 0xA081."""

    HEADUNIT_ADDR = 0x63
    RID_READ = 0xA081

    def do_work(self) -> list[dict]:
        resp = self.connection.send_uds(
            self.HEADUNIT_ADDR,
            bytes([0x31, 0x01, (self.RID_READ >> 8) & 0xFF, self.RID_READ & 0xFF]),
        )
        if resp[0] != 0x71:
            raise ConnectionError(f"Headunit rejected service history read: 0x{resp[0]:02X}")
        # Parse response: 0x71 + RID + record_count(2) + records...
        entries: list[dict] = []
        offset = 4
        try:
            while offset < len(resp):
                rec_len = resp[offset]
                offset += 1
                if offset + rec_len > len(resp):
                    break
                record = resp[offset:offset + rec_len]
                offset += rec_len
                # Minimal parse: extract ASCII date and items
                entry = _parse_service_record(record)
                if entry:
                    entries.append(entry)
        except (IndexError, ValueError) as e:
            logger.debug("Service record parse error: %s", e)
        return entries


class ServiceHistoryWriteWorker(CarWorker):
    """Write a service entry to headunit via UDS 0x31 RoutineControl RID 0xA081."""

    HEADUNIT_ADDR = 0x63
    RID_WRITE = 0xA081

    def __init__(self, connection: Any, entry: dict) -> None:
        super().__init__(connection)
        self.entry = entry

    def do_work(self) -> bool:
        date_str = self.entry.get("date", "")
        mileage = self.entry.get("mileage_km", 0)
        items_str = "|".join(self.entry.get("items", []))
        record_str = f"{date_str};{mileage};{items_str}"
        record_bytes = record_str.encode("ascii", errors="ignore")
        payload = (
            bytes([0x31, 0x01, (self.RID_WRITE >> 8) & 0xFF, self.RID_WRITE & 0xFF])
            + record_bytes
        )
        resp = self.connection.send_uds(self.HEADUNIT_ADDR, payload)
        if resp[0] != 0x71:
            raise ConnectionError(
                f"Headunit rejected service entry write: 0x{resp[0]:02X}"
            )
        return True


def _parse_service_record(data: bytes) -> dict | None:
    """Parse a binary service record into a dict. Best-effort ASCII extraction."""
    try:
        text = data.decode("ascii", errors="ignore").strip("\x00")
        parts = text.split(";")
        if len(parts) >= 2:
            return {
                "date": parts[0].strip(),
                "mileage_km": int(parts[1]) if parts[1].strip().isdigit() else 0,
                "items": parts[2].split("|") if len(parts) > 2 else [],
            }
    except (ValueError, IndexError):
        pass
    return None
