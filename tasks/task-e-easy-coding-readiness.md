# Task E — applicable Easy Coding and deferred-target enforcement

Priority: after CBS and diagnostic work. Status: planned implementation.
Apply [the shared C–F workflow](task-c-through-f-roadmap.md).
Advanced coding and unvalidated safety-ECU coding are deferred, not prerequisites
for delivering the applicable current Easy Coding scope.

## Baseline and concrete gaps

Preserve the plain coding catalogue, exact reported identities/source-compatible
layout selection, live group snapshots, composition, authorization/signatures,
headunit prerequisites, critical-condition guard, complete target-ECU originals,
explicit restoration and durable interruption handling. Use `app/coding.py`,
`app/coding_db.py`, `app/coding_write.py`, related helpers and `ui/coding_page.py`.

The current list enables source-mapped choices but checks full applicability
only during preparation. The old safety-critical blocked list is in Advanced/
DEMO rendering; it is **not** a global live Easy write gate. Both are real gaps.

Reanalysis of the owner's retained F48 profile found18 resolved coding
identities and200 source entries:172 applicable/mapped,8 applicable/unmapped
(ACSM),20 source-inapplicable. Nine coding ECUs have named curated roots;9 do not.
These are offline catalogue/profile facts, not current-car values or proof of
physical write safety. The source audit is retained at
`~/BMW-Tool/investigations/easy-coding-audit-20261105/`.

Read spec26 B-CODE-R/B-CODE-W/B-REC, owner decisions, doc29, current source
catalogue/selection/critical-guard evidence and
[source coding execution](source-coding-write-implementation.md). Do not repeat
already completed decryption/signing recovery or restore exact-file-only gates.

## Source investigation → implementation

- [ ] E1: Implement explicit current-scope safety/deferred-target enforcement
  for coding in both UI and prepare/write/restore paths. Recover ECU roles and
  source feature semantics; document precisely which identities/operations are
  deferred. Static security flags or a generic chassis/address list do not prove
  safety or write permission. Unknown classification is not authorization.
  Do not block diagnostics, fault clearing or legitimate CBS service resets via
  a blanket protocol-level address ban. Do not enable deferred coding simply
  because an imported backup/plan or old Advanced list permits it.
- [ ] E2: Collect applicability context in CarWorkers and evaluate source filters
  before offering selections: model/category, exact variant, headunit generation,
  declared series/exclusions and other recovered predicates. Preserve the source
  category0 semantics; unknown context must remain unknown. Show clear counts/
  reasons for unresolved or deferred options; do not silently lose catalogue
  entries or expose known-inapplicable choices until preflight rejects them.
- [ ] E3: Account for the complete supplied named catalogue and connected
  definitions. Use REA on actual selectors/readers and decrypted data to separate
  intentionally absent curated options from missing recovery. Use combined
  definitions and source primary-root ordering; no first variant, arbitrary
  nearest version, UI-index bytes or guessed function names/offsets.
- [ ] E4: Finish applicable non-deferred semantic/layout branches. Three current
  CAFD02.00.00 dispositions use `codingArea/sigId/sigLen` rather than the existing
  byte layout:000058AA-001-001-001,000058AA-001-001-002,
  00005C0A-049-001-020. Trace their source decoders and byte/signature meaning.
  Literal trimmed USER names `.` are not recoverable by renaming them; recover
  actual identifiers/mappings from the supplied reference packages and selection
  paths. Never invent a catalogue to fill a source absence.
- [ ] E5: Reconcile all applicable option types, duplicate names, dynamic
  matrices, masks/group bounds, untouched Custom values and multi-option conflicts.
  Read current values from actual complete ECU bytes. A source default is not
  a current value. Preserve source-defined lower-patch selection and exact-XML
  cross-checks with separate reported/selected provenance.
- [ ] E6: Investigate unsupported empty/EC signing material and any authorization
  path needed by non-deferred targets through actual source selection/algorithms.
  Do not choose a different key, invent credentials or replace a required source
  contract with a plausible generic crypto implementation. Distinguish a proven
  source restriction from an unfinished recovery branch.
- [ ] E7: Close live read/write/restore readiness for each enabled branch:
  fresh identity/current bytes, immutable complete target baseline/intent,
  exact requests and signatures, critical guards, application completion,
  required cycles, established-failure recovery and uncertain-outcome handling.
  Foreground loading must block competing actions; failures/cancelled review must
  not strand reads or replay writes. Read-only and DEMO cannot produce live writes.

## Verification and exit

- [ ] Whole-catalogue accounting with reproducible source hashes and explicit
  matched/inapplicable/unknown/deferred/missing dispositions. Re-run the retained
  F48-profile audit without presenting old captured values as current readings.
- [ ] Actual source-layout composition/current decoding and authorization checks;
  reordered/sparse options, unknown context, duplicate names, incomplete baselines,
  cross-group conflicts, stale software/plan, deferred-target bypass attempts,
  persistence loss, rejection, disconnection and explicit restoration.
- [ ] Actual Qt first load, tab switching, source-filtered choices, short/long
  pages, current Custom values, disabled reasons, loading/confirmation and error
  recovery. Keep normal titles and the single outer-scroll layout.
- [ ] Independent review, fixes, full preflight and current scope/evidence records.
  Any owner-car write observation is separately authorized and limited to the
  enabled non-deferred target; other cars are not a source-development dependency.

Exit: every enabled option is applicable and source-backed, displays its actual
mapped current value or honest Custom state, and reaches the checked shared
engine. Deferred coding is actually gated rather than merely described as
postponed. Outstanding exact source branches remain explicit; advanced editing
and deferred safety coding do not get silently re-enabled to close this task.
