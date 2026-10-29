"""Ordinary portable backups with integrity checks and explicit owner deletion."""

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.operation_store import OperationStore, load_record

logger = logging.getLogger(__name__)


class BackupsPage(QWidget):
    """Preview/import/export records; restoring needs an exact vehicle contract."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store = OperationStore()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addWidget(QLabel("Vehicle Backups"))
        location = QLabel(f"Backup location: {self.store.root}")
        location.setWordWrap(True)
        layout.addWidget(location)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self.list_layout = QVBoxLayout(container)
        self.list_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)
        actions = QHBoxLayout()
        for label, handler in (("Import JSON backup", self._import), ("Refresh", self.refresh)):
            button = QPushButton(label)
            button.clicked.connect(handler)
            actions.addWidget(button)
        layout.addLayout(actions)

    def set_connection(self, connection: Any) -> None:
        """Refresh local files; importing and viewing never send vehicle requests."""
        self.refresh()

    def refresh(self) -> None:
        """List validated records, explicit corruption states and legacy limitations."""
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            if item is not None and (widget := item.widget()) is not None:
                widget.deleteLater()
        paths = sorted(self.store.root.glob("*.json"), key=lambda path: path.name)
        if not paths:
            self.list_layout.insertWidget(0, QLabel("No vehicle backup records found."))
        for path in paths:
            card = QFrame()
            box = QVBoxLayout(card)
            try:
                record = load_record(path)
                original = record["original"]
                status = record["events"][-1]
                title = QLabel(
                    f"{original['created']} — {original['kind']} — {original['mode'].upper()}"
                )
                title.setWordWrap(True)
                box.addWidget(title)
                identity = QLabel(
                    f"VIN: {original['vin']}\n{len(original['targets'])} ECU target(s)\nState: {status['state']}"
                )
                identity.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                box.addWidget(identity)
                if status["instructions"]:
                    instructions = QLabel(status["instructions"])
                    instructions.setWordWrap(True)
                    box.addWidget(instructions)
                box.addWidget(
                    QLabel(
                        "Restoration requires a supported operation and matching vehicle/software identity."
                    )
                )
                export = QPushButton("Export JSON")
                export.clicked.connect(lambda checked=False, source=path: self._export(source))
                box.addWidget(export)
            except (OSError, ValueError):
                logger.warning("Backup cannot be validated: %s", path, exc_info=True)
                box.addWidget(
                    QLabel(
                        f"Unreadable or corrupt backup: {path.name}\nKept on disk; recovery eligibility unavailable."
                    )
                )
            delete = QPushButton("Delete backup")
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
