# Resume BMW Self Service review

Read `AGENTS.md`, then `.agents/skills/spec-driven-development/SKILL.md`,
`docs/README.md`, `docs/19-audit-and-readiness.md`,
`docs/20-protocol-evidence.md` and `docs/21-product-decisions.md`.

The owner distrusts earlier specs and app behavior. Documentation/tooling cleanup
has preceded a planned review of open PR #8 (`fix/hsfz-ack-handling`). Check the
actual worktree/index and PR head before changes; preserve existing work. Do not
rebuild infrastructure from the old twelve-task list.

Primary validation target is the owner's F48 X1 sDrive20i X-line, model year
2018, NBT. The goal is broader BMW ENET coverage via source-app investigation;
that is not universal compatibility or physical validation. PR text contains a
historical ACK/mismatched-response excerpt; the local log was empty at audit time.

Coding/history write screens must save a backup first, retain original/intended/observed
state and confirm by reading back from the car. Current UI-value backups do not
provide verified ECU restore. Service-history wire format is unresolved; its
current “read” invokes a candidate add routine. Review those blockers before
connecting pages that automatically start operations.

Skills live in `.agents/skills`; setup/provenance is in `.agents/README.md`.
REA instructions are installed, CLI 6.8.0 is available through a package runner,
but no live MCP/JADX/native provider is configured. Do not invent tool results.

Ask the owner about pending feature/recovery decisions and record answers. Scope
initial code work to a read-only connection baseline after the PR review. Keep
all car I/O off the GUI, use exact variant evidence and never interpret ACK as
completed application work. Follow current no-test-suite policy until changed.

Run `scripts/preflight.sh` over all app targets before completion/push and report
lint, format and mypy separately. The local venv was Python 3.15.2 while CI targets
3.13; align deliberately in separate toolchain work. No push/merge is authorized
merely by this resume prompt.
