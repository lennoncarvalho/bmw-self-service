"""Frozen in-memory headunit history plans and checked, explicitly requested writes."""

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import date
from typing import Any, cast

from app.coding import decode_cafd_identifiers
from app.history_files import (
    entry_conflicts,
    entry_model,
    mileage_conflicts,
    project_bytes,
    valid_vin,
    validate_project,
)
from app.protocol.contracts import (
    ENET_HEADUNIT_READ_TIMING,
    FailureKind,
    OperationContext,
    ProtocolFailure,
    TransportKind,
    WriteConditionsBlocked,
)
from app.resources import resource_path
from app.service_history import decode_nbt_add_result, encode_nbt_add
from app.session import LIVE, check_binding, environment
from app.vehicle import DiagnosticCatalog, check_write_conditions, did_data
from app.worker import CarWorker

logger = logging.getLogger(__name__)
INSTRUCTIONS = (
    "Wait for the headunit to finish restarting, then inspect the service list in iDrive. "
    "These are checked application responses, not a vehicle-history readback. "
    "If interrupted, inspect iDrive before a separately confirmed new action; never replay automatically."
)


def contracts() -> tuple[dict[str, Any], str]:
    """Load the embedded exact-variant execution contract and its full identity."""
    path = resource_path("coding_data/history_contracts.json")
    with path.open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError("History execution definitions exceed their size limit")
    data = json.loads(raw)
    if (
        not isinstance(data, dict)
        or data.get("schema_version") != 1
        or data.get("erase_delay_ms") != 200
        or data.get("add_delay_ms") != 100
    ):
        raise ValueError("Invalid history execution definitions")
    return data, hashlib.sha256(raw).hexdigest()


def select_target(ecus: list[dict[str, Any]]) -> dict[str, Any]:
    """Require a unique identified headunit with an exact embedded definition."""
    data, _ = contracts()
    candidates = [
        row
        for row in ecus
        if row.get("identified") is True
        and row.get("uds") is True
        and row.get("address_index") in data["engines"]
    ]
    if len(candidates) != 1:
        raise ValueError("No unique supported headunit identity")
    row = candidates[0]
    if int(row["addr"], 0) != 0x63 or data["engines"][row["address_index"]]["name"] != row.get(
        "name"
    ):
        raise ValueError("Headunit definition identity mismatch")
    return dict(row)


def validate_software(response: bytes) -> None:
    """Require a complete nonempty software-role table, retaining its raw identity."""
    decode_cafd_identifiers(response)
    if response[6] == 0:
        raise ValueError("Headunit software identity is empty")


@dataclass(frozen=True)
class HistoryPlan:
    """Immutable canonical intent; copies returned to callers cannot change it."""

    encoded: bytes

    def data(self) -> dict[str, Any]:
        """Return a detached display/execution snapshot."""
        return cast(dict[str, Any], json.loads(self.encoded))


def build_plan(
    *,
    workspace: dict,
    target: dict,
    mode: str,
    index: int | None,
    vin: str,
    known_dates: set[date],
    consumed: set[str],
    session: dict[str, str] | None = None,
    write_conditions: str = "",
) -> HistoryPlan:
    """Freeze append or replacement against local data, never an invented car baseline."""
    data, digest = contracts()
    project = json.loads(project_bytes(workspace["project"]))
    if not valid_vin(vin):
        raise ValueError("A verified vehicle VIN is required before writing")
    if mode not in ("append", "replace"):
        raise ValueError("Invalid history mode")
    if mode == "append":
        if type(index) is not int or not 0 <= index < len(project["entries"]):
            raise ValueError("Select one staged entry for append")
        indices = [index]
    else:
        indices = list(range(len(project["entries"])))
    if not indices:
        raise ValueError("Replacement requires a nonempty reviewed list")
    intended = [project["entries"][i] for i in indices]
    conflicts = entry_conflicts(project)
    if any(conflicts[index] for index in indices):
        raise ValueError(
            "Correct the selected entries' dates, mileage, garage and service items before writing"
        )
    ids = [workspace["records"][i]["id"] for i in indices]
    if mode == "append":
        if ids[0] in consumed or workspace["records"][indices[0]].get("write_state") in (
            "accepted",
            "uncertain",
        ):
            raise ValueError("This draft may already have been sent; inspect iDrive")
        existing = {
            date.fromisoformat(entry["date"])
            for i, entry in enumerate(project["entries"])
            if i != index
        } | known_dates
    else:
        existing = set()
    row = data["engines"].get(target.get("address_index"))
    if not row or row["name"] != target.get("name") or target.get("address") != 0x63:
        raise ValueError("Headunit does not match an exact execution contract")
    if did_data(bytes.fromhex(target["identity"]), 0xF150)[:3].hex().upper() != target["variant"]:
        raise ValueError("Headunit variant identity is inconsistent")
    if target["address_index"] != f"63 {target['variant']}":
        raise ValueError("Headunit address identity is inconsistent")
    validate_software(bytes.fromhex(target["software"]))
    requests: list[dict[str, Any]] = [
        {"kind": "identity", "request": request, "entry_index": None}
        for request in ("22f190", "22f150", "22f101")
    ]
    requests.append({"kind": "session", "request": data["default_session"], "entry_index": None})
    if mode == "replace":
        requests.append({"kind": "erase", "request": data["erase"], "entry_index": None})
    requests.extend(
        {
            "kind": "add",
            "request": encode_nbt_add(entry_model(entry), existing_dates=existing).hex(),
            "entry_index": i,
        }
        for i, entry in enumerate(intended)
    )
    requests.append({"kind": "reset", "request": data["reset"], "entry_index": None})
    plan = {
        "session": session or LIVE.binding(),
        "vin": vin,
        "mode": mode,
        "target": target,
        "encoder": {"id": data["id"], "sha256": digest},
        "local_before": project,
        "intended": intended,
        "requests": requests,
        "draft_ids": ids,
        "write_conditions": write_conditions,
    }
    return HistoryPlan(
        json.dumps(plan, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    )


def validate_execution(data: dict) -> dict:
    """Reject altered, incomplete or unsupported byte plans at the send boundary."""
    definition, digest = contracts()
    before = validate_project(data["local_before"])
    intended = validate_project(
        {"schema_version": 1, "vin": data["vin"], "entries": data["intended"]}
    )
    comparison = [*before["entries"], *intended["entries"]]
    if any(entry_conflicts(intended)) or any(
        mileage_conflicts(comparison)[len(before["entries"]) :]
    ):
        raise ValueError("Correct conflicting history dates and mileage before writing")
    if data["encoder"] != {"id": definition["id"], "sha256": digest}:
        raise ValueError("History execution definition changed")
    target = data["target"]
    row = definition["engines"].get(target["address_index"])
    if (
        not row
        or row["name"] != target["name"]
        or target["address"] != 0x63
        or target.get("vin_address") != 0x10
    ):
        raise ValueError("Invalid exact headunit execution identity")
    match = DiagnosticCatalog().identify(0x63, bytes.fromhex(target["identity"]))
    if match["address_index"] != target["address_index"] or match["variant"] != target["variant"]:
        raise ValueError("History target variant does not match its recorded bytes")
    validate_software(bytes.fromhex(target["software"]))
    expected: list[dict[str, Any]] = [
        {"kind": "identity", "request": request, "entry_index": None}
        for request in ("22f190", "22f150", "22f101")
    ]
    expected.append(
        {"kind": "session", "request": definition["default_session"], "entry_index": None}
    )
    if data["mode"] == "replace":
        if not data["intended"]:
            raise ValueError("History replacement requires at least one entry")
        expected.append({"kind": "erase", "request": definition["erase"], "entry_index": None})
    elif data["mode"] != "append" or len(data["intended"]) != 1:
        raise ValueError("Invalid history operation mode")
    expected.extend(
        {
            "kind": "add",
            "request": encode_nbt_add(entry_model(entry), existing_dates=()).hex(),
            "entry_index": i,
        }
        for i, entry in enumerate(data["intended"])
    )
    expected.append({"kind": "reset", "request": definition["reset"], "entry_index": None})
    if expected != data["requests"]:
        raise ValueError("History request sequence differs from its exact contract")
    return definition


def file_vin_mismatch(data: dict) -> bool:
    """Check provenance against the confirmed target without changing the staged file."""
    file_vin = data["local_before"]["vin"]
    return file_vin is not None and file_vin != data["vin"]


class HistoryPrepareWorker(CarWorker):
    """Read target identity and freeze the staging area before confirmation."""

    def __init__(
        self,
        connection: Any,
        ecus: list[dict],
        workspace: dict,
        mode: str,
        index: int | None,
        *,
        known_dates: set[date] | None = None,
        consumed: set[str] | None = None,
    ) -> None:
        super().__init__(connection)
        self.ecus = [dict(row) for row in ecus]
        self.workspace = json.loads(json.dumps(workspace))
        self.mode, self.index = mode, index
        self.known_dates = set(known_dates or ())
        self.consumed = set(consumed or ())

    def do_work(self) -> HistoryPlan:
        """Prepare on the owner within one 30-second budget."""
        connection = self.connection
        if connection.read_only or connection.kind != TransportKind.HSFZ:
            raise PermissionError("History writes require a supported writable session")
        row = select_target(self.ecus)
        vin = connection.verified_vin
        if not valid_vin(vin):
            raise ValueError("Verified vehicle identity is required")
        context = connection.context(30.0)
        known_dates = self.known_dates
        consumed = self.consumed
        context.remaining()

        conditions = ""

        def prepare(services: Any, ctx: OperationContext) -> bytes:
            nonlocal conditions
            timing = ctx.response_timing
            ctx.response_timing = ENET_HEADUNIT_READ_TIMING
            try:
                identity = services.invoke(b"\x22\xf1\x50", ctx)
                match = DiagnosticCatalog().identify(0x63, identity)
                if (
                    match.get("address_index") != row["address_index"]
                    or match.get("name") != row["name"]
                ):
                    raise ValueError("Headunit identity changed; refresh before writing")
                software = services.invoke(b"\x22\xf1\x01", ctx)
            finally:
                ctx.response_timing = timing
            validate_software(software)
            conditions = check_write_conditions(connection, self.ecus, ctx)
            return json.dumps(
                {
                    "address": 0x63,
                    "vin_address": 0x10,
                    "name": row["name"],
                    "variant": match["variant"],
                    "address_index": row["address_index"],
                    "identity": identity.hex(),
                    "software": software.hex(),
                }
            ).encode()

        target = json.loads(connection.run_operation(0x63, prepare, context=context))
        return build_plan(
            workspace=self.workspace,
            target=target,
            mode=self.mode,
            index=self.index,
            vin=vin,
            known_dates=known_dates,
            consumed=consumed,
            session=environment(connection).binding(),
            write_conditions=conditions,
        )


class HistoryWriteWorker(CarWorker):
    """Execute exactly one confirmed plan; preserve all outcomes and never replay."""

    def __init__(
        self,
        connection: Any,
        plan: HistoryPlan,
        *,
        power_acknowledged: bool = False,
        replacement_acknowledged: bool = False,
        file_vin_acknowledged: bool = False,
        ecus: list[dict] | None = None,
    ) -> None:
        super().__init__(connection)
        self.plan = plan
        self.power_acknowledged = power_acknowledged
        self.replacement_acknowledged = replacement_acknowledged
        self.file_vin_acknowledged = file_vin_acknowledged
        self.ecus = [dict(row) for row in ecus or ()]
        self._executed = False
        self.report: dict[str, Any] = {
            "state": "not-started",
            "events": [],
            "instructions": INSTRUCTIONS,
        }

    def do_work(self) -> dict[str, Any]:
        """Execute one confirmed in-memory intent without creating a saved history record."""
        if self._executed:
            raise PermissionError("A history operation cannot be replayed")
        self._executed = True
        connection = self.connection
        context = connection.context(300.0)
        data = self.plan.data()
        check_binding(connection, data.get("session"))
        definition = validate_execution(data)
        if file_vin_mismatch(data) and not self.file_vin_acknowledged:
            raise PermissionError("Review the mismatched source file VIN before writing")
        if (
            not self.power_acknowledged
            or getattr(connection, "power_sufficient", None) is False
            or (data["mode"] == "replace" and not self.replacement_acknowledged)
        ):
            raise PermissionError(
                "Power and irreversible replacement acknowledgements are required"
            )
        if (
            connection.read_only
            or connection.kind != TransportKind.HSFZ
            or connection.verified_vin != data["vin"]
            or not connection.alive_ok
        ):
            raise PermissionError("Vehicle identity/session changed before history write")
        context.remaining()
        requests = data["requests"]
        attempted = -1
        accepted_mutation = False
        failure = ""

        def record(
            state: str, step: int | None = None, response: bytes = b"", detail: str = ""
        ) -> None:
            event = {"state": state, "step": step, "response": response.hex(), "detail": detail}
            self.report["events"].append(event)

        def execute(services: Any, ctx: OperationContext) -> bytes:
            nonlocal attempted, accepted_mutation, failure
            for step, request in enumerate(requests):
                ctx.remaining()
                if request["kind"] == "session":
                    try:
                        self.report["write_conditions"] = check_write_conditions(
                            connection, self.ecus, ctx
                        )
                    except WriteConditionsBlocked as error:
                        self.report["instructions"] = str(error)
                        failure = "blocked"
                        return b""
                attempted = step
                record("sending", step)
                self.progress.emit(
                    f"History {data['mode']}: {request['kind']} ({step + 1}/{len(requests)})"
                )
                payload = bytes.fromhex(request["request"])
                deadline = ctx.deadline
                timing = ctx.response_timing
                ctx.deadline = min(deadline, time.monotonic() + 30.0)
                if payload in (b"\x22\xf1\x50", b"\x22\xf1\x01"):
                    ctx.response_timing = ENET_HEADUNIT_READ_TIMING
                try:
                    # Nested owner call remains inline on this executor, including gateway VIN.
                    try:
                        response = connection.send_uds(
                            0x10 if payload == b"\x22\xf1\x90" else 0x63, payload, context=ctx
                        )
                    except ProtocolFailure as exc:
                        if exc.kind != FailureKind.NEGATIVE or exc.reconnect:
                            raise
                        response = exc.raw
                finally:
                    ctx.deadline = deadline
                    ctx.response_timing = timing
                if response[:1] == b"\x7f":
                    record("rejected", step, response, "ECU rejected this request")
                    failure = "rejected"
                    return b""
                try:
                    if request["kind"] == "identity":
                        if payload == b"\x22\xf1\x90":
                            if did_data(response, 0xF190).decode("ascii") != data["vin"]:
                                raise ValueError("Vehicle VIN changed")
                        elif (
                            response.hex()
                            != data["target"][
                                "identity" if payload == b"\x22\xf1\x50" else "software"
                            ]
                        ):
                            raise ValueError("Headunit identity/software changed")
                    elif request["kind"] == "session":
                        if response[:2] != b"\x50\x01" or len(response) not in (2, 6):
                            raise ValueError("Invalid default-session response")
                    elif request["kind"] in ("add", "erase"):
                        result = (
                            decode_nbt_add_result(response)
                            if request["kind"] == "add"
                            else decode_erase_result(response)
                        )
                        if not result.accepted:
                            failure = "rejected" if result.code in (1, 2, 4) else "uncertain"
                            record(failure, step, response, result.description)
                            return b""
                    elif response != b"\x51\x01":
                        raise ValueError("Reset was not response-confirmed")
                except (ValueError, UnicodeError):
                    record(
                        "uncertain" if request["kind"] in ("add", "erase", "reset") else "rejected",
                        step,
                        response,
                        "Response/identity could not be validated; no further writes",
                    )
                    failure = (
                        "uncertain" if request["kind"] in ("add", "erase", "reset") else "rejected"
                    )
                    self.report["identity_changed"] = request["kind"] == "identity"
                    return b""
                accepted_mutation |= request["kind"] in ("add", "erase", "reset")
                record("accepted", step, response)
                delay = definition.get(f"{request['kind']}_delay_ms", 0) / 1000
                if delay:
                    ctx.remaining()
                    ctx.cancelled.wait(min(delay, ctx.remaining()))
                    ctx.remaining()
            return b""

        try:
            connection.run_operation(0x63, execute, context=context)
        except Exception:
            logger.warning(
                "History operation stopped; retained exact in-memory outcomes", exc_info=True
            )
            # Ambiguous service/stream failures must never be hidden from the owner.
            # run_operation invalidates transport failures; decoder exceptions may
            # also occur after effects, so explicitly stop this connection conservatively.
            connection.request_close()
            failure = "uncertain"
            pending = next(
                (
                    event["state"]
                    for event in reversed(self.report["events"])
                    if event["step"] == attempted
                ),
                None,
            )
            if attempted >= 0 and pending == "sending":
                record(
                    "uncertain",
                    attempted,
                    detail="Operation interrupted; inspect iDrive before any new action",
                )
        if self.report.get("identity_changed"):
            connection.request_close()
        overall = ("partial" if accepted_mutation else failure) if failure else "response-confirmed"
        self.report["state"] = overall
        for step in range(attempted + 1, len(requests)):
            record(
                "unattempted",
                step,
                detail="Stopped after an earlier failed or uncertain step",
            )
        record(overall, detail=self.report["instructions"])
        return self.report


def decode_erase_result(response: bytes) -> Any:
    """Use the exact shared business-status table with the ERASE routine echo."""
    if response[:4] != b"\x71\x01\xa0\x80" or len(response) != 5:
        raise ValueError("Invalid history erase application response")
    return decode_nbt_add_result(b"\x71\x01\xa0\x81" + response[4:])
