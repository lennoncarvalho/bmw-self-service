"""Bounded ordinary TCP stream and final diagnostic send policy."""

import errno
import logging
import select
import socket
import struct

from app.protocol.contracts import OperationContext

logger = logging.getLogger(__name__)
MAX_BODY = 1024 * 1024


def check_payload(payload: bytes, read_only: bool) -> None:
    """Reject malformed requests and enforce read-only policy on encoded bytes."""
    if not payload:
        raise ValueError("Diagnostic request cannot be empty")
    if not read_only:
        return
    sid = payload[0]
    allowed = sid in (0x01, 0x19, 0x1A, 0x22)
    if sid == 0x10:
        allowed = len(payload) == 2 and payload[1] in (1, 3)
    elif sid == 0x3E:
        allowed = len(payload) == 2 and payload[1] in (0, 0x80)
    if not allowed:
        raise PermissionError("This operation is disabled in the read-only session")


class BoundedStream:
    """Retain fragments and cap every socket wait by one absolute deadline."""

    def __init__(self, sock: socket.socket, generation: str) -> None:
        self.sock = sock
        self.sock.setblocking(False)
        self.generation = generation
        self.buffer = bytearray()

    @classmethod
    def connect(cls, host: str, port: int, local_ip: str, ctx: OperationContext) -> "BoundedStream":
        """Bind selected IPv4 before connecting without an unbounded wait."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind((local_ip, 0))
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.setblocking(False)
            result = sock.connect_ex((host, port))
            if result not in (0, errno.EINPROGRESS, errno.EWOULDBLOCK):
                raise ConnectionError("Could not open vehicle connection")
            while result:
                ctx.remaining()
                if select.select([], [sock], [], min(0.05, ctx.remaining()))[1]:
                    result = sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                    if result:
                        raise ConnectionError("Could not open vehicle connection")
                    break
            return cls(sock, ctx.generation)
        except BaseException:
            sock.close()
            raise

    def send(self, frame: bytes, ctx: OperationContext) -> None:
        """Send a complete frame once, checking cancellation between fragments."""
        view = memoryview(frame)
        while view:
            if not select.select([], [self.sock], [], min(0.05, ctx.remaining()))[1]:
                continue
            try:
                count = self.sock.send(view)
            except BlockingIOError:
                continue
            if count == 0:
                raise ConnectionError("Vehicle connection closed during send")
            logger.debug(
                "TX conn=%s request=%s frame=%s",
                self.generation,
                ctx.operation_id,
                bytes(view[:count]).hex(" "),
            )
            view = view[count:]

    def fill(self, size: int, ctx: OperationContext) -> None:
        """Read exactly the needed bytes while preserving incomplete frames."""
        while len(self.buffer) < size:
            if not select.select([self.sock], [], [], min(0.05, ctx.remaining()))[0]:
                continue
            try:
                chunk = self.sock.recv(size - len(self.buffer))
            except BlockingIOError:
                continue
            if not chunk:
                raise ConnectionError("Vehicle connection closed")
            logger.debug(
                "RX conn=%s request=%s fragment=%s",
                self.generation,
                ctx.operation_id,
                chunk.hex(" "),
            )
            self.buffer.extend(chunk)

    def frame(self, doip: bool, ctx: OperationContext) -> bytes:
        """Validate the envelope length before consuming its bounded body."""
        ctx.remaining()
        header_size = 8 if doip else 6
        self.fill(header_size, ctx)
        if doip:
            version, inverse, _, length = struct.unpack(">BBHI", self.buffer[:8])
            if version not in (2, 3) or inverse != version ^ 0xFF:
                raise ConnectionError("Invalid diagnostic transport header")
        else:
            length = struct.unpack(">I", self.buffer[:4])[0]
        if length > MAX_BODY:
            raise ConnectionError("Diagnostic transport frame exceeds size limit")
        self.fill(header_size + length, ctx)
        frame = bytes(self.buffer[: header_size + length])
        del self.buffer[: header_size + length]
        return frame

    def close(self) -> None:
        """Close the owned socket; no other reader may retain it."""
        self.sock.close()
        self.buffer.clear()
