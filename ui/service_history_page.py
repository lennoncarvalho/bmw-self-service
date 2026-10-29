"""Local JSON service records; vehicle execution is a separate workflow28 task."""

import copy
import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QDate, QLocale, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.service_history import SERVICE_TYPES
from app.worker import CarWorker

logger = logging.getLogger(__name__)


def _regional_locale() -> QLocale:
    locale = QLocale.system()
    return QLocale("pt_BR") if locale.language() == QLocale.Language.C else locale


def _label(text: str) -> QLabel:
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


class AddServiceDialog(QDialog):
    """Edit a local record without losing unknown imported fields or items."""

    SERVICE_ITEMS = SERVICE_TYPES

    def __init__(self, parent: QWidget | None = None, entry: dict | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Local service entry")
        self.setMinimumWidth(440)
        self.original = copy.deepcopy(entry or {})
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat(
            _regional_locale().dateFormat(QLocale.FormatType.ShortFormat)
        )
        self.date_edit.setDateRange(
            QDate(1, 1, 1),
            max(QDate.currentDate(), QDate.fromString(self.original.get("date", ""), "yyyy-MM-dd")),
        )
        self.date_edit.setDate(
            QDate.fromString(self.original.get("date", ""), "yyyy-MM-dd")
            if entry
            else QDate.currentDate()
        )
        form.addRow("Date", self.date_edit)
        self.mileage_edit = QLineEdit(str(self.original.get("mileage_km", 0)))
        form.addRow("Mileage (km)", self.mileage_edit)
        self.dealer_edit = QLineEdit(self.original.get("dealer", "OWNER"))
        form.addRow("Garage (1–7 ASCII bytes)", self.dealer_edit)
        self.dealer_flag = QComboBox()
        for text, value in (("Independent / owner", 0), ("BMW garage", 1)):
            self.dealer_flag.addItem(text, value)
        original_flag = self.original.get("dealer_flag", 0)
        if original_flag not in (0, 1):
            self.dealer_flag.addItem(f"Unknown flag {original_flag}", original_flag)
        self.dealer_flag.setCurrentIndex(self.dealer_flag.findData(original_flag))
        form.addRow("Garage flag", self.dealer_flag)
        self.status = QLineEdit(str(self.original.get("status", 1)))
        self.correction = QLineEdit(str(self.original.get("correction", 0)))
        form.addRow("Record status (1–3 to send)", self.status)
        form.addRow("Correction (0–255)", self.correction)
        layout.addLayout(form)
        layout.addWidget(
            _label(
                "Select 1–13 items for sending. Raw status/distance/time values and unknown fields are preserved until you explicitly edit or remove them."
            )
        )
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(200)
        body = QWidget()
        items_layout = QVBoxLayout(body)
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)
        self.checkboxes: dict[int, QCheckBox] = {}
        self.item_rows: list[tuple[dict, QCheckBox, QLineEdit, QLineEdit, QLineEdit]] = []
        originals = self.original.get("items", [])
        represented = {item["code"] for item in originals}
        choices = [(copy.deepcopy(item), True) for item in originals]
        choices.extend(
            ({"code": code, "status": 1, "remaining_distance": 0, "remaining_time": 0}, False)
            for _, code in SERVICE_TYPES
            if code not in represented
        )
        labels = {code: text for text, code in SERVICE_TYPES}
        for item, selected in choices:
            code = item["code"]
            box = QCheckBox(labels.get(code, f"Unknown service ID {code}"))
            box.setChecked(selected)
            self.checkboxes.setdefault(code, box)
            items_layout.addWidget(box)
            fields = QFormLayout()
            values = [
                QLineEdit(str(item[field]))
                for field in ("status", "remaining_distance", "remaining_time")
            ]
            for label, control in zip(
                (
                    "Status (1–3 to send)",
                    "Remaining distance (signed native)",
                    "Remaining time (native)",
                ),
                values,
                strict=True,
            ):
                fields.addRow(label, control)
                control.textChanged.connect(self._validate)
            items_layout.addLayout(fields)
            self.item_rows.append((item, box, *values))
            box.toggled.connect(self._validate)
        self.error_label = _label("")
        layout.addWidget(self.error_label)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.mileage_edit.textChanged.connect(self._validate)
        self.dealer_edit.textChanged.connect(self._validate)
        self.status.textChanged.connect(self._validate)
        self.correction.textChanged.connect(self._validate)
        self.resize(560, 650)
        self._validate()

    def get_data(self) -> dict:
        """Return native-unit JSON, preserving retained imported item values."""
        data = copy.deepcopy(self.original)
        items = []
        for original, box, status, distance, remaining_time in self.item_rows:
            if box.isChecked():
                item = copy.deepcopy(original)
                item.update(
                    status=int(status.text()),
                    remaining_distance=int(distance.text()),
                    remaining_time=int(remaining_time.text()),
                )
                items.append(item)
        data.update(
            date=self.date_edit.date().toString("yyyy-MM-dd"),
            mileage_km=int(self.mileage_edit.text()),
            dealer=self.dealer_edit.text(),
            dealer_flag=self.dealer_flag.currentData(),
            correction=int(self.correction.text()),
            status=int(self.status.text()),
            items=items,
        )
        return data

    @Slot()
    def _validate(self) -> None:
        if not hasattr(self, "buttons"):
            return
        try:
            from app.history_files import validate_project

            data = self.get_data()
            validate_project({"schema_version": 1, "vin": None, "entries": [data]})
            valid = bool(data["items"])
            if (
                data["date"] != self.original.get("date")
                and self.date_edit.date() > QDate.currentDate()
            ):
                valid = False
            if not self.original:
                from app.history_files import entry_conflicts

                valid = (
                    valid
                    and not entry_conflicts({"schema_version": 1, "vin": None, "entries": [data]})[
                        0
                    ]
                )
        except (ValueError, OverflowError):
            valid = False
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(valid)
        self.error_label.setText(
            "" if valid else "Check numeric ranges, date, garage and service items."
        )


class HistoryFileWorker(CarWorker):
    """Run bounded local file operations off the GUI, without vehicle traffic."""

    def __init__(self, operation: Callable[[], object]) -> None:
        super().__init__(None)
        self.operation = operation

    def do_work(self) -> object:
        """Complete the single durable file operation even during disconnect."""
        return self.operation()


class ServiceHistoryPage(QWidget):
    """Offline local editor with isolated live and demonstration workspaces."""

    busy_changed = Signal(bool)
    mutation_active = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from app.history_workspace import HistoryWorkspaceStore, new_workspace

        self.store = HistoryWorkspaceStore()
        self.workspace = new_workspace()
        self._connection: Any = None
        self._ecus: list[dict] = []
        self.can_mutate: Callable[[], bool] = lambda: False
        from app.history_journal import HistoryJournalStore

        self.journals = HistoryJournalStore()
        self._journal_records: list[dict] = []
        self._journal_states: dict[str, dict[int, str]] = {}
        self._journal_dates: set = set()
        self._consumed_ids: set[str] = set()
        self._journal_ready = False
        self._journal_dirty = False
        self._writing = False
        self._pending_confirmation: tuple[object, dict, str, object] | None = None
        self._write_report: dict | None = None
        self._worker: CarWorker | None = None
        self._key = "offline"
        self._desired_key = "offline"
        self._success: Callable[[object], None] | None = None
        self._loading_key: str | None = None
        self._page = 0
        self._shutting_down = False
        self._workspace_ready = False
        self._controls: list[QPushButton] = []
        self._setup_ui()
        self._load_workspace("offline")

    def _button(self, text: str, slot: Callable) -> QPushButton:
        button = QPushButton(text)
        button.clicked.connect(slot)
        self._controls.append(button)
        return button

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        title = _label("Local service records")
        title.setObjectName("titleLabel")
        layout.addWidget(title)
        layout.addWidget(
            _label(
                "Existing vehicle history cannot be read. These records come from this app or an imported JSON file. Editing a local record never changes the car."
            )
        )
        self.context_label = _label("")
        layout.addWidget(self.context_label)
        row = QHBoxLayout()
        for text, slot in (
            ("Import JSON…", self._import),
            ("Export JSON…", self._export),
            ("Reload local project", self._reload),
        ):
            row.addWidget(self._button(text, slot))
        layout.addLayout(row)
        contexts = QHBoxLayout()
        for text, slot in (
            ("Offline project", self._offline),
            ("Associate with connected VIN…", self._associate),
        ):
            contexts.addWidget(self._button(text, slot))
        layout.addLayout(contexts)
        self.message = _label("")
        layout.addWidget(self.message)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.entry_container = QWidget()
        self.entry_layout = QVBoxLayout(self.entry_container)
        self.scroll_area.setWidget(self.entry_container)
        layout.addWidget(self.scroll_area, 1)
        self.add_btn = self._button("+ Add local entry", self._on_add_clicked)
        layout.addWidget(self.add_btn)
        self.replace_btn = self._button(
            "Erase and replace with this local list…", self._replace_history
        )
        layout.addWidget(self.replace_btn)
        self.journal_button = QPushButton("Show history operation journals")
        self.journal_button.setCheckable(True)
        layout.addWidget(self.journal_button)
        self.journal_scroll = QScrollArea()
        self.journal_scroll.setWidgetResizable(True)
        self.journal_scroll.setMaximumHeight(220)
        self.journal_container = QWidget()
        self.journal_layout = QVBoxLayout(self.journal_container)
        self.journal_scroll.setWidget(self.journal_container)
        self.journal_scroll.hide()
        self.journal_button.toggled.connect(self.journal_scroll.setVisible)
        layout.addWidget(self.journal_scroll)
        self.report_export = self._button(
            "Export interrupted operation evidence…", self._export_memory_report
        )
        self.report_export.hide()
        layout.addWidget(self.report_export)
        layout.addWidget(
            _label(
                "Append sends one local draft without erasing. Erase-and-replace deletes all existing car entries absent from your reviewed list. Unknown car dates cannot be checked."
            )
        )

    def _run(self, operation: Callable[[], object], success: Callable[[object], None]) -> None:
        if self._worker is not None or self._shutting_down:
            return
        self._start_worker(HistoryFileWorker(operation), success)

    def _start_worker(self, worker: CarWorker, success: Callable[[object], None]) -> None:
        self._success = success
        self._worker = worker
        worker.result_ready.connect(self._result)
        worker.error.connect(self._error)
        worker.progress.connect(self.message.setText)
        worker.finished.connect(self._finished)
        self._set_busy(True)
        worker.start()

    def _set_busy(self, busy: bool) -> None:
        busy = busy or self._shutting_down
        for button in self._controls:
            button.setEnabled(not busy)
        self.add_btn.setEnabled(
            not busy
            and self._workspace_ready
            and (self._journal_ready or self.workspace["project"]["vin"] is None)
        )
        self.entry_container.setEnabled(not busy and self._workspace_ready)
        self.replace_btn.setEnabled(
            not busy and self._workspace_ready and self._journal_ready and self._can_offer_write()
        )
        self.busy_changed.emit(busy)

    @Slot(object)
    def _result(self, value: object) -> None:
        if self.sender() is self._worker and self._success is not None:
            self._success(value)

    @Slot(str)
    def _error(self, message: str) -> None:
        if self.sender() is not self._worker:
            return
        if isinstance(self._worker, HistoryFileWorker):
            if self._loading_key is None:
                self._workspace_ready = False
            if self._loading_key == self._desired_key:
                self._desired_key = self._key
            self.message.setText(
                "Local file operation failed. Publication could not be confirmed; displayed data is retained for inspection. Reload before editing, or explicitly import a replacement. Check format, permissions, free space and the session log."
            )
        else:
            self.message.setText(
                "History operation could not start or complete. "
                + message
                + " No automatic retry will occur. Inspect the local journals before a new action."
            )

    @Slot()
    def _finished(self) -> None:
        worker = self.sender()
        if worker is not self._worker:
            return
        self._worker = None
        self._success = None
        self._loading_key = None
        worker.deleteLater()
        was_writing = self._writing
        self._writing = False
        self._set_busy(False)
        if was_writing:
            self.mutation_active.emit(False)
        if self._shutting_down:
            return
        if self._desired_key != self._key:
            self._pending_confirmation = None
            self._load_workspace(self._desired_key)
        elif self._pending_confirmation is not None:
            pending = self._pending_confirmation
            self._pending_confirmation = None
            self._confirm_history(*pending)
        elif self._journal_dirty:
            self._refresh_journals()

    def _load_workspace(self, key: str) -> None:
        if self._shutting_down:
            return
        self._desired_key = key
        if self._worker is not None:
            return
        self._journal_ready = False
        self._loading_key = key

        def loaded(value: object) -> None:
            self._key = key
            self._loaded(value)

        self._run(lambda: self.store.load_workspace(key), loaded)

    def _loaded(self, value: object) -> None:
        assert isinstance(value, dict)
        self.workspace = value
        self._workspace_ready = True
        self._journal_records = []
        self._journal_states = {}
        self._journal_dates = set()
        self._consumed_ids = set()
        self._journal_ready = False
        self._clear_layout(self.journal_layout)
        self._journal_dirty = True
        self._page = 0
        self.message.clear()
        self._render()

    def is_busy(self) -> bool:
        """Whether this page still owns an active local file worker."""
        return self._worker is not None

    def shutdown(self) -> None:
        """Finish a current durable publication without starting any more file work."""
        self._shutting_down = True
        self._set_busy(True)

    def _context_current(self, workspace: dict, key: str) -> bool:
        if (
            self._shutting_down
            or self._worker is not None
            or self.workspace is not workspace
            or self._key != key
        ):
            self.message.setText(
                "The local project changed while the dialog was open. Reopen the action for the current project."
            )
            return False
        return True

    def set_connection(self, connection: Any, ecus: list[dict] | None = None) -> None:
        """Switch isolated local workspace; do not query the vehicle."""
        if self._connection is not connection:
            self._ecus = []
        self._connection = connection
        if ecus is not None:
            self.set_targets(ecus)
        if connection is None:
            self._load_workspace("offline")
            return
        demo = hasattr(connection, "data")
        vin = (
            connection.data.get("vehicle", {}).get("vin", "")
            if demo
            else getattr(connection, "verified_vin", "")
        )
        from app.history_files import valid_vin

        self._load_workspace(
            ("demo-" if demo else "live-") + vin
            if valid_vin(vin)
            else ("demo-unbound" if demo else "offline")
        )

    @Slot()
    def _reload(self) -> None:
        self._load_workspace(self._key)

    @Slot()
    def _offline(self) -> None:
        self._load_workspace("offline")

    def _save(self, workspace: dict) -> None:
        if not self._workspace_ready:
            return
        key = self._key
        snapshot = copy.deepcopy(workspace)

        def save() -> object:
            self.store.save_workspace(key, snapshot)
            return snapshot

        self._run(save, self._loaded)

    def _render(self) -> None:
        from app.history_files import entry_conflicts

        project = self.workspace["project"]
        self.context_label.setText(
            f"Workspace: {self._key} · File VIN: {project['vin'] or 'Unbound'} · Local evidence only"
        )
        self._clear_layout(self.entry_layout)
        conflicts = entry_conflicts(project)
        labels = {code: text for text, code in SERVICE_TYPES}
        entries = project["entries"]
        if not entries:
            self.entry_layout.addWidget(
                _label("No local entries. Existing car history is unknown.")
            )
        self._page = min(self._page, max(0, (len(entries) - 1) // 25))
        for index in range(self._page * 25, min(len(entries), (self._page + 1) * 25)):
            entry = entries[index]
            card = QFrame()
            card.setObjectName("card")
            box = QVBoxLayout(card)
            meta = self.workspace["records"][index]
            day = QDate.fromString(entry["date"], "yyyy-MM-dd")
            locale = _regional_locale()
            box.addWidget(
                _label(
                    f"{locale.toString(day, QLocale.FormatType.ShortFormat)} · {locale.toString(entry['mileage_km'])} km · {entry['dealer']}"
                )
            )
            box.addWidget(
                _label(
                    f"{meta['origin'].capitalize()} · {self._record_state(index)} · Record status {entry['status']} · {len(entry['items'])} items"
                )
            )
            box.addWidget(
                _label(
                    ", ".join(
                        labels.get(item["code"], f"Unknown ID {item['code']}")
                        for item in entry["items"]
                    )
                )
            )
            if conflicts[index]:
                box.addWidget(_label("Cannot send: " + "; ".join(conflicts[index])))
            if "source_workspace" in meta:
                box.addWidget(
                    _label(
                        f"Copied from {meta['source_workspace']}; original VIN: {meta.get('source_vin') or 'Unbound'}"
                    )
                )
            toggle = QPushButton("Show all item details")
            toggle.setCheckable(True)
            box.addWidget(toggle)
            detail = _label(
                "\n".join(
                    f"{labels.get(item['code'], 'Unknown ID ' + str(item['code']))}: status {item['status']}, remaining distance {item['remaining_distance']} (native), remaining time {item['remaining_time']} (native)"
                    for item in entry["items"]
                )
            )
            detail.hide()
            toggle.toggled.connect(detail.setVisible)
            box.addWidget(detail)
            row = QHBoxLayout()
            edit = QPushButton("Edit local draft")
            edit.clicked.connect(lambda _checked=False, i=index: self._edit(i))
            remove = QPushButton("Remove local draft")
            remove.clicked.connect(lambda _checked=False, i=index: self._remove(i))
            edit.setEnabled(not self._consumed(index))
            remove.setEnabled(not self._consumed(index))
            row.addWidget(edit)
            row.addWidget(remove)
            append = QPushButton("Append this entry…")
            append.setEnabled(
                self._journal_ready
                and self._can_offer_write()
                and not self._consumed(index)
                and not conflicts[index]
            )
            append.clicked.connect(
                lambda _checked=False, i=index: self._prepare_history("append", i)
            )
            row.addWidget(append)
            box.addLayout(row)
            self.entry_layout.addWidget(card)
        if len(entries) > 25:
            row = QHBoxLayout()
            for text, delta in (("Previous 25", -1), ("Next 25", 1)):
                button = QPushButton(text)
                button.setEnabled(0 <= self._page + delta <= (len(entries) - 1) // 25)
                button.clicked.connect(lambda _checked=False, step=delta: self._page_move(step))
                row.addWidget(button)
            self.entry_layout.addWidget(
                _label(
                    f"Page {self._page + 1} of {(len(entries) + 24) // 25}; imported order preserved"
                )
            )
            self.entry_layout.addLayout(row)
        self.entry_layout.addStretch()

    @staticmethod
    def _clear_layout(layout: QVBoxLayout | QHBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
            elif isinstance(child_layout, (QVBoxLayout, QHBoxLayout)):
                ServiceHistoryPage._clear_layout(child_layout)
                child_layout.deleteLater()

    def _page_move(self, step: int) -> None:
        self._page += step
        self._render()

    @Slot()
    def _on_add_clicked(self) -> None:
        self._edit(None)

    def _edit(self, index: int | None) -> None:
        if (
            self._worker is not None
            or not self._workspace_ready
            or (self.workspace["project"]["vin"] is not None and not self._journal_ready)
        ):
            return
        import json

        from app.history_files import entry_conflicts, parse_project
        from app.history_workspace import new_record

        before, key = self.workspace, self._key
        if index is not None and self._consumed(index):
            return
        entry = before["project"]["entries"][index] if index is not None else None
        dialog = AddServiceDialog(self, entry)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if not self._context_current(before, key):
            return
        data = dialog.get_data()
        from datetime import date

        if (entry is None or data["date"] != entry["date"]) and date.fromisoformat(
            data["date"]
        ) in self._known_journal_dates():
            self.message.setText(
                "That date belongs to a prior accepted or uncertain local operation. Inspect its journal; it is not a new append draft."
            )
            return
        workspace = copy.deepcopy(self.workspace)
        entries = workspace["project"]["entries"]
        if (entry is None or data["date"] != entry["date"]) and any(
            row["date"] == data["date"] for i, row in enumerate(entries) if i != index
        ):
            self.message.setText(
                "That date is already in known local records. Resolve duplicate dates explicitly; unseen car dates cannot be checked."
            )
            return
        if index is None:
            entries.append(data)
            workspace["records"].append(new_record("draft"))
        else:
            entries[index] = data
        try:
            parse_project(json.dumps(workspace["project"]).encode())
            problems = entry_conflicts(workspace["project"])[index if index is not None else -1]
            if problems and index is None:
                raise ValueError("; ".join(problems))
        except ValueError:
            self.message.setText(
                "The entry contains unsupported values. Remove unknown service types or correct its fields before saving this edit. The original is preserved."
            )
            return
        self._save(workspace)

    def _remove(self, index: int) -> None:
        if self._worker is not None or not self._workspace_ready or self._consumed(index):
            return
        before, key = self.workspace, self._key
        if (
            QMessageBox.question(
                self, "Remove local draft", "Remove only this local draft? The car is unchanged."
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        if not self._context_current(before, key):
            return
        workspace = copy.deepcopy(before)
        del workspace["project"]["entries"][index]
        del workspace["records"][index]
        self._save(workspace)

    @Slot()
    def _import(self) -> None:
        if self._worker is not None:
            return
        from pathlib import Path

        from app.history_files import load_project
        from app.history_workspace import new_workspace

        before, key = self.workspace, self._key
        path, _ = QFileDialog.getOpenFileName(self, "Import local project", "", "JSON (*.json)")
        if not path:
            return
        if (
            QMessageBox.question(
                self,
                "Replace local project",
                "Replace the open local project with this JSON file? No car request or write authorization is imported.",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        if not self._context_current(before, key):
            return

        def operation() -> object:
            project = load_project(Path(path))
            workspace = new_workspace(project, origin="imported")
            self.store.save_workspace(key, workspace)
            return workspace

        self._run(operation, self._loaded)

    @Slot()
    def _export(self) -> None:
        if self._worker is not None:
            return
        from pathlib import Path

        from app.history_files import save_project

        before, key = self.workspace, self._key
        path, _ = QFileDialog.getSaveFileName(
            self, "Export local project", "history.json", "JSON (*.json)"
        )
        if path and self._context_current(before, key):
            project = copy.deepcopy(self.workspace["project"])
            self._run(
                lambda: save_project(Path(path), project),
                lambda _: self.message.setText(
                    "Local JSON exported. No vehicle state was verified."
                ),
            )

    @Slot()
    def _associate(self) -> None:
        if self._worker is not None or self._connection is None or not self._workspace_ready:
            return
        from app.history_files import valid_vin

        before, previous_key, connection = self.workspace, self._key, self._connection
        demo = hasattr(connection, "data")
        vin = (
            connection.data.get("vehicle", {}).get("vin", "")
            if demo
            else getattr(connection, "verified_vin", "")
        )
        if not valid_vin(vin):
            return
        if (
            QMessageBox.question(
                self,
                "Associate local project",
                f"Copy this local project to {vin}? This replaces that vehicle's open local editing project. Source VIN/provenance is retained. This never writes the car.",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        if not self._context_current(before, previous_key) or self._connection is not connection:
            return
        workspace = copy.deepcopy(before)
        for record in workspace["records"]:
            record.setdefault("source_vin", workspace["project"]["vin"])
            record.setdefault("source_workspace", previous_key)
        workspace["project"]["vin"] = vin
        key = ("demo-" if demo else "live-") + vin
        if key != previous_key:
            for record in workspace["records"]:
                if "write_state" in record:
                    record["source_write_state"] = record.pop("write_state")
                if "last_operation" in record:
                    record["source_last_operation"] = record.pop("last_operation")

        def operation() -> object:
            self.store.save_workspace(key, workspace)
            return workspace

        self._desired_key = key

        def loaded(value: object) -> None:
            self._key = key
            self._loaded(value)

        self._run(operation, loaded)

    def set_targets(self, ecus: list[dict]) -> None:
        """Update identified targets without reading the car or changing local records."""
        self._ecus = [dict(row) for row in ecus]
        if self._workspace_ready and not self.is_busy():
            self._render()
            self._set_busy(False)

    def _can_offer_write(self) -> bool:
        from app.history_files import valid_vin
        from app.history_write import select_target

        connection = self._connection
        if (
            connection is None
            or hasattr(connection, "data")
            or getattr(connection, "read_only", True)
            or not getattr(connection, "alive_ok", False)
            or not valid_vin(getattr(connection, "verified_vin", ""))
            or self.workspace["project"]["vin"] != connection.verified_vin
            or not self._key.startswith("live-")
            or getattr(connection, "power_sufficient", None) is False
        ):
            return False
        try:
            select_target(self._ecus)
        except (ValueError, OSError):
            return False
        return True

    def _known_journal_dates(self) -> set:
        return set(self._journal_dates)

    def _step_state(self, record: dict, index: int) -> str:
        return self._journal_states.get(record["intent"]["id"], {}).get(index, "unattempted")

    def _consumed(self, index: int) -> bool:
        meta = self.workspace["records"][index]
        return (
            meta.get("write_state") in ("accepted", "uncertain") or meta["id"] in self._consumed_ids
        )

    def _record_state(self, index: int) -> str:
        return (
            "Previously accepted or possibly sent; inspect journal"
            if self._consumed(index)
            else "Local unsent draft"
        )

    def _refresh_journals(self) -> None:
        self._journal_dirty = False
        key, before = self._key, self.workspace
        vin = before["project"]["vin"]
        environment = "demo" if key.startswith("demo-") else "live"
        memory = copy.deepcopy(self._write_report)

        def operation() -> object:
            records = self.journals.list_records(vin, environment) if vin else []
            from datetime import date

            workspace = copy.deepcopy(before)
            metas = {meta["id"]: meta for meta in workspace["records"]}
            states = {}
            dates = set()
            consumed = set()

            def latch(intent: dict, latest: dict) -> None:
                for i, step in enumerate(intent["requests"]):
                    state = latest.get(i, "unattempted")
                    if step["kind"] != "add" or state not in ("accepted", "sending", "uncertain"):
                        continue
                    identity = intent["draft_ids"][step["entry_index"]]
                    dates.add(date.fromisoformat(intent["intended"][step["entry_index"]]["date"]))
                    consumed.add(identity)
                    if identity in metas:
                        metas[identity]["write_state"] = (
                            "accepted" if state == "accepted" else "uncertain"
                        )

            for record in records:
                intent = record["intent"]
                latest = {
                    event["step"]: event["state"]
                    for event in record["events"]
                    if event["step"] is not None
                }
                states[intent["id"]] = latest
                latch(intent, latest)
                for i, step in enumerate(intent["requests"]):
                    if step["kind"] == "add" and latest.get(i) in (
                        "accepted",
                        "sending",
                        "uncertain",
                    ):
                        identity = intent["draft_ids"][step["entry_index"]]
                        if identity in metas:
                            metas[identity]["last_operation"] = intent["id"]
            if (
                memory
                and memory.get("workspace_key") == key
                and memory.get("intent", {}).get("vin") == vin
            ):
                latest = {
                    event["step"]: event["state"]
                    for event in memory["events"]
                    if event["step"] is not None
                }
                latch(memory["intent"], latest)
            if workspace != before:
                self.store.save_workspace(key, workspace)
            return {
                "records": records,
                "workspace": workspace,
                "states": states,
                "dates": dates,
                "consumed": consumed,
            }

        def loaded(value: object) -> None:
            assert isinstance(value, dict)
            self.workspace = value["workspace"]
            self._journal_records = value["records"]
            self._journal_states = value["states"]
            self._journal_dates = value["dates"]
            self._consumed_ids = value["consumed"]
            self._journal_ready = True
            self._render()
            self._render_journals()

        self._run(operation, loaded)

    def _render_journals(self) -> None:
        self._clear_layout(self.journal_layout)
        self.journal_layout.addWidget(
            _label(
                "Local history intent/results only. Prior car history is unavailable; these journals cannot restore it. No automatic replay or resume."
            )
        )
        # Most recent50report previews; all files remain on disk and count in guards.
        for record in self._journal_records[-50:]:
            intent = record["intent"]
            state = record["events"][-1]["state"]
            if record["events"][-1]["step"] is not None or state == "prepared":
                state = "Interrupted / outcome uncertain — inspect iDrive"
            box = QFrame()
            layout = QVBoxLayout(box)
            layout.addWidget(
                _label(
                    f"{intent['created']} · {intent['mode']} · {state}\nVIN {intent['vin']} · {intent['target']['name']} · {len(intent['intended'])} record(s)"
                )
            )
            details = _label(
                "\n".join(
                    f"{i + 1}. {step['kind']}: {self._step_state(record, i)}"
                    for i, step in enumerate(intent["requests"][:100])
                )
                + "\n"
                + record["events"][-1]["detail"]
            )
            if len(intent["requests"]) > 100:
                details.setText(
                    details.text()
                    + "\nFirst100steps shown. Export the journal for every step and raw response."
                )
            details.hide()
            toggle = QPushButton("Show step outcomes")
            toggle.setCheckable(True)
            toggle.toggled.connect(details.setVisible)
            layout.addWidget(toggle)
            layout.addWidget(details)
            export = QPushButton("Export history journal…")
            export.clicked.connect(lambda _checked=False, r=record: self._export_journal(r))
            layout.addWidget(export)
            delete = QPushButton("Delete local journal…")
            delete.clicked.connect(lambda _checked=False, r=record: self._delete_journal(r))
            layout.addWidget(delete)
            self.journal_layout.addWidget(box)
        self.journal_layout.addStretch()

    @Slot()
    def _replace_history(self) -> None:
        self._prepare_history("replace", None)

    def _prepare_history(self, mode: str, index: int | None) -> None:
        if (
            self.is_busy()
            or not self._journal_ready
            or not self._can_offer_write()
            or not self.can_mutate()
            or (mode == "append" and index is not None and self._consumed(index))
        ):
            self.message.setText(
                "Bind the project to the connected VIN and wait for all page operations to settle. A supported exact headunit, writable session and readable local journals are required."
            )
            return
        from app.history_write import HistoryPrepareWorker

        before, key, connection = self.workspace, self._key, self._connection
        worker = HistoryPrepareWorker(connection, self._ecus, before, mode, index, self.journals)

        def prepared(value: object) -> None:
            self._pending_confirmation = (value, before, key, connection)

        self._start_worker(worker, prepared)

    def _confirm_history(self, plan: object, before: dict, key: str, connection: object) -> None:
        from app.history_write import HistoryPlan, HistoryWriteWorker

        if (
            not isinstance(plan, HistoryPlan)
            or not self._context_current(before, key)
            or connection is not self._connection
            or not self._can_offer_write()
            or not self.can_mutate()
        ):
            return
        data = plan.data()
        dialog = QDialog(self)
        dialog.setWindowTitle(
            "Confirm history append"
            if data["mode"] == "append"
            else "Confirm irreversible history replacement"
        )
        dialog.resize(620, 650)
        layout = QVBoxLayout(dialog)
        layout.addWidget(
            _label(
                f"VIN: {data['vin']}\nHeadunit: {data['target']['name']}\nMode: {data['mode']} · {len(data['intended'])} dated record(s) in the order below"
            )
        )
        layout.addWidget(
            _label(
                "Existing vehicle history cannot be read or backed up. Unseen duplicate dates and available capacity cannot be checked. Append never erases; a rejection stops this operation. Replacement permanently deletes records absent from this list."
            )
        )
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        labels = {code: name for name, code in SERVICE_TYPES}
        preview = _label(
            "\n\n".join(
                f"{i + 1}. {entry['date']} · {entry['mileage_km']} km · {entry['dealer']} · status {entry['status']}\n"
                + ", ".join(
                    labels[item["code"]]
                    + f" (status {item['status']}, distance {item['remaining_distance']}, time {item['remaining_time']})"
                    for item in entry["items"]
                )
                for i, entry in enumerate(data["intended"])
            )
        )
        scroll.setWidget(preview)
        layout.addWidget(scroll, 1)
        layout.addWidget(
            _label(
                "The headunit will be reset after accepted entries. Wait for it to restart and inspect iDrive. No readback, rollback or automatic retry is available. Once started there is no Cancel; navigation, disconnect and normal close are blocked."
            )
        )
        power = QCheckBox(
            "I confirm sufficient vehicle and computer power for the entire operation."
        )
        layout.addWidget(power)
        layout.addWidget(
            _label(
                "No source-derived power threshold is available for this operation; reliable power sufficiency is unknown. Do not proceed if the car or computer reports insufficient power."
            )
        )
        irreversible = QCheckBox(
            "I accept irreversible loss of all car entries absent from this replacement list."
        )
        irreversible.setVisible(data["mode"] == "replace")
        layout.addWidget(irreversible)
        prior = QCheckBox(
            "I inspected iDrive and the prior interrupted/uncertain operation before this new action."
        )
        needs_prior = any(
            record["events"][-1]["state"]
            not in ("response-confirmed", "rejected", "cycle-required")
            or record["events"][-1]["step"] is not None
            for record in self._journal_records
        )
        prior.setVisible(needs_prior)
        layout.addWidget(prior)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setText("Append entry" if data["mode"] == "append" else "Erase and replace")

        def valid() -> None:
            ok.setEnabled(
                power.isChecked()
                and (data["mode"] != "replace" or irreversible.isChecked())
                and (not needs_prior or prior.isChecked())
            )

        for check in (power, irreversible, prior):
            check.toggled.connect(valid)
        valid()
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if (
            not self._context_current(before, key)
            or self._connection is not connection
            or not self.can_mutate()
            or not self._can_offer_write()
        ):
            return
        self._writing = True
        self.mutation_active.emit(True)
        worker = HistoryWriteWorker(
            connection,
            plan,
            self.journals,
            power_acknowledged=power.isChecked(),
            replacement_acknowledged=irreversible.isChecked(),
        )
        self._start_worker(worker, self._history_written)

    def _history_written(self, value: object) -> None:
        assert isinstance(value, dict)
        from app.history_write import HistoryWriteWorker

        worker = self.sender()
        assert isinstance(worker, HistoryWriteWorker)
        self._write_report = copy.deepcopy(value)
        self._write_report["intent"] = worker.plan.data()
        self._write_report["workspace_key"] = self._key
        self.report_export.setVisible(bool(value["persistence_failed"]))
        self.message.setText(
            f"History outcome: {value['state']}. "
            + value["instructions"]
            + (
                " Local journal persistence failed; export the retained evidence before closing."
                if value["persistence_failed"]
                else ""
            )
        )
        self._journal_dirty = True

    def _export_memory_report(self) -> None:
        if self.is_busy() or self._write_report is None:
            return
        from pathlib import Path

        from app.history_journal import export_memory_evidence

        before, key = self.workspace, self._key
        path, _ = QFileDialog.getSaveFileName(
            self, "Export retained history evidence", "history-interruption.json", "JSON (*.json)"
        )
        if not path or not self._context_current(before, key):
            return
        report = copy.deepcopy(self._write_report)
        self._run(
            lambda: export_memory_evidence(Path(path), report),
            lambda _: self.message.setText(
                "Interrupted history evidence exported; inspect iDrive before any new action."
            ),
        )

    def _export_journal(self, record: dict) -> None:
        if self.is_busy():
            return
        from pathlib import Path

        before, key = self.workspace, self._key
        source = self.journals.root / (record["intent"]["id"] + ".json")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export history journal", source.name, "JSON (*.json)"
        )
        if path and self._context_current(before, key):
            self._run(
                lambda: self.journals.export_record(source, Path(path)),
                lambda _: self.message.setText(
                    "Local history journal exported. This is not a restorable car-history backup."
                ),
            )

    def _delete_journal(self, record: dict) -> None:
        if self.is_busy():
            return
        before, key = self.workspace, self._key
        if (
            QMessageBox.question(
                self,
                "Delete local history journal",
                "Delete this local intent/result record? This loses preservation, prior-date guard and troubleshooting evidence. Accepted/uncertain cards stay non-resendable, but deleted journal dates may no longer be known. The car is unchanged and unknown old history cannot be restored.",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        if not self._context_current(before, key):
            return
        source = self.journals.root / (record["intent"]["id"] + ".json")

        def removed(_: object) -> None:
            self._journal_dirty = True

        self._run(lambda: self.journals.delete_record(source), removed)
