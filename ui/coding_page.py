"""Coding page — Easy + Advanced coding with write/clear bar.

Easy: curated category -> option toggles.
Advanced: SVT ECU tree -> FDL hex editor (stub).

Reference: docs/16-ui-spec.md Screens 7, 8, 9
"""

import logging
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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

logger = logging.getLogger(__name__)

MOCK_CATEGORIES = [
    {
        "name": "Lighting",
        "icon": "L",
        "description": "Angel eyes brightness, welcome lights, DRL behavior",
        "options": [
            {"name": "Angel Eyes Brightness", "values": ["4%", "8%", "12%", "16%", "20%"], "current": 1},
            {"name": "Welcome Lights Duration", "values": ["10s", "20s", "30s", "40s"], "current": 2},
            {"name": "DRL Rear Lights", "values": ["Off", "On"], "current": 0},
        ],
    },
    {
        "name": "Comfort",
        "icon": "C",
        "description": "Fold mirrors, window control, seat heating memory",
        "options": [
            {"name": "Fold Mirrors on Lock", "values": ["Off", "On (hold)", "On (instant)"], "current": 1},
            {"name": "Window Control after Ignition Off", "values": ["Disabled", "30s", "60s", "Unlimited"], "current": 2},
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

                for v_i, v_name in enumerate(opt["values"]):
                    rb = QRadioButton(f"  {v_name}")
                    rb.setStyleSheet(
                        "QRadioButton { color: #a0a0a0; spacing: 8px; }"
                        "QRadioButton::indicator { width: 14px; height: 14px; }"
                    )
                    rb.setChecked(v_i == opt["current"])
                    rb.toggled.connect(
                        lambda checked, lbl=opt_lbl, o=opt,
                               vi=v_i, nm=v_name: (
                            self._apply_option(o, vi, nm, lbl, checked)
                            if checked else None
                        )
                    )
                    opts_layout.addWidget(rb)

            card_layout.addWidget(opts_widget)

            # Toggle expand on card click
            card.mousePressEvent = lambda e, ow=opts_widget: (
                ow.setVisible(not ow.isVisible())
            )

            cat_layout.addWidget(card)

        cat_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)
        return page

    def _build_advanced_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)
        warning = QLabel(
            "Advanced Coding\n\n"
            + chr(0x26A0)
            + " Use with caution "
            + chr(0x26A0)
        )
        warning.setAlignment(Qt.AlignCenter)
        warning.setStyleSheet("font-size: 16px; color: #F39C12;")
        layout.addWidget(warning)

        detail = QLabel("Full ECU tree and FDL hex editor coming soon.")
        detail.setAlignment(Qt.AlignCenter)
        detail.setStyleSheet("font-size: 13px; color: #a0a0a0;")
        layout.addWidget(detail)
        return page

    def set_connection(self, connection: Any) -> None:
        self._connection = connection

    def _apply_option(
        self, opt: dict, idx: int, name: str, label: QLabel, checked: bool
    ) -> None:
        if not checked:
            return
        opt["current"] = idx
        self._pending += 1
        val = opt["values"][idx]
        label.setText(f"{opt['name']}: {val}")
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

        # Mock: simulate write
        self._pending = 0
        self._update_pending_label()
        logger.info("Coding changes written (mock)")