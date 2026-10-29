# Task B — CBS reading and writing before coding

**Current implementation scope under D-58 (2026-10-29).** This existing path is
retained for incoming links; the old deferred/research-only status is superseded.
CBS read/write is due after history work and **before easy and advanced coding**.
Do not require completion of coding to implement CBS. Headunit service-history
entries and Condition Based Service counters/reset operations remain separate.

## Starting source and observed limits

Owner-provided reference:
[cbs.py](https://github.com/devttys1/bmw-service-manager/blob/6c0041bb71674ec52d567c4a6360b5469c048173/bmw_service_manager/cbs.py),
repository main verified at commit`6c0041bb71674ec52d567c4a6360b5469c048173`;
Git blob`f69332631214eef2573c3b9509b500e0ac7a8719`. Retrieved and inspected
2026-10-29. This is ordinary upstream Python source, not a new REA binary trace.
Earlier related-source inspection is retained in
[the source findings](../docs/evidence/task-b-history-new-sources.md).

Concrete porting anchors, **primary implementation reference**:

- `read_cbs`/`read_item` query cluster address60, DIDs4101–417F;4100is described
  as a summary. `decode` uses big-endian item/availability/counter/interval/
  signed-distance/date fields, including unavailable/empty cases. Retain raw
  bytes and verify full response shape/echo, not just a successful request.
- `read_dme_status` reads1001at12. `owner`/`RESET_ECU` associate oil/additive,
  brake and cluster items with12/29/60. The source defaults unknown items to60;
  do not port that as permission to probe unknown write owners.
- `reset_payload`/`reset_request` build a 2E 10 01 reset record with one-item count,
  availability 100, service increment and unchanged-field sentinels. Preserve
  exact field widths; corroborate version-specific meanings against target jobs.
  `reset_cbs` relies on its client to detect rejection; inspect that transport
  and callers before deciding which final replies establish completion.
- Source comments report an F-series cluster before/after observation and an
  F48B47D83BX7C0version6lead. They leave flag/status meanings unresolved and
  describe part of the version6layout as a presumption. These are bounded
  upstream claims, not observations on this project's F48/NBT or proof for
  every F/G/U/I ECU/software combination.

The reference substantially reduces the initial search space. Port complexity
still depends on exact variant/version and response semantics; do not call
unresolved branches complete merely because the module is small. Review the
repository's existing license/provenance findings before reusing code; legal
notices remain separate from protocol correctness. REA remains appropriate for
supplied PRGs/binaries and missing source facts, never a runtime dependency.

## Implementation sequence and files

1. **Recover/specify:** inspect the linked module, its `hsfz.py`/callers/item
   catalogue and actual supplied CBS read/reset jobs. Retain source revisions,
   hashes, exact methods/jobs, full requests/replies, item ownership, session/
   authorization/preconditions, units/sentinels, version limits and completion/
   cycle semantics. Add B-CBS-R/B-CBS-W rows to the feature support matrix.
2. **Read:** add standalone `app/cbs.py` and generic embedded definitions where
   required. Use CarWorker and Task A's existing owner/API, no second transport
   or socket reader. Integrate a Qt Widgets due-service view/section with settled
   loading, per-item coverage, English labels, raw detail and unavailable states.
   Resolve UI placement within existing single-window conventions.
3. **Write:** implement actual source-supported CBS writes/resets, not a permanent
   disabled button. Freeze exact item/owner/identity/intent/request before send;
   durably preserve before-state and per-step results in a separately versioned
   CBS record (reuse persistence primitives without weakening coding validators
   or mislabelling this as restorable ECU data). Confirm selected item/effects,
   apply existing known-low-power block/unknown-power acknowledgement and global
   mutation lockout; no Cancel or automatic replay. Unknown owner/encoder blocks
   that mutation and opens a concrete source task, not a speculative send.
4. **Complete/error:** check positive/negative echoes and application results;
   reread meaningful CBS state at the recovered completion point, with cycle
   instructions when required. Preserve partial/rejected/unattempted/uncertain
   outcomes. After interruption reidentify/reread before a separately confirmed
   action. Do not promise rollback of reset counters or replay automatically.
5. **Verify/deliver:** one-off offline byte/endianness/sentinel/item/negative/
   timeout/deadline/read-only/no-retry/persistence/partial checks; Qt/DEMO visual
   checks, independent Python/Qt/protocol/write review and corrections; full
   `scripts/preflight.sh` before every push. No tests/ suite. Deliver a separate
   implementation PR with exact support limits and updated handoff.

Default30second request/operation scopes include queueing/pending; document any
source-required longer bounded sequence. All car I/O stays on CarWorker and one
protocol owner. No reset on connection/page loading; --read-only rejects writes.
CBS fields/IDs are distinct from the14history item choices; reconcile names from
actual source instead of assuming shared numeric codes mean identical services.

## Acceptance

- Both CBS reading and writing implemented for recovered applicable branches,
  with a concrete disposition for remaining source branches; no F48-only shortcut.
- Correct service-due values, raw provenance and per-item unknown/error coverage.
- Exact owning ECU/software/version, durable before/intent/results, checked
  completion/post-state and honest irreversibility/uncertainty for writes.
- Standalone/offline app, independent review, meaningful offline/UI checks and
  green full-app Ruff lint, format check and mypy.
- Owner-operated F48/NBT observations recorded separately when performed. No
  other vehicle is needed for recovery, implementation/review or PR delivery.

No CBS app code, vehicle requests or physical reset is performed by this
priority-documentation change. No broad owner interview is a prerequisite;
ask only a genuinely new unavoidable product decision exposed during recovery.
