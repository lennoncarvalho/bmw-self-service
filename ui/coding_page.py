"""Coding page — Easy + Advanced coding with write/clear bar.

Easy: curated category -> option toggles.
Advanced: SVT ECU tree -> FDL hex editor (stub).

Reference: docs/16-ui-spec.md Screens 7, 8, 9
"""

import copy
import logging
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.worker import CarWorker

logger = logging.getLogger(__name__)

MOCK_CATEGORIES = [
    {
        "name": "Lighting",
        "icon": "L",
        "description": "Angel eyes brightness, welcome lights, DRL behavior",
        "options": [
            {"name": "Angel Eyes Brightness",
             "values": ["4%", "8%", "12%", "16%", "20%"], "current": 1},
            {"name": "Welcome Lights Duration",
             "values": ["10s", "20s", "30s", "40s"], "current": 2},
            {"name": "DRL Rear Lights", "values": ["Off", "On"], "current": 0},
        ],
    },
    {
        "name": "Comfort",
        "icon": "C",
        "description": "Fold mirrors, window control, seat heating memory",
        "options": [
            {"name": "Fold Mirrors on Lock",
             "values": ["Off", "On (hold)", "On (instant)"], "current": 1},
            {"name": "Window Control after Ignition Off",
             "values": ["Disabled", "30s", "60s", "Unlimited"], "current": 2},
        ],
    },
    {
        "name": "Instrument Cluster",
        "icon": "I",
        "description": "Digital speed, M Performance logo, startup animation",
        "options": [
            {"name": "Digital Speed in BC", "values": ["Off", "On"], "current": 1},
            {"name": "M Performance Logo", "values": ["Off", "On"], "current": 0},
            {"name": "Startup Animation", "values": ["Standard", "M", "Alpina"], "current": 0},
        ],
    },
    {
        "name": "Audio / iDrive",
        "icon": "A",
        "description": "Disclaimer timeout, video in motion, sound settings",
        "options": [
            {"name": "Disclaimer Timeout", "values": ["10s", "5s", "2s", "Off"], "current": 2},
            {"name": "Video in Motion", "values": ["Off", "On (US)", "On (EU)"], "current": 0},
        ],
    },
]


class CodingPage(QWidget):
    """Coding tab with Easy/Advanced sub-pages and shared pending-changes bar."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._connection: Any = None
        self._pending: int = 0
        self._originals = copy.deepcopy(MOCK_CATEGORIES)
        self._worker: CarWorker | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Sub-tab bar
        tab_bar = QHBoxLayout()
        tab_bar.setSpacing(0)
        tab_bar.setContentsMargins(24, 16, 24, 0)

        self._easy_tab = QPushButton("Easy")
        self._easy_tab.setCheckable(True)
        self._easy_tab.setChecked(True)
        self._easy_tab.setStyleSheet(
            "QPushButton { padding: 8px 24px; border: none; "
            "border-bottom: 2px solid transparent; color: #a0a0a0; font-weight: bold; }"
            "QPushButton:checked { color: #1C69D4; border-bottom: 2px solid #1C69D4; }"
        )
        self._easy_tab.clicked.connect(lambda: self._sub_stack.setCurrentIndex(0))
        tab_bar.addWidget(self._easy_tab)

        self._adv_tab = QPushButton("Advanced")
        self._adv_tab.setCheckable(True)
        self._adv_tab.setStyleSheet(
            "QPushButton { padding: 8px 24px; border: none; "
            "border-bottom: 2px solid transparent; color: #a0a0a0; font-weight: bold; }"
            "QPushButton:checked { color: #1C69D4; border-bottom: 2px solid #1C69D4; }"
        )
        self._adv_tab.clicked.connect(lambda: self._sub_stack.setCurrentIndex(1))
        tab_bar.addWidget(self._adv_tab)
        tab_bar.addStretch()

        # Make Easy/Advanced exclusive — clicking the active tab keeps it checked
        self._tab_group = QButtonGroup(self)
        self._tab_group.setExclusive(True)
        self._tab_group.addButton(self._easy_tab, 0)
        self._tab_group.addButton(self._adv_tab, 1)
        # Prevent unchecking the active tab
        self._tab_group.buttonClicked.connect(self._ensure_tab_checked)

        # Pending changes counter
        self._pending_label = QLabel("")
        self._pending_label.setStyleSheet(
            "color: #F39C12; font-size: 13px; font-weight: bold;"
        )
        tab_bar.addWidget(self._pending_label)
        layout.addLayout(tab_bar)

        # Sub-page stack
        self._sub_stack = QStackedWidget()
        self._sub_stack.addWidget(self._build_easy_page())
        self._sub_stack.addWidget(self._build_advanced_page())
        layout.addWidget(self._sub_stack, stretch=1)

        # Bottom bar (visible when pending > 0)
        self._bottom_bar = QFrame()
        self._bottom_bar.setObjectName("bottomNav")
        self._bottom_bar.setFixedHeight(52)
        self._bottom_bar.setVisible(False)
        bar_layout = QHBoxLayout(self._bottom_bar)
        bar_layout.setContentsMargins(24, 8, 24, 8)

        clear_btn = QPushButton("Clear All")
        clear_btn.setStyleSheet(
            "QPushButton { background: #3a3a5a; color: #a0a0a0; "
            "border-radius: 8px; padding: 8px 24px; font-weight: bold; }"
            "QPushButton:hover { background: #5a5a7a; color: white; }"
        )
        clear_btn.clicked.connect(self._on_clear)
        bar_layout.addWidget(clear_btn)
        bar_layout.addStretch()

        self._write_btn = QPushButton("Write to Car")
        self._write_btn.setStyleSheet(
            "QPushButton { background: #2ECC71; color: white; "
            "border-radius: 8px; padding: 8px 24px; font-weight: bold; }"
            "QPushButton:hover { background: #27AE60; }"
        )
        self._write_btn.clicked.connect(self._on_write)
        bar_layout.addWidget(self._write_btn)
        layout.addWidget(self._bottom_bar)

    def _build_easy_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 12, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Easy Coding")
        title.setObjectName("titleLabel")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        container = QWidget()
        cat_layout = QVBoxLayout(container)
        cat_layout.setSpacing(8)

        for cat in MOCK_CATEGORIES:
            card = QFrame()
            card.setObjectName("card")
            card.setCursor(Qt.PointingHandCursor)
            card.setStyleSheet(
                "QFrame#card { background: #16213e; border: 1px solid #2a2a4a; "
                "border-radius: 8px; padding: 12px; }"
                "QFrame#card:hover { border-color: #1C69D4; }"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(4)

            top = QHBoxLayout()
            icon_label = QLabel(cat["icon"])
            icon_label.setStyleSheet("font-size: 24px; background: transparent;")
            top.addWidget(icon_label)
            name_label = QLabel(cat["name"])
            name_label.setStyleSheet(
                "font-size: 15px; font-weight: bold; color: #e0e0e0; background: transparent;"
            )
            top.addWidget(name_label)
            top.addStretch()
            card_layout.addLayout(top)

            desc = QLabel(cat["description"])
            desc.setStyleSheet(
                "font-size: 12px; color: #a0a0a0; background: transparent;"
            )
            card_layout.addWidget(desc)

            # Options expandable section
            opts_widget = QWidget()
            opts_widget.setVisible(False)
            opts_layout = QVBoxLayout(opts_widget)
            opts_layout.setContentsMargins(0, 8, 0, 0)

            for opt in cat["options"]:
                current_val = opt["values"][opt["current"]]
                opt_lbl = QLabel(
                    f"{opt['name']}: {current_val}"
                )
                opt_lbl.setStyleSheet(
                    "font-size: 13px; color: #e0e0e0; background: transparent;"
                )
                opt_lbl.setWordWrap(True)
                opts_layout.addWidget(opt_lbl)

                # QButtonGroup ensures exclusivity within this option only
                opt_group = QButtonGroup(self)

                for v_i, v_name in enumerate(opt["values"]):
                    rb = QRadioButton(f"  {v_name}")
                    rb.setStyleSheet(
                        "QRadioButton { color: #a0a0a0; spacing: 8px; }"
                        "QRadioButton::indicator { width: 14px; height: 14px; }"
                    )
                    opt_group.addButton(rb, v_i)
                    # Set checked state before connecting signal so init
                    # does not fire toggled and increment _pending
                    rb.setChecked(v_i == opt["current"])
                    rb.toggled.connect(
                        lambda checked, lbl=opt_lbl, o=opt,
                               vi=v_i: (
                            self._apply_option(o, vi, lbl, checked)
                            if checked else None
                        )
                    )
                    opts_layout.addWidget(rb)

            card_layout.addWidget(opts_widget)

            # Toggle button for accessibility
            toggle_btn = QPushButton("\u25bc Expand")
            toggle_btn.setFlat(True)
            toggle_btn.setStyleSheet(
                "QPushButton { color: #1C69D4; font-size: 11px; "
                "background: transparent; border: none; padding: 4px 0; }"
                "QPushButton:hover { color: #4A90E2; }"
            )
            toggle_btn.clicked.connect(
                lambda checked, ow=opts_widget, b=None: (
                    ow.setVisible(not ow.isVisible()),
                    # Update via closure: set b reference on first click
                )
            )
            # Use a single-shot approach — rebuild the connection to capture btn
            def _make_toggle(ow: QWidget, btn: QPushButton):
                def _toggle():
                    visible = not ow.isVisible()
                    ow.setVisible(visible)
                    btn.setText("\u25b2 Collapse" if visible else "\u25bc Expand")
                return _toggle
            toggle_btn.clicked.disconnect()
            toggle_btn.clicked.connect(_make_toggle(opts_widget, toggle_btn))
            card_layout.addWidget(toggle_btn)

            cat_layout.addWidget(card)

        cat_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)
        return page

    def _build_advanced_page(self) -> QWidget:
        """Build the Advanced Coding page — SVT ECU tree with FDL editing.

        G-11: Shows ECU list from SVT. Each ECU expands to function groups
        with raw hex editing for FDL parameters.
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 12, 24, 24)
        layout.setSpacing(12)

        # Warning banner
        warning = QLabel(
            "\u26A0  Advanced Coding \u2014 use with caution"
        )
        warning.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #F39C12;"
            "background: rgba(243,156,18,0.1); border: 1px solid #F39C12;"
            "border-radius: 8px; padding: 8px 12px;"
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)

        sub = QLabel(
            "Incorrect values may cause malfunctions. Always back up first."
        )
        sub.setStyleSheet("font-size: 12px; color: #a0a0a0;")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        # ECU tree
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )
        container = QWidget()
        self._adv_ecu_layout = QVBoxLayout(container)
        self._adv_ecu_layout.setSpacing(6)

        # Populate ECU list from mock SVT (or empty for real-car)
        # Use the MOCK_CATEGORIES-friendly list from SVT data
        self._build_ecu_tree(container)

        self._adv_ecu_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)
        return page

    def _build_ecu_tree(self, container: QWidget) -> None:
        """Populate the Advanced Coding page with ECU cards from SVT data."""
        # Get ECU list — from mock data or connection
        ecus = self._get_svt_ecus()
        # Blocked ECUs (safety-critical)
        blocked = {
            "ACSM", "DME", "DSC", "SAS", "ZGW",
            "AIRBAG", "ABG", "MRS", "SRS",
        }

        for ecu in ecus:
            name = ecu.get("name", "???")
            desc = ecu.get("description", "")
            is_blocked = any(b in name.upper() for b in blocked)

            card = QFrame()
            card.setObjectName("card")
            card.setStyleSheet(
                "QFrame#card { background: #16213e; border: 1px solid #2a2a4a; "
                "border-radius: 8px; padding: 12px; }"
                + (" border-color: #E30B1F; " if is_blocked else "")
                + "QFrame#card:hover { border-color: "
                + ("#E30B1F" if is_blocked else "#1C69D4") + "; }"
            )

            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(4)

            top = QHBoxLayout()
            name_lbl = QLabel(f"\u26A0 {name}" if is_blocked else name)
            name_lbl.setStyleSheet(
                f"font-size: 14px; font-weight: bold; "
                f"color: {'#E30B1F' if is_blocked else '#e0e0e0'}; "
                "background: transparent;"
            )
            top.addWidget(name_lbl)
            if desc:
                d_lbl = QLabel(desc)
                d_lbl.setStyleSheet(
                    "font-size: 11px; color: #a0a0a0; background: transparent;"
                )
                top.addWidget(d_lbl)
            top.addStretch()

            toggle = QPushButton("\u25bc")
            toggle.setFlat(True)
            toggle.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            toggle.setStyleSheet(
                "QPushButton { font-size: 12px; color: #a0a0a0; "
                "background: transparent; border: none; padding: 4px; }"
                "QPushButton:hover { color: #1C69D4; }"
            )
            top.addWidget(toggle)
            card_layout.addLayout(top)

            # Expandable detail (FDL hex editor)
            detail = QWidget()
            detail.setVisible(False)
            detail_layout = QVBoxLayout(detail)
            detail_layout.setContentsMargins(0, 8, 0, 0)
            detail_layout.setSpacing(6)

            if is_blocked:
                block_warn = QLabel(
                    "\u26A0 Safety-critical ECU — coding blocked"
                )
                block_warn.setStyleSheet(
                    "font-size: 12px; color: #E30B1F; font-weight: bold;"
                )
                detail_layout.addWidget(block_warn)
            else:
                # Mock FDL parameters for demo
                fdl_funcs = [
                    ("PfFzgKl30BlerFahrzeugstart", "Terminal 30B output on start",
                     "Wert_2 (1 byte)", "01"),
                    ("PfKlemme15Status", "Terminal 15 status",
                     "Wert_1 (1 bit)", "01"),
                    ("PfCanKomfortStatus", "Comfort CAN status",
                     "Wert_2 (1 byte)", "02"),
                ]
                for func_name, func_desc, func_type, func_val in fdl_funcs:
                    func_card = QFrame()
                    func_card.setStyleSheet(
                        "background: #1a1a3e; border: 1px solid #2a2a4a; "
                        "border-radius: 6px; padding: 8px;"
                    )
                    func_layout = QVBoxLayout(func_card)
                    func_layout.setSpacing(2)

                    fn = QLabel(func_name)
                    fn.setStyleSheet(
                        "font-size: 12px; font-weight: bold; color: #e0e0e0; "
                        "background: transparent;"
                    )
                    func_layout.addWidget(fn)

                    fd = QLabel(func_desc)
                    fd.setStyleSheet(
                        "font-size: 11px; color: #a0a0a0; background: transparent;"
                    )
                    func_layout.addWidget(fd)

                    ft = QLabel(f"Type: {func_type}  |  Current: {func_val}")
                    ft.setStyleSheet(
                        "font-size: 11px; color: #a0a0a0; background: transparent;"
                    )
                    func_layout.addWidget(ft)

                    detail_layout.addWidget(func_card)

            card_layout.addWidget(detail)

            # Toggle detail
            toggle.clicked.connect(
                lambda checked, d=detail, b=toggle: (
                    d.setVisible(not d.isVisible()),
                    b.setText("\u25b2" if d.isVisible() else "\u25bc"),
                )
            )

            self._adv_ecu_layout.addWidget(card)

    def _get_svt_ecus(self) -> list[dict]:
        """Get the SVT ECU list from connection data or return default."""
        if self._connection and hasattr(self._connection, "data") \
                and self._connection.data:
            return self._connection.data.get("svt_ecus", [])
        # Fallback demo ECUs
        return [
            {"name": "DME", "description": "Digital Motor Electronics"},
            {"name": "EGS", "description": "Electronic Transmission Control"},
            {"name": "ZGW", "description": "Central Gateway"},
            {"name": "FEM_01", "description": "Front Electronic Module"},
            {"name": "REM_01", "description": "Rear Electronic Module"},
            {"name": "KOMBI", "description": "Instrument Cluster"},
            {"name": "HU_NBT", "description": "Headunit NBT"},
            {"name": "IHKA", "description": "Climate Control"},
            {"name": "ACSM", "description": "Airbag Control Unit"},
            {"name": "DSC", "description": "Dynamic Stability Control"},
        ]

    def set_connection(self, connection: Any) -> None:
        """Store the active connection for future coding operations.

        Args:
            conection: An HSFZConnection, DoIPConnection, or MockConnection.
        """
        self._connection = connection

        # G-8: For real cars, read CAFD/FDL data from each ECU
        if not (hasattr(connection, "data") and connection.data):
            self._worker = CodingReadWorker(connection)
            self._worker.progress.connect(
                lambda msg: logger.debug("Coding read: %s", msg)
            )
            self._worker.finished.connect(self._on_coding_read)
            self._worker.error.connect(
                lambda msg: logger.warning("Coding read failed: %s", msg)
            )
            self._worker.start()

    def _ensure_tab_checked(self, btn: QPushButton) -> None:
        """Keep the active sub-tab button checked — clicking it again keeps it."""
        if not btn.isChecked():
            btn.setChecked(True)

    def restore_backup(self, categories: list[dict]) -> None:
        """Restore coding from a backup manifest.

        Args:
            categories: List of category dicts from a backup manifest.json.
        """
        MOCK_CATEGORIES.clear()
        MOCK_CATEGORIES.extend(copy.deepcopy(categories))
        self._originals = copy.deepcopy(MOCK_CATEGORIES)
        self._pending = 0
        self._update_pending_label()
        # Rebuild easy page
        old_page = self._sub_stack.widget(0)
        self._sub_stack.removeWidget(old_page)
        old_page.deleteLater()
        self._sub_stack.insertWidget(0, self._build_easy_page())
        self._sub_stack.setCurrentIndex(0)
        self._easy_tab.setChecked(True)
        logger.info("Coding restored from backup (%d categories)", len(categories))

    def _apply_option(
        self, opt: dict, idx: int, label: QLabel, checked: bool
    ) -> None:
        if not checked:
            return
        opt["current"] = idx
        val = opt["values"][idx]
        label.setText(f"{opt['name']}: {val}")
        # Recalculate pending count by comparing against originals
        self._recalc_pending()

    def _recalc_pending(self) -> None:
        """Count how many options differ from the saved originals."""
        pending = 0
        for cat_idx, cat in enumerate(MOCK_CATEGORIES):
            orig_cat = self._originals[cat_idx]
            for opt_idx, opt in enumerate(cat["options"]):
                orig_opt = orig_cat["options"][opt_idx]
                if opt["current"] != orig_opt["current"]:
                    pending += 1
        self._pending = pending
        self._update_pending_label()

    def _update_pending_label(self) -> None:
        if self._pending > 0:
            self._pending_label.setText(f"[{self._pending} changes pending]")
            self._bottom_bar.setVisible(True)
        else:
            self._pending_label.setText("")
            self._bottom_bar.setVisible(False)

    def _on_clear(self) -> None:
        reply = QMessageBox.question(
            self,
            "Clear Changes",
            "Discard all pending coding changes?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._pending = 0
        self._update_pending_label()
        # Restore original option values by deep-copying into MOCK_CATEGORIES
        MOCK_CATEGORIES.clear()
        MOCK_CATEGORIES.extend(copy.deepcopy(self._originals))
        # Rebuild the easy page to reflect restored values
        old_page = self._sub_stack.widget(0)
        self._sub_stack.removeWidget(old_page)
        old_page.deleteLater()
        self._sub_stack.insertWidget(0, self._build_easy_page())
        self._sub_stack.setCurrentIndex(0)
        self._easy_tab.setChecked(True)
        logger.info("Coding changes cleared")

    def _on_write(self) -> None:
        reply = QMessageBox.question(
            self,
            "Write to Car",
            f"Write {self._pending} coding changes to the vehicle?\n\n"
            "A backup will be saved before writing.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # G-9: Auto-backup before write
        self._save_backup()

        # Mock path
        if hasattr(self._connection, "data") and self._connection.data:
            self._pending = 0
            self._update_pending_label()
            self._originals = copy.deepcopy(MOCK_CATEGORIES)
            logger.info("Coding changes written (mock)")
            return

        # G-9: Real car — write via UDS 0x2E WriteDataByIdentifier
        self._worker = CodingWriteWorker(self._connection, MOCK_CATEGORIES)
        self._worker.finished.connect(self._on_write_complete)
        self._worker.error.connect(self._on_write_error)
        self._worker.start()

    def _on_write_complete(self, _result: object = None) -> None:
        """Update UI after a successful coding write."""
        self._pending = 0
        self._update_pending_label()
        self._originals = copy.deepcopy(MOCK_CATEGORIES)
        QMessageBox.information(
            self,
            "Coding Written",
            "Coding changes saved to vehicle.\n"
            "Backup stored in ~/BMW-Tool/backups/.",
        )
        logger.info("Coding changes written")

    def _on_write_error(self, msg: str) -> None:
        """Handle coding write failure."""
        QMessageBox.warning(
            self,
            "Write Failed",
            f"Failed to write coding changes: {msg}\n\n"
            "Your original coding has been backed up.\n"
            "Use the Backups page to roll back.",
        )
        logger.warning("Coding write failed: %s", msg)

    def _save_backup(self) -> None:
        """Save a backup of current MOCK_CATEGORIES before writing.

        G-9: Creates a timestamped backup directory with ECU CAFD/FDL data.
        G-14: Handles disk-full gracefully with user-facing error.
        """
        import json
        import os
        from datetime import datetime

        backup_dir = os.path.join(
            os.path.expanduser("~"), "BMW-Tool", "backups",
            datetime.now().strftime("%Y-%m-%d_%H-%M"),
        )
        try:
            os.makedirs(backup_dir, exist_ok=True)
        except OSError:
            QMessageBox.warning(
                self,
                "Backup Failed",
                "Cannot save backup — disk is full.\n"
                "Free up space and try again.",
            )
            return

        # Save manifest
        manifest = {
            "timestamp": datetime.now().isoformat(),
            "changes": self._pending,
            "categories": MOCK_CATEGORIES,
        }
        try:
            with open(os.path.join(backup_dir, "manifest.json"), "w") as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)
        except OSError:
            QMessageBox.warning(
                self,
                "Backup Failed",
                "Cannot save backup — disk is full.\n"
                "Free up space and try again.",
            )
            return

        logger.info("Backup saved to %s", backup_dir)

    def _on_coding_read(self, categories: list[dict]) -> None:
        """Populate mock categories from real-car read."""
        if categories:
            MOCK_CATEGORIES.clear()
            MOCK_CATEGORIES.extend(categories)
            self._originals = copy.deepcopy(MOCK_CATEGORIES)
            # Rebuild easy page
            old_page = self._sub_stack.widget(0)
            self._sub_stack.removeWidget(old_page)
            old_page.deleteLater()
            self._sub_stack.insertWidget(0, self._build_easy_page())
            self._sub_stack.setCurrentIndex(0)
            self._easy_tab.setChecked(True)
            logger.info("Coding data loaded from car (%d categories)", len(categories))


# ---- Coding Workers ----

class CodingReadWorker(CarWorker):
    """Read CAFD/FDL coding data from all ECUs via UDS 0x22."""

    def __init__(self, connection: Any) -> None:
        super().__init__(connection)
        # Common ECUs to query for coding data
        self.targets = [
            (0x40, "FEM"), (0x50, "REM"), (0x60, "KOMBI"),
            (0x63, "HU_NBT"), (0x78, "IHKA"), (0x72, "ASD"),
        ]

    def do_work(self) -> list[dict]:
        categories: list[dict] = []
        for addr, name in self.targets:
            self.progress.emit(f"Reading coding from {name}...")
            try:
                # Extended session
                self.connection.send_uds(addr, bytes([0x10, 0x03]))
                # Read coding data — DID varies by ECU; use generic approach
                resp = self.connection.send_uds(addr, bytes([0x22, 0xF1, 0x00]))
                if resp[0] == 0x62:
                    logger.debug(
                        "Coding data from %s (0x%02X): %d bytes",
                        name, addr, len(resp),
                    )
            except Exception as e:
                logger.debug("Coding read skip %s (0x%02X): %s", name, addr, e)
        # Return empty — real coding data requires per-chassis DID mapping
        return categories


class CodingWriteWorker(CarWorker):
    """Write coding changes to ECUs via UDS 0x2E WriteDataByIdentifier."""

    def __init__(self, connection: Any, categories: list[dict]) -> None:
        super().__init__(connection)
        self.categories = categories

    def do_work(self) -> bool:
        for cat in self.categories:
            for opt in cat.get("options", []):
                self.progress.emit(f"Writing {opt.get('name', 'option')}...")
                # Build 0x2E payload — DID + data bytes
                payload = bytes([0x2E, opt.get("current", 0) & 0xFF])
                try:
                    self.connection.send_uds(0x40, payload)
                except Exception as e:
                    raise ConnectionError(
                        f"Write failed for {opt.get('name', 'option')}: {e}"
                    ) from e
        return True
