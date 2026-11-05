# Source reuse reconciliation — 2026-11-04

Owner request: reconcile the documentation around reuse of supplied definitions
and executable jobs first, investigate missing integration contracts, and record
that `sources/Ecu/` was removed. Work on `codex/source-reuse-reconciliation`;
no new PR is authorized. No vehicle operations are part of this work.

## Plan

1. Inventory the restored ISTA tree and compare relocated PRGs with retained
   evidence hashes. Preserve historical artifact identities rather than relabel
   changed files as the same evidence.
2. Establish one current handoff/status and source-routing record. Reconcile
   specs and decisions without silently expanding or narrowing owner scope.
   Preserve ISTA 4.29/HSFZ, CBS-before-coding, personal-use and write requirements.
3. Prefer existing coding definitions and PRG jobs; use REA for missing selectors,
   metadata, decoders and authorization contracts. Separate session limitations
   from project rules and distinguish uninspected candidates from proven facts.
4. Update active ECU paths and development-script defaults. Keep old paths in
   historical evidence with explicit relocation/version notices; do not rewrite
   raw evidence or shipped contract hashes to match newer PRGs.
5. Verify links/path references, one-off read-only checks and full app preflight.
   Record remaining concrete work, observed limitations and verification here.

## Completed

- Added doc 29 as the reconciled current source/status/continuation record and
  replaced accumulated SESSION-PROMPT checkpoints with a concise current handoff.
  Updated AGENTS, root README, capability map, doc index, source guide, decisions,
  feature spec and task entry notices to route there.
- Preserved D-60's release scope, CBS priority, write requirements and historical
  owner decisions. Explicitly marked rejected capture instructions historical;
  reconciled popular-option delivery ordering with D-17/current owner direction.
- Corrected unsupported impossibility/guaranteed-recovery phrasing. Historical
  assistant refusals remain attributed to that session, not project policy.
- Canonical ECU path is now the restored ISTA directory. Updated the two active
  script defaults; added relocation notices to old evidence without modifying
  raw historical JSON, shipped assets, hashes or decoder fingerprints.
- Added `docs/evidence/ecu-source-relocation-20261104.json`: 24 historical MIL
  artifact identities compared against current bytes (14 identical, eight changed,
  two absent). This is a subset comparison, not a full former-tree reconstruction.

## Verification and review

- Current ISTA inventory: 1,227 PRGs, 394 GRPs, 5,895 CAFDs, 26 FAFPs.
- Read only the DiagDocDb header and size: no ordinary SQLite header; this does
  not itself establish encryption/codec or prove a usable key exists.
- REA managed metadata inspection succeeded on the restored SQLite connector:
  assembly 4.29.15.23407, .NET Framework 4.8 CIL; exact hash/MVID in doc 29.
  No assembly or reference executable was executed and no database key recovered.
- Existing coding-data decode check in the immediately preceding assessment:
  2,305 files parsed without errors. This is catalogue availability, not per-car
  applicability or complete encoder correctness.
- Both modified script CLIs start with `--help`; AST parsing succeeds. No asset
  regeneration or extraction was run. All current relocation hashes rechecked.
- Local Markdown file links in changed/new docs resolve; `git diff --check` passes.
- Full app `scripts/preflight.sh`: Ruff check passed, Ruff format check passed
  (46 files), mypy passed (46 source files). No automated suite created.
- Independent reviewer found two ambiguities: blanket exclusion of source data
  from runtime, and active-looking popular-subset scope. Fixed both: reference
  applications/tooling stay development-only, approved jobs/data may run in the
  embedded interpreter, and historical D-66 is distinguished from current
  reconciliation with D-17 and the owner's direction.

No app runtime behavior changed, car traffic, physical validation, native build,
full ISTA decryption, visual UI check, push, PR creation or merge occurred. Native
runtime/bundle are absent locally; rebuilding and reproducing relevant job checks
is the first implementation task in doc 29, not a claim completed by this change.
