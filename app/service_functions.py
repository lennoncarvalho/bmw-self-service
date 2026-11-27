"""Vehicle-scoped service discovery and reviewed execution on the held protocol owner."""

import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from functools import cached_property, lru_cache
from typing import Any, Protocol

from PySide6.QtCore import Signal

from app.history_files import valid_vin
from app.history_write import validate_software
from app.ista_jobs import JobBackend
from app.power_readings import reader_profiles
from app.protocol.contracts import (
    ENET_HEADUNIT_READ_TIMING,
    OperationContext,
    ProtocolFailure,
    TransportKind,
    WriteConditionsBlocked,
)
from app.resources import resource_path
from app.session import environment
from app.uds import UdsServices
from app.vehicle import DiagnosticCatalog, check_write_conditions, read_engine_data
from app.vehicle_order import decode_vehicle_order
from app.worker import CarWorker

logger = logging.getLogger(__name__)


def rejected_before_execution(request: bytes, reply: bytes) -> bool:
    """Recognize correlated rejections of service, parameters, access or preconditions."""
    return (
        len(reply) == 3
        and reply[:2] == b"\x7f" + request[:1]
        and reply[2] in {0x11, 0x12, 0x13, 0x22, 0x31, 0x33}
    )


@dataclass(frozen=True)
class ServiceAction:
    """One allowed operator intent with its required acknowledgements."""

    key: str
    label: str
    requirements: tuple[str, ...] = ()
    temporary: bool = False

    @property
    def confirmations(self) -> tuple[str, ...]:
        """Include common readiness conditions for every vehicle mutation."""
        if not self.temporary:
            return self.requirements
        return (
            "The vehicle is safely parked and secured. Ignition is on, the engine is off, and power is stable.",
            *self.requirements,
        )


@dataclass(frozen=True)
class ServiceCard:
    """One function supported by the identified vehicle and source definition."""

    key: str
    title: str
    category: str
    component: str
    description: str
    actions: tuple[ServiceAction, ...]
    readings: tuple[str, ...] = ()
    observation: str = ""
    readings_label: str = "At the last availability check"


@dataclass(frozen=True)
class ServiceResult:
    """Diagnostic outcome and individual observations, including partial results."""

    state: str
    lines: tuple[str, ...]


@dataclass
class ServiceListing:
    """Bind each reviewed function to its resolver, vehicle and observed definitions."""

    generation: str
    vin: str
    cards: dict[str, tuple[str, ServiceCard]] = field(default_factory=dict)
    identities: dict[str, tuple[str, str, str, str]] = field(default_factory=dict)
    notices: list[str] = field(default_factory=list)


class ServiceContext:
    """One worker operation with fresh vehicle, definition and ECU identity evidence."""

    def __init__(
        self,
        connection: Any,
        backend: JobBackend,
        ecus: list[dict],
        ctx: OperationContext,
        progress: Callable[[str], None],
        previous: ServiceListing | None,
        observe: Callable[[str], None],
    ) -> None:
        self.connection = connection
        self.backend = backend
        self.ecus = ecus
        self.ctx = ctx
        self.observe = observe
        self.progress = progress
        self.previous = previous
        self.catalog = DiagnosticCatalog()
        self.selected_variants = backend.source.uds_variants() if backend.source else {}
        self.listing = ServiceListing(connection.trace_id, connection.verified_vin)
        self._targets: dict[tuple[str, str], dict | None] = {}

    @property
    def synthetic_outputs(self) -> bool:
        """Allow simulated-only phases exclusively on the bundled local DEMO vehicle."""
        return (
            environment(self.connection).mode == "demo"
            and getattr(self.connection, "synthetic_service_outputs", False) is True
        )

    @property
    def component_controls(self) -> bool:
        """Offer actuation on a live vehicle or on a peer that models the service controls."""
        return environment(self.connection).mode == "live" or self.synthetic_outputs

    def identify_vehicle(self) -> None:
        """Match a fresh gateway VIN to the connected vehicle and the previously reviewed session."""
        vin = self.connection.verified_vin
        if (
            not valid_vin(vin)
            or self.connection.send_uds(0x10, b"\x22\xf1\x90") != b"\x62\xf1\x90" + vin.encode()
            or self.previous is not None
            and (self.previous.vin != vin or self.previous.generation != self.ctx.generation)
        ):
            raise WriteConditionsBlocked(
                "Vehicle identity changed. Reconnect and check availability."
            )

    @cached_property
    def order(self) -> dict[str, Any]:
        """Read the vehicle order once when a procedure needs its applicability rules."""
        reply = self.connection.send_uds(0x10, b"\x22\x3f\x06")
        try:
            return decode_vehicle_order(reply)
        except ValueError:
            self.listing.notices.append(
                "Vehicle order unavailable. Equipment-dependent coverage is limited."
            )
            return {}

    def target(self, name: str, digest: str) -> dict | None:
        """Identify one unambiguous installed variant and bind its reported software and job."""
        key = (name, digest)
        if key in self._targets:
            return self._targets[key]
        matches = [e for e in self.ecus if e.get("name") == name and e.get("identified") is True]
        result = None
        if len(matches) == 1 and self.backend.file_sha256(name) == digest and digest:
            ecu = matches[0]
            address = int(ecu["addr"], 16)
            previous_timing = self.ctx.response_timing
            try:
                if address == 0x63:
                    self.ctx.response_timing = ENET_HEADUNIT_READ_TIMING
                identity = self.connection.send_uds(address, b"\x22\xf1\x50")
                fresh = self.catalog.identify(address, identity)
                if (
                    fresh.get("identified") is True
                    and fresh["address_index"] == ecu.get("address_index")
                    and fresh["name"] == name
                    and self.selected_variants.get(fresh["address_index"]) == name
                ):
                    software = self.connection.send_uds(address, b"\x22\xf1\x01")
                    validate_software(software)
                    snapshot = (fresh["address_index"], identity.hex(), software.hex(), digest)
                    if self.previous is None or self.previous.identities.get(name) == snapshot:
                        self.listing.identities[name] = snapshot
                        result = dict(
                            fresh,
                            identity=identity.hex(),
                            software=software.hex(),
                            prg_sha256=digest,
                            address=address,
                            source_variant=name,
                        )
            except ValueError:
                logger.info("Service identity unavailable ecu=%s", name, exc_info=True)
            finally:
                self.ctx.response_timing = previous_timing
        self._targets[key] = result
        return result

    def read_fields(
        self, name: str, address: int, job: str, args: str, request: bytes, size: int
    ) -> tuple[dict, bytes]:
        """Require one exact read-only transaction and one complete native result set."""
        if len(request) != 3 or request[0] != 0x22:
            raise ValueError("Invalid component read definition")
        try:
            run = self.backend.run(
                name,
                address,
                job,
                args,
                grant=frozenset({request[0]}),
                expected=frozenset({request}),
                sequence=(request,),
                timeout=self.ctx.remaining(),
                deadline=self.ctx.deadline,
                cancelled=self.ctx.cancelled,
            )
        except ProtocolFailure as exc:
            if exc.reconnect:
                raise ConnectionError("Connection lost during component read") from exc
            raise ValueError("Component read returned an invalid response") from exc
        if isinstance(run.error, (TimeoutError, ConnectionError)):
            raise run.error
        reply = run.reply(request)
        if (
            not run.ok
            or not run.result
            or len(run.result.sets) != 1
            or run.exchanges != [(request, reply)]
            or len(reply) != 3 + size
            or reply[:3] != b"\x62" + request[1:]
        ):
            raise ValueError("Component read rejected, malformed or unavailable")
        return run.result.sets[0], reply[3:]

    def stationary_targets(self) -> tuple[list[dict], bool]:
        """Bind speed, engine speed and ignition readers to the current canonical variants."""
        conditions = _condition_definitions()
        power = reader_profiles()
        targets = []
        ignition = False
        has_engine = False
        missing_engine = False
        for ecu in self.ecus:
            name = ecu.get("name", "")
            engine = conditions["engines"].get(name)
            power_profile = power.get(name)
            if engine is not None:
                digest = engine["sha256"]
            elif power_profile and any("kl15" in r["values"] for r in power_profile["readers"]):
                digest = power_profile["job_sha256"]
            else:
                continue
            target = self.target(name, digest)
            if engine and target is None:
                missing_engine = True
            if target is not None:
                targets.append(target)
                has_engine |= engine is not None
                ignition |= bool(
                    power_profile
                    and target["address_index"] in power_profile["selectors"]
                    and any("kl15" in r["values"] for r in power_profile["readers"])
                    and power_profile["job_sha256"] == digest
                )
        return targets, has_engine and ignition and not missing_engine

    def check_stationary(self) -> None:
        """Require a fresh stationary vehicle, stopped engine and stable ignition reading."""
        targets, available = self.stationary_targets()
        if not available:
            raise WriteConditionsBlocked(
                "Road speed, engine speed and ignition need verified readers. Check availability again."
            )
        engines = [e for e in targets if e["name"] in _condition_definitions()["engines"]]
        rows = read_engine_data(self.connection, engines, labels={"Speed", "Engine speed"}) or []
        readings = {(row["label"], row["unit"]): row["value"] for row in rows}
        if readings.get(("Speed", "km/h")) != 0 or readings.get(("Engine speed", "1/min")) != 0:
            raise WriteConditionsBlocked(
                "Zero road speed and a stopped engine could not be confirmed."
            )
        self.progress(
            check_write_conditions(self.connection, targets, self.ctx, require_ignition=True)
        )


@lru_cache(maxsize=1)
def _condition_definitions() -> dict[str, Any]:
    """Read reviewed motion prerequisites from the standalone bundle."""
    with resource_path("coding_data/service_conditions.json").open("rb") as stream:
        raw = stream.read(262145)
    if len(raw) > 262144:
        raise ValueError("Service condition definitions exceed their size limit")
    conditions = json.loads(raw)
    if (
        conditions["schema"] != 1
        or conditions["measurements_sha256"]
        != hashlib.sha256(
            resource_path("coding_data/engine_measurements.json").read_bytes()
        ).hexdigest()
    ):
        raise ValueError("Stationary-state definitions changed")
    return dict(conditions)


class ServiceProvider(Protocol):
    """Resolve and execute functions owned by a single feature implementation."""

    def discover(self, context: ServiceContext) -> list[ServiceCard]: ...
    def execute(
        self, context: ServiceContext, card: ServiceCard, action: ServiceAction
    ) -> ServiceResult: ...


def _providers() -> dict[str, ServiceProvider]:
    from app import service_mirror, service_observations, service_wipers

    return {
        "readings": service_observations,
        "mirror": service_mirror,
        "wipers": service_wipers,
    }


class ServiceWorker(CarWorker):
    """Discover supported cards or run a single freshly checked, explicitly selected action."""

    observation_ready = Signal(str)

    def __init__(
        self,
        connection: Any,
        ecus: list[dict],
        *,
        listing: ServiceListing | None = None,
        key: str = "",
        action: str = "",
        confirmed: tuple[str, ...] = (),
    ) -> None:
        super().__init__(connection)
        self.ecus = ecus
        self.listing = listing
        self.key = key
        self.action = action
        self.confirmed = confirmed

    def do_work(self) -> ServiceListing | ServiceResult:
        """Hold the owner across verification, native phases, release and readback."""
        conn = self.connection
        operation = conn.context(30.0)
        backend = JobBackend(conn)
        result: ServiceListing | ServiceResult | None = None
        observations: list[str] = []

        def publish(message: str) -> None:
            observations.append(message)
            self.progress.emit(message)

        if not backend.available or conn.kind != TransportKind.HSFZ:
            backend.close()
            return ServiceResult("Unavailable", ("No supported job data for this transport.",))
        try:
            context = ServiceContext(
                conn,
                backend,
                self.ecus,
                operation,
                publish,
                self.listing,
                self.observation_ready.emit,
            )

            def run(_services: UdsServices, _ctx: OperationContext) -> bytes:
                nonlocal result
                context.identify_vehicle()
                if self.listing is None:
                    result = self._discover(context)
                else:
                    result = self._execute(context, self.listing)
                return b""

            conn.run_operation(0x10, run, context=operation)
        except WriteConditionsBlocked as exc:
            return ServiceResult("Blocked", (str(exc),))
        except (OSError, ValueError):
            logger.warning("Service function operation interrupted", exc_info=True)
            lines = result.lines if isinstance(result, ServiceResult) else tuple(observations)
            if operation.mutation or (
                isinstance(result, ServiceResult) and result.state == "Uncertain"
            ):
                return ServiceResult(
                    "Uncertain",
                    (
                        *lines,
                        "Completion could not be confirmed. Check actual state before another operation.",
                    ),
                )
            return ServiceResult(
                "Unavailable" if not lines else "Partial",
                (
                    *lines,
                    "Vehicle data could not be verified. Check the connection and session log.",
                ),
            )
        finally:
            backend.close()
        if result is None:
            raise RuntimeError("Service operation finished without a result")
        return result

    def _discover(self, context: ServiceContext) -> ServiceListing:
        listing = context.listing
        for name, provider in _providers().items():
            try:
                cards = provider.discover(context)
            except (OSError, ValueError, KeyError) as exc:
                logger.warning("Service availability incomplete provider=%s", name, exc_info=True)
                listing.notices.append(f"Some {name} functions could not be checked.")
                if (
                    isinstance(exc, (TimeoutError, ConnectionError))
                    or not context.connection.alive_ok
                ):
                    break
                continue
            for card in cards:
                if card.key in listing.cards:
                    raise ValueError("Duplicate service function identity")
                listing.cards[card.key] = (name, card)
        if any(a.temporary for _, c in listing.cards.values() for a in c.actions):
            try:
                _, available = context.stationary_targets()
            except (KeyError, ValueError, OSError):
                logger.warning("Service motion or ignition readers unavailable", exc_info=True)
                available = False
            if not available:
                for key, (owner, card) in tuple(listing.cards.items()):
                    reads = tuple(a for a in card.actions if not a.temporary)
                    if reads:
                        listing.cards[key] = (owner, replace(card, actions=reads))
                    else:
                        del listing.cards[key]
                listing.notices.append(
                    "Controls need verified road speed, engine speed and ignition readers."
                )
        return listing

    def _execute(self, context: ServiceContext, listing: ServiceListing) -> ServiceResult:
        provider_name, reviewed = listing.cards[self.key]
        provider = _providers()[provider_name]
        current = next((card for card in provider.discover(context) if card.key == self.key), None)
        if current is None or self.action not in {a.key for a in reviewed.actions}:
            return ServiceResult(
                "Blocked", ("Compatibility or conditions changed. Check availability again.",)
            )
        action = next((item for item in current.actions if item.key == self.action), None)
        if action is None:
            return ServiceResult(
                "Blocked", ("This action is no longer available.", *current.readings)
            )
        if action not in reviewed.actions:
            return ServiceResult(
                "Blocked", ("The required conditions changed. Check availability again.",)
            )
        if action.confirmations != self.confirmed:
            return ServiceResult("Blocked", ("Review and confirm each required condition.",))
        if action.temporary:
            if context.connection.read_only:
                return ServiceResult("Blocked", ("This session is read-only.",))
            context.check_stationary()
        return provider.execute(context, current, action)
