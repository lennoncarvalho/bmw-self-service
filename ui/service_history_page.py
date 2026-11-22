"""Temporary service-history staging with explicit file and reviewed vehicle writes."""

import copy
import logging
import uuid
from collections import Counter
from collections.abc import Callable, Collection
from datetime import date
from typing import Any

from PySide6.QtCore import QDate, QLocale, Qt, Signal, Slot
from PySide6.QtGui import QHideEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.service_history import ITEM_STATUS_LABELS, RECORD_STATUS_LABELS, SERVICE_TYPES
from app.session import LIVE, SessionEnvironment, environment
from app.worker import CarWorker
from ui.cockpit import (
    DangerButton,
    ElidedLabel,
    PageHeader,
    StatusLabel,
    caption,
    match_button_widths,
)
from ui.dialogs import CockpitDialog
from ui.form_inputs import CheckInput, DateInput, SelectInput
from ui.regional import regional_locale

logger = logging.getLogger(__name__)


def _label(text: str) -> QLabel:
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


def _status_control(value: int, labels: dict[int, str], *, compact: bool = False) -> SelectInput:
    """Label supported source statuses while retaining an imported unknown code."""
    control = SelectInput(compact=compact)
    for code, label in labels.items():
        control.addItem(label, code)
    if value not in labels:
        control.addItem(f"Unknown status ({value})", value)
    control.setCurrentIndex(control.findData(value))
    return control


def _status_text(value: int, labels: dict[int, str]) -> str:
    return labels.get(value, f"Unknown status ({value})")


class AddServiceDialog(CockpitDialog):
    """Edit a local record without losing unknown imported fields or items."""

    SERVICE_ITEMS = SERVICE_TYPES

    def __init__(
        self,
        parent: QWidget | None = None,
        entry: dict | None = None,
        *,
        existing_dates: Collection[str] = (),
        existing_entries: Collection[dict] = (),
    ) -> None:
        """Validate a staged entry against the other displayed records, excluding itself."""
        super().__init__(
            "Edit service entry" if entry else "Add service entry", parent, width=960, height=780
        )
        self.setMinimumWidth(780)
        self.original = copy.deepcopy(entry or {})
        self._existing_entries = copy.deepcopy(list(existing_entries))
        self._existing_dates = frozenset(existing_dates) | {
            row["date"] for row in self._existing_entries
        }
        layout = self.body
        form = QGridLayout()
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(8)

        def field(text: str, control: QWidget, row: int, column: int) -> None:
            label = QLabel(text)
            label.setBuddy(control)
            form.addWidget(label, row * 2, column)
            form.addWidget(control, row * 2 + 1, column)
            form.setColumnStretch(column, 1)

        original_date = QDate.fromString(self.original.get("date", ""), "yyyy-MM-dd")
        self.date_edit = DateInput(
            value=original_date if entry else QDate.currentDate(),
            minimum=QDate(1, 1, 1),
            maximum=max(QDate.currentDate(), original_date),
        )
        field("Date", self.date_edit, 0, 0)
        self.mileage_edit = QLineEdit(str(self.original.get("mileage_km", 0)))
        field("Mileage (km)", self.mileage_edit, 0, 1)
        self.dealer_edit = QLineEdit(self.original.get("dealer", "OWNER"))
        field("Garage (1–7 ASCII characters)", self.dealer_edit, 1, 0)
        self.dealer_flag = SelectInput(options=(("Independent / owner", 0), ("BMW garage", 1)))
        original_flag = self.original.get("dealer_flag", 0)
        if original_flag not in (0, 1):
            self.dealer_flag.addItem(f"Unknown flag {original_flag}", original_flag)
        self.dealer_flag.setCurrentIndex(self.dealer_flag.findData(original_flag))
        field("Garage type", self.dealer_flag, 1, 1)
        self.status = _status_control(self.original.get("status", 1), RECORD_STATUS_LABELS)
        self.status.setToolTip(
            "Overall completion of this dated entry; item completion is separate."
        )
        field("Overall completion", self.status, 2, 0)
        layout.addLayout(form)
        layout.addWidget(
            _label("Select 1–13 service items and choose the completion status for each.")
        )
        body = QWidget()
        body.setObjectName("historyItemTable")
        items_layout = QGridLayout(body)
        items_layout.setContentsMargins(12, 8, 12, 8)
        items_layout.setHorizontalSpacing(12)
        items_layout.setVerticalSpacing(4)
        for column, title in enumerate(("", "Service item", "Completion")):
            items_layout.addWidget(caption(title, "tableHeader"), 0, column)
        items_layout.setColumnStretch(1, 1)
        layout.addWidget(body)
        self.checkboxes: dict[int, QCheckBox] = {}
        self.item_rows: list[tuple[dict, QCheckBox, QComboBox]] = []
        originals = self.original.get("items", [])
        represented = {item["code"] for item in originals}
        choices = [(copy.deepcopy(item), True) for item in originals]
        choices.extend(
            ({"code": code, "status": 1, "remaining_distance": 0, "remaining_time": 0}, False)
            for _, code in SERVICE_TYPES
            if code not in represented
        )
        labels = {code: text for text, code in SERVICE_TYPES}
        for row, (item, selected) in enumerate(choices, 1):
            code = item["code"]
            title = labels.get(code, f"Unknown service ID {code}")
            box = QCheckBox()
            box.setAccessibleName(f"Include {title}")
            box.setChecked(selected)
            self.checkboxes.setdefault(code, box)
            items_layout.addWidget(box, row, 0)
            item_label = _label(title)
            item_label.setBuddy(box)
            items_layout.addWidget(item_label, row, 1)
            control = _status_control(item["status"], ITEM_STATUS_LABELS, compact=True)
            control.setFixedWidth(180)
            control.setAccessibleName(f"{title}: Completion")
            control.setToolTip(
                "Completion of this service item, independent of overall entry completion"
            )
            control.setEnabled(selected)
            box.toggled.connect(control.setEnabled)
            control.currentIndexChanged.connect(self._validate)
            items_layout.addWidget(control, row, 2)
            self.item_rows.append((item, box, control))
            box.toggled.connect(self._validate)
        self.error_label = _label("")
        self.error_label.setProperty("role", "notice")
        self.add_notice(self.error_label)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            "Add to list" if not entry else "Update entry"
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.add_buttons(self.buttons)
        self.date_edit.dateChanged.connect(self._validate)
        self.mileage_edit.textChanged.connect(self._validate)
        self.dealer_edit.textChanged.connect(self._validate)
        self.dealer_flag.currentIndexChanged.connect(self._validate)
        self.status.currentIndexChanged.connect(self._validate)
        self.resize(960, 780)
        self._validate()

    def get_data(self) -> dict:
        """Return native-unit JSON, preserving retained imported item values."""
        data = copy.deepcopy(self.original)
        items = []
        for original, box, status in self.item_rows:
            if box.isChecked():
                item = copy.deepcopy(original)
                item["status"] = status.currentData()
                items.append(item)
        data.update(
            date=self.date_edit.date().toString("yyyy-MM-dd"),
            mileage_km=int(self.mileage_edit.text()),
            dealer=self.dealer_edit.text(),
            dealer_flag=self.dealer_flag.currentData(),
            correction=self.original.get("correction", 0),
            status=self.status.currentData(),
            items=items,
        )
        return data

    @Slot()
    def accept(self) -> None:
        """Keep invalid or duplicate entries open instead of silently dropping the edit."""
        self._validate()
        if self.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled():
            super().accept()

    @Slot()
    def _validate(self) -> None:
        if not hasattr(self, "buttons"):
            return
        message = self._validation_message()
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(not message)
        self.error_label.setText(message)
        self.error_label.setVisible(bool(message))

    def _validation_message(self) -> str:
        """Explain the first fix needed without closing or changing the staged record."""
        from app.history_files import (
            MAX_ENTRIES,
            MAX_MILEAGE_KM,
            entry_conflicts,
            mileage_conflicts,
            validate_project,
        )

        text = self.mileage_edit.text().strip()
        if not text.isdecimal():
            return "Enter mileage as whole kilometres, zero or greater (for example, 56000)."
        try:
            mileage = int(text)
        except (ValueError, OverflowError):
            mileage = MAX_MILEAGE_KM + 1
        if mileage > MAX_MILEAGE_KM:
            maximum = regional_locale().toString(MAX_MILEAGE_KM)
            return f"Enter mileage between 0 and {maximum} km."
        day = self.date_edit.date()
        if not day.isValid() or day > QDate.currentDate():
            return "Choose a valid service date that is today or earlier."
        if day.toString("yyyy-MM-dd") in self._existing_dates:
            return (
                "Another entry already uses this date. Choose a different date or edit that entry."
            )
        garage = self.dealer_edit.text()
        if not garage or len(garage) > 7 or not garage.isascii() or "\x00" in garage:
            return "Enter a garage name or code with 1–7 characters and no accents."
        if self.dealer_flag.currentData() not in (0, 1):
            return "Choose Independent / owner or BMW garage as the garage type."
        if self.status.currentData() not in RECORD_STATUS_LABELS:
            return "Choose a supported overall completion status."
        selected = [(item, status) for item, box, status in self.item_rows if box.isChecked()]
        if not 1 <= len(selected) <= 13:
            return "Select at least one service item, up to a maximum of 13."
        codes = {code for _, code in SERVICE_TYPES}
        if any(item["code"] not in codes for item, _ in selected):
            return "Remove unsupported service items before saving this entry."
        if any(status.currentData() not in ITEM_STATUS_LABELS for _, status in selected):
            return "Choose a supported completion status for each selected service item."
        if len(self._existing_entries) >= MAX_ENTRIES:
            return "This list supports up to 1,000 entries. Remove an entry before adding another."
        data = self.get_data()
        try:
            project = validate_project(
                {"schema_version": 1, "vin": None, "entries": [*self._existing_entries, data]}
            )
            if entry_conflicts({"schema_version": 1, "vin": None, "entries": [data]})[0]:
                return "Check the entry's date, garage, completion and selected service items."
        except (ValueError, OverflowError):
            return (
                "This entry exceeds the supported history limits. Correct its values and try again."
            )
        reference = mileage_conflicts(project["entries"])[-1]
        if reference is None:
            return ""
        locale = regional_locale()
        reference_date = locale.toString(
            QDate.fromString(reference["date"], "yyyy-MM-dd"), QLocale.FormatType.ShortFormat
        )
        reference_mileage = locale.toString(reference["mileage_km"])
        relation, direction = (
            ("later", "more") if data["date"] > reference["date"] else ("earlier", "less")
        )
        return (
            f"The entry on {reference_date} has {reference_mileage} km. For a {relation} date, "
            f"enter {direction} than {reference_mileage} km, or correct the service date."
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
    """In-memory staging, cleared on page exit, disconnect or environment change."""

    busy_changed = Signal(bool)
    mutation_active = Signal(bool)
    vehicle_loading_changed = Signal(bool)
    vehicle_loading_progress = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from app.history_workspace import new_workspace

        self._environment = LIVE
        self.workspace = new_workspace()
        self._connection: Any = None
        self._ecus: list[dict] = []
        self.can_mutate: Callable[[], bool] = lambda: False
        self._written_dates: set[date] = set()
        self._consumed_ids: set[str] = set()
        self._uncertain_operation = False
        self._write_results: list[dict[str, Any]] = []
        self._writing = False
        self._pending_confirmation: tuple[object, dict, str, object] | None = None
        self._worker: CarWorker | None = None
        self._key = uuid.uuid4().hex
        self._success: Callable[[object], None] | None = None
        self._page = 0
        self._shutting_down = False
        self._controls: list[QPushButton] = []
        self._setup_ui()
        self._render()
        self._set_busy(False)

    def clear_staging(self) -> None:
        """Discard temporary entries and invalidate callbacks without writing a file."""
        from app.history_workspace import new_workspace

        self.workspace = new_workspace()
        self._key = uuid.uuid4().hex
        self._pending_confirmation = None
        self._write_results.clear()
        self._page = 0
        self.message.clear()
        self._render()
        self._set_busy(self.is_busy())

    def hideEvent(self, event: QHideEvent) -> None:
        """Leaving the page discards its staging area without a save prompt."""
        if not event.spontaneous() and not self._writing:
            self.clear_staging()
        super().hideEvent(event)

    def _worker_current(self) -> bool:
        worker = self._worker
        return bool(
            self.sender() is worker
            and worker is not None
            and worker.property("environmentContext") == self._environment.binding()
            and worker.property("stageKey") == self._key
        )

    def _button(self, text: str, slot: Callable, *, danger: bool = False) -> QPushButton:
        button = DangerButton(text) if danger else QPushButton(text)
        button.clicked.connect(slot)
        self._controls.append(button)
        return button

    def _setup_ui(self) -> None:
        """Show explicit file actions and separate full-list and single-entry car writes."""
        self.setObjectName("historyPage")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        header = PageHeader(
            "Service history",
            "Temporary list. Nothing is saved or written until you choose an action. "
            "Leaving this page discards the list. Existing car history cannot be read.",
        )
        self.add_btn = self._button("+ Add entry", self._on_add_clicked)
        header.action_layout.addWidget(self.add_btn)
        layout.addWidget(header)
        actions = QHBoxLayout()
        for text, slot in (("Load from file", self._import), ("Write to file", self._export)):
            button = self._button(text, slot)
            button.setProperty("class", "secondary")
            actions.addWidget(button)
        actions.addStretch()
        self.replace_btn = self._button("Write to car", self._replace_history, danger=True)
        self.replace_btn.setToolTip(
            "Erase the existing car history and replace it with every entry in this list."
        )
        actions.addWidget(self.replace_btn)
        match_button_widths(
            action_widget
            for index in range(actions.count())
            if (item := actions.itemAt(index)) is not None
            and isinstance(action_widget := item.widget(), QPushButton)
        )
        layout.addLayout(actions)
        self.message = StatusLabel()
        layout.addWidget(self.message)
        self.entries_table = QFrame()
        self.entries_table.setObjectName("historyEntriesTable")
        table_layout = QVBoxLayout(self.entries_table)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)
        table_header = QFrame()
        table_header.setObjectName("historyTableHeader")
        heading = QHBoxLayout(table_header)
        heading.setContentsMargins(16, 12, 16, 12)
        heading.addWidget(caption("Entries to write", "featureTitle"))
        self.entry_count = caption("")
        heading.addWidget(self.entry_count, 1, Qt.AlignmentFlag.AlignRight)
        table_layout.addWidget(table_header)
        self.entry_container = QWidget()
        self.entry_container.setProperty("class", "transparent")
        self.entry_layout = QVBoxLayout(self.entry_container)
        self.entry_layout.setContentsMargins(0, 0, 0, 0)
        self.entry_layout.setSpacing(0)
        table_layout.addWidget(self.entry_container)
        layout.addWidget(self.entries_table)
        layout.addStretch()

    def _run(self, operation: Callable[[], object], success: Callable[[object], None]) -> None:
        if self._worker is not None or self._shutting_down:
            return
        self._start_worker(HistoryFileWorker(operation), success)

    def _start_worker(self, worker: CarWorker, success: Callable[[object], None]) -> None:
        self._success = success
        self._worker = worker
        worker.setProperty("environmentContext", self._environment.binding())
        worker.setProperty("stageKey", self._key)
        worker.result_ready.connect(self._result)
        worker.error.connect(self._error)
        worker.progress.connect(self.message.setText)
        worker.finished.connect(self._finished)
        self._set_busy(True)
        if self.is_using_vehicle():
            worker.progress.connect(self.vehicle_loading_progress)
            self.vehicle_loading_changed.emit(True)
        worker.start()

    def _set_busy(self, busy: bool) -> None:
        busy = busy or self._shutting_down
        for button in self._controls:
            button.setEnabled(not busy)
        self.entry_container.setEnabled(not busy)
        self.replace_btn.setEnabled(
            not busy and bool(self.workspace["project"]["entries"]) and self._can_offer_write()
        )
        self.busy_changed.emit(busy)

    @Slot(object)
    def _result(self, value: object) -> None:
        if self._worker_current() and self._success is not None:
            self._success(value)

    @Slot(str)
    def _error(self, message: str) -> None:
        if not self._worker_current():
            return
        self.message.setText(
            "File operation failed; the staged list is retained. Check the file and session log."
            if isinstance(self._worker, HistoryFileWorker)
            else "History operation could not complete. "
            + (getattr(self._worker, "guard_notice", "") or message)
            + " No automatic retry will occur."
        )

    @Slot()
    def _finished(self) -> None:
        worker = self.sender()
        if worker is not self._worker:
            return
        current = self._worker_current()
        self._worker = None
        self._success = None
        worker.deleteLater()
        was_writing = self._writing
        self._writing = False
        if was_writing:
            self.mutation_active.emit(False)
        if not isinstance(worker, HistoryFileWorker):
            self.vehicle_loading_changed.emit(False)
        if self._shutting_down:
            return
        if not current:
            self._pending_confirmation = None
        self._render()
        self._set_busy(False)
        if self._pending_confirmation is not None:
            pending = self._pending_confirmation
            self._pending_confirmation = None
            self._confirm_history(*pending)

    def _loaded(self, value: object) -> None:
        assert isinstance(value, dict)
        self._page = 0
        self.message.clear()
        self._stage(value)

    def is_busy(self) -> bool:
        """Whether this page still owns an active worker."""
        return self._worker is not None

    def is_using_vehicle(self) -> bool:
        """Whether history preparation or execution still owns the foreground."""
        return self._worker is not None and not isinstance(self._worker, HistoryFileWorker)

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

    def set_environment(self, current: SessionEnvironment) -> None:
        """Discard staging when switching between live and isolated DEMO sessions."""
        if self._environment != current:
            self._environment = current
            self._clear_session_guards()
            self.clear_staging()

    def _clear_session_guards(self) -> None:
        """Forget volatile write guards only when the connection or environment changes."""
        self._written_dates.clear()
        self._consumed_ids.clear()
        self._uncertain_operation = False

    def set_connection(self, connection: Any, ecus: list[dict] | None = None) -> None:
        """Update the target without loading or saving any service entries."""
        previous = self._connection
        if previous is not connection:
            self._ecus = []
            self._clear_session_guards()
        self._connection = connection
        if connection is not None:
            self.set_environment(environment(connection))
        if previous is not None and previous is not connection:
            self.clear_staging()
        if ecus is not None:
            self._ecus = [dict(row) for row in ecus]
        self._render()
        self._set_busy(self.is_busy())

    def _stage(self, workspace: dict, *, focus_id: str | None = None) -> None:
        """Apply an explicit edit in memory; only Write to file persists entries.

        Keep entries paired with their stable metadata when sorting by mileage.
        """
        self.workspace = copy.deepcopy(workspace)
        pairs = sorted(
            zip(self.workspace["project"]["entries"], self.workspace["records"], strict=True),
            key=lambda pair: pair[0]["mileage_km"],
            reverse=True,
        )
        self.workspace["project"]["entries"] = [entry for entry, _ in pairs]
        self.workspace["records"] = [record for _, record in pairs]
        if focus_id is not None:
            self._page = next(
                index // 25 for index, (_, record) in enumerate(pairs) if record["id"] == focus_id
            )
        self._render()
        self._set_busy(self.is_busy())

    def _render(self) -> None:
        from app.history_files import entry_conflicts

        project = self.workspace["project"]
        self._clear_layout(self.entry_layout)
        conflicts = entry_conflicts(project)
        labels = {code: text for text, code in SERVICE_TYPES}
        entries = project["entries"]
        pending = sum(not self._consumed(index) for index in range(len(entries)))
        total = f"{len(entries)} {'entry' if len(entries) == 1 else 'entries'}"
        self.entry_count.setText(f"{total} · {pending} not written")
        if not entries:
            empty = caption("No entries yet. Add a service entry to prepare it for writing.")
            empty.setObjectName("historyEmpty")
            self.entry_layout.addWidget(empty)
        self._page = min(self._page, max(0, (len(entries) - 1) // 25))
        for index in range(self._page * 25, min(len(entries), (self._page + 1) * 25)):
            entry = entries[index]
            card = QFrame()
            card.setObjectName("recordCard")
            state, state_text = self._record_status(index)
            if conflicts[index]:
                state, state_text = "conflict", "Needs attention"
            card.setProperty("class", "historyEntry")
            card.setProperty("writeState", state)
            box = QVBoxLayout(card)
            box.setContentsMargins(16, 10, 16, 10)
            box.setSpacing(8)
            meta = self.workspace["records"][index]
            day = QDate.fromString(entry["date"], "yyyy-MM-dd")
            locale = regional_locale()
            entry_header = QHBoxLayout()
            entry_header.setSpacing(8)
            entry_title = caption(
                f"{locale.toString(day, QLocale.FormatType.ShortFormat)} · "
                f"{locale.toString(entry['mileage_km'])} km",
                "technical",
            )
            entry_title.setObjectName("historyEntryTitle")
            entry_title.setWordWrap(False)
            entry_header.addWidget(entry_title)
            garage_type = {0: "Independent / owner", 1: "BMW garage"}.get(
                entry["dealer_flag"], f"Unknown garage flag {entry['dealer_flag']}"
            )
            garage = ElidedLabel(f"{entry['dealer']} · {garage_type}")
            garage.setObjectName("historyEntryGarage")
            entry_header.addWidget(garage, 1)
            badge = caption(state_text, "historyWriteState")
            badge.setProperty("writeState", state)
            badge.setWordWrap(False)
            entry_buttons = []
            for text, handler in (
                ("Edit", lambda _checked=False, i=index: self._edit(i)),
                ("Remove", lambda _checked=False, i=index: self._remove(i)),
            ):
                button = QPushButton(text)
                button.setProperty("class", "historyAction")
                button.clicked.connect(handler)
                entry_header.addWidget(button)
                entry_buttons.append(button)
            append = DangerButton("Write this entry")
            date_sent = date.fromisoformat(entry["date"]) in self._written_dates
            append.setToolTip(
                "This date was already sent in this session. Use Write to car for replacement."
                if date_sent
                else "Append only this entry, preserving existing car history."
            )
            append.setEnabled(
                self._can_offer_write()
                and not self._consumed(index)
                and not date_sent
                and not conflicts[index]
            )
            append.clicked.connect(
                lambda _checked=False, i=index: self._prepare_history("append", i)
            )
            entry_header.addWidget(append)
            entry_buttons.append(append)
            match_button_widths(entry_buttons)
            box.addLayout(entry_header)
            details = QGridLayout()
            details.setHorizontalSpacing(18)
            details.setVerticalSpacing(4)
            for column, title in enumerate(("Service item", "Completion")):
                details.addWidget(caption(title, "tableHeader"), 0, column)
            details.setColumnStretch(0, 1)
            for row, item in enumerate(entry["items"], 1):
                for column, value in enumerate(
                    (
                        labels.get(item["code"], f"Unknown service ID {item['code']}"),
                        _status_text(item["status"], ITEM_STATUS_LABELS),
                    )
                ):
                    label = _label(value)
                    if column:
                        label.setMinimumWidth(180)
                        label.setToolTip("Completion of this service item")
                    details.addWidget(label, row, column)
            box.addLayout(details)
            metadata = f"Overall: {_status_text(entry['status'], RECORD_STATUS_LABELS)}"
            if meta["origin"] == "imported":
                metadata += " · Imported entry"
            if conflicts[index]:
                box.addWidget(_label("Cannot write: " + "; ".join(conflicts[index])))
            if date_sent and not self._consumed(index):
                box.addWidget(
                    caption(
                        "This date was already sent in this session. Use Write to car to "
                        "replace history with the displayed list."
                    )
                )
            footer = QHBoxLayout()
            footer.setSpacing(8)
            footer.addWidget(caption(metadata, "historyMetadata"), 1)
            footer.addWidget(badge, 0, Qt.AlignmentFlag.AlignRight)
            box.addLayout(footer)
            self.entry_layout.addWidget(card)
        if len(entries) > 25:
            pagination = QHBoxLayout()
            for text, delta in (("Previous 25", -1), ("Next 25", 1)):
                button = QPushButton(text)
                button.setEnabled(0 <= self._page + delta <= (len(entries) - 1) // 25)
                button.clicked.connect(lambda _checked=False, step=delta: self._page_move(step))
                pagination.addWidget(button)
            self.entry_layout.addWidget(
                _label(
                    f"Page {self._page + 1} of {(len(entries) + 24) // 25}; highest mileage first"
                )
            )
            self.entry_layout.addLayout(pagination)

    @staticmethod
    def _clear_layout(layout: QVBoxLayout | QHBoxLayout | QGridLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
            elif isinstance(child_layout, (QVBoxLayout, QHBoxLayout, QGridLayout)):
                ServiceHistoryPage._clear_layout(child_layout)
                child_layout.deleteLater()

    def _page_move(self, step: int) -> None:
        self._page += step
        self._render()

    @Slot()
    def _on_add_clicked(self) -> None:
        self._edit(None)

    def _edit(self, index: int | None) -> None:
        if self._worker is not None:
            return
        import json

        from app.history_files import entry_conflicts, parse_project
        from app.history_workspace import new_record

        before, key = self.workspace, self._key
        entry = before["project"]["entries"][index] if index is not None else None
        dialog = AddServiceDialog(
            self,
            entry,
            existing_dates=[
                row["date"] for i, row in enumerate(before["project"]["entries"]) if i != index
            ],
            existing_entries=[
                row for i, row in enumerate(before["project"]["entries"]) if i != index
            ],
        )
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
            if data != entry:
                workspace["records"][index] = new_record("draft")
        try:
            parse_project(json.dumps(workspace["project"]).encode())
            problems = entry_conflicts(workspace["project"])[index if index is not None else -1]
            if problems:
                raise ValueError("; ".join(problems))
        except ValueError:
            self.message.setText(
                "The entry contains unsupported values. Remove unknown service types or correct its fields before adding this edit. The original is preserved."
            )
            return
        record_index = index if index is not None else len(entries) - 1
        self._stage(workspace, focus_id=workspace["records"][record_index]["id"])

    def _remove(self, index: int) -> None:
        if self.is_busy():
            return
        workspace = copy.deepcopy(self.workspace)
        del workspace["project"]["entries"][index]
        del workspace["records"][index]
        self._stage(workspace)

    @Slot()
    def _import(self) -> None:
        if self.is_busy():
            return
        from pathlib import Path

        from app.history_files import load_project
        from app.history_workspace import new_workspace

        before, key = self.workspace, self._key
        path, _ = QFileDialog.getOpenFileName(self, "Load from file", "", "JSON (*.json)")
        if not path or not self._context_current(before, key):
            return
        self._run(lambda: new_workspace(load_project(Path(path)), origin="imported"), self._loaded)

    @Slot()
    def _export(self) -> None:
        if self.is_busy():
            return
        from pathlib import Path

        from app.history_files import save_project

        before, key = self.workspace, self._key
        path, _ = QFileDialog.getSaveFileName(
            self, "Write to file", "history.json", "JSON (*.json)"
        )
        if path and self._context_current(before, key):
            project = copy.deepcopy(self.workspace["project"])
            self._run(
                lambda: save_project(Path(path), project),
                lambda _: self.message.setText("Entries written to file. The car is unchanged."),
            )

    def set_targets(self, ecus: list[dict]) -> None:
        """Update identified targets without reading the car or changing local records."""
        self._ecus = [dict(row) for row in ecus]
        if not self.is_busy():
            self._render()
            self._set_busy(False)

    def _can_offer_write(self) -> bool:
        from app.history_files import valid_vin
        from app.history_write import select_target
        from app.protocol.contracts import TransportKind

        connection = self._connection
        if (
            connection is None
            or getattr(connection, "read_only", True)
            or getattr(connection, "kind", None) != TransportKind.HSFZ
            or not getattr(connection, "alive_ok", False)
            or not valid_vin(getattr(connection, "verified_vin", ""))
            or environment(connection) != self._environment
            or getattr(connection, "power_sufficient", None) is False
        ):
            return False
        try:
            select_target(self._ecus)
        except (ValueError, OSError):
            return False
        return True

    def _known_dates(self) -> set[date]:
        return set(self._written_dates)

    def _consumed(self, index: int) -> bool:
        meta = self.workspace["records"][index]
        return (
            meta.get("write_state") in ("accepted", "uncertain") or meta["id"] in self._consumed_ids
        )

    def _record_status(self, index: int) -> tuple[str, str]:
        """Distinguish unsent entries, checked acceptance and uncertain vehicle outcomes."""
        meta = self.workspace["records"][index]
        if meta.get("write_state") == "accepted":
            return "accepted", (
                "Accepted in DEMO"
                if self._environment.mode == "demo"
                else "Accepted · check iDrive"
            )
        if self._consumed(index):
            return "uncertain", (
                "Outcome uncertain · DEMO"
                if self._environment.mode == "demo"
                else "Outcome uncertain · check iDrive"
            )
        if meta.get("write_state") == "rejected":
            return "rejected", "Rejected"
        if meta.get("write_state") == "unattempted":
            return "unattempted", "Not attempted"
        return "pending", "Not written"

    def interrupted_write_notice(self) -> str:
        """Expose an interrupted write outcome before a connection dialog can clear staging."""
        if not self._uncertain_operation:
            return ""
        from app.history_write import INSTRUCTIONS

        if self._write_results:
            return str(self._write_results[-1]["summary"])
        return "A previous history write was interrupted or incomplete. " + INSTRUCTIONS

    @Slot()
    def _replace_history(self) -> None:
        self._prepare_history("replace", None)

    def _prepare_history(self, mode: str, index: int | None) -> None:
        if mode == "append" and (
            index is None or not 0 <= index < len(self.workspace["project"]["entries"])
        ):
            self.message.setText(
                "The staged entry changed. Reopen the action for the current list."
            )
            return
        if (
            mode == "append"
            and index is not None
            and date.fromisoformat(self.workspace["project"]["entries"][index]["date"])
            in self._written_dates
        ):
            self.message.setText(
                "This date was already sent in this session. Use Write to car to replace "
                "history with the displayed list."
            )
            return
        if (
            self.is_busy()
            or not self._can_offer_write()
            or not self.can_mutate()
            or (mode == "append" and index is not None and self._consumed(index))
        ):
            self.message.setText(
                "Wait for the page to finish loading and check the connection. Writing requires "
                "a supported headunit and a writable connection."
            )
            return
        from app.history_write import HistoryPrepareWorker

        before, key, connection = self.workspace, self._key, self._connection
        worker = HistoryPrepareWorker(
            connection,
            self._ecus,
            before,
            mode,
            index,
            known_dates=self._known_dates(),
            consumed=set(self._consumed_ids),
        )

        def prepared(value: object) -> None:
            self._pending_confirmation = (value, before, key, connection)

        self._start_worker(worker, prepared)

    def _confirm_history(self, plan: object, before: dict, key: str, connection: object) -> None:
        from app.history_write import HistoryPlan, HistoryWriteWorker, file_vin_mismatch

        if (
            not isinstance(plan, HistoryPlan)
            or not self._context_current(before, key)
            or connection is not self._connection
            or not self._can_offer_write()
            or not self.can_mutate()
        ):
            return
        data = plan.data()
        dialog = CockpitDialog(
            "Confirm history append"
            if data["mode"] == "append"
            else "Confirm irreversible history replacement",
            self,
            width=720,
            height=680,
        )
        layout = dialog.body
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
        labels = {code: name for name, code in SERVICE_TYPES}
        preview = _label(
            "\n\n".join(
                f"{i + 1}. {entry['date']} · {entry['mileage_km']} km · {entry['dealer']} · {_status_text(entry['status'], RECORD_STATUS_LABELS)}\n"
                + ", ".join(
                    labels[item["code"]] + f" ({_status_text(item['status'], ITEM_STATUS_LABELS)})"
                    for item in entry["items"]
                )
                for i, entry in enumerate(data["intended"])
            )
        )
        layout.addWidget(preview)
        layout.addWidget(
            _label(
                "The headunit will be reset after accepted entries. Wait for it to restart and inspect iDrive. No readback, rollback or automatic retry is available. Once started there is no Cancel; navigation, disconnect and normal close are blocked."
            )
        )
        power = CheckInput(
            "I confirm ignition is on, the engine is off, and vehicle and computer power are adequate."
        )
        layout.addWidget(power)
        layout.addWidget(_label(data["write_conditions"]))
        file_vin = data["local_before"]["vin"]
        mismatch = file_vin_mismatch(data)
        if file_vin is not None:
            label = "Staged file VIN differs" if mismatch else "Staged file VIN"
            layout.addWidget(_label(f"{label}: {file_vin}"))
        vin_ack = CheckInput("I checked that these entries belong to the connected vehicle.")
        vin_ack.setVisible(mismatch)
        layout.addWidget(vin_ack)
        irreversible = CheckInput(
            "I accept irreversible loss of all car entries absent from this replacement list."
        )
        irreversible.setVisible(data["mode"] == "replace")
        layout.addWidget(irreversible)
        prior = CheckInput(
            "I inspected iDrive and the prior interrupted/uncertain operation before this new action."
        )
        needs_prior = self._uncertain_operation
        prior.setVisible(needs_prior)
        layout.addWidget(prior)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setText("Write this entry" if data["mode"] == "append" else "Erase and replace all")

        def valid() -> None:
            ok.setEnabled(
                power.isChecked()
                and (not mismatch or vin_ack.isChecked())
                and (data["mode"] != "replace" or irreversible.isChecked())
                and (not needs_prior or prior.isChecked())
            )

        for check in (power, vin_ack, irreversible, prior):
            check.toggled.connect(valid)
        valid()
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        dialog.add_buttons(buttons, destructive=True)
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
            power_acknowledged=power.isChecked(),
            replacement_acknowledged=irreversible.isChecked(),
            file_vin_acknowledged=vin_ack.isChecked(),
            ecus=self._ecus,
        )
        self._start_worker(worker, self._history_written)

    def _history_written(self, value: object) -> None:
        assert isinstance(value, dict)

        from app.history_write import HistoryWriteWorker

        worker = self.sender()
        assert isinstance(worker, HistoryWriteWorker)
        intent = worker.plan.data()
        latest = {
            event["step"]: event["state"] for event in value["events"] if event["step"] is not None
        }
        metadata = {record["id"]: record for record in self.workspace["records"]}
        if any(
            step["kind"] == "erase" and latest.get(index) == "accepted"
            for index, step in enumerate(intent["requests"])
        ):
            self._written_dates.clear()
            self._consumed_ids.clear()
            for record in metadata.values():
                record.pop("write_state", None)
        elif any(
            step["kind"] == "erase" and latest.get(index) in ("sending", "uncertain")
            for index, step in enumerate(intent["requests"])
        ):
            for record in metadata.values():
                if record.get("write_state") == "accepted":
                    record["write_state"] = "uncertain"
        for index, step in enumerate(intent["requests"]):
            state = latest.get(index)
            if step["kind"] != "add":
                continue
            entry_index = step["entry_index"]
            identity = intent["draft_ids"][entry_index]
            if state in ("accepted", "sending", "uncertain"):
                self._consumed_ids.add(identity)
                self._written_dates.add(date.fromisoformat(intent["intended"][entry_index]["date"]))
                if identity in metadata:
                    metadata[identity]["write_state"] = (
                        "accepted" if state == "accepted" else "uncertain"
                    )
            elif (
                state in ("rejected", "unattempted")
                and identity in metadata
                and metadata[identity].get("write_state") not in ("accepted", "uncertain")
            ):
                metadata[identity]["write_state"] = state
        if value["state"] != "blocked":
            self._uncertain_operation = value["state"] not in ("response-confirmed", "rejected")
        summary = self._write_summary(intent, value)
        self._write_results.append(
            {"intent": copy.deepcopy(intent), "report": copy.deepcopy(value), "summary": summary}
        )
        self.message.setText(summary)
        self._render()

    @staticmethod
    def _write_summary(intent: dict, report: dict) -> str:
        """Summarize the exact failed step and counts without repeating every accepted entry."""
        latest = {event["step"]: event for event in report["events"] if event["step"] is not None}
        counts: Counter[str] = Counter()
        lines = [f"History outcome: {report['state']}."]
        failures = []
        for index, request in enumerate(intent["requests"]):
            event = latest.get(index, {"state": "unattempted", "detail": ""})
            state = event["state"]
            label = request["kind"].capitalize()
            if request["kind"] == "add":
                counts[state] += 1
                label = "Entry " + intent["intended"][request["entry_index"]]["date"]
            elif request["kind"] in ("erase", "reset"):
                label = "Erase history" if request["kind"] == "erase" else "Headunit restart"
                detail = (
                    " " + event["detail"] if state in ("rejected", "uncertain", "sending") else ""
                )
                lines.append(f"{label}: {state}.{detail}")
            if request["kind"] not in ("erase", "reset") and state in (
                "rejected",
                "uncertain",
                "sending",
            ):
                failures.append(f"{label}: {state}. {event['detail']}".strip())
        if counts:
            lines.append(
                "Entries: " + ", ".join(f"{count} {state}" for state, count in counts.items()) + "."
            )
        return "\n".join([*lines, *failures, report["instructions"]])
