"""Condition Based Service read and reset (B-CBS-R / B-CBS-W, D-58).

Contract: docs/evidence/task-b-cbs-contract.md. The CBS version and owning
address are constants of the exactly identified ECU definition; an item belongs
to the ECU whose own `22 10 01` record contains it. There is no default owner.
Reset sends the shared default `2E 10 01` record once; completion is the exact
`6E 10 01` reply, and observation is a later re-read. CBS counters are distinct
from headunit service history and are never rolled back or replayed.
"""

import contextlib
import hashlib
import json
import os
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from app.history_files import valid_vin
from app.protocol.contracts import FailureKind, OperationContext, ProtocolFailure, TransportKind
from app.resources import resource_path
from app.vehicle import DiagnosticCatalog, did_data
from app.worker import CarWorker

RECORD = 12
MAX_RECORD_BYTES = 1024 * 1024
# BimmerLink waits this long after an accepted reset before re-reading (j6.g0.i.a.b).
SETTLE_SECONDS = 5.0
RESET_STATES = frozenset({"accepted", "rejected", "uncertain", "invalid", "changed", "failed"})
FINAL_STATES = frozenset({"verified", "response-confirmed", "rejected", "uncertain", "not-started"})
# v6 CBS_RESET_DETAIL_LESEN reasons (KOMBRDCT TAB_RUECK_GRUND, see the contract).
DETAIL_REASONS = {
    0x00: "no reason recorded",
    0x01: "invalid odometer",
    0x02: "invalid on-board date",
    0x03: "invalid coding",
    0x04: "ECU not initialised",
    0x05: "vehicle moving",
    0x06: "reset not allowed for this item type",
    0x07: "substitute value active",
    0x08: "vehicle in parked/residing state",
}
INSTRUCTIONS = (
    "A CBS reset cannot be undone by this app. If the outcome is uncertain, reconnect "
    "and read service status before any new reset."
)


def cbs_definitions() -> dict[str, Any]:
    """Load the embedded per-definition CBS version/owner/reset policy."""
    path = resource_path("coding_data/cbs_definitions.json")
    with path.open("rb") as stream:
        raw = stream.read(262145)
    if len(raw) > 262144:
        raise ValueError("CBS definitions exceed their supported size")
    data = json.loads(raw)
    if data.get("schema") != 1 or not isinstance(data.get("definitions"), dict):
        raise ValueError("Unsupported CBS definition format")
    return cast(dict[str, Any], data)


def _flag(value: int, invalid: dict[int, str]) -> str | None:
    return invalid.get(value)


def decode_record(record: bytes, version: str) -> dict[str, Any]:
    """Decode one 12-byte CBS record by its PRG version; raw bytes are always kept."""
    if len(record) != RECORD:
        raise ValueError("CBS record has an unsupported length")
    v63 = version == "6.3"
    remaining = int.from_bytes(record[1:3], "big", signed=True)
    unit = record[3] & 0x0F
    item: dict[str, Any] = {
        "item": record[0],
        "raw": record.hex(),
        "status": record[3] >> 4,
        "remaining": None,
        "unit": None,
        "count": record[4] if v63 else record[4] & 0x1F,
        "availability": None,
        "due_month": None,
        "due_year": None,
        "due_day": None,
        "forecast_km": None,
        "forecast_months": None,
        "notes": [],
    }
    sentinel = ({0x7FFF: "no information", -0x8000: "not relevant"} if version != "5" else {}).get(
        remaining
    )
    if sentinel:
        item["notes"].append(f"Remaining: {sentinel}")
    elif unit == 1:
        item.update(remaining=remaining * 10, unit="km")
    elif unit == 0 and not v63:
        item.update(remaining=remaining, unit="%")
    elif unit == 2 and not v63:
        item.update(remaining=remaining, unit="days")
    else:
        item["notes"].append("Remaining value has no valid unit")
    if (not v63 and item["count"] == 0x1F) or (v63 and item["count"] >= 0xFA):
        item["count"] = None
        item["notes"].append("Service count not available")
    availability = record[5]
    special = {0xFD: "no information", 0xFE: "new/uninitialised ECU", 0xFF: "invalid"}
    if availability in special:
        item["notes"].append(f"Availability: {special[availability]}")
    elif availability <= 100:
        item["availability"] = availability
    else:
        item["notes"].append("Availability outside 0-100 %")
    if record[6] != 0xFF:
        item["forecast_km"] = record[6] * 1000
    month = record[7] & 0x0F
    if 1 <= month <= 12:
        item["due_month"] = month
    year = record[8] if v63 else record[8] & 0x3F
    if (v63 and 0 < year < 0xFA) or (not v63 and 0 < year < 0x3F):
        item["due_year"] = 2000 + year
    if v63 and 0 < (record[10] & 0x3F) < 0x1F:
        item["due_day"] = record[10] & 0x3F
    if record[9] not in (0, 0xFF):
        item["forecast_months"] = record[9]
    return item


def decode_cbs_response(response: bytes, version: str) -> list[dict[str, Any]]:
    """Require the exact `62 10 01` echo and a whole number of 12-byte records."""
    data = did_data(response, 0x1001)
    if len(data) % RECORD:
        raise ValueError("CBS response is not a whole number of records")
    return [decode_record(data[i : i + RECORD], version) for i in range(0, len(data), RECORD)]


def reset_request(item: int) -> bytes:
    """Default record: availability 100, count +1 (0x1F), all other fields unchanged."""
    if not 0 <= item <= 0xFF:
        raise ValueError("Invalid CBS item")
    return bytes.fromhex("2E100101") + bytes((item,)) + bytes.fromhex("641F80000FFF0F3FFF00")


def cbs_targets(ecus: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return exactly identified ECUs whose definition has a recovered CBS reader."""
    definitions = cbs_definitions()["definitions"]
    targets = []
    for row in ecus:
        definition = definitions.get(str(row.get("name")))
        if row.get("identified") is not True or definition is None:
            continue
        if int(str(row.get("addr")), 16) != definition["address"]:
            continue
        targets.append({**definition, "name": row["name"], "index": row["address_index"]})
    return targets


def read_cbs(connection: Any, ecus: list[dict[str, Any]]) -> dict[str, Any]:
    """Read every applicable owner once; per-owner failures stay explicit."""
    data = cbs_definitions()
    labels: dict[str, str] = data["items"]
    blocked_items = set(data["not_resettable"])
    owners: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    deadline = time.monotonic() + 30.0
    for target in cbs_targets(ecus):
        owner = {k: target[k] for k in ("name", "address", "version", "index", "reset")}
        remaining = deadline - time.monotonic()
        if not connection.alive_ok or remaining <= 0:
            reason = "connection-closed" if not connection.alive_ok else "budget-exhausted"
            owners.append({**owner, "state": f"not-attempted-{reason}"})
            continue
        response = b""
        try:
            response = connection.send_uds(
                target["address"], b"\x22\x10\x01", context=connection.context(remaining)
            )
            records = decode_cbs_response(response, target["version"])
        except (ValueError, TimeoutError, ConnectionError) as exc:
            # One owner's failure never hides the others; a lost stream stops the rest.
            state = "timeout" if isinstance(exc, TimeoutError) else "unavailable"
            owners.append({**owner, "state": state, "response": response.hex()})
            continue
        owners.append({**owner, "state": "read", "response": response.hex()})
        for record in records:
            key = f"{record['item']:02X}"
            items.append(
                {
                    **record,
                    "label": labels.get(key, f"CBS item 0x{key}"),
                    "owner": owner,
                    "resettable": owner["reset"] == "default" and key not in blocked_items,
                }
            )
    seen: dict[int, int] = {}
    for record in items:
        seen[record["item"]] = seen.get(record["item"], 0) + 1
    complete = all(owner["state"] == "read" for owner in owners)
    for record in items:
        if seen[record["item"]] > 1:
            # No source rule picks a winner between owners; never guess one.
            record["resettable"] = False
            record["notes"].append("Reported by more than one ECU; reset blocked")
        elif not complete and record["resettable"]:
            # An unread owner could also hold this item; ownership is not established.
            record["resettable"] = False
            record["notes"].append("Not every CBS owner could be read; reset blocked")
    return {"owners": owners, "items": items, "observed_clock": time.monotonic()}


class CbsReadWorker(CarWorker):
    """Read service status from every applicable identified owner."""

    def __init__(self, connection: Any, ecus: list[dict[str, Any]]) -> None:
        super().__init__(connection)
        self.ecus = [dict(row) for row in ecus]

    def do_work(self) -> dict[str, Any]:
        """Read-only `22 10 01` per owner; allowed in a read-only session."""
        if getattr(self.connection, "kind", None) != TransportKind.HSFZ:
            raise ValueError("CBS needs a recovered logical-address mapping on this transport")
        return read_cbs(self.connection, self.ecus)


def demo_cbs(data: dict[str, Any]) -> dict[str, Any]:
    """Decode DEMO snapshot records with the live decoder; never resettable or live."""
    labels: dict[str, str] = cbs_definitions()["items"]
    owners, items = [], []
    for row in data.get("cbs", []):
        owner = {
            "name": row["name"],
            "address": int(row["address"], 16),
            "version": row["version"],
            "index": "DEMO",
            "reset": "demo",
        }
        owners.append({**owner, "state": "DEMO"})
        for record in decode_cbs_response(bytes.fromhex(row["response"]), row["version"]):
            key = f"{record['item']:02X}"
            label = labels.get(key, f"CBS item 0x{key}")
            items.append({**record, "label": label, "owner": owner, "resettable": False})
    return {"owners": owners, "items": items, "observed_clock": time.monotonic()}


# ── Durable intent/results journal ─────────────────────────────────────────


def _encoded(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_encoded(value)).hexdigest()


def _publish(path: Path, record: dict[str, Any]) -> None:
    """Atomically replace and fsync, so intent exists before any request is sent."""
    record["sha256"] = _digest({k: v for k, v in record.items() if k != "sha256"})
    raw = _encoded(record)
    if len(raw) > MAX_RECORD_BYTES:
        raise ValueError("CBS operation record exceeds its size limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".cbs-", delete=False) as out:
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


def load_record(path: Path) -> dict[str, Any]:
    """Load and integrity-check one record; it never authorizes a vehicle request."""
    with path.open("rb") as stream:
        raw = stream.read(MAX_RECORD_BYTES + 1)
    if len(raw) > MAX_RECORD_BYTES:
        raise ValueError("CBS operation record exceeds its size limit")
    record = json.loads(raw)
    if (
        not isinstance(record, dict)
        or record.get("schema_version") != 1
        or record.get("kind") != "cbs-reset"
        or set(record) != {"schema_version", "kind", "intent", "intent_sha256", "events", "sha256"}
        or _digest(record["intent"]) != record["intent_sha256"]
        or _digest({k: v for k, v in record.items() if k != "sha256"}) != record["sha256"]
        or not isinstance(record["events"], list)
    ):
        raise ValueError("Invalid CBS operation record")
    return cast(dict[str, Any], record)


class CbsJournalStore:
    """Separate durable CBS intent/results; not a coding backup or restorable state."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path.home() / "BMW-Tool" / "cbs" / "operations"

    def prepare(self, intent: dict[str, Any]) -> Path:
        """Freeze exact intent and the observed before-record prior to sending."""
        intent = json.loads(_encoded(intent))
        record = {
            "schema_version": 1,
            "kind": "cbs-reset",
            "intent": intent,
            "intent_sha256": _digest(intent),
            "events": [],
            "sha256": "",
        }
        path = self.root / f"{intent['id']}.json"
        if path.exists():
            raise ValueError("CBS operation identifier already exists")
        self._append(record, "prepared", None, b"", b"", "")
        _publish(path, record)
        load_record(path)
        return path

    @staticmethod
    def _append(
        record: dict[str, Any],
        state: str,
        step: str | None,
        request: bytes,
        response: bytes,
        detail: str,
    ) -> None:
        record["events"].append(
            {
                "sequence": len(record["events"]),
                "time": datetime.now(UTC).isoformat(),
                "state": state,
                "step": step,
                "request": request.hex(),
                "response": response.hex(),
                "detail": detail,
            }
        )

    def record(
        self,
        path: Path,
        state: str,
        step: str | None = None,
        request: bytes = b"",
        response: bytes = b"",
        detail: str = "",
    ) -> None:
        """Publish one ordered event; a failure stops any further vehicle request."""
        record = load_record(path)
        self._append(record, state, step, request, response, detail)
        _publish(path, record)


# ── Reset ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CbsResetPlan:
    """Frozen confirmation: exact owner identity, item and observed before-record."""

    vin: str
    owner: dict[str, Any]
    item: int
    label: str
    before_raw: str

    def intent(self) -> dict[str, Any]:
        """Return the durable intent stored before any send."""
        return {
            "id": uuid.uuid4().hex,
            "created": datetime.now(UTC).isoformat(),
            "environment": "live",
            "vin": self.vin,
            "owner": dict(self.owner),
            "item": {"id": f"{self.item:02X}", "label": self.label},
            "before_raw": self.before_raw,
            "before_provenance": "read-in-this-connection",
            "request": reset_request(self.item).hex(),
            "completion": "exact 6E1001, then re-read after settle",
        }


def plan_reset(vin: str, item: dict[str, Any]) -> CbsResetPlan:
    """Freeze a reset only for a resettable item read from its owner in this session."""
    if not valid_vin(vin):
        raise PermissionError("A verified vehicle identity is required before a CBS reset")
    if not item.get("resettable"):
        raise PermissionError("This CBS item has no source-supported reset")
    owner = item["owner"]
    if owner.get("reset") != "default" or owner.get("version") not in ("5", "6"):
        raise PermissionError("This CBS owner has no source-supported reset")
    return CbsResetPlan(vin, dict(owner), int(item["item"]), str(item["label"]), str(item["raw"]))


class CbsResetWorker(CarWorker):
    """Reset one confirmed item exactly once and report checked, honest outcomes."""

    def __init__(
        self,
        connection: Any,
        plan: CbsResetPlan,
        store: CbsJournalStore,
        *,
        power_acknowledged: bool = False,
    ) -> None:
        super().__init__(connection)
        self.plan, self.store = plan, store
        self.power_acknowledged = power_acknowledged
        self._executed = False
        self.report: dict[str, Any] = {
            "path": "",
            "state": "not-started",
            "events": [],
            "after": None,
            "detail": "",
            "persistence_failed": False,
            "instructions": INSTRUCTIONS,
        }

    def do_work(self) -> dict[str, Any]:
        """Persist intent, then run identity/before/reset/settle/re-read on the owner."""
        if self._executed:
            raise PermissionError("A CBS reset cannot be replayed")
        self._executed = True
        connection, plan = self.connection, self.plan
        if (
            not self.power_acknowledged
            or not valid_vin(plan.vin)
            or getattr(connection, "power_sufficient", None) is False
            or connection.read_only
            or connection.kind != TransportKind.HSFZ
            or connection.verified_vin != plan.vin
            or not connection.alive_ok
        ):
            raise PermissionError("CBS reset requires power acknowledgement and the same session")
        owner = plan.owner
        request = reset_request(plan.item)
        path = self.store.prepare(plan.intent())
        self.report["path"] = str(path)
        catalog = DiagnosticCatalog()
        state = {"sent": False, "accepted": False, "step": ""}

        def record(
            event: str, step: str | None, sent: bytes = b"", reply: bytes = b"", detail: str = ""
        ) -> None:
            self.report["events"].append(
                {"state": event, "step": step, "request": sent.hex(), "response": reply.hex()}
            )
            try:
                self.store.record(path, event, step, sent, reply, detail)
            except (OSError, ValueError):
                self.report["persistence_failed"] = True
                raise

        def exchange(services: Any, ctx: OperationContext, step: str, payload: bytes) -> bytes:
            state["step"] = step
            # specific_send assigns a new request ID only when bytes are transmitted.
            request_id = ctx.request_id
            try:
                return bytes(services.invoke(payload, ctx))
            except ProtocolFailure as exc:
                if exc.kind != FailureKind.NEGATIVE or exc.reconnect:
                    raise
                return bytes(exc.raw)
            finally:
                if step == "reset":
                    state["sent"] = ctx.request_id != request_id

        def find(response: bytes) -> dict[str, Any] | None:
            records = decode_cbs_response(response, owner["version"])
            matches = [rec for rec in records if rec["item"] == plan.item]
            return matches[0] if len(matches) == 1 else None

        def execute(services: Any, ctx: OperationContext) -> bytes:
            identity = exchange(services, ctx, "identity", b"\x22\xf1\x50")
            try:
                match = catalog.identify(owner["address"], identity)
            except ValueError:
                match = {}
            if match.get("address_index") != owner["index"] or match.get("name") != owner["name"]:
                record(
                    "changed", "identity", b"\x22\xf1\x50", identity, "Owner ECU identity changed"
                )
                return b""
            before = exchange(services, ctx, "before", b"\x22\x10\x01")
            try:
                current = find(before)
            except ValueError:
                current = None
            if current is None or current["raw"] != plan.before_raw:
                record(
                    "changed",
                    "before",
                    b"\x22\x10\x01",
                    before,
                    "CBS state could not be read or changed since it was shown",
                )
                return b""
            record("accepted", "before", b"\x22\x10\x01", before)
            record("sending", "reset", request)
            reply = exchange(services, ctx, "reset", request)
            if reply != b"\x6e\x10\x01":
                rejected = reply[:2] == b"\x7f\x2e" and len(reply) == 3
                record(
                    "rejected" if rejected else "uncertain",
                    "reset",
                    request,
                    reply,
                    "ECU rejected the reset" if rejected else "Unexpected reset reply",
                )
                return b""
            state["accepted"] = True
            record("accepted", "reset", request, reply)
            ctx.cancelled.wait(min(SETTLE_SECONDS, max(0.0, ctx.remaining() - 5.0)))
            after = exchange(services, ctx, "after", b"\x22\x10\x01")
            self.report["after"] = after.hex()
            record("read", "after", b"\x22\x10\x01", after)
            if owner["version"] == "6":
                detail = exchange(services, ctx, "detail", b"\x22\x10\x02")
                self.report["reset_detail"] = detail.hex()
                record("read", "detail", b"\x22\x10\x02", detail)
            return b""

        failure = ""
        try:
            connection.run_operation(owner["address"], execute, context=connection.context(30.0))
        except Exception as exc:
            failure = str(exc) or type(exc).__name__
            if self.report["persistence_failed"]:
                # Journal loss after intent: stop the connection rather than continue blind.
                connection.request_close()
            elif state["sent"] and not state["accepted"]:
                with contextlib.suppress(OSError, ValueError):
                    record("uncertain", "reset", request, detail=failure)
        self.report["state"], self.report["detail"] = self._outcome(state, failure)
        if not self.report["persistence_failed"]:
            try:
                self.store.record(path, self.report["state"], None, detail=self.report["detail"])
            except (OSError, ValueError):
                self.report["persistence_failed"] = True
        return self.report

    def _outcome(self, state: dict[str, Any], failure: str) -> tuple[str, str]:
        events = {(e["step"], e["state"]) for e in self.report["events"]}
        if ("reset", "rejected") in events:
            return "rejected", "The ECU rejected the reset request"
        if not state["sent"]:
            if ("identity", "changed") in events or ("before", "changed") in events:
                return "not-started", "Service status changed; read it again before resetting"
            return "not-started", "Reset was not sent" + (f" — {failure}" if failure else "")
        if not state["accepted"]:
            return "uncertain", "Reset outcome is uncertain; reconnect and read service status"
        after = self.report["after"]
        if after:
            try:
                records = decode_cbs_response(bytes.fromhex(after), self.plan.owner["version"])
                before = decode_record(
                    bytes.fromhex(self.plan.before_raw), self.plan.owner["version"]
                )
            except ValueError:
                records, before = [], {}
            match = [rec for rec in records if rec["item"] == self.plan.item]
            if len(match) == 1 and match[0]["availability"] == 100:
                if before.get("count") is not None and match[0]["count"] == before["count"] + 1:
                    return "verified", "Reset accepted; the re-read shows 100 % and the next count"
                if before.get("count") is None and match[0]["raw"] != self.plan.before_raw:
                    return (
                        "verified",
                        "Reset accepted; the re-read shows 100 % and a changed record",
                    )
            reason = self._detail_reason()
            return (
                "response-confirmed",
                "Reset accepted by the ECU, but the re-read does not show the new state yet"
                + (f" (ECU reports: {reason})" if reason else "")
                + " — read service status again later",
            )
        return (
            "response-confirmed",
            "Reset accepted by the ECU; no re-read was obtained — reconnect and read "
            "service status",
        )

    def _detail_reason(self) -> str:
        """Decode the v6 per-item reset reason (3-byte records), if one was read."""
        raw = bytes.fromhex(self.report.get("reset_detail", ""))
        if raw[:3] != b"\x62\x10\x02" or (len(raw) - 3) % 3:
            return ""
        for offset in range(3, len(raw), 3):
            if raw[offset] == self.plan.item:
                code = raw[offset + 1]
                if 0x80 <= code <= 0xBF:
                    return f"sensor-specific reason 0x{code:02X}"
                return DETAIL_REASONS.get(code, f"reason 0x{code:02X}")
        return ""
