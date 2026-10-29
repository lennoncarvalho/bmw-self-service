"""Exact-identity coding snapshots from the recovered F101/data-group read path.

Full preset selection, authorization and mutation are separate contracts. Opaque
bytes returned here are a real read, not a synthesized preset or write permission.
"""

import hashlib
import json
import logging
import time
from typing import Any

from app.coding_db import _decrypt_enc
from app.operation_store import OperationStore
from app.resources import resource_path
from app.vehicle import did_data
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
        for ecu in self.ecus:
            row: dict[str, Any] = {
                "name": ecu.get("name", "ECU"),
                "state": "not-attempted",
                "definitions": [],
                "blocks": {},
                "backup": "",
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
                response = self._read(address, b"\x22\xf1\x01")
                definitions = decode_cafd_identifiers(response)
                row["definitions"] = list(definitions)
                if not definitions:
                    row["state"] = "No coding definition reported"
                    continue
                groups: set[int] = set()
                hashes = []
                for definition in definitions:
                    path = resource_path(f"coding_data/{definition}.enc")
                    if not path.is_file():
                        raise ValueError(
                            "Exact reported coding definition is not available locally"
                        )
                    hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
                    data = json.loads(_decrypt_enc(str(path)))
                    for group in data["dataGroups"]:
                        did = int(group["address"], 0)
                        if not 0 <= did <= 0xFFFF:
                            raise ValueError("Coding group address exceeds the supported width")
                        groups.add(did)
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
                    if not raw:
                        raise ValueError("Coding group returned no bytes")
                    blocks[f"{did:04X}"] = raw.hex()
                # Reidentify before publication; all groups must belong to the
                # same software snapshot rather than a changing ECU definition.
                observed = self._read(address, b"\x22\xf1\x01")
                if observed != response:
                    raise ValueError("Coding software identity changed while reading")
                target = {
                    "address": address,
                    "variant": ecu["variant"],
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
                    instructions="Read-only coding snapshot. No vehicle write was requested. Restoration is unavailable until its exact operation contract is implemented.",
                )
                row["backup"] = str(path)
                row["state"] = "All reported groups read; snapshot saved"
            except (OSError, ValueError, KeyError, TypeError, ConnectionError, TimeoutError):
                logger.warning("Coding snapshot unavailable address=%04X", address, exc_info=True)
                row["state"] = "Coding snapshot incomplete; see session log"
        return results
