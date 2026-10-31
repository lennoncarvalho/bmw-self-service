> **2026-10-30, D-59:** the app no longer reads or shows the ECU lamp command
> (4A69 / F303). The overview indicator follows engine fault memory. This record
> is retained as source research; `coding_data/mil_contracts.json` remains only
> as input to `scripts/recover_engine_measurements.py`.

# Older-engine MIL block lifecycle recovery — 2026-10-29

Status: **primary implementation reference**; **implemented 2026-10-30** in
`app/mil_block.py` (commit 152df53) as an explicit confirmed action. The
generator now fingerprints `STATUS_BLOCK_LESEN` against the reviewed hash below
and marks the five rows `dynamic-block` (DID 4A69, slot F303). Overview refresh
still never defines a DID. Offline fake-gateway checks cover exact wire order,
pending replies, exclusivity, rejection/invalid/timeout/cleanup outcomes and
read-only rejection; see `tasks/task-b-cbs-mil-implementation.md`. No physical
observation exists for these engines (the owner's car uses direct DME_BX8).
DME9FF_R/EDMEI1 alternate MIL and DME98_R/FCCU definitions remain source work.

## Exact block source

All five original PRGs have the same complete `STATUS_BLOCK_LESEN` control flow,
after normalizing absolute BEST labels: SHA-256
`6ddbe56e3449b7195d15a71d56d9475831dd0d6095987b4b6cc14a82503a9675`,
31,180 disassembly lines each. Exact artifact/listing hashes, table references
and Android method Evidence IDs are retained in
[the machine-readable record](task-b-mil-block-recovery.json).

| Definition | STATUS_BLOCK_LESEN entry |
|---|---|
| MSD85L6 | `0x3FE8E` |
| MSD85YL6 | `0x3FE49` |
| MSD87 | `0x66354` |
| MSV90 | `0x4D351` |
| N55_ALP | `0x43DEE` |

These PRGs do not contain a generic `STATUS_LESEN` job. Files bearing that suffix
in the older breadth investigation directory actually contain the fixed
`STATUS_MESSWERTE` listings selected for inspection; their names must not be
used as proof of a direct generic reader. The enabled 17-definition direct-job
fingerprints are unaffected.

The block job accepts block number 0–255, a definition flag and ARG/ID/LABEL
selection. With definition enabled, it clears `F3nn` using `2C 03 F3 nn`, defines
selected source identifiers with `2C 01 F3 nn`, then reads `22 F3 nn`. With the
flag disabled it skips configuration but still reads `F3nn`; it does not switch
to a direct `22 4A 69` request. Each exact `ISMIL` table row is unsigned char,
unit `0/1`, identity scaling, source identifier `4A69`, service `22;2C`.
That metadata alone is not a complete independent direct-read contract.

Representative MSD85YL6 coordinates (identical normalized control flow in all
five): `0x40FC3` tests the definition flag; `0x411CF` sends the constructed clear;
`0x41B64` checks its returned F3/block echo; `0x41D8E` starts the definition;
`0x478D4` and `0x47A37` check definition subfunction/identifier echoes;
`0x47C37` constructs the F3 read; `0x48627` sets positive-data cursor to 3;
`0x4983B` extracts a one-byte value; `0x4BA8E`–`0x4BAF8` reject values other
than 0 and 1. A single selected ISMIL byte therefore follows the dynamic DID
in the positive response. The app's existing strict boolean semantics remain
applicable; no fault-count or truthiness inference is justified.

## Android allocation and polling contract

REA/JADX traced the supplied diagnostics APK (SHA-256
`da6f5b39efaa590fce68782f439c1b8f1b9f09ed41344055b8ff80666cae00d5`):
`j6.v.u0 → k6.y.a → k6.x.d → k6.c0.l/m` for UDS engine sensor selection.
`k6.c0.m` clears the explicit slot **F303**. `k6.c0.b.b` constructs
`2C 01 F3 03 <sensor ID BE16> 01 <sensor byte length>`; its nested callback reads
`22 F3 03` to check availability. The later grouped path
`k6.x.j → k6.x.b.b → k6.x.b.a.b` clears that same slot and constructs the same
four-byte source descriptor for each selected sensor. `k6.x.i` polls `22 F3 03`.
`k6.x.d.b` removes three PDU bytes and slices the data by each sensor byte length.

For the five exact ISMIL table definitions the prospective one-value sequence
is therefore `2C 03 F3 03`, `2C 01 F3 03 4A 69 01 01`, `22 F3 03`.
The checked positive shapes from the PRG are `6C 03 F3 03`, `6C 01 F3 03`,
then `62 F3 03 <00|01>`. This is a source-derived future contract, not an
implemented or physically observed transaction.

The Android callbacks check negative/SID status more weakly than the PRG's echo
checks. A reconstruction must preserve the stronger subfunction/DID/shape
validation rather than copy those weak checks. Source probing/cache and
continuous polling do not establish that a value is always available on a car.

## Ownership and cleanup work required before enabling

The traced stop path `k6.x.c → k6.c0.h` only sets local stop flags; it sends no
cleanup clear. The reviewed polling path leaves F303 defined. This is a bounded
source observation, not proof that every lifecycle path in the APK lacks cleanup.
No preservation/restoration contract for a prior external F303 definition was
found in these methods, and no cross-client exclusivity may be assumed.

The next implementation must own clear/define/read/cleanup as a single protocol
operation, with one absolute budget including queueing and any evidenced timing;
prevent another request sequence from redefining F303 between steps; track
whether definition/cleanup was response-confirmed, rejected, or uncertain; and
avoid replay after a stream failure. A cleanup clear is a proposed app lifecycle
improvement using the recovered clear contract, not an observed Android shutdown
behavior. A successful MIL result must not hide a failed/uncertain cleanup.
The current `operation_scope` shares deadlines but does not serialize a whole
multi-request sequence, so it is insufficient by itself. `--read-only` must
continue rejecting `2C` at the transport boundary; this path cannot be silently
promoted to a pure read. Do not add these mutations to ordinary overview refresh
until that owned lifecycle and visible operation policy are implemented/reviewed.
These are software/source tasks; additional vehicles are not a prerequisite.

## Alternate and absent definitions

The original APK's exact decrypted engine sensor lists were checked:
MSD85L6 355 rows, MSD85YL6 346, MSD87 325, MSV90 303, N55_ALP 348,
DME9FF_R 1,024, EDMEI1 6. None contains a sensor row matching `4A69`, the
MIL-lamp/actuation labels or `S_MILLAMP`. Member/plain hashes are in the JSON
record. This bounded negative search does not prove absence of all alternate
MIL contracts. DME9FF_R and EDMEI1 also have no direct ISMIL table row in the
exact supplied PRGs; alternate engine-reader selection remains unresolved.
DME98_R and FCCU still lack exact PRGs in the supplied Ecu directory; no
related-name replacement is justified. Keep these four branches explicit.

## Retention and limits

Portable REA export:
`/Users/lennon/BMW-Tool/investigations/task-b-mil-block-20261029/rea-evidence.json`,
SHA-256 `5d9ab857ef104aa043f9d4c1a1ea673e91f3592ef583a23c5e88de1f47509a05`.
The same directory retains all five complete BEST listings and their fingerprints.
REA 6.8.0 / JADX 0.7.1 static inspection; no source application execution,
vehicle traffic, dynamic DID change, physical lamp observation or hardware
acceptance. Runtime assets and current request counts remain unchanged.
