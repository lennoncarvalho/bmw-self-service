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
