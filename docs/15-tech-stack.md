# Tech Stack

> **App:** BMW Diagnostic Tool  
> **Platforms:** macOS (Apple Silicon + Intel) & Windows (x64)  
> **Interface:** ENET cable (HSFZ for F-series, DoIP for G/U/I-series)  
> **Date:** 2026-10-25  

---

## Stack summary

| Layer | Choice | Version | Notes |
|-------|--------|---------|-------|
| **Language** | Python | 3.13 | Stable, PySide6 support, all packages compatible |
| **GUI** | PySide6 | 6.12.0 | Qt 6.12 LTS, LGPL — free for commercial use |
| **Database** | sqlite3 | (stdlib) | Built-in, read-only mode, no dependencies |
| **Networking** | socket + asyncio | (stdlib) | TCP/UDP, no admin privileges needed |
| **Packaging** | PyInstaller | 6.2.3 | Single `.exe` / `.app`, code signing support |

### Why Python 3.13 over 3.14

Python 3.14 is the latest feature release (Jun 2026), but PySide6 added 3.14 support only recently (PySIDE-3147). The ecosystem still has ~33% of top packages not explicitly declaring 3.14 support. Python 3.13 has years of battle-testing, full PySide6 support since 6.6, and is the safer choice for a cross-platform binary distribution.

Both work — 3.13 today, upgrade to 3.14 when the ecosystem matures.

## Development dependencies

```bash
pip install pyside6==6.12.0
pip install pyinstaller==6.22.3
```

Everything else is stdlib: `socket`, `asyncio`, `sqlite3`, `struct`, `json`, `logging`, `pathlib`.

## Networking: ENET cable connection

BMW's ISTA software uses a **local DHCP server** (`ZGW_SEARCH.exe` / `pd64`)
to assign the ZGW an IP address. This is more reliable than relying on the
car's self-assigned link-local address — especially on G-series vehicles
where the ZGW may not auto-configure APIPA after a sleep cycle.

Our app uses a **two-tier approach**:

1. **APIPA first** (no admin) — try the car's self-assigned 169.254.x.x address
2. **DHCP fallback** (needs admin) — run a local DHCP server on the ENET interface

### Tier 1: APIPA auto-discovery (no privileges)

```python
import socket

def discover_zgw(timeout=5.0) -> tuple[str, int] | None:
    """Find ZGW via UDP broadcast. No admin needed."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)

    # HSFZ discovery broadcast
    sock.sendto(b"\x00\x00\x00\x01", ("169.254.255.255", 6811))

    try:
        data, addr = sock.recvfrom(1024)
        return (addr[0], 6801)  # ZGW IP + HSFZ TCP port
    except socket.timeout:
        return None
```

Works for most F-series cars. If the ZGW responds, connect and proceed — zero
elevation beyond the initial interface IP assignment.

### Tier 2: DHCP server (elevated privileges)

For cars that don't respond to APIPA discovery — common on G-series after
sleep cycles, or when the ZGW needs a fresh lease:

**macOS — built-in `bootpd` (zero dependencies, pre-installed on every Mac):**

```python
import subprocess, plistlib, os

ENET_INTERFACE = "en7"  # detect dynamically at runtime
DHCP_PLIST = "/etc/bootpd.plist"

def start_dhcp_server_macos():
    """Configure and start macOS built-in DHCP server on ENET interface."""
    config = {
        "bootp_enabled": False,
        "dhcp_enabled": [ENET_INTERFACE],
        "reply_threshold_seconds": 0,
        "Subnets": [{
            "name": "BMW ENET",
            "net_address": "169.254.0.0",
            "net_mask": "255.255.0.0",
            "net_range": ["169.254.1.2", "169.254.1.254"],
            "dhcp_router": "169.254.1.1",
            "allocate": True,
            "lease_max": 3600,
        }]
    }
    with open(DHCP_PLIST, "wb") as f:
        plistlib.dump(config, f)
    subprocess.run([
        "sudo", "/bin/launchctl", "load", "-w",
        "/System/Library/LaunchDaemons/bootps.plist"
    ], check=True)

def stop_dhcp_server_macos():
    subprocess.run([
        "sudo", "/bin/launchctl", "unload", "-w",
        "/System/Library/LaunchDaemons/bootps.plist"
    ], check=True)
    if os.path.exists(DHCP_PLIST):
        os.remove(DHCP_PLIST)
```

`bootpd` is Apple's production DHCP server — the same one Internet Sharing
uses. No `pip install` needed. Just a plist file + `launchctl`.

**Windows — pure Python `simple-dhcp-server` (one dependency):**

```
pip install simple-dhcp-server
```

```python
from simple_dhcp_server import DHCPServer

def start_dhcp_server_windows():
    server = DHCPServer(
        interface=find_enet_interface(),   # detect at runtime
        ip_range=("169.254.1.2", "169.254.1.254"),
        subnet_mask="255.255.0.0",
        gateway="169.254.1.1",
        lease_time=3600,
    )
    server.start()  # needs admin on Windows for port 67
    return server
```

Pure Python, no native dependencies, tested on Windows 7+.

### Connection flow

```
App starts
  │
  ├─ Detect ENET interface (USB-Ethernet adapter)
  │
  ├─ Set interface IP to 169.254.1.1/16 (sudo on macOS, netsh on Windows)
  │
  ├─ UDP broadcast discovery on 169.254.255.255:6811
  │    │
  │    ├─ ZGW responds → CONNECTED
  │    │    (most F-series — no admin beyond interface config)
  │    │
  │    └─ No response after 5s
  │         │
  │         └─ Show "Start DHCP Server" button
  │              │
  │              ├─ User approves → elevation prompt
  │              ├─ DHCP server starts → ZGW gets IP from pool
  │              └─ Re-discover → CONNECTED
  │
  └─ TCP connect to ZGW (port 6801 for HSFZ, 13400 for DoIP)
       │
       └─ UDS diagnostics/coding over established TCP channel
```

### Protocol sockets (no privileges needed once connected)

```python
# HSFZ — F-series (TCP 6801)
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
sock.connect((zgw_ip, 6801))

# DoIP — G/U/I-series (TCP 13400)
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((zgw_ip, 13400))
```

All diagnostics run over standard TCP. No raw sockets, no kernel bypass, no admin.

## Binary distribution

### macOS

```bash
pyinstaller \
    --onefile \
    --windowed \
    --name "BMW Diagnostic Tool" \
    --add-data "dtc_descriptions.db:." \
    --add-data "bimmercode_data: bimmercode_data" \
    --osx-bundle-identifier "com.yourapp.bmwtool" \
    --codesign-idenity "Developer ID Application: Your Name" \
    main.py
```

Output: `dist/BMW Diagnostic Tool.app` (single `.app` bundle, ~120-150 MB).

### Windows

```powershell
pyinstaller \
    --onefile \
    --windowed \
    --name "BMW Diagnostic Tool" \
    --add-data "dtc_descriptions.db;." \
    --add-data "bimmercode_data;bimmercode_data" \
    --icon "icon.ico" \
    main.py
```

Output: `dist/BMW Diagnostic Tool.exe` (single `.exe`, ~100-130 MB).

### Size breakdown

| Component | ~Size |
|-----------|-------|
| Python runtime | 25 MB |
| PySide6 Qt libraries | 70 MB |
| Application code | 2 MB |
| dtc_descriptions.db | 19 MB |
| bimmercode_data | 5 MB |
| **Total** | **~120 MB** |

Compressed with UPX or similar: ~50-60 MB download.

## Project structure

```
bmw-tool/
├── main.py                    # Entry point, QApplication, window setup
├── app/
│   ├── __init__.py
│   ├── hsfz.py                # HSFZ protocol (TCP 6801, UDP 6811)
│   ├── doip.py                # DoIP protocol (TCP 13400)
│   ├── network.py             # ENET detection, APIPA discovery, DHCP server
│   ├── uds.py                 # UDS message building/parsing
│   ├── diagnostics.py         # DTC read/clear, sensor values
│   ├── coding.py              # Easy + Advanced coding UI
│   ├── service_history.py     # Read/write maintenance records
│   └── dtc_db.py              # DtcDatabase class (from docs/14)
├── ui/
│   ├── __init__.py
│   ├── main_window.py         # QMainWindow with tabbed modules
│   ├── diagnostics_tab.py      # DTC list, MIL status, sensor view
│   ├── easy_coding_tab.py      # Curated presets, search, apply
│   ├── advanced_coding_tab.py  # SVT tree, FDL editor
│   └── service_history_tab.py  # Maintenance timeline, add/edit
├── assets/
│   ├── dtc_descriptions.db    # 88K DTC entries (committed)
│   └── bimmercode_data/       # Decrypted coding database
├── build_macos.spec           # PyInstaller spec for macOS
├── build_windows.spec          # PyInstaller spec for Windows
└── requirements.txt           # pyside6==6.12.0, pyinstaller==6.22.3
```

## Why Python + PySide6 over alternatives

| Factor | Python + PySide6 | TypeScript + Electron | C++ + Qt |
|--------|--------------------|----------------------|----------|
| **DeepSeek V4 Pro skill** | Excellent | Very Good | Good |
| **Existing protocol code** | Already in Python | Would need port | Would need full rewrite |
| **Single binary** | PyInstaller, mature | Electron-builder, large | Native, smallest |
| **ENET cable access** | Standard sockets | Needs node native addons | QTcpSocket, best |
| **Bundle size** | ~120 MB | ~200+ MB | ~30 MB |
| **UI development** | QT Designer + Python | HTML/CSS/JS | QT Creator + C++ |
| **macOS code signing** | Supported | Supported | Supported |
| **Future iOS/Android?** | PySide6 supports both | Electron doesn't | Qt supports both |

**The protocol code we already wrote is in Python.** Porting HSFZ, DoIP, and UDS to another language would be the single largest source of bugs. Using Python means the protocol layer ships as-is with zero rewrites.

## Constraints accepted

| Constraint | Impact |
|-----------|--------|
| **ENET connection reliability** | Two-tier: APIPA first (no admin), DHCP fallback (needs elevation). Matches how ISTA works. |
| **Cross-platform macOS + Windows** | macOS uses built-in `bootpd`. Windows uses pure Python `simple-dhcp-server`. Both need admin for DHCP. |
| **No admin for routine diagnostics** | Interface config + DHCP setup needs one-time elevation. All subsequent TCP/UDS traffic runs as user. |
| **Offline capable** | Coding database and DTC descriptions embedded in binary. No internet beyond ENET cable needed. |
| **DeepSeek V4 Pro as dev tool** | Python is the model's strongest language. All existing docs reference Python code. |