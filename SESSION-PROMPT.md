# Resume BMW Self Service development

Read `AGENTS.md`, `.agents/skills/spec-driven-development/SKILL.md`,
`docs/README.md`, docs 19/20/21, then select the requested task:

| Task | Start file | Specification | Outcome |
|------|------------|---------------|---------|
| A — library migration | `tasks/protocol-library-migration.md` | `docs/25-library-migration-spec.md` | One protocol owner/API using udsoncan and selected Scapy HSFZ/doipclient adapters |
| B — close feature gaps with REA | `tasks/rea-protocol-recovery.md` | `docs/26-feature-readiness-spec.md` | Real vehicle info, all-ECU fault display/single Clear All, history read/add and all applicable easy coding |

Task A code is merged into main through PR #12; see
`tasks/protocol-library-migration-verification.md` for the API, exact library
boundary and pending owner-car/platform/release acceptance. Task B consumes
that merged API; Task A acceptance remains pending independently. Follow the
[Task B implementation plan](tasks/rea-protocol-recovery-implementation-plan.md) and
[ordered development tasks](tasks/rea-protocol-recovery-tasks.md). Task B research
can run independently; B integration uses A's merged API. Do not invent BMW
constants inside A or declare the release functional merely because libraries work.
History edit/delete/replace and advanced coding are later priority; CBS is
explicitly future scope. All applicable easy presets are required, not a
hand-picked subset. Match source-supported model/ECU/software definitions.

Answers live in `sources/` and its extracted/reference trees, accessed through
REA for shipped artifacts. **Read `docs/27-rea-source-guide.md`** for artifact
paths, concrete class/job seeds, live tooling observations, portable evidence,
contract/ledger fields and additional-source options including ISTA+.
Ordinary upstream library source can be read without REA.

REA MCP 6.8.0 is connected as of this handoff. Android package/class/smali
inspection actually succeeded; Ghidra 12.1.4 is reported available. Do not rerun
setup based on earlier missing-engine notes. Check per-tool availability only
when needed; apktool decoding remains unavailable. Reuse retained evidence
bundles if new-session IDs are absent; do not fabricate `ev_...` references.

Current app baseline: PRs #8/#9/#11/#12 merged. The retained session (doc 23) proves
HSFZ discovery/session/VIN on the owner's F48 X1 MY2018/NBT. Optional reads were
rejected, I-level/FA successes were misleading and DTCs reached only the gateway.
Live history/coding readers are disabled pending evidence. The former add-like
history request is no longer automatically sent. Read doc 24 for library
evaluation and exact adapter obligations. Inspect current Git/PR state before
changes; this baseline does not replace current source review.

Save durable baseline and intent before history/coding mutations, then independent
readback. Fault clearing requires no saved report/backup. Interrupted writes:
reidentify, reread/compare, then user-selected recovery; no automatic replay.
Keep all I/O in CarWorker, partial coverage explicit and DEMO isolated. Source
support is not universal physical validation; exact ECU/software/definitions
gate writes. One Clear All is the only fault-clear UI action in this release.

Doc 21 owns product decisions and pending questions. Resolve only questions
needed for the current slice; continue independent research. No automated suite
or `tests/`. Full `scripts/preflight.sh` before every push; report Ruff lint,
formatting and mypy separately and actual hardware/runtime/package coverage.

Start new app code on a fresh `codex/` branch from current main and create its
own PR. Do not put app code into the docs/planning branch or reuse a merged PR
branch. Never merge without owner instruction. Follow the personal GitHub
account rule in AGENTS.md before push/`gh pr` operations.
