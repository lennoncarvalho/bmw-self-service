"""Main window shell for BMW Self Service.

Single QMainWindow + QStackedWidget architecture.
Reference: docs/16-ui-spec.md, docs/17-ui-decisions.md
"""

import logging
from collections.abc import Callable
from threading import Event
from typing import Any

from PySide6.QtCore import QSize, Qt, QThread, QTimer, Slot
from PySide6.QtGui import QAction, QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
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

from app.cbs import CbsJournalStore, CbsReadWorker, CbsResetWorker, demo_cbs, plan_reset
from app.connection import DoIPConnection, HSFZConnection
from app.mock_connection import MockConnection
from app.resources import resource_path
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
        self._overview_refresh = False
        self._overview_identity = ("", "")
        self._keepalive_worker: ProtocolWorker | None = None
        self._retired_workers: list[QThread] = []
        self._closing = False
        self._mutation_active = False
        self._overview_ecus: list[dict] = []
        self._cbs_worker: CbsReadWorker | CbsResetWorker | None = None
        self._cbs_journal = CbsJournalStore()
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
        self.vehicle_page.refresh_requested.connect(self._refresh_overview)
        self.vehicle_page.cbs_panel.read_requested.connect(self._start_cbs_read)
        self.vehicle_page.cbs_panel.reset_requested.connect(self._start_cbs_reset)
        self.stack.addWidget(self.vehicle_page)

        self.diag_page = DiagnosticsPage()
        self.vehicle_page.mil_changed.connect(self.diag_page.set_mil_observation)
        self.diag_page.mutation_active.connect(self._set_mutation_active)
        self.diag_page.can_mutate = self._can_start_mutation
        self.stack.addWidget(self.diag_page)

        self.coding_page = CodingPage()
        self.coding_page.can_capture = self._can_start_mutation
        self.stack.addWidget(self.coding_page)

        self.history_page = ServiceHistoryPage()
        self.history_page.can_mutate = self._can_start_mutation
        self.history_page.mutation_active.connect(self._set_mutation_active)
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
            btn.setEnabled(label in ("Vehicle", "History"))
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
        self._cancel_btn.setVisible(not self._mutation_active)

    def _show_retry_dialog(self) -> None:
        """G-13: Show retry dialog after 30s timeout."""
        if self._mutation_active:
            return
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
        if self._mutation_active:
            return
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
        """Show the selected page, returning Vehicle to Welcome when disconnected."""
        logger.info(
            "Navigation page=%s conn=%s read_only=%s",
            self.NAV_ITEMS[index][0],
            getattr(self._connection, "trace_id", "demo/disconnected"),
            self._read_only,
        )
        if not self._mutation_active:
            if index == 0 and not self._connected:
                self.stack.setCurrentWidget(self.welcome_page)
            else:
                self.stack.setCurrentIndex(index + 1)
            page = self.stack.currentWidget()
            if page in (self.diag_page, self.coding_page):
                page.activate()

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
            "Connecting: chassis_hint=%s interface=%s; transport from discovery", series, interface
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

                # Keep the retained gateway VIN path; the recovered source also
                # identifies through the body controller. Only final rejections
                # allow the alternate endpoint on the same healthy stream.
                vin = ""
                endpoints = (
                    (conn.entity, 0x40) if isinstance(conn, HSFZConnection) else (conn.entity,)
                )
                for endpoint in dict.fromkeys(endpoints):
                    outcome = conn.request(
                        endpoint,
                        b"\x22\xf1\x90",
                        context=OperationContext(
                            conn.trace_id, setup.deadline, cancelled=cancelled
                        ),
                    )
                    if outcome.failure is None and outcome.payload:
                        vin = outcome.payload[3:].decode("ascii")
                        if len(vin) == 17 and vin.isalnum() and vin != "0" * 17:
                            break
                        vin = ""
                    elif outcome.failure is not None:
                        from app.protocol.contracts import FailureKind

                        if outcome.failure != FailureKind.NEGATIVE:
                            break
                if not conn.alive_ok:
                    raise ConnectionError("Connection closed while identifying the vehicle")
                if not vin:
                    logger.warning(
                        "Gateway connected but VIN unverified; limited troubleshooting only"
                    )
                elif info.get("vin") and vin != info["vin"]:
                    raise ConnectionError("Discovery and diagnostic vehicle identities differ")
                conn.verified_vin = vin
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
        self._overview_identity = (vin, series)
        self._overview_refresh = False
        self.vehicle_page.reset()
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
            self.vehicle_page.set_loading(False)
            ecus = connection.data.get("svt_ecus", [])
            self.diag_page.set_connection(connection, ecus)
            self.history_page.set_connection(connection, ecus)
            self.coding_page.set_connection(connection, ecus)
            self.hide_spinner()
            logger.info("Connected successfully (demo=%s)", self._demo_mode)
            return

        if not vin:
            self.vehicle_page.populate({}, series, "Unverified")
            self.hide_spinner()
            for btn in self.nav_group.buttons():
                btn.setEnabled(self.nav_group.id(btn) == 3)
            self.stack.setCurrentWidget(self.vehicle_page)
            QMessageBox.information(
                self,
                "Limited connection",
                "The gateway responds, but the vehicle VIN could not be verified. Vehicle operations are unavailable. Check ignition, cable and the session log, then reconnect.",
            )
            return

        # Real car: start PostConnectWorker to read vehicle data
        # sequentially (with queue progress shown in spinner).
        self.show_spinner("Reading vehicle data...")
        self.vehicle_page.set_loading(True)
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

    @Slot()
    def _refresh_overview(self) -> None:
        """Refresh one settled overview without restarting other page operations."""
        if (
            self._connection is None
            or self._closing
            or self._mutation_active
            or self._post_connect_worker is not None
            or not getattr(self._connection, "alive_ok", True)
        ):
            return
        if self._demo_mode:
            self.vehicle_page.load_data(self._connection)
            return
        vin, series = self._overview_identity
        self._overview_refresh = True
        self.vehicle_page.set_loading(True)
        self._post_connect_context = (self._connection, vin, series)
        worker = PostConnectWorker(self._connection, self._build_post_connect_tasks(vin))
        self._post_connect_worker = worker
        worker.result_ready.connect(self._on_post_connect_result)
        worker.error.connect(self._on_post_connect_worker_error)
        worker.start()

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

        from app.vehicle import post_connect_tasks

        return post_connect_tasks()

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
        if self._closing or not getattr(connection, "alive_ok", True):
            self.vehicle_page.invalidate("Connection lost — reconnect before refreshing")
            self.vehicle_page.invalidate_order()
            self.vehicle_page.set_loading(False)
            self.vehicle_page.refresh_button.setEnabled(False)
            self._overview_refresh = False
            return

        results: dict = result.get("results", {})
        errors: dict = result.get("errors", {})
        if "mil" in errors:
            results["mil"] = {
                "on": None,
                "detail": "MIL could not be read — check ignition, connection and session log",
            }
        overview_ecus = results.get("ecu_list")
        self._overview_ecus = overview_ecus if isinstance(overview_ecus, list) else []
        config = getattr(connection, "config", None)
        kind = getattr(connection, "kind", "Unknown transport")
        results["connection_info"] = (
            f"Transport: {getattr(kind, 'value', kind)} · Gateway: "
            f"{getattr(config, 'host', 'Unavailable')} · Local interface: "
            f"{getattr(config, 'local_ipv4', None) or 'Unavailable'}"
        )

        # Populate vehicle page with all results
        self.vehicle_page.populate(results, series, vin)
        self.vehicle_page.set_loading(False)
        if self._overview_refresh:
            self._overview_refresh = False
            refreshed_ecus: list[dict] = results.get("ecu_list") or results.get("svt") or []
            if isinstance(refreshed_ecus, dict):
                refreshed_ecus = refreshed_ecus.get("ecus", [])
            self.diag_page.set_connection(connection, refreshed_ecus)
            self.history_page.set_targets(refreshed_ecus)
            return

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

        if (
            self._connection is not connection
            or self._closing
            or not getattr(connection, "alive_ok", True)
        ):
            return  # A modal message can deliver disconnect/reconnect events.

        # Now start secondary workers (DTC read, service history, coding).
        # These run on their own background threads and will queue
        # naturally on the connection lock.
        ecus: list[dict] = results.get("ecu_list") or results.get("svt") or []
        if isinstance(ecus, dict):
            ecus = ecus.get("ecus", [])
        self.diag_page.set_connection(self._connection, ecus)
        self.history_page.set_connection(self._connection, ecus)
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
        self.vehicle_page.invalidate("Overview read failed — refresh or reconnect")
        self.vehicle_page.invalidate_order()
        self.vehicle_page.set_loading(False)
        if self._closing or not getattr(connection, "alive_ok", True):
            self.vehicle_page.refresh_button.setEnabled(False)
        if self._overview_refresh:
            self._overview_refresh = False
            return
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
        self.vehicle_page.invalidate("Connection lost")
        self.vehicle_page.refresh_button.setEnabled(False)
        if self._mutation_active:
            logger.warning("Connection lost during mutation; waiting for explicit outcomes")
            return
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
        worker.setProperty("retired_by_main", True)
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
        if self._mutation_active:
            event.ignore()
            return
        if not self._closing:
            self._closing = True
            self.history_page.shutdown()
            self._on_disconnect()
            for page in (self.diag_page, self.coding_page):
                worker = getattr(page, "_worker", None)
                if isinstance(worker, QThread):
                    self._retire_worker(worker)
        from app.protocol.facade import protocol_workers

        for worker in protocol_workers():
            self._retire_worker(worker)
        self._reap_workers()
        if self._retired_workers or self.history_page.is_busy():
            event.ignore()
            QTimer.singleShot(100, self.close)
        else:
            super().closeEvent(event)

    # ---- Disconnect ----

    def _on_disconnect(self) -> None:
        if self._mutation_active:
            return
        self.vehicle_page.reset()
        self._overview_ecus = []
        if self._cbs_worker is not None:
            self._retire_worker(self._cbs_worker)
            self._cbs_worker = None
        self._overview_identity = ("", "")
        self._overview_refresh = False
        logger.info("Disconnecting from vehicle...")
        self._stop_keepalive()
        for worker in (self._worker, self._post_connect_worker):
            if worker is not None:
                self._retire_worker(worker)
        self.history_page.set_connection(None)
        for page in (self.diag_page, self.coding_page):
            for name in ("_worker", "_coding_reader", "_coding_writer", "_learn_worker"):
                worker = getattr(page, name, None)
                if isinstance(worker, QThread):
                    self._retire_worker(worker)
                    setattr(page, name, None)
            page._connection = None
        self.coding_page.learn_panel.set_context("", [], live=False)
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
            btn.setEnabled(self.nav_group.id(btn) in (0, 3))

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

    def _can_start_mutation(self) -> bool:
        """Only commit after background page reads have settled."""
        worker = self._post_connect_worker
        return (
            not self._mutation_active
            and self._cbs_worker is None
            and not self.history_page.is_busy()
            and (self.diag_page._worker is None or not self.diag_page._worker.isRunning())
            and not self.coding_page.is_reading()
            and (worker is None or not worker.isRunning())
        )

    @Slot()
    def _start_cbs_read(self) -> None:
        """Read CBS from identified owners; DEMO decodes its simulated snapshot."""
        connection = self._connection
        panel = self.vehicle_page.cbs_panel
        if connection is None or self._cbs_worker is not None or self._mutation_active:
            return
        if self._demo_mode:
            data = getattr(connection, "data", {}) or {}
            panel.show_result(
                demo_cbs(data),
                resets_allowed=False,
                note="DEMO — simulated records; reset is not available",
            )
            return
        if not getattr(connection, "alive_ok", False):
            panel.clear("Connection lost — reconnect before reading service status")
            return
        worker = CbsReadWorker(connection, self._overview_ecus)
        self._cbs_worker = worker
        panel.set_busy(True, "read")
        worker.result_ready.connect(self._on_cbs_read)
        worker.error.connect(self._on_cbs_error)
        worker.finished.connect(self._on_cbs_finished)
        worker.start()

    @Slot(object)
    def _on_cbs_read(self, result: dict) -> None:
        worker = self.sender()
        if worker is not self._cbs_worker or self._connection is not worker.connection:
            return
        read_only = self._read_only or getattr(self._connection, "read_only", False)
        self.vehicle_page.cbs_panel.show_result(
            result,
            resets_allowed=not read_only,
            note="Read-only session — resets disabled" if read_only else "",
        )

    @Slot(str)
    def _on_cbs_error(self, message: str) -> None:
        if self.sender() is self._cbs_worker:
            self.vehicle_page.cbs_panel.clear(message)

    @Slot()
    def _on_cbs_finished(self) -> None:
        worker = self.sender()
        if worker is not self._cbs_worker:
            return
        self._cbs_worker = None
        assert isinstance(worker, QThread)
        self._retire_worker(worker)
        reset = isinstance(worker, CbsResetWorker)
        if reset:
            self._set_mutation_active(False)
        self.vehicle_page.cbs_panel.set_busy(self._mutation_active)
        if isinstance(worker, CbsResetWorker) and self._connection is worker.connection:
            # Always replace the rows the reset was planned from; a closed
            # connection clears them instead of leaving stale reset actions.
            if getattr(worker.connection, "alive_ok", False):
                QTimer.singleShot(0, self._start_cbs_read)
            else:
                self.vehicle_page.cbs_panel.clear(
                    "Connection closed — reconnect and read service status"
                )

    @Slot(object)
    def _start_cbs_reset(self, item: dict) -> None:
        """Confirm one source-supported reset, freeze its plan and run it under lockout."""
        connection = self._connection
        if (
            connection is None
            or self._demo_mode
            or self._read_only
            or getattr(connection, "read_only", False)
            or not getattr(connection, "alive_ok", False)
            or not self._can_start_mutation()
        ):
            QMessageBox.information(
                self, "Reset Unavailable", "Wait for the current vehicle operation, then retry."
            )
            return
        try:
            plan = plan_reset(getattr(connection, "verified_vin", ""), item)
        except PermissionError as exc:
            QMessageBox.information(self, "Reset Unavailable", str(exc))
            return
        owner = item["owner"]
        dialog = QDialog(self)
        dialog.setWindowTitle("Reset Service Item")
        layout = QVBoxLayout(dialog)
        text = QLabel(
            f"Reset “{item['label']}” in {owner['name']} (0x{owner['address']:02X}, CBS "
            f"{owner['version']})?\n\nThe ECU sets availability to 100 % and counts one more "
            "service; it then recalculates the next due values. Other fields are sent as "
            "“unchanged”. This cannot be undone by the app. The current record is saved "
            "locally first.\n\nThis is separate from the headunit service history."
        )
        text.setWordWrap(True)
        layout.addWidget(text)
        power = QCheckBox("Battery charger connected or supply voltage is stable")
        layout.addWidget(power)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setText("Reset")
        ok.setEnabled(False)
        power.toggled.connect(ok.setEnabled)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if (
            dialog.exec() != QDialog.DialogCode.Accepted
            or connection is not self._connection
            or not self._can_start_mutation()
        ):
            return
        worker = CbsResetWorker(
            connection, plan, self._cbs_journal, power_acknowledged=power.isChecked()
        )
        self._cbs_worker = worker
        self._set_mutation_active(True)
        worker.result_ready.connect(self._on_cbs_reset)
        worker.error.connect(self._on_cbs_reset_error)
        worker.finished.connect(self._on_cbs_finished)
        worker.start()

    @Slot(object)
    def _on_cbs_reset(self, report: dict) -> None:
        if self.sender() is not self._cbs_worker:
            return
        persistence = (
            "\n\nThe local operation record could not be saved; see the session log."
            if report["persistence_failed"]
            else f"\n\nRecord: {report['path']}"
        )
        QMessageBox.information(
            self,
            "Service Reset Outcome",
            f"Outcome: {report['state']}\n{report['detail']}\n\n{report['instructions']}"
            + persistence,
        )

    @Slot(str)
    def _on_cbs_reset_error(self, message: str) -> None:
        if self.sender() is self._cbs_worker:
            QMessageBox.warning(self, "Service Reset Not Started", message)

    @Slot(bool)
    def _set_mutation_active(self, active: bool) -> None:
        """Keep the GUI responsive while blocking disruptive app actions."""
        self._mutation_active = active
        self.history_page.setEnabled(not active)
        self.vehicle_page.refresh_button.setEnabled(self._connected and not active)
        self.vehicle_page.cbs_panel.set_busy(active or self._cbs_worker is not None)
        if active:
            self.vehicle_page.invalidate("Vehicle operation in progress — refresh afterwards")
        elif self._connected:
            QTimer.singleShot(0, self._refresh_overview)
        for btn in self.nav_group.buttons():
            btn.setEnabled((self._connected or self.nav_group.id(btn) in (0, 3)) and not active)
        self._cancel_btn.setVisible(False)
        if (
            not active
            and self._connection is not None
            and not getattr(self._connection, "alive_ok", True)
        ):
            QTimer.singleShot(0, self._on_connection_lost)
        if active:
            self._spinner_cancel_timer.stop()
            self._spinner_retry_timer.stop()

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
