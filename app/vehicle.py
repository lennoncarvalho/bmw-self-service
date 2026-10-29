"""Vehicle inventory and identification recovered from diagnostic reference artifacts.

Contract/provenance: docs/evidence/task-b-recovered-contracts.md. These reads do
not infer transport, software identity or write capability from a chassis hint.
"""

import gzip
import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.protocol.contracts import TransportKind
from app.resources import resource_path

logger = logging.getLogger(__name__)


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
    data = did_data(response, 0x100B)
    if len(data) != 24:
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
    """Read all announced targets; preserve failed and unknown identification rows.

    Inventory and each identity have an absolute 30-second budget including
    queueing. An invalidated stream stops sends; remaining rows stay unattempted.
    """
    if getattr(connection, "kind", TransportKind.HSFZ) != TransportKind.HSFZ:
        raise ValueError("DoIP ECU inventory/address translation is not yet recovered")
    catalog = DiagnosticCatalog()
    addresses = decode_inventory(connection.send_uds(0x10, b"\x22\x3f\x07", timeout=30.0))
    results = []
    for address in addresses:
        row: dict[str, Any] = {
            "addr": hex(address),
            "name": f"ECU {address:02X}",
            "description": "Identification not attempted",
            "identified": False,
            "uds": False,
        }
        if getattr(connection, "alive_ok", True):
            try:
                response = connection.send_uds(address, b"\x22\xf1\x50", timeout=30.0)
                row = catalog.identify(address, response)
            except (ConnectionError, TimeoutError, ValueError):
                logger.warning(
                    "ECU identification unavailable address=%04X", address, exc_info=True
                )
                row["description"] = "Identification unavailable; see session log"
        results.append(row)
    return results


def post_connect_tasks() -> list[tuple[str, Callable[[Any], object]]]:
    """Return a single settled dashboard batch using recovered read contracts."""

    def supported(connection: Any, read: Callable[[Any], object]) -> object:
        if getattr(connection, "kind", TransportKind.HSFZ) != TransportKind.HSFZ:
            raise ValueError("This information read needs a recovered logical-address mapping")
        return read(connection)

    return [
        ("ECU list", read_inventory),
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
