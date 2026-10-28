# Diagnostic descriptions and DTC decoding

Reviewed 2026-10-28. Database facts and vehicle interpretation are separate.
The database remains a static read-only asset.

## Locally measured facts

There are **88,580 rows**, with **71,439 nonempty English texts**. These are
not counts of unique fault codes or professionally verified translations.

| Table type | Rows |
|------------|------|
| FORTTEXTE | 55,315 |
| IORTTEXTE | 16,091 |
| PCODETEXTE | 8,388 |
| FUMWELTTEXTE | 6,685 |
| FARTTEXTEINDIVIDUELL | 1,202 |
| IUMWELTTEXTE | 558 |
| FARTTEXTEERWEITERT | 242 |
| IARTTEXTEERWEITERT | 38 |
| FARTTEXTE | 33 |
| HORTTEXTE | 27 |
| POSWHEBELTEXTE | 1 |

Schema: `code`, `text_de`, `text_en`, `ecu`, `table_type`, `translated`, primary
key `(code, table_type)`. ECU is not part of the key: investigate collapsed
cross-ECU collisions before claiming complete ECU-specific coverage.

## Database access

Use an escaped file URI with `mode=ro`, parameterized queries and documented
connection ownership. Do not rebuild the database or enable WAL during lookup.
Read-only mode does not remove Python connection thread affinity. A singleton
service need not mean one SQLite connection shared across threads. See
[Python sqlite3](https://docs.python.org/3/library/sqlite3.html#sqlite3.connect).

Query the intended table type and ECU context; `WHERE code = ? LIMIT 1` can
select an unrelated kind of description. Unknown codes remain unknown. English
falls back to German; machine translation remains unverified. B-tree lookup is
not guaranteed O(1); measure performance and inspect query plans.

Read-only does not mean immutable or independent of WAL sidecars. Check asset
integrity and packaging before selecting immutable mode. See
[SQLite read-only/WAL behavior](https://sqlite.org/wal.html#read_only_databases).

## UDS decoding corrections

`19 02 <mask>` returns `59 02 <availability mask>` followed by repeated
`<DTC:3 bytes><status:1 byte>` records. Records begin at offset **3**, not 2.
Validate SID, subfunction, size and alignment. Mask `0x08` selects confirmed
DTCs, not all pending/current faults.

`19 03` identifies DTC/snapshot-record-number pairs. The earlier timestamp/km
layout was unsupported. `19 04` reads snapshot records; `19 06` reads extended
data. Codecs and lengths are ECU-specific: preserve raw unknown data rather
than inventing dates or mileage. See the
[ReadDTCInformation implementation](https://github.com/pylessard/python-udsoncan/blob/master/udsoncan/services/ReadDTCInformation.py).

Status bit 7 means warningIndicatorRequested, not a standalone global emissions
MIL reading. Status bits are not `FARTTEXTE` fault-type codes. The previous
hex-nibble “platform/ECU” interpretation of `B7F805` was unsupported. Retain
ECU identity and DTC format when interpreting codes.

## Clearing and MIL

`14 FF FF FF` requests all DTC groups on the addressed ECU; check the response
and reread that ECU. An incomplete scan is not “no faults.” Do not deduplicate
the same code across different ECUs. Single-code clears and the old claimed
powertrain/chassis/body group constants need ECU-specific evidence.

OBD service `01` and UDS `0x19` are different application services. MIL requires
an evidenced emissions endpoint and codec, not `01 01` sent to an assumed
gateway. Clearing does not guarantee the lamp stays off. Report readiness and
recurring faults from observed results.

The owner explicitly requires **no saved report/backup before fault clearing**.
Reread fault/lamp state to establish the result; do not add report persistence
as a prerequisite. Cleared memory, freeze frames and readiness are not guaranteed
restorable. Clear scope and confirmation wording remain owner decisions.
