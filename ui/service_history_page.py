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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from app.history_workspace import HistoryWorkspaceStore, new_workspace

        self.store = HistoryWorkspaceStore()
        self.workspace = new_workspace()
        self._connection: Any = None
        self._worker: HistoryFileWorker | None = None
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
        layout.addWidget(
            _label(
                "Vehicle append and explicit erase-and-replace execution are the next implementation step. No vehicle requests are made by this editor. Unknown car dates cannot be checked."
            )
        )

    def _run(self, operation: Callable[[], object], success: Callable[[object], None]) -> None:
        if self._worker is not None or self._shutting_down:
            return
        self._success = success
        worker = HistoryFileWorker(operation)
        self._worker = worker
        worker.result_ready.connect(self._result)
        worker.error.connect(self._error)
        worker.finished.connect(self._finished)
        self._set_busy(True)
        worker.start()

    def _set_busy(self, busy: bool) -> None:
        busy = busy or self._shutting_down
        for button in self._controls:
            button.setEnabled(not busy)
        self.add_btn.setEnabled(not busy and self._workspace_ready)
        self.entry_container.setEnabled(not busy and self._workspace_ready)
        self.busy_changed.emit(busy)

    @Slot(object)
    def _result(self, value: object) -> None:
        if self.sender() is self._worker and self._success is not None:
            self._success(value)

    @Slot(str)
    def _error(self, _message: str) -> None:
        if self.sender() is self._worker:
            if self._loading_key is None:
                self._workspace_ready = False
            if self._loading_key == self._desired_key:
                self._desired_key = self._key
            self.message.setText(
                "Local file operation failed. Publication could not be confirmed; displayed data is retained for inspection. Reload before editing, or explicitly import a replacement. Check format, permissions, free space and the session log."
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
        self._set_busy(False)
        if not self._shutting_down and self._desired_key != self._key:
            self._load_workspace(self._desired_key)

    def _load_workspace(self, key: str) -> None:
        if self._shutting_down:
            return
        self._desired_key = key
        if self._worker is not None:
            return
        self._loading_key = key

        def loaded(value: object) -> None:
            self._key = key
            self._loaded(value)

        self._run(lambda: self.store.load_workspace(key), loaded)

    def _loaded(self, value: object) -> None:
        assert isinstance(value, dict)
        self.workspace = value
        self._workspace_ready = True
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

    def set_connection(self, connection: Any) -> None:
        """Switch isolated local workspace; do not query the vehicle."""
        self._connection = connection
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
                    f"{meta['origin'].capitalize()} local draft · Record status {entry['status']} · {len(entry['items'])} items"
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
            row.addWidget(edit)
            row.addWidget(remove)
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
        if self._worker is not None or not self._workspace_ready:
            return
        import json

        from app.history_files import entry_conflicts, parse_project
        from app.history_workspace import new_record

        before, key = self.workspace, self._key
        entry = before["project"]["entries"][index] if index is not None else None
        dialog = AddServiceDialog(self, entry)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if not self._context_current(before, key):
            return
        data = dialog.get_data()
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
        if self._worker is not None or not self._workspace_ready:
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

        def operation() -> object:
            self.store.save_workspace(key, workspace)
            return workspace

        self._desired_key = key

        def loaded(value: object) -> None:
            self._key = key
            self._loaded(value)

        self._run(operation, loaded)
