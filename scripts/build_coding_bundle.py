"""Build the standalone coding catalogue from recovered local encrypted assets.

Development-only: no car access. Output contains compressed plaintext JSON,
English/German labels and an integrity/provenance manifest, never source paths.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import sqlite3
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from Crypto.Cipher import AES

_KEY = bytes.fromhex("244326462948404D635166546A576E5A")
_IV = bytes.fromhex("7639792442264529482B4D6251655468")
MAX_DOCUMENT = 32 * 1024 * 1024
MAX_SOURCE = 16 * 1024 * 1024


def decode(path: Path) -> bytes:
    """Decrypt one existing asset and validate its padding and decoded JSON."""
    if not 0 < path.stat().st_size <= MAX_SOURCE:
        raise ValueError(f"Source asset size is unsupported: {path.name}")
    source = path.read_bytes()
    if len(source) % 16:
        raise ValueError(f"Encrypted asset is not block aligned: {path.name}")
    data = AES.new(_KEY, AES.MODE_CBC, _IV).decrypt(source)
    padding = data[-1]
    if not 1 <= padding <= 16 or data[-padding:] != bytes([padding]) * padding:
        raise ValueError(f"Invalid asset padding: {path.name}")
    data = data[:-padding]
    if data.startswith(b"\x1f\x8b"):
        import io

        with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
            data = stream.read(MAX_DOCUMENT + 1)
    if len(data) > MAX_DOCUMENT:
        raise ValueError(f"Decoded asset is too large: {path.name}")
    document = json.loads(data)
    if not isinstance(document, (dict, list)):
        raise ValueError(f"Asset is not a JSON collection: {path.name}")
    return json.dumps(document, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def strings(path: Path) -> dict[str, str]:
    """Decode the supplied quoted key/value label format without losing escapes."""
    text = path.read_text(encoding="utf-8")
    pairs = re.findall(r'("(?:[^"\\]|\\.)*")\s*=\s*("(?:[^"\\]|\\.)*")\s*;', text)
    result = {}
    for key, value in pairs:
        result[json.loads(key)] = json.loads(value)
    if not result:
        raise ValueError(f"No labels recovered from {path.name}")
    return result


def runtime_label(value: str, language: str) -> str:
    """Adapt source branding to generic instructions while preserving technical restrictions."""
    if language == "en":
        value = value.replace("using “BimmerLink”", "using a diagnostic service tool")
        value = value.replace("with BimmerCode", "with this coding option")
    elif language == "de":
        value = value.replace("mit „BimmerLink“", "mit einem Diagnosewerkzeug")
        value = value.replace("mit BimmerCode", "mit dieser Codieroption")
    if re.search(r"\b(?:BimmerCode|BimmerLink|BimmerDaten|EDIABAS|ISTA)\b", value, re.I):
        raise ValueError("A source-branded runtime instruction needs explicit adaptation")
    return value


def build(
    source_dir: Path,
    destination: Path,
    apk: Path | None = None,
    selection_evidence: Path | None = None,
    resource_strings: Path | None = None,
    ista_definitions: Path | None = None,
) -> dict:
    """Atomically publish a checked standalone SQLite catalogue."""
    paths = sorted(source_dir.glob("*.enc"))
    if not paths or len(paths) > 10_000:
        raise ValueError("Coding source inventory is empty or exceeds its bound")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".coding-catalog-", dir=destination.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    sources: dict[str, str] = {}
    counts = {"documents": 0, "definitions": 0, "root_entries": 0, "labels": 0}
    dispositions: dict[str, str] = {}
    try:
        with sqlite3.connect(temporary) as db:
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute(
                "CREATE TABLE documents(name TEXT PRIMARY KEY, sha256 TEXT NOT NULL, json_size INTEGER NOT NULL, data BLOB NOT NULL)"
            )
            db.execute(
                "CREATE TABLE labels(language TEXT NOT NULL, name TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY(language,name))"
            )
            db.execute("CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            for path in paths:
                data = decode(path)
                document = json.loads(data)
                sources[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
                db.execute(
                    "INSERT INTO documents VALUES(?,?,?,?)",
                    (
                        path.stem,
                        hashlib.sha256(data).hexdigest(),
                        len(data),
                        gzip.compress(data, compresslevel=6, mtime=0),
                    ),
                )
                counts["documents"] += 1
                if isinstance(document, dict) and isinstance(document.get("dataGroups"), list):
                    counts["definitions"] += 1
                if re.fullmatch(r"[0-9A-Fa-f]{8}", path.stem) and isinstance(document, list):
                    counts["root_entries"] += len(document)
            if ista_definitions is not None:
                import importlib.util

                module_spec = importlib.util.spec_from_file_location(
                    "cafd_definition_conversion",
                    Path(__file__).with_name("import_cafd_definitions.py"),
                )
                if module_spec is None or module_spec.loader is None:
                    raise ValueError("Definition converter is unavailable")
                converter = importlib.util.module_from_spec(module_spec)
                module_spec.loader.exec_module(converter)
                counts["imported_definitions"] = 0
                counts["retained_original_definitions"] = 0
                sources["decrypted-definition-manifest"] = hashlib.sha256(
                    (ista_definitions / "manifest.json").read_bytes()
                ).hexdigest()
                for name, definition, source_hash in converter.converted_documents(
                    ista_definitions, dispositions
                ):
                    if (
                        db.execute("SELECT 1 FROM documents WHERE name=?", (name,)).fetchone()
                        is not None
                    ):
                        counts["retained_original_definitions"] += 1
                        continue
                    data = json.dumps(
                        definition, ensure_ascii=False, separators=(",", ":"), allow_nan=False
                    ).encode()
                    if len(data) > MAX_DOCUMENT:
                        dispositions[name] = (
                            "Converted definition exceeds the bounded runtime document format"
                        )
                        continue
                    db.execute(
                        "INSERT INTO documents VALUES(?,?,?,?)",
                        (
                            name,
                            hashlib.sha256(data).hexdigest(),
                            len(data),
                            gzip.compress(data, compresslevel=6, mtime=0),
                        ),
                    )
                    sources[name + ".enc"] = source_hash
                    counts["documents"] += 1
                    counts["definitions"] += 1
                    counts["imported_definitions"] += 1
                    if counts["imported_definitions"] % 250 == 0:
                        print(
                            f"Compiled {counts['imported_definitions']} additional exact definitions",
                            flush=True,
                        )
            if apk is not None:
                with zipfile.ZipFile(apk) as package:
                    member = package.getinfo("assets/app.gz")
                    if not 0 < member.file_size <= MAX_SOURCE:
                        raise ValueError("Authorization package member exceeds its bound")
                    compressed = package.read(member)
                    ncd_member = package.getinfo("assets/k-slim-ncds.enc")
                    if not 0 < ncd_member.file_size <= MAX_SOURCE:
                        raise ValueError("Signing package member exceeds its bound")
                    ncd_encrypted = package.read(ncd_member)
                import io

                with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
                    raw = stream.read(MAX_DOCUMENT + 1)
                if len(raw) > MAX_DOCUMENT:
                    raise ValueError("Authorization data exceeds its bound")
                entries = json.loads(raw)
                if not isinstance(entries, list) or len(entries) > 10_000:
                    raise ValueError("Authorization entries have an unsupported shape")
                if len(ncd_encrypted) % 16:
                    raise ValueError("Signing package is not block aligned")
                ncd_raw = AES.new(
                    bytes.fromhex("D79BC058046DBD081FE8C1EAF05791C3"),
                    AES.MODE_CBC,
                    bytes.fromhex("FB69C011B6197B7245E40CF84BF209D2"),
                ).decrypt(ncd_encrypted)
                padding = ncd_raw[-1]
                if not 1 <= padding <= 16 or ncd_raw[-padding:] != bytes([padding]) * padding:
                    raise ValueError("Signing package padding is invalid")
                ncd_raw = ncd_raw[:-padding]
                if ncd_raw.startswith(b"\x1f\x8b"):
                    with gzip.GzipFile(fileobj=io.BytesIO(ncd_raw)) as stream:
                        ncd_raw = stream.read(MAX_DOCUMENT + 1)
                if len(ncd_raw) > MAX_DOCUMENT:
                    raise ValueError("Signing package exceeds decoded bound")
                ncd_entries = json.loads(ncd_raw)
                if not isinstance(ncd_entries, list) or len(ncd_entries) > 10000:
                    raise ValueError("Signing entries have unsupported shape")
                entries.extend(ncd_entries)
                for entry in entries:
                    if not isinstance(entry, dict) or not re.fullmatch(
                        r"[0-9A-Fa-f]{8}", entry.get("bootloaderID", "")
                    ):
                        raise ValueError("Authorization identifier is invalid")
                    entry["algorithm"] = int(entry.get("algorithm", -1))
                    entry["keyType"] = int(entry.get("keyType", -1))
                    if entry["algorithm"] not in (0, 1) or entry["keyType"] not in (0, 1, 2):
                        raise ValueError("Authorization algorithm or key type is unsupported")
                    if not isinstance(entry.get("keyString"), str) or not isinstance(
                        entry.get("digest"), str
                    ):
                        raise ValueError("Authorization material is incomplete")
                data = json.dumps(
                    entries, ensure_ascii=False, separators=(",", ":"), allow_nan=False
                ).encode()
                db.execute(
                    "INSERT INTO documents VALUES(?,?,?,?)",
                    (
                        "authorization",
                        hashlib.sha256(data).hexdigest(),
                        len(data),
                        gzip.compress(data, compresslevel=6, mtime=0),
                    ),
                )
                sources["authorization-package"] = hashlib.sha256(apk.read_bytes()).hexdigest()
                sources["authorization-member"] = hashlib.sha256(compressed).hexdigest()
                sources["signing-member"] = hashlib.sha256(ncd_encrypted).hexdigest()
                counts["documents"] += 1
                counts["authorization_entries"] = len(entries)
            if selection_evidence is not None:
                evidence_raw = selection_evidence.read_bytes()
                evidence = json.loads(evidence_raw)
                if apk is None or evidence.get("artifact_sha256") != sources.get(
                    "authorization-package"
                ):
                    raise ValueError("Selection evidence does not match the supplied package")
                methods = {}
                guard_methods = {}
                for record in evidence["records"]:
                    if (
                        record.get("subject", {}).get("digest", {}).get("sha256")
                        != evidence["artifact_sha256"]
                    ):
                        raise ValueError("Selection evidence mixes package identities")
                    canonical = record.get("parameters", {}).get("class_name")
                    method_name = record.get("parameters", {}).get("method_name")
                    if (
                        canonical
                        in {
                            "de.appomotive.bimmercode.models.s0$p$a$a",
                            "de.appomotive.bimmercode.models.s0$p$a",
                        }
                        and method_name == "b"
                    ) or (canonical == "de.appomotive.bimmercode.models.s0" and method_name == "V"):
                        normalized = record["normalized_result"]
                        if (
                            normalized["body_status"] != "available"
                            or normalized["source"]["status"] != "complete"
                        ):
                            raise ValueError("Coding guard source is incomplete")
                        guard_methods[canonical] = normalized["source"]["text"]
                    result = record["normalized_result"]
                    if result.get("class_name") not in {
                        "de.appomotive.bimmercode.models.o",
                        "de.appomotive.bimmercode.models.r0",
                    }:
                        continue
                    if (
                        result["source"]["status"] != "complete"
                        or result["body_status"] != "available"
                    ):
                        raise ValueError("Selection evidence is incomplete")
                    methods[result["method"]["name"]] = result["source"]["text"]
                groups = {}
                for name in ("q", "s", "t"):
                    groups[name] = [
                        int(value)
                        for value in re.findall(r"arrayList\.add\((\d+)\)", methods[name])
                    ]
                    if not groups[name]:
                        raise ValueError("Series category method has no recovered values")
                if "arrayList.addAll(s())" not in methods["y"]:
                    raise ValueError("Electric category union changed")
                groups["y"] = [
                    int(value) for value in re.findall(r"arrayList\.add\((\d+)\)", methods["y"])
                ] + groups["s"]
                selector = methods["L"]
                mapping = {}
                for tag, target in re.findall(
                    r'if \(str\.toLowerCase\(\)\.equals\("([^"]+)"\)\) \{\s*return ([qsty])\(\);',
                    selector,
                ):
                    mapping[tag] = groups[target]
                for tag, value in re.findall(
                    r'if \(str\.toLowerCase\(\)\.equals\("([^"]+)"\)\) \{\s*ArrayList<Integer> \w+ = new ArrayList<>\(\);\s*\w+\.add\((\d+)\);',
                    selector,
                ):
                    mapping[tag] = [int(value)]
                # Final source branch uses an inverted guard and one returned category.
                tail = re.search(
                    r'if \(!str\.toLowerCase\(\)\.equals\("([^"]+)"\)\).*?arrayList\d*\.add\((\d+)\);',
                    selector,
                    re.S,
                )
                if tail:
                    mapping[tail[1]] = [int(tail[2])]
                if len(mapping) != 40:
                    raise ValueError("Series selector coverage changed; review evidence")
                primary = re.findall(r'next\.a\(\)\.equals\("([0-9A-F]{8})"\)', methods["i"])
                if len(primary) != 13:
                    raise ValueError("Primary definition selector coverage changed")
                codes_text = guard_methods.get("de.appomotive.bimmercode.models.s0$p$a$a", "")
                address_text = guard_methods.get("de.appomotive.bimmercode.models.s0$p$a", "")
                request_text = guard_methods.get("de.appomotive.bimmercode.models.s0", "")
                critical_codes = re.findall(r'arrayList2\.add\("0x([0-9A-Fa-f]{6})"\)', codes_text)
                address_match = re.search(r"p\.this\.a\.a\(\) != (\d+)", address_text)
                request_match = re.search(r"new byte\[\]\{([0-9, \-]+)\}", request_text)
                if (
                    len(critical_codes) != 2
                    or address_match is None
                    or request_match is None
                    or "putBoolean(this.f6701b, true)" not in codes_text
                    or "s0.this.f6593d.toLowerCase()" not in address_text
                ):
                    raise ValueError("Coding guard source selectors changed or are missing")
                request = bytes(int(part.strip()) & 255 for part in request_match[1].split(","))
                if len(request) != 3 or request[0] != 0x19 or request[1] != 2:
                    raise ValueError("Coding guard is not the recovered fault-status request")
                coding_guards = [
                    {
                        "id": "critical-climate-coding",
                        "address": int(address_match[1]),
                        "request": request.hex(),
                        "critical_codes": [value.upper() for value in critical_codes],
                        "sticky": True,
                    }
                ]
                model_categories: dict[str, list[int]] = {}
                category_descriptions = {}
                if resource_strings is not None:
                    if resource_strings.stat().st_size > MAX_SOURCE:
                        raise ValueError("Resource strings exceed the development input bound")
                    labels = {
                        element.attrib["name"]: "".join(element.itertext())
                        for element in ET.parse(resource_strings).getroot()
                        if element.tag == "string" and "name" in element.attrib
                    }
                    cases = re.findall(
                        r"case ([^:]+):\s*return context\.getString\(R\.string\.([A-Za-z0-9_]+)\);",
                        methods["N"],
                    )
                    if len(cases) != 45:
                        raise ValueError("Vehicle-category description selector changed")
                    for selector, label in cases:
                        number = re.fullmatch(r"\d+", selector.strip())
                        if number is None:
                            number = re.search(r"/\* (\d+) \*/", selector)
                        if number is None or label not in labels:
                            raise ValueError("Vehicle-category resource mapping is incomplete")
                        category = int(number[0] if number.lastindex is None else number[1])
                        text = labels[label]
                        category_descriptions[str(category)] = text
                        for code in re.findall(r"\b[FGUI]\d{2,3}\b", text):
                            normalized = code[0] + f"{int(code[1:]):02d}"
                            model_categories.setdefault(normalized, []).append(category)
                    sources["selection-resource-strings"] = hashlib.sha256(
                        resource_strings.read_bytes()
                    ).hexdigest()
                data = json.dumps(
                    {
                        "series_categories": mapping,
                        "primary_definitions": primary,
                        "model_categories": model_categories,
                        "category_descriptions": category_descriptions,
                        "coding_guards": coding_guards,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
                db.execute(
                    "INSERT INTO documents VALUES(?,?,?,?)",
                    (
                        "selection",
                        hashlib.sha256(data).hexdigest(),
                        len(data),
                        gzip.compress(data, compresslevel=6, mtime=0),
                    ),
                )
                sources["selection-evidence"] = hashlib.sha256(evidence_raw).hexdigest()
                counts["documents"] += 1
            for language in ("en", "de"):
                path = source_dir / f"{language}.strings"
                labels = strings(path)
                sources[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
                db.executemany(
                    "INSERT INTO labels VALUES(?,?,?)",
                    (
                        (language, key, runtime_label(value, language))
                        for key, value in sorted(labels.items())
                    ),
                )
                counts["labels"] += len(labels)
            counts["exact_cafd_definitions"] = sum(
                bool(re.fullmatch(r"[0-9A-F]{8}-[0-9]{3}-[0-9]{3}-[0-9]{3}", row[0]))
                for row in db.execute("SELECT name FROM documents")
            )
            counts["unsupported_imported_definitions"] = len(dispositions)
            manifest = {
                "schema_version": 1,
                "original_definitions": sorted(
                    path.stem
                    for path in paths
                    if re.fullmatch(r"[0-9A-F]{8}-[0-9]{3}-[0-9]{3}-[0-9]{3}", path.stem)
                ),
                "counts": counts,
                "sources": sources,
                "definition_dispositions": dispositions,
            }
            db.execute(
                "INSERT INTO metadata VALUES(?,?)",
                ("manifest", json.dumps(manifest, sort_keys=True, separators=(",", ":"))),
            )
            db.execute("PRAGMA user_version=1")
            db.commit()
            if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise ValueError("Generated catalogue failed integrity check")
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        directory = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return manifest
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source_dir", type=Path, help="Development-only recovered coding_data directory"
    )
    parser.add_argument("destination", type=Path, help="Standalone coding_catalog.db path")
    parser.add_argument(
        "--apk",
        type=Path,
        help="Development-only supplied coding package for authorization entries",
    )
    parser.add_argument(
        "--selection-evidence",
        type=Path,
        required=True,
        help="Retained complete REA series selector evidence",
    )
    parser.add_argument(
        "--resource-strings",
        type=Path,
        help="Development-only decoded resource strings paired with package",
    )
    parser.add_argument(
        "--ista-definitions",
        type=Path,
        help="Development-only completed decrypted definition export",
    )
    arguments = parser.parse_args()
    print(
        json.dumps(
            build(
                arguments.source_dir,
                arguments.destination,
                arguments.apk,
                arguments.selection_evidence,
                arguments.resource_strings,
                arguments.ista_definitions,
            )["counts"],
            indent=2,
        )
    )
