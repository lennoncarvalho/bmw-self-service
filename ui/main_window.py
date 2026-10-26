"""Main window shell for BMW Self Service.

Single QMainWindow + QStackedWidget architecture.
Reference: docs/16-ui-spec.md, docs/17-ui-decisions.md
"""

import logging
from typing import Any

from PySide6.QtCore import Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.connection import DoIPConnection, HSFZConnection
from app.mock_connection import MockConnection
from ui.backups_page import BackupsPage
from ui.coding_page import CodingPage
from ui.diagnostics_page import DiagnosticsPage
from ui.service_history_page import ServiceHistoryPage
from ui.vehicle_page import VehiclePage
from ui.welcome_page import WelcomePage

logger = logging.getLogger(__name__)


# Status indicators (replace_emoji)
RED_DOT = chr(0x1F534)
ORANGE_DOT = chr(0x1F7E0)
GREEN_DOT = chr(0x1F7E2)
GEAR_ICON = chr(0x2699)
HOME_ICON = chr(0x1F3E0)
SEARCH_ICON = chr(0x1F50D)
WRENCH_ICON = chr(0x1F6E0)
CLIPBOARD_ICON = chr(0x1F4CB)


class MainWindow(QMainWindow):
    """Main application window for the BMW Self Service."""

    NAV_ITEMS = [
        ("Vehicle", HOME_ICON),
        ("Diagnostics", SEARCH_ICON),
        ("Coding", WRENCH_ICON),
        ("History", CLIPBOARD_ICON),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("BMW Self Service")
        self.setMinimumSize(800, 600)
        self._demo_mode = False
        self._connection: object | None = None
        self._connected = False
        self._worker: QThread | None = None
        self._alive_timer: QTimer | None = None
        self._tester_present_timer: QTimer | None = None
        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_layout.addWidget(self._build_top_bar())

        self.stack = QStackedWidget()

        self.welcome_page = WelcomePage()
        self.welcome_page.connect_clicked.connect(self._on_connect_requested)
        self.stack.addWidget(self.welcome_page)

        self.vehicle_page = VehiclePage()
        self.stack.addWidget(self.vehicle_page)

        self.diag_page = DiagnosticsPage()
        self.stack.addWidget(self.diag_page)

        self.coding_page = CodingPage()
        self.stack.addWidget(self.coding_page)

        self.history_page = ServiceHistoryPage()
        self.stack.addWidget(self.history_page)

        self.backups_page = BackupsPage()
        self.stack.addWidget(self.backups_page)

        main_layout.addWidget(self.stack, stretch=1)

        self.spinner_overlay = self._build_spinner()

        main_layout.addWidget(self._build_bottom_nav())

    def _build_top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("topBar")
        bar.setFixedHeight(48)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 4, 12, 4)

        self.status_dot = QLabel(RED_DOT)
        self.status_dot.setObjectName("statusDot")
        self.status_dot.setStyleSheet("font-size: 12px;")
        self.status_dot.setToolTip("Disconnected")
        layout.addWidget(self.status_dot)

        self.car_label = QLabel("Not connected")
        self.car_label.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #e0e0e0;"
        )
        layout.addWidget(self.car_label)
        layout.addSpacing(8)

        self.vin_label = QLabel("")
        self.vin_label.setStyleSheet("font-size: 11px; color: #a0a0a0;")
        layout.addWidget(self.vin_label)

        layout.addStretch()

        gear_btn = QPushButton(GEAR_ICON)
        gear_btn.setFixedSize(36, 36)
        gear_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(255,255,255,0.08);"
            "  border: none;"
            "  font-size: 18px;"
            "  color: #c0c0d0;"
            "  border-radius: 18px;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(255,255,255,0.15);"
            "  color: #ffffff;"
            "}"
        )
        gear_btn.clicked.connect(self._show_gear_menu)
        layout.addWidget(gear_btn)

        return bar

    def _build_bottom_nav(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("bottomNav")
        bar.setFixedHeight(68)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        for i, (label, icon) in enumerate(self.NAV_ITEMS):
            btn = QPushButton(f"{icon}\n{label}")
            btn.setObjectName("navButton")
            btn.setCheckable(True)
            btn.setEnabled(False)
            btn.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
            )
            self.nav_group.addButton(btn, i)
            layout.addWidget(btn)

        self.nav_group.idClicked.connect(self._on_nav_clicked)
        return bar

    @staticmethod
    def _make_placeholder(title_text: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)
        label = QLabel(f"{title_text}\n\nConnect to a vehicle to begin")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 18px; color: #a0a0a0;")
        layout.addWidget(label)
        return page

    def _build_spinner(self) -> QFrame:
        overlay = QFrame(self)
        overlay.setObjectName("spinnerOverlay")
        overlay.setFixedSize(320, 160)
        overlay.setVisible(False)

        layout = QVBoxLayout(overlay)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)

        self.spinner_text = QLabel("Working...")
        self.spinner_text.setObjectName("spinnerText")
        self.spinner_text.setAlignment(Qt.AlignCenter)
        self.spinner_text.setWordWrap(True)
        layout.addWidget(self.spinner_text)

        # G-13: Cancel button (appears after 10s)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setVisible(False)
        self._cancel_btn.setStyleSheet(
            "QPushButton { background: #3a3a5a; color: #a0a0a0; "
            "border-radius: 8px; padding: 6px 24px; font-weight: bold; }"
            "QPushButton:hover { background: #5a5a7a; color: white; }"
        )
        layout.addWidget(self._cancel_btn, alignment=Qt.AlignCenter)

        # G-13: Timer for showing cancel button and triggering retry
        self._spinner_cancel_timer = QTimer(self)
        self._spinner_cancel_timer.setSingleShot(True)
        self._spinner_cancel_timer.timeout.connect(self._show_spinner_cancel)

        self._spinner_retry_timer = QTimer(self)
        self._spinner_retry_timer.setSingleShot(True)
        self._spinner_retry_timer.timeout.connect(self._show_retry_dialog)

        return overlay

    def _show_spinner_cancel(self) -> None:
        """G-13: Show cancel button after 10s."""
        self._cancel_btn.setVisible(True)

    def _show_retry_dialog(self) -> None:
        """G-13: Show retry dialog after 30s timeout."""
        self.hide_spinner()
        reply = QMessageBox.question(
            self,
            "Vehicle Not Responding",
            "The car is not responding.\n"
            "Check ignition and ENET cable connection.\n\n"
            "Retry?",
            QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Retry,
        )
        if reply == QMessageBox.StandardButton.Retry:
            self._on_retry_connect()
        else:
            self._on_disconnect()

    def _position_spinner(self) -> None:
        if self.spinner_overlay and self.stack:
            stack_geo = self.stack.geometry()
            x = (stack_geo.width() - self.spinner_overlay.width()) // 2
            y = (stack_geo.height() - self.spinner_overlay.height()) // 2
            if x >= 0 and y >= 0:
                self.spinner_overlay.move(x, y)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_spinner()

    def show_spinner(self, message: str = "Working...") -> None:
        self.spinner_text.setText(message)
        self._cancel_btn.setVisible(False)
        self._position_spinner()
        self.spinner_overlay.setVisible(True)
        QApplication.processEvents()
        # G-13: Start timers for cancel (10s) and retry (30s)
        self._spinner_cancel_timer.start(10000)
        self._spinner_retry_timer.start(30000)

    def hide_spinner(self) -> None:
        self.spinner_overlay.setVisible(False)
        self._cancel_btn.setVisible(False)
        self._spinner_cancel_timer.stop()
        self._spinner_retry_timer.stop()

    # ---- Gear menu ----

    def _show_gear_menu(self) -> None:
        menu = QMenu(self)

        self._demo_action = QAction("Enable DEMO Mode", self)
        self._demo_action.setCheckable(True)
        self._demo_action.setChecked(self._demo_mode)
        self._demo_action.triggered.connect(self._on_demo_toggled)
        if self._connected:
            self._demo_action.setEnabled(False)
        menu.addAction(self._demo_action)

        menu.addSeparator()

        backups_action = QAction("Backups...", self)
        backups_action.triggered.connect(self._on_backups)
        menu.addAction(backups_action)

        about_action = QAction("About", self)
        about_action.triggered.connect(self._on_about)
        menu.addAction(about_action)

        menu.addSeparator()

        disc_action = QAction("Disconnect", self)
        disc_action.triggered.connect(self._on_disconnect)
        if not self._connected:
            disc_action.setEnabled(False)
        menu.addAction(disc_action)

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        menu.addAction(exit_action)

        sender = self.sender()
        if hasattr(sender, "mapToGlobal"):
            gear_pos = sender.mapToGlobal(sender.rect().bottomLeft())
            menu.exec(gear_pos)
        else:
            menu.exec(self.mapToGlobal(self.rect().center()))

    def _on_demo_toggled(self, checked: bool) -> None:
        self._demo_mode = checked
        self.welcome_page.set_demo_mode(checked)
        logger.info("DEMO mode %s", "enabled" if checked else "disabled")

    # ---- Navigation ----

    def _on_nav_clicked(self, index: int) -> None:
        self.stack.setCurrentIndex(index + 1)

    # ---- Connection flow ----

    def _on_connect_requested(self, series: str, interface: str) -> None:
        if self._demo_mode:
            self._connect_demo(series)
        else:
            self._connect_real(series, interface)

    def _connect_demo(self, series: str) -> None:
        self.show_spinner("Starting DEMO mode...")

        def do_connect():
            conn = MockConnection()
            conn.connect()
            return (conn, "")

        self._async_connect(do_connect, series)

    def _connect_real(self, series: str, interface: str) -> None:
        logger.info(
            "Connecting: series=%s interface=%s proto=%s",
            series, interface,
            {chr(70): "HSFZ", chr(71): "DoIP", chr(85): "DoIP", chr(73): "DoIP"}.get(series, "?"),
        )
        self.show_spinner(f"Searching for vehicle on {interface}...")

        def do_connect():
            from app.connection import discover_zgw

            logger.debug("Step 1: UDP discovery on %s", interface)
            info = discover_zgw(interface, timeout=5.0)

            if info is None:
                logger.warning("Discovery failed, trying DHCP fallback")
                from app.connection import start_dhcp_server
                if start_dhcp_server(interface):
                    logger.debug("DHCP server started, waiting 10s")
                    import time
                    time.sleep(10)
                    info = discover_zgw(interface, timeout=5.0)
                    if info is None:
                        raise ConnectionError(
                            "Vehicle not found. Check the ENET cable "
                            "and ensure ignition is on."
                        )
                else:
                    logger.debug("DHCP denied, waiting 20s for APIPA")
                    import time
                    time.sleep(20)
                    info = discover_zgw(interface, timeout=5.0)
                    if info is None:
                        raise ConnectionError(
                            "Vehicle not found. DHCP server requires "
                            "admin/root privileges to assist with "
                            "IP assignment."
                        )

            host = info["ip"]
            logger.info("Step 2: TCP connect to %s", host)
            if series == "F":
                conn = HSFZConnection(host)
            else:
                conn = DoIPConnection(host)

            if not conn.connect():
                raise ConnectionError(
                    "Failed to connect to vehicle at " + host
                )

            logger.info("Step 3: reading vehicle identity")
            vin = ""
            # Extended diagnostic session on the ZGW
            try:
                conn.send_uds(0x10, bytes([0x10, 0x03]))
                resp = conn.send_uds(0x10, bytes([0x22, 0xF1, 0x90]))
                if len(resp) >= 4 and resp[0] == 0x62:
                    vin_bytes = resp[3:].decode("ascii", errors="ignore").strip("\x00 ")
                    vin = vin_bytes
            except Exception as exc:
                logger.warning("VIN/DSC read failed in worker: %s", exc)

            return (conn, vin)

        self._async_connect(do_connect, series)

    def _async_connect(self, connect_fn, series: str) -> None:

        class ConnectWorker(QThread):
            result_signal = Signal(object)
            error_signal = Signal(str)
            progress_signal = Signal(str)

            def __init__(self, fn):
                super().__init__()
                self.fn = fn

            def run(self):
                try:
                    result = self.fn()
                    self.result_signal.emit(result)
                except Exception as e:
                    self.error_signal.emit(str(e))

        self._worker = ConnectWorker(connect_fn)
        self._worker._connect_series = series  # captured for slot
        self._worker.result_signal.connect(self._on_worker_result)
        self._worker.error_signal.connect(self._on_connect_error)
        self._worker.progress_signal.connect(self.show_spinner)
        self._worker.start()

    @Slot(object)
    def _on_worker_result(self, result: object) -> None:
        """Handle worker result — runs on the main thread."""
        conn: Any
        vin: str
        conn, vin = result  # (connection, vin_str) tuple
        series = getattr(self._worker, "_connect_series", "")
        self._on_connect_success(conn, vin, series)

    def _on_connect_success(self, connection: Any, vin: str, series: str) -> None:
        self._connection = connection
        self._connected = True

        model = ""
        if vin:
            logger.debug("VIN from worker: %s", vin)

        # For mock connections: pull from stored data
        if hasattr(connection, "data") and connection.data:
            vehicle = connection.data.get("vehicle", {})
            if not model:
                model = vehicle.get("model", "")
            if not vin:
                vin = vehicle.get("vin", "")

        prefix = "[DEMO] " if self._demo_mode else ""
        self.status_dot.setText(ORANGE_DOT if self._demo_mode else GREEN_DOT)
        self.status_dot.setToolTip(
            "[DEMO] Demo Mode" if self._demo_mode else "Connected"
        )
        self.car_label.setText(
            f"{prefix}{model or f'BMW {series}-series'}"
        )
        self.vin_label.setText(f"VIN: {vin}" if vin else "")

        for btn in self.nav_group.buttons():
            btn.setEnabled(True)

        self.nav_group.button(0).setChecked(True)
        self.stack.setCurrentIndex(1)

        # Load vehicle data into the dashboard
        self.vehicle_page.load_data(connection, series)
        # Pass connection and ECUs to diagnostics page
        ecus: list[dict] = []
        if hasattr(connection, "data") and connection.data:
            ecus = connection.data.get("svt_ecus", [])
        self.diag_page.set_connection(connection, ecus)
        # Pass connection to service history page
        self.history_page.set_connection(connection)
        self.coding_page.set_connection(connection)

        # Start keep-alive timers for real connections
        if not self._demo_mode:
            self._start_keepalive()

        self.hide_spinner()
        logger.info("Connected successfully (demo=%s)", self._demo_mode)

    def _start_keepalive(self) -> None:
        """Start HSFZ alive-check and UDS TesterPresent timers."""
        conn = self._connection
        if conn is None:
            return

        # Transport-layer: HSFZ alive check every 2 seconds
        if hasattr(conn, "alive_check"):
            logger.debug("Starting HSFZ alive-check timer (every 2s)")
            self._alive_timer = QTimer(self)
            self._alive_timer.timeout.connect(conn.alive_check)
            self._alive_timer.start(2000)

        # Application-layer: UDS TesterPresent every 2.5 seconds
        if hasattr(conn, "send_uds"):
            _first_tp = [True]  # mutable to capture in closure

            def _tester_present():
                try:
                    conn.send_uds(0x10, bytes([0x3E, 0x00]))
                    if _first_tp[0]:
                        logger.debug("Starting TesterPresent timer (every 2.5s)")
                        _first_tp[0] = False
                except Exception:
                    pass

            self._tester_present_timer = QTimer(self)
            self._tester_present_timer.timeout.connect(_tester_present)
            self._tester_present_timer.start(2500)

    def _stop_keepalive(self) -> None:
        """Stop all keep-alive timers."""
        for timer in (self._alive_timer, self._tester_present_timer):
            if timer is not None:
                timer.stop()
                timer.deleteLater()
        self._alive_timer = None
        self._tester_present_timer = None

    def _on_connect_error(self, error_msg: str) -> None:
        self.hide_spinner()
        self.status_dot.setText(RED_DOT)
        self.status_dot.setToolTip("Disconnected")

        # G-14: Map error messages to user-friendly dialogs
        friendly = error_msg
        if "admin" in error_msg.lower() or "root" in error_msg.lower():
            friendly = (
                "DHCP server requires administrator privileges.\n\n"
                "Please run the application with elevated permissions "
                "to enable automatic IP assignment for the ENET cable."
            )
        elif "not found" in error_msg.lower() or "vehicle not found" in error_msg.lower():
            friendly = (
                "Vehicle not found on the network.\n\n"
                "1. Ensure the ENET cable is connected\n"
                "2. Check that ignition is on (press Start/Stop once)\n"
                "3. Verify the correct network interface is selected"
            )

        QMessageBox.warning(
            self,
            "Connection Failed",
            friendly or "Could not connect to the vehicle.",
        )
        logger.warning("Connection failed: %s", error_msg)

    def _on_retry_connect(self) -> None:
        """G-13: Re-attempt connection after timeout retry."""
        if self._connection:
            # Re-use last known settings
            pass
        self.stack.setCurrentIndex(0)

    # ---- Disconnect ----

    def _on_disconnect(self) -> None:
        logger.info("Disconnecting from vehicle...")
        self._stop_keepalive()
        if self._connection:
            try:
                if hasattr(self._connection, "disconnect"):
                    self._connection.disconnect()
            except Exception as e:
                logger.warning("Error during disconnect: %s", e)
            self._connection = None

        self._connected = False

        self.status_dot.setText(RED_DOT)
        self.status_dot.setToolTip("Disconnected")
        self.car_label.setText("Not connected")
        self.vin_label.setText("")

        for btn in self.nav_group.buttons():
            btn.setChecked(False)
            btn.setEnabled(False)

        self.stack.setCurrentIndex(0)
        self.hide_spinner()
        logger.info("Disconnected")

    # ---- Menu actions ----

    def _on_backups(self) -> None:
        self.backups_page.set_connection(self._connection)
        self.stack.setCurrentIndex(6)  # BackupsPage is at index 6

    def _on_about(self) -> None:
        QMessageBox.about(
            self,
            "About",
            "BMW Self Service\nVersion 1.0.0\n\n"
            "Built with Python, PySide6, and a lot of hard work.\n\n"
            "Compatible with BMW F, G, U, I series (2011+).\n"
            "ENET cable required.\n\n"
            "This tool is not affiliated with BMW AG.\n"
            "Use at your own risk.",
        )

    # ---- Public API ----

    def set_connected(self, vin: str, model: str) -> None:
        self.status_dot.setText(
            ORANGE_DOT if self._demo_mode else GREEN_DOT
        )
        self.car_label.setText(model)
        self.vin_label.setText(f"VIN: {vin}")
        for btn in self.nav_group.buttons():
            btn.setEnabled(True)
        self._connected = True

    def set_disconnected(self) -> None:
        self._on_disconnect()

    def _apply_theme(self) -> None:
        from app.theme import apply_theme
        apply_theme(QApplication.instance())
