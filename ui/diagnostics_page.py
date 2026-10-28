"""Diagnostics page — DTC read/clear from all ECUs.

Displays fault codes with descriptions from DtcDatabase.
Inline expand/collapse for detail view. Confirmation dialog for clears.

Reference: docs/16-ui-spec.md Screen 5, docs/14-dtc-database.md
"""

import logging
from threading import Event
from typing import Any

from PySide6.QtCore import Qt, Signal
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

from app.dtc_db import DtcDatabase
from app.protocol.contracts import OperationContext
from app.resources import resource_path
from app.uds import UdsServices, decode_dtc_records
from app.worker import CarWorker

logger = logging.getLogger(__name__)


class DtcReadWorker(CarWorker):
    """Read DTCs from all provided ECUs and enrich with descriptions.

    T-14: Emits ``ecu_timeout`` signal when an ECU times out.
    The UI slot sets ``self._timeout_action`` to 'skip', 'retry', or 'abort'
    and then sets ``self._timeout_event`` to unblock the worker thread.

    Signals:
        ecu_timeout(str): Emitted with ECU name when 30s timeout expires.
    """

    ecu_timeout = Signal(str)
    mil_status = Signal(bool, int)  # T-9: MIL on/off, DTC count

    def __init__(self, connection: Any, ecus: list[dict], *, coverage_known: bool = True) -> None:
        """Initialize diagnostic state and ownership for the supplied connection or page parent."""
        super().__init__(connection)
        self.ecus = ecus
        self.coverage_known = coverage_known
        self._timeout_event = Event()
        self._timeout_action = "abort"

    def requestInterruption(self) -> None:
        """Wake an ECU timeout prompt wait as well as any bounded socket read."""
        self._timeout_action = "abort"
        self._timeout_event.set()
        super().requestInterruption()

    def _handle_timeout(self, ecu_name: str) -> str:
        """Block until the UI thread decides: skip, retry, or abort."""
        if self.isInterruptionRequested() or not getattr(self.connection, "alive_ok", True):
            return "abort"
        self._timeout_event.clear()
        self._timeout_action = "abort"  # default if UI never responds
        self.ecu_timeout.emit(ecu_name)
        # Wait up to 60s for UI response — if UI never responds, abort
        import time

        deadline = time.monotonic() + 60.0
        while not self._timeout_event.wait(0.05):
            if self.isInterruptionRequested() or time.monotonic() >= deadline:
                return "abort"
        return self._timeout_action

    def do_work(self) -> dict:
        """Own and close description lookups on this background thread."""
        database = DtcDatabase(str(resource_path("dtc_descriptions.db")))
        try:
            return self._read_dtcs(database)
        finally:
            database.conn.close()

    def _read_dtcs(self, database: DtcDatabase) -> dict:
        """Read confirmed fault records with this worker-owned database and explicit coverage."""
        logger.info("DTC scan start ecus=%d coverage_known=%s", len(self.ecus), self.coverage_known)
        dtcs: list[dict] = []
        complete = self.coverage_known
        total = len(self.ecus)
        i = 0
        retries: dict[str, int] = {}
        while i < len(self.ecus):
            if self.isInterruptionRequested():
                complete = False
                break
            ecu = self.ecus[i]
            name = ecu.get("name", "ECU")
            addr_str = ecu.get("addr", "0x00")
            addr = int(addr_str, 16) if addr_str.startswith("0x") else int(addr_str)

            self.progress.emit(f"Reading {name}... ({i + 1}/{total})")

            try:
                if hasattr(self.connection, "run_operation"):

                    def read_ecu(services: UdsServices, ctx: OperationContext) -> bytes:
                        services.change_session(3, ctx)
                        return services.read_dtcs(0x08, ctx)

                    resp = self.connection.run_operation(
                        addr, read_ecu, context=self.connection.context(30.0)
                    )
                else:
                    self.connection.send_uds(addr, b"\x10\x03")
                    resp = self.connection.send_uds(addr, b"\x19\x02\x08")

                if len(resp) < 3 or resp[:2] != b"\x59\x02" or (len(resp) - 3) % 4:
                    raise ValueError("Invalid or negative ReadDTCInformation response")

                if not resp[2] & 0x08:
                    raise ValueError("ECU does not support the requested confirmed-DTC status")
                # 59 02 availability-mask, then [DTC:3, status:1] records.
                for code_id, status in decode_dtc_records(resp):
                    code = f"{code_id:06X}"
                    description = (
                        database.describe_for_ecu(code, name) or "(description unavailable)"
                    )
                    dtcs.append(
                        {
                            "code": code,
                            "status_byte": status,
                            "description": description,
                            "ecu_name": name,
                            "ecu_addr": addr,
                        }
                    )
                i += 1
                retries.pop(name, None)

                logger.info("DTC read complete ecu=%s address=0x%04X", name, addr)

            except TimeoutError:
                # T-14: Ask UI what to do
                action = self._handle_timeout(name)
                if action == "skip":
                    complete = False
                    i += 1
                    continue
                elif action == "retry":
                    retries[name] = retries.get(name, 0) + 1
                    if retries[name] > 3:
                        logger.warning("ECU %s: max retries exceeded, skipping", name)
                        complete = False
                        i += 1
                    # Don't increment i — retry the same ECU
                    continue
                else:  # abort
                    complete = False
                    break

            except Exception:
                complete = False
                logger.warning(
                    "DTC read unavailable ecu=%s address=0x%04X", name, addr, exc_info=True
                )
                i += 1

        logger.info("DTC scan end dtcs=%d complete=%s", len(dtcs), complete)
        return {"dtcs": dtcs, "complete": complete}


class DiagnosticsPage(QWidget):
    """Diagnostics tab — read and clear fault codes from all ECUs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize diagnostic state and ownership for the supplied connection or page parent."""
        super().__init__(parent)
        self._connection: Any = None
        self._ecus: list[dict] = []
        self._ecu_lookup: dict[str, str] = {}
        self._dtcs: list[dict] = []
        self._worker: CarWorker | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build diagnostic result, unknown-state and operation controls in the page."""
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

        # T-9: MIL (Check Engine) status indicator
        mil_row = QHBoxLayout()
        self._mil_indicator = QLabel("")
        self._mil_indicator.setStyleSheet("font-size: 32px; background: transparent;")
        mil_row.addWidget(self._mil_indicator)
        self._mil_label = QLabel("MIL status unavailable until the vehicle endpoint is verified")
        self._mil_label.setStyleSheet("font-size: 13px; color: #a0a0a0; background: transparent;")
        mil_row.addWidget(self._mil_label)
        mil_row.addStretch()
        layout.addLayout(mil_row)

        # Stack: empty state vs DTC list
        self.stack = QVBoxLayout()
        layout.addLayout(self.stack)

        # Empty state
        self.empty_state = QWidget()
        empty_layout = QVBoxLayout(self.empty_state)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_icon = QLabel(chr(0x1F50D))
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_icon.setStyleSheet("font-size: 48px; background: transparent;")
        empty_layout.addWidget(empty_icon)
        empty_text = QLabel("No DTC scan results yet.")
        self._empty_text = empty_text
        empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        list_layout.addWidget(self.clear_btn, alignment=Qt.AlignmentFlag.AlignCenter)

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
        self._empty_text.setText("Reading confirmed fault codes...")
        self.empty_state.setVisible(True)
        self.list_container.setVisible(False)
        self._mil_indicator.setText("")
        self._mil_label.setText("MIL unavailable: vehicle endpoint has not been verified")

        if hasattr(self._connection, "data") and self._connection.data:
            # Mock path — read directly from canned data
            self._on_dtcs_loaded(self._connection.data.get("dtcs", []))
            self._update_mil(False, 0)  # Mock: no MIL
            return

        # T-9: Read MIL status alongside DTCs — now done inside DtcReadWorker
        # so it runs on the background thread, not the UI thread.

        # Real car: use CarWorker
        ecus = (
            self._ecus
            if self._ecus
            else [{"name": "Gateway", "addr": hex(getattr(self._connection, "entity", 0x10))}]
        )
        worker = DtcReadWorker(self._connection, ecus, coverage_known=bool(self._ecus))
        self._worker = worker
        worker.started.connect(lambda: self.read_btn.setEnabled(False))
        worker.result_ready.connect(self._on_dtcs_loaded)
        worker.error.connect(self._on_dtc_error)
        # Capture worker ref at connect time so timeout handler always
        # references the correct DtcReadWorker, even if clear starts mid-read.
        worker.ecu_timeout.connect(lambda name, w=worker: self._on_ecu_timeout(name, w))
        worker.mil_status.connect(self._update_mil)
        worker.start()

    def _on_ecu_timeout(self, ecu_name: str, worker: "DtcReadWorker | None" = None) -> None:
        """T-14: Handle ECU timeout — show Skip/Retry/Abort dialog.

        Runs on the main thread. Sets the worker's _timeout_action and
        _timeout_event to unblock the worker thread.
        The worker parameter is captured at connect time to avoid
        reading self._worker which may have changed (e.g. clear started).
        """
        if (
            worker is None
            or worker.connection is not self._connection
            or worker.isInterruptionRequested()
        ):
            return
        msg = QMessageBox(self)
        msg.setWindowTitle("ECU Timeout")
        msg.setText(f"ECU {ecu_name} is not responding.")
        msg.setInformativeText("What would you like to do?")
        skip_btn = msg.addButton("Skip", QMessageBox.ButtonRole.AcceptRole)
        retry_btn = msg.addButton("Retry", QMessageBox.ButtonRole.ActionRole)
        msg.addButton("Abort", QMessageBox.ButtonRole.RejectRole)
        msg.setDefaultButton(skip_btn)
        msg.exec()

        clicked = msg.clickedButton()
        if clicked == skip_btn:
            worker._timeout_action = "skip"
        elif clicked == retry_btn:
            worker._timeout_action = "retry"
        else:
            worker._timeout_action = "abort"
        worker._timeout_event.set()

    def _on_dtcs_loaded(self, result: object) -> None:
        """Display the DTC list after reading."""
        sender = self.sender()
        if isinstance(sender, CarWorker) and sender.connection is not self._connection:
            return
        # Handle both legacy list format and new dict format
        if isinstance(result, dict):
            dtcs = result.get("dtcs", [])
            complete = result.get("complete", True)
        else:
            dtcs = result if isinstance(result, list) else []
            complete = True
        self._dtcs = dtcs
        self.read_btn.setEnabled(True)

        # Clean existing cards
        while self.dtc_list_layout.count() > 1:
            item = self.dtc_list_layout.takeAt(0)
            if item is None:
                continue
            child = item.widget()
            if child is not None:
                child.deleteLater()

        if not dtcs:
            if not complete:
                # Scan was aborted before all ECUs were read — don't claim healthy
                self.empty_state.setVisible(False)
                aborted_lbl = QLabel(
                    "DTC scan incomplete.\nSome ECUs were unavailable or not checked."
                )
                aborted_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                aborted_lbl.setStyleSheet("font-size: 14px; color: #F39C12; padding: 24px;")
                self.dtc_list_layout.insertWidget(self.dtc_list_layout.count() - 1, aborted_lbl)
                self.list_container.setVisible(True)
            else:
                self._empty_text.setText(
                    "No confirmed fault codes returned by the ECUs checked.\n"
                    "This does not establish overall vehicle health."
                )
                self.empty_state.setVisible(True)
                self.list_container.setVisible(False)
            return

        self.empty_state.setVisible(False)
        self.list_container.setVisible(True)
        self.clear_btn.setVisible(not getattr(self._connection, "read_only", False))

        if not complete:
            warn = QLabel(
                "\u26a0 DTC scan incomplete — showing partial results. Some ECUs were unavailable or not checked."
            )
            warn.setStyleSheet(
                "font-size: 12px; color: #F39C12; background: "
                "rgba(243,156,18,0.1); border: 1px solid #F39C12; "
                "border-radius: 6px; padding: 6px 12px;"
            )
            warn.setWordWrap(True)
            self.dtc_list_layout.insertWidget(self.dtc_list_layout.count() - 1, warn)

        for dtc in dtcs:
            code = dtc.get("code", "???")
            desc = dtc.get("description", dtc.get("description", "(no description)"))
            status = dtc.get("status_byte", 0)
            ecu = dtc.get("ecu_name", "Unknown")

            # Summary row
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
            full_desc = QLabel(desc)
            full_desc.setWordWrap(True)
            full_desc.setStyleSheet("font-size: 13px; color: #e0e0e0; background: transparent;")
            detail_layout.addWidget(full_desc)

            # G-10: Status byte decoded
            status_text = _decode_dtc_status(status)
            status_lbl = QLabel(f"Status: 0x{status:02X} — {status_text}")
            status_lbl.setStyleSheet("font-size: 12px; color: #F39C12; background: transparent;")
            detail_layout.addWidget(status_lbl)

            # G-10: ECU full name if available
            ecu_full = self._ecu_lookup.get(ecu, ecu)
            if ecu_full and ecu_full != ecu:
                ecu_lbl = QLabel(f"ECU: {ecu_full}")
                ecu_lbl.setStyleSheet("font-size: 12px; color: #a0a0a0; background: transparent;")
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
            search_btn.clicked.connect(lambda checked, c=code: self._open_search(checked, c))
            btn_row.addWidget(search_btn)

            btn_row.addStretch()
            detail_layout.addLayout(btn_row)
            card_layout.addWidget(detail)

            # Click card to toggle detail
            def _toggle_on_click(
                event: object,
                d: QWidget = detail,
                a: QLabel = expand_arrow,
            ) -> None:
                self._toggle_detail(d, a)

            card.mousePressEvent = _toggle_on_click  # type: ignore[method-assign]

            self.dtc_list_layout.insertWidget(self.dtc_list_layout.count() - 1, card)

    @staticmethod
    def _toggle_detail(detail: QWidget, arrow: QLabel) -> None:
        detail.setVisible(not detail.isVisible())
        arrow.setText("▼" if detail.isVisible() else "▶")

    def _on_dtc_error(self, msg: str) -> None:
        """Report an unavailable scan without leaving stale results or a healthy-car claim."""
        sender = self.sender()
        if isinstance(sender, CarWorker) and sender.connection is not self._connection:
            return
        self.read_btn.setEnabled(True)
        self._empty_text.setText("DTC scan unavailable. See the session log for details.")
        self.empty_state.setVisible(True)
        self.list_container.setVisible(False)
        QMessageBox.warning(self, "DTC Read Failed", msg)

    def _on_clear_clicked(self) -> None:
        """Confirm fault clearing only when the active session permits mutations."""
        if getattr(self._connection, "read_only", False):
            return
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
                """Initialize diagnostic state and ownership for the supplied connection or page parent."""
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
                        resp = self.connection.send_uds(addr, bytes([0x14, 0xFF, 0xFF, 0xFF]))
                        # Check for negative response (0x7F)
                        if resp == b"\x54":
                            cleared.append(name)
                        else:
                            failed.append(name)
                    except Exception:
                        failed.append(name)
                return {"cleared": cleared, "failed": failed}

        clear_worker = ClearWorker(self._connection, self._ecus)
        self._worker = clear_worker
        clear_worker.result_ready.connect(self._on_clear_complete)
        clear_worker.error.connect(self._on_dtc_error)
        clear_worker.start()

    def _on_clear_complete(self, result: dict | None = None) -> None:
        """Re-read DTCs after a successful clear, report per-ECU results."""
        sender = self.sender()
        if isinstance(sender, CarWorker) and sender.connection is not self._connection:
            return
        self.clear_btn.setEnabled(True)
        if result:
            cleared = result.get("cleared", [])
            failed = result.get("failed", [])
            if failed:
                QMessageBox.information(
                    self,
                    "Clear DTCs",
                    f"Clear requests accepted: {len(cleared)} ECUs\nFailed: {len(failed)} ({', '.join(failed)})",
                )
        self._read_dtcs()

    @staticmethod
    def _open_search(checked: bool, code: str) -> None:
        import webbrowser

        webbrowser.open(f"https://www.google.com/search?q={code}+BMW")

    # ── T-9: MIL status (updated from DtcReadWorker.mil_status signal) ─

    def _update_mil(self, mil_on: bool, dtc_count: int) -> None:
        """Update the MIL indicator on the UI thread."""
        if mil_on:
            self._mil_indicator.setText(chr(0x1F6A8))  # 🚨
            self._mil_label.setText(f"Check Engine Light ON — {dtc_count} code(s) stored")
            self._mil_label.setStyleSheet(
                "font-size: 13px; color: #E30B1F; font-weight: bold; background: transparent;"
            )
        else:
            self._mil_indicator.setText(chr(0x2705))  # ✅
            self._mil_label.setText("No Check Engine Light — MIL off")
            self._mil_label.setStyleSheet(
                "font-size: 13px; color: #2ECC71; background: transparent;"
            )


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
