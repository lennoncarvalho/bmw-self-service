# Implementation tasks

Work in priority order. Update these steps in place when the implementation
changes; remove completed detail instead of appending session or PR reports.
Current source contracts and reproduction routes are in [docs.md](docs.md).

## CBS — current priority

Implemented: manual native reads, strict record accounting, software/identity
preflight, exclusive foreground reset execution, durable journals, source-specific
DSC and routine sequences, stale-row reset revocation and uncertain-outcome
lockout. D94 now has an explicit historical job supplement and native start,
one-second delay, result query and post-read. Offline/native/Qt verification and
independent review cover this implementation; physical observations are separate.

- [ ] Resolve primary reset routing for BCP_SP21, CMEDIA, DME8FF_L, EHC_01,
  GSGE01QW, LMV_01, MGU_02_A and S63TU_L0 through source orchestration, dynamic
  group selection and diagnostic database service-function rules. The examined
  transport/delivery callers do not establish those routes; do not repeat those
  same searches or treat encoder presence as ownership. Integrate any recovered
  route into the compiler, worker and UI with exact provenance and failure checks.
  Keep a specific source restriction where the source actually establishes it.
- [ ] Close any resulting read/reset integration defects before moving priority
  to diagnostics. Verify actual native jobs, response boundaries, owner ambiguity,
  storage loss, pending/deadline/connection failures, no replay and Qt lockout.
- [ ] When a useful owner-car session is needed, compare actual identified CBS
  owners/records with the vehicle display. A service reset requires a suitable
  service and separate authorization; lack of that test does not block source work.

## Diagnostic details and clearing

- [ ] Inspect fields already returned by `FS_`/`IS_` jobs before adding requests:
  `app/ista_jobs.py:fault_records()` currently projects only a subset. Recover
  separate detail/snapshot jobs only where needed from actual PRGs/callers.
- [ ] Decode and display source-supported occurrence kilometre/time/date/counter
  and environment values in expandable fault cards. Distinguish first/last event,
  elapsed/operating time and calendar time; recover units/epochs/sentinels. Never
  substitute current mileage, current clock or guessed record numbers.
- [ ] Reconcile fault/information/permanent memory coverage and Clear All results
  for every in-scope branch, including local rejection, tainted stream, unattempted
  targets and faults remaining after reread. Keep untranslated codes visible.
- [ ] Verify native result boundaries, partial scans, descriptions, pending/error
  paths and actual Qt rendering/loading; review and run full preflight.

## Easy Coding readiness

- [ ] Enforce the owner's deferred/unvalidated safety-coding scope in UI and
  prepare/write/restore paths, including imported plans/backups. Recover actual
  ECU roles/option semantics; unknown classification is not authorization.
- [ ] Gather applicability context in CarWorkers and evaluate source model,
  category, exact variant, headunit and exclusion predicates before selection.
  Explain inapplicable/unknown/deferred choices instead of failing silently later.
- [ ] Reconcile the complete named source catalogue and actual current values,
  combined definitions, duplicate names, dynamic matrices, masks, Custom values
  and conflicts. Retain source primary ordering and proven lower-patch selection.
- [ ] Recover the `codingArea/sigId/sigLen` layout for CAFDs
  `000058AA-001-001-001`, `000058AA-001-001-002`, `00005C0A-049-001-020`;
  finish applicable non-deferred semantic mappings. Trimmed `.` names cannot be
  recovered by renaming positions. Investigate selected empty/EC authorization
  entries without choosing another key or guessing credentials.
- [ ] Verify live baseline/current decoding, exact signatures/requests, reader
  prerequisites, critical guards, application completion, required cycles,
  explicit restore and interruption recovery. Review, exercise Qt and run preflight.

## History and integrated acceptance

Implemented: local JSON editor/workspaces, sourced service types and multi-item
cards, separate journals, append/replacement workers and exact headunit contracts.

- [ ] Reconcile current supported headunit selection, encoder widths/business
  results, pacing and activation against source jobs. No new history reader.
- [ ] Exercise local create/edit/import/export, VIN binding and DEMO/live/session
  switching. Preserve conflicts/unknown fields and keep imports non-executable.
- [ ] Verify ADD-only append and explicit nonempty replacement; inject failures
  around ERASE, every ADD and activation. Persist intent/results, stop later
  mutations after uncertainty/persistence loss, export retained evidence, no replay.
- [ ] Exercise connection/refresh/loading/shutdown across all features under one
  owner. Fix competing operations, stale state and misleading success/recovery UI.
- [ ] Review, run full preflight and collect only the owner-car observations that
  can answer specific remaining questions. Record actual identities and results;
  do not induce faults or perform destructive writes just to complete a checklist.

Later: full-width DoIP feature addressing/newer releases, Advanced Coding,
validated deferred coding targets, Windows/Intel Mac and packaged releases.
