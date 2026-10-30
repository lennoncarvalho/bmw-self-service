"""Settled connection overview, with explicit availability and ECU coverage.

D-56 and docs/evidence/task-b-dashboard-read-findings.md define the contract.
All live I/O belongs to the owning CarWorker; this widget only displays results.
"""

from datetime import UTC, datetime
from time import monotonic
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.cbs_panel import CbsPanel
from ui.regional import regional_locale


class VehiclePage(QWidget):
    """Vehicle facts and an independently observed emissions MIL indicator."""

    refresh_requested = Signal()
    mil_read_requested = Signal()
    mil_changed = Signal(object, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._mil_on: bool | None = None
        self._observed_at: datetime | None = None
        self._observed_clock = monotonic()
        self._mil_clock = monotonic()
        self._ecus: list[dict[str, Any]] = []
        self._setup_ui()
        self._age_timer = QTimer(self)
        self._age_timer.timeout.connect(self._update_age)
        self._age_timer.start(1000)
        self.reset()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        header = QHBoxLayout()
        title = QLabel("Vehicle Information")
        title.setObjectName("titleLabel")
        header.addWidget(title)
        header.addStretch()
        self.refresh_button = QPushButton("Refresh overview")
        self.refresh_button.clicked.connect(self.refresh_requested)
        header.addWidget(self.refresh_button)
        layout.addLayout(header)

        self.mil_label = QLabel()
        self.mil_label.setObjectName("milStatus")
        self.mil_label.setWordWrap(True)
        self.mil_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.mil_label)
        self.mil_read_button = QPushButton("Read MIL from engine…")
        self.mil_read_button.setToolTip(
            "Temporarily defines an engine data slot, reads the MIL and clears the slot"
        )
        self.mil_read_button.clicked.connect(self.mil_read_requested)
        self.mil_read_button.hide()
        layout.addWidget(self.mil_read_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.observed_label = QLabel()
        self.observed_label.setObjectName("overviewCaption")
        layout.addWidget(self.observed_label)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        self.model_label = QLabel()
        self.vin_label = QLabel()
        self.connection_label = QLabel()
        self.mileage_label = QLabel()
        self.prod_date_label = QLabel()
        self.order_label = QLabel()
        self.ilevel_label = QLabel()
        self.battery_label = QLabel()
        self.engine_label = QLabel()
        for label in (
            self.model_label,
            self.vin_label,
            self.connection_label,
            self.mileage_label,
            self.prod_date_label,
            self.order_label,
            self.ilevel_label,
            self.battery_label,
            self.engine_label,
        ):
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            card_layout.addWidget(label)
        layout.addWidget(card)

        self.order_button = QPushButton("Show vehicle configuration")
        self.order_button.setCheckable(True)
        self.order_button.toggled.connect(self._toggle_order)
        layout.addWidget(self.order_button)
        self.order_scroll = QScrollArea()
        self.order_scroll.setWidgetResizable(True)
        self.order_scroll.setMaximumHeight(160)
        self.order_details = QLabel()
        self.order_details.setWordWrap(True)
        self.order_details.setTextFormat(Qt.TextFormat.PlainText)
        self.order_details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.order_scroll.setWidget(self.order_details)
        self.order_scroll.hide()
        layout.addWidget(self.order_scroll)

        self.cbs_panel = CbsPanel()
        layout.addWidget(self.cbs_panel)

        self.ecu_count_label = QLabel()
        layout.addWidget(self.ecu_count_label)
        self.details_button = QPushButton("Show ECU details")
        self.details_button.setCheckable(True)
        self.details_button.toggled.connect(self._toggle_details)
        layout.addWidget(self.details_button)
        self.ecu_scroll = QScrollArea()
        self.ecu_scroll.setWidgetResizable(True)
        self.ecu_container = QWidget()
        self.ecu_layout = QVBoxLayout(self.ecu_container)
        self.ecu_scroll.setWidget(self.ecu_container)
        self.ecu_scroll.hide()
        layout.addWidget(self.ecu_scroll, 1)
        layout.addStretch()

    def _toggle_order(self, visible: bool) -> None:
        self.order_scroll.setVisible(visible)
        self.order_button.setText(
            "Hide vehicle configuration" if visible else "Show vehicle configuration"
        )

    def _populate_order(self, order: dict[str, Any] | None) -> None:
        self.order_button.setEnabled(order is not None)
        if order is None:
            self.order_button.setChecked(False)
            self.order_details.clear()
            return
        sections = order["sections"]
        lines = [
            "Options:\n"
            + (
                "\n".join(order.get("option_descriptions", sections.get("8", []))) or "None decoded"
            ),
            "Section 4 codes: " + (", ".join(sections.get("4", [])) or "None decoded"),
            "Section 12 codes: " + (", ".join(sections.get("12", [])) or "None decoded"),
            "Vehicle-order configuration codes; unknown descriptions stay unavailable.",
        ]
        if not order["equipment_complete"]:
            lines.append("Unknown equipment section — decoded codes are incomplete.")
        self.order_details.setText("\n".join(lines))

    def _toggle_details(self, visible: bool) -> None:
        self.ecu_scroll.setVisible(visible)
        self.details_button.setText("Hide ECU details" if visible else "Show ECU details")

    def reset(self) -> None:
        """Discard all facts and MIL observations from the previous session."""
        self.populate({}, vin="Unavailable")
        self.cbs_panel.clear("Service status not read in this session")
        self._observed_at = None
        self.observed_label.setText("No current vehicle observation")
        self.refresh_button.setEnabled(False)
        self.details_button.setChecked(False)
        self.order_button.setChecked(False)

    def invalidate(self, reason: str = "Observation is no longer current") -> None:
        """Immediately remove a current MIL color after a disruptive event."""
        self._mil_on = None
        self._set_mil(None, reason)

    def show_mil_result(self, mil: dict[str, Any]) -> None:
        """Publish an explicitly requested MIL observation without other overview facts."""
        on = mil.get("on")
        self._mil_on = on if type(on) is bool else None
        clock = mil.get("observed_clock")
        self._mil_clock = float(clock) if isinstance(clock, (int, float)) else monotonic()
        self._set_mil(self._mil_on, str(mil.get("detail", "")))

    def invalidate_order(self) -> None:
        """Discard configuration details after a fatal overview read failure."""
        self.order_label.setText("Vehicle order: unavailable")
        self._populate_order(None)

    def set_loading(self, loading: bool) -> None:
        """Keep the previous settled facts together until the next result arrives."""
        self.refresh_button.setEnabled(not loading)
        self.refresh_button.setText("Reading overview…" if loading else "Refresh overview")

    def load_data(self, connection: Any, series: str = "") -> None:
        """Display a labelled demonstration snapshot without synchronous car I/O."""
        data = getattr(connection, "data", {}) or {}
        vehicle = data.get("vehicle", {})
        self.populate(
            {
                "model": vehicle.get("model"),
                "mileage": f"{vehicle['mileage_km']:,} km" if "mileage_km" in vehicle else None,
                "prod_date": vehicle.get("production_date"),
                "battery_voltage": (
                    f"{vehicle['battery_voltage']:.2f} V" if "battery_voltage" in vehicle else None
                ),
                "ecu_list": data.get("svt_ecus", []),
                "connection_info": "DEMO — simulated vehicle",
                "mil": {"on": False, "detail": "DEMO observation"},
            },
            series,
            vehicle.get("vin", "Unavailable"),
        )

    def populate(self, results: dict[str, object], series: str = "", vin: str = "") -> None:
        """Publish one settled batch; missing data never inherits earlier values."""
        self._observed_at = datetime.now(UTC)
        self._observed_clock = monotonic()
        model = results.get("model") or "BMW — exact model unavailable"
        self.model_label.setText(str(model))
        self.vin_label.setText(f"VIN: {vin or results.get('vin') or 'Unavailable'}")
        self.connection_label.setText(
            str(results.get("connection_info") or "Connection unavailable")
        )
        mileage = results.get("mileage")
        if isinstance(mileage, dict):
            mileage = f"{regional_locale().toString(int(mileage['km']))} km ({mileage['source']})"
        self.mileage_label.setText(f"Odometer: {mileage or 'Unavailable'}")
        self.prod_date_label.setText(f"Build date: {results.get('prod_date') or 'Unavailable'}")
        self.ilevel_label.setText(
            f"Software integration levels: {results.get('i-level') or 'Unavailable'}"
        )
        self.battery_label.setText(
            f"Supply voltage: {results.get('battery_voltage') or 'Unavailable'}"
        )
        engine = results.get("engine_data")
        self.engine_label.setVisible(isinstance(engine, list))
        if isinstance(engine, list):
            self.engine_label.setText(
                "Engine: " + " · ".join(self._measurement(item) for item in engine)
            )
        mil = results.get("mil")
        self._mil_on = mil.get("on") if isinstance(mil, dict) else None
        if type(self._mil_on) is not bool:
            self._mil_on = None
        clock = mil.get("observed_clock") if isinstance(mil, dict) else None
        self._mil_clock = float(clock) if isinstance(clock, (int, float)) else monotonic()
        detail = (
            str(mil.get("detail", ""))
            if isinstance(mil, dict)
            else "No verified read contract for this ECU"
        )
        engine = results.get("engine_data")
        speeds = [
            item.get("value")
            for item in (engine if isinstance(engine, list) else [])
            if item.get("label") == "Engine speed"
        ]
        if self._mil_on is True and speeds == [0.0]:
            # Owner F48 (DME_BX8), 2026-10-29: key-on with the engine stopped reported 1.
            detail += (
                "\nEngine not running (0 1/min): with the key on and the engine stopped the "
                "lamp is normally lit as a bulb check. Start the engine and refresh to read "
                "the running state."
            )
        self._set_mil(self._mil_on, detail)
        self.mil_read_button.setVisible(
            isinstance(mil, dict) and mil.get("action") == "dynamic-block"
        )
        ecus = results.get("ecu_list")
        self._ecus = ecus if isinstance(ecus, list) else []
        identified = sum(row.get("identified") is True for row in self._ecus)
        candidates = sum(row.get("origin") == "catalogue" for row in self._ecus)
        self.ecu_count_label.setText(
            (
                f"Catalogue candidates: {candidates} · Identified: {identified} · "
                "Installed topology unavailable; candidates do not establish vehicle coverage"
                if candidates
                else f"ECUs announced: {len(self._ecus)} · Identified: {identified} · "
                f"Unidentified: {len(self._ecus) - identified}"
            )
            if isinstance(ecus, list)
            else "ECU inventory: unavailable"
        )
        self._populate_ecus(self._ecus)
        order = results.get("vehicle_order")
        if isinstance(order, dict):
            self.order_label.setText(
                f"Model range: {order['model_range']} · Type key: {order['type_code']}\n"
                f"Time criterion: {order['time_criterion']} (configuration code)\n"
                f"Paint: {order['paint_code']} · Upholstery: {order['upholstery_code']}"
            )
        else:
            self.order_label.setText("Vehicle order: unavailable")
        self._populate_order(order if isinstance(order, dict) else None)
        self._update_age()

    @staticmethod
    def _measurement(item: dict[str, Any]) -> str:
        value, unit = item.get("value"), str(item.get("unit", ""))
        if not isinstance(value, (int, float)):
            return f"{item.get('label')} unavailable"
        if unit == "mV":
            value, unit = value / 1000, "V"
        unit = {"C": "°C", "rpm": "1/min"}.get(unit, unit)
        decimals = 0 if unit == "1/min" else 1
        return (
            f"{item.get('label')} {regional_locale().toString(float(value), 'f', decimals)} {unit}"
        )

    def _set_mil(self, on: bool | None, detail: str) -> None:
        state = "on" if on is True else "off" if on is False else "unknown"
        text = (
            "ON — ECU reports check-engine light"
            if on is True
            else "OFF — ECU reports check-engine light off"
            if on is False
            else "Unavailable"
        )
        self.mil_label.setText(f"● Emissions MIL: {text}\n{detail}")
        self.mil_label.setProperty("milState", state)
        self.mil_label.style().unpolish(self.mil_label)
        self.mil_label.style().polish(self.mil_label)
        self.mil_changed.emit(on, detail)

    def _update_age(self) -> None:
        if self._observed_at is None:
            return
        age = max(0, int(monotonic() - self._observed_clock))
        self.observed_label.setText(
            f"Overview read at {self._observed_at.astimezone():%H:%M:%S} · {age}s ago"
        )
        if monotonic() - self._mil_clock >= 60 and self._mil_on is not None:
            self.invalidate("Stale observation — refresh to read the current MIL")

    def _populate_ecus(self, ecus: list[dict[str, Any]]) -> None:
        while self.ecu_layout.count():
            item = self.ecu_layout.takeAt(0)
            child = item.widget() if item is not None else None
            if child is not None:
                child.hide()
                child.deleteLater()
        for ecu in ecus:
            status = "Identified" if ecu.get("identified") is True else "Unidentified"
            label = QLabel(
                f"{ecu.get('addr', '?')} · {ecu.get('name', 'Unknown ECU')} · {status}\n"
                f"Variant: {ecu.get('variant', 'Unavailable')} · {ecu.get('description', '')}\n"
                f"Origin: {ecu.get('origin', 'gateway')} · Identity: "
                f"{ecu.get('identity_state', status)} · Inventory: {ecu.get('inventory_state', 'read')}"
            )
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            self.ecu_layout.addWidget(label)
        self.ecu_layout.addStretch()
