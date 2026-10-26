# BMW Self Service — AGENTS.md

> OpenCode project configuration. Read automatically at session start.
> Compatible with OpenCode, Claude Code, and Codex.

---

## Project identity

**BMW Self Service** — cross-platform desktop app for BMW diagnostics,
coding, and service history via ENET cable (F/G/U/I-series, 2011+).

- **Language:** Python 3.13
- **GUI:** PySide6 6.12 (Qt Widgets + QSS, no QML)
- **Packaging:** PyInstaller 6.22 → single `.app` / `.exe`
- **Database:** SQLite 3 (read-only `dtc_descriptions.db`, 88K entries)
- **Networking:** TCP/UDP sockets + optional local DHCP server
- **Platforms:** macOS (Apple Silicon + Intel) and Windows (x64)

## Repository structure

```
docs/                       # All specifications (read-first before coding)
  01-05                     # Protocol research, UDS, DoIP, HSFZ
  06                       # Coding database extraction
  07                       # Vehicle identification flow
  08                       # Encryption key
  10                       # HSFZ protocol spec (Python implementation)
  11                       # Curated coding database format
  12                       # Service history wire format
  13                       # App architecture
  14                       # DTC database integration guide
  15                       # Tech stack (versions, networking, DHCP, binary distribution)
  16                       # UI/UX specification (all screens, states, flows)
  17                       # UI development decisions (10 rules to simplify coding)
extract_dtc.py              # DTC extraction script (one-time, already run)
translate_ollama.py         # DTC translation script (one-time, already run)
dtc_descriptions.db         # 88K DTC entries, German + English (static asset)
coding_data/                # Vehicle coding database (CAFD files, strings, ECU metadata)
BimmerDaten/decoderPrg.py   # PRG file parser (reference only, not used by app)
```

## Development workflow — spec-driven

This project follows spec-first development. Before writing any code:

1. **Read the relevant spec** from `docs/` — every protocol, UI screen, and
   data flow is documented.
2. **Plan the implementation** — list files to create/modify, order of work.
3. **Implement one module at a time** — verify against the spec before moving on.
4. **Commit** with descriptive messages referencing the spec doc.

All 16 specification docs are authoritative. If a doc and your understanding
conflict, the doc wins. If the doc is unclear, ask before coding.

### Gating rules

| Change size | Pipeline |
|-------------|----------|
| > 3 files OR new module OR architecture change | SPEC → PLAN → IMPLEMENT → VERIFY |
| 1-3 files, clear intent, no new deps | Brief plan → implement → verify |
| Typo/comment/formatting | Just fix it |

## Skills to load

When starting a development session, load these skills in order:

### Always load (every session)
1. **`spec-driven-development`** — structured spec → plan → implement → verify workflow

### Load by task

| Task | Skill | Why |
|------|-------|-----|
| **PySide6 code review** | `pyside6-reviewer` | Thread safety, signal/slot, Qt 6.8+ idioms, anti-pattern detection |
| **SQLite queries/schema** | `sqlite` | Prepared statements, WAL mode, indexing, Python sqlite3 patterns |
| **Protocol/debugging** | REA tools (`rea.*`) | Inspect original APKs and PRG files to resolve protocol gaps during implementation |
| **Session management** | `opencode` | Subagents, worktrees, parallel work |

## Coding conventions

### Python style
- Type hints on all function signatures (`def foo(x: int) -> str:`)
- Docstrings on public methods (Google style)
- 4-space indentation, 100-char line limit
- snake_case for functions/variables, PascalCase for classes
- All car I/O on background threads (QThread subclasses, never block the UI)
- **No external tool names in code or shipped assets.** The app is standalone.
  No mentions of BimmerCode, BimmerLink, ISTA, EDIABAS, BimmerDaten, or any
  reverse-engineering source. Use generic names: `coding_data/`, `vehicle
  coding database`, `diagnostic descriptions`. The `docs/` folder is internal
  research — it is NOT shipped with the app.

### PySide6 patterns
- **No QML.** Qt Widgets only, styled with QSS.
- **No QListView/QAbstractItemModel.** Use `QScrollArea` + `QVBoxLayout` + widget children for all lists.
- **No multi-window.** Single `QMainWindow` + `QStackedWidget` for page switching.
- **No asyncio + Qt mixing.** Use `QThread` + signals for async operations.
- **One `CarWorker(QThread)` base class** for all car I/O. Subclass per operation type.
- **QSS in one file:** `assets/theme.qss`, loaded once at startup.
- **QSettings** for all persistence. No manual config file I/O.
- **Inline expand/collapse** for detail views. No sub-page navigation.
- **QDialog** for forms (add service entry, write confirmation).

### SQLite patterns
- Read-only connection: `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)`
- Always use parameterized queries. Never string formatting for SQL.
- `DtcDatabase` is a singleton. Load once at startup, reuse everywhere.

### Error handling
- Every car operation has a 30-second timeout.
- Timeouts produce user-friendly messages (see error matrix in `docs/16-ui-spec.md`).
- Never show raw exceptions to the user.
- Log all UDS messages at DEBUG level for troubleshooting.

## Testing policy

- **No tests for protocol code** — requires physical ENET cable + car. Manual testing only.
- **No tests for UI code** — visual verification against `docs/16-ui-spec.md`.
- **Unit tests for pure functions:** DTC code normalization, VIN parsing, coding data decode/encode.
- Test runner: `pytest` (if tests exist).

## Build & packaging

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

## Key constraints

- **No admin/root for diagnostics.** Only initial ENET interface config + DHCP server need elevation.
- **Offline capable.** All databases embedded in the binary. No internet beyond ENET cable.
- **ENET cable only.** No Bluetooth, no WiFi OBD adapters, no K+DCAN.
- **F/G/U/I-series only (2011+).** No E-series.
- **117 of 139 ECUs are codable without SecurityAccess.** The 22 blocked ECUs are safety-critical (airbags, engine ECU, cameras).

## GitHub CLI (pushing to this repo)

This machine has two GitHub accounts: `lennoncarvalho` (personal, for this repo)
and `lcarvalho-tns` (work, for other repos). This repo must always use
`lennoncarvalho`.

- **Before any `git push` or `gh pr` command**, switch to the personal account:
  `gh auth switch --user lennoncarvalho`
- **Never** run `gh auth switch` to `lcarvalho-tns` while working in this repo.
- **Never** modify `~/.config/gh/` (the shared default config).
- The repo-local `user.name` is `Lennon Carvalho` and `user.email` is
  set from the personal account.