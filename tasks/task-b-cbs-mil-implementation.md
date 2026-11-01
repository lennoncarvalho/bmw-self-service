# Task B — CBS, older-engine MIL, odometer and owner-session fixes

2026-10-30. Branch `codex/task-b-cbs-mil`, created from fetched `origin/main`
(`85ed2ad`, after PR15 and PR16 merged). The owner has not asked for a PR, so none
exists. REA 6.8.0 MCP is connected in Claude Code. Physical vehicle
writes: **none**.

## Plan (ordered queue items 1–2 and 6)

1. Owner's read-only session log (2026-10-29): fix the observed defects.
2. Five older-engine MIL readers: owned F303 clear/define/read/cleanup.
3. Odometer, then exact engine measurements.
4. DoIP full-width address mapping: bound the source search.
5. CBS read and reset (D-58), with durable intent/results.
6. Independent review, fixes, offline/Qt/DEMO checks, preflight, push.

## Implemented

| Commit | Scope |
|---|---|
| 152df53 | F303 MIL sequence (`app/mil_block.py`), explicit 2C clear/define in `uds.py`, confirmed UI action under lockout; HSFZ late-reply quarantine; I-level trailer |
| ade79c0 | Odometer: cluster D122 or KOMB01/KOMB25 D10D−D114, BDC/FEM 1700 fallback; owner-session and odometer/DoIP evidence |
| 38d9857 | 83 engine measurements over 17 exact definitions; shared regional locale |
| 35edb75 | Review fixes: quarantine bounded to 30 s, then reconnect; honest not-attempted MIL steps; detail ranking |
| ddd0dd0 | CBS read/reset (`app/cbs.py`, `ui/cbs_panel.py`), 44 definitions; MIL UI retention/warning review fixes |

Contracts: [MIL block](../docs/evidence/task-b-mil-block-recovery.md),
[odometer/DoIP](../docs/evidence/task-b-odometer-identity-doip.md),
[CBS](../docs/evidence/task-b-cbs-contract.md),
[owner session](../docs/evidence/task-b-owner-session-20261029.md).

## Verification (offline, one-off; no tests/ suite)

Scripts and screenshots are retained in
`~/BMW-Tool/investigations/task-b-cbs-mil-20261030/`. Each one drives the real
owner/udsoncan/HSFZ stack against a scripted local fake gateway.

- `mil_block_check.py` (11 cases):
  - exact wire order, a pending reply, and a concurrent request that stays queued until cleanup
  - value 0/1; define rejected; read invalid/rejected; cleanup rejected
  - read/define timeout (connection replaced, no cleanup on a dead stream)
  - read-only rejected at the transport and in the worker; identity change; no replay; I-level from the owner car's bytes
- `quarantine_check.py` (4 cases):
  - the owner car's slow ECU: inventory continues, reuse is blocked, then resolved
  - a late pending reply does not resolve the block, the final reply does
  - a partial frame closes the connection
  - an unresolved block expires into a reconnect
- `odometer_check.py`: KOMB25/KOMB01 arithmetic, FFFFFFFF and offset sentinels, BDC range fallback, D122 shape, unknown variants send nothing.
- `engine_ui_check.py`: DME_BX8 scaling; overview rendering with pt_BR fallback.
- `cbs_check.py`:
  - v5/v6/6.3 decode and sentinels; encoder bytes; per-owner coverage
  - BDC never asked; duplicate owner blocks reset
  - verified with a pending reply; response-confirmed only; state changed; rejected; wrong echo; trailing byte; timeout
  - v6 detail read; read-only, power and journal-failure guards; blocked branches
- `mil_ui_check.py`, `cbs_ui_check.py` and the reviewer's `wipe_check.py` (Qt offscreen):
  - confirmation, lockout and result retention
  - persistent cleanup warning; read-only refusal
  - DEMO CBS decode with no reset; live read → reset → verified → automatic re-read
- Mutation probes (V1): removing the abort guard, widening the MIL value set, letting a pending reply resolve quarantine, disabling quarantine, accepting any `6E`, skipping the before-record check, and dropping the duplicate block each failed a check. The cleanup-reserve budget is not probed.
- `scripts/preflight.sh` passes: ruff check, ruff format --check, mypy over app/ ui/ main.py.

Independent review of 152df53 found 1 Medium and 4 Low issues; all are fixed (35edb75 and ddd0dd0).

Independent review of the CBS commit found 1 High, 3 Medium and 4 Low issues; all are fixed in the next commit:
- **High:** a reset could run with an unverified VIN. A valid VIN is now required at planning and in the worker.
- **Medium:**
  - The outcome was "verified" when the count was the sentinel and nothing changed.
  - Partial owner coverage now blocks every reset, because ownership is unproven.
  - The CBS read now has one 30 s overall deadline.
- **Low:**
  - "Uncertain" is reported only after the reset bytes were actually transmitted.
  - A negative identity reply no longer drops the connection.
  - The v6 `22 10 02` reason is decoded and shown, and the wording distinguishes "no re-read" from "unchanged".
  - The CBS rows are always re-read, or cleared, after any reset outcome.

## Remaining (source or physical, not hardware-blocked development)

- **Physical, owner-operated:**
  - read-only `22 10 01` at 0x12, 0x29 and 0x60
  - an odometer read compared with the cluster display
  - a confirmed CBS reset of one item
  - the MIL lamp state against DME_BX8 4A69 = 1
- **CBS:**
  - DSC_25 SVK-gated reset sequence
  - D94 6.3 routine reset type (TT) and whether `31 03` is required
  - KOMBSP21 reset job and DME9FF_R CBS absent
  - count wrap at 30
- **DoIP/U/I:** no supplied artifact converts addresses. The next source is a DoIP-capable EDIABAS/ISTA+ configuration or a pinned EdiabasLib DoIP branch.
- **MIL:** DME9FF_R/EDMEI1 alternate path; DME98_R/FCCU definitions absent.
- **Identity:** BDC_G05/ZGW_SP18 `2540` decoder; no production-date source.
- **Diagnostics:** category/description reconciliation (queue 3). Then easy coding (queue 7); the owner car lacks exact coding definitions for 12 ECUs.
  - Easy source path (not taken by Claude; left for another coder): ISTA
    `DiagDocDb.sqlite` → English fault short texts and ECU titles for the
    category/description reconciliation; ISTA 4.29 CAFD (all 12 CAFD IDs/versions
    confirmed present) or BimmerCode `coding_data/*.enc` → the 12 missing F48 ECU
    coding definitions. See [../docs/claude-session-limitations.md](../docs/claude-session-limitations.md).
