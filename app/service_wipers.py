"""Guide the owner through the vehicle's stalk procedure and independently read blade position."""

import json
from functools import lru_cache
from typing import Any

from app.resources import resource_path
from app.service_functions import ServiceAction, ServiceCard, ServiceContext, ServiceResult

_PREPARE = (
    "Park securely, apply the parking brake and stop the engine. Close the hood. "
    "Start with both blades fitted, resting on the glass, free of ice and clear of obstructions."
)
_LOWER = (
    "Fit both blades securely and lower both arms onto the glass before switching power on "
    "or touching the stalk."
)


def _instructions(guide: str) -> tuple[str, str]:
    if guide == "accessory":
        return (
            "Switch accessory power (terminal R) on, then immediately off. Hold the wiper stalk "
            "up for about 3 seconds, until both arms stop nearly upright. Release the stalk.",
            "Switch accessory power on and give the stalk one flick wipe. Wait for both blades "
            "to stop at the bottom of the windshield.",
        )
    direction = {"standby_down": "down", "standby_up": "up"}[guide]
    return (
        "Put the vehicle in operating readiness with the engine off. Hold the wiper stalk "
        f"{direction} until both arms stop upright, then release it.",
        f"With operating readiness on, hold the wiper stalk {direction} again. Wait for both "
        "blades to stop at the bottom of the windshield.",
    )


@lru_cache(maxsize=1)
def _definitions() -> dict[str, Any]:
    with resource_path("coding_data/service_wipers.json").open("rb") as stream:
        raw = stream.read(512 * 1024 + 1)
    if len(raw) > 512 * 1024:
        raise ValueError("Wiper definitions exceed their size limit")
    data = json.loads(raw)
    if data.get("schema") != 1:
        raise ValueError("Unsupported wiper definitions")
    return dict(data)


def _source(context: ServiceContext) -> tuple[str, dict, dict] | None:
    profiles = _definitions()["profiles"]
    matches = []
    for name in {
        e["name"] for e in context.ecus if e.get("identified") and e.get("name") in profiles
    }:
        profile = profiles[name]
        target = context.target(name, profile["sha256"])
        if target is not None and target["address_index"] in profile["selectors"]:
            matches.append((name, target, profile))
    return matches[0] if len(matches) == 1 else None


def _position(
    context: ServiceContext, source: tuple[str, dict, dict] | None
) -> tuple[str, tuple[str, ...]]:
    if source is None:
        return "unknown", ("ECU blade position unavailable for the identified equipment.",)
    name, target, profile = source
    values: dict[str, int] = {}
    lines = []
    for key, reader in profile["readers"].items():
        try:
            fields, data = context.read_fields(
                name,
                target["address"],
                reader["job"],
                reader["args"],
                bytes.fromhex(reader["request"]),
                1,
            )
            raw = data[0]
            if raw not in (0, 1) or fields.get(reader["field"]) != reader["values"][raw]:
                raise ValueError("Invalid ECU position")
            values[key] = raw
        except (ConnectionError, TimeoutError):
            if not values:
                raise
            lines.append("Connection interrupted before both ECU contacts could be read.")
            break
        except ValueError:
            lines.append(
                f"{'Service position' if key == 'service' else 'Park contact'} unavailable."
            )
    if "park_contact" in values:
        parked = values["park_contact"] == 0
        return ("park" if parked else "outside"), (
            "ECU reports the blades are parked."
            if parked
            else "ECU reports the blades are outside park. Check the upright position visually.",
        )
    statuses = {"park": "Park contact", "service": "Service position"}
    for key, value in values.items():
        lines.append(f"ECU {statuses[key].lower()} · {'Active' if value else 'Inactive'}")
    state = "partial" if values else "unknown"
    if "service" in values and "park" in values:
        pair = (values["service"], values["park"])
        if pair == (1, 0):
            state = "service"
        elif pair == (0, 1):
            state = "park"
        elif pair == (1, 1):
            lines.append("The two ECU indications disagree.")
        else:
            state = "neither"
            lines.append("The ECU reports neither end position.")
    return state, tuple(lines)


def _simulated(context: ServiceContext, source: tuple[str, dict, dict] | None) -> bool:
    return (
        context.synthetic_outputs
        and source is not None
        and source[0] == "BDC"
        and callable(context.connection.demo_wiper_stalk)
    )


def discover(context: ServiceContext) -> list[ServiceCard]:
    """Match the complete repair instruction to the current vehicle type and series."""
    definitions = _definitions()
    model = f"{context.order.get('model_range', '')} {context.order.get('type_code', '')}"
    documents = definitions["models"].get(model)
    if not documents:
        return []
    guide = definitions["documents"][str(documents[0])]["guide"]
    enter, park = _instructions(guide)
    source = _source(context)
    readings = _position(context, source)[1] if context.previous is None else ()
    demo = _simulated(context, source)
    actions = (
        ServiceAction("read", "Read blade position"),
        ServiceAction(
            "enter",
            "Simulate stalk to service position" if demo else "Check service position",
            ("The vehicle is parked. Both blades rest on the glass and the sweep area is clear.",)
            if demo
            else ("I followed the entry steps and checked where both blades stopped.",),
        ),
        ServiceAction(
            "park",
            "Simulate stalk to park" if demo else "Check parked position",
            ("Both wiper arms are lowered onto the glass with their blades fitted.",),
        ),
    )
    return [
        ServiceCard(
            f"wipers.service.{model.replace(' ', '.')}.{'.'.join(map(str, documents))}."
            f"{source[0] if source else 'manual'}",
            "Wiper service position",
            "Visibility",
            f"Front wiper arms · {source[0]}" if source else "Front wiper arms",
            "Use the wiper stalk to raise the blades for service and return them to park.",
            actions,
            (_PREPARE, "Enter · " + enter, "Return · " + _LOWER + " " + park, *readings),
            readings_label="Stalk procedure and ECU readings at last availability check",
        )
    ]


def execute(context: ServiceContext, card: ServiceCard, action: ServiceAction) -> ServiceResult:
    """Read the ECU contacts after manual operation or an explicitly simulated stalk input."""
    source = _source(context)
    simulated = _simulated(context, source)
    if action.key in ("enter", "park") and simulated:
        context.connection.demo_wiper_stalk(action.key == "enter")
    state, lines = _position(context, source)
    if action.key == "read":
        return ServiceResult(
            {"unknown": "Unavailable", "partial": "Partial"}.get(state, "Read"), lines
        )
    if action.key not in ("enter", "park"):
        return ServiceResult("Unavailable", ("Unknown wiper action.",))
    expected = "service" if action.key == "enter" else "park"
    if simulated:
        lines = ("Bundled DEMO stalk operated.", *lines)
    if state == expected:
        return ServiceResult("ECU position confirmed", lines)
    if expected == "service" and state == "outside":
        return ServiceResult("Visual check required", lines)
    return ServiceResult(
        "Position unconfirmed", (*lines, "Check the blades directly before proceeding.")
    )


def demo_reads(name: str) -> dict[str, str]:
    """Set the synthetic body controller's initial position to visibly parked."""
    return {"D355": "01", "D363": "00"} if name == "BDC" else {}


def set_demo_position(ecu: dict, service: bool) -> None:
    """Apply a local synthetic stalk input while the virtual vehicle lock is held."""
    if ecu["name"] != "BDC" or not {"D355", "D363"} <= ecu["reads"].keys():
        raise ValueError("The synthetic wiper stalk has no matching body controller")
    ecu["reads"].update({"D355": "00", "D363": "01"} if service else demo_reads("BDC"))
