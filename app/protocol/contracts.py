"""Transport-independent contracts for the spec 25 protocol migration."""

import math
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from threading import Event
from typing import Protocol


class TransportKind(StrEnum):
    """Explicit transport selected from discovery evidence."""

    HSFZ = "hsfz"
    DOIP = "doip"


@dataclass(frozen=True)
class EcuIdentity:
    """Address and known software identity within one connection generation."""

    generation: str
    transport: TransportKind
    address: int
    variant: str | None = None
    software: str | None = None

    def __post_init__(self) -> None:
        maximum = 0xFF if self.transport == TransportKind.HSFZ else 0xFFFF
        if not self.generation or not 0 <= self.address <= maximum:
            raise ValueError("Invalid ECU generation or transport address")


@dataclass(frozen=True)
class DiscoveryResult:
    """Validated discovery identity supplied by a future transport adapter."""

    transport: TransportKind
    host: str
    interface: str
    local_ipv4: str
    vin: str | None = None
    logical_address: int | None = None


@dataclass(frozen=True)
class EcuSession:
    """Immutable snapshot of one ECU's negotiated timing and session."""

    identity: EcuIdentity
    session: int = 1
    p2: float | None = None
    p2_star: float | None = None


class OperationCancelled(Exception):
    """Cancellation observed before the next bounded operation."""


@dataclass
class OperationContext:
    """One absolute budget, cancellation token and transmission phase.

    Only the owner mutates sent; callers may set cancelled from any thread.
    Adapters must check remaining before each bounded I/O and mark sent before
    the first send attempt, since an exception can follow a partial transmission.
    """

    generation: str
    deadline: float
    operation_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    cancelled: Event = field(default_factory=Event)
    sent: bool = False
    mutation: bool = False

    def __post_init__(self) -> None:
        if not self.generation or not math.isfinite(self.deadline):
            raise ValueError("An operation requires a generation and finite deadline")

    @classmethod
    def create(cls, generation: str, timeout: float = 30.0) -> "OperationContext":
        """Create the deadline before queue submission, never at socket send."""
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Operation timeout must be finite and positive")
        return cls(generation=generation, deadline=time.monotonic() + timeout)

    def remaining(self) -> float:
        """Check cancellation and return the remaining monotonic budget."""
        if self.cancelled.is_set():
            raise OperationCancelled("Vehicle operation cancelled")
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Vehicle operation timed out")
        return remaining


class FailureKind(StrEnum):
    """Project-level outcomes independent of backend exception classes."""

    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    CLOSED = "connection-closed"
    FAILED = "failed"
    UNCERTAIN = "outcome-uncertain"


@dataclass(frozen=True)
class OperationOutcome:
    """Immutable completion carrying request ownership and transmission state."""

    operation_id: str
    generation: str
    payload: bytes | None = None
    failure: FailureKind | None = None
    sent: bool = False


class TransportAdapter(Protocol):
    """Raw diagnostic boundary; implementations must honor the absolute context."""

    def send_diagnostic(self, ecu: EcuIdentity, payload: bytes, context: OperationContext) -> None:
        """Apply final byte policy, then send once within the remaining budget."""
        ...

    def receive_diagnostic(self, ecu: EcuIdentity, context: OperationContext) -> bytes:
        """Dispatch controls and return an addressed diagnostic payload."""
        ...

    def close(self) -> None:
        """Release resources on the owning worker."""
        ...
