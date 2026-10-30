"""Vehicle inventory and identification recovered from diagnostic reference artifacts.

Contract/provenance: docs/evidence/task-b-recovered-contracts.md. These reads do
not infer transport, software identity or write capability from a chassis hint.
"""

import gzip
import json
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from app.protocol.contracts import TransportKind
from app.resources import resource_path
from app.vehicle_order import read_vehicle_order

logger = logging.getLogger(__name__)


def mil_contracts() -> dict[str, dict[str, Any]]:
    """Load exact engine selection and read dispositions from embedded definitions."""
    path = resource_path("coding_data/mil_contracts.json")
    with path.open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError("MIL definitions exceed their supported size")
    data = json.loads(raw)
    if data.get("schema") != 1 or not isinstance(data.get("engines"), dict):
        raise ValueError("Unsupported MIL definition format")
    if any(not isinstance(row, dict) for row in data["engines"].values()):
        raise ValueError("Invalid MIL engine definition")
    return cast(dict[str, dict[str, Any]], data["engines"])


def decode_mil(response: bytes, did: int = 0x4A69) -> bool:
    """Decode one exact scalar MIL condition; unknown request values stay unavailable."""
    data = did_data(response, did)
    if len(data) != 1 or data[0] not in (0, 1):
        raise ValueError("Vehicle MIL response has an unsupported value or shape")
    return data[0] == 1


def select_mil_contract(ecus: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the unique identified engine and its exact definition, or explain why not."""
    engines = [row for row in ecus if row.get("addr") == "0x12"]
    if len(engines) != 1 or engines[0].get("identified") is not True:
        raise LookupError("No unique identified engine for an emissions MIL read")
    engine = engines[0]
    contract = mil_contracts().get(engine.get("address_index", ""), {})
    if contract.get("name") != engine.get("name"):
        raise LookupError("No verified MIL read contract for the identified engine")
    state = contract.get("state")
    if state not in ("scalar-boolean", "dynamic-block"):
        reasons = {
            "missing-definition": "MIL engine definition is not present in the supplied data",
            "no-direct-mil-row": "MIL direct-read mapping is not recovered for this engine",
        }
        raise LookupError(reasons.get(str(state), "MIL engine decoder is unavailable"))
    did = contract.get("did")
    if type(did) is not int or not 0 <= did <= 0xFFFF:
        raise ValueError("Invalid MIL read definition")
    return engine, contract


def read_mil(connection: Any, ecus: list[dict[str, Any]]) -> dict[str, object]:
    """Read an actual MIL condition only after an exact engine definition match.

    Dynamic-slot engines need a confirmed, exclusive configuration sequence
    (app/mil_block.py); ordinary overview refresh never defines a DID.
    """
    if getattr(connection, "kind", None) != TransportKind.HSFZ:
        return {"on": None, "detail": "MIL mapping for this transport is not yet implemented"}
    try:
        engine, contract = select_mil_contract(ecus)
    except LookupError as exc:
        return {"on": None, "detail": str(exc)}
    did = contract["did"]
    if contract["state"] == "dynamic-block":
        return {
            "on": None,
            "detail": f"Engine {engine['name']} reports MIL only through a temporary data "
            "definition — use Read MIL to run it",
            "action": "dynamic-block",
        }
    on = decode_mil(connection.send_uds(0x12, b"\x22" + did.to_bytes(2, "big"), timeout=30.0), did)
    return {
        "on": on,
        "detail": f"Engine {engine['name']} reports the MIL condition; not a physical lamp check",
        "observed_clock": time.monotonic(),
    }


def did_data(response: bytes, did: int) -> bytes:
    """Validate a positive DID echo and retain its complete opaque data."""
    if len(response) < 3 or response[:3] != b"\x62" + did.to_bytes(2, "big"):
        raise ValueError("Vehicle returned an unavailable or invalid data response")
    return response[3:]


def decode_inventory(response: bytes) -> tuple[int, ...]:
    """Decode gateway 3F07's BE16 byte count and one-byte ECU addresses."""
    data = did_data(response, 0x3F07)
    if len(data) < 2 or int.from_bytes(data[:2], "big") != len(data) - 2:
        raise ValueError("Vehicle ECU inventory has an invalid length")
    addresses = tuple(data[2:])
    if len(set(addresses)) != len(addresses):
        raise ValueError("Vehicle ECU inventory contains duplicate addresses")
    return addresses


def decode_ilevel(response: bytes) -> str:
    """Decode the three eight-byte integration levels returned by gateway 100B."""
    # The coding source requires at least three blocks and ignores any trailer
    # (FSeriesVehicleInterface s0$c.b); the owner's F48 gateway returns 15 more.
    data = did_data(response, 0x100B)
    if len(data) < 24:
        raise ValueError("Vehicle software level has an unsupported format")
    levels = []
    for offset in (0, 8, 16):
        block = data[offset : offset + 8]
        family = block[:4].decode("ascii")
        if not family.isalnum():
            raise ValueError("Vehicle software family has an invalid format")
        levels.append(
            f"{family}-{block[4]:02d}-{block[5]:02d}-{int.from_bytes(block[6:], 'big'):03d}"
        )
    return " / ".join(levels)


def decode_voltage(response: bytes) -> float:
    """Decode the source's 31-byte DME 402B voltage response, in volts."""
    did_data(response, 0x402B)
    if len(response) != 31:
        raise ValueError("Vehicle voltage has an unsupported format")
    return int.from_bytes(response[5:7], "big") * 0.00025 + 6.0


class DiagnosticCatalog:
    """Exact address/variant definitions and English fault descriptions."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or resource_path("coding_data/diagnostic_catalog.json.gz")
        self.variants: dict[str, dict[str, Any]] = {}
        self.descriptions: dict[str, dict[str, str]] = {}
        self.info_descriptions: dict[str, dict[str, str]] = {}
        if self.path.exists():
            data = json.loads(gzip.decompress(self.path.read_bytes()))
            if data.get("schema") != 1:
                raise ValueError("Unsupported diagnostic catalog version")
            self.variants = data["variants"]
            self.descriptions = data["descriptions"]
            self.info_descriptions = data["info_descriptions"]

    def uds_addresses(self) -> tuple[int, ...]:
        """Return all distinct source-catalogue UDS addresses for identity fallback.

        These are candidates, not installed/discovered vehicle ECUs. Non-UDS
        catalogue rows never authorize a UDS identity probe.
        """
        return tuple(
            sorted({int(key.split()[0], 16) for key, row in self.variants.items() if row["uds"]})
        )

    def identify(self, address: int, response: bytes) -> dict[str, Any]:
        """Match the F150 three-byte identifier against the exact address index."""
        data = did_data(response, 0xF150)
        if len(data) < 3:
            raise ValueError("Vehicle returned an incomplete ECU variant identity")
        variant = data[:3].hex().upper()
        key = f"{address:02X} {variant}"
        match = self.variants.get(key)
        result: dict[str, Any] = {
            "addr": hex(address),
            "variant": variant,
            "address_index": key,
            "name": f"ECU {address:02X}",
            "description": "Unknown variant",
            "identified": False,
            "uds": False,
        }
        if match:
            result.update(match)
            result["identified"] = True
        return result

    def describe(self, name: str, code: str, memory: str = "Fault") -> str | None:
        """Use only the exact variant's English entry; never borrow another ECU."""
        descriptions = self.info_descriptions if memory == "Information" else self.descriptions
        return descriptions.get(name, {}).get(code.upper().removeprefix("0X"))


def read_inventory(connection: Any) -> list[dict[str, Any]]:
    """Identify gateway targets, or source-catalogue candidates on failed/empty topology.

    The entire batch has a 30-second absolute deadline including catalogue load,
    queueing and all identities. A fallback never proves installed topology;
    retain every candidate and disposition without retrying an uncertain stream.
    """
    if getattr(connection, "kind", None) != TransportKind.HSFZ:
        raise ValueError("DoIP ECU inventory/address translation is not yet recovered")
    deadline = time.monotonic() + 30.0
    catalog = DiagnosticCatalog()

    def read(address: int, payload: bytes) -> tuple[bytes | None, str]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None, "not-attempted-budget-exhausted"
        if not connection.alive_ok:
            return None, "not-attempted-connection-closed"
        outcome = connection.request(
            address, payload, context=connection.context(min(30.0, remaining))
        )
        if outcome.failure is not None:
            logger.warning(
                "Identity read address=%02X request=%s outcome=%s nrc=%s",
                address,
                payload.hex(),
                outcome.failure,
                outcome.nrc,
            )
            return None, outcome.failure.value
        return outcome.payload, "read"

    response, inventory_state = read(0x10, b"\x22\x3f\x07")
    addresses: tuple[int, ...] = ()
    if response is not None:
        try:
            addresses = decode_inventory(response)
            inventory_state = "read" if addresses else "empty"
        except ValueError:
            logger.warning(
                "Invalid gateway inventory; retaining catalogue candidates", exc_info=True
            )
            inventory_state = "invalid"
    origin = "gateway" if addresses else "catalogue"
    if not addresses:
        addresses = catalog.uds_addresses()
    results = []
    for address in addresses:
        row: dict[str, Any] = {
            "addr": hex(address),
            "name": f"ECU {address:02X}",
            "description": "Identification not attempted",
            "identified": False,
            "uds": False,
        }
        response, state = read(address, b"\x22\xf1\x50")
        if response is not None:
            try:
                row = catalog.identify(address, response)
                state = "identified" if row["identified"] else "unmatched-variant"
            except ValueError:
                logger.warning("Invalid ECU identity address=%02X", address, exc_info=True)
                state = "invalid"
        if state not in ("identified", "unmatched-variant"):
            row["description"] = "Identification unavailable; see session log"
        row.update(origin=origin, inventory_state=inventory_state, identity_state=state)
        results.append(row)
    return results


def post_connect_tasks() -> list[tuple[str, Callable[[Any], object]]]:
    """Return a single settled dashboard batch using recovered read contracts."""
    ecus: list[dict[str, Any]] = []

    def inventory(connection: Any) -> object:
        ecus.clear()
        ecus.extend(read_inventory(connection))
        return list(ecus)

    def supported(connection: Any, read: Callable[[Any], object]) -> object:
        if getattr(connection, "kind", TransportKind.HSFZ) != TransportKind.HSFZ:
            raise ValueError("This information read needs a recovered logical-address mapping")
        return read(connection)

    return [
        ("ECU list", inventory),
        ("MIL", lambda conn: read_mil(conn, ecus)),
        ("Vehicle order", read_vehicle_order),
        (
            "I-Level",
            lambda conn: supported(
                conn, lambda active: decode_ilevel(active.send_uds(0x10, b"\x22\x10\x0b"))
            ),
        ),
        (
            "Battery voltage",
            lambda conn: supported(
                conn,
                lambda active: f"{decode_voltage(active.send_uds(0x12, b'\x22\x40\x2b')):.2f} V",
            ),
        ),
    ]
