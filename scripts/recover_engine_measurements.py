"""Build the embedded engine measurement asset from reviewed recovery rows.

Development-only. Input is the cross-checked row list from the odometer/identity
recovery (each row agrees between the diagnostics APK definition and the PRG
SG_FUNKTIONEN table); see docs/evidence/task-b-odometer-identity-doip.md (A4).
Only definitions already proven to use the reviewed plain STATUS_LESEN job
(scalar-boolean rows in coding_data/mil_contracts.json) are kept, so every
value is a single read-only `22 <DID>`. Engine-local mileage counters are not
the displayed odometer and are excluded.
"""

import argparse
import hashlib
import json
from pathlib import Path

LABELS = {
    "Coolant temperature": "Coolant",
    "Oil temperature": "Oil",
    "Engine oil temperature": "Oil",
    "Ambient temperature": "Ambient",
    "Engine speed": "Engine speed",
    "Vehicle speed": "Speed",
    "Battery voltage": "Battery",
}
SIZES = {"char": 1, "int": 2, "integer": 2, "long": 4}


def _number(value: object, default: float) -> float:
    """PRG tables use "-" for the identity scaling default."""
    return default if value == "-" else float(str(value))


def build(rows_path: Path, mil_path: Path, output: Path) -> None:
    """Emit one ordered row list per exact engine definition name."""
    raw = rows_path.read_bytes()
    rows = json.loads(raw)["verified"]
    mil = json.loads(mil_path.read_text())["engines"]
    direct = {row["name"] for row in mil.values() if row.get("state") == "scalar-boolean"}
    engines: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        name = row["definition"].upper()
        label = LABELS.get(row["label"])
        if (
            name not in direct
            or label is None
            or row["prg_lh"][:1] in ("l", "L")
            or row["unit"] in ("", "-")  # no physical unit recovered
        ):
            continue
        # Require numeric agreement of the APK definition and PRG table scaling.
        if (
            _number(row["prg_mul"], 1.0) != float(row["mul"])
            or _number(row["prg_div"], 1.0) != float(row["div"])
            or _number(row["prg_add"], 0.0) != float(row["add"])
            or row["prg_unit"] != row["unit"]
        ):
            continue
        signed, kind = row["type"].split()
        entry = {
            "did": int(row["did"], 16),
            "label": label,
            "size": SIZES[kind],
            "signed": signed == "signed",
            "mul": float(row["mul"]),
            "div": float(row["div"]),
            "add": float(row["add"]),
            "unit": row["unit"],
            "prg_sha256": row["prg_sha256"],
        }
        current = engines.setdefault(name, [])
        if any(other["label"] == label for other in current):
            continue  # first agreed row per label, in recovery order
        current.append(entry)
    asset = {
        "schema": 1,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "engines": dict(sorted(engines.items())),
    }
    output.write_text(json.dumps(asset, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("rows", type=Path)
    cli.add_argument("mil", type=Path)
    cli.add_argument("output", type=Path)
    args = cli.parse_args()
    build(args.rows, args.mil, args.output)
