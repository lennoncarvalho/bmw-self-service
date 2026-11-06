---
name: vehicle-write-safety
description: Review feature-specific baseline, intent, application completion and recovery for vehicle mutations.
---

# Vehicle write integrity

Read `plan.md` and the relevant contracts in `docs.md`; inspect current code.
A write needs exact vehicle/ECU/software/definition, confirmed intent, power policy,
durable required state and exclusive protocol ownership.

- Coding: save the complete original baseline/target bytes, immutable intended
  bytes, source hashes and meaningful observed post-state. Preserve unrelated
  groups, masks and Custom values. A UI index is not an encoder or baseline.
- History: existing car history cannot be read/backed up. Save local JSON,
  reviewed append/replacement intent, exact requests and per-step outcomes with
  prior car history explicitly null/unavailable. No reader or fake baseline.
- CBS: exact primary owner/item, fresh software/before-state and journal; retain
  source-specific routine/result or planned DSC occurrence sequences.
- Fault clearing: no saved backup/report prerequisite; preserve target coverage
  and reread results. Cleared faults cannot be restored from a report.

No write Cancel or disruptive app actions. Persistence failure before sending
blocks the mutation; failure after a step stops later mutations and preserves
in-memory outcomes. Exact application results and source-required activation/cycle
semantics determine completion. A transport ACK alone is insufficient; distinguish
response-confirmed from observed verification. Universal immediate readback is
not required where the source needs a cycle or provides no meaningful reader.

No automatic replay, resume or rollback after uncertainty. Reidentify and inspect
actual state/results before a separately confirmed recovery. Restoration is a new
write with matching definition/software and its own verification. Do not operate
on a physical car merely to validate this skill.
