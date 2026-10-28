# Tasks: Feature Gaps — Real-Car Readiness

> **Historical plan/status:** superseded by [the 2026-10-28 audit](../docs/19-audit-and-readiness.md).
> Checkboxes/merge claims below are not acceptance evidence. Protocol examples
> may be wrong; use [corrections](../docs/20-protocol-evidence.md) and
> [owner decisions](../docs/21-product-decisions.md) before implementing.

> Merged in PR #6 (`feat/feature-gaps`). Historical merge claim; completion not established (most checkboxes below are open).

---

## Phase 1: Real-car data paths (unblocks connecting to car)

These are the minimum to make the app show real data instead of stub/mock values.

- [ ] **G-1: Read mileage via UDS 0x1A**
  - CarWorker `MileageReadWorker` sends `0x1A` (ReadDynamicallyDefineDataIdentifier) or the correct BMW mileage DID to KOMBI (0x60). Parse the response bytes into km.
  - Wire into `VehiclePage._load_from_car()` so mileage_label shows real km, not "Unknown".
  - Acceptance: DEMO and real-car both show mileage on Vehicle page.
  - Verify: DEMO mode shows `66,000 km` from mock. Real car TBD with ENET cable.
  - Files: `ui/vehicle_page.py`, `app/worker.py`, `app/mock_connection.py`

- [ ] **G-2: Read SVT ECU list from ZGW**
  - ZGW (0x10) responds to an SVT read with the vehicle's ECU inventory. Parse the response into `[{name, description, addr}]` list.
  - Store on connection object or return from `_load_from_car()`. Wire into VehiclePage ECU list and DiagnosticsPage ECU list.
  - Acceptance: ECU count and chip list populated from car data.
  - Verify: DEMO uses mock SVT (already works). Real car shows actual ECU count.
  - Files: `app/connection.py`, `ui/vehicle_page.py`, `ui/main_window.py`

- [ ] **G-3: Read battery voltage from DME**
  - Send `0x22` with the correct battery DID to DME (0x12) or ZGW. Parse response as voltage with 0.1V resolution.
  - Wire into `VehiclePage._load_from_car()` so battery_label shows real voltage.
  - Acceptance: DEMO shows `12.4V` from mock. Real car shows actual voltage.
  - Files: `ui/vehicle_page.py`, `app/mock_connection.py`

- [ ] **G-4: Real-car DTC read — handle 0x7F negative responses gracefully**
  - When an ECU returns `0x7F` (service not supported or no DTCs), skip silently instead of logging a warning. Not all ECUs support DTC reads.
  - Acceptance: No spurious "ECU rejected" warnings in the log during a real-car DTC read.
  - Verify: DEMO unchanged. Real car: no false warnings in `~/BMW-Tool/logs/uds.log`.
  - Files: `ui/diagnostics_page.py`

- [ ] **G-5: Real-car DTC clear — confirmation and per-ECU error handling**
  - Already has a confirmation dialog and ClearWorker. Add per-ECU error handling: if one ECU fails to clear, continue to the next, report which failed in the final message.
  - Acceptance: Clear All shows a summary dialog: "3 ECUs cleared, 1 failed (DME)".
  - Verify: DEMO unchanged. Real car TBD.
  - Files: `ui/diagnostics_page.py`

- [ ] **G-6: Service history real-car read**
  - Send UDS `0x31` (RoutineControl) with RID `0xA081` (read service history) to the headunit (0x63). Parse the response into `[{date, mileage_km, items}]` list.
  - Wire into `ServiceHistoryPage._load_history()`.
  - Acceptance: DEMO uses mock (already works). Real car shows actual service records from headunit.
  - Verify: Real car TBD with ENET cable. Reference: `docs/12-service-history-wire-format.md`.
  - Files: `ui/service_history_page.py`, `app/worker.py`

- [ ] **G-7: Service history real-car write**
  - Send UDS `0x31` (RoutineControl) with RID `0xA081` (add entry) to headunit (0x63). Build the argument string per `docs/12-service-history-wire-format.md`.
  - Wire into `AddServiceDialog` flow — after OK, send via CarWorker.
  - Acceptance: Entries written to headunit. Mock: persisted to JSON file (already works).
  - Verify: Real car TBD. Mock: save + reload survives reconnects.
  - Files: `ui/service_history_page.py`, `app/worker.py`

- [ ] **G-8: Coding real-car read**
  - Send UDS `0x22` to read CAFD/FDL data from each ECU. Parse into the option structure used by `MOCK_CATEGORIES`.
  - Replace `MOCK_CATEGORIES` with real data after connection.
  - Acceptance: Easy Coding shows actual vehicle options instead of mock categories.
  - Verify: DEMO unchanged. Real car TBD.
  - Files: `ui/coding_page.py`, `app/worker.py`

- [ ] **G-9: Coding real-car write with auto-backup**
  - Send UDS `0x2E` (WriteDataByIdentifier) for each modified FDL parameter. Before writing, auto-backup the original CAFD data to `~/BMW-Tool/backups/`.
  - Backup format: `backups/YYYY-MM-DD_HH-MM/ECU_NAME.bin` + `manifest.json` with VIN, ECU, changes.
  - Rollback: restore from backup via `0x2E`.
  - Acceptance: Write confirmation dialog mentions backup path. Backup files created on disk. Rollback available from Backups page.
  - Verify: DEMO unchanged. Real car TBD.
  - Files: `ui/coding_page.py`, `app/backup.py` (new), `app/worker.py`

---

## Phase 2: Missing UI features

These are features described in the spec but not yet built.

- [ ] **G-10: DTC detail expanded view — full information**
  - Add to each expandable DTC card: ECU full name from SVT, status byte decoded (confirmed/pending), fault type from `DtcDatabase.fault_type()`, "Clear This DTC" per-DTC button.
  - Acceptance: Expanding a DTC card shows ECU name, status text, fault type, and per-DTC clear button.
  - Verify: Visual in DEMO mode — B7F805 shows HU_NBT, Confirmed, fault type description.
  - Files: `ui/diagnostics_page.py`

- [ ] **G-11: Advanced Coding — SVT ECU tree + FDL hex editor**
  - Replace the advanced coding placeholder. Read SVT from car. Display ECU tree. Tap ECU to expand function groups. Tap function to show FDL parameters with hex editor.
  - Safety: 22 blocked ECUs (airbags, engine ECU, cameras) grayed out with warning.
  - Acceptance: ECU tree populated from SVT. FDL parameters editable with hex input.
  - Verify: DEMO uses mock SVT (already in f48_x1.json). Real car TBD.
  - Files: `ui/coding_page.py`, `app/backup.py`

- [ ] **G-12: Backups page**
  - Gear menu → Backups opens a page listing all backup snapshots. Each shows date, ECUs affected, change count. Rollback button restores selected backup.
  - Backup location: `~/BMW-Tool/backups/`.
  - Acceptance: After a coding write, a backup appears in the list. Rollback restores pre-write state.
  - Verify: Visual in DEMO mode after simulated write.
  - Files: `ui/backups_page.py` (new), `ui/main_window.py`, `app/backup.py`

- [ ] **G-13: Loading state — cancel/timeout button after 10s, retry after 30s**
  - Every car operation shows a cancel button after 10 seconds. After 30 seconds with no response, show a retry/cancel dialog: "The car is not responding. Check ignition and ENET cable connection. [Retry] [Cancel]".
  - Acceptance: Long operations show cancel button. Timeout triggers retry dialog.
  - Verify: DEMO operations are instant (no change). Real car TBD.
  - Files: `ui/main_window.py`, `app/worker.py`

---

## Phase 3: Polish and infrastructure

- [ ] **G-14: Error handling matrix — user-facing messages**
  - Wire the 9 error scenarios from `docs/16-ui-spec.md` (Error handling matrix) to actual user-facing dialogs:
    - ENET cable not detected → "No ENET interface found."
    - ZGW not responding → "[Start DHCP Server] [Retry]"
    - ECU timeout (30s) → "[Skip] [Retry] [Abort]"
    - UDS negative response (0x7F) → "ECU [name] rejected the request (code 0x[XX])"
    - Write failure → "Failed to write to [ECU]. Backup saved. [Rollback] [Retry]"
    - Connection lost → Red dot + "Connection lost. [Reconnect]"
    - Coding database missing → "Coding database not found. Reinstall."
    - DTC database missing → "DTC descriptions unavailable. Reinstall."
    - Backup disk full → "Cannot save backup — disk full."
  - Acceptance: Each error path produces the specified dialog.
  - Files: `ui/main_window.py`, `ui/coding_page.py`, `ui/diagnostics_page.py`, `app/connection.py`

- [x] **G-15: Rename `bimmercode_data/` to `coding_data/`**
  - Rename the directory on disk. Update any remaining references.
  - Add `bimmercode_data/` to `.gitignore` as fallback.
  - Acceptance: No mention of "bimmercode_data" in shipped code or assets.
  - Files: directory rename, `app/connection.py`, `main.py`, `.gitignore`

- [ ] **G-16: PyInstaller bundle for macOS**
  - Run PyInstaller with `main.py`. Verify the `.app` launches, all assets included (theme.qss, dtc_descriptions.db, coding_data/, mock_data/).
  - Acceptance: `dist/BMW Self Service.app` opens and works in DEMO mode.
  - Verify: Launch on macOS, connect in DEMO mode, navigate all 4 tabs.
  - Files: `main.py`, `requirements.txt`

- [ ] **G-17: Windows compatibility check**
  - Test `list_interfaces()` on Windows with netifaces.
  - Test `start_dhcp_server()` with simple-dhcp-server.
  - Test the full app launch on Windows.
  - Acceptance: `python main.py` launches without errors on Windows 10/11.
  - Verify: Manual test on Windows.

---

## Dependency order

```
G-1 ─┐
G-2 ─┤
G-3 ─┤
G-4 ─┤  No dependencies — pure feature work
G-5 ─┘

G-6 → G-7   (read before write)

G-8 → G-9 → G-11 → G-12   (read → write → backup → advanced)

G-13 → G-14   (timeout patterns feed error handling)

G-15 ─┐
G-16 ─┤  Independent infrastructure
G-17 ─┘
```

### Suggested build order

```
Phase 1 (unblock car): G-1, G-2, G-3, G-4, G-5  (parallel)
Phase 2 (round out):   G-10, G-6, G-8  (parallel)
Phase 3 (write paths): G-7, G-9, G-11, G-12  (sequential)
Phase 4 (polish):      G-13, G-14  (parallel)
Phase 5 (ship):        G-15, G-16, G-17  (parallel)
```

## Parallel vs sequential

| Group | Tasks | Can run in parallel? |
|-------|-------|---------------------|
| A | G-1, G-2, G-3, G-4, G-5 | Yes — independent data sources |
| B | G-10, G-6, G-8 | Yes — different UI pages |
| C | G-7 (needs G-6), G-9 (needs G-8) | Partially — write depends on read |
| D | G-11 (needs G-9), G-12 (needs G-9/G-11) | Sequential |
| E | G-13, G-14 | Yes |
| F | G-15, G-16, G-17 | Yes |