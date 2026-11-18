"""Compile and verify exact low-voltage battery and terminal-status readers.

Development only. Native jobs run against an in-memory peer. AEP INFO 2's
32-byte reply and current SOC at PDU byte 20 agree with the supplied diagnostic
APK's j6.v.a.C0160a.C0161a.b; SOH uses the job's unsigned byte minus 128.
Structured readers derive their sizes, result names and units from PRG tables.
No reference application or vehicle is executed or contacted.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ediabas import JobEngine, JobResult  # noqa: E402
from app.ista_data import DataFormatError, IstaDataSource, read_job_table  # noqa: E402
from app.protocol.contracts import OperationContext  # noqa: E402

SOC = "STAT_LADUNGSZUSTAND_AKTUELL_WERT"
SOH = "STAT_SOH_BATTERIE_WERT"
QUALITY_SOC = "STAT_Q_LADEZUSTAND_AKTUELL_WERT"
QUALITY_SOH = "STAT_Q_SOH_BATTERIE_WERT"
SIZES = {"char": 1, "int": 2, "integer": 2, "long": 4}
# Translate only the explicit source terminal states. Transitions and errors do
# not establish a stable KL15 value; KL50 remains a separately labelled state.
TERMINALS = {
    0: "Initializing",
    1: "Reserved",
    2: "Off (KL30)",
    3: "Transition",
    4: "Off (KL30F)",
    5: "Transition",
    6: "Off (KL30B)",
    7: "Transition",
    8: "Off (accessory/KLR)",
    9: "Transition",
    10: "On (KL15)",
    11: "Transition",
    12: "Transition",
    13: "Cranking (KL50)",
    14: "Unavailable — terminal error",
    15: "Unavailable — invalid signal",
    255: "Unavailable — invalid value",
}
SOURCE_TERMINALS = {
    0: {"INIT", "Initialisierung"},
    1: {"Reserve"},
    2: {"KL30 alle Klemmen aus", "KL30 : Alle Klemmen aus"},
    3: {"KL30F-Änderung"},
    4: {"KL30F"},
    5: {"KL30B-Änderung"},
    6: {"KL30B"},
    7: {"KLR-Änderung"},
    8: {"KLR"},
    9: {"KL15-Änderung"},
    10: {"KL15"},
    11: {"KL50-Verzögerung"},
    12: {"KL50-Änderung"},
    13: {"KL50"},
    14: {"Fehler"},
    15: {"Ungültig", "ungültiger Signal"},
    255: {"Wert ungültig"},
}


class _Peer:
    """One exact offline exchange, with no network implementation."""

    def __init__(self, address: int) -> None:
        self.address = address
        self.request = b""
        self.response = b""
        self.sent: list[bytes] = []

    def context(self, timeout: float = 30.0, cancelled: Any = None) -> OperationContext:
        """Supply the interpreter's normal bounded operation context."""
        return OperationContext.create("power-reader-build", timeout)

    def send_uds(self, address: int, payload: bytes, **kwargs: Any) -> bytes:
        """Refuse extra requests, mutations and mismatched targets."""
        if address != self.address or payload != self.request or self.sent:
            raise ValueError("Power reader differs from its exact single-read contract")
        self.sent.append(bytes(payload))
        return self.response


def _run(engine: JobEngine, peer: _Peer, reader: dict, data: bytes) -> JobResult:
    peer.request = bytes.fromhex(reader["request"])
    peer.response = b"\x62" + peer.request[1:] + data
    peer.sent = []
    result = engine.run_job(reader["job"], reader["args"], timeout=2.0)
    if result.status != "OKAY" or peer.sent != [peer.request]:
        raise ValueError(f"Native reader failed: {engine.sgbd}/{reader['args']}: {result.status}")
    return result


def _result_values(result: JobResult, field: dict, *, percentage: bool = True) -> dict:
    matches = [row for row in result.sets if field["result"] in row]
    if len(matches) != 1:
        raise ValueError("Native reader returned missing or ambiguous values")
    values = matches[0]
    if percentage:
        unit = field["result"].removesuffix("_WERT") + "_EINH"
        if values.get(unit) != "%":
            raise ValueError("Native percentage unit is not in its value's result set")
    return values


def _table(path: Path, name: str) -> list[dict[str, str]]:
    columns, rows = read_job_table(path, name)
    return [dict(zip(columns, row, strict=True)) for row in rows]


def _structured(path: Path, row: dict[str, str], metric: str) -> tuple[dict, list[dict]]:
    fields = _table(path, row["RES_TABELLE"])
    offsets, position = {}, 0
    for field in fields:
        offsets[field["RESULTNAME"]] = position
        position += SIZES[field["DATENTYP"].split()[-1]]
    value = SOC if metric == "soc" else SOH
    quality = QUALITY_SOC if metric == "soc" else QUALITY_SOH
    for key in (value, quality):
        field = next(field for field in fields if field["RESULTNAME"] == key)
        if field["DATENTYP"] != "signed char" or field["EINHEIT"] != "%":
            raise ValueError(f"Changed percentage/quality layout: {path.name}/{key}")
        if any(
            field[k] not in ("-", "1.0" if k != "ADD" else "0.0") for k in ("MUL", "DIV", "ADD")
        ):
            raise ValueError("Changed percentage scaling")
    return {
        "job": "STATUS_LESEN",
        "args": f"ARG;{row['ARG']}",
        "request": "22" + f"{int(row['ID'], 16):04x}",
        "response_size": position + 3,
        "values": {metric: {"result": value, "quality": quality}},
        "fixture_offsets": {metric: offsets[value], "quality": offsets[quality]},
    }, fields


def _verify(engine: JobEngine, peer: _Peer, reader: dict) -> None:
    """Check signed/percentage boundaries and all source-defined terminal states."""
    size = reader["response_size"] - 3
    if "kl15" in reader["values"]:
        for value in sorted({int(code) for code in reader["source_states"]} | {254, 255}):
            spec = reader["values"]["kl15"]
            values = _result_values(
                _run(engine, peer, reader, bytes((value,))), spec, percentage=False
            )
            field = spec["result"]
            expected = reader["source_states"].get(str(value))
            if expected is not None and values.get(field) != expected:
                raise ValueError("Native terminal enumeration differs from its source table")
        return
    for metric, spec in reader["values"].items():
        for raw in (0, 1, 50, 100, 101, 127, 128, 228, 254, 255):
            data = bytearray(size)
            data[reader["fixture_offsets"][metric]] = raw
            values = _result_values(_run(engine, peer, reader, bytes(data)), spec)
            expected = raw - 128 if metric == "soh" and not spec.get("quality") else raw
            if spec.get("quality") and raw >= 128:
                expected = raw - 256
            if values.get(spec["result"]) != expected:
                raise ValueError(f"Changed native {metric} scaling: {engine.sgbd}")
            if quality := spec.get("quality"):
                data = bytearray(size)
                data[reader["fixture_offsets"]["quality"]] = raw
                values = _result_values(_run(engine, peer, reader, bytes(data)), spec)
                if values.get(quality) != (raw if raw < 128 else raw - 256):
                    raise ValueError("Changed native quality scaling")


def build(bundle: Path, parser_path: Path, output: Path, evidence: Path) -> None:
    """Generate exact selectors and native-verified readers from a prepared bundle."""
    spec = importlib.util.spec_from_file_location("power_reader_parser", parser_path)
    if spec is None or spec.loader is None:
        raise ValueError("Development job parser unavailable")
    parser = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = parser
    spec.loader.exec_module(parser)
    source = IstaDataSource.from_paths(bundle, None)
    identities = source.uds_variants()
    profiles, provenance = {}, {}
    for name in sorted(set(identities.values())):
        located = source.locate(name)
        if located is None or located[0].suffix.lower() != ".prg":
            continue
        path, directory = located
        raw = path.read_bytes()
        # PRG body strings use XOR 0xF7; this is only a candidate scan,
        # followed by structured table parsing and native job verification.
        decoded = raw.translate(bytes(value ^ 0xF7 for value in range(256)))
        if not any(
            token in decoded
            for token in (b"BZEDIAG_SOC", b"STATUS_SYSTEMCHECK_AEP_INFO_2", b"STAT_KLEMMENSTATUS")
        ):
            continue
        selectors = [key for key, variant in identities.items() if variant == name]
        addresses = {int(key.split()[0], 16) for key in selectors}
        peer = _Peer(min(addresses))
        engine = JobEngine(peer)
        try:
            engine.load(path, directory)
            jobs = engine.jobs()
            try:
                functions = {row["ARG"]: row for row in _table(path, "SG_FUNKTIONEN")}
            except DataFormatError:
                functions = {}
            readers, tables = [], {}
            for argument, metric in (("BZEDIAG_SOC", "soc"), ("BZEDIAG_SOH", "soh")):
                if argument in functions and functions[argument]["SERVICE"] == "22":
                    reader, fields = _structured(path, functions[argument], metric)
                    readers.append(reader)
                    tables[functions[argument]["RES_TABELLE"]] = fields
            if not readers and "STATUS_SYSTEMCHECK_AEP_INFO_2" in jobs:
                readers.append(
                    {
                        "job": "STATUS_SYSTEMCHECK_AEP_INFO_2",
                        "args": "",
                        "request": "224023",
                        "response_size": 32,
                        "values": {
                            "soc": {"result": SOC, "quality": None},
                            "soh": {"result": "STAT_SOH_WERT", "quality": None},
                        },
                        "fixture_offsets": {"soc": 17, "soh": 1},
                    }
                )
            if terminal := functions.get("STATUS_KLEMMEN"):
                if terminal["SERVICE"] != "22" or terminal["DATENTYP"] != "unsigned char":
                    raise ValueError("Changed terminal reader contract")
                rows = _table(path, terminal["NAME"])
                states = {
                    str(
                        int(row["WERT"], 0) if row["WERT"].startswith("0x") else int(row["WERT"])
                    ): row["TEXT"]
                    for row in rows
                }
                if any(
                    text not in SOURCE_TERMINALS.get(int(value), set())
                    for value, text in states.items()
                ):
                    raise ValueError("Unreviewed source terminal state")
                readers.append(
                    {
                        "job": "STATUS_LESEN",
                        "args": "ARG;STATUS_KLEMMEN",
                        "request": "22" + f"{int(terminal['ID'], 16):04x}",
                        "response_size": 4,
                        "values": {"kl15": {"result": "STAT_KLEMMENSTATUSO"}},
                        "states": {value: TERMINALS[int(value)] for value in states},
                        "source_states": states,
                    }
                )
                tables[terminal["NAME"]] = rows
            if not readers:
                continue
            if len(addresses) != 1:
                raise ValueError(f"Reader has multiple source addresses: {name}")
            parsed = parser.PrgParser(str(path)).parse()
            job_map = {job.name: job for job in parsed.jobs}
            anchors = {}
            for reader in readers:
                _verify(engine, peer, reader)
                job = job_map[reader["job"]]
                anchors[reader["job"]] = {
                    "offset": job.address,
                    "listing_sha256": hashlib.sha256(
                        "\n".join(job.disassembly).encode()
                    ).hexdigest(),
                }
                reader.pop("source_states", None)
                reader.pop("fixture_offsets", None)
            digest = hashlib.sha256(raw).hexdigest()
            profiles[name] = {"selectors": selectors, "job_sha256": digest, "readers": readers}
            provenance[name] = {"job_sha256": digest, "anchors": anchors, "tables": tables}
            print(f"Verified {name}: {len(readers)} readers", flush=True)
        finally:
            engine.close()
    if not profiles:
        raise ValueError("No power reader contracts recovered")
    _write(
        evidence,
        {
            "schema": 1,
            "profiles": provenance,
            "native_check": "Signed/percentage boundaries and all source terminal states; one exact read per job",
        },
    )
    _write(output, {"schema": 1, "profiles": profiles})
    print(f"Verified {len(profiles)} exact power-reader variants")


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = stream.name
            stream.write((json.dumps(data, sort_keys=True, indent=2) + "\n").encode())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--bundle", type=Path, default=ROOT / "ista_bundle")
    cli.add_argument("--parser", type=Path, required=True)
    cli.add_argument("--output", type=Path, default=ROOT / "coding_data/power_readers.json")
    cli.add_argument("--evidence", type=Path, required=True)
    args = cli.parse_args()
    build(args.bundle, args.parser, args.output, args.evidence)
