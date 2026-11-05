# PR 20 review follow-up

The six supplied findings were checked against current code at `bc30ad0`.
All are valid; the native cleanup finding belongs to
`native/ediabasx/platform/posix/loaders.c:load_prg_from_dir`, not `src/prg.c`.

## Minimal correction plan

- `app/cbs.py`: collect available software provenance for observation sources
  while retaining primary-only reset authority; report journal preparation
  failures with `persistence_failed` before any vehicle request.
- `native/ediabasx/platform/posix/loaders.c`: release partially parsed PRG-owned
  buffers before freeing the struct on parser failure.
- `scripts/recover_cbs_definitions.py`: normalize reset identifiers before
  validation/reserved-item checks and emit canonical uppercase values.
- `ui/cbs_panel.py`: merge fresh successful-owner rows with explicitly stale,
  non-resettable failed-owner rows; clear the busy state on panel reset.

Use focused offline native/compiler/worker/Qt checks, rebuild the native library
and update its runtime manifest entry, then run the full app quality gate.
No source wire contract, reset grant, dependency or automated suite is added.

## Corrections and verification

All six findings were fixed; none was skipped. The file-location correction
above does not invalidate the native finding.

- Eight actual native observational readers now retain the `22 F1 01` software
  response/provenance. Every observational reset remains refused, including a
  forced resettable selection. An observational software failure does not block
  a unique proved primary owner. No reset role, encoder or grant changed.
- `load_prg_from_dir` calls `edxn_prg_free` on parse failure. Allocation-tracked
  actual native parsing was exercised through both public POSIX loaders: 40
  failures after decoded-buffer/job allocation return to zero live allocations.
  A successful BCP_SP21 load retains all 1,844 tables and frees cleanly too.
- The compiler emits uppercase reset identifiers and rejects `e0`, `e1`, `ff`
  as well as their uppercase forms. Current canonical inputs regenerate a
  byte-identical CBS asset, so no vehicle definitions were rebuilt unnecessarily.
- Actual Qt partial refreshes preserve a failed owner's prior values with a
  stale note and `resettable=False`, while a successful owner's fresh row and
  permitted action update normally. Repeated partial/all-failed reads do not
  duplicate stale notes; a later successful empty owner response removes stale
  rows. Incoming results are copied, old queued clicks are rejected, and panel
  clear/disconnect resets busy state, values, actions and labels.
- `CbsJournalStore.prepare` filesystem/validation failures return a not-started,
  persistence-failed report before any vehicle request. Actual CarWorker/Qt
  delivery sets `_cbs_reset_blocked`; the existing automatic reread still runs
  and cannot re-enable reset buttons. Both failure types remain one-shot.
- Existing actual Qt native-worker flows and all seven fragmented real-owner
  loopback scenarios pass again. No physical car traffic or reset was performed.
- Rebuilt the universal arm64/x86_64 native library with the existing warning-free
  `-Werror` build and updated its runtime manifest hash. Full app Ruff lint,
  Ruff formatting and mypy pass over all 52 files; the modified compiler's
  scoped Ruff lint/format checks pass too. No automated suite was introduced.

Retained one-off checks/results/screenshots:
`/Users/lennon/BMW-Tool/investigations/pr20-review-20261105/`.
