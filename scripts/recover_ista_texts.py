"""Build standalone diagnostic text data from the supplied offline knowledge database.

Development-only: requires a SQLite Multiple Ciphers command-line reader with RC4
support. The application uses the resulting ordinary SQLite asset and never opens
this source database or requires the reader. See docs/evidence/source-database-access-20261104.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from typing import Any

# Source reference: DatabaseFunctions.cs in EdiabasLib 928cc36047f78721a70388e201c47e3922fbc3d8.
# The supplied connector obtains the entry assembly's public-key token as hex.
_DATABASE_PASSWORD = "6505EFBDC3E5F324"
_MAX_EXPORT_BYTES = 256 * 1024 * 1024
_SCHEMA = """
PRAGMA user_version=1;
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL) WITHOUT ROWID;
CREATE TABLE fault_texts (
    variant TEXT COLLATE NOCASE NOT NULL, code INTEGER NOT NULL,
    fault_type TEXT NOT NULL CHECK(fault_type IN ('F','I')),
    text_en TEXT NOT NULL, text_de TEXT NOT NULL,
    source_id INTEGER NOT NULL, label_id INTEGER NOT NULL,
    valid_from TEXT NOT NULL, valid_to TEXT NOT NULL,
    PRIMARY KEY (source_id,label_id)
) WITHOUT ROWID;
CREATE INDEX fault_lookup ON fault_texts(variant,code,fault_type);
CREATE TABLE ecu_titles (
    variant TEXT COLLATE NOCASE NOT NULL, text_en TEXT NOT NULL,
    text_de TEXT NOT NULL, source_id INTEGER PRIMARY KEY,
    valid_from TEXT NOT NULL, valid_to TEXT NOT NULL
);
CREATE INDEX ecu_lookup ON ecu_titles(variant);
"""
_FAULT_QUERY = """
SELECT lower(v.NAME) variant, f.CODE code, f.DATATYPE fault_type,
       coalesce(nullif(l.TITLE_ENGB,''),l.TITLE_ENUS,'') text_en,
       coalesce(l.TITLE_DEDE,'') text_de, f.ID source_id, l.ID label_id,
       coalesce(f.VALIDFROM,'') valid_from, coalesce(f.VALIDTO,'') valid_to
FROM XEP_FAULTCODES f
JOIN XEP_ECUVARIANTS v ON v.ID=f.ECUVARIANTID
JOIN XEP_REFFAULTLABELS r ON r.ID=f.ID
JOIN XEP_FAULTLABELS l ON l.ID=r.LABELID AND l.CODE=f.CODE
WHERE f.DATATYPE IN ('F','I') AND l.DATATYPE=f.DATATYPE
ORDER BY f.ID,l.ID
"""
_ECU_QUERY = """
SELECT lower(NAME) variant,
       coalesce(nullif(TITLE_ENGB,''),TITLE_ENUS,'') text_en,
       coalesce(TITLE_DEDE,'') text_de, ID source_id,
       coalesce(VALIDFROM,'') valid_from, coalesce(VALIDTO,'') valid_to
FROM XEP_ECUVARIANTS ORDER BY ID
"""


def sha256_file(path: Path) -> str:
    """Hash a file in bounded chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def query(reader: Path, source: Path, sql: str) -> list[dict[str, Any]]:
    """Query the encrypted source read-only without copying its pages."""
    uri = source.resolve().as_uri() + (
        "?mode=ro&immutable=1&cipher=rc4&hexkey=" + _DATABASE_PASSWORD.encode("ascii").hex()
    )
    with tempfile.TemporaryFile() as out:
        result = subprocess.run(
            [str(reader.resolve()), "-readonly", "-json", uri, sql],
            stdout=out,
            stderr=subprocess.PIPE,
            timeout=300,
            check=False,
        )
        if result.returncode:
            raise ValueError(
                "Source query failed; confirm the reader's RC4 support and source version"
            )
        size = out.tell()
        if size > _MAX_EXPORT_BYTES:
            raise ValueError("Source query exceeds the development export bound")
        out.seek(0)
        rows = json.load(out)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Source reader returned an unsupported result")
    return rows


def build(source: Path, reader: Path, output: Path) -> dict[str, Any]:
    """Atomically publish a plain, exact-variant diagnostic text database."""
    if not source.is_file() or not reader.is_file():
        raise ValueError("An existing source database and cipher reader are required")
    if source.resolve() == output.resolve():
        raise ValueError("Output must not replace the source database")
    before = source.stat()
    source_hash = sha256_file(source)
    version_rows = query(
        reader, source, "SELECT VERSION FROM RG_VERSION WHERE SUBSYSTEM='DATABASE'"
    )
    if len(version_rows) != 1 or version_rows[0]["VERSION"] != "4.29.14":
        raise ValueError("This extraction contract requires source data release 4.29.14")
    faults = query(reader, source, _FAULT_QUERY)
    titles = query(reader, source, _ECU_QUERY)
    if not faults or not titles:
        raise ValueError("Source contains no linked fault texts or ECU titles")
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".diagnostic-texts-", suffix=".db", dir=output.parent)
    os.close(fd)
    temporary_path = Path(temporary)
    try:
        with sqlite3.connect(temporary) as connection:
            connection.executescript(_SCHEMA)
            fault_rows = []
            for row in faults:
                code_string = row["code"]
                if (
                    not isinstance(code_string, str)
                    or not code_string.isascii()
                    or not code_string.isdecimal()
                ):
                    raise ValueError("Source fault code is not decimal text")
                code = int(code_string, 10)
                if not 0 <= code <= 0xFFFFFF:
                    raise ValueError("Source fault code exceeds diagnostic width")
                if not row["variant"] or row["fault_type"] not in {"F", "I"}:
                    raise ValueError("Source fault identity is incomplete")
                for key in ("variant", "text_en", "text_de", "valid_from", "valid_to"):
                    if not isinstance(row[key], str) or len(row[key]) > 65536:
                        raise ValueError("Source text exceeds the export contract")
                fault_rows.append(
                    (
                        row["variant"],
                        code,
                        row["fault_type"],
                        row["text_en"],
                        row["text_de"],
                        row["source_id"],
                        row["label_id"],
                        row["valid_from"],
                        row["valid_to"],
                    )
                )
            connection.executemany("INSERT INTO fault_texts VALUES (?,?,?,?,?,?,?,?,?)", fault_rows)
            connection.executemany(
                "INSERT INTO ecu_titles VALUES (?,?,?,?,?,?)",
                [
                    (
                        r["variant"],
                        r["text_en"],
                        r["text_de"],
                        r["source_id"],
                        r["valid_from"],
                        r["valid_to"],
                    )
                    for r in titles
                ],
            )
            metadata = {
                "schema_version": "1",
                "source_sha256": source_hash,
                "data_version": "4.29.14",
                "reader_sha256": sha256_file(reader),
                "fault_rows": str(len(fault_rows)),
                "ecu_rows": str(len(titles)),
                "selection": "exact-variant-code-datatype; differing candidate texts remain ambiguous",
            }
            connection.executemany("INSERT INTO metadata VALUES (?,?)", metadata.items())
            if connection.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise ValueError("Generated text database failed integrity verification")
        after = source.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (
            after.st_size,
            after.st_mtime_ns,
            after.st_ino,
        ):
            raise ValueError("Source identity changed during extraction")
        with temporary_path.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary_path, output)
        directory_fd = os.open(output.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return {
            "source_sha256": source_hash,
            "output_sha256": sha256_file(output),
            "bytes": output.stat().st_size,
            "fault_rows": len(faults),
            "ecu_rows": len(titles),
        }
    finally:
        temporary_path.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--reader", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("coding_data/diagnostic_texts.db"))
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.reader, args.output), indent=2))
