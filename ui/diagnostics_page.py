"""Diagnostics page — DTC read/clear from all ECUs.

Displays fault codes with descriptions from DtcDatabase.
Inline expand/collapse for detail view. Confirmation dialog for clears.

Reference: docs/16-ui-spec.md Screen 5, docs/14-dtc-database.md
"""

import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt, Signal, Slot
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

from app.diagnostics import DiagnosticClearWorker, DiagnosticReadWorker
from app.worker import CarWorker

logger = logging.getLogger(__name__)


class DiagnosticsPage(QWidget):
    """Diagnostics tab — read and clear fault codes from all ECUs."""

    mutation_active = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize diagnostic state and ownership for the supplied connection or page parent."""
        super().__init__(parent)
        self._connection: Any = None
        self._ecus: list[dict] = []
        self._ecu_lookup: dict[str, str] = {}
        self._dtcs: list[dict] = []
        self._coverage: list[dict] = []
        self._retired: list[CarWorker] = []
        self._loaded = False
        self._inventory_revision = 0
        self.can_mutate: Callable[[], bool] = lambda: True
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
        self._operation_progress = QLabel("")
        self._operation_progress.setWordWrap(True)
        layout.addWidget(self._operation_progress)

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
        """Replace settled targets and invalidate results from the previous inventory."""
        self._inventory_revision += 1
        self._connection = connection
        self._ecus = [dict(ecu) for ecu in ecus]
        # Build ECU name lookup map for detail view
        self._ecu_lookup = {e.get("name", ""): e.get("description", "") for e in ecus}
        self._loaded = False
        self._coverage = []
        self._dtcs = []
        self.read_btn.setEnabled(self._worker is None)
        self.clear_btn.setEnabled(False)
        self._empty_text.setText("Open Diagnostics to read vehicle fault memories.")
        self.empty_state.setVisible(True)
        self.list_container.setVisible(False)
        if hasattr(connection, "data"):
            self.activate()

    def activate(self) -> None:
        """Load this page once, publishing the full initial batch together."""
        if not self._loaded and self._worker is None:
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

        if hasattr(self._connection, "data") and self._connection.data:
            # Mock path — read directly from canned data
            self._on_dtcs_loaded(self._connection.data.get("dtcs", []))
            return

        worker = DiagnosticReadWorker(self._connection, self._ecus, coverage_known=bool(self._ecus))
        self._worker = worker
        worker.setProperty("inventory_revision", self._inventory_revision)
        self._retired.append(worker)
        worker.result_ready.connect(self._on_dtcs_loaded)
        worker.progress.connect(self._operation_progress.setText)
        worker.error.connect(self._on_dtc_error)
        worker.finished.connect(self._on_worker_finished)
        worker.start()

    @Slot()
    def _on_worker_finished(self) -> None:
        worker = self.sender()
        if worker is self._worker:
            self._worker = None
            self.read_btn.setEnabled(self._connection is not None)
        if isinstance(worker, CarWorker):
            if worker in self._retired:
                self._retired.remove(worker)
            if not worker.property("retired_by_main"):
                worker.deleteLater()

    def _on_dtcs_loaded(self, result: object) -> None:
        """Display the DTC list after reading."""
        sender = self.sender()
        if isinstance(sender, CarWorker) and sender.connection is not self._connection:
            return
        if isinstance(sender, DiagnosticReadWorker) and (
            sender.property("inventory_revision") != self._inventory_revision
        ):
            return
        # Handle both legacy list format and new dict format
        if isinstance(result, dict):
            dtcs = result.get("dtcs", [])
            complete = result.get("complete", True)
            self._coverage = result.get("coverage", [])
        else:
            dtcs = result if isinstance(result, list) else []
            complete = True
        self._operation_progress.setText("Read batch complete")
        self._dtcs = dtcs
        self._loaded = True
        self.read_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)

        # Clean existing cards
        while self.dtc_list_layout.count() > 1:
            item = self.dtc_list_layout.takeAt(0)
            if item is None:
                continue
            child = item.widget()
            if child is not None:
                child.deleteLater()

        self.empty_state.setVisible(False)
        self.list_container.setVisible(True)
        self.clear_btn.setVisible(not getattr(self._connection, "read_only", False))
        self.clear_btn.setEnabled(
            any(e.get("identified") and e.get("uds") for e in self._ecus)
            or hasattr(self._connection, "data")
        )
        if self._coverage:
            lines = [f"{r['name']} / {r['memory']}: {r['state']}" for r in self._coverage]
            summary = QLabel(
                ("Scan complete" if complete else "Scan incomplete")
                + (
                    " — installed topology unavailable; catalogue candidates only"
                    if isinstance(result, dict) and not result.get("topology_known", True)
                    else ""
                )
                + "\n"
                + "\n".join(lines)
            )
            summary.setWordWrap(True)
            self.dtc_list_layout.insertWidget(self.dtc_list_layout.count() - 1, summary)
        if not dtcs:
            label = QLabel(
                "No faults returned by the memories read."
                if complete
                else "No faults returned; some targets or memories could not be read."
            )
            label.setWordWrap(True)
            self.dtc_list_layout.insertWidget(self.dtc_list_layout.count() - 1, label)

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

            meta = QLabel(f"ECU: {ecu}  |  {dtc.get('memory', 'Fault')}  |  Status: 0x{status:02X}")
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
        if isinstance(sender, DiagnosticReadWorker) and (
            sender.property("inventory_revision") != self._inventory_revision
        ):
            return
        self.read_btn.setEnabled(True)
        self._empty_text.setText("DTC scan unavailable. See the session log for details.")
        self.empty_state.setVisible(True)
        self.list_container.setVisible(False)
        QMessageBox.warning(self, "DTC Read Failed", msg)

    def _on_clear_clicked(self) -> None:
        """Confirm one definitive clear, including scan gaps and permanent-memory limits."""
        if (
            self._connection is None
            or self._worker is not None
            or getattr(self._connection, "read_only", False)
        ):
            return
        if not self.can_mutate():
            QMessageBox.information(
                self,
                "Vehicle read in progress",
                "Wait for the current vehicle read to finish before clearing faults.",
            )
            return
        gaps = [
            f"{r['name']} / {r['memory']}: {r['state']}"
            for r in self._coverage
            if r["state"] not in ("read", "unsupported", "not-applicable")
        ]
        prompt = (
            "Clear all supported Fault and Information memories? Permanent faults are not cleared by this operation.\n\n"
            "This cannot be undone or cancelled once started. Keep the car and computer powered, ignition on and cable connected.\n"
        )
        if any(ecu.get("origin") == "catalogue" for ecu in self._ecus):
            prompt += (
                "\nInstalled topology is unavailable. Catalogue candidates are not a complete "
                "vehicle inventory; only identified supported targets can be cleared.\n"
            )
        if gaps:
            prompt += "\nScan gaps:\n" + "\n".join(gaps)
        connection = self._connection
        if (
            QMessageBox.question(
                self,
                "Clear All DTCs",
                prompt,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        if self._connection is not connection or self._worker is not None:
            return
        if hasattr(connection, "data"):
            connection.data["dtcs"] = []
            self._on_dtcs_loaded([])
            return
        self.mutation_active.emit(True)
        self.read_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        worker = DiagnosticClearWorker(connection, self._ecus, self._coverage)
        self._worker = worker
        self._retired.append(worker)
        worker.result_ready.connect(self._on_clear_complete)
        worker.progress.connect(self._operation_progress.setText)
        worker.error.connect(self._on_clear_error)
        worker.finished.connect(self._on_worker_finished)
        worker.start()

    @Slot(str)
    def _on_clear_error(self, message: str) -> None:
        self._on_dtc_error(message)
        self.mutation_active.emit(False)

    @Slot(object)
    def _on_clear_complete(self, result: dict) -> None:
        """Show application replies separately from the post-clear observations."""
        sender = self.sender()
        if not isinstance(sender, CarWorker) or sender.connection is not self._connection:
            return
        lines = [
            f"{r['name']} / {r['memory']}: {r['response']}; memory {r['observed']}"
            for r in result["outcomes"]
        ]
        QMessageBox.information(
            self, "Clear outcomes", "\n".join(lines) or "No supported clear targets."
        )
        self._operation_progress.setText("Clear batch complete; see individual outcomes")
        self.mutation_active.emit(False)
        if sender.connection is self._connection and self._connection.alive_ok:
            self._read_dtcs()

    @staticmethod
    def _open_search(checked: bool, code: str) -> None:
        import webbrowser

        webbrowser.open(f"https://www.google.com/search?q={code}+BMW")

    @Slot(object, str)
    def set_mil_observation(self, on: object, detail: str) -> None:
        """Mirror the overview's engine fault-memory indicator (D-59)."""
        state = "on" if on is True else "off" if on is False else "unknown"
        text = "ON" if on is True else "OFF" if on is False else "Unavailable"
        self._mil_indicator.setText("")
        self._mil_label.setObjectName("milStatus")
        self._mil_label.setStyleSheet("")
        self._mil_label.setText(f"Check engine (MIL): {text} · {detail}")
        self._mil_label.setWordWrap(True)
        self._mil_label.setTextFormat(Qt.TextFormat.PlainText)
        self._mil_label.setProperty("milState", state)
        self._mil_label.style().unpolish(self._mil_label)
        self._mil_label.style().polish(self._mil_label)


# ---- Helpers ----


def _decode_dtc_status(status: int) -> str:
    """Present a UDS status byte as ISTA does: present, stored (confirmed) or not confirmed."""
    if status & 0x01:
        state = "Present (active)"
    elif status & 0x08:
        state = "Stored, not present now (confirmed)"
    else:
        state = "Not confirmed"
    return state + (" · warning lamp requested" if status & 0x80 else "")
