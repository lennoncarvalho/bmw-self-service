# BMW Self Service

Cross-platform desktop app for BMW diagnostics, coding, and service history via ENET cable. Supports F/G/U/I-series vehicles (2011+).

## Requirements

- Python 3.13+
- ENET cable (Ethernet-to-OBD2)
- BMW F-series (2011-2019), G-series (2018+), U-series (2023+), or I-series (2013+)

## Quick start

```bash
# Clone and enter the project
git clone https://github.com/lennoncarvalho/bmw-self-service.git
cd bmw-self-service

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install pyside6==6.12.0 pyinstaller==6.22.3 netifaces==0.11.0 pycryptodome

# Run the app
python main.py
```

## Connecting to your car

1. Plug the ENET cable into your laptop's Ethernet port and the car's OBD2 port
2. Press the Start/Stop button once **without** pressing the brake — this enters ignition/diagnostic mode
3. Launch the app: `python main.py`
4. Select your BMW series from the dropdown
5. Pick your Ethernet adapter from the interface dropdown (e.g. `en7` on macOS)
6. Click **Connect to your BMW**
7. The top bar will show your VIN and model when connected

### DEMO mode

Toggle **Enable DEMO Mode** in the gear menu (top-right) to explore the app without a car. In DEMO mode, the interface dropdown is hidden and connection is instant with mock data from an F48 X1 (2018).

## Project structure

```
bmw-self-service/
├── main.py                     # Entry point, logging setup
├── app/
│   ├── connection.py           # ENET detection, HSFZ, DoIP, DHCP
│   ├── mock_connection.py      # DEMO mode connection
│   ├── uds.py                  # UDS message build/parse (ISO 14229)
│   ├── worker.py               # CarWorker QThread base class
│   ├── dtc_db.py               # DTC description database (88K entries)
│   ├── coding_db.py            # AES decrypt .enc files, query CAFD presets
│   ├── security.py             # Protected ECU registry, seed/key framework
│   └── theme.py                # Dark theme loader
├── ui/
│   ├── main_window.py          # QMainWindow shell, top bar, bottom nav
│   ├── welcome_page.py         # Series picker + connect screen
│   ├── vehicle_page.py         # VIN, model, mileage, battery, ECU list
│   ├── diagnostics_page.py     # DTC read/clear, MIL status, snapshots
│   ├── service_history_page.py # Timeline, add/erase entries
│   ├── coding_page.py          # Easy + Advanced coding, write/backup
│   └── backups_page.py         # Backup list, rollback
├── assets/
│   ├── theme.qss               # Dark QSS theme
│   └── gear.svg                # SVG gear icon
├── coding_data/                # Decrypted .enc CAFD files + .strings
├── mock_data/
│   └── f48_x1.json             # Canned car data for DEMO mode
├── dtc_descriptions.db         # Read-only DTC database (18.9 MB)
├── scripts/
│   └── preflight.sh            # Quality gate: ruff check + format + mypy
└── docs/                       # Protocol specs and research (18 docs)
```

## Before you push

Every push must pass the same three checks CI runs, over the full app code
(`app/`, `ui/`, `main.py`). One command does all of it:

```bash
scripts/preflight.sh          # ruff check + ruff format --check + mypy
scripts/preflight.sh --fix    # apply ruff fixes/formatting, then gate
```

| Gate | Command | Catches |
|------|---------|---------|
| Lint | `ruff check app/ ui/ main.py` | unused imports, import order, bugbear, simplify |
| Format | `ruff format --check app/ ui/ main.py` | formatting |
| Types | `mypy app/ ui/ main.py --ignore-missing-imports` | static type errors |

`ruff check` and `ruff format` are **separate** commands — passing one says
nothing about the other. Do not push with any gate red, and never run the
gate over a subset of the files.

There is no `tests/` directory; the gate is the only automated verification
at this stage.

## Building a standalone app (production)

The PyInstaller command bundles the app into a single executable with all data files embedded.

```bash
# macOS (onedir — proper .app bundle, macOS security compatible)
pyinstaller --onedir --windowed --name "BMW Self Service" \
    --add-data "dtc_descriptions.db:." \
    --add-data "coding_data:coding_data" \
    --add-data "mock_data:mock_data" \
    --add-data "assets/theme.qss:assets" \
    --add-data "assets/gear.svg:assets" \
    --osx-bundle-identifier "com.bmwtool.app" \
    --hidden-import PySide6.QtSvg \
    main.py

# Windows
pyinstaller --onefile --windowed --name "BMW Self Service" \
    --add-data "dtc_descriptions.db;." \
    --add-data "coding_data;coding_data" \
    --add-data "mock_data;mock_data" \
    --add-data "assets/theme.qss;assets" \
    --add-data "assets/gear.svg;assets" \
    --hidden-import PySide6.QtSvg \
    main.py
```

The resulting binary is at:
- **macOS:** `dist/BMW Self Service.app`
- **Windows:** `dist/BMW Self Service.exe`

### Verifying the build

```bash
# Launch the standalone app
open "dist/BMW Self Service.app"           # macOS
.\dist\"BMW Self Service.exe"               # Windows

# In DEMO mode: enable from gear menu, click Connect
# Verify: Vehicle page shows F48 X1, Diagnostics shows 3 DTCs,
#         Service History has 7 entries, Coding has 33 categories
```

## Logs & debugging

```bash
# Normal mode — logs errors only
python main.py

# Verbose mode — logs all UDS traffic, connection steps, and diagnostics
python main.py --debug

# No log file — console only
python main.py --no-log
```

When `--debug` is active, the log file at `~/BMW-Tool/logs/uds.log` records:

- Startup: Python version, platform, available Ethernet interfaces, theme load
- Discovery: broadcast address, timeout, response data (IP, VIN, MAC)
- Connection: TCP connect attempt, HSFZ/DoIP handshake, success/failure reason
- Diagnostics: every UDS request/response in hex with ECU address and length
- Keep-alive: timer start/stop for HSFZ alive-check and UDS TesterPresent
- Disconnect: clean shutdown sequence

The log rotates at 5 MB with 3 backup files. All timestamps are ISO 8601.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Vehicle not found | Ensure ignition is on (press Start/Stop once without brake). Try turning off Wi-Fi. |
| Connection timed out | Check the ENET cable is fully seated. The ZGW takes ~5s to respond. |
| DHCP server requires admin | On macOS/Linux, the DHCP fallback needs `sudo`. Grant it or wait for APIPA auto-config (up to 20s). |
| App won't launch | Verify Python 3.13+ and all pip dependencies are installed. |
| Font warnings at startup | Harmless — macOS doesn't ship `-apple-system` as a named font family. |

## License

This tool is not affiliated with BMW AG. Use at your own risk.