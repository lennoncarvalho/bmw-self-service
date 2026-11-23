"""Main window shell for BMW Self Service.

Single QMainWindow + QStackedWidget architecture.
Reference: plan.md#connection-and-display, AGENTS.md#implementation-rules
"""

import logging
from collections.abc import Callable
from pathlib import Path
from threading import Event
from typing import Any

from PySide6.QtCore import QSize, Qt, QThread, QTimer, QUrl, Slot
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.cbs import CbsJournalStore, CbsReadWorker, CbsResetWorker, plan_reset
from app.connection import DoIPConnection, HSFZConnection
from app.demo_vehicle import CAPTURED_DEMO_PROFILE, DemoVehicle
from app.diagnostics import coverage_complete
from app.ista_jobs import refresh_bundled_data
from app.protocol.contracts import TransportKind
from app.session import LIVE, environment
from app.vehicle import post_connect_tasks
from app.worker import ConnectWorker, PostConnectWorker, ProtocolWorker
from ui.backups_page import BackupsPage
from ui.cockpit import caption, cockpit_icon
from ui.coding_page import CodingPage
from ui.diagnostics_page import DiagnosticsPage
from ui.dialogs import CockpitDialog
from ui.dialogs import MessageBox as QMessageBox
from ui.form_inputs import CheckInput
from ui.ista_settings_dialog import IstaSettingsDialog
from ui.page_stack import PageStack
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
        ("CBS", ""),
        ("Backups", ""),
    ]

    def __init__(self, *, read_only: bool = False) -> None:
        """Build the application shell with the selected session policy and worker ownership."""
        super().__init__()
        self._read_only = read_only
        self.setWindowTitle("BMW Self Service" + (" — READ ONLY" if read_only else ""))
        self.setMinimumSize(1024, 700)
        self._demo_mode = False
        self._demo_vehicle: DemoVehicle | None = None
        self._connection: object | None = None
        self._connected = False
        self._worker: ConnectWorker | None = None
        self._connect_selection: tuple[str, str] | None = None
        self._post_connect_worker: PostConnectWorker | None = None
        self._overview_refresh = False
        self._overview_identity = ("", "")
        self._keepalive_worker: ProtocolWorker | None = None
        self._retired_workers: list[QThread] = []
        self._closing = False
        self._connection_loss_dialog = False
        self._mutation_active = False
        self._coding_loading = False
        self._diagnostics_loading = False
        self._overview_after_diagnostics = False
        self._overview_ecus: list[dict] = []
        self._cbs_worker: CbsReadWorker | CbsResetWorker | None = None
        self._cbs_reset_blocked = False
        self._cbs_journal = CbsJournalStore()
        # Job data folder is read here; CarWorkers must not create QSettings.
        refresh_bundled_data()
        self._worker_reap_timer = QTimer(self)
        self._worker_reap_timer.timeout.connect(self._reap_workers)
        self._setup_ui()
        self._apply_theme()
        self._chrome_timer = QTimer(self)
        self._chrome_timer.timeout.connect(self._sync_overview_chrome)
        self._chrome_timer.start(1000)

    def _setup_ui(self) -> None:
        """Build fixed chrome around the shared scrolling page stack."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_layout.addWidget(self._build_top_bar())

        self.stack = PageStack()

        self.welcome_page = WelcomePage()
        self.welcome_page.connect_clicked.connect(self._on_connect_requested)
        self.stack.addWidget(self.welcome_page)

        self.vehicle_page = VehiclePage()
        self.vehicle_page.refresh_requested.connect(self._refresh_overview)
        self.vehicle_page.navigation_requested.connect(self._navigate_from_overview)
        self.vehicle_page.cbs_panel.read_requested.connect(self._start_cbs_read)
        self.vehicle_page.cbs_panel.reset_requested.connect(self._start_cbs_reset)
        self.stack.addWidget(self.vehicle_page)

        self.diag_page = DiagnosticsPage()
        self.vehicle_page.mil_changed.connect(self.diag_page.set_mil_observation)
        self.diag_page.mil_observed.connect(self.vehicle_page.set_mil_observation)
        self.diag_page.mutation_active.connect(self._on_diagnostics_mutation_active)
        self.diag_page.loading_changed.connect(self._set_diagnostics_loading)
        self.diag_page.loading_progress.connect(self._on_diagnostics_loading_progress)
        self.diag_page.can_mutate = self._can_start_mutation
        self.stack.addWidget(self.diag_page)

        self.coding_page = CodingPage()
        self.coding_page.can_mutate = self._can_start_mutation
        self.coding_page.mutation_active.connect(self._set_mutation_active)
        self.coding_page.loading_changed.connect(self._set_coding_loading)
        self.coding_page.loading_progress.connect(self._on_coding_loading_progress)
        self.stack.addWidget(self.coding_page)

        self.history_page = ServiceHistoryPage()
        self.history_page.can_mutate = self._can_start_mutation
        self.history_page.mutation_active.connect(self._set_mutation_active)
        self.history_page.vehicle_loading_changed.connect(self._set_history_loading)
        self.history_page.vehicle_loading_progress.connect(self._on_history_loading_progress)
        self.stack.addWidget(self.history_page)

        self.backups_page = BackupsPage()
        self.backups_page.restore_requested.connect(self._review_coding_restore)
        self.backups_page.verification_requested.connect(self._verify_coding_backup)
        self.coding_page.verification_saved.connect(self.backups_page.refresh)
        self.stack.addWidget(self.backups_page)
        self.cbs_page = QWidget()
        cbs_layout = QVBoxLayout(self.cbs_page)
        cbs_layout.setContentsMargins(24, 24, 24, 24)
        cbs_layout.addWidget(self.vehicle_page.cbs_panel)
        self.vehicle_page.cbs_panel.show()
        cbs_layout.addStretch()
        self.stack.addWidget(self.cbs_page)

        self.content_scroll = QScrollArea()
        self.content_scroll.setObjectName("pageScrollArea")
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setWidget(self.stack)
        workspace = QHBoxLayout()
        workspace.setContentsMargins(0, 0, 0, 0)
        workspace.setSpacing(0)
        workspace.addWidget(self._build_bottom_nav())
        workspace.addWidget(self.content_scroll, stretch=1)
        main_layout.addLayout(workspace, stretch=1)

        self.spinner_overlay = self._build_spinner()

    def _build_top_bar(self) -> QFrame:
        """Build persistent branding, vehicle identity and connection controls."""
        bar = QFrame()
        bar.setObjectName("cockpitTopBar")
        bar.setFixedHeight(64)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(16)
        layout.addWidget(caption("BMW SELF SERVICE", "brand"))
        identity = QVBoxLayout()
        identity.setSpacing(2)
        self.car_label = caption("Not connected", "identity")
        self.vin_label = caption("", "technical")
        self.vin_label.setWordWrap(False)
        identity.addWidget(self.car_label)
        metadata = QHBoxLayout()
        metadata.setSpacing(12)
        metadata.addWidget(self.vin_label)
        self.observation_age = caption("")
        self.observation_age.setAccessibleName("Overview observation time")
        metadata.addWidget(self.observation_age, 1)
        identity.addLayout(metadata)
        layout.addLayout(identity, 1)
        self.status_dot = QLabel(RED_DOT)
        self.status_dot.setToolTip("Disconnected")
        layout.addWidget(self.status_dot)
        self.link_label = caption("Disconnected", "badge")
        layout.addWidget(self.link_label)
        self.power_status = caption("Voltage unavailable", "technical")
        layout.addWidget(self.power_status)
        gear_btn = QPushButton()
        gear_btn.setIcon(cockpit_icon("settings"))
        gear_btn.setIconSize(QSize(22, 22))
        gear_btn.setFixedSize(36, 36)
        gear_btn.setProperty("class", "iconButton")
        gear_btn.setToolTip("Settings and connection actions")
        gear_btn.setAccessibleName("Settings and connection actions")
        gear_btn.clicked.connect(self._show_gear_menu)
        layout.addWidget(gear_btn)
        return bar

    def _build_bottom_nav(self) -> QFrame:
        """Build the fixed QuickSelect rail with the established navigation IDs."""
        bar = QFrame()
        bar.setObjectName("cockpitRail")
        bar.setFixedWidth(80)
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(4, 10, 4, 12)
        layout.setSpacing(6)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        icons = ("overview", "faults", "coding", "history", "service", "backups")
        labels = ("Overview", "Faults", "Coding", "History", "CBS", "Backups")
        for index in (0, 1, 4, 2, 3, 5):
            nav_button = QToolButton()
            nav_button.setText(labels[index])
            nav_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            nav_button.setFixedWidth(72)
            nav_button.setObjectName("railButton")
            nav_button.setCheckable(True)
            nav_button.setIcon(cockpit_icon(icons[index]))
            nav_button.setIconSize(QSize(22, 22))
            nav_button.setFixedHeight(62)
            nav_button.setAccessibleName(labels[index])
            nav_button.setToolTip(labels[index])
            self.nav_group.addButton(nav_button, index)
            nav_button.setEnabled(index in (0, 3, 5))
            layout.addWidget(nav_button)
        self.nav_group.button(0).setChecked(True)
        layout.addStretch()
        flags = QHBoxLayout()
        flags.setContentsMargins(0, 0, 0, 0)
        flags.setSpacing(2)
        for flag, country in (("🇺🇸", "English"), ("🇧🇷", "Portuguese")):
            language = QToolButton()
            language.setText(flag)
            language.setProperty("class", "languagePlaceholder")
            language.setFixedSize(35, 36)
            language.setToolTip(country + " — language selection planned")
            language.setAccessibleName(country + " — language selection planned")
            language.setEnabled(False)
            flags.addWidget(language)
        layout.addLayout(flags)
        for name, label in (("github", "GitHub"), ("coffee", "Coffee")):
            button = QToolButton()
            button.setIcon(cockpit_icon(name))
            button.setIconSize(QSize(28, 28))
            button.setFixedSize(72, 44)
            button.setProperty("class", "railUtility")
            button.setToolTip(label if name == "github" else label + " — planned")
            button.setAccessibleName(label)
            if name == "github":
                button.clicked.connect(self._open_repository)
            else:
                button.setEnabled(False)
            layout.addWidget(button)
        self.nav_group.idClicked.connect(self._on_nav_clicked)
        return bar

    @Slot()
    def _open_repository(self) -> None:
        """Open this project's public source repository in the default browser."""
        QDesktopServices.openUrl(QUrl("https://github.com/lennoncarvalho/bmw-self-service"))

    @Slot(int)
    def _navigate_from_overview(self, index: int) -> None:
        """Route overview shortcuts through the guarded navigation entry point."""
        button = self.nav_group.button(index)
        if button is not None and button.isEnabled():
            self._on_nav_clicked(index)

    @Slot()
    def _sync_overview_chrome(self) -> None:
        """Reflect already settled UI state without scheduling vehicle work."""
        self.link_label.setText(
            "DEMO · Connected"
            if self._connected and self._demo_mode
            else "Connected"
            if self._connected
            else "Disconnected"
        )
        self.observation_age.setText(
            self.vehicle_page.observed_label.text() if self._connected else ""
        )
        self.power_status.setText(
            (self.vehicle_page.supply_voltage if self._connected else "") or "Voltage unavailable"
        )
        self.vehicle_page.scan_button.setEnabled(self._connected and not self._mutation_active)
        self.vehicle_page.health_value.setText(
            f"{self.diag_page.fault_memory_count} fault-memory entries"
            if self._connected and self.diag_page._loaded
            else "Not scanned"
        )
        coverage = self.diag_page._coverage if self._connected else []
        complete = sum(coverage_complete(row) for row in coverage)
        coverage_text = (
            f"Memory coverage: {complete}/{len(coverage)} accounted for · See Faults for inventory"
            if coverage
            else "Scan coverage · Unavailable"
        )
        if self._connected and not self.diag_page._stale_scan_notice.isHidden():
            coverage_text += " · Previous scan is stale"
        self.vehicle_page.coverage_label.setText(coverage_text)
        panel = self.vehicle_page.cbs_panel
        self.vehicle_page.service_note.setText(
            panel.message_label.text()
            or (
                "Last service read · Open CBS for service intervals and due dates"
                if self._connected and panel._has_result
                else "Service status not read in this session"
            )
        )
        self.vehicle_page.health_value.setToolTip(
            "Open Faults for scan coverage and any stale-result warnings."
        )
        self.vehicle_page.service_value.setToolTip(panel.message_label.text())
        self.vehicle_page.service_value.setText(
            f"{len(panel._items)} service items"
            if self._connected and panel._has_result
            else "Not read"
        )

    def _build_spinner(self) -> QFrame:
        self.loading_backdrop = QFrame(self)
        self.loading_backdrop.setObjectName("loadingBackdrop")
        self.loading_backdrop.hide()
        overlay = QFrame(self.loading_backdrop)
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
        progress = QProgressBar()
        progress.setObjectName("loadingProgress")
        progress.setAccessibleName("Loading")
        progress.setRange(0, 0)
        progress.setTextVisible(False)
        progress.setFixedHeight(6)
        layout.addWidget(progress)

        # G-13: Cancel button (appears after 10s)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setVisible(False)
        self._cancel_btn.setProperty("class", "secondary")
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
        self._cancel_btn.setVisible(
            not self._mutation_active and not self._diagnostics_loading and self._cbs_worker is None
        )
        self._position_spinner()

    def _show_retry_dialog(self) -> None:
        """G-13: Show retry dialog after 30s timeout."""
        if (
            self._mutation_active
            or self._coding_loading
            or self._diagnostics_loading
            or self._cbs_worker is not None
            or self._worker is None
        ):
            return
        worker = self._worker
        self.hide_spinner()
        reply = QMessageBox.question(
            self,
            "Vehicle Not Responding",
            "The car is not responding.\nCheck ignition and ENET cable connection.\n\nRetry?",
            QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Retry,
        )
        if self._worker is not worker or self._closing:
            return
        if reply == QMessageBox.StandardButton.Retry:
            self._on_retry_connect()
        else:
            self._on_disconnect()

    def _position_spinner(self) -> None:
        """Center the operation overlay within the visible content viewport."""
        if self.spinner_overlay and self.stack:
            self.loading_backdrop.setGeometry(self.rect())
            viewport = self.content_scroll.viewport()
            width = min(480, viewport.width() - 48)
            layout = self.spinner_overlay.layout()
            height = max(160, layout.heightForWidth(width) + 8 if layout is not None else 160)
            self.spinner_overlay.setFixedSize(width, height)
            center = self.loading_backdrop.mapFrom(
                self, viewport.mapTo(self, viewport.rect().center())
            )
            self.spinner_overlay.move(
                center.x() - self.spinner_overlay.width() // 2,
                center.y() - self.spinner_overlay.height() // 2,
            )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_spinner()

    def show_spinner(self, message: str = "Working...") -> None:
        self.spinner_text.setText(message)
        self._cancel_btn.setVisible(False)
        self._position_spinner()
        central = self.centralWidget()
        if central is not None:
            central.setEnabled(False)
        self.loading_backdrop.show()
        self.loading_backdrop.raise_()
        self.spinner_overlay.setVisible(True)
        # G-13: Start timers for cancel (10s) and retry (30s)
        self._spinner_cancel_timer.start(10000)
        self._spinner_retry_timer.start(30000)

    def hide_spinner(self) -> None:
        if (
            self._coding_loading
            or self._diagnostics_loading
            or self._cbs_worker is not None
            or self.history_page.is_using_vehicle()
        ):
            return
        self.loading_backdrop.hide()
        central = self.centralWidget()
        if central is not None:
            central.setEnabled(True)
        self.spinner_overlay.setVisible(False)
        self._cancel_btn.setVisible(False)
        self._spinner_cancel_timer.stop()
        self._spinner_retry_timer.stop()

    @Slot(bool)
    def _set_coding_loading(self, active: bool) -> None:
        """Keep foreground coding work exclusive behind a loading backdrop."""
        self._coding_loading = active
        if active:
            self.show_spinner("Reading coding data...")
            # Ordinary reads may disconnect cooperatively; sensitive sessions
            # acquire the mutation lock before their first control request.
            if self._mutation_active:
                self._spinner_cancel_timer.stop()
            self._spinner_retry_timer.stop()
        else:
            self.hide_spinner()
            if self._connection is not None and not getattr(self._connection, "alive_ok", True):
                QTimer.singleShot(0, self._on_connection_lost)

    @Slot(str)
    def _on_coding_loading_progress(self, message: str) -> None:
        """Display progress from the current foreground coding operation."""
        if self._coding_loading:
            self.spinner_text.setText(message)
            self._position_spinner()

    @Slot(bool)
    def _set_diagnostics_loading(self, active: bool) -> None:
        """Keep diagnostic progress inside the shared foreground loading backdrop."""
        self._diagnostics_loading = active
        if active:
            self.show_spinner("Reading fault memories...")
            self._spinner_cancel_timer.stop()
            self._spinner_retry_timer.stop()
        else:
            self.hide_spinner()
            if self._connection is not None and not getattr(self._connection, "alive_ok", True):
                QTimer.singleShot(0, self._on_connection_lost)
            if self._overview_after_diagnostics:
                self._overview_after_diagnostics = False
                QTimer.singleShot(0, self._refresh_overview)

    @Slot(str)
    def _on_diagnostics_loading_progress(self, message: str) -> None:
        """Update the modal only while its current diagnostic worker is active."""
        if self._diagnostics_loading:
            self.spinner_text.setText(message)
            self._position_spinner()

    @Slot(bool)
    def _set_history_loading(self, active: bool) -> None:
        """Show foreground history activity until its vehicle worker exits."""
        if active:
            self.show_spinner(
                "Writing service history..." if self._mutation_active else "Checking headunit..."
            )
            self._spinner_cancel_timer.stop()
            self._spinner_retry_timer.stop()
        else:
            self.hide_spinner()
            if self._connection is not None and not getattr(self._connection, "alive_ok", True):
                QTimer.singleShot(0, self._on_connection_lost)

    @Slot(str)
    def _on_history_loading_progress(self, message: str) -> None:
        """Publish progress from the foreground history worker."""
        if self.history_page.is_using_vehicle():
            self.spinner_text.setText(message)
            self._position_spinner()

    # ---- Gear menu ----

    def _show_gear_menu(self) -> None:
        if self._mutation_active:
            return
        menu = QMenu(self)

        self._demo_action = QAction("Enable DEMO Mode", self)
        self._demo_action.setCheckable(True)
        self._demo_action.setChecked(self._demo_mode)
        self._demo_action.triggered.connect(self._on_demo_toggled)
        if self._connected or not self._can_reset_demo():
            self._demo_action.setEnabled(False)
        menu.addAction(self._demo_action)
        if self._demo_mode:
            reset_demo = menu.addAction("Reset DEMO vehicle")
            reset_demo.setEnabled(self._can_reset_demo())
            reset_demo.triggered.connect(self._reset_demo)

        menu.addSeparator()

        backups_action = QAction("Backups...", self)
        backups_action.triggered.connect(self._on_backups)
        menu.addAction(backups_action)

        job_data_action = QAction("ECU Job Data...", self)
        job_data_action.triggered.connect(self._on_job_data)
        menu.addAction(job_data_action)

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
        if self._connected or not self._can_reset_demo():
            return
        if checked and self._demo_vehicle is None:
            self._demo_vehicle = self._load_demo_vehicle()
            if self._demo_vehicle is None:
                if hasattr(self, "_demo_action"):
                    self._demo_action.setChecked(False)
                return
        self._demo_mode = checked
        current = self._demo_vehicle.environment if checked and self._demo_vehicle else LIVE
        self.history_page.set_environment(current)
        self.backups_page.set_environment(current)
        self.welcome_page.set_demo_mode(checked)
        logger.info("DEMO mode %s", "enabled" if checked else "disabled")

    def _load_demo_vehicle(self) -> DemoVehicle | None:
        """Load the private capture when installed, otherwise use the bundled profile."""
        try:
            if CAPTURED_DEMO_PROFILE.exists():
                return DemoVehicle(CAPTURED_DEMO_PROFILE)
            return DemoVehicle()
        except (OSError, ValueError, KeyError, TypeError):
            logger.warning("DEMO vehicle data is unavailable", exc_info=True)
            QMessageBox.warning(
                self,
                "DEMO unavailable",
                "The DEMO vehicle profile is missing or invalid. Check the session log "
                "and regenerate the selected profile before trying again.",
            )
            return None

    def _can_reset_demo(self) -> bool:
        """Allow environment changes only after all foreground work has settled."""
        return (
            not self._closing
            and self._worker is None
            and self._post_connect_worker is None
            and not self._mutation_active
            and not self._coding_loading
            and not self._diagnostics_loading
            and self._cbs_worker is None
            and not self.history_page.is_busy()
        )

    @Slot()
    def _reset_demo(self) -> None:
        """Retire the old connection and start a fresh isolated virtual vehicle."""
        if not self._demo_mode or not self._can_reset_demo():
            return
        vehicle = self._load_demo_vehicle()
        if vehicle is None:
            return
        was_connected = self._connected
        series = self._overview_identity[1] or "F"
        self._on_disconnect()
        self._demo_vehicle = vehicle
        self.history_page.set_environment(self._demo_vehicle.environment)
        self.backups_page.set_environment(self._demo_vehicle.environment)
        if was_connected:
            self._connect_demo(series)

    # ---- Navigation ----

    def _on_nav_clicked(self, index: int) -> None:
        """Show the selected page, returning Vehicle to Welcome when disconnected."""
        logger.info(
            "Navigation page=%s conn=%s read_only=%s",
            self.NAV_ITEMS[index][0],
            getattr(self._connection, "trace_id", "demo/disconnected"),
            self._read_only,
        )
        if (
            not self._mutation_active
            and not self._coding_loading
            and not self._diagnostics_loading
            and self._cbs_worker is None
            and not self.history_page.is_using_vehicle()
        ):
            if index == 0 and not self._connected:
                self.stack.setCurrentWidget(self.welcome_page)
            else:
                pages = (
                    self.vehicle_page,
                    self.diag_page,
                    self.coding_page,
                    self.history_page,
                    self.cbs_page,
                    self.backups_page,
                )
                self.stack.setCurrentWidget(pages[index])
                if index == 5:
                    self.backups_page.set_connection(self._connection)
            self.nav_group.button(index).setChecked(True)
            self.content_scroll.verticalScrollBar().setValue(0)
            page = self.stack.currentWidget()
            if page in (self.diag_page, self.coding_page):
                page.activate()

    @Slot(object)
    def _review_coding_restore(self, path: object) -> None:
        """Show preparation progress before starting a reviewed backup restore."""
        if self._mutation_active or not isinstance(path, Path):
            return
        self.stack.setCurrentWidget(self.coding_page)
        self.nav_group.button(2).setChecked(True)
        self.content_scroll.verticalScrollBar().setValue(0)
        reason = self.coding_page.restore_vehicle_backup(path)
        if reason:
            QMessageBox.information(self, "Coding restoration unavailable", reason)
            self.coding_page.activate()

    @Slot(object)
    def _verify_coding_backup(self, path: object) -> None:
        """Start an explicit comparison from the backup page."""
        if self._closing or self._mutation_active or not isinstance(path, Path):
            return
        reason = self.coding_page.verify_vehicle_backup(path, self.backups_page.store)
        if reason:
            QMessageBox.information(self, "Coding verification unavailable", reason)

    # ---- Connection flow ----

    def _on_connect_requested(self, series: str, interface: str) -> None:
        if self._closing or self._mutation_active:
            return
        self._connect_selection = (series, interface)
        self._on_disconnect()
        if self._demo_mode:
            self._connect_demo(series)
        else:
            self._connect_real(series, interface)

    def _connect_demo(self, series: str) -> None:
        """Connect the local virtual vehicle through normal VIN and protocol handling."""
        self.show_spinner("Connecting DEMO vehicle...")
        if self._demo_vehicle is None:
            self._demo_vehicle = self._load_demo_vehicle()
            if self._demo_vehicle is None:
                self.hide_spinner()
                return
        vehicle = self._demo_vehicle
        read_only = self._read_only

        def do_connect(cancelled: Event) -> tuple[HSFZConnection, str]:
            conn = HSFZConnection(
                "127.0.0.1",
                local_ip="127.0.0.1",
                read_only=read_only,
                environment=vehicle.environment,
                stream_factory=vehicle.connect_stream,
            )
            context = conn.context(30.0, cancelled)
            try:
                conn.connect(conn.context(min(5.0, context.remaining()), cancelled))
                outcome = conn.request(0x10, b"\x22\xf1\x90", context=context)
                if outcome.failure is not None or outcome.payload is None:
                    raise ConnectionError("DEMO vehicle identity could not be verified")
                vin = outcome.payload[3:].decode("ascii")
                conn.verified_vin = vin
                return conn, vin
            except BaseException:
                conn.disconnect()
                raise

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
        self.welcome_page.set_adapter_polling(False)
        worker = ConnectWorker(connect_fn, series)
        self._worker = worker
        worker.result_ready.connect(self._on_worker_result)
        worker.error.connect(self._on_connect_error)
        worker.progress.connect(self._on_connection_progress)
        worker.start()

    @Slot(str)
    def _on_connection_progress(self, message: str) -> None:
        if not self._closing and self.sender() in (self._worker, self._post_connect_worker):
            if self._overview_refresh:
                self.spinner_text.setText(message)
                self._position_spinner()
            else:
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
        self.history_page.set_connection(connection)
        self.coding_page.set_connection(connection, [])
        self.backups_page.set_connection(connection)
        self._cbs_journal = CbsJournalStore(environment(connection).root / "cbs" / "operations")

        model = ""
        if vin:
            logger.debug("VIN from worker: %s", vin)

        prefix = "[DEMO] " if self._demo_mode else ("[READ ONLY] " if self._read_only else "")
        self.status_dot.setText(ORANGE_DOT if self._demo_mode else GREEN_DOT)
        self.status_dot.setToolTip("[DEMO] Demo Mode" if self._demo_mode else "Connected")
        self.car_label.setText(f"{prefix}{model or f'BMW {series}-series'}")
        self.vin_label.setText(f"VIN: {vin}" if vin else "")

        for btn in self.nav_group.buttons():
            btn.setEnabled(True)

        self.nav_group.button(0).setChecked(True)
        self.stack.setCurrentIndex(1)

        # Every environment uses the same owner for keepalive and connection loss.
        self._start_keepalive()

        if not vin:
            self.vehicle_page.populate({})
            self.vehicle_page.refresh_button.setEnabled(False)
            self.vehicle_page.cbs_panel.read_button.setEnabled(False)
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
        self._post_connect_worker = PostConnectWorker(connection, post_connect_tasks())
        self._post_connect_worker.progress.connect(self._on_connection_progress)
        self._post_connect_worker.result_ready.connect(self._on_post_connect_result)
        self._post_connect_worker.error.connect(self._on_post_connect_worker_error)
        self._post_connect_worker.start()

        logger.info("Connected successfully (demo=%s)", self._demo_mode)

    @Slot(object)
    def _on_post_connect_result(self, result: dict) -> None:
        worker = self.sender()
        if not isinstance(worker, PostConnectWorker) or worker is not self._post_connect_worker:
            return
        connection = worker.connection
        self._post_connect_worker = None
        self._retire_worker(worker)
        self._on_post_connect_finished(result, connection)

    @Slot()
    def _refresh_overview(self) -> None:
        """Refresh one settled overview without restarting other page operations."""
        if (
            self._connection is None
            or self._closing
            or self._mutation_active
            or self._coding_loading
            or self._diagnostics_loading
            or self._cbs_worker is not None
            or self.history_page.is_using_vehicle()
            or self._post_connect_worker is not None
            or not getattr(self._connection, "alive_ok", True)
        ):
            return
        if not self._overview_identity[0]:
            return
        self._overview_refresh = True
        self.vehicle_page.set_loading(True)
        self.show_spinner("Refreshing vehicle data...")
        self._spinner_cancel_timer.stop()
        self._spinner_retry_timer.stop()
        worker = PostConnectWorker(self._connection, post_connect_tasks())
        self._post_connect_worker = worker
        worker.progress.connect(self._on_connection_progress)
        worker.result_ready.connect(self._on_post_connect_result)
        worker.error.connect(self._on_post_connect_worker_error)
        worker.start()

    @Slot(str)
    def _on_post_connect_worker_error(self, message: str) -> None:
        worker = self.sender()
        if not isinstance(worker, PostConnectWorker) or worker is not self._post_connect_worker:
            return
        connection = worker.connection
        self._post_connect_worker = None
        self._retire_worker(worker)
        self._on_post_connect_error(message, connection)

    def _on_post_connect_finished(self, result: dict, connection: object) -> None:
        """Publish settled Overview and capability data for the active connection."""
        if self._connection is not connection:
            return  # connection changed, results are stale
        if self._closing or not getattr(connection, "alive_ok", True):
            self.vehicle_page.invalidate("Connection lost — reconnect before refreshing")
            self.vehicle_page.invalidate_order()
            self.vehicle_page.set_loading(False)
            self.vehicle_page.refresh_button.setEnabled(False)
            self._overview_refresh = False
            self.hide_spinner()
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

        if self._demo_mode and self._demo_vehicle is not None and self._demo_vehicle.captured:
            results["connection_info"] = "DEMO · Replaying a captured vehicle session"

        # Populate vehicle page with all results
        self.vehicle_page.populate(results)
        prefix = (
            "[DEMO] "
            if environment(connection).mode == "demo"
            else ("[READ ONLY] " if self._read_only else "")
        )
        self.car_label.setText(prefix + self.vehicle_page.model_label.text())
        self.vehicle_page.set_loading(False)
        inventory = overview_ecus or results.get("svt", overview_ecus)
        if isinstance(inventory, dict):
            inventory = inventory.get("ecus")
        ecus: list[dict] = inventory if isinstance(inventory, list) else []
        order = results.get("vehicle_order")
        model_range = order.get("model_range") if isinstance(order, dict) else ""
        type_code = order.get("type_code") if isinstance(order, dict) else ""
        model_range = model_range if isinstance(model_range, str) else ""
        type_code = type_code if isinstance(type_code, str) else ""
        overview_refresh = self._overview_refresh
        self._overview_refresh = False
        if errors and not overview_refresh:
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

        # Vehicle reads start on demand when their page is opened.
        self.diag_page.set_connection(connection, ecus)
        if overview_refresh:
            self.history_page.set_targets(ecus)
        else:
            self.history_page.set_connection(connection, ecus)
        # An incomplete refresh still marks unavailable observations on Vehicle.
        # Keep settled coding context for display. Preparation reads fresh identities.
        if not overview_refresh or (isinstance(inventory, list) and model_range and type_code):
            self.coding_page.set_connection(
                connection, ecus, model_range=model_range, type_code=type_code
            )

        self.hide_spinner()

    def _on_post_connect_error(self, error_msg: str, connection: object = None) -> None:
        """Handle PostConnectWorker fatal error.

        If the active connection has changed since the worker started,
        the error is stale and this handler returns immediately.
        """
        if connection is not None and self._connection is not connection:
            return  # connection changed, error is stale
        self.hide_spinner()
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

        Reference: plan.md#connection-and-display.
        """
        connection = self._connection
        if (
            connection is None
            or not self._connected
            or self._closing
            or self._connection_loss_dialog
            or getattr(connection, "alive_ok", True)
        ):
            return
        self.vehicle_page.invalidate("Connection lost")
        self.vehicle_page.refresh_button.setEnabled(False)
        if self._mutation_active:
            logger.warning("Connection lost during mutation; waiting for explicit outcomes")
            return
        if (
            self._coding_loading
            or self._diagnostics_loading
            or self._cbs_worker is not None
            or self.history_page.is_using_vehicle()
        ):
            logger.warning("Connection lost during a foreground read; waiting for its outcome")
            return
        self.status_dot.setText(RED_DOT)
        self.status_dot.setToolTip("Connection lost")
        self._stop_keepalive()

        self._connection_loss_dialog = True
        try:
            history_notice = self.history_page.interrupted_write_notice()
            reply = QMessageBox.warning(
                self,
                "Connection Lost",
                "The connection to the vehicle has been lost.\n\n"
                + (history_notice + "\n\n" if history_notice else "")
                + "Check the ENET cable and ensure ignition is on.\n\n"
                "Reconnect?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if self._closing or self._connection is not connection:
                return
            if reply == QMessageBox.StandardButton.Yes:
                self._on_retry_connect()
            else:
                self._on_disconnect()
        finally:
            self._connection_loss_dialog = False

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
        self.welcome_page.set_adapter_polling(True)
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
        """Retry discovery using the selected adapter, through the normal connect path."""
        if self._connect_selection is not None:
            self._on_connect_requested(*self._connect_selection)
        else:
            self._on_disconnect()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Keep worker objects alive while cooperative shutdown completes."""
        if self._mutation_active:
            event.ignore()
            return
        if self.coding_page.has_unexported_results():
            event.ignore()
            self.stack.setCurrentWidget(self.coding_page)
            QMessageBox.warning(
                self,
                "Export coding results",
                "Some coding results could not be saved. Use Export retained coding results "
                "before closing so the operation outcome remains available.",
            )
            return
        if not self._closing:
            self._closing = True
            self.history_page.shutdown()
            self._on_disconnect()
            for page in (self.welcome_page, self.diag_page, self.coding_page):
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
        self._coding_loading = False
        self.coding_page._loading_worker = None
        self._diagnostics_loading = False
        self._overview_after_diagnostics = False
        self._cbs_reset_blocked = False
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
            for name in ("_worker", "_coding_reader", "_coding_writer"):
                worker = getattr(page, name, None)
                if isinstance(worker, QThread):
                    self._retire_worker(worker)
                    setattr(page, name, None)
        self.diag_page.set_connection(None, [])
        self.coding_page._connection = None
        self._worker = None
        self._post_connect_worker = None
        if self._connection:
            try:
                if hasattr(self._connection, "disconnect"):
                    self._connection.disconnect()
            except Exception as e:
                logger.warning("Error during disconnect: %s", e)
            self._connection = None

        self._connected = False
        self.welcome_page.set_adapter_polling(not self._closing)

        self.status_dot.setText(RED_DOT)
        self.status_dot.setToolTip("Disconnected")
        self.car_label.setText("Not connected")
        self.vin_label.setText("")

        for btn in self.nav_group.buttons():
            btn.setChecked(False)
            btn.setEnabled(self.nav_group.id(btn) in (0, 3, 5))

        self.stack.setCurrentIndex(0)
        self.hide_spinner()
        logger.info("Disconnected")

    # ---- Menu actions ----

    def _on_backups(self) -> None:
        self.nav_group.button(5).setChecked(True)
        self.backups_page.set_connection(self._connection)
        idx = self.stack.indexOf(self.backups_page)
        if idx >= 0:
            self.stack.setCurrentIndex(idx)

    def _on_job_data(self) -> None:
        IstaSettingsDialog(self).exec()

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
        return (
            not self._closing
            and not self._mutation_active
            and not self._coding_loading
            and not self._diagnostics_loading
            and self._cbs_worker is None
            and not self.history_page.is_busy()
            and (self.diag_page._worker is None or not self.diag_page._worker.isRunning())
            and not self.coding_page.is_reading()
            and self._post_connect_worker is None
        )

    @Slot()
    def _start_cbs_read(self) -> None:
        """Read CBS from identified owners; DEMO decodes its simulated snapshot."""
        connection = self._connection
        coverage = self.diag_page._coverage if self._connected else []
        complete = sum(coverage_complete(row) for row in coverage)
        coverage_text = (
            f"Memory coverage: {complete}/{len(coverage)} accounted for · See Faults for inventory"
            if coverage
            else "Scan coverage · Unavailable"
        )
        if self._connected and not self.diag_page._stale_scan_notice.isHidden():
            coverage_text += " · Previous scan is stale"
        self.vehicle_page.coverage_label.setText(coverage_text)
        panel = self.vehicle_page.cbs_panel
        self.vehicle_page.service_note.setText(
            panel.message_label.text()
            or (
                "Last service read · Open CBS for source coverage and due values"
                if self._connected and panel._has_result
                else "Service status not read in this session"
            )
        )
        if connection is None:
            panel.show_error("Connect to the vehicle before reading service status")
            return
        if not self._can_start_mutation():
            panel.show_error("Service status unavailable — wait for the current vehicle operation")
            return
        if not self._overview_identity[0]:
            panel.show_error("Service status requires a verified vehicle VIN")
            return
        if getattr(connection, "kind", None) != TransportKind.HSFZ:
            panel.show_error(
                "CBS is unavailable on this transport: its service-controller address mapping "
                "has not been recovered."
            )
            return
        if not getattr(connection, "alive_ok", False):
            panel.show_error("Connection lost — reconnect before reading service status")
            return
        worker = CbsReadWorker(connection, self._overview_ecus)
        self._cbs_worker = worker
        panel.set_busy(True, "read")
        self.show_spinner("Reading service status...")
        self._spinner_cancel_timer.stop()
        self._spinner_retry_timer.stop()
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
        note = (
            "Reconnect and read service status before another reset; the previous outcome "
            "or its local record is incomplete."
            if self._cbs_reset_blocked
            else "Read-only session — resets disabled"
            if read_only
            else ""
        )
        self.vehicle_page.cbs_panel.show_result(
            result,
            resets_allowed=not read_only and not self._cbs_reset_blocked,
            note=note,
        )

    @Slot(str)
    def _on_cbs_error(self, message: str) -> None:
        if self.sender() is self._cbs_worker:
            self.vehicle_page.cbs_panel.show_error(message)

    @Slot()
    def _on_cbs_finished(self) -> None:
        worker = self.sender()
        if worker is not self._cbs_worker or not isinstance(
            worker, (CbsReadWorker, CbsResetWorker)
        ):
            return
        self._cbs_worker = None
        self._retire_worker(worker)
        reset = isinstance(worker, CbsResetWorker)
        if reset:
            self._set_mutation_active(False, refresh_overview=False)
        self.vehicle_page.cbs_panel.set_busy(self._mutation_active)
        self.hide_spinner()
        if (
            not reset
            and self._connection is worker.connection
            and not getattr(worker.connection, "alive_ok", True)
        ):
            QTimer.singleShot(0, self._on_connection_lost)
        if isinstance(worker, CbsResetWorker) and self._connection is worker.connection:
            # Always replace the rows the reset was planned from; a closed
            # connection clears them instead of leaving stale reset actions.
            if getattr(worker.connection, "alive_ok", False):
                self._start_cbs_read()
            else:
                self.vehicle_page.cbs_panel.show_error(
                    "Connection closed — reconnect and read service status"
                )

    @Slot(object)
    def _start_cbs_reset(self, item: dict) -> None:
        """Confirm one source-supported reset, freeze its plan and run it under lockout."""
        connection = self._connection
        if (
            connection is None
            or self._read_only
            or getattr(connection, "read_only", False)
            or not getattr(connection, "alive_ok", False)
            or self._cbs_reset_blocked
            or not self._can_start_mutation()
        ):
            reason = (
                "Reconnect and read service status to resolve the previous reset outcome."
                if self._cbs_reset_blocked
                else "This session is read-only; resets are disabled."
                if self._read_only or getattr(connection, "read_only", False)
                else "Reconnect and read service status before resetting."
                if connection is None or not getattr(connection, "alive_ok", False)
                else "Wait for the current vehicle operation, then retry."
            )
            QMessageBox.information(self, "Reset Unavailable", reason)
            return
        try:
            plan = plan_reset(
                getattr(connection, "verified_vin", ""), item, environment=environment(connection)
            )
        except PermissionError as exc:
            QMessageBox.information(self, "Reset Unavailable", str(exc))
            return
        owner = item["owner"]
        dialog = CockpitDialog("Reset service item", self, width=680, height=440)
        layout = dialog.body
        text = QLabel(
            f"Reset “{item['label']}” in {owner['name']} (0x{owner['address']:02X}, CBS "
            f"{owner['version']})?\n\nThe ECU applies its standard reset and recalculates "
            "the next due values. The app checks completion and rereads service status. "
            "This cannot be undone by the app. The current record and intended requests "
            "are saved locally first.\n\nThis is separate from the headunit service history."
        )
        text.setWordWrap(True)
        layout.addWidget(text)
        power = CheckInput("Battery charger connected or supply voltage is stable")
        layout.addWidget(power)
        dsc_extra = owner.get("reset") == "dsc25-plain"
        extra_ack = CheckInput(
            "I understand this ECU may also clear all DSC faults, run its reset "
            "completion routine and temporarily stop/restart event reporting. "
            "The extra sequence sends two planned reset writes to the ECU."
        )
        extra_ack.setVisible(dsc_extra)
        layout.addWidget(extra_ack)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setText("Reset")
        ok.setEnabled(False)

        def update_reset_confirmation() -> None:
            """Require power and applicable DSC side-effect acknowledgement."""
            ok.setEnabled(power.isChecked() and (not dsc_extra or extra_ack.isChecked()))

        power.toggled.connect(update_reset_confirmation)
        extra_ack.toggled.connect(update_reset_confirmation)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        dialog.add_buttons(buttons, destructive=True)
        if (
            dialog.exec() != QDialog.DialogCode.Accepted
            or connection is not self._connection
            or not self._can_start_mutation()
        ):
            return
        worker = CbsResetWorker(
            connection,
            plan,
            self._cbs_journal,
            power_acknowledged=power.isChecked(),
            dsc_extra_acknowledged=extra_ack.isChecked(),
        )
        self._cbs_worker = worker
        self._set_mutation_active(True)
        self.vehicle_page.cbs_panel.invalidate_resets()
        self.show_spinner("Resetting service item — checking completion...")
        self._spinner_cancel_timer.stop()
        self._spinner_retry_timer.stop()
        worker.result_ready.connect(self._on_cbs_reset)
        worker.error.connect(self._on_cbs_reset_error)
        worker.finished.connect(self._on_cbs_finished)
        worker.start()

    @Slot(object)
    def _on_cbs_reset(self, report: dict) -> None:
        if self.sender() is not self._cbs_worker:
            return
        self._cbs_reset_blocked = report["state"] == "uncertain" or report["persistence_failed"]
        self.vehicle_page.cbs_panel.show_outcome(report)
        persistence = (
            "\n\nThe local operation record could not be saved; see the session log."
            if report["persistence_failed"]
            else f"\n\nRecord: {report['path']}"
        )
        QMessageBox.information(
            self,
            "Service Reset Outcome",
            f"Outcome: {report['state']}\n{report['detail']}\n"
            + (f"Sent by: {report['execution']}\n" if report.get("execution") else "")
            + f"\n{report['instructions']}"
            + persistence,
        )

    @Slot(str)
    def _on_cbs_reset_error(self, message: str) -> None:
        if self.sender() is self._cbs_worker:
            self.vehicle_page.cbs_panel.show_error(message)
            QMessageBox.warning(self, "Service Reset Not Started", message)

    @Slot(bool, bool)
    def _on_diagnostics_mutation_active(self, active: bool, refresh_overview: bool) -> None:
        """Honor the diagnostic worker's explicit follow-up decision."""
        self._set_mutation_active(active, refresh_overview=refresh_overview)

    @Slot(bool)
    def _set_mutation_active(self, active: bool, refresh_overview: bool = True) -> None:
        """Keep the GUI responsive while blocking disruptive app actions."""
        self._mutation_active = active
        self.history_page.setEnabled(not active)
        self.coding_page.setEnabled(not active)
        self.backups_page.setEnabled(not active)
        self.diag_page.setEnabled(not active)
        self.vehicle_page.refresh_button.setEnabled(self._connected and not active)
        self.vehicle_page.cbs_panel.set_busy(active or self._cbs_worker is not None)
        if not active and self._connected and not self._coding_loading and refresh_overview:
            if self._diagnostics_loading:
                self._overview_after_diagnostics = True
            else:
                QTimer.singleShot(0, self._refresh_overview)
        for btn in self.nav_group.buttons():
            btn.setEnabled((self._connected or self.nav_group.id(btn) in (0, 3, 5)) and not active)
        self._cancel_btn.setVisible(False)
        if (
            not active
            and not self._coding_loading
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
