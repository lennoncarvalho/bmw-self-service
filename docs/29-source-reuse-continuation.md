# Current source reuse and continuation — 2026-11-04

This is the current reconciliation of the app, source locations and development
order. Older checkpoints remain historical evidence. Authority: owner request
of 2026-11-04 to reuse supplied definitions and executable jobs first, investigate
missing integration contracts, and disclose actual limitations without changing
the product to accommodate an assistant.

## Product and implementation boundaries

- D-60's ISTA 4.29 / HSFZ milestone, D-61 job execution, D-62 hybrid data and
  D-63 personal use remain recorded owner decisions. Broad applicability within
  that source release remains the target; F48 observations are not fleet proof.
- D-67 rejects learn-by-diff as a prerequisite. Reuse the supplied coding
  catalogue; do not ask the owner to capture each option to reconstruct it.
  Reconcile D-66's historical popular subset with D-17 and the current owner
  direction as delivery ordering, not silent exclusion of applicable definitions. This does not add newer ISTA/DoIP scope.
- CBS reads and writes precede coding. History remains local JSON plus explicit
  append/replacement, without vehicle-history reads or automatic replay.
- Exact identity, complete original coding bytes, durable intent/results,
  confirmation, power handling, lockout and checked completion remain required
  for writes. Use D-29's operation-specific completion instead of a universal
  immediate-readback prerequisite. DEMO is not a live backup.
- REA is development-only. The embedded interpreter/data are standalone runtime
  components; do not invoke REA, research providers or reference applications.
- Do not open a PR without explicit owner instruction. Do not merge for the owner.

## Reuse first

1. Use the existing definition loader and catalogue for named options, layouts,
   selectors and checksums. Account for exact versions and conditional/dynamic
   options before enabling editing; catalogue availability is not write readiness.
2. Execute existing PRG jobs through `JobBackend` / `JobEngine` and the existing
   protocol owner where they establish the requested behavior. Fix concrete VM
   gaps instead of writing another complete diagnostic implementation. Existing
   app-decoder fallbacks remain until equivalent behavior is checked.
3. Use REA on the missing selection, authorization and assembly/database paths.
   Recover the missing contract, not every already-understood layer again.
   Static source and meaningful offline checks can establish implementation;
   vehicle captures add observations, not a blanket development prerequisite.
4. Reuse readable text/mapping databases and investigate protected databases
   when needed. A failed tool call, unopened database or untraced algorithm is
   an investigation result, not an owner decision or permanent product limit.
   Record the precise blocker and next action. Do not promise recoverability.
5. Prefer existing libraries and parsers over new implementations when they fit
   the standalone app and recorded owner constraints. Evidence identifies the
   source/version and behavior actually relied on; it is not a demand to trace
   every library implementation before exposing a labelled read (D-65).

## Current local source inventory

Canonical ECU directory: `sources/ISTA_4.29.1x/Rheingold/Ecu/`.
The owner removed `sources/Ecu/`; do not recreate or require it. The standalone
headunit PRGs, APKs and existing extracted coding assets remain available.

Observed on 2026-11-04:

| Material | Observation | Limit |
|---|---|---|
| ISTA Ecu | 1,227 PRG and 394 GRP files | Not byte-identical to the deleted collection |
| ISTA PSdZ | 5,895 CAFD and 26 FAFP files | Inventory only; decryption not established here |
| DiagDocDb | 5,945,655,296 bytes; first 16 bytes `8e9d09414f37d004b31d374176a892e9` | No ordinary SQLite header; encryption/codec and key path still to recover; header alone does not prove the format |
| SQLite connector | REA identifies .NET Framework 4.8 CIL, assembly 4.29.15.23407 | Metadata inspection only; no key recovery or execution |
| Existing coding `.enc` files | All 2,305 decrypt/parse using the existing loader: 2,163 variant definitions and 142 lists; 1,566 entries in eight-character root indexes | Counts across the catalogue, not unique presets or per-car applicability |
| Native job runtime and bundle | `native/build/` and `ista_bundle/` absent in this checkout | Prior build/check records are historical; rebuild locally before claiming job execution here |

Connector identity: `TesterGUI/bin/Release/RheingoldDatabaseSQLiteConnector.dll`,
SHA-256 `b4c43353b2cd4a99f4bcafdfd3a5f19b3e2390e7b8ab88afe4f8e76d2e05b06b`,
MVID `140e8b25-cfe7-4ca7-9b6c-6bf16ccaa933`. REA metadata parent
`ev_1cdb7147d8b2916e4aa2fc99fa644d637825c12b9a5fcea10c36774779df8d26`,
summary `ev_ec3b4a500dc6b0aa8fdc3dca5bff8dffaa22b1df3c68f949ef4aea5f7e81d593`.
These IDs may be session-local; path, hash and MVID permit reinspection.

### Historical evidence after relocation

Keep original paths, hashes and offsets in retained JSON evidence. Resolve an
old basename case-insensitively in the current ECU directory and compare its
hash before using the old trace. Among the 24 files in
`evidence/task-b-mil-breadth.json`, 14 match, eight differ and two are absent
(`D94BX7A0`, `DME9FF_R`). Changed files require comparison/recovery; missing files
need another retained artifact or an explicit uncovered disposition. Do not
rewrite runtime contract hashes or treat a matching basename as matching bytes.
The [relocation manifest](evidence/ecu-source-relocation-20261104.json) records
both hashes and current paths for this subset. The old folder comparison in
the ISTA architecture record is historical.

## Current implementation and next work

Implemented code includes protocol ownership, identity/inventory, fault reads/
clears, history editor/journals/append/replacement, CBS read/reset, odometer and
measurements, and exact-definition coding snapshots. Fault/CBS paths can use
jobs with labelled app fallbacks. This review does not certify every branch or
repeat previous offline/physical acceptance. Live coding editing/writes/restore
remain disabled; the existing coding database is usable input, not a finished
writer. See `app/coding.py`, `app/coding_db.py`, `app/ista_jobs.py` and the
history/CBS implementation records.

Continue in this order, preserving completed substeps:

1. Rebuild the native interpreter and source bundle from the current ISTA tree;
   reproduce relevant offline job checks. Reconcile changed/missing PRG hashes,
   VM limitations, source selection and current applicability records.
2. Complete remaining CBS branches (including DSC_25, D94 6.3 and KOMBSP21) and
   diagnostics/text reconciliation through existing jobs/data. Migrate remaining
   STATUS-based values where jobs are equivalent. Keep uncovered branches named.
3. Establish the coding catalogue inventory/applicability with the existing
   decrypted data, including exact-version gaps; recover missing selectors,
   dynamic options, group layout/checksum metadata and authorization from sources.
   Use ISTA CAFD for gaps after establishing a working decode path, not as an
   assumed prerequisite for definitions already available locally.
4. Compose all applicable presets against complete real baseline blocks; integrate
   write, completion and restore contracts into the existing owner/store/UI.
   Implement and review with offline byte/error checks before PR delivery.
5. Recover DiagDocDb access for text/model/service mappings in parallel where it
   supplies needed facts. Investigate the connector and existing implementation
   references; report exact technical failures without replacing the requirement.

Retain source/offline/physical evidence separately. Only the owner's F48 is
available for physical observations; other cars do not gate source-based work.
No automated suite or `tests/`; full app preflight before every push.
