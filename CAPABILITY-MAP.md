# Capability Map: BMW Diagnostic Tool

> Phase 0 Scope Check.
> This is a **single desktop app** — one window, one connection, one theme.
> "Feature sections" are tabs/pages, not independent services.

## App anatomy

```
┌─────────────────────────────────────────────────────────────┐
│  Shared Infrastructure (built first, used by everything)   │
│  connection │ CarWorker threads │ theme.qss │ DtcDatabase  │
└───────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
   Vehicle Info          Diagnostics           Service History
   (dashboard tab)       (fault codes tab)     (maintenance tab)
                              │
                              ▼
                          Coding
                    (Easy + Advanced tabs)
```

Two layers, not six modules:

| Layer | What | Built when |
|-------|------|------------|
| **Infrastructure** | ENET connection, UDS transport, `CarWorker` threads, dark theme QSS, `DtcDatabase` singleton | First, once |
| **Feature sections** | Vehicle dashboard, Diagnostics, Service History, Coding | After infrastructure, in any order |

## Feature sections

| Section | What the user sees | Car operations |
|---------|--------------------|----------------|
| **Vehicle Dashboard** | Welcome → Connect flow. Post-connection: VIN, model, mileage, battery, ECU count | UDS 0x22 (VIN, I-level), 0x1A (mileage), SVT read |
| **Diagnostics** | DTC list (code, km, date, description). Expand for detail. Red "Clear All" button. Web search link | UDS 0x19 (read DTCs from all ECUs), 0x14 (clear) |
| **Service History** | Timeline by km/date. Expand for work done. Green "Add Entry" button → form dialog | UDS 0x22 (read headunit records), 0x31 (write RoutineControl) |
| **Coding** | Easy: curated category → option toggles. Advanced: SVT tree → FDL hex editor. Pending changes counter. Write/Clear buttons. Auto-backup | UDS 0x22 (read CAFD), 0x2E (write), backup to disk |

All four share: the car connection, `CarWorker` for background I/O, the spinner/error patterns, and the dark theme. None depends on another being finished — they just need the infrastructure to exist.

## Build order

```
1. Infrastructure  (connection + workers + theme + DtcDatabase)
        │
        ├─→ 2. Vehicle Dashboard  (proves connection works end-to-end)
        │
        └─→ 3–5. Diagnostics, Service History, Coding  (any order, can parallel)
```

Vehicle Dashboard first because it's the simplest feature — read VIN, show it — and proves the entire infrastructure stack works before building the complex features.