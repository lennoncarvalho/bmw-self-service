"""Easy Coding page with source presets and write review.

Reference: plan.md#coding-and-writes and docs.md#coding-contracts.
"""

import copy
import logging
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from threading import Event
from typing import Any

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from app.coding import CodingCatalogueWorker, CodingValuesWorker
from app.operation_store import OperationStore
from app.protocol.contracts import TransportKind
from app.worker import CarWorker
from ui.cockpit import CardSearch, CockpitCard, DangerButton, PageHeader, ResponsiveColumns, caption
from ui.dialogs import CockpitDialog
from ui.dialogs import MessageBox as QMessageBox
from ui.form_inputs import CheckInput
from ui.page_stack import PageStack

logger = logging.getLogger(__name__)


class CodingPage(QWidget):
    """Easy Coding options and the pending-changes bar."""

    mutation_active = Signal(bool)
    loading_changed = Signal(bool)
    loading_progress = Signal(str)
    verification_saved = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build coding previews with live writes and backup loading disabled until configured."""
        super().__init__(parent)
        self._connection: Any = None
        self._pending: int = 0
        self._worker: CarWorker | None = None
        self._coding_reader: CarWorker | None = None
        self._coding_writer: CarWorker | None = None
        self._sensitive_worker: CarWorker | None = None
        self._loading_worker: CarWorker | None = None
        self._live_unavailable = True
        self._snapshot_workers: list[CarWorker] = []
        self._snapshot_ecus: list[dict] = []
        self._snapshot_model_range = ""
        self._snapshot_type_code = ""
        self._snapshot_loaded = False
        self._live_selections: dict[tuple[int, str, str, int], str] = {}
        self._source_rows: list[dict] = []
        self._open_sections: set[str] = set()
        self._section_reads: list[str] = []
        self._pending_plan: Any = None
        self._write_report: dict = {}
        self.can_mutate: Callable[[], bool] = lambda: True
        self._sub_stack: PageStack
        self._setup_ui()
        self._evidence_export_btn = QPushButton("Export retained coding results")
        self._evidence_export_btn.clicked.connect(self._export_coding_report)
        self._evidence_export_btn.setVisible(False)
        page_layout = self.layout()
        assert isinstance(page_layout, QVBoxLayout)
        page_layout.addWidget(self._evidence_export_btn)
        page_layout.addStretch()
        self._write_btn.setEnabled(False)

    def _setup_ui(self) -> None:
        """Build the coding page, pending controls and the mutation action bar."""
        self.setObjectName("codingPage")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(
            PageHeader(
                "Car customization",
                "Review observed values and select supported changes for your vehicle.",
            )
        )

        # Sub-page stack
        self._sub_stack = PageStack(content_height=True)
        self.search = CardSearch(self._sub_stack, "Search sections or loaded features")
        content = QWidget()
        content.setProperty("class", "transparent")
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 0, 0, 0)
        body.addWidget(self.search)
        self._sub_stack.addWidget(caption("Connect to read supported coding options."))
        body.addWidget(self._sub_stack)

        review = CockpitCard("Changes to apply")
        self._pending_label = caption("No changes selected", "sectionTitle")
        review.box.addWidget(self._pending_label)
        review.box.addWidget(
            caption(
                "Choose options in a section. Current values stay selected until you change them."
            )
        )
        self._selection_summary = caption("")
        review.box.addWidget(self._selection_summary)
        review.box.addWidget(caption("PREPARATION CHECKS", "eyebrow"))
        review.box.addWidget(
            caption(
                "Vehicle identity, current software, original data and power "
                "are checked during the guarded review."
            )
        )
        review.box.addWidget(
            caption(
                "Original data is saved before a live write. Restoration requires a new review."
            )
        )

        # Bottom bar (visible when pending > 0)
        self._bottom_bar = QFrame()
        self._bottom_bar.setProperty("class", "reviewActions")
        self._bottom_bar.setVisible(False)
        bar_layout = QVBoxLayout(self._bottom_bar)
        bar_layout.setContentsMargins(0, 8, 0, 0)
        clear_btn = QPushButton("Discard selected changes")
        clear_btn.setProperty("class", "secondary")
        clear_btn.clicked.connect(self._on_clear)
        bar_layout.addWidget(clear_btn)
        self._write_btn = DangerButton("Review coding changes")
        self._write_btn.clicked.connect(self._on_write)
        bar_layout.addWidget(self._write_btn)
        review.box.addWidget(self._bottom_bar)
        layout.addWidget(ResponsiveColumns(content, review))

    def set_connection(
        self,
        connection: Any,
        ecus: list[dict] | None = None,
        *,
        model_range: str = "",
        type_code: str = "",
    ) -> None:
        """Store the active connection for future coding operations.

        Args:
            connection: An identified diagnostic connection.
            ecus: Optional SVT ECU list from vehicle connection.
            model_range: Model code from the connected vehicle order, when available.
            type_code: Exact type key from the connected vehicle order, when available.
        """
        if (
            connection is self._connection
            and (ecus or []) == self._snapshot_ecus
            and model_range == self._snapshot_model_range
            and type_code == self._snapshot_type_code
        ):
            return
        self._connection = connection
        self._live_selections.clear()
        self._source_rows = []
        self._open_sections.clear()
        self._section_reads.clear()
        self._pending_plan = None
        self._live_unavailable = True
        self._pending = 0
        self._update_pending_label()
        self._write_btn.setEnabled(False)
        self._write_btn.setText("Review coding changes")
        while self._sub_stack.count():
            old_page = self._sub_stack.widget(0)
            if old_page is None:
                break
            self._sub_stack.removeWidget(old_page)
            old_page.deleteLater()

        page = QWidget()
        layout = QVBoxLayout(page)
        message = QLabel("Identifying available Easy Coding options...")
        message.setWordWrap(True)
        layout.addWidget(message)
        layout.addStretch()
        self._sub_stack.addWidget(page)
        self._snapshot_ecus = copy.deepcopy(ecus or [])
        self._snapshot_model_range = model_range
        self._snapshot_type_code = type_code
        self._snapshot_loaded = False

    def activate(self) -> None:
        """Identify catalogues on first visit without reading coding values."""
        connection = self._connection
        if (
            connection is None
            or not getattr(connection, "alive_ok", True)
            or self._snapshot_loaded
            or self._coding_reader is not None
            or self.is_reading()
        ):
            return
        vin = getattr(connection, "verified_vin", "")
        if not vin:
            return
        worker = CodingCatalogueWorker(
            connection,
            self._snapshot_ecus,
            vin,
            model_range=self._snapshot_model_range,
            type_code=self._snapshot_type_code,
        )
        self._coding_reader = worker
        self._snapshot_workers.append(worker)
        worker.result_ready.connect(self._on_snapshot)
        worker.error.connect(self._on_snapshot_error)
        worker.finished.connect(self._on_snapshot_finished)
        self._start_loading(worker, "Identifying available coding options...")
        worker.start()

    def _toggle_source_section(self, section: str) -> None:
        """Open a section and queue owners whose current values still need a read."""
        connection = self._connection
        if (
            connection is None
            or not getattr(connection, "alive_ok", False)
            or self._coding_reader is not None
            or not self.can_mutate()
        ):
            return
        if section in self._open_sections:
            self._open_sections.remove(section)
            self._show_source_rows(self._source_rows, preserve_selections=True)
            return
        self._open_sections.add(section)
        self._section_reads = [
            row["addr"]
            for row in self._source_rows
            if section in row.get("sections", {})
            and row.get("available")
            and (not row.get("loaded") or row.get("partial"))
        ]
        if not self._read_next_section_owner():
            logger.debug("Opening cached coding section %s", section)
            self._show_source_rows(self._source_rows, preserve_selections=True)

    def _read_next_section_owner(self) -> bool:
        """Start one queued owner, leaving the loading backdrop active between reads."""
        connection = self._connection
        if (
            connection is None
            or not self._section_reads
            or not getattr(connection, "alive_ok", False)
        ):
            self._section_reads.clear()
            return False
        address = self._section_reads.pop(0)
        matches = [row for row in self._source_rows if row.get("addr") == address]
        if len(matches) != 1 or not matches[0].get("available"):
            self._section_reads.clear()
            return False
        row = matches[0]
        worker = CodingValuesWorker(connection, row, connection.verified_vin)
        worker.setProperty("coding_values_addr", address)
        self._coding_reader = worker
        self._snapshot_workers.append(worker)
        worker.sensitive_operation_requested.connect(self._begin_sensitive_read)
        worker.result_ready.connect(self._on_snapshot)
        worker.error.connect(self._on_snapshot_error)
        worker.finished.connect(self._on_snapshot_finished)
        self._start_loading(worker, f"Reading coding values: {row['name']}...")
        worker.start()
        return True

    def is_reading(self) -> bool:
        """Whether an owned coding snapshot read is still running."""
        return any(
            worker is not None and worker.isRunning()
            for worker in (self._coding_reader, self._worker, self._coding_writer)
        )

    def has_unexported_results(self) -> bool:
        """Whether coding outcomes exist only in retained memory."""
        return bool(
            self._write_report.get("persistence_failed")
            and not self._write_report.get("evidence_exported")
        )

    @Slot(str)
    def _on_snapshot_error(self, message: str) -> None:
        """Show a settled unavailable result for a failed snapshot worker."""
        worker = self.sender()
        if isinstance(worker, CarWorker) and worker.property("coding_values_addr"):
            address = worker.property("coding_values_addr")
            self._on_snapshot(
                [
                    {**row, "state": message, "loaded": False, "presets": [], "blocks": {}}
                    for row in self._source_rows
                    if row.get("addr") == address
                ]
            )
            return
        self._on_snapshot(
            [{"name": "Coding", "state": message, "definitions": [], "blocks": {}, "backup": ""}]
        )

    @Slot()
    def _on_snapshot_finished(self) -> None:
        """Release the finished snapshot and its sensitive-session lockout."""
        worker = self.sender()
        current = worker is self._coding_reader
        if worker is self._coding_reader:
            self._coding_reader = None
        if isinstance(worker, CarWorker):
            self._release_source_worker(worker)
            if (
                current
                and worker.connection is self._connection
                and self._read_next_section_owner()
            ):
                return
            self._finish_loading(worker)
            if current and worker.connection is self._connection:
                self._write_btn.setEnabled(
                    bool(self._live_selections)
                    and getattr(self._connection, "alive_ok", False)
                    and not self.is_reading()
                )

    def _start_loading(self, worker: CarWorker, message: str) -> None:
        """Block foreground controls before starting a coding read or preparation."""
        self._loading_worker = worker
        worker.progress.connect(self._on_loading_progress)
        self.loading_changed.emit(True)
        self.loading_progress.emit(message)

    def _finish_loading(self, worker: CarWorker) -> None:
        """Release the backdrop only for the worker that acquired it."""
        if worker is self._loading_worker:
            self._loading_worker = None
            self.loading_changed.emit(False)

    @Slot(str)
    def _on_loading_progress(self, message: str) -> None:
        """Publish current foreground progress without accepting stale workers."""
        worker = self.sender()
        if worker is self._loading_worker and worker.connection is self._connection:
            self._pending_label.setText(message)
            self.loading_progress.emit(message)

    @Slot(object)
    def _begin_sensitive_read(self, permission: object) -> None:
        """Lock disruptive GUI actions before a source-required session transition."""
        worker = self.sender()
        if (
            not isinstance(permission, Event)
            or not isinstance(worker, CarWorker)
            or worker not in self._snapshot_workers
            or worker.connection is not self._connection
            or worker.isInterruptionRequested()
        ):
            return
        if self._sensitive_worker is None:
            self._sensitive_worker = worker
            self.mutation_active.emit(True)
        if self._sensitive_worker is worker:
            permission.set()

    @Slot(object)
    def _on_snapshot(self, rows: list[dict]) -> None:
        """Publish exact source-backed current values after the entire batch settles."""
        worker = self.sender()
        if (
            not isinstance(worker, CarWorker)
            or worker is not self._coding_reader
            or worker.connection is not self._connection
        ):
            return
        self._snapshot_loaded = True
        address = worker.property("coding_values_addr")
        if address:
            matches = [row for row in rows if row.get("addr") == address]
            if len(matches) == 1:
                self._show_source_rows(
                    [
                        matches[0] if row.get("addr") == address else row
                        for row in self._source_rows
                    ],
                    preserve_selections=True,
                )
        else:
            self._show_source_rows(rows)

    def _show_source_rows(self, rows: list[dict], *, preserve_selections: bool = False) -> None:
        """Render source-backed values and selections without vehicle I/O."""
        self._source_rows = copy.deepcopy(rows)
        selections = dict(self._live_selections) if preserve_selections else {}
        self._live_selections.clear()
        self._pending = 0
        self._update_pending_label()
        self._live_unavailable = False
        self._write_btn.setText("Review coding changes")
        self._write_btn.setEnabled(False)
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        sections: dict[str, str] = {}
        for row in rows:
            sections.update(row.get("sections", {}))
        if not sections:
            layout.addWidget(QLabel("No Easy Coding sections available. See session log."))

        can_edit = (
            getattr(self._connection, "alive_ok", False)
            and not getattr(self._connection, "read_only", True)
            and getattr(self._connection, "kind", None) == TransportKind.HSFZ
        )
        for section, label in sorted(sections.items(), key=lambda entry: entry[1].casefold()):
            card = QFrame()
            card.setObjectName("recordCard")
            entries = QVBoxLayout(card)
            opened = section in self._open_sections
            toggle = QPushButton(f"{'▾' if opened else '▸'}  {label}")
            toggle.setObjectName("codingSection")
            toggle.setAccessibleName(f"{'Collapse' if opened else 'Expand'} {label}")
            toggle.clicked.connect(
                lambda checked=False, key=section: self._toggle_source_section(key)
            )
            entries.addWidget(toggle)
            presets: list[tuple[dict, dict]] = []
            for row in rows:
                if section not in row.get("sections", {}):
                    continue
                if opened and (not row.get("loaded") or row.get("partial")):
                    status = QLabel(row.get("state", "Current values unavailable"))
                    status.setWordWrap(True)
                    status.setEnabled(False)
                    entries.addWidget(status)
                presets.extend(
                    (row, preset)
                    for preset in row.get("presets", [])
                    if preset["section"] == section
                )
            card.setProperty(
                "searchText", label + " " + " ".join(preset["label"] for _, preset in presets)
            )
            repeated = Counter(preset["label"] for _, preset in presets)
            for row, preset in presets:
                key = (
                    preset["address"],
                    preset["definition"],
                    preset["id"],
                    preset["source_index"],
                )
                mapped = preset.get("mapping_supported", False)
                enabled = bool(
                    can_edit
                    and row.get("available")
                    and row.get("loaded")
                    and mapped
                    and not preset.get("write_block")
                )
                selected = selections.get(key, preset["current"])
                choices = preset.get("choices", [])
                if (
                    enabled
                    and selected != preset["current"]
                    and any(
                        option["name"] == selected and option.get("available", True)
                        for option in choices
                    )
                ):
                    self._live_selections[key] = selected
                else:
                    selected = preset["current"]
                if not opened:
                    continue
                feature = preset["label"]
                if repeated[feature] > 1:
                    feature = f"{feature} ({row.get('description') or row['name']})"
                self._add_source_feature(entries, feature, preset, key, selected, enabled)
            layout.addWidget(card)
        layout.addStretch()
        old = self._sub_stack.widget(0)
        if old is not None:
            self._sub_stack.removeWidget(old)
            old.deleteLater()
        self._sub_stack.insertWidget(0, page)
        self._sub_stack.setCurrentIndex(0)
        self.search.apply()
        self._pending = len(self._live_selections)
        self._update_pending_label()
        self._write_btn.setEnabled(bool(self._pending) and not self.is_reading())

    def _add_source_feature(
        self,
        layout: QVBoxLayout,
        label: str,
        preset: dict,
        key: tuple[int, str, str, int],
        selected: str | None,
        enabled: bool,
    ) -> None:
        """Show the observed or staged option and allow restoring the observed value."""
        feature = QWidget()
        feature.setObjectName("codingFeature")
        options = QVBoxLayout(feature)
        options.setContentsMargins(12, 4, 0, 4)
        heading = caption(label, "featureTitle")
        heading.setTextFormat(Qt.TextFormat.PlainText)
        heading.setWordWrap(True)
        options.addWidget(heading)
        if not preset.get("mapping_supported", False):
            options.addWidget(QLabel("Current value unavailable"))
            feature.setEnabled(False)
        else:
            current = preset["current"]
            group = QButtonGroup(feature)
            choices = [
                (option["name"], option["label"], option.get("available", True))
                for option in preset["choices"]
            ]
            if current is None:
                choices.insert(0, (None, "Custom (current)", True))
            for name, text, available in choices:
                button = QRadioButton(text)
                group.addButton(button)
                button.setChecked(name == selected)
                button.setEnabled(enabled and available)
                if not available:
                    button.setToolTip("Unavailable with this control unit's coding layout")
                button.clicked.connect(
                    lambda checked, value=name, identity=key, observed=current: (
                        self._select_source_option(identity, value, observed) if checked else None
                    )
                )
                options.addWidget(button)
            if blocked := preset.get("write_block"):
                notice = QLabel(blocked)
                notice.setWordWrap(True)
                options.addWidget(notice)
        layout.addWidget(feature)

    def _update_pending_label(self) -> None:
        """Show staged source options while preserving the existing review controls."""
        selected = []
        for row in self._source_rows:
            for preset in row.get("presets", []):
                key = (
                    preset["address"],
                    preset["definition"],
                    preset["id"],
                    preset["source_index"],
                )
                if key in self._live_selections:
                    value = self._live_selections[key]
                    label = next(
                        (
                            option["label"]
                            for option in preset["choices"]
                            if option["name"] == value
                        ),
                        value,
                    )
                    selected.append(f"{preset['label']} · {label}")
        self._selection_summary.setText("\n\n".join(selected))
        self.search.apply()
        self._pending_label.setText(
            f"{self._pending} changes pending" if self._pending else "No changes selected"
        )
        self._bottom_bar.setVisible(self._pending > 0)

    def _on_clear(self) -> None:
        """Discard pending selections without changing observed vehicle values."""
        if not self.is_reading():
            self._show_source_rows(self._source_rows)

    def _on_write(self) -> None:
        """Prepare selected changes through the shared guarded coding workflow."""
        self._prepare_source_write()

    def _select_source_option(
        self, identity: tuple[int, str, str, int], selected: Any, current: Any
    ) -> None:
        """Retain stable source option identities, preserving untouched Custom values."""
        if selected is None or selected == current:
            self._live_selections.pop(identity, None)
        else:
            self._live_selections[identity] = str(selected)
        self._pending = len(self._live_selections)
        self._update_pending_label()
        self._write_btn.setEnabled(bool(self._pending) and not self.is_reading())

    def _prepare_source_write(self, restore_path: Path | None = None) -> str | None:
        """Start preparation, or return a visible reason why it cannot begin."""
        from app.coding_write import CodingPrepareWorker

        connection = self._connection
        reason = ""
        if connection is None or not getattr(connection, "alive_ok", False):
            reason = "Connect to the vehicle before preparing coding or restoration."
        elif getattr(connection, "read_only", True):
            reason = "Coding and restoration are unavailable in a read-only connection."
        elif getattr(connection, "kind", None) != TransportKind.HSFZ:
            reason = "Coding and restoration are unavailable over this transport."
        elif self.is_reading():
            reason = "Wait for the current coding read or preparation to finish, then retry."
        elif not self.can_mutate():
            reason = "Wait for the current vehicle operation to finish, then retry."
        elif self.has_unexported_results():
            reason = "Export the retained coding results before preparing another operation."
        elif not self._live_selections and restore_path is None:
            reason = "Select a coding change before preparing an operation."
        elif restore_path is None:
            eligible = {
                (
                    preset["address"],
                    preset["definition"],
                    preset["id"],
                    preset["source_index"],
                ): {
                    option["name"]
                    for option in preset["choices"]
                    if option["name"] != preset["current"] and option.get("available", True)
                }
                for row in self._source_rows
                if row.get("available") and row.get("loaded")
                for preset in row.get("presets", [])
                if preset.get("mapping_supported") and not preset.get("write_block")
            }
            if any(
                option not in eligible.get(key, ()) for key, option in self._live_selections.items()
            ):
                reason = (
                    "A selected coding option is unavailable. Review the current options again."
                )
        if reason:
            self._pending_label.setText(reason)
            return reason
        changes = [
            {
                "address": address,
                "definition": definition,
                "preset": preset,
                "preset_index": source_index,
                "option": option,
            }
            for (address, definition, preset, source_index), option in self._live_selections.items()
        ]
        worker = CodingPrepareWorker(
            connection, self._snapshot_ecus, changes, restore_path=restore_path
        )
        self._worker = worker
        self._snapshot_workers.append(worker)
        self._pending_plan = None
        self._write_btn.setEnabled(False)
        self._pending_label.setText("Reading and checking the coding plan...")
        sensitive = getattr(worker, "sensitive_operation_requested", None)
        if sensitive is not None:
            sensitive.connect(self._begin_sensitive_read)
        worker.result_ready.connect(self._source_plan_ready)
        worker.error.connect(self._source_error)
        worker.finished.connect(self._source_prepare_finished)
        self._start_loading(worker, "Reading and checking the coding plan...")
        worker.start()
        return None

    @Slot(object)
    def _source_plan_ready(self, plan: Any) -> None:
        """Retain a plan only from the current preparation worker."""
        worker = self.sender()
        if worker is self._worker and worker.connection is self._connection:
            self._pending_plan = plan

    @Slot()
    def _source_prepare_finished(self) -> None:
        """Release preparation before presenting the retained confirmation plan."""
        worker = self.sender()
        if not isinstance(worker, CarWorker):
            return
        current = worker is self._worker and worker.connection is self._connection
        if worker is self._worker:
            self._worker = None
        self._release_source_worker(worker)
        self._finish_loading(worker)
        error = worker.property("preparation_error")
        if current and isinstance(error, str) and error:
            QMessageBox.warning(self, "Coding preparation unavailable", error)
            if worker.connection is not self._connection:
                return
        if current and self._pending_plan is not None:
            plan, self._pending_plan = self._pending_plan, None
            self._confirm_source_plan(plan, worker.connection)
        elif current:
            self._write_btn.setEnabled(bool(self._live_selections))
        if current and self._coding_writer is None:
            # A first visit through Backups may have deferred the snapshot.
            # Retry only after preparation/review settles, never beside a write.
            self.activate()

    def _confirm_source_plan(self, plan: Any, connection: Any) -> None:
        """Show a concrete frozen plan and mandatory power acknowledgement."""
        from app.coding_write import CodingWriteWorker

        if connection is not self._connection or not self.can_mutate():
            self._pending_label.setText("Wait for the other operation, then review coding again.")
            self._write_btn.setEnabled(bool(self._live_selections))
            return
        data = plan.data()
        dialog = CockpitDialog(
            "Restore coding" if data["mode"] == "restore" else "Review coding",
            self,
            width=720,
            height=680,
        )
        layout = dialog.body
        message = QLabel(
            f"VIN: {data['vin']}\n"
            "Complete original coding will be saved before writing. "
            "The app will change coding, write the vehicle stamp, restart affected ECUs "
            "and clear their diagnostic faults. Keep power and the cable connected. "
            "You cannot cancel once writing starts."
        )
        message.setWordWrap(True)
        layout.addWidget(message)
        preview = QPlainTextEdit()
        preview.setReadOnly(True)
        lines = []
        for target in data["targets"]:
            changed = [
                did
                for did in target["baseline"]
                if target["baseline"][did] != target["intended"][did]
            ]
            lines.append(f"{target['name']} · {len(changed)} changed group(s)")
        if data["mode"] == "restore":
            origin = data.get("restore_origin", {}).get("original", {})
            lines.append(f"Original snapshot: {origin.get('created', 'Selected backup')}")
            lines.append("Replace the listed ECU coding with that snapshot's original values.")
        for change in data.get("changes", []):
            if "preset" not in change:
                continue
            matches = [
                preset
                for row in self._source_rows
                for preset in row.get("presets", [])
                if preset["address"] == change["address"]
                and preset["definition"] == change["definition"]
                and preset["id"] == change["preset"]
                and preset["source_index"] == change["preset_index"]
            ]
            if len(matches) == 1:
                preset = matches[0]
                target_label = next(
                    (
                        choice["label"]
                        for choice in preset.get("choices", [])
                        if choice["name"] == change["option"]
                    ),
                    change["option"],
                )
                lines.append(f"{preset['label']}: set to {target_label}")
            else:
                lines.append(f"{change['preset']}: {change['option']}")
        preview.setPlainText("\n".join(lines))
        layout.addWidget(preview)
        power = CheckInput(
            "I confirm adequate vehicle and computer power throughout this operation."
        )
        layout.addWidget(power)
        prior = data.get("prior_operations", [])
        recovery = CheckInput(
            "I have completed any required vehicle cycle and reviewed the prior interrupted "
            "operation against the fresh readings. This is a new operation, not a replay."
        )
        recovery.setVisible(bool(prior))
        layout.addWidget(recovery)
        if prior:
            comparison_labels = {
                "matches-both": "matches saved original and intended bytes",
                "matches-original": "matches saved original bytes",
                "matches-intended": "matches saved intended bytes",
                "differs": "differs from both original and intended bytes",
                "identity-changed": "ECU identity/software changed",
                "definition-changed": "Source coding definition changed",
            }
            prior_lines = ["Prior operations require review:"]
            for record in prior:
                prior_lines.append(
                    f"{record.get('id', 'Operation')}: {record.get('state', 'unresolved')}"
                )
                for target in record.get("targets", []):
                    comparison = target.get("comparison", "not-read")
                    prior_lines.append(
                        f"ECU 0x{target['address']:02X}: "
                        + comparison_labels.get(comparison, "current state was not read")
                    )
            prior_lines.append(
                "A match before its required cycle does not establish application or failure."
            )
            prior_notice = QPlainTextEdit()
            prior_notice.setReadOnly(True)
            prior_notice.setPlainText("\n".join(prior_lines))
            layout.addWidget(prior_notice)
        restore = CheckInput("Replace current coding with the reviewed backup values.")
        restore.setVisible(data["mode"] == "restore")
        layout.addWidget(restore)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        accept = buttons.button(QDialogButtonBox.StandardButton.Ok)
        accept.setText("Restore" if data["mode"] == "restore" else "Write coding")
        accept.setEnabled(False)

        def refresh() -> None:
            """Enable confirmation only after every applicable acknowledgement."""
            accept.setEnabled(
                power.isChecked()
                and (data["mode"] != "restore" or restore.isChecked())
                and (not prior or recovery.isChecked())
            )

        power.toggled.connect(refresh)
        restore.toggled.connect(refresh)
        recovery.toggled.connect(refresh)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        dialog.add_buttons(buttons, destructive=True)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self._pending_label.setText("Coding review cancelled; no write was started.")
            self._write_btn.setEnabled(bool(self._live_selections))
            return
        if (
            connection is not self._connection
            or not connection.alive_ok
            or not self.can_mutate()
            or self.is_reading()
            or data["vin"] != getattr(connection, "verified_vin", None)
            or not power.isChecked()
            or (data["mode"] == "restore" and not restore.isChecked())
            or (prior and not recovery.isChecked())
        ):
            self._pending_label.setText(
                "Vehicle state changed or another operation is running; review coding again."
            )
            self._write_btn.setEnabled(bool(self._live_selections) and not self.is_reading())
            return
        self.mutation_active.emit(True)
        worker = CodingWriteWorker(
            connection,
            plan,
            power_acknowledged=True,
            recovery_acknowledged=recovery.isChecked(),
        )
        self._coding_writer = worker
        self._snapshot_workers.append(worker)
        self._write_btn.setEnabled(False)
        worker.progress.connect(self._pending_label.setText)
        worker.result_ready.connect(self._source_written)
        worker.error.connect(self._source_error)
        worker.finished.connect(self._source_write_finished)
        worker.start()

    @Slot(object)
    def _source_written(self, report: dict) -> None:
        """Retain the current writer outcome and expose unsaved evidence."""
        worker = self.sender()
        if worker is not self._coding_writer or worker.connection is not self._connection:
            return
        self._write_report = copy.deepcopy(report)
        self._snapshot_loaded = False
        self._live_selections.clear()
        self._pending = 0
        for row in self._source_rows:
            row.update(
                loaded=False,
                blocks={},
                presets=[],
                state="Current values need to be read again after the coding operation",
            )
        self._show_source_rows(self._source_rows)
        self._pending_label.setText(f"Coding: {report.get('state', 'unknown')}")
        logger.info(
            "Coding values cache invalidated conn=%s outcome=%s",
            getattr(self._connection, "trace_id", "unknown"),
            report.get("state", "unknown"),
        )
        message = f"Outcome: {report.get('state', 'unknown')}\n{report.get('instructions', '')}"
        if report.get("path"):
            message += f"\nRecord: {report['path']}"
        if report.get("persistence_failed"):
            message += "\nSome results remain in memory. Export them before closing."
            self._evidence_export_btn.setVisible(True)
        QMessageBox.information(self, "Coding result", message)

    @Slot(str)
    def _source_error(self, message: str) -> None:
        """Display a current worker failure while preserving any result evidence."""
        worker = self.sender()
        if not isinstance(worker, CarWorker) or worker.connection is not self._connection:
            return
        message = getattr(worker, "guard_notice", "") or message
        report = getattr(worker, "report", None)
        if isinstance(report, dict):
            self._write_report = copy.deepcopy(report)
            self._evidence_export_btn.setVisible(bool(report.get("persistence_failed")))
        self._pending_label.setText(message)
        if worker is self._loading_worker:
            worker.setProperty("preparation_error", message)
            self.loading_progress.emit(message)
            return
        QMessageBox.warning(self, "Coding unavailable", message)

    @Slot()
    def _source_write_finished(self) -> None:
        """Unlock after thread completion and refresh safely persisted results."""
        worker = self.sender()
        if not isinstance(worker, CarWorker):
            return
        current = worker is self._coding_writer and worker.connection is self._connection
        if worker is self._coding_writer:
            self._coding_writer = None
            self.mutation_active.emit(False)
        self._release_source_worker(worker)
        if current and not self._write_report.get("persistence_failed"):
            self._snapshot_loaded = False
            self.activate()

    def _release_source_worker(self, worker: CarWorker) -> None:
        """Release page ownership and any sensitive-session lock for a worker."""
        if self._sensitive_worker is worker:
            self._sensitive_worker = None
            self.mutation_active.emit(False)
        if worker in self._snapshot_workers:
            self._snapshot_workers.remove(worker)
        if not worker.property("retired_by_main"):
            worker.deleteLater()

    def restore_vehicle_backup(self, path: Path) -> str | None:
        """Prepare an explicit restore or explain its rejection; never write on selection."""
        return self._prepare_source_write(restore_path=path)

    def verify_vehicle_backup(self, path: Path, store: OperationStore) -> str | None:
        """Confirm completion of any required cycle, then start a coding comparison."""
        from app.coding_write import CodingVerificationWorker

        connection = self._connection
        if not getattr(connection, "verified_vin", "") or not getattr(
            connection, "alive_ok", False
        ):
            return "Connect to the vehicle from this backup before verifying."
        if getattr(connection, "kind", None) != TransportKind.HSFZ:
            return "Coding verification requires a supported ENET connection."
        if self.is_reading() or not self.can_mutate():
            return "Wait for the current vehicle operation to finish."
        if self.has_unexported_results():
            return "Export the retained coding results before verifying another operation."
        reply = QMessageBox.question(
            self,
            "Verify coding",
            "Have you completed any required vehicle cycle for this operation? "
            "Verification compares current bytes with the backup. A headunit may require a "
            "temporary reader session. Keep the vehicle powered and the cable connected.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if (
            reply != QMessageBox.StandardButton.Yes
            or connection is not self._connection
            or not getattr(connection, "alive_ok", False)
            or self.is_reading()
            or not self.can_mutate()
        ):
            return None
        worker = CodingVerificationWorker(connection, path, store, cycle_acknowledged=True)
        self._worker = worker
        self._snapshot_workers.append(worker)
        worker.sensitive_operation_requested.connect(self._begin_sensitive_read)
        worker.result_ready.connect(self._verification_ready)
        worker.error.connect(self._source_error)
        worker.finished.connect(self._verification_finished)
        self._start_loading(worker, "Reading saved coding targets...")
        worker.start()
        return None

    @Slot(object)
    def _verification_ready(self, report: dict) -> None:
        """Retain the comparison from the current worker and preserve unsaved evidence."""
        worker = self.sender()
        if report.get("persistence_failed"):
            self._write_report = report
            self._evidence_export_btn.setVisible(True)
        if worker is self._worker and worker.connection is self._connection:
            worker.setProperty("coding_verification", report)

    @Slot()
    def _verification_finished(self) -> None:
        """Present results only after the comparison worker and reader lockout end."""
        worker = self.sender()
        if not isinstance(worker, CarWorker):
            return
        current = worker is self._worker and worker.connection is self._connection
        if worker is self._worker:
            self._worker = None
        report = worker.property("coding_verification")
        error = worker.property("preparation_error")
        self._release_source_worker(worker)
        self._finish_loading(worker)
        if not current:
            return
        if not isinstance(report, dict):
            QMessageBox.warning(
                self, "Coding verification unavailable", error or "Verification stopped."
            )
            return
        if report.get("persistence_failed"):
            suffix = (
                "\nThe comparison could not be saved. Export retained results on the Coding page."
            )
        else:
            suffix = ""
            self.verification_saved.emit()
        QMessageBox.information(self, "Coding verification", report["instructions"] + suffix)

    def _export_coding_report(self) -> None:
        """Publish retained interruption evidence off the GUI thread."""
        if self.is_reading() or not self._write_report:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export coding results", "coding-results.json", "JSON (*.json)"
        )
        if not filename or self.is_reading():
            return
        worker = CodingEvidenceExportWorker(self._connection, Path(filename), self._write_report)
        self._worker = worker
        self._snapshot_workers.append(worker)
        worker.result_ready.connect(self._source_evidence_exported)
        worker.error.connect(self._source_error)
        worker.finished.connect(self._source_evidence_finished)
        worker.start()

    @Slot(object)
    def _source_evidence_exported(self, path: object) -> None:
        """Mark the originating report without changing a newer session's report."""
        worker = self.sender()
        if not isinstance(worker, CodingEvidenceExportWorker):
            return
        report = worker.originating_report
        report["evidence_exported"] = True
        if self._write_report is report:
            self._pending_label.setText("Coding evidence exported; reread before a new operation.")

    @Slot()
    def _source_evidence_finished(self) -> None:
        """Release the export worker and refresh after durable publication."""
        worker = self.sender()
        if not isinstance(worker, CarWorker):
            return
        current = worker is self._worker
        if current:
            self._worker = None
        self._release_source_worker(worker)
        if current and self._write_report.get("evidence_exported"):
            self._snapshot_loaded = False
            self.activate()


class CodingEvidenceExportWorker(CarWorker):
    """Publish local evidence using the page's bounded worker lifecycle."""

    def __init__(self, connection: Any, path: Path, report: dict) -> None:
        """Retain a detached result report and its requested export destination."""
        super().__init__(connection)
        self.path = path
        # GUI-only identity reference; background publication uses its detached
        # copy below. Disconnect may clear the page's current worker reference.
        self.originating_report = report
        self.report = copy.deepcopy(report)

    def do_work(self) -> str:
        """Save a non-restorable result file without vehicle I/O."""
        from app.operation_store import export_interruption_evidence

        export_interruption_evidence(self.path, self.report)
        return str(self.path)
