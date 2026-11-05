# Remaining development — Tasks C–F

Owner priority, 2026-11-05: **CBS reading and individual resetting is next, Task C.**
“Erasing CBS” means the evidenced reset of a selected service item; it does not
mean erasing headunit history or sending a generic fault-clear request. Those
operations have separate contracts. The owner’s repeated final task letter is
interpreted as sequential Tasks C, D, E and F.

Status: Task C is implemented and verified offline; its post-PR20 continuation
has independent review, while physical acceptance remains pending. Tasks D–F
remain planned. See the
[Task C evidence](../docs/evidence/task-c-cbs-reliability.md) for exact source
restrictions. This is not a universal completion or safety certificate.
This queue supersedes the priority order in historical Task B continuation files.
Use [the capability map](../CAPABILITY-MAP.md) and
[current source reconciliation](../docs/29-source-reuse-continuation.md) for the
implemented baseline. Unchecked old aggregate checkboxes may contain completed
substeps: inspect current code and retained checks before repeating them.

| Order | Task | Required outcome |
|---|---|---|
| 1 | [C — CBS reliability](task-c-cbs-read-reset-reliability.md) | Reliable source-supported live reads and individual resets, correct ownership, complete decoding and honest completion/failure handling |
| 2 | [D — diagnostic details and clearing](task-d-dtc-details-and-clearing.md) | Source-derived occurrence/environment details, including time/km where provided, with complete read/clear accounting |
| 3 | [E — Easy Coding readiness](task-e-easy-coding-readiness.md) | Applicable options before selection, actual current values, complete non-deferred source mappings and enforced deferred-target gates |
| 4 | [F — history and integrated acceptance](task-f-history-and-integrated-acceptance.md) | Reliable local JSON/append/replacement workflows and an honest end-to-end readiness record for all current features |

Advanced coding and unvalidated safety-ECU coding remain deferred. Diagnostics,
DTC clearing and source-supported CBS service resets are not “coding” and must
not be accidentally disabled by that deferral. The current live Easy path has
no global deferred-safety-target gate; Task E must implement it before claiming
those targets are excluded. Do not exercise those coding writes in earlier tasks.

## Mandatory method for every task

1. Read `AGENTS.md`, spec-driven-development, docs index/audit, current protocol
   evidence, owner decisions, spec26, source guide27 and the relevant task below.
   Load applicable protocol, write-safety, Python, Qt, SQLite and REA skills.
2. **Recover and reuse before implementing.** Most missing behavior is expected
   in the supplied applications, recovered classes, encrypted/decrypted packages,
   PRGs/GRPs, CAFD/FAFP data and databases. Use REA to trace the actual selector,
   orchestration, request, response and decoder. Reuse the existing interpreter,
   protocol libraries and recovered data instead of rebuilding them from scratch.
3. Canonical jobs: `sources/ISTA_4.29.1x/Rheingold/Ecu/`; the legacy collection
   supplies only Task C's explicit hash-bound D94 supplement. Sources and REA
   are development-only. Use development scripts to
   compile the required standalone database/JSON/job assets. The app must not
   inspect `sources/`, run reference executables or require REA at runtime.
4. Retain artifact/version/hash, exact class/method/job/table and REA evidence,
   dependency selection, byte layouts/units/sentinels, error behavior and caller.
   Compare current artifacts to historical evidence; never relabel changed hashes.
   A description, source flag or plausible UDS identifier is not a wire contract.
5. Correct disproven specs, record a concrete file-by-file implementation plan,
   implement the recovered contract and integrate the UI. **Research or a plan
   alone does not complete a task.** Unknown technical facts remain source work,
   not permanent placeholders or new owner questions. Ask only for a genuinely
   new, unavoidable product decision.
6. Keep one protocol owner and all car I/O in CarWorker. Publish settled results,
   use foreground loading/backdrops and disable competing actions. Preserve
   deadlines, read-only enforcement, identity checks, mutation lockout, durable
   write intent/results and operation-specific application/cycle completion.
   No automatic replay or guessed retry after an uncertain mutation.
7. Exercise actual source jobs/data with meaningful one-off offline byte/error/
   interruption checks and visual Qt/DEMO checks. Independent review and fixes
   are required. No `tests/` or automated test suite. Run full
   `scripts/preflight.sh` before every push: Ruff check, Ruff format check, mypy.
8. Report source-derived support, implemented behavior, offline verification and
   physical observations separately. Only the owner's F48 is available for car
   checks; other cars are **not** a dependency for source recovery, implementation,
   offline verification or reviewed delivery. Do not call unfinished code merely
   “awaiting hardware,” and do not claim universal physical validation.

Preserve the current ISTA4.29/HSFZ milestone (D-60) and broad source-supported
F/G/U/I goal. Account explicitly for DoIP branches outside the implemented feature
paths; do not claim that connecting over DoIP establishes CBS/history/coding
write support. Transport expansion is not silently added to this milestone.

## Delivery and handoff

Inspect the worktree, local unpublished commits and PR state; preserve unrelated
work. Fetch origin before implementation. Use a `codex/` branch, never main or a
merged PR branch. Do not discard pending UI fixes to restart from main.
Use the personal GitHub account `lennoncarvalho` before push/PR commands.
**Do not open a PR unless the owner explicitly asks. Never merge it.**

Each task updates its own checklist, relevant specs/generated assets, source
coverage/dispositions, verification and remaining exact branches. Deliver a
cohesive implemented/reviewed increment when authorized. Task F consolidates
acceptance; it does not postpone the functional verification required in C–E.
