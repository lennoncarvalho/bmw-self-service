# Read-only vehicle capture preparation

Date: 2026-10-28. Base: main d057f99 after merged PR #8.
Branch: codex/read-only-car-capture. Owner will run this Mac's source checkout,
navigate every page and read data without writing. Every change gets a new PR.

## Plan and acceptance

1. main.py: explicit --read-only launch, unique per-run rotating DEBUG log,
   thread/time/build/startup context, exception diagnostics and discoverable path.
2. app/connection.py: capture UDP/TCP endpoints, discovery bytes, full frame and
   fragment data, request queue/budget/late-response state and errors. Preserve
   existing transport semantics. Enforce a read-service allowlist in both real
   transports when --read-only is active, before sending any request. Diagnostic
   sessions/default/extended and TesterPresent are allowed; programming, writes,
   routine start, DTC clear and reset are blocked. No security probing.
3. app/worker.py: record worker identity, duration, parsed post-connect outcomes
   and parse exceptions, preserving existing result keys. ui/main_window.py: pass mode to transports, show it visibly, log navigation,
   do not auto-start DHCP in this read-only validation launch, preserve per-page
   outcomes and explicit unavailable states.
4. History: prevent the unverified 31 01 A0 81 read at both page and worker;
   no invented replacement. Keep the page navigable and DEMO data separate.
5. Coding: no live mock values or guessed CAFD probes on the GUI thread. Until
   exact ECU/software definitions and live reads are evidenced, show unavailable
   for live coding, preserve DEMO and disable live writes.
6. Diagnostics: block clear controls in this mode, fix the documented 59 02
   record offset/length validation, preserve incomplete-scan status and unknown
   MIL. Give the read worker its own SQLite connection and close it there.
   Do not invent snapshot timestamp/mileage codecs.
7. Document the exact source launch and log collection. Full preflight, source
   review, no automated behavioral suite, no vehicle/network/elevation actions.
   Commit, push on this branch, create/attach PR, verify CI. Do not merge it.

## Evidence and limits

Relevant contracts: docs/10,12,14,16,19,20,21. Existing History routine and coding
variant/decoder contracts are unresolved. Navigable does not mean every feature
has a supported live reader. Read-only mode prevents data-changing UDS services;
it still establishes diagnostic sessions and exchanges keepalive traffic.

## Verification and observed scope

- Full scripts/preflight.sh: Ruff lint, Ruff format and mypy pass across all 18
  source files. No automated behavioral suite or car/network/elevation action.
- Source review: both real transports validate read-only policy before locking
  or sending; no live History worker/routine is started; live Coding constructs
  explicit unavailable pages without its former probes. CLI help exposes mode.
- Local startup created a unique debug session and entered the Qt event loop on
  Python 3.15.2 / PySide6 6.12.0. Log creation, runtime/adapter metadata and the
  READ ONLY title were observed. The startup snapshot preceded the commit and
  therefore records base revision d057f99 rather than the final source revision.
- Native UI automation inspected the window but could not activate its gear
  menu via AX/keyboard/coordinate input. No complete DEMO navigation result or
  live disabled-page rendering is claimed. Only the launched process was stopped.
- Restore the preflight script's executable Git mode: main had mode 100644, so
  direct scripts/preflight.sh failed until its executable permission was restored.
- User confirmed this Mac's source checkout is the validation environment.
  Main stays untouched; changes will be delivered by a new PR without merging.
