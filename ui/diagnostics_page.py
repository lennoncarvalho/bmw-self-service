"""Diagnostics page — DTC read/clear from all ECUs.

Displays fault codes with descriptions from DtcDatabase.
Inline expand/collapse for detail view. Confirmation dialog for clears.

Reference: docs/16-ui-spec.md Screen 5, docs/14-dtc-database.md
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
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.dtc_db import dtc_db
from app.worker import CarWorker

logger = logging.getLogger(__name__)


class DtcReadWorker(CarWorker):
    """Read DTCs from all provided ECUs and enrich with descriptions."""

    def __init__(self, connection: Any, ecus: list[dict]) -> None:
        super().__init__(connection)
        self.ecus = ecus

    def do_work(self) -> list[dict]:
        dtcs: list[dict] = []
        total = len(self.ecus)
        for i, ecu in enumerate(self.ecus):
            name = ecu.get("name", "ECU")
            addr_str = ecu.get("addr", "0x00")
            addr = int(addr_str, 16) if addr_str.startswith("0x") else int(addr_str)

            self.progress.emit(f"Reading {name}... ({i + 1}/{total})")

            try:
                # Extended diagnostic session
                self.connection.send_uds(addr, bytes([0x10, 0x03]))
                # Read confirmed DTCs by status mask
                resp = self.connection.send_uds(addr, bytes([0x19, 0x02, 0x08]))

                if resp[0] != 0x59:
                    continue

                # Parse: 0x59 + status_mask + [3-byte DTC + 1-byte status]*
                offset = 2
                while offset + 4 <= len(resp):
                    code = resp[offset:offset + 3].hex().upper()
                    status = resp[offset + 3]
                    description = dtc_db.describe(code) or "(no description)"
                    dtcs.append({
                        "code": code,
                        "status_byte": status,
                        "description": description,
                        "ecu_name": name,
                        "ecu_addr": addr,
                    })
                    offset += 4
            except Exception as exc:
                logger.debug("ECU 0x%02X (%s) DTC read skipped: %s", addr, name, exc)

        return dtcs


class DiagnosticsPage(QWidget):
    """Diagnostics tab — read and clear fault codes from all ECUs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._connection: Any = None
        self._ecus: list[dict] = []
        self._ecu_lookup: dict[str, str] = {}
        self._dtcs: list[dict] = []
        self._worker: DtcReadWorker | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        # Title bar with read button
        title_row = QHBoxLayout()
        title = QLabel("Fault Codes")
        title.setObjectName("titleLabel")
        title.setStyleSheet("font-size: 19px; font-weight: bold; color: #ffffff;")
        title_row.addWidget(title)
        title_row.addStretch()

        self.read_btn = QPushButton("Read DTCs")
        self.read_btn.setStyleSheet(
            "QPushButton { background: #1C69D4; color: white; border-radius: 8px; "
            "padding: 8px 20px; font-size: 14px; font-weight: bold; }"
            "QPushButton:hover { background: #0653B6; }"
            "QPushButton:disabled { background: #3a3a5a; color: #888888; }"
        )
        self.read_btn.clicked.connect(self._on_read_clicked)
        title_row.addWidget(self.read_btn)
        layout.addLayout(title_row)

        # Stack: empty state vs DTC list
        self.stack = QVBoxLayout()
        layout.addLayout(self.stack)

        # Empty state
        self.empty_state = QWidget()
        empty_layout = QVBoxLayout(self.empty_state)
        empty_layout.setAlignment(Qt.AlignCenter)
        empty_icon = QLabel(chr(0x2705))
        empty_icon.setAlignment(Qt.AlignCenter)
        empty_icon.setStyleSheet("font-size: 48px; background: transparent;")
        empty_layout.addWidget(empty_icon)
        empty_text = QLabel("No fault codes found!\nYour BMW is healthy.")
        empty_text.setAlignment(Qt.AlignCenter)
        empty_text.setStyleSheet("font-size: 16px; color: #a0a0a0;")
        empty_layout.addWidget(empty_text)
        layout.addWidget(self.empty_state)

        # DTC list container
        self.list_container = QWidget()
        self.list_container.setVisible(False)
        list_layout = QVBoxLayout(self.list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll_container = QWidget()
        self.dtc_list_layout = QVBoxLayout(scroll_container)
        self.dtc_list_layout.setSpacing(8)
        self.dtc_list_layout.addStretch()
        scroll.setWidget(scroll_container)
        list_layout.addWidget(scroll, stretch=1)

        # Clear button
        self.clear_btn = QPushButton("Clear All DTCs")
        self.clear_btn.setObjectName("dangerButton")
        self.clear_btn.setStyleSheet(
            "QPushButton { background: #E30B1F; color: white; border-radius: 8px; "
            "padding: 10px 24px; font-size: 14px; font-weight: bold; }"
            "QPushButton:hover { background: #C40A1A; }"
            "QPushButton:disabled { background: #3a3a5a; color: #888888; }"
        )
        self.clear_btn.clicked.connect(self._on_clear_clicked)
        self.clear_btn.setVisible(False)
        list_layout.addWidget(self.clear_btn, alignment=Qt.AlignCenter)

        layout.addWidget(self.list_container)

    def set_connection(self, connection: Any, ecus: list[dict]) -> None:
        """Set the active connection and ECU list, then auto-read DTCs."""
        self._connection = connection
        self._ecus = ecus
        # Build ECU name lookup map for detail view
        self._ecu_lookup = {e.get("name", ""): e.get("description", "") for e in ecus}
        self._read_dtcs()

    def _on_read_clicked(self) -> None:
        if self._connection is None:
            return
        self._read_dtcs()

    def _read_dtcs(self) -> None:
        """Read DTCs from all ECUs via CarWorker."""
        if self._connection is None:
            return
        self.read_btn.setEnabled(False)

        if hasattr(self._connection, "data") and self._connection.data:
            # Mock path — read directly from canned data
            self._on_dtcs_loaded(self._connection.data.get("dtcs", []))
            return

        # Real car: use CarWorker
        ecus = self._ecus if self._ecus else [{"name": "ZGW", "addr": "0x10"}]
        self._worker = DtcReadWorker(self._connection, ecus)
        self._worker.started.connect(lambda: self.read_btn.setEnabled(False))
        self._worker.finished.connect(self._on_dtcs_loaded)
        self._worker.error.connect(self._on_dtc_error)
        self._worker.start()

    def _on_dtcs_loaded(self, dtcs: list[dict]) -> None:
        """Display the DTC list after reading."""
        self._dtcs = dtcs
        self.read_btn.setEnabled(True)

        # Clean existing cards
        while self.dtc_list_layout.count() > 1:
            item = self.dtc_list_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        if not dtcs:
            self.empty_state.setVisible(True)
            self.list_container.setVisible(False)
            return

        self.empty_state.setVisible(False)
        self.list_container.setVisible(True)
        self.clear_btn.setVisible(True)

        for dtc in dtcs:
            code = dtc.get("code", "???")
            desc = dtc.get("description", dtc.get("description", "(no description)"))
            status = dtc.get("status_byte", 0)
            ecu = dtc.get("ecu_name", "Unknown")

            # Summary row
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

            top_row = QHBoxLayout()
            code_label = QLabel(code)
            code_label.setStyleSheet(
                "font-size: 15px; font-weight: bold; color: #1C69D4; background: transparent;"
            )
            top_row.addWidget(code_label)
            top_row.addStretch()

            expand_arrow = QLabel("▶")
            expand_arrow.setStyleSheet("font-size: 12px; color: #a0a0a0; background: transparent;")
            top_row.addWidget(expand_arrow)
            card_layout.addLayout(top_row)

            desc_label = QLabel(desc[:100])
            desc_label.setStyleSheet("font-size: 13px; color: #e0e0e0; background: transparent;")
            desc_label.setWordWrap(True)
            card_layout.addWidget(desc_label)

            meta = QLabel(f"ECU: {ecu}  |  Status: 0x{status:02X}")
            meta.setStyleSheet("font-size: 11px; color: #a0a0a0; background: transparent;")
            card_layout.addWidget(meta)

            # Detail section (hidden by default)
            detail = QWidget()
            detail.setVisible(False)
            detail_layout = QVBoxLayout(detail)
            detail_layout.setContentsMargins(0, 8, 0, 0)
            detail_layout.setSpacing(6)

            # G-10: Full description
            full_desc = QLabel(dtc_db.describe(code) or desc)
            full_desc.setWordWrap(True)
            full_desc.setStyleSheet(
                "font-size: 13px; color: #e0e0e0; background: transparent;"
            )
            detail_layout.addWidget(full_desc)

            # G-10: Status byte decoded
            status_text = _decode_dtc_status(status)
            status_lbl = QLabel(f"Status: 0x{status:02X} — {status_text}")
            status_lbl.setStyleSheet(
                "font-size: 12px; color: #F39C12; background: transparent;"
            )
            detail_layout.addWidget(status_lbl)

            # G-10: Fault type from database
            ft = dtc_db.fault_type(f"{status:02X}")
            if ft:
                ft_lbl = QLabel(f"Fault type: {ft}")
                ft_lbl.setStyleSheet(
                    "font-size: 12px; color: #a0a0a0; background: transparent;"
                )
                detail_layout.addWidget(ft_lbl)

            # G-10: ECU full name if available
            ecu_full = self._ecu_lookup.get(ecu, ecu)
            if ecu_full and ecu_full != ecu:
                ecu_lbl = QLabel(f"ECU: {ecu_full}")
                ecu_lbl.setStyleSheet(
                    "font-size: 12px; color: #a0a0a0; background: transparent;"
                )
                detail_layout.addWidget(ecu_lbl)

            # Buttons row
            btn_row = QHBoxLayout()
            btn_row.setSpacing(8)

            search_btn = QPushButton(f'Search Web for "{code} BMW"')
            search_btn.setStyleSheet(
                "QPushButton { background: transparent; color: #1C69D4; border: 1px solid #1C69D4; "
                "border-radius: 6px; padding: 4px 12px; font-size: 11px; }"
                "QPushButton:hover { background: rgba(28,105,212,0.15); }"
            )
            search_btn.clicked.connect(
                lambda checked, c=code: self._open_search(checked, c)
            )
            btn_row.addWidget(search_btn)

            # G-10: Per-DTC clear button
            clear_one_btn = QPushButton(f"Clear {code}")
            clear_one_btn.setStyleSheet(
                "QPushButton { background: transparent; color: #E30B1F; "
                "border: 1px solid #E30B1F; border-radius: 6px; "
                "padding: 4px 12px; font-size: 11px; }"
                "QPushButton:hover { background: rgba(227,11,31,0.15); }"
            )
            clear_one_btn.clicked.connect(
                lambda checked, c=code, a=dtc.get("ecu_addr", 0x10): (
                    self._on_clear_single(c, a)
                )
            )
            btn_row.addWidget(clear_one_btn)
            btn_row.addStretch()
            detail_layout.addLayout(btn_row)
            card_layout.addWidget(detail)

            # Click card to toggle detail
            card.mousePressEvent = lambda e, d=detail, a=expand_arrow: self._toggle_detail(d, a)

            self.dtc_list_layout.insertWidget(self.dtc_list_layout.count() - 1, card)

    @staticmethod
    def _toggle_detail(detail: QWidget, arrow: QLabel) -> None:
        detail.setVisible(not detail.isVisible())
        arrow.setText("▼" if detail.isVisible() else "▶")

    def _on_dtc_error(self, msg: str) -> None:
        self.read_btn.setEnabled(True)
        QMessageBox.warning(self, "DTC Read Failed", msg)

    def _on_clear_clicked(self) -> None:
        reply = QMessageBox.question(
            self,
            "Clear All DTCs",
            "Clear all fault codes from all ECUs?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if self._connection is None:
            return

        self.clear_btn.setEnabled(False)

        if hasattr(self._connection, "data") and self._connection.data:
            # Mock path
            self._connection.data["dtcs"] = []
            self._on_dtcs_loaded([])
            self.clear_btn.setEnabled(True)
            return

        # Real car: send 0x14 FF FF FF to each ECU via background worker
        class ClearWorker(CarWorker):
            def __init__(self, conn, ecus):
                super().__init__(conn)
                self.ecus = ecus

            def do_work(self) -> dict:
                cleared: list[str] = []
                failed: list[str] = []
                for ecu in self.ecus:
                    addr_str = ecu.get("addr", "0x10")
                    addr = int(addr_str, 16) if addr_str.startswith("0x") else int(addr_str)
                    name = ecu.get("name", "ECU")
                    self.progress.emit(f"Clearing {name}...")
                    try:
                        resp = self.connection.send_uds(
                            addr, bytes([0x14, 0xFF, 0xFF, 0xFF])
                        )
                        # Check for negative response (0x7F)
                        if resp and resp[0] == 0x7F:
                            failed.append(name)
                        else:
                            cleared.append(name)
                    except Exception:
                        failed.append(name)
                return {"cleared": cleared, "failed": failed}

        self._worker = ClearWorker(self._connection, self._ecus)
        self._worker.finished.connect(self._on_clear_complete)
        self._worker.error.connect(self._on_dtc_error)
        self._worker.start()

    def _on_clear_complete(self, result: dict | None = None) -> None:
        """Re-read DTCs after a successful clear, report per-ECU results."""
        self.clear_btn.setEnabled(True)
        if result:
            cleared = result.get("cleared", [])
            failed = result.get("failed", [])
            if failed:
                QMessageBox.information(
                    self,
                    "Clear DTCs",
                    f"Cleared: {len(cleared)} ECUs\n"
                    f"Failed: {len(failed)} ({', '.join(failed)})",
                )
        self._read_dtcs()

    @staticmethod
    def _open_search(checked: bool, code: str) -> None:
        import webbrowser
        webbrowser.open(f"https://www.google.com/search?q={code}+BMW")

    def _on_clear_single(self, code: str, ecu_addr: int = 0x10) -> None:
        """Clear a single DTC from its ECU.

        Matches by both DTC code and ECU address to distinguish
        duplicate codes across different ECUs (e.g. B7F805 on HU_NBT vs FEM).
        """
        dtc = next(
            (d for d in self._dtcs
             if d.get("code") == code and d.get("ecu_addr") == ecu_addr),
            None,
        )
        if dtc is None or self._connection is None:
            return
        addr = dtc.get("ecu_addr", 0x10)
        reply = QMessageBox.question(
            self,
            f"Clear {code}",
            f"Clear fault code {code} from {dtc.get('ecu_name', 'ECU')}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        if hasattr(self._connection, "data") and self._connection.data:
            self._connection.data["dtcs"] = [
                d for d in self._connection.data.get("dtcs", []) if d.get("code") != code
            ]
        else:
            try:
                # Clear the specific DTC: 0x14 + 3-byte DTC code
                code_clean = code.upper().replace("0X", "").replace("0x", "")
                if len(code_clean) % 2 != 0:
                    code_clean = "0" + code_clean  # pad odd-length (e.g. P0300)
                dtc_bytes = bytes.fromhex(code_clean)
                if len(dtc_bytes) < 3:
                    dtc_bytes = dtc_bytes.rjust(3, b'\x00')
                self._connection.send_uds(addr, bytes([0x14]) + dtc_bytes[:3])
            except Exception as e:
                QMessageBox.warning(self, "Clear Failed", str(e))
        self._read_dtcs()


# ---- Helpers ----

def _decode_dtc_status(status: int) -> str:
    """Decode a UDS DTC status byte into human-readable text."""
    parts: list[str] = []
    if status & 0x01:
        parts.append("Warning requested")
    if status & 0x02:
        parts.append("Pending")
    if status & 0x08:
        parts.append("Confirmed")
    if status & 0x10:
        parts.append("Test failed since last clear")
    if status & 0x20:
        parts.append("Test failed this cycle")
    if status & 0x40:
        parts.append("Pending DTC")
    if status & 0x80:
        parts.append("Intermittent")
    return ", ".join(parts) if parts else "No status bits set"
