"""Durable local history intent/results, separate from coding ECU baselines.

Prior vehicle history is unavailable. These records preserve what this app
planned and received; they never authorize replay or claim observed car history.
"""

import hashlib
import json
import os
import tempfile
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from app.history_files import (
    entry_conflicts,
    entry_model,
    project_bytes,
    valid_vin,
    validate_project,
)
from app.service_history import encode_nbt_add

MAX_BYTES = 8 * 1024 * 1024
MAX_STEPS = 1006
MAX_LIST_BYTES = 32 * 1024 * 1024
MAX_EVENTS = 5000
_STEP_STATES = frozenset({"sending", "accepted", "rejected", "unattempted", "uncertain"})
_FINAL_STATES = frozenset(
    {"response-confirmed", "cycle-required", "partial", "uncertain", "rejected"}
)
_INTENT_FIELDS = frozenset(
    {
        "id",
        "created",
        "kind",
        "environment",
        "vin",
        "mode",
        "target",
        "encoder",
        "vehicle_history_before",
        "vehicle_history_before_provenance",
        "local_before",
        "intended",
        "requests",
        "draft_ids",
    }
)


def _encoded(value: object) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, UnicodeError, RecursionError, OverflowError) as exc:
        raise ValueError("History journal contains invalid JSON data") from exc


def _digest(value: object) -> str:
    return hashlib.sha256(_encoded(value)).hexdigest()


def _identifier(value: object) -> None:
    if not isinstance(value, str):
        raise ValueError("History journal identity must be canonical UUID hex")
    try:
        canonical = uuid.UUID(value).hex
    except ValueError as exc:
        raise ValueError("History journal identity must be canonical UUID hex") from exc
    if canonical != value:
        raise ValueError("History journal identity must be canonical UUID hex")


def _hex(value: object, *, maximum: int = 8192, empty: bool = False) -> None:
    if not isinstance(value, str) or len(value) > maximum or (not value and not empty):
        raise ValueError("History journal bytes must be bounded canonical hexadecimal")
    try:
        canonical = bytes.fromhex(value).hex()
    except ValueError as exc:
        raise ValueError("History journal bytes must be canonical hexadecimal") from exc
    if value != canonical:
        raise ValueError("History journal bytes must be canonical hexadecimal")


def _timestamp(value: object) -> None:
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("History journal timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("History journal timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("History journal timestamp requires an explicit timezone")


def _bounded_tree(value: object) -> None:
    pending = [(value, 0)]
    nodes = 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        if depth > 24 or nodes > 250000:
            raise ValueError("History journal exceeds its nesting or collection limit")
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str) or len(key) > 4096:
                    raise ValueError("History journal contains an invalid field name")
                pending.append((child, depth + 1))
        elif isinstance(item, list):
            if len(item) > 50000:
                raise ValueError("History journal exceeds its collection limit")
            pending.extend((child, depth + 1) for child in item)
        elif isinstance(item, str):
            if len(item) > 65536:
                raise ValueError("History journal exceeds its string limit")
        elif item is not None and type(item) not in (bool, int, float):
            raise ValueError("History journal contains a non-JSON value")


def _validate_intent(intent: object) -> dict[str, Any]:
    if not isinstance(intent, dict) or intent.keys() != _INTENT_FIELDS:
        raise ValueError("Invalid history journal intent fields")
    _identifier(intent["id"])
    _timestamp(intent["created"])
    if intent["kind"] != "history-operation" or intent["environment"] not in ("live", "demo"):
        raise ValueError("Invalid history journal kind or environment")
    if not valid_vin(intent["vin"]) or intent["mode"] not in ("append", "replace"):
        raise ValueError("Invalid history journal vehicle or mode")
    if (
        intent["vehicle_history_before"] is not None
        or intent["vehicle_history_before_provenance"] != "unavailable-not-read"
    ):
        raise ValueError("History journal must not invent a prior vehicle history baseline")
    before = validate_project(intent["local_before"])
    project_bytes(before)
    if before["vin"] != intent["vin"]:
        raise ValueError("History project must be explicitly bound to this vehicle")
    intended = {"schema_version": 1, "vin": intent["vin"], "entries": intent["intended"]}
    project_bytes(intended)
    entries = intended["entries"]
    if not entries or (intent["mode"] == "append" and len(entries) != 1):
        raise ValueError("History intent must contain one append or a nonempty replacement")
    # Dates were checked against today's date during preparation. Loading a
    # journal preserves historical intent without depending on later clock changes.
    if any(entry_conflicts(intended, today=date.max)):
        raise ValueError("History intent contains unsendable entries or duplicate dates")
    ids = intent["draft_ids"]
    if not isinstance(ids, list) or len(ids) != len(entries):
        raise ValueError("History intent draft identities do not match its entries")
    for identity in ids:
        _identifier(identity)
    if len(set(ids)) != len(ids):
        raise ValueError("History intent draft identities must be unique")
    target = intent["target"]
    required = {"address", "name", "variant", "address_index", "software", "identity"}
    if not isinstance(target, dict) or not target.keys() >= required:
        raise ValueError("History intent requires exact target identity")
    if type(target["address"]) is not int or not 0 <= target["address"] <= 0xFFFF:
        raise ValueError("Invalid history target address")
    if "vin_address" in target and (
        type(target["vin_address"]) is not int or not 0 <= target["vin_address"] <= 0xFFFF
    ):
        raise ValueError("Invalid history VIN identity endpoint")
    for field in ("name", "variant", "address_index"):
        if not isinstance(target[field], str) or not 1 <= len(target[field]) <= 256:
            raise ValueError("History intent requires exact target identity")
    for field in ("software", "identity"):
        _hex(target[field])
    encoder = intent["encoder"]
    if not isinstance(encoder, dict) or encoder.keys() != {"id", "sha256"}:
        raise ValueError("Invalid history encoder identity")
    if not isinstance(encoder["id"], str) or not 1 <= len(encoder["id"]) <= 256:
        raise ValueError("Invalid history encoder identity")
    _hex(encoder["sha256"], maximum=64)
    if len(encoder["sha256"]) != 64:
        raise ValueError("History encoder requires SHA-256")
    steps = intent["requests"]
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
        raise ValueError("History request plan exceeds its supported size")
    add_indices = []
    erase_count = 0
    for step in steps:
        if not isinstance(step, dict) or step.keys() != {"kind", "request", "entry_index"}:
            raise ValueError("Invalid history request plan step")
        if step["kind"] not in ("identity", "session", "erase", "add", "reset"):
            raise ValueError("Invalid history request kind")
        _hex(step["request"])
        if step["kind"] == "add":
            index = step["entry_index"]
            if type(index) is not int or not 0 <= index < len(entries):
                raise ValueError("Invalid history request entry index")
            add_indices.append(index)
            expected = encode_nbt_add(
                entry_model(entries[index]), existing_dates=(), today=date.max
            )
            if step["request"] != expected.hex():
                raise ValueError("History ADD bytes do not match the frozen intended entry")
        elif step["entry_index"] is not None:
            raise ValueError("Only ADD requests can refer to a history entry")
        if step["kind"] == "identity" and step["request"] not in ("22f190", "22f150", "22f101"):
            raise ValueError("Invalid history identity revalidation request")
        if step["kind"] == "erase":
            erase_count += 1
            if step["request"] != "3101a080":
                raise ValueError("Invalid history ERASE request")
        if step["kind"] == "session" and (
            len(step["request"]) != 4 or not step["request"].startswith("10")
        ):
            raise ValueError("Invalid history session request")
        if step["kind"] == "reset" and (
            len(step["request"]) != 4 or not step["request"].startswith("11")
        ):
            raise ValueError("Invalid history reset request")
    if add_indices != list(range(len(entries))):
        raise ValueError("History request plan must preserve reviewed entry order exactly once")
    if erase_count != (1 if intent["mode"] == "replace" else 0):
        raise ValueError("Append cannot erase; replacement requires exactly one erase")
    expected_steps: list[tuple[str, str, int | None]] = [
        ("identity", "22f190", None),
        ("identity", "22f150", None),
        ("identity", "22f101", None),
        ("session", "1001", None),
    ]
    if intent["mode"] == "replace":
        expected_steps.append(("erase", "3101a080", None))
    expected_steps.extend(
        ("add", encode_nbt_add(entry_model(entry), existing_dates=(), today=date.max).hex(), index)
        for index, entry in enumerate(entries)
    )
    expected_steps.append(("reset", "1101", None))
    if [(step["kind"], step["request"], step["entry_index"]) for step in steps] != expected_steps:
        raise ValueError("History journal requires the complete ordered version1 execution plan")
    if intent["mode"] == "replace":
        erase_index = next(i for i, step in enumerate(steps) if step["kind"] == "erase")
        first_add = next(i for i, step in enumerate(steps) if step["kind"] == "add")
        if erase_index > first_add:
            raise ValueError("Replacement must erase before writing its reviewed entries")
    return intent


def _step_states(record: dict[str, Any]) -> dict[int, str]:
    states: dict[int, str] = {}
    for event in record["events"]:
        if event["step"] is not None:
            states[event["step"]] = event["state"]
    return states


def validate_journal(value: object) -> dict[str, Any]:
    """Validate structure, immutable intent, events and full-record integrity."""
    _bounded_tree(value)
    if (
        not isinstance(value, dict)
        or value.keys() != {"schema_version", "intent", "intent_sha256", "events", "sha256"}
        or type(value["schema_version"]) is not int
        or value["schema_version"] != 1
    ):
        raise ValueError("Unsupported history journal schema")
    intent = _validate_intent(value["intent"])
    if value["intent_sha256"] != _digest(intent):
        raise ValueError("History journal immutable intent integrity check failed")
    events = value["events"]
    if not isinstance(events, list) or not 1 <= len(events) <= MAX_EVENTS:
        raise ValueError("History journal exceeds its event limit")
    states: dict[int, str] = {}
    terminal = False
    for index, event in enumerate(events):
        if not isinstance(event, dict) or event.keys() != {
            "sequence",
            "time",
            "state",
            "step",
            "response",
            "detail",
        }:
            raise ValueError("Invalid history journal event")
        if type(event["sequence"]) is not int or event["sequence"] != index or terminal:
            raise ValueError("Invalid history journal event sequence")
        _timestamp(event["time"])
        _hex(event["response"], empty=True)
        if not isinstance(event["detail"], str) or len(event["detail"]) > 4096:
            raise ValueError("History journal event detail exceeds its limit")
        state, step = event["state"], event["step"]
        if not isinstance(state, str):
            raise ValueError("History event state must be a string")
        if index == 0:
            if state != "prepared" or step is not None or event["response"]:
                raise ValueError("History journal must begin with prepared intent")
            continue
        if step is None:
            if state not in _FINAL_STATES:
                raise ValueError("Invalid history journal overall outcome")
            terminal = True
            if state == "rejected" and any(
                intent["requests"][i]["kind"] in ("erase", "add", "reset")
                and status in ("accepted", "sending", "uncertain")
                for i, status in states.items()
            ):
                raise ValueError(
                    "A rejected overall outcome cannot hide prior or uncertain mutations"
                )
            if state in ("response-confirmed", "cycle-required") and (
                len(states) != len(intent["requests"])
                or any(s != "accepted" for s in states.values())
            ):
                raise ValueError("History completion requires every planned application response")
        else:
            if type(step) is not int or not 0 <= step < len(intent["requests"]):
                raise ValueError("Invalid history journal step")
            if state not in _STEP_STATES:
                raise ValueError("Invalid history journal step state")
            previous = states.get(step)
            if state == "sending" and any(states.get(i) != "accepted" for i in range(step)):
                raise ValueError(
                    "History requests must execute in frozen order and stop on failure"
                )
            if state == "accepted" and not event["response"]:
                raise ValueError("History acceptance requires an application response")
            if previous is None and state not in ("sending", "unattempted"):
                raise ValueError("History outcomes require a durable sending marker first")
            if previous is not None and (
                previous != "sending" or state not in {"accepted", "rejected", "uncertain"}
            ):
                raise ValueError("History request cannot be replayed or rewritten")
            if state in ("sending", "unattempted") and event["response"]:
                raise ValueError("An uncompleted request cannot have an application reply")
            states[step] = state
    if value["sha256"] != _digest({k: v for k, v in value.items() if k != "sha256"}):
        raise ValueError("History journal full-record integrity check failed")
    return value


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("History journal contains duplicate JSON fields")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ValueError("History journal cannot contain nonfinite numbers")


def load_journal(path: Path) -> dict[str, Any]:
    """Read bounded data only; loading never resumes or authorizes an operation."""
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("History journal exceeds the 8 MiB limit")
    try:
        return validate_journal(
            json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)
        )
    except (UnicodeError, RecursionError, OverflowError, TypeError) as exc:
        raise ValueError("History journal contains malformed data") from exc


def _publish_bytes(path: Path, raw: bytes) -> None:
    if len(raw) > MAX_BYTES:
        raise ValueError("History preservation file exceeds the 8 MiB limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=".history-operation-", delete=False
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


def _publish(path: Path, record: dict[str, Any]) -> None:
    record["sha256"] = _digest({k: v for k, v in record.items() if k != "sha256"})
    validate_journal(record)
    _publish_bytes(path, _encoded(record))


def export_memory_evidence(destination: Path, report: dict[str, Any]) -> None:
    """Preserve retained interruption bytes when operation journaling failed.

    This separately labelled evidence is neither an executable operation journal
    nor a coding baseline or a recoverable copy of prior car history.
    """
    if not isinstance(report, dict):
        raise ValueError("History interruption evidence requires a report object")
    _bounded_tree(report)
    payload = {
        "schema_version": 1,
        "kind": "history-interruption-evidence",
        "created": datetime.now(UTC).isoformat(),
        "report": report,
    }
    envelope = {**payload, "sha256": _digest(payload)}
    _publish_bytes(destination, _encoded(envelope))


class HistoryJournalStore:
    """Keep local history plans/results without weakening coding backup storage."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path.home() / "BMW-Tool" / "history" / "operations"

    def prepare(
        self,
        *,
        vin: str,
        mode: str,
        target: dict[str, Any],
        encoder: dict[str, Any],
        local_before: dict[str, Any],
        intended: list[dict[str, Any]],
        requests: list[dict[str, Any]],
        draft_ids: list[str],
        environment: str = "live",
    ) -> Path:
        """Durably freeze exact local intent before any vehicle request is sent."""
        send_project = {"schema_version": 1, "vin": vin, "entries": intended}
        if any(entry_conflicts(send_project)):
            raise ValueError("History intent contains unsendable entries")
        identity = uuid.uuid4().hex
        intent = {
            "id": identity,
            "created": datetime.now(UTC).isoformat(),
            "kind": "history-operation",
            "environment": environment,
            "vin": vin,
            "mode": mode,
            "target": target,
            "encoder": encoder,
            "vehicle_history_before": None,
            "vehicle_history_before_provenance": "unavailable-not-read",
            "local_before": local_before,
            "intended": intended,
            "requests": requests,
            "draft_ids": draft_ids,
        }
        intent = json.loads(_encoded(intent))
        record = {
            "schema_version": 1,
            "intent": intent,
            "intent_sha256": _digest(intent),
            "events": [self._event(0, "prepared", None, b"", "")],
            "sha256": "",
        }
        path = self.root / f"{identity}.json"
        if path.exists():
            raise ValueError("History operation identifier already exists")
        _publish(path, record)
        load_journal(path)
        return path

    @staticmethod
    def _event(
        sequence: int, state: str, step: int | None, response: bytes, detail: str
    ) -> dict[str, Any]:
        return {
            "sequence": sequence,
            "time": datetime.now(UTC).isoformat(),
            "state": state,
            "step": step,
            "response": response.hex(),
            "detail": detail,
        }

    def record(
        self,
        path: Path,
        *,
        state: str,
        step: int | None = None,
        response: bytes = b"",
        detail: str = "",
    ) -> dict[str, Any]:
        """Publish one ordered event; persistence errors must stop subsequent writes."""
        record = load_journal(path)
        record["events"].append(self._event(len(record["events"]), state, step, response, detail))
        _publish(path, record)
        return record

    @staticmethod
    def load(path: Path) -> dict[str, Any]:
        """Load one journal for inspection, never execution or automatic recovery."""
        return load_journal(path)

    def list_records(
        self, vin: str | None = None, environment: str = "live"
    ) -> list[dict[str, Any]]:
        """Read owned journals only; imported reports never become operation authority."""
        if vin is not None and not valid_vin(vin):
            raise ValueError("Invalid journal filter vehicle identity")
        if environment not in ("live", "demo"):
            raise ValueError("Invalid journal filter environment")
        paths = []
        for path in self.root.glob("*.json"):
            paths.append(path)
            if len(paths) > 10000:
                raise ValueError("History journal listing exceeds its resource limit")
        records = []
        total_bytes = 0
        for path in sorted(paths):
            record = load_journal(path)
            total_bytes += len(_encoded(record))
            if total_bytes > MAX_LIST_BYTES:
                raise ValueError(
                    "History journals exceed the 32 MiB listing limit; explicitly export/archive older reports"
                )
            intent = record["intent"]
            if intent["environment"] == environment and (vin is None or intent["vin"] == vin):
                records.append(record)
        return records

    def known_dates(self, vin: str, environment: str = "live") -> set[date]:
        """Conservatively reserve dates of accepted or possibly sent ADD steps."""
        dates = set()
        for record in self.list_records(vin, environment):
            intent = record["intent"]
            for step, state in _step_states(record).items():
                request = intent["requests"][step]
                if request["kind"] == "add" and state in ("accepted", "sending", "uncertain"):
                    dates.add(
                        date.fromisoformat(intent["intended"][request["entry_index"]]["date"])
                    )
        return dates

    def consumed_draft_ids(self, vin: str, environment: str = "live") -> set[str]:
        """Identify drafts whose ADD may have occurred; never make them replayable."""
        identities = set()
        for record in self.list_records(vin, environment):
            intent = record["intent"]
            for step, state in _step_states(record).items():
                request = intent["requests"][step]
                if request["kind"] == "add" and state in ("accepted", "sending", "uncertain"):
                    identities.add(intent["draft_ids"][request["entry_index"]])
        return identities

    def delete_record(self, path: Path) -> None:
        """Delete one explicitly selected owned report, then sync the directory.

        Losing this local evidence also removes its date/draft accounting. UI
        callers must explain that consequence and obtain explicit confirmation.
        """
        root = self.root.resolve()
        if path.resolve().parent != root or path.suffix != ".json":
            raise ValueError("Only an owned local history journal can be deleted")
        record = load_journal(path)
        if path.name != f"{record['intent']['id']}.json":
            raise ValueError("History journal filename does not match its identity")
        path.unlink()
        directory = os.open(root, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def export_record(self, source: Path, destination: Path) -> None:
        """Export a validated local report; it contains no restorable car history."""
        _publish(destination, load_journal(source))

    def import_record(self, source: Path) -> Path:
        """Keep an imported report separately; it never enters owned operation state."""
        record = load_journal(source)
        destination = self.root / "imported" / f"{record['intent']['id']}.json"
        if destination.exists():
            if load_journal(destination)["sha256"] != record["sha256"]:
                raise ValueError("Another revision of this imported history report exists")
            return destination
        _publish(destination, record)
        return destination
