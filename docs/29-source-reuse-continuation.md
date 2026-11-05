# Current source reuse and continuation — 2026-11-04

Owner direction: recover how supplied applications communicate with cars, reuse
their definitions/databases/jobs, and generate standalone runtime assets during
development. Disclose concrete limitations; do not change the product to fit an
assistant. This is the current handoff; older checkpoints are historical.

## Runtime and source boundaries

D-68 supersedes D-62's runtime source-folder fallback. The app uses generated
assets only, including when old settings point at a source folder. The ECU Job
Data dialog displays bundled-data status; it does not select reference folders.
REA, source applications, decryption tools, licences and JARs are development-only.
The embedded native interpreter executes the copied job assets through CarWorker
and the existing protocol owner; it never opens a second vehicle connection.

Canonical development input: `sources/ISTA_4.29.1x/Rheingold/Ecu/`.
The legacy `sources/Ecu/` collection is currently present. The explicit,
hash-bound D94 development supplement is selected from it without replacing
canonical files or restoring runtime folder fallback. Historical evidence retains
old hashes and offsets; compare actual bytes before reusing it. Do not relabel
changed artifacts.

Preserve ISTA 4.29/HSFZ scope (D-60), personal use (D-63), CBS before coding (D-58),
labelled reads/strict writes (D-65), and no learn-by-diff prerequisite (D-67).
Popular models order delivery rather than silently excluding applicable source
branches. Do not open a PR without explicit owner instruction; never merge it.

## What the app now reuses

| Generated runtime input | Source and actual use |
|---|---|
| `coding_data/coding_catalog.db` | Decrypted coding documents, labels, source selectors, authorization/signing entries and converted ISTA definitions. The app reads ordinary SQLite; it does not decrypt source packages at runtime |
| `coding_data/diagnostic_texts.db` | 162,757 linked fault/information text rows and 1,227 ECU titles from the actually opened DiagDocDb. Exact variant/code/memory lookup; differing candidates remain ambiguous |
| `ista_bundle/` | All 13 supplied KIS families, 530 job files (399 PRG/131 GRP), 592,028,562 job bytes. Manifest membership/hash checks precede native use; model lists come from source data |
| `native/build/libedx.dylib` in source use; library at bundle root when packaged | Existing interpreter, built universally for arm64/x86_64 on this Mac |
| Recovered JSON/gzip contracts | Diagnostic identity/memory, CBS, headunit-history, equipment and measurements. Standards and source-defined wire codecs remain code; car-specific tables are assets |

The 620 exact job-table identities already exist in the 1,307-row diagnostic
catalogue. The added lookup is independent-source resilience, not 620 new variants.
KIS contains K/R metadata too; including it does not expand the app's product
scope or infer compatibility from a series letter. Common source aliases include
F01/F10/F20/F30/F48/F15/F25/G20/G30/G05/G01 and I001; source lists are potential
ECU coverage, never proof of what is installed or physically validated.

The coding asset contains 6,106 exact numeric CAFD versions plus retained legacy
source documents; there are 80 named numeric root indexes and 1,034 root entries.
Counts do not mean every entry applies to every model. The former 1,566 count
included non-CAFD eight-character metadata files. There are 2,829 recovered AS/NCDS
entries; source order and unsupported key formats remain explicit.

## Recovered selection and enabled flows

- Connection/identity and DTC read/clear retain the existing owner and source
  catalogue, with generated jobs where available and labelled source-based
  fallbacks. Source/offline/physical coverage stays separate.
- History JSON/editor/journals and ADD-only append/explicit replacement remain
  implemented. No history reader, legacy adapters or automatic replay is restored.
  Twelve of the fourteen exact source head-unit identities expose the recovered
  ADD/ERASE jobs, including MGU02A/L. CICM/RAD12 do not expose them.
  See workflow 28 and the current headunit source audit.
- Current-source CBS adds KOMBSP21/7.0 start/result handling and DSC_25's ordered
  extra sequence, with explicit acknowledgement of fault clearing/event control.
  Readable copies do not automatically become writers; owner roles require the
  recovered service workflow, not a guessed default address. The asset includes
  48 definitions: 47 canonical PRGs plus an explicit historical D94 supplement; 40 primary
  roles and eight branches retained for observation/ownership investigation.
- Coding reads use the reported F101 identities and source-selected layouts.
  REA recovered exact APK selection followed by the immediately lower patch
  within the same ID/major/minor; this replaces the invented exact-file-only
  restriction. Exact ISTA metadata cross-checks group bounds/signature addresses.
  Contradictions remain explicit, not guessed compatible.
- Easy coding exposes source labels, actual current values, option predicates,
  dynamic lighting, and stable entry/option identities even for duplicate names.
  Complete fresh baseline/intent, signing/authorization, global lockout, checked
  application responses, explicit restore and interrupted-operation comparisons
  are implemented through the shared engine. Reported and selected identities
  and all source hashes are retained separately.
- Source coding guards are compiled data too. The recovered climate-controller
  critical-fault guard is checked before coding and retained as separate local
  evidence. Clearing DTCs does not silently erase that observed source restriction.
  Guard/evidence files are not restorable coding backups.
- Head-unit reads also follow recovered prerequisites: separate entitlement
  retrieval/local preservation and the exact NBTEVO I-level/RAM/HMI checks.
  Their small generated reader contract is independent of the large catalogue.
  Session/routine prerequisites run only after GUI lockout acknowledgement and
  remain refused in read-only mode. Entitlement files are separate from coding
  baseline groups; no automatic entitlement upload or replay is enabled.

D-29 governs completion. Response-confirmed is distinct from post-cycle observed
verification. Do not roll back because a value is old before its required cycle.
Only an established rejection permits checked restoration of known accepted
changes; uncertain/disconnected operations stop without automatic retry/replay.
DEMO previews never qualify as live ECU backups. Advanced editing remains deferred.

## Development build and verification

Use `scripts/build_runtime_assets.py --help`. The inputs are the supplied ISTA
folder, recovered coding assets/APK/resources and the development SQLite codec
reader. The command builds the native library/job bundle, decodes or reuses a
hash-checked CAFD export, creates plain SQLite assets and emits
`runtime-assets.json`. No builder is invoked by the app.

A typical command from the repository is:

```bash
.venv/bin/python3 scripts/build_runtime_assets.py \
  --ista sources/ISTA_4.29.1x \
  --apk sources/BimmerCode_v4.25.04-12743.apk \
  --resource-strings bimmercode_extracted/res/values/strings.xml \
  --text-reader /path/to/development/sqlite3mc \
  --job-parser /path/to/development/job_parser.py \
  --reader-backup-evidence /path/to/coding-unlock-backup-contracts.json \
  --reader-prerequisite-evidence /path/to/coding-read-prerequisites.json
```

`--decrypted-definitions /path/to/completed/export` reuses a verified development
export. Use `--out build/runtime_assets` for a separate runtime-only data tree;
reference packages, licences, encrypted source files and the codec reader are
not part of that output. The extractor evidence records exact tool provenance.
Reader evidence files are retained under
`/Users/lennon/BMW-Tool/investigations/source-runtime-20261104/`; the reader
contract compiler validates their exact same-artifact methods before producing
its small runtime JSON. CBS/history contracts are regenerated too, rather than
copied from an older build. The personal generated databases/job bundle remain
local, not a public release.

Read `tasks/source-reuse-runtime-implementation.md` for final verification and
review findings. Separate detailed records cover job assets, source database
access, CAFD access, coding catalogue/selection, coding execution and current CBS.
Meaningful checks use actual data/jobs with synthetic ECU responses. The real
owner/Scapy/udsoncan path was exercised through a fragmented loopback gateway;
Qt confirmation, lockout, restore and interruption handling were checked offline.
No physical car operation or universal vehicle validation is claimed.

## Remaining concrete source work

Execution order is now the owner's [Tasks C–F](../tasks/task-c-through-f-roadmap.md),
starting with **CBS reading and individual reset reliability (Task C)**. The
inventory below supplies those tasks; it does not supersede that priority.

Task C implementation/verification is now recorded in its
[evidence and complete matrix](evidence/task-c-cbs-reliability.md): 47 current
readers, software-bound preflight, native table loading/decoding corrections,
exclusive foreground flow and actual-owner pending/interruption checks. The
eight observational reset-owner branches retain explicit source restrictions.
[The post-PR20 continuation](evidence/task-c-source-continuation.md) integrates
the available historical D94 PRG without relabelling it a canonical 4.29 file;
it adds native read/start/result handling and a hash-bound development supplement.
Independent continuation review is complete; physical acceptance is unperformed.

1. Three CAFD 02.00.00 files use a different `codingArea/sigId/sigLen` layout;
   the current converter records their exact identities/dispositions instead of
   pretending the byte-layout importer covers them.
2. Trimmed ISTA USER function names are literal `.`. All 5,895 CAFDs and 26 FAFPs
   decrypt, but decryption cannot restore removed names. Source-compatible APK
   layouts recover several owner's F48 options; remaining semantic mappings need
   actual identifiers/another source, never positional or near-version guesses.
3. Keep tracing any CBS ownership/argument branches not established by the service
   workflow. Preserve observational data without making it write authority.
4. Ninety-four group-table job names and five USES dependencies are absent from
   this supplied release. Record the affected source branch; use established app
   contracts where available, rather than assuming absent files are fleet proof.
5. Source signing entries with empty/EC material unsupported by this APK's RSA
   path remain explicit. No arbitrary fallback key or signing-server bypass.
6. Odometer/measurement migration to equivalent STATUS jobs, richer DTC details
   and later advanced editing remain separate work. Do not restart completed
   history/CBS/coding increments from stale aggregate checkboxes.

None of these source investigations requires access to another car. Physical
observations, Windows and packaged-release acceptance remain separate milestones.
