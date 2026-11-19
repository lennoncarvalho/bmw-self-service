"""Diagnostics page — DTC read/clear from all ECUs.

Displays fault codes with descriptions from DtcDatabase.
Always-visible fault details with a separate confirmation dialog for clears.

Reference: plan.md#diagnostics-and-cbs and docs.md#diagnostic-text-database.
"""

import logging
from collections import Counter
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.diagnostics import DiagnosticClearWorker, DiagnosticReadWorker, coverage_complete
from app.worker import CarWorker
from ui.cockpit import CardSearch, CockpitCard, DangerButton, PageHeader, ResponsiveColumns, caption
from ui.dialogs import MessageBox as QMessageBox
from ui.regional import regional_locale

logger = logging.getLogger(__name__)


class DiagnosticsPage(QWidget):
    """Diagnostics tab — read and clear fault codes from all ECUs."""

    mutation_active = Signal(bool, bool)
    loading_changed = Signal(bool)
    loading_progress = Signal(str)

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
        self._clear_refresh_pending = False
        self._clear_blocked = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build diagnostic result, unknown-state and operation controls in the page."""
        self.setObjectName("diagnosticsPage")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        # Title bar with read button
        header = PageHeader(
            "Vehicle health scan",
            "Read fault memories, review recorded conditions and inspect scan coverage.",
        )
        self.read_btn = QPushButton("Run full scan")
        self.read_btn.clicked.connect(self._on_read_clicked)
        header.action_layout.addWidget(self.read_btn)
        layout.addWidget(header)
        self.summary_card = CockpitCard("Scan coverage")
        self.scan_summary = caption("No scan results yet", "sectionTitle")
        self.summary_card.box.addWidget(self.scan_summary)
        self.coverage_summary = caption("Coverage unavailable until a scan completes.")
        self.summary_card.box.addWidget(self.coverage_summary)
        self.summary_card.box.addWidget(caption("RECORDED FAULTS BY ECU", "eyebrow"))
        self.system_summary = caption("No recorded faults to summarize.")
        self.summary_card.box.addWidget(self.system_summary)
        self.summary_card.box.addStretch()
        self._clear_summary = QLabel()
        self._clear_summary.hide()
        self._clear_summary.setWordWrap(True)
        self._clear_summary.setTextFormat(Qt.TextFormat.PlainText)
        self._clear_summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._clear_summary)
        self._stale_scan_notice = QLabel(
            "The displayed scan is stale after a partial clear. "
            "Read fault memories again when vehicle power permits."
        )
        self._stale_scan_notice.setWordWrap(True)
        self._stale_scan_notice.hide()
        layout.addWidget(self._stale_scan_notice)

        # T-9: MIL (Check Engine) status indicator
        mil_row = QHBoxLayout()
        self._mil_indicator = QLabel("")
        mil_row.addWidget(self._mil_indicator)
        self._mil_label = caption("MIL status unavailable until the vehicle endpoint is verified")
        mil_row.addWidget(self._mil_label)
        mil_row.addStretch()
        self.summary_card.box.addLayout(mil_row)

        # Stack: empty state vs DTC list
        self.stack = QVBoxLayout()
        results = QWidget()
        results.setProperty("class", "transparent")
        results_box = QVBoxLayout(results)
        results_box.setContentsMargins(0, 0, 0, 0)
        results_box.addLayout(self.stack)

        # Empty state
        self.empty_state = QWidget()
        empty_layout = QVBoxLayout(self.empty_state)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_icon = caption("FAULT MEMORY", "eyebrow")
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_icon)
        empty_text = QLabel("No DTC scan results yet.")
        self._empty_text = empty_text
        empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_text)
        results_box.addWidget(self.empty_state)

        # DTC list container
        self.list_container = QWidget()
        self.list_container.setVisible(False)
        list_layout = QVBoxLayout(self.list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)

        scroll_container = QWidget()
        self.dtc_list_layout = QVBoxLayout(scroll_container)
        self.dtc_list_layout.setSpacing(8)
        self.dtc_list_layout.addStretch()
        list_layout.addWidget(scroll_container)

        # Clear button
        self.clear_btn = DangerButton("Clear All DTCs")
        self.clear_btn.clicked.connect(self._on_clear_clicked)
        self.clear_btn.setVisible(False)
        self.search = CardSearch(self.list_container, "Search fault code, ECU or description")
        results_box.insertWidget(0, self.search)
        results_box.addWidget(self.list_container)
        layout.addWidget(ResponsiveColumns(self.summary_card, results, ratio=(1, 2)))
        header.action_layout.addWidget(self.clear_btn)
        layout.addStretch()

    def _update_actions(self) -> None:
        """Offer Clear All for supported targets independently of scan completeness."""
        connected = self._connection is not None and getattr(self._connection, "alive_ok", True)
        busy = self._worker is not None
        self.read_btn.setEnabled(connected and not busy)
        writable = connected and not getattr(self._connection, "read_only", False)
        supported = any(e.get("identified") and e.get("uds") for e in self._ecus)
        available = writable and supported
        self.clear_btn.setVisible(available)
        self.clear_btn.setEnabled(
            available
            and not busy
            and not self._clear_blocked
            and getattr(self._connection, "power_sufficient", None) is not False
        )

    def set_connection(self, connection: Any, ecus: list[dict]) -> None:
        """Replace settled targets and invalidate results from the previous inventory."""
        if connection is self._connection and ecus == self._ecus:
            self._update_actions()
            return
        self._inventory_revision += 1
        if connection is not self._connection:
            self._clear_summary.clear()
            self._clear_summary.hide()
            self._clear_blocked = False
        self._clear_refresh_pending = False
        self._connection = connection
        self._ecus = [dict(ecu) for ecu in ecus]
        # Build ECU name lookup map for detail view
        self._ecu_lookup = {e.get("name", ""): e.get("description", "") for e in ecus}
        self._loaded = False
        self.scan_summary.setText("No scan results yet")
        self.system_summary.setText("No recorded faults to summarize.")
        self.coverage_summary.setText("Coverage unavailable until a scan completes.")
        self._coverage = []
        self._dtcs = []
        self._stale_scan_notice.hide()
        self.read_btn.setEnabled(self._worker is None)
        self.clear_btn.setEnabled(False)
        self._empty_text.setText("Open Diagnostics to read vehicle fault memories.")
        self.empty_state.setVisible(True)
        self.list_container.setVisible(False)
        self._update_actions()

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
        if self._connection is None or self._worker is not None:
            return
        self.read_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self._empty_text.setText("Reading confirmed fault codes...")
        self.empty_state.setVisible(True)
        self.list_container.setVisible(False)

        worker = DiagnosticReadWorker(self._connection, self._ecus, coverage_known=bool(self._ecus))
        self._worker = worker
        worker.setProperty("inventory_revision", self._inventory_revision)
        self._retired.append(worker)
        worker.result_ready.connect(self._on_dtcs_loaded)
        worker.progress.connect(self._on_loading_progress)
        worker.error.connect(self._on_dtc_error)
        worker.finished.connect(self._on_worker_finished)
        self.loading_changed.emit(True)
        self.loading_progress.emit("Reading fault memories...")
        worker.start()

    @Slot(str)
    def _on_loading_progress(self, message: str) -> None:
        """Forward progress from the active worker to the foreground loading dialog."""
        worker = self.sender()
        if worker is not self._worker or not isinstance(worker, CarWorker):
            return
        if worker.connection is not self._connection:
            return
        if isinstance(worker, DiagnosticReadWorker) and (
            worker.property("inventory_revision") != self._inventory_revision
        ):
            return
        self.loading_progress.emit(message)

    @Slot()
    def _on_worker_finished(self) -> None:
        worker = self.sender()
        if worker is self._worker:
            self._worker = None
            if isinstance(worker, DiagnosticClearWorker):
                refresh = self._clear_refresh_pending
                self._clear_refresh_pending = False
                if refresh and worker.connection is self._connection and self._connection.alive_ok:
                    self._read_dtcs()
                self.mutation_active.emit(False, refresh)
            self.loading_changed.emit(self._worker is not None)
            self._update_actions()
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
        self._dtcs = dtcs
        self._loaded = True
        self._stale_scan_notice.hide()
        self._update_actions()

        self.scan_summary.setText(f"{len(dtcs)} recorded faults")
        self.coverage_summary.setText(
            ("Scan complete" if complete else "Scan incomplete")
            + (
                "\nVehicle inventory unavailable; identified controllers only."
                if isinstance(result, dict) and not result.get("topology_known", True)
                else (
                    "\nMemory coverage: "
                    f"{sum(coverage_complete(row) for row in self._coverage)}"
                    f"/{len(self._coverage)} accounted for."
                )
                if self._coverage
                else "\nPer-memory coverage unavailable."
            )
        )

        by_ecu = Counter(str(dtc.get("ecu_name") or "Unknown ECU") for dtc in dtcs)
        self.system_summary.setText(
            "\n\n".join(f"{name} · {count} recorded faults" for name, count in by_ecu.items())
            or "No faults returned by the memories read."
        )

        # Clean existing cards
        while self.dtc_list_layout.count() > 1:
            item = self.dtc_list_layout.takeAt(0)
            if item is None:
                continue
            child = item.widget()
            if child is not None:
                child.hide()
                child.deleteLater()

        self.empty_state.setVisible(False)
        self.list_container.setVisible(True)
        if self._coverage or isinstance(result, dict):
            summary = QLabel(
                ("Scan complete" if complete else "Scan incomplete")
                + f" · {len(dtcs)} {'fault' if len(dtcs) == 1 else 'faults'} found"
            )
            if not complete:
                summary.setText(
                    summary.text() + "\nSome vehicle fault memories could not be checked."
                )
            if isinstance(result, dict) and not result.get("topology_known", True):
                summary.setText(
                    summary.text()
                    + "\nVehicle inventory is unavailable; results cover identified controllers only."
                )
            summary.setWordWrap(True)
            summary.setTextFormat(Qt.TextFormat.PlainText)
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
            description = dtc.get("description") or "Description unavailable"
            ecu = dtc.get("ecu_name", "Unknown")
            full_name = self._ecu_lookup.get(ecu)
            ecu_text = f"{full_name} ({ecu})" if full_name and full_name != ecu else ecu

            card = QFrame()
            card.setObjectName("recordCard")
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(8)
            header = QHBoxLayout()
            code_label = caption(str(code), "technical")
            code_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            header.addWidget(code_label, 0, Qt.AlignmentFlag.AlignTop)
            heading = QLabel(description)
            heading.setObjectName("dtcHeading")
            heading.setWordWrap(True)
            heading.setTextFormat(Qt.TextFormat.PlainText)
            heading.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            header.addWidget(heading, 1)
            search = QPushButton("Search web")
            search.setObjectName("dtcSearchButton")
            search.setToolTip(f"Search the web for {code} BMW")
            search.clicked.connect(lambda checked, c=code: self._open_search(checked, c))
            header.addWidget(search, 0, Qt.AlignmentFlag.AlignTop)
            card_layout.addLayout(header)

            meta = QLabel(
                f"ECU: {ecu_text} · {dtc.get('memory', 'Fault')} memory · "
                f"{_decode_dtc_status(dtc.get('status_byte', 0))}"
            )
            meta.setObjectName("dtcMeta")
            meta.setWordWrap(True)
            meta.setTextFormat(Qt.TextFormat.PlainText)
            meta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            card_layout.addWidget(meta)
            _add_recorded_details(card_layout, dtc)
            self.dtc_list_layout.insertWidget(self.dtc_list_layout.count() - 1, card)
        self.search.apply()

    def _on_dtc_error(self, msg: str) -> None:
        """Report an unavailable scan without leaving stale results or a healthy-car claim."""
        sender = self.sender()
        if isinstance(sender, CarWorker) and sender.connection is not self._connection:
            return
        if isinstance(sender, DiagnosticReadWorker) and (
            sender.property("inventory_revision") != self._inventory_revision
        ):
            return
        self._update_actions()
        self.scan_summary.setText("Scan unavailable")
        self.coverage_summary.setText("The latest read failed. Previous coverage is stale.")
        self.system_summary.setText("Recorded fault counts unavailable after the failed read.")
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
            or getattr(self._connection, "power_sufficient", None) is False
            or not getattr(self._connection, "alive_ok", True)
            or self._clear_blocked
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
            if not coverage_complete(r)
        ]
        prompt = (
            "Clear all supported Fault and Information memories? Permanent faults are not cleared by this operation.\n\n"
            "This cannot be undone or cancelled once started. Confirm adequate car and "
            "computer power, with ignition on and cable connected.\n"
        )
        if not self._loaded:
            prompt += "\nFault memories have not been read in this session.\n"
        if any(ecu.get("origin") == "catalogue" for ecu in self._ecus):
            prompt += (
                "\nInstalled topology is unavailable. Catalogue candidates are not a complete "
                "vehicle inventory; only identified supported targets can be cleared.\n"
            )
        if gaps:
            prompt += "\nScan gaps:\n" + "\n".join(gaps)
        connection = self._connection
        revision = self._inventory_revision
        if (
            QMessageBox.question(
                self,
                "Clear All DTCs",
                prompt,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
                destructive=True,
                action_text="Clear all faults",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        if (
            self._connection is not connection
            or self._worker is not None
            or revision != self._inventory_revision
            or not self.can_mutate()
            or getattr(connection, "read_only", False)
            or not getattr(connection, "alive_ok", True)
            or getattr(connection, "power_sufficient", None) is False
        ):
            return
        self._clear_refresh_pending = False
        self.mutation_active.emit(True, False)
        self.read_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        worker = DiagnosticClearWorker(connection, self._ecus, self._coverage)
        self._worker = worker
        self._retired.append(worker)
        worker.result_ready.connect(self._on_clear_complete)
        worker.progress.connect(self._on_loading_progress)
        worker.error.connect(self._on_clear_error)
        worker.finished.connect(self._on_worker_finished)
        self.loading_changed.emit(True)
        self.loading_progress.emit("Clearing fault memories...")
        worker.start()

    @Slot(str)
    def _on_clear_error(self, message: str) -> None:
        """Retain a failed clear as unresolved until reconnect; unlock only after thread exit."""
        sender = self.sender()
        if (
            not isinstance(sender, DiagnosticClearWorker)
            or sender is not self._worker
            or sender.connection is not self._connection
        ):
            return
        self._clear_blocked = True
        self._clear_refresh_pending = False
        self._clear_summary.setText(
            "Clear All did not finish. Its outcome is unavailable; reconnect and read "
            "fault memories before a new clear. No automatic retry."
        )
        self._clear_summary.show()
        self._on_dtc_error(message)

    @Slot(object)
    def _on_clear_complete(self, result: dict) -> None:
        """Show application replies separately from the post-clear observations."""
        sender = self.sender()
        if (
            not isinstance(sender, DiagnosticClearWorker)
            or sender is not self._worker
            or sender.connection is not self._connection
        ):
            return
        lines = [
            f"{r['name']} / {r['memory']}: {r['response']}; memory {r['observed']}"
            + (f" ({r['remaining_count']} faults)" if r.get("remaining_count") is not None else "")
            + (f"; reread {r['read_state']}" if r.get("read_state") not in (None, "read") else "")
            + (f" ({r['source']})" if r.get("source") else "")
            for r in result["outcomes"]
        ]
        self._clear_blocked = result.get("stopped") == "connection"
        self._clear_refresh_pending = not result.get("stopped")
        text = "Clear All outcomes (application replies and observations are separate):\n"
        text += "\n".join(lines) or "No supported clear targets."
        if self._clear_blocked:
            text += (
                "\nBatch stopped. Previously displayed scan values may be stale. "
                "Reconnect and read fault memories before another clear."
            )
        elif result.get("stopped") == "low-power":
            text += "\nClear All stopped because vehicle power is insufficient."
            if any(row["response"] == "accepted" for row in result["outcomes"]):
                self._stale_scan_notice.show()
        elif result.get("stopped"):
            text += "\nBatch stopped. Read fault memories again; previous scan values may be stale."
        self._clear_summary.setText(text)
        self._clear_summary.show()
        counts = Counter(row["response"] for row in result["outcomes"])
        observed = Counter(row["observed"] for row in result["outcomes"])
        message = "Application outcomes:\n" + "\n".join(
            f"{state}: {count}" for state, count in sorted(counts.items())
        )
        message += (
            f"\n\nRereads: {observed['empty']} empty; "
            f"{observed['still-present']} with faults remaining.\n"
            "Permanent faults were not cleared. Full per-target results remain on this page."
        )
        if result.get("stopped"):
            message += "\nBatch stopped; inspect the unattempted targets and connection status."
        QMessageBox.information(self, "Clear outcomes", message)

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
        self._mil_label.setText(f"Check engine (MIL): {text} · {detail}")
        self._mil_label.setWordWrap(True)
        self._mil_label.setTextFormat(Qt.TextFormat.PlainText)
        self._mil_label.setProperty("milState", state)
        self._mil_label.style().unpolish(self._mil_label)
        self._mil_label.style().polish(self._mil_label)


# ---- Helpers ----


def _add_recorded_details(layout: QVBoxLayout, dtc: dict) -> None:
    """Render every collected state once as plain text without requesting data."""
    details = dtc.get("details", {})
    state = details.get("state", "not-in-scan")
    reasons = {
        "not-in-scan": "Recorded details were not collected in this scan.",
        "not-defined": "Recorded details are unavailable for this memory or ECU definition.",
        "ambiguous-record": "Recorded details are unavailable: this memory repeated the fault code.",
        "not-attempted-budget-exhausted": "Recorded details were not read within the scan budget.",
        "not-attempted-connection": "Recorded details were not read after communication failed.",
        "not-attempted-cancelled": "Recorded details were not read because the scan stopped.",
        "unsupported": "The ECU does not support this recorded-detail read.",
        "rejected": "The ECU rejected this recorded-detail read.",
        "timeout": "The recorded-detail read timed out.",
        "job-failed": "The ECU definition interpreter could not complete the recorded-detail job.",
        "failed": "Communication failed while reading recorded details.",
        "policy-blocked": "The recorded-detail read was blocked by the current session policy.",
        "cancelled": "The recorded-detail read was cancelled before completion.",
        "refused-unexpected-request": (
            "The recorded-detail job attempted an unexpected request; it was blocked."
        ),
        "outcome-uncertain": (
            "The job stopped after sending a vehicle write; its outcome is uncertain. "
            "Do not repeat the operation automatically."
        ),
        "invalid": "Recorded details could not be decoded or matched to this fault.",
    }

    def add(text: str, heading: bool = False) -> None:
        """Append a selectable plain-text heading or value to this card."""
        label = QLabel(text)
        label.setObjectName("faultDetailHeading" if heading else "faultDetailValue")
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setWordWrap(True)
        layout.addWidget(label)

    if state != "read":
        add("Recorded fault details", True)
        add(reasons.get(state, "Recorded details could not be read. See the session log."))
        return
    records = details.get("records", [])
    if not records:
        add("Recorded fault details", True)
        add("No recorded conditions were returned.")
        return
    locale = regional_locale()
    for index, record in enumerate(records, 1):
        add(f"Recorded fault details {index}", True)
        lines = []
        for field in record["fields"] + record["environment"]:
            value = field["value"]
            if value is None:
                formatted = "Unavailable"
            elif isinstance(value, int):
                formatted = locale.toString(value)
            elif isinstance(value, float):
                formatted = locale.toString(value, "g", 12)
            else:
                formatted = str(value)
            if field.get("unit") and value is not None:
                formatted += f" {field['unit']}"
            if field.get("note"):
                formatted += f" — {field['note']}"
            lines.append(f"{field['label']}: {formatted}")
        add("\n".join(lines) or "No recorded conditions were returned.")


def _decode_dtc_status(status: int) -> str:
    """Present a UDS status byte as ISTA does: present, stored (confirmed) or not confirmed."""
    if status & 0x01:
        state = "Present (active)"
    elif status & 0x08:
        state = "Stored, not present now (confirmed)"
    else:
        state = "Not confirmed"
    return state + (" · warning lamp requested" if status & 0x80 else "")
