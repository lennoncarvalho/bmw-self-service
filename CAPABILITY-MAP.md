# Capability Map: BMW Self Service (Up-to-date)

> Last updated: 2026-10-26 — cross-referenced against current code.
> Single desktop app — one window, one connection, one theme.

## App anatomy

```
┌─────────────────────────────────────────────────────────────┐
│  Shared Infrastructure                                      │
│  connection │ CarWorker │ theme.qss │ DtcDatabase           │
│  CodingDatabase │ SecurityAccess │ Backups                  │
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
                              │
                              ▼
                          Backups
                    (backup/rollback page)
```

## Feature sections

| Section | What the user sees | Car operations |
|---------|--------------------|----------------|
| **Vehicle Dashboard** | Welcome → Connect flow. Post-connection: VIN, model, mileage, battery, production date, ECU count, FA type code | UDS 0x22 (VIN, I-level, FA), 0x1A (mileage), SVT read |
| **Diagnostics** | DTC list with descriptions, ECU names, status decode, fault type. Expand for detail with first-seen mileage/date, per-DTC clear, web search. MIL status. Clear All with per-ECU reporting. Snapshot data. | UDS 0x19 02 (DTCs), 0x19 03 (snapshot IDs), 0x19 04 (snapshot records), 0x14 (clear single/all) |
| **Service History** | Timeline by date descending. Expand for work done. Add Entry form dialog. Erase History with confirmation. | UDS 0x22 (read headunit), UDS 0x2E (write entry with DID 0xA081, erase with DID 0xA080) |
| **Coding** | Easy: 33 categories with real presets from coding database, English labels. Advanced: SVT ECU tree with FDL functions, DIDs, byte masks. Pending changes counter. Write/Clear buttons. Auto-backup before write. | UDS 0x22 (read CAFD), UDS 0x2E (write with real DIDs), CodingDatabase (decrypt .enc, parse CAFD presets) |
| **Backups** | List of timestamped backup snapshots. Rollback to restore coding values. | Created automatically before each coding write (`~/BMW-Tool/backups/`) |

All share: car connection, `CarWorker` for background I/O, spinner/error patterns, dark theme.