"""Generate a standalone virtual HSFZ vehicle from bundled source contracts."""

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.coding import decode_cafd_identifiers  # noqa: E402
from app.coding_db import CodingDatabase, _number  # noqa: E402
from app.coding_write import _groups  # noqa: E402
from app.demo_vehicle import (  # noqa: E402
    CAPTURED_DEMO_PROFILE,
    HEADUNIT_ENTITLEMENT_LIST,
    DemoVehicle,
)
from app.history_files import valid_vin  # noqa: E402
from app.ista_data import IstaDataSource  # noqa: E402
from app.vehicle import decode_inventory  # noqa: E402


def build(asset_root: Path = ROOT) -> dict:
    """Create deterministic data; no captured owner identity or runtime source access."""
    db = CodingDatabase(str(asset_root / "coding_data"))
    source = IstaDataSource.from_paths(asset_root / "ista_bundle", None)
    identities = source.uds_variants()
    selected = {
        "ZGW_01": ("10 0F1310", None),
        "DME_BX8": ("12 0F1D20", None),
        "DSC_I1": ("29 0F1970", None),
        "IHX_I1": ("78 0F1C70", None),
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
    contracts = json.loads((asset_root / "coding_data/mil_contracts.json").read_text())
    mil_did = f"{contracts['engines'][selected['DME_BX8'][0]]['did']:04X}"
    ecus["12"]["reads"][mil_did] = "01"
    ecus["12"]["clear_lamp_did"] = mil_did
    ecus["12"]["faults"] = [{"code": "118001", "status": 8}]
    ecus["63"]["faults"] = [{"code": "B7F805", "status": 8}]
    ecus["12"]["cbs"] = [bytes((1, 1, 44, 1, 3, 20, 255, 11, 26, 0, 0, 0)).hex()]
    ecus["60"]["cbs"] = [
        bytes((3, 128, 0, 1, 2, 100, 255, 11, 28, 24, 0, 0)).hex(),
        bytes((17, 11, 54, 1, 3, 47, 50, 9, 28, 48, 0, 0)).hex(),
    ]
    from app.service_wipers import demo_reads as wiper_reads
    from scripts.recover_service_observations import demo_reads

    for ecu in ecus.values():
        ecu["reads"].update(demo_reads(ecu["name"]))
        ecu["reads"].update(wiper_reads(ecu["name"]))
    ecus["40"]["reads"].update({"D330": "01", "D32F": "00"})
    ecus["29"]["reads"]["DBE4"] = (bytes(15) + bytes((80, 85, 90, 95))).hex()
    return {"schema": 1, "vin": vin, "ecus": ecus}


UDS_LOG = re.compile(
    r"app\.protocol\.udsoncan_connection: UDS (TX|RX) "
    r"conn=(\w+) operation=(\w+) request=(\w+) ecu=0x([0-9a-fA-F]{4}) "
    r"data=([0-9a-fA-F ]+)$"
)


def captured_replies(path: Path) -> dict[tuple[int, bytes], bytes]:
    """Pair addressed exchanges from one HSFZ generation, keeping the last final read."""
    pending: dict[tuple[str, str, str, int], bytes] = {}
    generations: dict[str, dict[tuple[int, bytes], bytes]] = {}
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            match = UDS_LOG.search(line.rstrip())
            if match is None:
                continue
            direction, connection, operation, request_id, address_hex, data = match.groups()
            address = int(address_hex, 16)
            if address > 0xFF:
                continue
            key = (connection, operation, request_id, address)
            pdu = bytes.fromhex(data)
            if direction == "TX":
                if (
                    (len(pdu) == 3 and pdu[0] == 0x22)
                    or pdu[:1] == b"\x19"
                    or pdu == HEADUNIT_ENTITLEMENT_LIST
                ):
                    pending[key] = pdu
                continue
            request = pending.get(key)
            if request is None:
                continue
            negative = len(pdu) == 3 and pdu[:2] == bytes((0x7F, request[0]))
            if negative and pdu[2] == 0x78:
                continue
            echo = (
                bytes((request[0] + 0x40,)) + request[1 : {0x22: 3, 0x19: 2, 0x31: 4}[request[0]]]
            )
            if negative or pdu.startswith(echo):
                pending.pop(key)
                generations.setdefault(connection, {})[address, request] = pdu
    snapshots = [
        replies
        for replies in generations.values()
        if replies.get((0x10, b"\x22\xf1\x90"), b"").startswith(b"\x62\xf1\x90")
        and replies.get((0x10, b"\x22\x3f\x07"), b"").startswith(b"\x62\x3f\x07")
    ]
    if len(snapshots) != 1:
        raise ValueError("Expected one captured HSFZ connection with gateway VIN and ECU inventory")
    return snapshots[0]


def build_capture(path: Path, asset_root: Path, observed_mil: str | None) -> dict[str, Any]:
    """Compile captured read replies into a private standalone starting snapshot."""
    replies = captured_replies(path)
    vin = replies[0x10, b"\x22\xf1\x90"][3:].decode("ascii")
    if not valid_vin(vin):
        raise ValueError("Captured gateway VIN is invalid")
    inventory = decode_inventory(replies[0x10, b"\x22\x3f\x07"])
    if 0x10 not in inventory:
        raise ValueError("Captured inventory omits the gateway")
    db = CodingDatabase(str(asset_root / "coding_data"))
    variants = IstaDataSource.from_paths(asset_root / "ista_bundle", None).uds_variants()
    contracts = json.loads((asset_root / "coding_data/mil_contracts.json").read_text())["engines"]
    ecus: dict[str, dict[str, Any]] = {}
    mil_added = False
    for address in inventory:
        reads, responses = {}, {}
        for (target, request), reply in replies.items():
            if target != address:
                continue
            if request[0] == 0x22 and reply[0] == 0x62:
                reads[request[1:].hex().upper()] = reply[3:].hex()
            else:
                responses[request.hex()] = reply.hex()
        key = f"{address:02X} {reads.get('F150', '')[:6].upper()}"
        ecu: dict[str, Any] = {"reads": reads, "blocks": {}, "responses": responses}
        ecus[f"{address:02X}"] = ecu
        software = reads.get("F101")
        if software is not None:
            try:
                definitions = list(decode_cafd_identifiers(bytes.fromhex("62f101" + software)))
                if definitions and not db.easy_coding_block_reason(definitions):
                    for did in _groups(db, definitions):
                        field = f"{did:04X}"
                        if field in reads:
                            ecu["blocks"][field] = reads.pop(field)
            except (LookupError, ValueError):
                # The reads still replay so the production coding path can report its own outcome.
                pass
        service = reads.get("1001")
        if service is not None and len(service) % 24 == 0:
            ecu["cbs"] = [service[i : i + 24] for i in range(0, len(service), 24)]
            reads.pop("1001")
        lamp = contracts.get(key)
        if observed_mil is not None and lamp and lamp["state"] == "scalar-boolean":
            if lamp["name"] != variants.get(key):
                raise ValueError("Captured engine identity does not match the MIL definition")
            did = f"{lamp['did']:04X}"
            if did in reads or f"22{did.lower()}" in responses:
                raise ValueError("The capture already contains a lamp read; omit --observed-mil")
            reads[did] = "01" if observed_mil == "on" else "00"
            mil_added = True
    if observed_mil is not None and not mil_added:
        raise ValueError("No exact scalar lamp contract for the captured engine")
    metadata = {"session": path.name}
    if observed_mil is not None:
        metadata["observed_mil"] = observed_mil
    return {"schema": 1, "vin": vin, "capture": metadata, "ecus": ecus}


def _write_capture(destination: Path, data: dict[str, Any]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=destination.parent, prefix=".demo-", delete=False
    ) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(data, stream, indent=2)
            stream.write("\n")
            stream.close()
            DemoVehicle(temporary)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-root", type=Path, default=ROOT)
    parser.add_argument("--capture", type=Path, help="Compile a private profile from a DEBUG log")
    parser.add_argument(
        "--observed-mil", choices=("on", "off"), help="Lamp state observed in person"
    )
    args = parser.parse_args()
    root = args.asset_root.resolve()
    if args.capture is not None:
        destination = CAPTURED_DEMO_PROFILE
        _write_capture(destination, build_capture(args.capture, root, args.observed_mil))
    else:
        if args.observed_mil is not None:
            parser.error("--observed-mil requires --capture")
        destination = root / "assets" / "demo_vehicle.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(build(root), indent=2) + "\n", encoding="utf-8")
    print(destination)
