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


@lru_cache(maxsize=1)
def _models() -> dict[str, list[dict[str, str]]]:
    """Load the bounded generated model catalogue without accessing research inputs."""
    with resource_path("coding_data/vehicle_models.json").open("rb") as source:
        raw = source.read(4_194_305)
    if len(raw) > 4_194_304:
        raise ValueError("Vehicle model catalogue exceeds its size limit")
    try:
        data = json.loads(raw)
    except RecursionError as exc:
        raise ValueError("Vehicle model catalogue nesting exceeds its limit") from exc
    if (
        not isinstance(data, dict)
        or data.get("schema") != 1
        or not isinstance(data.get("models"), dict)
    ):
        raise ValueError("Invalid vehicle model catalogue")
    models = data["models"]
    result: dict[str, list[dict[str, str]]] = {}
    for code, rows in models.items():
        if not isinstance(code, str) or len(code) != 4 or not isinstance(rows, list):
            raise ValueError("Invalid vehicle model type code")
        if not all(
            isinstance(row, dict)
            and isinstance(row.get("series"), str)
            and isinstance(row.get("label"), str)
            and 0 < len(row["label"]) <= 1024
            for row in rows
        ):
            raise ValueError("Invalid vehicle model description")
        result[code] = [{"series": row["series"], "label": row["label"]} for row in rows]
    return result


def describe_model(type_code: str, model_range: str) -> str | None:
    """Resolve the observed type and series only when every matching label agrees."""
    labels = {row["label"] for row in _models().get(type_code, []) if row["series"] == model_range}
    return "BMW " + labels.pop() if len(labels) == 1 else None
