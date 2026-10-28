# Gap Analysis: What We Have vs. What We Need

> **2026-10-28 review:** Historical research/design, with unverified or contradicted claims.
> See [document status](README.md) and [protocol corrections](20-protocol-evidence.md).
> Completion labels and code examples below are not validated vehicle contracts.

> **Date:** 2026-10-23
> **Target:** Replacement BMW ENET app with 4 modules

---

## Module 1: Service History

| Component | Status | Detail |
|-----------|--------|--------|
| Argument format | ✅ Complete | `Day;Month;Year;CorrCnt;Km;Flag;Dealer;Status;Count;Code;Status;Dist;Time;` |
| Service code table | ✅ Complete | 41 codes with hex/decimal/names |
| Return values per headunit | ✅ Complete | CIC=0x01, NBT/MGU=0x00 with error codes |
| Headunit detection | ✅ Complete | Read SVT from ZGW, locate headunit at 0x63 |
| .bmwsh binary format | ✅ Complete | Full format reverse-engineered |
| Connection flow | ✅ Complete | ENET → DoIP/HSFZ → TCP connect |
| **Actual UDS wire format** | ⚠️ Gap | The exact UDS message to invoke `STEUERN_SERVICEHISTORY_ADD` is unknown |

### The Gap

BimmerGuide documents the Tool32/EDIABAS workflow, not the raw UDS. SHM.exe
uses IP*Works! TCP sockets, not EDIABAS, but its binary analysis in Ghidra
didn't reveal the exact message framing.

**Three approaches to close this gap:**

1. **Packet capture** (fastest): Run SHM.exe against a car with Wireshark,
   capture the TCP stream, extract the UDS RoutineControl message.

2. **PRG file analysis** (medium): The BMW PRG files (`CIC.PRG`, `NBT.PRG`,
   etc.) contain the job definition including the RoutineIdentifier. Parse
   a PRG file with `ediabaslib` or `BimmerDaten` to find the RID.

3. **UDS RoutineControl reverse** (educated guess): The service history
   write is almost certainly `UDS 0x31 (RoutineControl)` with a
   headunit-specific RID. The argument string becomes the routine's
   parameter bytes, sent as ASCII.

**Estimated effort to close:** 1-2 days with packet capture; 1 day with PRG analysis.

---

## Module 2: Diagnostics

| Component | Status | Detail |
|-----------|--------|--------|
| DTC reading protocol | ✅ Complete | UDS 0x19 with sub-functions 0x01/0x02/0x04/0x06 |
| DTC clearing protocol | ✅ Complete | UDS 0x14 with group masks |
| MIL status | ✅ Complete | Via UDS 0x19 or OBD-II Mode 01 PID 01 |
| Freeze frame reading | ✅ Complete | UDS 0x19 sub-function 0x04 |
| DTC status mask bits | ✅ Complete | All 8 bits documented |
| ECU addressing | ✅ Complete | Diagnostic addresses documented |
| **DTC description database** | ⚠️ Partial | Standard OBD-II P0xxx-P3xxx codes have public databases. BMW proprietary hex codes (e.g., "2A6C") need a BMW-specific database |

### The Gap

BimmerLink has a DTC description database (deserialized via
`BMWErrorLocationTextDeserializer`, Gson-based). We haven't extracted
BimmerLink's assets yet but can.

**Two approaches:**

1. **Extract from BimmerLink** (1 hour): Run `apktool` on BimmerLink,
   find the DTC JSON database in its assets.

2. **Public databases**: Standard OBD-II DTCs are well-documented. BMW
   proprietary DTCs can be built up from community sources (ISTA/D Rheingold
   data, BimmerScene forums).

**Estimated effort to close:** 1 hour to extract, ~1 day to build complete.

---

## Module 3: Easy Coding

| Component | Status | Detail |
|-----------|--------|--------|
| CAFD parameter database | ✅ Complete | ~350 CAFD variant files decrypted, 1,592+ params per ECU |
| Translation strings | ✅ Complete | 1,537 labels in 4 languages (en/de/fr/ja) |
| Vehicle ID flow | ✅ Complete | VIN → model → ECUs → filtered coding options |
| ECU compatibility mapping | ✅ Complete | ecus.enc (700+ entries), coding-ecu-infos.enc |
| SALAPA database | ✅ Complete | 5,640 option codes in 9 languages (decrypted) |
| Per-variant values | ✅ Complete | F020/F030/F010/F045/F015 per platform |
| Byte positions & bit masks | ✅ Complete | Every parameter has `storageInfo` with start/end/mask |
| Connection & UDS protocols | ✅ Complete | DoIP + HSFZ + UDS 0x22/0x2E documented |
| **Coding key → translation mapping** | ⚠️ Gap | CAFD uses names like "LWR_ENABLE" but .strings uses "BC_DIGITAL_V" |
| **SecurityAccess seed/key** | ⚠️ Gap | Some ECUs require level 1/3/5 authentication for coding |

### The Gaps

**1. Parameter name → translation key mapping**

The CAFD JSON has parameter names like:
```json
{"name": "LWR_ENABLE", "storageInfo": {"start": "0", "end": "0", "mask": "0b00000001"}}
```

The `.strings` file has labels like:
```
"ANGEL_EYES_BRIGHTNESS" = "Angel eyes brightness";
```

We need the mapping between them. This is likely in:
- The `swt.enc` file (decrypted, 202KB — we should examine it more carefully)
- The per-ECU `.enc` root index files (already decrypted)
- Or it may be embedded in the CAFD JSON's `params[].paramName` fields combined with the ECU group name

**2. SecurityAccess algorithm**

ECUs like DME/DDE, EGS, and some newer body modules require a seed/key
exchange before allowing coding writes. The algorithm is platform-specific
and stored in the MHD adapter's native library (`.so` file).

**Solutions:**
- For most body ECUs (FEM_BODY, REM, KOMBI, headunit): SecurityAccess is
  often NOT required for coding (BimmerCode works without it)
- For engine/transmission: The seed/key algorithm is needed
- Community algorithms exist for common BMW ECUs (MSD80, MSV80, etc.)
- MHD adapter may handle this transparently — if we use MHD as our transport

**Estimated effort:** Parameter mapping: 1-2 days. SecurityAccess: varies;
use MHD adapter to skip this, or implement known algorithms.

---

## Module 4: Advanced Coding

| Component | Status | Detail |
|-----------|--------|--------|
| SVT reading protocol | ✅ Complete | UDS 0x22 from ZGW, returns ECU tree |
| FDL parameter definitions | ✅ Complete | Full byte-level definitions for 350+ ECU variants |
| CAFD reading | ✅ Complete | UDS 0x22 with ECU-specific DID |
| CAFD writing | ✅ Complete | UDS 0x2E with parameter DIDs |
| Backup/restore flow | ✅ Complete | Hex file format documented |
| Expert mode flow | ✅ Complete | Read → parse → edit → diff → write |
| **HSFZ protocol framing** | ⚠️ Gap | F-series uses BMW-proprietary HSFZ on TCP 6801 |
| **SecurityAccess for write** | ⚠️ Gap | Same as Easy Coding |
| **Exact CAFD DID per ECU** | ⚠️ Partial | Known concept, exact DID varies |

### The Gaps

**1. HSFZ protocol framing**

F-series cars (2011-2019) use BMW's proprietary HSFZ protocol over TCP 6801.
G-series cars use standard DoIP over TCP 13400. The `rawenet` project on
GitHub has reverse-engineered HSFZ, but we'd need to implement it.

**2. CAFD DIDs**

The CAFD read/write DIDs are ECU-specific. BimmerCode's MHD adapter handles
this internally. For a from-scratch implementation, we need to:
- Either use the MHD adapter as a library
- Or reverse-engineer the CAFD DIDs from the MHD adapter's behavior

**Estimated effort:** HSFZ: 3-5 days (or use existing open-source implementation).
CAFD DIDs: use MHD adapter or extract from its protocol.

---

## Cross-Cutting Gaps

| Gap | Impact | Modules Affected |
|-----|--------|-----------------|
| HSFZ framing (TCP 6801) | Blocks F-series connection | All 4 |
| Parameter→translation mapping | No human-readable labels | Easy Coding |
| Service history wire format | Can't write to car yet | Service History |
| DTC description DB | No error descriptions | Diagnostics |
| SecurityAccess algorithm | Can't code protected ECUs | Easy + Advanced Coding |

---

## Recommended Build Order

### Phase A: Foundation (Week 1-2)
1. **DoIP connection** (G-series first — standard protocol, well-documented)
2. **VIN reading + SVT parsing** (works on both F and G series)
3. **Vehicle model detection** (VIN decoding + ECU tree)

### Phase B: Diagnostics (Week 2-3)
1. **DTC reading** — works immediately with standard UDS
2. **DTC clearing** — standard UDS
3. **MIL status** — standard OBD-II
4. **DTC descriptions** — extract from BimmerLink or use public DB

### Phase C: Easy Coding (Week 3-4)
1. **CAFD reading** via UDS 0x22
2. **Parameter parsing** using decrypted CAFD JSON
3. **Translation mapping** — build the bridge between CAFD names and .strings
4. **Writing** via UDS 0x2E (for non-protected ECUs first)

### Phase D: Service History (Week 4-5)
1. **Packet capture SHM.exe** to get the wire format
2. **Implement the RoutineControl call**

### Phase E: Advanced Coding (Week 5-6)
1. **SVT tree display** with full ECU listing
2. **Expert mode FDL editor**
3. **SecurityAccess** for protected ECUs

### Phase F: F-series Support (Week 6-7)
1. **HSFZ protocol implementation** (or use open-source library)

---

## Quick Wins — What Works TODAY

With zero additional reverse engineering, you can build:

```
✅ G-series connection (DoIP, TCP 13400)
✅ VIN reading
✅ SVT/ECU tree reading
✅ DTC reading + clearing + MIL status
✅ CAFD reading + parameter display (raw names from CAFD JSON)
✅ Advanced coding (Expert Mode) — read all FDL params, show raw values
✅ SALAPA decoding — 5,640 BMW option codes in 9 languages
✅ Service history READING (read from headunit via UDS 0x22)
```

## What Needs 1-2 Days Each

```
⚠️ F-series connection (HSFZ protocol)
⚠️ Service history WRITING (capture wire format from SHM.exe)
⚠️ DTC descriptions (extract from BimmerLink assets)
⚠️ Coding label mapping (CAFD names → .strings keys — probably in swt.enc structure)
⚠️ SecurityAccess (if needed — many ECUs don't require it for basic coding)
```