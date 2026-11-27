"""Stateful local vehicle peer below the production HSFZ and UDS layers."""

import contextlib
import copy
import json
import logging
import socket
import struct
import threading
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from app.cbs import reset_request
from app.coding import bootloader_identifier
from app.coding_authorization import derive_authorization_key
from app.coding_db import CodingDatabase
from app.demo_service_mirror import DemoMirror
from app.history_files import valid_vin
from app.protocol.contracts import OperationContext
from app.protocol.stream import MAX_BODY, BoundedStream
from app.resources import resource_path
from app.service_history import _HEADER, _ITEM
from app.session import SessionEnvironment

logger = logging.getLogger(__name__)
CAPTURED_DEMO_PROFILE = Path.home() / "BMW-Tool" / "demo" / "captured_vehicle.json"
HEADUNIT_ENTITLEMENT_LIST = bytes.fromhex("31010f1f04")


class DemoVehicle:
    """One virtual vehicle instance, retained across connection generations."""

    def __init__(self, profile_path: Path | None = None) -> None:
        """Load a bounded standalone profile without starting any communication."""
        self.environment = SessionEnvironment("demo", uuid.uuid4().hex)
        path = profile_path or resource_path("assets/demo_vehicle.json")
        with path.open("rb") as stream:
            raw = stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError("DEMO vehicle profile exceeds its size limit")
        profile = json.loads(raw)
        if (
            not isinstance(profile, dict)
            or profile.get("schema") != 1
            or not valid_vin(profile.get("vin"))
            or not isinstance(profile.get("ecus"), dict)
            or not profile["ecus"]
        ):
            raise ValueError("Unsupported DEMO vehicle profile")
        self.vin: str = profile["vin"]
        self.captured = "capture" in profile
        self._ecus: dict[int, dict[str, Any]] = {
            int(address, 16): copy.deepcopy(ecu) for address, ecu in profile["ecus"].items()
        }
        if len(self._ecus) != len(profile["ecus"]) or 0x10 not in self._ecus:
            raise ValueError("Invalid DEMO vehicle inventory")
        for address, ecu in self._ecus.items():
            if not 0 <= address <= 255 or not isinstance(ecu, dict):
                raise ValueError("Invalid DEMO ECU")
            for field in ("reads", "blocks"):
                if not isinstance(ecu.get(field), dict):
                    raise ValueError("Invalid DEMO ECU values")
                for did, value in ecu[field].items():
                    if len(did) != 4 or len(bytes.fromhex(did)) != 2:
                        raise ValueError("Invalid DEMO data identifier")
                    if len(bytes.fromhex(value)) > 65536:
                        raise ValueError("DEMO value exceeds its size limit")
            responses = ecu.get("responses", {})
            if not isinstance(responses, dict):
                raise ValueError("Invalid DEMO captured responses")
            for request, response in responses.items():
                if not bytes.fromhex(request) or not 1 <= len(bytes.fromhex(response)) <= 65536:
                    raise ValueError("Invalid DEMO captured exchange")
            for record in ecu.get("cbs", ()):
                if len(bytes.fromhex(record)) != 12:
                    raise ValueError("Invalid DEMO service record")
            for fault in ecu.get("faults", ()):
                if len(bytes.fromhex(fault["code"])) != 3 or not 0 <= fault["status"] <= 255:
                    raise ValueError("Invalid DEMO fault record")
        self._mirror = None if self.captured else DemoMirror()
        self._lock = threading.Lock()
        self._peers: list[tuple[socket.socket, threading.Thread]] = []
        self._history: list[bytes] = []

    def set_wiper_stalk(self, service: bool) -> None:
        """Move the bundled vehicle's virtual stalk independently of diagnostic commands."""
        from app.service_wipers import set_demo_position

        if self.captured:
            raise ValueError("A captured vehicle has no virtual wiper stalk")
        with self._lock:
            set_demo_position(self._ecus[0x40], service)

    def connect_stream(self, context: OperationContext) -> BoundedStream:
        """Create a private socket pair; never discover or connect a network endpoint."""
        context.remaining()
        client, peer = socket.socketpair()
        peer.settimeout(0.1)
        thread = threading.Thread(
            target=self._serve, args=(peer,), name="DEMO vehicle peer", daemon=True
        )
        self._peers = [(sock, worker) for sock, worker in self._peers if worker.is_alive()]
        self._peers.append((peer, thread))
        thread.start()
        return BoundedStream(client, context.generation)

    def close(self) -> None:
        """Stop virtual peers without waiting on the GUI or changing vehicle data."""
        for peer, _ in self._peers:
            with contextlib.suppress(OSError):
                peer.shutdown(socket.SHUT_RDWR)
        self._peers.clear()

    def _serve(self, peer: socket.socket) -> None:
        buffer = bytearray()
        sessions: dict[int, int] = {}
        unlocked: set[int] = set()
        try:
            while True:
                try:
                    chunk = peer.recv(65536)
                except TimeoutError:
                    continue
                if not chunk:
                    return
                buffer.extend(chunk)
                while len(buffer) >= 6:
                    length, control = struct.unpack(">IH", buffer[:6])
                    if not 2 <= length <= MAX_BODY:
                        return
                    if len(buffer) < length + 6:
                        break
                    body = bytes(buffer[6 : 6 + length])
                    del buffer[: 6 + length]
                    if control != 1 or body[0] != 0xF4:
                        return
                    address, request = body[1], body[2:]
                    if not request:
                        return
                    with self._lock:
                        reply = self._reply(address, request, sessions, unlocked)
                    # Separate transport acceptance from the final addressed application reply.
                    peer.sendall(self._frame(2, address, body[0], request))
                    peer.sendall(self._frame(1, address, body[0], reply))
        except (OSError, ValueError, KeyError, struct.error):
            logger.debug("DEMO peer closed", exc_info=True)
        finally:
            peer.close()

    @staticmethod
    def _frame(control: int, source: int, target: int, payload: bytes) -> bytes:
        body = bytes((source, target)) + payload
        return struct.pack(">IH", len(body), control) + body

    def _reply(
        self, address: int, request: bytes, sessions: dict[int, int], unlocked: set[int]
    ) -> bytes:
        sid = request[0]
        reject = bytes((0x7F, sid, 0x31))
        ecu = self._ecus.get(address)
        if ecu is None:
            return reject
        if self._mirror is not None:
            reply = self._mirror.reply(variant=ecu["name"], request=request, reads=ecu["reads"])
            if reply is not None:
                return reply
        responses = ecu.get("responses", {})
        captured_reply = responses.get(request.hex())
        if sid == 0x22 and len(request) == 3:
            did = request[1:].hex().upper()
            if did == "1001" and "cbs" in ecu:
                return b"\x62\x10\x01" + b"".join(bytes.fromhex(r) for r in ecu["cbs"])
            if did == "1002" and not self.captured:
                return bytes.fromhex("621002010000")
            if did == "2000" and not self.captured:
                return b"\x62\x20\x00"  # The virtual profile has no information-memory entries.
            value = ecu["blocks"].get(did, ecu["reads"].get(did))
            if value is not None:
                return b"\x62" + request[1:] + bytes.fromhex(value)
            if captured_reply is not None:
                return bytes.fromhex(captured_reply)
            logger.debug("DEMO unsupported DID ecu=%02X request=%s", address, request.hex())
            return reject
        if sid == 0x19:
            if captured_reply is not None:
                return bytes.fromhex(captured_reply)
            return reject if self.captured else self._fault_reply(ecu, request)
        if sid == 0x10 and request[1:] in (b"\x01", b"\x03", b"\x41", b"\x42"):
            sessions[address] = request[1]
            unlocked.discard(address)
            return b"\x50" + request[1:] + bytes.fromhex("00321388")
        if request == b"\x3e\x00":
            return b"\x7e\x00"
        if request == b"\x11\x01":
            sessions[address] = 1
            unlocked.discard(address)
            return b"\x51\x01"
        if request == b"\x14\xff\xff\xff":
            if self.captured:
                for key, value in responses.items():
                    if key.startswith("1902") and value.startswith("5902"):
                        responses[key] = value[:6]
                for key in tuple(responses):
                    if key.startswith(("1904", "1906", "1909")):
                        responses.pop(key)
            else:
                ecu["faults"].clear()
                if "clear_lamp_did" in ecu:
                    ecu["reads"][ecu["clear_lamp_did"]] = "00"
            return b"\x54"
        if request == bytes.fromhex("31010f06"):
            if self.captured:
                for key, value in responses.items():
                    if key.startswith("1917") and value.startswith("5917"):
                        responses[key] = value[:8]
                for key in tuple(responses):
                    if key.startswith(("1918", "1919", "2220")):
                        responses.pop(key)
                for did in tuple(ecu["reads"]):
                    if did.startswith("20"):
                        ecu["reads"].pop(did)
                        if did == "2000":
                            ecu["reads"][did] = ""
            return bytes.fromhex("71010f06")
        if sid == 0x27 and sessions.get(address) == 0x41:
            if request == bytes.fromhex("2701ffffffff"):
                return bytes.fromhex("670101020304")
            db = CodingDatabase()
            try:
                bootloader = bootloader_identifier(bytes.fromhex("62f101" + ecu["reads"]["F101"]))
                key = derive_authorization_key(
                    bytes.fromhex("01020304"), db.authorization(bootloader)
                )
            except (KeyError, ValueError):
                return reject
            if request == b"\x27\x02" + key:
                unlocked.add(address)
                return b"\x67\x02"
            return bytes((0x7F, sid, 0x35))
        if sid == 0x2E:
            if request[:3] == b"\x2e\x10\x01":
                for index, raw in enumerate(ecu.get("cbs", ())):
                    record = bytearray.fromhex(raw)
                    if request == reset_request(record[0]):
                        record[4] = (record[4] + 1) % 31
                        record[5] = 100
                        remaining = int.from_bytes(record[1:3], "big", signed=True)
                        unit = record[3] & 15
                        if remaining not in (-0x8000, 0x7FFF) and unit in (1, 2):
                            record[1:3] = (3000 if unit == 1 else 730).to_bytes(2, "big")
                        if 1 <= record[7] & 15 <= 12 and 0 < record[8] < 63:
                            record[8] = min(record[8] + 2, 62)
                        ecu["cbs"][index] = record.hex()
                        return b"\x6e\x10\x01"
                return reject
            if address not in unlocked:
                return bytes((0x7F, sid, 0x33))
            did = request[1:3].hex().upper()
            if did == "37FE" and request[3:] == self.vin[-7:].encode():
                return b"\x6e\x37\xfe"
            if did in ecu["blocks"] and len(request[3:]) == len(bytes.fromhex(ecu["blocks"][did])):
                ecu["blocks"][did] = request[3:].hex()
                return b"\x6e" + request[1:3]
            return reject
        if address == 0x63 and sessions.get(address, 1) in (1, 0x42):
            if request == HEADUNIT_ENTITLEMENT_LIST:
                if captured_reply is not None:
                    return bytes.fromhex(captured_reply)
                if not self.captured:
                    return bytes.fromhex("71010f1f0000000000") + bytes(7)
            if request == bytes.fromhex("3101a080"):
                self._history.clear()
                return bytes.fromhex("7101a08000")
            if request[:4] == bytes.fromhex("3101a081") and len(request) >= 4 + _HEADER.size:
                fields = _HEADER.unpack(request[4 : 4 + _HEADER.size])
                day, month, year = fields[:3]
                count = fields[-1]
                if (
                    1 <= count <= 13
                    and len(request) == 4 + _HEADER.size + count * _ITEM.size
                    and date(year, month, day) <= date.today()
                ):
                    self._history.append(bytes(request[4:]))
                    return bytes.fromhex("7101a08100")
        logger.debug("DEMO unsupported request ecu=%02X data=%s", address, request.hex())
        return reject

    @staticmethod
    def _fault_reply(ecu: dict[str, Any], request: bytes) -> bytes:
        records = ecu["faults"]
        if len(request) == 3 and request[1] == 2:
            return b"\x59\x02\xff" + b"".join(
                bytes.fromhex(row["code"]) + bytes((row["status"],))
                for row in records
                if row["status"] & request[2]
            )
        if request == b"\x19\x15":
            return b"\x59\x15\xff"
        if request == bytes.fromhex("19170c01"):
            return bytes.fromhex("591701ff")
        if len(request) >= 5 and any(request[2:5].hex().upper() == r["code"] for r in records):
            if request[1] == 9:
                return bytes.fromhex("5909ff0000") + request[2:5] + b"\x08"
            if request[1] == 6:
                return b"\x59\x06" + request[2:5] + bytes.fromhex("08010102ff03fe")
            if request[1] == 4:
                return b"\x59\x04" + request[2:5] + bytes.fromhex("080102170000006417010000007b")
        return bytes((0x7F, 0x19, 0x31))
