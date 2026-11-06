"""Welcome page -- series picker, interface dropdown, connect button.

Displayed before connection. User selects series (F/G/U/I) and network
interface, then clicks Connect.

Reference: plan.md#connection-and-display and AGENTS.md#implementation-rules.
"""

from typing import cast

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.connection import _InterfaceInfo, list_interfaces_detailed
from app.worker import ConnectWorker


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
        self._selected_interface = ""
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the welcome screen and asynchronous adapter refresh controls."""
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)

        # BMW logo
        logo = QLabel("\U0001f697")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("font-size: 80px; color: #1C69D4; background: transparent;")
        layout.addWidget(logo)
        layout.addSpacing(8)

        # Title
        title = QLabel("BMW Self Service")
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addSpacing(20)

        # Series picker
        series_label = QLabel("Vehicle Series:")
        series_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #a0a0a0;")
        layout.addWidget(series_label)

        self.series_combo = QComboBox()
        self.series_combo.setMinimumWidth(400)
        for value, label in self.SERIES_OPTIONS:
            self.series_combo.addItem(label, value)
        self.series_combo.currentIndexChanged.connect(self._on_choices_changed)
        layout.addWidget(self.series_combo)
        layout.addSpacing(12)

        # Interface picker (hidden in DEMO mode)
        self.interface_container = QWidget()
        self.interface_layout = QVBoxLayout(self.interface_container)
        self.interface_layout.setContentsMargins(0, 0, 0, 0)

        iface_label = QLabel("Network Interface:")
        iface_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #a0a0a0;")
        self.interface_layout.addWidget(iface_label)

        self.interface_combo = QComboBox()
        self.interface_combo.setMinimumWidth(400)
        adapter_row = QHBoxLayout()
        adapter_row.addWidget(self.interface_combo, 1)
        self.refresh_interfaces_btn = QPushButton("Refresh")
        self.refresh_interfaces_btn.clicked.connect(self._populate_interfaces)
        adapter_row.addWidget(self.refresh_interfaces_btn)
        self.interface_layout.addLayout(adapter_row)
        self._populate_interfaces()
        self.interface_combo.currentIndexChanged.connect(self._on_choices_changed)
        layout.addWidget(self.interface_container)
        layout.addSpacing(24)

        # Connect button
        self.connect_btn = QPushButton("Connect to your BMW")
        self.connect_btn.setObjectName("connectButton")
        self.connect_btn.setMinimumWidth(320)
        self.connect_btn.setEnabled(False)
        self.connect_btn.clicked.connect(self._on_connect_clicked)
        layout.addWidget(self.connect_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(32)

        # Instructions
        instr_title = QLabel("To ensure a stable connection:")
        instr_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #a0a0a0;")
        layout.addWidget(instr_title)

        for point in self.INSTRUCTIONS:
            bullet = QLabel(f"  \u2022 {point}")
            bullet.setStyleSheet("font-size: 12px; color: #a0a0a0; padding: 2px 0;")
            bullet.setWordWrap(True)
            layout.addWidget(bullet)

        layout.addStretch()

    @Slot()
    def _populate_interfaces(self) -> None:
        """Refresh bounded native metadata in the existing background-worker lifecycle."""
        if self._worker is not None:
            return
        self._selected_interface = self.interface_combo.currentData() or ""
        self.interface_combo.clear()
        self.interface_combo.addItem("Loading network adapters…", "")
        self.interface_combo.setEnabled(False)
        self.refresh_interfaces_btn.setEnabled(False)
        worker = ConnectWorker(lambda _cancelled: list_interfaces_detailed(), "")
        self._worker = worker
        worker.result_ready.connect(self._on_interfaces_loaded)
        worker.error.connect(self._on_interfaces_error)
        worker.finished.connect(self._on_interfaces_finished)
        worker.start()

    @Slot(object)
    def _on_interfaces_loaded(self, result: object) -> None:
        """Display friendly labels while retaining the wired system ID as item data."""
        worker = self.sender()
        if (
            not isinstance(worker, ConnectWorker)
            or worker is not self._worker
            or worker.property("retired_by_main")
        ):
            return
        adapters = cast(list[_InterfaceInfo], result)
        self.interface_combo.clear()
        self.interface_combo.addItem("-- Select interface --", "")
        for adapter in adapters:
            self.interface_combo.addItem(
                adapter.display_text(), adapter.name if adapter.wired else ""
            )
            self.interface_combo.setItemData(
                self.interface_combo.count() - 1,
                f"Interface: {adapter.name}"
                + ("" if adapter.wired else "\nENET connections require a wired Ethernet adapter."),
                Qt.ItemDataRole.ToolTipRole,
            )
        index = self.interface_combo.findData(self._selected_interface)
        if index > 0 and not self._demo_mode:
            self.interface_combo.setCurrentIndex(index)
        elif index > 0:
            self._saved_interface_idx = index

    @Slot(str)
    def _on_interfaces_error(self, _message: str) -> None:
        """Keep an inventory failure explicit without offering guessed interface IDs."""
        self.interface_combo.clear()
        self.interface_combo.addItem("Network adapter inventory unavailable", "")

    @Slot()
    def _on_interfaces_finished(self) -> None:
        """Retain the worker until completion and cooperate with main-window shutdown."""
        worker = self.sender()
        if worker is self._worker:
            self._worker = None
            self.interface_combo.setEnabled(True)
            self.refresh_interfaces_btn.setEnabled(True)
        if isinstance(worker, ConnectWorker) and not worker.property("retired_by_main"):
            worker.deleteLater()

    def set_demo_mode(self, enabled):
        self._demo_mode = enabled
        self.interface_container.setVisible(not enabled)
        if enabled:
            # Remember current selection for restore
            self._saved_interface_idx = self.interface_combo.currentIndex()
            self.interface_combo.setCurrentIndex(0)
        else:
            # Restore previous selection if it was saved
            saved = getattr(self, "_saved_interface_idx", 0)
            if saved > 0 and saved < self.interface_combo.count():
                self.interface_combo.setCurrentIndex(saved)
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
