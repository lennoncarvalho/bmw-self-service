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
from ui.cockpit import CockpitCard, caption, match_button_widths, set_lamp_state
from ui.regional import regional_locale


class VehiclePage(QWidget):
    """Vehicle facts and an independently observed emissions MIL indicator."""

    refresh_requested = Signal()
    mil_changed = Signal(object, str)
    navigation_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._observed_at: datetime | None = None
        self._observed_clock = monotonic()
        self._mil_clock: float | None = None
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
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        self.hero_grid = QGridLayout()
        self.hero_grid.setSpacing(16)
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
        self.mileage_source = caption("")
        for title, value in (
            ("HEALTH SCAN", self.health_value),
            ("SERVICE STATUS", self.service_value),
            ("ODOMETER", self.mileage_value),
        ):
            card = CockpitCard(title)
            card.setProperty("class", "metricCard")
            card.box.addWidget(value)
            if value is self.mileage_value:
                card.box.addWidget(self.mileage_source)
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
        match_button_widths((self.scan_button, self.refresh_button))
        self.hero.box.addLayout(actions)

        self.mil_card = CockpitCard("Check engine (MIL)")
        self.mil_label = caption("", "metric")
        self.mil_detail = caption("")
        self.mil_age = caption("")
        self.mil_card.box.addStretch()
        self.mil_card.box.addWidget(self.mil_label)
        self.mil_card.box.addWidget(self.mil_detail)
        self.mil_card.box.addStretch()
        self.mil_card.box.addWidget(self.mil_age)
        self.hero_grid.addWidget(self.hero, 0, 0)
        self.hero_grid.setColumnStretch(0, 5)
        layout.addLayout(self.hero_grid)

        self.observed_label = caption("")
        self.observed_label.setParent(self)
        self.observed_label.hide()
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
        details = CockpitCard("Vehicle details")
        self.prod_date_label = caption("")
        self.order_label = caption("")
        self.time_criterion_label = caption("")
        self.paint_label = caption("")
        self.upholstery_label = caption("")
        self.previous_ilevel_label = caption("")
        self.factory_ilevel_label = caption("")
        self.engine_label = caption("")
        self.supply_voltage = ""
        for label in (
            self.order_label,
            self.time_criterion_label,
            self.prod_date_label,
            self.paint_label,
            self.upholstery_label,
            self.previous_ilevel_label,
            self.factory_ilevel_label,
            self.engine_label,
        ):
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            details.box.addWidget(label)
        layout.addWidget(details)

        self.order_button = QPushButton("Show vehicle configuration")
        self.order_button.setProperty("class", "secondary")
        self.order_button.setCheckable(True)
        self.order_button.toggled.connect(self._toggle_order)
        layout.addWidget(self.order_button)
        self.configuration_card = CockpitCard("Vehicle configuration")
        self.order_details = caption("")
        self.configuration_card.box.addWidget(self.order_details)
        self.configuration_card.hide()
        layout.addWidget(self.configuration_card)

        layout.addWidget(caption("Vehicle subsystems", "featureTitle"))
        layout.addLayout(self.subsystem_grid)

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
        wide = self.width() >= 820
        self.hero_grid.addWidget(self.mil_card, 0 if wide else 1, 1 if wide else 0)
        self.hero_grid.setColumnStretch(1, 2 if wide else 0)

    def resizeEvent(self, event) -> None:
        """Apply the compact composition when the viewport changes width."""
        super().resizeEvent(event)
        self._reflow()

    def _toggle_order(self, visible: bool) -> None:
        """Expand configuration details without a nested viewport."""
        self.configuration_card.setVisible(visible)
        self.order_button.setText(
            "Hide vehicle configuration" if visible else "Show vehicle configuration"
        )

    def _populate_order(self, order: dict[str, Any] | None) -> None:
        """Display decoded equipment or clear unavailable configuration details."""
        self.order_button.setEnabled(order is not None)
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
        self._mil_clock = None
        self.populate({})
        self.cbs_panel.clear("Service status not read in this session")
        self._observed_at = None
        self.observed_label.setText("No current vehicle observation")
        self.refresh_button.setEnabled(False)
        self.details_button.setChecked(False)
        self.order_button.setChecked(False)

    def invalidate(self, reason: str = "Observation is no longer current") -> None:
        """Immediately remove a current MIL color after a disruptive event."""
        self._mil_clock = None
        self.set_mil_observation({"on": None, "detail": reason})

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

    def populate(self, results: dict[str, object]) -> None:
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
        self.connection_label.setText(
            str(results.get("connection_info") or "Connection unavailable")
        )
        mileage = results.get("mileage")
        if isinstance(mileage, dict):
            mileage = f"{regional_locale().toString(int(mileage['km']))} km ({mileage['source']})"
        production = results.get("prod_date")
        self.prod_date_label.setText(f"Production date: {production or 'Unavailable'}")
        self.prod_date_label.setVisible(bool(production))
        self._populate_ilevel(results.get("i-level"))
        self.supply_voltage = str(results.get("battery_voltage") or "")
        engine = results.get("engine_data")
        self.engine_label.setText(
            "\n".join(self._measurement(item) for item in engine)
            if isinstance(engine, list) and engine
            else "Engine readings: Unavailable"
        )
        self.set_mil_observation(results.get("mil"))
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
        amount, separator, source = str(mileage or "Unavailable").partition(" (")
        self.mileage_value.setText(amount)
        self.mileage_source.setText("(" + source if separator else "")
        self.mileage_source.setVisible(bool(separator))
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
        label = str(item.get("label", "Engine reading"))
        if unit in {"C", "°C"}:
            label += " temperature"
        if not isinstance(value, (int, float)):
            return f"{label}: Unavailable"
        if unit == "mV":
            value, unit = value / 1000, "V"
        unit = {"C": "°C", "rpm": "1/min"}.get(unit, unit)
        decimals = 0 if unit == "1/min" else 1
        return f"{label}: {regional_locale().toString(float(value), 'f', decimals)} {unit}"

    def set_mil_observation(self, result: object) -> None:
        """Publish the settled lamp command and its read time to both displays."""
        on = result.get("on") if isinstance(result, dict) else None
        clock = result.get("observed_clock") if isinstance(result, dict) else None
        if type(on) is bool and isinstance(clock, (int, float)):
            self._mil_clock = float(clock)
        elif self._mil_clock is not None:
            return
        detail = (
            str(result.get("detail", ""))
            if isinstance(result, dict)
            else "No lamp observation in this session."
        )
        self.mil_label.setText(set_lamp_state(self.mil_label, on))
        self.mil_detail.setText(detail)
        self._update_age()
        self.mil_changed.emit(on, detail)

    def _update_age(self) -> None:
        if self._mil_clock is None:
            self.mil_age.clear()
            self.mil_age.hide()
        else:
            age = max(0, int(monotonic() - self._mil_clock))
            self.mil_age.setText(f"Last read {age}s ago")
            self.mil_age.show()
        if self._observed_at is not None:
            age = max(0, int(monotonic() - self._observed_clock))
            self.observed_label.setText(
                f"Overview read at {self._observed_at.astimezone():%H:%M:%S} · {age}s ago"
            )

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
            label.setProperty("role", "technical")
            self.ecu_layout.addWidget(label)
        self.ecu_layout.addStretch()
