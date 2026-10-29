"""English labels for exact observed vehicle-equipment codes."""

import json
from functools import lru_cache

from app.resources import resource_path


@lru_cache(maxsize=1)
def _equipment() -> dict[str, str]:
    with resource_path("coding_data/vehicle_equipment.json").open("rb") as source:
        raw = source.read(1_048_577)
    if len(raw) > 1_048_576:
        raise ValueError("Vehicle equipment catalogue exceeds its size limit")
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise ValueError("Invalid vehicle equipment catalogue schema")
    rows = data.get("equipment")
    if not isinstance(rows, dict) or not 1 <= len(rows) <= 10_000:
        raise ValueError("Invalid vehicle equipment catalogue rows")
    for code, label in rows.items():
        if (
            not isinstance(code, str)
            or len(code) not in (3, 4)
            or not code.isascii()
            or not code.isalnum()
            or code != code.upper()
            or not isinstance(label, str)
            or not label.strip()
            or len(label) > 1024
        ):
            raise ValueError("Invalid vehicle equipment catalogue entry")
    return rows


def describe_options(codes: list[str]) -> list[str]:
    """Label exact observed codes; preserve unknowns without a translated guess.

    Called by the vehicle-information worker so catalogue reads never block the
    GUI. Catalogue failures leave the caller's raw observations intact.
    """
    if len(codes) > 2048 or any(
        not isinstance(code, str)
        or len(code) not in (3, 4)
        or not code.isascii()
        or not code.isalnum()
        for code in codes
    ):
        raise ValueError("Invalid vehicle equipment code list")
    labels = _equipment()
    return [f"{code} — {labels.get(code.upper(), 'Description unavailable')}" for code in codes]
