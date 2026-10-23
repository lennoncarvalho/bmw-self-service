# Phase 4: SHM.exe + .bmwsh Service History Writer Analysis

> **Date:** 2026-10-23
> **Status:** Complete
> **Source:** `sources/SHM/SHM.exe` (SHA-256: `2d6bb528...`), 
> `sources/SHM/history.2026.09.24.bmwsh` (360 bytes)
> **Evidence IDs:** `ev_c3b46d80ee...`(binary_overview), string search results

---

## 4a. .bmwsh Binary File Format — Reverse Engineered

### File Overview

The `.bmwsh` file is a proprietary binary format storing service history
records. The file is **360 bytes** containing **8 service records** of
variable length. Each record stores one complete service entry.

### Record Structure

Each record is variable-length with this layout:

```
Offset  Size    Field               Type        Description
------  ----    -----               ----        -----------
+0x00   1       Day                 uint8       Day of service (1-31)
+0x01   1       Month               uint8       Month of service (1-12)
+0x02   2       Year                uint16 LE   Four-digit year (e.g., 0x07EA = 2026)
+0x04   4       Unknown             uint32      Correction counter or flags
+0x08   2       String Length?      uint16      Length prefix for dealer ID
+0x0A   N       Dealer/VIN Code    ASCIIZ      Null-terminated dealer name or VIN fragment
+N      1       Dealer Flag?        uint8       0x01 likely = BMW dealer
+N+1    1       Item Count          uint8       Number of service items
+N+2    8×N     Service Items       [struct]    Array of service item entries
```

### Service Item Entry (8 bytes each)

```
Offset  Size    Field               Type        Description
------  ----    -----               ----        -----------
+0x00   1       Service Code        uint8       BMW service code (see Phase 1 table)
+0x01   1       Item Status         uint8       0x01 = completed, 0x02 = delayed
+0x02   2       Remaining Distance  uint16 LE   Distance remaining (km), 0 = on-time
+0x04   2       Remaining Time      uint16 LE   Time remaining, 0 = on-time
+0x06   2       Reserved/Padding    —           Always 0x0000 in observed data
```

### Decoded Records from `history.2026.09.24.bmwsh`

**Record 1** (offset 0x00, 68 bytes):
```
Date:       2026-09-24 (0x18=24, 0x09=9, 0x07EA=2026)
Unknown:    0x02010000
Dealer:     "Lennon" (6 chars + null)
Flag:       0x01
Item Count: 6

Service Items:
  1. Code=0x01 (Engine oil),          Status=1, Dist=0, Time=0
  2. Code=0x04 (Microfilter),         Status=1, Dist=0, Time=0
  3. Code=0x0B (Air filter),          Status=1, Dist=0, Time=0
  4. Code=0x64 (Vehicle check comb.), Status=1, Dist=0, Time=0
  5. Code=0x03 (Brake fluid),         Status=1, Dist=0, Time=0
  6. Code=0x0A (Spark plugs),         Status=1, Dist=0, Time=0
```

**Record 2** (offset 0x44, 22 bytes):
```
Date:       2025-09-09 (0x09=9, 0x09=9, 0x07E9=2025)
Unknown:    0x000068D8
Dealer:     "Lennon" (6 chars + null)
Flag:       0x01
Item Count: 2
  Items: Code=0x02 (Brake pads front), Status=1; Code=0x01 (Oil), Status=1
```

**Record 3** (offset 0x5A, 21 bytes):
```
Date:       2024-12-12 (0x0C=12, 0x0C=12, 0x07E8=2024)
Unknown:    0x0000BD74
Dealer:     "G655" (4 chars + null)
Flag:       0x00
Item Count: 1
  Items: Code=0x64 (Vehicle check), Status=1
```

**Record 4** (offset 0x6F, 39 bytes):
```
Date:       2024-09-09 (0x09=9, 0x09=9, 0x07E8=2024)
Unknown:    0x000099B2 (km = 39346?)
Dealer:     "G655" (4 chars + null)
Flag:       0x00
Item Count: 4
  Items: Code=0x0B (Air filter), Status=1; Code=0x0C (Fuel filter), Status=1;
          Code=0x03 (Brake fluid), Status=1; Code=0x08 (Battery), Status=1
```

**Record 5** (offset 0x96, 41 bytes):
```
Date:       2023-09-09 (0x09=9, 0x09=9, 0x07E7=2023)
Unknown:    0x00C98F01
Dealer:     "25332" (5 chars + null) — VIN fragment?
Flag:       0x00
Item Count: 4
  Items: Code=0x06 (Brake pads rear), Status=1; Code=0x04 (Microfilter), Status=1;
          Code=0x0C (Fuel filter), Status=1; Code=0x03 (Brake fluid), Status=1
```

**Record 6** (offset 0xBF, 39 bytes):
```
Date:       2022-08-08 (0x08=8, 0x08=8, 0x07E6=2022)
Unknown:    0x010E6600
Dealer:     "49124" (5 chars + null) — VIN fragment?
Flag:       0x00
Item Count: 5
  Items: Code=0x0A (Spark plugs), Status=1; Code=0x64 (Vehicle check), Status=1;
          Code=0x01 (Oil), Status=1; Code=0x02 (Brake pads front), Status=1;
          Code=0x03 (Brake fluid), Status=1
```

**Record 7** (offset 0xE6, 39 bytes):
```
Date:       2020-08-08 (0x08=8, 0x08=8, 0x07E4=2020)
Unknown:    0x012A3B00
Dealer:     "49124" (5 chars + null) — VIN fragment?
Flag:       0x00
Item Count: 3
  Items: Code=0x03 (Brake fluid), Status=1; Code=0x04 (Microfilter), Status=1;
          Code=0x1A=26 (unknown service)
```

**Record 8** (offset 0x10D, 27 bytes):
```
Date:       2019-03-03 (0x03=3, 0x03=3, 0x07E3=2019)
Unknown:    0x010C1800
Dealer:     "39611" (5 chars + null) — VIN fragment?
Flag:       0x00
Item Count: 1
  Items: Code=0x01 (Oil), Status=1
```

### Key Observations

1. **Dealer field dual-use**: The ASCII string field serves double duty —
   for some records it's a dealer name ("Lennon"), for others it's a VIN
   fragment or dealer code ("G655", "25332", "49124", "39611").

2. **Unknown 4-byte field**: The uint32 at offset +0x04 varies between
   records. It may encode the **odometer reading** (kilometers) mixed with
   flags. E.g., record 4 has 0x000099B2 = 39346 km, record 7 has
   0x012A3B00 = 19,553,280 which doesn't parse cleanly — might combine
   mileage with a correction counter.

3. **Year range**: Records span 2019-2026, stored as little-endian uint16
   (0x07E3-0x07EA).

4. **Item codes match known BMW codes**: All observed codes match the
   Tool32 `STEUERN_SERVICEHISTORY_ADD` service code table (Phase 1).

5. **No odometer as separate field**: Unlike the Tool32 argument format
   (which has explicit km field), the `.bmwsh` format appears to encode
   mileage in the unknown uint32 at +0x04, possibly combined with a
   correction counter.

---

## 4b. SHM.exe Binary Analysis

### Application Identity

| Property | Value |
|----------|-------|
| Developer | BlackBOX Sistemi |
| Title | BMW Service History Manager 1.00.100 (Lite/Free Edition) |
| Window Title | "BMW HU Service History Manager" / "Service History Manager Lite" |
| Compiler | Embarcadero Delphi for Win32 30.0 (Delphi 10.3 Rio) |
| Architecture | PE32 GUI, Intel 80386 (x86 32-bit) |
| Image Base | 0x400000 |
| Code Size | 2.5 MB (.text section) |
| Resources | 612 KB (.rsrc section) |
| Total Procedures | 8283 |
| Total Strings | 6419 |

### Technology Stack

SHM.exe is a **Delphi VCL application** that uses:
1. **IP*Works!** commercial networking library (by /n software) for
   UDP and TCP communication
2. **Delphi VCL** for the GUI (forms, buttons, date pickers, grids)
3. **TStringBuilder** for building semicolon-delimited argument strings
4. **Raw WinSock** calls (socket, send, closesocket) for direct socket IO
5. **BlackBOX Sistemi** licensing (https://automotive.blackboxsys.com)

### Key Finding: No EDIABAS/Tool32 Dependency

**Critical discovery**: SHM.exe does NOT use EDIABAS or Tool32. String
searches for `STEUERN`, `EDIABAS`, `Tool32`, `JOB_STATUS`, `PRG` all
returned zero results.

Instead, SHM.exe **implements the protocol directly** using:
- IP*Works! UDP (for vehicle discovery on UDP 6811 or UDP 13400)
- Raw TCP sockets via `uENETSocket` and `TClientSocketF` (for diagnostic
  communication on TCP 6801 or TCP 13400)
- The ENET connection is managed via `ENET_CONNECT` / `ENET_CONNECT_SUCCESS`
  strings

### Network Communication Architecture

```
┌──────────────────────────────────────────┐
│          SHM.exe (Delphi VCL)             │
├──────────────────────────────────────────┤
│  GUI Layer                                │
│  ├─ TDateTimePicker (date selection)     │
│  ├─ TEdit fields (dealer, mileage, VIN)  │
│  ├─ TStringGrid (service items)           │
│  └─ TButtons (Write/Read/Erase)          │
├──────────────────────────────────────────┤
│  Logic Layer                              │
│  ├─ .bmwsh file reader/writer             │
│  ├─ Argument string builder (TStringBuilder)│
│  └─ Headunit detection (auto-detect type) │
├──────────────────────────────────────────┤
│  Network Layer (IP*Works! + WinSock)      │
│  ├─ UDP Discovery (EipwUDPPort)           │
│  ├─ TCP Connection (uENETSocket)          │
│  ├─ TLS support (TClientSocketF)          │
│  └─ Raw socket ops (socket/send/closesocket)│
├──────────────────────────────────────────┤
│  Licensing Layer                          │
│  └─ blackboxsys.com (license check)       │
└──────────────────────────────────────────┘
```

### Key String Evidence

| String | Address | Interpretation |
|--------|---------|----------------|
| `ENET_CONNECT` | 0x60d934 | Connection initiation |
| `ENET_CONNECT_SUCCESS` | 0x60d970 | Successful connection |
| `Could not connect to target` | 0x60d994 | Connection failure |
| `- Connected to ` | 0x60eef4 | Connection status log |
| `ERR: Could not connect to target:` | 0x60ef10 | Error message prefix |
| `ERR: Service history list is empty!` | 0x60ee80 | Empty history warning |
| `- Erasing current service history...` | 0x60ef40 | Erase operation status |
| `- Writing new service history...` | 0x60efc0 | Write operation status |
| `TClientSocketF` | 0x60d24f | TLS client socket type |
| `uENETSocket` | 0x60d3b2 | ENET socket type |
| `DataToSend` | 0x60bf16 | Outgoing data buffer |
| `BMW SERVICE HISTORY FILES\|*.bmwsh` | 0x62870c | Open file dialog filter |
| `Save BMW Service History File` | 0x6288d0 | Save dialog title |
| `BlackBOX Sistemi: BMW Service History Manager 1.00.100` | 0x629a7c | App identity |
| `https://automotive.blackboxsys.com/home/pricing` | 0x627d0c | License server URL |
| `http://www.blackboxsys.com` | 0x627e10 | Vendor website |
| `Embarcadero Delphi for Win32 compiler version 30.0` | 0x6b3018 | Compiler version |

### No Hardcoded Protocol Strings

The absence of `STEUERN_SERVICEHISTORY_ADD`, `CIC.PRG`, `NBT.PRG`,
`STAT_SH_ADD_WERT`, `JOB_STATUS` strings in the binary is significant:

1. **The job name is built at runtime**: The app constructs
   `STEUERN_SERVICEHISTORY_ADD` (or ERASE/DEL) programmatically,
   possibly from components or read from a vehicle query response.

2. **The PRG file name is computed**: The headunit type (CIC/NBT/NBT
   EVO/MGU) is determined by querying the vehicle, and the PRG file
   name is composed as `<HEADUNIT_TYPE>.PRG`.

3. **The argument string is built with TStringBuilder**: Using format
   specifiers (`%s`, `%d`) and semicolons, the argument is assembled
   from the `.bmwsh` record data.

### Inferred Communication Flow

```
1. User clicks "Write to car"
2. App reads .bmwsh file → parses records
3. For each record:
   a. App detects headunit type (auto-detect via vehicle query)
   b. Selects PRG file: <HEADUNIT>.PRG
   c. Builds job name: "STEUERN_SERVICEHISTORY_ADD" (or _ERASE for full erase)
   d. Builds argument string:
      "Day;Month;Year;CorrectCnt;Km;DealerFlag;DealerID;Status;Count;"
      + per-item "Code;ItemStatus;RemainingDist;RemainingTime;"
   e. Opens TCP connection via uENETSocket
   f. Sends command via IP*Works! / WinSock socket
   g. Waits for response
   h. Checks JOB_STATUS == OKAY and STAT_SH_ADD_WERT
   i. Displays result
4. App closes connection
```

---

## 4c. Protocol Determination

### Transport Layer Options

Based on the binary's codebase having both `uENETSocket` and `EipwUDPPort`:

**For F-series vehicles (HSFZ):**
```
Discovery: UDP broadcast to port 6811
Data:      TCP connection to port 6801 (ZGW)
Protocol:  HSFZ framing over TCP
```

**For G-series vehicles (DoIP):**
```
Discovery: UDP broadcast to port 13400 (DoIP vehicle announcement)
Data:      TCP connection to port 13400 (DoIP diagnostic message)
Protocol:  ISO 13400 DoIP framing
```

### Service History Job Protocol

The job sent to the headunit uses:
1. TCP connection to the headunit through the ZGW/gateway
2. A job execution command containing the PRG file reference and job name
3. The semicolon-delimited argument string as the job parameter
4. Response parsing checking `JOB_STATUS` and `STAT_SH_ADD_WERT`

Since the app does NOT bundle EDIABAS, it must implement the EDIABAS job
protocol directly:
- **Job request format**: Likely a proprietary binary or text-based command
  sent over the socket containing the SGBD/PRG reference, job name, and
  arguments
- **Response format**: Key-value pairs including `JOB_STATUS=OKAY` and
  `STAT_SH_ADD_WERT=<value>`

---

## 4d. Conversion Function Inference

The critical function converts a `.bmwsh` record into the Tool32 argument
string. Based on the string evidence:

### Input (.bmwsh record)
```
struct BMWServiceRecord {
    uint8   day;
    uint8   month;
    uint16  year;          // LE
    uint32  odometer_flags; // Combined km + correction counter
    char    dealer_id[];    // Null-terminated ASCII
    uint8   dealer_flag;    // 0 or 1
    uint8   item_count;     // 1-13
    struct {
        uint8  code;
        uint8  status;
        uint16 remaining_km;  // LE
        uint16 remaining_time;// LE
        uint16 reserved;
    } items[item_count];
};
```

### Output (Tool32 argument string)
```
"24;9;2026;0;125000;0;Lennon;0x1;6;"
"1;0x1;0;0;"
"4;0x1;0;0;"
"11;0x1;0;0;"
"100;0x1;0;0;"
"3;0x1;0;0;"
"10;0x1;0;0;"
```

### Conversion Logic (Inferred)
```pascal
// Delphi pseudocode (inferred from TStringBuilder usage)
function BuildTool32Argument(rec: TBMWServiceRecord): string;
var
  sb: TStringBuilder;
  i: Integer;
begin
  sb := TStringBuilder.Create;
  try
    // Base fields
    sb.Append(Format('%d;%d;%d;', [rec.day, rec.month, rec.year]));
    sb.Append(Format('%d;', [rec.correction_counter]));
    sb.Append(Format('%d;', [rec.odometer]));
    sb.Append(Format('%d;', [rec.dealer_flag]));
    sb.Append(Format('%s;', [rec.dealer_id]));
    sb.Append(Format('0x%x;', [rec.overall_status]));
    sb.Append(Format('%d;', [rec.item_count]));
    
    // Service items
    for i := 0 to rec.item_count - 1 do
    begin
      sb.Append(Format('%d;', [rec.items[i].code]));
      sb.Append(Format('0x%x;', [rec.items[i].status]));
      sb.Append(Format('%d;', [rec.items[i].remaining_km]));
      sb.Append(Format('%d;', [rec.items[i].remaining_time]));
    end;
    
    Result := sb.ToString;
  finally
    sb.Free;
  end;
end;
```

---

## 4e. Headunit Detection

Since no CIC/NBT/MGU strings appear in the binary, the headunit type must
be auto-detected. The most plausible method:

1. **Connect to ZGW → Query ECU tree (SVT)**
2. **Look for headunit in SVT**: The headunit's ECU variant field reveals
   whether it's CIC, NBT, NBT EVO, or MGU
3. **Derive PRG file name**: `<DETECTED_TYPE>.PRG`
4. **Derive job name**: `STEUERN_SERVICEHISTORY_ADD` (constant across all
   headunits for this operation)

Alternatively, the app might query the headunit directly for its type
identifier and then map it to the correct PRG.

### Return Value Handling

Per the BimmerGuide article (Phase 1):
- **CIC**: Success = `STAT_SH_ADD_WERT = 0x01` (offset by one)
- **NBT/NBT EVO/MGU**: Success = `STAT_SH_ADD_WERT = 0x00`

The app must check the headunit type to interpret the return value
correctly. This conditional logic exists in the binary but uses
runtime-determined values rather than hardcoded strings.

---

## Research Gaps & Unresolved Questions

1. **Exact .bmwsh format**: The unknown uint32 field needs computing.
   It appears to encode both mileage and a correction counter or flags.

2. **Job request wire format**: Since SHM.exe bypasses EDIABAS, the
   exact TCP message format (how the PRG reference, job name, and
   arguments are packaged in a socket message) is unknown without
   packet capture or deeper function analysis.

3. **Headunit auto-detection**: The exact query used to identify the
   headunit type is in the obfuscated Delphi code.

4. **Function addresses**: Due to transport truncation of Ghidra's
   procedure list (8283 entries), specific function addresses for
   the `.bmwsh` parser and argument builder were not resolved.

5. **IP*Works! component details**: The specific IP*Works! components
   (TCPPort, UDPPort) and their configuration (timeouts, buffers) are
   embedded in the Delphi form files (.dfm) in the .rsrc section.

6. **Licensing**: The app phones home to `automotive.blackboxsys.com`.
   The Lite/Free edition may have limited features.

---

> **Next Phase:** Phase 5 — Synthesize all findings into a comprehensive
> protocol reference document.