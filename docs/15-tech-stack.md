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

## Networking: how the ENET cable works in Python

The ENET cable presents as a standard Ethernet interface. No special drivers, no kernel modules, no admin privileges for the actual diagnostics.

### Interface setup (one-time per session)

**macOS:**
```bash
# ENET cable via USB-Ethernet adapter appears as enX
sudo ifconfig en7 inet 169.254.1.1 netmask 255.255.0.0
```
One `sudo` to assign the auto-IP address. After that, all TCP/UDP communication runs as the appuser.

**Windows:**
```powershell
# ENET cable appears as a new Ethernet adapter
netsh interface ip set address "Ethernet 2" static 169.254.1.1 255.255.0.0
```
Requires admin for interface config. Could be automated or done manually by the user once.

### Protocol sockets (no privileges needed)

```python
import socket

# HSFZ — F-series vehicles (BMW's proprietary TCP protocol)
tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tcp_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
tcp_sock.settimeout(5.0)
tcp_sock.connect(("169.254.1.2", 6801))   # ZGW is always .1.2

# HSFZ discovery — UDP broadcast to find the ZGW
udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
udp_sock.sendto(b"\x00\x00\x00\x01", ("169.254.255.255", 6811))

# DoIP — G/U/I-series vehicles (ISO 13400 standard)
doip_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
doip_sock.connect(("169.254.1.2", 13400))   # DoIP gateway
```

No raw sockets, no packet injection, no admin. Just standard TCP/UDP — same as a web browser.

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
| **No admin/root for diagnostics** | TCP/UDP on user ports — satisfied. Only initial interface config may need sudo (one-time). |
| **Cross-platform macOS + Windows** | Python `socket`, PySide6, and PyInstaller all work on both. |
| **ENET cable auto-detection** | UDP broadcast on 169.254.255.255:6811 discovers the ZGW. If no response, fall back to known addresses. |
| **Offline capable** | Entire coding database and DTC descriptions are embedded in the binary. No network beyond the ENET cable needed. |
| **DeepSeek V4 Pro as dev tool** | Python is the model's strongest language. All existing docs reference Python code. |