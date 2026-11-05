"""Build runtime CBS definitions from historical and current source evidence.

The current contract overlays version/layout, exact current job hashes, checked
request sequences and source-traced primary-owner roles. Historical artifact
identities remain in their original evidence record, never relabelled as newer
PRGs. Pass --current-contract to include all recovered current release branches.
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

DEFAULT_RESET = "2E 10 01 01 00 64 1F 80 00 0F FF 0F 3F FF 00"
# Delivery state and development boards are not user services.
NOT_RESETTABLE = {0xE0, 0xE1, 0xFF}
# Recovered non-default branches: policy name and the contract section proving it.
SPECIAL_RESETS = {
    "DSC_25": ("dsc25-plain", "reset_dsc25_conditional"),
    "D94BX7A0": ("routine-6.3", "reset_63_routine"),
}


def build(
    contract_path: Path, catalog_path: Path, output: Path, current_contract: Path | None = None
) -> None:
    """Select reachable CBS definitions and their reset policy."""
    raw = contract_path.read_bytes()
    contract = json.loads(raw)
    catalog = json.loads(gzip.decompress(catalog_path.read_bytes()))["variants"]
    names = {row["name"] for key, row in catalog.items() if row["uds"]}
    definitions: dict[str, dict[str, object]] = {}
    for variant in contract["variants"]:
        name = variant["prg"].rsplit(".", 1)[0].upper()
        version = variant["cbs_version"]
        if version is None or not variant["catalogue_address_index_rows"] or name not in names:
            continue
        if "CBS_DATEN_LESEN" not in variant["jobs"] or variant["read_request"][1] != "22 10 01":
            raise ValueError(f"Unreviewed CBS read: {name}")
        template = (variant.get("reset_request_template") or [None, None])[1]
        disposition = variant["disposition"]
        if (
            disposition.startswith("read+reset implementable (default template)")
            and template == DEFAULT_RESET
            and version in ("5", "6")
        ):
            reset = "default"
        elif name in SPECIAL_RESETS and contract.get(SPECIAL_RESETS[name][1]):
            reset = SPECIAL_RESETS[name][0]
        else:
            reset = "blocked"
        if reset in ("dsc25-plain", "routine-6.3"):
            disposition = (
                "read+reset (DSC_25 plain write; SVK-gated extra sequence blocked)"
                if reset == "dsc25-plain"
                else "read+reset (CBS 6.3 routine 31 01 1000, standard reset type 0x02)"
            )
        definitions[name] = {
            "address": int(variant["address"], 16),
            "version": version,
            "reset": reset,
            "disposition": disposition,
            "prg_sha256": variant["sha256"],
            "detail": "CBS_RESET_DETAIL_LESEN" in variant["jobs"],
        }
    current_digest = ""
    if current_contract is not None:
        current_raw = current_contract.read_bytes()
        current = json.loads(current_raw)
        if current.get("schema") != 1 or not isinstance(current.get("definitions"), dict):
            raise ValueError("Unsupported current-job contract")
        ownership = current.get("ownership")
        if not isinstance(ownership, dict) or current["definitions"].keys() - ownership.keys():
            raise ValueError("Every current CBS definition requires a source ownership entry")
        current_digest = hashlib.sha256(current_raw).hexdigest()
        for name, definition in current["definitions"].items():
            if name not in names:
                raise ValueError(f"Current CBS definition is not reachable: {name}")
            policy = definition.get("source_reset_policy", definition.get("reset"))
            if definition.get("read_vectors_checked", 0) < 14:
                raise ValueError(f"Current CBS read layout has not been checked: {name}")
            if policy == "routine-7.0":
                if (
                    definition.get("version") != "7.0"
                    or definition.get("read_job") != "STATUS_CBS_DATEN_LESEN"
                    or definition.get("start_request") != "31011000{item}02ffffff"
                    or definition.get("results_request") != "31031000"
                ):
                    raise ValueError(f"Unreviewed current CBS operation: {name}")
            elif policy == "dsc25-plain":
                if definition.get("extra_sequence") != [
                    "{reset}",
                    "860002",
                    "3101030400",
                    "14ffffff",
                    "{reset}",
                    "860502",
                ]:
                    raise ValueError(f"Unreviewed DSC occurrence sequence: {name}")
            elif policy == "default":
                if (
                    definition.get("version") not in ("5", "6")
                    or definition.get("reset_xsend_count") != 1
                    or definition.get("verified_reset_request") != "2e10010101641f80000fff0f3fff00"
                ):
                    raise ValueError(f"Unreviewed default CBS reset: {name}")
            elif not (
                policy == "unrecovered"
                and definition.get("ownership") == "owner-not-recovered"
                and definition.get("reset") == "blocked"
            ):
                raise ValueError(f"Unreviewed current CBS operation: {name}")
            definitions[name] = {
                key: definition[key]
                for key in (
                    "address",
                    "version",
                    "reset",
                    "read_job",
                    "prg_sha256",
                    "detail",
                    "disposition",
                    "ownership",
                    "source_groups",
                    "source_reset_policy",
                )
            }
            if definition["version"] == "7.0":
                definitions[name]["routine_codes"] = {
                    table: {
                        row[0].removeprefix("0x").upper(): row[1]
                        for row in definition["tables"][table]["rows"]
                    }
                    for table in ("TAB_CBS_RETURN_CODE_ALLGEMEIN", "TAB_CBS_RETURN_CODE_KOMPONENTE")
                }
            if policy == "dsc25-plain":
                for field in ("extra_sequence", "extra_svk", "record_index", "side_effects"):
                    definitions[name][field] = definition[field]
        for name, owner in current.get("ownership", {}).items():
            if name not in definitions:
                continue
            definitions[name]["ownership"] = owner["role"]
            definitions[name]["source_groups"] = owner["groups"]
            if owner["role"] != "primary":
                definitions[name]["reset"] = "blocked"
    items = {
        int(item["id"], 16): item["en"]
        for item in contract["items"]
        if "only)" not in item["en"]  # labels from an unreachable divergent table
    }
    asset = {
        "schema": 1,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "current_source_sha256": current_digest,
        "definitions": dict(sorted(definitions.items())),
        "items": {f"{key:02X}": label for key, label in sorted(items.items())},
        "not_resettable": [f"{key:02X}" for key in sorted(NOT_RESETTABLE)],
    }
    output.write_text(json.dumps(asset, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("contract", type=Path)
    cli.add_argument("catalog", type=Path)
    cli.add_argument("output", type=Path)
    cli.add_argument("--current-contract", type=Path)
    args = cli.parse_args()
    build(args.contract, args.catalog, args.output, args.current_contract)
