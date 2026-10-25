# Spec: Infrastructure Layer

> **Phase 1 — Specify.** Reviewed by human before any code.
> Part of: BMW Self Service (`CAPABILITY-MAP.md`)

---

## Assumptions

```
ASSUMPTIONS I'M MAKING:
1. The user has Python 3.13 installed (macOS: brew, Windows: python.org)
2. The ENET cable appears as a standard USB-Ethernet adapter — no special drivers
3. The car's ZGW responds to UDP broadcast on 169.254.255.255:6811 within 5 seconds
4. DHCP server fallback needs sudo (macOS) or admin (Windows) — user accepts elevation
5. dtc_descriptions.db is at the app root alongside main.py
6. bimmercode_data/ directory is at the app root (decrypted .enc files)
7. PySide6 6.12.0 installs cleanly via pip on both platforms
8. No car is connected during development — we mock the connection for testing UI
→ Correct me now or I'll proceed with these.
```

---

## 1. Objective

Build the **shared infrastructure** that every feature section of the BMW
Diagnostic Tool depends on. This is not user-facing — it's the foundation.

**What we're building:**
- ENET cable detection and car connection (HSFZ + DoIP transport)
- UDS message layer (build, send, receive, parse ISO 14229)
- `CarWorker` thread base class for all background car I/O
- `DtcDatabase` singleton (read-only SQLite, 88K entries)
- Dark QSS theme (`assets/theme.qss`)
- `QMainWindow` shell with `QStackedWidget` for page switching

**Success means:** a developer can `from app.connection import HSFZConnection`,
create one, call `conn.send_uds(0x63, bytes([0x22, 0xF1, 0x90]))`, and get bytes
back. Then build any feature section on top without touching networking code.

## 2. Tech Stack

| Layer | Choice | Version |
|-------|---------|---------|
| Language | Python | 3.13 |
| GUI | PySide6 (Qt Widgets) | 6.12.0 |
| Database | sqlite3 (stdlib) | — |
| Networking | socket (stdlib) | — |
| Network interfaces | netifaces | 0.11.0 |
| Threading | QThread (PySide6) | — |
| Packaging | PyInstaller | 6.22.3 |

##3. Commands

```bash
# Create virtual environment
python3.13 -m venv .venv
source .venv/bin/activate        # macOS
.venv\Scripts\activate           # Windows

# Install dependencies
pip install pyside6==6.12.0
pip install pyinstaller==6.22.3
pip install netifaces==0.11.0

# Run the app (development)
python main.py

# Build distributable
pyinstaller --onefile --windowed --name "BMW Self Service" \
    --add-data "dtc_descriptions.db:." \
    --add-data "coding_data:coding_data" \
    --add-data "assets/theme.qss:assets" \
    main.py

# Run tests (if any)
pytest tests/ -v
```

##4. Project Structure

```
bmw-tool/
├── main.py                          # Entry point: QApplication, window launch
├── CAPABILITY-MAP.md                # This document
├── SPEC-INFRASTRUCTURE.md           # This spec
├── requirements.txt                 # pyside6==6.12.0, pyinstaller==6.22.3
├── coding_data/                 # Vehicle coding database (decrypted CAFD files, strings, ECUs)
├── mock_data/                      # Car data for offline development
│   └── f48_x1.json                 # User's F48 X1: VIN, DTCs, service history, SVT
├── assets/
│   ├── theme.qss                # Dark theme — loaded once at startup
│   └── dtc_descriptions.db      # 88K DTC entries (committed, read-only)
├── app/
│   ├── __init__.py
│   ├── connection.py            # ENET detection, HSFZ, DoIP, DHCP, discover_zgw()
│   ├── mock_connection.py       # MockConnection for DEMO mode
│   ├── uds.py                   # UDS message build/parse (ISO 14229)
│   ├── worker.py                # CarWorker(QThread) base class + subclasses
│   ├── dtc_db.py                # DtcDatabase singleton (from docs/14)
│   └── theme.py                 # QSS loader, color constants
├── ui/
│   ├── __init__.py
│   ├── main_window.py           # QMainWindow, top bar, bottom nav, QStackedWidget
│   └── welcome_page.py          # BMW logo, connect button, series picker
├── tests/
│   ├── test_uds.py
│   ├── test_dtc_db.py
│   └── test_connection.py
└── backups/                     # Auto-backup directory (gitignored, created at runtime)
```

##5. Code Style

Type hints on all function signatures. Google-style docstrings on public
methods. snake_case functions, PascalCase classes. 100-char lines.
No QML. No raw sockets in feature code — always go through `connection.py`.

```python
# Example: UDS message building
def build_uds(ecu_addr: int, service: int, payload: bytes = b"") -> bytes:
    """Build a UDS request message with HSFZ framing.

    Args:
        ecu_addr: ECU physical address (e.g. 0x63 for headunit).
        service: UDS service ID (e.g. 0x22 for ReadDataByIdentifier).
        payload: Service-specific data (e.g. identifier bytes).

    Returns:
        Complete HSFZ-framed message ready to send over TCP.
    """
    uds_msg = bytes([service]) + payload
    # HSFZ header: length(4) + type(2) + src(1) + dst(1)
    header = struct.pack(">I", len(uds_msg) + 2) + b"\x00\x01" + bytes([0xF4, ecu_addr])
    return header + uds_msg
```

##6. Testing Strategy

- **Unit tests** for pure functions: `build_uds()`, `parse_uds_response()`,
  `DtcDatabase.describe()`, VIN formatting, hex code normalization.
- **No integration tests** — requires physical ENET cable + car.
- **No UI tests** — visual verification against `docs/16-ui-spec.md`.
- Framework: `pytest`. Run: `pytest tests/ -v`.

##7. Boundaries

### Always do
- Use `CarWorker` for all car I/O — never block the UI thread
- Use parameterized SQL queries — never string formatting
- Log all UDS send/receive at DEBUG level to rotating file (`~/BMW-Tool/logs/uds.log`, 5MB × 3 files)
- Add type hints to new functions
- Return English from DtcDatabase when available, fall back to German
- Window opens maximized on launch

### Ask first
- Adding new pip dependencies (netifaces 0.11.0 approved for interface detection)
- Changing the HSFZ/DoIP protocol implementation
- Modifying `dtc_descriptions.db` schema
- Changing the QSS theme structure

### Never do
- Block the UI thread with network I/O
- Show raw exceptions to the user
- Hardcode ECU addresses — read them from SVT
- Use QML — Qt Widgets only
- Use QListView/QAbstractItemModel — QScrollArea + widgets instead
- Mix asyncio with Qt — QThread only
- Mention external tools or sources in code: no "BimmerCode", "BimmerLink", "ISTA", "EDIABAS", "BimmerDaten", "PRG files", or reverse-engineering references. Use generic terms: `coding_data/` not `bimmercode_data/`, `dtc_descriptions.db` is ours, UDS knowledge is from ISO 14229

##8. Success Criteria

- [ ] Series picker shows F/G/U/I with year/model guidance, selected series sets protocol
- [ ] DEMO Mode toggle in gear menu — checked → instant connect with mock data (no network)
- [ ] DEMO toggle disabled while connected
- [ ] Interface dropdown hidden when DEMO mode is checked
- [ ] `discover_zgw()` finds a car within 5 seconds or returns None
- [ ] DHCP fallback: if elevation denied → APIPA countdown 20s → "DHCP requires admin rights" if still failing
- [ ] `HSFZConnection.send_uds(addr, payload)` sends and receives correctly
- [ ] `CarWorker` runs on background thread, emits `progress`/`finished`/`error` signals
- [ ] `DtcDatabase.describe("B7F805")` returns English description in <1ms
- [ ] Dark theme applies to QMainWindow, all buttons, labels, and scroll areas
- [ ] QMainWindow opens maximized, shows 4 grayed-out nav buttons before connection
- [ ] Welcome page displays BMW logo, connect button, series picker, 5 instruction bullets
- [ ] Disconnect returns to welcome screen
- [ ] UDS logs at DEBUG level to rotating file (`~/BMW-Tool/logs/`, 5MB × 3 files)
- [ ] `python main.py` launches the window without errors on macOS and Windows
- [ ] `pyinstaller` produces a working `.app` (macOS) and `.exe` (Windows)

##9. Open Questions — ANSWERED

1. **Mock connection for development?** ✅ Uses real car data from user's
   F48 X1 (2018, NBT headunit, ~66,000 km). Stored in `mock_data/f48_x1.json`.
   `MockConnection` class loads this and returns canned UDS responses.
   Enables full UI development without physical car.

2. **Interface auto-detection?** ✅ Dropdown. Users coding their BMW know
   which Ethernet adapter they're using. No guessing.

3. **DHCP fallback: prompt or automatic?** ✅ Automatic after UDP timeout.
   Flow: UDP broadcast → wait 5s → if no response, auto-start DHCP server
   → wait 10s → retry UDP discovery. Show status at each step:
   "Searching for vehicle on [interface]..."
   "No response. Starting DHCP server..."
   "DHCP server running. Searching again..."
   "Connected to BMW F48 X1"