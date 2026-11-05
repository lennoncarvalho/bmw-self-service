# Resume BMW Self Service development

Read `AGENTS.md`, `.agents/skills/spec-driven-development/SKILL.md`,
`docs/README.md`, docs 19/20/21 and
[the current reconciliation](docs/29-source-reuse-continuation.md).
Doc29 owns current source locations and implemented baseline. The remaining
implementation queue is [Tasks C–F](tasks/task-c-through-f-roadmap.md):
**Task C — reliable CBS reading and individual resets — is next**, before DTC
details (D), Easy Coding readiness (E) and history/integrated acceptance (F).
Older Task B checkpoints are historical, not instructions to repeat merged work.

PR18 is merged in the current baseline. Inspect Git/PR status and fetch origin
before development; preserve unrelated changes and unpublished UI/task follow-ups.
For a new increment after the preceding PR merges, start a fresh `codex/` branch
from current origin/main; do not drop unmerged local work to do so. Never reuse a merged branch or commit
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

Read doc 29 before implementing; it reflects the actual source recovery and
runtime integration completed on `codex/source-derived-runtime`. Source folders
are build inputs only (D-68); the runtime ignores old folder preferences.

Implemented: generated job/text/coding databases, history append/replacement,
source-current CBS, source-selected coding reads, easy coding writes/signing,
explicit restore and interruption handling. REA recovered lower-patch layout
selection, so reported F101 and selected layout identities are distinct and
retained; arbitrary first/nearest variants remain forbidden. All supplied CAFDs
and FAFPs decrypt; three newer CAFD formats and trimmed semantic names have
explicit remaining investigation tasks. Do not reintroduce exact-file-only,
learn-by-diff or source-folder runtime prerequisites.

Use `tasks/source-reuse-runtime-implementation.md` and its linked subtask/evidence
records before repeating work. Execute Task C first, then the ordered C–F queue;
doc29's source gaps remain its input, not an alternate priority order.
Source/offline/physical status must stay separate. Advanced and unvalidated
safety-ECU coding are deferred; the live safety-coding gate remains Task E work.
No PR creation is authorized.

All car I/O stays on CarWorker and one protocol owner. Preserve settled initial
page results, bounded refresh, mutation lockout and checked completion. Current
engine indicator behavior follows D-59; old physical MIL-command research is
historical and must not silently override that decision.

Coding requires actual complete ECU baseline bytes and exact reported identity
with source-defined layout selection; DEMO
previews are not backups. History instead preserves local JSON/intent/results
with null prior-car state, ADD-only append or explicitly acknowledged replacement.
No history reader, legacy adapters, automatic replay or guessed old-car backup.
D-29 defines contract-specific completion/cycle handling; do not require universal
immediate readback or restore because an old value is visible before its cycle.

No automated suite or `tests/`. Use meaningful one-off offline byte/error checks,
visual Qt/DEMO checks for UI changes and independent review for implementation.
Run full `scripts/preflight.sh` before every push; report Ruff lint, Ruff format
and mypy separately. No physical writes are authorized by a development request.
