"""Build the compact bundled job-file and ECU-list data from an ISTA 4.29 folder (D-62).

For each requested series the KIS main series is looked up in ``PSdZ/mapping/brref.xml``;
its target ECU list (``PSdZ/kiswb/<main>``) is exported as JSON. Job files are selected
through the UDS group assignment table in ``Ecu/t_grtb.prg``: every group file serving an
address on a bundled ECU list, every variant PRG that group can resolve to, and the
external table files and USES files those reference. Every bundled group can therefore
resolve all of its variants from the bundle alone.

The output (default ``ista_bundle/``) holds BMW files for the owner's personal build;
it is git-ignored and must not be redistributed.

Usage:
    python3 scripts/build_ista_bundle.py /path/to/ISTA [--out ista_bundle] [--series F048 ...]
"""

import argparse
import hashlib
import json
import re
import shutil
import struct
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ista_data import (  # noqa: E402
    BUNDLE_DIRNAME,
    BUNDLE_FORMAT,
    GROUP_TABLE_FILE,
    FolderProvider,
    groups_by_address,
    normalize_series,
    read_group_assignments,
    read_kis_ecus,
    read_series_map,
    validate_ista_folder,
)

# Owner's F48 plus the common F/G platforms of D-62.
DEFAULT_SERIES = ["F056", "F020", "F030", "F015", "F025", "G020", "G030", "G005", "G001"]
_XOR = bytes(b ^ 0xF7 for b in range(256))
_TOKEN = re.compile(rb"[A-Za-z0-9_]{3,}")


def sha256(path: Path) -> str:
    """SHA-256 of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def uses(path: Path) -> list[str]:
    """Job files a PRG/GRP inherits from (its USES list)."""
    raw = path.read_bytes()
    offset = struct.unpack_from("<i", raw, 0x7C)[0]
    if offset <= 0 or offset + 4 > len(raw):
        return []
    count = struct.unpack_from("<i", raw, offset)[0]
    if not 0 <= count <= 256 or offset + 4 + count * 0x100 > len(raw):
        raise ValueError(f"{path.name}: invalid USES list")
    names = []
    for index in range(count):
        start = offset + 4 + index * 0x100
        entry = raw[start : start + 0x100].translate(_XOR)
        names.append(entry.split(b"\0", 1)[0].decode("cp1252").lower())
    return names


def table_references(path: Path, table_files: set[str]) -> set[str]:
    """External table files (``t_*.prg``) named anywhere in a job file."""
    body = path.read_bytes().translate(_XOR)
    tokens = {t.decode("ascii").lower() for t in _TOKEN.findall(body)}
    return tokens & table_files


def build(ista: Path, out: Path, requested: list[str]) -> dict[str, Any]:
    """Export ECU lists and job files; returns the manifest."""
    check = validate_ista_folder(ista)
    if not check.ok or check.root is None:
        raise SystemExit(f"Not a usable ISTA folder: {check.message}")
    rheingold = check.root
    folder = FolderProvider(rheingold)
    ecu_dir = folder.ecu_dir
    available = {
        p.stem.lower(): p for p in ecu_dir.iterdir() if p.suffix.lower() in (".prg", ".grp")
    }
    series_map = read_series_map(rheingold / "PSdZ" / "mapping" / "brref.xml")
    table_path = available[GROUP_TABLE_FILE]
    assignments = read_group_assignments(table_path)
    groups_for = groups_by_address(assignments)

    resolved: dict[str, str | None] = {}
    for code in requested:
        series = normalize_series(code)
        main = series if series in check.kis_series else series_map.get(series)
        resolved[series] = main if main in check.kis_series else None

    if out.exists():
        if not (out / "manifest.json").is_file() and any(out.iterdir()):
            raise SystemExit(f"{out} exists and is not a bundle; refusing to overwrite it")
        shutil.rmtree(out)
    (out / "series").mkdir(parents=True)
    (out / "ecu").mkdir()

    main_series: dict[str, Any] = {}
    addresses: set[int] = set()
    for main in sorted({m for m in resolved.values() if m}):
        kis_dir = rheingold / "PSdZ" / "kiswb" / main
        ecus = read_kis_ecus(kis_dir, groups_for)
        addresses.update(e["address"] for e in ecus)
        members = sorted(s for s, m in series_map.items() if m == main)
        target = out / "series" / f"{main}.json"
        content = {"main_series": main, "series": members, "ecus": ecus}
        target.write_text(json.dumps(content, ensure_ascii=False, indent=1), encoding="utf-8")
        main_series[main] = {
            "series": members,
            "ecus": len(ecus),
            "addresses": len({e["address"] for e in ecus}),
            "file": f"series/{main}.json",
            "sha256": sha256(target),
            "kis_script_sha256": sha256(kis_dir / "KIS.script"),
            "kis_data_sha256": sha256(kis_dir / "KIS.data"),
        }

    groups = {g for a in addresses for g in groups_for.get(a, [])}
    wanted = {GROUP_TABLE_FILE} | groups
    wanted |= {row.variant for row in assignments if row.group in groups}
    missing = sorted(n for n in wanted if n not in available)
    selected = {n for n in wanted if n in available}
    table_files = {n for n in available if n.startswith("t_")}
    missing_uses: set[str] = set()
    queue = sorted(selected)
    while queue:
        name = queue.pop()
        for ref in set(uses(available[name])) | table_references(available[name], table_files):
            if ref not in available:
                missing_uses.add(ref)
            elif ref not in selected:
                selected.add(ref)
                queue.append(ref)

    files: dict[str, Any] = {}
    total = 0
    for name in sorted(selected):
        source = available[name]
        target = out / "ecu" / source.name
        shutil.copyfile(source, target)
        digest = sha256(target)
        if digest != sha256(source):
            raise SystemExit(f"Copy of {source.name} does not match its source")
        size = target.stat().st_size
        total += size
        files[f"ecu/{source.name}"] = {"sha256": digest, "size": size}

    manifest = {
        "format": BUNDLE_FORMAT,
        "generated": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": {
            "folder": rheingold.parent.name,
            "version": check.version,
            "group_table_sha256": sha256(table_path),
            "brref_sha256": sha256(rheingold / "PSdZ" / "mapping" / "brref.xml"),
        },
        "requested": resolved,
        "main_series": main_series,
        "series_map": series_map,
        "groups": sorted(groups),
        "missing_job_files": missing,
        "missing_uses": sorted(missing_uses),
        "files": files,
        "job_bytes": total,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def main() -> None:
    """Command line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("ista", type=Path, help="ISTA installation or its Rheingold folder")
    parser.add_argument("--out", type=Path, default=Path(BUNDLE_DIRNAME))
    parser.add_argument("--series", nargs="+", default=DEFAULT_SERIES)
    args = parser.parse_args()
    manifest = build(args.ista, args.out, args.series)
    for series, main in manifest["requested"].items():
        print(f"{series}: {main or 'ABSENT from this ISTA folder'}")
    for main, info in manifest["main_series"].items():
        print(f"{main}: {info['ecus']} ECUs at {info['addresses']} addresses")
    print(
        f"{len(manifest['files'])} job files, {manifest['job_bytes'] / 2**20:.1f} MiB; "
        f"{len(manifest['groups'])} groups; source version {manifest['source']['version']}"
    )
    print(f"Variants named by the group table but absent: {len(manifest['missing_job_files'])}")
    print(f"USES/table references absent: {manifest['missing_uses']}")


if __name__ == "__main__":
    main()
