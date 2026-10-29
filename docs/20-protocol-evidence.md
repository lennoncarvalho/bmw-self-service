# Protocol evidence and correction register

Reviewed 2026-10-28. This register takes precedence over contradictory historical
research/examples. It specifies evidence boundaries, not universal BMW mappings.

## Evidence standard

A wire contract needs artifact/version/full SHA-256 plus class/method/offset or
capture location, exact request and response bytes, ECU/software identity and
known limits. Distinguish observed local facts, primary implementation references,
historical reports, hypotheses and owner decisions. The original abbreviated
hashes and `ev_...` IDs do not substitute for retained evidence.

Primary implementation references below are corroboration, not independent
certification of this app or access to all normative ISO editions.

## HSFZ

The primary implementation supports a six-byte base header with a body selected
by control word. Diagnostic/ACK addressing is not the structure of every control
frame. See [Scapy HSFZ](https://github.com/secdev/scapy/blob/master/scapy/contrib/automotive/bmw/hsfz.py)
and [the local transport contract](10-hsfz-protocol.md).

PR #8's retained excerpt supports the diagnosis that ACKs and late diagnostic
responses were misassociated in an earlier version. It does not establish a
universal two-second heartbeat, guaranteed ordering of all application traffic,
or successful validation of the proposed fix. The original local log is empty.

## DoIP

The header is **1-byte version, 1-byte inverse version, 2-byte payload type,
4-byte payload length**, totaling eight bytes. The old reference's two-byte
version fields are wrong. Routing activation precedes diagnostic exchange and
establishes tester routing, not a per-ECU UDS session.

The default RoutingActivationRequest payload is 7 bytes: source(2), activation
type(1), reserved(4); the variant with manufacturer-specific data is 11 bytes.
Padding a three-byte prefix to four-byte alignment does not produce this
message. Check response status and identity. See the
[python-doipclient message implementation](https://github.com/jacobschaer/python-doipclient/blob/main/doipclient/messages.py).

ACK `0x8002` confirms transport acceptance, NACK `0x8003` rejects it, and a
diagnostic response uses `0x8001`. Alive-check request/response are `0x0007` /
`0x0008`; dispatch them during the connection lifecycle. Do not assume exactly
one ACK followed by exactly one response. The DoIP entity initiates alive checks;
the tester responds with its two-byte logical source address. An idle poll is not
proof of liveness, and a skipped lock acquisition is not a failed exchange. See
[DoIP message documentation](https://python-doipclient.readthedocs.io/en/latest/messages.html).

## UDS

A negative response is `7F <original SID> <NRC>`. Thus `7F 10 21` refers to
DiagnosticSessionControl and busyRepeatRequest, not TesterPresent.
`0x78` means response pending; validate the echoed SID and continue within
bounded P2/P2*/overall timing. Do not start a new request while the old response
can still be mistaken for it. Session response timing is distinct from a fixed
socket timeout. See
[udsoncan response codes](https://github.com/pylessard/python-udsoncan/blob/master/udsoncan/ResponseCode.py)
and [client timing behavior](https://udsoncan.readthedocs.io/en/latest/udsoncan/client.html).

Validate positive SID, DID/subfunction/routine echoes and complete body before
calling an operation successful. `0x2C` is DynamicallyDefineDataIdentifier;
`0x3D` is WriteMemoryByAddress, not RoutineControl. `0x1A` is not a standard UDS
mileage operation; legacy manufacturer/KWP identification behavior needs its
own evidence. See [service definitions](https://udsoncan.readthedocs.io/en/latest/udsoncan/services.html).

## DTCs and emissions

DTC records for `59 02` begin after its availability mask at offset 3.
`19 03` identifies snapshots, not a universal timestamp/km codec. Bit 7 of a
DTC status byte is a requested warning indicator, not an independently verified
emissions MIL reading. `0x08` selects confirmed faults. See
[the decoder reference](https://github.com/pylessard/python-udsoncan/blob/master/udsoncan/services/ReadDTCInformation.py)
and [the corrected database/diagnostics guide](14-dtc-database.md).

`0xFFFFFF` means all DTC groups on the addressed ECU. The former hardcoded
powertrain/chassis/body group map and generic single-code clear are unverified.
A failed/unsupported scan must not appear as zero faults. Preserve per-ECU
identity. A transport success is not evidence that clearing changed the MIL.

## BMW-specific data remains unresolved

| Claim | Why it cannot currently drive production code |
|-------|-----------------------------------------------|
| F=HSFZ and all G/U/I=DoIP | A naming heuristic cannot replace discovery/variant evidence |
| VIN position 10 always gives model year | VIN interpretations vary by market; verify decoded identity |
| F18A is I-level | Requires BMW-specific source; generic identification naming is insufficient |
| F100/FC00 returns FA XML | Neither universal DID mapping nor XML wire format is established |
| F000 returns an SVT with fixed 11-byte records | Exact gateway response/decoder evidence is missing |
| F406 is mileage / F40C is voltage | Endpoint, length and scaling need primary evidence |
| CAFD describes bytes stored in the ECU | CAFD definition metadata and live coded values are separate data |
| First available CAFD variant is usable | Match exact vehicle software version; never choose by directory order |
| A data-group address proves a writable DID | Trace read/write logic and byte/block boundaries |
| Every preset is one value byte | Presets may span functions, bytes, masks and data groups |
| 117/139 ECUs need no SecurityAccess | Static flags/counts cannot certify actual authorization or writeability |
| Job prefixes establish service-history SIDs | Trace the job's request encoding; see doc 12 |

These are research questions, not newly chosen replacement constants. Record
unknown data as unavailable, preserve raw responses, and keep uncertain encoders
out of real-car write paths. No security-key guessing or bypass is required to
establish a read-only connection baseline.

## IP configuration

Do not use `169.254/16` as a DHCP pool; link-local assignment and DHCP are
separate mechanisms. See [RFC 3927 section 1.6](https://datatracker.ietf.org/doc/html/rfc3927#section-1.6).
A network fallback needs scoped interface selection, conflict detection and
owned cleanup; it must not kill unrelated host services. See doc 15.

## Next evidence collection

The [first retained session](23-first-vehicle-session.md) now establishes the
F48 setup's HSFZ/VIN baseline. It also records negative responses to the fixed
FA/mileage/voltage/topology requests, an invalid I-level decode and gateway-only
DTC coverage. Follow [the staged REA plan](../tasks/rea-protocol-recovery.md)
for source-derived replacements. The earlier collection recommendation below
describes the pre-session starting point.

Start with F48/NBT read-only identity and complete HSFZ frame dispatch. Preserve
fresh logs before rotation and record adapter/route/runtime. Next trace the
reference app's F/G/U/I connection selection and exact vehicle identity reads;
only then specify data availability and feature support by variant.

The earlier missing-engine observation is superseded: owner setup/restart now
provides REA MCP 6.8.0 and successful JADX package/class/method-smali inspection.
Ghidra 12.1.4 is reported available, not yet exercised on a native target here.
See [source guide and retained Evidence](27-rea-source-guide.md). Tool readiness
does not establish any missing BMW operation contract above.

## Post-PR13 selection findings — 2026-10-29

[Exact source chain](evidence/task-b-topology-selection.md): supplied F/G coding
interfaces share HSFZ ENET; the source does not choose DoIP from a chassis letter.
Failed/empty3F07 inventory uses148distinct UDS catalogue addresses for F150
identification. Candidates are not installed topology; failed/unknown/unattempted
identities remain explicit. Continue only on a healthy owned stream within the
whole inventory budget. No DoIP byte-to-logical-address conversion is inferred.

[MIL breadth](evidence/task-b-mil-breadth.md) supersedes the original three-engine
selection with53exact F150/name rows across17definitions, using source-selected
4A69/50D8/42BC scalar readers. Every other catalogued engine has a concrete source
or decoder disposition. Raw values beyond0/1 remain unavailable, not truthy On.
These static source contracts add no physical vehicle or lamp observation.
