# Resume BMW Self Service development

Read `AGENTS.md`, `.agents/skills/spec-driven-development/SKILL.md`,
`docs/README.md`, docs 19/20/21, then select the requested task:

| Task | Start file | Specification | Outcome |
|------|------------|---------------|---------|
| A — library migration | `tasks/protocol-library-migration.md` | `docs/25-library-migration-spec.md` | One protocol owner/API using udsoncan and selected Scapy HSFZ/doipclient adapters |
| B — close feature gaps with REA | `tasks/rea-protocol-recovery.md` | `docs/26-feature-readiness-spec.md` | Real vehicle info, all-ECU fault display/single Clear All, local JSON history/append/explicit replacement and all applicable easy coding |

Task A code is merged into main through PR #12; see
`tasks/protocol-library-migration-verification.md` for the API, exact library
boundary and pending owner-car/platform/release acceptance. Task B consumes
that merged API; Task A acceptance remains pending independently. Follow the
[Task B implementation plan](tasks/rea-protocol-recovery-implementation-plan.md) and
[ordered development tasks](tasks/rea-protocol-recovery-tasks.md). Task B research
can run independently; B integration uses A's merged API. Do not invent BMW
constants inside A or declare the release functional merely because libraries work.
Current Task B milestone is a working Mac Python-source application with broad
source-supported BMW F/G/U/I ENET coverage (D-57). The owner's F48/NBT is the
only physical validation vehicle; access to other cars is not a dependency.
Windows, packages/signing and public distribution
are later. [Spec 26](docs/26-feature-readiness-spec.md) is consolidated after the
2026-10-29 interview; [REA checklist](tasks/rea-protocol-recovery-investigations.md)
contains the remaining facts. No product interview gate remains for starting work.
All applicable easy presets are required. D-50–D-55 retire car-history reading
and promote explicit erase-and-replace alongside one-entry ADD-only append.
Use local JSON only, the14sourced service types and expandable multi-item cards.
Direct per-record car editing/deletion, advanced coding and CBS are later.
Reject future/known-local same-day dates and use entered mileage without an
odometer check. Do not pursue a reader or legacy .bmwsh/.tst adapters. English UI, regional formats (Brazilian/km fallback), simple
retained/deletable portable backups and full unmasked logs are required.

Answers live in `sources/` and its extracted/reference trees, accessed through
REA for shipped artifacts. **Read `docs/27-rea-source-guide.md`** for artifact
paths, concrete class/job seeds, live tooling observations, portable evidence,
contract/ledger fields and additional-source options including ISTA+.
Ordinary upstream library source can be read without REA.

REA MCP 6.8.0 is connected as of this handoff. Android package/class/smali
inspection actually succeeded; Ghidra 12.1.4 is reported available. Do not rerun
setup based on earlier missing-engine notes. Check per-tool availability only
when needed; apktool decoding remains unavailable. Reuse retained evidence
bundles if new-session IDs are absent; do not fabricate `ev_...` references.

Current app baseline: PRs #8/#9/#11/#12 merged. The retained session (doc 23) proves
HSFZ discovery/session/VIN on the owner's F48 X1 MY2018/NBT. Optional reads were
rejected, I-level/FA successes were misleading and DTCs reached only the gateway.
Live history reads are retired; full preset-value coding reads remain incomplete,
while exact-identity coding snapshots are implemented in PR13. The former add-like
history request is no longer automatically sent. Read doc 24 for library
evaluation and exact adapter obligations. Inspect current Git/PR state before
changes; this baseline does not replace current source review.

Save a complete vehicle baseline/intent before coding. History instead saves
local_before/intent/requests/results with null prior-car state in a separate
journal; it cannot back up or restore unknown car entries. Follow
[workflow28](docs/28-service-history-workflow.md) for explicit destructive
replacement acknowledgement and no automatic replay/resume/rollback. D-29 in doc 21
supersedes unconditional immediate readback: validate application completion,
recover per-operation ignition-cycle requirements, and distinguish response-confirmed
completion from observed verification. Easy coding stops/restores on established failure, never on premature old-value
readback. D-28/D-30 forbid write Cancel and block disruptive actions/normal quit;
D-31 blocks known insufficient power and permits acknowledgement when unknown.
Fault clearing requires no saved report/backup. Interrupted coding requires
reidentification/reread/compare. History uses its local journal and manual iDrive
inspection before a separately confirmed new operation; no automatic replay.
Keep all I/O in CarWorker, partial coverage explicit and DEMO isolated. Source
support is not universal physical validation; exact ECU/software/definitions
gate writes. One Clear All is the only fault-clear UI action in this release.

Doc 21 owns product decisions. Resolve technical facts with REA; ask only new
behavior questions actually exposed by evidence, not already answered choices. No automated suite
or `tests/`. Full `scripts/preflight.sh` before every push; report Ruff lint,
formatting and mypy separately and actual hardware/runtime/package coverage.

Start new app code on a fresh `codex/` branch from current main and create its
own PR. Do not put app code into the docs/planning branch or reuse a merged PR
branch. Never merge without owner instruction. Follow the personal GitHub
account rule in AGENTS.md before push/`gh pr` operations.

## Task B implementation checkpoint — 2026-10-29

Implementation branch: `codex/task-b-feature-recovery` (new from origin/main,
carrying the approved planning commits). The owner requested unattended REA-led
implementation, outsider review, fixes, verification and a PR. The fundamental
source-recovery rule is now in AGENTS.md. A reviewed recovery slice is implemented;
**Task B remains incomplete**. Under D-57, the owner reviews/merges PR13 as an
incremental delivery; do not keep it draft as a completion gate.

Read `docs/evidence/task-b-recovered-contracts.md` and
`tasks/task-b-implementation-verification.md` before continuing. They record
recovered requests/decoders, exact native/Android evidence, deterministic asset
reproduction, code/review findings, offline checks and outstanding work. SHM Lite's
native Read-from-car case only displays a Pro-only message; don't fabricate a
history read. D-50–D-55 supersede the old complete-car-baseline gate for history;
implement explicit append/replacement with durable local state and warnings.

Current code reads HSFZ inventory/variants and normal/information/permanent
faults, clears supported fault/information memories with checked post-reads,
and saves exact-identity opaque coding snapshots in portable durable JSON.
DoIP connection retains Task A but byte-to-logical ECU inventory translation
is not recovered. Full easy preset predicates/dynamic options/writes, recovery,
power/ignition contracts, local JSON/history append/replacement and broader
emissions MIL coverage remain open; a history reader is no longer required.
No new car acceptance or universal compatibility is claimed. The owner now plans
to merge PR13; follow the post-merge continuation below instead of starting
another implementation slice on this branch.

## History codec and runtime boundary follow-up — 2026-10-29

[Deep investigation](docs/evidence/task-b-history-deep-investigation.md) records extended Lite native tracing and four primary
headunit ADD jobs. The key-only dormant-reader assertion remains unconfirmed.
Standalone `app/service_history.py` now preserves local records and encodes the
recovered NBT ADD body with checked final application status; no vehicle send
worker is enabled yet. The approved next plan is workflow28 rather than the
old complete-car-history baseline/read prerequisite. Fixed7 dealer
padding is proven; the variable-NUL hypothesis was disproven by native offsets
and a byte-for-byte round-trip of all eight supplied records. Complete headunit
history read is retired; Task B implementation remains open. REA supports development recovery
of code/data/contracts and is never a runtime dependency.

## Next development after PR13 — owner handoff

Read [the ordered continuation](tasks/task-b-next-development.md) first. Confirm
PR13 merged, fetch origin, and create a fresh codex/ branch from origin/main.
Until merge, limit this branch to review fixes/documentation. Do not merge for
the owner or create the next branch early. D-57 supersedes older F48-only
acceptance wording and any instruction to hold PR13 draft until Task B is complete.

Next: broad connection/topology/definition selection, then MIL/dashboard coverage
and diagnostics breadth, local JSON/history journal/cards, history writes and
full applicable easy coding/recovery. Source-derived implementation/review and
offline checks proceed without fleet hardware. Keep source support and actual
physical observations separate; do not turn missing car access into missing code.
The three-variant MIL decoder and shared dashboard/Diagnostics observation are
implemented, reviewed and checked offline; reuse them rather than redoing that
trace. Additional engine mappings remain required source recovery.
