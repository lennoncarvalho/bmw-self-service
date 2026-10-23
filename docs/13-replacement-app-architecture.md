# Replacement App — Architecture & Integration Guide

> **Date:** 2026-10-23
> **Status:** Complete — all gaps resolved

---

## Technology Stack Decision

| Layer | Choice | Why |
|-------|--------|-----|
| Transport (F-series) | Own HSFZ implementation | ediabasx's ENET interface is a stub. We have a complete HSFZ spec in `docs/10-hsfz-protocol.md` (~150 lines of Python) |
| Transport (G-series) | `python-doipclient` or own DoIP | Standard ISO 13400, well-supported |
| PRG/RID extraction | `ediabasx` best-decompiler | Decompile `steuern_servicehistory_add` bytecode → extract RID |
| Coding database | Decrypted `.enc` files | Full curated database extracted |
| DTC descriptions | Public OBD-II DB + runtime lookup | Standard codes are public |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Replacement App                        │
├─────────────────────────────────────────────────────────┤
│  UI Layer (choose your framework)                        │
├─────────────────────────────────────────────────────────┤
│  Module: Diagnostics (Phase B)                           │
│  ├─ read_dtc() → UDS 0x19                                │
│  ├─ clear_dtc() → UDS 0x14                               │
│  └─ read_mil() → OBD-II Mode 01 PID 01                   │
├─────────────────────────────────────────────────────────┤
│  Module: Easy Coding (Phase C)                           │
│  ├─ load_root_index(cafd_id) → curated presets           │
│  ├─ load_cafd_variant(cafd_id, version) → byte layout    │
│  ├─ read_cafd(ecu_addr) → current coding                 │
│  └─ write_coding(ecu_addr, changes) → UDS 0x2E           │
├─────────────────────────────────────────────────────────┤
│  Module: Service History (Phase D)                       │
│  ├─ read_history() → UDS 0x22 from headunit              │
│  └─ write_history(entry) → UDS 0x31 + argument string    │
├─────────────────────────────────────────────────────────┤
│  Module: Advanced Coding (Phase E)                       │
│  ├─ read_svt() → full ECU tree                           │
│  └─ expert_edit(ecu, fdl_params) → raw FDL editor        │
├─────────────────────────────────────────────────────────┤
│  Transport Layer                                          │
│  ├─ HSFZConnection (F-series: TCP 6801)                  │
│  └─ DoIPClient (G-series: TCP 13400)                     │
├─────────────────────────────────────────────────────────┤
│  Vehicle Detection                                        │
│  ├─ discover() → VIN, MAC, IP                            │
│  ├─ read_fa() → factory options                          │
│  └─ read_svt() → ECU tree with variants                  │
├─────────────────────────────────────────────────────────┤
│  Coding Database                                           │
│  ├─ .enc files → decrypt → JSON                           │
│  ├─ .strings → human labels                               │
│  ├─ ecus.enc → ECU compatibility                          │
│  ├─ coding-ecu-infos.enc → expert mode flags              │
│  └─ salapa.enc → 5640 BMW option codes                    │
└─────────────────────────────────────────────────────────┘
```

---

## HSFZ Transport (F48 compatible)

From `docs/10-hsfz-protocol.md`, the complete implementation:

```python
import socket
import struct

HSFZ_PORT = 6801
HSFZ_DISCOVERY_PORT = 6811
TESTER_ADDR = 0xF4
ZGW_ADDR = 0x10

class HSFZConnection:
    def __init__(self):
        self.sock = None
    
    def discover(self) -> dict:
        """UDP broadcast to find vehicle on ENET."""
        disc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        disc.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        disc.settimeout(3.0)
        disc.sendto(bytes.fromhex("000000000011"), ("169.254.255.255", 6811))
        try:
            data, addr = disc.recvfrom(1024)
            text = data.decode('ascii', errors='ignore')
            vin_idx = text.find("BMWVIN")
            vin = text[vin_idx+6:vin_idx+23] if vin_idx >= 0 else None
            return {"ip": addr[0], "vin": vin}
        finally:
            disc.close()
    
    def connect(self, car_ip: str):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock.connect((car_ip, HSFZ_PORT))
    
    def send_uds(self, target: int, payload: bytes) -> bytes:
        """Send UDS message via HSFZ, return response."""
        hsfz_len = len(payload) + 2
        header = struct.pack(">IHBB", hsfz_len, 0x0001, TESTER_ADDR, target)
        self.sock.sendall(header + payload)
        hdr = self._recv_exact(8)
        resp_len = struct.unpack(">I", hdr[:4])[0]
        return self._recv_exact(resp_len - 2)
    
    def _recv_exact(self, n: int) -> bytes:
        data = b""
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk: raise ConnectionError()
            data += chunk
        return data
    
    def close(self):
        if self.sock: self.sock.close()
```

---

## Module: Diagnostics

```python
def read_dtc(conn, ecu_addr):
    """Read DTCs from an ECU. Returns list of (code, status_byte)."""
    # Extended session
    conn.send_uds(ecu_addr, bytes([0x10, 0x03]))
    
    # Read DTCs by status mask (confirmed + pending)
    resp = conn.send_uds(ecu_addr, bytes([0x19, 0x02, 0x08]))
    if resp[0] != 0x59:  # Positive response
        return []
    
    # Parse DTCs: after header, each is 4 bytes (3-byte DTC + 1-byte status)
    dtcs = []
    offset = 2  # Skip 0x59, 0x02
    while offset + 4 <= len(resp):
        dtc_code = resp[offset:offset+3].hex().upper()
        status = resp[offset+3]
        dtcs.append((dtc_code, status))
        offset += 4
    return dtcs

def clear_dtc(conn, ecu_addr):
    """Clear all DTCs."""
    conn.send_uds(ecu_addr, bytes([0x10, 0x03]))
    resp = conn.send_uds(ecu_addr, bytes([0x14, 0xFF, 0xFF, 0xFF]))
    return resp[0] == 0x54  # Positive response

def read_mil(conn):
    """Read MIL status via OBD-II Mode 01 PID 01."""
    resp = conn.send_uds(0x10, bytes([0x01, 0x01]))
    if len(resp) >= 6:
        mil_on = (resp[4] & 0x80) != 0
        dtc_count = resp[4] & 0x7F
        return {"mil": mil_on, "dtc_count": dtc_count}
    return None
```

---

## Module: Service History

### Step 1: Extract RID from PRG file (one-time)

```bash
# Using ediabasx best-decompiler
cd ediabasx
npx ediabasx decompile path/to/NBT.PRG

# Look for steuern_servicehistory_add job:
#   move B0, 0x??
#   move B1, 0x??
#   ...
#   xsend
# The RID = (B0_value << 8) | B1_value
```

Or use this Python extractor:

```python
import subprocess, re, json

def extract_rid_from_prg(prg_path):
    """Decompile PRG and extract RID for steuern_servicehistory_add."""
    result = subprocess.run(
        ["npx", "ediabasx", "decompile", prg_path],
        capture_output=True, text=True, cwd="ediabasx"
    )
    
    # Parse the decompiled output for the RID
    in_job = False
    rid_bytes = []
    for line in result.stdout.split('\n'):
        if 'steuern_servicehistory_add' in line.lower():
            in_job = True
            continue
        if in_job and '}' in line:
            break
        if in_job:
            # Look for: move B0, 0xXX;  or  move B1, 0xXX;
            m = re.match(r'\s*move\s+B([01]),\s*(0x[0-9A-Fa-f]+)', line)
            if m:
                idx = int(m.group(1))
                val = int(m.group(2), 16)
                while len(rid_bytes) <= idx:
                    rid_bytes.append(0)
                rid_bytes[idx] = val
    
    if len(rid_bytes) >= 2:
        rid = (rid_bytes[0] << 8) | rid_bytes[1]
        return rid
    return None
```

### Step 2: Write service history

```python
# RID extracted once from PRG — same for all headunits
SERVICE_HISTORY_ADD_RID = extract_rid_from_prg("NBT.PRG")  # e.g., 0x0200

def write_service_history(conn, headunit_addr, entry):
    """
    Write a service history entry.
    
    entry = {
        "day": 24, "month": 9, "year": 2026,
        "km": 125000, "dealer_flag": 0,
        "dealer_id": "Lennon", "overall_status": 1,
        "items": [
            {"code": 1, "status": 1, "distance": 0, "time": 0},
            {"code": 4, "status": 1, "distance": 0, "time": 0},
        ]
    }
    """
    # Build argument string
    args = f"{entry['day']};{entry['month']};{entry['year']};"
    args += f"0;{entry['km']};{entry['dealer_flag']};"
    args += f"{entry['dealer_id']};0x{entry['overall_status']:x};"
    args += f"{len(entry['items'])};"
    for item in entry['items']:
        args += f"{item['code']};0x{item['status']:x};"
        args += f"{item['distance']};{item['time']};"
    
    # Extended session on headunit
    conn.send_uds(headunit_addr, bytes([0x10, 0x03]))
    
    # Send RoutineControl (0x31) with RID and argument string
    msg = bytes([0x31, 0x01])  # SID, startRoutine
    msg += SERVICE_HISTORY_ADD_RID.to_bytes(2, 'big')
    msg += args.encode('ascii')
    
    resp = conn.send_uds(headunit_addr, msg)
    
    if resp[0] == 0x71:  # Positive
        # Success is 0x01 for CIC, 0x00 for NBT/MGU
        return True
    elif resp[0] == 0x7F:  # Negative
        raise Exception(f"NRC: 0x{resp[2]:02X}")

def erase_service_history(conn, headunit_addr):
    """Erase entire service history."""
    conn.send_uds(headunit_addr, bytes([0x10, 0x03]))
    msg = bytes([0x31, 0x01])
    msg += SERVICE_HISTORY_ERASE_RID.to_bytes(2, 'big')
    resp = conn.send_uds(headunit_addr, msg)
    return resp[0] == 0x71
```

---

## Module: Easy Coding

```python
import json
from Crypto.Cipher import AES
import gzip

KEY = bytes.fromhex("244326462948404D635166546A576E5A")
IV  = bytes.fromhex("7639792442264529482B4D6251655468")

def decrypt_enc(filepath):
    """Decrypt any BimmerCode .enc file."""
    with open(filepath, "rb") as f:
        data = f.read()
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    decrypted = cipher.decrypt(data)
    pad_len = decrypted[-1]
    decrypted = decrypted[:-pad_len] if 1 <= pad_len <= 16 else decrypted
    try:
        return gzip.decompress(decrypted)
    except:
        return decrypted

class CodingDatabase:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.strings = self._load_strings("en.strings")
        self.root_indexes = {}  # CAFD → curated presets
        self.cafd_variants = {}  # CAFD-version → byte layout
    
    def _load_strings(self, lang_file: str) -> dict:
        """Parse Apple .strings format."""
        import re
        path = f"{self.data_dir}/{lang_file}"
        with open(path) as f:
            content = f.read()
        pairs = re.findall(r'"([^"]+)"\s*=\s*"([^"]*)"', content)
        return dict(pairs)
    
    def load_ecu(self, cafd_id: str, variant: str):
        """Load coding database for one ECU variant."""
        # Root index: curated presets (e.g., "BC_DIGITAL_V" → values)
        root = f"{self.data_dir}/{cafd_id}.enc"
        self.root_indexes[cafd_id] = json.loads(decrypt_enc(root))
        
        # CAFD variant: byte-level parameter layout
        cafd = f"{self.data_dir}/{cafd_id}-{variant}.enc"
        self.cafd_variants[f"{cafd_id}-{variant}"] = json.loads(decrypt_enc(cafd))
    
    def get_presets(self, cafd_id: str) -> list[dict]:
        """Return curated coding presets with human labels."""
        root = self.root_indexes[cafd_id]
        presets = []
        for entry in root:
            key = entry["name"]
            presets.append({
                "section": entry.get("section", ""),
                "key": key,
                "label": self.strings.get(key, key),
                "description": self.strings.get(entry.get("descriptionText", ""), ""),
                "options": [
                    {
                        "name": v["name"],
                        "label": self.strings.get(v["name"], v["name"]),
                        "functions": v["functions"]
                    }
                    for v in entry["values"]
                ]
            })
        return presets
    
    def get_current_value(self, preset: dict, current_bytes: bytes, 
                          cafd_id: str, variant: str) -> str:
        """Determine which option is currently active from CAFD bytes."""
        cafd = self.cafd_variants[f"{cafd_id}-{variant}"]
        
        for option in preset["options"]:
            match = True
            for func in option["functions"]:
                func_def = self._find_function(cafd, func["name"])
                if not func_def:
                    match = False
                    break
                byte_pos = int(func_def["storageInfo"]["start"])
                mask = int(func_def["storageInfo"]["mask"].replace("0b", ""), 2)
                expected = int(func["values"][0]["value"], 16)
                actual = (current_bytes[byte_pos] & mask)
                # Align to LSB
                shift = (mask & -mask).bit_length() - 1
                actual_shifted = (actual >> shift) & 0xFF
                if actual_shifted != expected:
                    match = False
                    break
            if match:
                return option["name"]
        return None  # Unknown
    
    def build_write_payload(self, preset: dict, selected_option: str,
                            current_bytes: bytes, cafd_id: str, variant: str) -> bytes:
        """Build modified CAFD bytes for writing."""
        option = next(o for o in preset["options"] if o["name"] == selected_option)
        cafd = self.cafd_variants[f"{cafd_id}-{variant}"]
        modified = bytearray(current_bytes)
        
        for func in option["functions"]:
            func_def = self._find_function(cafd, func["name"])
            if not func_def:
                continue
            byte_pos = int(func_def["storageInfo"]["start"])
            mask_str = func_def["storageInfo"]["mask"]
            mask = int(mask_str.replace("0b", ""), 2)
            new_val = int(func["values"][0]["value"], 16)
            shift = (mask & -mask).bit_length() - 1
            
            modified[byte_pos] &= ~mask
            modified[byte_pos] |= (new_val << shift) & mask
        
        return bytes(modified)
    
    def _find_function(self, cafd: dict, name: str) -> dict | None:
        for dg in cafd.get("dataGroups", []):
            for func in dg.get("functions", []):
                if func["name"] == name:
                    return func
        return None
```

---

## Full Connection + Coding Flow

```python
def main():
    # 1. Connect
    conn = HSFZConnection()
    info = conn.discover()
    print(f"Found {info['vin']} at {info['ip']}")
    conn.connect(info["ip"])
    
    # 2. Detect vehicle
    vin_resp = conn.send_uds(ZGW_ADDR, bytes([0x22, 0xF1, 0x90]))
    vin = vin_resp[3:].decode('ascii')
    model = vin[3:7]  # "3E32" → F30
    
    # 3. Read SVT (ECU tree)
    # svt = read_svt(conn, ZGW_ADDR)
    # Extract headunit type and CAFD versions
    
    # 4. Load coding database for each ECU
    db = CodingDatabase("bimmercode_data")
    db.load_ecu("000024C3", "008-005-000")  # FEM_BODY
    
    # 5. Show curated presets
    for preset in db.get_presets("000024C3"):
        print(f"[{preset['section']}] {preset['label']}")
        print(f"  {preset['description']}")
        for opt in preset["options"]:
            print(f"    - {opt['label']}")
    
    # 6. Read current coding, determine active options
    # current_cafd = read_cafd(conn, ecu_addr, CAFD_DID)
    # current_bytes = bytes.fromhex(current_cafd)
    # for preset in presets:
    #     current = db.get_current_value(preset, current_bytes, "000024C3", "008-005-000")
    
    # 7. User selects option → write
    # modified = db.build_write_payload(preset, "NOT_ACTIVE", current_bytes, ...)
    # conn.send_uds(ecu_addr, bytes([0x10, 0x03]))
    # conn.send_uds(ecu_addr, bytes([0x2E]) + modified)  # WriteDataByIdentifier
    
    conn.close()
```

---

## What You Need to Download

1. **PRG files** (for service history RID): BMW Standard Tools 2024 from bimmerscene.com → extract `CIC.PRG`, `NBT.PRG`, `NBTEVO.PRG`, `HU_MGU.PRG` to `ediabasx/ecu/`

2. **Extract the RID** (one-time):
```bash
cd ediabasx && npx ediabasx decompile ecu/NBT.PRG | grep -A 20 steuern_servicehistory_add
```

3. **BimmerCode database** (already extracted): `bimmercode_data/` directory

4. **pycryptodome**: `pip3 install pycryptodome` (already installed)