"""Bind the reviewed speed and engine-speed observations to the current canonical jobs."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ediabas import JobEngine  # noqa: E402
from app.ista_data import (  # noqa: E402
    DataFormatError,
    read_group_assignments,
    read_job_table,
    uds_variant_map,
)
from scripts.recover_power_readers import _Peer, _run, _write  # noqa: E402


def wheel_readers(ecu_dir: Path) -> dict:
    """Verify the five standstill speeds, direction flags and signal quality for each DSC."""
    bases = [ecu_dir / f"{name}.prg" for name in ("dsc_i1", "dsc_25")]

    def layout(path: Path) -> tuple:
        _, rows = read_job_table(path, "SG_FUNKTIONEN")
        (row,) = [r for r in rows if r[0] == "GESCHWINDIGKEIT_RAD"]
        return (
            row[1],
            row[-3:],
            read_job_table(path, row[-1]),
            read_job_table(path, "TAB_DREHRICHTUNG"),
        )

    examples = [layout(p) for p in bases]
    assignment = uds_variant_map(read_group_assignments(ecu_dir / "t_grtb.prg"))
    request = bytes.fromhex("22dbe4")
    # Five signed speeds, five directions, then four separate quality bytes.
    payload = bytes(15) + bytes((80, 85, 90, 95))
    profiles = {}
    for name in sorted({v for v in assignment.values() if v.startswith("DSC_")}):
        path = ecu_dir / (name.lower() + ".prg")
        try:
            if layout(path) not in examples:
                continue
        except (ValueError, OSError, DataFormatError):
            continue
        addresses = {int(key.split()[0], 16) for key, v in assignment.items() if v == name}
        if len(addresses) != 1:
            continue
        peer = _Peer(addresses.pop())
        engine = JobEngine(peer)
        try:
            engine.load(path, ecu_dir=ecu_dir)
            job = {
                "job": "STATUS_LESEN",
                "args": "ARG;GESCHWINDIGKEIT_RAD",
                "request": request.hex(),
                "size": 3 + len(payload),
            }
            result = _run(engine, peer, job, payload)
            (values,) = result.sets
            quality = [
                key
                for key in values
                if key.startswith("STAT_SIGNALQUALITAET_") and key.endswith("_WERT")
            ]
            speeds = [
                key
                for key in values
                if key.startswith("STAT_GESCHWINDIGKEIT_") and key.endswith("_WERT")
            ]
            directions = [
                key
                for key in values
                if key.startswith("STAT_DREHRICHTUNG_") and values[key] == "Stand"
            ]
            if (
                len(speeds) != 5
                or len(directions) != 5
                or any(values[k] != 0 for k in speeds)
                or sorted(values[k] for k in quality) != [80, 85, 90, 95]
            ):
                raise ValueError(f"Unexpected standstill result fields for {name}")
            profiles[name] = dict(
                job,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                speeds=speeds,
                directions=directions,
                quality=quality,
            )
        finally:
            engine.close()
    return profiles


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
        "wheel_readers": wheel_readers(ecu_dir),
    }


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("ecu_dir", type=Path)
    cli.add_argument("measurements", type=Path)
    cli.add_argument("output", type=Path)
    args = cli.parse_args()
    _write(args.output, build(args.ecu_dir, args.measurements))
