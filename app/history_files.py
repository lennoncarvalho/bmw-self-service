"""Bounded, data-only local history JSON interchange (workflow 28).

Projects preserve same-version extension fields and semantic conflicts. They
carry neither operation authority nor trusted vehicle outcomes; those belong to
separate local journals. Import and export never contact a vehicle.
"""

import json
import math
import os
import re
import tempfile
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from app.service_history import SERVICE_TYPES, HistoryEntry, HistoryItem, encode_nbt_add

MAX_BYTES = 1024 * 1024
MAX_ENTRIES = 1000
MAX_ITEMS = 255
MAX_DEPTH = 16
MAX_NODES = 50000
MAX_STRING = 4096
_VIN = re.compile(r"[A-HJ-NPR-Z0-9]{17}\Z")
_ENTRY_FIELDS = frozenset(
    {"date", "mileage_km", "dealer", "dealer_flag", "correction", "status", "items"}
)
_ITEM_FIELDS = frozenset({"code", "status", "remaining_distance", "remaining_time"})


def valid_vin(value: object) -> bool:
    """Recognize canonical vehicle identity without inventing a checksum rule."""
    return isinstance(value, str) and _VIN.fullmatch(value) is not None and value != "0" * 17


def _integer(value: object, lower: int, upper: int, label: str) -> None:
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError(f"{label} must be an integer from {lower} to {upper}")


def _tree(value: object) -> None:
    """Bound extension data too, before encoding or recursively validating it."""
    pending: list[tuple[object, int]] = [(value, 0)]
    nodes = 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        if nodes > MAX_NODES or depth > MAX_DEPTH:
            raise ValueError("History JSON exceeds its nesting or collection limit")
        if isinstance(item, dict):
            if len(item) > MAX_NODES:
                raise ValueError("History JSON object exceeds its collection limit")
            for key, child in item.items():
                if not isinstance(key, str) or len(key) > MAX_STRING:
                    raise ValueError("History JSON object keys must be bounded strings")
                try:
                    key.encode("utf-8")
                except UnicodeError as exc:
                    raise ValueError("History JSON keys must contain valid Unicode") from exc
                pending.append((child, depth + 1))
        elif isinstance(item, list):
            if len(item) > MAX_NODES:
                raise ValueError("History JSON list exceeds its collection limit")
            pending.extend((child, depth + 1) for child in item)
        elif isinstance(item, str):
            if len(item) > MAX_STRING:
                raise ValueError("History JSON string exceeds its supported length")
            try:
                item.encode("utf-8")
            except UnicodeError as exc:
                raise ValueError("History JSON strings must contain valid Unicode") from exc
        elif type(item) is float:
            if not math.isfinite(item):
                raise ValueError("History JSON cannot contain nonfinite numbers")
        elif item is not None and type(item) not in (bool, int):
            raise ValueError("History project contains a non-JSON value")


def _entry(entry: object) -> dict[str, Any]:
    if not isinstance(entry, dict) or not entry.keys() >= _ENTRY_FIELDS:
        raise ValueError("History entry is missing required fields")
    day = entry["date"]
    if not isinstance(day, str):
        raise ValueError("History date must be an ISO calendar date")
    try:
        parsed_day = date.fromisoformat(day)
    except ValueError as exc:
        raise ValueError("History date must be a valid ISO calendar date") from exc
    if parsed_day.isoformat() != day:
        raise ValueError("History date must use YYYY-MM-DD")
    _integer(entry["mileage_km"], 0, 0xFFFFFFFF, "Mileage")
    _integer(entry["dealer_flag"], 0, 255, "Garage flag")
    _integer(entry["correction"], 0, 255, "Correction")
    _integer(entry["status"], 0, 255, "Entry status")
    if not isinstance(entry["dealer"], str):
        raise ValueError("Garage must be a string")
    items = entry["items"]
    if not isinstance(items, list) or len(items) > MAX_ITEMS:
        raise ValueError("History items must be a list of at most 255 items")
    for item in items:
        if not isinstance(item, dict) or not item.keys() >= _ITEM_FIELDS:
            raise ValueError("History service item is missing required fields")
        _integer(item["code"], 0, 255, "Service type")
        _integer(item["status"], 0, 255, "Item status")
        _integer(item["remaining_distance"], -0x80000000, 0x7FFFFFFF, "Remaining distance")
        _integer(item["remaining_time"], 0, 0xFFFF, "Remaining time")
    return entry


def validate_project(project: object) -> dict[str, Any]:
    """Validate structure without dropping extensions or semantic conflicts."""
    _tree(project)
    if not isinstance(project, dict) or not {"schema_version", "vin", "entries"} <= project.keys():
        raise ValueError("History project is missing required fields")
    if type(project["schema_version"]) is not int or project["schema_version"] != 1:
        raise ValueError("Unsupported history project schema version")
    if project["vin"] is not None and not valid_vin(project["vin"]):
        raise ValueError("History project VIN must be null or a valid uppercase 17-character VIN")
    entries = project["entries"]
    if not isinstance(entries, list) or len(entries) > MAX_ENTRIES:
        raise ValueError("History project must contain at most 1000 entries")
    for entry in entries:
        _entry(entry)
    return project


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("History JSON contains duplicate object keys")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ValueError("History JSON cannot contain nonfinite numbers")


def parse_project(raw: bytes) -> dict[str, Any]:
    """Parse at most 1 MiB of strict UTF-8 JSON; reject a bad import atomically."""
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise ValueError("History project exceeds the 1 MiB limit")
    try:
        project = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant
        )
        return validate_project(project)
    except (UnicodeError, RecursionError, OverflowError) as exc:
        raise ValueError("History project contains invalid or excessively nested JSON") from exc


def load_project(path: Path) -> dict[str, Any]:
    """Read one bounded project without following any paths embedded in its data."""
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    return parse_project(raw)


def project_bytes(project: dict[str, Any]) -> bytes:
    """Encode validated project data deterministically, retaining extension fields."""
    validate_project(project)
    try:
        raw = (
            json.dumps(
                project, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
            )
        ).encode("utf-8")
    except (UnicodeError, RecursionError, OverflowError) as exc:
        raise ValueError("History project cannot be encoded as JSON") from exc
    if len(raw) > MAX_BYTES:
        raise ValueError("History project exceeds the 1 MiB limit")
    return raw


def save_project(path: Path, project: dict[str, Any]) -> None:
    """Durably publish a deterministic project at an explicitly selected path."""
    raw = project_bytes(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=".history-", delete=False
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


def entry_model(entry: dict[str, Any]) -> HistoryEntry:
    """Convert a structured entry to encoder input without changing its fields."""
    _tree(entry)
    _entry(entry)
    try:
        dealer = entry["dealer"].encode("ascii")
    except UnicodeError as exc:
        raise ValueError("Garage must contain one to seven ASCII bytes without NUL") from exc
    return HistoryEntry(
        service_date=date.fromisoformat(entry["date"]),
        correction=entry["correction"],
        mileage_km=entry["mileage_km"],
        dealer_flag=entry["dealer_flag"],
        dealer_bytes=dealer,
        status=entry["status"],
        items=tuple(
            HistoryItem(
                code=item["code"],
                status=item["status"],
                remaining_distance=item["remaining_distance"],
                remaining_time=item["remaining_time"],
            )
            for item in entry["items"]
        ),
    )


def entry_conflicts(project: dict[str, Any], today: date | None = None) -> list[list[str]]:
    """Return each entry's send conflicts; retain every imported entry unchanged.

    This checks duplicate dates within this project. Append preparation must
    additionally check dates in the bound vehicle's known local journal, excluding
    only the edited draft identity. Imported extension fields confer no authority.
    """
    validate_project(project)
    counts = Counter(entry["date"] for entry in project["entries"])
    codes = {code for _, code in SERVICE_TYPES}
    result: list[list[str]] = []
    for entry in project["entries"]:
        conflicts = []
        if counts[entry["date"]] > 1:
            conflicts.append("Duplicate date in local project")
        unknown = sorted({item["code"] for item in entry["items"] if item["code"] not in codes})
        if unknown:
            conflicts.append("Unknown service types: " + ", ".join(map(str, unknown)))
        try:
            encode_nbt_add(entry_model(entry), existing_dates=(), today=today)
        except ValueError as exc:
            message = str(exc)
            if message != "Unsupported service type for a new entry":
                conflicts.append(message)
        result.append(conflicts)
    return result
