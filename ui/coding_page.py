"""Coding page — Easy + Advanced coding with write/clear bar.

Easy: curated category -> option toggles.
Advanced: SVT ECU tree -> FDL hex editor (stub).

Reference: docs/16-ui-spec.md Screens 7, 8, 9
"""

import copy
import logging
import os
from typing import Any

from PySide6.QtCore import Qt, Slot
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

from app.coding import CodingSnapshotWorker
from app.coding_db import CodingDatabase, _decrypt_enc
from app.resources import resource_path
from app.worker import CarWorker

logger = logging.getLogger(__name__)

# T-3: Build CAFD lookup from coding-ecu-infos.enc at import time.
# Maps ECU short names to (cafd_id, first_available_variant) tuples.
_CAFD_MAP: dict[str, tuple[str, str]] = {}
try:
    import json as _json

    _infos = _json.loads(_decrypt_enc(str(resource_path("coding_data/coding-ecu-infos.enc"))))
    for _e in _infos:
        _name = _e.get("shortName", "")
        _cafd = _e.get("identifier", "")
        if _name and _cafd:
            # Find first available variant file
            _var = None
            for _f in os.listdir(resource_path("coding_data")):
                if _f.startswith(f"{_cafd}-") and _f.endswith(".enc"):
                    _var = _f[len(_cafd) + 1 : -4]
                    break
            if _var:
                _CAFD_MAP[_name] = (_cafd, _var)
except (FileNotFoundError, _json.JSONDecodeError, ValueError) as _e:
    logger.warning("Failed to load CAFD map: %s", _e)

# Singleton coding database instance
coding_db = CodingDatabase(str(resource_path("coding_data")))

MOCK_CATEGORIES = [
    {
        "name": "Lighting",
        "icon": "L",
        "description": "Angel eyes brightness, welcome lights, DRL behavior",
        "options": [
            {
                "name": "Angel Eyes Brightness",
                "values": ["4%", "8%", "12%", "16%", "20%"],
                "current": 1,
            },
            {
                "name": "Welcome Lights Duration",
                "values": ["10s", "20s", "30s", "40s"],
                "current": 2,
            },
            {"name": "DRL Rear Lights", "values": ["Off", "On"], "current": 0},
        ],
    },
    {
        "name": "Comfort",
        "icon": "C",
        "description": "Fold mirrors, window control, seat heating memory",
        "options": [
            {
                "name": "Fold Mirrors on Lock",
                "values": ["Off", "On (hold)", "On (instant)"],
                "current": 1,
            },
            {
                "name": "Window Control after Ignition Off",
                "values": ["Disabled", "30s", "60s", "Unlimited"],
                "current": 2,
            },
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
        """Build coding previews with live writes and backup loading disabled until configured."""
        super().__init__(parent)
        self._connection: Any = None
        self._pending: int = 0
        self._categories: list[dict] = copy.deepcopy(MOCK_CATEGORIES)
        self._originals = copy.deepcopy(self._categories)
        self._worker: CarWorker | None = None
        self._coding_reader: CarWorker | None = None
        self._coding_writer: CarWorker | None = None
        self._is_real = False  # True when categories come from car, not mock
        self._live_unavailable = True
        self._snapshot_workers: list[CarWorker] = []
        self._sub_stack: QStackedWidget
        self._setup_ui()
        self._write_btn.setEnabled(False)

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
            "QPushButton { background-color: transparent; padding: 8px 24px; "
            "border: none; border-bottom: 2px solid transparent; "
            "color: #a0a0a0; font-weight: bold; }"
            "QPushButton:hover { color: #d0d0d0; }"
            "QPushButton:checked { color: #1C69D4; "
            "border-bottom: 2px solid #1C69D4; }"
        )
        self._easy_tab.clicked.connect(lambda: self._sub_stack.setCurrentIndex(0))
        tab_bar.addWidget(self._easy_tab)

        self._adv_tab = QPushButton("Advanced")
        self._adv_tab.setCheckable(True)
        self._adv_tab.setStyleSheet(
            "QPushButton { background-color: transparent; padding: 8px 24px; "
            "border: none; border-bottom: 2px solid transparent; "
            "color: #a0a0a0; font-weight: bold; }"
            "QPushButton:hover { color: #d0d0d0; }"
            "QPushButton:checked { color: #1C69D4; "
            "border-bottom: 2px solid #1C69D4; }"
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
        self._pending_label.setStyleSheet("color: #F39C12; font-size: 13px; font-weight: bold;")
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

        for cat in self._categories:
            card = QFrame()
            card.setObjectName("card")
            card.setCursor(Qt.CursorShape.PointingHandCursor)
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
            desc.setStyleSheet("font-size: 12px; color: #a0a0a0; background: transparent;")
            card_layout.addWidget(desc)

            # Options expandable section
            opts_widget = QWidget()
            opts_widget.setVisible(False)
            opts_layout = QVBoxLayout(opts_widget)
            opts_layout.setContentsMargins(0, 8, 0, 0)

            for opt in cat["options"]:
                current_val = opt["values"][opt["current"]]
                opt_lbl = QLabel(f"{opt['name']}: {current_val}")
                opt_lbl.setStyleSheet("font-size: 13px; color: #e0e0e0; background: transparent;")
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
                        lambda checked, lbl=opt_lbl, o=opt, vi=v_i: (
                            self._apply_option(o, vi, lbl, checked) if checked else None
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
        warning = QLabel("\u26a0  Advanced Coding \u2014 use with caution")
        warning.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #F39C12;"
            "background: rgba(243,156,18,0.1); border: 1px solid #F39C12;"
            "border-radius: 8px; padding: 8px 12px;"
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)

        sub = QLabel("Incorrect values may cause malfunctions. Always back up first.")
        sub.setStyleSheet("font-size: 12px; color: #a0a0a0;")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        # ECU tree
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
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
            "ACSM",
            "DME",
            "DSC",
            "SAS",
            "ZGW",
            "AIRBAG",
            "ABG",
            "MRS",
            "SRS",
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
                + ("#E30B1F" if is_blocked else "#1C69D4")
                + "; }"
            )

            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(4)

            top = QHBoxLayout()
            name_lbl = QLabel(f"\u26a0 {name}" if is_blocked else name)
            name_lbl.setStyleSheet(
                f"font-size: 14px; font-weight: bold; "
                f"color: {'#E30B1F' if is_blocked else '#e0e0e0'}; "
                "background: transparent;"
            )
            top.addWidget(name_lbl)
            if desc:
                d_lbl = QLabel(desc)
                d_lbl.setStyleSheet("font-size: 11px; color: #a0a0a0; background: transparent;")
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
                block_warn = QLabel("\u26a0 Safety-critical ECU — coding blocked")
                block_warn.setStyleSheet("font-size: 12px; color: #E30B1F; font-weight: bold;")
                detail_layout.addWidget(block_warn)
            else:
                # T-5: Real FDL parameters from coding database
                fdl_funcs: list[dict] = []
                cafd_entry = _CAFD_MAP.get(name)
                if cafd_entry:
                    try:
                        cafd_id, variant = cafd_entry
                        coding_db.load_ecu(cafd_id, variant)
                        fdl_funcs = coding_db.get_ecu_fdl_functions(cafd_id, variant)[
                            :50
                        ]  # limit to 50 for performance
                    except Exception:
                        pass

                if fdl_funcs:
                    for func in fdl_funcs:
                        si = func.get("storageInfo", {})
                        func_type = f"byte {si.get('start', '?')}  mask {si.get('mask', '?')}"
                        func_card = QFrame()
                        func_card.setStyleSheet(
                            "background: #1a1a3e; border: 1px solid #2a2a4a; "
                            "border-radius: 6px; padding: 8px;"
                        )
                        func_layout = QVBoxLayout(func_card)
                        func_layout.setSpacing(2)

                        fn = QLabel(func["name"])
                        fn.setStyleSheet(
                            "font-size: 12px; font-weight: bold; "
                            "color: #e0e0e0; background: transparent;"
                        )
                        func_layout.addWidget(fn)

                        ft_lbl = QLabel(f"DID: 0x{func['did']:04X}  |  {func_type}")
                        ft_lbl.setStyleSheet(
                            "font-size: 11px; color: #a0a0a0; background: transparent;"
                        )
                        func_layout.addWidget(ft_lbl)

                        detail_layout.addWidget(func_card)
                else:
                    no_data = QLabel("No FDL data available for this ECU")
                    no_data.setStyleSheet("font-size: 11px; color: #a0a0a0; font-style: italic;")
                    detail_layout.addWidget(no_data)

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
        if self._connection and hasattr(self._connection, "data") and self._connection.data:
            svt: list[dict] = self._connection.data.get("svt_ecus", [])
            return svt
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

    def set_connection(self, connection: Any, ecus: list[dict] | None = None) -> None:
        """Store the active connection for future coding operations.

        T-2: If ECU list is provided (from SVT read), load real coding
        presets from the coding database, replacing MOCK_CATEGORIES.

        Args:
            connection: An HSFZConnection, DoIPConnection, or MockConnection.
            ecus: Optional SVT ECU list from vehicle connection.
        """
        self._connection = connection
        is_demo = bool(getattr(connection, "data", None))
        self._live_unavailable = not is_demo
        self._pending = 0
        self._categories = copy.deepcopy(MOCK_CATEGORIES) if is_demo else []
        self._originals = copy.deepcopy(self._categories)
        self._is_real = False
        self._update_pending_label()
        self._write_btn.setEnabled(is_demo)
        while self._sub_stack.count():
            old_page = self._sub_stack.widget(0)
            if old_page is None:
                break
            self._sub_stack.removeWidget(old_page)
            old_page.deleteLater()
        if is_demo:
            self._sub_stack.addWidget(self._build_easy_page())
            self._sub_stack.addWidget(self._build_advanced_page())
            if ecus:
                self._load_coding_presets(ecus)
            return

        for mode in ("Easy", "Advanced"):
            page = QWidget()
            layout = QVBoxLayout(page)
            message = QLabel(f"{mode}: reading exact coding definitions and stored bytes...")
            message.setWordWrap(True)
            layout.addWidget(message)
            layout.addStretch()
            self._sub_stack.addWidget(page)
        self._snapshot_ecus = ecus or []
        self._snapshot_loaded = False

    def activate(self) -> None:
        """Start an exact-identity read when this live page is first opened."""
        connection = self._connection
        if (
            connection is None
            or hasattr(connection, "data")
            or getattr(self, "_snapshot_loaded", False)
            or self._coding_reader is not None
        ):
            return
        vin = getattr(connection, "verified_vin", "")
        if not vin:
            return
        worker = CodingSnapshotWorker(connection, self._snapshot_ecus, vin)
        self._coding_reader = worker
        self._snapshot_workers.append(worker)
        worker.result_ready.connect(self._on_snapshot)
        worker.error.connect(self._on_snapshot_error)
        worker.finished.connect(self._on_snapshot_finished)
        worker.start()

    def is_reading(self) -> bool:
        """Whether an owned coding snapshot read is still running."""
        return self._coding_reader is not None and self._coding_reader.isRunning()

    @Slot(str)
    def _on_snapshot_error(self, message: str) -> None:
        self._on_snapshot(
            [{"name": "Coding", "state": message, "definitions": [], "blocks": {}, "backup": ""}]
        )

    @Slot()
    def _on_snapshot_finished(self) -> None:
        worker = self.sender()
        if worker is self._coding_reader:
            self._coding_reader = None
        if isinstance(worker, CarWorker):
            if worker in self._snapshot_workers:
                self._snapshot_workers.remove(worker)
            if not worker.property("retired_by_main"):
                worker.deleteLater()

    @Slot(object)
    def _on_snapshot(self, rows: list[dict]) -> None:
        """Publish an entire settled read batch; never make opaque bytes editable."""
        worker = self.sender()
        if (
            not isinstance(worker, CarWorker)
            or worker is not self._coding_reader
            or worker.connection is not self._connection
        ):
            return
        self._snapshot_loaded = True
        page = QWidget()
        layout = QVBoxLayout(page)
        notice = QLabel(
            "Stored coding bytes read from the vehicle. Preset editing and writes require the remaining selection, authorization and restoration contracts."
        )
        notice.setWordWrap(True)
        layout.addWidget(notice)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        entries = QVBoxLayout(content)
        for row in rows:
            label = QLabel(
                f"{row['name']}: {row['state']}\nDefinitions: {', '.join(row['definitions']) or 'Unavailable'}\nGroups read: {len(row['blocks'])}"
            )
            label.setWordWrap(True)
            entries.addWidget(label)
            if row["backup"]:
                saved = QLabel(f"Snapshot: {row['backup']}")
                saved.setWordWrap(True)
                entries.addWidget(saved)
        entries.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        old = self._sub_stack.widget(0)
        if old is not None:
            self._sub_stack.removeWidget(old)
            old.deleteLater()
        self._sub_stack.insertWidget(0, page)
        advanced = self._sub_stack.widget(1)
        if advanced is not None:
            self._sub_stack.removeWidget(advanced)
            advanced.deleteLater()
        settled = QWidget()
        settled_layout = QVBoxLayout(settled)
        settled_notice = QLabel(
            "Advanced coding is unavailable. See the Easy tab for snapshot results and coverage."
        )
        settled_notice.setWordWrap(True)
        settled_layout.addWidget(settled_notice)
        settled_layout.addStretch()
        self._sub_stack.insertWidget(1, settled)
        self._sub_stack.setCurrentIndex(0)
        self._easy_tab.setChecked(True)

    def _load_coding_presets(self, ecus: list[dict]) -> None:
        """T-2/T-3/T-4: Load coding presets from database for discovered ECUs.

        Matches ECU names against coding-ecu-infos.enc to find CAFD IDs,
        loads the coding database, and builds Easy Coding presets grouped
        by section with human-readable labels. Preserves full CAFD metadata
        per option so CodingWriteWorker can construct correct writes.

        Falls back to MOCK_CATEGORIES if no ECUs match the database.
        """
        presets_by_section: dict[str, list[dict]] = {}
        # T-4: Metadata for real writes — maps (cat_name, opt_name) → coding info
        self._coding_meta: dict[tuple[str, str], dict] = {}
        loaded_ecus = 0

        for ecu in ecus:
            name = ecu.get("name", "")
            ecu_addr_str = ecu.get("addr", "0x10")
            ecu_addr = int(ecu_addr_str, 16) if ecu_addr_str.startswith("0x") else int(ecu_addr_str)

            # Try exact match first, then prefix match
            if name in _CAFD_MAP:
                cafd_id, variant = _CAFD_MAP[name]
            else:
                # Try prefix match (e.g. "FEM_01" matches "FEM" prefix)
                match = None
                for short_name, (cid, var) in _CAFD_MAP.items():
                    if name.upper().startswith(short_name.upper().split()[0][:3]):
                        cafd_id, variant = cid, var
                        match = short_name
                        break
                if match is None:
                    logger.debug("No CAFD match for ECU %s", name)
                    continue
                cafd_id, variant = _CAFD_MAP[match]

            # Load this ECU's coding database
            try:
                coding_db.load_ecu(cafd_id, variant)
                loaded_ecus += 1
            except Exception as e:
                logger.warning("Failed to load coding for %s: %s", name, e)
                continue

            # T-2: Try to read current CAFD bytes from the ECU via UDS 0x22
            cafd_bytes = b""
            if self._connection and not (
                hasattr(self._connection, "data") and self._connection.data
            ):
                for cafd_did in (0xF100, 0xF110, 0xF120, 0xF130):
                    try:
                        resp = self._connection.send_uds(
                            ecu_addr,
                            bytes([0x22, (cafd_did >> 8) & 0xFF, cafd_did & 0xFF]),
                            timeout=5.0,
                        )
                        if resp[0] == 0x62 and len(resp) > 3:
                            cafd_bytes = resp[3:]
                            break
                    except Exception:
                        pass
                if cafd_bytes:
                    logger.debug(
                        "Read %d CAFD bytes from %s (0x%02X)",
                        len(cafd_bytes),
                        name,
                        ecu_addr,
                    )

            # Build presets grouped by section
            for preset in coding_db.get_presets(cafd_id):
                section = preset["section"]
                if section not in presets_by_section:
                    presets_by_section[section] = []
                opt_label = preset["label"]
                opt_values = [o["label"] for o in preset["options"]]
                opt_entry = {
                    "name": opt_label,
                    "values": opt_values,
                    "current": 0,  # Will be updated when CAFD bytes are read
                }
                # Check if this option already exists in section
                existing_names = [o["name"] for o in presets_by_section[section]]
                if opt_entry["name"] not in existing_names:
                    presets_by_section[section].append(opt_entry)
                    # T-4: Store metadata for write path
                    # Look up the DID from the first function's dataGroup
                    did = 0x3000  # default
                    for option in preset.get("options", []):
                        for func in option.get("functions", []):
                            d = coding_db.get_did_for_preset(cafd_id, variant, func.get("name", ""))
                            if d is not None:
                                did = d
                                break
                        if did != 0x3000:
                            break
                    section_name = section.replace("_", " ").title()
                    self._coding_meta[(section_name, opt_label)] = {
                        "cafd_id": cafd_id,
                        "variant": variant,
                        "ecu_addr": ecu_addr,
                        "did": did,
                        "preset": preset,
                        "cafd_bytes": cafd_bytes,
                    }

                    # T-2: If we have CAFD bytes, determine current value
                    if cafd_bytes:
                        current_val = coding_db.get_current_value(
                            preset, cafd_bytes, cafd_id, variant
                        )
                        if current_val is not None:
                            # Find the index of the current value in options
                            for oi, o in enumerate(preset["options"]):
                                if o["name"] == current_val:
                                    opt_entry["current"] = oi
                                    break

        if loaded_ecus == 0:
            logger.info("No coding data for discovered ECUs — using mock")
            return

        # T-3: Build categories from presets, replacing MOCK_CATEGORIES
        categories: list[dict] = []
        for section, options in presets_by_section.items():
            icon_text = section.split("_")[0][:1] if "_" in section else section[:1]
            categories.append(
                {
                    "name": section.replace("_", " ").title(),
                    "icon": icon_text,
                    "description": f"{len(options)} coding options",
                    "options": sorted(options, key=lambda o: o["name"]),
                }
            )

        if categories:
            self._on_coding_read(categories)
            logger.info(
                "Loaded coding presets: %d categories from %d ECUs",
                len(categories),
                loaded_ecus,
            )

    def _ensure_tab_checked(self, btn: QPushButton) -> None:
        """Keep the active sub-tab button checked — clicking it again keeps it."""
        if not btn.isChecked():
            btn.setChecked(True)

    def restore_backup(self, categories: list[dict]) -> bool:
        """Load a local DEMO preview from a backup; return False when unavailable.

        The restored values become the active state, and any differences
        from the previous originals are counted as pending changes so
        the user can write them to the car.

        Args:
            categories: List of category dicts from a backup manifest.json.
        """
        if self._live_unavailable:
            logger.warning("Live coding backup restore blocked: verified restore unavailable")
            return False
        # Save pre-restore originals to count differences
        prev_originals = self._originals
        self._categories.clear()
        self._categories.extend(copy.deepcopy(categories))
        self._originals = prev_originals  # keep old originals so diff is correct
        # Rebuild easy page
        old_page = self._sub_stack.widget(0)
        if old_page is not None:
            self._sub_stack.removeWidget(old_page)
            old_page.deleteLater()
        self._sub_stack.insertWidget(0, self._build_easy_page())
        self._sub_stack.setCurrentIndex(0)
        self._easy_tab.setChecked(True)
        # Recalculate pending — differences between restored and previous originals
        self._recalc_pending()
        logger.info("Coding restored from backup (%d categories)", len(categories))
        return True

    def _apply_option(self, opt: dict, idx: int, label: QLabel, checked: bool) -> None:
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
        for cat_idx, cat in enumerate(self._categories):
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
        # Restore original option values by deep-copying into self._categories
        self._categories.clear()
        self._categories.extend(copy.deepcopy(self._originals))
        # Rebuild the easy page to reflect restored values
        old_page = self._sub_stack.widget(0)
        if old_page is not None:
            self._sub_stack.removeWidget(old_page)
            old_page.deleteLater()
        self._sub_stack.insertWidget(0, self._build_easy_page())
        self._sub_stack.setCurrentIndex(0)
        self._easy_tab.setChecked(True)
        logger.info("Coding changes cleared")

    def _on_write(self) -> None:
        """Apply pending changes only when the active connection permits coding writes."""
        if self._live_unavailable:
            logger.warning("Live coding write blocked: exact definitions/readback unavailable")
            return
        reply = QMessageBox.question(
            self,
            "Write to Car",
            f"Write {self._pending} coding changes to the vehicle?\n\n"
            "A DEMO preview will be saved. No vehicle backup or write is performed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # DEMO metadata is deliberately separate from vehicle backups.
        if not self._save_demo_preview():
            QMessageBox.warning(
                self,
                "Write Aborted",
                "Cannot save the DEMO preview. Check storage space and permissions.",
            )
            return

        # Mock path
        if hasattr(self._connection, "data") and self._connection.data:
            self._pending = 0
            self._update_pending_label()
            self._originals = copy.deepcopy(self._categories)
            logger.info("Coding changes written (mock)")
            return

        # G-9: Real car — write via UDS 0x2E WriteDataByIdentifier
        self._write_btn.setEnabled(False)
        self._coding_writer = CodingWriteWorker(
            self._connection,
            self._categories,
            getattr(self, "_coding_meta", {}),
            self._originals,
        )
        self._coding_writer.result_ready.connect(self._on_write_complete)
        self._coding_writer.error.connect(self._on_write_error)
        self._coding_writer.start()

    def _on_write_complete(self, _result: object = None) -> None:
        """Update UI after a successful coding write."""
        self._write_btn.setEnabled(True)
        self._coding_writer = None
        self._pending = 0
        self._update_pending_label()
        self._originals = copy.deepcopy(self._categories)
        QMessageBox.information(
            self,
            "Coding Written",
            "Coding changes saved to vehicle.\nBackup stored in ~/BMW-Tool/backups/.",
        )
        logger.info("Coding changes written")

    def _on_write_error(self, msg: str) -> None:
        """Handle coding write failure."""
        self._write_btn.setEnabled(True)
        self._coding_writer = None
        QMessageBox.warning(
            self,
            "Write Failed",
            f"Failed to write coding changes: {msg}\n\n"
            "Your original coding has been backed up.\n"
            "Use the Backups page to roll back.",
        )
        logger.warning("Coding write failed: %s", msg)

    def _save_demo_preview(self) -> bool:
        """Save a non-restorable DEMO preview, never a live ECU backup.

        Live coding snapshots use OperationStore; future writes must prepare
        complete baseline/intent there rather than reusing UI category data.
        """
        if not getattr(self._connection, "data", None):
            return False
        import json
        import os
        from datetime import datetime

        backup_dir = os.path.join(
            os.path.expanduser("~"),
            "BMW-Tool",
            "demo-previews",
            datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f"),
        )
        try:
            os.makedirs(backup_dir, exist_ok=True)
        except OSError:
            QMessageBox.warning(
                self,
                "Backup Failed",
                "Cannot save backup — disk is full.\nFree up space and try again.",
            )
            return False

        # Display metadata only; never accepted by the live backup importer.
        manifest = {
            "mode": "demo",
            "restorable": False,
            "timestamp": datetime.now().isoformat(),
            "changes": self._pending,
            "categories": self._originals,
        }
        try:
            with open(os.path.join(backup_dir, "manifest.json"), "w") as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)
        except OSError:
            QMessageBox.warning(
                self,
                "Backup Failed",
                "Cannot save backup — disk is full.\nFree up space and try again.",
            )
            return False

        logger.info("Backup saved to %s", backup_dir)
        return True

    def _on_coding_read(self, categories: list[dict]) -> None:
        """Populate categories from real-car read or coding database."""
        if categories:
            self._categories.clear()
            self._categories.extend(categories)
            self._originals = copy.deepcopy(self._categories)
            self._pending = 0
            self._update_pending_label()
            self._is_real = True
            # Rebuild easy page
            old_page = self._sub_stack.widget(0)
            if old_page is not None:
                self._sub_stack.removeWidget(old_page)
                old_page.deleteLater()
            self._sub_stack.insertWidget(0, self._build_easy_page())
            self._sub_stack.setCurrentIndex(0)
            self._easy_tab.setChecked(True)
            logger.info("Coding data loaded (%d categories)", len(categories))


# ---- Coding Workers ----


class CodingReadWorker(CarWorker):
    """Read CAFD/FDL coding data from all ECUs via UDS 0x22."""

    def __init__(self, connection: Any) -> None:
        """Build coding previews with live writes and backup loading disabled until configured."""
        super().__init__(connection)
        # Common ECUs to query for coding data
        self.targets = [
            (0x40, "FEM"),
            (0x50, "REM"),
            (0x60, "KOMBI"),
            (0x63, "HU_NBT"),
            (0x78, "IHKA"),
            (0x72, "ASD"),
        ]

    def do_work(self) -> list[dict]:
        """The old guessed reader is retired; use exact-identity snapshots."""
        raise PermissionError("Use the exact coding snapshot reader")


class CodingWriteWorker(CarWorker):
    """Write coding changes to ECUs via UDS 0x2E WriteDataByIdentifier.

    T-4: Uses coding_db metadata when available to construct writes
    with correct ECU addresses and real DIDs from CAFD dataGroups.
    Rejects options without CAFD metadata (unsafe to write blindly).
    Skips options whose value hasn't changed from originals.
    """

    def __init__(
        self,
        connection: Any,
        categories: list[dict],
        coding_meta: dict[tuple[str, str], dict] | None = None,
        originals: list[dict] | None = None,
    ) -> None:
        """Build coding previews with live writes and backup loading disabled until configured."""
        super().__init__(connection)
        self.categories = categories
        self.coding_meta = coding_meta or {}
        self.originals = originals or []

    def do_work(self) -> bool:
        """Block the retired encoder until composed writes and recovery are recovered."""
        raise PermissionError(
            "Coding writes require the recovered authorization and restoration contract"
        )
