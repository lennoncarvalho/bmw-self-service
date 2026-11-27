"""Bind the reviewed speed and engine-speed observations to the current canonical jobs."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ista_data import DataFormatError, read_job_table  # noqa: E402
from scripts.recover_power_readers import _write  # noqa: E402


def build(ecu_dir: Path, measurements: Path) -> dict:
    """Keep exact scalar encodings shared by the reviewed decoder and current job table."""
    profiles = {}
    for name, rows in json.loads(measurements.read_bytes())["engines"].items():
        path = ecu_dir / f"{name.lower()}.prg"
        if not path.is_file():
            continue
        try:
            columns, data = read_job_table(path, "SG_FUNKTIONEN")
        except DataFormatError:
            continue
        fields = [dict(zip(columns, record, strict=True)) for record in data]
        matched = []
        for row in rows:
            if row["label"] not in {"Speed", "Engine speed"}:
                continue
            candidates = [field for field in fields if field["ID"].upper() == f"0X{row['did']:04X}"]
            for field in candidates:
                try:
                    signed, kind = field["DATENTYP"].lower().split()
                    size = {"char": 1, "int": 2, "integer": 2, "long": 4}[kind]
                    scale = tuple(
                        default if field[key] == "-" else float(field[key])
                        for key, default in (("MUL", 1), ("DIV", 1), ("ADD", 0))
                    )
                except (KeyError, ValueError):
                    continue
                if (
                    len(candidates) == 1
                    and signed in {"signed", "unsigned"}
                    and (signed == "signed") == row["signed"]
                    and size == row["size"]
                    and field["L/H"].lower() == "high"
                    and "22" in field["SERVICE"].split(";")
                    and row["unit"] == field["EINHEIT"]
                    and scale == (row["mul"], row["div"], row["add"])
                ):
                    matched.append(row["did"])
        if len(matched) == 2:
            profiles[name] = {
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "dids": matched,
            }
    return {
        "schema": 1,
        "measurements_sha256": hashlib.sha256(measurements.read_bytes()).hexdigest(),
        "engines": profiles,
    }


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("ecu_dir", type=Path)
    cli.add_argument("measurements", type=Path)
    cli.add_argument("output", type=Path)
    args = cli.parse_args()
    _write(args.output, build(args.ecu_dir, args.measurements))
