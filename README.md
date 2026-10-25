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
source .venv/bin/activate

# Install dependencies
pip install pyside6==6.12.0 pyinstaller==6.22.3 netifaces==0.11.0

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

Toggle **Enable DEMO Mode** in the gear menu (top-right) to explore the app without a car. In DEMO mode, the interface dropdown is hidden and connection is instant with mock data.

## Project structure

```
bmw-tool/
├── main.py                     # Entry point
├── app/
│   ├── uds.py                  # UDS message build/parse (ISO 14229)
│   ├── connection.py           # ENET detection, HSFZ, DoIP, DHCP
│   ├── mock_connection.py      # DEMO mode connection
│   ├── worker.py               # CarWorker QThread base class
│   ├── dtc_db.py               # DTC description database (88K entries)
│   └── theme.py                # Dark theme loader
├── ui/
│   ├── welcome_page.py         # Series picker + connect screen
│   └── main_window.py          # QMainWindow shell
├── assets/
│   ├── theme.qss               # Dark QSS theme
│   └── dtc_descriptions.db     # Read-only DTC database
├── mock_data/
│   └── f48_x1.json             # Canned car data for DEMO mode
├── tests/                      # pytest unit tests
└── docs/                       # Protocol specs and research
```

## Running tests

```bash
pytest tests/ -v
```

## Building a standalone app

```bash
# macOS
pyinstaller --onefile --windowed --name "BMW Self Service" \
    --add-data "assets/dtc_descriptions.db:assets" \
    --add-data "assets/theme.qss:assets" \
    --add-data "coding_data:coding_data" \
    --add-data "mock_data:mock_data" \
    main.py

# Windows
pyinstaller --onefile --windowed --name "BMW Self Service" \
    --add-data "assets/dtc_descriptions.db;assets" \
    --add-data "assets/theme.qss;assets" \
    --add-data "coding_data;coding_data" \
    --add-data "mock_data;mock_data" \
    main.py
```

## Logs

UDS diagnostic messages are logged to `~/BMW-Tool/logs/uds.log` (5 MB rotating files, 3 backups).

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