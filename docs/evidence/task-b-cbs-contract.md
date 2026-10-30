# Task B — CBS read and reset contract (B-CBS-R / B-CBS-W)

Static source recovery, 2026-10-30. **No vehicle traffic, no app code, no target
execution.** Labels follow the spec-driven skill: *primary implementation
reference* (supplied PRG bytecode, shipped APK, pinned upstream source),
*historical report* (upstream comments about its own car), *observed locally*
(only the F150 identities from the owner's 2026-10-29 session), *hypothesis*,
*unresolved*. Machine-readable twin: [task-b-cbs-contract.json](task-b-cbs-contract.json)
(per-PRG SHA-256, job addresses, catalogue rows, REA evidence IDs). Raw dumps,
scripts and the REA bundle are kept outside the repo in
`/Users/lennon/BMW-Tool/investigations/task-b-cbs-20261030/`.

## Sources and identities

| Source | Identity | Used for |
|---|---|---|
| 186 PRGs in `sources/Ecu/` with a CBS-named job, decoded with `BimmerDaten/decoderPrg.py` (XOR-0xF7 BEST/2 disassembly, file offsets retained) | per-file SHA-256 in JSON | Wire contract, layouts, sentinels, versions |
| `sources/Ecu/T_GRTB.PRG` table `ZUORDNUNGSTABELLEUDS` + `G_KOMBI.grp` `IDENTIFIKATION` (`22 F1 50` → `tabsetex ZuordnungsTabelleUDS`) | SHA-256 in JSON | Variant → PRG selection |
| `coding_data/diagnostic_catalog.json.gz` (app catalogue from the APK's `ecu-variants.enc`) | SHA-256 in JSON | Agrees with T_GRTB on 113/114 CBS-PRG rows; only diff is `12 0F2E00` (DME9FF_R vs DME98_R), which has no CBS job anyway |
| `sources/BimmerLink_v2.36.1.apk` `da6f5b39…cae00d5`; REA/JADX 0.7.1 | 6 evidence records, bundle `rea-evidence.json` (16 records) | Owner selection, reset bytes, completion behaviour |
| devttys1/bmw-service-manager @ `6c0041bb…5469c048173`; `cbs.py` blob `f69332631214…` and `hsfz.py` blob `755550f260d1…` (verified with `git hash-object`), plus `web.py`, `simulator.py`, `tests/test_headunit.py` | PolyForm Noncommercial: facts are recorded here, no code was copied | Cross-check and conflicts |

REA records: `j6.g0.i.b` reset builder `ev_6611523c…86d18db`; `j6.g0.i.a.b`
completion `ev_e27c40a4…7c07e38`; `j6.g0.h.a.b` read send `ev_5efc6d57…a8b70`;
`j6.b.j` record split `ev_0813415b…ceb5764`; `j6.b.<init>` field decode
`ev_68c46195…a5ca703`; `j6.v.X` read order `ev_6d348ff4…bf853`.

## Branch classification (versions are per-PRG constants)

`CBS_INFO` never contacts the ECU. It returns a constant baked into the PRG
(KOMBRDCT `0x0E183B "CBS 6"`, `0x0E189D "0x06"`). The **version is therefore a
property of the identified variant**, decided by this chain: `22 F1 50` → address +
three-byte index → `ZuordnungsTabelleUDS` / app catalogue → PRG → version below.
No CBS-version DID exists to read.

| Class | PRGs | Disposition |
|---|---|---|
| E-series KWP (`83/89/8F FF F1` framing; CBS ≤4; 8-byte records) | 122 files (listed in JSON `excluded_kwp_e_series`) | Excluded |
| **CBS 5, UDS** (12-byte records, default 2E reset) | KOMB01, **KOMB25** (0x60); MEVD172/1724/1725/172Y, **DME_BX8**, D70BX7A0, D72N47A0, D73N57A0/E0, D75BX7A0, EDMEI1, MSD85L6, MSD85YL6, MSD87, MSD87_R0, MSV90, N55_ALP, N63TU_R0, S55, S63TU_R0 (0x12); S63TU_L0 (0x13); DSC_01, DSC_10, DSC_25 (0x29); LMV_01 (0x19); CMEDIA (0x36); EHC_01 (0x38) | Read and reset implementable, except DSC_25 reset (see unresolved) |
| **CBS 6, UDS** | KOMBRDCT, KOMBSP18, KOMB_G11 (0x60); D83BX7C0, DME8FF_R (0x12); DME8FF_L (0x13); GSGE01QW (0x18); DSC_G11/G20/G30N, **DSC_I1**, IB_G05, IB_G2X (0x29) | Read, reset and 22 10 02 detail read implementable |
| **CBS 6.3** (“fuer CBS-Version 6.3”) | D94BX7A0 (0x12, U06 DDE 9.45); KOMBSP21 (0x60, I20/U06/RR21/U26) | Read implementable (changed field meanings); D94 resets by routine; KOMBSP21 has no reset job |
| No CBS job | DME9FF_R (U06/G09 DME9: only history read), N63TU_L0, BDC/BDC_G05/BDC_G11, FEM_20, ZGW | Not a CBS owner |
| Decoder present but unreachable | AEP2, D72VDA0A, D73V8RCA, dme_bx80/81/82, dsc_20, dxc_25, mevd172_alt, mevd172y_alt, MSD85L6_EA | No UDS address-index row selects them. Do not route to them. |

Within each class, the semantic token traces of `CBS_DATEN_LESEN` and `CBS_RESET`
are identical except for the target address and ECU-name strings. Example
diffs: KOMB25 and DME_BX8 against MEVD172 show 0 differing tokens; DSC_I1 against
D83BX7C0 shows 0. The other v6 resets differ from KOMBRDCT only by an
`'rda'`-item guard. Exceptions: DSC_25 (163 extra reset tokens) and MSD85L6_EA.

## Owner's F48 branches (F150 identities observed locally 2026-10-29; no CBS DID read yet)

| Addr | Variant (index) | PRG | CBS | Read | Reset |
|---|---|---|---|---|---|
| 0x60 | 0F1630 | KOMB25 | 5 | `22 10 01` | default `2E 10 01` template |
| 0x12 | 0F1D22 | DME_BX8 | 5 | `22 10 01` | default template |
| 0x29 | (index from session) | DSC_I1 | 6 | `22 10 01`; `22 10 02` detail | default template |
| 0x40 | 0F19C0 | BDC | — | none; its 0x41xx DIDs are FUSI/terminal data, never CBS | none |
| 0x10 / 0x63 | ZGW_01 / ENTRYNAV | — | — | none (headunit history is separate) | none |

**Item ownership on this car is decided at runtime.** An item belongs to the ECU
whose own `22 10 01` response contains it (rule below). *Hypothesis*, until a read
on this car: oil/NOx → DME_BX8, brake pads → DSC_I1, and brake fluid, vehicle
check, statutory checks, pre-delivery and running-in → KOMB25. Sources for this
hypothesis: the generic `CBS_RESET` ARGCOMMENT "Kombi-Umfaenge: Brfl, Sic, Sic_v,
TUV, AU, Ueb, Efk / externe Umfaenge: Oel, NOx_a, Br_v, Br_h", the upstream
`RESET_ECU`, and BimmerLink. If spark plugs (0x0A) or another item appears, it goes
to whichever ECU returned it. Upstream's KOMBI fallback would misroute it.

## Owner selection rule (no default owner)

BimmerLink `j6.v.X` → `v$b0` → `v$b0$a` reads `22 10 01` from 0x12, then 0x29,
then 0x60. It tags each record with its source address (`j6.b.a`), and `j6.g0.i.b`
sends the reset to that same address (`c6.g(b.b(), …)`). The PRGs widen the
source-supported set to every identified ECU whose PRG has a v5/v6/6.3
`CBS_DATEN_LESEN`, which adds 0x13, 0x18, 0x19, 0x36 and 0x38. Contract:

1. Identify ECUs with the existing F150 catalogue. Read `22 10 01` only at
   addresses whose exact variant maps to a CBS PRG above.
2. Owner(item) = the responding ECU. Never fall back to 0x60. An item absent from
   every response is not resettable.
3. The same item ID in more than one ECU response is *unresolved* (no source rule
   picks a winner). Show both raw records and block reset of that item.

## Read contract (`22 10 01`, default session, no security)

PRG `CBS_DATEN_LESEN` comment: "UDS: $22 ReadDataByIdentifier, Modus: Default".
Request `22 10 01`; positive `62 10 01` + *N*×12-byte records, *N* = (len−3)/12
(KOMBRDCT `0x0E22E3`). v6 rejects a non-multiple as `ERROR_ECU_RESPONSE_TOO_LESS_DATA`
(`0x0E2443`); v6 D83/DSC and 6.3 also check the `10 01` echo. The app should
require the SID+DID echo and an exact multiple in every version, and keep the raw
bytes. BimmerLink parses the same 12-byte stride (`j6.b.j`, type `o`).

| Rec byte | v5 (MEVD172 group) | v6 (KOMBRDCT offsets) | 6.3 (D94/KOMBSP21) |
|---|---|---|---|
| 0 | item ID | same | same |
| 1–2 | remaining, signed BE16 (BEST `int`; BimmerLink two's-complement) | same; `0x8000` invalid/not relevant (`0x0E3DAE`), `0x7FFF` no info (`0x0E3E2B`) | value×10 km; same sentinels |
| 3 lo | unit: 0 %, 1 distance ×10 km, 2 days, else not allowed | same (`TAB_CBS_EINHEITEN`, 0x0F invalid) | 1 distance, 0xF invalid |
| 3 hi | status flags 0x10 substitute values, 0x20 Baukasten client, 0x40 data manipulated, 0xF0 invalid | `&0xF0` → `TAB_CBS_STATUS` (`0x0E4166`) | `CBS_STATUS_FLAG_DOP` |
| 4 | service count `&0x1F`; 0x1F not allowed | same; 0 = no service yet (`0x0E42FC`) | full byte; ≥0xFA not allowed |
| 5 | availability %; 0xFE not initialised; >100 flagged (address-dependent bound) | 0xFD no info, 0xFE new ECU, 0xFF invalid (`0x0E454F`) | ≤0x97 %, 0xFE new ECU, else invalid |
| 6 | forecast distance ×1000 km | same; 0xFF invalid; 0 with CBS bit = not relevant | ×1000 km; 0xFF invalid |
| 7 | `&0x0F` due month (1–12; 0x0F d.c.) | month `&0x0F` (`TAB_CBS_MONAT`: 0 not relevant, 0x0E new ECU, 0x0F unavailable); bit4 = show (`0x0E4E42`); bit5 = CBS, clear = CBR (`0x0E49DA`) | month; bits4–5 CHOV table (0..3) |
| 8 | `&0x3F` years after 2000 | same; 0 not relevant, 0x3F invalid (`0x0E4F89`) | **full byte** +2000; 0 not relevant, ≥0xFA invalid |
| 9 | forecast months | same; 0 not relevant, 0xFF invalid (`0x0E51DE`) | same |
| 10 | not decoded | not decoded | `&0x3F` target day (0 n/r, 0x1F invalid) |
| 11 | reserve | reserve (`0x0E5456`) | reserve |

Item labels come from the **variant's own** `CbsKennung` / `CbsNrText` /
`CBS_6_3_KENNUNG` table; IDs diverge (MSD85L6_EA). English names are in the JSON
`items` list. The German text is the source; the translations are ours,
cross-checked with BimmerLink strings for 1/2/3/4/6/0x0A/0x11/0x20/0x64. CBS IDs
are **not** the headunit history codes. History 5 is recirculating air filter
while CBS 0x05 is Service Inclusive; 0x14/0x15/0x20/0x21/0x64 happen to coincide.
0xE0/0xE1 (eval boards) and 0xFF (delivery state) are not user services.
BimmerLink lists only 1,2,3,4,6,0x0A,0x11,0x64 with count ≤30. That is a
presentation filter, not a protocol limit.

Optional for v6 owners: `22 10 02` returns 3-byte records (item, reason, reserve).
Reasons: 0 none, 1 invalid odometer, 2 invalid date, 3 invalid coding,
4 not initialised, 5 vehicle moving, 6 CBR item, 7 substitute value active,
8 "Wohnen" state, 0x80–0xBF sensor-specific, 0xFE none given (KOMBRDCT
`0x0E7394`, `TAB_RUECK_GRUND`).

## Reset contract

**v5 and v6 (all three sources agree byte-for-byte):** default session, no
security access, no routine, sent to the owner address:

```
2E 10 01 | 01 | II | 64 | 1F | 80 00 | 0F | FF | 0F | 3F | FF | 00
 SID DID  cnt item avail svc  remain  unit fkm  mon  yr  fmon res
```

Sources for these bytes:
- PRG: KOMBRDCT `0x0E556B`, MEVD172 `0x07398F` template, identical in all 53 UDS v5/v6 PRGs per JSON. Item is written at offset 4 (`0x0E56CC`…).
- BimmerLink: `j6.g0.i.b`.
- Upstream: `reset_payload`.

Written fields: item, availability 100, service count 31 = "+1". Every other
field is a no-change sentinel: remaining `0x8000`, unit `0x0F`, forecast km
`0xFF`, month `0x0F`, year `0x3F`, forecast months `0xFF`, reserve `00`. Encoder
side effects:
- v6 sets unit=1 and forecast=0 only when availability <100 (`0x0E58AC`).
- v6 ORs 0x10 into byte 11 only when `CHOV_CBS_CBR_VIEW`=1 (`0x0E65EE`).
- v6 D83/DSC/KOMBSP18 reject item 0xFF `'rda'`.

The app sends only the default record. The comments for KOMBRDCT, and only that
PRG, require the vehicle to be in "Pruefen_Analyse_Diagnose / Fahrbereitschaft
herstellen / Fahren / Fahrbereitschaft beenden", meaning ignition/diagnosis
active, not "Wohnen".

**6.3 D94BX7A0 (separate branch):**
- Start: `31 01 10 00 ID TT VV VV VV` (`0x219DAD`; TT from `TAB_RESET_ART`: 0x02 standard, 0x03–0x07 corrections, 0x01 plant, 0x0A delivery; VV default `FF FF FF`).
- Positive response: 8 bytes `71 01 10 00 GG KK RR RR`, routine echo `10 00` checked, GG = general return code (0x00 OK; 0x01–0x0B reasons incl. 0x09 counter not 1–250), KK = component code (0x00 OK).
- `31 03 10 00` re-reads the codes.
- A standard reset would use TT = 0x02. That is our reading of "Standardreset", a *hypothesis* that needs review before it is enabled.

## Completion, negative responses, re-read

- **PRG `CBS_RESET`:** OKAY when `S3[0] == SID+0x40` and the source/target addresses match (`0x0E6EBD`). It checks neither the DID echo nor any payload. NRC 0x21 is resent in a bounded loop (`0x0E6E4F`). Other NRCs map to `JobResult` text, and 0x78 is handled by the EDIABAS interface, not the job.
- **BimmerLink `j6.g0.i.a.b`:** a first byte other than 0x6E (including 7F) means failure, with the message "try again… check error memory". On 0x6E it waits **5000 ms**, reports success, then re-reads every CBS item (`ServiceActivity.Z`).
- **Upstream:** `reset_cbs` succeeds on any response starting with `6E`, without a DID echo check. `hsfz.request` raises on any `7F` without checking the echoed SID, and on 0x78 it renews a 30 s receive timeout for each frame. `web.py` re-reads immediately, with no delay.
- **Contract (D-29):**
  1. Freeze the owner, variant, version and item, and the raw before-record from a fresh `22 10 01`.
  2. Send once and require exactly `6E 10 01` (stricter than all three sources); that establishes *response-confirmed acceptance*.
  3. Treat 0x78 with the existing owner, inside the 30 s deadline.
  4. Any other NRC means *rejected*. NRC 0x21 means *not applied*, but under D-28 the app does not auto-replay. Timeout or disconnect means *uncertain*: re-identify and re-read before a new confirmed action.
  5. After 5 s (BimmerLink), re-read `22 10 01` at the same owner. *Observed verification* = the item record shows availability 100 and count = before+1.
  6. If unchanged, report "accepted, not observed" and, for v6, read `22 10 02`. No source documents an ignition cycle requirement.

## Conflicts with the upstream Python (do not port blindly)

1. **Read path.** Upstream reads cluster DIDs 0x4101–0x417F (20-byte records), but no supplied PRG defines a CBS 0x41xx DID: the KOMB* files contain only an unrelated `0x4100`, and the BDC 0x41xx DIDs are FUSI. BimmerLink also never reads them. PRGs and BimmerLink read `22 10 01` per owning ECU. Treat 0x41xx as a *historical report*, outside the contract.
2. **Default owner 0x60** for unlisted items contradicts source ownership. Remove it.
3. **DME record comment.** Upstream puts "status" at byte 10 and the show flag in the "high nibble of unit byte, 0 = show". The PRGs put status in byte 3's high nibble, leave byte 10 undecoded (6.3: target day), and use byte 7 bit 4 for show = 1. The default bytes still agree, because the flag is clear (0x0F).
4. **Completion:** upstream checks only the SID, does no DID echo check, has no delay, and has no NRC-SID correlation (see above).
5. **Upstream's F48 lead** (D83BX7C0, CBS 6) is not the owner's car, which has DME_BX8, CBS 5. `NO_DISTANCE`=32000 belongs to the 0x41xx format; the PRG sentinels are 0x7FFF/0x8000.
6. **Minor:** BimmerLink masks year with `&0x1F`; the PRG uses `&0x3F` (v5/v6) or the full byte (6.3). Follow the PRG per version.

## Unresolved (exact next source path)

- **DSC_25 reset** (F20/F25/F10 M5/F80 brake pads): when the services argument is not 1 (`0x0E831D`), the job reads `22 F1 01`, compares SVK bytes 0x29–0x2B, and may run `22 10 01`, `86 00 02`, `31 01 03 04 00`, `14 FF FF FF`. Block the reset; next, disassemble `DSC_25.prg` `CBS_RESET` `0x0E8390`–`0x0EB3B9` fully. Its read is plain v5.
- **KOMBSP21 reset** has no job, and DME9FF_R has no CBS read or reset job. Next: a newer cluster/DME9 PRG or ISTA data. Do not infer from D94's routine.
- **D94 6.3 reset type and post-routine semantics:** confirm TT 0x02 and whether `31 03` is required (`D94BX7A0.prg` `CBS_RESET` `0x219B29` onward).
- **Item duplicated across ECUs.**
- **Count wrap** when count = 30.
- **Exact v5 availability bound** (address-conditioned compare in MEVD172 `CBS_DATEN_LESEN` near 0x0712xx).
- **Physical:** no CBS bytes were read on the owner's KOMB25/DME_BX8/DSC_I1. The first validation is a read-only `22 10 01` at the three addresses.
- **Unreachable decoders** (11 PRGs) stay unrouted. `CBS_INTERNE_DATEN_LESEN` (`22 10 03`) and `CBS_RESET_KOR` are not needed.

Feature-matrix rows to add: **B-CBS-R** = v5/v6/6.3 read, owner-by-response;
**B-CBS-W** = v5/v6 default 2E reset with D-29 completion. D94 routine, DSC_25,
KOMBSP21 and DME9 stay blocked with the disposition above.
