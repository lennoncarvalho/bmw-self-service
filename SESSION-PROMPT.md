# Resume BMW Self Service development

Read `AGENTS.md`, `.agents/skills/spec-driven-development/SKILL.md`,
`docs/README.md`, docs 19/20/21 and
[the current reconciliation](docs/29-source-reuse-continuation.md).
Doc 29 owns current source locations, implementation status and continuation;
older task checkpoints are historical, not instructions to repeat merged work.

PRs through #17 are merged in the current local baseline. Inspect Git status and
fetch origin before development; preserve unrelated changes and start a fresh
`codex/` branch from current origin/main. Never reuse a merged branch or commit
to main. **Do not open a PR unless the owner explicitly asks.** Never merge it
for the owner. Use the personal `lennoncarvalho` account before push/PR commands.

## Source reuse and scope

Use existing coding definitions, data tables and executable PRG jobs first.
REA recovers missing selectors, codecs, authorization and integration contracts;
it is development-only and never an app dependency. Do not rebuild source data
by trial captures or invent constants. State actual tool/source limitations
without converting them into permanent scope restrictions.

The canonical job directory is `sources/ISTA_4.29.1x/Rheingold/Ecu/`.
`sources/Ecu/` was removed. Existing historical evidence retains its original
paths/hashes: compare current bytes before reusing offsets or contract claims.
See doc 29 for known changed/missing definitions and the current ISTA inventory.

Preserve recorded owner decisions: ISTA 4.29/HSFZ milestone and job execution
(D-60–D-62), personal use (D-63), labelled best-effort reads/strict writes (D-65),
and no learn-by-diff prerequisite (D-67). Popular options order delivery rather
than permanently limiting the applicable source catalogue. CBS reads **and
writes** precede easy/advanced coding (D-58). No additional car is a dependency
for source recovery, implementation, offline review or delivery.

## Current implementation and continuation

Read doc 29's current-status/queue before implementing. Existing code includes
history JSON/editor/journals/append/replacement and CBS read/reset; do not
restart them from unchecked aggregate tasks. Fault/CBS jobs use the existing
owner with labelled app fallbacks. Coding supports exact-definition snapshots;
live editing, composed writes and restoration remain unfinished.

Rebuild missing local native runtime/bundle, reconcile current PRG versions,
finish remaining CBS/diagnostic branches, then implement coding from the usable
local catalogue and recovered write/restore contracts. Investigate ISTA database
access for missing text/model/service facts. Previous checks are historical;
report exactly what this checkout and session actually verify.

Task A/library boundaries: `tasks/protocol-library-migration.md`, spec 25.
Task B acceptance: spec 26; sources: doc 27; implementation detail:
`tasks/ista-job-engine-plan.md`, `tasks/rea-protocol-recovery-tasks.md`,
`tasks/rea-protocol-recovery-investigations.md`, history workflow 28.

All car I/O stays on CarWorker and one protocol owner. Preserve settled initial
page results, bounded refresh, mutation lockout and checked completion. Current
engine indicator behavior follows D-59; old physical MIL-command research is
historical and must not silently override that decision.

Coding requires actual complete ECU baseline bytes and exact identity; DEMO
previews are not backups. History instead preserves local JSON/intent/results
with null prior-car state, ADD-only append or explicitly acknowledged replacement.
No history reader, legacy adapters, automatic replay or guessed old-car backup.
D-29 defines contract-specific completion/cycle handling; do not require universal
immediate readback or restore because an old value is visible before its cycle.

No automated suite or `tests/`. Use meaningful one-off offline byte/error checks,
visual Qt/DEMO checks for UI changes and independent review for implementation.
Run full `scripts/preflight.sh` before every push; report Ruff lint, Ruff format
and mypy separately. No physical writes are authorized by a development request.
