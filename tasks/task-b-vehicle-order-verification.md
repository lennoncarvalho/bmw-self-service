# Task B — packed vehicle order / equipment verification

2026-10-29. Implemented increment, not overall Task B completion.

## Branch and code

PR14 verified MERGED at2026-10-29T19:06:05Z, merge
`dcb70a604a9bbe1958410497eedcfe6a6c4d854c`. Original worktree was clean. Fetched
origin/main and created `codex/task-b-vehicle-order` from that exact merge.
Preserved PR14 diagnostic refresh/revision guards and PR13 protocol ownership,
settled results, bounded refresh, mutation lockout and shared MIL semantics.

Standalone packed3F06decoder + existing post-connect worker integration, visible
model-range/type/time-criterion/paint/upholstery and expandable configuration
sections are implemented.4735English equipment labels are shipped in generic
JSON, exactProws only; source tools/executables/decryption/REA are development-only.
Catalogue failure affects labels only; raw valid vehicle order remains available.
Time criterion does not become a production date, and model range/type key do
not become a guessed trim or transport selector. Legacy unused FA XML extraction
and chassis→protocol constant were removed. No history/coding storage changed.

## Executed offline checks

One-off scripts/logs/screenshots and SHA manifest retained at:
`/Users/lennon/BMW-Tool/investigations/task-b-vehicle-order-20261029/`.
These scripts are verification artifacts outside the repository, not a new suite.

- `task-b-vehicle-order-check.py`: independent MSB-first encoder, five fixed
  fields, all8optional-section presence combinations and empty sections, exact
  raw/prefix retention; unknown tag and nonzero tails; truncated header/item/
  terminator, wrong DID/negative/control characters/oversize rejected. Exact
  HSFZ10request22/3F06with30second timeout; DoIP zero-send. Missing-label asset
  preserves raw/fixed facts. Actual PostConnectWorker optional-read error boundary
  retains later task results. Passed.
- `task-b-vehicle-order-ui.py`: actual background DEMO connect, synthetic byte-
  derived order through MainWindow's settled refresh callback, English/unknown
  labels, expand/collapse, time-criterion vs unavailable build-date separation,
  unknown-section warning, stale-session result rejection, failed refresh clears
  previous configuration/labels, mutation refresh/quit lockout and shutdown.
  Passed. Visually inspected welcome, expanded configuration and unavailable
  screenshots at1050×850; no clipping/overlap. Source-derived byte presentation
  is synthetic and explicitly distinct from car observations.
- Independent reviewer `identity-review-check.py` and final-check: fixed fields,
  all8section combinations,12unknown tags, nonzero trailing bits, malformed
  catalogue schema/encoding fallbacks, exact/case/unknown lookup and Qt rendering
  at900×650. No blocking findings. Reviewed source offset/alphabet/markers,
  CarWorker ownership, stale/reset state, metadata integration and asset inclusion.
- Metadata check at
  `/Users/lennon/BMW-Tool/investigations/task-b-vehicle-metadata-20261029/offline-check.py`
  (`PYTHONPATH=.`): all4735exact/lowercase labels,249passenger/motorcycle collision,
  unknowns/empty/invalid/oversized inputs, malformed/oversized catalogue and
  byte-identical source asset+manifest reproduction. Passed. Preserves4735codes;
  IST1label neutralized to Diagnostic simulation checks under AGENTS naming rule,
  with original/replacement retained in internal provenance. Generated asset
  SHA-256`6f9c5e8ec94a6ffb03c6e9f21d0e972322a9d82de0930b48b275f0b85a1f1567`.

Harness-only corrections: an initial invalid-control fixture used a negative
encoder input, corrected to explicit zero bytes; metadata standalone launch
needed PYTHONPATH to locate the app. Corrected runs above passed. No product bug
was hidden by those harness corrections.

## Quality gate and source review

Full `scripts/preflight.sh`: Ruff check passed; Ruff format check passed;
mypy passed35app/ui/main source files. Development extraction script separately
passes Ruff check and format check. `git diff --check` passed. Rerun full gate
immediately before push as required. Local runtime Python3.15.2; no3.13run claimed.

Three independent delegations: packed-source/Python/Qt review, source-series/
equipment recovery and remaining MIL block source recovery. No blocking final
runtime findings; label-only error isolation and force-adding the ignored
standalone asset were explicitly checked. Source evidence and exact hashes are
in docs/evidence/task-b-vehicle-order.md, task-b-vehicle-metadata.md and
 task-b-mil-block-recovery.md with portable local bundles.

## Concrete remaining work and boundaries

- Supplied45series groups account for electric models through F/G categories;
  no explicit U/I20group, exact trim decoder or DoIP logical-address converter
  exists in those traced paths. Recover a concrete applicable source branch,
  actual odometer/build/model measurements and diagnostic category/description
  reconciliation next; do not guess from year/chassis or wait for more cars.
- Five older MIL readers now have exact fixedF303clear/define/read evidence,
  but runtime configuration mutations are not enabled. Implement exclusive whole-
  sequence ownership, bounded checked cleanup and uncertainty before enabling;
  operation_scope alone only shares a deadline. Preserve read-only2Crejection.
  Other four alternate/missing engines remain source work.53direct-scalar rows
  remain the current runtime coverage, unchanged by this increment.
- Continue local JSON history journal/cards, mode-specific append/replacement
  writes and full easy coding/recovery in the ordered queue. No reader/legacy
  adapters or weakened baseline/storage requirements are introduced.

No vehicle traffic, dynamic DID mutations, physical lamp/ECU observations,
network/DHCP/elevation changes, universal compatibility claims, Windows/runtime
packaging/signing checks or source-application execution. Physical acceptance
remains distinct from source support and offline verification. Do not merge PR.
