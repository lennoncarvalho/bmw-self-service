"""Source-defined coding reader prerequisites and separate entitlement backups."""

import hashlib
import json
import logging
import os
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from app.coding_db import CodingDatabase
from app.history_files import valid_vin
from app.operation_store import OperationStore
from app.protocol.contracts import (
    FailureKind,
    OperationCancelled,
    OperationContext,
    ProtocolFailure,
    TransportKind,
)
from app.resources import resource_path
from app.vehicle import did_data

_MAX_FILE = 4 * 1024 * 1024
ENET_READER_TIMING = (1.0, 7.0)
logger = logging.getLogger(__name__)


def reader_contract() -> tuple[dict, str]:
    """Load the bounded, development-compiled coding-reader contract."""
    with resource_path("coding_data/reader_contracts.json").open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError("Coding reader contract exceeds its bound")
    data = json.loads(raw)
    if data.get("schema_version") != 1 or not data.get("source_evidence_sha256"):
        raise ValueError("Coding reader contract is missing source provenance")
    for field in ("unlock_backup", "nbtevo"):
        if not isinstance(data.get(field), dict):
            raise ValueError("Coding reader contract is incomplete")
    return data, hashlib.sha256(raw).hexdigest()


def applies(address: int, definitions: list[str], db: CodingDatabase) -> bool:
    """Select the recovered outer reader branch from source identity."""
    contract, _ = reader_contract()
    backup = contract["unlock_backup"]
    return bool(
        address == backup["address"]
        or (db.primary_definition(definitions)[:8] == backup["primary_definition"])
    )


def _read_file(path: Path) -> bytes:
    """Read entitlement material with a fixed size bound."""
    with path.open("rb") as stream:
        payload = stream.read(_MAX_FILE + 1)
    if len(payload) > _MAX_FILE:
        raise ValueError("Entitlement backup exceeds its supported bound")
    return payload


def _publish(path: Path, payload: bytes) -> None:
    """Atomically publish and sync exact entitlement bytes before proceeding."""
    if len(payload) > _MAX_FILE:
        raise ValueError("Entitlement backup exceeds its supported bound")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = ""
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = stream.name
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def _verify(payload: bytes, variant: str, status: int, contract: dict) -> None:
    """Apply the source variant/status and RSA-MD5 entitlement checks."""
    if variant != contract["verify_variant"]:
        return
    if status == 4:
        raise ValueError("The headunit reports an invalid entitlement state")
    # The primary reader explicitly accepts short payloads, including its
    # unsigned formats. This is source verification, not a completeness claim.
    if len(payload) < 128:
        return
    expected = hashlib.md5(payload[:-128], usedforsecurity=False).hexdigest()
    signature = int.from_bytes(payload[-128:], "big")
    for modulus in contract["moduli"]:
        decoded = pow(signature, contract["public_exponent"], int(modulus, 16))
        encoded = decoded.to_bytes(max(1, (decoded.bit_length() + 7) // 8), "big")
        if encoded[0] & 0x80:
            encoded = b"\x00" + encoded
        if encoded.hex()[-32:] == expected:
            return
    raise ValueError("The saved headunit entitlement failed source signature verification")


def run_prerequisites(
    *,
    address: int,
    variant: str,
    definitions: list[str],
    database: CodingDatabase,
    vin: str,
    store: OperationStore,
    read: Callable[[bytes, int | None], bytes],
    read_only: bool,
    expected: dict | None = None,
    context: OperationContext | None = None,
    transport: TransportKind | None = None,
) -> dict:
    """Retrieve durable source entitlement material, then check headunit safety.

    The caller must hold the sole protocol owner and disruptive-action lockout.
    Sessions/routines stay forbidden in read-only mode. No entitlement upload,
    coding group mutation or automatic restoration is performed here.
    """
    contract, digest = reader_contract()
    if expected is not None and expected.get("contract_sha256") != digest:
        raise ValueError("Coding reader contract changed after preparation")
    result: dict = {"contract_sha256": digest, "files": [], "headunit": None}
    backup = contract["unlock_backup"]
    required = address == backup["address"] or (
        database.primary_definition(definitions)[:8] == backup["primary_definition"]
    )
    original_read = read

    def timed_read(payload: bytes, override: int | None = None) -> bytes:
        """Scope the source ENET response windows to headunit prerequisite requests."""
        if (
            context is None
            or transport != TransportKind.HSFZ
            or not required
            or override is not None
        ):
            return original_read(payload, override)
        timing = context.response_timing
        # Recovered ENET initial/pending response windows, still bounded by the
        # caller's absolute per-request and overall operation deadlines.
        context.response_timing = ENET_READER_TIMING
        logger.debug(
            "Coding reader request conn=%s operation=%s ecu=0x%04X data=%s "
            "initial_floor=1.000 pending_floor=7.000 remaining=%.3f",
            context.generation,
            context.operation_id,
            address,
            payload.hex(" "),
            context.deadline - time.monotonic(),
        )
        try:
            return original_read(payload, override)
        finally:
            context.response_timing = timing

    read = timed_read
    directory = store.root.parent / "coding-entitlements" / vin
    if required:
        if read_only or not valid_vin(vin):
            raise PermissionError(
                "Headunit source prerequisites require a writable identified session"
            )
        if expected is not None:
            for item in expected.get("files", []):
                name = item["name"]
                if Path(name).name != name or not name.startswith(f"FSC_{vin[-7:]}_"):
                    raise ValueError("Prepared entitlement filename is invalid")
                if hashlib.sha256(_read_file(directory / name)).hexdigest() != item["sha256"]:
                    raise ValueError("Prepared entitlement backup is missing or changed")
        stream_usable = True
        try:
            for session in backup["sessions"]:
                response = read(bytes.fromhex(session), None)
                if not response.startswith(b"\x50" + bytes.fromhex(session)[1:2]):
                    raise ValueError("Headunit backup session was rejected")
            raw = read(bytes.fromhex(backup["list_request"]), None)
            offset, width = backup["list_offset"], backup["entry_width"]
            if raw[:4] != b"\x71\x01\x0f\x1f" or len(raw) < 16 or (len(raw) - offset) % width:
                raise ValueError("Headunit entitlement list is malformed")
            seen = set()
            for start in range(offset, len(raw), width):
                entry = raw[start : start + width]
                identifier, upgrade = (
                    int.from_bytes(entry[:2], "big"),
                    int.from_bytes(entry[2:4], "big"),
                )
                status = int.from_bytes(entry[5:6], "big", signed=True)
                name = f"FSC_{vin[-7:]}_{identifier:04X}{upgrade:04X}.FSC"
                if name in seen:
                    raise ValueError("Headunit entitlement list contains duplicate identities")
                seen.add(name)
                path = directory / name
                if path.exists():
                    payload = _read_file(path)
                elif status == 2:
                    request = bytes.fromhex(backup["retrieve_prefix"]) + entry[:4]
                    response = read(request, None)
                    if (
                        response[:4] != b"\x71\x01\x0f\x1f"
                        or len(response) < backup["payload_offset"]
                    ):
                        raise ValueError("Headunit entitlement retrieval is malformed")
                    payload = response[backup["payload_offset"] :]
                    _verify(payload, variant, status, backup)
                    _publish(path, payload)
                else:
                    continue
                _verify(payload, variant, status, backup)
                result["files"].append(
                    {"name": name, "sha256": hashlib.sha256(payload).hexdigest()}
                )
        except (ConnectionError, TimeoutError, OperationCancelled):
            stream_usable = False
            raise
        except ProtocolFailure as exc:
            stream_usable = not exc.reconnect and exc.kind == FailureKind.NEGATIVE
            raise
        finally:
            if stream_usable:
                cleanup = read(bytes.fromhex(backup["cleanup"]), None)
                if not cleanup.startswith(b"\x50\x01"):
                    raise ValueError("Headunit backup session cleanup was not confirmed")
            else:
                logger.warning(
                    "Headunit reader failed; session cleanup skipped on an unusable stream"
                )
    guard = contract["nbtevo"]
    if address == guard["address"] and variant == guard["variant"]:
        level = did_data(
            read(bytes.fromhex(guard["ilevel_request"]), guard["ilevel_address"]), 0x100B
        )
        if len(level) < 24:
            raise ValueError("Headunit integration-level information is incomplete")
        first = level[:8]
        text = (
            f"{first[:4].decode('ascii')}-{first[4]}-{first[5]}-{int.from_bytes(first[6:8], 'big')}"
        )
        if any(prefix in text for prefix in guard["critical_prefixes"]):
            raise ValueError(
                "The headunit integration level is refused by the source coding reader"
            )
        ram_raw = read(bytes.fromhex(guard["ram_request"]), None)
        did_data(ram_raw, 0xD00A)
        if len(ram_raw) != guard["raw_length"]:
            raise ValueError("Headunit memory information is malformed")
        start = guard["ram_offset"]
        ram = int.from_bytes(
            ram_raw[start : start + guard["ram_width"]], "big", signed=guard["ram_signed"]
        )
        hmi = did_data(read(bytes.fromhex(guard["hmi_request"]), None), 0xD03F).decode("utf-8")
        if hmi.lower().startswith(guard["hmi_prefix"].lower()) and ram < guard["minimum_ram"]:
            raise ValueError(
                "The headunit software/memory combination is refused by the source reader"
            )
        result["headunit"] = {"integration_level": text, "ram": ram, "hmi": hmi}
    return result
