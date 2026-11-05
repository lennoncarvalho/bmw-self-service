"""Execute embedded source coding guards and retain separate observed evidence."""

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.coding_db import CodingDatabase
from app.history_files import valid_vin
from app.operation_store import OperationStore, export_interruption_evidence
from app.uds import decode_dtc_records

_MAX_GUARD_BYTES = 65536
_NOTICE = (
    "Coding is blocked because this vehicle has a recorded critical ECU condition. "
    "Clearing fault memory does not remove the retained coding guard. "
    "Inspect the diagnostic report and session log."
)


def _encoded(value: Any) -> bytes:
    """Encode canonical JSON for retained guard integrity checks."""
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


class CodingGuardBlocked(ValueError):
    """A source guard refuses coding, independently of ordinary DTC clearing."""

    user_message = _NOTICE


def contracts(database: CodingDatabase, address: int) -> list[dict]:
    """Select source-defined guard branches without an application variant list."""
    selection = database.read_document("selection")
    if (
        not isinstance(selection, dict)
        or not isinstance(selection.get("coding_guards"), list)
        or not selection["coding_guards"]
    ):
        raise ValueError("Embedded coding guard contracts are missing")
    result = []
    for guard in selection["coding_guards"]:
        if (
            not isinstance(guard, dict)
            or not isinstance(guard.get("id"), str)
            or type(guard.get("address")) is not int
            or not 0 <= guard["address"] <= 255
            or guard.get("sticky") is not True
            or not isinstance(guard.get("critical_codes"), list)
        ):
            raise ValueError("Embedded coding guard contract is invalid")
        payload = bytes.fromhex(guard["request"])
        if len(payload) != 3 or payload[:2] != b"\x19\x02":
            raise ValueError("Coding guard needs a recovered read-only fault request")
        codes = guard["critical_codes"]
        if not codes or any(
            not isinstance(code, str) or len(code) != 6 or not 0 <= int(code, 16) <= 0xFFFFFF
            for code in codes
        ):
            raise ValueError("Coding guard fault identifiers are invalid")
        if guard["address"] == address:
            result.append(dict(guard))
    return result


def _path(store: OperationStore, vin: str, guard: dict) -> Path:
    """Derive a per-vehicle guard path without exposing the VIN in its name."""
    if not valid_vin(vin):
        raise ValueError("Coding guard requires verified vehicle identity")
    identity = hashlib.sha256((vin + "\0" + guard["id"]).encode()).hexdigest()
    return store.root.parent / "coding-guards" / (identity + ".json")


def _load(path: Path, vin: str, guard: dict, *, required: bool) -> dict | None:
    """Load bounded guard evidence and verify its envelope and source identity."""
    if not path.exists():
        if required:
            raise ValueError("The prepared coding guard evidence is missing")
        return None
    with path.open("rb") as stream:
        raw = stream.read(_MAX_GUARD_BYTES + 1)
    if len(raw) > _MAX_GUARD_BYTES:
        raise ValueError("Coding guard evidence exceeds its supported bound")
    record = json.loads(raw)
    if (
        not isinstance(record, dict)
        or set(record) != {"schema", "kind", "report", "sha256"}
        or record["schema"] != 1
        or record["kind"] != "coding-interruption-evidence"
    ):
        raise ValueError("Coding guard evidence has an invalid envelope")
    body = {key: value for key, value in record.items() if key != "sha256"}
    if record["sha256"] != hashlib.sha256(_encoded(body)).hexdigest():
        raise ValueError("Coding guard evidence failed integrity validation")
    report = record["report"]
    if (
        not isinstance(report, dict)
        or report.get("kind") != "coding-critical-observation"
        or report.get("vin") != vin
        or report.get("guard_id") != guard["id"]
        or report.get("address") != guard["address"]
        or report.get("request") != guard["request"]
        or type(report.get("critical")) is not bool
        or report.get("sticky") is not report["critical"]
    ):
        raise ValueError("Coding guard evidence has an invalid vehicle/contract identity")
    datetime.fromisoformat(report["observed"])
    response = bytes.fromhex(report["response"])
    found = {code for code, _status in decode_dtc_records(response)}
    critical = bool(found & {int(code, 16) for code in guard["critical_codes"]})
    if report["critical"] != critical:
        raise ValueError("Coding guard evidence differs from its observed fault bytes")
    return record


def observe(
    store: OperationStore,
    vin: str,
    guard: dict,
    read: Callable[[bytes], bytes],
    *,
    expected: dict | None = None,
) -> dict:
    """Require a fresh checked read; a retained critical fact is never auto-cleared."""
    path = _path(store, vin, guard)
    previous = _load(path, vin, guard, required=expected is not None)
    if previous is not None and previous["report"]["sticky"]:
        raise CodingGuardBlocked(_NOTICE)
    if expected is not None and (previous is None or previous["sha256"] != expected["sha256"]):
        raise ValueError("Coding guard evidence changed after confirmation")
    response = bytes(read(bytes.fromhex(guard["request"])))
    codes = {code for code, _status in decode_dtc_records(response)}
    critical = bool(codes & {int(code, 16) for code in guard["critical_codes"]})
    report = {
        "kind": "coding-critical-observation",
        "vin": vin,
        "guard_id": guard["id"],
        "address": guard["address"],
        "request": guard["request"],
        "response": response.hex(),
        "critical": critical,
        "sticky": critical,
        "observed": datetime.now(UTC).isoformat(),
        "contract_sha256": hashlib.sha256(_encoded(guard)).hexdigest(),
    }
    if (
        len(
            _encoded(
                {
                    "schema": 1,
                    "kind": "coding-interruption-evidence",
                    "report": report,
                    "sha256": "0" * 64,
                }
            )
        )
        > _MAX_GUARD_BYTES
    ):
        raise ValueError("Coding guard observation exceeds the evidence bound")
    export_interruption_evidence(path, report)
    record = _load(path, vin, guard, required=True)
    if record is None:
        raise ValueError("Coding guard evidence could not be retained")
    if critical:
        raise CodingGuardBlocked(_NOTICE)
    return {
        "guard_id": guard["id"],
        "address": guard["address"],
        "path": str(path),
        "sha256": record["sha256"],
        "contract_sha256": report["contract_sha256"],
        "response": response.hex(),
    }
