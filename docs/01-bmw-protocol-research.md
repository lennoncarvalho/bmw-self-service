# Phase 1: BMW ENET Protocol Research

> **Date:** 2026-10-23
> **Status:** Complete
> **Sources:** Web research, ISO standards, BMW community documentation, BimmerGuide.de

---

## 1. Physical Layer: ENET Cable & OBD2 Pinout

### ENET Cable (BMW F/G/I Series)

BMW's ENET cable is an **Ethernet-to-OBD2** adapter that connects a laptop's
RJ-45 port to the vehicle's OBD2 diagnostic connector. It replaces older
K+DCAN (E-series) and ICOM interfaces with direct 100BASE-TX Ethernet.

**OBD2 Pin Mapping (ISO 13400-4 Option 1, used by BMW):**

| OBD2 Pin | Signal | Function |
|----------|--------|----------|
| 3        | RX+    | Ethernet receive (positive) |
| 11       | RX-    | Ethernet receive (negative) |
| 12       | TX+    | Ethernet transmit (positive) |
| 13       | TX-    | Ethernet transmit (negative) |
| 8        | Activation | Ethernet activation line |
| 16       | +12V   | Battery power |

The two differential pairs provide standard **IEEE 802.3 100BASE-TX**
Ethernet. Pin 8 serves as an activation line — when the tester applies a load
on this pin, the vehicle's ZGW (Central Gateway) wakes up and enables the
Ethernet interface.

### Vehicle-side Architecture

- The **ZGW (Zentrales Gateway)** acts as the TCP server and Ethernet switch
- In F-series vehicles, the ZGW is a separate physical module
- In G-series vehicles (BDC_BODY, FEM_BODY), the gateway function is
  integrated into the body domain controller
- Ethernet runs as a point-to-point link between the OBD2 port and ZGW

---

## 2. DoIP: Diagnostics over IP (ISO 13400)

### Overview

**DoIP (ISO 13400)** is the standardized diagnostic transport protocol for
Ethernet-based vehicle communication. It packages UDS diagnostic messages
inside Ethernet frames and operates at OSI layers 3-4 on top of IEEE 802.3.

### Standard Ports

| Service | Protocol | Port | IANA Name |
|---------|----------|------|-----------|
| Vehicle Discovery | UDP | 13400 | `doip-disc` |
| Diagnostic Data | TCP | 13400 | `doip-data` |
| TLS (optional) | TCP | 3496 | — |

### BMW's Two Protocol Eras

BMW uses **two different transport protocols** depending on vehicle generation:

| Aspect | HSFZ (Legacy) | DoIP (Modern) |
|--------|---------------|---------------|
| Origin | BMW-proprietary | Industry standard (ISO 13400) |
| Vehicles | F-series, early G-series | Late G-series, I-series |
| Discovery Port | UDP 6811 | UDP 13400 |
| Data Port | TCP 6801 | TCP 13400 |
| Protocol | Custom HSFZ framing over TCP | ISO 13400 DoIP framing |

**HSFZ** (High-Speed-Fahrzeug-Zugang, "High-Speed Vehicle Access") is BMW's
proprietary predecessor to DoIP, shipped since ~2008. It tunnels UDS over
TCP port 6801 with a custom framing header. The ZGW acts as TCP server on
port 6801, and vehicle discovery uses UDP broadcast on port 6811.

### DoIP Session Lifecycle

```
1. Vehicle Discovery (UDP 13400)
   └─ Tester sends Vehicle Identification Request (broadcast)
   └─ Vehicle responds with Vehicle Announcement Message (VAM)
      containing: VIN, logical address, IP address

2. TCP Connection (TCP 13400)
   └─ Tester opens TCP connection to vehicle's IP on port 13400

3. Routing Activation (TCP 13400)
   └─ Tester sends Routing Activation Request
   └─ Vehicle responds with Routing Activation Response
   └─ This opens the route to a specific ECU behind the gateway

4. Diagnostic Communication (TCP 13400)
   └─ UDS request/response messages tunneled in DoIP frames
   └─ Each message includes source/destination logical addresses

5. Connection Teardown
   └─ Tester sends Routing Deactivation
   └─ TCP connection closed
```

### DoIP Payload Types

| Payload Type | Name | Connection |
|-------------|------|------------|
| 0x0000 | Generic negative acknowledge | UDP/TCP |
| 0x0001 | Vehicle Identification Request | UDP |
| 0x0002 | Vehicle Identification Request with EID | UDP |
| 0x0003 | Vehicle Identification Request with VIN | UDP |
| 0x0004 | Vehicle Announcement / Identification Response | UDP |
| 0x0005 | Routing Activation Request | TCP |
| 0x0006 | Routing Activation Response | TCP |
| 0x0007 | Alive Check Request | TCP |
| 0x0008 | Alive Check Response | TCP |
| 0x8001 | Diagnostic Message | TCP |
| 0x8002 | Diagnostic Message Positive Acknowledgment | TCP |
| 0x8003 | Diagnostic Message Negative Acknowledgment | TCP |

---

## 3. UDS: Unified Diagnostic Services (ISO 14229)

UDS (ISO 14229) is the application-layer diagnostic protocol. BMW vehicles
use **UDSonIP** (ISO 14229-5) — UDS transported over DoIP.

### Diagnostic Sessions (0x10)

ECUs operate in exactly one diagnostic session at a time. Different sessions
expose different services:

| Session | Value | Purpose | Timeout |
|---------|-------|---------|---------|
| Default | 0x01 | Basic diagnostics, DTC reading | No timeout |
| Programming | 0x02 | Flash/update operations | ~5s (S3 timer) |
| Extended | 0x03 | Advanced functions, coding | ~5s (S3 timer) |

Non-default sessions are kept alive via `TesterPresent` (0x3E) heartbeats.

### Key UDS Services for BMW

| SID | Name | BMW Usage |
|-----|------|-----------|
| 0x10 | DiagnosticSessionControl | Switch to programming/extended session |
| 0x11 | ECUReset | Hard/soft reset of an ECU |
| 0x14 | ClearDiagnosticInformation | Clear DTCs |
| 0x19 | ReadDTCInformation | Read diagnostic trouble codes and freeze frames |
| 0x22 | ReadDataByIdentifier | Read ECU data by 2-byte DID (VIN, coding, sensor values) |
| 0x27 | SecurityAccess | Seed/key exchange for privileged operations |
| 0x2E | WriteDataByIdentifier | Write configuration/coding data by DID |
| 0x2F | InputOutputControlByIdentifier | Actuate components for testing |
| 0x31 | RoutineControl | Execute predefined routines (service resets, calibrations) |
| 0x34 | RequestDownload | Prepare ECU for firmware download |
| 0x35 | RequestUpload | Prepare ECU for data upload |
| 0x36 | TransferData | Transfer firmware/data blocks |
| 0x37 | RequestTransferExit | End transfer session |
| 0x3E | TesterPresent | Keep-alive heartbeat |

### UDS Message Structure

```
Request:
  [Service ID (1 byte)] [Sub-function or DID (1-2 bytes)] [Parameters...]

Positive Response:
  [SID + 0x40 (1 byte)] [Sub-function/DID echo] [Data...]

Negative Response:
  [0x7F (1 byte)] [Original SID] [NRC (1 byte)]

Common NRCs:
  0x11 - serviceNotSupported
  0x22 - conditionsNotCorrect
  0x31 - requestOutOfRange
  0x33 - securityAccessDenied
  0x35 - invalidKey
  0x7E - subFunctionNotSupportedInActiveSession
```

---

## 4. BMW FA (Vehicle Order) and FDL Coding

### Fahrzeugauftrag (FA) / Vehicle Order (VO)

The FA is the vehicle's "birth certificate" — a data structure containing:

- **VIN**: 17-character Vehicle Identification Number
- **Zeitkriterium / Production Date**: Build date (e.g., `0715` = July 2015)
- **SA (Sonderausstattung)**: Factory option codes (e.g., `522` = Xenon, `6NK` = Enhanced BT)
- **HO (Händleroption)**: Dealer-installed options
- **SALAPA Elements**: Individual equipment/software entries
- **Type Code**: Vehicle model (e.g., `3E32` for F30 328i)

The FA determines which coding data is applied during VO-coding.

### FDL (Funktionale Daten Liste / Function Data List)

FDL is the individual parameter coding within each ECU. The flow:

```
FA (Vehicle Order) → CAFD (Coding Application Data File) → FDL parameters
```

- **CAFD**: A binary blob in each ECU containing all settable FDL values for
  that module. Named like `CAFD_0005638F_003_025.001`
- **NCD (Net-Coded Data)**: The actual coded values read from an ECU, stored
  as `.ncd` files. An NCD is a specific instance of a CAFD
- **FDL parameter**: Individual named settings like
  `KOMFORT_SCHLIESSEN` → `aktiv`/`nicht_aktiv`
- **Werte**: The possible values for a parameter; one is the default (used
  during VO-coding)

### CAFD Structure

```
Header
  Daten
    Functional Group (e.g., 3000 HMI)
      Aktivbedingung (activation conditions)
      Funktionen (functions)
        MACRO_PDC
          SpeicherInfo (format/storage metadata)
          aktiv       ← werte value
          nicht_aktiv ← werte value
```

### VO-Coding vs FDL-Coding

| Method | Description | Use Case |
|--------|-------------|----------|
| VO-Coding | Apply FA to ECU; ECU resets FDL to factory defaults for the FA | Adding/removing factory options, retrofits |
| FDL-Coding | Directly edit individual FDL parameters | Custom behavior (e.g., disable disclaimer, video-in-motion) |

### E-Sys Workflow

```
1. Connect to vehicle (via ENET, select target F020/F010/G020)
2. Read FA → Save to C:\Data\FA\
3. Read SVT (ECU tree) → Save to C:\Data\SVT\
4. Read Coding Data from ECU → CAFD/NCD saved to C:\Data\CAF\
5. Edit FDL → Modify parameters in FDL-Editor
6. Code FDL → Write modified NCD back to ECU
```

### BimmerCode's Expert Mode

BimmerCode's expert mode mirrors E-Sys's FDL-Editor:
- Reads the same CAFD/NCD data from ECUs
- Exposes the same FDL parameters
- Limits: only supports "safe" ECUs (no safety-critical modules like airbag)
- Advantage: mobile/tablet-based, no need for Windows VM

---

## 5. CBS: Condition Based Service

### System Architecture

CBS tracks maintenance items based on sensors, driving data, and elapsed time
rather than fixed intervals. Each module holds its own counters:

| Module | CBS Items Tracked |
|--------|-------------------|
| DME/DDE | Engine oil, spark plugs, air filter, fuel filter |
| KOMBI | Brake pads (front/rear), vehicle check |
| IBO (integrated) | Brake fluid, microfilter, other items |

### CBS Data Structure (per item)

- **Percentage of wear** (0-100%, 100% = new)
- **Forecast distance remaining** (km/miles until due)
- **Forecast time remaining** (days/date until due)
- **Service Counter**: Incremented each time the item is reset
- **Due date**: Computed from above

### CBS Service Intervals (typical)

| Service | Time Interval | Mileage Interval |
|---------|---------------|------------------|
| Engine Oil | 24 months (or 12 months post-07/2013) | Varies by driving |
| Brake Fluid | 36 months initial, 24 months subsequent | — |
| Vehicle Check | 48 months | ~40,000 miles |
| Microfilter | ~24 months | ~30,000 miles |
| Spark Plugs | ~48-60 months | ~60,000 miles |

### CBS Reset (Instrument Cluster Method)

1. Press trip reset button until first CBS item appears
2. Scroll to desired item
3. Display shows "Reset executable" if possible
4. Press and hold to initiate reset
5. Progress bar → "Reset successful"

### CBS Reset via UDS

UDS RoutineControl (0x31) with specific routine identifiers per CBS item.
The exact routine IDs vary by ECU/vehicle generation and are not publicly
standardized.

### Service History in Headunit

The headunit (CIC, NBT, NBT EVO, MGU) stores a local service history
separate from CBS counters. This is the **record of performed maintenance**
— what was done, when, at what mileage, and by whom.

---

## 6. BMW ECU Naming Reference

### Core ECUs

| Acronym | Name | Function |
|---------|------|----------|
| **ZGW** | Zentrales Gateway | Central gateway; Ethernet router; TCP server for diagnostics |
| **DME** | Digital Motor Electronics | Petrol engine management |
| **DDE** | Digital Diesel Electronics | Diesel engine management |
| **EGS** | Elektronische Getriebesteuerung | Transmission control |
| **KOMBI** | Kombiinstrument | Instrument cluster; holds some CBS data |
| **FEM_BODY** | Front-Elektronik-Modul Body | F-series front body controller (ZGW+FRM+CAS+JBBF combined) |
| **BDC_BODY** | Body Domain Controller | G-series body domain controller (ZGW+FEM+REM+SZL+IHKA+TCB+CAS+JBBF) |
| **CAS** | Car Access System | Key authentication, immobilizer |
| **FRM** | Fußraummodul | Footwell module (lighting) |
| **JBBF** | Junction Box Beifahrer | Passenger-side fuse box controller |

### Headunits (Infotainment)

| Acronym | Name | Generation | Vehicles |
|---------|------|------------|----------|
| **CIC** | Car Information Computer | E9x, early F-series | ~2008-2013 |
| **NBT** | Next Big Thing | F-series | ~2013-2017 |
| **NBT EVO** | NBT Evolution | Late F-series, early G-series | ~2016-2019 |
| **HU_MGU** | Head Unit MGU (Media Graphics Unit) | G-series | ~2019+ |
| **HU_ENTRY** | Head Unit Entry | Base model headunit | Various |

### Other Important ECUs

| Acronym | Function |
|---------|----------|
| DSC | Dynamic Stability Control (ABS/traction) |
| EKP | Electric fuel pump |
| EPS | Electric power steering |
| ICM | Integrated Chassis Management |
| IHKA | Automatic climate control |
| PDC | Park Distance Control |
| RDC | Tire pressure monitoring |
| SZL | Steering column switch cluster |
| TCB | Telematics communication box |
| VDM | Vertical dynamics management (adaptive suspension) |

---

## 7. Tool32 & EDIABAS: Service History Protocol

### Tool32 Architecture

**Tool32** is BMW's low-level ECU communication tool, part of the EDIABAS
(ELektronik DIAgnose BASis) toolset. It sends jobs directly to ECUs:

```
Tool32 → EDIABAS API → PRG file (job definitions) → ENET/DoIP → ZGW → Target ECU
```

Key components:
- **PRG files**: ECU-specific program files defining available jobs,
  arguments, and return types (e.g., `NBT.PRG`, `CIC.PRG`, `HU_MGU.PRG`)
- **GRP files**: Group files that bundle related PRGs (e.g., `g_mmi.grp`)
- **Jobs**: Named operations like `STEUERN_SERVICEHISTORY_ADD`
- **EDIABAS API**: The communication layer that routes jobs over the
  cable (K+DCAN, ENET, or ICOM)

### Service History Job: `STEUERN_SERVICEHISTORY_ADD`

This is the exact job that BMW's Service History Manager (SHM.exe)
implements. The job writes a service record into the headunit's locally
stored service history.

**Source:** [BimmerGuide.de — Service Historie: Eintrag mit Tool32](https://www.bimmerguide.de/service-historie-eintrag-mit-tool32/)

#### PRG Files Per Headunit

| Headunit | PRG File | Job Name |
|----------|----------|----------|
| CIC | `CIC.PRG` | `STEUERN_SERVICEHISTORY_ADD` |
| NBT | `NBT.PRG` | `STEUERN_SERVICEHISTORY_ADD` |
| NBT EVO | `NBTEVO.PRG` | `STEUERN_SERVICEHISTORY_ADD` |
| MGU | `HU_MGU.PRG` | `STEUERN_SERVICEHISTORY_ADD` |

Erase jobs also exist: `STEUERN_SERVICEHISTORY_ERASE` /
`STEUERN_SERVICEHISTORY_DEL` (no arguments, deletes the ENTIRE history).

#### Argument String Format

All PRG files use the **same semicolon-delimited argument format**:

```
Day;Month;Year;CorrectionCounter;Kilometer;DealerFlag;DealerID;Status;Count;
[Code;ItemStatus;RemainingDistance;RemainingTime;]... (up to 13 items)
```

#### Base Fields (9 fields, always present)

| # | Field | Type | Description |
|---|-------|------|-------------|
| 1 | Day | uint8 | Day of service (1-31) |
| 2 | Month | uint8 | Month of service (1-12) |
| 3 | Year | uint16 | Four-digit year (e.g., 2026) |
| 4 | Correction Counter | uint8 | 0 for new entry; increment for corrections |
| 5 | Kilometer | uint32 | Odometer in km (always km, even if car shows miles) |
| 6 | Dealer Flag | uint8 | `0` = independent, `1` = BMW dealer |
| 7 | Dealer ID | ASCII | Up to 7 ASCII characters (no umlauts/special chars) |
| 8 | Overall Status | uint8 | `0x1` = completed, `0x2` = delayed, `0x3` = incomplete |
| 9 | Item Count | uint8 | Number of service items (max 13) |

#### Per-Item Fields (4 fields each, up to 13 items)

| # | Field | Type | Description |
|---|-------|------|-------------|
| 1 | Code | uint8 | Service code (see table below) |
| 2 | Item Status | uint8 | `0x1` = performed, `0x2` = delayed, `0x3` = overdue |
| 3 | Remaining Distance | sint32 | Signed; `0` for completed on-time |
| 4 | Remaining Time | uint32 | Non-negative; `0` for completed on-time |

#### Example Argument String

Oil + brake fluid + microfilter at 125,000 km, independent shop "WERKST":

```
01;08;2026;0;125000;0;WERKST;0x1;3;1;0x1;0;0;3;0x1;0;0;4;0x1;0;0;
```

#### Return Values

**All headunits:** `JOB_STATUS = OKAY` on success.

**STAT_SH_ADD_WERT per headunit:**

| Headunit | Success | Memory Error | Data Inconsistency | No Permission | Unknown Error |
|----------|---------|--------------|-------------------|---------------|---------------|
| CIC | `0x01` | `0x02` | `0x03` | — | — |
| NBT | `0x00` | `0x01` | `0x02` | `0x04` | `0x05` |
| NBT EVO | `0x00` | `0x01` | `0x02` | `0x04` | `0x05` |
| MGU | `0x00` | `0x01` | `0x02` | `0x04` | `0x05` |

**Key difference:** CIC uses offset values (success = `0x01`), all others
use zero-based (success = `0x00`).

---

## 8. Complete Service Code Reference Table

The `ARG_WARTUNGSTEXT` parameter is `unsigned char` (0-255). Source: PRG
files (reported by BimmerGuide.de).

| Dec | Hex | Label |
|-----|-----|-------|
| 1 | `0x01` | Engine oil |
| 2 | `0x02` | Brake pads front |
| 3 | `0x03` | Brake fluid |
| 4 | `0x04` | Microfilter / cabin filter |
| 5 | `0x05` | Service Inclusive |
| 6 | `0x06` | Brake pads rear |
| 7 | `0x07` | Particulate filter |
| 8 | `0x08` | State of Health / battery (software-dependent) |
| 9 | `0x09` | QMV-H oil |
| 10 | `0x0A` | Spark plugs / glow plugs (adaptive, software-dependent) |
| 11 | `0x0B` | Air filter element |
| 12 | `0x0C` | Fuel filter |
| 13 | `0x0D` | NOx additive |
| 16 | `0x10` | Spark plugs |
| 17 | `0x11` | Visual inspection / vehicle check |
| 18 | `0x12` | Coolant |
| 19 | `0x13` | H2 check |
| 20 | `0x14` | Pre-delivery inspection |
| 21 | `0x15` | Break-in inspection |
| 22 | `0x16` | Particulate filter additive |
| 23 | `0x17` | Water filter |
| 24 | `0x18` | Gas pressure spring |
| 32 | `0x20` | Vehicle inspection / MOT |
| 33 | `0x21` | Emissions test |
| 35 | `0x23` | Transmission oil (AT/DCT, system-dependent) |
| 49 | `0x31` | Tire age |
| 50 | `0x32` | Clutch |
| 51 | `0x33` | Gas pressure damper (active pedestrian protection) |
| 52 | `0x34` | First aid kit |
| 53 | `0x35` | Tire Fit |
| 54 | `0x36` | Catalytic converter |
| 55 | `0x37` | Shock absorber |
| 97 | `0x61` | Service safety vehicle |
| 100 | `0x64` | Visual inspection / vehicle check (combined) |
| 224 | `0xE0` | CBS Evalboard (internal test) |
| 225 | `0xE1` | CBR Evalboard (internal test) |
| 255 | `0xFF` | Delivery state (special state) |

**Notes:**
- Not all codes are visible/useful on every headunit version
- Some labels differ between vehicle and software versions
- Code 10 (`0x0A`) and 16 (`0x10`) can both represent spark plugs
  depending on software version

---

## 9. Coding Communication Flow (BimmerCode / E-Sys)

### Reading ECU Coding Data

```
1. Establish DoIP/HSFZ connection to ZGW
2. Routing activation to target ECU (e.g., FEM_BODY @ 0x40)
3. UDS DiagnosticSessionControl → Extended (0x03)
4. UDS SecurityAccess (0x27) → Seed/Key exchange if required
5. UDS ReadDataByIdentifier (0x22):
   - VIN (DID 0xF190)
   - FA/Vehicle Order (ECU-specific DID)
   - SVT (ECU tree from ZGW)
   - CAFD data (ECU-specific DIDs for coding blocks)
6. Parse CAFD → Present as FDL parameters in editor
```

### Writing ECU Coding Data

```
1. Same connection + session as reading
2. Modified FDL parameters → serialized back to NCD format
3. UDS WriteDataByIdentifier (0x2E) with coding DIDs
4. ECU validates signature/CPS (Code Verification Stamp)
5. ECU applies changes (may require ECU reset)
```

### BimmerCode-Specific Flow (Curated Mode)

BimmerCode's "basic mode" uses a **curated database** of tested coding
presets per model. Rather than reading/writing raw FDL, it:

1. Identifies vehicle model and ECUs
2. Looks up compatible coding presets from its internal database
3. Shows user-friendly toggle descriptions
4. Translates user selections to the correct FDL parameters
5. Writes only the changed parameters

This database is the key differentiator — it contains validated
"cheat codes" for each BMW model/ECU combination.

---

## 10. Diagnostics Communication Flow (BimmerLink)

### Reading Live Sensor Data

```
1. Connect via ENET → DoIP/HSFZ
2. Routing activation to target ECU (e.g., DME @ 0x12)
3. UDS DiagnosticSessionControl → Extended (0x03)
4. UDS ReadDataByIdentifier (0x22) with sensor DIDs:
   - Engine RPM (DID varies by ECU)
   - Coolant temperature
   - Oil temperature
   - Battery voltage
   - Boost pressure
   - Lambda/AFR values
   - Exhaust gas temperature
   - DPF soot mass (diesel)
   - etc.
5. Parse and display live values
```

### Reading/Clearing DTCs

```
Reading:
  1. Extended session
  2. UDS ReadDTCInformation (0x19):
     - Sub-function 0x01: Report number of DTCs by status mask
     - Sub-function 0x02: Report DTCs by status mask
     - Sub-function 0x04: Report snapshot (freeze frame) by DTC
     - Sub-function 0x06: Report extended data by DTC

Clearing:
  1. Extended session
  2. UDS ClearDiagnosticInformation (0x14) with DTC group
```

### BMW-Specific Diagnostic Addressing

ECU diagnostic addresses (logical addresses for routing):

| ECU | Typical Address |
|-----|-----------------|
| ZGW | 0x10 |
| DME/DDE | 0x12 |
| EGS | 0x18 |
| KOMBI | 0x60 |
| FEM_BODY / BDC_BODY | 0x40 |
| DSC | 0x29 |
| Headunit (CIC/NBT/MGU) | 0x63 |
| EPS | 0x30 |
| IHKA | 0x78 |

**Note:** Exact addresses vary by model and generation; always read from
vehicle at connection time.

---

## 11. Connection Architecture Summary

```
┌─────────────┐     ENET Cable     ┌──────────────┐     CAN/Ethernet    ┌──────────┐
│   Laptop    │ ◄────────────────► │   ZGW/BDC    │ ◄─────────────────► │   ECU    │
│  (Tester)   │    100BASE-TX      │  (Gateway)   │    Internal Bus     │ (Target) │
└─────────────┘                    └──────────────┘                     └──────────┘
      │                                   │
      │  Ethernet (RJ45)                  │  OBD2 Port (pins 3,11,12,13)
      │                                   │
      │  ┌─ TCP 6801 (HSFZ, legacy)       │
      │  ├─ TCP 13400 (DoIP)              │
      ├──┤                                │
      │  ├─ UDP 6811 (HSFZ discovery)     │
      │  └─ UDP 13400 (DoIP discovery)    │
      │                                   │
      │  ┌─ EDIABAS API (Tool32, INPA)    │
      │  └─ Direct socket (BimmerCode,    │
      │     BimmerLink, custom apps)      │
```

---

## 12. Key References

1. **ISO 13400**: Road vehicles — Diagnostic communication over Internet
   Protocol (DoIP), Parts 1-4
2. **ISO 14229**: Road vehicles — Unified Diagnostic Services (UDS)
3. **ISO 14229-5**: UDSonIP — UDS over Internet Protocol
4. **AUTOSAR CP SWS DiagnosticOverIP**: Specification of DoIP module
   (R19-11, R21-11, R24-11)
5. **BimmerGuide.de**: Service history entry with Tool32 — definitive
   reference for the `STEUERN_SERVICEHISTORY_ADD` protocol
6. **python-doipclient** (jacobschaer): Open-source DoIP client
   implementation in Python
7. **ediabaslib** (uholeschak): .NET library for reading/interpreting
   EDIABAS GRP/PRG files
8. **rawenet** (rawmind0): Open-source reverse engineering of BMW HSFZ
   protocol
9. **scapy** (scapy.contrib.automotive.doip): DoIP packet implementation
   for packet manipulation

---

## 13. Research Gaps & Unknowns

1. **Exact DID mappings**: The specific Data Identifiers used for
   FDL coding parameters, sensor values, and service functions are
   ECU-specific and not publicly documented. Reversing the APKs
   (Phases 2-3) should reveal the app's DID table.

2. **SecurityAccess algorithm**: The seed/key exchange for level 1/3/5
   access varies by ECU. BimmerCode/BimmerLink likely contain the
   algorithms for the ECUs they support.

3. **HSFZ framing details**: The exact header structure of BMW's
   proprietary HSFZ protocol over TCP 6801 is documented by rawenet
   but needs confirmation against the apps.

4. **BimmerCode curated database format**: Unknown whether it's JSON,
   SQLite, protobuf, or custom binary. Phase 2 should reveal this.

5. **FA calculation algorithm**: E-Sys can "calculate" an FA (compute
   what coding an ECU would get from an FA), but this algorithm is
   proprietary.

6. **DoIP vs HSFZ switching**: How apps detect which protocol to use
   (auto-negotiation, user selection, or vehicle database lookup).

7. **Model detection**: How the apps identify the vehicle model (VIN
   decoding, FA parsing, or manual selection).

---

> **Next Phase:** Phase 2 — Reverse engineer BimmerCode APK to understand
> the coding database, communication layer, and expert mode implementation.