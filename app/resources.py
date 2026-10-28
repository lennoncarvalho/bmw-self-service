"""Read-only bundled resource paths independent of the working directory."""

import sys
from pathlib import Path


def resource_path(relative: str) -> Path:
    """Resolve a shipped asset in a source checkout or PyInstaller bundle."""
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return root / relative
