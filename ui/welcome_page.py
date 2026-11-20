"""Welcome page -- series picker, interface dropdown, connect button.

Displayed before connection. User selects series (F/G/U/I) and network
interface, then clicks Connect.

Reference: plan.md#connection-and-display and AGENTS.md#implementation-rules.
"""

import logging
from threading import Event
from typing import cast

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.connection import _InterfaceInfo, list_interfaces_detailed
from app.worker import ConnectWorker
from ui.cockpit import CockpitCard, caption
from ui.form_inputs import SelectInput

logger = logging.getLogger(__name__)


class WelcomePage(QWidget):
    """Welcome/connect screen with series picker, interface dropdown, and connect button.

    Signals:
        connect_clicked: Emitted when user clicks Connect.
            Args: (series: str, interface: str)
    """

    connect_clicked = Signal(str, str)

    SERIES_OPTIONS = [
        ("", "-- Select your BMW series --"),
        ("F", "F-series chassis"),
        ("G", "G-series chassis"),
        ("U", "U-series chassis"),
        ("I", "BMW i / electric models"),
    ]

    INSTRUCTIONS = [
        "Press the Start/Stop button once (without pressing the brake) to enter ignition mode",
        "For vehicles with Comfort Access: press Start/Stop 3 times quickly",
        "Fasten the driver seatbelt to prevent auto-shutoff after ~15 min",
        "Turn off lights, A/C, and radio to reduce battery drain",
        "Connect the ENET cable BEFORE turning on ignition",
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the connection choices and start a bounded adapter inventory."""
        super().__init__(parent)
        self._demo_mode = False
        self._worker: ConnectWorker | None = None
        self._saved_interface = ""
        self._adapters: list[_InterfaceInfo] | None = None
        self._inventory_logged = False
        self._inventory_error_pending = False
        self._adapter_polling = True
        self._adapter_timer = QTimer(self)
        self._adapter_timer.setInterval(3000)
        self._adapter_timer.timeout.connect(self._populate_interfaces)
        self._setup_ui()
        self._adapter_timer.start()

    def _setup_ui(self) -> None:
        """Present the existing connection choices inside the shared cockpit shell."""
        self.setObjectName("connectionPage")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 28)
        outer.setSpacing(18)
        self.mode_label = caption("ENET connection", "identity")
        outer.addWidget(self.mode_label)
        outer.addWidget(caption("Connect to your BMW", "connectionTitle"))
        outer.addWidget(
            caption("Select your vehicle series and network adapter to start a diagnostic session.")
        )

        grid = QGridLayout()
        grid.setSpacing(20)
        setup = CockpitCard("Connection setup")
        setup.box.setSpacing(14)

        # Series picker
        series_label = caption("Vehicle series", "identity")
        setup.box.addWidget(series_label)
        self.series_combo = SelectInput()
        self.series_combo.setAccessibleName("Vehicle series")
        self.series_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.series_combo.setMinimumContentsLength(24)
        self.series_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for value, label in self.SERIES_OPTIONS:
            self.series_combo.addItem(label, value)
        series_label.setBuddy(self.series_combo)
        self.series_combo.currentIndexChanged.connect(self._on_choices_changed)
        setup.box.addWidget(self.series_combo)
        setup.box.addSpacing(8)

        # Interface picker (hidden in DEMO mode)
        self.interface_container = QWidget()
        self.interface_container.setProperty("class", "transparent")
        self.interface_layout = QVBoxLayout(self.interface_container)
        self.interface_layout.setContentsMargins(0, 0, 0, 0)
        self.interface_layout.setSpacing(12)
        iface_label = caption("Network adapter", "identity")
        self.interface_layout.addWidget(iface_label)
        self.interface_combo = SelectInput()
        self.interface_combo.setAccessibleName("Network adapter")
        self.interface_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.interface_combo.setMinimumContentsLength(24)
        self.interface_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        iface_label.setBuddy(self.interface_combo)
        self._interface_view = self.interface_combo.view()
        self._interface_view.installEventFilter(self)
        self.interface_layout.addWidget(self.interface_combo)
        self.interface_layout.addWidget(
            caption("Choose the physical Ethernet or Wi-Fi adapter connected to your ENET device.")
        )
        self._populate_interfaces()
        self.interface_combo.currentIndexChanged.connect(self._on_choices_changed)
        setup.box.addWidget(self.interface_container)
        setup.box.addSpacing(12)

        # Connect button
        self.connect_btn = QPushButton("Connect to your BMW")
        self.connect_btn.setObjectName("connectionAction")
        self.connect_btn.setEnabled(False)
        self.connect_btn.clicked.connect(self._on_connect_clicked)
        setup.box.addWidget(self.connect_btn)
        setup.box.addWidget(
            caption("Connection details and available vehicle observations appear after discovery.")
        )
        setup.box.addStretch()
        grid.addWidget(setup, 0, 0)

        # Instructions
        preparation = CockpitCard("Prepare your vehicle")
        preparation.box.setSpacing(14)
        for point in self.INSTRUCTIONS:
            preparation.box.addWidget(caption("•  " + point))
        preparation.box.addStretch()
        grid.addWidget(preparation, 0, 1)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)
        outer.addLayout(grid)
        outer.addStretch()

    @Slot()
    def _populate_interfaces(self) -> None:
        """Refresh bounded native metadata in the existing background-worker lifecycle."""
        if not self._adapter_polling or self._worker is not None:
            return
        if not self.interface_combo.count():
            self.interface_combo.addItem("Loading network adapters…", "")
        worker = ConnectWorker(self._load_interfaces, "")
        self._worker = worker
        worker.result_ready.connect(self._on_interfaces_loaded)
        worker.error.connect(self._on_interfaces_error)
        worker.finished.connect(self._on_interfaces_finished)
        worker.start()

    def _load_interfaces(self, _cancelled: Event) -> list[_InterfaceInfo]:
        """Collect and log initial adapter metadata in the worker without accessing widgets."""
        adapters = list_interfaces_detailed()
        if not self._inventory_logged:
            self._inventory_logged = True
            for interface in adapters:
                logger.info(
                    "Adapter candidate=%s IPv4=%s MAC=%s description=%s",
                    interface.name,
                    interface.ip,
                    interface.mac,
                    interface.description,
                )
            try:
                import netifaces

                for interface in adapters:
                    logger.debug(
                        "Adapter %s IPv4 configuration=%s",
                        interface.name,
                        netifaces.ifaddresses(interface.name).get(netifaces.AF_INET, []),
                    )
            except Exception:
                logger.warning("Interface configuration logging failed", exc_info=True)
        return adapters

    @Slot(object)
    def _on_interfaces_loaded(self, result: object) -> None:
        """Display friendly labels while retaining the wired system ID as item data."""
        worker = self.sender()
        if (
            not isinstance(worker, ConnectWorker)
            or worker is not self._worker
            or worker.property("retired_by_main")
            or worker.cancelled
            or not self._adapter_polling
        ):
            return
        self._inventory_error_pending = False
        adapters = cast(list[_InterfaceInfo], result)
        if adapters == self._adapters or self.interface_combo.view().isVisible():
            return
        selected = (
            self._saved_interface if self._demo_mode else self.interface_combo.currentData() or ""
        )
        self._adapters = adapters
        self.interface_combo.clear()
        self.interface_combo.addItem(
            "-- Select interface --" if adapters else "No physical network adapters found", ""
        )
        for adapter in adapters:
            self.interface_combo.addItem(adapter.display_text(), adapter.name)
            self.interface_combo.setItemData(
                self.interface_combo.count() - 1,
                f"Interface: {adapter.name}",
                Qt.ItemDataRole.ToolTipRole,
            )
        index = self.interface_combo.findData(selected)
        if index > 0 and not self._demo_mode:
            self.interface_combo.setCurrentIndex(index)
        elif self._demo_mode:
            self._saved_interface = selected if index > 0 else ""

    @Slot(str)
    def _on_interfaces_error(self, _message: str) -> None:
        """Keep an inventory failure explicit without offering guessed interface IDs."""
        worker = self.sender()
        if (
            not isinstance(worker, ConnectWorker)
            or worker is not self._worker
            or worker.cancelled
            or worker.property("retired_by_main")
            or not self._adapter_polling
        ):
            return
        self._inventory_error_pending = True
        self._apply_inventory_error()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Apply a pending inventory failure after the popup has finished closing."""
        if watched is self._interface_view and event.type() == QEvent.Type.Hide:
            QTimer.singleShot(0, self._apply_inventory_error)
        return super().eventFilter(watched, event)

    @Slot()
    def _apply_inventory_error(self) -> None:
        """Keep open choices intact; clear them only for a still-current inventory failure."""
        if (
            not self._inventory_error_pending
            or not self._adapter_polling
            or self.interface_combo.view().isVisible()
        ):
            return
        self._inventory_error_pending = False
        self._adapters = None
        self.interface_combo.clear()
        self.interface_combo.addItem("Network adapter inventory unavailable", "")

    @Slot()
    def _on_interfaces_finished(self) -> None:
        """Retain the worker until completion and cooperate with main-window shutdown."""
        worker = self.sender()
        if worker is self._worker:
            self._worker = None
            if self._adapter_polling and isinstance(worker, ConnectWorker) and worker.cancelled:
                self._populate_interfaces()
        if isinstance(worker, ConnectWorker) and not worker.property("retired_by_main"):
            worker.deleteLater()

    def set_adapter_polling(self, enabled: bool) -> None:
        """Poll only while disconnected, ignoring any result from a paused refresh."""
        if enabled == self._adapter_polling:
            return
        self._adapter_polling = enabled
        if enabled:
            self._adapter_timer.start()
            self._populate_interfaces()
        else:
            self._adapter_timer.stop()
            self._inventory_error_pending = False
            if self._worker is not None:
                self._worker.stop()

    def set_demo_mode(self, enabled):
        self._demo_mode = enabled
        self.mode_label.setText("DEMO mode · Simulated vehicle" if enabled else "ENET connection")
        self.connect_btn.setText("Connect DEMO vehicle" if enabled else "Connect to your BMW")
        self.interface_container.setVisible(not enabled)
        if enabled:
            # Remember current selection for restore
            self._saved_interface = self.interface_combo.currentData() or ""
            self.interface_combo.setCurrentIndex(0)
        else:
            # Restore previous selection if it was saved
            saved = self.interface_combo.findData(self._saved_interface)
            self.interface_combo.setCurrentIndex(saved if saved > 0 else 0)
        self._on_choices_changed()

    def _on_choices_changed(self):
        series = self.series_combo.currentData()
        iface = self.interface_combo.currentData()

        enable = bool(series) if self._demo_mode else bool(series) and bool(iface)

        self.connect_btn.setEnabled(enable)

    def _on_connect_clicked(self):
        series = self.series_combo.currentData()
        iface = self.interface_combo.currentData() if not self._demo_mode else ""
        if series:
            self.connect_clicked.emit(series, iface)
