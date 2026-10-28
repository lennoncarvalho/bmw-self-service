# BimmerCode Coding Database — Extraction Guide

> **2026-10-28 review:** Historical research/design, with unverified or contradicted claims.
> See [document status](README.md) and [protocol corrections](20-protocol-evidence.md).
> Completion labels and code examples below are not validated vehicle contracts.

> **Extracted:** 2026-10-23
> **Database Version:** 24.11.3
> **Scope:** F/G/U/I-series CAFD coding. E-series not supported.
> **Source:** `sources/BimmerCode_v4.25.04-12743.apk`

---

## Quick Start

```bash
# 1. Install apktool
brew install apktool

# 2. Extract the APK
apktool d sources/BimmerCode_v4.25.04-12743.apk -o bimmercode_extracted -f

# 3. Extract the main database
unzip bimmercode_extracted/assets/bimmercode_data.zip -d bimmercode_data/

# 4. Explore
ls bimmercode_data/          # .enc files + .strings + version.json
ls bimmercode_extracted/assets/  # sim-*.json files + enet-sim.json
```

---

## Database Architecture

```
bimmercode_data.zip (64 MB)
├── version.json              # "24.11.3"
│
├── *.strings                 # Human-readable labels (4 languages)
│   ├── en.strings  (109 KB, 1537 entries)
│   ├── de.strings  (117 KB, 1568 entries)
│   ├── fr.strings  (104 KB, 1378 entries)
│   └── ja.strings  (118 KB, 1490 entries)
│
├── ecus.enc       (79 KB)   # [ENCRYPTED] ECU list with addresses
├── coding-ecu-infos.enc (18 KB)  # [ENCRYPTED] Coding-to-ECU mapping
├── swt.enc        (197 KB)  # [ENCRYPTED] Software Token / parameter mapping
├── salapa.enc     (2.4 MB)  # [ENCRYPTED] SALAPA option codes
│
├── 000024C3.enc   (160 B)   # CAFD index for ECU family 0x000024C3
├── 000024C3-008-005-000.enc  # [ENCRYPTED] Coding defs for variant 008-005-000
├── 000024C3-008-007-002.enc
├── ...
├── 00002660.enc   (816 B)   # CAFD index for ECU family 0x00002660
├── 00002660-005-007-006.enc
├── ...
│
├── ACSM.enc / ACSM.C08.enc  # [ENCRYPTED] Airbag module coding defs
├── CIC.enc / CIC.C08.enc    # [ENCRYPTED] CIC headunit coding defs
├── FRM3_E7X.enc / FRM3_E7X.C31.enc  # [ENCRYPTED] FRM3 module coding defs
├── KOMB56.enc / KOMB56.C05.enc  # [ENCRYPTED] Instrument cluster coding defs
├── KOMBI_PL2.enc / KOMBI_PL2.C05.enc
├── ...
└── (~400+ .enc files total, ~25 ECU families)

External to ZIP (in assets/):
├── sim.json         (126 KB)  # Main simulation CAFD data (plaintext hex)
├── sim-g20.json     (120 KB)  # G20 3-series simulation data
├── sim-g01.json     (100 KB)  # G01 X3 simulation data
├── sim-g81.json     (62 KB)   # G81 M3 Touring simulation data
├── sim-f15.json     (35 KB)   # F15 X5 simulation data
├── sim-fsc.json     (40 KB)   # F-series combi simulation
├── sim-e87.json     (24 KB)   # E87 1-series simulation data
├── sim-i3.json      (19 KB)   # I01 i3 simulation data
├── sim-r56.json     (12 KB)   # R56 MINI simulation data
├── enet-sim.json    (110 KB)  # ENET protocol simulation data
├── sim-enet.json    (133 KB)  # ENET response simulation
├── app.gz → k-slim.json (1.2 MB) # Compressed CAFD catalog
├── E60.enc, E70.enc, E89.enc, R56.enc  # [ENCRYPTED] Model-specific data
├── ecus.enc, k-slim-ncds.enc, salapa.enc, swt.enc
```

---

## What's Available (Plaintext)

### 1. Translation Strings (`en.strings`)

1537 human-readable labels and descriptions for every coding option:

```
Format: "CODING_KEY" = "Human-readable label";
        "CODING_KEY_DESCRIPTION" = "Full description of what this does.";

Examples:
"BC_DIGITAL_V" = "Digital speed in board computer";
"BC_DIGITAL_V_DESCRIPTION" = "Enable/disable the display of the digital speed...";

"VIDEO_WHILE_DRIVING" = "Video in motion";
"VIDEO_WHILE_DRIVING_DESCRIPTION" = "Activate video in motion. Use a backup...";

"ASD_ACTIVE" = "Active Sound Design deactivation";
"LEGAL_DISCLAIMER" = "Warning at start-up";
"STARTUP_EMBLEM" = "Start animation";
"STARTUP_EMBLEM_M" = "M variant 1";
"COMFORT_OPENING_CLOSING" = "Comfort opening/closing";
"KOMFORTSCHLIESSUNG_FB" = "Comfort closing with key fob";
"ANGEL_EYES_BRIGHTNESS" = "Angel eyes brightness";
"DAYTIME_RUNNING_LIGHTS" = "Daytime running lights";
"TCM_MSA_DEFAULT_OFF" = "Auto Start/Stop default off";
"TCM_MSA_MEMORY" = "Auto Start/Stop memory";
"FOLD_MIRRORS" = "Fold mirrors with comfort closing";
"HUD_ENTERTAINMENT_ENABLE" = "HUD entertainment list";
"EMERGENCY_STOP_SIGNAL" = "Emergency stop signal";
```

**286 unique coding categories** spanning:
- Lighting (DRL, angel eyes, welcome lights, cornering lights, ambient)
- Comfort (mirrors, windows, seats, climate)
- iDrive/Infotainment (startup emblem, ringtone, disclaimer, video)
- Safety (emergency brake signal, PDC, blind spot)
- Instrument Cluster (digital speed, M Performance logo, sport displays)
- Body (folding mirrors, tailgate, convertible top)

### 2. Simulation CAFD Data (`sim-*.json`)

Raw ECU coding data in hex format, used for the app's demo/simulation mode:

```json
{
  "{40}0322F101": "640F1108462F1010101\n640F121000E1409068B\n...",
  "{01}03223056": "601F1104B6230564208\n601F12100189020FFFF\n...",
  "{56}03223013": "656F110876230130000\n656F1210020759B4D57\n...",
  "{63}0322300E": "663F1106762300E89AA\n663F121AA02A0AA8308\n..."
}
```

Key format: `{ECU_LOGICAL_ADDRESS}CAFD_ID` → hex-encoded CAFD data
- `{40}` = FEM_BODY / BDC_BODY
- `{01}` = Unknown ECU
- `{56}` = KOMBI (instrument cluster)
- `{63}` = Headunit (CIC/NBT/MGU)
- `{60}` = Unknown
- `{06}` = Unknown
- `{10}` = ZGW
- `{3F}` = Unknown
- `{67}` = Unknown

### 3. ENET Simulation (`enet-sim.json`, `sim-enet.json`)

Protocol-level simulation data — the raw byte responses the app expects from
each ECU during coding operations. These define the UDS message exchange
patterns for reading and writing coding data.

### 4. App Catalog (`app.gz` → `k-slim.json`)

A compressed JSON catalog (1.2 MB decompressed) mapping coding option keys
to their CAFD parameter positions. This is the bridge between the string
labels and the raw hex data.

---

## What's Encrypted (`.enc` files)

All `.enc` files use a **proprietary encryption scheme**. The files have:
- No recognizable headers (not gzip, not zip, not protobuf)
- High entropy (random byte distribution)
- Consistent file size patterns suggesting structured data inside

The encryption key is embedded in the obfuscated DEX code. From the
decompiled `i0` class and related code, the decryption likely happens in
the `de.appomotive.bimmercode.c.d` package (classes `a` and `b`), which
contain hex/byte conversion utilities also used for backup files.

### What's Inside the Encrypted Files

| File | Size | Contents |
|------|------|----------|
| `ecus.enc` | 79 KB | List of all supported ECUs with addresses, variants, names |
| `coding-ecu-infos.enc` | 18 KB | Mapping: which coding options apply to which ECU |
| `swt.enc` | 197 KB | Software Token — parameter indices, bit positions, masks |
| `salapa.enc` | 2.4 MB | SALAPA option code database (all BMW factory option codes) |
| `*.C*.enc` (per-ECU) | 1-500 KB | Per-ECU-variant coding parameter definitions |
| `*.enc` (per-ECU root) | 160 B-5 KB | ECU family index/metadata |

### `.enc` File Naming Convention

**CAFD-based names:**
```
000024C3-008-005-000.enc
│        │   │   │
│        │   │   └─ Revision/patch
│        │   └─ Minor version
│        └─ Major version
└─ CAFD ID (hex)
```

**ECU-based names:**
```
FRM3_E7X.C31.enc
│        │
│        └─ Software version (C31)
└─ ECU family + platform variant
```

Each `.enc` file defines the coding parameters for ONE specific ECU software
version. This is why there are ~400 files — each ECU has multiple software
versions, and each version may have slightly different parameter layouts.

---

## How to Use This Database for a Replacement App

### Step 1: Translation Layer (available now)

The `.strings` files give you all human-readable labels. Map `CODING_KEY`
to your UI:

```javascript
// en.strings is an Apple .strings format file
const translations = parseStringsFile("en.strings");
// { "BC_DIGITAL_V": "Digital speed in board computer", ... }
```

### Step 2: Find the Encryption Key

The `.enc` files need to be decrypted to access the parameter-to-byte
mapping. The key is in the obfuscated DEX code. Two approaches:

**A. Static analysis — trace the decrypt call:**
- The classes `de.appomotive.bimmercode.c.d.a` and `c.d.b` contain
  hex/byte conversion utilities
- Search for references to `.enc` file loading in the decompiled code
- The decryption likely uses AES with a key derived from the app signature
  or a hardcoded constant

**B. Runtime extraction — hook the decryption:**
- Run BimmerCode on a rooted Android device or emulator
- Use Frida to hook the file read/decrypt methods
- Dump the decrypted data to files

```javascript
// Frida hook pseudocode
Java.perform(() => {
    const FileReader = Java.use("java.io.FileReader");
    // Hook file opens for .enc files
    // Dump decrypted bytes after the decrypt transformation
});
```

### Step 3: With Decrypted Data

Once decrypted, each `.enc` file reveals:
- Parameter name (maps to `CODING_KEY` in `.strings`)
- Parameter position (byte offset in the CAFD data)
- Parameter size (bit length or byte count)
- Valid values (byte representations and their labels)
- Conditions (which vehicle models/options this parameter applies to)

Combined with the simulation data (`sim-*.json`), you can build the complete:
1. **Read flow**: Parse raw CAFD hex → extract parameter values → label them
2. **Write flow**: User changes label → lookup byte representation → modify CAFD → write to ECU

### Step 4: Fallback — Use Simulation Data

Even without decrypting `.enc` files, the `sim-*.json` files and
`enet-sim.json` give you:
- Exact byte patterns for each ECU's CAFD
- Which bytes change between coding options (by comparing sim files)
- The UDS message exchange patterns for reading/writing

### Database Statistics

| Component | Count |
|-----------|-------|
| String entries (en) | 1,537 |
| Unique coding categories | ~286 |
| ECU families | ~25 |
| Per-ECU variant files | ~400 |
| Simulation models | 9 (g20, g01, g81, f15, fsc, e87, i3, r56, enet) |
| Languages | 4 (en, de, fr, ja) |
| Database version | 24.11.3 |

### Encryption Key Search Paths

From the decompiled APK, key candidates:
1. `de.appomotive.bimmercode.c.d` — hex/byte utilities, likely includes decrypt
2. `de.appomotive.bimmercode.models.i0` — file reading, calls `c.d.b.c()` for hex decode
3. The MHD adapter library (native `.so`) — may include the decrypt routine
4. A hardcoded key in `de.appomotive.bimmercode.c.d.a` or similar

The `c.d.b.a(byte[])` and `c.d.b.c(String)` methods convert between byte
arrays and hex strings for backup files. The encryption/decryption for
`.enc` files is a separate layer on top of this.