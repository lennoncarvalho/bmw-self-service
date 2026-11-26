"""Vehicle inventory and identification recovered from diagnostic reference artifacts.

Contract/provenance: docs.md#identity-configuration-and-diagnostics. These reads do
not infer transport, software identity or write capability from a chassis hint.
"""

import gzip
import json
import logging
import time
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Any, cast

from app.diagnostic_texts import diagnostic_texts
from app.ista_data import DataFormatError
from app.ista_jobs import data_source
from app.power_readings import read_power_status, reader_profiles
from app.protocol.contracts import (
    FailureKind,
    OperationContext,
    ProtocolFailure,
    TransportKind,
    WriteConditionsBlocked,
)
from app.resources import resource_path
from app.vehicle_order import read_vehicle_order

logger = logging.getLogger(__name__)


ACTIVE = 0x01  # ISO 14229 testFailed: fault present now
CONFIRMED = 0x08  # ISO 14229 confirmedDTC: fault stored as confirmed


def fault_state(status: int) -> str:
    """Summarize one DTC status byte the way ISTA presents a stored fault."""
    if status & ACTIVE:
        return "present"
    if status & CONFIRMED:
        return "stored"
    return "not-confirmed"


@cache
def mil_contracts() -> dict[str, dict[str, Any]]:
    """Load the exact engine identities and lamp-command contracts."""
    with resource_path("coding_data/mil_contracts.json").open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError("MIL definitions exceed their supported size")
    data = json.loads(raw)
    if data.get("schema") != 1 or not isinstance(data.get("engines"), dict):
        raise ValueError("Unsupported MIL definition format")
    return cast(dict[str, dict[str, Any]], data["engines"])


def read_mil(
    connection: Any, ecus: list[dict[str, Any]], *, timeout: float = 30.0
) -> dict[str, object]:
    """Observe the ECU lamp command through the matching scalar read contract."""
    if connection.kind != TransportKind.HSFZ:
        return {"on": None, "detail": "MIL is unavailable on this transport."}
    engines = [row for row in ecus if row.get("addr") == "0x12"]
    if len(engines) != 1 or engines[0].get("identified") is not True:
        return {"on": None, "detail": "Engine controller identity is unavailable."}
    engine = engines[0]
    name = engine["name"]
    if timeout <= 0 or not connection.alive_ok:
        return {"on": None, "detail": "Lamp command could not be read in this operation."}
    try:
        contract = mil_contracts().get(engine.get("address_index", ""), {})
        if contract.get("name") != name or contract.get("state") != "scalar-boolean":
            return {"on": None, "detail": f"No verified direct lamp read for {name}."}
        did = contract["did"]
        response = connection.send_uds(0x12, b"\x22" + did.to_bytes(2, "big"), timeout=timeout)
        value = did_data(response, did)
        if value not in (b"\x00", b"\x01"):
            raise ValueError("Invalid scalar lamp-command response")
    except (OSError, ValueError, ProtocolFailure):
        logger.warning("MIL command unavailable for %s", name, exc_info=True)
        return {"on": None, "detail": f"Lamp command could not be read from {name}."}
    return {
        "on": value == b"\x01",
        "detail": f"Lamp command from {name}. The light may illuminate during startup checks.",
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


def decode_ilevel(response: bytes) -> dict[str, str]:
    """Decode current, previous and shipment integration levels from gateway 100B."""
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
    return dict(zip(("current", "previous", "factory"), levels, strict=True))


def decode_voltage(response: bytes) -> float:
    """Decode the source's 31-byte DME 402B voltage response, in volts."""
    did_data(response, 0x402B)
    if len(response) != 31:
        raise ValueError("Vehicle voltage has an unsupported format")
    return int.from_bytes(response[5:7], "big") * 0.00025 + 6.0


# Exact cluster/body definitions selected by F150 address-index (T_GRTB
# ZuordnungsTabelleUDS); see docs.md#identity-configuration-and-diagnostics.
CLUSTER_DISPLAYED = frozenset({"KOMBRDCT", "KOMB_G11", "KOMBSP18", "KOMBSP21"})  # 22 D122
CLUSTER_ABSOLUTE = frozenset({"KOMB01", "KOMB25"})  # STATUS_GWSZ_ANZEIGE: D10D - D114
BODY_COPY = frozenset({"BDC", "BDC_G11", "FEM_20"})  # STATUS_KILOMETERSTAND: 22 1700


def decode_displayed_odometer(response: bytes) -> int:
    """Decode cluster D122, km x1; FFFFFFFF is treated as invalid (hypothesis)."""
    data = did_data(response, 0xD122)
    if len(data) != 4 or data == b"\xff\xff\xff\xff":
        raise ValueError("Cluster odometer has an unsupported value or shape")
    return int.from_bytes(data, "big")


def decode_absolute_odometer(absolute: bytes, offset: bytes) -> int:
    """Displayed km = D10D RAM counter - D114 display offset, as STATUS_GWSZ_ANZEIGE."""
    counter = did_data(absolute, 0xD10D)
    shift = did_data(offset, 0xD114)
    if len(counter) not in (4, 8) or len(shift) != 1 or counter[:4] == b"\xff\xff\xff\xff":
        raise ValueError("Cluster odometer has an unsupported value or shape")
    value = int.from_bytes(counter[:4], "big") - shift[0]
    if value < 0:
        raise ValueError("Cluster odometer offset exceeds its counter")
    return value


def decode_body_odometer(response: bytes) -> int:
    """Decode the body controller's redundant copy, valid range 0-16777214 km."""
    data = did_data(response, 0x1700)
    if len(data) != 4 or int.from_bytes(data, "big") > 16777214:
        raise ValueError("Body controller odometer has an unsupported value or shape")
    return int.from_bytes(data, "big")


def read_odometer(connection: Any, ecus: list[dict[str, Any]]) -> dict[str, object] | None:
    """Read the displayed odometer from an exact cluster, else the body controller copy.

    Only exactly identified definitions are used; unknown variants stay unavailable.
    The definitions fix the unit as km and the value is never converted.
    """
    names = {row.get("addr"): row.get("name") for row in ecus if row.get("identified") is True}
    cluster, body = names.get("0x60"), names.get("0x40")
    failure: Exception | None = None
    try:
        if cluster in CLUSTER_DISPLAYED:
            return {
                "km": decode_displayed_odometer(connection.send_uds(0x60, b"\x22\xd1\x22")),
                "source": f"instrument cluster {cluster}",
            }
        if cluster in CLUSTER_ABSOLUTE:
            absolute = connection.send_uds(0x60, b"\x22\xd1\x0d")
            offset = connection.send_uds(0x60, b"\x22\xd1\x14")
            return {
                "km": decode_absolute_odometer(absolute, offset),
                "source": f"instrument cluster {cluster}",
            }
    except ValueError as exc:
        failure = exc
        logger.warning("Cluster odometer unavailable; trying body controller", exc_info=True)
    if body in BODY_COPY and connection.alive_ok:
        return {
            "km": decode_body_odometer(connection.send_uds(0x40, b"\x22\x17\x00")),
            "source": f"body controller {body} stored copy",
        }
    if failure is not None:
        raise failure
    logger.info("No recovered odometer definition cluster=%s body=%s", cluster, body)
    return None


def engine_measurements() -> dict[str, list[dict[str, Any]]]:
    """Load exact engine measurement rows (scripts/recover_engine_measurements.py)."""
    path = resource_path("coding_data/engine_measurements.json")
    with path.open("rb") as stream:
        raw = stream.read(262145)
    if len(raw) > 262144:
        raise ValueError("Engine measurement definitions exceed their supported size")
    data = json.loads(raw)
    if data.get("schema") != 1 or not isinstance(data.get("engines"), dict):
        raise ValueError("Unsupported engine measurement format")
    return cast(dict[str, list[dict[str, Any]]], data["engines"])


def decode_measurement(response: bytes, row: dict[str, Any]) -> float:
    """Decode one exact big-endian table value: raw x MUL / DIV + ADD."""
    data = did_data(response, int(row["did"]))
    if len(data) != row["size"]:
        raise ValueError("Engine measurement has an unsupported shape")
    raw = int.from_bytes(data, "big", signed=bool(row["signed"]))
    return float(raw * row["mul"] / row["div"] + row["add"])


def read_supply_voltage(
    connection: Any, ecus: list[dict[str, Any]], *, context: OperationContext | None = None
) -> float | None:
    """Read live supply voltage using an applicable engine definition."""
    engines = [row for row in ecus if row.get("addr") == "0x12" and row.get("identified") is True]
    if len(engines) != 1:
        return None
    ecu = engines[0]
    name = ecu["name"]
    if name == "DME_BX8":
        if ecu.get("address_index") not in reader_profiles().get(name, {}).get("selectors", ()):
            return None
        request = b"\x22\x40\x2b"
        measurement = None
    else:
        measurement = next(
            (row for row in engine_measurements().get(name, []) if row["label"] == "Battery"),
            None,
        )
        if measurement is None or measurement["unit"] not in {"mV", "V"}:
            return None
        request = b"\x22" + int(measurement["did"]).to_bytes(2, "big")
    try:
        response = connection.send_uds(0x12, request, context=context)
        if measurement is None:
            return decode_voltage(response)
        value = decode_measurement(response, measurement)
        return value / 1000 if measurement["unit"] == "mV" else value
    except ProtocolFailure as error:
        if error.kind != FailureKind.NEGATIVE or error.reconnect:
            raise
    except ValueError:
        logger.debug("Supply voltage response unavailable", exc_info=True)
    return None


def check_write_conditions(
    connection: Any, ecus: list[dict[str, Any]], context: OperationContext
) -> str:
    """Read fresh conditions on the held owner and refuse known unsafe ignition/power."""
    if getattr(connection, "power_sufficient", None) is False:
        raise WriteConditionsBlocked("Vehicle power is insufficient.")
    deadline = context.deadline
    context.deadline = min(deadline, time.monotonic() + 30.0)
    try:
        status = read_power_status(connection, ecus, ignition_only=True, context=context)
        ignition = [item for item in status["kl15"] if item["state"] in {"read", "transition"}]
        for observation in ignition:
            if observation["raw_value"] != 10:
                logger.info(
                    "Vehicle write preflight blocked conn=%s source=%s terminal=0x%02X",
                    context.generation,
                    observation["source"],
                    observation["raw_value"],
                )
                raise WriteConditionsBlocked(
                    f"{observation['source']} reports {observation['value']}. "
                    "Switch on the ignition (KL15) while keeping the engine off. "
                    "On vehicles with a Start/Stop button, release the brake and clutch pedals "
                    "before switching on the ignition."
                )
        voltage = read_supply_voltage(connection, ecus, context=context)
        context.remaining()
    finally:
        context.deadline = deadline
    if not connection.alive_ok:
        raise ConnectionError("Connection lost while checking vehicle power and ignition")
    ignition_text = "Ignition on (KL15)" if ignition else "Ignition unavailable"
    voltage_text = (
        f"Supply voltage {voltage:.2f} V" if voltage is not None else "Voltage unavailable"
    )
    result = f"{ignition_text}. {voltage_text}. Confirm stable vehicle and computer power."
    logger.info("Vehicle write preflight conn=%s %s", context.generation, result)
    return result


def read_engine_data(connection: Any, ecus: list[dict[str, Any]]) -> list[dict[str, object]] | None:
    """Read core engine values for an exactly identified definition; failures stay per item."""
    engines = [row for row in ecus if row.get("addr") == "0x12" and row.get("identified") is True]
    if len(engines) != 1:
        return None
    rows = engine_measurements().get(str(engines[0].get("name")))
    if not rows:
        return None
    values: list[dict[str, object]] = []
    for row in rows:
        item: dict[str, object] = {"label": row["label"], "unit": row["unit"], "value": None}
        if connection.alive_ok:
            try:
                response = connection.send_uds(0x12, b"\x22" + int(row["did"]).to_bytes(2, "big"))
                item["value"] = decode_measurement(response, row)
            except ValueError:
                logger.warning("Engine measurement unavailable did=%04X", row["did"], exc_info=True)
        values.append(item)
    return values


class DiagnosticCatalog:
    """Exact address/variant definitions and English fault descriptions."""

    def __init__(self, path: Path | None = None) -> None:
        """Load the bundled diagnostic catalogue and optional exact text mappings."""
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
        # The embedded job table covers identities absent from the older
        # diagnostic catalogue. A row identifies a variant, not write permission
        # or proof that its job file is present on this installation.
        try:
            for key, name in data_source().uds_variants().items():
                if key not in self.variants:
                    self.variants[key] = {
                        "name": name,
                        "description": name,
                        "uds": True,
                        "identity_source": "embedded job table",
                    }
        except (OSError, ValueError, DataFormatError):
            logger.warning("Embedded job identities unavailable", exc_info=True)

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
            title = diagnostic_texts.ecu_title(str(result["name"]))
            if title:
                result["description"] = title
        return result

    def describe(self, name: str, code: str, memory: str = "Fault") -> str | None:
        """Prefer English for the exact variant, retaining available source-language text."""
        try:
            text = diagnostic_texts.describe(
                int(code.upper().removeprefix("0X"), 16),
                ecu=name,
                fault_type="I" if memory == "Information" else "F",
            )
        except ValueError:
            text = ""
        if text:
            return text
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

    def voltage(connection: Any) -> str | None:
        value = read_supply_voltage(connection, ecus)
        return None if value is None else f"{value:.2f} V"

    return [
        ("ECU list", inventory),
        ("MIL", lambda conn: read_mil(conn, ecus)),
        ("Mileage", lambda conn: supported(conn, lambda active: read_odometer(active, ecus))),
        (
            "Engine data",
            lambda conn: supported(conn, lambda active: read_engine_data(active, ecus)),
        ),
        ("Vehicle order", read_vehicle_order),
        (
            "I-Level",
            lambda conn: supported(
                conn, lambda active: decode_ilevel(active.send_uds(0x10, b"\x22\x10\x0b"))
            ),
        ),
        (
            "Battery voltage",
            lambda conn: supported(conn, voltage),
        ),
    ]
