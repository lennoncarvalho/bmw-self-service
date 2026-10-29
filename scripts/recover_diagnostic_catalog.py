"""Reproduce the generic diagnostic asset from the owner-supplied APK.

Research-only tool; not imported by the application. Native key provenance and
class/method anchors are in docs/evidence/task-b-recovered-contracts.md.
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

from Crypto.Cipher import AES

SOURCE_SHA256 = "da6f5b39efaa590fce68782f439c1b8f1b9f09ed41344055b8ff80666cae00d5"
KEY = bytes.fromhex("D79BC058046DBD081FE8C1EAF05791C3")
IV = bytes.fromhex("FB69C011B6197B7245E40CF84BF209D2")


def decode(raw: bytes) -> tuple[object, bytes]:
    """Decode the native-key AES/CBC/PKCS5 + GZIP data asset exactly."""
    plain = AES.new(KEY, AES.MODE_CBC, IV).decrypt(raw)
    padding = plain[-1]
    if not 1 <= padding <= 16 or plain[-padding:] != bytes([padding]) * padding:
        raise ValueError("Invalid data-asset padding")
    plain = plain[:-padding]
    if plain.startswith(b"\x1f\x8b"):
        plain = gzip.decompress(plain)
    return json.loads(plain), plain


def recover(apk: Path, destination: Path, provenance: Path) -> None:
    """Hash every input and preserve missing description coverage explicitly."""
    if hashlib.sha256(apk.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("This recovery contract requires the inventoried APK version")
    members = []
    with ZipFile(apk) as archive:
        names = {name.lower(): name for name in archive.namelist()}
        raw = archive.read("assets/dat/ecu-variants.enc")
        variants, plain = decode(raw)
        members.append(
            {
                "path": "assets/dat/ecu-variants.enc",
                "sha256": hashlib.sha256(raw).hexdigest(),
                "plain_sha256": hashlib.sha256(plain).hexdigest(),
            }
        )
        rows = {}
        descriptions = {}
        info = {}
        missing = []
        for variant in variants:
            index = variant["addressIndex"].upper()
            if index in rows:
                raise ValueError("Duplicate diagnostic address index")
            name = variant["descriptionFilename"]
            rows[index] = {"name": name, "description": variant["group"], "uds": variant["UDS"]}
            if not variant["UDS"] or name in descriptions:
                continue
            member = f"assets/dat/{name.lower()}.enc"
            if member not in names:
                if member not in missing:
                    missing.append(member)
                continue
            raw = archive.read(names[member])
            data, plain = decode(raw)

            def english(dictionary: dict) -> dict[str, str]:
                return {
                    code.upper().removeprefix("0X"): value["en"]
                    for code, value in dictionary.items()
                    if value.get("en")
                }

            descriptions[name] = english(data.get("errors", {}))
            info[name] = english(data.get("infoErrors", {}))
            members.append(
                {
                    "path": names[member],
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "plain_sha256": hashlib.sha256(plain).hexdigest(),
                }
            )
    catalog = {
        "schema": 1,
        "variants": rows,
        "descriptions": descriptions,
        "info_descriptions": info,
    }
    encoded = json.dumps(catalog, ensure_ascii=False, separators=(",", ":")).encode()
    destination.write_bytes(gzip.compress(encoded, mtime=0))
    provenance.write_text(
        json.dumps(
            {
                "source_sha256": SOURCE_SHA256,
                "members": members,
                "missing": sorted(missing),
                "variants": len(rows),
                "normal_english": sum(map(len, descriptions.values())),
                "information_english": sum(map(len, info.values())),
                "asset_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("provenance", type=Path)
    options = parser.parse_args()
    recover(options.apk, options.destination, options.provenance)
