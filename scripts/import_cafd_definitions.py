"""Convert development-decrypted CAFD XML to exact runtime group definitions.

This is a format conversion, not a source of friendly labels or vehicle defaults.
Literal stripped names remain stripped; no near-version naming is inferred.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path

NAMESPACE = "http://bmw.com/2005/psdz.data.caf"
NS = {"c": NAMESPACE}
MAX_XML = 64 * 1024 * 1024
CODING_PROOF_STAMP_BYTES = 8


def _values(parent: ET.Element | None) -> list[dict[str, str]]:
    """Decode unique positioned XML byte values with explicit bounds."""
    if parent is None:
        return []
    result = []
    positions = set()
    for unit in parent.findall("c:unitVal", NS):
        position = unit.get("position", "")
        value = (unit.text or "").strip()
        if not position.isdecimal() or not re.fullmatch(r"[0-9A-Fa-f]{2}", value):
            raise ValueError("CAFD unit value is not a positioned byte")
        number = int(position)
        if number > 65535 or number in positions:
            raise ValueError("CAFD value position exceeds its bound or is duplicated")
        positions.add(number)
        result.append({"position": str(number), "value": "0x" + value.upper()})
    return result


def convert(path: Path) -> tuple[str, dict]:
    """Convert a byte-layout plaintext CAFD, preserving conditions and source names."""
    if not 0 < path.stat().st_size <= MAX_XML:
        raise ValueError("CAFD XML exceeds its supported bound")
    if path.suffix == ".gz":
        with gzip.GzipFile(fileobj=io.BytesIO(path.read_bytes())) as stream:
            raw = stream.read(MAX_XML + 1)
    else:
        raw = path.read_bytes()
    return convert_bytes(raw)


def _coding_area_layout(root: ET.Element, header: ET.Element, raw: bytes) -> dict:
    """Preserve the separate NCD envelope and its virtual function groups."""
    if root.get("version") not in {"02.00.00", "02.00.01"}:
        raise ValueError("CAFD coding-area version is not supported")
    area, sig_id, sig_len = (header.get(field, "") for field in ("codingArea", "sigId", "sigLen"))
    default = header.get("defVal", "")
    crc_default = header.get("obdCrc32")
    if (
        not re.fullmatch(r"[0-9]{1,3}", area)
        or int(area) > 255
        or not re.fullmatch(r"[0-9]{2}", sig_id)
        or not re.fullmatch(r"[0-9]{1,5}", sig_len)
        or not 0 < int(sig_len) <= 65535
        or not re.fullmatch(r"[0-9A-Fa-f]{2}", default)
        or (crc_default is not None and not re.fullmatch(r"[0-9A-Fa-f]{8}", crc_default))
    ):
        raise ValueError("Invalid CAFD coding area or signature metadata")
    groups = {}
    for group in root.findall("c:metaData/c:groups/c:group", NS):
        group_id = group.get("id", "")
        if not re.fullmatch(r"[0-9]{1,10}", group_id) or int(group_id) in groups:
            raise ValueError("Invalid or duplicated virtual CAFD group")
        groups[int(group_id)] = group.text or ""
    functions = []
    for function in root.findall("c:data/c:function", NS):
        start, end, mask = (
            function.findtext(f"c:storageInfo/c:{key}", default="", namespaces=NS)
            for key in ("start", "end", "mask")
        )
        group_id = function.get("groupId", "")
        if (
            not re.fullmatch(r"[0-9]{1,5}", start)
            or not re.fullmatch(r"[0-9]{1,5}", end)
            or not 0 <= int(start) <= int(end) < 65536
            or not re.fullmatch(r"[0-9A-Fa-f]{2}", mask)
            or not re.fullmatch(r"[0-9]{1,10}", group_id)
            or int(group_id) not in groups
        ):
            raise ValueError("Invalid CAFD coding-area function storage")
        params = []
        for parameter in function.findall("c:condParam", NS):
            value = parameter.findtext("c:value", default="", namespaces=NS).strip()
            if not re.fullmatch(r"[0-9A-Fa-f]+", value) or len(value) != 2 * (
                int(end) - int(start) + 1
            ):
                raise ValueError("CAFD coding-area parameter width differs from its storage")
            params.append(
                {
                    "paramName": parameter.findtext("c:paramName", default="", namespaces=NS),
                    "value": value,
                    "conditions": [
                        {"attributes": dict(e.attrib), "expression": e.text or ""}
                        for e in parameter.findall("c:bool", NS)
                    ],
                }
            )
        functions.append(
            {
                "name": function.get("name", ""),
                "virtualGroup": int(group_id),
                "storageInfo": {"start": int(start), "end": int(end), "mask": mask},
                "params": params,
            }
        )
    if not functions or min(function["storageInfo"]["start"] for function in functions) != 0:
        raise ValueError("CAFD coding-area layout must have a zero-based function range")
    payload_length = 1 + max(function["storageInfo"]["end"] for function in functions)
    return {
        "codingAreaLayout": {
            "codingArea": int(area),
            "signatureId": sig_id,
            "payloadLength": payload_length,
            "proofStampLength": CODING_PROOF_STAMP_BYTES,
            "signatureLength": int(sig_len),
            "ncdLength": payload_length + CODING_PROOF_STAMP_BYTES + int(sig_len),
            "defaultByte": default,
            "obdCrc32Default": crc_default,
            "virtualGroups": [{"id": number, "name": name} for number, name in groups.items()],
            "functions": functions,
        },
        "sourceDefinition": {
            "xml_sha256": hashlib.sha256(raw).hexdigest(),
            "schemaVersion": root.get("version"),
        },
    }


def convert_bytes(raw: bytes) -> tuple[str, dict]:
    """Convert bounded XML bytes after the caller checked source provenance."""
    if not 0 < len(raw) <= MAX_XML:
        raise ValueError("CAFD XML exceeds its supported bound")
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("CAFD XML document type/entity declarations are unsupported")
    root = ET.fromstring(raw)
    if root.tag != f"{{{NAMESPACE}}}caf" or root.get("isEncrypted") != "false":
        raise ValueError("CAFD is not a plaintext source definition")
    header = root.find("c:sweHeader", NS)
    if header is None:
        raise ValueError("CAFD header is missing")
    identity = header.find("c:cafIdent", NS)
    if identity is None:
        raise ValueError("CAFD identity is missing")
    cafd_id = identity.findtext("c:id", namespaces=NS)
    versions = [
        identity.findtext(f"c:{part}Version", namespaces=NS) for part in ("main", "sub", "patch")
    ]
    if (
        cafd_id is None
        or not re.fullmatch(r"[0-9A-Fa-f]{8}", cafd_id)
        or any(v is None or not v.isdecimal() or not 0 <= int(v) <= 255 for v in versions)
    ):
        raise ValueError("CAFD identity/version is invalid")
    identifier = (
        cafd_id.upper() + "-" + "-".join(f"{int(v):03d}" for v in versions if v is not None)
    )
    if header.get("memoryLayout") != "BYTE":
        if header.get("memoryLayout") is None and header.get("codingArea") is not None:
            return identifier, _coding_area_layout(root, header, raw)
        raise ValueError("CAFD memory layout is unsupported")
    groups = []
    addresses = set()
    for group in root.findall("c:data/c:datagroup", NS):
        address, units = group.get("address", ""), group.get("units", "")
        if not re.fullmatch(r"[0-9A-Fa-f]{1,4}", address) or not re.fullmatch(
            r"[0-9A-Fa-f]{1,8}", units
        ):
            raise ValueError("CAFD group address/size is invalid")
        did, length = int(address, 16), int(units, 16)
        if did in addresses or not 0 < length <= 65536:
            raise ValueError("CAFD group address is repeated or length exceeds its bound")
        addresses.add(did)
        item = {
            "address": f"0x{did:04X}",
            "name": group.get("name", ""),
            "dataGroupClass": group.get("datagroupClass", ""),
            "units": length,
            "functions": [],
        }
        condition = group.find("c:activatingCondition", NS)
        if condition is not None:
            item["activatingConditionXml"] = ET.tostring(condition, encoding="unicode")
        for function in group.findall("c:function", NS):
            storage = function.find("c:storageInfo", NS)
            if storage is None:
                raise ValueError("CAFD function storage is missing")
            start, end = (
                storage.findtext("c:start", namespaces=NS),
                storage.findtext("c:end", namespaces=NS),
            )
            mask = storage.findtext("c:mask", namespaces=NS) or ""
            if (
                start is None
                or end is None
                or not start.isdecimal()
                or not end.isdecimal()
                or not 0 <= int(start) <= int(end) < length
                or not re.fullmatch(r"[01]{1,8}b", mask)
            ):
                raise ValueError("CAFD function range/mask is unsupported")
            params = []
            for parameter in function.findall("c:condParam", NS):
                entry = {
                    "paramName": parameter.findtext("c:paramName", default="", namespaces=NS),
                    "values": _values(parameter.find("c:values", NS)),
                    "conditions": [
                        {"attributes": dict(e.attrib), "expression": e.text or ""}
                        for e in parameter.findall("c:bool", NS)
                    ],
                }
                if any(int(v["position"]) > int(end) - int(start) for v in entry["values"]):
                    raise ValueError("CAFD parameter value exceeds function storage")
                params.append(entry)
            item["functions"].append(
                {
                    "name": function.get("name", ""),
                    "storageInfo": {
                        "start": str(int(start)),
                        "end": str(int(end)),
                        "mask": "0b" + mask[:-1],
                    },
                    "params": params,
                    "defaultValues": _values(function.find("c:defVal", NS)),
                }
            )
        groups.append(item)
    if not groups:
        raise ValueError("CAFD has no source data groups")
    sign = header.get("ncdSignAddress", "")
    signature = f"0x{int(sign, 16):04X}" if re.fullmatch(r"[0-9A-Fa-f]{1,4}", sign) else None
    return identifier, {
        "dataGroups": groups,
        "sourceDefinition": {
            "xml_sha256": hashlib.sha256(raw).hexdigest(),
            "memoryLayout": "BYTE",
            "ncdSignAddress": signature,
            "sourceNcdSignAddress": sign,
            "userLabelsAvailable": any(
                f["name"] not in ("", ".")
                for g in groups
                if g["dataGroupClass"] == "USER"
                for f in g["functions"]
            ),
        },
    }


def converted_documents(
    directory: Path, dispositions: dict[str, str] | None = None
) -> Iterator[tuple[str, dict, str]]:
    """Yield hash-checked converted definitions from a completed development export."""
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file() or manifest_path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("Decrypted definition manifest is missing or too large")
    manifest = json.loads(manifest_path.read_bytes())
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("documents"), dict):
        raise ValueError("Unsupported decrypted definition manifest")
    for relative, row in sorted(manifest["documents"].items()):
        if row.get("kind") != "cafd":
            continue
        if not re.fullmatch(r"cafd/[0-9A-F]{8}-[0-9]{3}-[0-9]{3}-[0-9]{3}\.xml\.gz", relative):
            raise ValueError("Decrypted definition path is not canonical")
        path = directory / relative
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_XML:
            raise ValueError("Decrypted definition member is unavailable or too large")
        compressed = path.read_bytes()
        if hashlib.sha256(compressed).hexdigest() != row.get("gzip_sha256"):
            raise ValueError("Decrypted definition compressed hash changed")
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
            raw = stream.read(MAX_XML + 1)
        if len(raw) != row.get("xml_bytes") or hashlib.sha256(raw).hexdigest() != row.get(
            "xml_sha256"
        ):
            raise ValueError("Decrypted definition XML hash or size changed")
        source_hash = row.get("source_sha256")
        if not isinstance(source_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", source_hash):
            raise ValueError("Decrypted definition source identity is missing")
        try:
            identity, definition = convert_bytes(raw)
        except (ValueError, ET.ParseError) as error:
            if dispositions is None:
                raise
            dispositions[row["identifier"]] = str(error)
            continue
        if identity != row.get("identifier") or relative != f"cafd/{identity}.xml.gz":
            raise ValueError("Decrypted definition identity differs from its manifest")
        yield identity, definition, source_hash
