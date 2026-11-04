"""Exact-identity coding snapshots from the recovered F101/data-group read path.

Full preset selection, authorization and mutation are separate contracts. Opaque
bytes returned here are a real read, not a synthesized preset or write permission.
"""

import hashlib
import logging
import time
from threading import Event
from typing import Any

from PySide6.QtCore import Signal

from app.coding_db import CodingDatabase
from app.coding_prerequisites import applies, run_prerequisites
from app.operation_store import OperationStore
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


class CodingSnapshotWorker(CarWorker):
    """Read all groups of exact matching definitions and save complete snapshots.

    Each F101/group read has a 30-second budget including queueing, within a
    five-minute page batch. Partial reads
    remain visible but never become a supposedly complete restorable backup.
    """

    sensitive_operation_requested = Signal(object)

    def __init__(self, connection: Any, ecus: list[dict], vin: str) -> None:
        super().__init__(connection)
        self.ecus = [dict(ecu) for ecu in ecus]
        self.vin = vin
        self._deadline = 0.0

    def _read(self, address: int, payload: bytes) -> bytes:
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Coding snapshot batch budget exhausted")
        result: bytes = self.connection.send_uds(address, payload, timeout=min(30.0, remaining))
        return result

    def do_work(self) -> list[dict]:
        """Return a settled batch of real coding bytes and exact coverage reasons."""
        self._deadline = time.monotonic() + 300.0
        results = []
        database = CodingDatabase()
        for ecu in self.ecus:
            row: dict[str, Any] = {
                "name": ecu.get("name", "ECU"),
                "state": "not-attempted",
                "definitions": [],
                "blocks": {},
                "backup": "",
                "presets": [],
            }
            results.append(row)
            if not ecu.get("identified") or not ecu.get("uds"):
                row["state"] = "Variant not identified with a supported protocol"
                continue
            if self.isInterruptionRequested() or not self.connection.alive_ok:
                continue
            address = int(str(ecu["addr"]), 0)
            self.progress.emit(f"Reading coding identity: {row['name']}...")
            try:
                identity = self._read(address, b"\x22\xf1\x50")
                match = DiagnosticCatalog().identify(address, identity)
                if (
                    not match.get("identified")
                    or not match.get("uds")
                    or match["variant"] != ecu.get("variant")
                    or match["name"] != ecu.get("name")
                ):
                    raise ValueError("Coding ECU identity changed since inventory")
                response = self._read(address, b"\x22\xf1\x01")
                definitions = decode_cafd_identifiers(response)
                row["definitions"] = list(definitions)
                row["definition_resolution"] = [
                    database.definition_resolution(definition) for definition in definitions
                ]
                if not definitions:
                    row["state"] = "No coding definition reported"
                    continue
                store = OperationStore()
                if applies(address, list(definitions), database):
                    if self.connection.read_only:
                        raise PermissionError(
                            "Headunit reader prerequisites require writable access"
                        )
                    acknowledged = Event()
                    self.sensitive_operation_requested.emit(acknowledged)
                    while not acknowledged.wait(0.05):
                        if self.isInterruptionRequested() or time.monotonic() >= self._deadline:
                            raise TimeoutError(
                                "Coding reader prerequisite lockout was not acquired"
                            )

                def prerequisites(
                    services: Any,
                    context: Any,
                    *,
                    row: dict = row,
                    address: int = address,
                    match: dict = match,
                    definitions: tuple[str, ...] = definitions,
                    store: OperationStore = store,
                ) -> bytes:
                    def read_prerequisite(payload: bytes, override: int | None = None) -> bytes:
                        deadline = context.deadline
                        context.deadline = min(deadline, time.monotonic() + 30.0)
                        try:
                            return self._read(address if override is None else override, payload)
                        finally:
                            context.deadline = deadline

                    observed_vin = did_data(read_prerequisite(b"\x22\xf1\x90", 0x10), 0xF190)
                    if observed_vin.decode("ascii") != self.vin:
                        raise ValueError("Vehicle VIN changed before headunit prerequisites")

                    row["reader_prerequisites"] = run_prerequisites(
                        address=address,
                        variant=match["variant"],
                        definitions=list(definitions),
                        database=database,
                        vin=self.vin,
                        store=store,
                        read=read_prerequisite,
                        read_only=self.connection.read_only,
                    )
                    return b""

                self.connection.run_operation(
                    address,
                    prerequisites,
                    context=self.connection.context(max(0.001, self._deadline - time.monotonic())),
                )
                groups: set[int] = set()
                group_minimums: dict[int, int] = {}
                group_sizes: dict[int, int] = {}
                hashes = []
                for definition in definitions:
                    cafd_id, variant = definition.split("-", 1)
                    if not database.has_definition(cafd_id, variant):
                        raise ValueError(
                            "Exact reported coding definition is not available locally"
                        )
                    hashes.append(database.source_sha256(definition))
                    data = database.get_definition(cafd_id, variant)
                    for group in data["dataGroups"]:
                        did = int(group["address"], 0)
                        if not 0 <= did <= 0xFFFF:
                            raise ValueError("Coding group address exceeds the supported width")
                        groups.add(did)
                        minimum = max(
                            (
                                int(function["storageInfo"]["end"]) + 1
                                for function in group.get("functions", [])
                            ),
                            default=1,
                        )
                        group_minimums[did] = max(group_minimums.get(did, 1), minimum)
                        size = group.get("units")
                        if size is not None:
                            if type(size) is not int or not 0 < size <= 65536:
                                raise ValueError("Coding group has an invalid declared byte count")
                            if did in group_sizes and group_sizes[did] != size:
                                raise ValueError("Coding definitions disagree on the group size")
                            group_sizes[did] = size
                if not groups:
                    raise ValueError("Coding definition has no readable groups")
                blocks: dict[str, str] = {}
                row["blocks"] = blocks
                for did in sorted(groups):
                    if self.isInterruptionRequested():
                        raise ValueError("Coding snapshot interrupted before completion")
                    self.progress.emit(f"Reading {row['name']}: group {did:04X}...")
                    raw = did_data(
                        self._read(address, b"\x22" + did.to_bytes(2, "big")),
                        did,
                    )
                    if len(raw) < group_minimums[did] or (
                        did in group_sizes and len(raw) != group_sizes[did]
                    ):
                        raise ValueError("Coding group returned incomplete source-defined bytes")
                    blocks[f"{did:04X}"] = raw.hex()
                # Reidentify before publication; all groups must belong to the
                # same software snapshot rather than a changing ECU definition.
                observed = self._read(address, b"\x22\xf1\x01")
                if observed != response or self._read(address, b"\x22\xf1\x50") != identity:
                    raise ValueError("Coding software identity changed while reading")
                target = {
                    "address": address,
                    "variant": match["variant"],
                    "software": response.hex(),
                    "definition_sha256": hashlib.sha256("".join(hashes).encode()).hexdigest(),
                    "baseline": blocks,
                    "intended": dict(blocks),
                }
                store = OperationStore()
                path = store.prepare(kind="coding", mode="live", vin=self.vin, targets=[target])
                store.record(
                    path,
                    state="verified",
                    observed={str(address): blocks},
                    responses=[
                        {
                            "kind": "definition-selection",
                            "selections": row["definition_resolution"],
                        }
                    ],
                    instructions="Complete coding snapshot. No coding write was requested. Any separately retrieved entitlement material is stored independently; restoration requires fresh identity and baseline checks.",
                )
                row["backup"] = str(path)
                byte_blocks = {int(did, 16): bytes.fromhex(raw) for did, raw in blocks.items()}
                presets = []
                for definition in (database.primary_definition(list(definitions)),):
                    cafd_id, variant = definition.split("-", 1)
                    database.load_ecu(cafd_id, variant)
                    for preset in database.get_presets(cafd_id):
                        if preset.get("type", 0):
                            try:
                                preset = database.resolve_dynamic_preset(
                                    preset,
                                    byte_blocks,
                                    cafd_id,
                                    variant,
                                    definitions=list(definitions),
                                )
                            except (ValueError, KeyError, TypeError):
                                logger.info("Dynamic source option unavailable: %s", preset["name"])
                        current = database.get_current_option(
                            preset, byte_blocks, cafd_id, variant, definitions=list(definitions)
                        )
                        mapped, mapping_reason = database.preset_mapping_status(
                            preset, cafd_id, variant, byte_blocks, definitions=list(definitions)
                        )
                        label = next(
                            (
                                option["label"]
                                for option in preset["options"]
                                if option["name"] == current
                            ),
                            "Custom / no unique option"
                            if mapped
                            else "Definition mapping unavailable",
                        )
                        predicates = {
                            key: preset[key]
                            for key in (
                                "series",
                                "excludedSeries",
                                "excludeECUVariants",
                                "supportedForID8",
                            )
                            if key in preset
                        }
                        presets.append(
                            {
                                "address": address,
                                "definition": definition,
                                "id": preset["name"],
                                "source_index": preset["source_index"],
                                "label": preset["label"],
                                "section": preset["section"],
                                "current": current,
                                "current_label": label,
                                "options": [option["label"] for option in preset["options"]],
                                "choices": [
                                    {"name": option["name"], "label": option["label"]}
                                    for option in preset["options"]
                                ],
                                "predicates": predicates,
                                "mapping_supported": mapped,
                                "mapping_reason": mapping_reason,
                                "type": preset.get("type", 0),
                            }
                        )
                row["presets"] = presets
                row["state"] = "All reported groups read; snapshot saved"
            except (OSError, ValueError, KeyError, TypeError, ConnectionError, TimeoutError):
                logger.warning("Coding snapshot unavailable address=%04X", address, exc_info=True)
                row["state"] = "Coding snapshot incomplete; see session log"
        return results
