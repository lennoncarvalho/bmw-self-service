"""doipclient message/parser reuse with project-owned bounded dispatch.

The high-level DoIPClient receive/ACK loops are deliberately not instantiated:
its early-reply loss and resetting timers cannot satisfy the operation contract.
No reconnect or resend code is reachable from this adapter.
"""

import select
from typing import Any

from doipclient.client import DoIPClient, Parser
from doipclient.messages import (
    AliveCheckRequest,
    AliveCheckResponse,
    DiagnosticMessage,
    DiagnosticMessageNegativeAcknowledgement,
    DiagnosticMessagePositiveAcknowledgement,
    GenericDoIPNegativeAcknowledge,
    RoutingActivationRequest,
    RoutingActivationResponse,
)

from app.protocol.contracts import EcuIdentity, FailureKind, OperationContext, ProtocolFailure
from app.protocol.stream import BoundedStream, check_payload


class DoipAdapter:
    """One stream, one target per transaction and a retained early reply queue."""

    def __init__(self, stream: BoundedStream, read_only: bool, tester: int = 0x0E00) -> None:
        self.stream = stream
        self.read_only = read_only
        self.tester = tester
        self.parser = Parser()
        self.activated = False
        self._early: list[bytes] = []

    def _send(self, message: Any, ctx: OperationContext) -> None:
        self.stream.send(DoIPClient._pack_doip(2, message.payload_type, message.pack()), ctx)

    def _receive(self, ctx: OperationContext) -> Any:
        while True:
            raw = self.stream.frame(True, ctx)
            message = self.parser.read_message(raw)
            if message is None:
                raise ConnectionError("Invalid diagnostic transport frame")
            if isinstance(message, GenericDoIPNegativeAcknowledge):
                raise ProtocolFailure(FailureKind.TRANSPORT_REJECTED, raw)
            if isinstance(message, AliveCheckRequest):
                self._send(AliveCheckResponse(self.tester), ctx)
            else:
                return message

    def activate(self, ctx: OperationContext, entity: int) -> None:
        """Validate routing identity/status before allowing diagnostics."""
        ctx.remaining()
        ctx.sent = True
        self._send(RoutingActivationRequest(self.tester, 0), ctx)
        message = self._receive(ctx)
        if not isinstance(message, RoutingActivationResponse) or (
            message.client_logical_address != self.tester
            or message.logical_address != entity
            or message.response_code != 0x10
        ):
            raise ConnectionError("Vehicle declined diagnostic routing activation")
        self.activated = True

    def _addressed(self, message: Any, ecu: EcuIdentity) -> bool:
        return bool(message.source_address == ecu.address and message.target_address == self.tester)

    def send_diagnostic(self, ecu: EcuIdentity, payload: bytes, context: OperationContext) -> None:
        """Keep diagnostics arriving before ACK rather than discarding them."""
        if not self.activated:
            raise ConnectionError("Diagnostic routing is not activated")
        check_payload(payload, self.read_only)
        context.remaining()
        context.sent = True
        context.mutation |= payload[0] not in (1, 0x10, 0x19, 0x1A, 0x22, 0x3E)
        self._send(DiagnosticMessage(self.tester, ecu.address, payload), context)
        while True:
            message = self._receive(context)
            if isinstance(message, DiagnosticMessage) and self._addressed(message, ecu):
                if len(self._early) >= 64:
                    raise ConnectionError("Too many diagnostic responses before acknowledgement")
                self._early.append(bytes(message.user_data))
            elif isinstance(message, DiagnosticMessageNegativeAcknowledgement):
                if self._addressed(message, ecu):
                    raise ProtocolFailure(FailureKind.TRANSPORT_REJECTED)
            elif isinstance(message, DiagnosticMessagePositiveAcknowledgement):
                if self._addressed(message, ecu):
                    if message.ack_code != 0:
                        raise ConnectionError("Invalid diagnostic acknowledgement")
                    return

    def receive_diagnostic(self, ecu: EcuIdentity, context: OperationContext) -> bytes:
        """Return only the addressed ECU's payload within the original deadline."""
        if self._early:
            return self._early.pop(0)
        while True:
            message = self._receive(context)
            if isinstance(message, DiagnosticMessage) and self._addressed(message, ecu):
                return bytes(message.user_data)
            if isinstance(message, DiagnosticMessageNegativeAcknowledgement) and self._addressed(
                message, ecu
            ):
                raise ProtocolFailure(FailureKind.TRANSPORT_REJECTED)

    def poll(self, ctx: OperationContext) -> None:
        """Answer idle alive requests; do not assign stale diagnostics to new work."""
        message = self._receive(ctx)
        if not isinstance(message, DiagnosticMessagePositiveAcknowledgement):
            raise ConnectionError("Unowned transport response requires reconnect")

    def prepare(self, ctx: OperationContext) -> None:
        """Resolve already queued controls/fragments before a new diagnostic send."""
        if self._early:
            raise ConnectionError("Unconsumed diagnostic response requires reconnect")
        while self.stream.buffer or select.select([self.stream.sock], [], [], 0)[0]:
            self.poll(ctx)

    def close(self) -> None:
        """Close the stream without reconnecting or replaying any request."""
        self.stream.close()
