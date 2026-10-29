# BMW Self Service — AGENTS.md

> Repository instructions for development and review.
> Compatible with OpenCode, Claude Code, and Codex.

---

## Read first

1. Load `.agents/skills/spec-driven-development/SKILL.md`.
2. Read `docs/README.md` for document status, then `docs/19-audit-and-readiness.md`.
3. Read `docs/20-protocol-evidence.md` before transport/UDS changes and
   `docs/21-product-decisions.md` before changing behavior.
4. Load applicable skills from `.agents/skills/`; provenance and setup are in
   `.agents/README.md`. Skills installed in the repo are available next turn;
   their instructions can be read directly now.
5. Development handoff is `SESSION-PROMPT.md`: Task A is library migration
   (`tasks/protocol-library-migration.md`, spec 25); Task B is REA feature
   recovery (`tasks/rea-protocol-recovery.md`, spec 26). Source/tool/evidence
   routing is `docs/27-rea-source-guide.md`. REA is now connected; earlier
   missing-engine observations are historical. Do not repeat setup blindly.

The 2026-10-29 owner interview (docs 21/26, D-21–D-49) supersedes older
conflicting behavior requirements, including universal immediate readback.
Current milestone: functional personal Mac Python-source use; packages/signing
and Windows validation are later. D-29 uses contract-specific application/cycle
completion, D-28/D-30 forbid write Cancel and block disruptive app actions, and
D-39 removes history odometer validation.

The 2026-10-28 audit overrides older completion labels and contradictory protocol
examples. Historical REA notes are evidence candidates, not authoritative wire
contracts. Correct a disproven spec before implementing it; ask the owner about
product decisions that remain unclear. Do not infer vehicle support from year
or chassis letter alone. The first retained session establishes HSFZ/VIN on the
owner's setup, with failed optional reads and incomplete DTC coverage; see
`docs/23-first-vehicle-session.md` and `tasks/rea-protocol-recovery.md`.

## Fundamental implementation rule — source recovery

The owner reaffirmed on 2026-10-29 that this project reconstructs behavior from
software in `sources/` using REA. Recover and reuse the classes, encrypted and
decrypted data, databases, request engines and variant selection paths; do not
replace that investigation with guessed constants or an F48-only implementation.
Aim for the full F/G/U/I ENET coverage represented by the supplied artifacts.
Trace each enabled branch to the exact artifact and decoder. Source breadth is
not a claim that every BMW/ECU/software combination has been physically tested.
Proceed unattended through implementation, independent review, corrections,
verification and a PR; unresolved facts are research work, not owner questions.

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

Approved product decisions define required behavior. Reproducible protocol
evidence defines byte-level behavior. `docs/README.md` records the status of all
18 original documents and the audit additions. Older documents contain known
errors; use their correction notices. If evidence is missing, mark the claim
unverified and investigate; if intent is unclear, ask before implementing it.

### Gating rules

| Change size | Pipeline |
|-------------|----------|
| > 3 files OR new module OR architecture change | SPEC → PLAN → IMPLEMENT → VERIFY → GATE |
| 1-3 files, clear intent, no new deps | Brief plan → implement → verify → GATE |
| Typo/comment/formatting | Just fix it → GATE |

---

## Quality gate — mandatory before every push

**No push leaves this machine without a green `ruff` and `mypy` run over the
full app code.** CI includes these three commands plus `pip-audit`; skipping them locally
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

Start with `spec-driven-development` every session. Open local files directly;
do not assume skills named in prose or `rea.*` tools are already loaded.

| Task | Project skill |
|------|---------------|
| Python correctness / PR review | `.agents/skills/python-reviewer/SKILL.md` |
| Exceptions and input validation | `.agents/skills/python-error-handling/SKILL.md` |
| PySide6 review and UI implementation | `.agents/skills/pyside6-reviewer/SKILL.md` plus its `project-overlay.md` |
| SQLite schema and queries | `.agents/skills/sqlite/SKILL.md` |
| ENET / HSFZ / DoIP / UDS | `.agents/skills/bmw-enet-protocol/SKILL.md` |
| Any vehicle mutation or restoration | `.agents/skills/vehicle-write-safety/SKILL.md` |
| APK / native binary investigation | `.agents/skills/reverse-engineer-anything/SKILL.md` |
| Feature and failure-behavior decisions | `.agents/skills/requirements-interview/SKILL.md` |

Generic skill examples do not override repository choices: Python 3.13 target,
100-column lines, Qt Widgets, QThread subclasses, no asyncio/QML/model-view
migration, and no automated test suite. Do not introduce dependencies merely
because a skill example uses them. Session management uses the current harness;
there is no required `opencode` skill. REA skill installation supplies guidance,
not its analysis engines or a live MCP connection. See `.agents/README.md`.

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
- **QSettings** for application preferences. Backups, current/intended state,
  readback records and exports are versioned data files, not preferences.
- **Inline expand/collapse** for detail views. No sub-page navigation.
- **QDialog** for forms (add service entry, write confirmation).

### SQLite patterns
- Read-only connection: `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)`
- Always use parameterized queries. Never string formatting for SQL.
- `DtcDatabase` is an application-level singleton. Its SQLite connection ownership
  must respect thread affinity; read-only mode does not make one connection
  safe across threads. Do not enable WAL on the embedded static asset.

### Error handling
- Default operation budget is 30 seconds. Apply a monotonic overall deadline
  including queueing, ACKs and UDS pending responses; document per-operation
  timing. Do not reset the deadline with each received fragment.
- Timeouts produce user-friendly messages (see error matrix in `docs/16-ui-spec.md`).
- Never show raw exceptions to the user.
- Log all UDS messages at DEBUG level for troubleshooting.

## Testing policy

The current owner policy is **no automated test suite at this stage**.
Do not create `tests/`. Framing, parsers and timeout behavior can be verified
offline; physical cars are required to validate ECU-specific behavior.
The owner reaffirmed this policy on 2026-10-28. It is not evidence of production
readiness; track verification limits in `docs/21-product-decisions.md`. UI verification is
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

## Key constraints

- **No admin/root for diagnostics.** Only initial ENET interface config + DHCP server need elevation.
- **REA is development-only.** Use it to recover behavior/data and implement
  standalone Python contracts. No research tools, source executables, providers
  or runtime REA service may be required by the app or included in its bundle.
- **Offline capable.** All databases embedded in the binary. No internet beyond ENET cable.
- **ENET cable only.** No Bluetooth, no WiFi OBD adapters, no K+DCAN.
- **F/G/U/I-series only (2011+).** No E-series.
- Static database support/security flags do not establish that an ECU is safe or
  writable on a particular car. Exact variant, software, authorization and
  verified write/readback behavior are required; the old 117/139 claim is unverified.
- **Coding/history writes save a backup first; completion follows D-29.**
  Preserve original, intended and observed state separately. This includes
  service history and both coding modes. The owner explicitly exempts fault
  clearing from saved backups/reports. Cleared DTC memory cannot be promised
  restorable.
- A transport ACK alone is insufficient. Under D-29, checked final application
  responses can establish response-confirmed completion where immediate readback
  is not meaningful; distinguish it from observed verification and give required
  cycle instructions. Resolve uncertain/partial outcomes before retry/rollback.

## GitHub CLI (pushing to this repo)

Every new code change starts on its own branch and is delivered through a new
pull request. Do not commit directly to main or reuse a merged PR branch.
The owner confirmed this workflow after merging PR #8 on 2026-10-28.

This machine has two GitHub accounts: `lennoncarvalho` (personal, for this repo)
and `lcarvalho-tns` (work, for other repos). This repo must always use
`lennoncarvalho`.

- **Before any `git push` or `gh pr` command**, switch to the personal account:
  `gh auth switch --user lennoncarvalho`
- **Never** run `gh auth switch` to `lcarvalho-tns` while working in this repo.
- **Never** modify `~/.config/gh/` (the shared default config).
- The repo-local `user.name` is `Lennon Carvalho` and `user.email` is
  set from the personal account.
