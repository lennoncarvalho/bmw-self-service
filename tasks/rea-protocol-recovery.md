# Task B — source-first BMW protocol and feature recovery

Current functional authority: [spec 26](../docs/26-feature-readiness-spec.md),
consolidated after owner interview D-21–D-49 on 2026-10-29. Use the
[implementation plan](rea-protocol-recovery-implementation-plan.md),
[ordered tasks](rea-protocol-recovery-tasks.md) and
[remaining REA investigations](rea-protocol-recovery-investigations.md).
Current acceptance is working personal use from Python source on the owner's Mac;
Windows/packages/signing are later. No open interview gate blocks source work.

Status: ready for source investigation; not completed reverse engineering.
Feature acceptance: [spec 26](../docs/26-feature-readiness-spec.md).
Source/tool/evidence routing: [doc 27](../docs/27-rea-source-guide.md).
Separate prerequisite runtime task: [Task A](protocol-library-migration.md),
[spec 25](../docs/25-library-migration-spec.md). Task A PR #12 is merged;
app integration uses its API. Do not reimplement its libraries here.
Created 2026-10-28 after [the first retained car session](../docs/23-first-vehicle-session.md).
Scope: ENET support across source-supported BMW F/G/U/I gateway/ECU/software
families; retain the existing exclusion of E-series and other adapters.

## Outcome and constraints

Required first usable slice: connection and real vehicle information, all-ECU
fault display with one Clear All action, local JSON history/append/explicit replacement and all
applicable easy coding reads/writes. No preset subset is accepted as catalog
completion. Explicit whole-list history replacement is current scope under D-51;
direct per-record car editing/deletion, advanced coding and CBS remain later.
This task includes evidence, corrected operation specs and implementation PRs,
not research documents alone. Spec 26 defines completion and pending choices.

Derive implementable protocol contracts from supplied applications and their
data, then use recorded traffic and vehicles to validate our implementation.
The owner's car is not the source from which we invent universal mappings.
Reuse standard protocol libraries rather than maintaining duplicate stacks;
[the released-library evaluation](../docs/24-protocol-library-evaluation.md)
recommends udsoncan, evaluates doipclient and prioritizes Scapy HSFZ integration,
with Gallia as an alternative. BMW-specific contracts remain REA work.
“Any BMW” remains the coverage objective, measured against the reference apps'
actual supported branches and restrictions, not a promise based on model year.

No app implementation is changed by this plan. Each later implementation starts
on a fresh `codex/` branch and new PR. Preserve no-automated-suite policy: do not
create `tests/`, even though offline byte analysis is possible. Keep all car I/O
in CarWorker threads and source-tool names out of shipped code/assets.

## Implementation planning handoff

The [implementation plan](rea-protocol-recovery-implementation-plan.md) and
[ordered development tasks](rea-protocol-recovery-tasks.md) turn this research
roadmap into file-level slices and acceptance gates. Planned from fetched
`origin/main` `db3c99f` on `codex/task-b-recovery-plan`, after Task A PR #12 merged.
Task A physical/platform/release acceptance remains independent. B1–B7 remain
pending; this planning session recovered no new wire contracts and changed no
app code. Planning verification is recorded below.

## Execution packages and tracking

| Package | Required deliverable | Status |
|---------|----------------------|--------|
| B0 | REA session/package/class/method smoke + portable Evidence | Complete for Android tooling only; doc 27 |
| B1 | Artifact/extraction reconciliation and feature contract ledger | Pending |
| B2 | Source-derived connection/inventory + vehicle-info contracts, then integration | Pending |
| B3 | All-ECU faults + one Clear All, partial results, post-clear reread | Pending |
| B4 | Shared durable baseline/intent/readback storage and recovery state design | Pending; needed before B5/B6 mutations |
| B5 | Local JSON/cards, ADD-only append and explicit erase-and-replace, known-local date checks and checked completion | Planned under D-50–D-55; reader retired |
| B6 | Every applicable easy preset: catalog/live state, composed write/restore/completion | Pending |
| B7 | Owner Mac source acceptance and source/vehicle coverage; packaged release later | Pending |

Use [the contract ledger](../docs/evidence/feature-contract-ledger.md), source
guide 27 and spec 26. For each package record the exact files before code, source
and portable Evidence links, corrected spec, implementation PR and verification.
B2/B3 integration uses the merged Task A API. B5/B6 read research can run independently, but mutations depend on
B4 and their own complete encoder/application/cycle contracts. A missing applicable easy preset is
an open item, not an acceptable undocumented subset. Do not implement B7's
claimed results or check completed until actually observed.

## Established starting point

- Two HSFZ connections and VIN reads worked in the retained session; no evidence
  of ACK misassociation in its 28 diagnostic transactions.
- FA, mileage, voltage and topology requests were rejected. I-level was decoded
  as a tab; empty FA was reported as successful. DTCs scanned the gateway only.
- Doc 02's limitations list says only `ESeriesVehicleInterface` had been analyzed.
  Doc 03's sensor JSON is explicitly inferred. Doc 07's topology example is
  conceptual. Docs 19/20 already identify the app's fixed reads as unverified.
- The gap is an incomplete evidence-to-implementation chain. This does not
  prove earlier REA calls were wrong; distinguish missing retained evidence,
  incomplete research and later implementation drift per claim.

## Evidence and deliverables required for every operation

Every contract must retain:

1. Original artifact name/version/full SHA-256; extraction identity and tool
   versions; actual REA Evidence IDs and portable export, when produced.
2. Entry point → variant/ECU selection → dependency assets/job → encoder →
   transport send → response dispatcher → decoder → displayed result, with
   exact classes/methods/overloads, offsets or PRG job/instruction locations.
3. Endpoint/tester addressing, transport/activation, session/security requirements,
   complete request sequence, exact request/response examples and byte layout.
   Mark static examples separately from observed traffic.
4. Length, endianness, sign, scale, units, sentinels, echo checks, NRC handling,
   P2/P2*/overall deadlines, keepalive, cancellation and late-response behavior.
5. Applicability by gateway/ECU/software/data version; exact definition selection,
   prerequisites, explicit unsupported behavior and unresolved branches.
6. App implementation location and acceptance checklist. Binary strings,
   UI labels, function names and simulation data alone do not close the chain.

Store a finding ledger and corrected operation contracts in `docs/evidence/`
and `docs/`; keep large/private originals and raw logs locally with integrity
references. Never invent an Evidence ID or commit keys, personal config, VINs
or entire proprietary source bundles. Keep standalone runtime dependencies
separate from research tools and reference applications.

## Phase 0 — use the now-working analysis capability

**After owner setup/restart:** REA MCP 6.8.0 now responds; actual package/class
inspection and method smali fallback succeeded with JADX 0.7.1. Ghidra 12.1.4
is reported available. Exported evidence, IDs and precise limitations are in
doc 27. Do not reinstall/reconfigure to resolve the historical findings below.
Android smoke inspection is complete; native target analysis is unattempted.
Continue with the actual artifact and relevant advertised tools.

Historical checks before the owner completed setup:

- No REA MCP tools are advertised to this session.
- Cached public REA launcher 6.8.0 runs with bundled Node 24.22.1. `npx` is
  absent from the current shell PATH; this is a launcher issue, not missing Node.
- `doctor --client codex --json` reports missing Codex registration and missing
  configured JADX, Ghidra, Hopper, IDA and Kuna providers. It does not establish
  a working live server. No provider or host configuration was changed.
- The project REA skill is present; doctor's missing shared skill copy is not
  a reason to duplicate it. Do not repair other clients merely because they
  appear in informational diagnostics.

Historical recovery procedure, only for a new observed blocker:

1. Check existing configuration/provider locations without exposing unrelated
   config. Prepare REA's scoped Codex `setup --dry-run --json`; show exact
   paths, backups and skill replacements before any configuration write, per
   `.agents/skills/reverse-engineer-anything/references/connection-and-recovery.md`.
2. Select only needed engines: Android requires a full Java 17+ JDK and supplied
   `jadx-headless-mcp` 0.7.1 JAR configured through `REA_JADX_MCP_JAR`.
   Native/managed routes depend on the actual SHM/PRG artifact type. Do not
   install every provider or assume a managed decompiler handles native code.
3. After authorized setup, reconnect the client, inspect actual tool schemas
   and `binary_session` availability. A green doctor alone is insufficient.
4. Smoke-inspect one actual APK using `inspect_android_package`, then inspect
   a known class/method; export complete Evidence. For SHM, inventory/identify
   before selecting `inspect_managed_artifact` or native `open_binary`.
5. Reuse existing smali/assets after validating their correspondence to the
   original APK. Until that link is proven, label them local extracted-source
   observations with unknown extraction provenance. Do not discard them or
   repeatedly re-decompile whole apps to answer focused questions.

Exit: working relevant analysis with retained evidence. Android meets this
smoke criterion now. Resolve missing tools only when a selected operation needs
them; do not claim Ghidra analyzed SHM just because it is available.

## Phase 1 — artifact and evidence reconciliation

Rehash originals, reconcile old abbreviated hashes/`ev_...` references with
recoverable exports, and record unsupported claims separately. Full hashes of
the following files were freshly checked and match the existing inventory:

| Artifact | SHA-256 |
|----------|---------|
| BimmerCode 4.25.04-12743 APK | `fc6eedeb741cbec49f46c126f8c72dac6a3dd1455f8a993c028695642459b728` |
| BimmerLink 2.36.1 APK | `da6f5b39efaa590fce68782f439c1b8f1b9f09ed41344055b8ff80666cae00d5` |
| SHM.exe | `2d6bb52808f1754ac9334958530c5b2c60ec373fa35b674f28bdb34dc93cf92a` |
| NBT.prg | `e94e3b4434c9f8563448ee0b89153ed62856cce3d72db61b18373b184f896415` |

Also inventory/hash relevant CIC/NBTEVO/HU_MGU PRGs, ECU groups, encrypted
assets, extracted datasets and interpreter dependencies as they enter scope.
Inspect existing `BimmerDaten/decoderPrg.py` and `ediabasx` parser/decompiler/VM
and transport source; independently verify relevant paths against originals.

Exit: each reused claim is retained/reproducible, contradicted, or unresolved;
all analysis targets and extraction relationships have explicit identities.

## Phase 2 — connection, identity and complete ECU inventory (first priority)

Trace reference apps' Connect entry points through adapter filtering, address
selection, discovery, multiple-vehicle handling, gateway selection, HSFZ/DoIP
decision, routing activation, tester addressing, VIN and ECU enumeration.
Trace F/G/U/I branches independently, including electric/i-series variants;
do not extrapolate ESeries logic or choose transport from a chassis letter.

Recover the actual inventory mechanism, its decoder and ECU address/software
identities. Do not assume a single F000 DID or ASCII/fixed-record SVT structure.
Trace how apps resolve a logical ECU, variant, diagnostic group/PRG and dataset;
preserve missing/unsupported inventory states. Establish session timing and
keepalive behavior, including whether this app's HSFZ heartbeat is appropriate.

Outputs: connection state machine and variant selection table, real inventory
contract, updated docs 07/10/20 (and DoIP portions of 01/05), implementation
mapping for `app/connection.py`, controller and vehicle page.

Exit: exact source-backed path from connection to an addressable ECU inventory;
the retained F48 session's rejection is explained without substituting a guess.
Unknown addresses must never silently become `0x00`.

## Phase 3 — vehicle information and complete diagnostics (next release slice)

Deliver B-CON/B-INFO/B-DTC-R/B-DTC-W from spec 26. Recover Clear All targets
and post-clear DTC/MIL checks, retaining the no-saved-report exception. Display
faults from all ECUs; only one Clear All button, no per-ECU/per-code clear UI.
Static/read-only research is not authorization for automatic vehicle mutation.

Follow data loaders as well as code. Concrete local seeds to verify with REA:

- `bimmerlink_extracted/smali/j6/h.smali` loads `dat/ecu-variants.enc`;
  `j6/e.smali` loads `dat/%s.enc`.
- `smali/io/sgsoftware/bimmerlink/asyncTasks/FileDecompression.smali` contains
  decryption/decompression logic. Recover its exact format and dependencies.
- `BMWSensorValueDeserializer.b()` → `j6/m.<init>` exposes fields such as
  `id`, `resultName`, `unit`, `label`, `byte`; follow incoming callers into
  the execution engine. This is not doc 03's invented generic DID/formula JSON.

Trace mileage, voltage, I-level, FA/vehicle identity through job selection,
request construction and decoding. Determine whether model/year/production
date come from vehicle data, reference lookup or external services. Preserve
offline operation and leave unavailable data explicit.

For DTCs, trace ECU inclusion/exclusion, session prerequisites, fault-memory
variants, status masks and complete record codecs. Treat confirmed, current,
pending, history, details/snapshots and emissions MIL as separate contracts.
Trace exact ECU-specific description lookup and extraction collisions. Fault
clearing later needs its own source-backed target/group and post-clear reread;
the owner requires no saved report/backup for that operation.

Outputs: corrected docs 03/07/14/20, versioned operation/decoder contracts,
diagnostic coverage schema and app change plan. Record unsupported reads as
unavailable; never label an empty task value a successful decode.

Exit: source-derived endpoint/job/codec for every enabled field; full discovered
ECU scan with explicit per-ECU success/failure/not-attempted coverage. The F48
validation should provide meaningful data and explain any remaining unavailable
fields, without promoting one vehicle's result to universal support.

## Phase 4 — local JSON history and coding reads

Deliver B-HIST-F local project/cards/JSON and B-CODE-R live coding reads.
B-HIST-R is retired under D-50: no read/probe pursuit or history-reader gate.
Use [workflow28](../docs/28-service-history-workflow.md) and B5a tasks for sourced
service types,1..13items, local-known date checks, origin/VIN/conflict handling,
expandable cards and strict JSON-only import/export. No proprietary/legacy adapters.

Coding still requires source-derived exact ECU/software/CAFD matching and actual
current data, block ordering/integrity and preset masks/composition. Use supplied
simulations only as labelled offline examples, not hardware acceptance.

## Phase 5 — mode-specific history writes and coding recovery

History: one-entry ADD-only append or a separately acknowledged nonempty full
replacement (ERASE once + ADDs in frozen preview order + evidenced activation).
Persist a separate local JSON history-operation journal with null prior-car state,
immutable local_before/intent/requests and per-step outcomes. Do not fabricate a
car backup or require its unavailable readback. Unknown car dates cannot be checked;
state the limitation. No automatic erase fallback, replay/resume/rollback or promise
to recover erased unseen entries. Capacity/session/result/reset facts still need
source/physical validation; no further history reader research is requested.

Coding: keep complete live original ECU bytes, exact definitions, durable backup/
intent, composed writes and meaningful readback/restoration. D-27 easy rollback and
D-29 cycle-aware results remain. Fault clearing retains its no-report exception.
All modes keep CarWorker/Task A ownership, power policy, app lockout and no Cancel.

Deliver B-HIST-W/B-CODE-W/B-REC per spec26/workflow28. Review and offline-check each
execution/result contract before agreed owner mutation validation. Retain raw
responses, partial/uncertain outcomes and per-variant applicability separately.

## Phase 6 — broaden coverage and prepare releases

Build a support matrix by transport/gateway/ECU/software/feature using branches
recovered from sources. For each row distinguish source-evidenced,
implemented, offline-inspected, physically validated, unsupported and unknown.
Compare coverage with the reference apps; explicitly retain their limitations.
Add ISTA+ if existing sources leave concrete diagnostics/topology/MIL/CBS gaps;
inventory the supplied version/data dependencies before planning its engine.
CBS remains future scope ([existing task](future-cbs-research.md)). ISTA+
availability is not a prerequisite for exploiting current APK/PRG material.

Current acceptance validates source launch/offline assets and actual operations
on the owner’s Mac (D-47–D-49). Windows/Intel/packages/signing remain later work. Full Ruff lint, Ruff format and mypy
are required before each push; green static checks do not establish car behavior.
Physical validation currently covers only the owner's car, so fleet validation
gaps remain explicit even when static source support is broad.

## Delivery order and acceptance

1. Analysis capability + evidence inventory.
   In parallel, design the selected-library adapter and verify lifecycle
   compatibility per doc 24; do not rewrite standard transports during REA.
2. ECU discovery/identity, then vehicle information + complete DTC reads.
3. Local JSON history/cards and exact live coding reads; no history-reader gate.
4. Verified mutations and recovery.
5. Broader source coverage and platform releases.

Track feature contracts by B-CON/B-INFO/B-DTC-R/B-DTC-W/B-HIST-F/B-HIST-W/
B-CODE-R/B-CODE-W/B-REC with source/evidence/spec/code/verification links.
Each row remains pending until its spec 26 acceptance is observed. Engine
setup is no longer the baseline blocker. No new wire mapping is established
by the limited tooling smoke inspection.

Each package ends with retained evidence, corrected specs, implementation plan,
an isolated PR when implemented, gate results and stated validation limits.
Do not complete a package on class-name search, UI resemblance or mock success.
Owner decisions D-21–D-49 now settle current product behavior. Remaining
technical questions belong to the REA checklist: network needs, actual field/
item constraints, write/restore/completion/cycle contracts and power readings.
No further car session is needed to start source investigation. Later public
release decisions do not block the Mac source milestone.

## Initial planning verification (before owner REA setup)

This documentation change was prepared on `codex/rea-protocol-recovery-plan`
from merged main `c866f83`. The complete 688-line session was inspected, its
request/reply counts and SHA-256 checked, and an identical local preservation
copy made outside Git. The four original artifact hashes above were rechecked;
existing extracted-source entry points were inspected without target execution.
Fresh REA doctor output establishes the listed setup gaps, not decompilation.

Full `scripts/preflight.sh` passed: Ruff lint, Ruff formatting and mypy across
all 18 application files. Local document links and `git diff --check` passed.
No app code, automated suite, vehicle operation, binary execution, provider
installation or host MCP configuration change was performed. The plan's phases
remain pending; these checks validate the planning deliverable only.

## Subsequent development handoff

The owner installed/configured REA and restarted; this session successfully
called `binary_session`, `inspect_android_package`, `inspect_android_class` and
`inspect_android_method`. The method used a declared smali fallback. Four actual
Evidence records were exported with integrity hash; see doc 27. No source app
was executed or car operation performed. Ghidra is available but native target
analysis was not attempted. This supersedes the old setup blocker above.

Separate Task A/spec 25 and Task B/spec 26 now define ownership, file maps,
dependencies, completion evidence and current owner scope D-16–D-20. Root/session
entry points route to those files and to the source/ledger guide. All feature
protocol rows remain open; tooling smoke results are not feature acceptance.

Handoff verification: all changed local Markdown links were checked (133), the
four-record portable bundle's byte count/SHA-256 matched its index, and JSON
indices parsed. Full `scripts/preflight.sh` passed Ruff lint, Ruff formatting
and mypy across all 18 app files; `git diff --check` passed. App sources and
installed dependencies were unchanged. These are documentation/tooling checks,
not Task A migration acceptance or Task B vehicle feature acceptance.

## Task B implementation-planning verification

Prepared on `codex/task-b-recovery-plan` from fetched `origin/main` `db3c99f`
(merge of PR #12). Reviewed session handoff, specs 19/20/21/26, source guide 27,
feature ledger and current Task A integration/caller boundaries. Added file-level
implementation plan and ordered B1–B7 tasks; updated navigation and merged status.
No new feature evidence, app implementation, vehicle operation or REA setup is
claimed. Pending product decisions remain gates for their affected slices.

Full `scripts/preflight.sh` passed: Ruff lint, Ruff formatting (28 files) and
mypy (28 sources). All 71 local Markdown targets in the five planning/handoff
files resolved; `git diff --check` passed. No automated suite was added. These
checks validate planning/document consistency and static baseline only, not
Task B vehicle behavior or release acceptance.

## Owner interview and spec consolidation — 2026-10-29

Recorded D-21–D-49 and consolidated docs 21/26, implementation plan, ordered
work and handoff. Current acceptance is functional personal Mac Python-source
use on the owner's car; packaging/signing/Windows are deferred. Removed old
product gates for immediate readback, mileage verification, write Cancel,
exact-duplicate-only additions and backup/locale/log preferences. D-29 now uses
operation-specific application/cycle/observation semantics. Added the factual
REA checklist; no new wire contract or feature implementation is claimed.

Verification: full `scripts/preflight.sh` passed Ruff lint, Ruff format check
(28 files) and mypy (28 sources). All 108 local Markdown targets in changed/new
documents resolved; D-01–D-49 appear exactly once in the decision register.
`git diff --check` passed and application sources were unchanged. No automated
suite, REA analysis, vehicle requests or network setup was performed during
this interview. Actual Mac/car feature acceptance remains development work.

## Implementation slice — 2026-10-29

REA-backed connection/inventory/diagnostics, exact-identity coding snapshots and
portable backup storage are implemented in `codex/task-b-feature-recovery`.
Task B is **not complete**: history local JSON/append/replacement flows, full preset writes and
restoration, actual MIL and DoIP inventory/address recovery remain open.
The supplied history utility's native read action is a Pro-only message.

See [recovered contracts](../docs/evidence/task-b-recovered-contracts.md) and
[verification/review](task-b-implementation-verification.md).

## History codec and runtime boundary follow-up — 2026-10-29

[Deep investigation](../docs/evidence/task-b-history-deep-investigation.md) records extended Lite native tracing and four primary
headunit ADD jobs. The key-only dormant-reader assertion remains unconfirmed.
Standalone `app/service_history.py` now preserves local records and encodes the
recovered NBT ADD body with checked final application status; no vehicle send
worker is enabled yet. D-50–D-55/workflow28 replace the old vehicle-history
baseline/read prerequisite with a local snapshot/intent/outcome journal. Fixed7 dealer
padding is proven; the variable-NUL hypothesis was disproven by native offsets
and a byte-for-byte round-trip of all eight supplied records. Complete headunit
history read is retired by D-50; Task B implementation remains open. REA supports development recovery
of code/data/contracts and is never a runtime dependency.
