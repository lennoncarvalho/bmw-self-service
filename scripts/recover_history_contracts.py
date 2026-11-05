"""Generate exact headunit history contracts from the prepared source job bundle.

Development-only: runs existing job encoders/decoders against an in-memory peer,
never a car or reference application. Every selected address/index comes from the
bundle's group table. A changed encoder, extra request or business decoder aborts
asset generation instead of silently enabling the branch.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ediabas import JobEngine  # noqa: E402
from app.ista_data import (  # noqa: E402
    GROUP_TABLE_FILE,
    IstaDataSource,
    bundle_root,
    read_group_assignments,
)
from app.protocol.contracts import OperationContext  # noqa: E402
from app.service_history import (  # noqa: E402
    SERVICE_TYPES,
    HistoryEntry,
    HistoryItem,
    encode_nbt_add,
)

ADD = "STEUERN_SERVICEHISTORY_ADD"
ERASE = "STEUERN_SERVICEHISTORY_ERASE"
RESET = "STEUERGERAETE_RESET"
SESSION = "DIAGNOSE_MODE"
# Retained original NBT and HU_MGU have this identical encoder instruction
# prefix. Only relocatable hexadecimal branch labels are normalized.
REVIEWED_ADD_PREFIX = "a5e9b6de05df7adc76d3420ded00306430f4c94fac90ebbe0950a39c9abc28fa"


class _EncoderPeer:
    """Only predetermined request/response pairs; no networking implementation."""

    def __init__(self) -> None:
        """Initialize an empty, network-free expected exchange."""
        self.expected = b""
        self.reply = b""
        self.requests: list[bytes] = []

    def context(self, timeout: float = 30.0, cancelled: Any = None) -> OperationContext:
        """Supply a deadline to the existing interpreter's transport shim."""
        return OperationContext.create("history-asset-build", timeout)

    def send_uds(self, address: int, payload: bytes, **kwargs: Any) -> bytes:
        """Refuse anything except the exact independently encoded expected PDU."""
        if address != 0x63 or payload != self.expected or self.requests:
            raise ValueError(
                "Source history job differs from its recovered one-request contract: "
                f"expected {self.expected.hex()}, actual {payload.hex()}"
            )
        self.requests.append(bytes(payload))
        return self.reply


def _arguments(entry: HistoryEntry) -> str:
    """Serialize a history entry into the source job argument order."""
    header: list[object] = [
        entry.service_date.day,
        entry.service_date.month,
        entry.service_date.year,
        entry.correction,
        entry.mileage_km,
        entry.dealer_flag,
        entry.dealer,
        entry.status,
        len(entry.items),
    ]
    for item in entry.items:
        header.extend([item.code, item.status, item.remaining_distance, item.remaining_time])
    return ";".join(str(value) for value in header)


def _fixtures() -> list[HistoryEntry]:
    """Cover all sourced service types and signed/unsigned encoding boundaries."""
    codes = [code for _, code in SERVICE_TYPES]
    return [
        HistoryEntry(
            date(2026, 1, 2),
            0,
            12345,
            0,
            b"ABC1234",
            1,
            (
                HistoryItem(1, 1, -500, 10),
                HistoryItem(3, 2, 12345, 20),
            ),
        ),
        HistoryEntry(
            date(2026, 1, 2),
            255,
            0xFFFFFFFF,
            1,
            b"X",
            3,
            tuple(
                HistoryItem(code, (i % 3) + 1, -0x80000000 if i % 2 else 0x7FFFFFFF, 0xFFFF)
                for i, code in enumerate(codes[:13])
            ),
        ),
        HistoryEntry(date(2026, 1, 2), 0, 0, 0, b"1234567", 2, (HistoryItem(codes[-1], 3, 0, 0),)),
    ]


def _run(
    engine: JobEngine,
    peer: _EncoderPeer,
    job: str,
    args: str,
    request: bytes,
    response: bytes,
    *,
    field: str | None = None,
    status: int = 0,
) -> dict[str, Any]:
    """Execute one exact exchange and verify its final application status."""
    peer.expected, peer.reply, peer.requests = request, response, []
    result = engine.run_job(job, args, timeout=3.0, grant=frozenset({0x31, 0x11}))
    if result.status != "OKAY" or peer.requests != [request]:
        raise ValueError(f"Source job {job} did not complete its exact expected exchange")
    if field is not None:
        values = [row[field] for row in result.sets if field in row]
        if values != [status]:
            raise ValueError(f"Source job {job} changed its application status decoder")
    return {"job": job, "request_sha256": hashlib.sha256(request).hexdigest(), "status": status}


def _write(path: Path, data: dict[str, Any]) -> None:
    """Publish deterministic JSON through an atomic file replacement."""
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_bytes(path, _encoded(data))


def _encoded(data: dict[str, Any]) -> bytes:
    """Encode stable JSON bytes shared by publication and provenance hashes."""
    return (json.dumps(data, indent=2, sort_keys=True) + "\n").encode()


def _write_bytes(path: Path, raw: bytes) -> None:
    """Flush a temporary file before replacing the destination atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=".history-asset-", delete=False
        ) as out:
            temporary = out.name
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


def _publish(output: Path, asset: dict[str, Any], evidence: Path, record: dict[str, Any]) -> None:
    """Restore both prior files if either publication fails; surface rollback failures."""
    if output.resolve() == evidence.resolve():
        raise ValueError("Runtime asset and evidence must have distinct paths")
    snapshots = [
        (path, path.read_bytes() if path.exists() else None) for path in (output, evidence)
    ]
    try:
        _write(output, asset)
        _write(evidence, record)
    except BaseException:
        try:
            path, previous = snapshots[0]
            if previous is None:
                path.unlink(missing_ok=True)
            else:
                _write_bytes(path, previous)
        finally:
            path, previous = snapshots[1]
            if previous is None:
                path.unlink(missing_ok=True)
            else:
                _write_bytes(path, previous)
        raise


def _fingerprint(parser: Any, path: Path) -> dict[str, Any]:
    """Require the reviewed ADD encoder before recording normalized job hashes."""
    parsed = parser.PrgParser(str(path))
    job = next(job for job in parsed._parse_jobs(parsed._parse_description()) if job.name == ADD)
    lines = parsed._disassemble_job(job.address)
    labels = {
        match.group(1): f"BLOCK{index}"
        for index, match in enumerate(re.finditer(r"(__[0-9A-F]{8}):", "\n".join(lines)))
    }
    normalized = [
        re.sub(
            r"__[0-9A-F]{8}", lambda match: labels.get(match.group(), match.group()), line
        ).strip()
        for line in lines
    ]
    end = next(index for index, line in enumerate(normalized) if "xsend " in line) + 1
    prefix = hashlib.sha256("\n".join(normalized[:end]).encode()).hexdigest()
    if prefix != REVIEWED_ADD_PREFIX:
        raise ValueError(f"{path.name}: source ADD encoder differs from reviewed instructions")
    return {
        "job_offset": hex(job.address),
        "encoder_prefix_sha256": prefix,
        "complete_job_sha256": hashlib.sha256("\n".join(normalized).encode()).hexdigest(),
    }


def build(bundle: Path, output: Path, evidence: Path, parser_path: Path) -> dict[str, Any]:
    """Validate every exact source headunit and publish a standalone execution asset."""
    spec = importlib.util.spec_from_file_location("history_asset_parser", parser_path)
    if spec is None or spec.loader is None:
        raise ValueError("The development job parser is unavailable")
    parser = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = parser
    spec.loader.exec_module(parser)
    source = IstaDataSource.from_paths(bundle, None)
    table = source.job_file(GROUP_TABLE_FILE)
    if table is None:
        raise ValueError("A generated job group table is required")
    rows = [row for row in read_group_assignments(table) if row.address == 0x63]
    by_name: dict[str, list[str]] = {}
    for row in rows:
        by_name.setdefault(row.variant.upper(), []).append(f"63 {row.sgbd_index.upper()}")
    peer = _EncoderPeer()
    engine = JobEngine(peer)
    engines: dict[str, Any] = {}
    profiles, excluded = {}, {}
    try:
        for name, identities in sorted(by_name.items()):
            located = source.locate(name)
            if located is None:
                excluded[name] = {"identities": identities, "reason": "source definition absent"}
                continue
            path, directory = located
            engine.load(path, ecu_dir=directory)
            jobs = set(engine.jobs())
            if not {ADD, ERASE}.issubset(jobs):
                excluded[name] = {"identities": identities, "reason": "no source ADD/ERASE jobs"}
                continue
            if not {SESSION, RESET}.issubset(jobs):
                raise ValueError(f"{name} has no recovered session/reset jobs")
            fingerprint = _fingerprint(parser, path)
            checks = []
            for entry in _fixtures():
                payload = encode_nbt_add(entry, existing_dates=set(), today=entry.service_date)
                checks.append(
                    _run(
                        engine,
                        peer,
                        ADD,
                        _arguments(entry),
                        payload,
                        bytes.fromhex("7101a08100"),
                        field="STAT_SH_ADD_WERT",
                    )
                )
            entry = _fixtures()[0]
            payload = encode_nbt_add(entry, existing_dates=set(), today=entry.service_date)
            for status in (0, 1, 2, 4, 5):
                checks.append(
                    _run(
                        engine,
                        peer,
                        ADD,
                        _arguments(entry),
                        payload,
                        bytes.fromhex("7101a081") + bytes((status,)),
                        field="STAT_SH_ADD_WERT",
                        status=status,
                    )
                )
                checks.append(
                    _run(
                        engine,
                        peer,
                        ERASE,
                        "",
                        bytes.fromhex("3101a080"),
                        bytes.fromhex("7101a080") + bytes((status,)),
                        field="STAT_SH_ERASE_WERT",
                        status=status,
                    )
                )
            checks.append(
                _run(engine, peer, SESSION, "", bytes.fromhex("1001"), bytes.fromhex("5001"))
            )
            checks.append(
                _run(engine, peer, RESET, "", bytes.fromhex("1101"), bytes.fromhex("5101"))
            )
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            for identity in identities:
                engines[identity] = {"name": name, "definition_sha256": digest}
            profiles[name] = {
                "source_job_sha256": digest,
                "identities": identities,
                "checks": checks,
                **fingerprint,
            }
    finally:
        engine.close()
    if not engines:
        raise ValueError("No source history execution contracts were verified")
    asset = {
        "schema_version": 1,
        "id": "headunit-history-v1",
        "engines": engines,
        "default_session": "1001",
        "erase": "3101a080",
        "add_prefix": "3101a081",
        "reset": "1101",
        "erase_delay_ms": 200,
        "add_delay_ms": 100,
    }
    evidence_data = {
        "schema": 1,
        "source_group_table_sha256": hashlib.sha256(table.read_bytes()).hexdigest(),
        "asset_sha256": hashlib.sha256(_encoded(asset)).hexdigest(),
        "profiles": profiles,
        "excluded": excluded,
        "pacing_source": "retained native writer contract: erase200ms/add100ms",
        "native_width_verification": {
            "resolved": True,
            "opcodes": ["ASR 0x18", "fix2flt 0x68"],
            "correction": "32-bit registers are already signed; sign-extend only shorter widths",
            "boundary_vectors": "I32 min/max, negative256/65536 multiples, U32 maximum mileage",
            "arithmetic_source_sha256": hashlib.sha256(
                (
                    Path(__file__).resolve().parents[1] / "native/ediabasx/src/opcodes_arith.c"
                ).read_bytes()
            ).hexdigest(),
            "conversion_source_sha256": hashlib.sha256(
                (
                    Path(__file__).resolve().parents[1] / "native/ediabasx/src/opcodes_misc.c"
                ).read_bytes()
            ).hexdigest(),
        },
        "physical_validation": False,
    }
    _publish(output, asset, evidence, evidence_data)
    return asset


def main() -> None:
    """Generate reviewed history contracts from the current prepared source bundle."""
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--bundle", type=Path, default=bundle_root())
    cli.add_argument("--output", type=Path, default=Path("coding_data/history_contracts.json"))
    cli.add_argument(
        "--evidence",
        type=Path,
        default=Path("docs/evidence/source-history-contracts-20261104.json"),
    )
    cli.add_argument("--parser", type=Path, required=True)
    args = cli.parse_args()
    asset = build(args.bundle, args.output, args.evidence, args.parser)
    print(f"Verified {len(asset['engines'])} exact headunit history contracts")


if __name__ == "__main__":
    main()
