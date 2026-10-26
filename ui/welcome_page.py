"""Welcome page -- series picker, interface dropdown, connect button.

Displayed before connection. User selects series (F/G/U/I) and network
interface, then clicks Connect.

Reference: docs/16-ui-spec.md (Screen 1), docs/17-ui-decisions.md (Decisions 1-3)
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.connection import list_interfaces


class WelcomePage(QWidget):
    """Welcome/connect screen with series picker, interface dropdown, and connect button.

    Signals:
        connect_clicked: Emitted when user clicks Connect.
            Args: (series: str, interface: str)
    """

    connect_clicked = Signal(str, str)

    SERIES_OPTIONS = [
        ("", "-- Select your BMW series --"),
        ("F", "F-series (2011-2019): 1-7 Series, X1-X6, M2-M6"),
        ("G", "G-series (2018+): 1-8 Series, X1-X7, M2-M8"),
        ("U", "U-series (2023+): XM, iX, U11 X1"),
        ("I", "I-series (2013+): i3, i4, i5, i7, iX1, iX3"),
    ]

    SERIES_PROTOCOL = {"F": "HSFZ", "G": "DoIP", "U": "DoIP", "I": "DoIP"}

    INSTRUCTIONS = [
        "Press the Start/Stop button once (without pressing the brake) to enter ignition mode",
        "For vehicles with Comfort Access: press Start/Stop 3 times quickly",
        "Fasten the driver seatbelt to prevent auto-shutoff after ~15 min",
        "Turn off lights, A/C, and radio to reduce battery drain",
        "Connect the ENET cable BEFORE turning on ignition",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._demo_mode = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)

        # BMW logo
        logo = QLabel("\U0001F697")
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet("font-size: 80px; color: #1C69D4; background: transparent;")
        layout.addWidget(logo)
        layout.addSpacing(8)

        # Title
        title = QLabel("BMW Self Service")
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignCenter)
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
        self._populate_interfaces()
        self.interface_combo.currentIndexChanged.connect(self._on_choices_changed)
        self.interface_layout.addWidget(self.interface_combo)
        layout.addWidget(self.interface_container)
        layout.addSpacing(24)

        # Connect button
        self.connect_btn = QPushButton("Connect to your BMW")
        self.connect_btn.setObjectName("connectButton")
        self.connect_btn.setMinimumWidth(320)
        self.connect_btn.setEnabled(False)
        self.connect_btn.clicked.connect(self._on_connect_clicked)
        layout.addWidget(self.connect_btn, alignment=Qt.AlignCenter)
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

    def _populate_interfaces(self):
        self.interface_combo.clear()
        self.interface_combo.addItem("-- Select interface --", "")
        try:
            ifaces = list_interfaces()
            for iface in ifaces:
                self.interface_combo.addItem(iface, iface)
        except Exception:
            self.interface_combo.addItem("en0", "en0")
            self.interface_combo.addItem("en7", "en7")

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
