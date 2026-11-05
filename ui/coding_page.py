"""Coding page — Easy + Advanced coding with write/clear bar.

Easy: curated category -> option toggles.
Advanced: SVT ECU tree -> FDL hex editor (stub).

Reference: docs/16-ui-spec.md Screens 7, 8, 9
"""

import copy
import logging
from collections.abc import Callable
from pathlib import Path
from threading import Event
from typing import Any

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from app.coding import CodingSnapshotWorker
from app.coding_db import CodingDatabase
from app.worker import CarWorker
from ui.page_stack import PageStack

logger = logging.getLogger(__name__)

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

    mutation_active = Signal(bool)
    loading_changed = Signal(bool)
    loading_progress = Signal(str)

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
        self._sensitive_worker: CarWorker | None = None
        self._loading_worker: CarWorker | None = None
        self._is_real = False  # True when categories come from car, not mock
        self._live_unavailable = True
        self._snapshot_workers: list[CarWorker] = []
        self._live_selections: dict[tuple[int, str, str, int], str] = {}
        self._source_rows: list[dict] = []
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
        """Build coding tabs, pending controls and the mutation action bar."""
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
        self._sub_stack = PageStack(content_height=True)
        self._sub_stack.addWidget(self._build_easy_page())
        self._sub_stack.addWidget(self._build_advanced_page())
        layout.addWidget(self._sub_stack)

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
        """Build expandable DEMO categories from the current preview values."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 12, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Easy Coding")
        title.setObjectName("titleLabel")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title)

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
        layout.addWidget(container)
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
        container = QWidget()
        self._adv_ecu_layout = QVBoxLayout(container)
        self._adv_ecu_layout.setSpacing(6)

        # Populate ECU list from mock SVT (or empty for real-car)
        # Use the MOCK_CATEGORIES-friendly list from SVT data
        self._build_ecu_tree(container)

        self._adv_ecu_layout.addStretch()
        layout.addWidget(container)
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
                # DEMO fixtures do not establish a software version. Show only
                # explicitly supplied exact identities, never a first match.
                database: CodingDatabase | None = None
                for definition in ecu.get("definitions", []):
                    try:
                        if database is None:
                            database = CodingDatabase()
                        cafd_id, variant = definition.split("-", 1)
                        database.load_ecu(cafd_id, variant)
                        fdl_funcs.extend(database.get_ecu_fdl_functions(cafd_id, variant))
                    except (OSError, ValueError, KeyError):
                        logger.warning("DEMO definition unavailable", exc_info=True)

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
        self._live_selections.clear()
        self._source_rows = []
        self._pending_plan = None
        is_demo = bool(getattr(connection, "data", None))
        self._live_unavailable = not is_demo
        self._pending = 0
        self._categories = copy.deepcopy(MOCK_CATEGORIES) if is_demo else []
        self._originals = copy.deepcopy(self._categories)
        self._is_real = False
        self._update_pending_label()
        self._write_btn.setEnabled(is_demo)
        self._write_btn.setText("Save DEMO preview" if is_demo else "Review coding changes")
        while self._sub_stack.count():
            old_page = self._sub_stack.widget(0)
            if old_page is None:
                break
            self._sub_stack.removeWidget(old_page)
            old_page.deleteLater()
        if is_demo:
            self._sub_stack.addWidget(self._build_easy_page())
            self._sub_stack.addWidget(self._build_advanced_page())
            return

        for mode in ("Easy", "Advanced"):
            page = QWidget()
            layout = QVBoxLayout(page)
            message = QLabel(
                "Reading source-selected coding definitions and stored bytes..."
                if mode == "Easy"
                else "Advanced editing is deferred. Source-backed values and easy coding are in the Easy tab."
            )
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
            or self.is_reading()
        ):
            return
        vin = getattr(connection, "verified_vin", "")
        if not vin:
            return
        worker = CodingSnapshotWorker(connection, self._snapshot_ecus, vin)
        self._coding_reader = worker
        self._snapshot_workers.append(worker)
        worker.sensitive_operation_requested.connect(self._begin_sensitive_read)
        worker.result_ready.connect(self._on_snapshot)
        worker.error.connect(self._on_snapshot_error)
        worker.finished.connect(self._on_snapshot_finished)
        self._start_loading(worker, "Reading coding values...")
        worker.start()

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
        self._on_snapshot(
            [{"name": "Coding", "state": message, "definitions": [], "blocks": {}, "backup": ""}]
        )

    @Slot()
    def _on_snapshot_finished(self) -> None:
        """Release the finished snapshot and its sensitive-session lockout."""
        worker = self.sender()
        if worker is self._coding_reader:
            self._coding_reader = None
        if isinstance(worker, CarWorker):
            self._release_source_worker(worker)
            self._finish_loading(worker)

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
        self._show_source_rows(rows)

    def _show_source_rows(self, rows: list[dict]) -> None:
        """Render source-backed values and selections without vehicle I/O."""
        self._source_rows = copy.deepcopy(rows)
        self._live_selections.clear()
        self._pending = 0
        self._update_pending_label()
        self._live_unavailable = False
        self._write_btn.setText("Review coding changes")
        self._write_btn.setEnabled(False)
        page = QWidget()
        layout = QVBoxLayout(page)
        notice = QLabel(
            "Current values use the source-selected layout for each ECU’s reported software. "
            "Conditional options retain their applicability restrictions. "
            "Choose changes, then review the freshly checked plan before writing."
        )
        notice.setWordWrap(True)
        layout.addWidget(notice)
        content = QWidget()
        entries = QVBoxLayout(content)
        for row in rows:
            label = QLabel(
                f"{row['name']}: {row['state']}\nDefinitions: {', '.join(row['definitions']) or 'Unavailable'}\nGroups read: {len(row['blocks'])}"
            )
            label.setWordWrap(True)
            entries.addWidget(label)
            for selection in row.get("definition_resolution", []):
                if selection["reported"] != selection["selected"]:
                    selected_layout = QLabel(
                        f"Compatible layout: {selection['selected']} for reported "
                        f"{selection['reported']} ({selection['method']})."
                    )
                    selected_layout.setWordWrap(True)
                    entries.addWidget(selected_layout)
            if row["backup"]:
                saved = QLabel(f"Snapshot: {row['backup']}")
                saved.setWordWrap(True)
                entries.addWidget(saved)
            if row.get("backup") and not row.get("presets"):
                unavailable = QLabel(
                    "A complete snapshot is available, but this definition has no named "
                    "easy-coding options in the supplied catalogue."
                )
                unavailable.setWordWrap(True)
                entries.addWidget(unavailable)
            for preset in row.get("presets", []):
                card = QFrame()
                card.setFrameShape(QFrame.Shape.StyledPanel)
                details = QVBoxLayout(card)
                heading = QLabel(f"{preset['label']}: {preset['current_label']}")
                heading.setWordWrap(True)
                details.addWidget(heading)
                detail = QLabel(
                    f"{preset['definition']} · {preset['section']}\n"
                    f"Options: {', '.join(preset['options']) or 'Dynamic source option'}"
                )
                detail.setWordWrap(True)
                details.addWidget(detail)
                choices = QComboBox()
                choices.addItem("Keep current value", None)
                for option in preset.get("choices", []):
                    choices.addItem(option["label"], option["name"])
                choices.setEnabled(
                    bool(row.get("backup"))
                    and preset.get("mapping_supported", False)
                    and not getattr(self._connection, "read_only", True)
                )
                key = (
                    preset["address"],
                    preset["definition"],
                    preset["id"],
                    preset["source_index"],
                )
                choices.currentIndexChanged.connect(
                    lambda index, box=choices, identity=key, current=preset["current"]: (
                        self._select_source_option(identity, box.currentData(), current)
                    )
                )
                details.addWidget(choices)
                if not preset.get("mapping_supported", False):
                    unavailable = QLabel(
                        preset.get("mapping_reason", "Option mapping is unavailable.")
                    )
                    unavailable.setWordWrap(True)
                    details.addWidget(unavailable)
                if preset["predicates"]:
                    restriction = QLabel(
                        "Applicability requires vehicle context: "
                        + "; ".join(f"{key}={value}" for key, value in preset["predicates"].items())
                    )
                    restriction.setWordWrap(True)
                    details.addWidget(restriction)
                entries.addWidget(card)
        entries.addStretch()
        layout.addWidget(content)
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
        if not getattr(self._connection, "data", None):
            logger.warning("Metadata previews cannot restore live coding")
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
        """Discard pending live selections or confirm resetting DEMO preview choices."""
        if not getattr(self._connection, "data", None):
            if not self.is_reading():
                self._show_source_rows(self._source_rows)
            return
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
        if not getattr(self._connection, "data", None):
            self._prepare_source_write()
            return
        if self._live_unavailable:
            return
        reply = QMessageBox.question(
            self,
            "Save DEMO preview",
            f"Save {self._pending} DEMO coding changes as a local preview?\n\n"
            "No vehicle backup or write is performed.",
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
            logger.info("DEMO coding preview saved")
            return

    def _save_demo_preview(self) -> bool:
        """Save a non-restorable DEMO preview, never a live ECU backup.

        Live coding uses OperationStore with complete source-bound ECU bytes,
        independently of this display-only preview.
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
            "categories": self._categories,
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
        """Populate a DEMO preview; live values use the source snapshot path."""
        if categories and getattr(self._connection, "data", None):
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

    def _select_source_option(
        self, identity: tuple[int, str, str, int], selected: Any, current: Any
    ) -> None:
        """Retain stable source option identities, preserving untouched Custom values."""
        if selected is None or selected == current:
            self._live_selections.pop(identity, None)
        else:
            self._live_selections[identity] = str(selected)
        self._pending = len(self._live_selections)
        self._pending_label.setText(f"{self._pending} pending coding change(s)")
        self._bottom_bar.setVisible(self._pending > 0)
        self._write_btn.setEnabled(bool(self._pending) and not self.is_reading())

    def _prepare_source_write(self, restore_path: Path | None = None) -> str | None:
        """Start preparation, or return a visible reason why it cannot begin."""
        from app.coding_write import CodingPrepareWorker

        connection = self._connection
        reason = ""
        if connection is None or not getattr(connection, "alive_ok", False):
            reason = "Connect to the vehicle before preparing coding or restoration."
        elif hasattr(connection, "data"):
            reason = "DEMO previews cannot prepare live coding or restoration."
        elif getattr(connection, "read_only", True):
            reason = "Coding and restoration are unavailable in a read-only connection."
        elif self.is_reading():
            reason = "Wait for the current coding read or preparation to finish, then retry."
        elif not self.can_mutate():
            reason = "Wait for the current vehicle operation to finish, then retry."
        elif self.has_unexported_results():
            reason = "Export the retained coding results before preparing another operation."
        elif not self._live_selections and restore_path is None:
            reason = "Select a coding change before preparing an operation."
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
        dialog = QDialog(self)
        dialog.setWindowTitle("Restore coding" if data["mode"] == "restore" else "Review coding")
        dialog.resize(650, 560)
        layout = QVBoxLayout(dialog)
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
        power = QCheckBox(
            "I confirm adequate vehicle and computer power throughout this operation."
        )
        layout.addWidget(power)
        prior = data.get("prior_operations", [])
        recovery = QCheckBox(
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
        restore = QCheckBox("Replace current coding with the reviewed backup values.")
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
        layout.addWidget(buttons)
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
        self._pending_label.setText(f"Coding: {report.get('state', 'unknown')}")
        self._snapshot_loaded = False
        self._live_selections.clear()
        self._pending = 0
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
