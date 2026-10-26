# Spec: Infrastructure Layer (Up-to-date)

> Built and verified. Last updated: 2026-10-26.
> Cross-referenced against current code: 9 app modules, 7 UI pages, 39 tests.

---

## What's built

| Layer | Module | File |
|-------|--------|------|
| Transport | HSFZ (F-series, TCP 6801), DoIP (G/U/I, TCP 13400) | `app/connection.py` |
| Discovery | UDP broadcast, DHCP fallback, interface detection | `app/connection.py` |
| Mock | Full car simulation for DEMO mode | `app/mock_connection.py` |
| UDS | Message build/parse (ISO 14229) | `app/uds.py` |
| Threading | `CarWorker(QThread)` base class | `app/worker.py` |
| DTC lookup | 88,580 entries, read-only SQLite, OBD2 fallback | `app/dtc_db.py` |
| Coding DB | AES decrypt `.enc` files, parse CAFD presets | `app/coding_db.py` |
| Security | Protected ECU registry, seed/key framework | `app/security.py` |
| Theme | Dark QSS, BMW M colors | `app/theme.py`, `assets/theme.qss` |
| Pages | Welcome, Vehicle, Diagnostics, Service History, Coding, Backups | `ui/*.py` |
| Entry | Argument parsing, logging setup | `main.py` |

---

## Project structure

```
bmw-self-service/
├── main.py
├── AGENTS.md
├── requirements.txt
├── dtc_descriptions.db           # 88K DTC entries (committed, read-only)
├── coding_data/                  # Decrypted .enc files, .strings, ECU data
├── mock_data/
│   └── f48_x1.json               # F48 X1: VIN, DTCs, service history, SVT
├── assets/
│   ├── theme.qss                 # Dark theme QSS
│   └── gear.svg                  # SVG gear icon for menu button
├── app/
│   ├── __init__.py
│   ├── connection.py             # HSFZ, DoIP, DHCP, discover_zgw()
│   ├── mock_connection.py        # MockConnection for DEMO mode
│   ├── uds.py                    # UDS message build/parse
│   ├── worker.py                 # CarWorker(QThread) base class
│   ├── dtc_db.py                 # DtcDatabase singleton
│   ├── coding_db.py              # CodingDatabase — decrypt .enc, query presets
│   ├── security.py               # Protected ECU registry, seed/key framework
│   └── theme.py                  # QSS loader, color constants
├── ui/
│   ├── __init__.py
│   ├── main_window.py            # QMainWindow shell, top bar, bottom nav
│   ├── welcome_page.py           # Series picker, connect button
│   ├── vehicle_page.py           # VIN, model, mileage, battery, ECU list
│   ├── diagnostics_page.py       # DTC read/clear, MIL status, snapshots
│   ├── service_history_page.py   # Timeline, add/erase entries
│   ├── coding_page.py            # Easy + Advanced coding, write/backup
│   └── backups_page.py           # Backup list, rollback
├── tests/
│   ├── test_uds.py
│   ├── test_dtc_db.py
│   └── test_connection.py
├── docs/                         # 18 specification documents
└── tasks/                        # Task files (historical — all completed)
```

---

## Success criteria

- [x] Series picker shows F/G/U/I with year/model guidance, selected series sets protocol
- [x] DEMO Mode toggle in gear menu — checked → instant connect with mock data (no network)
- [x] DEMO toggle disabled while connected
- [x] Interface dropdown hidden when DEMO mode is checked
- [x] `discover_zgw()` finds a car within 5 seconds or returns None
- [x] DHCP fallback: if elevation denied → APIPA countdown 20s → "DHCP requires admin rights" if still failing
- [x] `HSFZConnection.send_uds(addr, payload)` sends and receives correctly
- [x] `CarWorker` runs on background thread, emits `progress`/`finished`/`error` signals
- [x] `DtcDatabase.describe("B7F805")` returns English description in <1ms
- [x] Dark theme applies to QMainWindow, all buttons, labels, and scroll areas
- [x] QMainWindow opens maximized, shows 4 grayed-out nav buttons before connection
- [x] Welcome page displays BMW logo, connect button, series picker, 5 instruction bullets
- [x] Disconnect returns to welcome screen
- [x] UDS logs at DEBUG level to rotating file (`~/BMW-Tool/logs/`, 5MB × 3 files)
- [x] `python main.py` launches the window without errors on macOS and Windows
- [ ] `pyinstaller` produces a working `.app` (macOS) and `.exe` (Windows) — not yet verified

---

## Known gaps

| Gap | Status |
|-----|--------|
| PyInstaller bundle not verified on macOS/Windows | Deferred |
| Real-car connection not tested (0 km on physical car) | Deferred |
| CAFD bytes not read from car (coding writes use DID-correct payloads, not bit-accurate CAFD modifications) | Documented in `tasks/coding-database-gaps.md` |
| Seed/key algorithms for protected ECUs (22 of 139) not implemented | Documented in `tasks/coding-database-gaps.md` |