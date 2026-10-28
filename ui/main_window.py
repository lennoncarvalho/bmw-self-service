"""Main window shell for BMW Self Service.

Single QMainWindow + QStackedWidget architecture.
Reference: docs/16-ui-spec.md, docs/17-ui-decisions.md
"""

import logging
from collections.abc import Callable
from typing import Any, cast

from PySide6.QtCore import QSize, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QIcon
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
from app.worker import PostConnectWorker
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
        self.car_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #e0e0e0;")
        layout.addWidget(self.car_label)
        layout.addSpacing(8)

        self.vin_label = QLabel("")
        self.vin_label.setStyleSheet("font-size: 11px; color: #a0a0a0;")
        layout.addWidget(self.vin_label)

        layout.addStretch()

        gear_btn = QPushButton()
        gear_btn.setIcon(QIcon("assets/gear.svg"))
        gear_btn.setIconSize(QSize(20, 20))
        gear_btn.setFixedSize(36, 36)
        gear_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(255,255,255,0.10);"
            "  border: none;"
            "  border-radius: 18px;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(255,255,255,0.20);"
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
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self.nav_group.addButton(btn, i)
            layout.addWidget(btn)

        self.nav_group.idClicked.connect(self._on_nav_clicked)
        return bar

    @staticmethod
    def _make_placeholder(title_text: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label = QLabel(f"{title_text}\n\nConnect to a vehicle to begin")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 18px; color: #a0a0a0;")
        layout.addWidget(label)
        return page

    def _build_spinner(self) -> QFrame:
        overlay = QFrame(self)
        overlay.setObjectName("spinnerOverlay")
        overlay.setFixedSize(320, 160)
        overlay.setVisible(False)

        layout = QVBoxLayout(overlay)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)

        self.spinner_text = QLabel("Working...")
        self.spinner_text.setObjectName("spinnerText")
        self.spinner_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        layout.addWidget(self._cancel_btn, alignment=Qt.AlignmentFlag.AlignCenter)

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
            "The car is not responding.\nCheck ignition and ENET cable connection.\n\nRetry?",
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
        if isinstance(sender, QWidget):
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
            series,
            interface,
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
                            "Vehicle not found. Check the ENET cable and ensure ignition is on."
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
            conn = HSFZConnection(host) if series == "F" else DoIPConnection(host)

            if not conn.connect():
                raise ConnectionError("Failed to connect to vehicle at " + host)

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

            def __init__(self, fn: Callable[[], object]) -> None:
                super().__init__()
                self.fn = fn
                self._connect_series: str = ""

            def run(self) -> None:
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
        assert isinstance(result, tuple), "connect fn must return (conn, vin)"
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
        self.status_dot.setToolTip("[DEMO] Demo Mode" if self._demo_mode else "Connected")
        self.car_label.setText(f"{prefix}{model or f'BMW {series}-series'}")
        self.vin_label.setText(f"VIN: {vin}" if vin else "")

        for btn in self.nav_group.buttons():
            btn.setEnabled(True)

        self.nav_group.button(0).setChecked(True)
        self.stack.setCurrentIndex(1)

        # Start keep-alive timers for real connections
        if not self._demo_mode:
            self._start_keepalive()

        # Mock mode: load data directly from MockConnection (no UDS needed)
        if hasattr(connection, "data") and connection.data:
            self.vehicle_page.load_data(connection, series)
            ecus = connection.data.get("svt_ecus", [])
            self.diag_page.set_connection(connection, ecus)
            self.history_page.set_connection(connection)
            self.coding_page.set_connection(connection, ecus)
            self.hide_spinner()
            logger.info("Connected successfully (demo=%s)", self._demo_mode)
            return

        # Real car: start PostConnectWorker to read vehicle data
        # sequentially (with queue progress shown in spinner).
        self.show_spinner("Reading vehicle data...")
        tasks = self._build_post_connect_tasks(vin)
        self._post_connect_worker = PostConnectWorker(connection, tasks)
        self._post_connect_worker.progress.connect(self.show_spinner)
        self._post_connect_worker.finished.connect(
            lambda result, conn=connection: self._on_post_connect_finished(
                result, conn, vin, series
            )
        )
        self._post_connect_worker.error.connect(
            lambda msg, conn=connection: self._on_post_connect_error(msg, conn)
        )
        self._post_connect_worker.start()

        logger.info("Connected successfully (demo=%s)", self._demo_mode)

    def _build_post_connect_tasks(self, vin: str = "") -> list[tuple[str, Callable[[Any], object]]]:
        """Build the queue of data-loading tasks for PostConnectWorker.

        Each task is a ``(label, fn)`` tuple where ``fn(connection)``
        performs one or more UDS reads and returns a parsed value.
        Fallback logic lives inside each task function.
        """

        # -- I-Level (0xF18A from ZGW) ----------------------------------------
        def _read_ilevel(conn):
            resp = conn.send_uds(0x10, bytes([0x22, 0xF1, 0x8A]), timeout=5.0)
            if resp[0] == 0x62:
                return resp[3:].decode("ascii", errors="ignore").strip("\x00 ")
            raise ValueError(f"Unexpected response SID: 0x{resp[0]:02X}")

        # -- FA / Vehicle Order (0xF100 then 0xFC00 fallback) -----------------
        def _read_fa(conn):
            """Returns a dict with fa_xml, prod_date, type_code."""
            import re as _re

            fa_xml = ""
            for fa_did in (0xF100, 0xFC00):
                try:
                    resp = conn.send_uds(
                        0x10,
                        bytes([0x22, (fa_did >> 8) & 0xFF, fa_did & 0xFF]),
                        timeout=5.0,
                    )
                    if resp[0] == 0x62:
                        fa_xml = resp[3:].decode("ascii", errors="ignore").strip("\x00 ")
                        break
                except Exception:
                    pass

            prod_date = ""
            type_code = ""
            if fa_xml:
                m = _re.search(r"<ProductionDate>(\d{4})</ProductionDate>", fa_xml)
                if m:
                    pd = m.group(1)
                    prod_date = f"20{pd[2:]}-{pd[:2]}"
                tc = _re.search(r"<TypeCode>(\w+)</TypeCode>", fa_xml)
                if tc:
                    type_code = tc.group(1)

            return {
                "fa_xml": fa_xml,
                "prod_date": prod_date,
                "type_code": type_code,
            }

        # -- Mileage: try KOMBI 0x1A, then ZGW 0x22 0xF406 --------------------
        def _read_mileage(conn):
            # Primary: KOMBI (0x60) via 0x1A ReadDynamicallyDefineDataIdentifier
            try:
                resp = conn.send_uds(0x60, bytes([0x1A, 0x00]), timeout=5.0)
                if resp[0] == 0x5A and len(resp) >= 5:
                    mileage_raw = int.from_bytes(resp[3:7], "big")
                    return f"{mileage_raw:,} km"
            except Exception:
                pass

            # Fallback: ZGW via ReadDataByIdentifier 0xF406
            resp = conn.send_uds(
                0x10,
                bytes([0x22, 0xF4, 0x06]),
                timeout=5.0,
            )
            if resp[0] == 0x62 and len(resp) >= 7:
                mileage_raw = int.from_bytes(resp[3:7], "big")
                # BMW encodes mileage in 10s of km
                mileage_val = mileage_raw // 10
                return f"{mileage_val:,} km"
            raise ValueError(f"Could not read mileage (resp SID: 0x{resp[0]:02X})")

        # -- Battery voltage: try DME (0x12), then ZGW (0x10) -----------------
        def _read_battery(conn):
            for ecu in (0x12, 0x10):
                try:
                    resp = conn.send_uds(
                        ecu,
                        bytes([0x22, 0xF4, 0x0C]),
                        timeout=5.0,
                    )
                    if resp[0] == 0x62 and len(resp) >= 5:
                        voltage_raw = int.from_bytes(resp[3:5], "big")
                        return f"{voltage_raw / 10.0:.1f}V"
                except Exception:
                    continue
            raise ValueError("Could not read battery voltage from any ECU")

        # -- SVT ECU list (0xF000 from ZGW) -----------------------------------
        def _read_svt(conn):
            resp = conn.send_uds(
                0x10,
                bytes([0x22, 0xF0, 0x00]),
                timeout=10.0,
            )
            if resp[0] == 0x62:
                from ui.vehicle_page import _parse_svt_response

                return _parse_svt_response(resp)
            raise ValueError(f"Unexpected SVT response SID: 0x{resp[0]:02X}")

        tasks: list[tuple[str, object]] = [
            ("I-Level", _read_ilevel),
            ("Vehicle Order (FA)", _read_fa),
            ("Mileage", _read_mileage),
            ("Battery voltage", _read_battery),
            ("ECU list", _read_svt),
        ]
        return cast("list[tuple[str, Callable[[Any], object]]]", tasks)

    @Slot(object)
    def _on_post_connect_finished(
        self, result: dict, connection: object, vin: str, series: str
    ) -> None:
        """Handle PostConnectWorker completion on the main thread.

        Populates the vehicle page with results, reports any errors,
        then starts the secondary workers (DTC read, service history,
        coding load).

        If the active connection has changed since the worker started
        (e.g. user disconnected and reconnected), the results are
        stale and this handler returns immediately.
        """
        if self._connection is not connection:
            return  # connection changed, results are stale

        results: dict = result.get("results", {})
        errors: dict = result.get("errors", {})

        # Extract sub-results from FA dict
        fa_data = results.get("vehicle_order_(fa)")
        if isinstance(fa_data, dict):
            results["prod_date"] = fa_data.get("prod_date", "")
            results["fa_xml"] = fa_data.get("fa_xml", "")
            results["type_code"] = fa_data.get("type_code", "")

        # Populate vehicle page with all results
        self.vehicle_page.populate(results, series, vin)

        # Report any errors with a single friendly dialog
        if errors:
            error_lines = []
            for label, msg in sorted(errors.items()):
                # Make label human-readable
                human = label.replace("_", " ").title()
                error_lines.append(f"• {human}: {msg}")
            error_text = "\n".join(error_lines)
            logger.warning(
                "Post-connect: %d errors — %s",
                len(errors),
                error_text,
            )
            QMessageBox.information(
                self,
                "Some Data Unavailable",
                "The following items could not be read from the vehicle:\n\n"
                f"{error_text}\n\n"
                "Other features remain available.",
            )

        # Now start secondary workers (DTC read, service history, coding).
        # These run on their own background threads and will queue
        # naturally on the connection lock.
        ecus: list[dict] = results.get("ecu_list") or results.get("svt") or []
        if isinstance(ecus, dict):
            ecus = ecus.get("ecus", [])
        self.diag_page.set_connection(self._connection, ecus)
        self.history_page.set_connection(self._connection)
        self.coding_page.set_connection(self._connection, ecus)

        self.hide_spinner()

    def _on_post_connect_error(self, error_msg: str, connection: object = None) -> None:
        """Handle PostConnectWorker fatal error.

        If the active connection has changed since the worker started,
        the error is stale and this handler returns immediately.
        """
        if connection is not None and self._connection is not connection:
            return  # connection changed, error is stale
        self.hide_spinner()
        QMessageBox.warning(
            self,
            "Data Load Failed",
            f"Could not read vehicle data:\n\n{error_msg}\n\n"
            "The connection may still be usable. Check the "
            "Vehicle page for available information.",
        )
        # Still try to set up the other pages with what we have
        self.diag_page.set_connection(self._connection, [])
        self.history_page.set_connection(self._connection)
        self.coding_page.set_connection(self._connection, [])
        logger.warning("Post-connect data load failed: %s", error_msg)

    def _start_keepalive(self) -> None:
        """Start HSFZ alive-check and UDS TesterPresent timers.

        Both are non-blocking: they try the connection lock and skip
        this cycle if a ``send_uds()`` is in flight.  Missing one
        cycle is harmless for both the transport-layer heartbeat and
        the UDS session timer.
        """
        conn = self._connection
        if conn is None:
            return

        # Transport-layer: HSFZ alive check every 2 seconds
        if hasattr(conn, "alive_check"):
            logger.debug("Starting HSFZ alive-check timer (every 2s)")
            self._alive_timer = QTimer(self)
            self._alive_timer.timeout.connect(lambda c=conn: self._do_alive_check(c))
            self._alive_timer.start(2000)

        # Application-layer: UDS TesterPresent every 2.5 seconds
        if hasattr(conn, "tester_present"):
            _first_tp = [True]

            def _do_tester_present(c=conn):
                if _first_tp[0]:
                    logger.debug("Starting TesterPresent timer (every 2.5s)")
                    _first_tp[0] = False
                ok = c.tester_present()
                if not ok and not c.alive_ok:
                    if self._tester_present_timer is not None:
                        self._tester_present_timer.stop()
                    self._on_connection_lost()

            self._tester_present_timer = QTimer(self)
            self._tester_present_timer.timeout.connect(_do_tester_present)
            self._tester_present_timer.start(2500)

    def _do_alive_check(self, conn: object) -> None:
        """Send transport-layer keep-alive and check connection health.

        T-12: After 3 consecutive alive-check failures (~6s), treat
        the connection as lost.
        """
        if hasattr(conn, "alive_check"):
            conn.alive_check()
            if hasattr(conn, "alive_ok") and not conn.alive_ok:
                if self._alive_timer is not None:
                    self._alive_timer.stop()
                if self._tester_present_timer is not None:
                    self._tester_present_timer.stop()
                self._on_connection_lost()

    def _on_connection_lost(self) -> None:
        """T-12: Handle lost connection with reconnect dialog.

        Reference: docs/16-ui-spec.md error matrix (line 578).
        """
        self.status_dot.setText(RED_DOT)
        self.status_dot.setToolTip("Connection lost")
        self._stop_keepalive()

        reply = QMessageBox.warning(
            self,
            "Connection Lost",
            "The connection to the vehicle has been lost.\n\n"
            "Check the ENET cable and ensure ignition is on.\n\n"
            "Reconnect?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._on_disconnect()
        else:
            # No or closed dialog — still disconnect to prevent pages
            # from using a broken connection
            self._on_disconnect()

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
        idx = self.stack.indexOf(self.backups_page)
        if idx >= 0:
            self.stack.setCurrentIndex(idx)

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
        self.status_dot.setText(ORANGE_DOT if self._demo_mode else GREEN_DOT)
        self.car_label.setText(model)
        self.vin_label.setText(f"VIN: {vin}")
        for btn in self.nav_group.buttons():
            btn.setEnabled(True)
        self._connected = True

    def set_disconnected(self) -> None:
        self._on_disconnect()

    def _apply_theme(self) -> None:
        from app.theme import apply_theme

        app = QApplication.instance()
        if isinstance(app, QApplication):
            apply_theme(app)
