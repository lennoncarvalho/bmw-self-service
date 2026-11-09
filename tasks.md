# Implementation tasks

Work in priority order. Update these steps in place when the implementation
changes; remove completed detail instead of appending session or PR reports.
Current source contracts and reproduction routes are in [docs.md](docs.md).

## CBS — complete for the current milestone

Implemented: manual native reads, strict record accounting, software/identity
preflight, exclusive foreground reset execution, durable journals, source-specific
DSC and routine sequences, stale-row reset revocation and uncertain-outcome
lockout. D94 now has an explicit historical job supplement and native start,
one-second delay, result query and post-read. Source selection is reconciled:
the eight additional readers are outside the standard workflow's primary groups
and remain observations. Same-item records from different primary ECUs retain
explicit owner selection; duplicates within one ECU stay blocked. Compiler,
native-worker, fragmented protocol-owner and Qt checks cover these boundaries.
Captured distance sentinels are suppressed in both native-result and fallback
decoding. Other source-supported owners retain offline verification; this is
not universal vehicle acceptance.
No implementation or owner-car acceptance step remains open for this milestone.

## Diagnostic details and clearing — source implementation complete

Implemented: native fault/information detail jobs selected by fault code,
occurrence/healing counters, recorded mileage/time and source-scaled environment
values in always-visible cards. Preserve every recorded state, source units and raw
results. Time counters have no invented calendar epoch or first/last labels.
Basic lists settle before bounded details; failed details retain collected codes.
Native optional-table trap handling supports environment decoding. Offline native,
worker/error and Qt checks cover these boundaries; physical behavior is unverified.

Memory coverage follows the loaded variant's readers, including permanent memory;
native record accounting retains partial codes without claiming a complete scan.
Clear All includes every target disposition, continues after definite rejection,
stops on uncertainty/stream failure, and preserves reread counts and remaining
faults. UI outcomes survive refreshes, with thread-exit lockout and no automatic
retry or reread after a stopped batch. Native, fragmented/pending protocol-owner,
failure and Qt flows are verified offline; no physical clearing is claimed.

## Easy Coding readiness

- [ ] Resolve the observed coding-page timeouts and subsequent outstanding-request/
  reconnect errors. Investigate source contracts and offline behavior first. When
  missing live request/reply or timing evidence blocks a concrete diagnosis, ask
  the owner promptly for a focused car session with exact reproduction steps and
  session logs from the app's `logs/` folder. Use that evidence to avoid repeated
  speculative coding iterations; confirm the fix against the captured failure.
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
