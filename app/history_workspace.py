"""Separate durable local editor workspaces; never a vehicle mutation journal.

Draft identities and import provenance belong here, outside project interchange
and coding backups. Workspace isolation never changes a project's explicit VIN.
"""

import hashlib
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from app.history_files import project_bytes, valid_vin, validate_project

MAX_BYTES = 2 * 1024 * 1024
_FIELDS = frozenset({"schema_version", "kind", "project", "records"})


def _encoded(value: object) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (UnicodeError, RecursionError, OverflowError, TypeError) as exc:
        raise ValueError("History workspace cannot be encoded as JSON") from exc


def _key(key: str) -> str:
    if key in ("offline", "demo-unbound"):
        return key
    if not isinstance(key, str):
        raise ValueError("Invalid history workspace identity")
    mode, separator, vin = key.partition("-")
    if separator != "-" or mode not in ("live", "demo") or not valid_vin(vin):
        raise ValueError(
            "History workspace requires offline, demo-unbound, live-VIN or demo-VIN identity"
        )
    return key


def _path(key: str, root: Path | None) -> Path:
    directory = root if root is not None else Path.home() / "BMW-Tool" / "history" / "projects"
    # No component of a supplied key or project is interpreted as a filesystem path.
    return directory / (hashlib.sha256(_key(key).encode("ascii")).hexdigest() + ".json")


def _validate(workspace: object) -> dict[str, Any]:
    if not isinstance(workspace, dict) or workspace.keys() != _FIELDS:
        raise ValueError("Invalid history workspace fields")
    if (
        type(workspace["schema_version"]) is not int
        or workspace["schema_version"] != 1
        or workspace["kind"] != "history-workspace"
    ):
        raise ValueError("Unsupported history workspace schema")
    project = validate_project(workspace["project"])
    project_bytes(project)
    metadata = workspace["records"]
    if not isinstance(metadata, list) or len(metadata) != len(project["entries"]):
        raise ValueError("History workspace entry identities do not match its project")
    identities: set[str] = set()
    for row in metadata:
        if (
            not isinstance(row, dict)
            or not {"id", "origin"} <= row.keys()
            or row.keys() - {"id", "origin", "source_vin", "source_workspace"}
        ):
            raise ValueError("Invalid history workspace entry provenance")
        identity = row["id"]
        if not isinstance(identity, str):
            raise ValueError("Invalid history workspace entry identity")
        try:
            canonical = uuid.UUID(identity).hex
        except ValueError as exc:
            raise ValueError("Invalid history workspace entry identity") from exc
        if canonical != identity or identity in identities:
            raise ValueError("Invalid or duplicate history workspace entry identity")
        identities.add(identity)
        if row["origin"] not in ("draft", "imported"):
            raise ValueError("History editor records must be drafts or imports")
        if "source_workspace" in row:
            _key(row["source_workspace"])
        if (
            "source_vin" in row
            and row["source_vin"] is not None
            and not valid_vin(row["source_vin"])
        ):
            raise ValueError("History source VIN must be null or a canonical vehicle identity")
    return workspace


def new_record(origin: str = "draft") -> dict[str, Any]:
    """Create a stable local editor identity without trusted vehicle-outcome claims."""
    if origin not in ("draft", "imported"):
        raise ValueError("History editor records must be drafts or imports")
    return {"id": uuid.uuid4().hex, "origin": origin}


def new_workspace(project: dict[str, Any] | None = None, origin: str = "draft") -> dict[str, Any]:
    """Copy project data and create independent stable local identities for its entries."""
    if origin not in ("draft", "imported"):
        raise ValueError("History editor records must be drafts or imports")
    supplied = project if project is not None else {"schema_version": 1, "vin": None, "entries": []}
    # JSON round-trip detaches nested caller collections while retaining extension fields.
    copied = json.loads(project_bytes(supplied))
    return _validate(
        {
            "schema_version": 1,
            "kind": "history-workspace",
            "project": copied,
            "records": [new_record(origin) for _ in copied["entries"]],
        }
    )


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("History workspace contains duplicate object keys")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ValueError("History workspace cannot contain nonfinite numbers")


def load_workspace(key: str, *, root: Path | None = None) -> dict[str, Any]:
    """Read one isolated workspace, or return a new unbound workspace if absent.

    Corruption is an error, never an empty-project fallback. A stored project VIN
    is retained even when different from the workspace's active-vehicle identity;
    callers must explicitly resolve that mismatch before a future vehicle write.
    """
    path = _path(key, root)
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
    except FileNotFoundError:
        return new_workspace()
    if len(raw) > MAX_BYTES:
        raise ValueError("History workspace exceeds the 2 MiB limit")
    try:
        record = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeError, RecursionError, OverflowError) as exc:
        raise ValueError("History workspace contains invalid JSON") from exc
    if not isinstance(record, dict) or record.keys() != {"key", "workspace", "sha256"}:
        raise ValueError("Invalid history workspace record")
    if record["key"] != key:
        raise ValueError("History workspace belongs to another vehicle or mode")
    digest = hashlib.sha256(_encoded({"key": key, "workspace": record["workspace"]})).hexdigest()
    if record["sha256"] != digest:
        raise ValueError("History workspace integrity check failed")
    return _validate(record["workspace"])


def save_workspace(key: str, workspace: dict[str, Any], *, root: Path | None = None) -> None:
    """Atomically publish validated local state and sync it before reporting success."""
    path = _path(key, root)
    payload = {"key": key, "workspace": _validate(workspace)}
    record = {**payload, "sha256": hashlib.sha256(_encoded(payload)).hexdigest()}
    raw = _encoded(record)
    if len(raw) > MAX_BYTES:
        raise ValueError("History workspace exceeds the 2 MiB limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=".history-workspace-", delete=False
        ) as stream:
            temporary = stream.name
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


class HistoryWorkspaceStore:
    """Keep offline, live and demonstration editors in separately addressed files."""

    def __init__(self, root: Path | None = None) -> None:
        """Select local editor storage separately from coding and mutation records."""
        self.root = root

    def load_workspace(self, key: str) -> dict[str, Any]:
        """Load validated local state, never silently replacing corrupted data."""
        return load_workspace(key, root=self.root)

    def save_workspace(self, key: str, workspace: dict[str, Any]) -> None:
        """Durably save the editor without associating or changing its project VIN."""
        save_workspace(key, workspace, root=self.root)
