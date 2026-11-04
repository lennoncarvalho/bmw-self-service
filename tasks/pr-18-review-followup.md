# PR 18 review follow-up

## Coding catalogue and snapshot review

Both reported findings are valid in the current code:

- Dynamic lighting selects a module position but indexes the source parameter's
  value list by that position. Source values carry explicit `position`; ordering
  and sparse lists must not change the encoded value.
- Preset discovery runs after a complete snapshot is saved inside the same
  exception boundary. A later metadata error incorrectly changes the row to
  incomplete despite its durable, verified backup.

Implementation plan: resolve the selected source value by explicit position,
reject missing/ambiguous positions and retain live vector bounds. Settle the
snapshot state after successful persistence, then isolate preset discovery while
retaining existing per-option behavior and any already discovered options.
Verify reordered/sparse/missing/duplicate source values and post-save metadata
failure with offline bytes and actual snapshot worker execution; no test suite
or asset rebuild is needed.

### Implementation and verification

- `app/coding_db.py`: selected `DRL_Idx` values are matched by their explicit
  source position. Exactly one match is required; the existing live matrix
  bounds remain mandatory. No catalogue asset changed.
- `app/coding.py`: complete state is published only after durable preparation
  and the verified snapshot event succeed. Later preset metadata failures retain
  that state, baseline, backup path and already discovered options, with an
  explicit options-unavailable notice. Existing dynamic-option fallback remains.
- Added accurate docstrings to every previously undocumented function in these
  two files, including nested reader and dynamic-lighting helpers. AST inventory:
  6/6 and 42/42 functions documented, respectively.
- Offline actual-source fixture `000024C3-008-005-000` still roundtrips 79% and
  100%. A generated source-style parameter fixture selects module position 2,
  value `0x01`, independently of reordered neighboring bytes. Sparse values
  succeed; missing/duplicate selected positions and short live vectors fail.
- Actual `CodingSnapshotWorker` plus actual `OperationStore` exercised metadata
  failure immediately after saving and after one good option. The real JSON
  records remain verified with original group `3000: 01`; complete backup paths
  and prior options remain visible. Incomplete reads and failed persistence
  still report incomplete and publish no backup path.
- One-off scratch verification: `/tmp/check_pr18_coding_fixes.py`; no `tests/`
  directory or asset rebuild. Scoped Ruff check, Ruff format check and mypy pass.
  Parent owns the mandatory final full-app preflight before pushing.

## Remaining review findings and dispositions

Verified against the current PR code before edits; pasted code, paths and review
instructions were treated as review data rather than execution authority.

Valid findings fixed:

- DSC acknowledgement now explicitly discloses the two planned reset writes;
  previous fault-clear, routine and event-control warnings remain intact.
- Live selections reveal/hide the action bar and retain the reading-state write
  guard. Post-accept state races leave a clear retry message and recover the
  review action without starting a mutation.
- Removed module-level coding database construction. Import/window startup work
  with a missing coding catalogue; DEMO exact-definition lookup is lazy and its
  existing error handling remains in place.
- Corrected source-guide key pointer and opened/extracted diagnostic database
  status, retaining the uncertainty about additional named preset coverage.
- DTC extraction requires an explicit PRG directory only with `--extract`;
  statistics/translation modes keep their original argument behavior.
- Aggregate build rejects a mismatched diagnostic catalogue before producer or
  output work and propagates an explicit development job-parser path. History
  parser and MIL ECU directory are caller inputs rather than branded defaults.
- Staging cleanup preserves the triggering exception. Bundle publication records
  an atomic, manifest-bound recovery marker before moving the old directory;
  runtime/status lookup recovers exactly that generated bundle if interrupted,
  including repeated crashes with multiple old siblings. No source-folder
  fallback or newest-directory guess is introduced.
- History asset/evidence publication restores prior bytes (or removes a newly
  created output) when evidence publication fails. Rollback failures propagate;
  evidence and aggregate manifest remain unchanged in injected failures.
- Removed the generated directory name from the runtime asset module docstring,
  preserving the actual directory, constants and manifest references.
- Added accurate missing function docstrings. The remote report was60.70% with
  an80% threshold for touched functions of complexity>=2. A local changed-range
  AST audit now documents all201 selected functions. This is a local audit,
  not a claim that the external service has rerun or uses identical selection.

Skipped after verification:

1. `runtime_label` hardcoded matcher strings: this is a development-only
   sanitizer, not shipped code. Those names are deliberate match/rejection
   inputs that prevent branded instructions entering runtime labels. Verified
   existing XML resources expose the source app name and a companion product,
   but do not provide an established interface for the complete forbidden-name
   list. Moving strings to invented configuration or weakening detection would
   not be a valid minimal fix; existing adaptation/detection is retained.
2. Renaming imports in the job-data dialog: these are existing internal module
   paths, not external executable/service dependencies. Aliases cannot remove
   those paths from source; changing them requires a repository-wide module/API
   migration. Left names intact rather than make a cosmetic alias-only change.

## Verification

- Actual source dynamic-light matrix79/100 round trip; reordered/sparse selected
  position, missing/duplicate position and short-vector cases. Actual snapshot
  worker/store preserve verified baseline/path across immediate and later-option
  metadata failures; read/save failures remain incomplete.
- Actual Qt MainWindow import/startup with coding database construction forced
  to fail; visible pending bar, reading lockout and overview-refresh race after
  dialog acceptance. No car requests. Existing full coding/restore UI harness
  still passes157 synthetic requests, power/restore acknowledgements and lockout.
- Builder failure injection: OSError/KeyboardInterrupt staging cleanup, abrupt
  process exit during publication, successive interrupted builds with multiple
  previous bundles, traversal/wrong-hash marker rejection, history old/no-output
  rollback and rollback failure propagation. Prior manifest/evidence sentinels
  remain unchanged. Runtime recovery and status lookup use the same bundle.
- Actual explicit-parser generation validates all12 history profiles and emits
  runtime bytes identical to the current asset. Explicit empty MIL directory
  produces62 missing-definition dispositions; no implicit source path used.
- Mismatched catalogue rejected before output/producers; matching catalogue
  reaches producer. `extract_dtc.py --extract` without a directory reports an
  argument error; `--stats` still runs without a PRG directory.
- Full app preflight and scoped builder Ruff checks pass; final gate is rerun
  immediately before push. No tests/ directory or real vehicle access.

## Other existing remote checks inspected

The separate Robin review job stops because the complete diff exceeds its
200,000-character configured limit. CodeQL flags the development-only SHA-1
licence passphrase derivation in `recover_cafd_assets.py`; that algorithm is
required by the supplied file format, not a new application password-storage
scheme. Neither check is disabled, silenced or reconfigured by this review fix.

## Second review batch — plan

Verify the newly supplied findings against the current code. Preserve the DSC
plain-reset source gate when an exact optional job is unavailable; keep unmapped
coding categories unknown; enforce D-43 English-only normal text lookup. Make
selection evidence mandatory in the builder CLI, bound source reads before
allocation and require independent CBS ownership entries. Bind export completion
to the actual originating report across disconnect/reconnect, prevent overlapping
snapshot/preparation, reset selected-page scrolling and make restore preparation
visible. Exercise focused offline/Qt and failure cases before the full gate/push;
no test suite or protocol guesses.

### Second batch results

All ten new findings were still valid and were fixed minimally; none skipped.

- DSC optional extra-job metadata failures return `None`, allowing only the
  pre-existing SVK/fixed-record gate to authorize a plain reset. Unknown/unsafe
  extra branches remain blocked; exact supported jobs retain their full sequence.
- Nonempty series tags with no recovered category mapping return unknown,
  including category0. Mapped categories, mixed tags and existing exclusions
  retain their established behavior.
- D-43 English lookups no longer return German when English is absent. Explicit
  German requests are unchanged; this applies to descriptions and ECU titles.
- CLI selection evidence is required. Encrypted definition source files are
  size-checked before reads (strictly positive and at most2×MAX_XML). Current
  CBS overlays require a corresponding independent ownership table entry.
- Export workers keep a GUI-only reference to their originating report and a
  detached background payload. Successful completion marks that original report
  even after disconnect clears the current worker; an older export cannot mark
  a newer report. Snapshot activation now refuses overlapping page work while
  retaining the uncleared-reader guard.
- Main-page navigation resets the outer scroll position after page selection.
  Backup restoration switches to Coding, selects its navigation tab and resets
  scrolling before invoking preparation, so its existing progress is visible.

Focused verification (outside the repository; no suite):

- `/tmp/check_pr18_cbs_category_review.py`: actual CBS worker/journal plain-safe
  and unsafe paths for absent extra sequence/job/hash; no86/31/14 emitted by
  fallback; read-only zero-I/O; exact six-step metadata retained. Unknown-only,
  mapped/mixed/category0 and exclusion predicate outcomes checked.
- `/tmp/pr18_review_batch2.py`: required CLI input rejects before output,
  pre-read size hooks reject zero/oversize without reading, inclusive boundary
  reaches parsing, missing ownership tampering preserves prior output, and
  explicit nonprimary ownership remains blocked. Actual CBS regeneration is
  byte-identical. `/tmp/pr18_one_cafd.py` decrypts an actual supplied CAFD to
  75,908 XML bytes with the size guard in place.
- `~/BMW-Tool/investigations/source-runtime-20261104/pr18_batch2_ui_check.py`:
  actual threaded export completion after MainWindow disconnect marks origin;
  older export after reconnect leaves a replacement report untouched; active
  preparation/uncleared reader prevent snapshot allocation; two long pages
  reset scroll to zero; restore visibility precedes invocation; mutation blocks
  restore navigation. Zero vehicle requests.
- Independent `/tmp/review-pr18-final-ui-text.py`: stalled actual QThread export,
  detached payload snapshot, report identity, Qt navigation/restore ordering and
  English-missing/German-request SQLite fixtures all pass. No actionable findings.

No runtime asset bytes, cryptographic contracts or vehicle storage requirements
were changed by this review batch. Full preflight is rerun before push.
