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
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.service_history import SERVICE_TYPES
from app.worker import CarWorker

logger = logging.getLogger(__name__)


class AddServiceDialog(QDialog):
    """Modal form for adding a new service entry."""

    SERVICE_ITEMS = SERVICE_TYPES

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the service-history page with separate displayed and pending entries."""
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
        self.date_edit.setMaximumDate(QDate.currentDate())
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
        items_label = QLabel("Services performed (select 1–13):")
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
        count = sum(cb.isChecked() for cb in self.checkboxes.values())
        ok_btn = self._button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn is not None:
            ok_btn.setEnabled(1 <= count <= 13)


class ServiceHistoryPage(QWidget):
    """Service history tab — timeline of past and upcoming maintenance."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the service-history page with separate displayed and pending entries."""
        super().__init__(parent)
        self._connection: Any = None
        self._entries: list[dict] = []
        self._pending_writes: list[dict] = []
        self._unavailable_reason = ""
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
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.entry_container = QWidget()
        self.entry_layout = QVBoxLayout(self.entry_container)
        self.entry_layout.setSpacing(8)
        self.entry_layout.addStretch()
        self.scroll_area.setWidget(self.entry_container)
        layout.addWidget(self.scroll_area, stretch=1)

        # Add button
        self.add_btn = QPushButton("+ Add New Service Entry")
        self.add_btn.setObjectName("successButton")
        self.add_btn.setStyleSheet(
            "QPushButton { background: #2ECC71; color: white; border-radius: 8px; "
            "padding: 10px 24px; font-size: 14px; font-weight: bold; }"
            "QPushButton:hover { background: #27AE60; }"
        )
        self.add_btn.clicked.connect(self._on_add_clicked)
        layout.addWidget(self.add_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # T-8: Erase History button
        self.erase_btn = QPushButton("Erase Service History")
        self.erase_btn.setObjectName("dangerButton")
        self.erase_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #E30B1F; "
            "border: 1px solid #E30B1F; border-radius: 8px; "
            "padding: 8px 20px; font-size: 12px; font-weight: bold; }"
            "QPushButton:hover { background: rgba(227,11,31,0.15); }"
        )
        self.erase_btn.clicked.connect(self._on_erase_clicked)
        self.erase_btn.setVisible(False)
        layout.addWidget(self.erase_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # Bottom bar (visible when pending writes exist)
        self._write_bar = QFrame()
        self._write_bar.setObjectName("bottomNav")
        self._write_bar.setFixedHeight(52)
        self._write_bar.setVisible(False)
        bar_layout = QHBoxLayout(self._write_bar)
        bar_layout.setContentsMargins(24, 8, 24, 8)

        clear_pending_btn = QPushButton("Clear")
        clear_pending_btn.setStyleSheet(
            "QPushButton { background: #3a3a5a; color: #a0a0a0; "
            "border-radius: 8px; padding: 8px 24px; font-weight: bold; }"
            "QPushButton:hover { background: #5a5a7a; color: white; }"
        )
        clear_pending_btn.clicked.connect(self._on_clear_pending)
        bar_layout.addWidget(clear_pending_btn)

        self._pending_label = QLabel("")
        self._pending_label.setStyleSheet("color: #F39C12; font-size: 13px; font-weight: bold;")
        bar_layout.addWidget(self._pending_label)
        bar_layout.addStretch()

        self._write_btn = QPushButton("Write to Car")
        self._write_btn.setStyleSheet(
            "QPushButton { background: #2ECC71; color: white; "
            "border-radius: 8px; padding: 8px 24px; font-weight: bold; }"
            "QPushButton:hover { background: #27AE60; }"
        )
        self._write_btn.clicked.connect(self._on_write_clicked)
        self._write_btn.setEnabled(False)
        self._write_btn.setToolTip("Vehicle history writes are not implemented yet")
        bar_layout.addWidget(self._write_btn)
        layout.addWidget(self._write_bar)

    def set_connection(self, connection: Any) -> None:
        """Set the active connection and load service history."""
        self._connection = connection
        self._load_history()

    def _load_history(self) -> None:
        """Load service entries from mock data or car."""
        entries: list[dict] = []

        if hasattr(self._connection, "data") and self._connection.data:
            self._unavailable_reason = ""
            self.add_btn.setEnabled(True)
            self._write_btn.setEnabled(False)
            entries = self._connection.data.get("service_history", [])
            self._entries = sorted(entries, key=lambda e: e.get("date", ""), reverse=True)
            self._render()
            return

        # No evidenced live read contract exists. In particular, the old
        # 31 01 A0 81 request may start an add routine; never send it as a read.
        self._unavailable_reason = "Vehicle history cannot be read. Local JSON editing, append and replacement are not implemented yet."
        self._entries = []
        self._pending_writes = []
        self.add_btn.setEnabled(False)
        self.erase_btn.setVisible(False)
        self._write_btn.setEnabled(False)
        self._write_bar.setVisible(False)
        logger.info("Vehicle history read retired; local history workflow is not implemented yet")
        self._render()

    def _on_history_loaded(self, entries: list[dict]) -> None:
        """Display service entries read from the car."""
        self.add_btn.setEnabled(True)
        self._entries = sorted(entries, key=lambda e: e.get("date", ""), reverse=True)
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
            if item is None:
                break
            child = item.widget()
            if child is not None:
                child.deleteLater()
            else:
                child_layout = item.layout()
                if child_layout is not None:
                    self._clear_layout(child_layout)

        if not self._entries:
            empty = QLabel(self._unavailable_reason or "No service records found.")
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
            card.setCursor(Qt.CursorShape.PointingHandCursor)
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
                summary = QLabel(
                    ", ".join(items[:3]) + (f" + {len(items) - 3} more" if len(items) > 3 else "")
                )
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
            full_label.setStyleSheet(
                "font-size: 12px; font-weight: bold; color: #a0a0a0; background: transparent;"
            )
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

        self._update_erase_visibility()

    def _on_add_clicked(self) -> None:
        dialog = AddServiceDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        data = dialog.get_data()
        if not data.get("items"):
            return

        if any(entry.get("date") == data["date"] for entry in self._entries):
            QMessageBox.information(
                self,
                "Date already recorded",
                "An entry already exists on this date. A second entry on the same day cannot be added.",
            )
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

        # Real car: add to pending writes (user must click "Write to Car")
        self._pending_writes.append(data)
        self._update_pending_label()

    def _on_history_erased(self, _result: object = None) -> None:
        """Re-load history after successful erase."""
        self.erase_btn.setEnabled(True)
        self._load_history()

    def _on_entry_written(self, _result: object = None) -> None:
        """Re-load history after a successful write."""
        self._write_btn.setEnabled(False)
        self.add_btn.setEnabled(True)
        self._pending_writes = []
        self._update_pending_label()
        self._load_history()

    def _update_pending_label(self) -> None:
        """Show/hide the bottom bar based on pending write count."""
        count = len(self._pending_writes)
        if count > 0:
            self._pending_label.setText(f"[{count} pending writes]")
            self._write_bar.setVisible(True)
        else:
            self._pending_label.setText("")
            self._write_bar.setVisible(False)

    def _on_write_clicked(self) -> None:
        """Keep the unfinished live write boundary unavailable."""
        # The forthcoming journal-backed append/replacement workers own sending.
        # Keep this boundary closed even if a stale callback exposes the button.
        logger.info("Vehicle history write unavailable: implementation pending")

    def _on_write_error(self, msg: str) -> None:
        """Handle write failure — re-enable buttons, preserve pending entries."""
        self.add_btn.setEnabled(True)
        self._write_btn.setEnabled(False)
        logger.warning("Service history write failed: %s", msg)
        QMessageBox.warning(
            self,
            "Write Failed",
            f"Could not write service entr{'ies' if len(self._pending_writes) > 1 else 'y'}: {msg}",
        )

    def _on_clear_pending(self) -> None:
        """Discard all pending writes without writing to the car."""
        if not self._pending_writes:
            return
        reply = QMessageBox.question(
            self,
            "Clear Pending",
            f"Discard {len(self._pending_writes)} pending service entr{'ies' if len(self._pending_writes) > 1 else 'y'}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._pending_writes = []
        self._update_pending_label()

    def _on_erase_clicked(self) -> None:
        """T-8: Confirm and erase entire service history."""
        reply = QMessageBox.question(
            self,
            "Erase Service History",
            "Delete ALL service records from the vehicle?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes or self._connection is None:
            return

        self.erase_btn.setEnabled(False)

        if hasattr(self._connection, "data") and self._connection.data:
            self._connection.data["service_history"] = []
            if hasattr(self._connection, "save"):
                self._connection.save()
            self._entries = []
            self._render()
            self.erase_btn.setEnabled(True)
            return

        self._worker = ServiceHistoryEraseWorker(self._connection)
        self._worker.result_ready.connect(self._on_history_erased)
        self._worker.error.connect(self._on_erase_error)
        self._worker.start()

    def _on_erase_error(self, msg: str) -> None:
        """Handle erase failure — re-enable button, preserve entries."""
        self.erase_btn.setEnabled(True)
        logger.warning("Service history erase failed: %s", msg)
        QMessageBox.warning(
            self,
            "Erase Failed",
            f"Could not erase service history: {msg}",
        )

    def _update_erase_visibility(self) -> None:
        """Show erase button only when there are entries."""
        self.erase_btn.setVisible(len(self._entries) > 0)

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
    """Reserved for a recovered, read-only headunit history contract."""

    def do_work(self) -> list[dict]:
        """Do not send the old unverified add routine as a read."""
        raise PermissionError("Vehicle service-history reading is not recovered")


class ServiceHistoryWriteWorker(CarWorker):
    """Reserved for journal-backed append or explicit replacement (workflow28)."""

    def __init__(self, connection: Any, entry_or_entries: dict | list[dict]) -> None:
        super().__init__(connection)
        self.entries = entry_or_entries

    def do_work(self) -> bool:
        """Reject the former guessed ASCII/DID encoder at the worker boundary."""
        raise PermissionError(
            "History writes require an implemented local journal and supported execution contract"
        )


class ServiceHistoryEraseWorker(CarWorker):
    """Standalone history erase is outside the append/replacement product scope."""

    def do_work(self) -> bool:
        """Never send the former unverified erase DID."""
        raise PermissionError("Vehicle history erase is unavailable")
