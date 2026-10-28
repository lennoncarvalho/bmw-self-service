---
name: vehicle-write-safety
description: Specify or review backup, write, readback and recovery flows for coding, service history and diagnostic clearing in BMW Self Service.
---

# Vehicle write integrity

Owner requirements (2026-10-28): coding/history write screens save a backup
first, retain current/intended state and read the car back to confirm. The owner
explicitly exempts fault clearing from saving a backup/report. Do not add that
step. Interrupted writes require reread/compare before user-chosen recovery; no
automatic replay. Read `docs/21-product-decisions.md` for decisions and limits.

Before a coding/history write, identify VIN, transport, ECU address, hardware/software and exact
data definition/version. Read and validate all affected original data. Save a
durable, uniquely identified backup containing original bytes, decoded display
data, schema/app version and integrity hashes. Preserve the baseline; store
intended state and observed readback separately. A UI option index is neither
an ECU value nor a restorable backup.

No coding/history mutation proceeds with missing/mismatched coding definitions, guessed DIDs,
incomplete original reads, failed backup persistence or an unknown encoder.
Easy and advanced modes share the same verified write engine. Review data-group
boundaries, masks and preservation of unrelated bits; combine changes against
one baseline rather than overwriting prior changes with later full-block writes.

Validate application responses, then reread and compare affected data before
reporting success. Account for ECU normalization and expected restart semantics
only when documented. A transport ACK, successful `sendall()` or positive UDS
response alone is insufficient. Report partial success and uncertain outcomes.

After timeout or disconnect, do not automatically replay a mutation. Reidentify
the vehicle/ECU, inspect the observed state and offer only evidenced recovery.
Restoring is itself a write requiring matching identity and verified readback.
Never imply a diagnostic report can reinsert cleared DTCs or restore readiness.

Do not operate on a car merely to validate this skill. Establish behavior with
reviewed artifacts and the owner's agreed vehicle validation procedure.
