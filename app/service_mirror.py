"""Fitted electrochromic interior-mirror test and ECU-reported dimming readback."""

import json
import time
from functools import lru_cache
from typing import Any

from app.protocol.contracts import OperationCancelled, ProtocolFailure
from app.resources import resource_path
from app.service_functions import (
    ServiceAction,
    ServiceCard,
    ServiceContext,
    ServiceResult,
    rejected_before_execution,
)


@lru_cache(maxsize=1)
def mirror_profiles() -> dict[str, Any]:
    """Read the standalone, versioned mirror contracts."""
    with resource_path("coding_data/service_mirror.json").open("rb") as stream:
        raw = stream.read(16_385)
    if len(raw) > 16_384:
        raise ValueError("Interior mirror definitions exceed the size limit")
    data = json.loads(raw)
    if (
        not isinstance(data, dict)
        or data.get("schema") != 1
        or not isinstance(data.get("profiles"), dict)
    ):
        raise ValueError("Invalid interior mirror definitions")
    profiles = dict(data["profiles"])
    try:
        for p in profiles.values():
            seconds = p["seconds"]
            if (
                type(seconds) is not int
                or not 0 < seconds <= 10
                or len(bytes.fromhex(p["sha256"])) != 32
                or not 0 <= p["source"]["address"] <= 65535
                or p["start"]
                != {
                    "job": "STEUERN",
                    "args": f"ARG;EC_SPIEGEL_ABBLENDEN;{seconds}",
                    "request": f"2ed32f{seconds:02x}",
                    "reply": "6ed32f",
                }
            ):
                raise ValueError("Invalid timed mirror activation")
            for key, request, args in (
                ("present", "22d330", "ARG;EC_SPIEGEL_VORHANDEN"),
                ("state", "22d32f", "ARG;EC_SPIEGEL_ABBLENDEN"),
            ):
                r = p[key]
                if (r["request"], r["args"], r["job"]) != (request, args, "STATUS_LESEN") or (
                    not isinstance(r["field"], str)
                ):
                    raise ValueError("Invalid mirror reading")
    except (KeyError, TypeError) as exc:
        raise ValueError("Incomplete interior mirror definitions") from exc
    return profiles


def _reading(context: ServiceContext, name: str, profile: dict, key: str) -> int:
    spec = profile[key]
    fields, payload = context.read_fields(
        name,
        profile["source"]["address"],
        spec["job"],
        spec["args"],
        bytes.fromhex(spec["request"]),
        1,
    )
    value = fields.get(spec["field"])
    if value != payload[0] or value > (1 if key == "present" else 100):
        raise ValueError("Invalid interior mirror reading")
    return int(value)


def _idle(context: ServiceContext, name: str, profile: dict) -> bool:
    return _reading(context, name, profile, "present") == 1 and (
        _reading(context, name, profile, "state") == 0
    )


def discover(context: ServiceContext) -> list[ServiceCard]:
    """Offer the timed test only for a freshly identified ECU and a fitted, undimmed mirror."""
    cards: list[ServiceCard] = []
    if not context.component_controls:
        return cards
    for name, profile in mirror_profiles().items():
        target = context.target(name, profile["sha256"])
        if target is None or target["address"] != profile["source"]["address"]:
            continue
        try:
            idle = _idle(context, name, profile)
        except ValueError:
            continue
        if idle:
            seconds = profile["seconds"]
            cards.append(
                ServiceCard(
                    f"mirror/{name}",
                    "Interior mirror dimming",
                    "Visibility",
                    name,
                    f"Command full darkening for {seconds} seconds. The ECU releases the test "
                    "when its timer expires.",
                    (ServiceAction("dim", "Dim mirror", temporary=True),),
                    ("Mirror fitted. ECU reports 0% dimming.",),
                    "Mirror observation",
                )
            )
    return cards


def execute(context: ServiceContext, card: ServiceCard, action: ServiceAction) -> ServiceResult:
    """Send the reviewed timed command once and verify active and released ECU readings."""
    if not context.component_controls:
        return ServiceResult("Unavailable", ("This session has no controllable mirror.",))
    name = card.component
    profile = mirror_profiles()[name]
    seconds = profile["seconds"]
    if action.key != "dim" or not _idle(context, name, profile):
        return ServiceResult("Blocked", ("Mirror fitment or initial dimming changed.",))
    if context.ctx.remaining() < seconds + 2:
        return ServiceResult("Unavailable", ("Insufficient time to observe dimming and release.",))
    spec = profile["start"]
    request = bytes.fromhex(spec["request"])
    lines: list[str] = []

    def report(line: str) -> None:
        lines.append(line)
        context.progress(line)

    try:
        run = context.backend.run(
            name,
            profile["source"]["address"],
            spec["job"],
            spec["args"],
            deadline=context.ctx.deadline,
            cancelled=context.ctx.cancelled,
            grant=frozenset({request[0]}),
            expected=frozenset({request}),
            sequence=(request,),
        )
        raw = run.reply(request)
        if run.exchanges == [(request, raw)] and rejected_before_execution(request, raw):
            return ServiceResult(
                "Rejected", (f"{name} rejected mirror dimming (NRC 0x{raw[2]:02X}).",)
            )
        confirmed = (
            run.ok
            and run.result is not None
            and len(run.result.sets) == 1
            and run.exchanges == [(request, bytes.fromhex(spec["reply"]))]
        )
    except (OSError, ProtocolFailure):
        confirmed = False
    if not confirmed:
        report("The ECU did not confirm the dimming command. It will not be repeated.")
    # The expiry is encoded in the ECU command. This wait only schedules the final read.
    check_at = time.monotonic() + seconds
    try:
        if _reading(context, name, profile, "state") == 100:
            report("ECU reports 100% dimming.")
            context.observe("Interior mirror at full dimming")
        else:
            confirmed = False
            report("The ECU did not report full dimming.")
    except (OSError, ValueError, OperationCancelled):
        confirmed = False
        report("Active dimming readback was unavailable.")
    try:
        while (left := check_at - time.monotonic()) > 0:
            if not context.connection.alive_ok or context.ctx.remaining() <= 0.1:
                raise ConnectionError("Cannot observe mirror release")
            time.sleep(min(left, 0.1))
        final = _reading(context, name, profile, "state")
    except (OSError, ValueError, OperationCancelled):
        report("Mirror release could not be verified. Check the mirror before driving.")
        return ServiceResult("Uncertain", tuple(lines))
    report(f"After the ECU timer, dimming reads {final}%.")
    if final != 0 or not confirmed:
        return ServiceResult("Uncertain", tuple(lines))
    return ServiceResult("Completed", tuple(lines))
