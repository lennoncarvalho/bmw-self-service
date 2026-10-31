"""Build the embedded CBS definition asset from the reviewed CBS contract record.

Development-only. Input: docs/evidence/task-b-cbs-contract.json (static PRG/APK
recovery). Version and owner address are per-PRG constants selected by the exact
F150 catalogue name; only PRGs that a catalogue row reaches are kept. Reset is
enabled only for the shared default 2E 10 01 template; every other branch keeps
its recorded disposition. See docs/evidence/task-b-cbs-contract.md.
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


def build(contract_path: Path, catalog_path: Path, output: Path) -> None:
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
    items = {
        int(item["id"], 16): item["en"]
        for item in contract["items"]
        if "only)" not in item["en"]  # labels from an unreachable divergent table
    }
    asset = {
        "schema": 1,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
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
    args = cli.parse_args()
    build(args.contract, args.catalog, args.output)
