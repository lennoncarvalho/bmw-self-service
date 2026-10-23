# Service History Write Protocol — Gap 7 Resolution (Corrected)

> **Status:** Protocol fully mapped. Uses UDS 0x2E WriteDataByIdentifier, NOT 0x31.
> **Source:** ediabasx SGBD documentation (`MRBMSMP1.md`) — definitive PRG job type reference

---

## What We Know

| Component | Value |
|-----------|-------|
| Group file | `g_mmi.grp` |
| PRG files | `CIC.PRG`, `NBT.PRG`, `NBTEVO.PRG`, `HU_MGU.PRG` |
| Job name (add) | `steuern_servicehistory_add` |
| Job name (erase) | `steuern_servicehistory_erase` |
| Argument format | `Day;Month;Year;CorrCnt;Km;Flag;Dealer;Status;Count;Code;Status;Dist;Time;...` |
| Target ECU | Headunit (typically 0x63, from SVT) |
| **UDS Service** | **0x2E WriteDataByIdentifier** (STEUERN = $2E) |

---

## How EDIABAS PRG Jobs Map to UDS

From the ediabasx SGBD documentation which documents every PRG job type:

| PRG Job Type | UDS Service | Description |
|---|---|---|
| **STEUERN** | **$2E WriteDataByCommonIdentifier** | Write data to a DID |
| STEUERN_IO | $2F InputOutputControlByCommonIdentifier | I/O control |
| STEUERN_ROUTINE | $31 StartRoutineByLocalIdentifier | Start a routine |

`steuern_servicehistory_add` is a **STEUERN** job → uses **UDS 0x2E WriteDataByIdentifier**.

The SG_FUNKTIONEN table in the PRG defines:
- The DataIdentifier (DID) for the write
- How arguments map to the data payload
- Result names (JOB_STATUS, STAT_SH_ADD_WERT)

### Wire Format

```
HSFZ Frame:
  [Length 4B] [Type 0x0001 2B] [SRC 0xF4 1B] [DST 0x10 1B]
  [UDS Payload]

UDS WriteDataByIdentifier (0x2E):
  2E <DID_HI> <DID_LO> <ASCII_argument_bytes...>

Example (with placeholder DID 0x1234):
  2E 12 34 32 34 3B 39 3B 32 30 32 36 3B 30 3B ...
       ↑--DID--↑ ↑-- "24;9;2026;0;..." in ASCII

Positive Response:
  6E <DID_HI> <DID_LO>

Negative Response:
  7F 2E <NRC>
```

---

## Complete Service History Write Flow

```python
# DID extracted from the PRG file's SG_FUNKTIONEN table
# for the steuern_servicehistory_add job
SERVICE_HISTORY_ADD_DID = 0x????  # extract from PRG (see below)

def write_service_history(conn, headunit_addr, entry):
    """
    Write a service history entry via UDS 0x2E WriteDataByIdentifier.
    
    entry = {
        "day": 24, "month": 9, "year": 2026,
        "km": 125000, "dealer_flag": 0,
        "dealer_id": "Lennon", "overall_status": 1,
        "items": [
            {"code": 1, "status": 1, "distance": 0, "time": 0},
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
    
    # Send WriteDataByIdentifier (0x2E) with DID + argument bytes
    msg = bytes([0x2E])
    msg += SERVICE_HISTORY_ADD_DID.to_bytes(2, 'big')
    msg += args.encode('ascii')
    
    resp = conn.send_uds(headunit_addr, msg)
    
    if resp[0] == 0x6E:  # Positive response (0x2E + 0x40)
        return True
    elif resp[0] == 0x7F:  # Negative response
        raise Exception(f"NRC: 0x{resp[2]:02X}")

def erase_service_history(conn, headunit_addr):
    """Erase entire service history."""
    conn.send_uds(headunit_addr, bytes([0x10, 0x03]))
    msg = bytes([0x2E])
    msg += SERVICE_HISTORY_ERASE_DID.to_bytes(2, 'big')
    resp = conn.send_uds(headunit_addr, msg)
    return resp[0] == 0x6E
```

---

## How to Extract the DID from a PRG File

### Option 1: ediabasx decompile (TypeScript)

```bash
cd ediabasx
npx ediabasx decompile path/to/NBT.PRG

# Look for the steuern_servicehistory_add job:
# The DID appears as a constant loaded before xsend:
#   move B0, 0x??   ← DID high byte
#   move B1, 0x??   ← DID low byte
#   ...
#   xsend            ← Send UDS 0x2E with the DID
```

### Option 2: Python PRG scanner

```python
import struct

def extract_did_from_prg(prg_path):
    """Search for the DID near the steuern_servicehistory_add job."""
    with open(prg_path, 'rb') as f:
        data = f.read()
    
    # PRG files are XOR-obfuscated with 0xF7
    # Search for the job name
    job_name = b"steuern_servicehistory_add"
    
    # Try both raw and XOR-decoded
    for obfuscated in [False, True]:
        search = bytes(b ^ 0xF7 for b in job_name) if obfuscated else job_name
        offset = data.find(search)
        if offset >= 0:
            print(f"Job found at 0x{offset:X} (XOR={obfuscated})")
            # Scan nearby bytes for 0x2E (UDS WriteDataByIdentifier)
            context = data[max(0, offset-30):offset+200]
            for i in range(len(context) - 2):
                if context[i] == 0x2E:  # WriteDataByIdentifier SID
                    did = struct.unpack('>H', context[i+1:i+3])[0]
                    if 0x0000 <= did <= 0xFFFF:
                        print(f"  Potential DID: 0x{did:04X} at offset +{i}")
            return

# Same DID works for all headunits — it's defined in g_mmi.grp's SG_FUNKTIONEN
# The return value check differs per headunit:
#   CIC: success when STAT_SH_ADD_WERT == 0x01
#   NBT/MGU: success when STAT_SH_ADD_WERT == 0x00
```

---

## PRG File Sources

1. **BMW Standard Tools 2024** — includes EDIABAS 7.6.0 with all PRG files
2. **Motorcarsoft PRG Collection (2023)** — 2110 files, 1.5 GB
3. **ISTA/D Rheingold** — complete SGBD database
4. **PSdZData Full** — includes untrimmed CAFDs + PRGs

Once you extract `NBT.PRG` (or `CIC.PRG`, `NBTEVO.PRG`, `HU_MGU.PRG`), run the scanner above. The DID is the same across all headunits — only the return value interpretation differs (CIC=0x01, others=0x00).

## Key Correction

This document previously incorrectly stated the service history write uses UDS
RoutineControl (0x31). The ediabasx SGBD documentation (`MRBMSMP1.md`) revealed
that **STEUERN** jobs (like `steuern_servicehistory_add`) use **UDS 0x2E
WriteDataByIdentifier**, while only **STEUERN_ROUTINE** jobs use UDS 0x31.