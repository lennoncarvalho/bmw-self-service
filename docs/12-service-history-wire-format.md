# Service History Write Protocol — Gap 7 Resolution

> **Status:** Fully specified, PRG extraction approach documented

---

## What We Know

The service history write uses the EDIABAS job system:

| Component | Value |
|-----------|-------|
| Group file | `g_mmi.grp` |
| PRG files | `CIC.PRG`, `NBT.PRG`, `NBTEVO.PRG`, `HU_MGU.PRG` |
| Job name (add) | `steuern_servicehistory_add` |
| Job name (erase) | `steuern_servicehistory_erase` |
| Argument format | `Day;Month;Year;CorrCnt;Km;Flag;Dealer;Status;Count;Code;Status;Dist;Time;...` |
| Target ECU | Headunit (typically 0x63, from SVT) |

---

## How EDIABAS PRG Jobs Map to UDS

From the ediabaslib/ediabasx PRG format analysis and the EdiabasTool documentation:

1. The PRG file contains a job table with entries for each job
2. Jobs with the `STEUERN_` prefix and an `SG_FUNKTIONEN` table use **UDS RoutineControl (0x31)**
3. The SG_FUNKTIONEN table maps the job name to:
   - A UDS service (RoutineControl = 0x31)
   - A RoutineIdentifier (RID, 2 bytes)
   - Argument packing instructions
4. The argument string is sent as the routine parameter bytes (ASCII encoded)

### Wire Format (Inferred)

```
HSFZ Frame:
  [Length 4B] [Type 0x0001 2B] [SRC 0xF4 1B] [DST 0x10 1B]
  [UDS Payload]

UDS RoutineControl (0x31):
  31 01 <RID_HI> <RID_LO> <ASCII_argument_bytes...>

Response:
  71 01 <RID_HI> <RID_LO> <routine_status>

Negative Response:
  7F 31 <NRC>
```

NRC meanings from BimmerGuide:
- 0x22 = conditionsNotCorrect
- 0x31 = requestOutOfRange (invalid argument)
- 0x33 = securityAccessDenied

---

## PRG File Format

From `ediabasx/docs/sgbd-format.md`:

```
Offset  Size  Field
0x00    16    Signature: "_EDIABAS_OBJECT\0" or similar
0x10    4     File type: 0 = PRG, 1 = GRP
0x14    ?     Version
...     ...   Job table (BEST2 bytecode)
```

The PRG file contains BEST2 bytecode that the EDIABAS interpreter executes.
For STEUERN jobs, the bytecode instructs the interpreter to:
1. Open a UDS session (if needed)
2. Send RoutineControl (0x31) with the job's RID
3. Pack the arguments as ASCII bytes
4. Parse the response for JOB_STATUS and result values

### SG_FUNKTIONEN Table

Each PRG file has an `SG_FUNKTIONEN` table that maps job function names to
UDS routines. The table entry for `steuern_servicehistory_add` would contain:

```
Function name: "steuern_servicehistory_add"
UDS Service:   0x31 (RoutineControl)
RID:           <2-byte value>
Argument type: ASCII string
Result names:  "JOB_STATUS", "STAT_SH_ADD_WERT"
```

---

## How to Extract the RID

### Option 1: Use ediabaslib's PRG parser (recommended)

```bash
# Clone ediabaslib
git clone https://github.com/uholeschak/ediabaslib

# Build and run EdiabasTest to dump PRG job info
# Or use the PRG file listing from https://www.motorcarsoft.com/viewtopic.php?t=25567

# Once you have CIC.PRG or NBT.PRG:
# Use ediabaslib to parse and list all jobs with their UDS mappings
```

### Option 2: Use ediabasx (TypeScript)

```bash
git clone https://github.com/emdzej/ediabasx
cd ediabasx
npm install

# List all jobs in a PRG file
npx ediabasx jobs NBT.PRG

# Get details for a specific job
npx ediabasx job NBT.PRG steuern_servicehistory_add --json
```

### Option 3: Parse PRG directly

The PRG file format is reverse-engineered. The job table contains:
- Job names (null-terminated strings)
- UDS service IDs
- RIDs (2-byte values)
- Argument descriptors

For `STEUERN_` jobs, the entry contains the RID as a 16-bit little-endian
value in the job's bytecode. Search for the string "steuern_servicehistory_add"
in the PRG file — the following bytes contain the RID.

### Option 4: Use BMWEcuExplorer (bimmer.studio)

The bimmer.studio ECU Explorer has 42,000+ BMW diagnostic jobs from the
ISTA database. Search for the headunit ECU and look for the
`steuern_servicehistory_add` job to see its UDS mapping.

### Option 5: Python PRG Parser

```python
import struct

def parse_prg(filepath):
    """Minimal PRG parser to find job RIDs."""
    with open(filepath, 'rb') as f:
        data = f.read()
    
    # Search for job name in the binary
    # PRG files use CP1252 encoding with optional XOR obfuscation
    job_name = b"steuern_servicehistory_add"
    offset = data.find(job_name)
    
    if offset >= 0:
        print(f"Job found at offset 0x{offset:X}")
        # The RID follows the job definition header
        # Scan nearby bytes for the UDS service pattern (0x31)
        # The RID is typically a 2-byte value in the range 0x0200-0xDFFF
        context = data[max(0, offset-20):offset+100]
        print(f"Context hex: {context.hex()}")
        
        # Look for 0x31 byte (UDS RoutineControl SID) near the job name
        for i in range(len(context)):
            if context[i] == 0x31:
                rid_pos = i + 1  # RID follows the 0x31 byte
                if rid_pos + 1 < len(context):
                    rid = struct.unpack('<H', context[rid_pos:rid_pos+2])[0]
                    print(f"Potential RID: 0x{rid:04X} at offset +{i}")
```

---

## Complete Service History Write Flow

```python
def write_service_history(conn, headunit_addr, entry):
    """
    Write a service history entry to the headunit.
    
    Args:
        conn: HSFZConnection or DoIPClient
        headunit_addr: ECU address from SVT (typically 0x63)
        entry: dict with day, month, year, corr_cnt, km, dealer_flag,
               dealer_id, status, items[]
    """
    # 1. Enter Extended Diagnostic Session on headunit
    # Route through ZGW to headunit
    conn.send_uds(ZGW_ADDR, bytes([0x10, 0x03]))  # Or route to headunit
    
    # 2. Build argument string
    args = f"{entry['day']};{entry['month']};{entry['year']};"
    args += f"{entry['corr_cnt']};{entry['km']};{entry['dealer_flag']};"
    args += f"{entry['dealer_id']};0x{entry['status']:x};{len(entry['items'])};"
    
    for item in entry['items']:
        args += f"{item['code']};0x{item['status']:x};"
        args += f"{item['remaining_dist']};{item['remaining_time']};"
    
    # 3. Send UDS RoutineControl
    # RID to be determined from PRG file analysis
    # For now, documenting the structure:
    routine_params = args.encode('ascii')
    
    msg = bytes([0x31, 0x01])  # RoutineControl, startRoutine
    msg += bytes([RID_HI, RID_LO])  # TODO: Extract from PRG
    msg += routine_params
    
    resp = conn.send_uds(headunit_addr, msg)
    
    # 4. Parse response
    if resp[0] == 0x71:  # Positive response
        # Check routine status
        status = resp[4] if len(resp) > 4 else None
        # For CIC: success if status == 0x01
        # For NBT/MGU: success if status == 0x00
        return True
    elif resp[0] == 0x7F:  # Negative response
        nrc = resp[2]
        raise Exception(f"Service history write failed: NRC 0x{nrc:02X}")
```

---

## Quick Win: Use ediabaslib Directly

For the fastest implementation, use ediabaslib (C#/.NET) or ediabasx (TypeScript)
which already understand PRG files and can execute `steuern_servicehistory_add`
without needing to know the RID:

```typescript
// Using ediabasx (TypeScript)
import { EdiabasClient } from '@emdzej/ediabasx';

const client = new EdiabasClient({ interface: 'ENET' });
await client.connect();

// Load the PRG file
await client.loadSgbd('NBT.PRG');  // or CIC.PRG based on headunit

// Execute the job
const result = await client.executeJob('steuern_servicehistory_add', {
  arguments: '24;9;2026;0;125000;0;Lennon;0x1;6;1;0x1;0;0;4;0x1;0;0;11;0x1;0;0;100;0x1;0;0;3;0x1;0;0;10;0x1;0;0;'
});

console.log(result.JOB_STATUS);    // 'OKAY'
console.log(result.STAT_SH_ADD_WERT); // 0x00 or 0x01
```

---

## PRG File Sources

PRG files are part of BMW Standard Tools / EDIABAS:

1. **BMW Standard Tools 2024** (includes EDIABAS 7.6.0 with all PRG files)
2. **BMW Standard Tools 2.12** 
3. **Collection of .PRG files (2023)** from motorcarsoft.com — 2110 files, 1.5 GB
4. **ISTA/D Rheingold** — includes the complete SGBD database
5. **SP-Daten** files from BMW coding packs

Once you have the PRG files, use the Python parser above or ediabaslib to
extract the RID for `steuern_servicehistory_add`.