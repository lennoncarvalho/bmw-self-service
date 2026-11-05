# Standalone job assets — 2026-11-04

Current runtime policy: **generated bundle only**, including when old source-folder
preferences exist. Explicit folder providers are development extraction helpers.
The final bundle includes every available source KIS main-series list; the early
compact-build checkpoint below records the initial verification, not final scope.

Owner direction: reuse supplied executable ECU jobs and extracted model tables,
without runtime lookup in `sources/`. This increment owns the existing native
build, bundle builder and data-provider boundary; no new VM or car operation.

## Plan

1. Rebuild the existing native interpreter and the source-derived common-model
   bundle from the restored ISTA 4.29 tree.
2. Inspect provider/build behavior for source dependencies and incomplete bundle
   verification. Correct concrete failures while preserving optional user-folder
   fallback and one protocol owner.
3. Run real PRG jobs offline using only generated bundle/native library, with
   source paths hidden from the data source. Check model mappings, dependency
   closure, tampered/missing asset handling and non-checkout working directory.
4. Record exact bundle/library identities, coverage, remaining VM limits and
   gate results. No physical-validation claim, tests/ suite, push or PR.

## Implemented and checked

- Built `native/build/libedx.dylib`: universal arm64/x86_64, existing compiler
  flags include `-Wall -Wextra -Werror`. No native source/VM modification.
- Built standalone `ista_bundle/`: 507 job files (387 PRG,120 GRP), 579,980,549
  job bytes; model lists for F020,F025,F056,S15A,S18A map all nine requested
  common-model codes. Output contains data/jobs, never the source executable.
  Exact sizes/hashes/source provenance: `docs/evidence/source-job-assets-20261104.json`.
- Builder now checks the supported release, refuses ambiguous stems, uses unique
  staging directories, and restores the previous bundle if publication fails.
  Reference-folder names are omitted from the generated runtime manifest.
- Bundle provider bounds and validates manifest paths/sizes/digests; native
  table/USES dependency files must all be manifested, present and unchanged.
  Verification is lazy on first job lookup and cached by file identity/mtime.
  Model JSON hashes are checked too. Invalid providers produce explicit logged
  data errors; they do not authorize an unlisted job.
- Added `IstaDataSource.uds_variants()` from the checked bundled group table,
  preserving exact address+three-byte index identity. Folder fallback remains
  explicitly selected, not an automatic `sources/` lookup. 620 exact mappings;
  conflicts/invalid rows rejected, provider precedence explicit.
- Native loader parsed all 387 bundled PRGs with no load failures. Available job
  counts: FS_LESEN383,FS_LOESCHEN383,IS_LESEN380,IS_LOESCHEN372,
  STATUS_LESEN377,CBS_DATEN_LESEN43,CBS_RESET47. Job existence is not per-car proof.
- Executed INFO/FS_LESEN/CBS_DATEN_LESEN from actual bundled DME_BX8,KOMB25,DSC_I1
  PRGs against synthetic offline responses. Started from `/tmp`; Python audit
  hook rejected any original `/sources/` access. No vehicle traffic.
- Checked tampered/missing/unlisted jobs, path-escape manifests and conflicting
  identity rows: rejected. Verified model aliases F48,F20,F30,F15,F25,G20,G30,G05,G01.
- Independently checked root's identity integration: all1307existing diagnostic
  rows are preserved; with that older catalogue absent, all620job-table rows
  still identify exact addresses/indices. These620already exist in the older
  catalogue, so this is source independence/resilience, not new variant coverage.
- Scratch checks/results retained outside the repository at
  `~/BMW-Tool/investigations/source-job-assets-20261104/`.

## Remaining concrete limits

- The initial compact selection lacked86names; the final all-source selection
  lacks94names referenced by selected group
  assignments, plus USES `_bfh_ext`, `_bfs_ext`, `_cas4`, `_fah_ext`, `_fas_ext`.
  These are explicit manifest gaps; do not claim every named variant executes.
- Current packaged build examples need the generated `ista_bundle/` plus
  `native/build/libedx.dylib` at bundle root (`libedx.so` on supported POSIX).
  Source launch is standalone now; no packaged acceptance run occurred.
- Existing VM small string registers, frequent-mode/functional requests and
  nominal adapter voltage behavior remain documented limitations; no new VM was
  invented here. No physical validation is claimed.

## CBS continuation plan

The restored KOMBSP21 PRG disproves the former reset-unavailable assertion:
its jobs include `STATUS_CBS_DATEN_LESEN` (CBS7.0) and `CBS_RESET` (routine1000,
STR/RRR). Recover exact result fields, record length, routine arguments and
application codes using current PRG jobs/listings and REA ABL CIL evidence before
enabling this branch. Existing D94 6.3 routine support is already implemented;
do not repeat it. Inspect DSC_25's gated extra path and record every mutation
and fault-clearing side effect in frozen intent before execution. Root owns UI;
communicate any additional acknowledgement and preflight fields it must show.

## CBS continuation implemented

- Current-source KOMBSP21 read/reset now consumes its actual CBS7.0 job results,
  runs source STR/standard then RRR with exact completion/application checks,
  preserves raw before/after records, and requires the exact generated job hash.
- DSC_25's sourced conditional sequence now runs through the existing native
  job, with explicit extra-side-effect acknowledgement, current hash and frozen
  exact occurrence list. The second identical reset is explicitly planned;
  wrong-position repeats remain blocked. Fresh job preconditions must match the
  checked bytes before the first mutation. No automatic cleanup/replay.
- JobBackend accepts an optional exact ordered occurrence list plus callbacks
  for durable sending/result records. Existing single-use behavior is unchanged
  when no ordered list is supplied.
- Concrete source data moved into the generated CBS asset: DSC software gates,
  item positions, extra sequence and CBS7.0 return-code tables. Runtime only
  loads generated assets, never original PRGs in sources/. Current contract and
  reproduction command: docs/evidence/source-cbs-current-jobs-20261104.md/json.
- Six actual-PRG CBS7.0 worker scenarios and six DSC worker scenarios passed,
  plus ordered-repeat refusal; checks retained outside repo. Existing generated
  DME_BX8/KOMB25/DSC_I1 read/fault checks still pass. No physical traffic.
- Root owns the narrow raw86 controls and confirmation UI; this branch requires
  `dsc_extra_acknowledged` before the extra source path can run.

## Runtime bundle-only correction plan

The latest owner clarification supersedes D-62's runtime folder fallback. Keep
explicit FolderProvider/from_paths APIs for development extraction only, but
runtime data_source()/from_settings() must ignore stale source-folder settings.
Replace the source-folder chooser with generated-bundle status. Verify with a
Python audit hook rejecting sources access, stale QSettings and absent bundle:
missing generated assets must remain explicitly unavailable, never fall back to
research/source folders. Root owns the decision/handoff amendment.

## Final standalone runtime and broad source bundle

- Runtime `data_source()` and `IstaDataSource.from_settings()` ignore source-folder
  settings entirely. The old startup compatibility hook only clears bundle
  metadata cache. No validation, listing or open of the saved folder occurs.
- The ECU Job Data dialog is now read-only bundled-data/interpreter status with
  Refresh and Close, without source folder choose/clear controls. It distinguishes
  manifest metadata from integrity validation and library existence from actual
  compatibility. Present/missing screenshots were visually checked.
- Added `--all-source-series`, mutually exclusive with explicit `--series`.
  Selection comes from the available KIS directories rather than another model
  list. Default compact builds remain available for development compatibility.
- Final all-source bundle: 13main-series lists,530jobfiles (399PRG,131GRP),
  592,028,562jobbytes,134namedgroupreferences. All399PRGs load in the existing
  native interpreter. FSread/clear395each; ISread392/clear384; STATUS389;
  CBS_DATEN_LESEN43,STATUS_CBS_DATEN_LESEN4,CBS_RESET47. Source K/R metadata in
  this corpus does not add product support or physical validation.
- The source release lacks94referenced job names and five USES dependencies;
  these remain explicit in the generated manifest. No source folder fallback
  conceals a missing generated asset.
- With stale QSettings pointing at the original sources, monkeypatched setting/
  validation helpers that raise, and audit hooks rejecting all sources opens,
  listdir and scandir: runtime jobs/table identities still use the bundle. With
  bundle absent, data_source/from_settings return no providers, JobBackend
  explicitly reports unavailable, and the status dialog shows missing data.
- Checks/screenshot script:
  `~/BMW-Tool/investigations/source-job-assets-20261104/runtime-bundle-only-check.py`.
  Exact final bundle/library identities and inventory are in
  `docs/evidence/source-job-assets-20261104.json`.
- Additional CBS checks: negative result query after acceptedCBS7start remains
  uncertain; disk failure after accepted start retains raw evidence in memory,
  closes the connection and sends no results query or further reset.

No physical I/O, source application execution, commit, push or PR performed by
this delegated work. The root task owns final integrated preflight and review.

## Concrete native-width correction

The history signed-minimum discrepancy was traced to `asr` opcode0x18:
`1u << (len*8)` shifts a32-bit value by32 when a long register is used, then
subtracts from an already-signed int32. The fix2flt0x68 path repeats this undefined
shift/sign-extension error. Correct32-bit registers to use their already-signed
value; retain explicit sign extension for shorter registers. Build the library
through a temporary output and atomic rename so active mapped copies are not
truncated. Recheck exact signed-boundary history frames and all CBS/native paths.

## Final provenance, breadth and native verification

- Reconciled all original44 CBS definitions with the restored release:23 identical,
  20 changed,1 absent (D94). Recovered47 current readers and retained48 definitions
  including the explicitly historical D94 row. All47 readers passed14 native
  vectors each (658): calendar/count/availability, forecast sentinels, units and
  status fields. Corrected legacy status-bit normalization and current7.0 units.
- Recovered source reset ownership from the CBS reset application's groups and
  exact variants. All rows now require that proof:40 primary,8 observable copies
  whose primary write-owner route remains an explicit source investigation. A
  response plus a generic reset job does not establish ownership. Reader copies
  do not block a unique proved primary owner; competing proved primaries do.
- Expanded history contracts from10 to12 exact source profiles (MGU_02_A/L), with
  all14 sourced service codes, multi-item serialization, status decoding and
  default/reset responses checked. CICM/RAD12 expose no ADD/ERASE and remain
  excluded. Encoder fingerprints prove the new branches share the retained
  implementation; historical source hashes were not relabelled.
- Fixed the native ASR/fix2flt32-bit undefined shift/sign-extension issue. Both
  architectures built;13 direct actual-library width cases and all12 history
  profiles now pass signed minimum, negative exact256/65536 multiples and U32
  mileage maximum. This resolves the previously recorded native oracle limit.
  The source encoder/Python contract did not change to accommodate the bug.
- Fresh-process post-build verification passed generated DME_BX8/KOMB25/DSC_I1
  fault/CBS jobs and asset-integrity refusals; CBS7 seven outcome/replay cases;
  DSC six sequence/ack/error cases and out-of-order repeat refusal. No physical
  traffic or source application execution occurred.
- Independent actual MainWindow harness passed source selection, global write
  lockout, synchronous sensitive-session permission after GUI lock, close refusal
  during work, finish-only unlock, retained-result close refusal/export gate,
  read-only/DEMO zero-write and distinct restore confirmation. Scratch checks and
  screenshots remain outside the repository; root owns integrated final gate.
