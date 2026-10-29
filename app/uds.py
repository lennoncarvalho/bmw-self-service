"""Standard service encoding/validation through udsoncan; no transport framing."""

import time
from dataclasses import dataclass
from typing import Any

from udsoncan import DidCodec, Request, Response
from udsoncan.BaseService import BaseService
from udsoncan.client import Client
from udsoncan.exceptions import (
    InvalidResponseException,
    NegativeResponseException,
    TimeoutException,
    UnexpectedResponseException,
)
from udsoncan.services import ReadDTCInformation

from app.protocol.contracts import (
    EcuIdentity,
    EcuSession,
    FailureKind,
    OperationContext,
    ProtocolFailure,
)
from app.protocol.udsoncan_connection import UdsConnection

UDS_NEGATIVE_RESPONSE = 0x7F


class LegacyIdentification(BaseService):
    """Opaque compatibility for existing 0x1A calls; supplies no BMW decoder."""

    _sid = 0x1A
    _use_subfunction = False
    supported_negative_response: list[int] = []


class LegacyMeasurement(BaseService):
    """Opaque compatibility for existing 0x01 calls; supplies no field mapping."""

    _sid = 0x01
    _use_subfunction = False
    supported_negative_response: list[int] = []


class RawCodec(DidCodec):
    """Retain unknown DID data without interpreting it as vehicle information."""

    def encode(self, *values: Any) -> bytes:
        return bytes(values[0])

    def decode(self, payload: bytes) -> bytes:
        return bytes(payload)

    def __len__(self) -> int:
        raise DidCodec.ReadAllRemainingData


class VinCodec(DidCodec):
    """The retained session establishes an ASCII VIN of exactly 17 characters."""

    def decode(self, payload: bytes) -> str:
        vin = payload.decode("ascii")
        if len(vin) != 17 or not vin.isalnum():
            raise ValueError("Vehicle returned an invalid VIN")
        return vin

    def __len__(self) -> int:
        return 17


class UdsServices:
    """Per-ECU client/configuration confined to the protocol owner thread."""

    def __init__(self, bridge: UdsConnection) -> None:
        self.bridge = bridge
        self._definitions: dict[int, tuple[str, str]] = {}
        self.session = 1
        self.keepalive_enabled = False
        self.session_unavailable_reason: str | None = None
        self.last_activity = time.monotonic()
        self.client = Client(
            bridge,
            config={
                "exception_on_negative_response": True,
                "exception_on_invalid_response": True,
                "exception_on_unexpected_response": True,
                "data_identifiers": {0xF190: VinCodec},
                "tolerate_zero_padding": False,
                "ignore_all_zero_dtc": False,
                "p2_timeout": 5.0,
                "p2_star_timeout": 5.0,
            },
        )

    @property
    def session_state(self) -> EcuSession:
        """Snapshot this ECU's accepted session and negotiated timing."""
        timing = self.client.session_timing
        return EcuSession(
            self.bridge.ecu, self.session, timing.p2_server_max, timing.p2_star_server_max
        )

    def register_codecs(self, registration: "CodecRegistration") -> None:
        """Apply one exact identity/definition snapshot on the owner thread."""
        if registration.ecu.variant is None or registration.ecu.software is None:
            raise ValueError("BMW codecs require an identified ECU variant and software")
        if registration.ecu != self.bridge.ecu:
            raise ValueError("Codec definition does not match the active ECU identity")
        if not registration.definition_id or len(registration.sha256) != 64:
            raise ValueError("Codec definition requires an ID and full SHA-256")
        int(registration.sha256, 16)
        snapshot = dict(self.client.config["data_identifiers"])
        definitions = dict(self._definitions)
        if len({did for did, _ in registration.codecs}) != len(registration.codecs):
            raise ValueError("Duplicate DID codec registration")
        for did, codec in registration.codecs:
            if not 0 <= did <= 0xFFFF or not issubclass(codec, DidCodec):
                raise ValueError("Invalid DID codec registration")
            identity = (registration.definition_id, registration.sha256)
            if did in definitions and (definitions[did] != identity or snapshot[did] is not codec):
                raise ValueError("Conflicting DID definition versions")
            if did == 0xF190 and codec is not VinCodec:
                raise ValueError("VIN codec cannot be replaced")
            snapshot[did] = codec
            definitions[did] = identity
        self.client.config["data_identifiers"] = snapshot
        self._definitions = definitions

    def invoke(self, payload: bytes, ctx: OperationContext) -> bytes:
        """Execute through one udsoncan lifecycle with the active outer budget."""
        if not payload:
            raise ValueError("Diagnostic request cannot be empty")
        self.bridge.context = ctx
        self.client.config["request_timeout"] = ctx.remaining()
        response: Any
        try:
            sid = payload[0]
            if sid == 0x10 and len(payload) == 2:
                response = self.client.change_session(payload[1])
            elif sid == 0x22 and len(payload) == 3:
                did = int.from_bytes(payload[1:], "big")
                self.client.config["data_identifiers"].setdefault(did, RawCodec)
                response = self.client.read_data_by_identifier(did)
            elif sid == 0x19 and len(payload) == 3 and payload[1] == 2:
                response = self.client.get_dtc_by_status_mask(payload[2])
            elif sid == 0x14 and len(payload) == 4:
                response = self.client.clear_dtc(int.from_bytes(payload[1:], "big"))
            elif sid == 0x3E and payload == b"\x3e\x00":
                response = self.client.tester_present()
            elif sid == 0x2E and len(payload) >= 3:
                did = int.from_bytes(payload[1:3], "big")
                self.client.config["data_identifiers"].setdefault(did, RawCodec)
                response = self.client.write_data_by_identifier(did, payload[3:])
            elif sid == 0x31 and len(payload) >= 4:
                response = self.client.routine_control(
                    int.from_bytes(payload[2:4], "big"), payload[1], payload[4:]
                )
            elif payload == b"\x19\x15":
                # Source ECU variants use both standard and legacy permanent-memory
                # layouts. Feature decoder validates their exact record boundaries.
                response = self.client.send_request(Request.from_payload(payload))
            elif sid in (1, 0x1A):
                response = self.client.send_request(Request.from_payload(payload))
            else:
                raise ValueError("Diagnostic service requires an explicit supported operation")
            if response is None:
                raise ConnectionError("Vehicle did not return a diagnostic response")
            self.bridge.waiting = False
            self.last_activity = time.monotonic()
            if sid == 0x10:
                self.session = payload[1]
                self.keepalive_enabled = self.session != 1
                self.session_unavailable_reason = None
            return bytes(response.original_payload)
        except NegativeResponseException as exc:
            self.bridge.waiting = False
            raise ProtocolFailure(
                FailureKind.NEGATIVE, bytes(exc.response.original_payload or b""), reconnect=False
            ) from exc
        except InvalidResponseException as exc:
            raise ProtocolFailure(
                FailureKind.INVALID, bytes(exc.response.original_payload or b"")
            ) from exc
        except UnexpectedResponseException as exc:
            raise ProtocolFailure(
                FailureKind.UNEXPECTED, bytes(exc.response.original_payload or b"")
            ) from exc
        except TimeoutException as exc:
            raise TimeoutError("Vehicle diagnostic response timed out") from exc

    def change_session(self, session: int, ctx: OperationContext) -> bytes:
        """Change session and retain the ECU's advertised P2/P2* timing."""
        return self.invoke(bytes((0x10, session)), ctx)

    def read_data_by_identifier(self, did: int, ctx: OperationContext) -> bytes:
        """Read a DID using registered standard validation; unknown data stays raw."""
        return self.invoke(b"\x22" + did.to_bytes(2, "big"), ctx)

    def read_dtcs(self, mask: int, ctx: OperationContext) -> bytes:
        """Read standard DTC records/status through the library decoder."""
        return self.invoke(bytes((0x19, 2, mask)), ctx)

    def clear_dtcs(self, ctx: OperationContext) -> bytes:
        """Return protocol acceptance only; feature-level readback is still required."""
        return self.invoke(b"\x14\xff\xff\xff", ctx)

    def tester_present(self, ctx: OperationContext) -> bytes:
        """Maintain this ECU session with a correlated unsuppressed response."""
        return self.invoke(b"\x3e\x00", ctx)


@dataclass(frozen=True)
class CodecRegistration:
    """Task B's immutable exact-ECU/definition codec configuration."""

    ecu: EcuIdentity
    definition_id: str
    sha256: str
    codecs: tuple[tuple[int, type[DidCodec]], ...]


def decode_dtc_records(payload: bytes) -> list[tuple[int, int]]:
    """Use the standard library decoder for complete, unpadded DTC records."""
    response = Response.from_payload(payload)
    if not response.valid or not response.positive:
        raise ValueError("Invalid diagnostic fault response")
    interpreted = ReadDTCInformation.interpret_response(
        response, 2, tolerate_zero_padding=False, ignore_all_zero_dtc=False
    )
    return [(dtc.id, dtc.status.get_byte_as_int()) for dtc in interpreted.service_data.dtcs]
