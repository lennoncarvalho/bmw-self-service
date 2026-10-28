# Plan: Infrastructure Layer

> **Historical plan/status:** superseded by [the 2026-10-28 audit](../docs/19-audit-and-readiness.md).
> Checkboxes/merge claims below are not acceptance evidence. Protocol examples
> may be wrong; use [corrections](../docs/20-protocol-evidence.md) and
> [owner decisions](../docs/21-product-decisions.md) before implementing.

> **Phase 2.** Reviewed by human before task breakdown.
> Spec: `SPEC-INFRASTRUCTURE.md` | Capability Map: `CAPABILITY-MAP.md`

---

## Components

| # | Component | File(s) | Depends on |
|---|-----------|---------|------------|
| C1 | UDS message layer | `app/uds.py` | — (pure functions) |
| C2 | DTC database singleton | `app/dtc_db.py` | — (reads `dtc_descriptions.db`) |
| C3 | Theme loader | `app/theme.py`, `assets/theme.qss` | — |
| C4 | ENET connection | `app/connection.py` | C1 (UDS framing) |
| C5 | Mock connection | `app/mock_connection.py` | C4 (same interface) |
| C6 | CarWorker threads | `app/worker.py` | C4 (send_uds) |
| C7 | Welcome page | `ui/welcome_page.py` | C3 (theme) |
| C8 | Main window shell | `ui/main_window.py` | C3, C7 (theme, welcome page) |
| C9 | Entry point | `main.py` | C8 (main window) |

## Build order

```
Pure functions          Networking            UI shell
C1 ─┐                   C4 ─┐                C7 ─┐
C2 ─┤  no car needed    C5 ─┤  mock first    C8 ─┤  wires all
C3 ─┘                   C6 ─┘                C9 ─┘
```

C1, C2, C3 are independent — can be built in any order or parallel.
C4 needs C1 (uses `build_uds()` for framing). C5 implements C4's interface.
C6 needs C4 (wraps `send_uds()` in QThread). C7, C8 need C3.
C9 needs C8.

## What each component delivers

### C1 — UDS message layer (`app/uds.py`)
```python
build_uds(ecu_addr: int, service: int, payload: bytes) -> bytes
parse_uds_response(data: bytes) -> tuple[int, bytes]  # (service|0x40, payload) or raises
is_negative_response(data: bytes) -> bool
get_negative_code(data: bytes) -> int
```
Pure functions. No network I/O. Unit-testable.

### C2 — DTC database (`app/dtc_db.py`)
```python
class DtcDatabase:
    def __init__(self, db_path: str)
    def describe(self, code: str) -> str | None
    def describe_with_ecu(self, code: str) -> tuple[str, str] | None
    def fault_type(self, type_code: str) -> str | None
```
Copy from `docs/14-dtc-database.md`. Read-only SQLite, singleton.

### C3 — Theme (`app/theme.py` + `assets/theme.qss`)
```python
def load_theme() -> str          # reads theme.qss, returns stylesheet
def apply_theme(app: QApplication)
```
Dark theme with BMW M colors. One QSS file. Color constants for Python code.

### C4 — ENET connection (`app/connection.py`)
```python
def list_interfaces() -> list[str]                                # en0, en7, eth0...
def discover_zgw(interface: str, timeout: float = 5.0) -> str | None  # returns IP
def start_dhcp_server(interface: str)                              # macOS bootpd or Windows simple-dhcp-server
def stop_dhcp_server()

class HSFZConnection:
    def __init__(self, host: str, port: int = 6801)
    def connect() -> bool
    def send_uds(ecu_addr: int, payload: bytes, timeout: float = 30.0) -> bytes
    def disconnect()

class DoIPConnection:
    def __init__(self, host: str, port: int = 13400)
    def connect() -> bool
    def send_uds(ecu_addr: int, payload: bytes, timeout: float = 30.0) -> bytes
    def disconnect()
```
HSFZ and DoIP share the same `send_uds()` signature — feature code doesn't
care which transport is active.

### C5 — Mock connection (`app/mock_connection.py`)
```python
class MockConnection:
    """Implements same interface as HSFZConnection but returns data from mock_data/f48_x1.json."""
    def connect() -> bool
    def send_uds(ecu_addr: int, payload: bytes, timeout: float = 30.0) -> bytes
    def disconnect()
```
Loads `mock_data/f48_x1.json` at init. Routes UDS requests:
- `0x22 0xF1 0x90` → VIN bytes
- `0x19 0x02 0x08` → canned DTC response
- Unknown requests → generic negative response
Used for all UI development. Swap `MockConnection` → `HSFZConnection` for real car.

### C6 — CarWorker threads (`app/worker.py`)
```python
class CarWorker(QThread):
    started = Signal()
    progress = Signal(str)      # "Reading fault codes from DME..."
    finished = Signal(object)   # result data
    error = Signal(str)         # user-friendly error message

    def __init__(self, connection):
        self.connection = connection

    def run(self):
        # Template: emit started, call do_work(), emit finished or error
        # Subclass and override do_work()
```
```
Subclasses: `DtcReadWorker`, `DtcClearWorker`, `VinReadWorker`, `SvtReadWorker`, etc.
These aren't built here — just the base class. Subclasses come with feature sections.

### C7 — Welcome page (`ui/welcome_page.py`)
```python
class WelcomePage(QWidget):
    connect_clicked = Signal(str, str)   # emits (series: "F"/"G"/"U"/"I", interface: str)

    def __init__(self):
        # BMW logo (label with large font/emoji)
        # Series picker: dropdown with F/G/U/I + descriptive labels
        #   "F-series (2011-2019): 1-7 Series, X1-X6, M2-M6"
        #   "G-series (2018+): 1-8 Series, X1-X7, M2-M8"
        #   "U-series (2023+): XM, iX, U11 X1"
        #   "I-series (2013+): i3, i4, i5, i7, iX1, iX3"
        # Interface dropdown (hidden when DEMO mode on)
        # "Connect to your BMW" button
        # 5 instruction bullets
        # 4 grayed-out nav buttons at bottom
```
Series choice determines protocol: F → HSFZ on port 6801, G/U/I → DoIP on port 13400.

### C8 — Main window (`ui/main_window.py`)
```python
class MainWindow(QMainWindow):
    def __init__(self):
        # Top bar: status dot, model, VIN, gear menu
        # QStackedWidget for page switching
        # Bottom nav: QButtonGroup + 4 QPushButtons
        # Spinner overlay widget (centered, semi-transparent)
        # Load theme

    def show_spinner(self, message: str)
    def hide_spinner(self)
    def set_connected(self, vin: str, model: str)
    def set_disconnected(self)
```
Top bar updates on connect. Nav buttons enable/disable. Spinner blocks input.

### C9 — Entry point (`main.py`)
```python
def main():
    app = QApplication(sys.argv)
    apply_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
```
~15 lines. Wires everything together.

## Risks & mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| HSFZ byte-level errors | Car won't connect | Build and test with MockConnection first. Validate against `docs/10-hsfz-protocol.md`. Real-car test last. |
| DHCP server needs sudo | Can't auto-start on some setups | Detect permission failure, fall back to manual instructions in UI |
| QThread bugs (deadlocks, segfaults) | App crashes | Unit test signals/slots. Keep thread code minimal — just I/O. |
| Cross-platform interface detection | Different OS APIs | `list_interfaces()` uses `netifaces` or platform-specific shell commands |
| macOS code signing for DHCP | PyInstaller bundle rejected | Sign the bundled app. DHCP elevation uses `osascript` for clean UX |

## Verification checkpoints

After each component: `python main.py` must launch without import errors.
After C4: `python -c "from app.connection import discover_zgw; print(discover_zgw('en0'))"` returns None (no car) without crashing.
After C5: `python -c "from app.mock_connection import MockConnection; m = MockConnection(); print(m.send_uds(0x63, bytes([0x22, 0xF1, 0x90])))"` prints VIN bytes.
After C8: Window opens with dark theme, 4 gray nav buttons, spinner overlay works.
After C9: Full connect flow works with MockConnection — VIN appears in top bar, nav activates.