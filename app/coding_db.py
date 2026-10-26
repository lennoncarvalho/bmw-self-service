"""Coding database — decrypt and query BimmerCode .enc files.

Loads the curated coding database from coding_data/ at startup.
Each ECU has a root index (curated presets) and CAFD variants
(byte-level parameter layouts). Human-readable labels come from
Apple .strings files.

Reference: docs/13-replacement-app-architecture.md (lines 282-406),
           docs/11-curated-coding-format.md, docs/08-encryption-key.md
"""

import gzip
import json
import logging
import re
from pathlib import Path

from Crypto.Cipher import AES

logger = logging.getLogger(__name__)

# AES-256-CBC key and IV extracted from BimmerCode's ExternalLib
# Reference: docs/08-encryption-key.md
_KEY = bytes.fromhex("244326462948404D635166546A576E5A")
_IV = bytes.fromhex("7639792442264529482B4D6251655468")


def _decrypt_enc(filepath: str) -> bytes:
    """Decrypt a BimmerCode .enc file. Returns decompressed plaintext bytes."""
    with open(filepath, "rb") as f:
        encrypted = f.read()
    cipher = AES.new(_KEY, AES.MODE_CBC, _IV)
    decrypted = cipher.decrypt(encrypted)
    # Strip PKCS5/PKCS7 padding
    pad_len = decrypted[-1]
    if 1 <= pad_len <= 16:
        decrypted = decrypted[:-pad_len]
    # Try GZIP decompress; fall back to raw
    try:
        return gzip.decompress(decrypted)
    except (gzip.BadGzipFile, OSError):
        return decrypted


def _parse_strings(filepath: str) -> dict[str, str]:
    """Parse an Apple .strings file into a label dict."""
    with open(filepath, encoding="utf-8") as f:
        content = f.read()
    pairs = re.findall(r'"([^"]+)"\s*=\s*"([^"]*)"', content)
    return dict(pairs)


class CodingDatabase:
    """Load and query the BimmerCode curated coding database.

    Usage:
        db = CodingDatabase("coding_data")
        db.load_ecu("000024C3", "008-004-002")  # FEM variant
        presets = db.get_presets("000024C3")
        current = db.get_current_value(presets[0], cafd_bytes, "000024C3", "008-004-002")
    """

    def __init__(self, data_dir: str = "coding_data") -> None:
        """Initialise the coding database.

        Args:
            data_dir: Path to the coding database directory.
        """
        self.data_dir = data_dir
        self.strings: dict[str, str] = {}
        self.root_indexes: dict[str, list[dict]] = {}
        self.cafd_variants: dict[str, dict] = {}
        self._loaded_ecus: set[str] = set()

        # Load strings
        self._load_strings()

    # ── loading ──────────────────────────────────────────────────────

    def _load_strings(self) -> None:
        """Load English (primary) and German (fallback) labels."""
        for lang in ("en", "de"):
            path = f"{self.data_dir}/{lang}.strings"
            try:
                self.strings.update(_parse_strings(path))
            except FileNotFoundError:
                logger.debug("%s.strings not found", lang)

    def load_ecu(self, cafd_id: str, variant: str) -> None:
        """Load coding database for one ECU variant.

        Args:
            cafd_id: CAFD identifier (e.g. "000024C3").
            variant: CAFD variant string (e.g. "008-004-002").
        """
        key = f"{cafd_id}-{variant}"
        if key in self._loaded_ecus:
            return

        # Root index: curated presets with section/name/values
        root_path = f"{self.data_dir}/{cafd_id}.enc"
        if Path(root_path).exists() and cafd_id not in self.root_indexes:
            try:
                data = json.loads(_decrypt_enc(root_path))
                self.root_indexes[cafd_id] = data if isinstance(data, list) else []
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning("Failed to load root index %s: %s", cafd_id, e)
                self.root_indexes[cafd_id] = []

        # CAFD variant: byte-level parameter layout
        cafd_path = f"{self.data_dir}/{cafd_id}-{variant}.enc"
        if Path(cafd_path).exists() and key not in self.cafd_variants:
            try:
                data = json.loads(_decrypt_enc(cafd_path))
                self.cafd_variants[key] = data if isinstance(data, dict) else {}
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(
                    "Failed to load CAFD variant %s-%s: %s", cafd_id, variant, e
                )
                self.cafd_variants[key] = {}

        self._loaded_ecus.add(key)
        logger.info(
            "Loaded coding database for %s-%s (%d presets)",
            cafd_id, variant,
            len(self.root_indexes.get(cafd_id, [])),
        )

    # ── query: curated presets ───────────────────────────────────────

    def get_presets(self, cafd_id: str) -> list[dict]:
        """Return curated coding presets with human-readable labels.

        Args:
            cafd_id: CAFD identifier loaded via load_ecu().

        Returns:
            List of preset dicts with keys: section, name, label,
            description, values (each with name, label, functions).
        """
        root = self.root_indexes.get(cafd_id, [])
        presets: list[dict] = []
        for entry in root:
            key = entry.get("name", "")
            presets.append({
                "section": entry.get("section", ""),
                "name": key,
                "label": self.strings.get(key, key),
                "description": self.strings.get(
                    entry.get("descriptionText", ""),
                    entry.get("descriptionText", ""),
                ),
                "options": [
                    {
                        "name": v.get("name", ""),
                        "label": self.strings.get(v.get("name", ""), v.get("name", "")),
                        "functions": v.get("functions", []),
                    }
                    for v in entry.get("values", [])
                ],
            })
        return presets

    # ── query: current value detection ───────────────────────────────

    def get_current_value(
        self,
        preset: dict,
        cafd_bytes: bytes,
        cafd_id: str,
        variant: str,
    ) -> str | None:
        """Determine which option is currently active from raw CAFD bytes.

        Compares each option's function values against actual ECU bytes.

        Args:
            preset: A single preset dict from get_presets().
            cafd_bytes: Raw CAFD bytes read from the ECU.
            cafd_id: CAFD identifier.
            variant: CAFD variant string.

        Returns:
            Option name string if found, None if unknown.
        """
        cafd_key = f"{cafd_id}-{variant}"
        cafd = self.cafd_variants.get(cafd_key, {})

        for option in preset.get("options", []):
            match = True
            for func in option.get("functions", []):
                func_def = self._find_function(cafd, func.get("name", ""))
                if not func_def:
                    match = False
                    break
                si = func_def.get("storageInfo", {})
                byte_pos = int(si.get("start", "0"))
                mask_str = si.get("mask", "0b11111111")
                mask = int(mask_str.replace("0b", ""), 2)

                if byte_pos >= len(cafd_bytes):
                    match = False
                    break

                expected = int(func["values"][0].get("value", "0x00"), 16)
                actual = cafd_bytes[byte_pos] & mask
                # Align to LSB
                shift = (mask & -mask).bit_length() - 1
                actual_shifted = (actual >> shift) & 0xFF
                if actual_shifted != expected:
                    match = False
                    break
            if match:
                return option["name"]
        return None

    # ── query: write payload construction ────────────────────────────

    def build_write_payload(
        self,
        preset: dict,
        selected_option_name: str,
        cafd_bytes: bytes,
        cafd_id: str,
        variant: str,
    ) -> bytes | None:
        """Build modified CAFD bytes for writing to an ECU.

        Modifies only the bytes affected by the selected option,
        preserving all other bits in each byte via mask operations.

        Args:
            preset: A single preset dict from get_presets().
            selected_option_name: Which option value to apply.
            cafd_bytes: Current raw CAFD bytes from the ECU.
            cafd_id: CAFD identifier.
            variant: CAFD variant string.

        Returns:
            Modified bytearray ready for WriteDataByIdentifier, or None
            if the selected option is not found.
        """
        option = next(
            (o for o in preset.get("options", [])
             if o.get("name") == selected_option_name),
            None,
        )
        if option is None:
            return None

        cafd_key = f"{cafd_id}-{variant}"
        cafd = self.cafd_variants.get(cafd_key, {})
        modified = bytearray(cafd_bytes)

        for func in option.get("functions", []):
            func_def = self._find_function(cafd, func.get("name", ""))
            if not func_def:
                continue
            si = func_def.get("storageInfo", {})
            byte_pos = int(si.get("start", "0"))
            mask_str = si.get("mask", "0b11111111")
            mask = int(mask_str.replace("0b", ""), 2)

            if byte_pos >= len(modified):
                continue

            new_val = int(func["values"][0].get("value", "0x00"), 16)
            shift = (mask & -mask).bit_length() - 1

            modified[byte_pos] &= ~mask
            modified[byte_pos] |= (new_val << shift) & mask

        return bytes(modified)

    # ── query: CAFD metadata ─────────────────────────────────────────

    def get_did_for_preset(
        self, cafd_id: str, variant: str, function_name: str
    ) -> int | None:
        """Look up the DID (Data Identifier) for a function.

        Uses the CAFD variant's dataGroup addresses as the DID for
        WriteDataByIdentifier calls.

        Args:
            cafd_id: CAFD identifier.
            variant: CAFD variant string.
            function_name: Function name from preset functions[].

        Returns:
            DID as an integer, or None if not found.
        """
        cafd_key = f"{cafd_id}-{variant}"
        cafd = self.cafd_variants.get(cafd_key, {})
        func_def = self._find_function(cafd, function_name)
        if func_def is None:
            return None
        # The dataGroup's address serves as the DID for writes
        for dg in cafd.get("dataGroups", []):
            for func in dg.get("functions", []):
                if func.get("name") == function_name:
                    addr_str = dg.get("address", "0x3000")
                    return int(addr_str, 16)
        return None

    def get_ecu_fdl_functions(
        self, cafd_id: str, variant: str
    ) -> list[dict]:
        """Return all FDL functions with their storage info for Advanced Coding.

        Args:
            cafd_id: CAFD identifier.
            variant: CAFD variant string.

        Returns:
            List of function dicts with name, storageInfo, params.
        """
        cafd_key = f"{cafd_id}-{variant}"
        cafd = self.cafd_variants.get(cafd_key, {})
        functions: list[dict] = []
        for dg in cafd.get("dataGroups", []):
            for func in dg.get("functions", []):
                functions.append({
                    "name": func.get("name", ""),
                    "did": int(dg.get("address", "0x0000"), 16),
                    "storageInfo": func.get("storageInfo", {}),
                    "params": func.get("params", []),
                })
        return functions

    # ── helpers ──────────────────────────────────────────────────────

    def _find_function(self, cafd: dict, name: str) -> dict | None:
        """Search CAFD variant for a function by name."""
        for dg in cafd.get("dataGroups", []):
            for func in dg.get("functions", []):
                if func.get("name") == name:
                    return func
        return None

    # ── infrastructure ───────────────────────────────────────────────

    def is_loaded(self, cafd_id: str, variant: str) -> bool:
        """Check whether an ECU variant has been loaded."""
        return f"{cafd_id}-{variant}" in self._loaded_ecus

    def loaded_count(self) -> int:
        """Return the number of loaded ECU variants."""
        return len(self._loaded_ecus)
