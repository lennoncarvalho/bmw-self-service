"""Frozen headunit history plans and checked journal-backed execution (workflow28)."""

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import date
from typing import Any, cast

from app.coding import decode_cafd_identifiers
from app.history_files import entry_conflicts, entry_model, project_bytes, valid_vin
from app.history_journal import HistoryJournalStore
from app.protocol.contracts import FailureKind, OperationContext, ProtocolFailure, TransportKind
from app.resources import resource_path
from app.service_history import decode_nbt_add_result, encode_nbt_add
from app.vehicle import DiagnosticCatalog, did_data
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
    data = json.loads(raw)
    if len(raw) > 65536 or data.get("schema_version") != 1:
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
) -> HistoryPlan:
    """Freeze append or replacement against local data, never an invented car baseline."""
    data, digest = contracts()
    project = json.loads(project_bytes(workspace["project"]))
    if not valid_vin(vin) or project["vin"] != vin:
        raise ValueError("Associate the local project with the verified VIN before writing")
    if mode not in ("append", "replace"):
        raise ValueError("Invalid history mode")
    if mode == "append":
        if type(index) is not int or not 0 <= index < len(project["entries"]):
            raise ValueError("Select one local draft for append")
        indices = [index]
    else:
        indices = list(range(len(project["entries"])))
    if not indices:
        raise ValueError("Replacement requires a nonempty reviewed list")
    intended = [project["entries"][i] for i in indices]
    send_project = {"schema_version": 1, "vin": vin, "entries": intended}
    if any(entry_conflicts(send_project)):
        raise ValueError("Resolve future, duplicate or unsupported history values before writing")
    ids = [workspace["records"][i]["id"] for i in indices]
    if mode == "append":
        if ids[0] in consumed or workspace["records"][indices[0]].get("write_state") in (
            "accepted",
            "uncertain",
        ):
            raise ValueError("This draft may already have been sent; inspect its journal")
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
        "vin": vin,
        "mode": mode,
        "target": target,
        "encoder": {"id": data["id"], "sha256": digest},
        "local_before": project,
        "intended": intended,
        "requests": requests,
        "draft_ids": ids,
    }
    return HistoryPlan(
        json.dumps(plan, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    )


def validate_execution(data: dict) -> None:
    """Reject altered, incomplete or unsupported byte plans at the send boundary."""
    definition, digest = contracts()
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
    expected.append({"kind": "session", "request": "1001", "entry_index": None})
    if data["mode"] == "replace":
        expected.append({"kind": "erase", "request": "3101a080", "entry_index": None})
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
    expected.append({"kind": "reset", "request": "1101", "entry_index": None})
    if expected != data["requests"]:
        raise ValueError("History request sequence differs from its exact contract")


class HistoryPrepareWorker(CarWorker):
    """Read target identity and local journal guards before showing confirmation."""

    def __init__(
        self,
        connection: Any,
        ecus: list[dict],
        workspace: dict,
        mode: str,
        index: int | None,
        store: HistoryJournalStore,
    ) -> None:
        super().__init__(connection)
        self.ecus = [dict(row) for row in ecus]
        self.workspace = json.loads(json.dumps(workspace))
        self.mode, self.index, self.store = mode, index, store

    def do_work(self) -> HistoryPlan:
        """Prepare on the owner with a whole30second read budget, no mutations."""
        connection = self.connection
        if connection.read_only or connection.kind != TransportKind.HSFZ:
            raise PermissionError("History writes require a supported writable session")
        row = select_target(self.ecus)
        vin = connection.verified_vin
        if not valid_vin(vin):
            raise ValueError("Verified vehicle identity is required")
        context = connection.context(30.0)
        known_dates = self.store.known_dates(vin)
        consumed = self.store.consumed_draft_ids(vin)
        context.remaining()

        def prepare(services: Any, ctx: OperationContext) -> bytes:
            identity = services.invoke(b"\x22\xf1\x50", ctx)
            match = DiagnosticCatalog().identify(0x63, identity)
            if (
                match.get("address_index") != row["address_index"]
                or match.get("name") != row["name"]
            ):
                raise ValueError("Headunit identity changed; refresh before writing")
            software = services.invoke(b"\x22\xf1\x01", ctx)
            validate_software(software)
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
        )


class HistoryWriteWorker(CarWorker):
    """Execute exactly one confirmed plan; preserve all outcomes and never replay."""

    def __init__(
        self,
        connection: Any,
        plan: HistoryPlan,
        store: HistoryJournalStore,
        *,
        power_acknowledged: bool = False,
        replacement_acknowledged: bool = False,
    ) -> None:
        super().__init__(connection)
        self.plan, self.store = plan, store
        self.power_acknowledged = power_acknowledged
        self.replacement_acknowledged = replacement_acknowledged
        self._executed = False
        self.report: dict[str, Any] = {
            "path": "",
            "state": "not-started",
            "events": [],
            "instructions": INSTRUCTIONS,
            "persistence_failed": False,
        }

    def do_work(self) -> dict[str, Any]:
        """Persist intent, then exclusively execute a bounded checked sequence."""
        if self._executed:
            raise PermissionError("A history operation cannot be replayed")
        self._executed = True
        connection = self.connection
        context = connection.context(300.0)
        data = self.plan.data()
        validate_execution(data)
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
        # Recheck known local operation effects after confirmation, before any send.
        if data["mode"] == "append" and (
            data["draft_ids"][0] in self.store.consumed_draft_ids(data["vin"])
            or date.fromisoformat(data["intended"][0]["date"])
            in self.store.known_dates(data["vin"])
        ):
            raise ValueError("This date/draft has a prior accepted or uncertain operation")
        context.remaining()
        path = self.store.prepare(**data)
        self.report["path"] = str(path)
        requests = data["requests"]
        attempted = -1
        accepted_mutation = False
        failure = ""

        def record(
            state: str, step: int | None = None, response: bytes = b"", detail: str = ""
        ) -> None:
            event = {"state": state, "step": step, "response": response.hex(), "detail": detail}
            self.report["events"].append(event)
            try:
                self.store.record(path, state=state, step=step, response=response, detail=detail)
            except (OSError, ValueError):
                self.report["persistence_failed"] = True
                raise

        def execute(services: Any, ctx: OperationContext) -> bytes:
            nonlocal attempted, accepted_mutation, failure
            for step, request in enumerate(requests):
                ctx.remaining()
                attempted = step
                record("sending", step)
                self.progress.emit(
                    f"History {data['mode']}: {request['kind']} ({step + 1}/{len(requests)})"
                )
                payload = bytes.fromhex(request["request"])
                deadline = ctx.deadline
                ctx.deadline = min(deadline, time.monotonic() + 30.0)
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
                delay = (
                    0.2 if request["kind"] == "erase" else 0.1 if request["kind"] == "add" else 0
                )
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
            # run_operation invalidates transport failures; disk/decoder exceptions may
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
            if attempted >= 0 and pending == "sending" and not self.report["persistence_failed"]:
                try:
                    record(
                        "uncertain",
                        attempted,
                        detail="Operation interrupted; inspect iDrive before any new action",
                    )
                except (OSError, ValueError):
                    self.report["persistence_failed"] = True
        if self.report.get("identity_changed"):
            connection.request_close()
        overall = ("partial" if accepted_mutation else failure) if failure else "response-confirmed"
        self.report["state"] = overall
        if not self.report["persistence_failed"]:
            try:
                for step in range(attempted + 1, len(requests)):
                    record(
                        "unattempted",
                        step,
                        detail="Stopped after an earlier failed or uncertain step",
                    )
                record(overall, detail=INSTRUCTIONS)
            except (OSError, ValueError):
                self.report["persistence_failed"] = True
        if self.report["persistence_failed"]:
            self.report["state"] = "partial" if accepted_mutation else "uncertain"
        return self.report


def decode_erase_result(response: bytes) -> Any:
    """Use the exact shared business-status table with the ERASE routine echo."""
    if response[:4] != b"\x71\x01\xa0\x80" or len(response) != 5:
        raise ValueError("Invalid history erase application response")
    return decode_nbt_add_result(b"\x71\x01\xa0\x81" + response[4:])
