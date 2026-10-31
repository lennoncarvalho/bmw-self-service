"""Settings dialog for the ECU job data: bundled data status and the ISTA 4.29 folder (D-62)."""

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ista_data import (
    SUPPORTED_VERSION_PREFIX,
    BundleProvider,
    DataFormatError,
    bundle_root,
    save_ista_folder,
    saved_ista_folder,
    validate_ista_folder,
)


def bundle_summary() -> str:
    """One-line status of the bundled job data."""
    root = bundle_root()
    if not (root / "manifest.json").is_file():
        return "Not included in this build."
    try:
        bundle = BundleProvider(root)
    except DataFormatError:
        return "Present but unreadable; it will be ignored."
    files = bundle.manifest.get("files", {})
    count = len(files) if isinstance(files, dict) else 0
    series = ", ".join(bundle.available_series()) or "none"
    version = bundle.source_version or "unknown version"
    return f"{count} job files; model ECU lists {series}; built from data {version}."


class IstaSettingsDialog(QDialog):
    """Choose and validate the ISTA 4.29 folder used when bundled data lacks a file."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the dialog from the saved setting and the bundle manifest."""
        super().__init__(parent)
        self.setWindowTitle("ECU Job Data")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)

        intro = QLabel(
            "Diagnostic jobs use the bundled data first. Models or ECUs it does not "
            "cover are read from an ISTA 4.29 folder on this computer."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        self.bundle_label = QLabel(bundle_summary())
        self.bundle_label.setWordWrap(True)
        form.addRow("Bundled data", self.bundle_label)
        self.folder_label = QLabel()
        self.folder_label.setWordWrap(True)
        form.addRow("ISTA folder", self.folder_label)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        form.addRow("Status", self.status_label)
        layout.addLayout(form)

        row = QHBoxLayout()
        self.choose_button = QPushButton("Choose Folder...")
        self.choose_button.clicked.connect(self._choose)
        row.addWidget(self.choose_button)
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self._clear)
        row.addWidget(self.clear_button)
        row.addStretch(1)
        layout.addLayout(row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._show_folder(saved_ista_folder())

    def _show_folder(self, folder: str) -> None:
        self.clear_button.setEnabled(bool(folder))
        if not folder:
            self.folder_label.setText("Not set")
            self.status_label.setText("No folder selected.")
            return
        self.folder_label.setText(folder)
        check = validate_ista_folder(folder)
        self.status_label.setText(self._describe(check.ok, check.message, check.version))

    @staticmethod
    def _describe(ok: bool, message: str, version: str) -> str:
        if not ok:
            return f"Not usable: {message}"
        text = f"Valid: {message}."
        if not version:
            return f"{text} Data version unknown."
        if not version.startswith(SUPPORTED_VERSION_PREFIX):
            return f"{text} Data version {version} is not {SUPPORTED_VERSION_PREFIX}; untested."
        return f"{text} Data version {version}."

    def _choose(self) -> None:
        start = saved_ista_folder()
        folder = QFileDialog.getExistingDirectory(self, "Choose the ISTA folder", start)
        if not folder:
            return
        check = validate_ista_folder(folder)
        if check.ok:
            save_ista_folder(folder)
            self._show_folder(folder)
            return
        # Keep the previous setting; show why the new choice was rejected.
        self.folder_label.setText(saved_ista_folder() or "Not set")
        self.status_label.setText(
            f"{folder} was not saved. {self._describe(False, check.message, '')}"
        )

    def _clear(self) -> None:
        save_ista_folder("")
        self._show_folder("")
