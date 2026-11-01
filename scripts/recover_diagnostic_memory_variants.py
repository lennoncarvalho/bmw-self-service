"""Build the per-variant diagnostic memory request asset from the PRG breadth scan.

Development-only. Input: the static IS_LESEN / IS_LOESCHEN / FS_LESEN_PERMANENT
scan of the 367 supplied PRGs whose names match catalogue UDS variants (see
docs/evidence/task-b-diagnostic-breadth.md, G2/G7). Variants without a PRG are
absent and keep the diagnostics application's uniform requests at runtime.
"""

import argparse
import hashlib
import json
from pathlib import Path

INFO_READS = {"22 20 00", "19 17 0C 01", None}
INFO_CLEARS = {"31 01 0F 06", None}


def build(scan_path: Path, output: Path) -> None:
    """Keep only the reviewed request forms; anything else is a recovery error."""
    raw = scan_path.read_bytes()
    variants = json.loads(raw)["variants"]
    compact: dict[str, dict[str, object]] = {}
    for name, row in sorted(variants.items()):
        if row["fault_read"] != "19 02 0C" or row["fault_clear"] != "14 FF FF FF":
            raise ValueError(f"Unreviewed fault-memory request: {name}")
        if row["info_read"] not in INFO_READS or row["info_clear"] not in INFO_CLEARS:
            raise ValueError(f"Unreviewed information-memory request: {name}")
        if row["permanent_read"] not in ("19 15", None):
            raise ValueError(f"Unreviewed permanent-memory request: {name}")
        compact[name] = {
            "info": row["info_read"],
            "info_clear": row["info_clear"],
            "permanent": row["permanent_read"] is not None,
        }
    asset = {"schema": 1, "source_sha256": hashlib.sha256(raw).hexdigest(), "variants": compact}
    output.write_text(json.dumps(asset, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("scan", type=Path)
    cli.add_argument("output", type=Path)
    args = cli.parse_args()
    build(args.scan, args.output)
