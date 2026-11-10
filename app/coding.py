"""Bounded coding catalogue discovery and on-demand source-group reads."""

import copy
import logging
import time
from threading import Event
from typing import Any

from PySide6.QtCore import Signal

from app.coding_db import CodingDatabase
from app.coding_prerequisites import ENET_READER_TIMING, applies, reader_contract, run_prerequisites
from app.operation_store import OperationStore
from app.protocol.contracts import TransportKind
from app.vehicle import DiagnosticCatalog, did_data
from app.worker import CarWorker

logger = logging.getLogger(__name__)


def decode_cafd_identifiers(response: bytes) -> tuple[str, ...]:
    """Decode the F101 response's trailing role-tagged eight-byte identifiers."""
    did_data(response, 0xF101)
    if len(response) < 8:
        raise ValueError("Incomplete coding software identity")
    count = response[6]
    if len(response) < 8 + count * 8:
        raise ValueError("Incomplete coding identifier table")
    identifiers = []
    for index in range(count):
        entry = response[len(response) - (index + 1) * 8 : len(response) - index * 8]
        if entry[0] == 5:
            identifier = int.from_bytes(entry[1:5], "big")
            identifiers.append(f"{identifier:08X}-{entry[5]:03d}-{entry[6]:03d}-{entry[7]:03d}")
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Duplicate coding definition identity")
    return tuple(identifiers)


class CodingCatalogueWorker(CarWorker):
    """Read identities only; discovering options never reads coding groups or sessions."""

    def __init__(self, connection: Any, ecus: list[dict], vin: str) -> None:
        """Copy the inventory for a five-minute batch of bounded identity reads."""
        super().__init__(connection)
        self.ecus = copy.deepcopy(ecus)
        self.vin = vin
        self._deadline = 0.0
        self._stage = "catalogue"
        self._timed_address: int | None = None

    def _read(self, address: int, payload: bytes) -> bytes:
        """Log and cap one request without extending the current batch deadline."""
        remaining = self._deadline - time.monotonic()
        if self.isInterruptionRequested():
            raise ConnectionError("Coding read cancelled")
        if remaining <= 0:
            raise TimeoutError("Coding read batch budget exhausted")
        logger.debug(
            "Coding request conn=%s stage=%s ecu=0x%04X data=%s remaining=%.3f",
            getattr(self.connection, "trace_id", "unknown"),
            self._stage,
            address,
            payload.hex(" "),
            remaining,
        )
        context = self.connection.context(min(30.0, remaining))
        if address == self._timed_address:
            context.response_timing = ENET_READER_TIMING
        result: bytes = self.connection.send_uds(address, payload, context=context)
        return result

    def _identity(self, ecu: dict, *, stage: str = "identity") -> tuple[bytes, bytes, list[str]]:
        """Reidentify the exact ECU and its complete reported coding software table."""
        address = int(str(ecu["addr"]), 0)
        self._stage = f"{stage}-F150"
        identity = self._read(address, b"\x22\xf1\x50")
        match = DiagnosticCatalog().identify(address, identity)
        if (
            not match.get("identified")
            or not match.get("uds")
            or match["variant"] != ecu.get("variant")
            or match["name"] != ecu.get("name")
        ):
            raise ValueError("Coding ECU identity changed since inventory")
        self._stage = f"{stage}-F101"
        software = self._read(address, b"\x22\xf1\x01")
        return identity, software, list(decode_cafd_identifiers(software))

    def do_work(self) -> list[dict]:
        """Return named source catalogues with explicit unavailable/untouched coverage."""
        self._deadline = time.monotonic() + 300.0
        database = CodingDatabase()
        if self.connection.kind == TransportKind.HSFZ:
            self._timed_address = reader_contract()[0]["unlock_backup"]["address"]
        rows: list[dict] = []
        logger.info(
            "Coding catalogue begin conn=%s targets=%s values_requested=False",
            getattr(self.connection, "trace_id", "unknown"),
            [ecu.get("addr") for ecu in self.ecus],
        )
        for ecu in self.ecus:
            row: dict[str, Any] = {
                **ecu,
                "state": "Not read",
                "definitions": [],
                "blocks": {},
                "presets": [],
                "available": False,
                "loaded": False,
                "expanded": False,
            }
            rows.append(row)
            if not ecu.get("identified") or not ecu.get("uds"):
                row["state"] = "Variant not identified with a supported protocol"
                continue
            if self.isInterruptionRequested():
                row["state"] = "Not read: coding read cancelled"
                continue
            if not self.connection.alive_ok:
                row["state"] = "Not read: connection unavailable; reconnect before reading again"
                continue
            if time.monotonic() >= self._deadline:
                row["state"] = "Not read: coding catalogue time limit reached"
                continue
            self.progress.emit(f"Identifying coding options: {row['name']}...")
            try:
                identity, software, definitions = self._identity(ecu, stage="catalogue")
                row.update(
                    identity=identity.hex(), software=software.hex(), definitions=definitions
                )
                if not definitions:
                    row["state"] = "No coding definition reported"
                    continue
                primary = database.primary_definition(definitions)
                # Loading the root names does not require a car baseline or even
                # reading a secondary layout that has no Easy Coding options.
                database.load_ecu(primary[:8], primary[9:])
                presets = database.get_presets(primary[:8])
                row.update(
                    definition_resolution=[database.definition_resolution(primary)],
                    preset_count=len(presets),
                    available=bool(presets),
                    state=(
                        f"{len(presets)} source options; current values not read"
                        if presets
                        else "No named Easy Coding options in the supplied catalogue"
                    ),
                )
            except (OSError, ValueError, KeyError, TypeError):
                logger.warning(
                    "Coding catalogue unavailable conn=%s ecu=%s stage=%s",
                    getattr(self.connection, "trace_id", "unknown"),
                    ecu.get("addr"),
                    self._stage,
                    exc_info=True,
                )
                row["state"] = "Coding catalogue unavailable; see session log"
            logger.debug("Coding catalogue result ecu=%s state=%s", ecu.get("addr"), row["state"])
        logger.info(
            "Coding catalogue settled targets=%d available=%d",
            len(rows),
            sum(bool(row["available"]) for row in rows),
        )
        return rows


class CodingValuesWorker(CodingCatalogueWorker):
    """Read only one opened ECU's mapped Easy Coding groups; never create a backup."""

    sensitive_operation_requested = Signal(object)

    def __init__(self, connection: Any, row: dict, vin: str) -> None:
        """Retain the exact catalogue identity for this on-demand value batch."""
        super().__init__(connection, [row], vin)
        self.row = copy.deepcopy(row)
        self._stage = "identity"

    def do_work(self) -> list[dict]:
        """Return current values without treating partial display bytes as a write baseline."""
        self._deadline = time.monotonic() + 300.0
        database = CodingDatabase()
        row = self.row
        row.update(blocks={}, presets=[], loaded=False, expanded=True)
        sensitive = False
        address = int(str(row["addr"]), 0)
        logger.info(
            "Coding values begin conn=%s ecu=0x%04X variant=%s definitions=%s",
            getattr(self.connection, "trace_id", "unknown"),
            address,
            row.get("variant"),
            row["definitions"],
        )
        try:
            if self.connection.kind == TransportKind.HSFZ and applies(
                address, row["definitions"], database
            ):
                self._timed_address = address
            self.progress.emit(f"Checking coding identity: {row['name']}...")
            identity, software, definitions = self._identity(row)
            if identity.hex() != row["identity"] or software.hex() != row["software"]:
                row["available"] = False
                raise ValueError("Coding software changed; reconnect to identify its options again")
            primary = database.primary_definition(definitions)
            database.load_ecu(primary[:8], primary[9:])
            presets = database.get_presets(primary[:8])
            groups: set[int] = set()
            reasons: dict[int, str] = {}
            for index, preset in enumerate(presets):
                try:
                    groups.update(
                        database.preset_read_groups(preset, primary, definitions=definitions)
                    )
                except (ValueError, KeyError, TypeError) as exc:
                    reasons[index] = str(exc)
            logger.info(
                "Coding group plan conn=%s ecu=0x%04X groups=%s options=%d unmapped=%d",
                getattr(self.connection, "trace_id", "unknown"),
                address,
                [f"{did:04X}" for did in sorted(groups)],
                len(presets),
                len(reasons),
            )
            row["definition_resolution"] = [
                database.definition_resolution(item) for item in definitions
            ]
            bounds: dict[int, tuple[int, int | None]] = {}
            for definition in definitions:
                data = database.get_definition(definition[:8], definition[9:])
                for group in data["dataGroups"]:
                    did = int(str(group["address"]), 0)
                    if did not in groups:
                        continue
                    minimum = max(
                        (
                            int(function["storageInfo"]["end"]) + 1
                            for function in group.get("functions", [])
                        ),
                        default=1,
                    )
                    size = group.get("units")
                    if size is not None and (type(size) is not int or not 0 < size <= 65536):
                        raise ValueError("Coding group has an invalid source byte count")
                    old_minimum, old_size = bounds.get(did, (1, None))
                    if old_size is not None and size is not None and old_size != size:
                        raise ValueError("Coding definitions disagree on the group size")
                    bounds[did] = max(minimum, old_minimum), size if size is not None else old_size
            if groups and applies(address, definitions, database):
                if self.connection.read_only:
                    raise PermissionError("Headunit reader prerequisites require writable access")
                permission = Event()
                self.sensitive_operation_requested.emit(permission)
                while not permission.wait(0.05):
                    if self.isInterruptionRequested() or not self.connection.alive_ok:
                        raise ConnectionError("Coding read stopped before reader prerequisites")
                    if time.monotonic() >= self._deadline:
                        raise TimeoutError("Coding reader lockout was not acquired")
                sensitive = True
            if groups:
                self._stage = "reader-prerequisites"
                self.progress.emit(f"Checking reader prerequisites: {row['name']}...")

                def prerequisites(services: Any, context: Any) -> bytes:
                    """Run sourced reader controls under one bounded protocol owner."""

                    def read(payload: bytes, override: int | None = None) -> bytes:
                        """Bound nested requests while preserving the owner's outer deadline."""
                        deadline = context.deadline
                        context.deadline = min(deadline, time.monotonic() + 30.0)
                        try:
                            return self._read(address if override is None else override, payload)
                        finally:
                            context.deadline = deadline

                    if did_data(read(b"\x22\xf1\x90", 0x10), 0xF190).decode("ascii") != self.vin:
                        raise ValueError("Vehicle VIN changed before coding values were read")
                    run_prerequisites(
                        address=address,
                        variant=row["variant"],
                        definitions=definitions,
                        database=database,
                        vin=self.vin,
                        store=OperationStore(),
                        read=read,
                        read_only=self.connection.read_only,
                        context=context,
                        transport=self.connection.kind,
                    )
                    return b""

                self.connection.run_operation(
                    address,
                    prerequisites,
                    context=self.connection.context(max(0.001, self._deadline - time.monotonic())),
                )
            for did in sorted(groups):
                self._stage = f"group-{did:04X}"
                self.progress.emit(f"Reading {row['name']}: group {did:04X}...")
                block = did_data(self._read(address, b"\x22" + did.to_bytes(2, "big")), did)
                minimum, size = bounds[did]
                if len(block) < minimum or (size is not None and len(block) != size):
                    raise ValueError("Coding group returned incomplete source-defined bytes")
                row["blocks"][f"{did:04X}"] = block.hex()
            self._stage = "final-identity"
            final_identity, final_software, _ = self._identity(row, stage="final-identity")
            if final_identity != identity or final_software != software:
                row["available"] = False
                raise ValueError("Coding software changed during the value read")
            blocks = {int(did, 16): bytes.fromhex(value) for did, value in row["blocks"].items()}
            for index, preset in enumerate(presets):
                reason = reasons.get(index, "")
                if not reason and preset.get("type", 0):
                    try:
                        preset = database.resolve_dynamic_preset(
                            preset, blocks, primary[:8], primary[9:], definitions=definitions
                        )
                    except (ValueError, KeyError, TypeError) as exc:
                        reason = str(exc)
                mapped, mapping_reason = database.preset_mapping_status(
                    preset, primary[:8], primary[9:], blocks, definitions=definitions
                )
                mapped = mapped and not reason
                current = (
                    database.get_current_option(
                        preset, blocks, primary[:8], primary[9:], definitions=definitions
                    )
                    if mapped
                    else None
                )
                row["presets"].append(
                    {
                        "address": address,
                        "definition": primary,
                        "id": preset["name"],
                        "source_index": preset["source_index"],
                        "label": preset["label"],
                        "section": preset["section"],
                        "current": current,
                        "current_label": next(
                            (
                                option["label"]
                                for option in preset["options"]
                                if option["name"] == current
                            ),
                            "Custom / no unique option"
                            if mapped
                            else "Definition mapping unavailable",
                        ),
                        "options": [option["label"] for option in preset["options"]],
                        "choices": [
                            {"name": option["name"], "label": option["label"]}
                            for option in preset["options"]
                        ],
                        "mapping_supported": mapped,
                        "mapping_reason": reason or mapping_reason,
                        "predicates": {
                            key: preset[key]
                            for key in (
                                "series",
                                "excludedSeries",
                                "excludeECUVariants",
                                "supportedForID8",
                            )
                            if key in preset
                        },
                    }
                )
            row.update(
                loaded=True,
                state=(
                    f"Current values read from {len(groups)} Easy Coding group(s)"
                    if groups
                    else "No option has a readable source mapping"
                ),
            )
        except (OSError, ValueError, KeyError, TypeError) as exc:
            logger.warning(
                "Coding values unavailable conn=%s ecu=0x%04X stage=%s groups_retained=%s alive=%s",
                getattr(self.connection, "trace_id", "unknown"),
                address,
                self._stage,
                list(row["blocks"]),
                self.connection.alive_ok,
                exc_info=True,
            )
            if sensitive and isinstance(exc, (ConnectionError, TimeoutError)):
                self.connection.request_close()
            row["presets"] = []
            if isinstance(exc, PermissionError):
                row["state"] = (
                    "Current values require reader prerequisites disabled in read-only mode"
                )
            elif not row["available"]:
                row["state"] = "Coding software changed; reconnect to identify its options again"
            else:
                row["state"] = (
                    "Current values unavailable; reconnect before trying again"
                    if not self.connection.alive_ok
                    else "Current values unavailable; see session log"
                )
        logger.info(
            "Coding values settled conn=%s ecu=0x%04X loaded=%s stage=%s groups=%d",
            getattr(self.connection, "trace_id", "unknown"),
            address,
            row["loaded"],
            self._stage,
            len(row["blocks"]),
        )
        return [row]
