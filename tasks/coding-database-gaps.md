# Tasks: Coding Database & Protocol Gaps

> Audit of all specs against current code. 15 gaps found.
> Branch: `feat/coding-database`

---

## Phase 1: Coding database foundation (blocks all real-car coding)

- [x] **T-1: Build `app/coding_db.py` — `CodingDatabase` class**
  - Decrypt `.enc` files with AES-256-CBC (key `2443...`, IV `7639...`, from `docs/08`)
  - Optional GZIP decompress after decryption
  - Output: JSON plaintext
  - Parse `.strings` files (Apple format) — `en.strings` (1537 entries), `de.strings`
  - Expose `load_ecu(cafd_id, variant)` — loads root index + CAFD variant
  - Expose `get_presets(cafd_id)` — curated presets with human labels
  - Expose `get_current_value(preset, current_bytes, cafd_id, variant)` — determine active option
  - Expose `build_write_payload(preset, selected_option, current_bytes, cafd_id, variant)` — modified CAFD bytes
  - Reference: `docs/13:282-406`, `docs/11`, `docs/08`
  - Files: `app/coding_db.py` (new)

- [x] **T-2: Wire SVT → coding database after connection**
  - After reading SVT ECU list in `CodingPage`, for each ECU:
    - Determine CAFD ID from SVT response (format: `CAFD_XXXXXXXX_XXX_XXX_XXX`)
    - Load root index + variant from `CodingDatabase`
    - Read current CAFD bytes from ECU via UDS 0x22
    - Call `get_current_value()` for each preset
    - Replace `MOCK_CATEGORIES` with real presets
  - Files: `ui/coding_page.py`, `app/coding_db.py`

- [x] **T-3: Replace MOCK_CATEGORIES with coding database lookups**
  - Remove the 4 hardcoded categories and 10 mock options
  - `_build_easy_page()` reads from `CodingDatabase` instead
  - Proper `.strings` labels: "BC_DIGITAL_V" → "Digital Speed in Board Computer"
  - Proper sections from root index: `BOARD_COMPUTER`, `ANGEL_EYES`, etc.
  - Files: `ui/coding_page.py`

- [x] **T-4: Fix CodingWriteWorker to use real DIDs**
  - Use `build_write_payload()` from `CodingDatabase` for each modified option
  - Correct ECU address per option (not hardcoded 0x40)
  - Correct DID per option (not placeholder 0xF000)
  - Correct byte offset + bit mask from CAFD variant
  - Files: `ui/coding_page.py`, `app/coding_db.py`

- [x] **T-5: Replace hardcoded Advanced FDL with real CAFD data**
  - Remove the 3 hardcoded `PfFzgKl30...` mock functions
  - Read real FDL parameters from CAFD variant for selected ECU
  - Show `function name`, `storageInfo` (byte offset, mask), current value
  - Safety-critical ECUs still shown as blocked
  - Files: `ui/coding_page.py`

---

## Phase 2: Service history protocol fix

- [x] **T-6: Fix service history write — 0x2E not 0x31**
  - `ServiceHistoryWriteWorker` currently uses 0x31 (RoutineControl)
  - Spec correction (`docs/12:181-186`): STEUERN jobs use 0x2E WriteDataByIdentifier
  - Use `SERVICE_HISTORY_ADD_RID = 0xA081` as the DID for 0x2E
  - Build proper argument string: `day;month;year;corr_cnt;km;dealer_flag;dealer_id;status;count;code;status;dist;time;...`
  - Check positive response: `0x6E` for CIC (status 0x01), NBT/MGU (status 0x00)
  - Check negative response: `0x7F 0x2E <NRC>`
  - Files: `ui/service_history_page.py`

- [x] **T-7: Fix service history read — 0x22 for headunit records**
  - `ServiceHistoryReadWorker` currently uses 0x31
  - Spec (`docs/13:43-44`): use 0x22 ReadDataByIdentifier from headunit
  - Parse response into entries with proper structure
  - Files: `ui/service_history_page.py`

- [x] **T-8: Add erase service history**
  - `SERVICE_HISTORY_ERASE_RID = 0xA080`
  - UDS 0x2E with DID 0xA080 to headunit
  - Add "Erase History" button to service history page (with confirmation)
  - Files: `ui/service_history_page.py`

---

## Phase 3: Diagnostics completeness

- [x] **T-9: Implement MIL status**
  - OBD-II Mode 01 PID 01 via UDS: `0x01 0x01`
  - Parse: bit 7 = MIL on/off, bits 0-6 = DTC count
  - Show MIL indicator (check-engine icon) on diagnostics page
  - Reference: `docs/13:159-166`, `docs/16` screen 5
  - Files: `ui/diagnostics_page.py`, `app/worker.py`

- [x] **T-10: Implement DTC snapshot read**
  - UDS 0x19 04 (report DTC snapshot identification) or 0x19 06 (report DTC with snapshot)
  - Per-DTC: mileage/km at first occurrence, date/timestamp, freeze-frame data
  - Show in DTC detail expanded view
  - Reference: `docs/16:562`
  - Files: `ui/diagnostics_page.py`, `app/worker.py`

---

## Phase 4: Security & robustness

- [x] **T-11: Implement SecurityAccess (0x27) for protected ECUs**
  - 22 of 139 ECUs require seed/key before writing
  - UDS flow: `0x27 0x01` → ECU returns seed → compute key → `0x27 0x02 [key]`
  - Blocked ECUs list: ACSM, DME, DSC, SAS, ZGW, AIRBAG, ABG, MRS, SRS
  - For now: skip SecurityAccess for these ECUs, show warning
  - (Seed/key algorithms are ECU-specific; document as future work)
  - Files: `app/security.py` (new), `ui/coding_page.py`

- [x] **T-12: Add connection-lost detection**
  - Monitor alive-check / TesterPresent failures
  - On failure: set status dot red, show "Connection lost. [Reconnect]" dialog
  - Reference: `docs/16:578`
  - Files: `ui/main_window.py`

---

## Phase 5: Polish

- [x] **T-13: Read production date from car**
  - UDS 0x22 to ZGW with production-date DID
  - Currently `_load_from_car` sets `prod_date_label` to empty string
  - Files: `ui/vehicle_page.py`

- [x] **T-14: Add ECU-level Skip/Retry/Abort for DTC reads**
  - When an ECU times out (30s), offer: [Skip] [Retry] [Abort]
  - Reference: `docs/16:575` error matrix
  - Files: `ui/diagnostics_page.py`, `app/worker.py`

- [x] **T-15: Implement read_fa() for factory options**
  - UDS 0x22 to ZGW to read Vehicle Order / FA
  - Display factory option codes on Vehicle page
  - Reference: `docs/13:56`
  - Files: `ui/vehicle_page.py`

---

## Dependency order

```
Phase 1 (sequential):
  T-1 → T-2 → T-3 → T-4 → T-5
  (each builds on the previous)

Phase 2 (parallel):
  T-6, T-7  (independent)

Phase 2b:
  T-8 (depends on T-6)

Phase 3 (parallel):
  T-9, T-10  (independent)

Phase 4 (parallel):
  T-11, T-12  (independent)

Phase 5 (parallel):
  T-13, T-14, T-15  (independent)
```

### Suggested build order

```
1. T-1  CodingDatabase class           (foundation — unblocks all coding)
2. T-2  SVT → database wiring           (connects car identity to data)
3. T-3  Replace MOCK_CATEGORIES         (real presets in Easy Coding)
4. T-4  Fix CodingWriteWorker DIDs      (real writes)
5. T-5  Advanced FDL from real data     (real Advanced Coding)

6. T-6  Fix service write (0x2E)       (correct protocol)
7. T-7  Fix service read  (0x22)       (correct protocol)
8. T-8  Erase history                   (feature)

9. T-9  MIL status                      (diagnostics)
10. T-10 DTC snapshot                   (diagnostics)

11. T-11 SecurityAccess                 (safety)
12. T-12 Connection-lost detection      (robustness)

13. T-13 Production date                (polish)
14. T-14 Skip/Retry/Abort per ECU       (UX)
15. T-15 Factory options                (polish)
```

---

## Dependencies

| Module | Requires |
|--------|----------|
| `pycryptodome` | AES decryption in `app/coding_db.py` |
| `coding_data/` | `.enc` files + `.strings` on disk |