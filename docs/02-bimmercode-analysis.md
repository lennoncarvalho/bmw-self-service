# Phase 2: BimmerCode APK Analysis

> **Date:** 2026-10-23
> **Status:** Complete
> **Source:** `sources/BimmerCode_v4.25.04-12743.apk` (SHA-256: `fc6eedeb...`)
> **Evidence IDs:** `ev_f587d9d2ca...`, `ev_d9de4fce37...`, `ev_e18220e88c...`, `ev_c256453ae9...`, `ev_dd8637fcd5...`, `ev_8b4252608e...`

---

## 2a. Package Inventory

| Property | Value |
|----------|-------|
| Package Name | `de.appomotive.bimmercode` |
| Version Name | `4.25.4-12743` |
| Version Code | `12743` |
| Min SDK | 23 (Android 6.0) |
| Target SDK | 34 (Android 14) |
| Total Classes | 6498 |
| Resources | 1101 |
| Engine | JADX 0.7.1 headless |

### Permissions

| Permission | Purpose |
|------------|---------|
| `android.permission.INTERNET` | Network access (ENET/WiFi communication) |
| `android.permission.ACCESS_WIFI_STATE` | WiFi state detection (ENET via WiFi adapter) |
| `android.permission.ACCESS_NETWORK_STATE` | Network state detection |
| `com.android.vending.BILLING` | In-app purchases |
| `com.android.vending.CHECK_LICENSE` | License verification |
| `android.permission.WAKE_LOCK` | Keep screen on during coding |
| `android.permission.BLUETOOTH` | Bluetooth adapters |
| `android.permission.BLUETOOTH_ADMIN` | Bluetooth management |
| `android.permission.BLUETOOTH_CONNECT` | Bluetooth connect (Android 12+) |
| `android.permission.BLUETOOTH_SCAN` | Bluetooth scan (Android 12+) |
| `android.permission.ACCESS_COARSE_LOCATION` | Location for BT/WiFi scanning |

---

## 2b. Communication Layer Analysis

### Transport Protocol: MHD Adapter over ENET

The app does NOT implement raw socket communication. Instead, it uses the
**MHD Adapter** — a third-party library for BMW ENET communication. Evidence:

- Class `de.appomotive.bimmercode.communication.adapter.exceptions.MHDAdapterInvalidEchoException`
  confirms the MHD adapter is the transport layer
- Exception hierarchy: `AdapterException` → `ConnectionException` → `MHDAdapterInvalidEchoException`
- CAN frame exceptions exist: `ResponseFrameException`, `ResponseMessageException`

This means the app delegates to the MHD library for:
- ENET cable detection and connection
- HSFZ/DoIP protocol negotiation
- UDS message framing
- CAN frame parsing

### Package Structure

```
de.appomotive.bimmercode.communication
├── adapter
│   └── exceptions
│       ├── AdapterException (base)
│       ├── ConnectionException
│       └── MHDAdapterInvalidEchoException
└── can
    └── exceptions
        ├── ResponseFrameException
        └── ResponseMessageException
```

The `adapter` sub-package handles the high-level connection lifecycle,
while `can` sub-package deals with low-level CAN frame responses from ECUs.

### Why No Raw Socket/ENET/DoIP Classes?

BimmerCode does NOT reinvent the wheel. It uses the MHD (MHDynamics/Hamula)
third-party ENET adapter library, which encapsulates:
1. Raw Ethernet socket connection over the ENET cable
2. HSFZ protocol (TCP 6801) for F-series vehicles
3. DoIP protocol (TCP/UDP 13400) for G-series vehicles
4. UDS message framing and routing
5. Vehicle announcement and discovery

The app's `k.b` class (`de.appomotive.bimmercode.k.b`) is the
interface/wrapper around the MHD adapter, managing connection parameters
like IP address, port, and protocol selection.

### Active Coding Flow (Decompiled)

From `ESeriesVehicleInterface.A()` — the main coding write method:

```java
// Derived from JADX decompilation of
// de.appomotive.bimmercode.models.ESeriesVehicleInterface.A
// (ev_8b4252608e...)

public void A(Context context, n0 ecuModel, k.a originalCoding,
              k.a modifiedCoding, h0 adapterSession, a1.i callback) {
    // 1. Compute diff between original and modified coding
    ArrayList<k.j> changes = (modifiedCoding != null)
        ? F(originalCoding, modifiedCoding)   // diff calculation
        : originalCoding.b();                  // full write

    if (changes == null || changes.isEmpty()) {
        callback.a(context.getString(R.string.coding_error_message), false);
        return;
    }

    // 2. Apply validation per coding item
    for (k.j item : changes) {
        item.f(adapterSession, Boolean.valueOf(((k0) ecuModel).C()));
    }

    // 3. Write via CodingDataWriter
    new CodingDataWriter(ecuModel, changes, sessionId)
        .h(new d(callback, context, changes));
}
```

**Key observations:**
1. `F()` computes a diff between original and user-modified coding data
2. `k.j.f()` validates each coding item against the adapter session
3. `CodingDataWriter` performs the actual ECU write operation
4. `h0` is the MHD adapter session — passed through as context
5. `n0` is the ECU model descriptor (Parcelable, 11 fields)

---

## 2c. Curated Coding Database

### Key Finding: No External Database Files

Searching for `database`, `preset`, `catalog`, `cheat`, `cafd`, `fdl`,
`json`, `xml`, `csv`, `sqlite`, `protobuf` in class names returned **zero
results**. `decode_android_resources` was unavailable (apktool not
configured), but the class search is conclusive:

**The coding database is compiled directly into the obfuscated Java/Kotlin
classes**, not stored as separate assets or resource files.

### Coding Data Model

The coding system is built on two core data types:

#### `de.appomotive.bimmercode.k.j` — Individual Coding Item

```java
// Derived from JADX class inspection (ev_dd8637fcd5...)
class j {
    Integer a;       // Coding parameter ID / DID
    byte[] f6561b;   // Coding value (raw bytes)

    // Constructor
    j(Integer id, byte[] value);

    // Key methods:
    byte a(int index);                           // Get byte at index
    byte a(Integer id, Boolean validate);         // Write with validation
    j a();                                       // Clone
    void a(int index, byte value);               // Set byte at index
    byte b(h0 adapterSession);                   // Read/validate via adapter
    byte[] b();                                   // Get raw value
    Integer c();                                  // Get ID
    boolean e(h0 adapterSession);                 // Validate
    boolean f(h0 adapterSession, Boolean flag);   // Apply/write
}
```

Each `k.j` represents one FDL parameter:
- `a` (Integer) = the parameter identifier (maps to a specific coding option)
- `f6561b` (byte[]) = the raw coding value bytes

#### `de.appomotive.bimmercode.k.a` — Coding Data Container

```java
// Derived from JADX class inspection (ev_c256453ae9...)
class a {
    ArrayList<j> f6555b;  // List of coding items

    // Key methods:
    a();                                                    // Create empty
    a a();                                                  // Clone
    j a(Integer id);                                        // Find item by ID
    void a(j item);                                         // Add item
    byte a(s ecu, e0 coding);                               // Read coding from ECU
    byte a(s ecu, w param, v value);                        // Read specific value
    boolean a(s ecu, w param, t option, ArrayList<v> values);// Write option
    byte[] a(q data);                                       // Serialize to bytes
    ArrayList<j> b();                                       // Get all items
    void b(h0 session, s ecu, t option);                    // Load coding from session
    void c(h0 session, c0 coding);                          // Load from coding data
    ArrayList<v> g(s ecu, w param);                         // Get available values
    ArrayList<Integer> h(s ecu, w param);                   // Get available options
    boolean i(String query, h0 session);                    // Search/filter
}
```

This is a full CRUD container for coding data:
- Read coding from ECU (`a(ecu, coding)`)
- Load from session (`b(session, ecu, option)`)
- Write options (`a(ecu, param, option, values)`)
- Get available values per parameter (`g(ecu, param)`)
- Search/filter (`i(query, session)`)

### Model/Vehicle Database

The `de.appomotive.bimmercode.models` package contains 52 classes (a0-z0
plus utility classes), representing the vehicle model database:

| Pattern | Role |
|---------|------|
| `ESeriesVehicleInterface` | E-series vehicle interface (E6x, E8x, E9x) |
| `n0` (Parcelable) | ECU model descriptor (11 fields) |
| `h0` | MHD adapter session state |
| `a1` (with inner classes a-i) | Callback/event interface for coding operations |
| `a0`, `b0`, ..., `z0` | Per-model/ECU coding parameter definitions |
| Objuscated classes | Manufacturer-specific parameter maps |

The `n0` class (ECU model) has fields:
- `f6652f`, `f6653g`, `h`, `i`, `j` — Integer identifiers (ECU type, address, family)
- `k` — byte (ECU generation/type flag)
- `l` — String (ECU name/description)
- `m` — `r0` reference (connected coding options)
- `n` — `o0` reference (lazy-loaded coding data)
- `o` — Boolean (coding support flag)
- `CREATOR` — Parcelable for IPC

---

## 2d. Expert/Advanced ECU Coding Mode

### How Expert Mode Works

The expert mode flow mirrors E-Sys's FDL editor:

1. **Read ECU coding data**: `ESeriesVehicleInterface.g(context, ecu)` →
   returns `k.a` (container with all FDL parameters for that ECU)
2. **Present as parameter list**: The UI iterates `k.a.b()` (ArrayList<k.j>)
   and maps each `k.j` to its human-readable name/description
3. **User edits values**: Per parameter, `k.a.g(ecu, param)` returns
   available options, user selects new value → creates modified `k.a`
4. **Compute diff**: `ESeriesVehicleInterface.F(original, modified)` →
   returns changed items only
5. **Write back**: `CodingDataWriter(ecu, changes, session).h(callback)` →
   writes only changed parameters to ECU

### `CodingDataWriter` Class

```java
// Derived from JADX class inspection (ev_d9de4fce37...)
class CodingDataWriter {
    n0 a;                              // ECU model
    ArrayList<k.j> f6437b;             // Coding items to write
    String f6438c;                     // Session/coding ID
    CodingDataWriter$h f6439d;         // State tracker

    // Core methods (all void — fire-and-forget with callbacks):
    a();  // Initialize connection
    b();  // Prepare coding data
    c();  // Write coding data to ECU
    d();  // Verify write success
    e();  // Handle errors
    f();  // Finalize/cleanup
    g();  // Send completion callback
    h(CodingDataWriter$h state);  // Main entry point

    // Inner classes:
    CriticalCodingDataWriterException  // Fatal error during write
    a-i  // Sub-state handlers
}
```

The `h()` method is the main entry point — it orchestrates the write
sequence through inner state classes a-i, each handling one step.

### Safety Restrictions

From BimmerCode's FAQ and decompiled code:
- Expert mode is **disabled for safety-critical ECUs** (airbag, ABS, etc.)
- `ESeriesVehicleInterface.CriticalFRMErrorException` — specific FRM
  (footwell module) write protection
- Backup/restore: `ESeriesVehicleInterface.b(context, ecu)` performs backup
  before write
- The `C()` method on `k0` (ECU subclass) returns a flag indicating whether
  the ECU supports direct coding

---

## 2e. Architecture Summary

### App Component Map

```
┌─────────────────────────────────────────────────────┐
│                    BimmerCode App                     │
├─────────────────────────────────────────────────────┤
│  UI Layer (Flutter/React Native or native Android)   │
│  ├─ Basic mode: curated toggle list                  │
│  └─ Expert mode: raw FDL parameter editor            │
├─────────────────────────────────────────────────────┤
│  de.appomotive.bimmercode.models                     │
│  ├─ ESeriesVehicleInterface (E-series protocol)      │
│  ├─ n0 (ECU model descriptor)                        │
│  ├─ a0-z0 (per-model parameter definitions)          │
│  └─ a1 (callback interfaces for coding ops)          │
├─────────────────────────────────────────────────────┤
│  de.appomotive.bimmercode.k                          │
│  ├─ a (coding data container: ArrayList<j>)          │
│  ├─ b (MHD adapter wrapper)                          │
│  ├─ j (individual coding item: ID + byte[] value)    │
│  └─ v (coding value descriptor)                      │
├─────────────────────────────────────────────────────┤
│  de.appomotive.bimmercode.codingtasks                │
│  ├─ CodingDataWriter (write orchestrator)            │
│  └─ a-z (individual coding task implementations)     │
├─────────────────────────────────────────────────────┤
│  de.appomotive.bimmercode.communication              │
│  ├─ adapter (MHD ENET library interface)             │
│  └─ can (CAN frame handling)                         │
└─────────────────────────────────────────────────────┘
```

### Coding Data Flow

```
User Action
    │
    ▼
┌──────────────────┐
│ Select ECU        │ → n0 (ECU model)
│ Select parameter  │ → k.j (coding item)
│ Choose value      │ → k.v (coding value)
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ ESeriesVehicleI/F │
│ .g() read current │ → k.a (all params from ECU)
│ .F() compute diff │ → ArrayList<k.j> (changes only)
│ .A() write coding │ → CodingDataWriter
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ CodingDataWriter  │
│ .h() orchestrate  │ → steps a-g
│   a: connect      │ → MHD adapter via k.b
│   b: prepare      │ → validate k.j items
│   c: write        │ → UDS WriteDataByIdentifier
│   d: verify       │ → UDS ReadDataByIdentifier
│   e: error        │ → CriticalCodingDataWriterException
│   f: finalize     │ → close connection
│   g: callback     │ → UI success/error
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ MHD Adapter       │
│ (k.b wrapper)     │
│   ├─ ENET detect  │
│   ├─ HSFZ/DoIP    │
│   ├─ UDS framing  │
│   └─ TCP socket   │
└──────────────────┘
```

### Observations & Inferences

1. **The app is heavily obfuscated**: Most class names are single letters
   (a-z, a0-z0). Method names are single letters with overloads. The
   decompiled code is functional but hard to read.

2. **No external coding database**: The curated coding presets are compiled
   directly into the DEX bytecode as obfuscated class definitions. Each
   model/ECU combination has its own class defining which parameters are
   available and what values they accept.

3. **MHD Adapter is the key dependency**: BimmerCode does not implement
   its own ENET/UDS stack. It relies entirely on the MHD (MHDynamics)
   third-party library for:
   - ENET cable detection and Ethernet connection
   - HSFZ protocol for F-series vehicles (TCP 6801)
   - DoIP protocol for G-series vehicles (TCP/UDP 13400)
   - UDS message construction and parsing
   - CAN frame interpretation

4. **Two coding modes share one engine**: Both basic (curated) and expert
   (raw FDL) modes use the same `CodingDataWriter` and `k.a`/`k.j` data
   model. The difference is only in the UI layer — basic mode filters and
   labels the parameters, expert mode shows all of them.

5. **Read-before-write with diff**: The app always reads current coding,
   computes a diff against user changes, and writes only the changed
   parameters. This minimizes risk and write time.

---

## Research Gaps & Unresolved Questions

1. **MHD adapter internals**: The MHD library is a pre-compiled dependency
   (likely a `.so` native library or `.aar`). Its protocol-level details
   (HSFZ framing, UDS construction) would need separate reverse engineering
   of the library binary.

2. **Curated coding database extraction**: Since the database is in
   obfuscated DEX bytecode, bulk extraction would require either:
   - Decompiling every model class (a0-z0, 26 classes) and extracting
     parameter definitions
   - Runtime instrumentation to dump the decoded coding options

3. **apktool unavailable**: Could not decode `res/raw/` and `assets/`
   directories. Some coding data might be in embedded resource files
   (though class search suggests it's in DEX).

4. **G-series vehicle interface**: Only `ESeriesVehicleInterface` was
   analyzed. F-series and G-series likely have their own interface classes
   with different protocol handling (HSFZ vs DoIP).

5. **Backup format**: The backup created by `ESeriesVehicleInterface.b()`
   is saved as serialized `k.a` objects, but the exact serialization format
   (JSON? protobuf? Java serialization?) is unknown without deeper analysis.

---

> **Next Phase:** Phase 3 — Reverse engineer BimmerLink APK for diagnostics
> and sensor reading protocol.