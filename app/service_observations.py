"""Five read-only service functions backed by identified native component jobs."""

import json
from functools import lru_cache
from typing import Any

from app.resources import resource_path
from app.service_functions import ServiceAction, ServiceCard, ServiceContext, ServiceResult

_GROUPS = {
    "washer": ("Washer fluid", "Visibility", "Read the reservoir switch and its voltage."),
    "brake": ("Brake-fluid switch", "Chassis", "Read the brake-fluid level switch."),
    "climate": (
        "Climate temperatures",
        "Cabin",
        "Read the calculated cabin temperature and evaporator sensor temperature.",
    ),
    "radio": (
        "Radio reception",
        "Cabin",
        "Read the tuned frequency, signal quality and field strength.",
    ),
    "wake": (
        "Last battery sensor wake-up",
        "Power",
        "Read the last wake-up reason the body controller stored for the intelligent battery sensor.",
    ),
}


@lru_cache(maxsize=1)
def _profiles() -> dict[str, Any]:
    with resource_path("coding_data/service_observations.json").open("rb") as stream:
        raw = stream.read(131073)
    if len(raw) > 131072:
        raise ValueError("Component reader catalog too large")
    catalog = json.loads(raw)
    if not isinstance(catalog, dict) or catalog.get("schema") != 1:
        raise ValueError("Invalid component reader catalog")
    profiles = catalog.get("profiles")
    if not isinstance(profiles, dict):
        raise ValueError("Invalid component reader definitions")
    return profiles


def _target(context: ServiceContext, name: str, profile: dict) -> dict | None:
    ecu = context.target(name, profile["sha256"])
    if ecu is None or ecu["address_index"] not in profile["selectors"]:
        return None
    return ecu


def discover(context: ServiceContext) -> list[ServiceCard]:
    """Offer only the reader groups belonging to freshly identified components."""
    cards = []
    profiles = _profiles()
    for name in dict.fromkeys(ecu.get("name", "") for ecu in context.ecus):
        profile = profiles.get(name)
        if not profile or _target(context, name, profile) is None:
            continue
        for group in sorted({row["group"] for row in profile["readers"].values()}):
            title, category, description = _GROUPS[group]
            cards.append(
                ServiceCard(
                    f"read/{name}/{group}",
                    title,
                    category,
                    name,
                    description,
                    (ServiceAction("read", "Read"),),
                )
            )
    return cards


def _number(value: object, unit: str, low: int, high: int) -> str | None:
    if isinstance(value, (int, float)) and low <= value <= high:
        return f"{value:g} {unit}"
    return None


def _values(argument: str, fields: dict, raw: bytes) -> tuple[tuple[str, str | None], ...]:
    if argument == "WASCHWASSERSTAND":
        state = {0: "Low", 1: "Sufficient"}.get(raw[0])
        voltage = _number(fields.get("STAT_WASCHWASSERSTAND_WERT"), "mV", 0, 65534)
        return ("Reservoir level", state), ("Sensor voltage", voltage)
    if argument == "BREMSFLUESSIGKEITSSCHALTER":
        return (("Switch", {0: "Low fluid or open circuit", 1: "Fluid present"}.get(raw[0])),)
    if argument == "STATUS_ANT_QFS":
        return (
            ("Tuned frequency", _number(fields.get("STAT_FREQUENZ_WERT"), "kHz", 150, 108000)),
            ("Signal quality", _number(fields.get("STAT_QUALITY_WERT"), "/ 15", 0, 15)),
            ("Field strength", _number(fields.get("STAT_FIELDSTRENGTH_EXACT_WERT"), "dBµV", 0, 60)),
        )
    if argument == "TEMP_INNEN_UNBELUEFTET":
        return (("Cabin", _number(fields.get("STAT_TEMP_INNEN_WERT"), "°C", -128, 127)),)
    if argument == "TEMP_VERDAMPFER_WERT":
        return (("Evaporator", _number(fields.get("STAT_TEMP_VERDAMPFER_WERT"), "°C", -128, 126)),)
    if argument == "IBS_WAKEUP_GRUND":
        reason = {
            1: "Starting capability threshold 1 reached",
            2: "Starting capability threshold 2 reached",
            3: "Parked-current limit exceeded",
            4: "Recharging function",
        }.get(raw[0])
        return (("Last recorded wake-up", reason),)
    raise ValueError("Unrecognized component observation")


def execute(context: ServiceContext, card: ServiceCard, action: ServiceAction) -> ServiceResult:
    """Read each applicable channel once and preserve fields received before a failure."""
    _, name, group = card.key.split("/")
    profile = _profiles()[name]
    ecu = _target(context, name, profile)
    if ecu is None or action.key != "read":
        return ServiceResult("Unavailable", ("Component identity changed.",))
    lines: list[str] = []
    complete = True
    obtained = False
    for argument, row in profile["readers"].items():
        if row["group"] != group:
            continue
        context.progress(f"Reading {card.title.lower()}…")
        try:
            fields, raw = context.read_fields(
                name,
                ecu["address"],
                row["job"],
                row["args"],
                bytes.fromhex(row["request"]),
                row["size"],
            )
            for label, value in _values(argument, fields, raw):
                lines.append(f"{label} · {value or 'Unavailable'}")
                obtained |= value is not None
                complete &= value is not None
        except (TimeoutError, ConnectionError):
            lines.append("Connection lost or timed out. The read stopped.")
            complete = False
            break
        except ValueError:
            label = {
                "TEMP_INNEN_UNBELUEFTET": "Cabin",
                "TEMP_VERDAMPFER_WERT": "Evaporator",
            }.get(argument, card.title)
            lines.append(f"{label} · Reading unavailable")
            complete = False
    state = "Read" if complete and obtained else "Partial" if obtained else "Unavailable"
    return ServiceResult(state, tuple(lines))
