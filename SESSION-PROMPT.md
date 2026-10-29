# Resume BMW Self Service development

Read `AGENTS.md`, `.agents/skills/spec-driven-development/SKILL.md`,
`docs/README.md`, docs 19/20/21, then select the requested task:

| Task | Start file | Specification | Outcome |
|------|------------|---------------|---------|
| A — library migration | `tasks/protocol-library-migration.md` | `docs/25-library-migration-spec.md` | One protocol owner/API using udsoncan and selected Scapy HSFZ/doipclient adapters |
| B — close feature gaps with REA | `tasks/rea-protocol-recovery.md` | `docs/26-feature-readiness-spec.md` | Real vehicle info, all-ECU fault display/single Clear All, history read/add and all applicable easy coding |

Task A code is merged into main through PR #12; see
`tasks/protocol-library-migration-verification.md` for the API, exact library
boundary and pending owner-car/platform/release acceptance. Task B consumes
that merged API; Task A acceptance remains pending independently. Follow the
[Task B implementation plan](tasks/rea-protocol-recovery-implementation-plan.md) and
[ordered development tasks](tasks/rea-protocol-recovery-tasks.md). Task B research
can run independently; B integration uses A's merged API. Do not invent BMW
constants inside A or declare the release functional merely because libraries work.
Current Task B milestone is working personal use from Python 3.13 source on the
owner's Mac/F48/NBT (D-47–D-49). Windows, packages/signing and public distribution
are later. [Spec 26](docs/26-feature-readiness-spec.md) is consolidated after the
2026-10-29 interview; [REA checklist](tasks/rea-protocol-recovery-investigations.md)
contains the remaining facts. No product interview gate remains for starting work.
All applicable easy presets are required. History user editing/deletion/replacement,
advanced coding and CBS are later. Internal preserving whole-list rewrite is
allowed for add; reject future/same-day dates and use entered mileage without
an odometer check. English UI, regional formats (Brazilian/km fallback), simple
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
Live history/coding readers are disabled pending evidence. The former add-like
history request is no longer automatically sent. Read doc 24 for library
evaluation and exact adapter obligations. Inspect current Git/PR state before
changes; this baseline does not replace current source review.

Save durable baseline and intent before history/coding mutations. D-29 in doc 21
supersedes unconditional immediate readback: validate application completion,
recover per-operation ignition-cycle requirements, and distinguish response-confirmed
completion from observed verification. Easy coding stops/restores on established failure, never on premature old-value
readback. D-28/D-30 forbid write Cancel and block disruptive actions/normal quit;
D-31 blocks known insufficient power and permits acknowledgement when unknown.
Fault clearing requires no saved report/backup. Interrupted writes:
reidentify, reread/compare, then user-selected recovery; no automatic replay.
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
**Task B remains incomplete** and its PR must remain draft.

Read `docs/evidence/task-b-recovered-contracts.md` and
`tasks/task-b-implementation-verification.md` before continuing. They record
recovered requests/decoders, exact native/Android evidence, deterministic asset
reproduction, code/review findings, offline checks and outstanding work. SHM Lite's
native Read-from-car case only displays a Pro-only message; don't fabricate a
history read or enable destructive rewrite without an original car baseline.

Current code reads HSFZ inventory/variants and normal/information/permanent
faults, clears supported fault/information memories with checked post-reads,
and saves exact-identity opaque coding snapshots in portable durable JSON.
DoIP connection retains Task A but byte-to-logical ECU inventory translation
is not recovered. Full easy preset predicates/dynamic options/writes, recovery,
power/ignition contracts, history read/add and actual emissions MIL remain open.
No new car acceptance or universal compatibility is claimed. Continue the same
unmerged implementation PR/branch for this work; don't reuse it after merge.

## History codec and runtime boundary follow-up — 2026-10-29

[Deep investigation](docs/evidence/task-b-history-deep-investigation.md) records extended Lite native tracing and four primary
headunit ADD jobs. The key-only dormant-reader assertion remains unconfirmed.
Standalone `app/service_history.py` now preserves local records and encodes the
recovered NBT ADD body with checked final application status; no vehicle send
worker is enabled without a complete baseline/execution contract. Fixed7 dealer
padding is proven; the variable-NUL hypothesis was disproven by native offsets
and a byte-for-byte round-trip of all eight supplied records. Complete headunit
history read and Task B completion remain open. REA supports development recovery
of code/data/contracts and is never a runtime dependency.
