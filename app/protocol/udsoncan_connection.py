"""udsoncan's split send/receive connection with the outer operation budget."""

import logging
import time
import uuid

from udsoncan.connections import BaseConnection
from udsoncan.exceptions import TimeoutException

from app.protocol.contracts import EcuIdentity, OperationContext, TransportAdapter

logger = logging.getLogger(__name__)


class UdsConnection(BaseConnection):
    """Owner-confined bridge; queue cleanup never discards transport bytes."""

    def __init__(self, adapter: TransportAdapter, ecu: EcuIdentity) -> None:
        super().__init__(name=ecu.generation)
        self.adapter = adapter
        self.ecu = ecu
        self.context: OperationContext | None = None
        self.waiting = False

    def open(self) -> "UdsConnection":
        """The owning facade opens transport before constructing this bridge."""
        return self

    def close(self) -> None:
        """Only the connection owner may close the shared transport."""
        self.context = None

    def is_open(self) -> bool:
        """Whether an operation context is currently bound."""
        return self.context is not None

    def empty_rxqueue(self) -> None:
        """Reject unfinished ownership instead of draining fragments or late replies."""
        if self.waiting:
            raise ConnectionError("Outstanding diagnostic request requires reconnect")
        if self.context is None:
            raise ConnectionError("No active diagnostic operation")
        self.adapter.prepare(self.context)

    def empty_txqueue(self) -> None:
        """No additional transmit queue exists outside the owner."""

    def specific_send(self, payload: bytes, timeout: float | None = None) -> None:
        """Send raw bytes once; the adapter enforces policy immediately before send."""
        if self.context is None:
            raise ConnectionError("No active diagnostic operation")
        self.context.remaining()
        self.context.request_id = uuid.uuid4().hex
        self.context.ecu = self.ecu
        logger.debug(
            "UDS TX conn=%s operation=%s request=%s ecu=0x%04X data=%s",
            self.context.generation,
            self.context.operation_id,
            self.context.request_id,
            self.ecu.address,
            payload.hex(" "),
        )
        self.adapter.send_diagnostic(self.ecu, payload, self.context)
        self.waiting = True

    def specific_wait_frame(self, timeout: float | None = None) -> bytes:
        """Respect both udsoncan's P2/P2* wait and the outer deadline."""
        if self.context is None:
            raise ConnectionError("No active diagnostic operation")
        ctx = self.context
        deadline = (
            ctx.deadline if timeout is None else min(ctx.deadline, time.monotonic() + timeout)
        )
        receive = OperationContext(ctx.generation, deadline, ctx.operation_id, ctx.cancelled)
        receive.request_id = ctx.request_id
        try:
            payload = self.adapter.receive_diagnostic(self.ecu, receive)
            logger.debug(
                "UDS RX conn=%s operation=%s request=%s ecu=0x%04X data=%s",
                ctx.generation,
                ctx.operation_id,
                ctx.request_id,
                self.ecu.address,
                payload.hex(" "),
            )
            return payload
        except TimeoutError as exc:
            raise TimeoutException("Vehicle diagnostic response timed out") from exc
