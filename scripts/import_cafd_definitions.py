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
    if header is None or header.get("memoryLayout") != "BYTE":
        raise ValueError("CAFD memory layout is not the supported byte layout")
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
