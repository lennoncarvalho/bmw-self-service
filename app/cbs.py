"""Condition Based Service read and reset (B-CBS-R / B-CBS-W, D-58).

Contracts: docs/evidence/task-c-cbs-reliability.md and the retained CBS contracts.
Generated definitions establish exact versions, primary roles and reset item
identifiers. A readable observation alone never grants reset ownership.

Native readers are preferred. Resets retain the source-defined plain write,
CBS7 start/result lifecycle and ordered DSC side effects. Software identity and
before-state are checked inside the same owner operation as the mutation.
Application confirmation is distinct from a later observed post-state. Counters
are separate from headunit history and are never rolled back or replayed.
"""

import contextlib
import hashlib
import json
import logging
import os
import tempfile
import time
import uuid
from calendar import monthrange
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from app.history_files import valid_vin
from app.ista_jobs import APP_SOURCE, JobBackend, JobRun
from app.protocol.contracts import FailureKind, OperationContext, ProtocolFailure, TransportKind
from app.resources import resource_path
from app.vehicle import DiagnosticCatalog, did_data
from app.worker import CarWorker

logger = logging.getLogger(__name__)
RECORD = 12
MAX_RECORD_BYTES = 1024 * 1024
# Recovered reader settle interval after an accepted reset (j6.g0.i.a.b).
SETTLE_SECONDS = 5.0
RESET_STATES = frozenset({"accepted", "rejected", "uncertain", "invalid", "changed", "failed"})
FINAL_STATES = frozenset({"verified", "response-confirmed", "rejected", "uncertain", "not-started"})
# v6 CBS_RESET_DETAIL_LESEN reasons (KOMBRDCT TAB_RUECK_GRUND, see the contract).
DETAIL_REASONS = {
    0x00: "no reason recorded",
    0x01: "invalid odometer",
    0x02: "invalid on-board date",
    0x03: "invalid coding",
    0x04: "ECU not initialised",
    0x05: "vehicle moving",
    0x06: "reset not allowed for this item type",
    0x07: "substitute value active",
    0x08: "vehicle in parked/residing state",
}
INSTRUCTIONS = (
    "A CBS reset cannot be undone by this app. If the outcome is uncertain, reconnect "
    "and read service status before any new reset."
)


def cbs_definitions() -> dict[str, Any]:
    """Load the embedded per-definition CBS version/owner/reset policy."""
    path = resource_path("coding_data/cbs_definitions.json")
    with path.open("rb") as stream:
        raw = stream.read(262145)
    if len(raw) > 262144:
        raise ValueError("CBS definitions exceed their supported size")
    data = json.loads(raw)
    if data.get("schema") != 1 or not isinstance(data.get("definitions"), dict):
        raise ValueError("Unsupported CBS definition format")
    return cast(dict[str, Any], data)


def _flag(value: int, invalid: dict[int, str]) -> str | None:
    return invalid.get(value)


def decode_record(record: bytes, version: str) -> dict[str, Any]:
    """Decode one 12-byte CBS record by its PRG version; raw bytes are always kept."""
    if len(record) != RECORD:
        raise ValueError("CBS record has an unsupported length")
    v63 = version in ("6.3", "7.0")
    remaining = int.from_bytes(record[1:3], "big", signed=True)
    unit = record[3] & 0x0F
    item: dict[str, Any] = {
        "item": record[0],
        "raw": record.hex(),
        "status": record[3] >> 4,
        "remaining": None,
        "unit": None,
        "count": record[4] if v63 else record[4] & 0x1F,
        "availability": None,
        "due_month": None,
        "due_year": None,
        "due_day": None,
        "forecast_km": None,
        "forecast_months": None,
        "notes": [],
    }
    sentinel = ({0x7FFF: "no information", -0x8000: "not relevant"} if version != "5" else {}).get(
        remaining
    )
    if sentinel:
        item["notes"].append(f"Remaining: {sentinel}")
    elif version == "6.3" and remaining < 0:
        item["notes"].append("Remaining: not allowed (ECU job text)")
    elif version == "6.3" and remaining * 10 > 0x7FFF:
        item["notes"].append("Remaining distance exceeds the ECU job result range")
    elif unit == 1:
        item.update(remaining=remaining * 10, unit="km")
    elif unit == 0 and version != "6.3":
        item.update(remaining=remaining, unit="%")
    elif unit == 2 and version != "6.3":
        item.update(remaining=remaining, unit="days")
    else:
        item["notes"].append("Remaining value has no valid unit")
    if (not v63 and item["count"] == 0x1F) or (v63 and item["count"] > 250):
        item["count"] = None
        item["notes"].append("Service count not available")
    availability = record[5]
    special = {0xFD: "no information", 0xFE: "new/uninitialised ECU", 0xFF: "invalid"}
    if availability in special:
        item["notes"].append(f"Availability: {special[availability]}")
    elif availability <= 100:
        item["availability"] = availability
    else:
        item["notes"].append("Availability outside 0-100 %")
    if record[6] != 0xFF and (version != "6.3" or record[6] * 1000 <= 0x7FFF):
        item["forecast_km"] = record[6] * 1000
    month = record[7] & 0x0F
    if 1 <= month <= 12:
        item["due_month"] = month
    year = record[8] if v63 else record[8] & 0x3F
    if (v63 and 0 < year < 0xFA) or (not v63 and 0 < year < 0x3F):
        item["due_year"] = 2000 + year
    if v63 and 0 < (record[10] & 0x3F) <= 31:
        item["due_day"] = record[10] & 0x3F
    if record[9] not in (0, 0xFF):
        item["forecast_months"] = record[9]
    return _calendar_record(item)


def _calendar_record(item: dict[str, Any]) -> dict[str, Any]:
    """Keep impossible calendar combinations out of due-date presentation."""
    year, month, day = (item.get(key) for key in ("due_year", "due_month", "due_day"))
    if year and month and day and day > monthrange(year, month)[1]:
        item["notes"].append("Invalid target calendar date in the ECU record")
        item.update(due_year=None, due_month=None, due_day=None)
    return item


def decode_cbs_response(response: bytes, version: str) -> list[dict[str, Any]]:
    """Require the exact `62 10 01` echo and a whole number of 12-byte records."""
    data = did_data(response, 0x1001)
    if len(data) % RECORD:
        raise ValueError("CBS response is not a whole number of records")
    return [decode_record(data[i : i + RECORD], version) for i in range(0, len(data), RECORD)]


RESET_POLICIES = frozenset({"default", "dsc25-plain", "routine-6.3", "routine-7.0"})
JOB_READ = "CBS_DATEN_LESEN"
JOB_RESET = "CBS_RESET"
# Policies whose CBS_RESET job telegram equals reset_request() (verified offline for
# DME_BX8, KOMB25 and DSC_I1). DSC_25 has a separate ordered-job path with
# acknowledged side effects. Routine owners use their separate start/result jobs.
JOB_RESET_POLICIES = frozenset({"default"})
# CBS_RESET arguments after the item: availability 100 %, service count +1 (31);
# the remaining arguments keep the job's "unchanged" defaults.
JOB_RESET_VALUES = "100;31"
_JOB_UNITS = {0: "%", 1: "km", 2: "days"}
_JOB_UNIT_TEXTS = {"%": "%", "Weg": "km", "Tage": "days", "Zeit": "days"}
_JOB_REMAINING_UNITS = frozenset({"x 10 km", "Tage", "%"})


def reset_request(item: int, policy: str = "default") -> bytes:
    """Encode the owner's recovered reset for one item.

    Default/DSC_25 plain path: 2E 1001 record with availability 100, count +1
    (0x1F) and every other field unchanged. 6.3 (D94BX7A0): routine 31 01 1000
    with reset type 0x02, the PRG table's only "Standardreset", and no value.
    """
    if not 0 <= item <= 0xFF:
        raise ValueError("Invalid CBS item")
    if policy in ("routine-6.3", "routine-7.0"):
        return bytes.fromhex("31011000") + bytes((item,)) + bytes.fromhex("02FFFFFF")
    if policy not in ("default", "dsc25-plain"):
        raise ValueError("No recovered reset for this CBS owner")
    return bytes.fromhex("2E100101") + bytes((item,)) + bytes.fromhex("641F80000FFF0F3FFF00")


def check_reset_reply(
    policy: str,
    reply: bytes,
    *,
    routine_codes: dict[str, Any] | None = None,
    routine_start: bool = False,
) -> tuple[str, str]:
    """Classify a final reset reply: accepted, rejected (final, nothing applied) or uncertain."""
    if policy in ("routine-6.3", "routine-7.0"):
        if len(reply) == 3 and reply[:2] == b"\x7f\x31":
            if routine_start and reply[2] != 0x78:
                return "rejected", "The ECU rejected reset start"
            return "uncertain", "The ECU rejected the result query; reset completion is unknown"
        header = b"\x71\x01\x10\x00" if routine_start else b"\x71\x03\x10\x00"
        if len(reply) != 8 or reply[:4] != header:
            return "uncertain", "Unexpected CBS routine result"
        if reply[4] == 0 and reply[5] == 0:
            return "accepted", ""
        if reply[4] in (0xFE, 0xFF) or reply[5] in (0xFE, 0xFF):
            return "uncertain", "The ECU returned an unavailable CBS routine result"
        if routine_codes is None:
            return "uncertain", "The CBS routine result tables are unavailable"
        codes = routine_codes
        messages = []
        for value, table in (
            (reply[4], "TAB_CBS_RETURN_CODE_ALLGEMEIN"),
            (reply[5], "TAB_CBS_RETURN_CODE_KOMPONENTE"),
        ):
            if value:
                message = codes[table].get(f"{value:02X}")
                if message is None:
                    return "uncertain", "The ECU returned an unknown CBS routine result code"
                messages.append(message)
        return "rejected", "ECU job result: " + "; ".join(messages)
    if reply == b"\x6e\x10\x01":
        return "accepted", ""
    if reply[:2] == b"\x7f\x2e" and len(reply) == 3 and reply[2] != 0x78:
        return "rejected", "ECU rejected the reset"
    return "uncertain", "Unexpected reset reply"


def _job_int(values: dict[str, Any], key: str) -> int | None:
    value = values.get(key)
    return value if isinstance(value, int) else None


def _job_text(values: dict[str, Any], key: str) -> str:
    value = values.get(key)
    return value.strip() if isinstance(value, str) else ""


def job_record(values: dict[str, Any], version: str) -> dict[str, Any]:
    """Map one CBS_DATEN_LESEN result set to the record shape of ``decode_record``.

    The job's own unit and validity texts decide which values are meaningful.
    """
    status = _job_int(values, "STATUS_MESSUNG")
    item: dict[str, Any] = {
        "item": _job_int(values, "ID_FN_CBS_MESS_WERT"),
        "raw": "",
        "status": status >> 4 if status is not None else None,
        "status_text": _job_text(values, "STATUS_MESSUNG_TEXT"),
        "remaining": None,
        "unit": None,
        "count": None,
        "availability": None,
        "due_month": None,
        "due_year": None,
        "due_day": None,
        "forecast_km": None,
        "forecast_months": None,
        "notes": [],
        "job_text": _job_text(values, "ID_FN_CBS_MESS_TEXT"),
    }
    notes: list[str] = item["notes"]
    remaining = _job_int(values, "RMMI_CBS_WERT")
    remaining_unit = _job_text(values, "RMMI_CBS_EINH")
    code = _job_int(values, "ST_UN_CBS_WERT")
    unit = _JOB_UNITS.get(code) if code is not None else None
    if code is None:
        unit = _JOB_UNIT_TEXTS.get(_job_text(values, "ST_UN_CBS_TEXT"))
    if remaining is None:
        notes.append("Remaining value not reported by the job")
    elif remaining_unit not in _JOB_REMAINING_UNITS:
        notes.append(f"Remaining: {remaining_unit or 'no unit'} (ECU job text)")
    elif unit is None:
        notes.append("Remaining value has no valid unit")
    else:
        item.update(remaining=remaining * 10 if unit == "km" else remaining, unit=unit)
    count = _job_int(values, "COU_RSTG_CBS_MESS_WERT")
    limit = 0xFA if version == "6.3" else 0x1F
    if (
        count is None
        or not 0 <= count < limit
        or _job_text(values, "COU_RSTG_CBS_MESS_EINH") == "nicht erlaubt"
    ):
        notes.append("Service count not available")
    else:
        item["count"] = count
    availability = _job_int(values, "AVAI_CBS_WERT")
    availability_unit = _job_text(values, "AVAI_CBS_EINH")
    if availability is not None and availability_unit == "%" and 0 <= availability <= 100:
        item["availability"] = availability
    elif availability_unit == "%":
        notes.append("Availability outside 0-100 %")
    else:
        notes.append(f"Availability: {availability_unit or 'not reported'} (ECU job text)")
    month = _job_int(values, "ZIEL_MM_WERT")
    if month is not None and 1 <= month <= 12:
        item["due_month"] = month
    year = _job_int(values, "ZIEL_YY_WERT")
    limit = 0xFA if version == "6.3" else 0x3F
    if (
        year is not None
        and _job_text(values, "ZIEL_YY_EINH") == "Jahre nach 2000"
        and 0 < year < limit
    ):
        item["due_year"] = 2000 + year
    day = _job_int(values, "ZIEL_TT_WERT")
    if day is not None and 0 < day < 0x1F:
        item["due_day"] = day
    way = _job_int(values, "FRC_INTM_WAY_CBS_MESS")
    if way is not None and way != 0xFF:
        item["forecast_km"] = way * 1000
    months = _job_int(values, "FRC_INTM_T_CBS_MESS")
    if months is not None and months not in (0, 0xFF):
        item["forecast_months"] = months
    return _calendar_record(item)


def job_record_v7(values: dict[str, Any], version: str = "7.0") -> dict[str, Any]:
    """Use routine-owner named results; CBS6.3 also scales remaining distance."""
    item: dict[str, Any] = {
        "item": _job_int(values, "ID_CBS_MESS"),
        "raw": "",
        "status": _job_int(values, "STATUS_MESSUNG_BOS"),
        "status_text": _job_text(values, "STATUS_MESSUNG_BOS_TEXT"),
        "remaining": None,
        "unit": None,
        "count": None,
        "availability": None,
        "due_month": None,
        "due_year": None,
        "due_day": None,
        "forecast_km": None,
        "forecast_months": None,
        "notes": [],
        "job_text": _job_text(values, "ID_CBS_MESS_TEXT"),
    }
    remaining = _job_int(values, "RMMI_CBS")
    unit_code = _job_int(values, "ST_UN_CBS")
    unit = _JOB_UNITS.get(unit_code) if unit_code is not None else None
    info = _job_text(values, "RMMI_CBS_INFO")
    valid_info = (
        info == "km" and unit == "km" if version == "6.3" else info in ("* 10km", "Tage", "%")
    )
    if remaining is not None and unit is not None and valid_info:
        scaled = remaining * 10 if version != "6.3" and unit == "km" else remaining
        item.update(remaining=scaled, unit=unit)
    else:
        item["notes"].append(f"Remaining: {info or 'not reported'} (ECU job text)")
    count = _job_int(values, "COU_RSTG_CBS_MESS")
    if count is not None and 0 <= count <= 250:
        item["count"] = count
    else:
        item["notes"].append("Service count not available")
    availability = _job_int(values, "AVAI_CBS")
    if availability is not None and 0 <= availability <= 100:
        item["availability"] = availability
    else:
        item["notes"].append(
            f"Availability: {_job_text(values, 'AVAI_CBS_TEXT') or 'not reported'} (ECU job text)"
        )
    for field, source, low, high in (
        ("due_month", "TARD_MON_CBS_MESS", 1, 12),
        ("due_year", "TARD_YR_CBS_MESS", 2001, 2249),
        ("due_day", "TARD_DY_CBS_MESS", 1, 31),
        ("forecast_km", "FRC_INTM_WAY_CBS_MESS", 0, 254000),
        (
            "forecast_months",
            "FRC_INT_T_CBS_MESS" if version == "6.3" else "FRC_INTM_T_CBS_MESS",
            1,
            254,
        ),
    ):
        value = _job_int(values, source)
        if value is not None and low <= value <= high:
            item[field] = value
    return _calendar_record(item)


def job_cbs_records(run: JobRun, version: str) -> list[dict[str, Any]]:
    """Records of a successful CBS_DATEN_LESEN run, each with its raw 12-byte record.

    The raw record comes from the owner's own `62 10 01` reply; it is left empty
    (and the item is not resettable) unless exactly one record carries the item.
    """
    if run.result is None:
        raise ValueError("CBS job produced no results")
    data = did_data(run.response(), 0x1001)
    if len(data) % RECORD:
        raise ValueError("CBS job response is not a whole number of records")
    raws = [data[i : i + RECORD] for i in range(0, len(data), RECORD)]
    records = []
    for values in run.result.sets:
        routine = version in ("6.3", "7.0")
        id_field = "ID_CBS_MESS" if routine else "ID_FN_CBS_MESS_WERT"
        if not isinstance(values.get(id_field), int):
            continue
        record = job_record_v7(values, version) if routine else job_record(values, version)
        matches = [raw for raw in raws if raw[0] == record["item"]]
        if len(matches) == 1:
            record["raw"] = matches[0].hex()
            if version == "6.3" and matches[0][6] != 0xFF and matches[0][6] * 1000 > 0x7FFF:
                # This job emits the scaled forecast as a signed 16-bit result.
                # Keep an overflowed value unknown rather than display its wrapped number.
                record["forecast_km"] = None
                record["notes"].append("Distance forecast exceeds the ECU job result range")
            if (
                version == "6.3"
                and int.from_bytes(matches[0][1:3], "big", signed=True) * 10 > 0x7FFF
            ):
                record.update(remaining=None, unit=None)
                record["notes"].append("Remaining distance exceeds the ECU job result range")
        else:
            record["notes"].append("Raw record not identified in the ECU reply")
        records.append(record)
    if len(records) != len(raws) or sorted(rec["item"] for rec in records) != sorted(
        raw[0] for raw in raws
    ):
        raise ValueError("CBS job results do not account for every returned record")
    return records


def job_reset_args(backend: JobBackend, name: str, item: int) -> str:
    """CBS_RESET arguments for an item from the job file's CBSKENNUNG table, or ""."""
    table = backend.table(name, "CBSKENNUNG")
    if table is None:
        return ""
    columns, rows = table
    if "NR" not in columns or "CBS_K" not in columns:
        return ""
    number, key = columns.index("NR"), columns.index("CBS_K")
    for row in rows:
        try:
            if int(row[number], 16) == item and row[key] and ";" not in row[key]:
                return f"{row[key]};{JOB_RESET_VALUES}"
        except ValueError:
            continue
    return ""


def cbs_targets(
    ecus: list[dict[str, Any]], backend: JobBackend | None = None
) -> list[dict[str, Any]]:
    """Identified ECUs with a recovered CBS definition or a CBS_DATEN_LESEN job.

    A recovered definition fixes the owner's address, version and reset policy;
    a job-only owner is read with its job and has no reset policy.
    """
    definitions = cbs_definitions()["definitions"]
    targets = []
    for row in ecus:
        if row.get("identified") is not True:
            continue
        name = str(row.get("name"))
        address = int(str(row.get("addr")), 16)
        definition = definitions.get(name)
        if definition is not None and address != definition["address"]:
            continue
        read_job = definition.get("read_job", JOB_READ) if definition else JOB_READ
        job = backend is not None and backend.has_job(name, read_job)
        if definition is None and not job:
            continue
        base = dict(definition or {"address": address, "version": "unknown", "reset": "none"})
        base.setdefault("ownership", "owner-not-recovered")
        if (
            job and backend is not None and backend.file_sha256(name) != base.get("prg_sha256")
        ) or (
            base["version"] in ("6.3", "7.0")
            and (not job or backend is None or not backend.has_job(name, JOB_RESET))
        ):
            base["reset"] = "blocked"
            base["reset_block_reason"] = "Exact reviewed ECU job data unavailable; reset blocked"
        targets.append(
            {
                **base,
                "name": name,
                "index": row["address_index"],
                "job": job,
                "defined": definition is not None,
            }
        )
    return targets


def read_cbs(
    connection: Any, ecus: list[dict[str, Any]], backend: JobBackend | None = None
) -> dict[str, Any]:
    """Read every applicable owner once; per-owner failures stay explicit."""
    deadline = time.monotonic() + 30.0
    jobs = backend if backend is not None else JobBackend(connection)
    try:
        return _read_cbs(connection, ecus, jobs, deadline)
    finally:
        if backend is None:
            jobs.close()


def _read_cbs(
    connection: Any, ecus: list[dict[str, Any]], jobs: JobBackend, deadline: float
) -> dict[str, Any]:
    """Read source-selected CBS owners within one bounded batch."""
    data = cbs_definitions()
    labels: dict[str, str] = data["items"]
    blocked_items = set(data["not_resettable"])
    owners: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    for target in cbs_targets(ecus, jobs):
        owner = {
            k: target[k] for k in ("name", "address", "version", "index", "reset", "ownership")
        }
        if "read_job" in target:
            owner["read_job"] = target["read_job"]
        for key in ("prg_sha256", "software_request", "ownership_reason", "reset_block_reason"):
            if key in target:
                owner[key] = target[key]
        owner["source"] = jobs.fallback_source(target["name"])
        remaining = deadline - time.monotonic()
        if not connection.alive_ok or remaining <= 0:
            reason = "connection-closed" if not connection.alive_ok else "budget-exhausted"
            owners.append({**owner, "state": f"not-attempted-{reason}"})
            continue
        records: list[dict[str, Any]] | None = None
        response = b""
        if target["job"]:
            run = jobs.run(
                target["name"],
                target["address"],
                target.get("read_job", JOB_READ),
                timeout=remaining,
            )
            if run.interpreter_failed and target["defined"]:
                logger.warning("CBS reader job failed for %s: %s", target["name"], run.error)
                owner["source"] = f"{APP_SOURCE} (ECU job reader unavailable)"
            else:
                owner["source"] = run.source
                response = run.response()
                state = run.state()
                if state == "read":
                    try:
                        records = job_cbs_records(run, target["version"])
                    except ValueError:
                        state = "invalid"
                if records is None:
                    if state == "unsupported" and not target["defined"]:
                        # The ECU states it has no CBS data; it cannot own an item.
                        state = "not-held"
                    elif state != "timeout":
                        state = "unavailable"
                    owners.append({**owner, "state": state, "response": response.hex()})
                    continue
        if records is None:
            try:
                left = deadline - time.monotonic()
                if left <= 0:
                    raise TimeoutError("CBS read budget exhausted")
                response = connection.send_uds(
                    target["address"],
                    b"\x22\x10\x01",
                    context=connection.context(left),
                )
                records = decode_cbs_response(response, target["version"])
            except (ValueError, TimeoutError, ConnectionError) as exc:
                # One owner's failure never hides the others; a lost stream stops the rest.
                state = "timeout" if isinstance(exc, TimeoutError) else "unavailable"
                owners.append({**owner, "state": state, "response": response.hex()})
                continue
        owner["software"] = ""
        if target.get("software_request"):
            try:
                if deadline <= time.monotonic():
                    raise TimeoutError("CBS software identity budget exhausted")
                software = connection.send_uds(
                    target["address"],
                    bytes.fromhex(target["software_request"]),
                    context=connection.context(deadline - time.monotonic()),
                )
                owner["software_response"] = software.hex()
                if not did_data(software, 0xF101):
                    raise ValueError("Empty software identity")
                owner["software"] = software.hex()
            except (ValueError, TimeoutError, ConnectionError):
                owner["software_state"] = "unavailable — resets blocked"
        owners.append({**owner, "state": "read", "response": response.hex()})
        for record in records:
            key = f"{record['item']:02X}"
            items.append(
                {
                    **record,
                    "label": labels.get(key)
                    or (
                        f"{record['job_text']} (German text from the ECU job file)"
                        if record.get("job_text")
                        else f"CBS item 0x{key}"
                    ),
                    "owner": owner,
                    "resettable": (
                        owner["ownership"] == "primary"
                        and owner["reset"] in RESET_POLICIES
                        and bool(record["raw"])
                        and bool(owner["software"])
                        and record["availability"] is not None
                        and record["count"] is not None
                        and key in target.get("reset_items", [])
                        and key not in blocked_items
                        and (
                            owner["reset"] != "dsc25-plain"
                            or f"{record['item']:02X}" in target.get("record_index", {})
                        )
                    ),
                }
            )
    seen: dict[int, int] = {}
    for record in items:
        if record["owner"]["ownership"] == "primary":
            seen[record["item"]] = seen.get(record["item"], 0) + 1
    complete = all(
        owner["state"] in ("read", "not-held")
        for owner in owners
        if owner["ownership"] == "primary"
    )
    for record in items:
        if record["owner"]["ownership"] != "primary":
            record["resettable"] = False
            record["notes"].append(
                record["owner"].get("ownership_reason")
                or "Primary service-reset owner not recovered for this observation source"
            )
        elif not record["owner"].get("software"):
            record["notes"].append("Software identity unavailable; read again before resetting")
        elif seen.get(record["item"], 0) > 1:
            # No source rule picks a winner between owners; never guess one.
            record["resettable"] = False
            record["notes"].append("More than one primary record reports this item; reset blocked")
        elif not complete and record["resettable"]:
            # An unread owner could also hold this item; ownership is not established.
            record["resettable"] = False
            record["notes"].append("Not every CBS owner could be read; reset blocked")
        if record["owner"]["ownership"] == "primary" and (
            record["availability"] is None or record["count"] is None
        ):
            record["notes"].append("Availability or service count is unavailable; reset blocked")
        if record["owner"].get("reset_block_reason"):
            record["notes"].append(record["owner"]["reset_block_reason"])
        definition = data["definitions"].get(record["owner"]["name"], {})
        if record["owner"]["ownership"] == "primary" and (
            f"{record['item']:02X}" not in definition.get("reset_items", [])
        ):
            record["notes"].append("No standard reset identifier for this item in the definition")
    return {"owners": owners, "items": items, "observed_clock": time.monotonic()}


class CbsReadWorker(CarWorker):
    """Read service status from every applicable identified owner."""

    def __init__(
        self,
        connection: Any,
        ecus: list[dict[str, Any]],
        *,
        backend: JobBackend | None = None,
    ) -> None:
        super().__init__(connection)
        self.ecus = [dict(row) for row in ecus]
        self.backend = backend

    def do_work(self) -> dict[str, Any]:
        """Read-only CBS_DATEN_LESEN / `22 10 01` per owner; allowed in a read-only session."""
        if getattr(self.connection, "kind", None) != TransportKind.HSFZ:
            raise ValueError("CBS needs a recovered logical-address mapping on this transport")
        return read_cbs(self.connection, self.ecus, self.backend)


def demo_cbs(data: dict[str, Any]) -> dict[str, Any]:
    """Decode DEMO snapshot records with the live decoder; never resettable or live."""
    labels: dict[str, str] = cbs_definitions()["items"]
    owners, items = [], []
    for row in data.get("cbs", []):
        owner = {
            "name": row["name"],
            "address": int(row["address"], 16),
            "version": row["version"],
            "index": "DEMO",
            "reset": "demo",
        }
        owners.append({**owner, "state": "DEMO"})
        for record in decode_cbs_response(bytes.fromhex(row["response"]), row["version"]):
            key = f"{record['item']:02X}"
            label = labels.get(key, f"CBS item 0x{key}")
            items.append({**record, "label": label, "owner": owner, "resettable": False})
    return {"owners": owners, "items": items, "observed_clock": time.monotonic()}


# ── Durable intent/results journal ─────────────────────────────────────────


def _encoded(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_encoded(value)).hexdigest()


def _publish(path: Path, record: dict[str, Any]) -> None:
    """Atomically replace and fsync, so intent exists before any request is sent."""
    record["sha256"] = _digest({k: v for k, v in record.items() if k != "sha256"})
    raw = _encoded(record)
    if len(raw) > MAX_RECORD_BYTES:
        raise ValueError("CBS operation record exceeds its size limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".cbs-", delete=False) as out:
            temporary = out.name
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
        temporary = None
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


def load_record(path: Path) -> dict[str, Any]:
    """Load and integrity-check one record; it never authorizes a vehicle request."""
    with path.open("rb") as stream:
        raw = stream.read(MAX_RECORD_BYTES + 1)
    if len(raw) > MAX_RECORD_BYTES:
        raise ValueError("CBS operation record exceeds its size limit")
    record = json.loads(raw)
    if (
        not isinstance(record, dict)
        or record.get("schema_version") != 1
        or record.get("kind") != "cbs-reset"
        or set(record) != {"schema_version", "kind", "intent", "intent_sha256", "events", "sha256"}
        or _digest(record["intent"]) != record["intent_sha256"]
        or _digest({k: v for k, v in record.items() if k != "sha256"}) != record["sha256"]
        or not isinstance(record["events"], list)
    ):
        raise ValueError("Invalid CBS operation record")
    return cast(dict[str, Any], record)


class CbsJournalStore:
    """Separate durable CBS intent/results; not a coding backup or restorable state."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path.home() / "BMW-Tool" / "cbs" / "operations"

    def prepare(self, intent: dict[str, Any]) -> Path:
        """Freeze exact intent and the observed before-record prior to sending."""
        intent = json.loads(_encoded(intent))
        record = {
            "schema_version": 1,
            "kind": "cbs-reset",
            "intent": intent,
            "intent_sha256": _digest(intent),
            "events": [],
            "sha256": "",
        }
        path = self.root / f"{intent['id']}.json"
        if path.exists():
            raise ValueError("CBS operation identifier already exists")
        self._append(record, "prepared", None, b"", b"", "")
        _publish(path, record)
        load_record(path)
        return path

    @staticmethod
    def _append(
        record: dict[str, Any],
        state: str,
        step: str | None,
        request: bytes,
        response: bytes,
        detail: str,
    ) -> None:
        record["events"].append(
            {
                "sequence": len(record["events"]),
                "time": datetime.now(UTC).isoformat(),
                "state": state,
                "step": step,
                "request": request.hex(),
                "response": response.hex(),
                "detail": detail,
            }
        )

    def record(
        self,
        path: Path,
        state: str,
        step: str | None = None,
        request: bytes = b"",
        response: bytes = b"",
        detail: str = "",
    ) -> None:
        """Publish one ordered event; a failure stops any further vehicle request."""
        record = load_record(path)
        self._append(record, state, step, request, response, detail)
        _publish(path, record)


# ── Reset ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CbsResetPlan:
    """Frozen confirmation: exact owner identity, item and observed before-record."""

    vin: str
    owner: dict[str, Any]
    item: int
    label: str
    before_raw: str

    def intent(self, execution: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return the durable intent stored before any send.

        Args:
            execution: How the request is produced: the job file, job, arguments,
                grant and file hash for a job-backed reset, else the app request.
        """
        return {
            "execution": execution or {"path": "app-request"},
            "id": uuid.uuid4().hex,
            "created": datetime.now(UTC).isoformat(),
            "environment": "live",
            "vin": self.vin,
            "owner": dict(self.owner),
            "item": {"id": f"{self.item:02X}", "label": self.label},
            "before_raw": self.before_raw,
            "before_provenance": "read-in-this-connection",
            "preconditions": {
                "session": "default",
                "session_request_if_needed": "1001",
                "identity_request": "22f150",
                "software_request": "22f101",
                "before_request": "221001",
            },
            "request": reset_request(self.item, self.owner["reset"]).hex(),
            "request_sequence": (
                [reset_request(self.item, self.owner["reset"]).hex(), "31031000"]
                if self.owner["reset"] in ("routine-6.3", "routine-7.0")
                else [reset_request(self.item, self.owner["reset"]).hex()]
            ),
            "completion": (
                "exact 71 01 1000, then 71 03 1000 with zero application codes and re-read"
                if self.owner["reset"] == "routine-7.0"
                else "exact 71 01 1000 00 00 RR RR, then 71 03 1000 00 00 RR RR and re-read"
                if self.owner["reset"] == "routine-6.3"
                else "exact 6E1001, then re-read after settle"
            ),
        }


def _primary_reset_owner(owner: dict[str, Any]) -> bool:
    """Require the exact source-defined primary reset owner metadata."""
    definition = cbs_definitions()["definitions"].get(owner.get("name"), {})
    return (
        definition.get("ownership") == "primary"
        and definition.get("address") == owner.get("address")
        and definition.get("version") == owner.get("version")
        and definition.get("reset") == owner.get("reset")
        and definition.get("prg_sha256") == owner.get("prg_sha256")
        and owner.get("ownership") == "primary"
    )


def plan_reset(vin: str, item: dict[str, Any]) -> CbsResetPlan:
    """Freeze a reset only for a resettable item read from its owner in this session."""
    if not valid_vin(vin):
        raise PermissionError("A verified vehicle identity is required before a CBS reset")
    if not item.get("resettable"):
        raise PermissionError("This CBS item has no source-supported reset")
    owner = item["owner"]
    try:
        raw = bytes.fromhex(item.get("raw", ""))
        software = bytes.fromhex(owner.get("software", ""))
        software_valid = bool(did_data(software, 0xF101))
    except ValueError:
        raw, software_valid = b"", False
    if (
        len(raw) != RECORD
        or raw[0] != item["item"]
        or f"{raw[0]:02X}" in cbs_definitions()["not_resettable"]
        or not software_valid
    ):
        raise PermissionError("Fresh CBS data and software identity are required for this item")
    if not _primary_reset_owner(owner):
        raise PermissionError("This source is not an established primary service-reset owner")
    definition = cbs_definitions()["definitions"][owner["name"]]
    before = decode_record(raw, owner["version"])
    if (
        f"{raw[0]:02X}" not in definition.get("reset_items", [])
        or before["availability"] is None
        or before["count"] is None
    ):
        raise PermissionError("This record has no available source-supported standard reset")
    policy = owner.get("reset")
    if policy not in RESET_POLICIES or (
        (policy in ("routine-6.3", "routine-7.0")) != (owner.get("version") in ("6.3", "7.0"))
    ):
        raise PermissionError("This CBS owner has no source-supported reset")
    if policy == "dsc25-plain" and f"{int(item['item']):02X}" not in (
        cbs_definitions()["definitions"].get(owner["name"], {}).get("record_index", {})
    ):
        raise PermissionError("This DSC software defines a reset only for brake pads")
    return CbsResetPlan(vin, dict(owner), int(item["item"]), str(item["label"]), str(item["raw"]))


class CbsResetWorker(CarWorker):
    """Reset one confirmed item exactly once and report checked, honest outcomes."""

    def __init__(
        self,
        connection: Any,
        plan: CbsResetPlan,
        store: CbsJournalStore,
        *,
        power_acknowledged: bool = False,
        dsc_extra_acknowledged: bool = False,
        backend: JobBackend | None = None,
    ) -> None:
        """Retain the frozen reset plan, storage and explicit power acknowledgement."""
        super().__init__(connection)
        self.plan = CbsResetPlan(
            plan.vin, json.loads(_encoded(plan.owner)), plan.item, plan.label, plan.before_raw
        )
        self.store = store
        self.power_acknowledged = power_acknowledged
        self.dsc_extra_acknowledged = dsc_extra_acknowledged
        self.backend = backend
        self._executed = False
        self.report: dict[str, Any] = {
            "path": "",
            "state": "not-started",
            "events": [],
            "after": None,
            "detail": "",
            "execution": "",
            "persistence_failed": False,
            "instructions": INSTRUCTIONS,
        }

    def _job_execution(self, backend: JobBackend, request: bytes) -> dict[str, Any] | None:
        """The CBS_RESET job call for a default-policy owner with a job file, else ``None``."""
        owner = self.plan.owner
        if owner["reset"] == "dsc25-plain" and self.dsc_extra_acknowledged:
            definition = cbs_definitions()["definitions"].get(owner["name"], {})
            if (
                not definition.get("extra_sequence")
                or not backend.has_job(owner["name"], JOB_RESET)
                or backend.file_sha256(owner["name"]) != definition.get("prg_sha256")
            ):
                return None
            sequence = [
                request.hex() if part == "{reset}" else part
                for part in definition["extra_sequence"]
            ]
            return {
                "path": "job-dsc25",
                "job": JOB_RESET,
                "job_file": str(getattr(backend.job_file(owner["name"]), "name", "")),
                "job_file_sha256": definition["prg_sha256"],
                "args": job_reset_args(backend, owner["name"], self.plan.item),
                "grant": ["2E", "86", "31", "14"],
                "request_sequence": sequence,
                "allowed_request_sequences": [[request.hex()], sequence],
                "side_effects": list(definition["side_effects"]),
                "extra_svk": list(definition["extra_svk"]),
                "record_index": dict(definition["record_index"]),
            }
        if owner["reset"] in ("routine-6.3", "routine-7.0"):
            definition = cbs_definitions()["definitions"].get(owner["name"], {})
            if (
                definition.get("reset") != owner["reset"]
                or not backend.has_job(owner["name"], JOB_RESET)
                or backend.file_sha256(owner["name"]) != definition.get("prg_sha256")
            ):
                raise PermissionError("The exact CBS routine job definition is not available")
            return {
                "path": "job-routine",
                "job": JOB_RESET,
                "job_file": str(getattr(backend.job_file(owner["name"]), "name", "")),
                "job_file_sha256": definition["prg_sha256"],
                "args": f"STR;0x{self.plan.item:02X};standard",
                "results_args": "RRR",
                "grant": ["31"],
                "expected_request": request.hex(),
                "results_request": "31031000",
                "results_delay_ms": definition.get("results_delay_ms", 0),
            }
        if owner["reset"] not in JOB_RESET_POLICIES or not backend.has_job(
            owner["name"], JOB_RESET
        ):
            return None
        definition = cbs_definitions()["definitions"].get(owner["name"], {})
        if backend.file_sha256(owner["name"]) != definition.get("prg_sha256"):
            raise PermissionError("The current CBS job hash has no reviewed reset contract")
        return {
            "path": "ista-job",
            "job_file": str(getattr(backend.job_file(owner["name"]), "name", "")),
            "job_file_sha256": backend.file_sha256(owner["name"]),
            "job": JOB_RESET,
            "args": job_reset_args(backend, owner["name"], self.plan.item),
            "grant": ["2E"],
            "expected_request": request.hex(),
        }

    def do_work(self) -> dict[str, Any]:
        """Persist intent, then run identity/before/reset/settle/re-read on the owner."""
        if self._executed:
            raise PermissionError("A CBS reset cannot be replayed")
        self._executed = True
        connection, plan = self.connection, self.plan
        if not _primary_reset_owner(plan.owner):
            raise PermissionError("The source primary reset owner changed or is not recovered")
        plan_reset(
            plan.vin,
            {
                "resettable": True,
                "owner": plan.owner,
                "item": plan.item,
                "label": plan.label,
                "raw": plan.before_raw,
            },
        )
        if (
            not self.power_acknowledged
            or not valid_vin(plan.vin)
            or getattr(connection, "power_sufficient", None) is False
            or connection.read_only
            or connection.kind != TransportKind.HSFZ
            or connection.verified_vin != plan.vin
            or not connection.alive_ok
        ):
            raise PermissionError("CBS reset requires power acknowledgement and the same session")
        backend = self.backend if self.backend is not None else JobBackend(connection)
        try:
            return self._reset(backend)
        finally:
            if self.backend is None:
                backend.close()

    def _reset(self, backend: JobBackend) -> dict[str, Any]:
        """Persist intent and execute the exact reset policy with observed outcomes."""
        connection, plan = self.connection, self.plan
        owner = plan.owner
        policy = owner["reset"]
        request = reset_request(plan.item, policy)
        execution = self._job_execution(backend, request)
        if execution is not None and not execution["args"]:
            # A job file that cannot name this item cannot reset it; never improvise.
            raise PermissionError("The ECU job file defines no reset identifier for this item")
        self.report["execution"] = (
            f"ECU job {JOB_RESET} {execution['args']} ({execution['job_file']})"
            if execution is not None
            else f"app request ({backend.fallback_source(owner['name'])})"
        )
        try:
            path = self.store.prepare(plan.intent(execution))
        except (OSError, ValueError):
            logger.warning("CBS reset journal preparation failed", exc_info=True)
            self.report["persistence_failed"] = True
            self.report["detail"] = "The local operation record could not be saved; reset not sent"
            return self.report
        self.report["path"] = str(path)
        catalog = DiagnosticCatalog()
        state: dict[str, Any] = {
            "sent": False,
            "accepted": False,
            "step": "",
            "checked": False,
            "dsc_extra": False,
        }
        deadline = time.monotonic() + 30.0

        def record(
            event: str, step: str | None, sent: bytes = b"", reply: bytes = b"", detail: str = ""
        ) -> None:
            self.report["events"].append(
                {"state": event, "step": step, "request": sent.hex(), "response": reply.hex()}
            )
            try:
                self.store.record(path, event, step, sent, reply, detail)
            except (OSError, ValueError):
                self.report["persistence_failed"] = True
                raise

        def exchange(services: Any, ctx: OperationContext, step: str, payload: bytes) -> bytes:
            state["step"] = step
            # specific_send assigns a new request ID only when bytes are transmitted.
            request_id = ctx.request_id
            try:
                return bytes(services.invoke(payload, ctx))
            except ProtocolFailure as exc:
                if exc.kind != FailureKind.NEGATIVE or exc.reconnect:
                    raise
                return bytes(exc.raw)
            finally:
                if step == "reset":
                    state["sent"] = ctx.request_id != request_id

        def find(response: bytes) -> dict[str, Any] | None:
            records = decode_cbs_response(response, owner["version"])
            matches = [rec for rec in records if rec["item"] == plan.item]
            return matches[0] if len(matches) == 1 else None

        def dsc25_plain_allowed(services: Any, ctx: OperationContext, before: bytes) -> bool:
            """DSC_25 CBS_RESET uses the plain write unless SVK and record select its extra path."""
            svk = exchange(services, ctx, "svk", b"\x22\xf1\x01")
            if svk[:3] != b"\x62\xf1\x01" or len(svk) < 0x2C:
                record("changed", "svk", b"\x22\xf1\x01", svk, "Software version unavailable")
                self.report["reset_reason"] = (
                    "DSC software version could not be read; reset not sent"
                )
                return False
            record("read", "svk", b"\x22\xf1\x01", svk)
            state["svk"] = svk
            definition = cbs_definitions()["definitions"][owner["name"]]
            if svk[0x29:0x2C].hex() not in definition["extra_svk"]:
                return True
            # The job reads a fixed record position, not the item ID; require both to agree.
            start = 3 + RECORD * int(definition["record_index"][f"{plan.item:02X}"])
            fixed = before[start : start + RECORD]
            if (
                len(fixed) == RECORD
                and fixed[0] == plan.item
                and int.from_bytes(fixed[1:3], "big", signed=True) > 0
            ):
                return True
            state["dsc_extra"] = True
            if self.dsc_extra_acknowledged and execution is not None:
                return True
            record(
                "blocked",
                "svk",
                b"\x22\xf1\x01",
                svk,
                "This DSC software needs an extra sequence that also clears DSC fault memory",
            )
            self.report["reset_reason"] = (
                "This DSC software version needs an extra reset sequence that also clears all "
                "DSC fault memory; that sequence is not enabled"
            )
            return False

        def check(services: Any, ctx: OperationContext) -> bytes:
            """Exact owner identity and unchanged before-record, in one owner operation."""
            if getattr(services, "session", 1) != 1:
                session = exchange(services, ctx, "session", b"\x10\x01")
                if session[:2] != b"\x50\x01":
                    record(
                        "changed",
                        "session",
                        b"\x10\x01",
                        session,
                        "The source-required default diagnostic session is unavailable",
                    )
                    return b""
                record("accepted", "session", b"\x10\x01", session)
            identity = exchange(services, ctx, "identity", b"\x22\xf1\x50")
            try:
                match = catalog.identify(owner["address"], identity)
            except ValueError:
                match = {}
            if match.get("address_index") != owner["index"] or match.get("name") != owner["name"]:
                record(
                    "changed", "identity", b"\x22\xf1\x50", identity, "Owner ECU identity changed"
                )
                return b""
            software = exchange(services, ctx, "software", b"\x22\xf1\x01")
            if software.hex() != owner["software"]:
                record(
                    "changed",
                    "software",
                    b"\x22\xf1\x01",
                    software,
                    "Owner ECU software changed since service status was read",
                )
                return b""
            before = exchange(services, ctx, "before", b"\x22\x10\x01")
            try:
                current = find(before)
            except ValueError:
                current = None
            if current is None or current["raw"] != plan.before_raw:
                record(
                    "changed",
                    "before",
                    b"\x22\x10\x01",
                    before,
                    "CBS state could not be read or changed since it was shown",
                )
                return b""
            record("accepted", "before", b"\x22\x10\x01", before)
            state["before"] = before
            if policy == "dsc25-plain" and not dsc25_plain_allowed(services, ctx, before):
                return b""
            state["checked"] = True
            return b""

        def reread(services: Any, ctx: OperationContext) -> bytes:
            ctx.cancelled.wait(min(SETTLE_SECONDS, max(0.0, ctx.remaining() - 5.0)))
            after = exchange(services, ctx, "after", b"\x22\x10\x01")
            self.report["after"] = after.hex()
            record("read", "after", b"\x22\x10\x01", after)
            return detail(services, ctx)

        def detail(services: Any, ctx: OperationContext) -> bytes:
            if owner["version"] == "6":
                reasons = exchange(services, ctx, "detail", b"\x22\x10\x02")
                self.report["reset_detail"] = reasons.hex()
                record("read", "detail", b"\x22\x10\x02", reasons)
            return b""

        def execute(services: Any, ctx: OperationContext) -> bytes:
            check(services, ctx)
            if not state["checked"]:
                return b""
            record("sending", "reset", request)
            reply = exchange(services, ctx, "reset", request)
            verdict, reason = check_reset_reply(policy, reply)
            if verdict != "accepted":
                record(verdict, "reset", request, reply, reason)
                self.report["reset_reason"] = reason
                return b""
            state["accepted"] = True
            record("accepted", "reset", request, reply)
            return reread(services, ctx)

        def remaining() -> float:
            left = deadline - time.monotonic()
            if left <= 0:
                raise TimeoutError("Vehicle operation timed out")
            return left

        def execute_dsc_job(services: Any, ctx: OperationContext) -> bytes:
            """Run the source's exact occurrence plan, with durable per-send results."""
            assert execution is not None
            check(services, ctx)
            if not state["checked"]:
                return b""
            sequence = (
                tuple(bytes.fromhex(part) for part in execution["request_sequence"])
                if state["dsc_extra"]
                else (request,)
            )
            self.report["request_sequence"] = [part.hex() for part in sequence]
            if state["dsc_extra"]:
                self.report["side_effects"] = list(execution["side_effects"])
                self.report["instructions"] += (
                    " An interrupted DSC sequence may leave event reporting paused or fault "
                    "memory cleared; inspect the recorded outcomes before another reset."
                )
            position = 0
            active = ""

            def sending(payload: bytes) -> None:
                """Persist the exact next reset-sequence telegram before transmission."""
                nonlocal position, active
                active = f"reset-step-{position + 1}"
                record("sending", active, payload)
                position += 1

            def received(payload: bytes, reply: bytes) -> None:
                """Check source preconditions and classify each reset-sequence response."""
                if payload in (b"\x22\xf1\x01", b"\x22\x10\x01") and position == 0:
                    field = "svk" if payload == b"\x22\xf1\x01" else "before"
                    if reply != state[field]:
                        self.report["reset_reason"] = (
                            "CBS state or software changed before the reset"
                        )
                        record("changed", field, payload, reply, "Source precondition changed")
                        raise ValueError(self.report["reset_reason"])
                if payload not in sequence:
                    return
                state["sent"] = True
                if payload == request:
                    accepted = reply == b"\x6e\x10\x01"
                elif payload[0] == 0x86:
                    accepted = reply[:2] == bytes((0xC6, payload[1]))
                elif payload[0] == 0x31:
                    accepted = reply[:4] == b"\x71\x01\x03\x04"
                else:
                    accepted = reply == b"\x54"
                verdict = "accepted" if accepted else "uncertain"
                if len(reply) == 3 and reply[:2] == bytes((0x7F, payload[0])):
                    verdict = "rejected"
                    if position == 1:
                        self.report["reset_reason"] = (
                            "The ECU rejected the reset before side effects"
                        )
                        record("rejected", "reset", payload, reply, self.report["reset_reason"])
                record(verdict, active, payload, reply)
                if not accepted:
                    raise ValueError("A DSC reset sequence step was rejected or unconfirmed")

            run = backend.run(
                owner["name"],
                owner["address"],
                JOB_RESET,
                execution["args"],
                timeout=remaining(),
                grant=frozenset({0x2E, 0x86, 0x31, 0x14}),
                expected=frozenset(sequence),
                sequence=sequence,
                on_send=sending,
                on_reply=received,
            )
            state["sent"] = state["sent"] or run.sent(request)
            if run.error is not None:
                raise run.error
            if (
                not run.ok
                or position != len(sequence)
                or run.result is None
                or not run.result.mutated
            ):
                raise ValueError("The DSC reset job did not complete its full recorded sequence")
            state["accepted"] = True
            record("accepted", "reset", request, run.reply(request), f"JOB_STATUS {run.status}")
            self._cancelled.wait(min(SETTLE_SECONDS, max(0.0, remaining() - 5.0)))
            after_run = backend.run(owner["name"], owner["address"], JOB_READ, timeout=remaining())
            if after_run.ok:
                after = after_run.response()
                self.report["after"] = after.hex()
                record("read", "after", b"\x22\x10\x01", after, after_run.source)
            elif after_run.interpreter_failed:
                reread(services, ctx)
            else:
                raise after_run.error or ValueError(f"Re-read {after_run.state()}")
            return b""

        def execute_routine_job(services: Any, ctx: OperationContext) -> bytes:
            """CBS6.3/7.0 start/results stay under one exclusive owner operation."""
            assert execution is not None
            check(services, ctx)
            if not state["checked"]:
                return b""
            record("sending", "reset", request, detail=self.report["execution"])
            run = backend.run(
                owner["name"],
                owner["address"],
                JOB_RESET,
                execution["args"],
                timeout=remaining(),
                grant=frozenset({0x31}),
                expected=frozenset({request}),
            )
            state["sent"] = run.sent(request)
            if run.error is not None and not run.write_rejected(request):
                raise run.error
            reply = run.reply(request)
            if len(reply) == 3 and reply[:2] == b"\x7f\x31" and reply[2] != 0x78:
                record("rejected", "reset", request, reply, "The ECU rejected reset start")
                self.report["reset_reason"] = "The ECU rejected reset start"
                return b""
            verdict, reason = (
                check_reset_reply(
                    policy,
                    reply,
                    routine_codes=cbs_definitions()["definitions"][owner["name"]]["routine_codes"],
                    routine_start=True,
                )
                if policy == "routine-6.3"
                else ("accepted", "")
                if reply == b"\x71\x01\x10\x00"
                else ("uncertain", "Reset start was not confirmed")
            )
            if verdict == "accepted" and (
                not run.ok or run.result is None or not run.result.mutated
            ):
                verdict, reason = "uncertain", "The CBS start job did not complete successfully"
            if verdict != "accepted":
                record(verdict, "reset", request, reply, reason)
                self.report["reset_reason"] = reason
                return b""
            record("accepted", "reset-start", request, reply, "Routine started; results pending")
            delay = execution["results_delay_ms"] / 1000.0
            if delay:
                if remaining() <= delay:
                    raise TimeoutError("CBS result delay exceeds the remaining operation budget")
                if self._cancelled.wait(delay):
                    raise InterruptedError("CBS reset interrupted before its result query")
            result_request = bytes.fromhex(execution["results_request"])
            record("sending", "reset-results", result_request)
            results = backend.run(
                owner["name"],
                owner["address"],
                JOB_RESET,
                execution["results_args"],
                timeout=remaining(),
                grant=frozenset({0x31}),
                expected=frozenset({result_request}),
            )
            if results.error is not None and not results.write_rejected(result_request):
                raise results.error
            reply = results.reply(result_request)
            verdict, reason = check_reset_reply(
                policy,
                reply,
                routine_codes=cbs_definitions()["definitions"][owner["name"]]["routine_codes"],
            )
            if verdict == "accepted" and not results.ok:
                verdict, reason = "uncertain", "The CBS results job did not complete successfully"
            state["accepted"] = verdict == "accepted"
            record(verdict, "reset", result_request, reply, reason)
            self.report["reset_reason"] = reason
            if verdict != "accepted":
                return b""
            self._cancelled.wait(min(SETTLE_SECONDS, max(0.0, remaining() - 5.0)))
            after_run = backend.run(
                owner["name"],
                owner["address"],
                owner.get("read_job", JOB_READ),
                timeout=remaining(),
            )
            if after_run.ok:
                after = after_run.response()
                self.report["after"] = after.hex()
                record("read", "after", b"\x22\x10\x01", after, after_run.source)
            elif after_run.interpreter_failed:
                reread(services, ctx)
            else:
                raise after_run.error or ValueError(f"Re-read {after_run.state()}")
            return b""

        def execute_job(services: Any, ctx: OperationContext) -> bytes:
            assert execution is not None
            check(services, ctx)
            if not state["checked"]:
                return b""
            record("sending", "reset", request, detail=self.report["execution"])
            run = backend.run(
                owner["name"],
                owner["address"],
                JOB_RESET,
                execution["args"],
                timeout=remaining(),
                grant=frozenset({0x2E}),
                expected=frozenset({request}),
            )
            state["sent"] = run.sent(request)
            rejected_once = run.write_rejected(request)
            if run.error is not None and not rejected_once:
                raise run.error
            reply = run.reply(request)
            verdict, reason = (
                check_reset_reply(policy, reply)
                if reply
                else ("uncertain", "The reset job sent no reset request")
            )
            if verdict == "accepted" and (
                run.result is None or run.status != "OKAY" or not run.result.mutated
            ):
                verdict = "uncertain"
                reason = (
                    f"The ECU accepted the reset but the job reported {run.status or 'no'} status"
                )
            job_detail = f"JOB_STATUS {run.status or '-'}"
            if verdict != "accepted":
                record(verdict, "reset", request, reply, f"{reason}; {job_detail}")
                self.report["reset_reason"] = reason
                return b""
            state["accepted"] = True
            record("accepted", "reset", request, reply, job_detail)
            self._cancelled.wait(min(SETTLE_SECONDS, max(0.0, remaining() - 5.0)))
            after_run = backend.run(owner["name"], owner["address"], JOB_READ, timeout=remaining())
            if after_run.ok:
                after = after_run.response()
                self.report["after"] = after.hex()
                record("read", "after", b"\x22\x10\x01", after, after_run.source)
                detail(services, ctx)
            elif after_run.interpreter_failed:
                reread(services, ctx)
            else:
                raise after_run.error or ValueError(f"Re-read {after_run.state()}")
            return b""

        failure = ""
        try:
            if execution is not None and execution["path"] == "job-dsc25":
                connection.run_operation(
                    owner["address"],
                    execute_dsc_job,
                    context=connection.context(remaining()),
                )
            elif policy in ("routine-6.3", "routine-7.0"):
                connection.run_operation(
                    owner["address"],
                    execute_routine_job,
                    context=connection.context(remaining()),
                )
            elif execution is not None:
                connection.run_operation(
                    owner["address"], execute_job, context=connection.context(remaining())
                )
            else:
                connection.run_operation(
                    owner["address"], execute, context=connection.context(remaining())
                )
        except Exception as exc:
            failure = str(exc) or type(exc).__name__
            logger.warning("CBS reset stopped for %s", owner["name"], exc_info=True)
            if self.report["persistence_failed"]:
                # Journal loss after intent: stop the connection rather than continue blind.
                connection.request_close()
            elif state["sent"] and not state["accepted"]:
                with contextlib.suppress(OSError, ValueError):
                    record("uncertain", "reset", request, detail=failure)
        self.report["state"], self.report["detail"] = self._outcome(state, failure)
        if not self.report["persistence_failed"]:
            try:
                self.store.record(path, self.report["state"], None, detail=self.report["detail"])
            except (OSError, ValueError):
                self.report["persistence_failed"] = True
        return self.report

    def _outcome(self, state: dict[str, Any], failure: str) -> tuple[str, str]:
        """Classify reset completion from observed sends, responses and rereads."""
        events = {(e["step"], e["state"]) for e in self.report["events"]}
        if ("reset", "rejected") in events:
            return "rejected", self.report.get("reset_reason") or "The ECU rejected the reset"
        if ("svk", "blocked") in events or ("svk", "changed") in events:
            return "not-started", self.report["reset_reason"]
        if not state["sent"]:
            if ("session", "changed") in events:
                return "not-started", "Default diagnostic session unavailable; reset not sent"
            if any((step, "changed") in events for step in ("identity", "software", "before")):
                return "not-started", "Service status changed; read it again before resetting"
            return "not-started", "Reset was not sent" + (
                "; check the connection and session log" if failure else ""
            )
        if not state["accepted"]:
            return "uncertain", "Reset outcome is uncertain; reconnect and read service status"
        after = self.report["after"]
        if after:
            try:
                records = decode_cbs_response(bytes.fromhex(after), self.plan.owner["version"])
                before = decode_record(
                    bytes.fromhex(self.plan.before_raw), self.plan.owner["version"]
                )
            except ValueError:
                records, before = [], {}
            match = [rec for rec in records if rec["item"] == self.plan.item]
            if len(match) == 1 and match[0]["availability"] == 100:
                limit = 250 if self.plan.owner["version"] in ("6.3", "7.0") else 30
                saturated = before.get("count") is not None and before["count"] >= limit
                if saturated:
                    before["count"] = None  # no source wrap rule; require an observed change
                if before.get("count") is not None and match[0]["count"] == before["count"] + 1:
                    return "verified", "Reset accepted; the re-read shows 100 % and the next count"
                if before.get("count") is None and match[0]["raw"] != self.plan.before_raw:
                    return (
                        "verified",
                        "Reset accepted; the re-read shows 100 % and a changed record",
                    )
            reason = self._detail_reason()
            return (
                "response-confirmed",
                "Reset accepted by the ECU, but the re-read does not show the new state yet"
                + (f" (ECU reports: {reason})" if reason else "")
                + " — read service status again later",
            )
        return (
            "response-confirmed",
            "Reset accepted by the ECU; no re-read was obtained — reconnect and read "
            "service status",
        )

    def _detail_reason(self) -> str:
        """Decode the v6 per-item reset reason (3-byte records), if one was read."""
        raw = bytes.fromhex(self.report.get("reset_detail", ""))
        if raw[:3] != b"\x62\x10\x02" or (len(raw) - 3) % 3:
            return ""
        for offset in range(3, len(raw), 3):
            if raw[offset] == self.plan.item:
                code = raw[offset + 1]
                if 0x80 <= code <= 0xBF:
                    return f"sensor-specific reason 0x{code:02X}"
                return DETAIL_REASONS.get(code, f"reason 0x{code:02X}")
        return ""
