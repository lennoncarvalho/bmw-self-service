# Dashboard reads and MIL lead — 2026-10-29

Observed local source inspection; no vehicle traffic, app behavior change or
physical validation. Owner request: a richer first page after connection,
especially a green/red emissions-MIL indicator. D-25 already requires a real
MIL read separate from fault count. D-56 records the dashboard emphasis.

## What is already recovered

The current implementation branch contains HSFZ source-derived inventory and
exact ECU-variant identities (`22 3F07`, `22 F150`), three integration levels
(`22 100B`) and a specific DME supply-voltage decoder (`22 402B`). Their source
methods/hashes are in [the recovered contracts](task-b-recovered-contracts.md).
These reads are not newly validated on the owner's car; the retained physical
session established VIN but rejected earlier optional guesses. Do not infer
that the current installed/running app already displays every new branch value.

Dashboard candidates, separated by current evidence:

| Information | Evidence/readiness |
|---|---|
| VIN, chosen adapter/transport and identified gateway | Existing connection data; distinguish verified identity from chassis hint |
| ECU count, names, variants and identification coverage | Recovered inventory/catalogue path; display unidentified/unreachable rows and do not call all detected ECUs connected |
| Software integration levels: factory/current/backup | Recovered three-entry gateway response; label order only after matching source decoder semantics |
| Supply voltage in volts | Recovered source decoder; this is neither battery state-of-charge nor a universal safe-to-write threshold |
| MIL on/off | New concrete PRG lead below; exact engine/software mapping and response extraction/owner validation still pending |
| Mileage, coolant/oil temperature, RPM, vehicle speed | Real encrypted sensor definitions with IDs/types/scales; need exact variant, read path, response framing/sentinels and applicability before enabling |
| Model/chassis/engine/gearbox/build date/paint/options | Valuable identity/configuration targets; FA/identification decoder remains open, never derive them from a series hint or unreliable VIN-year assumption |
| CBS remaining distance/due date | Additional-source read lead, explicitly later CBS scope; different from the retired service-history reader |

## New MIL source lead

The earlier bounded APK sensor search did not find a genuine MIL endpoint. A
new scan of 2,478 local PRG/GRP files, followed by format-aware table/job inspection,
finds this concrete **engine MIL-on condition**, not a DTC status-bit substitute:

| Original PRG | Selector/table | DID/result and meaning |
|---|---|---|
| MEVD172.prg | SG_FUNKTIONEN, ARG=ISMIL | ID4A69, STAT_MIL_EIN_WERT, unsigned char, unit0/1, labelB_mil, MIL-Ansteuerung, allowed services22;2C |
| MEVD172Y.prg | Same | Same4A69 result/type/units |
| MEVD1725.prg | Same | Same4A69, description Bedingung MIL Lampe Ein (condition MIL lamp on) |

MEVD172 SHA-256:
`c0ba4f472218f79cd18954eb6b6763aa8782b9f0b259afa1d23bfc8613468c97`.
All three complete source hashes and decoded table rows are retained locally.
STATUS_LESEN at BEST offsets150F4/15149/150FD respectively starts with22,
resolves ID from SG_FUNKTIONEN, writes the DID high/low bytes into the request,
and sends through xsend. For MEVD172 the shared sender is at16C77. This supports
investigating a single direct `22 4A 69` request on an **exactly matched** variant.
It does not establish a universal DME DID, complete minimal response length,
bit/sentinel handling, or compatibility with the owner's unidentified engine ECU.

The data is the ECU-reported MIL condition/command, not independent physical-bulb
verification. Retain full decoder/response evidence and compare against the actual
check-engine display before declaring it physically validated. Do not invoke
STEUERN_MIL or any lamp-actuation routines as a read. New engine definitions must
not inherit4A69 by a model/year/name-prefix assumption. DME9FF_R's inspected table
has no matching ISMIL/STAT_MIL_EIN_WERT row; it must remain unavailable until its
own mapping is recovered. Likewise, later MEVD variants can differ in DID.

The keyword scan also finds mileage strings containing MILG and lamp coding or
actuation entries; those are false positives/different operations. The scan's
468 matching files are candidates, not468 supported MIL readers.

## Other real sensor definitions

The hashed original diagnostics APK is
`da6f5b39efaa590fce68782f439c1b8f1b9f09ed41344055b8ff80666cae00d5`.
Using the already recovered development-only AES/GZIP decoder on selected original
assets yields, for example:

| Exact definition | Sensor | ID/type/scaling from metadata |
|---|---|---|
| mevd172 | Coolant temperature | 4300, unsigned8, raw×0.75−48°C |
| mevd172 | Engine speed | 4807, unsigned16, raw×0.25rpm |
| mevd172 | Vehicle speed | 4AB1, unsigned16, raw×0.0078125km/h |
| dme9ff_r | Engine oil temperature measured | 4C9A, unsigned8, raw−40°C |
| dme9ff_r | Vehicle mileage over lifetime | 4F6F, unsigned32, raw/10km; not automatically equivalent to displayed cluster odometer |
| dme9ff_r | Battery voltage | 4F8F, signed16, raw/512V |
| dme9ff_r | Coolant temperature | EF49, signed16, raw/100°C |
| dme9ff_r | Engine speed | EF5F, signed16, raw/2rpm |

These are concrete metadata, not a finished request/decoder contract. Preserve
native units and sensor validity; oil-level measurement states/48V or HV battery
values are not interchangeable with a12V battery health summary. Avoid exposing
engineering counters as if they were ordinary dashboard measurements.

REA/JADX inspected a concrete sensor streaming continuation:
`k6.c0$b$a.b(c6.d)` accepts6C after dynamic definition then requests22F303 from
engine12 (Evidence`ev_c8551d11b0e8e886892b6118fc115d8cd30133df321d4b3d6e0f4172f3c4d5bc`).
That demonstrates an existing dynamic sensor mechanism, not a proven generic
single-DID response layout. Do not introduce2C dynamic definition writes for
simple dashboard reads without separate need/evidence. A second retained method,
`j6.v.i`, was found to clear faults, not read sensors; it provides **no dashboard
read authority** and must not be called to populate the page.

## Dashboard behavior to implement

- Show an overview with identity, mileage when valid, software levels, supply
  voltage, ECU identification coverage and a prominent labelled MIL indicator.
  Put detailed configuration/ECU data in inline expansion; source-supported live
  temperatures/RPM can live in an expanded measurements area rather than dumping
  thousands of engineering signals into the initial connection batch.
- MIL green=`ECU reports Off`, red=`ECU reports On`, grey=`unavailable/not yet
  read/stale` with text/icon as well as color. Where verified powertrain identity
  establishes no applicable emissions MIL, show Not applicable, never green Off.
- Prioritize identification/MIL/core summary in the bounded initial batch. Respect
  D-23: publish the initial page result together after settlement, not field by
  field. Optional failures leave verified connection active and show unavailable.
- Read MIL on the overview, not only when visiting Diagnostics. After Clear All,
  reread its actual endpoint; clearing/zero DTCs never sets it Off by inference.
  Retain a timestamp and turn a lost/stale observation grey; no last-car value
  survives VIN change/reconnect. A manual refresh uses one bounded background
  worker and cannot compete with a write/clear or reset operation.
- Green MIL is not an overall “car healthy” badge. DTC scan coverage and fault
  count are separate. No unverified field defaults to zero, no fake model/build
  date and no permanent auto-scanning of unsupported measurements.

## Retained evidence and work

Full local evidence: `/Users/lennon/BMW-Tool/investigations/task-b-dashboard-20261029/`.
The companion [manifest](task-b-dashboard-read-manifest.json) hashes search scripts,
source/member records, original PRG metadata and STATUS_LESEN disassembly,
selected sensor metadata and the exported REA bundle. Proprietary bodies stay
local; REA and generators stay development-only.

Next tasks: exact engine matching, complete MIL response/validity/prerequisite
contract, remaining identity/odometer definitions, primary-batch budgeting and
readiness accounting; then implement/review offline checks and owner observation.
This investigation does not enable new reads or claim a working MIL on the F48.
''')
PY