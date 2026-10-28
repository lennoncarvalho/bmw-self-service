# PR #9 review follow-up

2026-10-28. Starting head e47f6fa, branch codex/read-only-car-capture.
Owner requested findings from both reviewers, deduplication, validation and fixes.
The PR remains open; this is follow-up on its own branch, not a new feature PR.

## Plan and scope

1. Gather eight inline threads plus both review submissions/timeline. Review
   bodies repeat the inline findings. The walkthrough also reports missing
   docstrings for touched functions; track it separately from the eight threads.
2. Fix four concrete defects: initialize page capabilities before navigation,
   propagate blocked backup-preview outcomes, retain read-only network failure
   guidance and qualify the --no-log documentation.
3. Audit all send paths and add a read-only check at the low-level DoIP sender,
   documenting the two supported control-message exemptions. No active write
   bypass was found in the current caller graph.
4. Preserve the strict short-payload guards and SQLite query; do not apply
   suggestions contradicted by short-circuit evaluation or the actual schema.
5. Document touched functions missing docstrings to address the walkthrough's
   docstring-coverage warning, without changing behavior or review configuration.
6. Full preflight and source checks; no automated suite, car requests, network
   configuration or REA work. Commit/push to PR #9, resolve dispositioned threads,
   verify CI. Do not merge or trigger another reviewer with a comment.

## Deduplicated dispositions

| Comment | Verification and disposition |
|---------|------------------------------|
| [4405020469](https://github.com/lennoncarvalho/bmw-self-service/pull/9#discussion_r4405020469) — Robin: short payload IndexError | False positive. Both public send_uds methods reject empty payloads; 10/3E use len(payload) == 2 and payload[1]... so indexing is short-circuited for short inputs. The suggested >=2 would weaken the exact-length boundary. No code change. |
| [4405020488](https://github.com/lennoncarvalho/bmw-self-service/pull/9#discussion_r4405020488) — Robin: audit read-only send paths | Current callers checked: HSFZ send_uds guards reads; its keepalive paths send fixed 0012 / 3E 80. DoIP send_uds guards diagnostics, TesterPresent is fixed 3E 80 and remaining TCP sends are routing activation / alive response. No active bypass. Add a defensive policy check inside _send_doip as well; allow only diagnostic reads and the two supported control kinds in read-only mode. Document discovery/control exemptions. |
| [4405020500](https://github.com/lennoncarvalho/bmw-self-service/pull/9#discussion_r4405020500) — Robin: coding writes need flag guards | _on_write and restore_backup already check _live_unavailable before proceeding. No missing handler check. Related initialization window is fixed under 4405222519; initialize default state closed too. No redundant helper required for two existing guards. |
| [4405222471](https://github.com/lennoncarvalho/bmw-self-service/pull/9#discussion_r4405222471) — CodeRabbit: ambiguous fetchone | Not valid for the supported schema. Read-only sqlite_master/PRAGMA inspection confirms PRIMARY KEY(code, table_type) backed by a unique index. The query fixes both values to non-null code and FORTTEXTE, hence at most one row; UPPER(ecu) can only filter that row. fetchall cannot recover collisions already discarded during extraction. Keep query; source/data extraction gap remains separately tracked in A-16. |
| [4405222510](https://github.com/lennoncarvalho/bmw-self-service/pull/9#discussion_r4405222510) — CodeRabbit: --no-log wording | Valid. State that launches without --no-log create a session file in README and validation guide. |
| [4405222519](https://github.com/lennoncarvalho/bmw-self-service/pull/9#discussion_r4405222519) — CodeRabbit: live page initialization window | Valid. Configure History/Coding for the real connection before enabling navigation or starting post-connect loading. Keep later final-data refresh. Start coding write/restore state closed until an explicit DEMO connection enables it. |
| [4405222535](https://github.com/lennoncarvalho/bmw-self-service/pull/9#discussion_r4405222535) — CodeRabbit: false backup restore success | Valid. Return bool from restore_backup, report blocked outcome in BackupsPage, and show success only when local preview loads. Clarify that loading a preview does not restore vehicle data. |
| [4405222543](https://github.com/lennoncarvalho/bmw-self-service/pull/9#discussion_r4405222543) — CodeRabbit: discovery explanation lost | Valid. Match the read-only discovery failure before the generic not-found mapping so the dialog retains the disabled DHCP/network-change explanation. |

| [Walkthrough docstring check](https://github.com/lennoncarvalho/bmw-self-service/pull/9#issuecomment-6478243051) — CodeRabbit | Valid documentation gap. The bot reported 61.29% coverage on its scoped functions. AST/source inspection identified undocumented touched methods and callbacks; add concise behavior/ownership docstrings. No test generation, bot invocation or threshold/configuration changes. |

## Verification

Observed locally: scripts/preflight.sh passes Ruff lint, Ruff format and mypy
across all 18 application source files; git diff --check is clean. Source tracing
confirms the page setters run before navigation becomes enabled and the existing
later calls still refresh final data. Both restore outcomes reach distinct user
messages. The low-level DoIP policy check precedes all socket access.

Read-only inspection of sqlite_master and PRAGMA index_list confirms the composite
primary key and unique index; no database data/schema was altered. No automated
behavioral suite, GUI/vehicle run, network configuration or REA work was performed
for this follow-up. Static checks cannot validate a vehicle or establish new
manufacturer mappings. The owner's source-first REA gap plan follows the planned
vehicle run; this review introduces no guessed read/write contracts.
