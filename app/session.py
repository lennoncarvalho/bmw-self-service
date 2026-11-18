"""Immutable environment identity and isolated operation stores."""

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.operation_store import OperationStore


@dataclass(frozen=True)
class SessionEnvironment:
    """Keep environment authority separate from vehicle identity and transport."""

    mode: str = "live"
    instance: str = ""

    def __post_init__(self) -> None:
        if self.mode not in ("live", "demo"):
            raise ValueError("Unknown session environment")
        if self.mode == "demo":
            if uuid.UUID(self.instance).hex != self.instance:
                raise ValueError("Invalid DEMO instance")
        elif self.instance:
            raise ValueError("Live sessions cannot carry a DEMO instance")

    @property
    def root(self) -> Path:
        """Return the durable root without creating files or directories."""
        base = Path.home() / "BMW-Tool"
        return base / "demo" / self.instance if self.mode == "demo" else base

    def binding(self) -> dict[str, str]:
        """Return detached identity for immutable write plans."""
        return {"mode": self.mode, "instance": self.instance}


LIVE = SessionEnvironment()


def environment(connection: Any) -> SessionEnvironment:
    """Read explicit context; retained live callers default to the live environment."""
    value = getattr(connection, "environment", LIVE)
    if not isinstance(value, SessionEnvironment):
        raise PermissionError("Invalid session environment")
    return value


def check_binding(connection: Any, binding: object) -> None:
    """Reject an operation prepared in another environment or virtual instance."""
    expected = environment(connection).binding()
    if binding is None and expected == LIVE.binding():
        return
    if binding != expected:
        raise PermissionError("Operation belongs to another session environment")


def check_record(connection: Any, mode: str, path: Path | None = None) -> None:
    """Check saved-record environment before any restoration or verification send."""
    current = environment(connection)
    if mode != current.mode:
        raise PermissionError("Saved record belongs to another environment")
    if (
        current.mode == "demo"
        and path is not None
        and not path.resolve().is_relative_to(current.root.resolve())
    ):
        raise PermissionError("Import this record into the current DEMO instance first")


def check_store(connection: Any, store: Any) -> None:
    """Prevent a virtual operation from using live persistence, even with an injected store."""
    current = environment(connection)
    if getattr(store, "mode", current.mode) != current.mode:
        raise PermissionError("Operation store belongs to another environment")
    root = store.root.resolve()
    if current.mode == "demo" and not root.is_relative_to(current.root.resolve()):
        raise PermissionError("Operation store belongs to another DEMO instance")
    if current.mode == "live" and root.is_relative_to((current.root / "demo").resolve()):
        raise PermissionError("A live operation cannot use a DEMO store")


def operation_store(connection: Any) -> "OperationStore":
    """Build the normal coding store in the active environment."""
    from app.operation_store import OperationStore

    current = environment(connection)
    return OperationStore(current.root / "backups" / "operations", mode=current.mode)
