# History journals and writes — PR16 implementation plan

Owner request2026-10-29: include journals/writes in this existing PR. Branch
codex/task-b-cbs-priority, baseline dc59c30. No new PR, merge or vehicle execution.
Apply spec-driven, protocol, vehicle-write-safety and Qt/Python review skills;
D-50–D-55/workflow28 override obsolete history baseline/readback skill text.

1. Recover exact ADD/ERASE/session/activation/result chains across supplied
   headunit definitions and runtime writer, with REA/provenance. Update evidence
   and specs for disproven claims before enabling requests. Capacity rejection
   stops append without fallback; no destructive capacity discovery.
2. app/history_journal.py: independent history-operation schema, immutable local
   before/intent/exact plan/target/encoder hashes, null prior vehicle history,
   durable per-step outcomes, bounded data-only view/export and known-date/draft
   accounting. Preserve coding schema and editor interchange unchanged.
3. app/history_write.py: frozen mode plans, exact catalogue/identity selection,
   fresh VIN/F150/F101 preflight/revalidation, single-owner whole execution,
  30second perrequest/300second overall deadlines, checked business/echo outcomes,
   stop on first failure, uncertainty/partial/no retry and durable failure handling.
4. ui/service_history_page.py + main_window: explicit append per unsent draft and
   separate reviewed replacement; exact target/list/order/irreversible-loss/power
   confirmation. Global no-Cancel lockout includes scans/refresh/navigation/close.
   Show journals separately from draft records, export in-memory failure evidence
   and manual iDrive/cycle instructions; no readback or restore promise.
5. One-off byte/error/persistence/deadline/identity/read-only/partial checks,
   actual Qt/DEMO visual checks, independent review/fixes and full preflight before
   push to existing PR16. No tests/ suite or physical writes.

## Review follow-up — 2026-10-29

The history-operation journal and mode-specific append/replacement workers are
implemented in `app/history_journal.py`, `app/history_write.py` and
`ui/service_history_page.py`; physical validation remains pending. See the
[recovered execution contract](../docs/evidence/task-b-history-write-contract.md).

Review-fix plan: reconcile current handoff/status text and CBS contract links;
restore offline History → Vehicle → Welcome navigation; filter journals by VIN
and environment before full validation/counting and show actionable listing
limits. Verify with one-off offline/Qt checks and the full quality gate.

Observed locally: all five findings were still valid and fixed. One-off journal
filter/integrity/byte/count boundary checks and actual offscreen Qt navigation,
lockout and file-worker limit-message checks passed on Python 3.13.15/Qt 6.12.0.
Full Ruff lint/format and mypy passed across all 39 app files; dependency audit
found no known vulnerabilities. Added local links/anchors and whitespace checks
passed. No vehicle requests or physical acceptance were performed. CBS app code
and verification results remain pending; contract links identify the current plans.
