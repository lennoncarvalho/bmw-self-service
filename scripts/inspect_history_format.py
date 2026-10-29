"""Development-only legacy sample codecs; never imported by the app.

Retained to reproduce docs/evidence/task-b-history-deep-investigation.md.
The product uses JSON only; these helpers do not add file interchange support.
"""

from collections.abc import Collection
from datetime import date

from app.service_history import (
    _HEADER,
    _ITEM,
    HistoryEntry,
    HistoryItem,
    _new_record_bytes,
    _validate_fields,
)

MAX_FILE_BYTES = 1024 * 1024


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
