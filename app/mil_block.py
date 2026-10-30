"""Owned dynamic-slot MIL read for the five older engine definitions.

Contract: docs/evidence/task-b-mil-block-recovery.md. The engine exposes its MIL
condition only through STATUS_BLOCK_LESEN: clear slot F3nn, define it from source
DID 4A69, read it. This is a diagnostic configuration change, so it runs only as
an explicit confirmed action under the global mutation lockout, never as part of
an overview refresh, and is rejected by a read-only session's transport policy.

One run_operation holds the protocol owner for the whole sequence; no other
request can redefine the slot between steps. The source application leaves the
slot defined; this app adds a response-checked cleanup clear with a reserved
budget and reports its outcome separately. A transport failure is never retried.
"""

import logging
import time
from typing import Any

from app.protocol.contracts import FailureKind, OperationContext, ProtocolFailure, TransportKind
from app.vehicle import DiagnosticCatalog, select_mil_contract
from app.worker import CarWorker

logger = logging.getLogger(__name__)

ENGINE = 0x12
# Keep enough of the 30-second budget to attempt the cleanup clear after a slow read.
CLEANUP_RESERVE = 5.0


def block_requests(did: int, slot: int) -> dict[str, bytes]:
    """Encode the recovered one-value sequence: clear, define (position 1, one byte), read."""
    slot_bytes = slot.to_bytes(2, "big")
    return {
        "clear": b"\x2c\x03" + slot_bytes,
        "define": b"\x2c\x01" + slot_bytes + did.to_bytes(2, "big") + b"\x01\x01",
        "read": b"\x22" + slot_bytes,
        "cleanup": b"\x2c\x03" + slot_bytes,
    }


def check_block_response(step: str, slot: int, response: bytes) -> int | None:
    """Apply the PRG's exact echo/shape checks; return the MIL byte for the read step."""
    slot_bytes = slot.to_bytes(2, "big")
    if step in ("clear", "cleanup"):
        if response != b"\x6c\x03" + slot_bytes:
            raise ValueError("Invalid dynamic data clear response")
        return None
    if step == "define":
        if response != b"\x6c\x01" + slot_bytes:
            raise ValueError("Invalid dynamic data definition response")
        return None
    if len(response) != 4 or response[:3] != b"\x62" + slot_bytes or response[3] not in (0, 1):
        raise ValueError("Vehicle MIL response has an unsupported value or shape")
    return response[3]


class MilBlockReadWorker(CarWorker):
    """Execute one confirmed clear/define/read/cleanup sequence; never replayed."""

    def __init__(self, connection: Any, ecus: list[dict[str, Any]]) -> None:
        super().__init__(connection)
        self.ecus = [dict(row) for row in ecus]
        self._executed = False
        self.steps: list[dict[str, str]] = []

    def _record(self, step: str, state: str, request: bytes, response: bytes = b"") -> None:
        self.steps.append(
            {"step": step, "state": state, "request": request.hex(), "response": response.hex()}
        )
        logger.info(
            "MIL block step=%s state=%s request=%s response=%s",
            step,
            state,
            request.hex(),
            response.hex(),
        )

    def do_work(self) -> dict[str, object]:
        """Run the owned sequence and describe value and cleanup outcomes separately."""
        if self._executed:
            raise PermissionError("A MIL slot sequence cannot be replayed")
        self._executed = True
        connection = self.connection
        if connection.read_only or connection.kind != TransportKind.HSFZ or not connection.alive_ok:
            raise PermissionError("MIL slot reads require a writable HSFZ session")
        engine, contract = select_mil_contract(self.ecus)
        if contract["state"] != "dynamic-block":
            raise ValueError("Identified engine does not use the dynamic MIL slot")
        slot = contract.get("slot")
        if type(slot) is not int or not 0xF300 <= slot <= 0xF3FF:
            raise ValueError("Invalid MIL slot definition")
        requests = block_requests(contract["did"], slot)
        catalog = DiagnosticCatalog()
        value: int | None = None
        defined = False
        in_flight = ""

        def send(services: Any, step: str, ctx: OperationContext) -> bytes | None:
            """Return a positive response, or None after a recorded final rejection."""
            nonlocal in_flight
            in_flight = step
            payload = requests.get(step, b"\x22\xf1\x50")
            try:
                response = bytes(services.invoke(payload, ctx))
            except ProtocolFailure as exc:
                if exc.kind != FailureKind.NEGATIVE or exc.reconnect:
                    raise
                in_flight = ""
                self._record(step, "rejected", payload, exc.raw)
                return None
            in_flight = ""
            return response

        def execute(services: Any, ctx: OperationContext) -> bytes:
            nonlocal value, defined
            aborted = False
            overall = ctx.deadline
            ctx.deadline = overall - CLEANUP_RESERVE
            try:
                identity = send(services, "identity", ctx)
                if identity is None:
                    return b""
                match = catalog.identify(ENGINE, identity)
                if (
                    match.get("address_index") != engine["address_index"]
                    or match.get("name") != engine["name"]
                ):
                    self._record("identity", "changed", b"\x22\xf1\x50", identity)
                    return b""
                self._record("identity", "accepted", b"\x22\xf1\x50", identity)
                for step in ("clear", "define", "read"):
                    response = send(services, step, ctx)
                    if response is None:
                        return b""
                    try:
                        value = check_block_response(step, slot, response)
                    except ValueError:
                        # An unexpected positive reply leaves the slot state unknown.
                        defined |= step != "clear"
                        state = "uncertain" if step != "read" else "invalid"
                        self._record(step, state, requests[step], response)
                        return b""
                    defined |= step == "define"
                    self._record(step, "accepted", requests[step], response)
                return b""
            except BaseException:
                # A failed exchange leaves the stream unusable; the owner closes it.
                aborted = True
                raise
            finally:
                ctx.deadline = overall
                if defined and not aborted:
                    response = send(services, "cleanup", ctx)
                    if response is not None:
                        try:
                            check_block_response("cleanup", slot, response)
                            self._record("cleanup", "accepted", requests["cleanup"], response)
                        except ValueError:
                            self._record("cleanup", "uncertain", requests["cleanup"], response)

        context = connection.context(30.0)
        failure = ""
        try:
            connection.run_operation(ENGINE, execute, context=context)
        except Exception as exc:
            # The owner invalidates the stream after a timeout/loss; never retry or replay.
            logger.warning("MIL slot sequence stopped", exc_info=True)
            failure = str(exc) or type(exc).__name__
            if in_flight:
                request = requests.get(in_flight, b"\x22\xf1\x50")
                state = "uncertain" if in_flight in ("clear", "define", "cleanup") else "failed"
                self._record(in_flight, state, request)
                defined |= in_flight == "define"
        return self._result(engine["name"], slot, value, defined, failure)

    def _result(
        self, name: str, slot: int, value: int | None, defined: bool, failure: str
    ) -> dict[str, object]:
        states = {row["step"]: row["state"] for row in self.steps}
        cleanup = states.get("cleanup", "not-attempted" if defined else "not-needed")
        if cleanup == "not-attempted":
            cleanup_text = (
                f"temporary slot {slot:04X} could not be cleared (connection stopped); "
                "the engine may keep it until it resets — reconnect before other actions"
            )
        elif cleanup != "accepted" and cleanup != "not-needed":
            cleanup_text = (
                f"cleanup of temporary slot {slot:04X} was {cleanup}; "
                "the engine may keep it until it resets"
            )
        else:
            cleanup_text = ""
        result: dict[str, object] = {
            "steps": list(self.steps),
            "cleanup": cleanup,
            "slot": f"{slot:04X}",
        }
        if value is not None:
            detail = (
                f"Engine {name} reports the MIL condition through temporary data slot "
                f"{slot:04X}; not a physical lamp check"
            )
            result.update(on=value == 1, observed_clock=time.monotonic())
        elif states.get("identity") == "changed":
            detail = "Engine identity changed — refresh the overview before reading MIL"
            result["on"] = None
        elif any(state == "rejected" for state in states.values()):
            step = next(row for row in self.steps if row["state"] == "rejected")
            detail = f"Engine rejected the MIL {step['step']} request ({step['response']})"
            result["on"] = None
        else:
            detail = "MIL could not be read" + (f" — {failure}" if failure else "")
            result["on"] = None
        result["detail"] = detail + (f"\nWarning: {cleanup_text}" if cleanup_text else "")
        return result
