# Future REA job — CBS reads and resets

Requested by the owner on 2026-10-28. **Future scope; not implemented or scheduled.**
The owner currently uses ISTA+ for CBS. Current history work covers headunit-local
records, including add/edit/delete/replace; a history write is not a CBS reset.

## Objective

Document the actual Condition Based Service read/reset contracts for the first
validation vehicle (F48/NBT), then identify differences for other target variants.
Use the owner's reference software/artifacts where available. The current source
inventory does not establish a supplied ISTA+ installation; locate the authorized
artifact before claiming analysis. Do not download a replacement automatically.

## Research deliverables

1. Record exact source versions/hashes and inspect service-item definitions,
   responsible ECUs, request/response encoders and runtime preconditions.
2. Separate read-only status (remaining distance/time, due date, reset counter,
   reset eligibility) from reset/control actions. Determine units, scaling,
   endianness, unavailable values and per-item/variant identifiers.
3. Trace session/security requirements and reset conditions from primary evidence;
   do not infer them from job names or reuse service-history candidate constants.
4. Preserve exact byte sequences, parser rules, source locations and limitations.
   Prefer existing captures and static analysis before any vehicle mutation.
5. Interview the owner on item selection, confirmation, partial reset, failed
   preconditions, readback/reconnect and whether a backup can actually restore
   counters. Current coding/history backup rules do not prove reversibility.
6. Produce a scoped CBS spec and acceptance procedure before implementation.
   Include before/after readback and the no-automated-tests policy in effect.

No CBS command, reset, simulation of a completed reset, or automatic retry is
part of this initial audit. No scheduling/monitoring automation is created.
