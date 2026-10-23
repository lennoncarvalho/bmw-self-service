# HSFZ Protocol — Complete Specification

> **Source:** rawenet, Scapy implementation, ELM327 HSFZ extension, ediabaslib
> **Status:** Fully specified, ready to implement

---

## HSFZ (High-Speed-Fahrzeug-Zugang)

BMW's proprietary transport protocol for UDS diagnostics over Ethernet.
Used in all F-series vehicles (including F48) since ~2008.

---

## Network Layer

| Parameter | Value |
|-----------|-------|
| Transport | TCP |
| Data port | **6801** |
| Discovery port | **6811** (UDP) |
| Discovery broadcast | `169.254.255.255:6811` |
| Car IP range | `169.254.0.0/16` (link-local) |
| Typical car IP | `169.254.1.1` |
| Tester ECU address | **0xF4** (244) |
| ZGW ECU address | **0x10** |
| Discovery request | `000000000011` (6 hex bytes) |

---

## Packet Format

### Header (8 bytes)

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                            Length                             |  ← 4 bytes, BIG-ENDIAN
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|            Type               |   Source      |   Target      |  ← Type=2B, Src=1B, Dst=1B
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                                                               |
|                         Payload (UDS)                         |  ← variable
|                                                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0-3 | 4 | Length | Payload length + 2 (for src+dst bytes), BIG-ENDIAN |
| 4-5 | 2 | Type | Control word / message type |
| 6 | 1 | Source | Source ECU address (tester = 0xF4) |
| 7 | 1 | Target | Destination ECU address (ZGW = 0x10) |
| 8+ | var | Payload | UDS message data |

**Length field note**: The Length includes the src+dst bytes (2) plus the actual payload.
For a UDS message with N payload bytes, Length = N + 2.

### Message Types

| Code | Name | Src/Dst? | Payload? | Description |
|------|------|----------|----------|-------------|
| 0x0001 | diagnostic_req_res | Yes | Yes (UDS) | Diagnostic request/response — the main workhorse |
| 0x0002 | acknowledge_transfer | Yes | No | ACK from ZGW after receiving a message |
| 0x0010 | terminal15 | No | No | Ignition terminal status notification |
| 0x0011 | vehicle_ident_data | No | Maybe | Vehicle identification (discovery response) |
| 0x0012 | alive_check | Length=2: Yes, Length>2: No + ID string | No/Length | Keep-alive heartbeat — two variants |
| 0x0040 | incorrect_tester_address | Yes (exp+recv) | No | Error: wrong tester address |
| 0x0041 | incorrect_control_word | No | No | Error: invalid control word |
| 0x0042 | incorrect_format | No | No | Error: invalid format |
| 0x0043 | incorrect_dest_address | No | No | Error: invalid destination |
| 0x0044 | message_too_large | No | No | Error: message too large |
| 0x0045 | diag_app_not_ready | No | No | Error: diagnostic application not ready |
| 0x00FF | out_of_memory | No | No | Error: out of memory |

---

## Connection Flow

### 1. Physical Link Up

```
ENET cable plugged in → Pin 8 (activation line) → ZGW wakes up
Ethernet link negotiated (100BASE-TX)
Car and laptop auto-configure link-local IPs (169.254.x.x)
```

### 2. Discovery (UDP)

```
Tester sends to 169.254.255.255:6811:
  00 00 00 00 00 11
  └─ 6 bytes: LENGTH=0, TYPE=0x0011 (vehicle_ident_data)

ZGW responds:
  00 00 00 32 00 11 44 49 41 47 41 44 52 31 30 42 ...
  └─ LENGTH=0x32 (50 bytes)
  └─ TYPE=0x0011
  └─ ASCII markers: DIAGADR10, BMWMAC<12 hex>, BMWVIN<17 chars>
```

Parse the response by searching for `DIAGADR10`, `BMWMAC`, `BMWVIN` markers.

### 3. TCP Connection

```
TCP connect to <car_ip>:6801
No routing activation needed (unlike DoIP)
Once connected, start sending UDS messages
```

### 4. Alive Check (Keep-Alive)

```
Tester sends every ~2s to keep the TCP connection alive:
  00 00 00 02 00 12 F4 10
  └─ LENGTH=2, TYPE=0x0012, SRC=0xF4, DST=0x10

ZGW responds with acknowledge_transfer (TYPE 0x0002)
```

This is the transport-layer heartbeat. It's separate from UDS TesterPresent (0x3E)
which maintains the diagnostic session at the application layer.

### 5. UDS Diagnostic Message

```
Tester sends:
  00 00 00 04 00 01 F4 10  10 03
  └─ LENGTH=4 (payload 2 + src/dst 2)
  └─ TYPE=0x0001 (diagnostic_req_res)
  └─ SRC=0xF4, DST=0x10
  └─ Payload: 10 03 (UDS DiagnosticSessionControl, Extended)

ZGW responds:
  00 00 00 04 00 01 10 F4  50 03
  └─ LENGTH=4, TYPE=0x0001, SRC=0x10, DST=0xF4
  └─ Payload: 50 03 (UDS positive response)
```

Note: For routed messages (to ECUs behind the ZGW), the HSFZ header
still uses SRC/DST for the ZGW, but the UDS payload includes
internal routing addressing.

---

## Python Implementation

```python
import socket
import struct
import time

HSFZ_PORT = 6801
HSFZ_DISCOVERY_PORT = 6811
TESTER_ADDR = 0xF4
ZGW_ADDR = 0x10

TYPE_DIAG_REQ_RES = 0x0001
TYPE_ACK_TRANSFER = 0x0002
TYPE_ALIVE_CHECK = 0x0012
TYPE_VEHICLE_IDENT = 0x0011

class HSFZConnection:
    def __init__(self):
        self.sock = None
        self.car_ip = None
        self.vin = None
    
    def discover(self, interface_ip: str = "169.254.255.255") -> dict:
        """Discover vehicle on ENET network."""
        disc_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        disc_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        disc_sock.settimeout(3.0)
        
        # Discovery request: LENGTH=0, TYPE=0x0011
        request = struct.pack(">IH", 0, TYPE_VEHICLE_IDENT)
        disc_sock.sendto(request, (interface_ip, HSFZ_DISCOVERY_PORT))
        
        try:
            data, addr = disc_sock.recvfrom(1024)
            response = data.decode('ascii', errors='ignore')
            
            # Parse VIN from BMWVIN marker
            vin_idx = response.find("BMWVIN")
            vin = response[vin_idx+6:vin_idx+23] if vin_idx >= 0 else None
            
            # Parse MAC from BMWMAC marker
            mac_idx = response.find("BMWMAC")
            mac = response[mac_idx+6:mac_idx+18] if mac_idx >= 0 else None
            
            return {"ip": addr[0], "vin": vin, "mac": mac}
        except socket.timeout:
            raise ConnectionError("No vehicle found on ENET")
        finally:
            disc_sock.close()
    
    def connect(self, car_ip: str):
        """Open TCP connection to ZGW."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock.connect((car_ip, HSFZ_PORT))
        self.car_ip = car_ip
    
    def send_uds(self, target_ecu: int, uds_payload: bytes) -> bytes:
        """Send a UDS message and receive response."""
        # Build HSFZ diagnostic_req_res frame
        payload_len = len(uds_payload)
        hsfz_len = payload_len + 2  # +2 for src/dst bytes
        
        header = struct.pack(">IHBB",
            hsfz_len,           # Length (big-endian uint32)
            TYPE_DIAG_REQ_RES,  # Type
            TESTER_ADDR,        # Source
            target_ecu          # Target
        )
        
        self.sock.sendall(header + uds_payload)
        
        # Read response: first 8 bytes = HSFZ header
        hdr = self._recv_exact(8)
        resp_len, resp_type, resp_src, resp_dst = struct.unpack(">IHBB", hdr)
        
        # Read payload
        payload = self._recv_exact(resp_len - 2)
        
        if resp_type == TYPE_DIAG_REQ_RES:
            return payload
        else:
            raise Exception(f"Unexpected HSFZ response type: 0x{resp_type:04X}")
    
    def alive_check(self):
        """Send transport-layer keep-alive."""
        frame = struct.pack(">IHBB", 2, TYPE_ALIVE_CHECK, TESTER_ADDR, ZGW_ADDR)
        self.sock.sendall(frame)
        # ZGW responds with acknowledge_transfer
    
    def _recv_exact(self, n: int) -> bytes:
        """Receive exactly n bytes."""
        data = b""
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("Connection closed")
            data += chunk
        return data
    
    def close(self):
        if self.sock:
            self.sock.close()


# === Usage Example ===

conn = HSFZConnection()

# 1. Discover
info = conn.discover()
print(f"Found vehicle at {info['ip']}, VIN: {info['vin']}")

# 2. Connect
conn.connect(info['ip'])

# 3. Enter Extended Diagnostic Session
conn.send_uds(ZGW_ADDR, bytes([0x10, 0x03]))  # UDS 10 03

# 4. Read VIN
resp = conn.send_uds(ZGW_ADDR, bytes([0x22, 0xF1, 0x90]))
# resp = 62 F1 90 <17-char VIN>

# 5. Keep alive every 2 seconds
import threading
def keep_alive():
    while True:
        conn.alive_check()
        time.sleep(2.0)
threading.Thread(target=keep_alive, daemon=True).start()

# 6. Send TesterPresent every 2.5s to maintain UDS session
def tester_present():
    while True:
        conn.send_uds(ZGW_ADDR, bytes([0x3E, 0x00]))
        time.sleep(2.5)
threading.Thread(target=tester_present, daemon=True).start()
```

---

## ELM327 AT Commands for HSFZ

Some WiFi adapters expose an ELM327-style AT interface to tunnel HSFZ:

```
AT E1              ← Enable echo
AT H1              ← Enable headers
AT SP E            ← Set protocol to "E" (BMW HSFZ)
AT SH F4           ← Set header to F4 (tester address)
```

Then send raw hex data — the adapter wraps it into HSFZ diagnostic_req_res frames.

---

## DoIP vs HSFZ Quick Reference

| Feature | DoIP (G-series) | HSFZ (F-series) |
|---------|-----------------|-----------------|
| Standard | ISO 13400 | BMW proprietary |
| TCP port | 13400 | 6801 |
| UDP port | 13400 | 6811 |
| Header size | 8 bytes | 8 bytes |
| Addressing | 2-byte logical addr | 1-byte logical addr |
| Routing activation | Required | **Not required** |
| Discovery | Vehicle ID Request/Announce | UDP broadcast `000000000011` |
| Wireshark dissector | Built-in | Needs port config |

---

## Addressing Quick Reference

| ECU | HSFZ Address | DoIP Address |
|-----|-------------|--------------|
| Tester | 0xF4 | 0x0E00 |
| ZGW | 0x10 | 0x0010 |
| DME/DDE | Via ZGW routing | 0x0012 |
| EGS | Via ZGW routing | 0x0018 |
| FEM_BODY / BDC | Via ZGW routing | 0x0040 |
| KOMBI | Via ZGW routing | 0x0060 |
| Headunit | Via ZGW routing | 0x0063 |
| DSC | Via ZGW routing | 0x0029 |

---

## Timing Parameters

| Timer | Value | Description |
|-------|-------|-------------|
| TCP connect timeout | 5000 ms | Connection establishment |
| S3 (session timeout) | 5000 ms | UDS session reverts to default without TesterPresent |
| TesterPresent interval | 2000-3000 ms | Must send before S3 expires |
| Alive check interval | ~2000 ms | Transport-layer heartbeat |
| P2 (response time) | 1000 ms | Max time for ECU to respond |
| P2* (extended) | 2000 ms | Max after Response Pending (0x78) |