"""Compile separately retained source coding-reader contracts (development only)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path


def build(backup_evidence: Path, read_evidence: Path, output: Path) -> dict:
    """Validate complete same-artifact evidence and publish the small reader asset."""
    records = []
    hashes = {}
    for path in (backup_evidence, read_evidence):
        raw = path.read_bytes()
        if len(raw) > 16 * 1024 * 1024:
            raise ValueError("Reader evidence exceeds its supported bound")
        document = json.loads(raw)
        records.extend(document["records"])
        hashes[path.name] = hashlib.sha256(raw).hexdigest()
    source_hashes = {row["subject"]["digest"]["sha256"] for row in records}
    if len(source_hashes) != 1:
        raise ValueError("Reader evidence does not identify one source artifact")

    def method(class_name: str, name: str) -> str:
        matches = [
            row
            for row in records
            if row.get("parameters", {}).get("class_name", "").endswith(class_name)
            and row.get("parameters", {}).get("method_name") == name
        ]
        if not matches:
            raise ValueError(f"Reader method is absent: {class_name}.{name}")
        bodies = set()
        for row in matches:
            result = row["normalized_result"]
            if result["body_status"] != "available" or result["source"]["status"] != "complete":
                raise ValueError("Reader evidence contains an incomplete method")
            bodies.add(result["source"]["text"])
        if len(bodies) != 1:
            raise ValueError("Reader evidence disagrees on a method body")
        return bodies.pop()

    selector = method("models.n0", "t")
    if not re.search(r'a\(\) == 99 \|\| o\(\)\.equals\("00004224"\)', selector):
        raise ValueError("Unlock-backup selector differs from the recovered contract")
    verification = method("codingtasks.u", "u")
    moduli = re.findall(r'w\(bArr, "([0-9A-F]{256})"\)', verification)
    if len(moduli) != 2 or 'q().equals("0F2230")' not in verification:
        raise ValueError("Unlock-backup verification keys or selector are absent")
    digest = method("codingtasks.u", "w")
    for expected in ("bArr.length < 128", 'getInstance("MD5")', 'new BigInteger("03", 16)'):
        if expected not in digest:
            raise ValueError("Unlock-backup signature decoder differs")
    listing = method("codingtasks.u$d", "b")
    retrieval = method("codingtasks.u$e", "b")
    if "bArrB, 9, bArrB.length" not in listing or "length % 7" not in listing:
        raise ValueError("Unlock-backup listing layout differs")
    if "bArrB, 6, bArrB.length" not in retrieval:
        raise ValueError("Unlock-backup payload layout differs")
    for class_name, name, array in (
        ("codingtasks.u", "s", "16, 3"),
        ("codingtasks.u", "t", "16, 66"),
        ("codingtasks.u", "p", "49, 1, 15, 31, 4"),
        ("codingtasks.u", "o", "49, 1, 15, 31, 11"),
        ("codingtasks.u", "m", "16, 1"),
    ):
        if "new byte[]{" + array not in method(class_name, name):
            raise ValueError("Unlock-backup request differs")
    evo = method("models.s0", "L")
    prefixes = re.findall(r'contains\("([A-Z0-9]+-16-11-5)"\)', evo)
    if len(prefixes) != 4 or 'equals("0F2230")' not in evo:
        raise ValueError("Head-unit critical software selector differs")
    ram = method("models.s0$m", "b")
    hmi = method("models.s0$m$a", "b")
    if not all(value in ram for value in ("21", "12", "16", "-48, 63")):
        raise ValueError("Head-unit RAM/HMI read contract differs")
    if 'startsWith("NBTevo_ID5_"' not in hmi or "this.a < 4000000" not in hmi:
        raise ValueError("Head-unit memory condition differs")
    contract = {
        "schema_version": 1,
        "source_artifact_sha256": source_hashes.pop(),
        "source_evidence_sha256": hashes,
        "unlock_backup": {
            "address": 99,
            "primary_definition": "00004224",
            "list_request": "31010f1f04",
            "retrieve_prefix": "31010f1f0b",
            "sessions": ["1003", "1042"],
            "cleanup": "1001",
            "list_offset": 9,
            "entry_width": 7,
            "payload_offset": 6,
            "verify_variant": "0F2230",
            "public_exponent": 3,
            "moduli": moduli,
        },
        "nbtevo": {
            "address": 99,
            "variant": "0F2230",
            "ilevel_address": 16,
            "ilevel_request": "22100b",
            "critical_prefixes": prefixes,
            "ram_request": "22d00a",
            "raw_length": 21,
            "ram_offset": 12,
            "ram_width": 4,
            "ram_signed": True,
            "hmi_request": "22d03f",
            "hmi_prefix": "NBTevo_ID5_",
            "minimum_ram": 4000000,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".reader-contracts-", dir=output.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(contract, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, output)
    finally:
        Path(temporary_name).unlink(missing_ok=True)
    return contract


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup_evidence", type=Path)
    parser.add_argument("read_evidence", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    build(arguments.backup_evidence, arguments.read_evidence, arguments.output)
