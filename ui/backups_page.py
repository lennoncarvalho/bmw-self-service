"""Ordinary portable backups with integrity checks and explicit owner deletion."""

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.operation_store import OperationStore, coding_comparison_basis, load_record
from app.session import LIVE, SessionEnvironment, environment
from ui.cockpit import CardSearch, CockpitCard, DangerButton, PageHeader, caption
from ui.dialogs import MessageBox as QMessageBox

logger = logging.getLogger(__name__)


class BackupsPage(QWidget):
    """Preview/import/export records; restoring needs an exact vehicle contract."""

    restore_requested = Signal(object)
    verification_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the expanding backup record list and local file actions."""
        super().__init__(parent)
        self.store = OperationStore()
        self._environment = LIVE
        self.setObjectName("backupsPage")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        header = PageHeader(
            "Coding backups & restoration",
            "Inspect saved original data and review a supported restoration.",
        )
        for label, handler in (("Import JSON backup", self._import), ("Refresh", self.refresh)):
            button = QPushButton(label)
            button.setProperty("class", "secondary")
            button.clicked.connect(handler)
            header.action_layout.addWidget(button)
        layout.addWidget(header)
        note = CockpitCard("Saved originals & operation outcomes")
        note.box.addWidget(
            caption(
                "Records contain complete original and intended data with integrity checks. "
                "A restoration requires fresh vehicle, software and definition checks."
            )
        )
        note.box.addWidget(
            caption("Portable unencrypted JSON · Retained until you delete it", "supporting")
        )
        layout.addWidget(note)
        self.record_count = caption("", "supportingStrong")
        layout.addWidget(self.record_count)
        location = caption(f"Backup location: {self.store.root}")
        self._location = location
        location.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(location)
        container = QWidget()
        container.setProperty("class", "transparent")
        self.list_layout = QVBoxLayout(container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(16)
        self.list_layout.addStretch()
        self.search = CardSearch(container, "Search VIN, control unit or operation state")
        layout.addWidget(self.search)
        layout.addWidget(container)

    def set_connection(self, connection: Any) -> None:
        """Refresh local files; importing and viewing never send vehicle requests."""
        if connection is not None:
            self.set_environment(environment(connection))
        else:
            self.refresh()

    def set_environment(self, current: SessionEnvironment) -> None:
        """Browse only records from the explicitly selected session environment."""
        self._environment = current
        self.store = OperationStore(current.root / "backups" / "operations", mode=current.mode)
        self._location.setText(f"Backup location: {self.store.root}")
        self.refresh()

    def refresh(self) -> None:
        """List validated records, explicit corruption states and legacy limitations."""
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            if item is not None and (widget := item.widget()) is not None:
                widget.hide()
                widget.deleteLater()
        paths = sorted(self.store.root.glob("*.json"), key=lambda path: path.name)
        self.record_count.setText(f"{len(paths)} LOCAL RECORD FILES")
        if not paths:
            empty = CockpitCard("No saved vehicle backups")
            empty.box.addWidget(
                caption(
                    "Original data and operation outcomes appear here after coding preparation. "
                    "You can also import a portable JSON record."
                )
            )
            self.list_layout.insertWidget(0, empty)
        for path in paths:
            card = QFrame()
            card.setObjectName("recordCard")
            box = QVBoxLayout(card)
            box.setSpacing(12)
            try:
                record = load_record(path)
                original = record["original"]
                status = record["events"][-1]
                title = QLabel(f"{original['kind'].title()} backup · {original['mode'].upper()}")
                title.setWordWrap(True)
                title.setProperty("role", "sectionTitle")
                title.setTextFormat(Qt.TextFormat.PlainText)
                box.addWidget(title)
                box.addWidget(caption(f"Saved original · {original['created']}"))
                state_text = {
                    "response-confirmed": "Response confirmed · Verification pending",
                    "cycle-required": "Vehicle cycle required · Verification pending",
                    "verified": "Observed verification recorded",
                    "uncertain": "Outcome uncertain · Inspect operation",
                    "mismatch": "Verification mismatch",
                }.get(status["state"], status["state"].capitalize())
                state = caption(state_text, "badge")
                state.setProperty("state", status["state"])
                box.addWidget(state)
                identity = QLabel(
                    f"VIN: {original['vin']}\n{len(original['targets'])} ECU target(s)\nState: {status['state']}"
                )
                identity.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                identity.setWordWrap(True)
                identity.setTextFormat(Qt.TextFormat.PlainText)
                identity.setProperty("role", "technical")
                box.addWidget(identity)
                card.setProperty(
                    "searchText",
                    " ".join(
                        f"{target['variant']} 0x{target['address']:02X} {target['software']}"
                        for target in original["targets"]
                    ),
                )
                self._add_comparison(box, path, record["original_sha256"])
                if status["instructions"]:
                    instructions = QLabel(status["instructions"])
                    instructions.setWordWrap(True)
                    box.addWidget(instructions)
                box.addWidget(
                    caption(
                        "Restoration requires a supported operation and matching vehicle/software identity."
                    )
                )
                if original["kind"] == "coding" and original["mode"] == self._environment.mode:
                    restore = DangerButton("Review coding restoration")
                    restore.clicked.connect(
                        lambda checked=False, source=path: self.restore_requested.emit(source)
                    )
                    box.addWidget(restore)
                    basis = coding_comparison_basis(record)
                    if basis is not None:
                        verify = QPushButton(
                            "Compare interrupted coding"
                            if basis == "both"
                            else "Verify coding after vehicle cycle"
                        )
                        verify.clicked.connect(
                            lambda checked=False, source=path: self.verification_requested.emit(
                                source
                            )
                        )
                        box.addWidget(verify)
                export = QPushButton("Export JSON")
                export.setProperty("class", "secondary")
                export.clicked.connect(lambda checked=False, source=path: self._export(source))
                box.addWidget(export)
            except (OSError, ValueError):
                logger.warning("Backup cannot be validated: %s", path, exc_info=True)
                box.addWidget(
                    caption(
                        f"Unreadable or corrupt backup: {path.name}\nKept on disk; recovery eligibility unavailable."
                    )
                )
            delete = DangerButton("Delete backup")
            delete.clicked.connect(lambda checked=False, source=path: self._delete(source))
            box.addWidget(delete)
            self.list_layout.insertWidget(self.list_layout.count() - 1, card)
        legacy = self.store.root.parent
        if legacy.exists() and any(legacy.glob("*/manifest.json")):
            notice = QLabel(
                "Legacy metadata previews remain in the backup folder. They contain no complete vehicle bytes and cannot restore a car."
            )
            notice.setWordWrap(True)
            self.list_layout.insertWidget(self.list_layout.count() - 1, notice)
        self.search.apply()

    @staticmethod
    def _add_comparison(layout: QVBoxLayout, source: Path, original_hash: str) -> None:
        """Load bounded comparison widgets only when the saved record is expanded."""
        detail = QWidget()
        detail.setProperty("class", "comparison")
        box = QVBoxLayout(detail)
        box.setContentsMargins(12, 12, 12, 12)
        detail.hide()

        def reveal(visible: bool) -> None:
            """Revalidate the local original before displaying its byte preview."""
            if visible and box.count() == 0:
                try:
                    record = load_record(source)
                    if record["original_sha256"] != original_hash:
                        raise ValueError("Saved original changed")
                except (OSError, ValueError):
                    box.addWidget(
                        caption("Comparison unavailable. Refresh to check the saved record again.")
                    )
                else:
                    BackupsPage._populate_comparison(box, record["original"])
            detail.setVisible(visible)

        toggle = QPushButton("Show original / intended block comparison")
        toggle.setProperty("class", "disclosure")
        toggle.setCheckable(True)
        toggle.toggled.connect(reveal)
        layout.addWidget(toggle)
        layout.addWidget(detail)

    @staticmethod
    def _populate_comparison(box: QVBoxLayout, original: dict) -> None:
        """Show bounded original/intended previews with complete JSON export available."""
        for target in original["targets"][:25]:
            title = caption(
                f"{target['variant']} · 0x{target['address']:02X} · {target['software']}",
                "technical",
            )
            box.addWidget(title)
            grid = QGridLayout()
            grid.setColumnStretch(1, 1)
            grid.setColumnStretch(2, 1)
            for column, text in enumerate(("BLOCK", "ORIGINAL BYTES", "INTENDED BYTES")):
                grid.addWidget(caption(text, "tableHeader"), 0, column)
            blocks = list(target["baseline"])
            for row, block in enumerate(blocks[:25], 1):
                grid.addWidget(caption(block, "technical"), row, 0)
                for column, field in ((1, "baseline"), (2, "intended")):
                    value = target[field][block]
                    preview = " ".join(
                        value[index : index + 8] for index in range(0, min(64, len(value)), 8)
                    )
                    preview += "…" if len(value) > 64 else ""
                    label = caption(f"{preview}  ({len(value) // 2} bytes)", "technical")
                    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                    grid.addWidget(label, row, column)
            box.addLayout(grid)
            box.addWidget(
                caption(
                    "Preview shows up to 25 blocks and 32 bytes per value. "
                    "Export JSON for complete original and intended data."
                )
            )
            definition = caption("Definition SHA-256 · " + target["definition_sha256"], "technical")
            definition.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            box.addWidget(definition)
        if len(original["targets"]) > 25:
            box.addWidget(
                caption("Showing the first 25 targets. Export JSON for the complete saved record.")
            )

    def _import(self) -> None:
        source, _ = QFileDialog.getOpenFileName(self, "Import backup", "", "JSON files (*.json)")
        if not source:
            return
        try:
            self.store.import_record(Path(source))
        except (OSError, ValueError):
            logger.warning("Import failed", exc_info=True)
            QMessageBox.warning(
                self,
                "Import unavailable",
                "The file could not be imported. Check its schema, integrity and file permissions.",
            )
        self.refresh()

    def _export(self, source: Path) -> None:
        destination, _ = QFileDialog.getSaveFileName(
            self, "Export backup", source.name, "JSON files (*.json)"
        )
        if not destination:
            return
        try:
            self.store.export_record(source, Path(destination))
        except (OSError, ValueError):
            logger.warning("Export failed", exc_info=True)
            QMessageBox.warning(
                self,
                "Export unavailable",
                "The file could not be exported. Check backup integrity, free disk space and permissions.",
            )

    def _delete(self, source: Path) -> None:
        reply = QMessageBox.question(
            self,
            "Delete backup",
            "Permanently delete this local backup? You will lose its recovery information, including any unresolved operation state.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
            destructive=True,
            action_text="Delete backup",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            source.unlink()
        except OSError:
            logger.warning("Backup deletion failed", exc_info=True)
            QMessageBox.warning(
                self,
                "Delete unavailable",
                "The backup could not be deleted. Check file permissions.",
            )
        self.refresh()
