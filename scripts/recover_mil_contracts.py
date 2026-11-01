"""Recover exact scalar MIL contracts and account for every catalogued engine.

Development-only BEST table/job inspection; no PRG interpreter enters runtime.
See docs/evidence/task-b-mil-breadth.md for the reviewed decoder fingerprints.
"""

import argparse
import gzip
import hashlib
import importlib.util
import json
import re
import struct
import sys
from pathlib import Path
from typing import Any

# Complete STATUS_LESEN listings normalized only for absolute BEST branch labels.
# Reviewed differences: maximum argument count and non-MIL special identifier lists.
REVIEWED_JOBS = {
    "211d8e9fb1141035244b0379ee629811365cebc6fdb278a914c73ab773ef4893",
    "4db6f236abfa7ad0bf9cc30e24bd7f71d7889c13a666055efa89b68a7ea69c12",
    "aeec47c5f4ff7476fb9548e761d577f5673c7fcb1f63349881a0594d206aee66",
    "003e4b778b0bf725b88dcdd9d982c8528355f4266c4b568547b992f1e0c0844e",
    "36f664998c2827d1c2742f4b7ab3b591a84deefec6843c7bb1369c72a4888a6e",
    "a71e62867f0b5a076d9ad05efce917dbca85c82482db2595d333194970e13789",
}
# Complete STATUS_BLOCK_LESEN listing shared by the five older engines; see
# docs/evidence/task-b-mil-block-recovery.md for clear/define/read echo checks.
REVIEWED_BLOCK_JOB = "6ddbe56e3449b7195d15a71d56d9475831dd0d6095987b4b6cc14a82503a9675"
# The source application's fixed dynamic slot for engine sensor selection (k6.c0.m).
BLOCK_SLOT = 0xF303


def recover(root: Path, parser_path: Path, output: Path, manifest: Path) -> None:
    """Select exact engine rows, preserving every non-enabled disposition."""
    spec = importlib.util.spec_from_file_location("mil_prg_reference", parser_path)
    if spec is None or spec.loader is None:
        raise ValueError("Reference BEST parser is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    catalog_raw = (root / "coding_data/diagnostic_catalog.json.gz").read_bytes()
    if hashlib.sha256(catalog_raw).hexdigest() != (
        "c988392c26b75e57551139b6cd82662befad808112025d568908348837bb44ab"
    ):
        raise ValueError("MIL recovery requires the reviewed diagnostic catalogue")
    catalog = json.loads(gzip.decompress(catalog_raw))
    engine_rows = {
        key: row for key, row in catalog["variants"].items() if key.startswith("12 ") and row["uds"]
    }
    files = {
        path.stem.upper(): path
        for path in (root / "sources/Ecu").iterdir()
        if path.suffix.lower() == ".prg"
    }
    definitions: dict[str, Any] = {}
    provenance: dict[str, Any] = {}
    for name in sorted({row["name"] for row in engine_rows.values()}):
        path = files.get(name.upper())
        if path is None:
            definitions[name] = {"state": "missing-definition"}
            continue
        parser = module.PrgParser(str(path))
        tables = parser._parse_tables()
        matches = [
            (index, dict(zip(table.columns, row.values, strict=True)))
            for table in tables
            if table.name.upper() == "SG_FUNKTIONEN"
            for index, row in enumerate(table.rows)
            if dict(zip(table.columns, row.values, strict=True)).get("ARG") == "ISMIL"
        ]
        source: dict[str, Any] = {
            "path": str(path.relative_to(root)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        source["boolean_labels"] = [
            dict(zip(table.columns, row.values, strict=True))
            for table in tables
            if table.name.upper() == "DIG_DDE_KOMBI"
            for row in table.rows
            if dict(zip(table.columns, row.values, strict=True)).get("NAME") == "S_MILLAMP"
        ]
        provenance[name] = source
        if not matches:
            definitions[name] = {"state": "no-direct-mil-row"}
            continue
        if len(matches) != 1:
            raise ValueError(f"Ambiguous MIL definition: {name}")
        index, row = matches[0]
        source.update({"table": "SG_FUNKTIONEN", "row": index, "values": row})
        offset = parser._get_int32_header(0x88)
        jobs = {}
        for i in range(parser._read_int32_raw(offset)):
            entry = parser._read_decrypted(offset + 4 + i * 0x44, 0x44)
            jobs[parser._read_null_string(entry[:0x40])] = struct.unpack_from("<i", entry, 0x40)[0]
        job = "STATUS_LESEN" if "STATUS_LESEN" in jobs else "STATUS_BLOCK_LESEN"
        if job not in jobs:
            raise ValueError(f"No reviewed MIL job: {name}")
        listing = "\n".join(parser._disassemble_job(jobs[job]))
        fingerprint = hashlib.sha256(
            re.sub(r"__[0-9A-F]+", "__LABEL", listing).encode()
        ).hexdigest()
        if fingerprint not in (REVIEWED_JOBS if job == "STATUS_LESEN" else {REVIEWED_BLOCK_JOB}):
            raise ValueError(f"Unreviewed MIL request/decoder: {name} {fingerprint}")
        if (
            row["DATENTYP"] != "unsigned char"
            or "22" not in re.split(r"[;,]", row["SERVICE"])
            or row["RES_TABELLE"] != "-"
            or row["ARG_TABELLE"] != "-"
            or row["SG_ADR"] not in ("12", "-")
            or row["MUL"] not in ("-", "1", "1.0", "1.000000")
            or row["DIV"] not in ("-", "1", "1.0", "1.000000")
            or row["ADD"] not in ("-", "0", "0.0", "0.000000")
        ):
            raise ValueError(f"MIL row has unreviewed encoding/scaling: {name}")
        did = int(row["ID"], 16)
        source.update({"job": job, "job_offset": jobs[job], "job_sha256": fingerprint})
        if job == "STATUS_LESEN":
            definitions[name] = {"state": "scalar-boolean", "did": did}
        elif "2C" in re.split(r"[;,]", row["SERVICE"]):
            definitions[name] = {"state": "dynamic-block", "did": did, "slot": BLOCK_SLOT}
        else:
            raise ValueError(f"MIL block row lacks dynamic definition service: {name}")
    asset = {
        "schema": 1,
        "engines": {
            key: {"name": row["name"], **definitions[row["name"]]}
            for key, row in sorted(engine_rows.items())
        },
    }
    encoded = (json.dumps(asset, indent=2, sort_keys=True) + "\n").encode()
    output.write_bytes(encoded)
    manifest.write_text(
        json.dumps(
            {
                "catalogue_engine_names": len(definitions),
                "catalogue_engine_rows": len(engine_rows),
                "parser_sha256": hashlib.sha256(parser_path.read_bytes()).hexdigest(),
                "asset_sha256": hashlib.sha256(encoded).hexdigest(),
                "definitions": provenance,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("root", type=Path)
    cli.add_argument("parser_path", type=Path)
    cli.add_argument("output", type=Path)
    cli.add_argument("manifest", type=Path)
    args = cli.parse_args()
    recover(args.root, args.parser_path, args.output, args.manifest)
