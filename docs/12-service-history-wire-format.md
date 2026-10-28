# Service history wire protocol — unresolved

Reviewed 2026-10-28. The earlier “fully resolved” claim contradicted its own
examples. This is the current research contract, not an encoder specification.
Original text remains in Git history.

## What is established

Research describes headunit jobs `steuern_servicehistory_add` and
`steuern_servicehistory_erase`, with semicolon-delimited **job API arguments**
containing date, mileage, dealer identity, status and service items. The owner
confirmed an NBT headunit in “Plan BMW Service History Tool” and reports that
the Windows history manager has written to this car successfully.

A PRG job may parse strings, encode binary fields, send multiple requests and
decode named results. This does not establish that the car receives the job
name, PRG filename, `JOB_STATUS` or unchanged semicolon string.

## Claims withdrawn pending evidence

| Previous claim | Current status |
|----------------|----------------|
| All `STEUERN` jobs use `0x2E` | Job-name prefixes cannot establish UDS SIDs |
| `0xA081` / `0xA080` are DIDs | Candidate constants; trace into transmitted bytes |
| The same constants are routine identifiers | Conflicts with the DID claim; unverified |
| Job arguments go on the wire as ASCII | No saved byte-level trace establishes this |
| Read history uses `31 01 A0 81` | Starts a routine labeled “add” elsewhere; not a proven read |
| All CIC/NBT/EVO/MGU share this contract | Requires per-variant/software evidence |
| `0x6E` or `0x71` proves business success | Validate echoes, result semantics and readback |
| `.bmwsh` layout equals the wire format | Local serialization is a separate format |

## Evidence needed before implementation

1. Hash the actual headunit PRG and referenced tables. Trace job entry points,
   argument parsing and every transmitted buffer, including initialization and
   diagnostic-session requirements.
2. Preserve disassembly/decompilation and byte provenance, not just `ev_...`
   IDs or nearby constants. PRG is BEST bytecode, not ordinary x86. A raw byte
   search is not a decoder.
3. Identify a genuinely read-only operation independently of add/erase. Establish
   record framing, field lengths, endianness, item codes, dates/km, pagination
   and unknown-field preservation.
4. Correlate with an existing known-good capture or planned owner-operated
   session. Record headunit/software and complete request/response ordering.
   Do not perform a destructive erase as a discovery probe.
5. Save reproducible evidence, then specify read, append, replace and erase
   independently. Do not enable a real-car encoder based on candidate constants.

## Required application behavior

Every write saves original state first, retains intended state and rereads the
headunit to confirm the result. A backup must support the advertised recovery
with vehicle/ECU identity and integrity metadata. Unknown readback/restore
semantics cannot support verified success or guaranteed rollback.

Headunit-local history, CBS counters and BMW backend history are separate
stores. Backend synchronization and CBS resets are not established here.
Append/edit/delete/replace behavior is pending in
[the decision register](21-product-decisions.md).
