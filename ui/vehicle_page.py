"""Vehicle Dashboard — VIN, model, mileage, battery, ECU list.

Displayed after connection shows an overview of the connected vehicle.
Data comes from UDS ReadDataByIdentifier (0x22) requests.

Reference: docs/16-ui-spec.md Screen 4
"""

import logging
from typing import Any

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


def _parse_svt_response(resp: bytes) -> list[dict]:
    """Parse a raw SVT (0x62 F0 00 ...) UDS response into ECU entries.

    Attempts to extract ECU short names from the response payload.
    Format varies by BMW generation; this parser handles common patterns.

    Args:
        resp: Raw UDS response including SID/DID echo bytes.

    Returns:
        List of dicts with 'name' and 'addr' keys, or empty list.
    """
    ecus: list[dict] = []
    payload = resp[3:] if len(resp) > 3 else resp
    try:
        text = payload.decode("ascii", errors="ignore")
        # Try to find ECU short-name patterns (2-8 uppercase alphanumeric)
        import re
        seen: set[str] = set()
        for match in re.finditer(r'\b([A-Z]{2,8}(?:_[A-Z0-9]{1,4})?)\b', text):
            name = match.group(1)
            if name not in seen and len(name) >= 2:
                seen.add(name)
                ecus.append({"name": name, "description": ""})
    except Exception:
        pass
    return ecus


class VehiclePage(QWidget):
    """Dashboard showing vehicle identity, mileage, battery, and ECU list."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel("Vehicle Information")
        title.setObjectName("titleLabel")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title)

        # Info card
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(8)

        self.model_label = QLabel("")
        self.model_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #e0e0e0;")
        card_layout.addWidget(self.model_label)

        self.vin_label = QLabel("")
        self.vin_label.setStyleSheet("font-size: 13px; color: #a0a0a0;")
        card_layout.addWidget(self.vin_label)

        self.mileage_label = QLabel("")
        self.mileage_label.setStyleSheet("font-size: 13px; color: #a0a0a0;")
        card_layout.addWidget(self.mileage_label)

        self.prod_date_label = QLabel("")
        self.prod_date_label.setStyleSheet("font-size: 13px; color: #a0a0a0;")
        card_layout.addWidget(self.prod_date_label)

        self.ilevel_label = QLabel("")
        self.ilevel_label.setStyleSheet("font-size: 13px; color: #a0a0a0;")
        card_layout.addWidget(self.ilevel_label)

        self.battery_label = QLabel("")
        self.battery_label.setStyleSheet("font-size: 13px; color: #a0a0a0;")
        card_layout.addWidget(self.battery_label)

        layout.addWidget(card)

        # ECU list
        ecu_title = QLabel("Connected ECUs")
        ecu_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #e0e0e0; margin-top: 8px;")
        layout.addWidget(ecu_title)

        self.ecu_count_label = QLabel("")
        self.ecu_count_label.setStyleSheet("font-size: 12px; color: #a0a0a0;")
        layout.addWidget(self.ecu_count_label)

        # Scrollable ECU tags
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.ecu_container = QWidget()
        self.ecu_layout = QVBoxLayout(self.ecu_container)
        self.ecu_layout.setSpacing(4)
        scroll.setWidget(self.ecu_container)
        layout.addWidget(scroll, stretch=1)

    def load_data(self, connection: Any, series: str = "") -> None:
        """Populate the dashboard with vehicle data from the connection.

        For mock connections, reads from MockConnection.data.
        For real connections, expects data to be passed via
        ``populate()`` after a ``PostConnectWorker`` completes.
        This method exists for backward compatibility with the
        direct-connect flow (mock mode).
        """
        # Try mock data first (MockConnection has .data attribute)
        if hasattr(connection, "data") and connection.data:
            vehicle = connection.data.get("vehicle", {})
            ecus = connection.data.get("svt_ecus", [])
            self._ecus = ecus

            self.model_label.setText(
                vehicle.get("model", "Unknown model")
            )
            self.vin_label.setText(
                f"VIN: {vehicle.get('vin', 'Unknown')}"
            )
            self.mileage_label.setText(
                f"Mileage: {vehicle.get('mileage_km', 0):,} km"
            )
            self.prod_date_label.setText(
                f"Production Date: {vehicle.get('production_date', 'Unknown')}"
            )

            # Read I-Level from MockConnection's canned response for 0xF18A
            try:
                resp = connection.send_uds(0x10, bytes([0x22, 0xF1, 0x8A]))
                if resp[0] == 0x62:
                    ilevel = resp[3:].decode("ascii", errors="ignore").strip("\x00 ")
                    self.ilevel_label.setText(f"I-Level: {ilevel}")
                else:
                    self.ilevel_label.setText("I-Level: unavailable")
            except Exception:
                self.ilevel_label.setText("I-Level: unavailable")

            # Read battery voltage from MockConnection's response for 0xF40C
            try:
                resp = connection.send_uds(0x10, bytes([0x22, 0xF4, 0x0C]))
                if resp[0] == 0x62 and len(resp) >= 5:
                    voltage_raw = int.from_bytes(resp[3:5], "big")
                    voltage = voltage_raw / 10.0
                    self.battery_label.setText(f"Battery: {voltage:.1f}V")
                else:
                    self.battery_label.setText("Battery: unavailable")
            except Exception:
                self.battery_label.setText("Battery: unavailable")

            self.ecu_count_label.setText(f"{len(ecus)} ECUs detected")
            self._populate_ecus(ecus)
            return

        # Real connection: data will be populated via populate() later.
        # Show a placeholder until then.
        model_map = {"F": "F-series", "G": "G-series", "U": "U-series", "I": "I-series"}
        self.model_label.setText(model_map.get(series, "BMW"))
        self.vin_label.setText("VIN: reading...")
        self.mileage_label.setText("Mileage: reading...")
        self.ilevel_label.setText("I-Level: reading...")
        self.battery_label.setText("Battery: reading...")
        self.ecu_count_label.setText("Scanning ECUs...")

    def populate(
        self,
        results: dict[str, object],
        series: str = "",
        vin: str = "",
    ) -> None:
        """Populate the dashboard from pre-loaded UDS results.

        Called by ``MainWindow`` after ``PostConnectWorker`` finishes.
        No UDS calls are made here — this is pure display.

        Args:
            results: Dict with keys like ``i-level``, ``mileage``,
                     ``battery_voltage``, ``ecu_list``, ``prod_date``,
                     ``fa_xml``, ``type_code``.
            series: BMW series letter (F/G/U/I).
            vin: VIN already read during connect (may be empty).
        """
        model_map = {"F": "F-series", "G": "G-series", "U": "U-series", "I": "I-series"}

        # Model / VIN
        self.model_label.setText(model_map.get(series, "BMW"))
        self.vin_label.setText(f"VIN: {vin or results.get('vin', 'Unknown')}")

        # I-Level
        ilevel = results.get("i-level")
        self.ilevel_label.setText(
            f"I-Level: {ilevel}" if ilevel else "I-Level: unavailable"
        )

        # Mileage
        mileage = results.get("mileage")
        self.mileage_label.setText(
            f"Mileage: {mileage}" if mileage else "Mileage: unavailable"
        )

        # Battery voltage
        battery = results.get("battery_voltage")
        self.battery_label.setText(
            f"Battery: {battery}" if battery else "Battery: unavailable"
        )

        # Production date
        prod_date = results.get("prod_date")
        self.prod_date_label.setText(
            f"Production Date: {prod_date}" if prod_date else ""
        )

        # SVT ECU list
        ecus = results.get("ecu_list")
        if isinstance(ecus, list):
            self._ecus = ecus
            self.ecu_count_label.setText(f"{len(ecus)} ECUs detected")
            self._populate_ecus(ecus)
        elif isinstance(ecus, dict):
            ecus_list = ecus.get("ecus", [])
            self._ecus = ecus_list
            self.ecu_count_label.setText(f"{len(ecus_list)} ECUs detected")
            self._populate_ecus(ecus_list)
        else:
            self.ecu_count_label.setText("ECU scan failed")

        # Store FA / type code for coding_page
        self._fa_xml = results.get("fa_xml", "")
        self._type_code = results.get("type_code", "")

    def _populate_ecus(self, ecus: list) -> None:
        """Fill the ECU list with name + description tags."""
        # Clear existing layouts and widgets recursively
        while self.ecu_layout.count():
            item = self.ecu_layout.takeAt(0)
            if item is None:
                continue
            child = item.widget()
            if child is not None:
                child.deleteLater()
            else:
                # It's a layout — recursively clean up
                child_layout = item.layout()
                if child_layout is not None:
                    self._clear_layout(child_layout)

        if not ecus:
            empty = QLabel("No ECU data available")
            empty.setStyleSheet("color: #555555; font-size: 12px;")
            self.ecu_layout.addWidget(empty)
            self.ecu_layout.addStretch()
            return

        # Add ECU tags in a flowing row layout
        row_layout = QHBoxLayout()
        row_layout.setSpacing(6)
        chips_per_row = 4
        count = 0

        for ecu in ecus:
            name = ecu.get("name", "???")
            chip = QLabel(name)
            chip.setStyleSheet(
                "background: #16213e; color: #1C69D4; border: 1px solid #1C69D4; "
                "border-radius: 6px; padding: 4px 10px; font-size: 12px; "
                "font-weight: bold;"
            )
            chip.setToolTip(ecu.get("description", name))
            row_layout.addWidget(chip)
            count += 1

            if count % chips_per_row == 0:
                self.ecu_layout.addLayout(row_layout)
                row_layout = QHBoxLayout()
                row_layout.setSpacing(6)

        if count % chips_per_row != 0:
            row_layout.addStretch()
            self.ecu_layout.addLayout(row_layout)

        self.ecu_layout.addStretch()

    @staticmethod
    def _clear_layout(layout: QLayout) -> None:
        """Recursively remove and destroy all widgets in a layout."""
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                continue
            child = item.widget()
            if child is not None:
                child.deleteLater()
            else:
                child_layout = item.layout()
                if child_layout is not None:
                    VehiclePage._clear_layout(child_layout)
