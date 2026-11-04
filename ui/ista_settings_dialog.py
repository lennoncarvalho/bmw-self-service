"""Status of the standalone generated job data and interpreter included in the app."""

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ediabas import library_path
from app.ista_data import BundleProvider, IstaDataSource, bundle_root
from app.ista_jobs import refresh_bundled_data


def bundle_summary() -> str:
    """Describe generated-data metadata without opening reference source folders."""
    root = bundle_root()
    source = IstaDataSource.from_paths(root, None)
    if not source.providers:
        return (
            "Present but unreadable. Job-backed features are unavailable."
            if root.exists()
            else "Not included in this build. Job-backed features are unavailable."
        )
    bundle = source.providers[0]
    assert isinstance(bundle, BundleProvider)
    count = len(bundle.manifest["files"])
    series = ", ".join(bundle.available_series()) or "none"
    return (
        f"{count} job files listed; model ECU lists {series}; data {bundle.source_version}. "
        "File integrity is checked before jobs are used."
    )


class IstaSettingsDialog(QDialog):
    """Show bundled diagnostic-data status with no runtime source-folder chooser."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the status dialog using only generated runtime-asset metadata."""
        super().__init__(parent)
        self.setWindowTitle("ECU Job Data")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        intro = QLabel("Diagnostic jobs use the data and interpreter included with this build.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        self.bundle_label = QLabel()
        self.bundle_label.setWordWrap(True)
        form.addRow("Bundled data", self.bundle_label)
        self.runtime_label = QLabel()
        self.runtime_label.setWordWrap(True)
        form.addRow("Job interpreter", self.runtime_label)
        layout.addLayout(form)

        self.status_label = QLabel(
            "Available functions depend on the identified ECU and the data included in this build."
        )
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        refresh = QPushButton("Refresh Status")
        refresh.clicked.connect(self._refresh)
        layout.addWidget(refresh)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._refresh()

    def _refresh(self) -> None:
        """Reload generated-data status without opening research source folders."""
        refresh_bundled_data()
        self.bundle_label.setText(bundle_summary())
        self.runtime_label.setText(
            "Included. Compatibility is checked before execution."
            if library_path().is_file()
            else "Not included in this build. Job execution is unavailable."
        )
