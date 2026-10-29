# BMW Self Service

Cross-platform Python desktop app under development for BMW diagnostics, coding,
and service history over ENET. F/G/U/I coverage is a goal, not a verified
compatibility claim.

**Current status:** PRs #8/#9 are merged. The retained owner session confirms
HSFZ connection/session/VIN, but optional reads failed and DTC coverage was
gateway-only ([diagnosis](docs/23-first-vehicle-session.md)). Live coding remains
unavailable; writes and rollback are not production validated.
Next development is split into [library migration](tasks/protocol-library-migration.md)
and [REA feature recovery](tasks/rea-protocol-recovery.md), with separate specs.
Local JSON/cards, a separate history-operation journal and mode-specific workers
for ADD-only append or explicit erase-and-replace are implemented; physical
validation remains pending. Vehicle history reading is retired. See
[the workflow](docs/28-service-history-workflow.md) and
[the implementation](tasks/task-b-history-write-implementation.md).
Use [the session handoff](SESSION-PROMPT.md) and [source guide](docs/27-rea-source-guide.md).
Start with [the documentation index](docs/README.md),
[readiness audit](docs/19-audit-and-readiness.md) and
[owner decisions](docs/21-product-decisions.md).

Project skills live in [`.agents/`](.agents/README.md); they are development
resources and are not shipped with the application.

## Requirements

- Python 3.13 (declared CI/tooling target; the current local venv differs)
- ENET cable (Ethernet-to-OBD2)
- An ENET-capable BMW with an evidenced transport/ECU contract. First physical
  validation target: owner’s F48 X1, model year 2018, NBT. Year alone does not
  establish compatibility; E-series remains outside the current transport scope.

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
python3 -m pip install -r requirements.txt

# Run the app
python3 main.py
```

## Connecting to your car

1. Plug the ENET cable into your laptop's Ethernet port and the car's OBD2 port
2. Put the vehicle in the ignition/diagnostic state appropriate to its model;
   the previous universal button sequence has not been validated across models
3. For vehicle validation, launch: `.venv/bin/python3 main.py --debug --read-only`
4. Select your BMW series from the dropdown
5. Pick your Ethernet adapter from the interface dropdown (e.g. `en7` on macOS)
6. Click **Connect to your BMW**
7. The top bar will show your VIN and model when connected

> This is the existing UI flow, not a validated connection procedure. Capture
> fresh debug logs for the next read-only validation. Do not use real-car
> coding actions before their baseline/restore gates are met, or history actions
> before the mode/journal/result gates in [workflow28](docs/28-service-history-workflow.md)
> are implemented and reviewed. History reading is no longer a prerequisite.

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
└── docs/                       # Specifications, research, evidence and handoff guides
```

## Before you push

Every push must pass the three static checks included in CI, over the full app code
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

There is no automated test suite under the current project policy. The three
local gates do not prove correct vehicle behavior. CI also runs `pip-audit`;
that security check is not included in `scripts/preflight.sh`.

## Building a standalone app (unverified examples)

These commands describe intended packaging. Neither platform’s release build
is validated. See [stack and packaging status](docs/15-tech-stack.md).

```bash
# macOS (onedir — proper .app bundle, macOS security compatible)
pyinstaller --onedir --windowed --name "BMW Self Service" \
    --add-data "dtc_descriptions.db:." \
    --add-data "coding_data:coding_data" \
    --add-data "mock_data:mock_data" \
    --add-data "assets/theme.qss:assets" \
    --add-data "assets/gear.svg:assets" \
    --add-data "licenses:licenses" \
    --add-data "THIRD_PARTY_NOTICES.md:." \
    --collect-submodules udsoncan.services \
    --hidden-import scapy.contrib.automotive.bmw.hsfz \
    --hidden-import doipclient.messages \
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
    --add-data "licenses;licenses" \
    --add-data "THIRD_PARTY_NOTICES.md;." \
    --collect-submodules udsoncan.services \
    --hidden-import scapy.contrib.automotive.bmw.hsfz \
    --hidden-import doipclient.messages \
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
# Read-only vehicle validation, including detailed persistent logs
.venv/bin/python3 main.py --debug --read-only

# Normal mode (persistent log contains warnings/errors)
.venv/bin/python3 main.py

# Console only; do not use for vehicle validation
.venv/bin/python3 main.py --no-log
```

Each launch without `--no-log` creates
`~/BMW-Tool/logs/session-<UTC timestamp>-<PID>.log`.
With --debug it captures raw discovery/HSFZ/DoIP bytes (including ACKs and partial
reads), request/connection IDs, deadlines, endpoints, workers, page navigation,
Qt warnings and Python exceptions. Preserve the session and matching rotated
segments (.1 through .5); segments are 10 MiB. Earlier sessions are not overwritten.
The [validation guide](docs/22-read-only-validation.md) defines per-page limits.

## Troubleshooting and next validation

Confirm the wired link, selected adapter’s IPv4/netmask and route, then collect
fresh `--debug` logs. Distinguish discovery failure, TCP failure, routing
activation, UDS response correlation and optional-data failures. The current
old `uds.log` was empty during the initial audit. A newer session and preserved
local copy are now indexed in doc 23; retain new logs before retry/rotation.

Do not force a particular host IP, disable unrelated networking, start DHCP or
run the entire GUI as root based on the older troubleshooting table. Network
fallback and cross-platform privilege handling need review. See
[protocol corrections](docs/20-protocol-evidence.md).

## Project and data licensing

This project is not affiliated with BMW AG. A release license and redistribution
rights for extracted data have not been established by this audit. Development
skill provenance is recorded separately in `.agents/README.md`.
