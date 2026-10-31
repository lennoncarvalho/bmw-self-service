"""Learn-coding-option section of the coding page (D-66, Phase 1, read-only).

The owner captures one ECU before and after applying a single option with their
own coding tool; the bit-level difference is saved as an owner-labelled preset.
All vehicle I/O runs in CodingCaptureWorker, owned by the coding page.
"""

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
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

from app.coding_learn import (
    CaptureStore,
    PresetStore,
    applicability,
    describe_change,
    diff_captures,
)

logger = logging.getLogger(__name__)

APPLY_PENDING = (
    "Applying presets will be enabled after the coding write procedure is verified. "
    "This section only reads the vehicle."
)
INTRO = (
    "Learn a coding option from your own car: capture the selected ECU, apply ONE option "
    "with your coding app, then capture again. The exact bit changes are saved as your "
    "own labelled preset for this ECU and coding version. Each capture scans data "
    "identifiers 3000–3FFF and can take a few minutes."
)
AFTER_BEFORE = (
    "Before-capture saved. Next:\n"
    "1. Disconnect this app (gear menu → Disconnect). Only one tool may use the car.\n"
    "2. Connect your coding app and apply exactly ONE option on {name}. Change nothing else.\n"
    "3. Close your coding app, reconnect this app, open Coding and press 'Capture after'.\n"
    "The before-capture is stored on disk and survives the reconnect."
)


def _label(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


class CodingLearnPanel(QWidget):
    """Collapsible capture → diff → label → save workflow plus the learned-preset list."""

    capture_requested = Signal(object, str)
    stop_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        captures: CaptureStore | None = None,
        presets: PresetStore | None = None,
    ) -> None:
        super().__init__(parent)
        self.captures = captures or CaptureStore()
        self.presets = presets or PresetStore()
        self._vin = ""
        self._live = False
        self._busy = False
        self._ecus: list[dict[str, Any]] = []
        self._pending: tuple[Path, Path] | None = None
        self._has_before = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 8, 24, 0)
        self.toggle_button = QPushButton("Show: Learn coding option")
        self.toggle_button.setCheckable(True)
        self.toggle_button.toggled.connect(self._toggle)
        layout.addWidget(self.toggle_button)

        self.body = QScrollArea()
        self.body.setWidgetResizable(True)
        self.body.setMaximumHeight(460)
        content = QWidget()
        column = QVBoxLayout(content)
        column.addWidget(_label(INTRO))
        notice = _label(APPLY_PENDING)
        notice.setStyleSheet("color: #F39C12;")
        column.addWidget(notice)

        row = QHBoxLayout()
        row.addWidget(QLabel("ECU:"))
        self.ecu_combo = QComboBox()
        self.ecu_combo.currentIndexChanged.connect(lambda _index: self._refresh_state())
        row.addWidget(self.ecu_combo, 1)
        self.before_button = QPushButton("Capture before")
        self.before_button.clicked.connect(lambda: self._request("before"))
        row.addWidget(self.before_button)
        self.after_button = QPushButton("Capture after")
        self.after_button.clicked.connect(lambda: self._request("after"))
        row.addWidget(self.after_button)
        self.stop_button = QPushButton("Stop capture")
        self.stop_button.clicked.connect(self.stop_requested)
        row.addWidget(self.stop_button)
        column.addLayout(row)

        self.status_label = _label()
        column.addWidget(self.status_label)
        self.diff_label = _label()
        self.diff_label.setStyleSheet("font-family: Menlo, Consolas, monospace;")
        column.addWidget(self.diff_label)

        save_row = QHBoxLayout()
        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("Preset label, e.g. 'Mirror fold on lock'")
        self.label_edit.setMaxLength(120)
        save_row.addWidget(self.label_edit, 2)
        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("Notes (optional)")
        self.notes_edit.setMaxLength(1000)
        save_row.addWidget(self.notes_edit, 2)
        self.save_button = QPushButton("Save preset")
        self.save_button.clicked.connect(self._save)
        save_row.addWidget(self.save_button)
        column.addLayout(save_row)

        column.addWidget(QLabel("Learned presets for this car"))
        self.preset_rows = QVBoxLayout()
        column.addLayout(self.preset_rows)
        column.addStretch()
        self.body.setWidget(content)
        layout.addWidget(self.body)
        self._toggle(False)
        self.set_context("", [], live=False)

    # ---- public API ----

    def set_context(self, vin: str, ecus: list[dict[str, Any]], *, live: bool) -> None:
        """Bind the connected car; only exactly identified UDS ECUs can be captured."""
        self._vin = vin
        self._live = live
        self._busy = False
        self._ecus = [dict(e) for e in ecus if e.get("identified") is True and e.get("uds") is True]
        self.ecu_combo.blockSignals(True)
        self.ecu_combo.clear()
        for ecu in self._ecus:
            self.ecu_combo.addItem(f"{ecu.get('name', 'ECU')} ({ecu['addr']})")
        self.ecu_combo.blockSignals(False)
        self._refresh_state()

    def set_busy(self, busy: bool, text: str = "") -> None:
        """Reflect a running capture (or another blocking page worker)."""
        self._busy = busy
        if text:
            self.status_label.setText(text)
        self._update_buttons()

    def capture_finished(self, result: dict[str, Any]) -> None:
        """Show one persisted capture; an after-capture is diffed against its before."""
        capture = result["capture"]
        name = capture["ecu"]["name"]
        if not capture["complete"]:
            self._refresh_state()
            self.status_label.setText(
                f"Capture of {name} is incomplete ({capture['incomplete_reason']}). It was "
                f"saved for reference but cannot be used for a preset. Capture again.\n"
                f"File: {result['path']}"
            )
            return
        self._refresh_state()
        if capture["role"] == "before":
            self.status_label.setText(
                f"{len(capture['blocks'])} coding data identifiers captured in "
                f"{capture['duration_s']:.0f} s.\n" + AFTER_BEFORE.format(name=name)
            )

    def capture_failed(self, message: str) -> None:
        """Report a capture that could not start or produce data."""
        self._refresh_state()
        self.status_label.setText(f"Capture failed: {message}")

    # ---- internals ----

    def _toggle(self, visible: bool) -> None:
        self.body.setVisible(visible)
        self.toggle_button.setText(
            "Hide: Learn coding option" if visible else "Show: Learn coding option"
        )

    def _selected(self) -> dict[str, Any] | None:
        index = self.ecu_combo.currentIndex()
        return self._ecus[index] if 0 <= index < len(self._ecus) else None

    def _identity(self, ecu: dict[str, Any]) -> tuple[int, str]:
        return int(str(ecu["addr"]), 0), str(ecu.get("variant", ""))

    def _request(self, role: str) -> None:
        ecu = self._selected()
        if ecu is not None and not self._busy and self._live:
            self.capture_requested.emit(ecu, role)

    def _update_buttons(self) -> None:
        ecu = self._selected()
        ready = self._live and ecu is not None and not self._busy
        self.before_button.setEnabled(ready)
        self.after_button.setEnabled(ready and self._has_before)
        self.stop_button.setEnabled(self._busy)
        self.ecu_combo.setEnabled(not self._busy)
        self.save_button.setEnabled(self._pending is not None and not self._busy)

    def _refresh_state(self) -> None:
        """Recompute the before/after pair from disk so the flow survives reconnects."""
        self._pending = None
        self._has_before = False
        self.diff_label.setText("")
        ecu = self._selected()
        if not self._live:
            self.status_label.setText("Learning needs a live, identified vehicle connection.")
        elif ecu is None:
            self.status_label.setText("No exactly identified ECU is available for capture.")
        else:
            address, variant = self._identity(ecu)
            before = self.captures.latest(self._vin, address, variant, "before")
            after = self.captures.latest(self._vin, address, variant, "after")
            self._has_before = before is not None
            if before is None:
                self.status_label.setText("Step 1: press 'Capture before'.")
            elif after is None or after[1]["finished"] < before[1]["finished"]:
                self.status_label.setText(
                    f"Before-capture from {before[1]['finished'][:19]} is ready. "
                    "Apply ONE option with your coding app (this app disconnected), "
                    "then reconnect and press 'Capture after'."
                )
            else:
                self._show_diff(before, after)
        self._reload_presets()
        self._update_buttons()

    def _show_diff(self, before: tuple[Path, dict], after: tuple[Path, dict]) -> None:
        try:
            changes = diff_captures(before[1], after[1])
        except ValueError as exc:
            self.status_label.setText(f"These captures cannot form a preset: {exc}")
            return
        if not changes:
            self.status_label.setText(
                "No coding difference between the latest before- and after-capture. "
                "Apply the option with your coding app and capture after again."
            )
            return
        saved = any(p["after"]["path"] == str(after[0]) for p in self._safe_presets(self._vin))
        lines = [describe_change(change) for change in changes]
        self.diff_label.setText("\n".join(lines))
        if saved:
            self.status_label.setText("This difference is already saved as a preset.")
            return
        self.status_label.setText(
            f"{len(changes)} changed byte(s) found. Enter a label and save the preset."
            + (
                "\nMore than one byte changed: confirm only ONE option was applied."
                if len(changes) > 1
                else ""
            )
        )
        self._pending = (before[0], after[0])

    def _save(self) -> None:
        if self._pending is None:
            return
        try:
            preset = self.presets.add(
                self.label_edit.text(), *self._pending, notes=self.notes_edit.text()
            )
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Preset Not Saved", str(exc))
            return
        self.label_edit.clear()
        self.notes_edit.clear()
        self._refresh_state()
        self.status_label.setText(f"Preset '{preset['label']}' saved.")

    def _safe_presets(self, vin: str) -> list[dict[str, Any]]:
        try:
            return self.presets.presets(vin)
        except (OSError, ValueError):
            logger.warning("Preset database unreadable", exc_info=True)
            return []

    def _reload_presets(self) -> None:
        while self.preset_rows.count():
            item = self.preset_rows.takeAt(0)
            child = item.widget() if item is not None else None
            if child is not None:
                child.hide()
                child.deleteLater()
        if not self._vin:
            self.preset_rows.addWidget(_label("Connect a vehicle to see its learned presets."))
            return
        try:
            presets = self.presets.presets(self._vin)
        except (OSError, ValueError) as exc:
            self.preset_rows.addWidget(_label(f"Preset database unavailable: {exc}"))
            return
        if not presets:
            self.preset_rows.addWidget(_label("No presets learned on this car yet."))
        for preset in presets:
            ecu = preset["ecu"]
            latest = self.captures.newest(self._vin, ecu["address"], ecu["variant"])
            frame = QFrame()
            frame.setObjectName("card")
            row = QHBoxLayout(frame)
            text = (
                f"{preset['label']} — {ecu['name']} (0x{ecu['address']:02X}, "
                f"variant {ecu['variant']})\n"
                f"{applicability(preset, latest)}\n"
                f"Coding definition: {', '.join(preset['cafd'])} · "
                f"{len(preset['changes'])} change(s) · learned {preset['created'][:19]}\n"
                + "\n".join(describe_change(c) for c in preset["changes"])
                + (f"\nNotes: {preset['notes']}" if preset.get("notes") else "")
            )
            row.addWidget(_label(text), 1)
            delete = QPushButton("Delete")
            delete.clicked.connect(lambda _=False, chosen=preset: self._delete(chosen))
            row.addWidget(delete, 0, Qt.AlignmentFlag.AlignTop)
            self.preset_rows.addWidget(frame)

    def _delete(self, preset: dict[str, Any]) -> None:
        answer = QMessageBox.question(
            self,
            "Delete Preset",
            f"Delete preset '{preset['label']}'? Its capture files are kept.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.presets.delete(preset["id"])
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Preset Not Deleted", str(exc))
        self._refresh_state()
