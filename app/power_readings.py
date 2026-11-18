"""Exact low-voltage battery and ignition observations over the existing job owner."""

import json
import logging
import math
import time
from typing import Any

from app.ediabas import JobError
from app.ista_jobs import JobBackend, JobRun
from app.protocol.contracts import OperationCancelled, TransportKind
from app.resources import resource_path

logger = logging.getLogger(__name__)
METRICS = ("soc", "soh", "kl15")


def reader_profiles() -> dict[str, Any]:
    """Load bounded standalone reader contracts; source folders are never consulted."""
    with resource_path("coding_data/power_readers.json").open("rb") as stream:
        raw = stream.read(524289)
    if len(raw) > 524288:
        raise ValueError("Power reader definitions exceed their supported size")
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise ValueError("Unsupported power reader format")
    profiles = data.get("profiles")
    if not isinstance(profiles, dict):
        raise ValueError("Power reader profiles are unavailable")
    for name, profile in profiles.items():
        if (
            not isinstance(name, str)
            or not isinstance(profile, dict)
            or not isinstance(profile.get("selectors"), list)
            or not isinstance(profile.get("job_sha256"), str)
            or len(profile["job_sha256"]) != 64
            or not isinstance(profile.get("readers"), list)
        ):
            raise ValueError("Invalid power reader identity")
        for reader in profile["readers"]:
            if (
                not isinstance(reader, dict)
                or reader.get("job") not in {"STATUS_LESEN", "STATUS_SYSTEMCHECK_AEP_INFO_2"}
                or not isinstance(reader.get("args"), str)
                or not isinstance(reader.get("response_size"), int)
                or not 4 <= reader["response_size"] <= 256
                or not isinstance(reader.get("request"), str)
                or len(reader["request"]) != 6
                or not reader["request"].startswith("22")
                or not isinstance(reader.get("values"), dict)
                or not reader["values"]
                or not set(reader["values"]).issubset(METRICS)
            ):
                raise ValueError("Invalid power reader request")
            if len(bytes.fromhex(reader["request"])) != 3:
                raise ValueError("Invalid power reader identifier")
            for metric, field in reader["values"].items():
                if not isinstance(field, dict) or not isinstance(field.get("result"), str):
                    raise ValueError("Invalid power result definition")
                if metric == "kl15":
                    if not isinstance(reader.get("states"), dict) or any(
                        not isinstance(key, str) or not isinstance(value, str)
                        for key, value in reader["states"].items()
                    ):
                        raise ValueError("Invalid terminal state definitions")
                elif field.get("quality") is not None and not isinstance(field["quality"], str):
                    raise ValueError("Invalid power quality definition")
    return profiles


def _percentage(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and 0 <= value <= 100
    )


def decode_reading(run: JobRun, reader: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Require exact complete replies and native results, retaining invalid raw values."""
    request = bytes.fromhex(reader["request"])
    reply = run.reply(request)
    if (
        not run.ok
        or run.result is None
        or run.exchanges != [(request, reply)]
        or len(reply) != reader["response_size"]
        or reply[:3] != b"\x62" + request[1:]
    ):
        raise ValueError("Power reader did not return a complete matching result")
    output = {}
    for metric, field in reader["values"].items():
        matches = [row for row in run.result.sets if field["result"] in row]
        if len(matches) != 1:
            raise ValueError("Power reader returned missing or ambiguous values")
        values = matches[0]
        raw = values[field["result"]]
        observation: dict[str, Any] = {
            "value": None,
            "state": "unavailable",
            "detail": "ECU reported an unavailable value",
            "raw_value": raw,
            "response": reply.hex(),
            "quality": None,
        }
        if metric == "kl15":
            state = reader["states"].get(str(reply[3]))
            observation["raw_value"] = reply[3]
            if isinstance(raw, str) and state is not None:
                status = (
                    "read"
                    if reply[3] in (2, 4, 6, 8, 10, 13)
                    else "transition"
                    if reply[3] in (3, 5, 7, 9, 11, 12)
                    else "unavailable"
                )
                observation.update(
                    value=state, state=status, detail="Observed terminal state", raw_state=raw
                )
            output[metric] = observation
            continue
        unit = field["result"].removesuffix("_WERT") + "_EINH"
        if values.get(unit) != "%":
            raise ValueError("Power reader did not confirm a percentage unit")
        quality_field = field.get("quality")
        quality = values.get(quality_field) if quality_field else None
        observation["raw_quality"] = quality
        plausibility = values.get("STAT_PLAUSIBILITAET_LADEZUSTAND_AKTUELL")
        if plausibility is not None:
            observation["plausibility_code"] = plausibility
        # Quality is a reported percentage, not a pass/fail threshold. Retain 0
        # as 0; missing/out-of-range qualifiers never imply a reliable value.
        if quality_field and not _percentage(quality):
            observation["detail"] = "ECU reported unavailable quality"
        elif _percentage(raw):
            observation.update(
                value=raw,
                state="read",
                quality=quality,
                detail=(
                    "Reported quality is shown separately; no acceptance threshold is established"
                    if quality_field
                    else "Quality is not reported by this reader"
                ),
            )
        output[metric] = observation
    return output


def read_power_status(connection: Any, ecus: list[dict[str, Any]]) -> dict[str, Any]:
    """Read every applicable exact variant within one shared 30-second operation budget.

    Independent sources remain separate observations. Definite failures retain
    earlier results; cancellation, stream loss and budget exhaustion stop new I/O.
    These observations do not grant vehicle-write or power-readiness authority.
    """
    report: dict[str, Any] = {metric: [] for metric in METRICS}
    report["detail"] = "No exact supported reader in the identified ECU inventory"
    if getattr(connection, "kind", None) != TransportKind.HSFZ:
        report["detail"] = "Power readers need a recovered logical-address mapping"
        return report
    profiles = reader_profiles()
    deadline = time.monotonic() + 30.0
    stopped = False
    backend = JobBackend(connection)
    try:
        for ecu in ecus:
            name = ecu.get("name")
            if not isinstance(name, str):
                continue
            profile = profiles.get(name)
            if ecu.get("identified") is not True or profile is None:
                continue
            # A matching name alone is insufficient: keep the exact address/index
            # and generated native decoder identity bound to each observation.
            if ecu.get("address_index") not in profile["selectors"]:
                continue
            address = int(ecu["addr"], 16)
            if ecu["address_index"] != f"{address:02X} {ecu.get('variant')}":
                continue
            try:
                matching = backend.file_sha256(name) == profile["job_sha256"]
            except (JobError, OSError, ValueError):
                logger.warning("Power reader job unavailable %s", name, exc_info=True)
                matching = False
            for reader in profile["readers"]:
                remaining = deadline - time.monotonic()
                decoded = {}
                reason = "Exact verified job data unavailable"
                if stopped or not connection.alive_ok or remaining <= 0:
                    stopped = True
                    reason = "Not read — connection, cancellation or operation budget ended"
                elif matching:
                    try:
                        run = backend.run(
                            name, address, reader["job"], reader["args"], timeout=remaining
                        )
                        if run.error is not None:
                            logger.warning(
                                "Power reader failed %s/%s: %s", name, reader["job"], run.error
                            )
                        reason = "Read unavailable — check the session log"
                        stopped = (
                            isinstance(run.error, OperationCancelled) or run.state() == "cancelled"
                        )
                        decoded = decode_reading(run, reader)
                    except (JobError, OSError, ValueError):
                        logger.warning(
                            "Power result unavailable %s/%s", name, reader["job"], exc_info=True
                        )
                for metric in reader["values"]:
                    observation = decoded.get(
                        metric,
                        {
                            "value": None,
                            "quality": None,
                            "state": "unavailable",
                            "detail": reason,
                        },
                    )
                    observation.update(
                        source=f"{name} ({address:02X})",
                        address_index=ecu["address_index"],
                        job_sha256=profile["job_sha256"],
                    )
                    report[metric].append(observation)
        return report
    finally:
        backend.close()
