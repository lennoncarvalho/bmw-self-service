# Standalone coding catalogue — implementation plan (2026-11-04)

Owner request: use recovered databases/packages as the implementation basis;
produce development-built runtime assets, without accessing `sources/` at runtime.

## Concrete work

1. Inspect existing decrypted definitions, curated roots, selector/ECU metadata
   and actual storage/value layout, with focused REA lookup where behavior is
   absent from data. Retain original identity and distinguish data from wire proof.
2. Add `scripts/build_coding_bundle.py`: decrypt source assets only during
   development; preserve all JSON documents, labels and exact variant names in
   bounded compressed JSON members with a versioned hash/size manifest. Publish
   the complete directory atomically; runtime receives no source paths or keys.
3. Replace runtime AES loading in `app/coding_db.py` with checked bundle reads.
   Preserve public query APIs; expose definitions/variants/ECU metadata to migrate
   snapshot/UI callers away from raw `.enc` scans. Reject missing/invalid assets.
4. Remove unsafe encoder defaults/skips, support source-established group-specific
   multi-byte values and masks, and retain unrelated bits. Do not enable car writes
   or conflate catalogue availability with authorization/recovery readiness.
5. Build complete local asset, compare every decoded JSON document, exercise
   real catalogue layout and error cases offline, then run required app checks.
   No automated suite, `tests/`, vehicle traffic, push or PR creation.

## Implementation checkpoint

- Built one standalone read-only SQLite asset instead of decrypting at runtime.
  It preserves all original JSON and label data with source hashes and bounded
  compressed members. Runtime no longer imports AES or reads `.enc` files.
- Added exact variant, definition, provenance and source ECU metadata APIs;
  group-aware matching/composition, nonvacuous dynamic handling, optional-function
  behavior, conflict detection and strict baseline bounds.
- Recovered source AS/NCDS packages, signing/auth transforms, primary-definition,
  category and ID8 selectors, plus both dynamic lighting rows. Added pure runtime
  helpers and development-generated selection/authorization data.
- Full evidence, reproduction command, corrected inventory counts and verification
  limits are in `docs/evidence/source-coding-catalogue-20261104.md`.
- One-off original-data comparisons, actual matrix roundtrips and independent
  Java cryptographic comparisons pass. No car traffic, tests suite, push or PR.
- Parent owns migration of UI/snapshot consumers and the shared journalled coding
  engine. A green local subset check is not a substitute for parent's final full
  app preflight after all concurrent changes settle.

## Source discovery correcting the exact-file assumption

REA `models.q.b(k.v)`, `k.v.i()` and `q0.compare/b` establish that the reference
first selects an exact package definition, then the nearest lower patch with the
same CAFD ID, major and minor. This is an evidenced source selection rule, not a
first-variant/nearest-model heuristic. Earlier exact-file-only wording was too
restrictive. The loader now retains reported and selected identities separately,
with both original source and compiled document hashes. Exact imported XML
independently cross-checks group addresses, signature destination and byte bounds;
contradicted compatibility is not used for named coding.

`definition_resolution(reported)` is frozen/rechecked by the parent coding
engine. All thirteen missing owner-car CAFD versions are now readable; five
CAFDs across ACSM/FZD/ENTR obtain named lower-patch source layouts whose exact
XML group/signature cross-checks agree. Literal stripped names in the others are
not reconstructed by guessed offsets or nearby versions.

Full source conversion yielded 4,127 additional runtime definitions, retaining
1,765 existing named source definitions. Three version-2 CAFDs have a different
codingArea/sigId/sigLen schema with no byte-layout data/datagroup nodes; their
explicit dispositions remain source parser work rather than hardware gates.

Also recovered combined-definition function lookup and whole-preset required
function applicability, duplicate source-root entries and duplicate named color
choices. Root/preset indices and ordinal-qualified duplicate option keys preserve
actual source objects instead of silently choosing one by display name.

Final aggregate asset build completed (6,434 documents, 6,106 exact CAFD versions,
2,829 authorization entries), including compiled critical-climate guards. Final
coding asset hash and source-reader prerequisite findings are retained in the
evidence document. Parent was notified of the separate source unlock-code backup
and exact NBTEVO I-level/RAM/HMI prerequisite branches; ordinary group reads use
direct `22` requests. Reader integration is outside this helper's ownership.

Follow-up completed: recovered all unlock-backup callbacks, file verification,
cleanup and separate explicit-upload semantics. Built the small standalone
`reader_contracts.json` with source hashes using
`scripts/build_coding_reader_contracts.py`, without rebuilding the catalogue.
Independent runtime-helper checks passed request order, durable payload/cache
reuse, conditional status-4 handling, signed RAM refusal, cleanup and read-only
zero-I/O. Review found and the engine owner fixed duplicate source-entry identity,
FSC status handling and Java integer-byte semantics. Parent corrected stale
confirmation labels. Unexported-result closing and snapshot per-request deadline
findings were sent to their owners before final gating.
