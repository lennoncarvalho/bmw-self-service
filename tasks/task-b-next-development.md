# Task B — continuation after PR13

Authority: owner decision D-57 in docs/21-product-decisions.md. PR13 is an
incremental delivery; the owner handles its review and merge. Task B is unfinished.
No new product interview is needed to start the work below.

## Branch boundary

1. Verify PR13 is actually merged; until then, only its review fixes and handoff
   belong on codex/task-b-feature-recovery. Do not merge it for the owner.
2. Check worktree status, fetch origin, then create a fresh codex/ branch from
   fetched origin/main. Never reuse the merged branch or assume the local main
   contains the merge. Preserve any unrelated changes.
3. Reconcile the merged implementation/evidence with this queue. Retain working
   Task A ownership and Task B code; do not restart already completed recovery.

## Development target and evidence

Implement broad source-supported BMW F/G/U/I ENET behavior, using supplied
binaries, extracted classes, PRGs and decrypted definitions. Only the owner's
F48/NBT is available for physical observations. Another vehicle, a fleet test
program or prior owner-car acceptance is not a dependency for continuing source
recovery, implementation, review or incremental PR delivery.

For each branch track source contract, implemented code, offline verification,
physical observations and source restrictions separately. A single-car result
cannot establish fleet validation; lack of another car cannot justify leaving
recoverable source branches unimplemented. Exact variant/software/definition
matching remains required, especially for writes. Unsupported means a traced
source restriction; not-yet-recovered means an actionable investigation.

## Ordered implementation queue

1. **Broad connection and identity (B1/B2; R2/R3).** Recover actual HSFZ/DoIP
   discovery, routing/session selection, address translation and inventory
   branches from source apps. Build a branch/definition coverage inventory and
   integrate it with the existing owner. Preserve unknown/unreachable targets.
   Exit: every recovered source branch implemented or a specific unresolved
   source path recorded; no F48/year/chassis-only routing shortcut.
2. **Complete first-page information (B2; R3/R5).** Expand MIL beyond the current
   three exact MEVD identities by tracing engine definitions and reader selection.
   Recover actual odometer, vehicle/FA identity, model/build/configuration and
   useful optional measurements with type/scaling/validity. Reuse the settled
   dashboard/refresh/shared MIL UI already implemented. Exit: source inventory
   accounting and supported data displayed, with no guessed values or DTC-to-MIL
   substitution. Do not add dynamic-definition writes without an evidenced need.
3. **Diagnostic breadth (B3a/B3b; R4/R5).** Reconcile existing memory codecs,
   description catalogue and Clear All against all recovered selection branches;
   finish gaps in applicability, target accounting, negatives and post-clear
   reads. Exit: per-target outcomes and full source-category accounting.
4. **Local history, independent of car access (B4/B5a).** Implement the separate
   durable history journal, versioned JSON-only files, fourteen service choices,
   multi-item cards and date/VIN/conflict rules in workflow28. Keep the coding
   backup validator intact. No reader, legacy adapters or current-odometer gate.
5. **History writes (B5b; R7).** Finish exact headunit session/result/reset/
   capacity contracts, then implement ADD-only append and explicit one-ERASE
   replacement with frozen plans, durable per-step outcomes and global lockout.
   No automatic retries/replay or invented old-car backup.
6. **All applicable easy coding (B6a/B6b; R8/R9).** Recover full preset selection,
   dynamic options, exact current-value bytes, composition, authorization,
   completion/cycle and restoration. Account for the whole source catalogue;
   missing applicable rows are unfinished work, not silently excluded scope.
7. **Close implementation and review (B7).** Perform meaningful one-off offline
   byte/error/deadline checks and visual DEMO/UI inspection, independent review,
   fixes and full scripts/preflight.sh before every push. No tests/ suite.
   Deliver reviewed incremental PRs, distinguishing completed implementation from
   remaining source recovery and physical observation records.

Use tasks/rea-protocol-recovery-tasks.md for detailed acceptance and
tasks/rea-protocol-recovery-investigations.md for source entry points. The retained
source/evidence routing is docs/27-rea-source-guide.md; REA remains development-only.

## Current baseline to preserve

PR13 includes recovered HSFZ inventory/F150 identities, diagnostic memory reads
and Clear All, exact coding snapshots/portable backup storage, history byte
codecs, and the richer dashboard. MIL is implemented for MEVD172/172Y/1725 only;
that is current coverage, not the final support target. See
[dashboard verification](dashboard-implementation.md) and
[MIL contract](../docs/evidence/task-b-mil-read-contract.md).

Physical car checks can be recorded when the owner runs them, with a concrete
reviewed procedure for mutations. They do not block the source-based queue or
require more cars. Windows/build/signing remain deferred; Mac source use remains
first, with the actual local Python version distinguished from the3.13 target.

## PR13 review carry-forward

See [review dispositions](pr-13-review-followup.md) for every Robin/CodeRabbit
finding and current-slice fixes. Preserve these boundaries in the next coding
session:

- B5a/B5b must replace the intentionally disabled history send boundary with the
  separate local journal and mode-specific workers. Do not re-enable it merely
  because an ADD encoder exists. Vehicle history reading remains retired.
- `SERVICE_TYPES` in app/service_history.py is the shared fourteen-type catalogue;
  legacy sample parsing now lives only in scripts/inspect_history_format.py.
  JSON/card work reuses the catalogue; it must not restore legacy interchange.
- B6b must prepare live baseline/intent and per-step results through OperationStore
  using actual ECU bytes. `_save_demo_preview` stores non-restorable display
  metadata outside the live backup tree and is not a vehicle backup implementation.
- Keep filesystem-heavy backup import/export/validation off the UI thread when
  extending the backup UI. Current reads are bounded32MiB; do not add a streaming
  dependency or relax integrity checks based on the review's incorrect claim
  that the read is unbounded. Define byte/depth/collection bounds for new schemas.
- Preserve exact tail-based F101 decoding, full-window discovery ambiguity checks,
  shared tri-state MIL/freshness and operation deadlines. A simplification must
  retain their recovered contracts, not substitute plausible offsets or routing.

## Completed next increment checkpoint — topology/MIL selection

PR13 merge verified at06e8baf; fresh branch codex/task-b-topology-selection.
Failed/empty inventory now follows the source's148-address UDS candidate branch
with origin/identity/coverage accounting. Native Ethernet types remove Wi-Fi
misidentification. MIL expands to53exact rows/17definitions across three traced
DIDs; all62engine rows are accounted. See
[verification](task-b-topology-verification.md),
[topology source](../docs/evidence/task-b-topology-selection.md) and
[MIL source](../docs/evidence/task-b-mil-breadth.md).

Continue queue1–3 with actual DoIP address translation/U/I category metadata,
gateway3F06 bit-packed vehicle order/model decoder, five older MIL block-reader
chains and alternate/missing engine definitions. Diagnostic category/description
reconciliation and local history/writes/coding remain required in order. After
this increment merges, verify merge/fetch and create another fresh codex/branch;
do not reuse a merged implementation branch or wait for more cars.

## Post-PR14 vehicle-order checkpoint

PR14 merge verified at dcb70a6, new branch codex/task-b-vehicle-order from fetched
origin/main. Gateway3F06 packed vehicle order and4735English passenger-equipment
labels are implemented in the settled overview with explicit unknown/incomplete
states. No trim/build date is inferred. Exact45source-category groups and their
U/I/DoIP limits are recorded in the metadata evidence. See
[verification](task-b-vehicle-order-verification.md),
[vehicle-order contract](../docs/evidence/task-b-vehicle-order.md) and
[metadata/category accounting](../docs/evidence/task-b-vehicle-metadata.md).

The next MIL software task is now concrete: implement fixedF303 clear/define/read
under one exclusive multi-request lifecycle with bounded cleanup and honest
uncertain outcomes, preserving --read-only's2Crejection. The current overview
still uses the53direct-scalar rows; this increment does not enable mutations.
[Recovered block lifecycle](../docs/evidence/task-b-mil-block-recovery.md) includes
all five original job paths and Android allocation/stop behavior. Alternate/missing
four engines remain source work. Queue1–3also retains actual DoIP full-width
mapping/newer U artifacts, actual odometer/model/build measurements and diagnostic
category/description reconciliation. History/coding follow in the existing order.
