# Tasks: Infrastructure Layer

> **Historical plan/status:** superseded by [the 2026-10-28 audit](../docs/19-audit-and-readiness.md).
> Checkboxes/merge claims below are not acceptance evidence. Protocol examples
> may be wrong; use [corrections](../docs/20-protocol-evidence.md) and
> [owner decisions](../docs/21-product-decisions.md) before implementing.

> **Phase 3.** From plan `tasks/plan.md`. Spec: `SPEC-INFRASTRUCTURE.md`

---

## Pure functions (no car, no UI)

- [x] **T-1: `app/uds.py`**
  - Build: `build_uds()`, `parse_uds_response()`, `is_negative_response()`, `get_negative_code()`
  - Acceptance: All functions return correct types. `build_uds(0x63, 0x22, bytes([0xF1, 0x90]))` produces valid HSFZ-framed bytes matching `docs/10-hsfz-protocol.md`. `parse_uds_response()` on a `0x7F` response returns `(0x7F, error_bytes)`.
  - Files: `app/uds.py`

- [x] **T-2: `app/dtc_db.py`**
  - Build: `DtcDatabase` class — copy from `docs/14-dtc-database.md`
  - Acceptance: `dtc_db.describe("B7F805")` returns English text. `dtc_db.describe("ZZZZZZ")` returns None. `dtc_db.fault_type("08")` returns "implausible signal or value".
  - Files: `app/dtc_db.py`

- [x] **T-3: `assets/theme.qss` + `app/theme.py`**
  - Build: Dark theme QSS (background `#1a1a2e`, BMW blue `#1C69D4`, red `#E30B1F`). `load_theme()` and `apply_theme()` functions.
  - Acceptance: QSS file has rules for QMainWindow, QPushButton (normal/hover/disabled), QLabel, QScrollArea. No inline styles needed. `apply_theme()` works without errors.
  - Verify: Visual — apply to a minimal QApplication, confirm dark background and blue buttons
  - Files: `assets/theme.qss`, `app/theme.py`

## Networking (mock first, then real)

- [x] **T-4: `app/connection.py` — interface detection**
  - Build: `list_interfaces()` using `netifaces`. `discover_zgw()`.
  - Acceptance: `list_interfaces()` returns all Ethernet adapter names (en0-en9 on macOS, Ethernet on Windows). No fragile shell parsing.
  - Verify: Run on macOS — prints interface list from netifaces
  - Files: `app/connection.py`

- [x] **T-5: `app/connection.py` — HSFZ transport**
  - Build: `HSFZConnection` class. `connect()`, `send_uds()`, `disconnect()`.
  - Acceptance: TCP connect to port 6801. `send_uds()` builds UDS via `app.uds.build_uds()`, sends over TCP, reads response, returns payload bytes. Timeout after 30s raises `TimeoutError`.
  - Verify: Unit test with mock socket (no real car needed for transport layer test)
  - Files: `app/connection.py`

- [x] **T-6: `app/connection.py` — DoIP transport + DHCP**
  - Build: `DoIPConnection` class (same interface as HSFZConnection). `start_dhcp_server()` / `stop_dhcp_server()` — macOS bootpd, Windows simple-dhcp-server.
  - Acceptance: DoIP connects to port 13400. DHCP configures and starts on the selected interface.
  - Verify: Manual — `start_dhcp_server("en7")` prints "DHCP server started" (check with `launchctl list` on macOS)
  - Files: `app/connection.py`

- [x] **T-7: `app/mock_connection.py`**
  - Build: `MockConnection` — same interface as `HSFZConnection`. Loads `mock_data/f48_x1.json`. Routes UDS requests to canned responses.
  - Acceptance: `send_uds(0x63, bytes([0x22, 0xF1, 0x90]))` returns VIN bytes. `send_uds(0x63, bytes([0x19, 0x02, 0x08]))` returns DTC data. Unknown requests return `0x7F 0x22 0x11`.
  - Verify: `python -c "from app.mock_connection import MockConnection; ..."` — prints VIN, DTCs
  - Files: `app/mock_connection.py`

- [x] **T-8: `app/worker.py`**
  - Build: `CarWorker(QThread)` base class. Emits `started`, `progress(str)`, `finished(object)`, `error(str)`.
  - Acceptance: Subclass can override `do_work()`. Signals fire in correct order.
  - Verify: Subclass `TestWorker` that sleeps 1s then returns "done". Connect signals to print.
  - Files: `app/worker.py`

## UI shell

- [x] **T-9: `ui/welcome_page.py`**
  - Build: `WelcomePage(QWidget)`. BMW logo, series picker dropdown (F/G/U/I with year/model labels), interface dropdown (hidden when DEMO mode on), "Connect to your BMW" button, 5 instruction bullets, 4 gray nav buttons.
  - Series picker: F → HSFZ, G/U/I → DoIP. Button disabled until series selected + (interface selected OR DEMO mode on).
  - Interface dropdown: populated by `connection.list_interfaces()`, filtered to Ethernet adapters only. Hidden entirely when DEMO mode is checked in main window.
  - Acceptance: Matches Screen 1 from `docs/16-ui-spec.md`. Connect button enables only when choices are valid. Emits `connect_clicked(series, interface)`.
  - Verify: Visual — launch standalone, toggle DEMO mode, confirm dropdown show/hide
  - Files: `ui/welcome_page.py`

- [x] **T-10: `ui/main_window.py` — shell + DEMO mode**
  - Build: `MainWindow(QMainWindow)`. Top bar (status dot, model label, VIN label, gear button), QStackedWidget, bottom nav (4 QPushButtons in QButtonGroup), spinner overlay.
  - Gear menu items: Enable DEMO Mode (checkable), Backups, About, Disconnect, Exit.
  - DEMO Mode: toggled via gear menu. When checked, `connect_clicked` uses `MockConnection` instead of `HSFZConnection`. Top bar shows orange dot + "[DEMO]" prefix when active.
  - Acceptance: Window opens with dark theme. DEMO Mode unchecked by default. Toggle on → gear menu shows checkmark. Toggle off → unchecks.
  - Verify: Visual — launch window, open gear menu, toggle DEMO Mode, confirm checkmark
  - Files: `ui/main_window.py`

- [x] **T-11: `ui/main_window.py` — connect flow**
  - Build: Wire WelcomePage connect signal → connection logic. If DEMO Mode on → instantiate MockConnection. If off → HSFZConnection with interface from dropdown. Show spinner during connection. On success: populate top bar (VIN, model), enable nav buttons, switch to Vehicle page (placeholder). On failure: show error, stay on welcome page.
  - Top bar indicator: 🟢 green = real car connected, 🟠 orange = DEMO Mode, 🔴 red = disconnected/error. Orange dot shows "[DEMO]" label in top bar.
  - Acceptance: DEMO Mode on → connect → top bar shows "🟠 [DEMO] F48 X1 sDrive20i X-line". DEMO Mode off → connect with real car (fails gracefully if no car).
  - Verify: `python main.py` — toggle DEMO in gear menu, connect, confirm orange dot + [DEMO] label
  - Files: `ui/main_window.py`, `main.py`

- [x] **T-12: `main.py`**
  - Build: Entry point. `QApplication`, `apply_theme()`, `MainWindow`, `app.exec()`.
  - Acceptance: `python main.py` launches window. Dark theme applies. Window title "BMW Diagnostic Tool".
  - Verify: Visual — launch on macOS and (if available) Windows
  - Files: `main.py`

## Parallel vs sequential

```
T-1 ─┬─ (parallel)
T-2 ─┤
T-3 ─┘
      │
T-4 → T-5 → T-6 → T-7 ─┬─ (parallel, T-7 needs MockConnection
                    T-8 ─┘  but can be built in parallel with T-5/T-6)
                           │
                      T-9 → T-10 → T-11 → T-12
```

T-1, T-2, T-3 can be built simultaneously. T-7 and T-8 can be built in parallel
after T-5 (they only need the interface, not the implementation). T-9 through
T-12 are strictly sequential.