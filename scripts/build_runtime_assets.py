"""Build standalone personal-use runtime assets from development sources.

This command is development tooling. The app loads the generated data and native
library; it never invokes this script or opens the input source directories.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*arguments: str) -> None:
    """Stop the build on the first failed producer."""
    subprocess.run(arguments, cwd=ROOT, check=True)


def digest(path: Path) -> str:
    """Hash one generated artifact without loading a large bundle into memory."""
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def build(
    ista: Path,
    coding: Path,
    apk: Path,
    reader: Path,
    output: Path,
    selection_evidence: Path,
    resource_strings: Path,
    reader_backup_evidence: Path,
    reader_prerequisite_evidence: Path,
    decrypted_definitions: Path | None = None,
    openssl: str = "/opt/homebrew/bin/openssl",
) -> None:
    """Run existing producers, then publish a content manifest for the final set.

    A failed producer stops before the manifest is published. Per-producer atomic
    publication preserves its previous valid artifact; this manifest verifies the
    completed set rather than claiming an atomic swap of a whole application.
    """
    ista, coding, apk, reader, output = (
        path.expanduser().resolve() for path in (ista, coding, apk, reader, output)
    )
    output.mkdir(parents=True, exist_ok=True)
    data = output / "coding_data"
    data.mkdir(parents=True, exist_ok=True)
    run("bash", str(ROOT / "scripts/build_native.sh"))
    run(
        sys.executable,
        str(ROOT / "scripts/build_ista_bundle.py"),
        str(ista),
        "--out",
        str(output / "ista_bundle"),
        "--all-source-series",
    )
    rheingold = ista / "Rheingold" if (ista / "Rheingold").is_dir() else ista
    if decrypted_definitions is None:
        decrypted_definitions = ROOT / "build/recovered_definitions"
        run(
            sys.executable,
            str(ROOT / "scripts/recover_cafd_assets.py"),
            str(rheingold / "PSdZ"),
            str(decrypted_definitions),
            "--openssl",
            openssl,
            "--include-fafp",
        )
    run(
        sys.executable,
        str(ROOT / "scripts/build_coding_bundle.py"),
        str(coding),
        str(data / "coding_catalog.db"),
        "--apk",
        str(apk),
        "--selection-evidence",
        str(selection_evidence.expanduser().resolve()),
        "--resource-strings",
        str(resource_strings.expanduser().resolve()),
        "--ista-definitions",
        str(decrypted_definitions.expanduser().resolve()),
    )
    run(
        sys.executable,
        str(ROOT / "scripts/recover_ista_texts.py"),
        str(rheingold / "SQLiteDBs/DiagDocDb.sqlite"),
        "--reader",
        str(reader),
        "--output",
        str(data / "diagnostic_texts.db"),
    )
    run(
        sys.executable,
        str(ROOT / "scripts/build_coding_reader_contracts.py"),
        str(reader_backup_evidence.expanduser().resolve()),
        str(reader_prerequisite_evidence.expanduser().resolve()),
        str(data / "reader_contracts.json"),
    )
    # Regenerate current-source execution contracts instead of copying stale
    # definitions from a prior build. The history generator executes only its
    # in-memory peer and refuses changed source encoders.
    run(
        sys.executable,
        str(ROOT / "scripts/recover_cbs_definitions.py"),
        str(ROOT / "docs/evidence/task-b-cbs-contract.json"),
        str(coding / "diagnostic_catalog.json.gz"),
        str(data / "cbs_definitions.json"),
        "--current-contract",
        str(ROOT / "docs/evidence/source-cbs-current-jobs-20261104.json"),
    )
    run(
        sys.executable,
        str(ROOT / "scripts/recover_history_contracts.py"),
        "--bundle",
        str(output / "ista_bundle"),
        "--output",
        str(data / "history_contracts.json"),
        "--evidence",
        str(output / "build/history-contract-verification.json"),
    )
    # Existing independently recovered runtime contracts remain assets, never
    # reference-application dependencies. Their own evidence records own provenance.
    for name in (
        "diagnostic_catalog.json.gz",
        "diagnostic_memory_variants.json",
        "engine_measurements.json",
        "vehicle_equipment.json",
        "mil_contracts.json",
    ):
        source = ROOT / "coding_data" / name
        destination = data / name
        if source.resolve() != destination.resolve():
            shutil.copy2(source, destination)
    library = ROOT / "native/build" / ("libedx.dylib" if sys.platform == "darwin" else "libedx.so")
    if output != ROOT:
        shutil.copy2(library, output / library.name)
    publish_manifest(output)


def publish_manifest(output: Path) -> None:
    """Publish hashes after all producers have finished their atomic outputs."""
    output = output.expanduser().resolve()
    data = output / "coding_data"
    library = ROOT / "native/build" / ("libedx.dylib" if sys.platform == "darwin" else "libedx.so")
    files = [
        path for path in data.iterdir() if path.is_file() and path.suffix in {".db", ".json", ".gz"}
    ]
    files += [path for path in (output / "ista_bundle").rglob("*") if path.is_file()]
    files.append(library if output == ROOT else output / library.name)
    manifest = {
        "schema_version": 1,
        "files": {
            str(path.relative_to(output)): {"bytes": path.stat().st_size, "sha256": digest(path)}
            for path in sorted(files)
        },
    }
    descriptor, temporary_name = tempfile.mkstemp(prefix=".runtime-assets-", dir=output)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(manifest, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output / "runtime-assets.json")
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ista", type=Path, required=True)
    parser.add_argument("--coding", type=Path, default=ROOT / "coding_data")
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--text-reader", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT)
    parser.add_argument(
        "--selection-evidence",
        type=Path,
        default=ROOT / "docs/evidence/source-coding-selection-20261104.json",
    )
    parser.add_argument("--resource-strings", type=Path, required=True)
    parser.add_argument("--reader-backup-evidence", type=Path, required=True)
    parser.add_argument("--reader-prerequisite-evidence", type=Path, required=True)
    parser.add_argument(
        "--decrypted-definitions",
        type=Path,
        help="Reuse a completed, hash-checked development CAFD export instead of decoding again",
    )
    parser.add_argument("--openssl", default="/opt/homebrew/bin/openssl")
    args = parser.parse_args()
    build(
        args.ista,
        args.coding,
        args.apk,
        args.text_reader,
        args.out,
        args.selection_evidence,
        args.resource_strings,
        args.reader_backup_evidence,
        args.reader_prerequisite_evidence,
        args.decrypted_definitions,
        args.openssl,
    )
