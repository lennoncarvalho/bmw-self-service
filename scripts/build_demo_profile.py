"""Generate a standalone virtual HSFZ vehicle from bundled source contracts."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.coding_db import CodingDatabase, _number  # noqa: E402
from app.ista_data import IstaDataSource  # noqa: E402


def build(asset_root: Path = ROOT) -> dict:
    """Create deterministic data; no captured owner identity or runtime source access."""
    db = CodingDatabase(str(asset_root / "coding_data"))
    source = IstaDataSource.from_paths(asset_root / "ista_bundle", None)
    identities = source.uds_variants()
    selected = {
        "ZGW_01": ("10 0F1310", None),
        "DME_BX8": ("12 0F1D20", None),
        "BDC": ("40 0F19C0", "000017BE-005-016-064"),
        "KOMB25": ("60 0F1630", "00000760-007-003-017"),
        "NBT": ("63 0F1A30", "00000DED-001-016-001"),
    }
    vin = "WBA00000000000001"
    ecus = {}
    for name, (key, definition) in selected.items():
        if identities[key] != name:
            raise ValueError(f"Bundled identity changed: {key}")
        address, variant = key.split()
        reads = {"F150": variant, "F190": vin.encode().hex()}
        blocks = {}
        software = bytes.fromhex("62f10100000001000600000003010000")
        if definition:
            identifier, version = definition.split("-", 1)
            decoded = db.get_definition(identifier, version)
            for group in decoded["dataGroups"]:
                size = max(
                    (_number(f["storageInfo"]["end"]) + 1 for f in group["functions"]), default=1
                )
                blocks[_number(group["address"])] = bytes(size)
            blocks = db.finalize_write_blocks(blocks, [definition], "00000003")
            entry = bytes((5,)) + bytes.fromhex(identifier) + bytes(map(int, version.split("-")))
            software = bytes.fromhex("62f1010000000200") + entry + bytes.fromhex("0600000003010000")
        reads["F101"] = software[3:].hex()
        ecus[address] = {
            "name": name,
            "reads": reads,
            "blocks": {f"{did:04X}": value.hex() for did, value in blocks.items()},
            "faults": [],
            "cbs": [],
            "definition": definition,
            "job_sha256": hashlib.sha256(source.locate(name)[0].read_bytes()).hexdigest(),
        }
    # Packed six-bit gateway fields use the inverse of the recovered decoder.
    alphabet = {
        chr(base + low): group * 16 + low
        for group, base in enumerate((0, 48, 64, 80))
        for low in range(16)
    }
    bits = "00000001" + "".join(f"{alphabet[c]:06b}" for c in "0317F048JG31A300KCSW")
    bits += "1000" + "".join(f"{alphabet[c]:06b}" for c in "205249544") + "00"
    bits += "0" * (-len(bits) % 8)
    ecus["10"]["reads"].update(
        {
            "3F07": (len(ecus).to_bytes(2, "big") + bytes(int(a, 16) for a in ecus)).hex(),
            "3F06": "0000" + int(bits, 2).to_bytes(len(bits) // 8, "big").hex(),
            "100B": (b"F056" + bytes.fromhex("12070212")).hex() * 3,
        }
    )
    ecus["60"]["reads"].update({"D10D": (66000).to_bytes(4, "big").hex(), "D114": "00"})
    ecus["40"]["reads"]["1700"] = (66000).to_bytes(4, "big").hex()
    voltage = bytearray(28)
    voltage[2:4] = int((13.2 - 6) / 0.00025).to_bytes(2, "big")
    ecus["12"]["reads"]["402B"] = voltage.hex()
    # AEP INFO 2 uses the exact 32-byte positive reply checked by the power
    # reader compiler: SOH is unsigned byte minus 128; current SOC is byte 20.
    power = bytearray(29)
    power[1], power[17] = 90 + 128, 82
    ecus["12"]["reads"]["4023"] = power.hex()
    ecus["40"]["reads"]["DC56"] = "0a"
    values = {"Coolant": 90, "Engine speed": 0, "Speed": 0, "Ambient": 24, "Oil": 90}
    measurements = json.loads(
        (asset_root / "coding_data/engine_measurements.json").read_text(encoding="utf-8")
    )
    for row in measurements["engines"]["DME_BX8"]:
        raw = round((values[row["label"]] - row["add"]) * row["div"] / row["mul"])
        ecus["12"]["reads"][f"{row['did']:04X}"] = raw.to_bytes(row["size"], "big").hex()
    ecus["12"]["faults"] = [{"code": "118001", "status": 8}]
    ecus["63"]["faults"] = [{"code": "B7F805", "status": 8}]
    ecus["12"]["cbs"] = [bytes((1, 1, 44, 1, 3, 20, 255, 11, 26, 0, 0, 0)).hex()]
    ecus["60"]["cbs"] = [
        bytes((3, 0, 30, 2, 2, 10, 255, 11, 26, 0, 0, 0)).hex(),
        bytes((17, 1, 44, 1, 1, 20, 255, 11, 26, 0, 0, 0)).hex(),
    ]
    return {"schema": 1, "vin": vin, "ecus": ecus}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-root", type=Path, default=ROOT)
    root = parser.parse_args().asset_root.resolve()
    destination = root / "assets" / "demo_vehicle.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(build(root), indent=2) + "\n", encoding="utf-8")
    print(destination)
