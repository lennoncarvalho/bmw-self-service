"""Bounded packed vehicle-order decoding for the recovered gateway read.

Wire and field provenance: docs/evidence/task-b-vehicle-order.md.
No production-date, exact model, transport or coding applicability is inferred.
"""

import logging
from typing import Any

from app.protocol.contracts import TransportKind
from app.vehicle_metadata import describe_options

logger = logging.getLogger(__name__)


class _Bits:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def read(self, start: int, width: int) -> int:
        if start < 0 or width < 1 or start + width > len(self.data) * 8:
            raise ValueError("Vehicle order is truncated")
        result = 0
        for position in range(start, start + width):
            result = (result << 1) | ((self.data[position // 8] >> (7 - position % 8)) & 1)
        return result

    def text(self, start: int, count: int) -> str:
        characters = []
        for index in range(count):
            value = self.read(start + index * 6, 6)
            group, low = divmod(value, 16)
            character = (0, 48, 64, 80)[group] + low
            if character < 32:
                raise ValueError("Vehicle order contains an unsupported control character")
            characters.append(chr(character))
        return "".join(characters)


def decode_vehicle_order(response: bytes) -> dict[str, Any]:
    """Decode fixed fields and ordered optional sections; preserve opaque remainder.

    The source skips two bytes after the DID; their meaning is not assumed.
    Unknown section tags leave equipment explicitly incomplete. Truncated known
    sections are rejected instead of presenting a shortened list as complete.
    """
    if not response.startswith(b"\x62\x3f\x06") or not 21 <= len(response) <= 4096:
        raise ValueError("Vehicle-order response has an unsupported echo or size")
    data = response[5:]
    bits = _Bits(data)
    result: dict[str, Any] = {
        "raw_hex": response.hex().upper(),
        "framing_prefix": response[3:5].hex().upper(),
        "version": data[0],
    }
    for index, field in enumerate(
        ("time_criterion", "model_range", "type_code", "paint_code", "upholstery_code")
    ):
        result[field] = bits.text(8 + index * 24, 4)
    position = 128
    sections: dict[str, list[str]] = {}
    for marker, width in ((8, 3), (4, 4), (12, 4)):
        if len(data) * 8 - position < 4:
            break
        if bits.read(position, 4) != marker:
            continue
        position += 4
        values = []
        while bits.read(position, 2) != 0:
            values.append(bits.text(position, width))
            position += width * 6
        position += 2
        sections[str(marker)] = values
    # The final list ends with two zero bits; byte padding may be shorter than
    # a whole tag. Preserve all remaining bytes, without interpreting new tags.
    remaining = len(data) * 8 - position
    result["equipment_complete"] = remaining == 0 or bits.read(position, remaining) == 0
    result["decoded_bits"] = position
    result["sections"] = sections
    result["options"] = sections.get("8", [])
    return result


def read_vehicle_order(connection: Any) -> dict[str, Any]:
    """Read gateway vehicle order on the recovered byte-addressed HSFZ branch."""
    if getattr(connection, "kind", None) != TransportKind.HSFZ:
        raise ValueError("Vehicle-order logical-address mapping is not yet recovered")
    order = decode_vehicle_order(connection.send_uds(0x10, b"\x22\x3f\x06", timeout=30.0))
    try:
        order["option_descriptions"] = describe_options(order["options"])
    except (OSError, ValueError):
        logger.warning("Vehicle equipment descriptions unavailable", exc_info=True)
        order["option_descriptions"] = [
            f"{code} — Description unavailable" for code in order["options"]
        ]
    return order
