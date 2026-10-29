# UI/UX Specification

Current Task B behavior (2026-10-29): [spec 26](26-feature-readiness-spec.md)
and D-21–D-49 in [doc 21](21-product-decisions.md) supersede conflicting older
examples below. No write Cancel; disruptive controls/normal quit blocked during
writes. Completion is operation/cycle-aware, not universally immediate readback.
History add may preserve/rewrite the complete list; reject future/same-day new
entries; use entered mileage without reading current odometer. Mac Python-source
functionality is the milestone; packages/signing are deferred. Protocol examples
remain unverified unless linked to retained source evidence.


> **2026-10-28 review:** Historical research/design, with unverified or contradicted claims.
> See [document status](README.md) and [protocol corrections](20-protocol-evidence.md).
> Completion labels and code examples below are not validated vehicle contracts.
> Wireframes are proposals; [owner decisions](21-product-decisions.md) govern write/backup/readback behavior.

> **Current release profile:** [spec 26](26-feature-readiness-spec.md) overrides
> older controls/scope below: faults from all ECUs, one Clear All button with
> partial outcomes, history read/add with exact duplicate blocking, and every
> applicable easy preset. Per-code/per-ECU clear controls, history editing and
> advanced coding are not first-release requirements. Use [spec 25](25-library-migration-spec.md)
> for protocol ownership and [doc 27](27-rea-source-guide.md) for source answers.

> **App:** BMW Diagnostic Tool  
> **Theme:** Dark, modern, mobile-friendly  
> **Date:** 2026-10-25  

---

## Global behavior

### Connection and capability availability (owner-confirmed, 2026-10-28)

When VIN and diagnostic communication are verified, optional mileage, battery,
FA or ECU read failures keep the connection active. Mark unavailable fields and
incomplete scan coverage explicitly. Enable only operations whose prerequisites
and protocol support are established; do not show guessed or stale data as current.

Identified but unverified ECU/software variants can use supported reads while
unverified writes remain disabled with a reason. Keep the mandatory series picker
only if review establishes that it simplifies connection behavior and initial
loading for all pages. Selection is a hint, not proof of transport compatibility.
See decisions D-12 through D-14 in [the register](21-product-decisions.md).

### Theme

- Dark background throughout (`#1a1a2e` or Qt dark palette)
- BMW M colors for accents: light blue (`#1C69D4`), dark blue (`#0653B6`), red (`#E30B1F`)
- Rounded corners on cards/buttons (8px radius)
- System font stack: SF Pro (macOS), Segoe UI (Windows)
- All text high-contrast against dark backgrounds

### Loading & async

Every operation that talks to the car shows a **centered spinner** with a
status label. While loading:

- Navigation buttons are disabled (prevent double-clicks)
- A cancel/timeout button appears after 10 seconds
- After 30 seconds of no response: "The car is not responding. Check ignition
  and ENET cable connection. [Retry] [Cancel]"

No operation blocks the UI thread — all car I/O runs on background threads
via `CarWorker(QThread)` subclasses and signals.

### Mobile-friendly layout

The app uses a **bottom navigation bar** with 4 tabs. On desktop, it also
appears as a bottom bar (not a sidebar) so the layout is consistent across
screen sizes. On narrow windows (< 600px), content margins shrink and cards
stack vertically.

---

## Screen 1: Welcome / Connect

```
┌──────────────────────────────────────────┐
│                                          │
│              [BMW Hero Logo]             │
│           (large, centered, ~200px)       │
│                                          │
│        ┌─────────────────────────┐        │
│        │  Connect to your BMW    │        │
│        └─────────────────────────┘        │
│          (prominent blue button)          │
│                                          │
│  To ensure a stable connection:          │
│  • Press the Start/Stop button once      │
│    (without pressing the brake) to enter  │
│    ignition/diagnostic mode              │
│  • For vehicles with Comfort Access:     │
│    press Start/Stop 3 times quickly      │
│  • Fasten the driver's seatbelt to       │
│    prevent auto-shutoff after ~15 min    │
│  • Turn off lights, A/C, and radio to    │
│    reduce battery drain                  │
│  • Connect the ENET cable BEFORE         │
│    turning on ignition                   │
│                                          │
│  [Bottom nav: grayed-out tabs]           │
│  🏠  Diagnostics  🛠️ Coding  📋 History │
└──────────────────────────────────────────┘
```

### Connection flow

1. User clicks "Connect to your BMW"
2. Spinner: "Detecting ENET interface..."
3. Interface found → "Searching for vehicle..."
4. UDP broadcast discovery
5. If ZGW found → "Connected to BMW [Series] [Model]"
6. If not found → offer DHCP server fallback (see docs/15)
7. Top bar populates with VIN, model, production date, I-level
8. Bottom nav activates (tabs become clickable)

---

## Screen 2: Top bar (persistent, after connection)

```
┌──────────────────────────────────────────┐
│ 🟢 Connected  │  F48 X1 xDrive25i  │  ⚙️  │
│               │  VIN: WBA...12345   │      │
└──────────────────────────────────────────┘
```

- Green dot = connected, Yellow dot = busy, Red dot = disconnected
- VIN and model pulled from vehicle identification (UDS 0x22 F190)
- ⚙️ gear icon opens menu:
  - **Backups** → manage/rollback coding backups
  - **About** → version, licenses, credits
  - **Disconnect** → close TCP session, return to welcome screen
  - **Exit** → disconnect + close app

---

## Screen 3: Bottom navigation (persistent, after connection)

```
┌──────────┬──────────┬──────────┬──────────┐
│    🏠    │  🔍      │  🛠️     │  📋      │
│  Vehicle │  Diagnos │  Coding  │  History │
└──────────┴──────────┴──────────┴──────────┘
```

- Vehicle tab: overview dashboard (VIN, model, mileage, battery voltage, I-level)
- Diagnostics tab: DTC read/clear
- Coding tab: sub-tabs for Easy + Advanced
- History tab: service records

Active tab is highlighted in BMW blue. Inactive tabs are slightly dimmed.

---

## Screen 4: Vehicle Overview (🏠 tab)

```
┌──────────────────────────────────────────┐
│  Vehicle Information                     │
│  ┌──────────────────────────────────────┐│
│  │ Model      F48 X1 xDrive25i (F048)   ││
│  │ VIN        WBAJG7101XXXXXXX          ││
│  │ Mileage    87,432 km                 ││
│  │ Prod Date  2018-03-14                ││
│  │ I-Level    F056-18-07-530            ││
│  │ Battery    12.4V                     ││
│  └──────────────────────────────────────┘│
│                                          │
│  Connected ECUs: 27                      │
│  ┌──────────────────────────────────────┐│
│  │ DME · EGS · ZGW · FEM · REM · KOMBI  ││
│  │ IHKA · ASD · HU_NBT · PMA · ACSM ... ││
│  └──────────────────────────────────────┘│
└──────────────────────────────────────────┘
```

Quick glance after connection. Pulled from UDS 0x22 identifiers and SVT tree.

---

## Screen 5: Diagnostics (🔍 tab)

### No DTCs

```
┌──────────────────────────────────────────┐
│                                          │
│              ✅                          │
│     No fault codes found!                │
│     No faults reported by the ECUs successfully scanned.                 │
│                                          │
│     [Read DTCs Again]                    │
│                                          │
└──────────────────────────────────────────┘
```

### DTCs present

```
┌──────────────────────────────────────────┐
│  Fault Codes (3)                         │
│                                          │
│  ┌─ B7F805 ──────────────────────────┐   │
│  │ Head unit DAB antenna: line disc. │   │
│  │ 87,432 km · Oct 12 2026 · 14:22  │ > │
│  └────────────────────────────────────┘   │
│  ┌─ 8040BD ──────────────────────────┐   │
│  │ Terminal 30F reset or shutdown    │   │
│  │ 87,430 km · Oct 10 2026 · 09:15  │ > │
│  └────────────────────────────────────┘   │
│  ┌─ CD9427 ──────────────────────────┐   │
│  │ Drivetrain message not current    │   │
│  │ 87,120 km · Sep 28 2026 · 16:40  │ > │
│  └────────────────────────────────────┘   │
│                                          │
│           [ Clear All DTCs ]             │
│              (red button)                │
└──────────────────────────────────────────┘
```

Each DTC card shows:
- Hex code + short description (from `DtcDatabase.describe()`)
- Mileage and timestamp (from UDS 0x19 snapshot data, if available)
- `>` arrow to expand for detail view

### DTC detail (expanded from list)

```
┌──────────────────────────────────────────┐
│  ← Back to DTC list                      │
│                                          │
│  B7F805                                  │
│  Connection head unit to DAB L-band      │
│  antenna base: line disconnection        │
│                                          │
│  ECU:        CHAMP2 (Headunit)           │
│  Status:     Confirmed, not pending      │
│  Fault type: Signal or value below       │
│              threshold (0x02)            │
│  First seen: 87,432 km / Oct 12 2026     │
│  Environment: Battery 12.1V, Speed 0     │
│                                          │
│  [Search Web for "B7F805 BMW"]           │
│  [Clear This DTC]                        │
└──────────────────────────────────────────┘
```

"Search Web" opens the system browser with a pre-filled search query.

### Read flow

1. User enters Diagnostics tab
2. Spinner: "Reading fault codes..."
3. App sends UDS 0x19 02 08 to each identified ECU through serialized transport transactions (with timeout)
4. Results aggregated with ECU identity retained, enriched with DtcDatabase
5. Display list or "No faults" message

### Clear flow

1. User clicks "Clear All DTCs"
2. Confirmation dialog: "Clear all fault codes from all ECUs? This cannot be undone."
3. Spinner: "Clearing fault codes..."
4. App sends UDS 0x14 FF FF FF to every ECU
5. Re-read DTCs to confirm
6. Show "All fault codes cleared" or list any that remain

---

## Screen 6: Service History (📋 tab)

### List view

```
┌──────────────────────────────────────────┐
│  Service History                         │
│                                          │
│  ┌─ 87,000 km · Mar 15 2026 ─────────┐   │
│  │ Engine oil, Microfilter, Vehicle   │ > │
│  │ check                              │   │
│  └────────────────────────────────────┘   │
│  ┌─ 72,000 km · Mar 02 2025 ─────────┐   │
│  │ Engine oil, Microfilter, Front     │ > │
│  │ brakes                             │   │
│  └────────────────────────────────────┘   │
│  ┌─ 57,000 km · Feb 18 2024 ─────────┐   │
│  │ Engine oil, Microfilter, Vehicle   │ > │
│  │ check, Spark plugs                 │   │
│  └────────────────────────────────────┘   │
│                                          │
│        [+ Add New Service Entry]         │
│              (green button)              │
└──────────────────────────────────────────┘
```

Entries require a verified read-only headunit contract (unresolved; see docs/12).
Sorted by date descending.

### Detail view (expanded from list)

```
┌──────────────────────────────────────────┐
│  ← Back to list                          │
│                                          │
│  Service at 87,000 km                    │
│  Date: March 15, 2026                    │
│  Dealer: BMW Munich                      │
│                                          │
│  Work carried out:                       │
│  ✓ Engine oil change (5W-30)             │
│  ✓ Microfilter / cabin filter            │
│  ✓ Vehicle check (standard scope)        │
│  ✓ Brake fluid change                    │
│                                          │
│  Next service: 102,000 km / Mar 2028     │
│  Next oil:      97,000 km / Mar 2027     │
└──────────────────────────────────────────┘
```

### Add new entry (modal or page)

```
┌──────────────────────────────────────────┐
│  ← Cancel          New Service Entry     │
│                                          │
│  Date:        [2026-10-25       📅]      │
│  Mileage:     [87,500           km]      │
│  Dealer:      [BMW Munich            ]   │
│                                          │
│  Services performed:                     │
│  ☐ Engine oil change                     │
│  ☐ Microfilter / cabin filter            │
│  ☐ Air filter                            │
│  ☐ Fuel filter                           │
│  ☐ Spark plugs                           │
│  ☐ Front brake pads                      │
│  ☐ Rear brake pads                       │
│  ☐ Brake fluid                           │
│  ☐ Vehicle check (standard scope)        │
│  ☐ Vehicle check (extended scope)        │
│  ☐ Coolant                               │
│                                          │
│  Next service due:                       │
│  Date:    [2028-03-15         📅]        │
│  Mileage: [102,000           km]        │
│                                          │
│  Next oil change due:                    │
│  Date:    [2027-03-15         📅]        │
│  Mileage: [97,000            km]         │
│                                          │
│  Notes: [                            ]   │
│                                          │
│           [ Save to Vehicle ]            │
│              (green button)              │
└──────────────────────────────────────────┘
```

Checkboxes for common BMW service items. Date and mileage pickers.
Writes require a verified headunit encoder and readback contract (unresolved; see docs/12).

---

## Write integrity requirement (owner-confirmed, 2026-10-28)

Coding and history mutations save a durable backup of the original vehicle data,
retain intended state, then reread and compare before showing success. Fault
clearing has an explicit no-saved-report exception. On reconnect after interrupted
writes, reread/compare before user-chosen recovery; never automatically replay.
History supports add/edit/delete/replace; CBS reads/resets are future scope.
The historical dialogs below are proposals; do not advertise restore capability
until a matching-identity vehicle restore and readback path exists.

## Screen 7: Coding — shared behavior

Both Easy and Advanced Coding share these elements:

**Top bar counter:**
```
│  🛠️ Coding  │  [3 changes pending]  │
```

**Bottom buttons (visible when changes exist):**
```
│  [Clear All]              [Write to Car] │
│   (gray)                    (green)      │
```

**Write flow:**
1. User clicks "Write to Car"
2. Warning dialog: "You are about to write 3 coding changes. Continue?"
3. If Advanced: second warning about risks
4. **Auto-backup** current coding data for the affected ECUs (saved to disk)
5. Spinner: "Writing coding data..." (per ECU, sequential)
6. Reread the affected car state and compare with intended state; report success only on a verified match.
7. Failure: "Failed to write [ECU_NAME]. Original coding has been backed up.
   [Rollback] [Retry]"

---

## Screen 8: Easy Coding (🛠️ tab → Easy)

### Category list

```
┌──────────────────────────────────────────┐
│  Easy Coding                             │
│                                          │
│  ┌────────────────────────────────────┐   │
│  │ 💡 Lighting                     >  │   │
│  │ Angel Eyes brightness, welcome     │   │
│  │ lights, DRL behavior              │   │
│  └────────────────────────────────────┘   │
│  ┌────────────────────────────────────┐   │
│  │ 🚪 Comfort                       >  │   │
│  │ Fold mirrors, window control,     │   │
│  │ seat heating memory               │   │
│  └────────────────────────────────────┘   │
│  ┌────────────────────────────────────┐   │
│  │ 📊 Instrument Cluster            >  │   │
│  │ Digital speed, M Performance      │   │
│  │ logo, startup animation           │   │
│  └────────────────────────────────────┘   │
│  ┌────────────────────────────────────┐   │
│  │ 🎵 Audio / iDrive               >  │   │
│  │ Disclaimer timeout, video in      │   │
│  │ motion, sound settings            │   │
│  └────────────────────────────────────┘   │
│  ... more categories ...                 │
└──────────────────────────────────────────┘
```

Categories and options filtered to the specific vehicle model (FA/VO).
Data from the curated coding database (see docs/11).

### Option detail (click into a category → pick an option)

```
┌──────────────────────────────────────────┐
│  ← Easy Coding    Angel Eyes Brightness  │
│                                          │
│  Controls the brightness of the angel    │
│  eye / corona ring daytime running       │
│  lights. Factory default is 8%.          │
│                                          │
│  Current value: 8% (factory)             │
│                                          │
│  ○ Very low   (4%)                       │
│  ○ Low        (8%)  ← current            │
│  ● Medium     (12%)                       │
│  ○ High       (16%)                       │
│  ○ Very high  (20%)                       │
│                                          │
│  Changes pending: 1                       │
└──────────────────────────────────────────┘
```

Radio buttons or toggle switches depending on the option type.
Each option shows the coded value and translation.

---

## Screen 9: Advanced Coding (🛠️ tab → Advanced)

### SVT ECU tree

```
┌──────────────────────────────────────────┐
│  �⚠  Advanced coding — use with caution    │
│  │ Incorrect values may cause             │
│  │ malfunctions. Always back up first.     │
│  └────────────────────────────────────────│
│                                          │
│  ┌─ DME (Engine) ───────────────────┐     │
│  │ Digital Motor Electronics     >  │     │
│  └─────────────────────────────────┘     │
│  ┌─ EGS (Transmission) ────────────┐     │
│  │ Electronic Transmission        >  │     │
│  └─────────────────────────────────┘     │
│  ┌─ FEM (Body Controller) ────────┐     │
│  │ Front Electronic Module    >    │     │
│  └─────────────────────────────────┘     │
│  ┌─ HU_NBT (Headunit) ────────────┐     │
│  │ Navigation / iDrive         >  │     │
│  └─────────────────────────────────┘     │
│  ... all ECUs from SVT tree ...          │
└──────────────────────────────────────────┘
```

Full SVT list from the car. Click ECU → expand to function groups → expand
to individual FDL parameters.

### FDL parameter editing (inside an ECU)

```
┌──────────────────────────────────────────┐
│  ← FEM          BDC_BODY / 3062          │
│                                          │
│  Function:  PfFzgKl30BlerFahrzeugstart  │
│  German:    Ausgang Klemme 30B bei       │
│             Fahrzeugstart                 │
│  English:   Terminal 30B output on       │
│             vehicle start (best guess)    │
│                                          │
│  Type:      Wert_2 (1 byte)              │
│  Current:   01 (aktiv)                    │
│                                          │
│  New value: [01    ]                     │
│             (hex input)                  │
│                                          │
│  ⚠️ Warning: This parameter controls     │
│  the power supply to multiple ECUs.      │
│  Incorrect values may prevent the        │
│  vehicle from starting.                  │
└──────────────────────────────────────────┘
```

German→English is a best-effort machine translation (the LLM translation
from our database). Both are shown so the user can cross-reference.
Hex-only input for raw FDL values.

---

## Screen 10: Backups & Rollback (⚙️ → Backups)

```
┌──────────────────────────────────────────┐
│  ← Settings       Coding Backups       │
│                                         │
│  Backup location:                       │
│  ~/BMW-Tool/backups/                    │
│                                         │
│  ┌─ 2026-10-25 14:22 ──────────────┐    │
│  │ FEM, REM, HU_NBT, KOMBI, IHKA   │    │
│  │ 3 coding changes                │    │
│  │                    [Rollback] > │    │
│  └──────────────────────────────────┘    │
│  ┌─ 2026-10-20 09:15 ────────────┐    │
│  │ FEM, HU_NBT                     │    │
│  │ 1 coding change                 │    │
│  │                    [Rollback] > │    │
│  └──────────────────────────────────┘    │
└──────────────────────────────────────────┘
```

Backups store the raw CAFD/FDL data per ECU before writing. Rollback requires a verified per-ECU write/readback contract and matching
vehicle/software identity; the current UI-only restore does not meet this requirement.

Backup format (per directory):
```
backups/2026-10-25_14-22/
├── manifest.json        # timestamp, VIN, ECUs affected, change summary
├── FEM_01.bin           # raw CAFD data dump
├── HU_NBT.bin
├── KOMBI.bin
└── ...
```

---

## Screen 11: About (⚙️ → About)

```
┌──────────────────────────────────────────┐
│  ← Settings       About                  │
│                                          │
│           [BMW Logo - small]             │
│                                          │
│  BMW Diagnostic Tool                     │
│  Version 1.0.0                           │
│                                          │
│  Built with Python, PySide6, and a       │
│  lot of reverse engineering.             │
│                                          │
│  Compatible with BMW F, G, U, I series   │
│  (2011+). ENET cable required.           │
│                                          │
│  This tool is not affiliated with BMW AG.│
│  Use at your own risk.                   │
│                                          │
│  [Check for Updates]                     │
└──────────────────────────────────────────┘
```

---

## State machine

```
  WELCOME ──connect──→ CONNECTING ──success──→ CONNECTED
     ↑                      │                      │
     │                   timeout              ┌─────┴─────┐
     │                      │                 │           │
     └──disconnect──────────└──error──→ ERROR │  TABS     │
                                              │  ACTIVE   │
                                              │           │
                                              └───────────┘
```

---

## Data flow per module

| Module | Read from car | Write to car |
|--------|--------------|--------------|
| **Vehicle overview** | UDS 0x22 (VIN, I-Level), 0x1A (mileage) | None |
| **Diagnostics** | UDS 0x19 02 (DTCs by status), 0x19 04/06 (snapshot) | UDS 0x14 (clear) |
| **Service History** | Read-only contract unresolved (doc 12) | Encoder/readback unresolved (doc 12) |
| **Easy Coding** | UDS 0x22 (read CAFD/FDL per ECU) | Verified per-ECU coding contract; no guessed service/DID fallback |
| **Advanced Coding** | UDS 0x22 (read full SVT + FDL) | UDS 0x2E (WriteDataByIdentifier) |

---

## Error handling matrix

| Error | User sees |
|-------|----------|
| ENET cable not detected | "No ENET interface found. Connect the cable and try again." |
| ZGW not responding (APIPA) | "Vehicle not found on the network. [Start DHCP Server] [Retry]" |
| ECU timeout (30s) | "ECU [name] is not responding. [Skip] [Retry] [Abort]" |
| UDS negative response (0x7F) | "ECU [name] rejected the request (code 0x[XX]). [Details]" |
| Write failure | "Failed to write to [ECU]. Your original coding has been backed up. [Rollback] [Retry]" |
| Connection lost mid-session | Red top bar. "Connection lost. Check the ENET cable and ignition. [Reconnect]" |
| Coding database missing | "Coding database not found. Reinstall the application." |
| DTC database missing | "DTC descriptions unavailable. Reinstall the application." |
| Backup disk full | "Cannot save backup — disk is full. Free up space and try again." |
