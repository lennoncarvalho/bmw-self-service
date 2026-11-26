"""Source-backed easy coding plans and single-owner, journalled execution.

Only source identifiers enter preparation. Runtime uses embedded definitions and
complete real ECU groups; imported JSON and UI indexes never authorize telegrams.
"""

import hashlib
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Any, cast

from PySide6.QtCore import Signal

from app.coding import bootloader_identifier, decode_cafd_identifiers
from app.coding_authorization import derive_authorization_key
from app.coding_db import CodingDatabase
from app.coding_guards import CodingGuardBlocked
from app.coding_guards import contracts as guard_contracts
from app.coding_guards import observe as observe_guard
from app.coding_prerequisites import (
    applies,
    reader_contract,
    run_prerequisites,
)
from app.history_files import valid_vin
from app.operation_store import OperationStore, coding_comparison_basis, load_record
from app.protocol.contracts import (
    ENET_HEADUNIT_READ_TIMING,
    FailureKind,
    OperationContext,
    ProtocolFailure,
    TransportKind,
    WriteConditionsBlocked,
)
from app.session import check_binding, check_record, check_store, environment, operation_store
from app.vehicle import DiagnosticCatalog, check_write_conditions, did_data
from app.vehicle_order import decode_vehicle_order
from app.worker import CarWorker

logger = logging.getLogger(__name__)
_INSTRUCTIONS = (
    "Wait for ECU restart and any required vehicle cycle, then reconnect. "
    "Compare current coding from Backups. "
    "Response-confirmed completion is not an observed post-cycle verification. "
    "Do not replay an interrupted operation; compare current data before a separately confirmed restore."
)


def _canonical(value: Any) -> bytes:
    """Encode deterministic JSON for frozen plans and integrity hashes."""
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _groups(db: CodingDatabase, definitions: list[str]) -> list[int]:
    """Collect complete coding group DIDs in source definition order."""
    groups: set[int] = set()
    for definition in definitions:
        identifier, version = definition.split("-", 1)
        for group in db.get_definition(identifier, version)["dataGroups"]:
            value = group["address"]
            did = int(value, 0) if isinstance(value, str) else int(value)
            if not 0 <= did <= 0xFFFF:
                raise ValueError("Coding group address exceeds diagnostic width")
            groups.add(did)
    if not groups:
        raise ValueError("Exact coding definitions have no readable groups")
    ordered: list[int] = []
    for definition in definitions:
        identifier, version = definition.split("-", 1)
        for group in db.get_definition(identifier, version)["dataGroups"]:
            value = group["address"]
            did = int(value, 0) if isinstance(value, str) else int(value)
            if did not in ordered:
                ordered.append(did)
    return ordered


def _definition_digest(db: CodingDatabase, definitions: list[str]) -> str:
    """Bind the selected definition material to its ordered source hashes."""
    return hashlib.sha256(
        "".join(db.source_sha256(item) for item in definitions).encode()
    ).hexdigest()


def _read_groups(
    db: CodingDatabase, definitions: list[str], read: Callable[[bytes], bytes]
) -> dict[int, bytes]:
    """Read and validate the complete source group set from one target."""
    blocks = {
        did: did_data(read(b"\x22" + did.to_bytes(2, "big")), did)
        for did in _groups(db, definitions)
    }
    db.validate_blocks(definitions, blocks)
    return blocks


def _prior_records(
    store: OperationStore,
    vin: str,
    addresses: set[int],
    ctx: OperationContext,
    *,
    exclude: Path | None = None,
) -> list[dict]:
    """Read owned interrupted records on the worker, never from embedded paths."""
    paths = sorted(store.root.glob("*.json"))
    if len(paths) > 10000:
        raise ValueError("Coding recovery inventory exceeds its supported bound")
    total = 0
    result = []
    for path in paths:
        ctx.remaining()
        if path == exclude:
            continue
        total += path.stat().st_size
        if total > 256 * 1024 * 1024:
            raise ValueError("Coding recovery inventory exceeds its byte bound")
        record = load_record(path)
        original = record["original"]
        if original["kind"] != "coding" or original["mode"] != store.mode or original["vin"] != vin:
            continue
        state = record["events"][-1]["state"]
        if state not in {"writing", "partial", "uncertain", "mismatch"}:
            continue
        targets = [target for target in original["targets"] if target["address"] in addresses]
        if targets:
            result.append(
                {
                    "path": str(path),
                    "id": original["id"],
                    "sha256": record["sha256"],
                    "state": state,
                    "targets": targets,
                }
            )
    return result


@dataclass(frozen=True)
class CodingPlan:
    """Immutable original/intent and source selection for confirmation/execution."""

    encoded: bytes

    def data(self) -> dict[str, Any]:
        """Return a detached display copy without changing the frozen intent."""
        return cast(dict[str, Any], json.loads(self.encoded))


def _resolve_changes(
    db: CodingDatabase,
    changes: list[dict],
    definitions: list[str],
    baseline: dict[int, bytes],
    *,
    variant_index: str,
    vehicle_context: dict,
) -> dict[int, bytes]:
    """Validate source preset selections and compose nonconflicting masked changes."""
    primary = db.primary_definition(definitions)
    identifier, version = primary.split("-", 1)
    selected: list[tuple[dict, str]] = []
    available_presets = db.get_presets(identifier)
    seen: set[tuple[str, int]] = set()
    for change in changes:
        definition, name, option = change["definition"], change["preset"], change["option"]
        if definition != primary:
            raise ValueError("Coding option definition is absent or selected twice")
        if "preset_index" in change:
            index = change["preset_index"]
            if type(index) is not int or not 0 <= index < len(available_presets):
                raise ValueError("Coding source preset index is invalid")
            presets = [available_presets[index]]
            if presets[0]["name"] != name:
                raise ValueError("Coding source preset identity differs from its name")
        else:
            presets = [preset for preset in available_presets if preset["name"] == name]
        if len(presets) != 1:
            raise ValueError("Coding preset is missing or ambiguous")
        source_identity = (definition, presets[0]["source_index"])
        if source_identity in seen:
            raise ValueError("Coding source preset is selected twice")
        seen.add(source_identity)
        choices = db.preset_choice_patches(
            presets[0],
            definition[:8],
            definition[9:],
            baseline,
            definitions=definitions,
        )
        if option not in choices:
            raise ValueError("Selected coding choice is unavailable with the current layout")
        applicable, reason = db.preset_applicability(
            presets[0],
            category=vehicle_context.get("category"),
            variant_index=variant_index,
            id8=vehicle_context.get("id8"),
            model_range=vehicle_context.get("model_range", ""),
            type_code=vehicle_context.get("type_code", ""),
        )
        if applicable is not True:
            raise ValueError(reason)
        resolved = db.resolve_dynamic_preset(
            presets[0], baseline, definition[:8], definition[9:], definitions=definitions
        )
        selected.append((resolved, option))
    return db.compose_changes(selected, baseline, identifier, version, definitions=definitions)


def _finalize(
    db: CodingDatabase, blocks: dict[int, bytes], definitions: list[str], software: bytes
) -> dict[int, bytes]:
    # This helper implements source NCD signatures and exact key selection. Its
    # absence is not permission to return unfinalized bytes.
    """Apply source signatures using the reported bootloader identity."""
    return db.finalize_write_blocks(blocks, definitions, bootloader_identifier(software))


def _target_record(target: dict) -> dict:
    """Extract the strict complete-baseline storage fields from a prepared target."""
    return {
        key: target[key]
        for key in ("address", "variant", "software", "definition_sha256", "baseline", "intended")
    }


class CodingPrepareWorker(CarWorker):
    """Read a complete fresh baseline and compose source-defined easy options."""

    sensitive_operation_requested = Signal(object)

    def __init__(
        self,
        connection: Any,
        ecus: list[dict],
        changes: list[dict],
        store: OperationStore | None = None,
        *,
        restore_path: Path | None = None,
        vehicle_context: dict | None = None,
    ) -> None:
        """Copy selection inputs and retain the optional explicit restore source."""
        super().__init__(connection)
        self.restore_path = restore_path
        self.guard_notice = ""
        self.vehicle_context = json.loads(json.dumps(vehicle_context or {}))
        if set(self.vehicle_context) - {"id8", "category"}:
            raise ValueError("Unknown coding selection context")
        if (
            self.vehicle_context.get("id8") is not None
            and type(self.vehicle_context["id8"]) is not bool
        ):
            raise ValueError("Invalid headunit generation context")
        if (
            self.vehicle_context.get("category") is not None
            and type(self.vehicle_context["category"]) is not int
        ):
            raise ValueError("Invalid source category context")
        self.ecus = json.loads(json.dumps(ecus))
        self.changes = json.loads(json.dumps(changes))
        self.store = store or operation_store(connection)
        self.restore_record: dict | None = None

    def do_work(self) -> CodingPlan:
        """Freeze exact source selection after read-only owner operations."""
        connection = self.connection
        check_store(connection, self.store)
        if (
            connection.read_only
            or connection.kind != TransportKind.HSFZ
            or not valid_vin(connection.verified_vin)
        ):
            raise PermissionError("Coding requires a supported writable identified connection")
        if self.restore_path is not None:
            record = load_record(self.restore_path)
            original = record["original"]
            if (
                original["kind"] != "coding"
                or original["mode"] != environment(connection).mode
                or original["vin"] != connection.verified_vin
            ):
                raise ValueError(
                    "Restore requires complete originals from this vehicle and environment"
                )
            check_record(connection, original["mode"], self.restore_path)
            self.restore_record = record
            self.changes = [{"address": target["address"]} for target in original["targets"]]
        db = CodingDatabase()
        context = connection.context(300.0)
        addresses = sorted({change["address"] for change in self.changes})
        if not addresses or any(type(address) is not int for address in addresses):
            raise ValueError("Select source-supported coding changes")
        plan: dict[str, Any] = {
            "schema_version": 1,
            "environment": environment(connection).binding(),
            "mode": "restore" if self.restore_record else "coding",
            "vin": connection.verified_vin,
            "changes": self.changes,
            "vehicle_context": {"category": None},
            "targets": [],
            "composition": "baseline-i",
        }
        if self.restore_record is not None:
            plan["restore_origin"] = {
                "original": self.restore_record["original"],
                "original_sha256": self.restore_record["original_sha256"],
            }
        source_targets = (
            {t["address"]: t for t in self.restore_record["original"]["targets"]}
            if self.restore_record
            else {}
        )
        for address in addresses:
            rows = [
                row
                for row in self.ecus
                if row.get("identified") is True
                and row.get("uds") is True
                and int(str(row["addr"]), 0) == address
            ]
            if len(rows) != 1:
                raise ValueError("Coding requires one identified target for each selected address")
            self.progress.emit(f"Reading complete coding baseline: {rows[0]['name']}")
            target: dict[str, Any] = {}

            def read(
                services: Any,
                ctx: OperationContext,
                address: int = address,
                rows: list[dict] = rows,
                target: dict = target,
            ) -> bytes:
                """Read, validate and freeze one complete target under the protocol owner."""
                headunit_reader = address == reader_contract()[0]["unlock_backup"]["address"]

                def read_uds(payload: bytes, address_override: int | None = None) -> bytes:
                    """Cap each owner request while preserving the overall preparation deadline."""
                    deadline = ctx.deadline
                    timing = ctx.response_timing
                    ctx.deadline = min(deadline, time.monotonic() + 30.0)
                    if headunit_reader and address_override is None:
                        ctx.response_timing = ENET_HEADUNIT_READ_TIMING
                    try:
                        result = (
                            services.invoke(payload, ctx)
                            if address_override is None
                            else connection.send_uds(address_override, payload, context=ctx)
                        )
                        return bytes(result)
                    finally:
                        ctx.deadline = deadline
                        ctx.response_timing = timing

                if "vin_observed" not in plan:
                    observed_vin = read_uds(b"\x22\xf1\x90", 0x10)
                    if did_data(observed_vin, 0xF190).decode("ascii") != plan["vin"]:
                        raise ValueError("Vehicle VIN changed before coding preparation")
                    plan["vin_observed"] = observed_vin.hex()
                identity = read_uds(b"\x22\xf1\x50")
                match = DiagnosticCatalog().identify(address, identity)
                if (
                    match.get("identified") is not True
                    or match.get("uds") is not True
                    or match.get("address_index") != rows[0].get("address_index")
                ):
                    raise ValueError("Coding target identity changed")
                software = read_uds(b"\x22\xf1\x01")
                definitions = list(decode_cafd_identifiers(software))
                if not definitions:
                    raise ValueError("ECU reports no exact coding definitions")
                scope_reason = db.easy_coding_block_reason(definitions)
                if scope_reason:
                    self.guard_notice = (
                        f"{match['name']}: {scope_reason}. No coding write was sent."
                    )
                    raise PermissionError(scope_reason)
                headunit_reader = applies(address, definitions, db)
                bootloader = bootloader_identifier(software)
                try:
                    authorization = db.coding_write_authorization(bootloader)
                except ValueError as error:
                    self.guard_notice = f"{match['name']}: {error}. No coding write was sent."
                    raise
                guard_observations = []
                for guard in guard_contracts(db, address):
                    try:
                        guard_observations.append(
                            observe_guard(self.store, plan["vin"], guard, read_uds)
                        )
                    except CodingGuardBlocked as error:
                        self.guard_notice = (
                            f"{rows[0]['name']}: {error.user_message} No coding write was sent."
                        )
                        raise
                    except Exception:
                        self.guard_notice = (
                            f"{rows[0]['name']}: the required coding-condition check is unavailable. "
                            "No coding write was sent. Check the connection, local evidence and session log."
                        )
                        raise
                if "write_conditions" not in plan or headunit_reader:
                    try:
                        plan["write_conditions"] = check_write_conditions(
                            connection, self.ecus, ctx
                        )
                    except WriteConditionsBlocked as error:
                        self.guard_notice = str(error)
                        raise
                if headunit_reader:
                    acknowledged = Event()
                    self.sensitive_operation_requested.emit(acknowledged)
                    while not acknowledged.wait(0.05):
                        ctx.remaining()
                prerequisites = run_prerequisites(
                    address=address,
                    variant=match["variant"],
                    definitions=definitions,
                    database=db,
                    vin=plan["vin"],
                    store=self.store,
                    read=read_uds,
                    read_only=connection.read_only,
                    context=ctx,
                    transport=connection.kind,
                )
                baseline = _read_groups(db, definitions, read_uds)
                if read_uds(b"\x22\xf1\x01") != software:
                    raise ValueError("Coding software changed during baseline read")
                digest = _definition_digest(db, definitions)
                selection_context: dict[str, Any] = {
                    "category": None,
                    "id8": db.id8_context(definitions, baseline),
                }
                if self.restore_record:
                    saved = source_targets[address]
                    if (
                        saved["variant"] != match["variant"]
                        or saved["software"] != software.hex()
                        or saved["definition_sha256"] != digest
                    ):
                        raise ValueError(
                            "Restore baseline does not match the current ECU/software/definitions"
                        )
                    intended = {
                        int(did, 16): bytes.fromhex(data) for did, data in saved["baseline"].items()
                    }
                    if set(intended) != set(baseline):
                        raise ValueError("Restore baseline has an incomplete coding group set")
                    if any(len(intended[did]) != len(baseline[did]) for did in baseline):
                        raise ValueError("Restore baseline group lengths differ")
                else:
                    selected = [change for change in self.changes if change["address"] == address]
                    needs_category = any(
                        (preset.get("series") or preset.get("excludedSeries"))
                        for change in selected
                        for preset in db.get_presets(change["definition"][:8])
                        if preset["name"] == change["preset"]
                    )
                    if needs_category:
                        if "vehicle_order" not in plan:
                            order_raw = read_uds(b"\x22\x3f\x06", 0x10)
                            plan["vehicle_order"] = order_raw.hex()
                        order = decode_vehicle_order(bytes.fromhex(plan["vehicle_order"]))
                        category = db.category_for_model_range(
                            order["model_range"], order["type_code"]
                        )
                        plan["vehicle_context"]["category"] = category
                        selection_context["category"] = category
                        selection_context.update(
                            model_range=order["model_range"], type_code=order["type_code"]
                        )
                    intended = _resolve_changes(
                        db,
                        selected,
                        definitions,
                        baseline,
                        variant_index=match["variant"],
                        vehicle_context=selection_context,
                    )
                intended = _finalize(db, intended, definitions, software)
                if address == 0x12 and intended.get(0x3010) != baseline.get(0x3010):
                    raise ValueError(
                        "This option changes a group excluded by the engine source writer"
                    )
                if any(len(intended[did]) != len(baseline[did]) for did in baseline):
                    raise ValueError(
                        "Source coding signature/group width differs from the actual baseline"
                    )
                if intended == baseline:
                    raise ValueError("The selected coding state is already current")
                target.update(
                    {
                        "address": address,
                        "name": rows[0]["name"],
                        "variant": match["variant"],
                        "address_index": match["address_index"],
                        "guard_observations": guard_observations,
                        "reader_prerequisites": prerequisites,
                        "identity": identity.hex(),
                        "software": software.hex(),
                        "definitions": definitions,
                        "definition_resolution": [
                            db.definition_resolution(item) for item in definitions
                        ],
                        "definition_sha256": digest,
                        "preset_source_sha256": (
                            None
                            if self.restore_record
                            else db.source_sha256(db.primary_definition(definitions)[:8])
                        ),
                        "authorization_sha256": authorization["source_sha256"],
                        "baseline": {f"{did:04X}": data.hex() for did, data in baseline.items()},
                        "intended": {f"{did:04X}": data.hex() for did, data in intended.items()},
                    }
                )
                return b""

            connection.run_operation(address, read, context=context)
            plan["targets"].append(target)
        prior = _prior_records(self.store, plan["vin"], set(addresses), context)
        current = {target["address"]: target for target in plan["targets"]}
        for operation in prior:
            compared = []
            for old in operation.pop("targets"):
                fresh = current[old["address"]]
                if old["variant"] != fresh["variant"] or old["software"] != fresh["software"]:
                    comparison = "identity-changed"
                elif old["definition_sha256"] != fresh["definition_sha256"]:
                    comparison = "definition-changed"
                elif fresh["baseline"] == old["baseline"] == old["intended"]:
                    comparison = "matches-both"
                elif fresh["baseline"] == old["baseline"]:
                    comparison = "matches-original"
                elif fresh["baseline"] == old["intended"]:
                    comparison = "matches-intended"
                else:
                    comparison = "differs"
                compared.append({"address": old["address"], "comparison": comparison})
            operation["targets"] = compared
        plan["prior_operations"] = prior
        return CodingPlan(_canonical(plan))


class CodingRestorePrepareWorker(CodingPrepareWorker):
    """Prepare a separately confirmed restore, never execute an imported record."""

    def __init__(
        self,
        connection: Any,
        ecus: list[dict],
        backup_path: Path,
        store: OperationStore | None = None,
    ) -> None:
        """Defer validated backup loading and fresh comparison to the worker."""
        super().__init__(connection, ecus, [], store, restore_path=backup_path)


class CodingVerificationWorker(CarWorker):
    """Compare complete observed coding groups with a saved operation."""

    sensitive_operation_requested = Signal(object)

    def __init__(
        self,
        connection: Any,
        path: Path,
        store: OperationStore,
        *,
        cycle_acknowledged: bool,
        ecus: list[dict] | None = None,
    ) -> None:
        """Retain the explicitly selected record and its local storage owner."""
        super().__init__(connection)
        self.path = path
        self.store = store
        self.cycle_acknowledged = cycle_acknowledged
        self.ecus = [dict(row) for row in ecus or ()]
        self.guard_notice = ""

    def do_work(self) -> dict:
        """Check current identity and bytes after the owner's cycle confirmation."""
        if not self.cycle_acknowledged:
            raise PermissionError("Acknowledge any required vehicle cycle before verification")
        connection = self.connection
        check_store(connection, self.store)
        record = load_record(self.path)
        check_record(connection, record["original"]["mode"], self.path)
        basis = coding_comparison_basis(record)
        original = record["original"]
        vin = original["vin"]
        if basis is None:
            self.guard_notice = (
                "This coding record has no applied or interrupted operation to compare."
            )
            raise ValueError(self.guard_notice)
        if (
            connection.kind != TransportKind.HSFZ
            or not connection.alive_ok
            or not valid_vin(vin)
            or connection.verified_vin != vin
        ):
            self.guard_notice = "Verification requires the same identified vehicle over ENET."
            raise PermissionError(self.guard_notice)
        db = CodingDatabase()
        context = connection.context(300.0)
        observed: dict[str, Any] = {"kind": "coding-comparison", "basis": basis, "targets": []}
        archived = {}
        for event in record["events"]:
            for response in event["responses"]:
                if isinstance(response, dict) and response.get("kind") == "frozen-plan":
                    origin = response["plan"].get("restore_origin")
                    if origin is not None:
                        archived_original = origin["original"]
                        if (
                            hashlib.sha256(_canonical(archived_original)).hexdigest()
                            != origin["original_sha256"]
                            or archived_original["vin"] != vin
                            or archived_original["mode"] != original["mode"]
                        ):
                            raise ValueError("Archived restore source failed its integrity check")
                        archived = {
                            target["address"]: target for target in archived_original["targets"]
                        }
                        if set(archived) != {target["address"] for target in original["targets"]}:
                            raise ValueError("Archived restore source target set does not match")
        sensitive = False

        def read_target(services: Any, ctx: OperationContext, saved: dict) -> bytes:
            """Read one exact ECU with the normal coding reader controls and timing."""
            nonlocal sensitive
            address = saved["address"]
            headunit_reader = address == reader_contract()[0]["unlock_backup"]["address"]

            def read(payload: bytes, override: int | None = None) -> bytes:
                deadline = ctx.deadline
                timing = ctx.response_timing
                ctx.deadline = min(deadline, time.monotonic() + 30.0)
                if headunit_reader and override is None:
                    ctx.response_timing = ENET_HEADUNIT_READ_TIMING
                try:
                    return bytes(
                        services.invoke(payload, ctx)
                        if override is None
                        else connection.send_uds(override, payload, context=ctx)
                    )
                finally:
                    ctx.deadline = deadline
                    ctx.response_timing = timing

            if did_data(read(b"\x22\xf1\x90", 0x10), 0xF190).decode("ascii") != vin:
                raise ValueError("The vehicle VIN changed before coding verification")
            identity = read(b"\x22\xf1\x50")
            match = DiagnosticCatalog().identify(address, identity)
            if (
                not match.get("identified")
                or not match.get("uds")
                or match.get("variant") != saved["variant"]
            ):
                raise ValueError(f"ECU 0x{address:02X} no longer matches the saved variant")
            software = read(b"\x22\xf1\x01")
            if software.hex() != saved["software"]:
                raise ValueError(f"ECU 0x{address:02X} software differs from the saved operation")
            definitions = list(decode_cafd_identifiers(software))
            if not definitions or _definition_digest(db, definitions) != saved["definition_sha256"]:
                raise ValueError(
                    f"ECU 0x{address:02X} source layout differs from the saved operation"
                )
            expected = {key: saved[key] for key in ("baseline", "intended")}
            if address in archived:
                archived_target = archived[address]
                if any(
                    archived_target[key] != saved[key]
                    for key in ("variant", "software", "definition_sha256")
                ):
                    raise ValueError("Archived restore source differs from the observed ECU")
                expected["archived"] = archived_target["baseline"]
            groups = {f"{did:04X}" for did in _groups(db, definitions)}
            for values in expected.values():
                if set(values) != groups:
                    raise ValueError(
                        f"ECU 0x{address:02X} record lacks the complete coding group set"
                    )
                db.validate_blocks(
                    definitions, {int(did, 16): bytes.fromhex(raw) for did, raw in values.items()}
                )
            headunit_reader = applies(address, definitions, db)
            if headunit_reader:
                if connection.read_only:
                    raise PermissionError("This ECU requires an available headunit reader session")
                check_write_conditions(connection, self.ecus, ctx)
                acknowledged = Event()
                self.sensitive_operation_requested.emit(acknowledged)
                while not acknowledged.wait(0.05):
                    ctx.remaining()
                sensitive = True
            run_prerequisites(
                address=address,
                variant=match["variant"],
                definitions=definitions,
                database=db,
                vin=vin,
                store=self.store,
                read=read,
                read_only=connection.read_only,
                context=ctx,
                transport=connection.kind,
            )
            blocks = {
                f"{did:04X}": raw.hex() for did, raw in _read_groups(db, definitions, read).items()
            }
            if read(b"\x22\xf1\x50") != identity or read(b"\x22\xf1\x01") != software:
                raise ValueError(f"ECU 0x{address:02X} identity changed during verification")
            differences = {
                key: [did for did in blocks if blocks[did] != values[did]]
                for key, values in expected.items()
            }
            observed["targets"].append(
                {
                    "address": address,
                    "variant": saved["variant"],
                    "identity": identity.hex(),
                    "software": software.hex(),
                    "definition_sha256": saved["definition_sha256"],
                    "blocks": blocks,
                    "differences": differences,
                    "different_groups": differences.get(basis, []),
                }
            )
            return b""

        try:
            for target in original["targets"]:
                address = target["address"]
                self.progress.emit(f"Verifying coding on ECU 0x{address:02X}...")
                connection.run_operation(
                    address,
                    lambda services, ctx, target=target: read_target(services, ctx, target),
                    context=context,
                )
        except Exception as error:
            if sensitive:
                connection.request_close()
            if not self.guard_notice and isinstance(error, (ValueError, PermissionError)):
                self.guard_notice = str(error)
            raise
        if basis == "both":
            state = record["events"][-1]["state"]
            lines = ["The operation remains interrupted. Observed coding groups:"]
            for target in observed["targets"]:
                differences = target["differences"]
                lines.append(
                    f"ECU 0x{target['address']:02X} · "
                    f"{len(differences['baseline'])} differ from original, "
                    f"{len(differences['intended'])} differ from intended."
                )
            message = "\n".join(lines)
        else:
            mismatch = any(target["different_groups"] for target in observed["targets"])
            expected_label = "original" if basis == "baseline" else "intended"
            comparison = "differs from" if mismatch else "matches"
            message = f"Observed coding {comparison} the saved {expected_label} bytes."
            state = "mismatch" if mismatch else "verified"
        if archived:
            archived_diff = [
                f"ECU 0x{target['address']:02X} · " + ", ".join(target["differences"]["archived"])
                for target in observed["targets"]
                if target["differences"].get("archived")
            ]
            if archived_diff:
                message += "\nGroups differing from the archived restore source:\n" + "\n".join(
                    archived_diff
                )
                if basis == "intended":
                    state = "mismatch"
            else:
                message += "\nObserved coding matches the archived restore source."
        logger.info("Coding verification backup=%s state=%s", self.path.name, state)
        report: dict[str, Any] = {
            "path": str(self.path),
            "state": state,
            "observed": observed,
            "instructions": message,
        }
        try:
            self.store.record(
                self.path,
                state=state,
                observed=observed,
                instructions=message,
                expected_sha256=record["sha256"],
            )
        except (OSError, ValueError):
            logger.exception("Could not save the observed coding comparison")
            report["persistence_failed"] = True
        return report


def validate_plan(plan: CodingPlan, db: CodingDatabase) -> dict:
    """Recompute source composition and identity before publishing a mutation."""
    data = plan.data()
    if (
        data.get("schema_version") != 1
        or data.get("mode") not in {"coding", "restore"}
        or not valid_vin(data.get("vin"))
    ):
        raise ValueError("Invalid coding plan")
    if did_data(bytes.fromhex(data.get("vin_observed", "")), 0xF190).decode("ascii") != data["vin"]:
        raise ValueError("Coding preparation is not bound to its observed VIN")
    if not data.get("targets") or data.get("composition") != "baseline-i":
        raise ValueError("Coding plan has no complete source-based target")
    derived_category = None
    order: dict[str, Any] = {}
    if "vehicle_order" in data:
        order = decode_vehicle_order(bytes.fromhex(data["vehicle_order"]))
        derived_category = db.category_for_model_range(order["model_range"], order["type_code"])
    if data.get("vehicle_context", {}).get("category") != derived_category:
        raise ValueError("Coding selection category is not bound to its source vehicle order")
    restore_targets: dict[int, dict] = {}
    if data["mode"] == "restore":
        origin = data.get("restore_origin", {})
        original = origin.get("original", {})
        if (
            hashlib.sha256(_canonical(original)).hexdigest() != origin.get("original_sha256")
            or original.get("kind") != "coding"
            or original.get("mode") != data.get("environment", {"mode": "live"})["mode"]
            or original.get("vin") != data["vin"]
            or not original.get("id")
        ):
            raise ValueError("Restore intent is not bound to a validated original backup")
        restore_targets = {item["address"]: item for item in original["targets"]}
        if set(restore_targets) != {target["address"] for target in data["targets"]}:
            raise ValueError("Restore intent target list differs from its original")
    seen = set()
    selected_addresses = {change["address"] for change in data.get("changes", [])}
    if selected_addresses != {target["address"] for target in data["targets"]}:
        raise ValueError("Coding targets differ from the reviewed selection")
    for target in data["targets"]:
        address = target["address"]
        if type(address) is not int or address in seen or not 0 <= address <= 0xFF:
            raise ValueError("Invalid coding target address")
        seen.add(address)
        software = bytes.fromhex(target["software"])
        definitions = list(decode_cafd_identifiers(software))
        if (
            definitions != target["definitions"]
            or _definition_digest(db, definitions) != target["definition_sha256"]
        ):
            raise ValueError("Coding definitions changed")
        match = DiagnosticCatalog().identify(address, bytes.fromhex(target["identity"]))
        if (
            match.get("identified") is not True
            or match.get("uds") is not True
            or match["variant"] != target["variant"]
            or match["name"] != target["name"]
            or match["address_index"] != target["address_index"]
        ):
            raise ValueError("Coding variant bytes differ from the exact source identity")
        scope_reason = db.easy_coding_block_reason(definitions)
        if scope_reason:
            raise PermissionError(scope_reason)
        resolutions = [db.definition_resolution(item) for item in definitions]
        if target.get("definition_resolution") != resolutions:
            raise ValueError("Coding source layout selection or reference metadata changed")
        if target.get("reader_prerequisites", {}).get("contract_sha256") != reader_contract()[1]:
            raise ValueError("Coding reader prerequisites are missing or changed")
        guards = guard_contracts(db, address)
        observations = target.get("guard_observations", [])
        if len(observations) != len(guards):
            raise ValueError("Coding plan omits a recovered source guard")
        for guard, observation in zip(guards, observations, strict=True):
            if (
                observation.get("guard_id") != guard["id"]
                or observation.get("address") != address
                or observation.get("contract_sha256")
                != hashlib.sha256(_canonical(guard)).hexdigest()
            ):
                raise ValueError("Coding source guard selection changed")
        auth = db.coding_write_authorization(bootloader_identifier(software))
        if auth["source_sha256"] != target["authorization_sha256"]:
            raise ValueError("Coding authorization definition changed")
        baseline = {int(did, 16): bytes.fromhex(raw) for did, raw in target["baseline"].items()}
        intended = {int(did, 16): bytes.fromhex(raw) for did, raw in target["intended"].items()}
        if (
            set(baseline) != set(_groups(db, definitions))
            or set(intended) != set(baseline)
            or any(not raw for raw in baseline.values())
        ):
            raise ValueError("Coding plan baseline is incomplete")
        db.validate_blocks(definitions, baseline)
        db.validate_blocks(definitions, intended)
        if data["mode"] == "coding":
            if target.get("preset_source_sha256") != db.source_sha256(
                db.primary_definition(definitions)[:8]
            ):
                raise ValueError("The curated coding source catalogue changed after confirmation")
            selected = [change for change in data["changes"] if change["address"] == address]
            expected = _finalize(
                db,
                _resolve_changes(
                    db,
                    selected,
                    definitions,
                    baseline,
                    variant_index=target["variant"],
                    vehicle_context={
                        **data.get("vehicle_context", {}),
                        "id8": db.id8_context(definitions, baseline),
                        "model_range": order.get("model_range", ""),
                        "type_code": order.get("type_code", ""),
                    },
                ),
                definitions,
                software,
            )
        else:
            saved = restore_targets[address]
            if (
                saved["variant"] != target["variant"]
                or saved["software"] != target["software"]
                or saved["definition_sha256"] != target["definition_sha256"]
            ):
                raise ValueError("Restore intent differs from its original ECU identity")
            original_blocks = {
                int(did, 16): bytes.fromhex(raw) for did, raw in saved["baseline"].items()
            }
            expected = _finalize(db, original_blocks, definitions, software)
        if address == 0x12 and intended.get(0x3010) != baseline.get(0x3010):
            raise ValueError("Coding changes a group excluded by the source engine writer")
        if expected != intended or any(
            len(intended[did]) != len(baseline[did]) for did in baseline
        ):
            raise ValueError("Coding composition differs from its source contract")
    return data


class _Rejected(Exception):
    """A correlated final ECU negative response, with no inferred acceptance."""

    def __init__(self, stage: str) -> None:
        super().__init__(f"ECU rejected the coding {stage} request")
        self.stage = stage


class CodingWriteWorker(CarWorker):
    """Execute one confirmed frozen plan with durable before/intent/step outcomes."""

    def __init__(
        self,
        connection: Any,
        plan: CodingPlan,
        store: OperationStore | None = None,
        *,
        power_acknowledged: bool = False,
        recovery_acknowledged: bool = False,
        ecus: list[dict] | None = None,
    ) -> None:
        """Retain the frozen plan and explicit power/recovery acknowledgements."""
        super().__init__(connection)
        self.plan = plan
        self.store = store or operation_store(connection)
        self.power_acknowledged = power_acknowledged
        self.recovery_acknowledged = recovery_acknowledged
        self.ecus = [dict(row) for row in ecus or ()]
        self._executed = False
        self.report: dict[str, Any] = {
            "path": "",
            "state": "not-started",
            "events": [],
            "instructions": _INSTRUCTIONS,
            "persistence_failed": False,
        }

    def do_work(self) -> dict[str, Any]:
        """Recheck baseline, then run complete source sequencing under one owner."""
        if self._executed:
            raise PermissionError("A coding operation cannot be replayed")
        self._executed = True
        connection = self.connection
        check_store(connection, self.store)
        if not self.power_acknowledged or getattr(connection, "power_sufficient", None) is False:
            raise PermissionError("Adequate vehicle/device power must be acknowledged")
        if connection.read_only or connection.kind != TransportKind.HSFZ or not connection.alive_ok:
            raise PermissionError("Coding requires a usable writable identified session")
        db = CodingDatabase()
        check_binding(connection, self.plan.data().get("environment"))
        data = validate_plan(self.plan, db)
        timed_readers = {
            target["address"]
            for target in data["targets"]
            if applies(target["address"], target["definitions"], db)
        }
        if connection.verified_vin != data["vin"]:
            raise PermissionError("Vehicle identity changed before coding")
        if data.get("prior_operations") and not self.recovery_acknowledged:
            raise PermissionError(
                "Review prior coding interruption and acknowledge the required cycle/comparison"
            )
        context = connection.context(600.0)
        try:
            path = self.store.prepare(
                kind="coding",
                mode=environment(connection).mode,
                vin=data["vin"],
                targets=[_target_record(t) for t in data["targets"]],
            )
        except (OSError, ValueError):
            logger.exception("Coding original and intent could not be saved")
            self.report.update(
                state="blocked",
                instructions=(
                    "Could not save the coding backup and intent. No coding write was sent. "
                    "Check local storage and review a new coding plan before trying again."
                ),
            )
            return self.report
        self.report["path"] = str(path)
        accepted: dict[int, dict[str, str]] = {}
        attempted_mutation = False
        rejected_stage = ""

        def check_conditions(ctx: OperationContext) -> None:
            try:
                notice = check_write_conditions(connection, self.ecus, ctx)
            except WriteConditionsBlocked as error:
                self.report["guard_notice"] = str(error)
                self.report["instructions"] = str(error) + " " + _INSTRUCTIONS
                raise
            self.report["write_conditions"] = notice
            try:
                self.store.record(
                    path,
                    state="writing",
                    responses=[{"kind": "write-conditions", "detail": notice}],
                )
            except (OSError, ValueError):
                self.report["persistence_failed"] = True
                raise

        def event(
            kind: str, address: int, request: bytes, response: bytes = b"", state: str = "sending"
        ) -> None:
            """Retain and durably journal each step before continuing execution."""
            record = {
                "kind": kind,
                "address": address,
                "request": request.hex(),
                "response": response.hex(),
                "state": state,
            }
            self.report["events"].append(record)
            try:
                self.store.record(path, state="writing", responses=[record])
            except (OSError, ValueError):
                self.report["persistence_failed"] = True
                raise

        def send(ctx: OperationContext, address: int, payload: bytes, kind: str) -> bytes:
            """Journal one bounded telegram and validate its final application response."""
            nonlocal attempted_mutation
            ctx.remaining()
            event(kind, address, payload)
            mutation = payload[0] in {0x2E, 0x11, 0x14}
            attempted_mutation |= mutation
            deadline = ctx.deadline
            timing = ctx.response_timing
            ctx.deadline = min(deadline, time.monotonic() + 30.0)
            if address in timed_readers and payload[:1] == b"\x22":
                ctx.response_timing = ENET_HEADUNIT_READ_TIMING
            try:
                try:
                    response = connection.send_uds(
                        address,
                        payload,
                        context=ctx,
                        raw=payload[0] == 0x27,
                        grant=frozenset({0x27}),
                    )
                except ProtocolFailure as error:
                    if error.kind != FailureKind.NEGATIVE or error.reconnect:
                        raise
                    response = error.raw
            finally:
                ctx.deadline = deadline
                ctx.response_timing = timing
            if response[:1] == b"\x7f":
                if len(response) != 3 or response[1] != payload[0] or response[2] == 0x78:
                    raise ValueError("Malformed final coding response")
                event(kind, address, payload, response, "rejected")
                raise _Rejected(kind)
            if kind == "session":
                valid = response[:2] == bytes((0x50, payload[1])) and len(response) in (2, 6)
            elif kind == "write" or kind == "stamp":
                valid = response == b"\x6e" + payload[1:3]
            elif kind == "reset":
                valid = response == b"\x51\x01"
            elif kind == "clear":
                valid = response == b"\x54"
            elif kind == "keepalive":
                valid = response == b"\x7e\x00"
            elif kind == "seed":
                valid = response[:2] == b"\x67\x01" and 2 < len(response) <= 4098
            elif kind == "key":
                valid = response == b"\x67\x02"
            else:
                valid = True
            if not valid:
                event(kind, address, payload, response, "uncertain")
                raise ValueError("Coding application response did not match the exact request")
            if kind == "write":
                accepted.setdefault(address, {})[payload[1:3].hex().upper()] = payload[3:].hex()
            event(kind, address, payload, response, "accepted")
            return bytes(response)

        def check(ctx: OperationContext, target: dict, expected: dict[str, str]) -> None:
            """Compare current identity, software and complete groups with expected bytes."""
            address = target["address"]
            if send(ctx, address, b"\x22\xf1\x50", "identity").hex() != target["identity"]:
                raise ValueError("Coding ECU identity changed")
            if send(ctx, address, b"\x22\xf1\x01", "software").hex() != target["software"]:
                raise ValueError("Coding ECU software changed")
            for did, raw in expected.items():
                request = b"\x22" + int(did, 16).to_bytes(2, "big")
                if did_data(send(ctx, address, request, "baseline"), int(did, 16)).hex() != raw:
                    raise ValueError("Coding current data changed; review a new plan")

        def program(
            ctx: OperationContext,
            target: dict,
            blocks: dict[str, str],
            current: dict[str, str] | None = None,
        ) -> None:
            """Run the source session, authorization, group and completion sequence."""
            address = target["address"]
            if address == 0x12 and blocks.get("3010") != (current or target["baseline"]).get(
                "3010"
            ):
                raise ValueError("Coding changes a source-excluded engine group")
            check_conditions(ctx)
            for session in (1, 3, 0x41):
                send(ctx, address, bytes((0x10, session)), "session")
            auth = db.authorization(bootloader_identifier(bytes.fromhex(target["software"])))
            seed = send(ctx, address, b"\x27\x01\xff\xff\xff\xff", "seed")[2:]
            send(ctx, address, b"\x27\x02" + derive_authorization_key(seed, auth), "key")
            primary = db.primary_definition(target["definitions"])[:8]
            metadata = [row for row in db.ecu_infos() if row.get("identifier") == primary]
            if len(metadata) > 1 and any(row != metadata[0] for row in metadata[1:]):
                raise ValueError("Coding ECU write metadata is ambiguous")
            partial = bool(metadata and metadata[0].get("partialCodingAllowed") is True)
            for group in _groups(db, target["definitions"]):
                if address == 0x12 and group == 0x3010:
                    continue
                did = f"{group:04X}"
                raw = blocks[did]
                if address != 0x12 and partial and raw == (current or target["baseline"])[did]:
                    continue
                # Source uses suppress-positive tester-present. The owner uses
                # the standard unsuppressed form so every reply remains owned.
                send(ctx, address, b"\x3e\x00", "keepalive")
                self.progress.emit(f"Coding {target['name']}: group {did}")
                send(
                    ctx,
                    address,
                    b"\x2e" + int(did, 16).to_bytes(2, "big") + bytes.fromhex(raw),
                    "write",
                )
            send(ctx, address, b"\x3e\x00", "keepalive")
            if address in {0x12, 0x50}:
                ctx.cancelled.wait(min(3.0, ctx.remaining()))
                ctx.remaining()
            send(ctx, address, b"\x2e\x37\xfe" + data["vin"][-7:].encode("ascii"), "stamp")
            send(
                ctx,
                address,
                b"\x10\x01" if address == 0x50 else b"\x11\x01",
                "session" if address == 0x50 else "reset",
            )
            send(ctx, address, b"\x14\xff\xff\xff", "clear")

        def execute(services: Any, ctx: OperationContext) -> bytes:
            """Recheck confirmed recovery evidence and fresh targets before programming."""
            nonlocal rejected_stage
            prior_now = _prior_records(
                self.store,
                data["vin"],
                {target["address"] for target in data["targets"]},
                ctx,
                exclude=path,
            )
            confirmed = {item["id"]: item["sha256"] for item in data.get("prior_operations", [])}
            if any(confirmed.get(item["id"]) != item["sha256"] for item in prior_now):
                raise ValueError(
                    "A coding interruption changed after confirmation; review a new comparison"
                )
            if prior_now and not self.recovery_acknowledged:
                raise PermissionError(
                    "A previous coding interruption requires explicit acknowledgement"
                )
            vin = did_data(send(ctx, 0x10, b"\x22\xf1\x90", "identity"), 0xF190).decode("ascii")
            if vin != data["vin"]:
                raise ValueError("Vehicle VIN changed")
            if (
                "vehicle_order" in data
                and send(ctx, 0x10, b"\x22\x3f\x06", "vehicle-order").hex() != data["vehicle_order"]
            ):
                raise ValueError("Vehicle order changed before coding")
            for target in data["targets"]:
                for guard, observation in zip(
                    guard_contracts(db, target["address"]),
                    target["guard_observations"],
                    strict=True,
                ):

                    def read_guard(payload: bytes, address: int = target["address"]) -> bytes:
                        """Read the selected guard through the journalled owner request path."""
                        return send(ctx, address, payload, "guard")

                    try:
                        observed = observe_guard(
                            self.store,
                            data["vin"],
                            guard,
                            read_guard,
                            expected=observation,
                        )
                        self.report.setdefault("guard_observations", []).append(observed)
                    except CodingGuardBlocked as error:
                        notice = f"{target['name']}: {error.user_message}"
                        if not attempted_mutation:
                            notice += " No coding write was sent."
                        self.report["guard_notice"] = notice
                        self.report["instructions"] = notice
                        raise
                    except Exception as error:
                        notice = (
                            f"{target['name']}: the required coding-condition check is unavailable. "
                            "No coding write was sent. Check the connection, local evidence and session log."
                        )
                        self.report["guard_notice"] = notice
                        self.report["instructions"] = notice
                        if isinstance(error, OSError):
                            self.report["persistence_failed"] = True
                        raise

                if (
                    send(ctx, target["address"], b"\x22\xf1\x50", "identity").hex()
                    != target["identity"]
                    or send(ctx, target["address"], b"\x22\xf1\x01", "identity").hex()
                    != target["software"]
                ):
                    raise ValueError("Coding target changed before source reader prerequisites")

                def read_prerequisite(
                    payload: bytes, override: int | None = None, *, address: int = target["address"]
                ) -> bytes:
                    """Route reader prerequisites through bounded, journalled owner requests."""
                    return send(
                        ctx,
                        address if override is None else override,
                        payload,
                        "reader-prerequisite",
                    )

                if target["address"] in timed_readers:
                    check_conditions(ctx)
                run_prerequisites(
                    address=target["address"],
                    variant=target["variant"],
                    definitions=target["definitions"],
                    database=db,
                    vin=data["vin"],
                    store=self.store,
                    read=read_prerequisite,
                    read_only=connection.read_only,
                    expected=target["reader_prerequisites"],
                    context=ctx,
                    transport=connection.kind,
                )
                check(ctx, target, target["baseline"])
            self.store.record(
                path, state="writing", responses=[{"kind": "frozen-plan", "plan": data}]
            )
            for target in data["targets"]:
                try:
                    program(ctx, target, target["intended"])
                except _Rejected as error:
                    # Keep automatic recovery within the group-write stage and
                    # the single target whose accepted transitions are known.
                    address = target["address"]
                    if error.stage != "write" or set(accepted) != {address}:
                        rejected_stage = error.stage
                        return b""
                    self.report["rollback_attempted"] = True
                    expected = {**target["baseline"], **accepted[address]}
                    try:
                        check(ctx, target, expected)
                        program(ctx, target, target["baseline"], current=expected)
                    except _Rejected as recovery_error:
                        rejected_stage = recovery_error.stage
                        return b""
                    self.report["state"] = "recovered"
                    self.report["instructions"] = (
                        "The ECU rejected a coding group. Original coding bytes were rewritten "
                        "with checked application responses. " + _INSTRUCTIONS
                    )
                    return b""
            return b""

        try:
            connection.run_operation(data["targets"][0]["address"], execute, context=context)
            if rejected_stage:
                self.report["state"] = "partial" if accepted else "rejected"
                if self.report.get("rollback_attempted"):
                    notice = f"Automatic recovery stopped at a rejected {rejected_stage} step. "
                elif rejected_stage == "clear":
                    notice = "Fault clearing was rejected after the coding activation response. "
                else:
                    notice = f"The ECU rejected the {rejected_stage} step. "
                self.report["instructions"] = notice + _INSTRUCTIONS
                connection.request_close()
            elif self.report["state"] != "recovered":
                self.report["state"] = "response-confirmed"
        except Exception:
            logger.warning(
                "Coding stopped; preserve original/intent and inspect outcomes", exc_info=True
            )
            self.report["state"] = (
                ("partial" if attempted_mutation else "blocked")
                if self.report.get("guard_notice")
                else "uncertain"
                if attempted_mutation
                else "mismatch"
            )
            if attempted_mutation or self.report["persistence_failed"]:
                connection.request_close()
        final = self.report["state"]
        try:
            self.store.record(
                path,
                state="mismatch" if final in {"rejected", "blocked"} else final,
                instructions=self.report["instructions"],
            )
        except (OSError, ValueError):
            self.report["persistence_failed"] = True
            connection.request_close()
        return self.report
