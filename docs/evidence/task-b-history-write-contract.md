# History execution contracts — PR16 continuation, 2026-10-29

**Primary implementation references; static source recovery.** This extends the
[ADD investigation](task-b-history-deep-investigation.md) with exact ERASE,
headunit selection, session/default-mode, reset and pacing observations. It
implements no reader and makes no vehicle observation. D-50–D-55/workflow28
supersede historical baseline/readback requirements in older source reports.

## Scope and retained provenance

REA/Ghidra12.1.4 read the supplied native writer's mapped bytes. Existing
format-aware BEST parser `BimmerDaten/decoderPrg.py` freshly decoded all ten exact
headunit PRGs' ADD, ERASE, initialization, session and reset jobs. The parser is
development tooling only; runtime uses standalone recovered contracts. Native
objdump instruction decoding independently locates call arguments and pacing.
No source executable, PRG bytecode, Java frontend or car request was executed.

Retained under
`/Users/lennon/BMW-Tool/investigations/task-b-history-write-20261029/`:

- `prg-contracts.json`: exact inputs/jobs/comments/result tables/listing hashes
  and matching diagnostic catalogue rows; SHA-256
  `5d4557c00b222692aaf2b4b6c39365f0f99ce4f86f53d5c38e29f9b5eab3cfb7`.
- Complete selected BEST listings, `recover-source.py` and native write-region
  objdump. The report retains each listing hash; source files remain unchanged.
- `rea-evidence.json`: four complete mapped-byte observations,15,844bytes;
  SHA-256 `36bbf9ad312d9d6a370f2583373a1f64f240743d8caeb3f7f65d9ee5c2cc1c74`.
  REA exported before closing the ephemeral native analysis session.

All supported source branches target HSFZ UDS address`63`. Exact F150 catalogue
identity and PRG names must match; a chassis hint, headunit label chosen by a
user, similar name or generic address alone never enables writes. Full-width
DoIP translation remains an independent recovery task; do not apply byte63 as
an inferred DoIP logical target.

| F150 address index | Definition | PRG path | Full SHA-256 |
|---|---|---|---|
|63 0F12D0|CIC|sources/CIC.prg|d77e5bf8dd036d58354fa560dff1403610a1e194a21d2b650066b4baaa853650|
|63 0F1580|CHAMP2|sources/Ecu/CHAMP2.prg|30ae075209a42cda7c42f28426de1e27a7b140dfc1ccb32e9f1fafc4c334dac9|
|63 0F1820|ENTRY|sources/Ecu/ENTRY.prg|800fb0b8c9c54938aaf38ad48cc772afcd816a57e702da0ca1c4389d6a5aeb66|
|63 0F1A30|NBT|sources/NBT.prg|e94e3b4434c9f8563448ee0b89153ed62856cce3d72db61b18373b184f896415|
|63 0F1BE0|ENTRYNAV|sources/Ecu/ENTRYNAV.prg|8adf15810a89fcc46a0814b61e40d33d02bc9ddbc2a3641819557f0d208bae67|
|63 0F1CD0|RAD_UKL|sources/Ecu/RAD_UKL.prg|9b92f1a3890d58d0140ac0663a66feec294c947db9c1edbbc2adff782ad7b960|
|63 0F2230|NBTEVO|sources/NBTEVO.prg|e269380deede7bd2da54717af3eeb270b355f2d4cc6ead978a9d9897c136e4ff|
|63 0F2330|ENAVEVO|sources/Ecu/ENAVEVO.prg|8a24eeb907f49b4436c390b8784d546dba70011c510ee12b8f91734ea63483c5|
|63 0F25B0|HU_MGU|sources/HU_MGU.prg|74daa7f74246ab5bb4078816d2b7e79915b4744a5fb351f1f9fde72d760bba10|
|63 0F2700|BIS01|sources/Ecu/BIS01.prg|b6b77e19b6c462bfdfc24578b5e730552b7e4bd37b3b5f5bbe79f4f82a21c4ab|

All ten exact current catalogue rows are accounted for, rather than just the
owner's NBT. This is source applicability, not every ECU software authorization
or physical validation. Fresh F150 and complete F101 software identity should be
retained/compared before execution. No negative rejection authorizes guessed
sessions, security access, retry, ERASE fallback or another ECU variant.

## Complete request sequence and decoding

| Mode/step | Request PDU | Required final application response |
|---|---|---|
|Explicit default-session normalization|10 01|50 01 followed by the valid session timing body supported by the shared UDS service|
|Replacement only: erase once|31 01 A0 80|71 01 A0 80 result|
|Append one entry / replacement each reviewed entry|31 01 A0 81 plus recovered nineteen-byte header and eight-byte items|71 01 A0 81 result|
|After all accepted records: hard headunit reset|11 01|51 01|

The ADD record codec and fourteen service IDs are documented in workflow28 and
implemented in app/service_history.py. All ten jobs declare61arguments (nine
header arguments plus four fields for thirteen items), construct the same ADD
routine and extract the one-byte application result from PDU offset4. All ten
ERASE jobs independently construct the ERASE routine and extract offset4 too.

Accept only exact5byte ADD/ERASE responses with the requested routine/subfunction
and result00. The PRGs extract status at offset4 but do not establish that an
extended response shape is valid; extra/truncated bytes fail closed. Standard
shared UDS negative-response/pending handling remains bounded and correlated.
No copying the external Python frontend's permissive missing-status/01 success.

All ten exact tables agree:00EverythingOK;01OutofMemory;02Datainconsistency;
04Nowritingpermission;05Unknownerror. HU_MGU/BIS01/ENAVEVO additionally expose
FFInvalid in their TAB_SERVICEHISTORY table. Unknown status never means accepted.
The source JOB_STATUS may say OKAY after obtaining a valid UDS response while
its business status rejects the operation: the worker must check both layers.

Representative exact job entry offsets (all remaining offsets/listings retained):

|Definition|ADD|ERASE|Hard reset|
|---|---|---|---|
|CIC|0x17F613|0x183788|0xFD8CE|
|NBT|0x13763B|0x13B7B0|0xDCB90|
|NBTEVO|0x174F44|0x174789|0x1048F6|
|HU_MGU|0xD6129|0xD5943|0xA560D|
|BIS01|0xC7DB5|0xC75F2|0xA4B9F|
|CHAMP2|0x151637|0x1557AC|0x10150C|
|ENAVEVO|0x117C83|0x1174C0|0xE1B69|
|ENTRY|0xE09A8|0xE01ED|0xD690C|
|ENTRYNAV|0x111BBE|0x111403|0xE1BA0|
|RAD_UKL|0xABA92|0xAFC07|0x9EDF0|

## Session, reset and source timing

ADD/ERASE job bodies contain no preceding10session or27security requests. Their
comments impose no separate named diagnostic mode. INITIALISIERUNG initializes
transport parameters, not a UDS session. Every reviewed DIAGNOSE_MODE begins with
1001 and exposes DEFAULT as its default argument; DIAGMODE maps DEFAULT→01,
ECUEXTDIAG→03 and ECUSWT→42. Explicit1001 is a supported default normalization,
not a claim that an extended/coding/security session is required for history.
Do not invent an authorization sequence after04NoWritingPermission.

Every STEUERGERAETE_RESET job explicitly documents UDS11EcuReset/01HardReset,
modeDefault, and sends1101. Exact5101 validation is stricter than the generic
PRG sender's positive-SID check and follows the standard hard-reset response;
never treat disconnect as an accepted reset. A checked response precedes actual
visible reboot, so report response-confirmed and ask for manual iDrive inspection.
There is no source-supported universal ignition off/on duration. Do not promise
that an arbitrary manual cycle substitutes for a missing/failed reset response.

Native writer SHA-256
`2d6bb52808f1754ac9334958530c5b2c60ec373fa35b674f28bdb34dc93cf92a`:
`0x60EC67` calls exchange0x60D9D4 for ERASE then waits200ms; `0x60ED7D` calls
ADD for each stored record then waits100ms; `0x60EDBB` sends final1101. Its record
iteration uses existing list order. Pacing is source-frontend behavior, not proof
of an ECU minimum or capacity. Preserve these delays within the overall budget.

REA evidence IDs: write control bytes
`ev_0017e6e61852ebe0f55e8b2ad0cc1664960453ec6a9079e04e0dc27165885ca7`;
target63/ERASE literal at0x60EF98/0x60EFA8
`ev_ab45f7a0102cd7e8a14a12d581461521fd5e955349a4785d5f0f50e72933264e`;
ADD literal at0x60F010
`ev_6189964ef186d03a4a638bfcf49017c3b7f4083ef3c9a7c53e77d57cec78ffd5`;
reset literal at0x60F08C
`ev_9d306e4518a7745a09c07b6cb8261d01336cf8e9da48c6e1a661b6b2cc9553d7`.

## Capacity, preservation and operational limits

The ten PRGs supply an out-of-memory result, not an exact maximum archive count
or eviction/order algorithm. No capacity probe, destructive discovery, full-list
scan or invented limit is justified. ADD-only means this app never sends ERASE;
it cannot guarantee behavior of unseen existing records or duplicate dates.
Capacity rejection stops the operation without replacement. Explicit replacement
irreversibly removes the unknown prior list; persist null prior-car state and all
reviewed local intent/results. Do not turn source unknowns into promised backups.

No applicable vehicle-voltage or host-battery threshold was present in these
reviewed history jobs. Unknown power therefore requires the D-31 acknowledgement;
a future reliable insufficient-power observation must block writes. Do not invent
an ECU threshold or borrow an unrelated coding requirement to enable history.

Use one owner-exclusive whole sequence, no write Cancel, at most30seconds per
request and a five-minute absolute overall budget including queueing/delays/
reset. Publish/flush immutable intent before any mutation; publish each sending
and final-response event before subsequent mutation. Persistence failure after a
step stops later steps, preserving any in-memory result. Never retry/replay or
resume automatically. Stop on any rejected/malformed/uncertain step; retain all
remaining work as unattempted. Checked reset failure after accepted ADDs is
partial/uncertain activation, not "nothing written" or success. Reidentify on any
new action after an interruption; local journals never become history readback.

Remaining source branches are any newer/absent headunit identity outside the ten
rows and actual DoIP logical addressing; they need exact matching artifacts.
Physical capacity/insertion/visibility observations remain separate and can only
be recorded on available hardware. Their absence does not block implementation
of the source-backed request/result contracts above.
