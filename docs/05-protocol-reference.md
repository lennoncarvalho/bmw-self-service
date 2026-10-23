# Phase 5: Complete Protocol Reference

> **Date:** 2026-10-23
> **Status:** Complete. Covers F-series (HSFZ), G/U/I-series (DoIP). E-series excluded.

---

## Table of Contents

1. [Connection Setup](#1-connection-setup)
2. [Diagnostic Sessions](#2-diagnostic-sessions)
3. [Vehicle Identification](#3-vehicle-identification)
4. [Curated Coding Flow](#4-curated-coding-flow-bimmercode-basic-mode)
5. [Expert Coding Flow](#5-expert-coding-flow-bimmercode-expert-mode)
6. [Sensor Reading Flow](#6-sensor-reading-flow-bimmerlink)
7. [DTC Flow](#7-dtc-flow)
8. [Service History Flow](#8-service-history-flow)
9. [Service Code Reference Table](#9-service-code-reference-table)
10. [Model/ECU Database](#10-modelecu-database)
11. [Message Reference](#11-message-reference)

---

## 1. Connection Setup

### Physical Layer

```
Laptop (RJ45) ←→ ENET Cable ←→ OBD2 Port (pins 3,11,12,13) ←→ ZGW
```

The ENET cable provides standard 100BASE-TX Ethernet over the OBD2 port
using ISO 13400-4 Option 1 pinout. The ZGW (Central Gateway) acts as the
Ethernet endpoint and TCP server.

### Protocol Selection

BMW vehicles use one of two transport protocols:

| Generation | Protocol | Discovery | Data Port | Standard |
|------------|----------|-----------|-----------|----------|
| F-series | HSFZ (BMW proprietary) | UDP 6811 | TCP 6801 | BMW-specific |
| G/I-series | DoIP | UDP 13400 | TCP 13400 | ISO 13400 |

### Connection Sequence

```
┌──────────────────────────────────────────────────────────────┐
│ STEP 1: ENET Cable Detection                                  │
│   - MHD Adapter or IP*Works! detects Ethernet link on ENET    │
│   - Pin 8 activation line wakes ZGW                           │
├──────────────────────────────────────────────────────────────┤
│ STEP 2: Vehicle Discovery (UDP)                               │
│   HSFZ: UDP broadcast to 255.255.255.255:6811                │
│   DoIP: Vehicle Identification Request → 13400               │
│   Vehicle responds with VIN, logical address, IP              │
├──────────────────────────────────────────────────────────────┤
│ STEP 3: TCP Connection                                        │
│   HSFZ: TCP connect to <vehicle_ip>:6801                     │
│   DoIP: TCP connect to <vehicle_ip>:13400                    │
│   DoIP: Send Routing Activation Request                      │
│   DoIP: Receive Routing Activation Response                  │
├──────────────────────────────────────────────────────────────┤
│ STEP 4: Diagnostic Session                                    │
│   UDS DiagnosticSessionControl (0x10) → Session Type         │
│   UDS TesterPresent (0x3E) → Keep-alive heartbeat            │
├──────────────────────────────────────────────────────────────┤
│ STEP 5: ECU Routing                                           │
│   Messages contain source/destination logical addresses      │
│   ZGW routes to target ECU behind internal bus               │
└──────────────────────────────────────────────────────────────┘
```

### HSFZ Framing (BMW Proprietary, F-series)

HSFZ ("High-Speed Vehicle Access") wraps UDS messages in a proprietary
header over TCP 6801:

```
HSFZ Frame:
  [Header: ~10 bytes] [UDS Message: variable] [Trailer: ~2 bytes]

Header contains:
  - Frame type (request/response/keep-alive)
  - Source ECU address
  - Destination ECU address  
  - Message length
```

### DoIP Framing (ISO 13400, G-series)

```
DoIP Frame:
  [Protocol Version: 2 bytes] [Inverse Version: 2 bytes]
  [Payload Type: 2 bytes]     [Payload Length: 4 bytes]
  [Payload: variable]

Diagnostic Message (payload type 0x8001):
  [Source Address: 2 bytes] [Target Address: 2 bytes]
  [UDS Message: variable]
```

---

## 2. Diagnostic Sessions

### Session Types

| Session | SID 0x10 Value | Purpose | Available Services |
|---------|---------------|---------|-------------------|
| Default | 0x01 | Basic OBD, DTC reading | 0x19, 0x22 (limited) |
| Programming | 0x02 | Flash/update | 0x31, 0x34-0x37 |
| Extended | 0x03 | Coding, advanced diagnostics | 0x22, 0x2E, 0x27, 0x31, 0x2F |

### Session Lifecycle

```
Client                          Server (ECU)
  |                                  |
  |-- 10 03 (Extended Session) ---->|   Server enters Extended mode
  |<-- 50 03 -----------------------|   S3 timer starts (~5 seconds)
  |                                  |
  |-- 3E 00 (TesterPresent) ------->|   Reset S3 timer
  |                                  |
  |-- 22 F1 90 (Read VIN) --------->|   Diagnostic operation
  |<-- 62 F1 90 <VIN> --------------|   
  |                                  |
  |-- 3E 00 (TesterPresent) ------->|   Keep-alive
  |                                  |
  |-- 10 01 (Default Session) ----->|   Server returns to default
  |<-- 50 01 -----------------------|
```

### Session Control Request

```
Byte 0:   0x10 (DiagnosticSessionControl SID)
Byte 1:   Session Type (0x01=Default, 0x02=Programming, 0x03=Extended)
          Bit 7: suppressPosRspMsgIndicationBit (0x80 to suppress response)
```

---

## 3. Vehicle Identification

### Reading VIN

```
UDS ReadDataByIdentifier (0x22)
  DID: 0xF190 (Vehicle Identification Number)

Request:  22 F1 90
Response: 62 F1 90 <17 ASCII chars>
```

### Reading Vehicle Order (FA)

```
UDS ReadDataByIdentifier (0x22)
  DID: ECU-specific (varies by ZGW/BDC generation)
  
The FA is an XML structure containing:
  - VIN
  - Type code (e.g., 3E32 for F30 328i)
  - Production date (MMYY format)
  - SALAPA elements (option codes like 522, 6NK)
```

### Reading SVT (ECU Tree)

```
UDS ReadDataByIdentifier (0x22) from ZGW (address 0x10)
  DID: Gateway-specific

SVT contains:
  - List of all ECUs in vehicle
  - Each ECU: logical address, variant, hardware/software version
  - Headunit type (CIC/NBT/NBT_EVO/MGU) from ECU variant field
```

### Model Detection

Apps determine the vehicle model through:
1. **VIN decoding**: Characters 4-7 encode model (e.g., 3E32 → F30)
2. **FA parsing**: Type code and build date
3. **SVT inspection**: List of ECUs reveals platform generation
4. **Manual selection**: User picks model from list

### BMW VIN Structure

```
Position:  1  2  3  4  5  6  7  8  9  10 11 12 13 14 15 16 17
Example:   W  B  A  3  E  3  2  0  5  F  Z  Z  9  9  9  9  9
           │  │  │  │        │  │  │  │           │
           │  │  │  │        │  │  │  └─ Plant     └─ Serial
           │  │  │  │        │  │  └─ Check digit
           │  │  │  │        │  └─ Model year (F=2015)
           │  │  │  └─ Model (3E32 = F30 328i)
           │  │  └─ Series/body
           │  └─ Manufacturer (B=BMW AG)
           └─ Region (W=Germany)
```

---

## 4. Curated Coding Flow (BimmerCode Basic Mode)

### Architecture

```
┌──────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  UI Presets   │     │  Coding Engine   │     │  MHD Adapter    │
│  (curated     │────►│  (k.a / k.j)    │────►│  (ENET stack)   │
│   database)   │     │                  │     │                  │
└──────────────┘     └─────────────────┘     └─────────────────┘
```

### Flow

```
1. User browses available coding options for selected ECU
   └─ Options come from compiled-in model classes (a0-z0 in
      de.appomotive.bimmercode.models)

2. User toggles an option (e.g., "Fold mirrors on lock" → ON)
   └─ UI maps toggle to specific FDL parameter
   └─ Parameter stored as k.j { Integer id, byte[] value }

3. Read current coding from ECU
   └─ ESeriesVehicleInterface.g(context, ecu) → k.a container
   └─ k.a contains ArrayList<k.j> of all FDL parameters

4. Compute diff
   └─ ESeriesVehicleInterface.F(original, modified) → ArrayList<k.j>
   └─ Returns only changed parameters

5. Write changes
   └─ CodingDataWriter.h() orchestrates write
   └─ Steps: connect → validate → write → verify → finalize

6. Write protocol per parameter:
   UDS WriteDataByIdentifier (0x2E) with parameter-specific DID
   Payload: modified byte[] value for that parameter
```

### Coding Data Structure

```
k.j (individual coding parameter):
  Integer a          — Parameter identifier (maps to FDL parameter)
  byte[] f6561b      — Raw coding value bytes

k.a (coding data container):
  ArrayList<k.j> f6555b — All parameters for an ECU
  
Internal operations:
  a(ecu, coding)     — Read coding from ECU via UDS 0x22
  b(session, ecu)    — Load from adapter session
  a(ecu, param, values) — Write option via UDS 0x2E
  g(ecu, param)      — Get available values for a parameter
  F(original, modified) — Compute diff between two coding sets
```

---

## 5. Expert Coding Flow (BimmerCode Expert Mode)

### Flow

```
1. User selects ECU → App reads ALL FDL parameters
   └─ ESeriesVehicleInterface.g(context, ecu) → k.a (all params)

2. App displays raw FDL editor
   └─ Each k.j shown with: name, current value, available options
   └─ Parameter names come from model class definitions
   └─ Available values from k.a.g(ecu, param)

3. User edits parameters directly (raw hex or selected values)
   └─ Modified k.a container tracks changes

4. Write flow:
   └─ Same as curated mode: diff → CodingDataWriter → MHD adapter
   └─ Safety: some ECUs blocked (airbag, ABS)
   └─ Backup: ESeriesVehicleInterface.b() saves before write
```

### Comparison: Basic vs Expert Mode

| Aspect | Basic Mode | Expert Mode |
|--------|------------|-------------|
| Parameter visibility | Curated subset | ALL FDL parameters |
| Parameter names | User-friendly descriptions | Raw FDL names |
| Value selection | Toggle/dropdown | Raw hex or dropdown |
| Risk | Low (tested presets) | Higher (all parameters accessible) |
| ECU access | Most non-safety ECUs | Same + some safety ECUs blocked |
| Backend | Same CodingDataWriter | Same CodingDataWriter |

### FDL Structure

```
CAFD (Coding Application Data File):
  ├── Header
  ├── Daten
  │   ├── Functional Group (e.g., 3000 HMI)
  │   │   ├── Aktivbedingung (activation conditions)
  │   │   └── Funktionen (functions)
  │   │       ├── MACRO_PDC
  │   │       │   ├── SpeicherInfo (storage format)
  │   │       │   ├── aktiv (werte: enabled)
  │   │       │   └── nicht_aktiv (werte: disabled)
  │   │       └── ...
  │   └── ...
  └── Signature / CPS (Code Verification Stamp)
```

Each FDL parameter in BimmerCode maps to a CAFD function node:
- `k.j.a` (Integer) = index into the function list
- `k.j.f6561b` (byte[]) = the selected werte value
- The available wertes are enumerated by `k.a.g(ecu, param)`

---

## 6. Sensor Reading Flow (BimmerLink)

### Architecture

```
┌──────────────────┐     ┌──────────────────┐     ┌────────────┐
│  Sensor Database  │     │  Live Data Engine │     │  Adapter   │
│  (JSON/Gson)      │────►│  (u5.j model)    │────►│  (MHD/ENET)│
│                    │     │                    │     │            │
└──────────────────┘     └──────────────────┘     └────────────┘
```

### Sensor Database (Inferred JSON Structure)

BimmerLink stores sensor definitions in JSON, deserialized by Gson:

```json
{
  "sensors": [
    {
      "sensorId": "DME_COOLANT_TEMP",
      "ecuLogicalAddress": 18,
      "did": "F405",
      "name": "Coolant Temperature",
      "unit": "°C",
      "scale": 0.75,
      "offset": -48.0,
      "dataType": "uint16",
      "byteLength": 2,
      "formula": "(value * 0.75) - 48",
      "category": "engine",
      "refreshInterval": 200
    },
    {
      "sensorId": "DME_RPM",
      "ecuLogicalAddress": 18,
      "did": "F40C",
      "name": "Engine RPM",
      "unit": "rpm",
      "scale": 0.25,
      "offset": 0,
      "dataType": "uint16",
      "formula": "value * 0.25",
      "category": "engine",
      "refreshInterval": 100
    }
  ]
}
```

Deserializer classes:
- `BMWSensorValueDeserializer` — Parses sensor definitions
- `BMWEcuDescriptionDeserializer` — Parses ECU metadata

### Live Reading Loop

```
┌─────────────────────────────────────────────────────┐
│ Start monitoring                                     │
│   │                                                   │
│   ▼                                                   │
│ UDS 10 03 (Extended Session)                         │
│   │                                                   │
│   ▼                                                   │
│ ┌─[Loop: every ~200ms per sensor]──┐                │
│ │                                    │                │
│ │ UDS 22 <DID> (ReadDataByIdentifier)│               │
│ │   │                                │                │
│ │   ▼                                │                │
│ │ Response: 62 <DID> <raw bytes>    │                │
│ │   │                                │                │
│ │   ▼                                │                │
│ │ Apply formula: raw → display value │               │
│ │   │                                │                │
│ │   ▼                                │                │
│ │ Update UI gauge                    │                │
│ │                                    │                │
│ └────────────────────────────────────┘                │
│   │                                                   │
│   ▼                                                   │
│ Every ~2s: UDS 3E 00 (TesterPresent)                 │
│   │                                                   │
│   ▼                                                   │
│ User stops → UDS 10 01 (Default Session)             │
└─────────────────────────────────────────────────────┘
```

### Supported Sensor Categories (from Activity Names)

| Activity | Sensors Covered |
|----------|----------------|
| DashboardActivity | RPM, speed, coolant temp, oil temp, boost |
| BatteryActivity | Voltage, SoC, SoH, charging current |
| DPFActivity | Soot mass, ash mass, DPF temp, diff. pressure |
| ExhaustFlapActivity | Exhaust flap position |
| TransmissionAdaptationValues | EGS clutch/gear adaptations |

### Sensor Data Formula Examples

| Sensor | RAW Type | Formula |
|--------|----------|---------|
| Engine RPM | uint16 (2 bytes) | `value * 0.25` |
| Coolant Temp | uint16 (2 bytes) | `value * 0.75 - 48` |
| Vehicle Speed | uint16 (2 bytes) | `value * 0.01` (km/h) |
| Battery Voltage | uint16 (2 bytes) | `value * 0.1` |
| Oil Temperature | uint16 (2 bytes) | `value - 40` |
| Boost Pressure | uint16 (2 bytes) | `value * 0.1` (absolute, subtract 1000 mbar for gauge) |
| DPF Soot Mass | uint16 (2 bytes) | `value * 0.01` (grams) |

---

## 7. DTC Flow

### Read DTCs

```
┌─────────────────────────────────────────────────────┐
│ 1. Extended Session (0x10 03)                        │
│                                                       │
│ 2. Report DTC Count by Status Mask (0x19 01)         │
│    Request:  19 01 <status_mask>                      │
│    Response: 59 01 <status_mask> <count> <format>    │
│                                                       │
│ 3. Report DTCs by Status Mask (0x19 02)              │
│    Request:  19 02 <status_mask>                      │
│    Response: 59 02 <availability>                     │
│              [<DTC 3 bytes> <status 1 byte>]...       │
│                                                       │
│ 4. Report Snapshot (Freeze Frame) per DTC (0x19 04)  │
│    Request:  19 04 <DTC> <snapshot_record>            │
│    Response: 59 04 <DTC> <status> <record_num>       │
│              <DID_count> [<DID> <value>]...           │
│                                                       │
│ 5. Report Extended Data per DTC (0x19 06)            │
│    Request:  19 06 <DTC> <ext_data_record>            │
│    Response: 59 06 <DTC> <status> <record_num>       │
│              <data>                                    │
└─────────────────────────────────────────────────────┘
```

### DTC Status Mask Bits

| Bit | Name | Meaning |
|-----|------|---------|
| 0 | testFailed | DTC failed at time of request |
| 1 | testFailedThisOperationCycle | Failed in current cycle |
| 2 | pendingDTC | Failed in current or last cycle |
| 3 | confirmedDTC | Confirmed, stored in memory |
| 4 | testNotCompletedSinceLastClear | Test incomplete since clear |
| 5 | testFailedSinceLastClear | Test failed since clear |
| 6 | testNotCompletedThisOperationCycle | Test incomplete this cycle |
| 7 | warningIndicatorRequested | MIL/warning is on |

### Clear DTCs

```
UDS ClearDiagnosticInformation (0x14)
  Request:  14 <group_of_dtc>
  Response: 54
  
Group of DTC values:
  0xFFFFFF — All DTCs (powertrain, chassis, body, network)
  0x000000 — Powertrain only
  ECU-specific groups also possible
```

### BimmerLink DTC Features

From activity names and model classes:
1. **ErrorMemoryEcuSelectionActivity**: Select which ECUs to scan
2. **ErrorMemoryActivity**: Shows DTC list with descriptions
3. **ErrorMemoryResultActivity**: Detailed results per ECU
4. **ErrorDetailsActivity**: Freeze frame data, environment data
5. **ErrorReportActivity**: Export/share diagnostic report

The DTC database is JSON-based (`BMWErrorLocationTextDeserializer`),
mapping DTC codes to human-readable descriptions.

---

## 8. Service History Flow

### Complete End-to-End Flow

```
┌─────────────────────────────────────────────────────────────┐
│ APPLICATION: SHM.exe (BlackBOX Sistemi BMW Service History   │
│             Manager 1.00.100, Delphi 10.3 Rio)              │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│ 1. USER enters service data in GUI                           │
│    ├─ Date (TDateTimePicker)                                  │
│    ├─ Mileage (km)                                            │
│    ├─ Dealer name / code (up to 7 chars)                     │
│    ├─ Dealer type (BMW dealer / independent)                 │
│    └─ Service items (checkboxes from code table)              │
│                                                               │
│ 2. APP saves to .bmwsh file                                  │
│    ├─ Binary format: date (4B) + flags (4B) +                │
│    │   dealer ASCIIZ + dealer_flag + item_count +            │
│    │   [code + status + dist + time] ×N                      │
│    └─ Variable-length records, multiple entries              │
│                                                               │
│ 3. USER clicks "Write to car"                                │
│                                                               │
│ 4. APP reads .bmwsh file                                     │
│    └─ Parses binary records into internal structure           │
│                                                               │
│ 5. APP connects to vehicle                                   │
│    ├─ ENET cable detection                                    │
│    ├─ Vehicle discovery (UDP 6811 or UDP 13400)              │
│    ├─ TCP connection to ZGW (port 6801 or 13400)             │
│    └─ "ENET_CONNECT_SUCCESS" / "Connected to "               │
│                                                               │
│ 6. APP detects headunit type                                 │
│    ├─ Query SVT from ZGW                                     │
│    ├─ Locate headunit ECU (address 0x63 typically)           │
│    └─ Determine type: CIC / NBT / NBT EVO / MGU              │
│                                                               │
│ 7. APP selects PRG file and job name                         │
│    ├─ PRG: <HEADUNIT>.PRG (e.g., NBT.PRG)                    │
│    └─ Job: STEUERN_SERVICEHISTORY_ADD                        │
│        (or _ERASE / _DEL for full history deletion)          │
│                                                               │
│ 8. APP builds argument string (TStringBuilder)               │
│    Format:                                                    │
│    "Day;Month;Year;CorrectCnt;Km;DealerFlag;DealerID;       │
│     Status;Count;                                            │
│     [Code;ItemStatus;RemainingDist;RemainingTime;]..."       │
│                                                               │
│    Example:                                                   │
│    "24;9;2026;0;125000;0;Lennon;0x1;6;                      │
│     1;0x1;0;0;4;0x1;0;0;11;0x1;0;0;                        │
│     100;0x1;0;0;3;0x1;0;0;10;0x1;0;0;"                      │
│                                                               │
│ 9. APP sends job over TCP socket                             │
│    ├─ Routes to headunit via ZGW                             │
│    ├─ Job execution command contains:                         │
│    │   - PRG file reference                                   │
│    │   - Job name (STEUERN_SERVICEHISTORY_ADD)                │
│    │   - Argument string                                      │
│    └─ Uses IP*Works! TCP socket or uENETSocket                │
│                                                               │
│ 10. HEADUNIT processes and responds                          │
│     ├─ Validates argument format and item count              │
│     ├─ Checks writing permission                              │
│     ├─ Stores entry in local service history                 │
│     └─ Returns: JOB_STATUS and STAT_SH_ADD_WERT              │
│                                                               │
│ 11. APP checks response                                       │
│     "JOB_STATUS = OKAY"                                       │
│     "STAT_SH_ADD_WERT = <value>"                             │
│                                                               │
│     Per headunit success values:                              │
│     ┌──────────┬─────────┐                                   │
│     │ Headunit │ Success │                                   │
│     ├──────────┼─────────┤                                   │
│     │ CIC      │ 0x01    │                                   │
│     │ NBT      │ 0x00    │                                   │
│     │ NBT EVO  │ 0x00    │                                   │
│     │ MGU      │ 0x00    │                                   │
│     └──────────┴─────────┘                                   │
│                                                               │
│     Error codes (NBT/NBT_EVO/MGU):                            │
│     0x01 = Memory error / no free space                       │
│     0x02 = Data inconsistency                                 │
│     0x04 = No writing permission                              │
│     0x05 = Unknown error                                      │
│                                                               │
│ 12. APP displays result to user                              │
│     └─ Success: "Writing new service history..."             │
│     └─ Failure: "ERR: Could not connect to target:"          │
│                   or specific error message                   │
└─────────────────────────────────────────────────────────────┘
```

### .bmwsh ↔ Argument String Conversion

```
.bmwsh Binary Record:
  [18 09 EA 07] [00 00 01 02] [06] "Lennon" [00] [01] [06]
  [01] [01] [00 00] [00 00] [00 00]    ← Item 1: Oil
  [04] [01] [00 00] [00 00] [00 00]    ← Item 2: Microfilter
  [0B] [01] [00 00] [00 00] [00 00]    ← Item 3: Air filter
  [64] [01] [00 00] [00 00] [00 00]    ← Item 4: Vehicle check
  [03] [01] [00 00] [00 00] [00 00]    ← Item 5: Brake fluid
  [0A] [01] [00 00] [00 00] [00 00]    ← Item 6: Spark plugs

        ↓ TStringBuilder conversion ↓

Tool32 Argument String:
  "24;9;2026;0;125000;0;Lennon;0x1;6;
   1;0x1;0;0;4;0x1;0;0;11;0x1;0;0;
   100;0x1;0;0;3;0x1;0;0;10;0x1;0;0;"
```

### Erase Operations

Two additional jobs exist for deleting service history:

| Job | Argument | Effect |
|-----|----------|--------|
| `STEUERN_SERVICEHISTORY_ERASE` | None required | Deletes entire service history |
| `STEUERN_SERVICEHISTORY_DEL` | None required | Deletes entire service history (alias) |

**Warning**: These jobs provide no confirmation beyond JOB_STATUS.
Running them removes all stored service records irreversibly.

---

## 9. Service Code Reference Table

Complete table from PRG files (source: BimmerGuide.de, confirmed in .bmwsh analysis).

| Dec | Hex | Label | Notes |
|-----|-----|-------|-------|
| 1 | 0x01 | Engine oil | BMW Longlife-01/04/12/14 FE |
| 2 | 0x02 | Brake pads front | — |
| 3 | 0x03 | Brake fluid | DOT 4, every 36/24 months |
| 4 | 0x04 | Microfilter / cabin filter | Activated charcoal |
| 5 | 0x05 | Service Inclusive | Package indicator |
| 6 | 0x06 | Brake pads rear | — |
| 7 | 0x07 | Particulate filter (gasoline) | OPF/GPF |
| 8 | 0x08 | Battery (State of Health) | Software-dependent |
| 9 | 0x09 | QMV-H oil | Special oil variant |
| 10 | 0x0A | Spark/glow plugs (adaptive) | Software-dependent |
| 11 | 0x0B | Air filter element | Engine air filter |
| 12 | 0x0C | Fuel filter | Diesel vehicles |
| 13 | 0x0D | NOx additive | SCR/AdBlue |
| 16 | 0x10 | Spark plugs | Non-adaptive variant |
| 17 | 0x11 | Vehicle check / visual inspection | Every 48 months |
| 18 | 0x12 | Coolant | Lifetime fill, check only |
| 19 | 0x13 | H2 check | Hydrogen system (FCEV) |
| 20 | 0x14 | Pre-delivery inspection | Factory/dealer |
| 21 | 0x15 | Break-in inspection | ~2000 km |
| 22 | 0x16 | Particulate filter additive | Eolys/DPF additive |
| 23 | 0x17 | Water filter | Diesel water separator |
| 24 | 0x18 | Gas pressure spring | Hood/trunk struts |
| 32 | 0x20 | Vehicle inspection (MOT/TÜV) | Regulatory |
| 33 | 0x21 | Emissions test (AU) | Regulatory |
| 35 | 0x23 | Transmission oil | AT, DCT, or MT |
| 49 | 0x31 | Tire age | ≥6 years recommendation |
| 50 | 0x32 | Clutch | Manual transmission |
| 51 | 0x33 | Gas pressure damper (ped. protection) | Active hood |
| 52 | 0x34 | First aid kit | Expiration date |
| 53 | 0x35 | Tire Fit (mobility kit) | Expiration date |
| 54 | 0x36 | Catalytic converter | Inspection |
| 55 | 0x37 | Shock absorber | Inspection |
| 97 | 0x61 | Service safety vehicle | Authority vehicles |
| 100 | 0x64 | Vehicle check (combined) | Bundled inspection |
| 224 | 0xE0 | CBS Evalboard | Internal test only |
| 225 | 0xE1 | CBR Evalboard | Internal test only |
| 255 | 0xFF | Delivery state | Factory special state |

### Additional Observed Codes

The .bmwsh file contained code 26 (0x1A) which is not in the public PRG
table. This may be a model-specific or software-version-specific code.

---

## 10. Model/ECU Database

### ECU Diagnostic Addresses (Typical)

| ECU | Logical Address | Bus | Function |
|-----|----------------|-----|----------|
| ZGW | 0x10 | Gateway | Central gateway, Ethernet endpoint |
| DME/DDE | 0x12 | PT-CAN | Engine management |
| EGS | 0x18 | PT-CAN | Transmission control |
| DSC | 0x29 | PT-CAN | Stability control/ABS |
| EPS | 0x30 | PT-CAN/FlexRay | Electric power steering |
| FEM_BODY | 0x40 | K-CAN2 | F-series front body controller |
| BDC_BODY | 0x40 | K-CAN2/K-CAN4 | G-series body domain controller |
| KOMBI | 0x60 | K-CAN | Instrument cluster |
| Headunit | 0x63 | K-CAN2/MOST | CIC/NBT/NBT_EVO/MGU |
| IHKA | 0x78 | K-CAN | Climate control |
| ACSM | 0x0D | K-CAN | Airbag/restraint system |
| CAS | 0x0F | K-CAN | Car access system (E-series) |
| FRM | 0x1D | K-CAN | Footwell module (E-series) |

### Headunit Generations

| Type | Years | Vehicles | Bus | Notes |
|------|-------|----------|-----|-------|
| CIC | ~2008-2013 | E9x, early F-series | MOST/K-CAN2 | Car Information Computer |
| NBT | ~2013-2017 | F-series | K-CAN2/Ethernet | Next Big Thing |
| NBT EVO | ~2016-2019 | Late F, early G | Ethernet | NBT Evolution |
| MGU | ~2019+ | G-series | Ethernet | Media Graphics Unit |
| HU_ENTRY | Various | Base models | K-CAN2 | Entry headunit |
| ENTRYNAV2 | ~2017+ | Entry models | Ethernet | Entry nav with connected drive |

### BMW Model Series Reference

| Series | Platform Code | Generation | Diagnostic Method |
|--------|--------------|------------|-------------------|
| E81-E88 | E8x | 1 Series (2004-2013) | K+DCAN |
| E90-E93 | E9x | 3 Series (2005-2013) | K+DCAN |
| F20-F21 | F2x | 1 Series (2011-2019) | ENET (HSFZ) |
| F30-F31-F34-F80 | F3x | 3 Series (2011-2019) | ENET (HSFZ) |
| F10-F11 | F1x | 5 Series (2010-2017) | ENET (HSFZ) |
| F15-F16-F85-F86 | F1x | X5/X6 (2013-2019) | ENET (HSFZ) |
| G20-G21 | G2x | 3 Series (2018+) | ENET (DoIP) |
| G30-G31 | G3x | 5 Series (2016+) | ENET (DoIP) |
| G05-G06 | G0x | X5/X6 (2018+) | ENET (DoIP) |
| G01 | G0x | X3 (2017+) | ENET (DoIP) |
| I01 | I01 | i3 (2013-2022) | ENET |
| I12 | I12 | i8 (2014-2020) | ENET |

### BimmerCode Model Database

BimmerCode stores model-specific coding presets in obfuscated classes:

```
de.appomotive.bimmercode.models
├── ESeriesVehicleInterface  — E-series protocol (K+DCAN)
├── a0-a1                    — Per-model parameter maps
├── b0-b1, c0, d0-d1, ...    — Additional model definitions
├── n0                       — ECU model descriptor (Parcelable)
│   ├── f6652f, f6653g       — Integer identifiers
│   ├── h, i, j              — ECU type/address/family IDs
│   ├── k                    — ECU generation flag
│   ├── l                    — ECU name string
│   └── m, n, o              — Coding data references
└── r0, o0, p0, ...          — Supporting types
```

---

## 11. Message Reference

### UDS ReadDataByIdentifier (0x22)

```
Request:
  Byte 0:   0x22
  Byte 1-2: Data Identifier (DID), MSB first

Response (positive):
  Byte 0:   0x62
  Byte 1-2: DID echo
  Byte 3+:  Data value (variable length)

Response (negative):
  Byte 0:   0x7F
  Byte 1:   0x22
  Byte 2:   NRC (Negative Response Code)
```

### UDS WriteDataByIdentifier (0x2E)

```
Request:
  Byte 0:   0x2E
  Byte 1-2: Data Identifier (DID), MSB first
  Byte 3+:  Data to write (variable length)

Response (positive):
  Byte 0:   0x6E
  Byte 1-2: DID echo

Response (negative):
  Byte 0:   0x7F
  Byte 1:   0x2E
  Byte 2:   NRC
```

### UDS RoutineControl (0x31)

```
Request:
  Byte 0:   0x31
  Byte 1:   Sub-function
              0x01 = startRoutine
              0x02 = stopRoutine
              0x03 = requestRoutineResults
              (+0x80 to suppress response)
  Byte 2-3: Routine Identifier (RID), MSB first
  Byte 4+:  Routine-specific parameters (optional)

Response (positive):
  Byte 0:   0x71
  Byte 1:   Sub-function echo
  Byte 2-3: RID echo
  Byte 4+:  Routine results (optional)

Response (negative):
  Byte 0:   0x7F
  Byte 1:   0x31
  Byte 2:   NRC
```

### UDS ReadDTCInformation (0x19)

```
Request (Report DTC by Status Mask, sub-function 0x02):
  Byte 0:   0x19
  Byte 1:   0x02 (reportDTCByStatusMask)
  Byte 2:   DTC status mask

Response:
  Byte 0:   0x59
  Byte 1:   0x02
  Byte 2:   DTCStatusAvailabilityMask
  Byte 3+:  [DTC 3 bytes] [Status 1 byte] (repeating)

DTC encoding (3 bytes):
  Byte 0:   High byte (bits 7-6 = category, bits 5-0 = first digit group)
  Byte 1:   Middle byte (second and third digit groups)
  Byte 2:   Low byte (fourth and fifth digit groups)

Example: 0x12 0x34 0x56 → DTC "123456"
```

### UDS ClearDiagnosticInformation (0x14)

```
Request:
  Byte 0:   0x14
  Byte 1-3: Group of DTC (3 bytes)
              0xFFFFFF = all groups
              0x000000 = powertrain
              0x000040 = chassis
              0x000080 = body
              0x0000C0 = network communication

Response:
  Byte 0:   0x54
```

### UDS DiagnosticSessionControl (0x10)

```
Request:
  Byte 0:   0x10
  Byte 1:   Session type
              0x01 = defaultSession
              0x02 = programmingSession
              0x03 = extendedDiagnosticSession

Response:
  Byte 0:   0x50
  Byte 1:   Session type echo
  Byte 2+:  Session parameters (P2/P2* timing, optional)
```

### UDS TesterPresent (0x3E)

```
Request:
  Byte 0:   0x3E
  Byte 1:   0x00 (zero sub-function)
              (or 0x80 to suppress response)

Response (if not suppressed):
  Byte 0:   0x7E
  Byte 1:   0x00
```

### Common Negative Response Codes (NRC)

| NRC | Name | Meaning |
|-----|------|---------|
| 0x10 | generalReject | Operation rejected |
| 0x11 | serviceNotSupported | SID not supported |
| 0x12 | subFunctionNotSupported | Sub-function not supported |
| 0x13 | incorrectMessageLengthOrInvalidFormat | Bad message length |
| 0x22 | conditionsNotCorrect | Wrong state for operation |
| 0x31 | requestOutOfRange | DID/RID out of range |
| 0x33 | securityAccessDenied | Security level insufficient |
| 0x35 | invalidKey | Wrong security key |
| 0x36 | exceededNumberOfAttempts | Security lockout |
| 0x37 | requiredTimeDelayNotExpired | Retry delay active |
| 0x7E | subFunctionNotSupportedInActiveSession | Wrong session type |
| 0x7F | serviceNotSupportedInActiveSession | Wrong session for SID |

---

## Summary: Building a Replacement App

This reverse-engineering effort has documented the complete BMW ENET
communication stack needed to build a replacement application.

### What You Need to Implement

1. **Physical layer**: ENET cable detection and Ethernet link establishment
   using OBD2 pins 3/11/12/13

2. **Transport layer**: HSFZ protocol (TCP 6801) for F-series, DoIP
   protocol (TCP/UDP 13400) for G-series. Reference: rawenet (HSFZ),
   python-doipclient (DoIP)

3. **Application layer**: UDS message construction and parsing per
   ISO 14229-5 (UDSonIP)

4. **Coding engine**: 
   - Read FA/VO from ZGW → parse SALAPA elements
   - Read SVT from ZGW → build ECU tree
   - Read CAFD from ECU → parse FDL parameters
   - Diff engine for coding changes
   - Write modified parameters back via UDS 0x2E

5. **Sensor engine**:
   - Per-ECU sensor DID database
   - Conversion formulas (raw bytes → display values)
   - Polling loop with TesterPresent keep-alive

6. **DTC engine**:
   - UDS 0x19 ReadDTCInformation with status mask parsing
   - DTC code → description mapping database
   - Freeze frame display
   - UDS 0x14 ClearDiagnosticInformation

7. **Service history engine**:
   - `.bmwsh` binary format reader/writer (documented above)
   - Tool32 argument string builder
   - Headunit auto-detection from SVT
   - Job execution over TCP socket
   - Response parsing with headunit-specific success values

### Key Databases to Build

1. **Model database** (FDL parameter definitions per ECU per model)
2. **Sensor DID database** (which DIDs to poll for each ECU)
3. **DTC description database** (code → text mapping)
4. **Service code table** (Section 9 above — complete)

### Known Byte-Level Message Formats

All UDS messages documented in Section 11. The HSFZ header is the
remaining gap (requires packet capture or deeper SHM.exe analysis).

---

> **End of Phase 5.** This completes the end-to-end reverse engineering
> of the BMW ENET communication protocol, BimmerCode, BimmerLink, and
> SHM.exe service history manager.