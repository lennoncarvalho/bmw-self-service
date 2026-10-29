# Exact-variant MIL read contract — 2026-10-29

Status: **primary implementation reference**, independently inspected offline.
No vehicle request, PRG execution, lamp actuation or physical validation was
performed. This completes the direct decoder trace behind the earlier
[dashboard lead](task-b-dashboard-read-findings.md); it does not establish
compatibility with the owner's engine or every BMW.

## Original artifacts and selection

The format-aware reference parser `BimmerDaten/decoderPrg.py` was used to inspect
the original BEST jobs and tables, rather than treating PRG bytes as native x86.
No reference parser or PRG interpreter is required by the application at runtime.

| Original under `sources/Ecu/` | SHA-256 | STATUS_LESEN job offset |
|---|---|---|
| MEVD172.prg | `c0ba4f472218f79cd18954eb6b6763aa8782b9f0b259afa1d23bfc8613468c97` | `0x150F4` |
| MEVD172Y.prg | `849576ee032504f53012ba3ef20d67c1844f157b6df7de470f5ca71e59e6b3b6` | `0x15149` |
| MEVD1725.prg | `e5d4866a9b8cdeb51c638a29ba508ca4cb52ba5bb9670236e4ec6d13648f45dd` | `0x150FD` |

All three `SG_FUNKTIONEN` rows specify `ARG=ISMIL`, `ID=0x4A69`,
`RESULTNAME=STAT_MIL_EIN_WERT`, `EINHEIT=0/1`, `LABEL=B_mil`,
`DATENTYP=unsigned char` and allowed services `22;2C`. The descriptions are
MIL-Ansteuerung / Bedingung MIL Lampe Ein. Scaling, result-table and per-row
address overrides are absent. The complete STATUS_LESEN disassemblies are
identical after absolute-label normalization; normalized SHA-256 is
`211d8e9fb1141035244b0379ee629811365cebc6fdb278a914c73ab773ef4893`.

Exact identity mapping comes from the diagnostics APK's original
`assets/dat/ecu-variants.enc`, not a name-prefix or chassis guess:

| HSFZ address-index from F150 | Exact catalog name |
|---|---|
| `12 0F13F0` | `MEVD172` |
| `12 0F1910` | `MEVD172Y` |
| `12 0F17F0` | `MEVD1725` |

APK SHA-256 is
`da6f5b39efaa590fce68782f439c1b8f1b9f09ed41344055b8ff80666cae00d5`;
encrypted member SHA-256 is
`c88b107140ec7ddf22afc356207b16c5999c68246a4e682a20af166f7dbf1360`;
decrypted member SHA-256 is
`110fd7b85f512ebec08be7d843ca6f23a8551d152bf28194f0c95cb9b9441460`.
The original lookup route is `j6.v.O` / `v$d0.b` / `j6.h.f`: first three
data bytes of `62 F1 50` become uppercase hex and combine with the ECU address.
[Catalog provenance](task-b-diagnostic-catalog.json) and
[recovered contracts](task-b-recovered-contracts.md) retain the extraction,
REA records and deterministic asset-generation route.

## Request and response extraction

For a uniquely identified matching engine on HSFZ address `0x12`, send one
read-only request `22 4A 69`. The source job begins with service `22`, resolves
the selected ID from its table and appends the DID in big-endian order.
It contains no diagnostic-session change, security access, dynamic definition
or lamp-actuation exchange. Do not call `STEUERN_MIL` to obtain this value.

The PRG sender wraps the PDU in its own transport representation, checks frame
length/source/target and removes that representation before interpreting S3.
Those PRG wrapper bytes are not an additional application-level HSFZ header.
The application continues using Task A's existing transport owner/correlation.

| Decoder stage | MEVD172 | MEVD172Y | MEVD1725 |
|---|---|---|---|
| xsend, target set to `0x12` in preceding sender | `0x16C77` | `0x16CCC` | `0x16C80` |
| Transport-wrapper removal block | `0x16CEB` | `0x16D40` | `0x16CF4` |
| Initialize response cursor to 1, after positive SID | `0x17051` | `0x170A6` | `0x1705A` |
| One-byte scalar extraction branch | `0x18ABC` | `0x18B11` | `0x18AC5` |
| Scalar length check | `0x19BCA` | `0x19C1F` | `0x19BD3` |
| Emit named numeric result | `0x1AF34` | `0x1AF89` | `0x1AF3D` |
| Zero/one validity comparisons | `0x1B06C`–`0x1B0DC` | `0x1B0C1`–`0x1B131` | `0x1B075`–`0x1B0E5` |

After initializing the cursor to 1, the decoder consumes and compares the next
two bytes as the returned big-endian DID, advancing to 3. The unsigned-char
branch reads `S3[cursor]` as one byte and advances by one. The `0/1` branch
explicitly rejects values other than zero and one with
`ERROR_ECU_RESPONSE_VALUE_OUT_OF_RANGE`; malformed short data also produces an
error. There is no bit mask, multiplier or separate validity byte for this row.

The resulting narrow application contract is:

- Positive PDU `62 4A 69 00`: ECU-reported MIL condition Off.
- Positive PDU `62 4A 69 01`: ECU-reported MIL condition On.
- Negative reply, wrong DID/SID, missing data or any other value: unavailable,
  never coerced through Python truthiness or inferred from the DTC count.
- Require exactly four bytes for this single-DID request. This is a deliberate
  fail-closed shape policy; the generic source job also supports requesting
  several table-selected DIDs together, which this application does not do here.

Only the three exact address-index/name pairs above are enabled. MEVD1724 is a
different catalog row and is not covered by this inspection. The inspected
DME9FF_R table has no matching ISMIL row. DoIP address translation and other
engines require their own evidence; do not apply this byte-addressed mapping.

## Observation and verification limits

The value is the engine's MIL condition/command, not an independent test of the
physical bulb. Display On/Off with text plus color, retain observation age, and
invalidate after connection loss, mutation or staleness. A later accepted read
must not republish a current color after its connection has already failed.
After clearing faults, only a newly observed MIL result can describe the new
condition; successful clearing does not imply Off.

Local retention under
`/Users/lennon/BMW-Tool/investigations/task-b-dashboard-20261029/` includes the
three full STATUS_LESEN listings and their source table/comment extracts.
`independent-mil-contract-review.json` has SHA-256
`cbac5988e3427afded23a93a500be5af455ea02f1901da5983f38d09137ffc35`.
Actual owner-car validation remains pending: retain the exact observed F150
identity, raw request/reply and iDrive/cluster comparison without promoting one
vehicle result to universal support. REA and all source investigation tooling
remain development-only.

Independent one-off offline exercises of the implemented functions confirmed
both boolean values; rejection of negative/wrong-DID/truncated/extended/invalid-
value replies; zero sends for missing, duplicate or mismatched identity rows;
and one exact `22 4A 69` request for a matched synthetic row. An offscreen Qt
exercise confirmed the overview and Diagnostics mirror the same observation,
immediately remove color for an already-stale result, and clear both on reset.
These checks created no automated suite and involved no connection to a car.

## Broader exact-definition implementation

The [catalogue expansion](task-b-mil-breadth.md) now supersedes the original
three-definition coverage boundary:17 fully traced scalar engine definitions
cover53 exact F150 address-index rows, with9 other rows explicitly accounted for
as missing definitions or remaining decoder recovery. The original three
contracts remain unchanged. No universal DID or additional physical validation
is claimed.
