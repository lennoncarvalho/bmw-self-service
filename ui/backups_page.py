"""Backups page — list and rollback coding backups.

Shows backup snapshots from ~/BMW-Tool/backups/. Each shows date,
ECUs affected, change count. Rollback restores selected backup.

Reference: docs/16-ui-spec.md Screen 10
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class BackupsPage(QWidget):
    """Page listing coding backup snapshots with rollback capability."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._backups: list[dict] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        # Title
        title = QLabel("Coding Backups")
        title.setObjectName("titleLabel")
        title.setStyleSheet("font-size: 19px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title)

        # Location info
        backup_path = Path.home() / "BMW-Tool" / "backups"
        loc = QLabel(f"Backup location: {backup_path}")
        loc.setStyleSheet("font-size: 12px; color: #a0a0a0;")
        layout.addWidget(loc)

        # Scrollable backup list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setSpacing(8)
        self.list_layout.addStretch()
        scroll.setWidget(self.list_container)
        layout.addWidget(scroll, stretch=1)

        # Refresh button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(
            "QPushButton { background: #1C69D4; color: white; "
            "border-radius: 8px; padding: 8px 20px; "
            "font-size: 14px; font-weight: bold; }"
            "QPushButton:hover { background: #0653B6; }"
        )
        refresh_btn.clicked.connect(self.refresh)
        layout.addWidget(refresh_btn, alignment=Qt.AlignCenter)

    def set_connection(self, connection: Any) -> None:
        """Store connection for rollback writes (reserved for future use)."""
        self.refresh()

    def refresh(self) -> None:
        """Scan ~/BMW-Tool/backups/ and rebuild the list."""
        self._backups = self._scan_backups()
        self._render()

    @staticmethod
    def _scan_backups() -> list[dict]:
        """Enumerate backup directories with metadata."""
        backup_root = Path.home() / "BMW-Tool" / "backups"
        if not backup_root.is_dir():
            return []

        results: list[dict] = []
        for entry in sorted(backup_root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if not entry.is_dir():
                continue
            manifest_path = entry / "manifest.json"
            if not manifest_path.is_file():
                continue
            try:
                with open(manifest_path) as f:
                    manifest = json.load(f)
                results.append(
                    {
                        "path": str(entry),
                        "name": entry.name,
                        "timestamp": manifest.get("timestamp", ""),
                        "changes": manifest.get("changes", 0),
                        "categories": manifest.get("categories", []),
                    }
                )
            except (json.JSONDecodeError, OSError) as e:
                logger.debug("Skipping backup %s: %s", entry.name, e)
        return results

    def _render(self) -> None:
        """Rebuild backup cards from self._backups."""
        # Clear existing cards
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        if not self._backups:
            empty = QLabel(
                "No backups found.\n\nBackups are created automatically before each coding write."
            )
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("font-size: 14px; color: #a0a0a0; padding: 32px;")
            empty.setWordWrap(True)
            self.list_layout.insertWidget(self.list_layout.count() - 1, empty)
            return

        for backup in self._backups:
            name = backup.get("name", "")
            changes = backup.get("changes", 0)
            path = backup.get("path", "")

            card = QFrame()
            card.setObjectName("card")
            card.setStyleSheet(
                "QFrame#card { background: #16213e; border: 1px solid #2a2a4a; "
                "border-radius: 8px; padding: 12px; }"
                "QFrame#card:hover { border-color: #1C69D4; }"
            )

            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(4)

            top_row = QHBoxLayout()
            date_lbl = QLabel(name.replace("_", " "))
            date_lbl.setStyleSheet(
                "font-size: 14px; font-weight: bold; color: #e0e0e0; background: transparent;"
            )
            top_row.addWidget(date_lbl)
            top_row.addStretch()

            rollback_btn = QPushButton("Rollback")
            rollback_btn.setStyleSheet(
                "QPushButton { background: transparent; color: #F39C12; "
                "border: 1px solid #F39C12; border-radius: 6px; "
                "padding: 4px 16px; font-size: 12px; font-weight: bold; }"
                "QPushButton:hover { background: rgba(243,156,18,0.15); }"
            )
            rollback_btn.clicked.connect(lambda checked, p=path, n=name: self._on_rollback(p, n))
            top_row.addWidget(rollback_btn)
            card_layout.addLayout(top_row)

            info = QLabel(f"{changes} coding changes")
            info.setStyleSheet("font-size: 12px; color: #a0a0a0; background: transparent;")
            card_layout.addWidget(info)

            self.list_layout.insertWidget(self.list_layout.count() - 1, card)

    def _on_rollback(self, path: str, name: str) -> None:
        """Restore a backup to the coding page."""
        reply = QMessageBox.question(
            self,
            "Rollback Coding",
            f"Restore coding from backup '{name}'?\n\n"
            "This will overwrite all current coding values.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        manifest_path = os.path.join(path, "manifest.json")
        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
            # Find the CodingPage in the app and restore
            window = self.window()
            if window and hasattr(window, "coding_page"):
                window.coding_page.restore_backup(manifest.get("categories", []))
                QMessageBox.information(
                    self,
                    "Rollback Complete",
                    f"Restored coding from backup '{name}'.",
                )
        except (OSError, json.JSONDecodeError) as e:
            QMessageBox.warning(
                self,
                "Rollback Failed",
                f"Could not restore backup: {e}",
            )
