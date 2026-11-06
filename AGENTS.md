# BMW Self Service — contributor instructions

## Start here

Read [plan.md](plan.md) for approved scope, [tasks.md](tasks.md) for current
implementation steps and the relevant section of [docs.md](docs.md) for source
contracts/data recovery. Inspect current code before trusting a status claim.
Load the applicable local skill from `.agents/skills/`; project rules override
its generic examples. Do not run setup or install tools just because a skill
mentions them.

## Documentation budget

There are only three project documents: `plan.md`, `docs.md`, `tasks.md`.
`README.md` is setup/usage; this file is contributor policy. Licences and reusable
skill/native-library manuals are utility files, not extra project plans.

- Update only the owning document when useful behavior, a reusable discovery or
  an actual implementation step changes. Most code fixes need no Markdown edit.
- Do not create per-feature specs, PR review reports, session handoffs, daily
  evidence summaries, status indexes, capability maps or completion histories.
- Remove obsolete claims instead of appending corrections/history. Keep useful
  technical discoveries concise in `docs.md`, with exact source/code pointers.
- Keep machine-readable evidence only for real build/decoder/provenance needs;
  no Markdown wrapper or duplicate report is required. Put scratch checks and
  large research output outside the repository.
- Documentation/research does not substitute for finishing implementation.
  Continue source investigation and code until the authorized work is complete.

## Source recovery and scope

Recover/reuse supplied applications, decrypted data, databases and executable
PRG jobs through REA and existing tooling. No guessed constants, car-trial
reconstruction, arbitrary variant selection or F48-only implementation.
Canonical jobs: `sources/ISTA_4.29.1x/Rheingold/Ecu/`. The explicit hash-bound
D94 supplement may come from `sources/Ecu/`; never replace canonical files.
Generate runtime assets during development. The app must not open source folders,
reference applications, encrypted research inputs or a runtime REA service.
Preserve exact reported and source-selected identities/hashes separately.

Support the broad source-supported F/G/U/I ENET scope. Only the owner's F48/NBT
is available for physical observations; other cars are not a development
prerequisite. Separate source support, offline verification and actual car
observations. Ask for targeted car logs at a hard blocker they can resolve,
with a specific purpose/procedure. No gratuitous vehicle mutation for testing.
Technical unknowns are research work; ask the owner only for unresolved product
choices. Do not introduce unsupported restrictions to match a tool limitation.

## Implementation rules

- Python 3.13 target, PySide6/Qt Widgets, 100-column Python style, typed signatures
  and public-method docstrings. Use existing dependencies; `python3`, not `python`.
- One `CarWorker(QThread)` base and one protocol owner for all vehicle I/O.
  No UI-thread sockets, separate job sockets, QML or asyncio/Qt mixing.
- One main window with stacked pages; widget children/QScrollArea for lists,
  inline detail expansion, QDialog forms, one outer page scrollbar. QSS stays
  in `assets/theme.qss`. QSettings stores preferences, not operation records.
- Default operation budget 30 seconds including queueing, ACKs and pending
  replies, with monotonic deadlines. Feature-specific longer budgets must be
  explicit. Preserve fragmented frames and late-response/tainted-stream handling.
- Explicit unavailable/partial/uncertain results; no raw exceptions or invented
  success. Retain useful results and full DEBUG UDS logs. English interface;
  diagnostic source-language fallback must keep every code visible.
- SQLite assets open read-only with parameterized queries and correct per-thread
  connection ownership. No WAL or schema mutation on embedded static assets.
- Keep source tool names out of new application code/shipped data; research
  provenance belongs in development records. The runtime must remain standalone.

## Vehicle writes

Follow `plan.md` and `docs.md` for exact feature behavior. Every write requires
fresh matching identity/software/source definition, confirmed intent, adequate
power or explicit acknowledgement, durable required state and one owner.
Coding saves complete original baseline/target bytes; history saves local JSON,
intent and outcomes with unreadable prior car history explicitly unavailable.
CBS saves its exact before-state/intent/results. Fault clearing needs no backup.

No write Cancel; block disruptive UI actions. Check final application responses
and meaningful post-state/cycle completion. A transport ACK is insufficient.
Distinguish response-confirmed and observed verification. Never automatically
replay/resume/rollback uncertain mutations. Keep exact planned duplicate
occurrences distinct from retries. Restoration is a newly guarded write.

## Verification and delivery

No automated test suite or `tests/` directory. Use meaningful one-off offline
source/native/byte/error checks and actual Qt/DEMO flows as needed; no new test
framework/dependency. Review nontrivial code and fix concrete findings. A short
PR description and existing source contracts suffice; no review-report file.

Before **every push**, run `scripts/preflight.sh` over all `app/`, `ui/`, `main.py`:
Ruff check, Ruff format check and mypy must all pass. No subset or pre-existing
failure exception. Fix behavior-preserving lint/format issues and real types;
never suppress a defect to turn a gate green. Static checks do not validate cars.

For new work after a merge, fetch origin and use a fresh `codex/` branch from
`origin/main`; do not reuse merged branches or commit to main. Preserve unrelated
work. Open a PR only when explicitly requested; never merge it. For an open PR,
keep related authorized fixes on its branch. Before any `git push` or `gh pr`,
run `gh auth switch --user lennoncarvalho`. Never switch to the work account or
modify shared `~/.config/gh/`. Use the repository's personal Git identity.
