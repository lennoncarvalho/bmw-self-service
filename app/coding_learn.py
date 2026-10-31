"""Learn-by-diff coding presets (D-66, Phase 1: read-only capture and diff).

The owner captures one ECU's coding data identifiers before and after applying a
single option with another coding tool. The exact bit-level difference becomes
an owner-labelled preset bound to the ECU address, variant and F101 coding
identity it was learned on. Data comes only from the owner's captures. Applying
a preset is a later, separately verified write contract.

Capture contract: `22 F101` (coding identity, at least one CAFD identifier),
then `22 DID` for every DID in 0x3000-0x3FFF under one overall budget. Per D-65
reads are relaxed: a negative reply means the DID is absent (non-0x31 codes are
recorded). A timeout, lost connection, invalid echo or interruption marks the
capture incomplete. A complete capture rereads F101 and requires it unchanged.
"""

import hashlib
import json
import logging
import os
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from typing import Any, cast

from app.coding import decode_cafd_identifiers
from app.history_files import valid_vin
from app.protocol.contracts import FailureKind, TransportKind
from app.vehicle import did_data
from app.worker import CarWorker

logger = logging.getLogger(__name__)

SCAN_FIRST = 0x3000
SCAN_LAST = 0x3FFF
CAPTURE_BUDGET = 240.0
REQUEST_LIMIT = 30.0
# Below this remaining budget no request is sent: a reply cut off by the deadline
# would quarantine the ECU on the connection instead of ending the capture cleanly.
MIN_REQUEST = 1.0
PROGRESS_EVERY = 64
ROLES = ("before", "after")
MAX_CAPTURE_BYTES = 8 * 1024 * 1024
MAX_PRESET_BYTES = 4 * 1024 * 1024
MAX_PRESETS = 500
MAX_LABEL = 120
MAX_NOTES = 1000
CAPTURE_FIELDS = frozenset(
    {
        "schema_version",
        "kind",
        "id",
        "role",
        "vin",
        "ecu",
        "f101",
        "cafd",
        "range",
        "blocks",
        "negative",
        "absent",
        "scanned",
        "complete",
        "incomplete_reason",
        "started",
        "finished",
        "duration_s",
        "sha256",
    }
)


def _encoded(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_encoded(value)).hexdigest()


def _publish(path: Path, record: dict[str, Any], limit: int) -> None:
    """Atomically replace and fsync file and directory entry."""
    record["sha256"] = _digest({k: v for k, v in record.items() if k != "sha256"})
    raw = _encoded(record)
    if len(raw) > limit:
        raise ValueError("Coding record exceeds its size limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".coding-", delete=False) as out:
            temporary = out.name
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
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


def _read_json(path: Path, limit: int) -> object:
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("Coding record exceeds its size limit")
    return json.loads(raw)


def _hex(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return bytes.fromhex(value).hex() == value
    except ValueError:
        return False


def _did_key(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 4
        and value == value.upper()
        and _hex(value.lower())
        and SCAN_FIRST <= int(value, 16) <= SCAN_LAST
    )


def validate_capture(record: object) -> dict[str, Any]:
    """Check structure and integrity; a capture is evidence, never write permission."""
    if not isinstance(record, dict) or set(record) != CAPTURE_FIELDS:
        raise ValueError("Invalid coding capture fields")
    if record["schema_version"] != 1 or record["kind"] != "coding-capture":
        raise ValueError("Unsupported coding capture")
    if record["sha256"] != _digest({k: v for k, v in record.items() if k != "sha256"}):
        raise ValueError("Coding capture integrity check failed")
    if not valid_vin(record["vin"]) or record["role"] not in ROLES:
        raise ValueError("Invalid coding capture identity")
    ecu = record["ecu"]
    if (
        not isinstance(ecu, dict)
        or set(ecu) != {"name", "address", "variant", "address_index"}
        or type(ecu["address"]) is not int
        or not 0 <= ecu["address"] <= 0xFF
        or not all(isinstance(ecu[k], str) and ecu[k] for k in ("name", "variant"))
    ):
        raise ValueError("Invalid coding capture ECU identity")
    if not _hex(record["f101"]) or not record["f101"]:
        raise ValueError("Invalid coding capture F101 identity")
    if not isinstance(record["cafd"], list) or not record["cafd"]:
        raise ValueError("Coding capture has no coding definition identity")
    blocks, negative = record["blocks"], record["negative"]
    if not isinstance(blocks, dict) or not isinstance(negative, dict):
        raise ValueError("Invalid coding capture data")
    for key, value in blocks.items():
        if not _did_key(key) or not _hex(value) or not value:
            raise ValueError("Coding capture blocks must be canonical hexadecimal")
    for key, value in negative.items():
        if not _did_key(key) or type(value) is not int or key in blocks:
            raise ValueError("Invalid coding capture negative replies")
    if record["range"] != [f"{SCAN_FIRST:04X}", f"{SCAN_LAST:04X}"]:
        raise ValueError("Unsupported coding capture range")
    if type(record["complete"]) is not bool or not isinstance(record["incomplete_reason"], str):
        raise ValueError("Invalid coding capture completion")
    if record["complete"] and (record["incomplete_reason"] or not blocks):
        raise ValueError("Inconsistent coding capture completion")
    datetime.fromisoformat(record["started"])
    datetime.fromisoformat(record["finished"])
    return cast(dict[str, Any], record)


class CaptureStore:
    """Durable per-capture JSON files; captures are never rewritten after publication."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path.home() / "BMW-Tool" / "coding" / "captures"

    def save(self, capture: dict[str, Any]) -> Path:
        """Publish one capture with fsync; returns its path."""
        record = json.loads(_encoded(capture))
        record["sha256"] = _digest({k: v for k, v in record.items() if k != "sha256"})
        validate_capture(record)
        stamp = datetime.fromisoformat(record["started"]).strftime("%Y%m%dT%H%M%SZ")
        name = (
            f"{record['vin']}-{record['ecu']['address']:02X}-{stamp}-"
            f"{record['role']}-{record['id'][:8]}.json"
        )
        path = self.root / name
        if path.exists():
            raise ValueError("Coding capture already exists")
        _publish(path, record, MAX_CAPTURE_BYTES)
        load_capture(path)
        return path

    def latest(self, vin: str, address: int, variant: str, role: str) -> tuple[Path, dict] | None:
        """Newest complete, intact capture of one ECU identity and role; damaged files skip."""
        best: tuple[str, Path, dict] | None = None
        if not self.root.is_dir():
            return None
        for path in self.root.glob(f"{vin}-{address:02X}-*-{role}-*.json"):
            try:
                record = load_capture(path)
            except (OSError, ValueError, KeyError, TypeError):
                logger.warning("Skipping unreadable coding capture %s", path.name, exc_info=True)
                continue
            if (
                record["complete"]
                and record["vin"] == vin
                and record["role"] == role
                and record["ecu"]["address"] == address
                and record["ecu"]["variant"] == variant
                and (best is None or record["finished"] > best[0])
            ):
                best = (record["finished"], path, record)
        return (best[1], best[2]) if best else None

    def newest(self, vin: str, address: int, variant: str) -> dict[str, Any] | None:
        """Newest complete capture of either role, the ECU's last known coding version."""
        found = [self.latest(vin, address, variant, role) for role in ROLES]
        records = [item[1] for item in found if item is not None]
        return max(records, key=lambda r: str(r["finished"])) if records else None


def load_capture(path: Path) -> dict[str, Any]:
    """Read and validate one capture file."""
    try:
        return validate_capture(_read_json(path, MAX_CAPTURE_BYTES))
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("Invalid coding capture structure") from exc


def file_sha256(path: Path) -> str:
    """Digest of a published capture file's exact bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def diff_captures(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    """Return per-byte bit-mask changes between two complete captures of one ECU identity.

    Raises:
        ValueError: identities differ, either capture is incomplete, the F101
            coding identity changed, or a DID/block length differs between them.
    """
    validate_capture(before)
    validate_capture(after)
    if not before["complete"] or not after["complete"]:
        raise ValueError("Both captures must be complete")
    if before["vin"] != after["vin"]:
        raise ValueError("Captures belong to different vehicles")
    if (before["ecu"]["address"], before["ecu"]["variant"]) != (
        after["ecu"]["address"],
        after["ecu"]["variant"],
    ):
        raise ValueError("Captures belong to different ECUs or variants")
    if before["f101"] != after["f101"]:
        raise ValueError(
            "The ECU's coding version (F101) changed between captures; the difference "
            "cannot be bound to one coding version"
        )
    only = sorted(set(before["blocks"]) ^ set(after["blocks"]))
    if only:
        raise ValueError("Data identifiers present in only one capture: " + ", ".join(only))
    changes: list[dict[str, Any]] = []
    for did in sorted(before["blocks"]):
        old = bytes.fromhex(before["blocks"][did])
        new = bytes.fromhex(after["blocks"][did])
        if len(old) != len(new):
            raise ValueError(f"Data identifier {did} changed length between captures")
        for offset, (a, b) in enumerate(zip(old, new, strict=True)):
            mask = a ^ b
            if mask:
                changes.append(
                    {"did": did, "offset": offset, "mask": mask, "old": a & mask, "new": b & mask}
                )
    return changes


class CodingCaptureWorker(CarWorker):
    """Read one identified ECU's coding identity and 0x3000-0x3FFF data; read-only.

    One overall CAPTURE_BUDGET (queueing included); each request's context is
    bounded by the remaining budget. The capture is always persisted, complete
    or not, and returned as {"capture": dict, "path": str}.
    """

    def __init__(self, connection: Any, ecu: dict[str, Any], vin: str, role: str) -> None:
        super().__init__(connection)
        self.ecu = dict(ecu)
        self.vin = vin
        self.role = role
        self.store = CaptureStore()
        # Stop is honoured between DIDs: cancelling an in-flight read would end
        # the whole connection, so requests get a token that is never set.
        self._uncancelled = Event()

    def _read(self, address: int, did: int, deadline: float) -> tuple[bytes | None, str, int]:
        """Return (data, state, nrc); state is read, negative or a failure value."""
        remaining = deadline - time.monotonic()
        if remaining < MIN_REQUEST:
            return None, "budget-exhausted", 0
        if not self.connection.alive_ok:
            return None, "connection-closed", 0
        outcome = self.connection.request(
            address,
            b"\x22" + did.to_bytes(2, "big"),
            context=self.connection.context(
                min(REQUEST_LIMIT, remaining), cancelled=self._uncancelled
            ),
        )
        if outcome.failure == FailureKind.NEGATIVE:
            return None, "negative", outcome.nrc or 0
        if outcome.failure is not None:
            return None, outcome.failure.value, 0
        try:
            return did_data(outcome.payload or b"", did), "read", 0
        except ValueError:
            return None, "invalid-response", 0

    def do_work(self) -> dict[str, Any]:
        """Capture, persist and return the result; never sends anything but `22`."""
        if getattr(self.connection, "kind", None) != TransportKind.HSFZ:
            raise ValueError("Coding capture needs an HSFZ connection with known ECU addresses")
        if not valid_vin(self.vin) or self.role not in ROLES:
            raise ValueError("Coding capture needs a verified vehicle identity")
        if self.ecu.get("identified") is not True or self.ecu.get("uds") is not True:
            raise ValueError("Coding capture needs an exactly identified UDS ECU")
        address = int(str(self.ecu["addr"]), 0)
        name = str(self.ecu.get("name", f"ECU {address:02X}"))
        started_wall = datetime.now(UTC)
        started = time.monotonic()
        deadline = started + CAPTURE_BUDGET
        self.progress.emit(f"Reading coding identity of {name}...")
        identity, state, nrc = self._read(address, 0xF101, deadline)
        if identity is None:
            raise ValueError(f"Coding identity (F101) unavailable: {state} {nrc:02X}".strip())
        f101 = b"\x62\xf1\x01" + identity
        cafd = decode_cafd_identifiers(f101)
        if not cafd:
            raise ValueError("ECU reported no coding definition identity")
        blocks: dict[str, str] = {}
        negative: dict[str, int] = {}
        absent = 0
        reason = ""
        scanned = 0
        total = SCAN_LAST - SCAN_FIRST + 1
        for did in range(SCAN_FIRST, SCAN_LAST + 1):
            if self.isInterruptionRequested():
                reason = "interrupted"
                break
            data, state, nrc = self._read(address, did, deadline)
            if state == "read" and data:
                blocks[f"{did:04X}"] = data.hex()
            elif state == "read":
                negative[f"{did:04X}"] = -1  # positive echo with no data
            elif state == "negative":
                if nrc == 0x31:
                    absent += 1
                else:
                    negative[f"{did:04X}"] = nrc
            else:
                reason = f"{state} at DID {did:04X}"
                break
            scanned += 1
            if scanned % PROGRESS_EVERY == 0:
                self.progress.emit(
                    f"Reading {name}: {did:04X} ({scanned}/{total}, {len(blocks)} found)"
                )
        if not reason and not blocks:
            reason = "no coding data identifiers answered in 3000-3FFF"
        if not reason:
            reread, state, nrc = self._read(address, 0xF101, deadline)
            if reread is None:
                reason = f"coding identity reread failed: {state}"
            elif reread != identity:
                reason = "coding identity (F101) changed during capture"
        capture = {
            "schema_version": 1,
            "kind": "coding-capture",
            "id": uuid.uuid4().hex,
            "role": self.role,
            "vin": self.vin,
            "ecu": {
                "name": name,
                "address": address,
                "variant": str(self.ecu.get("variant", "")),
                "address_index": str(self.ecu.get("address_index", "")),
            },
            "f101": f101.hex(),
            "cafd": list(cafd),
            "range": [f"{SCAN_FIRST:04X}", f"{SCAN_LAST:04X}"],
            "blocks": blocks,
            "negative": negative,
            "absent": absent,
            "scanned": scanned,
            "complete": not reason,
            "incomplete_reason": reason,
            "started": started_wall.isoformat(),
            "finished": datetime.now(UTC).isoformat(),
            "duration_s": round(time.monotonic() - started, 3),
            "sha256": "",
        }
        logger.info(
            "Coding capture ecu=%02X role=%s complete=%s blocks=%d scanned=%d %.1fs %s",
            address,
            self.role,
            capture["complete"],
            len(blocks),
            scanned,
            capture["duration_s"],
            reason,
        )
        path = self.store.save(capture)
        return {"capture": load_capture(path), "path": str(path)}


class PresetStore:
    """Versioned owner-labelled presets learned from the owner's own captures."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path.home() / "BMW-Tool" / "coding" / "presets.json"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema_version": 1, "kind": "coding-presets", "presets": {}, "sha256": ""}
        record = _read_json(self.path, MAX_PRESET_BYTES)
        if (
            not isinstance(record, dict)
            or set(record) != {"schema_version", "kind", "presets", "sha256"}
            or record["schema_version"] != 1
            or record["kind"] != "coding-presets"
            or not isinstance(record["presets"], dict)
            or record["sha256"] != _digest({k: v for k, v in record.items() if k != "sha256"})
        ):
            raise ValueError("Preset database is damaged or unsupported; it was not modified")
        return record

    def presets(self, vin: str | None = None) -> list[dict[str, Any]]:
        """Presets (optionally learned on one VIN), oldest first."""
        presets = list(self._load()["presets"].values())
        if vin is not None:
            presets = [p for p in presets if p.get("vin") == vin]
        return sorted(presets, key=lambda p: str(p.get("created", "")))

    def add(
        self,
        label: str,
        before_path: Path,
        after_path: Path,
        notes: str = "",
    ) -> dict[str, Any]:
        """Re-verify both capture files, diff them and publish one preset."""
        label, notes = label.strip(), notes.strip()
        if not label or len(label) > MAX_LABEL or len(notes) > MAX_NOTES:
            raise ValueError(f"Label must be 1-{MAX_LABEL} characters, notes ≤ {MAX_NOTES}")
        before, after = load_capture(before_path), load_capture(after_path)
        if before["role"] != "before" or after["role"] != "after":
            raise ValueError("Preset needs one before and one after capture")
        changes = diff_captures(before, after)
        if not changes:
            raise ValueError("The captures are identical; there is no change to save")
        record = self._load()
        if any(p["after"]["path"] == str(after_path) for p in record["presets"].values()):
            raise ValueError("A preset from this after-capture is already saved")
        if len(record["presets"]) >= MAX_PRESETS:
            raise ValueError("Preset database is full")
        identity = uuid.uuid4().hex
        preset = {
            "id": identity,
            "label": label,
            "notes": notes,
            "source": "learned-by-diff",
            "created": datetime.now(UTC).isoformat(),
            "vin": before["vin"],
            "ecu": {k: before["ecu"][k] for k in ("name", "address", "variant")},
            "cafd": list(before["cafd"]),
            "f101": before["f101"],
            "changes": changes,
            "before": {"path": str(before_path), "sha256": file_sha256(before_path)},
            "after": {"path": str(after_path), "sha256": file_sha256(after_path)},
        }
        record["presets"][identity] = preset
        _publish(self.path, record, MAX_PRESET_BYTES)
        return preset

    def delete(self, identity: str) -> None:
        """Remove one preset; capture files are retained."""
        record = self._load()
        if record["presets"].pop(identity, None) is None:
            raise ValueError("Preset not found")
        _publish(self.path, record, MAX_PRESET_BYTES)


def applicability(preset: dict[str, Any], capture: dict[str, Any] | None) -> str:
    """Describe whether a preset's exact coding identity matches a capture of the ECU."""
    if capture is None:
        return "Coding version of this ECU not captured yet"
    if (
        capture["vin"] != preset["vin"]
        or capture["ecu"]["address"] != preset["ecu"]["address"]
        or capture["ecu"]["variant"] != preset["ecu"]["variant"]
    ):
        return "Learned on another ECU"
    if capture["f101"] == preset["f101"]:
        return "Applicable to this ECU (coding version matches the latest capture)"
    return "Learned on another coding version"


def describe_change(change: dict[str, Any]) -> str:
    """One readable line: DID, byte offset, mask and old -> new masked bits."""
    mask = int(change["mask"])
    return (
        f"DID {change['did']} byte {change['offset']}: mask {mask:08b} "
        f"{int(change['old']):08b} -> {int(change['new']):08b} "
        f"(0x{int(change['old']):02X} -> 0x{int(change['new']):02X})"
    )
