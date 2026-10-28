"""Scapy HSFZ codecs behind the project's bounded stream adapter."""

import select

from scapy.contrib.automotive.bmw.hsfz import HSFZ

from app.protocol.contracts import EcuIdentity, FailureKind, OperationContext, ProtocolFailure
from app.protocol.stream import BoundedStream, check_payload


class HsfzAdapter:
    """Dispatch HSFZ controls without interpreting UDS service semantics."""

    def __init__(self, stream: BoundedStream, read_only: bool, tester: int = 0xF4) -> None:
        self.stream = stream
        self.read_only = read_only
        self.tester = tester

    def send_diagnostic(self, ecu: EcuIdentity, payload: bytes, context: OperationContext) -> None:
        """Check the actual bytes and send one Scapy-encoded diagnostic frame."""
        check_payload(payload, self.read_only)
        context.remaining()
        context.sent = True
        context.mutation |= payload[0] not in (1, 0x10, 0x19, 0x1A, 0x22, 0x3E)
        frame = HSFZ(control=1, source=self.tester, target=ecu.address) / payload
        self.stream.send(bytes(frame), context)

    def receive_diagnostic(self, ecu: EcuIdentity, context: OperationContext) -> bytes:
        """Consume controls separately and return only the addressed UDS bytes."""
        while True:
            raw = self.stream.frame(False, context)
            control = int.from_bytes(raw[4:6], "big")
            if control in (1, 2) and len(raw) < 8:
                raise ConnectionError("Truncated diagnostic address fields")
            packet = HSFZ(raw)
            if control == 1:
                if packet.source == ecu.address and packet.target == self.tester:
                    return raw[8:]
            elif control == 0x12:
                self._alive(raw, context)
            elif control >= 0x40:
                raise ProtocolFailure(FailureKind.TRANSPORT_REJECTED, raw)

    def _alive(self, raw: bytes, ctx: OperationContext) -> None:
        if len(raw) == 8 and raw[7] == self.tester:
            # Type-specific control length is explicit; Scapy's default length
            # calculation assumes the diagnostic addressing envelope.
            reply = HSFZ(length=2, control=0x12, source=self.tester, target=raw[6])
            self.stream.send(bytes(reply), ctx)

    def poll(self, ctx: OperationContext) -> None:
        """Service idle controls; an unowned diagnostic invalidates the stream."""
        raw = self.stream.frame(False, ctx)
        control = int.from_bytes(raw[4:6], "big")
        if control == 0x12:
            self._alive(raw, ctx)
        elif control == 1 or control >= 0x40:
            raise ConnectionError("Unowned diagnostic response requires reconnect")

    def prepare(self, ctx: OperationContext) -> None:
        """Resolve already queued controls/fragments before a new diagnostic send."""
        while self.stream.buffer or select.select([self.stream.sock], [], [], 0)[0]:
            self.poll(ctx)

    def close(self) -> None:
        """Release the owned bounded stream."""
        self.stream.close()
