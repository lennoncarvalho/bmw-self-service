"""Durable, portable JSON records for vehicle backups and mutation outcomes.

The immutable original/intended payload is hashed separately from observations.
This is accidental-corruption detection, not a signature or encryption scheme.
No imported record is permission to send anything to a vehicle.
"""

import hashlib
import json
import os
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = 1
MAX_BYTES = 32 * 1024 * 1024
STATES = frozenset(
    {
        "prepared",
        "writing",
        "response-confirmed",
        "cycle-required",
        "verified",
        "mismatch",
        "partial",
        "uncertain",
        "recovered",
    }
)


def _encoded(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_encoded(value)).hexdigest()


def _validate(record: object) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != SCHEMA:
        raise ValueError("Unsupported backup schema")
    if set(record) != {"schema", "original", "original_sha256", "events", "sha256"}:
        raise ValueError("Invalid backup fields")
    original = record["original"]
    if not isinstance(original, dict) or set(original) != {
        "id",
        "created",
        "kind",
        "mode",
        "vin",
        "targets",
    }:
        raise ValueError("Invalid backup identity")
    if original["kind"] not in ("coding", "history") or original["mode"] not in ("live", "demo"):
        raise ValueError("Invalid backup kind")
    if not isinstance(original["id"], str) or uuid.UUID(original["id"]).hex != original["id"]:
        raise ValueError("Invalid backup identifier")
    datetime.fromisoformat(original["created"])
    vin = original["vin"]
    if (
        not isinstance(vin, str)
        or len(vin) != 17
        or not vin.isascii()
        or not vin.isalnum()
        or vin == "0" * 17
    ):
        raise ValueError("Invalid backup vehicle identity")
    targets = original["targets"]
    if not isinstance(targets, list) or not targets:
        raise ValueError("Backup must preserve at least one complete target")
    addresses = set()
    for target in targets:
        if not isinstance(target, dict) or set(target) != {
            "address",
            "variant",
            "software",
            "definition_sha256",
            "baseline",
            "intended",
        }:
            raise ValueError("Invalid backup target")
        address = target["address"]
        if type(address) is not int or not 0 <= address <= 0xFFFF or address in addresses:
            raise ValueError("Invalid or duplicate backup target address")
        addresses.add(address)
        for field in ("variant", "software", "definition_sha256"):
            if not isinstance(target[field], str) or not target[field]:
                raise ValueError("Backup requires exact ECU and definition identity")
        digest = target["definition_sha256"]
        if len(digest) != 64 or len(bytes.fromhex(digest)) != 32:
            raise ValueError("Invalid definition integrity value")
        for field in ("baseline", "intended"):
            blocks = target[field]
            if not isinstance(blocks, dict) or not blocks:
                raise ValueError("Backup target data is incomplete")
            for key, value in blocks.items():
                if (
                    not isinstance(key, str)
                    or not key
                    or not isinstance(value, str)
                    or not value
                    or value != bytes.fromhex(value).hex()
                ):
                    raise ValueError("Backup target bytes must be canonical hexadecimal")
        if set(target["baseline"]) != set(target["intended"]):
            raise ValueError("Original and intended target block sets differ")
    if record["original_sha256"] != _digest(original):
        raise ValueError("Original backup integrity check failed")
    events = record["events"]
    if not isinstance(events, list) or not events:
        raise ValueError("Backup has no operation state")
    for index, event in enumerate(events):
        if not isinstance(event, dict) or set(event) != {
            "sequence",
            "time",
            "state",
            "observed",
            "responses",
            "instructions",
        }:
            raise ValueError("Invalid backup event")
        if event["sequence"] != index or event["state"] not in STATES:
            raise ValueError("Invalid backup event sequence or state")
        datetime.fromisoformat(event["time"])
        if (
            not isinstance(event["observed"], dict)
            or not isinstance(event["responses"], list)
            or not isinstance(event["instructions"], str)
        ):
            raise ValueError("Invalid operation observations")
    if record["sha256"] != _digest(
        {key: value for key, value in record.items() if key != "sha256"}
    ):
        raise ValueError("Backup integrity check failed")
    return record


def load_record(path: Path) -> dict[str, Any]:
    """Read and validate a standalone record without following embedded paths."""
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Backup exceeds the supported size")
    try:
        return _validate(json.loads(raw))
    except (KeyError, TypeError, OverflowError) as exc:
        raise ValueError("Invalid backup structure") from exc


def _publish(path: Path, record: dict[str, Any]) -> None:
    record["sha256"] = _digest({key: value for key, value in record.items() if key != "sha256"})
    _validate(record)
    raw = _encoded(record)
    if len(raw) > MAX_BYTES:
        raise ValueError("Backup exceeds the supported size")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=".backup-", delete=False
        ) as stream:
            temporary = stream.name
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
        # Sync the directory entry too: durable baseline publication must survive
        # power loss before any later vehicle mutation, not merely be atomic.
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


class OperationStore:
    """Retain every original and outcome until the owner explicitly deletes it."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path.home() / "BMW-Tool" / "backups" / "operations"

    def prepare(self, *, kind: str, mode: str, vin: str, targets: list[dict[str, Any]]) -> Path:
        """Publish and sync complete baseline/intent before any vehicle send."""
        identity = uuid.uuid4().hex
        original = {
            "id": identity,
            "created": datetime.now(UTC).isoformat(),
            "kind": kind,
            "mode": mode,
            "vin": vin,
            "targets": targets,
        }
        record = {
            "schema": SCHEMA,
            "original": original,
            "original_sha256": _digest(original),
            "events": [self._event(0, "prepared", {}, [], "")],
            "sha256": "",
        }
        path = self.root / f"{identity}.json"
        _publish(path, record)
        load_record(path)
        return path

    @staticmethod
    def _event(
        sequence: int, state: str, observed: dict, responses: list, instructions: str
    ) -> dict:
        return {
            "sequence": sequence,
            "time": datetime.now(UTC).isoformat(),
            "state": state,
            "observed": observed,
            "responses": responses,
            "instructions": instructions,
        }

    def record(
        self,
        path: Path,
        *,
        state: str,
        observed: dict | None = None,
        responses: list | None = None,
        instructions: str = "",
    ) -> None:
        """Append state with original/intent integrity preserved; never overwrite baseline."""
        record = load_record(path)
        record["events"].append(
            self._event(len(record["events"]), state, observed or {}, responses or [], instructions)
        )
        _publish(path, record)

    def import_record(self, source: Path) -> Path:
        """Validate and copy a portable backup; importing never restores a vehicle."""
        record = load_record(source)
        destination = self.root / f"{record['original']['id']}.json"
        if destination.exists():
            # Both complete revision digests have already been validated,
            # including events; comparing only the original would lose updates.
            if load_record(destination)["sha256"] != record["sha256"]:
                raise ValueError("A different revision of this backup already exists")
            return destination
        _publish(destination, record)
        return destination

    def export_record(self, source: Path, destination: Path) -> None:
        """Publish a standalone validated JSON copy to the owner-selected location."""
        _publish(destination, load_record(source))
