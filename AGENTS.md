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
4. **Run the quality gate** — `scripts/preflight.sh` must be green (see below).
5. **Commit** with descriptive messages referencing the spec doc.

All 16 specification docs are authoritative. If a doc and your understanding
conflict, the doc wins. If the doc is unclear, ask before coding.

### Gating rules

| Change size | Pipeline |
|-------------|----------|
| > 3 files OR new module OR architecture change | SPEC → PLAN → IMPLEMENT → VERIFY → GATE |
| 1-3 files, clear intent, no new deps | Brief plan → implement → verify → GATE |
| Typo/comment/formatting | Just fix it → GATE |

---

## Quality gate — mandatory before every push

**No push leaves this machine without a green `ruff` and `mypy` run over the
full app code.** CI runs exactly these three commands; skipping them locally
does not make the failure go away, it only moves it to GitHub and burns a
review cycle.

```bash
scripts/preflight.sh          # all three gates, mirrors CI exactly
scripts/preflight.sh --fix    # apply ruff fixes + formatting first, then gate
```

The gates, always over `app/`, `ui/` and `main.py` — never a subset:

| # | Command | Catches |
|---|---------|---------|
| 1 | `ruff check app/ ui/ main.py` | pycodestyle, pyflakes, isort, bugbear, comprehensions, pyupgrade, simplify |
| 2 | `ruff format --check app/ ui/ main.py` | formatting |
| 3 | `mypy app/ ui/ main.py --ignore-missing-imports` | static type errors |

### `ruff check` is not `ruff format`

Two separate commands; a green run of one proves nothing about the other.
Lint passing does **not** mean formatting passes, and formatting passing does
**not** mean types pass. All three must be green before a push. Reporting
"lint is clean" without having run `ruff format --check` and `mypy` is wrong.

### Tooling on this machine

- `ruff` is not installed globally — use `.venv/bin/ruff` or `pipx run ruff`.
- `mypy` lives in the project venv — `.venv/bin/python3 -m mypy app/ ui/ main.py`.
- `python` is not a command; use `python3`.
- `scripts/preflight.sh` resolves all of the above, so prefer it over
  retyping commands by hand.

### Fixing gate failures

- **`ruff check`** — apply only fixes that cannot change behaviour. Never
  silence a rule that is hiding a real defect.
- **`ruff format`** — run `ruff format`; the resulting diff is cosmetic.
- **`mypy`** — fix the type properly: add a `None` guard, an explicit local
  annotation, or a `cast`. Reserve `# type: ignore[...]` for cases where the
  third-party stub is genuinely wrong, and always name the error code.
- **Re-run all three gates after every fix** — fixing one can break another.

### Never

- Push with any gate red, even when the failure looks pre-existing.
- Run the gate over a subset (e.g. only the file you touched).
- Assume a green gate means the change is correct — the gate proves it
  compiles, imports and type-checks, not that the vehicle logic is right.
- Recreate a `tests/` directory or point any tool at one; it does not exist
  and is not wanted at this stage.

---

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

Automated tests are **not needed at this stage**.  All protocol code
requires a physical ENET cable and a real car.  UI verification is
visual against `docs/16-ui-spec.md`.  Pure functions (UDS framing,
DTC normalisation, VIN parsing) are exercised indirectly through the
app's real-car and DEMO-mode flows.  When the communication layer
stabilises across more vehicle variants, a focused test suite for
the pure-function modules may be reintroduced.

The quality gate above (`ruff check`, `ruff format --check`, `mypy`) is
therefore the **only** automated verification required before a push.
There is no `tests/` directory — do not recreate one, and do not add
`tests/` to any command or CI path.

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