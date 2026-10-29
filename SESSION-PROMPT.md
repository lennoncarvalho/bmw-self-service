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
Direct per-record car editing/deletion and advanced coding remain later.
CBS reading/writing is current scope under D-58, due before both coding modes.
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
recovered NBT ADD body with checked final application status. The subsequent
[history execution implementation](tasks/task-b-history-write-implementation.md)
adds the separate journal and mode-specific write workers; physical validation
remains pending. The approved contract is workflow28 rather than the
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

## Post-PR13 topology/dashboard increment — 2026-10-29

PR13 is merged at06e8baf. The next implementation branch is
codex/task-b-topology-selection, created from fetched origin/main with a clean
worktree. Read tasks/task-b-topology-implementation.md and its verification
record before repeating work. Source recovery adds failed/empty-inventory
fallback over all148UDS catalogue addresses, preserving candidate origin and
identity outcomes without claiming installed topology. Native Qt Ethernet types
replace interface-number/Wi-Fi heuristics. MIL now accounts for all62exact
engine rows:53rows/17definitions use three traced direct DIDs;9rows/9definitions
have explicit remaining decoder/source branches. Shared freshness/UI stays intact.

Next concrete source work remains: U/I category/metadata and actual full-width
DoIP address mapping, bit-packed gateway3F06 vehicle order/model decoding, the
five older MIL block-reader chains, alternate DME9FF_R/EDMEI1 MIL and missing
DME98_R/FCCU definitions; then diagnostic category/description breadth. Follow
ordered queue after those branches with local JSON/history journal/cards,
mode-specific writes and complete easy coding/recovery. None is hardware-blocked.
No history reader, legacy product adapters or guessed coding baseline is revived.

## CBS priority amendment — D-58 (2026-10-29)

The owner requires CBS **reads and writes before easy and advanced coding**.
Insert CBS after local/history execution in the ordered queue; do not leave it
in future scope. Use [the promoted task](tasks/future-cbs-research.md) and pinned
upstream cbs.py first, then resolve exact variants/versions with supplied source.
The task includes actual read/write implementation, durable before/intent/results,
checked completion/post-state, offline/UI verification and independent review.
History writes and CBS resets are distinct; history reading remains retired.

PR15 merged at b62243f on 2026-10-29 (20:12:28Z). The owner requested continued
implementation on PR16's codex/task-b-cbs-priority branch, updated with fetched
origin/main. Preserve both the vehicle-order implementation and D-58 ordering.
Do not open another PR unless the owner explicitly asks; do not merge PR16.

## Post-PR14 vehicle-order increment — 2026-10-29

PR14 merged at dcb70a6 (19:06:05Z), including refreshed diagnostic target/revision
fixes. Clean worktree, fetched origin/main, new branch
`codex/task-b-vehicle-order`. The packed gateway3F06 read is implemented in the
settled overview worker: model range/type key/time criterion/paint/upholstery,
ordered optional configuration sections and raw response preservation. Time
criterion remains a configuration code, not a physical production date.
4735exact passenger equipment codes have English descriptions, with unknown
codes retained; no guessed trim or model lookup. Read
`tasks/task-b-vehicle-order-verification.md` and the linked source evidence
before repeating work. The supplied45series groups are fully accounted; i3/i8
use the F interface category and i4/iX3 the inherited G category. There is no
explicit U/I20 group or DoIP logical-address converter in those supplied paths.

Next concrete work: full-width DoIP mapping/newer U source branch from a matching
artifact, remaining odometer/exact model/build measurements and diagnostic
category/description reconciliation. Five older MIL block readers are now traced
to fixedF303 clear/define/read; see `docs/evidence/task-b-mil-block-recovery.md`.
Implement exclusive whole-sequence ownership, bounded response-confirmed cleanup
and visible uncertainty before enabling these diagnostic configuration mutations;
operation_scope alone only shares a deadline. Preserve --read-only rejection of2C.
DME9FF_R/EDMEI1 alternate MIL and DME98_R/FCCU missing definitions remain source
work. These are implementation/source tasks, not waits for more cars. Then
continue local JSON/history journal/cards, mode-specific history writes and full
applicable coding/recovery in the ordered queue. No new physical observations.


## PR16 implementation continuation — local history editor

PR15 merged at b62243f (2026-10-29T20:12:28Z). At the owner's request, switched
cleanly to codex/task-b-cbs-priority and merged fetched origin/main, preserving
both PR15's code/fixes and D-58. No new PR is authorized; continue this existing
PR16 branch until the owner directs otherwise. Do not merge it.

Local JSON history/editor/workspaces are implemented; read
`tasks/task-b-local-history-implementation.md` before repeating this work.
JSON-only bounded import/export,14service choices, editable multi-item cards,
unknown/conflict preservation, explicit VIN association and isolated offline/
live/DEMO durable projects have offline/Qt/DEMO and independent-review evidence.
Editor persistence remains separate from the implemented B4 history-operation
journal. Frozen append/replacement plans and mode-specific write workers are
implemented with exact headunit identity/session/result/reset handling and durable
per-step outcomes; physical validation remains pending. Read
[tasks/task-b-history-write-implementation.md](tasks/task-b-history-write-implementation.md)
and [the execution contract](docs/evidence/task-b-history-write-contract.md).
CBS read **and write** follows before coding.

Queue1–3also retains real DoIP/newer U sources, odometer/model/build/measurements,
diagnostic category/description reconciliation and remaining MIL branches.
Independent code review confirms the five older engines can use existing
run_operation for exclusive clear/define/read/cleanup; explicit2C service support,
confirmed UI action/global lockout, reserved cleanup budget and per-step uncertain
outcomes remain required. Do not put dynamic-DID writes in normal overview refresh.
No additional physical vehicles are a prerequisite for these implementation tasks.
