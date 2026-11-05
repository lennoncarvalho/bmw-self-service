# Standalone source-derived runtime — 2026-11-04

Owner direction: recover how supplied applications communicate with cars, reuse
extracted/decrypted databases and executable jobs, and generate runtime assets
during development. No runtime lookup in `sources/`, no per-option car trials,
no guessed protocol constants, no required physical-car access. Scope includes
popular source-supported BMWs, DTC read/clear, history writes, CBS read/reset and
easy coding. No PR creation is authorized.

## Plan before implementation

1. Audit actual runtime data use and retire encrypted-file scanning/first-variant
   assumptions in coding consumers. Build a versioned decrypted catalogue asset
   from supplied definitions, labels and model mappings, with exact provenance.
2. Build the existing native PRG interpreter and source-derived job bundle.
   Verify popular-platform coverage offline and fix concrete portability/data
   issues without creating another protocol stack or VM.
3. Use REA to trace missing model/ECU selection, coding layout/authorization and
   ISTA text database access. Implement only supported contracts; leave precise
   unresolved branches visible without declaring them permanently unsupported.
4. Integrate catalogue-backed coding reads and current values into the UI and
   snapshot store, retaining real complete baseline bytes and exact versions.
   Do not enable the retired partial/guessed write encoder.
5. Review and exercise offline byte/error cases and actual Qt/DEMO flows, fix
   findings, update status/handoff and run full app preflight. No tests/ suite.

Independent delegated work: coding catalogue/loader, native/job assets, and
ISTA database access investigation. Root owns consumer/UI integration, cross-
module review, offline verification and handoff. No car traffic authorized.

## Source findings and corrections during implementation

- Restored job bundle contains 620 exact T_GRTB identities, all already present
  in the 1,307-row diagnostic catalogue. Integrating it provides independent
  source fallback, not 620 newly covered variants. 387 bundled PRGs expose
  fault/CBS/STATUS jobs; source availability is not universal physical validation.
- DiagDocDb is now actually readable with a development-only codec/reference
  access path. It is no longer an assumed inaccessible input. Generated plain
  text asset has 162,757 linked fault/info text rows and 1,227 ECU titles.
- Strict eight-hex-character coding roots contain 1,034 preset entries. The prior
  count 1,566 included non-CAFD eight-character metadata filenames. All 2,305
  source documents remain retained; distinguish raw file count and usable roots.
- Source-recovered F-series coding uses signatures, not generalized E-series
  block XOR checksums. Actual source class models.w is storage start/end/mask;
  do not infer checksum metadata from its name.
- REA confirms F101 tail role6 selects BTLD, role5 CAFD; CPS source is the VIN
  and its last seven ASCII characters. F-series s0.P filters DID3010; it is not
  a group-ordering algorithm. The data reader d.c/p.n sends22+source group DID
  directly. The separate u class is an unlock-code backup creator, not the
  general coding-data reader; its1003 preamble must not be generalized.
- Portable root REA records are retained outside the app/repo at
  `/Users/lennon/BMW-Tool/investigations/source-runtime-20261104/root-rea-evidence.json`.
  Source callbacks and encoder details remain implementation evidence, not proof
  of an actual vehicle operation.

## Implemented increment

- Development producers now build ordinary SQLite coding/text assets and the
  existing native job bundle. Runtime ignores source-folder preferences and
  cannot silently fall back to reference folders. `scripts/build_runtime_assets.py`
  orchestrates the producers and records every published asset's size/hash.
- Decrypted all 5,895 CAFDs and 26 FAFPs; imported 4,127 additional exact coding
  definitions. Three distinct CAFD v2 layouts retain explicit dispositions.
  Catalogue: 6,434 documents, 6,106 numeric CAFD versions, 1,034 root presets,
  3,074 labels and 2,829 authorization entries. Literal stripped source names
  remain stripped, rather than acquiring invented semantics.
- Runtime layout selection implements the recovered exact/same-major-minor
  lower-patch rule, with exact-source layout cross-checks and recorded reported
  versus selected identities. Composition uses actual groups, offsets/masks,
  duplicate-entry identities, combined definitions and source option predicates.
- Fresh complete snapshots, source authorization/signatures, easy coding,
  explicit restoration, retained interrupted-operation comparisons, durable
  before-send journals and global mutation lockout replace the old stub flow.
  The source climate critical-condition guard persists independently of DTC
  clearing and is rechecked before mutation. DEMO saves remain previews.
- Diagnostic text lookup now uses 162,757 actual linked source descriptions and
  1,227 titles, with exact ECU/code/memory matching and ambiguity handling.
- Generated job bundle covers all 13 supplied KIS families: 399 PRGs and 131
  GRPs, 592,028,562 bytes. Source catalogue fallback is separate from inventory
  observation, never a claim that all potential ECUs are installed.
- Current-source CBS asset has 48 definitions (47 present, historical D94 absent),
  with 40 workflow-established primary roles and eight observational branches
  whose ownership remains a concrete investigation. CBS7.0 start/result and
  DSC25 ordered side effects have explicit outcomes and acknowledgements.
- History contracts are generated from 14 exact head-unit source identities:
  12 expose the recovered ADD/ERASE path, including the new MGU02A/L branches;
  CICM/RAD12 do not expose these jobs. JSON-only local state/intent, fourteen
  service types, ADD-only append and explicit replacement remain unchanged.

## Verification and independent review

One-off scripts and outputs are retained outside the repository under
`/Users/lennon/BMW-Tool/investigations/`; no `tests/` or persistent suite was added.

- `source-runtime-20261104/coding_snapshot_check.py`: actual CarWorker and Qt
  source cards, all 14 KOMB25 groups and validated complete snapshot, source
  labels/current values. Audit hook denies source-folder/encrypted-file opens;
  none attempted. Fresh F150/F101 checks precede/follow the data reads.
- `source-runtime-20261104/coding_ui_check.py`: actual prepare/write/restore
  workers, source catalogue/keys and synthetic ECU replies; 157 requests,
  response-confirmed results, mandatory power/restore acknowledgements,
  `[true,false,true,false]` mutation signals and no GUI-thread car I/O.
  Visually inspected rendered source cards and restoration confirmation.
- `source-runtime-20261104/coding_facade_check.py`: actual connection,
  ProtocolOwner, Scapy, udsoncan and socket framing against a fragmented loopback
  gateway; 50 frames, source access denied, response-confirmed and zero errors.
  This is offline protocol verification, not traffic to a car.
- `source-coding-execution-20261104/`: actual complete coding/restore,
  ENTRYNAV reported003015037/source006 fallback, critical climate condition
  appearing after confirmation (zero coding writes), sticky guard and eleven
  rejection/interruption/recovery scenarios. Unsupported/tampered source plans,
  missing/changed current data and durable-storage failures stop further sends.
- Independently compared signing output with Java primitives across 27 usable
  source digest/width families. Rechecked all 2,305 original document hashes,
  multibyte/mask/conflict handling, combined definition lookup and actual
  dynamic lighting matrix79/100 round trips.
- Delegated source/catalogue and engine reviewers corrected primary-root and
  combined lookup, lower-patch selection, duplicate labels, F101 role selection,
  DME3010 exclusion, partial-coding group semantics, source signatures,
  recovery provenance/prior-record races and source guard behavior. UI review
  separately exercises global lockout, close refusal and evidence export.

Detailed evidence and unresolved source branches are linked from doc29 and the
source-specific task records. No physical vehicle operation, fleet validation,
Windows/package acceptance, public asset distribution, push or PR is claimed.

### Later source/review corrections completed in the same increment

- Recovered the actual head-unit entitlement list/retrieval/session cleanup,
  local-file verification, and NBTEVO I-level/RAM/HMI gates. A separately compiled
  `reader_contracts.json` carries selectors, requests, layout and provenance.
  It is generated from retained same-APK REA records, never source reads at
  runtime. Entitlements are local separate files, not coding group baselines
  or an automatic upload/restore claim. Read-only sessions send none of these
  session/routine requests.
- Source-required sensitive reads use a worker-to-GUI Event handshake: GUI
  lockout precedes permission to change session and lasts until worker finish.
  Ordinary coding reads keep their existing behavior. The independent actual
  MainWindow harness verified this ordering and close/navigation refusal.
- Independent review found stale previous-page values in the confirmation;
  the preview now states the frozen intended choice without a false fresh
  before-value claim. It also found in-memory coding results could be lost on
  ordinary close after a storage failure. Normal close now routes to coding
  and requires successful evidence export; canceled/failed export retains them.
- Native signed-width handling was corrected in ASR/fixed-to-float: long
  registers are already signed, so shifting a32-bit modulus was undefined.
  Actual source history jobs now agree with the Python codec at signed minimum
  remaining distance and maximum unsigned mileage. Storage ranges were not
  narrowed. Native build publishes by atomic rename so loaded libraries are
  not truncated underneath active readers.

## Final gate and asset publication

After all source-reader/native/UI corrections, `scripts/preflight.sh` passed:
Ruff check, Ruff format check (51 files), and mypy (51 files). `git diff --check`
also passed. The aggregate build completed, and the later CBS/history/reader
producers were exercised separately after their final changes. Refreshed the
aggregate manifest only after publication; every one of its 556 entries matches
size and SHA-256. It contains generated assets/library, no source folder,
encrypted package, APK or JAR. Final native library SHA-256:
`10fb6d7cda60326ce7c2b213fc1bf83b3809e19fb76453fcbcc140e995030b22`.

Independent actual MainWindow checks cover both source-sensitive prepare and
write lockout, navigation/close refusal, unlock at actual thread completion,
unexported-results close refusal, successful evidence export, read-only/DEMO
zero-write and separate restore confirmation. Native CBS checks cover all47
current readers (658 source-layout vectors), seven CBS7 result scenarios, six
DSC sequence cases, persistence failures, owner/copy distinctions and source
integrity rejection. Twelve history profiles match actual source encoders at
signed-distance/unsigned-mileage boundaries and decode statuses0/1/2/4/5.

Remaining work is the concrete source queue in doc29, rather than a hardware
prerequisite for finishing these implementations. Generated personal databases
and job files remain ignored local assets; generators/provenance and the
already-tracked CBS contract are included in the code increment. No push or PR.

Final independent review also found nested snapshot prerequisite reads inherited
its 300-second owner context despite a30-second argument. Each now temporarily
caps the actual active deadline at30seconds (including fresh VIN), restores the
overall deadline in `finally`, and passes injected-failure budget checks.
Repeated full preflight after that fix: all three gates green, 51 files.

`source-runtime-20261104/demo_visual_check.py` ran actual async DEMO connection
with MockConnection, rendered Vehicle/Diagnostics/Coding/History and the bundled
job-data dialog with source-file access denied, and closed cooperatively.
Screenshots were visually checked. Coding's action remains Save DEMO preview;
no live coding writer was created and no mock/source file was modified.
