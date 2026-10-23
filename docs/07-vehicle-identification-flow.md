# Vehicle Identification & ECU Compatibility Flow

> **Date:** 2026-10-23
> **Based on:** Decompiled BimmerCode APK classes + Phase 1 protocol research

---

## How BimmerCode goes from "car plugged in" to "here are your codings"

This is the complete flow your replacement app needs to replicate.

---

## Step 1: Physical Connection

```
User plugs ENET cable into OBD2 port → RJ45 into phone/tablet (via USB-C Ethernet adapter or WiFi OBD2 adapter)
```

The app detects the Ethernet link via the MHD adapter library. The ZGW wakes
up when pin 8 (activation line) sees voltage.

---

## Step 2: Vehicle Discovery

```
HSFZ (F-series):  UDP broadcast to 255.255.255.255:6811
DoIP (G-series):   UDP Vehicle Identification Request to 13400
```

The ZGW responds with:
- **VIN** (17-character Vehicle Identification Number)
- **Logical address** of the gateway
- **IP address** for TCP connection

```python
# Python equivalent (using python-doipclient)
from doipclient import DoIPClient

client = DoIPClient(ecu_ip_address, 13400)
vin = client.request_vehicle_identification()
# Returns: "WBA3E32050FZ99999"
```

---

## Step 3: TCP Connection + Session

```
HSFZ: TCP connect to <vehicle_ip>:6801
DoIP: TCP connect to <vehicle_ip>:13400, then Routing Activation
```

Then enter Extended Diagnostic Session:
```
UDS: 10 03  (DiagnosticSessionControl, Extended)
UDS: 3E 00  (TesterPresent, keep-alive)
```

---

## Step 4: Read VIN (Confirmation)

```
UDS ReadDataByIdentifier: 22 F1 90
Response: 62 F1 90 <17 ASCII chars>
```

The VIN encodes:
```
WBA 3E 32 0 5 0 F Z Z 9 9 9 9 9
│   │  │     │ │
│   │  │     │ └─ Model year: F=2015
│   │  │     └─ Check digit
│   │  └─ Model: 3E32 = F30 328i
│   └─ Series/body
└─ Manufacturer
```

**VIN position mapping from BimmerCode** (decompiled from `k0.D()`):
```java
// k0 constructor takes: byte type, byte[] data, int address
// k0.D() returns data[9] = ECU diagnostic address
// k0.E() returns "C" + hex(address) = e.g., "C40" for FEM_BODY at 0x40
```

---

## Step 5: Read FA (Vehicle Order / Fahrzeugauftrag)

The FA is the factory build sheet — it defines exactly which options the
car has. Read from ZGW:

```
UDS ReadDataByIdentifier: 22 <ZGW_FA_DID>
Response: <XML structure>
```

The FA contains:
```xml
<FA>
  <VIN>WBA3E32050FZ99999</VIN>
  <TypeCode>3E32</TypeCode>
  <ProductionDate>0715</ProductionDate>  <!-- July 2015 -->
  <SALAPA>
    <SA>522</SA>   <!-- Xenon headlights -->
    <SA>6NK</SA>   <!-- Enhanced Bluetooth -->
    <SA>5AC</SA>   <!-- High-beam assist -->
    <SA>609</SA>   <!-- Navigation Professional -->
    <!-- ... typically 30-60 option codes -->
  </SALAPA>
</FA>
```

---

## Step 6: Read SVT (ECU Tree)

The SVT is the list of every ECU physically present in the car:

```
UDS ReadDataByIdentifier from ZGW: <ZGW_SVT_DID>
Response: List of ECUs with:
  - Logical address (e.g., 0x40 for FEM_BODY)
  - ECU variant (e.g., "FEM_BODY", "BDC_BODY3")
  - Hardware number (e.g., "HW: 1234567")
  - Software version (e.g., "SW: F020-15-07-530")
  - CAFD IDs (which coding data files this ECU uses)
  - Diagnostic address
```

Example SVT response (conceptual):
```
ECU 0x40: FEM_BODY, HW: 9366888, SW: F020-15-07-530, CAFD: 000024C3-008-005-000
ECU 0x56: KOMBI   , HW: 9387447, SW: F020-15-07-530, CAFD: 00002660-007-003-072
ECU 0x63: HU_NBT  , HW: 9384153, SW: F020-15-07-530, CAFD: 00004694-014-056-005
ECU 0x12: DME     , HW: 8654321, SW: F020-15-03-501, CAFD: 0000570E-003-002-010
...
```

---

## Step 7: Model Detection (VIN + FA → Vehicle Model)

BimmerCode decodes the VIN and FA to determine the vehicle model:

```java
// Decompiled from BimmerCode's model detection logic
// The app uses a lookup table (salapa.enc, 2.4 MB encrypted)
// to map type codes and SALAPA options to models

String typeCode = vin.substring(3, 7);  // e.g., "3E32"

// Look up in vehicle database:
// 3E32 → F30 (3 Series Sedan, 2011-2019)
// 3E32 + production 0715 → F30 LCI (facelift)
// F30 + SALAPA 522 → xenon-equipped variant
```

The `salapa.enc` database (2.4 MB, encrypted) contains:
- Every BMW type code → model/platform mapping
- Every SALAPA option code → human name + vehicle compatibility
- Production date ranges for each equipment variant

`h0.f(Integer address)` maps an ECU address to a model variant (`y`) containing:
- Which models this ECU appears in
- Which software versions exist
- Which coding parameters are available

---

## Step 8: ECU Compatibility Filtering

For each ECU in the SVT, the app checks compatibility:

```java
// Decompiled from k0.C() — the compatibility flag
public boolean C() {
    return a() == 36 || a() == 107;
    //       ↑         ↑
    //     type=36    type=107
    // These are specific ECU "type codes" that mean
    // "this ECU supports coding via this app"
}
```

The `n0` (ECU model) class has:
- `k: byte` = ECU type/generation flag (0-255)
- `l: String` = ECU display name
- `o: Boolean` = coding supported flag
- `m: r0` = connected coding option descriptors
- `n: o0` = lazy-loaded coding data

**From `n0.k()` — getting the human-readable ECU name:**
```java
public String k() {
    // Look up the display name for this ECU type
    p0 option = p0.e(
        a(),                                    // ECU type byte
        o.I(App.a().c()).intValue()             // App context ID
    );
    return option != null ? option.g() : "";    // g() returns name string
}
```

The `p0` class is the coding option descriptor (from the decrypted database):
```java
class p0 {
    String a;        // Coding key (e.g., "BC_DIGITAL_V")
    byte f6657b;     // Type flag
    ArrayList<Integer> f6658c;  // Valid value IDs
    String f6659d;   // Label string (from .strings file)
    int f6660e;      // Parameter ID
}
```

---

## Step 9: Populate Coding Options

`h0.h(s ecu)` returns the list of coding options for a specific ECU:

```java
// h0.h(s)
public ArrayList<t> h(s ecu) {
    return ecu.c();  // Each ECU 's' holds its own options list
}
```

The `t` class represents one coding option:
```java
class t {
    String f6706f;           // Display name (from .strings)
    ArrayList<v> f6707g;     // Available values
    
    String a() → get name
    ArrayList<v> c() → get values
}
```

Each `v` (value descriptor):
```java
class v {
    Integer f6713f;   // Value ID
    byte f6714g;      // Raw byte representation
    
    Integer c() → get ID
    byte d() → get byte value
}
```

---

## Step 10: Filter by Vehicle Model

BimmerCode filters coding options based on the detected vehicle model.

The `h0` class (adapter session) is populated by selecting the right `q`
objects (vehicle model definitions) that match the detected car:

```java
// h0 constructor
public h0(ArrayList<q> models) {
    this.a = models;  // Only the q objects matching this vehicle
}

// h0.d() — get all ECUs for the matched models
public ArrayList<s> d() {
    ArrayList<s> allEcus = new ArrayList<>();
    for (q model : this.a) {
        allEcus.addAll(model.g());  // ECUs that exist in this model
    }
    Collections.sort(allEcus, ...);
    return allEcus;
}
```

The `q` class represents one vehicle model (e.g., "F30"):
```java
class q {
    // Contains:
    // - Model identifier (e.g., "F30")
    // - Model name (e.g., "3 Series 2011-2019")
    // - List of compatible ECUs and their variants
    // - SALAPA option filters
    
    ArrayList<y> j() → get model variants  // Platform-specific configs
    ArrayList<s> g() → get compatible ECUs  // Sum of all variants' ECUs
}
```

---

## Complete Flow Summary

```
┌──────────────────────────────────────────────────────────────┐
│ CAR SIDE                                                     │
│                                                               │
│ ENET Cable → ZGW                                              │
│   ├─ VIN: WBA3E32050FZ99999                                  │
│   ├─ FA (Vehicle Order): type=3E32, SALAPA={522,6NK,5AC,...}│
│   ├─ SVT (ECU Tree): 0x40=FEM_BODY, 0x56=KOMBI,             │
│   │   0x63=HU_NBT, 0x12=DME, ...                             │
│   └─ CAFD versions per ECU                                    │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│ APP SIDE (BimmerCode)                                         │
│                                                               │
│ 1. Decode VIN → model: F30 (3E32), year: 2015                │
│                                                               │
│ 2. Match FA against salapa.enc (2.4 MB)                      │
│    → Select vehicle model q = "F30_2011_2019"                │
│    → Filter ECUs by SALAPA options                           │
│                                                               │
│ 3. For each ECU in SVT:                                      │
│    ├─ Match ECU variant against ecus.enc (79 KB)             │
│    ├─ Match coding params against <CAFD>.<VERSION>.enc       │
│    ├─ Checks k0.C() for coding compatibility                 │
│    └─ If compatible → add n0 to supported ECUs list          │
│                                                               │
│ 4. For each compatible ECU:                                  │
│    ├─ Load coding options from h0.h(ecu) → ArrayList<t>      │
│    ├─ Look up labels from .strings files                     │
│    │   "BC_DIGITAL_V" → "Digital speed in board computer"    │
│    ├─ Look up value labels                                   │
│    │   "AKTIV" → "Active", "NICHT_AKTIV" → "Not active"     │
│    └─ Display in UI grouped by category                      │
│                                                               │
│ 5. User selects an ECU → sees all compatible coding options  │
│    filtered by:                                               │
│    ✓ Vehicle model (F30, not G20)                            │
│    ✓ ECU presence (FEM_BODY, not BDC_BODY)                   │
│    ✓ ECU software version (C08 vs C09 variant)               │
│    ✓ SALAPA options (has 522 xenon → show xenon options)     │
└──────────────────────────────────────────────────────────────┘
```

---

## What You Need for Your Replacement App

### Data You Already Have (Plaintext)

| Resource | What It Gives You |
|----------|-------------------|
| `en.strings` (1,537 entries) | All coding option labels + descriptions in English |
| `de/fr/ja.strings` | Same labels in 3 more languages |
| `sim-*.json` (9 files) | Sample CAFD hex dumps — shows exact byte layout per ECU |
| `enet-sim.json` | ENET protocol simulation data |
| Phase 5 protocol reference | UDS message formats, ECU addresses, session flow |

### Data You Still Need (Encrypted)

| File | Purpose | How to Get It |
|------|---------|--------------|
| `ecus.enc` (79 KB) | ECU address → name, variant mapping | Decrypt or rebuild |
| `coding-ecu-infos.enc` (18 KB) | Which coding options apply to which ECU | Decrypt or rebuild |
| `salapa.enc` (2.4 MB) | SALAPA codes → model/option descriptions | Decrypt or use FDL database |
| `*.C*.enc` (~400 files) | Per-ECU-variant coding parameter definitions | Decrypt per ECU |
| `k-slim-ncds.enc` | Pre-calculated NCD values | Decrypt |

### Alternative: Build Your Own Database

You don't strictly need to decrypt the `.enc` files. You can build your own
compatibility database from public sources:

1. **VIN decoding**: Use the standard BMW VIN structure (positions 4-7 = model)
2. **Model/platform reference**: Build a lookup table from public BMW model lists
3. **SVT interpretation**: The ZGW already tells you which ECUs are present
4. **CAFD matching**: The SVT already tells you the CAFD IDs and versions
5. **Per-ECU coding**: Read current CAFD from the ECU → present all FDL parameters
   (this is how "Expert Mode" works — it doesn't need a curated database)

### Flow for Your App

```python
# Simplified implementation outline

def on_car_connected():
    # 1. Discover vehicle
    vin = doip_client.request_vehicle_identification()
    
    # 2. Read FA
    fa_xml = uds_read_did(zgw_address, FA_DID)
    model = decode_vin(vin)          # "F30"
    salapa_codes = parse_fa(fa_xml)  # ["522", "6NK", ...]
    
    # 3. Read SVT (ECU tree)
    svt = uds_read_did(zgw_address, SVT_DID)
    ecus_present = parse_svt(svt)
    # [{addr: 0x40, name: "FEM_BODY", cafd: "000024C3", version: "008-005-000"}, ...]
    
    # 4. Filter by vehicle model
    compatible_ecus = []
    for ecu in ecus_present:
        if ecu.addr in CODING_SUPPORTED_ADDRESSES:  # skip airbag, etc.
            compatible_ecus.append(ecu)
    
    # 5. For each compatible ECU, read current coding
    for ecu in compatible_ecus:
        coding_data = uds_read_did(ecu.addr, CODING_DID)
        # Fallback to Expert Mode: show all FDL parameters
        parameters = parse_cafd_parameters(coding_data, ecu.cafd_id)
        display_in_ui(ecu.name, parameters)
    
    # 6. If you have the decrypted database, filter further:
    # parameters = filter_by_model(parameters, model, salapa_codes)
```

---

## Key BimmerCode Classes in the Flow

| Class | Role | Key Methods |
|-------|------|-------------|
| `c.a.b` | MHD adapter connection | Low-level ENET/DoIP communication |
| `a1` | Vehicle interface session | `i()` → ECUs, `g()` → read coding, `A()` → write coding |
| `h0` | Adapter session / vehicle data | `d()` → all ECUs, `h()` → options per ECU, `f()` → model lookup |
| `q` | Vehicle model definition | `j()` → model variants, `g()` → compatible ECUs |
| `y` | Model variant | `d()` → ECUs for this variant |
| `s` | ECU definition | `c()` → coding options, references to `t` objects |
| `t` | Coding option | `a()` → name, `c()` → valid values |
| `v` | Value descriptor | `c()` → ID, `d()` → raw byte value |
| `n0` | ECU model descriptor | `a()` → type byte, `k()` → name, `o()` → session ID |
| `k0` | ECU variant descriptor | `C()` → compatible flag, `D()` → address, `E()` → name |
| `p0` | Named coding option | `g()` → label, `e()` → lookup by type+id |
| `k.a` | Coding data container | `b()` → all items, `g()` → values per parameter |
| `k.j` | Individual coding item | `c()` → ID, `b()` → byte value |
| `k.v` | Coding value | Maps to `v` in options, serialized as Parcelable |

---

## The `.enc` Decryption Path

The encryption key is in `de.appomotive.bimmercode.c.d.b` which contains
`a(byte[])` and `c(String)` methods for hex/byte conversion. The `.enc` file
decryption is a layer above this — likely AES-CTR or AES-CBC with a key
derived from the APK signature or a hardcoded constant.

To extract:
1. Find where `.enc` files are opened (search for `FileReader` on filenames ending in `.enc`)
2. Trace the byte transformation — the decrypt is applied after reading, before parsing
3. Hook with Frida: `FileReader.read()` → capture data → run through decrypt → dump

```javascript
// Frida hook pseudocode
Interceptor.attach(Module.findExportByName(null, "read"), {
    onLeave(retval) {
        // Check if this read is for a .enc file
        // Capture and decrypt
    }
});
```