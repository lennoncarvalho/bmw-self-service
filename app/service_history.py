"""Recovered history data codecs, independent of any research tool at runtime.

The local records and recovered NBT add body have a seven-byte dealer slot.
These codecs provide no vehicle read, authorization, baseline or write worker.
Provenance: docs/evidence/task-b-history-deep-investigation.md.
"""

import struct
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date

_ITEM = struct.Struct(">BBiH")
_HEADER = struct.Struct(">BBHBIB7sBB")
ADD_REQUEST = b"\x31\x01\xa0\x81"
MAX_FILE_BYTES = 1024 * 1024


@dataclass(frozen=True)
class HistoryItem:
    """One raw service item; unknown code/status values remain preserved on read."""

    code: int
    status: int
    remaining_distance: int
    remaining_time: int


@dataclass(frozen=True)
class HistoryEntry:
    """Decoded entry retaining exact local bytes when read from an existing file."""

    service_date: date
    correction: int
    mileage_km: int
    dealer_flag: int
    dealer_bytes: bytes
    status: int
    items: tuple[HistoryItem, ...]
    original_bytes: bytes = b""

    @property
    def dealer(self) -> str:
        """Display ASCII dealer text without changing unrecognized original bytes."""
        return self.dealer_bytes.split(b"\x00", 1)[0].decode("ascii", errors="replace")


def decode_legacy_history(data: bytes) -> tuple[HistoryEntry, ...]:
    """Parse the concatenated legacy records; reject incomplete or trailing data.

    Calendar/year/mileage/item numbers are big-endian. The dealer occupies
    exactly seven bytes, including any NUL padding. Existing status bytes, codes,
    dates and padding are preserved without normalization or filtering.
    """
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("History file exceeds the supported local file size")
    entries = []
    offset = 0
    while offset < len(data):
        if len(data) - offset < _HEADER.size:
            raise ValueError("Incomplete history record header")
        start = offset
        day, month, year, correction, mileage, flag, dealer, status, count = _HEADER.unpack_from(
            data, offset
        )
        service_date = date(year, month, day)
        offset += _HEADER.size
        end = offset + count * _ITEM.size
        if end > len(data):
            raise ValueError("Incomplete history service items")
        items = tuple(
            HistoryItem(*_ITEM.unpack_from(data, offset + i * _ITEM.size)) for i in range(count)
        )
        offset = end
        entries.append(
            HistoryEntry(
                service_date, correction, mileage, flag, dealer, status, items, data[start:end]
            )
        )
    return tuple(entries)


def encode_legacy_history(entries: Collection[HistoryEntry]) -> bytes:
    """Serialize a local file while preserving every previously decoded record."""
    encoded = bytearray()
    for entry in entries:
        if entry.original_bytes:
            # Do not accept a modified model paired with stale original bytes.
            original = decode_legacy_history(entry.original_bytes)
            if len(original) != 1 or original[0] != entry:
                raise ValueError("Original history bytes no longer match the decoded entry")
            encoded.extend(entry.original_bytes)
        else:
            _validate_fields(entry)
            encoded.extend(_new_record_bytes(entry))
        if len(encoded) > MAX_FILE_BYTES:
            raise ValueError("History file exceeds the supported local file size")
    return bytes(encoded)


def _validate_fields(entry: HistoryEntry) -> None:
    if type(entry.service_date) is not date:
        raise ValueError("Service date must be a calendar date")
    if type(entry.correction) is not int or not 0 <= entry.correction <= 255:
        raise ValueError("Correction counter exceeds its encoded range")
    if type(entry.mileage_km) is not int or not 0 <= entry.mileage_km <= 0xFFFFFFFF:
        raise ValueError("Mileage exceeds its encoded range")
    if type(entry.dealer_flag) is not int or entry.dealer_flag not in (0, 1):
        raise ValueError("Unsupported dealer flag for a new entry")
    if (
        not isinstance(entry.dealer_bytes, bytes)
        or not entry.dealer_bytes
        or b"\x00" in entry.dealer_bytes
        or not entry.dealer_bytes.isascii()
        or len(entry.dealer_bytes) > 7
    ):
        raise ValueError("Dealer must contain one to seven ASCII bytes without NUL")
    if type(entry.status) is not int or entry.status not in (1, 2, 3):
        raise ValueError("Unsupported service status for a new entry")
    if not 1 <= len(entry.items) <= 255:
        raise ValueError("A service entry requires an encoded item count")
    _item_bytes(entry.items)


def _item_bytes(items: Collection[HistoryItem]) -> bytes:
    result = bytearray()
    for item in items:
        values = (item.code, item.status, item.remaining_distance, item.remaining_time)
        if any(type(value) is not int for value in values):
            raise ValueError("Service item fields must be integers")
        if not 0 <= item.code <= 255 or item.status not in (1, 2, 3):
            raise ValueError("Unsupported new service item code or status")
        if (
            not -0x80000000 <= item.remaining_distance <= 0x7FFFFFFF
            or not 0 <= item.remaining_time <= 0xFFFF
        ):
            raise ValueError("Service item distance/time exceeds its encoded range")
        result.extend(_ITEM.pack(*values))
    return bytes(result)


def encode_nbt_add(
    entry: HistoryEntry, *, existing_dates: Collection[date], today: date | None = None
) -> bytes:
    """Encode a new NBT add routine after product and source field validation.

    This is a payload encoder, NOT a send operation or proof of preserved car
    history. Callers still need a freshly identified complete vehicle baseline,
    durable backup/intent and the appropriate execution/recovery contract.
    """
    _validate_fields(entry)
    if entry.service_date > (today or date.today()):
        raise ValueError("Future service dates cannot be written")
    if entry.service_date in existing_dates:
        raise ValueError("A service entry already exists on this date")
    if len(entry.items) > 13:
        raise ValueError("This headunit format supports at most thirteen service items")
    return ADD_REQUEST + _new_record_bytes(entry)


def _new_record_bytes(entry: HistoryEntry) -> bytes:
    header = _HEADER.pack(
        entry.service_date.day,
        entry.service_date.month,
        entry.service_date.year,
        entry.correction,
        entry.mileage_km,
        entry.dealer_flag,
        entry.dealer_bytes.ljust(7, b"\x00"),
        entry.status,
        len(entry.items),
    )
    return header + _item_bytes(entry.items)


@dataclass(frozen=True)
class HistoryApplicationResult:
    """Routine business status; acceptance is distinct from observed history."""

    code: int

    @property
    def accepted(self) -> bool:
        """Whether the application reports Everything OK (not a readback claim)."""
        return self.code == 0

    @property
    def description(self) -> str:
        """Return the source status label or an explicit unknown value."""
        return {
            0: "Everything OK",
            1: "Out of memory",
            2: "Data inconsistency",
            4: "No writing permission",
            5: "Unknown error",
        }.get(self.code, f"Unknown application status 0x{self.code:02X}")


def decode_nbt_add_result(response: bytes) -> HistoryApplicationResult:
    """Validate final routine echo and exact one-byte application status."""
    if len(response) != 5 or response[:4] != b"\x71\x01\xa0\x81":
        raise ValueError("Invalid history routine application response")
    return HistoryApplicationResult(response[4])
