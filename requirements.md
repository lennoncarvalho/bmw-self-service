# BMW ENET Reverse Engineering — Session Requirements (Complete)

> All phases completed. Results in `docs/01` through `docs/18`.
> The replacement app is built and functional.

Prompt/plan for an unattended REA session to document how the BMW apps communicate
with the car over an ENET (Ethernet-to-OBD2) cable.

---

## Goal

Reverse engineer two Android applications and one Windows application that
communicate with BMW cars over an ENET cable, and document the communication
protocol, command structures, and model-specific databases so we can build our
own replacement app with both customization and diagnostics features.

## Targets in `sources/`

| File | Type | Purpose |
|---|---|---|
| `sources/BimmerCode_v4.25.04-12743.apk` (73 MB) | Android APK | BMW coding/customization. Two modes: a curated database of tested coding presets per model, and an advanced/expert mode that reads ECU coding data directly (like BMW E-Sys) |
| `sources/BimmerLink_v2.36.1.apk` (48 MB) | Android APK | BMW diagnostics & sensor reading (live values, DTCs, battery, exhaust) |
| `sources/SHM/SHM.exe` (3.5 MB) | PE32 GUI x86 | Service History Manager — writes service entries to BMW iDrive/CBS |
| `sources/SHM/history.2026.09.24.bmwsh` (360 bytes) | Proprietary binary | The app's local service-history database |
| `sources/SHM/shm_help.pdf` | Documentation | Vendor help file for SHM; mine it for UI/field semantics before decompiling |

### How SHM.exe works

User enters service data in the GUI → app saves it to the `.bmwsh` file → user
clicks **"Write to car"** → app reads the `.bmwsh` file → converts entries into a
semicolon-delimited argument string → sends via EDIABAS/Tool32 over the ENET cable
to the car's headunit.

### Observed `.bmwsh` facts (starting points, not conclusions)

- 360 bytes, repeating record structure
- ASCII strings: `Lennon` (dealer), `G655` (dealer/vehicle code), `25332`, `49124`,
  `39611` (mileage / VIN fragments)
- Year-like little-endian uint16 values spanning 2019–2026
- Date bytes consistent with the filename (`18 09 07 ea` ≈ 24 Sept 2026)
- Service-code-like small integers matching the known BMW codes (1, 2, 3, 4, 6, 8,
  10, 11, 12, 22, 26)

---

## Phase 1: Research the domain (web search)

Research the BMW ENET communication landscape before touching the binaries:

- BMW DoIP (Diagnostics over IP) — port, handshake, vehicle announcement
- UDS services: SessionControl (0x10), ReadByIdentifier (0x22),
  WriteByIdentifier (0x2E), RoutineControl (0x31), TesterPresent (0x3E),
  ReadDataByLocalIdentifier (0x21), ReadDTCInformation (0x19),
  InputOutputControlByIdentifier (0x2F)
- BMW FA (Vehicle Order) and FDL coding data structure
- CBS (Condition Based Service) — service entry structure
- BMW ECU naming: ZGW, FEM_BODY, BDC_BODY, DME/DDE, EGS, KOMBI, HU_NBT/HU_ENTRY, etc.
- How BimmerCode's expert mode mirrors E-Sys
- **Key reference:** <https://www.bimmerguide.de/service-historie-eintrag-mit-tool32/>
  — documents the exact Tool32 job `STEUERN_SERVICEHISTORY_ADD`, the
  semicolon-delimited argument format, the complete service code table, headunit
  PRG files (`CIC.PRG`, `NBT.PRG`, `NBTEVO.PRG`, `HU_MGU.PRG`), and return values
  per headunit. This is the protocol SHM.exe implements.

Save to `docs/01-bmw-protocol-research.md`.

---

## Phase 2: Reverse engineer BimmerCode APK (coding/customization)

Use REA's Android/JADX tools (no `open_binary` needed).

**2a — Inventory:** `inspect_android_package` on
`sources/BimmerCode_v4.25.04-12743.apk`. Note package name, class count,
permissions, manifest services.

**2b — Communication code:** Search classes for: `enet`, `connection`, `socket`,
`ethernet`, `doip`, `uds`, `diagnostic`, `ecu`, `coding`, `vin`, `gateway`, `zgw`,
`vehicle`, `communication`, `transport`, `can`, `send`, `command`, `request`,
`response`, `message`, `packet`, `frame`.

**2c — Curated coding database:** Search classes for: `database`, `preset`,
`catalog`, `library`, `repository`, `cheat`, `code`, `coding`, `cafd`, `fdl`,
`parameter`, `option`, `feature`, `model`, `series`, `exx`, `fxx`, `gxx`. Also
inspect `res/raw/` and `assets/` for embedded JSON, XML, CSV, SQLite, or protobuf.

**2d — Expert/advanced ECU coding mode (E-Sys-like):** Search classes for:
`expert`, `advanced`, `manual`, `raw`, `esys`, `ncd`, `cafd`, `fdl`, `werte`,
`function`, `address`, `byte`, `hex`, `read`, `write`, `backup`, `restore`,
`flash`, `svt`, `tal`.

**2e — Deep-dive:** For promising classes: `inspect_android_class` →
`inspect_android_method` → `trace_android_references`.

Save to `docs/02-bimmercode-analysis.md`.

---

## Phase 3: Reverse engineer BimmerLink APK (diagnostics & sensors)

Same JADX approach on `sources/BimmerLink_v2.36.1.apk`.

**3a — Inventory:** `inspect_android_package`. Compare permissions and structure
to BimmerCode.

**3b — Sensor reading:** Search for: `sensor`, `read`, `live`, `value`, `measure`,
`monitor`, `gauge`, `temperature`, `pressure`, `rpm`, `speed`, `battery`,
`voltage`, `dtc`, `fault`, `error`, `0x19`, `clear`, `exhaust`, `emission`,
`lambda`, `dpf`, `particulate`, `oil`, `coolant`, `boost`, `torque`.

**3c — DTC handling:** Search for: `dtc`, `trouble`, `fault`, `error`, `freeze`,
`frame`, `description`, `translation`, `mil`, `check`, `engine`, `warning`.

**3d — Deep-dive:** `inspect_android_class` → `inspect_android_method` → trace
sensor data request flow. Find the list of supported sensor PIDs/data identifiers.

Save to `docs/03-bimmerlink-analysis.md`.

---

## Phase 4: Reverse engineer SHM.exe + .bmwsh (service history writer)

Use REA's native analysis with Ghidra. Start with `open_binary` on
`sources/SHM/SHM.exe` with `provider: "ghidra"`. The binary is **PE32 GUI, Intel
80386 (32-bit x86)** — Ghidra imports it as x86 32-bit.

**Background from research:** The BimmerGuide article documents the protocol
SHM.exe implements:

- Job: `STEUERN_SERVICEHISTORY_ADD`
- Argument format:
  `Day;Month;Year;CorrectionCounter;Km;DealerFlag;DealerID;Status;Count;`
  followed by per-item `Code;ItemStatus;RemainingDist;RemainingTime;`
- Headunit PRG files: `CIC.PRG`, `NBT.PRG`, `NBTEVO.PRG`, `HU_MGU.PRG`
- Erase jobs: `STEUERN_SERVICEHISTORY_ERASE` / `STEUERN_SERVICEHISTORY_DEL`
- Complete service code table in the article (oil=1, brake pads front=2, brake
  fluid=3, microfilter=4, etc.)
- Return values: CIC uses offset values (success=0x01), others use 0x00

**4a — Analyze the `.bmwsh` file first:** This is the internal data model.
Reverse engineer its binary structure:

- It is a proprietary format with repeating records, each containing a date, a
  dealer name, a dealer code, VIN/mileage identifiers, and service item entries
- Years 2019–2026 appear as little-endian uint16
- ASCII strings: `Lennon` (dealer), `G655` (code), `25332`/`49124`/`39611`
  (mileage/VIN)
- Understanding this format reveals exactly what data the EXE sends to the car
- Look for date fields (day, month, year as uint16 LE), null-terminated name
  strings, uint32 mileage values, and service code identifiers

**4b — Inventory the EXE:** `list_procedures` and `list_strings`. The string table
is the fastest path to protocol clues.

**4c — Find service history logic using these exact search terms:**

- Strings: `STEUERN_SERVICEHISTORY_ADD`, `STEUERN_SERVICEHISTORY_ERASE`,
  `STEUERN_SERVICEHISTORY_DEL`, `CIC.PRG`, `NBT.PRG`, `NBTEVO.PRG`, `HU_MGU.PRG`,
  `EDIABAS`, `Tool32`, `STAT_SH_ADD_WERT`, `JOB_STATUS`, `OKAY`
- The file extension `.bmwsh` as a string — find where the EXE opens/reads/writes it
- Direct semicolon usage: string concatenation with `;` delimiters (argument builder)
- Service codes from the article: 1, 2, 3, 4, 5, 6, 7, 10, 11, 12, 32, 33, 35, 49, 50
- General: `service`, `history`, `cbs`, `oil`, `brake`, `inspection`, `microfilter`,
  `spark`, `vehicle`, `check`, `reset`, `write`, `routine`, `entry`, `record`,
  `mileage`, `kilometer`, `date`, `dealer`, `bmwsh`

**4d — Communication code:** Search for: `connect`, `send`, `recv`, `socket`,
`doip`, `uds`, `0x31`, `0x2E`, `0x22`, `ediabas`, `api`, `transport`, `zgw`,
`gateway`, `diagnostic`, `vin`. Search strings for IP addresses, port 6801, `13400`.

**4e — Find the conversion function:** The critical piece is the function that
reads a `.bmwsh` record and converts it to the semicolon-delimited Tool32 argument.
Look for:

- Functions that open/read `.bmwsh` files
- Functions that build strings with `;` separators and format specifiers
  (`sprintf`, `wsprintf`, string concatenation with integers)
- Functions that call the EDIABAS API or send over the network

**4f — Deep-dive:** For each promising function: `analyze_function` → pseudocode,
assembly, callees, callers, referenced strings. Trace: `.bmwsh` file read → data
structure → argument string assembly → send to car → response parsing.

**4g — Headunit-specific logic:** Look for conditionals on headunit type
(CIC/NBT/NBT EVO/MGU) that change PRG file selection or return-value checking.

Save to `docs/04-service-writer-analysis.md`.

---

## Phase 5: Synthesize everything

Combine all findings into `docs/05-protocol-reference.md`:

1. **Connection setup:** ENET → DoIP handshake → gateway routing → VIN announcement
2. **Diagnostic session:** Session type for coding vs diagnostics vs service writing
3. **Vehicle identification:** Reading VIN, FA (vehicle order), SVT (ECU tree)
4. **Curated coding flow:** Preset database format + read/write message exchange
5. **Expert coding flow:** Raw ECU read → user edit → write (E-Sys path)
6. **Sensor reading flow:** How BimmerLink requests/receives live data
7. **DTC flow:** Reading and clearing diagnostic trouble codes
8. **Service history flow:** Complete flow — `.bmwsh` binary format → internal data
   model → argument string construction → Tool32 job execution → response checking
   per headunit
9. **Service code reference table:** All maintenance codes found
10. **Model/ECU database:** BMW models, ECU addresses, coding parameters
11. **Message reference:** Byte-level format for each message type identified

---

## Rules for this session

- Start with internet research (Phase 1) — knowing what to look for makes
  decompilation vastly more productive
- APKs → JADX tools via REA MCP only; EXE → Ghidra via REA MCP only
- Paste decompiled code excerpts into docs with source attribution (class/method,
  address) and the note that it is derived, not original source
- If you find encrypted/encoded data, document it as `TODO: encrypted data at ...`
- Write documentation incrementally, one file per phase
- Do not write to `sources/`
- If REA times out on a broad operation, retry with explicit narrowing (specific
  class name or function address)
