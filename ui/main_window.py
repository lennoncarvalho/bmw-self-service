"""Main window shell for BMW Self Service.

Single QMainWindow + QStackedWidget architecture.
Reference: docs/16-ui-spec.md, docs/17-ui-decisions.md
"""

import logging
from collections.abc import Callable
from threading import Event
from typing import Any, cast

from PySide6.QtCore import QSize, Qt, QThread, QTimer, Slot
from PySide6.QtGui import QAction, QCloseEvent, QIcon
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
from app.resources import resource_path
from app.uds import UdsServices
from app.worker import ConnectWorker, PostConnectWorker, ProtocolWorker
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

    def __init__(self, *, read_only: bool = False) -> None:
        """Build the application shell with the selected session policy and worker ownership."""
        super().__init__()
        self._read_only = read_only
        self.setWindowTitle("BMW Self Service" + (" — READ ONLY" if read_only else ""))
        self.setMinimumSize(800, 600)
        self._demo_mode = False
        self._connection: object | None = None
        self._connected = False
        self._worker: ConnectWorker | None = None
        self._post_connect_worker: PostConnectWorker | None = None
        self._post_connect_context: tuple[object, str, str] | None = None
        self._keepalive_worker: ProtocolWorker | None = None
        self._retired_workers: list[QThread] = []
        self._closing = False
        self._worker_reap_timer = QTimer(self)
        self._worker_reap_timer.timeout.connect(self._reap_workers)
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
        gear_btn.setIcon(QIcon(str(resource_path("assets/gear.svg"))))
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
        self._cancel_btn.clicked.connect(self._on_disconnect)
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
        """Record navigation and show the selected connected-vehicle page."""
        logger.info(
            "Navigation page=%s conn=%s read_only=%s",
            self.NAV_ITEMS[index][0],
            getattr(self._connection, "trace_id", "demo/disconnected"),
            self._read_only,
        )
        self.stack.setCurrentIndex(index + 1)

    # ---- Connection flow ----

    def _on_connect_requested(self, series: str, interface: str) -> None:
        if self._closing:
            return
        self._on_disconnect()
        if self._demo_mode:
            self._connect_demo(series)
        else:
            self._connect_real(series, interface)

    def _connect_demo(self, series: str) -> None:
        self.show_spinner("Starting DEMO mode...")

        def do_connect(cancelled: Event) -> tuple[MockConnection, str]:
            """Establish the selected connection with cancellation checks between bounded operations."""
            if cancelled.is_set():
                raise ConnectionError("Connection cancelled")
            conn = MockConnection()
            conn.connect()
            return (conn, "")

        self._async_connect(do_connect, series)

    def _connect_real(self, series: str, interface: str) -> None:
        """Discover and identify the vehicle using a cancellable background connection attempt."""
        logger.info(
            "Connecting: series=%s interface=%s proto=%s",
            series,
            interface,
            {chr(70): "HSFZ", chr(71): "DoIP", chr(85): "DoIP", chr(73): "DoIP"}.get(series, "?"),
        )
        self.show_spinner(f"Searching for vehicle on {interface}...")
        read_only = self._read_only

        def do_connect(cancelled: Event) -> tuple[HSFZConnection | DoIPConnection, str]:
            """Discover, activate and identify within one setup deadline."""
            from app.protocol.contracts import OperationContext
            from app.protocol.discovery import discover_vehicle

            setup = OperationContext.create("discovery", 30.0)
            setup.cancelled = cancelled
            info = discover_vehicle(interface, setup)
            if info is None:
                raise ConnectionError(
                    "Vehicle not found. Check the cable, ignition and Ethernet IPv4 settings."
                )
            connection_type = HSFZConnection if info["transport"] == "hsfz" else DoIPConnection
            conn = connection_type(
                info["ip"],
                read_only=read_only,
                local_ip=info["local_ip"],
                entity=int(info.get("logical_addr", "16")),
            )
            context = OperationContext(conn.trace_id, setup.deadline, cancelled=cancelled)
            try:
                conn.connect(context)
                if isinstance(conn, DoIPConnection):
                    conn.activate_routing(
                        OperationContext(conn.trace_id, setup.deadline, cancelled=cancelled)
                    )

                def identify(services: UdsServices, active: OperationContext) -> bytes:
                    services.change_session(3, active)
                    return services.read_data_by_identifier(0xF190, active)

                resp = conn.run_operation(
                    conn.entity,
                    identify,
                    context=OperationContext(conn.trace_id, setup.deadline, cancelled=cancelled),
                )
                vin = resp[3:].decode("ascii")
                if vin != info["vin"]:
                    raise ConnectionError("Discovery and diagnostic vehicle identities differ")
                return conn, vin
            except Exception:
                conn.disconnect()
                raise

        self._async_connect(do_connect, series)

    def _async_connect(self, connect_fn: Callable[[Event], object], series: str) -> None:
        worker = ConnectWorker(connect_fn, series)
        self._worker = worker
        worker.result_ready.connect(self._on_worker_result)
        worker.error.connect(self._on_connect_error)
        worker.progress.connect(self._on_connection_progress)
        worker.start()

    @Slot(str)
    def _on_connection_progress(self, message: str) -> None:
        if not self._closing and self.sender() in (self._worker, self._post_connect_worker):
            self.show_spinner(message)

    @Slot(object)
    def _on_worker_result(self, result: object) -> None:
        """Reject late/cancelled results before changing the active connection."""
        worker = self.sender()
        assert isinstance(result, tuple), "connect fn must return (conn, vin)"
        conn, vin = result
        if (
            not isinstance(worker, ConnectWorker)
            or worker is not self._worker
            or worker.cancelled
            or self._closing
        ):
            conn.disconnect()
            return
        self._worker = None
        self._retire_worker(worker)
        self._on_connect_success(conn, vin, worker.series)

    def _on_connect_success(self, connection: Any, vin: str, series: str) -> None:
        """Configure page capabilities before exposing navigation and loading optional data."""
        self._connection = connection
        self._connected = True
        if not getattr(connection, "data", None):
            # Clear DEMO/default page state before navigation can expose it.
            # These live setters only display unavailable capabilities; no I/O.
            self.history_page.set_connection(connection)
            self.coding_page.set_connection(connection, [])

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

        prefix = "[DEMO] " if self._demo_mode else ("[READ ONLY] " if self._read_only else "")
        self.status_dot.setText(ORANGE_DOT if self._demo_mode else GREEN_DOT)
        self.status_dot.setToolTip("[DEMO] Demo Mode" if self._demo_mode else "Connected")
        self.car_label.setText(f"{prefix}{model or f'BMW {series}-series'}")
        self.vin_label.setText(f"VIN: {vin}" if vin else "")

        for btn in self.nav_group.buttons():
            btn.setEnabled(True)

        self.nav_group.button(0).setChecked(True)
        self.stack.setCurrentIndex(1)

        # Start the keepalive worker for real connections
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
        self._post_connect_context = (connection, vin, series)
        self._post_connect_worker.progress.connect(self._on_connection_progress)
        self._post_connect_worker.result_ready.connect(self._on_post_connect_result)
        self._post_connect_worker.error.connect(self._on_post_connect_worker_error)
        self._post_connect_worker.start()

        logger.info("Connected successfully (demo=%s)", self._demo_mode)

    @Slot(object)
    def _on_post_connect_result(self, result: dict) -> None:
        worker = self.sender()
        if worker is not self._post_connect_worker or self._post_connect_context is None:
            return
        connection, vin, series = self._post_connect_context
        self._post_connect_worker = None
        self._post_connect_context = None
        assert isinstance(worker, QThread)
        self._retire_worker(worker)
        self._on_post_connect_finished(result, connection, vin, series)

    @Slot(str)
    def _on_post_connect_worker_error(self, message: str) -> None:
        worker = self.sender()
        if worker is not self._post_connect_worker or self._post_connect_context is None:
            return
        connection, _vin, _series = self._post_connect_context
        self._post_connect_worker = None
        self._post_connect_context = None
        assert isinstance(worker, QThread)
        self._retire_worker(worker)
        self._on_post_connect_error(message, connection)

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
                try:
                    value = resp[3:].decode("ascii").strip("\x00 ")
                except UnicodeDecodeError as exc:
                    raise ValueError("Vehicle software level has no verified text decoder") from exc
                if not value or not value.isprintable():
                    raise ValueError("Vehicle software level has no verified text decoder")
                return value
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

            if not fa_xml:
                raise ValueError("Vehicle order is unavailable: no supported response")
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

        if self._connection is not connection or self._closing:
            return  # A modal message can deliver disconnect/reconnect events.

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
        if self._connection is not connection or self._closing:
            return
        # Still try to set up the other pages with what we have
        self.diag_page.set_connection(self._connection, [])
        self.history_page.set_connection(self._connection)
        self.coding_page.set_connection(self._connection, [])
        logger.warning("Post-connect data load failed: %s", error_msg)

    def _start_keepalive(self) -> None:
        """Monitor the single owner; it services all keepalive traffic itself."""
        conn = self._connection
        if isinstance(conn, (HSFZConnection, DoIPConnection)):
            self._keepalive_worker = conn.worker
            conn.worker.error.connect(self._on_keepalive_error)
            conn.worker.finished.connect(self._on_protocol_finished)

    @Slot()
    def _on_protocol_finished(self) -> None:
        """Reflect a tainted/closed stream even when its command failed cleanly."""
        if self.sender() is self._keepalive_worker and not self._closing:
            self._on_connection_lost()

    @Slot(str)
    def _on_keepalive_error(self, message: str) -> None:
        if self.sender() is self._keepalive_worker and not self._closing:
            logger.warning("Protocol owner stopped: %s", message)
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
        """Request worker shutdown and retain it until its thread actually exits."""
        worker = self._keepalive_worker
        self._keepalive_worker = None
        if worker is not None:
            self._retire_worker(worker)

    def _retire_worker(self, worker: QThread) -> None:
        if isinstance(worker, (ProtocolWorker, ConnectWorker)):
            worker.stop()
        else:
            worker.requestInterruption()
        if worker not in self._retired_workers:
            self._retired_workers.append(worker)
        self._worker_reap_timer.start(100)

    def _reap_workers(self) -> None:
        for worker in self._retired_workers[:]:
            if not worker.isRunning():
                self._retired_workers.remove(worker)
                worker.deleteLater()
        if not self._retired_workers:
            self._worker_reap_timer.stop()

    @Slot(str)
    def _on_connect_error(self, error_msg: str) -> None:
        """Report an active connection failure while preserving read-only network guidance."""
        worker = self.sender()
        if worker is not self._worker or self._closing:
            return
        self._worker = None
        if isinstance(worker, QThread):
            self._retire_worker(worker)
        self.hide_spinner()
        self.status_dot.setText(RED_DOT)
        self.status_dot.setToolTip("Disconnected")

        # G-14: Map error messages to user-friendly dialogs
        friendly = error_msg
        if self._read_only and "vehicle not found" in error_msg.lower():
            friendly = (
                "Vehicle not found. Check the ENET cable, ignition and Ethernet IPv4 settings.\n\n"
                "Automatic DHCP and network changes are disabled in this read-only session."
            )
        elif "admin" in error_msg.lower() or "root" in error_msg.lower():
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
        self._on_disconnect()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Keep worker objects alive while cooperative shutdown completes."""
        if not self._closing:
            self._closing = True
            self._on_disconnect()
            for page in (self.diag_page, self.history_page, self.coding_page):
                worker = getattr(page, "_worker", None)
                if isinstance(worker, QThread):
                    self._retire_worker(worker)
        from app.protocol.facade import protocol_workers

        for worker in protocol_workers():
            self._retire_worker(worker)
        self._reap_workers()
        if self._retired_workers:
            event.ignore()
            QTimer.singleShot(100, self.close)
        else:
            super().closeEvent(event)

    # ---- Disconnect ----

    def _on_disconnect(self) -> None:
        logger.info("Disconnecting from vehicle...")
        self._stop_keepalive()
        for worker in (self._worker, self._post_connect_worker):
            if worker is not None:
                self._retire_worker(worker)
        for page in (self.diag_page, self.history_page, self.coding_page):
            for name in ("_worker", "_coding_reader", "_coding_writer"):
                worker = getattr(page, name, None)
                if isinstance(worker, QThread):
                    self._retire_worker(worker)
                    setattr(page, name, None)
            page._connection = None
        self._worker = None
        self._post_connect_worker = None
        self._post_connect_context = None
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
