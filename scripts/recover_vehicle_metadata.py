"""Recover the English vehicle-equipment catalogue from the supplied APK.

Development-only; original class/method anchors are recorded in
``docs/evidence/task-b-vehicle-metadata.md``.
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

from Crypto.Cipher import AES

SOURCE_SHA256 = "fc6eedeb741cbec49f46c126f8c72dac6a3dd1455f8a993c028695642459b728"
KEY = bytes.fromhex("D79BC058046DBD081FE8C1EAF05791C3")
IV = bytes.fromhex("FB69C011B6197B7245E40CF84BF209D2")
EDITORIAL_SUBSTITUTIONS = {
    "IST1": {
        "original": "ISTA simulation tests",
        "replacement": "Diagnostic simulation checks",
        "reason": "Keep development tool names out of shipped labels (AGENTS.md)",
    }
}


def recover(apk: Path, destination: Path, provenance: Path) -> None:
    """Retain exact passenger-vehicle selection, never motorcycle collisions."""
    if hashlib.sha256(apk.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("This recovery contract requires the inventoried APK version")
    with ZipFile(apk) as archive:
        raw = archive.read("assets/salapa.enc")
    plain = AES.new(KEY, AES.MODE_CBC, IV).decrypt(raw)
    padding = plain[-1]
    if not 1 <= padding <= 16 or plain[-padding:] != bytes([padding]) * padding:
        raise ValueError("Invalid metadata padding")
    plain = gzip.decompress(plain[:-padding])
    rows = json.loads(plain)
    equipment = {}
    types: dict[str, int] = {}
    for row in rows:
        types[row["type"]] = types.get(row["type"], 0) + 1
        if row["type"] != "P":
            continue
        code = row["name"].upper()
        label = row["en"]
        if code in equipment or not isinstance(label, str) or not label.strip():
            raise ValueError("Duplicate or incomplete passenger equipment row")
        if code in EDITORIAL_SUBSTITUTIONS:
            substitution = EDITORIAL_SUBSTITUTIONS[code]
            if label != substitution["original"]:
                raise ValueError("The recorded editorial source label no longer matches")
            label = substitution["replacement"]
        equipment[code] = label
    if not EDITORIAL_SUBSTITUTIONS.keys() <= equipment.keys():
        raise ValueError("A recorded editorial source code is missing")
    encoded = json.dumps(
        {"schema": 1, "equipment": equipment},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    destination.write_bytes(encoded + b"\n")
    provenance.write_text(
        json.dumps(
            {
                "source_sha256": SOURCE_SHA256,
                "member": "assets/salapa.enc",
                "member_sha256": hashlib.sha256(raw).hexdigest(),
                "plain_sha256": hashlib.sha256(plain).hexdigest(),
                "rows": len(rows),
                "types": types,
                "equipment": len(equipment),
                "editorial_substitutions": EDITORIAL_SUBSTITUTIONS,
                "asset_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("provenance", type=Path)
    args = parser.parse_args()
    recover(args.apk, args.destination, args.provenance)
