"""Normalize recorded fault conditions decoded by the exact ECU's native jobs.

The jobs own snapshot layouts, scaling and information-memory position lookup.
Emission order does not establish first/last occurrence, and an ECU time counter
does not establish a calendar date. Original typed results remain available for
diagnostics even when a value cannot be presented.
"""

import logging
import math
import re
from typing import Any

from app.ista_jobs import JobRun

logger = logging.getLogger(__name__)
DETAIL_JOBS = {"Fault": "FS_LESEN_DETAIL", "Information": "IS_LESEN_DETAIL"}


def _number(value: Any, maximum: int) -> int | float | None:
    if type(value) not in (int, float) or not math.isfinite(value):
        return None
    return value if 0 <= value <= maximum else None


def decode_fault_details(run: JobRun, code: int) -> dict[str, Any]:
    """Retain each job-emitted state and its source-defined environment values.

    Raises:
        ValueError: Results cannot be associated with the requested fault or their
            declared environment count is inconsistent.
    """
    if not run.ok or run.result is None:
        raise ValueError("Fault detail job did not complete")
    result = run.result
    logger.debug("Fault details %s code=%06X results=%r", run.source, code, result.sets)
    raw = [
        {
            "values": {
                key: value.hex() if isinstance(value, bytes) else value
                for key, value in values.items()
            },
            "types": result.types[index] if index < len(result.types) else {},
        }
        for index, values in enumerate(result.sets)
    ]
    if not any(values.get("F_ORT_NR") == code for values in result.sets) or any(
        "F_ORT_NR" in values and values["F_ORT_NR"] != code for values in result.sets
    ):
        raise ValueError("Fault detail results belong to another fault")
    records = []
    for values in result.sets:
        if "F_ORT_NR" not in values and not any(key.startswith("F_UW") for key in values):
            continue
        fields: list[dict[str, Any]] = []
        for key, label, unit, maximum, note in (
            ("F_HFK", "Occurrence counter", "", 255, "Saturates at 255"),
            ("F_HLZ", "Healing counter", "", 255, ""),
            ("F_UW_KM", "Recorded mileage", "km", 0xFFFFFE, ""),
            (
                "F_UW_ZEIT",
                "ECU time counter",
                "s",
                0xFFFFFFFE,
                "Calendar origin unavailable; not a date",
            ),
        ):
            if key in values:
                value = _number(values[key], maximum)
                # Newer jobs retain unsigned counters and subsecond precision
                # in a decimal string even when the older signed result is -1.
                supreme = values.get(key + "_SUPREME")
                if isinstance(supreme, str):
                    try:
                        precise = float(supreme)
                        value = (
                            precise
                            if math.isfinite(precise) and 0 <= precise < 0xFFFFFFFF
                            else None
                        )
                    except ValueError:
                        value = None
                    if isinstance(value, float) and value.is_integer():
                        value = int(value)
                fields.append(
                    {
                        "label": label,
                        "value": value,
                        "unit": unit,
                        "note": note,
                        "field": key,
                    }
                )
        for key, label in (
            ("F_UW_KM_SUPREME_INSYNC", "Mileage synchronization"),
            ("F_UW_ZEIT_SUPREME_INSYNC", "ECU time synchronization"),
        ):
            if key in values:
                fields.append(
                    {
                        "label": label,
                        "value": _yes_no(values[key]),
                        "unit": "",
                        "field": key,
                        "note": (
                            str(values.get("F_UW_ZEIT_SUPREME_USER_INFORMATION", ""))
                            if "ZEIT" in key
                            else ""
                        ),
                    }
                )
        if "F_UEBERLAUF" in values:
            overflow = values["F_UEBERLAUF"]
            fields.append(
                {
                    "label": "Fault memory overflow",
                    "value": _yes_no(overflow),
                    "unit": "",
                    "field": "F_UEBERLAUF",
                }
            )
        count = values.get("F_UW_ANZ", 0)
        indices = {
            int(match[1])
            for key in values
            if (match := re.fullmatch(r"F_UW([1-9][0-9]*)_WERT", key))
        }
        if (
            type(count) is not int
            or not 0 <= count <= len(values)
            or indices != set(range(1, count + 1))
        ):
            raise ValueError("Incomplete environment results")
        environment = []
        for index in sorted(indices):
            prefix = f"F_UW{index}"
            env_label, env_unit = values.get(prefix + "_TEXT"), values.get(prefix + "_EINH")
            env_value = values[prefix + "_WERT"]
            if (
                not isinstance(env_label, str)
                or not env_label.strip()
                or not isinstance(env_unit, str)
            ):
                raise ValueError("Environment result lacks its label or unit")
            presented: int | float | str | None = None
            if isinstance(env_value, (int, float, str)) and not (
                isinstance(env_value, float) and not math.isfinite(env_value)
            ):
                presented = env_value
            environment.append(
                {
                    "label": env_label.strip(),
                    "value": presented,
                    "unit": env_unit.strip(),
                    "field": prefix,
                    "identifier": values.get(prefix + "_NR"),
                }
            )
        records.append({"fields": fields, "environment": environment})
    if not records:
        raise ValueError("Fault detail job returned no matching records")
    return {"state": "read", "source": run.source, "records": records, "raw": raw}


def _yes_no(value: Any) -> str | None:
    return {0: "No", 1: "Yes"}.get(value) if isinstance(value, int) else None
