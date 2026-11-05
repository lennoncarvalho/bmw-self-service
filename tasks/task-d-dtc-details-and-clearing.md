# Task D — DTC occurrence details and complete clearing coverage

Priority: after Task C. Status: planned source-led implementation.
Apply [the shared C–F workflow](task-c-through-f-roadmap.md).

## Goal and baseline

Read the connected vehicle's supported diagnostic memories and show the actual
source-provided circumstances of a fault: occurrence mileage in kilometres,
time/date when genuinely provided, occurrence counters and other environment
values. Keep every read fault visible regardless of description language. Make
Clear All's target/memory coverage and post-clear results complete and honest.

Preserve `app/diagnostics.py`, `app/ista_jobs.py`, `ui/diagnostics_page.py`, the
exact identity/memory catalogues and `app/diagnostic_texts.py`. Live records
currently expose code/status/text/presence/source but no occurrence time/km.
Clear All already handles supported fault/information targets and rereads them;
permanent memory is read separately, without a separate permanent-erase action.
This is extension/reconciliation, not a new diagnostics stack.

Read spec26 B-DTC-R/B-DTC-W, docs20/21/27, current source database/job evidence,
[owner capture](../docs/evidence/task-b-owner-session-20261029.md), and existing
diagnostic breadth/recovered-contract records. Historical capture limitations
are not current universal vehicle restrictions.

## Source investigation → implementation

- [ ] D1: Inventory actual diagnostic readers and result sets by exact ECU/
  software/memory. **First inspect data already returned by FS_/IS_ jobs.**
  `fault_records()` currently projects only a small subset; preserve/reuse
  available source fields before adding any request.
- [ ] D2: Use REA on source diagnostic selection/orchestration and current PRGs
  to recover environment/detail/snapshot/extended-data paths where separate jobs
  are required. Inspect decrypted databases and associated tables for field
  names, units, type/scaling, applicability and descriptions. Trace exact job
  arguments and response decoders; do not guess record numbers or sweep DIDs.
- [ ] D3: Distinguish first/last occurrence, current mileage, stored occurrence
  mileage, elapsed/operating time and calendar timestamps. Recover epochs,
  units, offsets and invalid sentinels from sources. Do not label a counter as
  a date, use the current clock as occurrence time, or substitute the overview
  odometer for fault-event mileage. Unsupported fields remain explicitly absent.
- [ ] D4: Extend the normalized result model and expandable Qt fault cards with
  proven fields, units and provenance; retain raw detail data needed to explain
  decoding and source discrepancies. Prefer complete, agreeing English text and
  then coherent available source-language text under the latest owner decision.
  Missing/ambiguous translations never remove or conceal a code.
- [ ] D5: Reconcile fault/information/permanent categories, status semantics,
  inventory completeness, per-target failures and budgets. Catalogue candidates
  do not establish installed topology. Empty partial reads never mean a healthy
  whole vehicle. Reuse jobs/fallbacks and the existing protocol owner.
- [ ] D6: Audit Clear All against every in-scope source branch: applicability,
  exact granted request, application result, readback and remaining faults.
  Continue after definite ECU-local rejection on a usable stream; account for
  unattempted targets after ambiguous/lost transport. Do not claim deletion of
  unsupported memories, promise permanent faults disappear, or introduce per-code
  clearing, report-backup prerequisites or unrelated mutations.
- [ ] D7: Make foreground scans/clears use clear loading and blocked competing
  actions. Preserve completed page batches, visible rejected/unavailable states
  and shared engine indicator behavior under D-59. No language-dependent MIL
  or success inference and no generic scan before a detail contract is known.

## Verification and exit

- [ ] Actual source job/result fixtures cover multiple ECU families and memories;
  prove first/last/time/km meanings, units and sentinel boundaries. Retain a
  decoder matrix that identifies fields not supplied by a branch.
- [ ] Exercise untranslated and empty descriptions, malformed/truncated details,
  conflicting records, pending/negative responses, deadlines, transport loss,
  partial scans and post-clear faults still present. No invented timestamps.
- [ ] Visually check long/expanded fault details at narrow/wide sizes with one
  outer scrollbar; read/clear lockout and visible source/coverage states.
- [ ] Independent review, fixes, full preflight and updated evidence/specs/task.
  Optional owner-F48 observations are recorded narrowly and require no deliberate
  fault injection or access to other cars. Real occurrence values are not inferred
  from synthetic fixtures.

Exit: source-supported detail fields reach the live UI, Clear All's applicable
coverage is accounted for, and exact missing source branches remain actionable.
Research-only output or a universal “time/km unavailable” placeholder is not
completion. Where a field is absent in the source contract, record that specific
restriction rather than fabricate it.
