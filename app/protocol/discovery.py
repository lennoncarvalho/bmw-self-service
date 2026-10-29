"""Source-bound discovery using Scapy HSFZ and doipclient message definitions."""

import ipaddress
import logging
import select
import socket
import struct
import time

import netifaces
from doipclient.client import DoIPClient, Parser
from doipclient.messages import VehicleIdentificationRequest, VehicleIdentificationResponse
from scapy.contrib.automotive.bmw.hsfz import HSFZ

from app.protocol.contracts import OperationContext

logger = logging.getLogger(__name__)


def discover_vehicle(interface: str, context: OperationContext) -> dict[str, str] | None:
    """Probe both explicit transports on the selected IPv4; reject ambiguity."""
    addresses = netifaces.ifaddresses(interface).get(netifaces.AF_INET, [])
    if len(addresses) != 1 or not addresses[0].get("addr") or not addresses[0].get("netmask"):
        raise ConnectionError("Select an Ethernet interface with one configured IPv4 address")
    address = addresses[0]
    local = address["addr"]
    broadcast = str(
        ipaddress.IPv4Interface(f"{local}/{address['netmask']}").network.broadcast_address
    )
    probes = [
        ("hsfz", 6811, bytes(HSFZ(length=0, control=0x11))),
        ("doip", 13400, DoIPClient._pack_doip(2, 1, VehicleIdentificationRequest().pack())),
    ]
    sockets: dict[socket.socket, str] = {}
    found: dict[tuple[str, str], dict[str, str]] = {}
    settle: float | None = None
    deadline = min(context.deadline, time.monotonic() + 5.0)
    try:
        for kind, port, payload in probes:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sockets[sock] = kind
            sock.bind((local, 0))
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.setblocking(False)
            context.remaining()
            sock.sendto(payload, (broadcast, port))
            logger.debug(
                "Discovery TX interface=%s local=%s kind=%s frame=%s",
                interface,
                local,
                kind,
                payload.hex(" "),
            )
        while time.monotonic() < min(deadline, settle or deadline):
            context.remaining()
            ready = select.select(
                list(sockets), [], [], min(0.05, max(0, deadline - time.monotonic()))
            )[0]
            for sock in ready:
                raw, peer = sock.recvfrom(65535)
                logger.debug(
                    "Discovery RX kind=%s peer=%s frame=%s", sockets[sock], peer, raw.hex(" ")
                )
                kind = sockets[sock]
                info = {"ip": peer[0], "local_ip": local, "transport": kind}
                if kind == "hsfz":
                    if (
                        len(raw) < 6
                        or raw[4:6] != b"\x00\x11"
                        or int.from_bytes(raw[:4], "big") != len(raw) - 6
                    ):
                        continue
                    marker = raw.find(b"BMWVIN", 6)
                    if marker < 0:
                        continue
                    vin_bytes = raw[marker + 6 : marker + 23]
                else:
                    if (
                        len(raw) < 8
                        or raw[0] not in (2, 3)
                        or raw[1] != raw[0] ^ 0xFF
                        or int.from_bytes(raw[4:8], "big") != len(raw) - 8
                    ):
                        continue
                    try:
                        message = Parser().read_message(raw)
                    except (ValueError, IndexError, struct.error, UnicodeDecodeError):
                        continue
                    if not isinstance(message, VehicleIdentificationResponse):
                        continue
                    vin_bytes = message.vin.encode("ascii")
                    info["logical_addr"] = str(message.logical_address)
                try:
                    vin = vin_bytes.decode("ascii")
                except UnicodeDecodeError:
                    continue
                if len(vin) != 17 or not vin.isalnum():
                    continue
                info["vin"] = vin
                found[(peer[0], kind)] = info
                settle = settle or time.monotonic() + 0.2
        vehicles = {(item["ip"], item["vin"]) for item in found.values()}
        if len(vehicles) > 1:
            raise ConnectionError(
                "Multiple vehicles responded; isolate the intended ENET connection"
            )
        # A responding entity may support both protocols. Preserve the observed
        # HSFZ baseline when both are explicitly advertised, never infer by series.
        return next(
            (item for item in found.values() if item["transport"] == "hsfz"),
            next(iter(found.values()), None),
        )
    finally:
        for sock in sockets:
            sock.close()
