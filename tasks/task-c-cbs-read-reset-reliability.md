# Task C — reliable CBS reading and individual resets

Priority: **next development task**, explicitly set by the owner on 2026-11-05.
Status: planned; the existing CBS implementation is the starting point.
Apply [the shared C–F workflow](task-c-through-f-roadmap.md).

## Goal and scope

Make connection → read service status → display every applicable item → reset one
supported item → report completion/post-state reliable across the source-supported
current milestone. The owner calls this “CBS read and erasing must be flawless.”
Translate that into concrete acceptance below, not a guarantee of universal
vehicle behavior. “Erasing” here is an individual source-supported service reset.
No generic erase-all routine, history ERASE or unrelated DTC clear is substituted.

CBS takes precedence over new diagnostic details and Easy/Advanced coding work.
Advanced and deferred safety-ECU coding are outside this task; that does not
exclude legitimate, source-proven CBS resets in controllers such as DSC.

## Preserve the implemented baseline

- `app/cbs.py`, `ui/cbs_panel.py`, MainWindow CBS workers/confirmation and the
  existing single protocol owner. Live read is currently an explicit **Read
  service status** action after connection; expansion alone does not issue I/O.
- Generated `coding_data/cbs_definitions.json`:48 definitions,47 current PRGs
  plus the missing historical D94 entry;40 primary roles and8 observational
  branches. Recount against current inputs before treating these as current.
- Native job decoding, CBS7 start/result handling, DSC_25 source-planned ordered
  side effects, durable journals, and the guarded plain-reset fallback when the
  optional exact DSC job is unavailable. Do not replace them with handwritten
  universal requests or broaden job grants.
- [Current CBS evidence](../docs/evidence/source-cbs-current-jobs-20261104.md),
  its paired JSON/provenance audit, [source-job work](source-job-assets-implementation.md),
  [PR18 corrections](pr-18-review-followup.md), spec26 B-CBS-R/B-CBS-W and D-58/D-29.

## Source investigation → implementation

- [ ] C1: Reconcile exact variant/software → job/version → CBS reader → owning
  controller → item/reset policy across the supplied release. Inventory every
  row, duplicate observation, missing dependency and disposition. Use REA on the
  service reset orchestration, especially `ABL_GEN_AS6100_CBS_RESET.dll`, its
  callers/dependencies and current PRG jobs/tables. Use decrypted database
  descriptions/rules when they resolve semantics or selection.
- [ ] C2: Trace the8 currently unresolved ownership branches: BCP_SP21, CMEDIA,
  DME8FF_L, EHC_01, GSGE01QW, LMV_01, MGU_02_A and S63TU_L0. Distinguish an
  intentional read-only copy from an actual reset owner. Implement every
  recovered applicable branch; retain exact source restrictions where proven.
  Job presence, address or successful read alone never grants reset authority.
  Investigate the missing D94 artifact/dependencies without falsely claiming
  that the restored release contains it.
- [ ] C3: Reconcile returned fields and versions against actual native jobs:
  units, signedness, status bits, service counters, availability, dates, distance/
  time forecasts, sentinel values and duplicate item IDs. Prefer existing decoded
  job results; preserve raw evidence. Never double-scale fields or turn an invalid
  record into a due value. Integrate recovered changes into generated assets.
- [ ] C4: Finish the foreground flow. Read/refresh/reset cannot overlap. Use
  loading indicators/backdrops and disable competing controls; retain settled
  results and visible failures. Make unsupported/observational/ambiguous items
  understandable. A rejected click must explain its reason. DEMO is labelled
  and cannot reset a vehicle. Do not add silent connect-time probes as a shortcut.
- [ ] C5: Reconcile each reset's actual preconditions, session/software/before
  checks, argument encoding, exact mutation sequence and completion decoder.
  Retain source-specific STR/RRR handling and DSC's two planned resets plus
  routine/event-control/fault-clear disclosures. No repeated mutation except an
  exact source-planned occurrence. Preflight, persist and execute under one owner.
- [ ] C6: Correct partial/uncertain handling and post-state presentation wherever
  evidence disproves current behavior. A start acknowledgement is not reset
  completion. Application-confirmed and observed post-state remain distinct;
  respect source cycle/reconnect instructions and source refusals. No automatic
  replay, counter rollback promise or “success” after a lost result.

## Required verification and exit

- [ ] Use all applicable current source readers/encoders as offline oracles.
  Reuse existing658 native read vectors as a baseline; extend only for missing
  branches/bugs. Check actual source byte boundaries and version differences.
- [ ] Cover absent/mismatched jobs, missing ownership evidence, duplicate owners,
  unavailable items, malformed/negative replies, NRC pending/deadline exhaustion,
  start-versus-result failures, software/before-state changes, connection loss,
  replay attempts and storage failure before/after each mutation occurrence.
- [ ] Exercise actual Qt manual read, expansion, refresh, single-item confirmation,
  power/side-effect acknowledgement, loading, read-only refusal and failure
  recovery. No hidden or enabled conflicting actions; no stale reset selection.
- [ ] Independently review, fix and run full preflight. Update source matrix,
  task/specs/assets and exact verification results. Do not close with research
  notes or a checkbox that merely says a worker exists.
- [ ] Retain an owner-F48 acceptance procedure: identify actual KOMB25/DME_BX8/
  DSC_I1 contracts, read current CBS, and only perform a separately owner-authorized
  appropriate reset after preflight. Record meaningful before/application/after
  or cycle observations. No gratuitous service reset for testing.

Implementation exit: all recovered in-scope branches integrated and independently
checked; source restrictions and any exact unfinished branches explicitly listed;
no invented ownership, false completion or unaccounted partial outcome. Physical
acceptance has its own status, not an all-car claim or a reason to stop source
implementation. Another vehicle is not a dependency.
