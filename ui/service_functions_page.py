"""Vehicle-specific service cards and modal operator controls."""

from collections.abc import Callable
from functools import partial
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import QDialogButtonBox, QPushButton, QVBoxLayout, QWidget

from app.service_functions import (
    ServiceAction,
    ServiceCard,
    ServiceListing,
    ServiceResult,
    ServiceWorker,
)
from ui.cockpit import ActionCard, CardGrid, PageHeader, StatusLabel, caption, match_button_widths
from ui.dialogs import CockpitDialog
from ui.form_inputs import CheckInput, SelectInput


class ServiceDialog(CockpitDialog):
    """Keep the reviewed operation, live readings and owner observations together."""

    requested = Signal(object, tuple)

    def __init__(self, card: ServiceCard, read_only: bool, parent: QWidget) -> None:
        super().__init__(card.title, parent)
        self.card = card
        self.read_only = read_only
        self.running = False
        self.stale = False
        self.body.addWidget(caption(card.component, "identity"))
        self.body.addWidget(caption(card.description))
        if card.readings:
            self.body.addWidget(caption(card.readings_label, "featureTitle"))
            self.body.addWidget(caption("\n".join(card.readings)))
        self.choice = SelectInput(options=((a.label, a.key) for a in card.actions))
        self.choice.setAccessibleName("Service action")
        if len(card.actions) > 1:
            action_label = caption("Action", "featureTitle")
            action_label.setBuddy(self.choice)
            self.body.addWidget(action_label)
        self.choice.setVisible(len(card.actions) > 1)
        self.body.addWidget(self.choice)
        self.conditions = QVBoxLayout()
        self.body.addLayout(self.conditions)
        self.checks: list[CheckInput] = []
        self.progress = StatusLabel()
        self.outcome_label = caption("")
        self.outcome_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.body.addWidget(self.progress)
        self.body.addWidget(self.outcome_label)
        self.owner = SelectInput(
            options=(
                ("Not checked", ""),
                ("As expected", "As expected"),
                ("Issue observed", "Issue observed"),
            )
        )
        self.owner.setAccessibleName(card.observation)
        self.owner.setEnabled(False)
        self.owner_log = caption("")
        self._stage = ""
        if card.observation:
            self.body.addWidget(caption(card.observation, "featureTitle"))
            self.body.addWidget(self.owner)
            self.body.addWidget(self.owner_log)
            self.owner.activated.connect(self._observe)
        else:
            self.owner.hide()
            self.owner_log.hide()
        self.body.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        self.run_button = buttons.addButton("Run", QDialogButtonBox.ButtonRole.AcceptRole)
        self.add_buttons(buttons)
        self.run_button.setAutoDefault(False)
        self.close_button.setDefault(True)
        self.close_button.setFocus()
        buttons.rejected.connect(self.reject)
        self.run_button.clicked.connect(self._request)
        self.choice.currentIndexChanged.connect(self._select)
        self._select()

    @property
    def action(self) -> ServiceAction:
        """Return the immutable action at the selected position."""
        return self.card.actions[self.choice.currentIndex()]

    @Slot()
    def _select(self) -> None:
        for check in self.checks:
            self.conditions.removeWidget(check)
            check.hide()
            check.deleteLater()
        self.checks = []
        for condition in self.action.confirmations:
            check = CheckInput(condition)
            check.toggled.connect(self._controls)
            self.conditions.addWidget(check)
            self.checks.append(check)
        self.run_button.setText(self.action.label)
        match_button_widths((self.run_button, self.close_button))
        self._controls()

    @Slot()
    def _controls(self) -> None:
        denied = self.read_only and self.action.temporary
        self.choice.setEnabled(not self.running and not self.stale)
        for check in self.checks:
            check.setEnabled(not self.running and not denied and not self.stale)
        self.run_button.setEnabled(
            not self.running
            and not self.stale
            and not denied
            and all(c.isChecked() for c in self.checks)
        )
        if denied and not self.stale:
            self.progress.setText("This session is read-only.")
        self.close_button.setEnabled(not self.running)

    @Slot()
    def _request(self) -> None:
        if self.run_button.isEnabled():
            self.requested.emit(
                self.action, tuple(c.accessibleName() for c in self.checks if c.isChecked())
            )

    @Slot(int)
    def _observe(self, index: int) -> None:
        if index and self._stage:
            observation = f"{self._stage} — {self.owner.currentText()}"
            self.owner_log.setText("\n".join(filter(None, (self.owner_log.text(), observation))))
        self.owner.setCurrentIndex(0)

    def set_running(self, active: bool) -> None:
        """Lock operation inputs until the held worker releases the vehicle."""
        self.running = active
        self.observe("")
        if active:
            self.outcome_label.clear()
            self.owner_log.clear()
            self.progress.setText("Checking vehicle and component…")
        else:
            for check in self.checks:
                check.setChecked(False)
        self._controls()

    def show_progress(self, message: str) -> None:
        """Expose phase readings and the context for an independent owner observation."""
        self.progress.setText(message)

    def observe(self, component: str) -> None:
        """Associate the owner’s observation with the active output or inspection stage."""
        self._stage = component
        self.owner.setEnabled(bool(component))

    def show_result(self, result: ServiceResult) -> None:
        """Keep the full outcome visible after the operation finishes."""
        self.progress.clear()
        self.outcome_label.setText("\n".join((result.state, *result.lines)))

    def connection_lost(self) -> None:
        """Preserve the guidance and last readings while the owner finishes the procedure."""
        self.stale = True
        self.progress.setText("Connection lost. Close this dialog to reconnect.")
        self._controls()

    def reject(self) -> None:
        """Keep the dialog open until its worker has settled."""
        if self.running:
            return
        super().reject()


class ServiceFunctionsPage(QWidget):
    """Present the currently identified vehicle's supported component functions."""

    discovery_loading = Signal(bool)
    mutation_active = Signal(bool, bool)
    settled = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.can_start: Callable[[], bool] = lambda: True
        self._connection: Any = None
        self._ecus: list[dict] = []
        self.worker: ServiceWorker | None = None
        self.listing: ServiceListing | None = None
        self.dialog: ServiceDialog | None = None
        self._mutation = False
        box = QVBoxLayout(self)
        box.setContentsMargins(24, 24, 24, 24)
        box.setSpacing(16)
        header = PageHeader(
            "Service Functions", "Read component status and check the wipers and interior mirror."
        )
        self.refresh = QPushButton("Check availability")
        self.refresh.setProperty("class", "secondary")
        self.refresh.clicked.connect(self.discover)
        header.action_layout.addWidget(self.refresh)
        box.addWidget(header)
        self.notice = StatusLabel()
        box.addWidget(self.notice)
        self.groups = QVBoxLayout()
        self.groups.setSpacing(16)
        box.addLayout(self.groups)
        box.addStretch()
        self.set_connection(None, [])

    def set_connection(self, connection: Any, ecus: list[dict]) -> None:
        """Invalidate reviewed results when inventory or connection generation changes."""
        if self.dialog is not None:
            self.dialog.set_running(False)
            self.dialog.reject()
        self._connection, self._ecus = connection, list(ecus)
        self.listing = None
        self._clear()
        self.refresh.setEnabled(connection is not None and bool(ecus))
        self.notice.setText(
            "Connect and identify the vehicle to check service availability." if not ecus else ""
        )

    def _clear(self) -> None:
        while self.groups.count():
            item = self.groups.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.hide()
                widget.deleteLater()

    def activate(self) -> None:
        """Discover equipment on first visit after identification."""
        if self.listing is None and self.refresh.isEnabled():
            self.discover()

    @Slot()
    def discover(self) -> None:
        """Refresh availability through the same worker used by the control dialog."""
        if self._connection is None or not self.can_start() or self.worker is not None:
            return
        self._clear()
        self.listing = None
        self.notice.clear()
        worker = ServiceWorker(self._connection, self._ecus)
        self._start(worker)
        self.discovery_loading.emit(True)
        worker.start()

    def _render(self, listing: ServiceListing) -> None:
        self.listing = listing
        self._clear()
        groups: dict[str, CardGrid] = {}
        for _, definition in listing.cards.values():
            grid = groups.get(definition.category)
            if grid is None:
                self.groups.addWidget(caption(definition.category, "sectionTitle"))
                grid = CardGrid()
                groups[definition.category] = grid
                self.groups.addWidget(grid)
            card = ActionCard(definition.title, definition.component)
            card.button.clicked.connect(partial(self._open, definition))
            grid.add_card(card)
        lines = list(listing.notices)
        if not listing.cards:
            lines.insert(0, "No supported functions were identified for this vehicle.")
        self.notice.setText("\n".join(lines))

    def _open(self, card: ServiceCard) -> None:
        if not self.listing or self.worker or self.dialog or not card.actions:
            return
        self.dialog = ServiceDialog(card, self._connection.read_only, self)
        self.dialog.requested.connect(self._run)
        self.dialog.finished.connect(self._dismiss)
        self.dialog.open()

    @Slot()
    def _dismiss(self) -> None:
        if self.dialog is not None:
            self.dialog.deleteLater()
            self.dialog = None
            if self._connection is not None and not self._connection.alive_ok:
                QTimer.singleShot(0, self.settled.emit)

    @Slot(object, tuple)
    def _run(self, action: ServiceAction, confirmed: tuple[str, ...]) -> None:
        if not self.listing or not self.dialog or self.worker is not None or not self.can_start():
            return
        worker = ServiceWorker(
            self._connection,
            self._ecus,
            listing=self.listing,
            key=self.dialog.card.key,
            action=action.key,
            confirmed=confirmed,
        )
        self.dialog.set_running(True)
        self._mutation = action.temporary
        self._start(worker)
        if self._mutation:
            self.mutation_active.emit(True, False)
        worker.start()

    def _start(self, worker: ServiceWorker) -> None:
        self.worker = worker
        self.refresh.setEnabled(False)
        worker.result_ready.connect(self._result)
        worker.progress.connect(self._progress)
        if self.dialog is not None:
            worker.observation_ready.connect(self.dialog.observe)
        worker.error.connect(self._error)
        worker.finished.connect(self._finished)

    @Slot(str)
    def _progress(self, message: str) -> None:
        if self.sender() is self.worker and self.dialog is not None:
            self.dialog.show_progress(message)

    @Slot(object)
    def _result(self, result: ServiceListing | ServiceResult) -> None:
        if self.sender() is not self.worker:
            return
        if isinstance(result, ServiceListing):
            self._render(result)
        elif self.dialog is not None:
            self.dialog.show_result(result)
            if not self._connection.alive_ok or self._mutation and result.state == "Uncertain":
                self._invalidate()
        else:
            self.notice.setText("\n".join((result.state, *result.lines)))

    def _invalidate(self) -> None:
        self.listing = None
        self._clear()
        self.notice.setText("Check availability again to review fresh vehicle state.")
        if self.dialog is not None:
            self.dialog.stale = True

    @Slot(str)
    def _error(self, message: str) -> None:
        if self.worker is None or self.sender() is not self.worker:
            return
        if self._mutation:
            self._invalidate()
        self._result(ServiceResult("Uncertain" if self._mutation else "Unavailable", (message,)))

    @Slot()
    def _finished(self) -> None:
        worker = self.worker
        if worker is None or self.sender() is not worker:
            return
        self.worker = None
        self.refresh.setEnabled(self._connection is not None and self._connection.alive_ok)
        if self.dialog is not None:
            self.dialog.set_running(False)
        if worker.listing is None:
            self.discovery_loading.emit(False)
        if self._mutation:
            self._mutation = False
            self.mutation_active.emit(False, False)
        worker.deleteLater()
        self.settled.emit()
