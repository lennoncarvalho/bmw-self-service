"""Query the standalone vehicle coding catalogue and compose exact group changes.

The development builder supplies coding_catalog.db. Runtime reads no encrypted
source assets and contains no source-data decryption key. Definitions remain
separate from actual ECU blocks and vehicle write authorization.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import io
import json
import logging
import re
import sqlite3
from collections import Counter
from contextlib import closing
from pathlib import Path
from typing import Any

from app.resources import resource_path

logger = logging.getLogger(__name__)
MAX_DATABASE = 512 * 1024 * 1024
MAX_DOCUMENT = 32 * 1024 * 1024
MAX_MANIFEST = 4 * 1024 * 1024
_IDENTIFIER = re.compile(r"[0-9A-F]{8}")
_VARIANT = re.compile(r"[0-9]{3}-[0-9]{3}-[0-9]{3}")


def _number(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("Boolean is not a coding integer")
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        raise ValueError("Coding integer is missing")
    return int(value, 0) if value.startswith(("0x", "0b")) else int(value, 10)


class CodingDatabase:
    """Read exact definitions, labels and curated options from the built asset."""

    def __init__(self, data_dir: str | None = None) -> None:
        """Open metadata from the bundled catalogue without retaining a SQL connection."""
        directory = Path(data_dir) if data_dir else resource_path("coding_data")
        self.data_dir = str(directory)
        self.path = directory / "coding_catalog.db"
        self.strings: dict[str, str] = {}
        self.root_indexes: dict[str, list[dict]] = {}
        self.cafd_variants: dict[str, dict] = {}
        self._loaded_ecus: set[str] = set()
        self._function_indexes: dict[str, dict[str, list[tuple[int, dict]]]] = {}
        self._document_names: set[str] = set()
        self._manifest: dict = {}
        self._resolutions: dict[str, dict] = {}
        self._package_status: dict[str, bool] = {}
        self._load_metadata()

    def _connect(self) -> sqlite3.Connection:
        if not self.path.is_file() or not 0 < self.path.stat().st_size <= MAX_DATABASE:
            raise ValueError("Standalone vehicle coding catalogue is missing or too large")
        connection = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)
        connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_DOCUMENT + 4096)
        connection.execute("PRAGMA query_only=ON")
        return connection

    def _load_metadata(self) -> None:
        with closing(self._connect()) as connection:
            if connection.execute("PRAGMA user_version").fetchone() != (1,):
                raise ValueError("Unsupported coding catalogue schema")
            row = connection.execute(
                "SELECT value FROM metadata WHERE key=?", ("manifest",)
            ).fetchone()
            if row is None or not isinstance(row[0], str) or len(row[0]) > MAX_MANIFEST:
                raise ValueError("Coding catalogue manifest is missing or too large")
            manifest = json.loads(row[0])
            if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
                raise ValueError("Unsupported coding catalogue manifest")
            self._manifest = manifest
            rows = connection.execute("SELECT name FROM documents LIMIT 10001").fetchall()
            if len(rows) > 10_000:
                raise ValueError("Coding catalogue document inventory exceeds its bound")
            self._document_names = {row[0] for row in rows}
            labels = connection.execute(
                "SELECT language,name,value FROM labels LIMIT 20001"
            ).fetchall()
            if len(labels) > 20_000:
                raise ValueError("Coding catalogue labels exceed their bound")
            for language in ("de", "en"):
                self.strings.update(
                    {name: value for lang, name, value in labels if lang == language}
                )

    def manifest(self) -> dict:
        """Return detached build provenance and inventory counts."""
        return copy.deepcopy(self._manifest)

    def read_document(self, name: str) -> dict | list:
        """Read and integrity-check one bounded recovered JSON document by asset name."""
        if name.endswith(".enc"):
            name = name[:-4]
        if name not in self._document_names:
            raise ValueError("Exact coding document is unavailable")
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT sha256,json_size,data FROM documents WHERE name=?", (name,)
            ).fetchone()
        if row is None:
            raise ValueError("Coding document disappeared")
        digest, size, compressed = row
        if (
            not isinstance(size, int)
            or not 0 < size <= MAX_DOCUMENT
            or not isinstance(compressed, bytes)
            or len(compressed) > MAX_DOCUMENT
        ):
            raise ValueError("Coding document exceeds its supported bounds")
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
            data = stream.read(MAX_DOCUMENT + 1)
        if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("Coding document integrity check failed")
        document = json.loads(data)
        if not isinstance(document, (dict, list)):
            raise ValueError("Coding document is not a collection")
        return document

    def _source_hash(self, name: str) -> str:
        value = self._manifest.get("sources", {}).get(name + ".enc")
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError("Coding document provenance is unavailable")
        return value

    def _document_hash(self, name: str) -> str:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT sha256 FROM documents WHERE name=?", (name,)
            ).fetchone()
        if row is None or not isinstance(row[0], str):
            raise ValueError("Coding document integrity metadata is unavailable")
        return row[0]

    def _package_definition(self, name: str) -> bool:
        original = self._manifest.get("original_definitions")
        if isinstance(original, list):
            return name in original
        if name not in self._package_status:
            # Schema-1 catalogues from before explicit origin inventory are
            # unambiguous: imported XML alone carries sourceDefinition metadata.
            document = self.read_document(name)
            self._package_status[name] = (
                isinstance(document, dict) and "sourceDefinition" not in document
            )
        return self._package_status[name]

    def definition_resolution(self, reported: str) -> dict:
        """Resolve exact or source-compatible lower patches, retaining both identities."""
        if not isinstance(reported, str) or not re.fullmatch(
            r"[0-9A-F]{8}-[0-9]{3}-[0-9]{3}-[0-9]{3}", reported
        ):
            raise ValueError("Coding software definition identity is invalid")
        if reported in self._resolutions:
            return copy.deepcopy(self._resolutions[reported])
        selected = None
        if reported in self._document_names and self._package_definition(reported):
            selected = reported
            method = "exact-package"
        else:
            prefix = reported.rsplit("-", 1)[0] + "-"
            candidates = sorted(
                (
                    name
                    for name in self._document_names
                    if name.startswith(prefix) and name < reported and _VARIANT.fullmatch(name[9:])
                ),
                reverse=True,
            )
            selected = next((name for name in candidates if self._package_definition(name)), None)
            method = "same-major-minor-lower-patch" if selected else "exact-xml"
        if selected is None:
            if reported not in self._document_names:
                raise LookupError("No exact or source-compatible coding definition is available")
            selected = reported
        result = {
            "reported": reported,
            "selected": selected,
            "method": method,
            "source_sha256": self._source_hash(selected),
            "document_sha256": self._document_hash(selected),
            "crosscheck": "not-required",
            "widths": {},
        }
        if reported in self._document_names and reported != selected:
            exact = self.read_document(reported)
            if isinstance(exact, dict) and "sourceDefinition" in exact:
                layout = self.read_document(selected)
                if not isinstance(layout, dict):
                    raise ValueError("Selected coding layout is invalid")
                reference = {_number(g["address"]): g for g in exact["dataGroups"]}
                chosen = {_number(g["address"]): g for g in layout["dataGroups"]}
                sign = exact["sourceDefinition"].get("ncdSignAddress")
                named = [
                    _number(g["address"])
                    for g in layout["dataGroups"]
                    if g.get("name") == "SIGNATURE"
                ]
                conflict = set(reference) != set(chosen) or (
                    sign is not None and named != [_number(sign)]
                )
                if not conflict:
                    for did, group in chosen.items():
                        width = _number(reference[did]["units"])
                        if any(
                            _number(f["storageInfo"]["end"]) >= width
                            for f in group.get("functions", [])
                        ):
                            conflict = True
                            break
                result["exact_reference"] = {
                    "source_sha256": self._source_hash(reported),
                    "document_sha256": self._document_hash(reported),
                }
                if conflict:
                    result.update(
                        selected=reported,
                        method="exact-xml-source-fallback-conflict",
                        source_sha256=self._source_hash(reported),
                        document_sha256=self._document_hash(reported),
                        crosscheck="source-compatible layout conflicts with exact source group bounds/signature",
                    )
                    result["rejected_layout"] = selected
                else:
                    result["crosscheck"] = "exact-source group bounds and signature agree"
                    result["widths"] = {
                        f"{did:04X}": _number(g["units"]) for did, g in reference.items()
                    }
        self._resolutions[reported] = result
        return copy.deepcopy(result)

    def source_sha256(self, document_name: str) -> str:
        """Return the selected original source hash, keeping reported identity distinct."""
        name = document_name.removesuffix(".enc")
        if re.fullmatch(r"[0-9A-F]{8}-[0-9]{3}-[0-9]{3}-[0-9]{3}", name):
            value = self.definition_resolution(name)["source_sha256"]
            if not isinstance(value, str):
                raise ValueError("Coding source identity is invalid")
            return value
        return self._source_hash(name)

    def available_variants(self, cafd_id: str) -> tuple[str, ...]:
        """List exact available definition versions; never select a first version."""
        if not _IDENTIFIER.fullmatch(cafd_id):
            return ()
        prefix = cafd_id + "-"
        return tuple(
            sorted(
                name[len(prefix) :]
                for name in self._document_names
                if name.startswith(prefix) and _VARIANT.fullmatch(name[len(prefix) :])
            )
        )

    def has_definition(self, cafd_id: str, variant: str) -> bool:
        """Report an exact or explicitly source-compatible definition without guessing."""
        if not _IDENTIFIER.fullmatch(cafd_id) or not _VARIANT.fullmatch(variant):
            return False
        try:
            self.definition_resolution(f"{cafd_id}-{variant}")
            return True
        except LookupError:
            return False

    def ecu_infos(self) -> list[dict]:
        """Return source ECU metadata for selection; flags do not authorize writes."""
        rows = self.read_document("coding-ecu-infos")
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError("Invalid coding ECU metadata")
        return rows

    def authorization(self, bootloader_identifier: str, key_type: int = 0) -> dict:
        """Select the source AS entry for an exact bootloader ID, without version guessing."""
        if not _IDENTIFIER.fullmatch(bootloader_identifier):
            raise ValueError("Bootloader authorization identifier is invalid")
        document = self.read_document("authorization")
        if not isinstance(document, list):
            raise ValueError("Authorization catalogue is invalid")
        matches = [
            entry
            for entry in document
            if isinstance(entry, dict)
            and entry.get("bootloaderID") == bootloader_identifier
            and entry.get("keyType") == key_type
        ]
        if not matches:
            raise ValueError("Exact bootloader authorization is missing")
        result = copy.deepcopy(matches[0])
        result["source_sha256"] = self._manifest["sources"][
            "authorization-member" if key_type == 0 else "signing-member"
        ]
        return result

    def validate_blocks(self, definitions: list[str], blocks: dict[int, bytes]) -> None:
        """Require source-declared group widths, or the full described storage range."""
        for identifier in definitions:
            data = self.get_definition(identifier[:8], identifier[9:])
            for group in data["dataGroups"]:
                did = _number(group["address"])
                if did not in blocks or not isinstance(blocks[did], bytes) or not blocks[did]:
                    raise ValueError("Complete source coding group is missing")
                if "units" in group and len(blocks[did]) != _number(group["units"]):
                    raise ValueError("Coding group width differs from exact source definition")
                required = max(
                    (
                        _number(function["storageInfo"]["end"]) + 1
                        for function in group.get("functions", [])
                    ),
                    default=0,
                )
                if len(blocks[did]) < required:
                    raise ValueError("Coding group does not cover all source-described bytes")

    def finalize_write_blocks(
        self, blocks: dict[int, bytes], definitions: list[str], bootloader_identifier: str
    ) -> dict[int, bytes]:
        """Apply source NCD signatures to all complete exact definitions in order.

        Baseline-based coding signs each definition's declared groups, omitting
        only its named SIGNATURE group. No ECU request is performed here.
        """
        from app.coding_authorization import sign_coding_data

        if not definitions or len(definitions) != len(set(definitions)):
            raise ValueError("Coding definition list is missing or repeated")
        entry = self.authorization(bootloader_identifier, key_type=1)
        result = dict(blocks)
        signature_dids = set()
        for identifier in definitions:
            if not re.fullmatch(r"[0-9A-F]{8}-[0-9]{3}-[0-9]{3}-[0-9]{3}", identifier):
                raise ValueError("Coding definition identity is invalid")
            data = self.get_definition(identifier[:8], identifier[9:])
            groups = data["dataGroups"]
            addresses = [_number(group.get("address")) for group in groups]
            if len(addresses) != len(set(addresses)) or any(
                address not in result for address in addresses
            ):
                raise ValueError("Complete unique definition groups are required for signing")
            signatures = [
                _number(group["address"]) for group in groups if group.get("name") == "SIGNATURE"
            ]
            explicit = data.get("sourceDefinition", {}).get("ncdSignAddress")
            if explicit is not None:
                declared = _number(explicit)
                if declared not in addresses or (signatures and signatures != [declared]):
                    raise ValueError("Coding signature metadata conflicts with exact group layout")
                signatures = [declared]
            if len(signatures) != 1 or signatures[0] in signature_dids:
                raise ValueError("Coding signature destination is missing or ambiguous")
            destination = signatures[0]
            signature_dids.add(destination)
            payload = b"".join(result[address] for address in addresses if address != destination)
            result[destination] = sign_coding_data(payload, entry)
        return result

    def get_definition(self, cafd_id: str, variant: str) -> dict:
        """Return the reported identity's source-selected layout without source-folder access."""
        self.load_ecu(cafd_id, variant)
        return copy.deepcopy(self.cafd_variants[f"{cafd_id}-{variant}"])

    def load_ecu(self, cafd_id: str, variant: str) -> None:
        """Load a reported identity with its evidenced exact/lower-patch layout and root."""
        key = f"{cafd_id}-{variant}"
        if key in self._loaded_ecus:
            return
        if not self.has_definition(cafd_id, variant):
            raise ValueError("No source-selected coding definition is available")
        resolution = self.definition_resolution(key)
        data = self.read_document(resolution["selected"])
        if isinstance(data, dict):
            for group in data.get("dataGroups", []):
                width = resolution.get("widths", {}).get(f"{_number(group['address']):04X}")
                if width is not None:
                    group["units"] = width
        if not isinstance(data, dict) or not isinstance(data.get("dataGroups"), list):
            raise ValueError("Invalid coding definition groups")
        if cafd_id in self._document_names and cafd_id not in self.root_indexes:
            root = self.read_document(cafd_id)
            if not isinstance(root, list) or any(not isinstance(row, dict) for row in root):
                raise ValueError("Invalid curated coding index")
            self.root_indexes[cafd_id] = root
        self.cafd_variants[key] = data
        index: dict[str, list[tuple[int, dict]]] = {}
        for group in data["dataGroups"]:
            did = _number(group.get("address"))
            if not 0 <= did <= 0xFFFF:
                raise ValueError("Coding group address is invalid")
            for function in group.get("functions", []):
                index.setdefault(function["name"], []).append((did, function))
        self._function_indexes[key] = index
        self._loaded_ecus.add(key)

    def category_for_model_range(self, model_range: str) -> int | None:
        """Map an exact reported model code through source resource descriptions."""
        if not isinstance(model_range, str) or not re.fullmatch(r"[FGUI][0-9]{2,3}", model_range):
            return None
        normalized = model_range[0] + f"{int(model_range[1:]):02d}"
        selection = self.read_document("selection")
        if not isinstance(selection, dict):
            raise ValueError("Coding selection metadata is invalid")
        categories = selection.get("model_categories", {}).get(normalized, [])
        unique = set(categories)
        if len(unique) != 1:
            return None
        category = next(iter(unique))
        return category if isinstance(category, int) and not isinstance(category, bool) else None

    def primary_definition(self, definitions: list[str]) -> str:
        """Select the source-prioritized CAFD from the reported ordered identities."""
        if not definitions:
            raise ValueError("Coding definition identities are missing")
        selection = self.read_document("selection")
        if not isinstance(selection, dict):
            raise ValueError("Coding selection metadata is invalid")
        preferred = selection["primary_definitions"]
        for identifier in definitions:
            if identifier[:8] in preferred:
                return identifier
        return definitions[0]

    def id8_context(self, definitions: list[str], blocks: dict[int, bytes]) -> bool:
        """Read the source headunit-generation predicate from exact definition/current bytes."""
        if self.primary_definition(definitions)[:8] != "00003E52":
            return False
        for identifier in definitions:
            data = self.get_definition(identifier[:8], identifier[9:])
            for group in data["dataGroups"]:
                for function in group.get("functions", []):
                    if function.get("name") != "HMI_ID_VERSION":
                        continue
                    storage = function["storageInfo"]
                    start, end, mask = (_number(storage[key]) for key in ("start", "end", "mask"))
                    if start != end:
                        return False
                    did = _number(group["address"])
                    if (
                        did not in blocks
                        or not 0 <= start < len(blocks[did])
                        or not 0 < mask <= 255
                    ):
                        raise ValueError("Headunit generation baseline is incomplete")
                    shift = (mask & -mask).bit_length() - 1
                    return ((blocks[did][start] & mask) >> shift) == 3
        return False

    def preset_applicability(
        self, preset: dict, *, category: int | None, variant_index: str | None, id8: bool | None
    ) -> tuple[bool | None, str]:
        """Evaluate recovered source filters; unknown context remains explicitly unknown."""
        if preset.get("supportedForID8") is not True:
            if id8 is None:
                return None, "Headunit generation context is not established"
            if id8:
                return False, "Option is excluded by the source headunit-generation filter"
        excluded = preset.get("excludeECUVariants", [])
        if excluded:
            if variant_index is None:
                return None, "ECU variant predicate has no identified variant"
            if variant_index in excluded:
                return False, "Source excludes this ECU variant"
        tags = preset.get("series", [])
        if tags:
            document = self.read_document("selection")
            if not isinstance(document, dict):
                raise ValueError("Coding selection metadata is invalid")
            mapping = document["series_categories"]
            supported = {value for tag in tags for value in mapping.get(str(tag).lower(), [])}
            if supported:
                if category is None:
                    return None, "Source category predicate is not identified"
                if category != 0 and category not in supported:
                    return False, "Option is excluded by the source category filter"
        if preset.get("excludedSeries"):
            return (
                None,
                "Excluded-series metadata is retained but its selector is not yet recovered",
            )
        return True, "Source filters allow this identified context"

    def _combined_index(
        self, cafd_id: str, variant: str, definitions: list[str] | None = None
    ) -> dict[str, list[tuple[int, dict]]]:
        ordered = definitions if definitions is not None else [f"{cafd_id}-{variant}"]
        combined: dict[str, list[tuple[int, dict]]] = {}
        for identity in ordered:
            if not isinstance(identity, str) or not re.fullmatch(
                r"[0-9A-F]{8}-[0-9]{3}-[0-9]{3}-[0-9]{3}", identity
            ):
                raise ValueError("Combined coding definition identity is invalid")
            self.load_ecu(identity[:8], identity[9:])
            for name, matches in self._function_indexes[identity].items():
                combined.setdefault(name, []).extend(matches)
        return combined

    def get_presets(
        self,
        cafd_id: str,
        variant: str | None = None,
        blocks: dict[int, bytes] | None = None,
        *,
        definitions: list[str] | None = None,
    ) -> list[dict]:
        """Return labels plus all source predicates and static/dynamic option data."""
        result = []
        for source_index, entry in enumerate(self.root_indexes.get(cafd_id, [])):
            preset = copy.deepcopy(entry)
            preset["source_index"] = source_index
            name = entry.get("name", "")
            description = entry.get("descriptionText", "")
            preset.update(
                label=self.strings.get(name, name),
                description=self.strings.get(description, description),
            )
            preset["options"] = []
            value_names = Counter(value.get("name", "") for value in entry.get("values", []))
            for value_index, value in enumerate(entry.get("values", [])):
                option = copy.deepcopy(value)
                source_name = value.get("name", "")
                option["source_name"] = source_name
                option["source_index"] = value_index
                option["name"] = (
                    f"{source_name}@{value_index}" if value_names[source_name] > 1 else source_name
                )
                option["label"] = self.strings.get(source_name, source_name)
                if value_names[source_name] > 1:
                    detail = value.get("color", str(value_index + 1))
                    option["label"] += f" ({detail})"
                option["functions"] = copy.deepcopy(value.get("functions", []))
                preset["options"].append(option)
            if preset.get("type", 0) and variant is not None and blocks is not None:
                preset = self.resolve_dynamic_preset(
                    preset, blocks, cafd_id, variant, definitions=definitions
                )
            result.append(preset)
        return result

    def preset_mapping_status(
        self,
        preset: dict,
        cafd_id: str,
        variant: str,
        blocks: dict[int, bytes] | None = None,
        *,
        definitions: list[str] | None = None,
    ) -> tuple[bool, str]:
        """Check the entire source option's required functions, not just one choice."""
        try:
            self.load_ecu(cafd_id, variant)
            if preset.get("type", 0):
                if blocks is None:
                    return False, "Dynamic option requires actual current group bytes"
                preset = self.resolve_dynamic_preset(
                    preset, blocks, cafd_id, variant, definitions=definitions
                )
            options = preset.get("options")
            if not isinstance(options, list) or not options:
                return False, "Source option contains no concrete choices"
            required = {
                function.get("name")
                for option in options
                if isinstance(option, dict)
                for function in option.get("functions", [])
                if isinstance(function, dict) and function.get("optional") is not True
            }
            identities = definitions if definitions is not None else [f"{cafd_id}-{variant}"]
            self._combined_index(cafd_id, variant, identities)
            if preset.get("source_type", 0) != 1 and not any(
                all(name in self._function_indexes[identity] for name in required)
                for identity in identities
            ):
                return False, "No exact definition contains all source-required option functions"
            for option in options:
                if not isinstance(option, dict) or not isinstance(option.get("functions"), list):
                    return False, "Source option function list is missing"
                patches = self._patches(
                    preset, option.get("name", ""), cafd_id, variant, definitions=definitions
                )
                if blocks is not None and any(
                    did not in blocks or offset >= len(blocks[did]) for did, offset, _, _ in patches
                ):
                    return False, "Source option lacks complete current group bytes"
            return True, "All source choices have applicable concrete function mappings"
        except (ValueError, KeyError, TypeError) as error:
            return False, str(error)

    def resolve_dynamic_preset(
        self,
        preset: dict,
        blocks: dict[int, bytes],
        cafd_id: str,
        variant: str,
        *,
        definitions: list[str] | None = None,
    ) -> dict:
        """Resolve the source type-1 lighting matrix into current and 100% choices."""
        if preset.get("type", 0) == 0:
            return copy.deepcopy(preset)
        if preset.get("type") != 1:
            raise ValueError("Unknown dynamic coding option type")
        self.load_ecu(cafd_id, variant)
        index = self._combined_index(cafd_id, variant, definitions)

        def function(name: str) -> tuple[int, dict]:
            entries = index.get(name, [])
            if not entries:
                raise ValueError("Dynamic lighting function is missing")
            return entries[0]

        def values(name: str) -> list[dict]:
            did, definition = function(name)
            storage = definition["storageInfo"]
            start, end, mask = (_number(storage[key]) for key in ("start", "end", "mask"))
            if did not in blocks or not 0 <= start <= end < len(blocks[did]) or not 0 < mask <= 255:
                raise ValueError("Dynamic lighting baseline is incomplete")
            shift = (mask & -mask).bit_length() - 1
            return [
                {
                    "position": str(offset - start),
                    "value": f"0x{(blocks[did][offset] & mask) >> shift:02X}",
                }
                for offset in range(start, end + 1)
            ]

        def parameter(name: str) -> dict:
            _, definition = function(name)
            current = values(name)
            for candidate in definition.get("params", []):
                if not isinstance(candidate, dict):
                    raise ValueError("Dynamic lighting parameter is invalid")
                expected = candidate.get("values", [])
                if expected and all(
                    0 <= _number(value.get("position")) < len(current)
                    and _number(current[_number(value["position"])]["value"])
                    == _number(value.get("value"))
                    for value in expected
                ):
                    return candidate
            raise ValueError("Dynamic lighting value has no matching source parameter")

        def scalar(name: str) -> int:
            expected = parameter(name).get("values", [])
            if len(expected) != 1:
                raise ValueError("Dynamic lighting parameter is not scalar")
            return _number(values(name)[_number(expected[0]["position"])]["value"])

        def module_index(code: int) -> int:
            selected = -1
            for offset in range(1, 11):
                if scalar(f"LM{offset:02d}_Name") == code:
                    selected = offset
            if selected < 0:
                return -1
            function(f"LM_ID_LT{selected:02d}")
            return selected - 1

        def intensity(name: str, offset: int) -> int:
            current = values(name)
            if not 0 <= offset < len(current):
                raise ValueError("Dynamic lighting module index is out of range")
            number = _number(current[offset]["value"])
            return scalar(f"LmmIdx{number:02d}_Intensity")

        selected = -1
        best = -1
        for code in (7, 8, 9):
            offset = module_index(code)
            if offset >= 0 and intensity("DRL_Idx", offset) == 100:
                brightness = intensity("POLI1_Idx", offset)
                if brightness > best:
                    selected, best = offset, brightness
        if selected < 0:
            raise ValueError("No source-supported daytime-light module is selected")
        brightness = intensity("POLI1_Idx", selected)
        vectors = {name: values(name) for name in ("POLI1_Idx", "POLI2_Idx", "POLI3_Idx")}
        source_values = parameter("DRL_Idx").get("values", [])
        if selected >= len(source_values) or any(
            selected >= len(vector) for vector in vectors.values()
        ):
            raise ValueError("Dynamic lighting matrix is incomplete")
        choices = []
        for percent in [brightness] if brightness == 100 else [brightness, 100]:
            functions = []
            for name, vector in vectors.items():
                intended = copy.deepcopy(vector)
                if percent == 100 and brightness != 100:
                    intended[selected]["value"] = source_values[selected]["value"]
                functions.append({"name": name, "values": intended})
            choices.append(
                {"name": f"{percent}_PERCENT", "label": f"{percent}%", "functions": functions}
            )
        resolved = copy.deepcopy(preset)
        resolved.update(type=0, source_type=1, options=choices)
        return resolved

    def _patches(
        self,
        preset: dict,
        option_name: str,
        cafd_id: str,
        variant: str,
        *,
        definitions: list[str] | None = None,
    ) -> list[tuple[int, int, int, int]]:
        self.load_ecu(cafd_id, variant)
        if preset.get("type", 0) != 0:
            raise ValueError("Dynamic coding option requires its source-specific resolver")
        matches = [
            option for option in preset.get("options", []) if option.get("name") == option_name
        ]
        if len(matches) != 1 or not matches[0].get("functions"):
            raise ValueError("Coding option has no unique concrete function mapping")
        patches = []
        index = self._combined_index(cafd_id, variant, definitions)
        for requested in matches[0]["functions"]:
            functions = index.get(requested.get("name", ""), [])
            if not functions and requested.get("optional") is True:
                continue
            if not functions:
                raise ValueError("Coding function is missing")
            did, function = functions[0]
            storage = function.get("storageInfo", {})
            start, end, function_mask = (
                _number(storage.get(field)) for field in ("start", "end", "mask")
            )
            if not 0 <= start <= end <= 65535 or not 0 < function_mask <= 255:
                raise ValueError("Coding function storage is invalid")
            values = requested.get("values", [])
            if not values:
                raise ValueError("Coding function has no concrete values")
            positions = set()
            for value in values:
                position = _number(value.get("position"))
                if position in positions or not 0 <= position <= end - start:
                    raise ValueError("Coding value position is invalid or repeated")
                positions.add(position)
                mask = function_mask
                if "mask" in value:
                    override = _number(value["mask"])
                    if not 0 <= override <= 255:
                        raise ValueError("Coding value mask is invalid")
                    if override:
                        mask &= override
                if not mask:
                    raise ValueError("Coding value mask has no supported bits")
                shift = (mask & -mask).bit_length() - 1
                number = _number(value.get("value"))
                if not 0 <= number <= 255 or (number << shift) & ~mask:
                    raise ValueError("Coding value exceeds its mask")
                patches.append((did, start + position, mask, number << shift))
        if not patches:
            raise ValueError("Coding option has no applicable concrete function values")
        return patches

    def get_current_option(
        self,
        preset: dict,
        blocks: dict[int, bytes],
        cafd_id: str,
        variant: str,
        *,
        definitions: list[str] | None = None,
    ) -> str | None:
        """Match every mapped value against its own exact data group; ambiguous is Custom."""
        try:
            preset = self.resolve_dynamic_preset(
                preset, blocks, cafd_id, variant, definitions=definitions
            )
        except (ValueError, KeyError, TypeError):
            return None
        matches = []
        for option in preset.get("options", []):
            try:
                patches = self._patches(
                    preset, option.get("name", ""), cafd_id, variant, definitions=definitions
                )
            except (ValueError, KeyError, TypeError):
                continue
            if all(
                did in blocks and offset < len(blocks[did]) and blocks[did][offset] & mask == value
                for did, offset, mask, value in patches
            ):
                matches.append(option["name"])
        return matches[0] if len(matches) == 1 else None

    def compose_changes(
        self,
        changes: list[tuple[dict, str]],
        blocks: dict[int, bytes],
        cafd_id: str,
        variant: str,
        *,
        definitions: list[str] | None = None,
    ) -> dict[int, bytes]:
        """Compose concrete options against complete group baselines, rejecting conflicts.

        Returns all baseline groups with selected bit changes. This pure operation
        does not supply checksum, authentication, vehicle I/O or write permission.
        """
        if not changes:
            raise ValueError("No coding changes selected")
        modifications: dict[tuple[int, int], tuple[int, int]] = {}
        for preset, selected in changes:
            preset = self.resolve_dynamic_preset(
                preset, blocks, cafd_id, variant, definitions=definitions
            )
            for did, offset, mask, value in self._patches(
                preset, selected, cafd_id, variant, definitions=definitions
            ):
                if did not in blocks or offset >= len(blocks[did]):
                    raise ValueError("Complete coding group baseline is missing")
                previous_mask, previous_value = modifications.get((did, offset), (0, 0))
                if (previous_value ^ value) & previous_mask & mask:
                    raise ValueError("Selected coding options conflict")
                modifications[did, offset] = (previous_mask | mask, previous_value | value)
        result = {did: bytearray(value) for did, value in blocks.items()}
        for (did, offset), (mask, value) in modifications.items():
            result[did][offset] = (result[did][offset] & ~mask) | value
        return {did: bytes(value) for did, value in result.items()}

    def get_current_value(
        self, preset: dict, cafd_bytes: bytes, cafd_id: str, variant: str
    ) -> str | None:
        """Compatibility for single-group options only; multiple groups remain unavailable."""
        dids = {
            self.get_did_for_preset(cafd_id, variant, function.get("name", ""))
            for option in preset.get("options", [])
            for function in option.get("functions", [])
        }
        if len(dids) != 1 or None in dids:
            return None
        did = next(iter(dids))
        assert did is not None
        return self.get_current_option(preset, {did: cafd_bytes}, cafd_id, variant)

    def build_write_payload(
        self, preset: dict, selected_option_name: str, cafd_bytes: bytes, cafd_id: str, variant: str
    ) -> bytes | None:
        """Compatibility for one group; never silently skip unknown functions/bytes."""
        try:
            patches = self._patches(preset, selected_option_name, cafd_id, variant)
            dids = {patch[0] for patch in patches}
            if len(dids) != 1:
                return None
            did = next(iter(dids))
            return self.compose_changes(
                [(preset, selected_option_name)], {did: cafd_bytes}, cafd_id, variant
            )[did]
        except (ValueError, KeyError, TypeError):
            return None

    def get_did_for_preset(self, cafd_id: str, variant: str, function_name: str) -> int | None:
        """Return the source's first named function group in declared definition order."""
        self.load_ecu(cafd_id, variant)
        matches = self._function_indexes[f"{cafd_id}-{variant}"].get(function_name, [])
        return matches[0][0] if matches else None

    def get_ecu_fdl_functions(self, cafd_id: str, variant: str) -> list[dict]:
        """Return all group-scoped source functions with their complete storage metadata."""
        data = self.get_definition(cafd_id, variant)
        return [
            {**copy.deepcopy(function), "did": _number(group["address"])}
            for group in data["dataGroups"]
            for function in group.get("functions", [])
        ]

    def is_loaded(self, cafd_id: str, variant: str) -> bool:
        """Report whether an exact definition was successfully loaded."""
        return f"{cafd_id}-{variant}" in self._loaded_ecus

    def loaded_count(self) -> int:
        """Return the number of loaded exact definitions."""
        return len(self._loaded_ecus)
