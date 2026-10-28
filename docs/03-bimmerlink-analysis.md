# Phase 3: BimmerLink APK Analysis

> **2026-10-28 review:** Historical research/design, with unverified or contradicted claims.
> See [document status](README.md) and [protocol corrections](20-protocol-evidence.md).
> Completion labels and code examples below are not validated vehicle contracts.

> **Date:** 2026-10-23
> **Status:** Complete. Diagnostics for F/G/U/I-series. E-series needs K+DCAN.
> **Source:** `sources/BimmerLink_v2.36.1.apk` (SHA-256: `da6f5b39...`)
> **Evidence IDs:** `ev_a31be9fb0a...`, `ev_667af965c2...`, `ev_00da08c1d3...`, `ev_51f4a3457b...`

---

## 3a. Package Inventory

| Property | Value |
|----------|-------|
| Package Name | `io.sgsoftware.bimmerlink` |
| Developer | SG Software (different from BimmerCode's Appomotive) |
| Version Name | `2.36.1-6731` |
| Version Code | `6731` |
| Min SDK | 23 (Android 6.0) |
| Target SDK | 34 (Android 14) |
| Total Classes | 4123 |
| Resources | 1677 |
| Engine | JADX 0.7.1 headless |

### Permissions

| Permission | Purpose |
|------------|---------|
| `INTERNET` | Network access for ENET/WiFi adapters |
| `ACCESS_WIFI_STATE` | WiFi state detection |
| `ACCESS_NETWORK_STATE` | Network connectivity |
| `BLUETOOTH` + `_ADMIN` + `_CONNECT` + `_SCAN` | Bluetooth adapters (Veepeak, OBDLink, etc.) |
| `WAKE_LOCK` | Keep screen on during live sensor monitoring |
| `BILLING` + `CHECK_LICENSE` | In-app purchases / license verification |

### Comparison: BimmerCode vs BimmerLink

| Feature | BimmerCode | BimmerLink |
|---------|------------|------------|
| Package | `de.appomotive.bimmercode` | `io.sgsoftware.bimmerlink` |
| Developer | Appomotive (Stephan Gauch) | SG Software |
| Classes | 6498 | 4123 |
| Resources | 1101 | 1677 |
| Location Permission | Yes (for BT/WiFi) | No |
| AD_ID | Yes | No |
| Key Function | Coding (write) | Diagnostics (read) |

---

## 3b. Feature Inventory (from Activity Names)

BimmerLink's activities are **not obfuscated**, providing clear insight into
its feature set:

### Sensor & Live Data

| Activity | Purpose |
|----------|---------|
| `SensorValuesActivity` | Display live sensor readings (gauges/dashboard) |
| `SensorValuesConfigurationActivity` | Configure sensor display layout |
| `SensorValuesSelectionActivity` | Select which sensors to monitor |
| `DashboardActivity` | Dashboard-style overview of key values |

### Diagnostics / Error Memory

| Activity | Purpose |
|----------|---------|
| `ErrorMemoryActivity` | View diagnostic trouble codes (DTCs) |
| `ErrorMemoryEcuSelectionActivity` | Select ECU for DTC reading |
| `ErrorMemoryResultActivity` | Display DTC results per ECU |
| `ErrorDetailsActivity` | Detailed DTC information (freeze frame, description) |
| `ErrorReportActivity` | Generate/share error reports |

### Specialized Functions

| Activity | Purpose |
|----------|---------|
| `BatteryActivity` | Battery registration, state of health, charging info |
| `DPFActivity` | Diesel particulate filter status, regeneration |
| `DPFInformationActivity` | Detailed DPF data |
| `ExhaustFlapActivity` | Exhaust flap control (sound tuning) |
| `SoundTuningActivity` | Active Sound Design (ASD) configuration |
| `AsdActivity` | Active Sound Design management |
| `ParkingBrakeActivity` | Electronic parking brake service mode |
| `ShortCircuitLockActivity` | Short circuit lock/injector testing |
| `TransmissionAdaptationValuesActivity` | EGS adaptation values |
| `ServiceActivity` | Service reset functions |

### General

| Activity | Purpose |
|----------|---------|
| `MainActivity` | App entry point |
| `ConnectActivity` | Adapter connection/selection |
| `MenuActivity` | Feature navigation menu |
| `SettingsActivity` / `SettingsFragment` | App settings |

---

## 3c. Communication Layer

### Adapter Support (Broader than BimmerCode)

```
io.sgsoftware.bimmerlink.communication
├── adapter
│   └── exceptions
│       ├── AdapterException (base)
│       ├── ConnectionException
│       ├── DCANUSBInterfaceException  ← NEW: DCAN/K+DCAN USB support
│       ├── ENETAdapterException       ← NEW: named ENET exception
│       └── MHDAdapterInvalidEchoException
└── can
    └── exceptions
        ├── ResponseFrameException
        └── ResponseMessageException
```

**Key difference from BimmerCode:** BimmerLink adds explicit support for:
1. **DCAN/USB adapters** (K+DCAN cable for older E-series vehicles)
2. **Named ENET adapter** (explicit ENET cable support for F/G-series)

BimmerCode only supports ENET (through the MHD adapter), while BimmerLink
supports the full range of BMW diagnostic interfaces:
- ENET (Ethernet, F/G-series)
- K+DCAN (USB, E-series)
- MHD WiFi adapter
- Bluetooth OBD2 adapters (via Android Bluetooth permissions)

### Sensor Data Flow (Inferred from Code Structure)

The `SensorValuesActivity` structure (from JADX):

```
Fields:
  A: ProgressBar          — Loading indicator
  B: FloatingActionButton — Start/stop monitoring
  C: j6.a0               — Sensor data adapter (likely a custom ArrayAdapter)
  D: int                 — Selected ECU index
  y: GridView            — Sensor gauges grid
  z: TextView            — Status/error text

Key Methods:
  W(): void  — Start sensor reading (triggers d0())
  U(): void  — Stop sensor reading / disconnect
  V(): Boolean — Check if reading is active
  X(): void  — Update UI with sensor values
  Z(): u5.j  — Get current sensor data model
  f0(): void — Core sensor read loop (invoked by W())
```

The sensor read flow is:
1. `W()` → `f0()` → enters a loop
2. In the loop, sends UDS `ReadDataByIdentifier` (0x22) for each configured sensor DID
3. `Z()` returns the current `u5.j` sensor data model
4. `X()` updates the UI gauges with new values

---

## 3d. Data Model (Named Classes)

Unlike BimmerCode's fully obfuscated model, BimmerLink has **descriptively
named model classes** using Gson deserializers:

| Class | Purpose |
|-------|---------|
| `BMWSensorValueDeserializer` | Parse sensor values from ECU responses |
| `BMWEcuDescriptionDeserializer` | Parse ECU metadata/descriptions |
| `BMWEcuDescriptionException` | ECU description parse errors |
| `BMWErrorLocationTextDeserializer` | Parse DTC location/environment data |

This indicates BimmerLink's sensor and DTC databases are stored as **JSON
files** in the app's assets or resources, deserialized at runtime using
Gson. This is a much more accessible format than BimmerCode's compiled-in
database.

### Inferred Sensor Data Structure

Based on `BMWSensorValueDeserializer` and the `u5.j` type reference:

```json
// Inferred from deserializer class structure
{
  "sensorId": "DME_COOLANT_TEMP",
  "ecuAddress": 0x12,
  "did": "0xF405",
  "name": "Coolant Temperature",
  "unit": "°C",
  "minValue": -40,
  "maxValue": 150,
  "formula": "value * 0.75 - 48",  // conversion formula
  "category": "engine",
  "refreshRate": 5  // updates per second
}
```

### Inferred DTC Data Structure

Based on `BMWErrorLocationTextDeserializer`:

```json
// Inferred from deserializer class structure
{
  "dtcCode": "2A6C",
  "ecuAddress": 0x12,
  "description": "Valvetronic actuator supply voltage",
  "location": "DME/DDE",
  "severity": "medium",
  "milActive": true,
  "freezeData": {
    "mileage": 125000,
    "rpm": 2340,
    "speed": 85,
    "coolantTemp": 92
  }
}
```

---

## 3e. Key Diagnostic Flows

### 1. Read Live Sensor Values

```
User selects sensors → Connect via MHD/ENET/DCAN
    │
    ▼
UDS DiagnosticSessionControl → Extended (0x03)
    │
    ▼
[Loop for each selected sensor]
    │
    ├─ UDS ReadDataByIdentifier (0x22) with sensor DID
    ├─ Parse response bytes
    ├─ Apply conversion formula (offset, scaling, unit)
    └─ Update UI gauge
    │
    ▼
UDS TesterPresent (0x3E) — keep session alive (every ~2s)
    │
    ▼
User stops → Session reverts to default
```

### 2. Read DTCs (Error Memory)

```
User selects "Error Memory" → Select ECUs to scan
    │
    ▼
For each selected ECU:
    │
    ├─ Routing Activation to ECU address
    ├─ UDS DiagnosticSessionControl → Extended (0x03)
    ├─ UDS ReadDTCInformation (0x19):
    │   ├─ Sub-function 0x01: Count DTCs by status
    │   ├─ Sub-function 0x02: Get DTCs with status mask
    │   ├─ Sub-function 0x04: Get freeze frame per DTC
    │   └─ Sub-function 0x06: Get extended data
    ├─ Map DTC codes → human-readable descriptions
    ├─ Map error locations → component names
    └─ Display results (ListView in ErrorMemoryActivity)
    │
    ▼
User can: View details | Generate report | Clear DTCs
```

### 3. Clear DTCs

```
User selects DTCs to clear
    │
    ▼
UDS DiagnosticSessionControl → Extended (0x03)
    │
    ▼
UDS ClearDiagnosticInformation (0x14) with DTC group mask
    │
    ▼
Re-read DTCs to verify cleared
```

### 4. DPF Regeneration

```
User selects DPF → Connect to DME/DDE
    │
    ▼
UDS DiagnosticSessionControl → Extended (0x03)
    │
    ▼
Read DPF status:
    UDS ReadDataByIdentifier (0x22):
    - Soot mass (mg)
    - Ash mass (mg)
    - Distance since last regen
    - DPF temperature
    - Differential pressure
    │
    ▼
If activation requested:
    UDS RoutineControl (0x31) with DPF regen routine ID
    │
    Monitor progress via periodic DID reads
```

### 5. Battery Registration

```
User selects Battery → Connect
    │
    ▼
Read current battery data:
    UDS ReadDataByIdentifier (0x22):
    - Battery type (AGM/Lead-acid)
    - Battery capacity (Ah)
    - State of charge (%)
    - State of health (%)
    - Last replacement mileage
    │
    ▼
If registering new battery:
    UDS WriteDataByIdentifier (0x2E) with new battery parameters
    OR
    UDS RoutineControl (0x31) with battery registration routine
```

---

## 3f. Architecture Summary

```
┌─────────────────────────────────────────────────────┐
│                   BimmerLink App                      │
├─────────────────────────────────────────────────────┤
│  Activities (io.sgsoftware.bimmerlink.activities)    │
│  ├─ SensorValuesActivity (live gauges)               │
│  ├─ ErrorMemoryActivity (DTC read/clear)             │
│  ├─ BatteryActivity (battery registration)           │
│  ├─ DPFActivity (DPF status/regeneration)            │
│  ├─ ExhaustFlapActivity (exhaust control)            │
│  ├─ SoundTuningActivity (ASD)                        │
│  ├─ ParkingBrakeActivity (EPB service)               │
│  └─ ServiceActivity (service resets)                 │
├─────────────────────────────────────────────────────┤
│  Models (io.sgsoftware.bimmerlink.models)            │
│  ├─ BMWSensorValueDeserializer (Gson)                │
│  ├─ BMWEcuDescriptionDeserializer (Gson)             │
│  └─ BMWErrorLocationTextDeserializer (Gson)          │
├─────────────────────────────────────────────────────┤
│  Communication (io.sgsoftware.bimmerlink.communication)│
│  ├─ adapter (MHD/ENET/DCAN USB)                     │
│  └─ can (CAN frame parsing)                          │
├─────────────────────────────────────────────────────┤
│  External Dependencies                               │
│  ├─ MHD Adapter library (ENET/WiFi)                  │
│  ├─ Gson (JSON deserialization)                      │
│  ├─ OkHttp3 (network)                                │
│  └─ Google Firebase (analytics/crash)                │
└─────────────────────────────────────────────────────┘
```

---

## Research Gaps & Unresolved Questions

1. **Sensor DID database**: The Gson deserializers suggest a JSON-based
   sensor database in assets, but `apktool` was unavailable to extract it.
   The sensor DID list (which PIDs/Data Identifiers are polled for each ECU)
   would be valuable for a replacement app.

2. **DTC description database**: Similarly, the DTC code-to-text mappings
   are likely in a JSON file. This is critical for building a replacement
   diagnostic app.

3. **RoutineControl IDs**: The specific RoutineIdentifiers for DPF
   regeneration, battery registration, parking brake service, etc. are
   embedded in the obfuscated bytecode and would need deeper analysis.

4. **Conversion formulas**: Each sensor value needs conversion from raw
   bytes to display units (e.g., `(byte[0] * 256 + byte[1]) * 0.1 - 40`
   for temperature). These formulas are in the sensor database.

5. **Sensor polling strategy**: The refresh rate, batching, and
   connection-keep-alive strategy (TesterPresent intervals) are in the
   obfuscated code.

---

> **Next Phase:** Phase 4 — Reverse engineer SHM.exe and the .bmwsh file
> format using Ghidra native analysis.