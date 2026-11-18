"""Settled connection overview, with explicit availability and ECU coverage.

Overview data contracts: docs.md#identity-configuration-and-diagnostics.
All live I/O belongs to the owning CarWorker; this widget only displays results.
"""

from datetime import UTC, datetime
from time import monotonic
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.cbs_panel import CbsPanel
from ui.cockpit import CockpitCard, caption
from ui.regional import regional_locale


class VehiclePage(QWidget):
    """Vehicle facts and an independently observed emissions MIL indicator."""

    refresh_requested = Signal()
    mil_changed = Signal(object, str)
    navigation_requested = Signal(int)

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
        """Compose the approved overview from settled observations and shortcuts."""
        self.setObjectName("vehicleOverview")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 24)
        layout.setSpacing(20)
        self.hero_grid = QGridLayout()
        self.hero_grid.setSpacing(14)
        self.hero = CockpitCard("Vehicle systems overview")
        self.model_label = caption("", "display")
        self.hero.box.addWidget(self.model_label)
        self.connection_label = caption("")
        self.hero.box.addWidget(self.connection_label)
        self.ilevel_label = caption("")
        self.hero.box.addWidget(self.ilevel_label)
        self.hero.box.addSpacing(24)
        metrics = QHBoxLayout()
        self.health_value = caption("Not scanned", "metric")
        self.mileage_value = caption("Unavailable", "metric")
        self.service_value = caption("Not read", "metric")
        for title, value in (
            ("HEALTH SCAN", self.health_value),
            ("SERVICE STATUS", self.service_value),
            ("ODOMETER", self.mileage_value),
        ):
            card = CockpitCard(title)
            card.setProperty("class", "metricCard")
            card.box.addWidget(value)
            metrics.addWidget(card, 1)
        self.hero.box.addLayout(metrics)
        self.coverage_label = caption("Scan coverage · Not read")
        self.hero.box.addWidget(self.coverage_label)
        self.service_note = caption("Service status not read in this session")
        self.hero.box.addWidget(self.service_note)
        self.hero.box.addSpacing(18)
        actions = QHBoxLayout()
        self.scan_button = QPushButton("Read fault codes")
        self.scan_button.clicked.connect(lambda: self.navigation_requested.emit(1))
        self.refresh_button = QPushButton("Refresh overview")
        self.refresh_button.setProperty("class", "secondary")
        self.refresh_button.clicked.connect(self.refresh_requested)
        actions.addWidget(self.scan_button)
        actions.addWidget(self.refresh_button)
        actions.addStretch()
        self.hero.box.addLayout(actions)

        self.power_card = CockpitCard("Battery & power")
        self.voltage_value = caption("Unavailable", "display")
        self.power_card.box.addWidget(self.voltage_value)
        self.power_card.box.addWidget(caption("Observed supply voltage"))
        self.power_card.box.addSpacing(12)
        self.power_card.box.addWidget(
            caption("Power readiness is checked when preparing a vehicle write.", "caption")
        )
        self.side_column = QWidget()
        self.side_column.setProperty("class", "transparent")
        side = QVBoxLayout(self.side_column)
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(14)
        side.addWidget(self.power_card)
        quick = CockpitCard("Quick actions")
        for text, target in (("Scan vehicle  ›", 1), ("Service status  ›", 4)):
            button = QPushButton(text)
            button.clicked.connect(
                lambda checked=False, index=target: self.navigation_requested.emit(index)
            )
            if target == 4:
                button.setProperty("class", "secondary")
            quick.box.addWidget(button)
        side.addStretch()
        side.addWidget(quick)
        self.hero_grid.addWidget(self.hero, 0, 0)
        self.hero_grid.addWidget(self.side_column, 0, 1)
        self.hero_grid.setColumnStretch(0, 3)
        self.hero_grid.setColumnStretch(1, 2)
        layout.addLayout(self.hero_grid)

        self.mil_label = caption("")
        self.mil_label.setObjectName("milStatus")
        layout.addWidget(self.mil_label)
        self.observed_label = caption("")
        self.observed_label.setParent(self)
        self.observed_label.hide()
        layout.addWidget(caption("VEHICLE SUBSYSTEMS", "eyebrow"))
        self.subsystem_grid = QGridLayout()
        self.subsystem_grid.setSpacing(12)
        self.subsystem_cards: list[CockpitCard] = []
        for title, body, action, destination in (
            ("Diagnostics", "Read fault memories and inspect scan coverage.", "View faults", 1),
            (
                "Maintenance & service",
                "Read supported service items and their due values.",
                "View service status",
                4,
            ),
            (
                "Feature customization",
                "Load supported options and their observed values.",
                "Open Easy Coding",
                2,
            ),
            ("Vehicle backups", "Review saved records and operation outcomes.", "View backups", 5),
        ):
            card = CockpitCard(title)
            card.box.addWidget(caption(body))
            card.box.addStretch()
            button = QPushButton(action + "  ›")
            button.setProperty("class", "cardAction")
            button.clicked.connect(
                lambda checked=False, target=destination: self.navigation_requested.emit(target)
            )
            card.box.addWidget(button)
            self.subsystem_cards.append(card)
        layout.addLayout(self.subsystem_grid)

        self.order_button = QPushButton("Show vehicle configuration")
        self.order_button.setProperty("class", "secondary")
        self.order_button.setCheckable(True)
        self.order_button.toggled.connect(self._toggle_order)
        layout.addWidget(self.order_button)
        self.facts_card = CockpitCard("Vehicle details")
        facts = self.facts_card.box
        self.vin_label = caption("")
        self.mileage_label = caption("")
        self.prod_date_label = caption("")
        self.order_label = caption("")
        self.time_criterion_label = caption("")
        self.paint_label = caption("")
        self.upholstery_label = caption("")
        self.previous_ilevel_label = caption("")
        self.factory_ilevel_label = caption("")
        self.battery_label = caption("")
        self.engine_label = caption("")
        for label in (
            self.vin_label,
            self.mileage_label,
            self.prod_date_label,
            self.order_label,
            self.time_criterion_label,
            self.paint_label,
            self.upholstery_label,
            self.previous_ilevel_label,
            self.factory_ilevel_label,
            self.battery_label,
            self.engine_label,
        ):
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            facts.addWidget(label)
        self.order_details = caption("")
        facts.addWidget(self.order_details)
        self.facts_card.hide()
        layout.addWidget(self.facts_card)

        # Keep one CBS instance and its established signal/worker ownership.
        # The main window mounts this panel on its own navigation page.
        self.cbs_panel = CbsPanel(self)
        self.cbs_panel.hide()
        self.ecu_count_label = caption("")
        layout.addWidget(self.ecu_count_label)
        self.details_button = QPushButton("Show ECU details")
        self.details_button.setProperty("class", "secondary")
        self.details_button.setCheckable(True)
        self.details_button.toggled.connect(self._toggle_details)
        layout.addWidget(self.details_button)
        self.ecu_container = QWidget()
        self.ecu_layout = QVBoxLayout(self.ecu_container)
        self.ecu_container.hide()
        layout.addWidget(self.ecu_container)
        layout.addStretch()
        self._reflow()

    def _reflow(self) -> None:
        """Reflow surfaces at laptop widths while retaining one outer scrollbar."""
        columns = 4 if self.width() >= 1250 else 2
        for i, card in enumerate(self.subsystem_cards):
            self.subsystem_grid.addWidget(card, i // columns, i % columns)
        wide = self.width() >= 1150
        self.hero_grid.addWidget(self.side_column, 0 if wide else 1, 1 if wide else 0)
        self.hero_grid.setColumnStretch(1, 2 if wide else 0)

    def resizeEvent(self, event) -> None:
        """Apply the compact composition when the viewport changes width."""
        super().resizeEvent(event)
        self._reflow()

    def _toggle_order(self, visible: bool) -> None:
        """Expand configuration details without a nested viewport."""
        self.facts_card.setVisible(visible)
        self.order_button.setText(
            "Hide vehicle configuration" if visible else "Show vehicle configuration"
        )

    def _populate_order(self, order: dict[str, Any] | None) -> None:
        """Display decoded equipment or clear unavailable configuration details."""
        self.order_button.setEnabled(True)
        if order is None:
            self.order_button.setChecked(False)
            self.order_details.clear()
            return
        sections = order["sections"]
        lines = [
            f"Time criterion (raw): {order['time_criterion']}",
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
        """Expand the complete ECU list within the outer page viewport."""
        self.ecu_container.setVisible(visible)
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

    def invalidate_order(self) -> None:
        """Discard configuration details after a fatal overview read failure."""
        self.order_label.setText("Vehicle order: unavailable")
        self.time_criterion_label.setText("Vehicle-order date: Unavailable")
        self.paint_label.hide()
        self.upholstery_label.hide()
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
                "mil": {"on": False, "detail": "DEMO — simulated engine fault memory"},
            },
            series,
            vehicle.get("vin", "Unavailable"),
        )

    def populate(self, results: dict[str, object], series: str = "", vin: str = "") -> None:
        """Publish one settled batch; missing data never inherits earlier values."""
        self._observed_at = datetime.now(UTC)
        self._observed_clock = monotonic()
        order = results.get("vehicle_order")
        model = (
            results.get("model")
            or (order.get("model") if isinstance(order, dict) else None)
            or "BMW — model designation unavailable"
        )
        self.model_label.setText(str(model))
        self.vin_label.setText(f"VIN: {vin or results.get('vin') or 'Unavailable'}")
        self.connection_label.setText(
            str(results.get("connection_info") or "Connection unavailable")
        )
        mileage = results.get("mileage")
        if isinstance(mileage, dict):
            mileage = f"{regional_locale().toString(int(mileage['km']))} km ({mileage['source']})"
        self.mileage_label.setText(f"Odometer: {mileage or 'Unavailable'}")
        production = results.get("prod_date")
        self.prod_date_label.setText(f"Production date: {production or 'Unavailable'}")
        self.prod_date_label.setVisible(bool(production))
        self._populate_ilevel(results.get("i-level"))
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
        self._set_mil(self._mil_on, detail)
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
        self.paint_label.setVisible(isinstance(order, dict))
        self.upholstery_label.setVisible(isinstance(order, dict))
        if isinstance(order, dict):
            self.order_label.setText(
                f"Model range: {order['model_range']} · Type key: {order['type_code']}"
            )
            code = order["time_criterion"]
            date = (
                f"{code[:2]}/20{code[2:]}"
                if len(code) == 4 and code.isascii() and code.isdigit() and 1 <= int(code[:2]) <= 12
                else f"Unrecognised ({code})"
            )
            self.time_criterion_label.setText(f"Vehicle-order date: {date}")
            self.time_criterion_label.setToolTip(
                f"Time criterion {code}: configuration reference month. "
                "It can match the production month, but is not an independent production-date read."
            )
            self.paint_label.setText(f"Paint: {order['paint_code']}")
            self.upholstery_label.setText(f"Upholstery: {order['upholstery_code']}")
        else:
            self.order_label.setText("Vehicle order: unavailable")
            self.time_criterion_label.setText("Vehicle-order date: Unavailable")
            self.time_criterion_label.setToolTip("")
        self._populate_order(order if isinstance(order, dict) else None)
        self.mileage_value.setText(str(mileage or "Unavailable"))
        self.voltage_value.setText(str(results.get("battery_voltage") or "Unavailable"))
        self._update_age()

    def _populate_ilevel(self, levels: object) -> None:
        """Label the source's three roles, collapsing equal values without losing their meaning."""
        self.ilevel_label.setToolTip(
            "Vehicle-level current, previous and factory records; these are not separate ECUs."
        )
        self.previous_ilevel_label.hide()
        self.factory_ilevel_label.hide()
        if not isinstance(levels, dict):
            self.ilevel_label.setText(f"Software I-Level: {levels or 'Unavailable'}")
            return
        current, previous, factory = (levels.get(key) for key in ("current", "previous", "factory"))
        if current and current == previous == factory:
            self.ilevel_label.setText(
                f"Software I-Level: {current} (current, previous and factory)"
            )
            return
        self.ilevel_label.setText(f"Current I-Level: {current or 'Unavailable'}")
        self.previous_ilevel_label.setText(f"Previous I-Level: {previous or 'Unavailable'}")
        self.factory_ilevel_label.setText(f"Factory I-Level: {factory or 'Unavailable'}")
        self.previous_ilevel_label.show()
        self.factory_ilevel_label.show()

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
            "ON — engine has a present or confirmed fault"
            if on is True
            else "OFF — no present or confirmed engine fault"
            if on is False
            else "Unavailable"
        )
        self.mil_label.setText(f"● Check engine (MIL): {text}\n{detail}")
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
        """Replace ECU detail rows without retaining prior session widgets."""
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
