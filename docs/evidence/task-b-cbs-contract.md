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
`ev_68c46195…a5ca703`; `j6.v.X` read order `ev_6d348ff4…bf853`. Blocked-branch pass
(2026-10-30, same APK): `j6.h.d` record-type selector `ev_e9f3113a…ad53daa`;
`j6.b.h` item filter `ev_3f433cc5…f73f3`; `j6.b.i` count filter `ev_135f7f5b…0f47a`;
`j6.g0.i.b` re-read `ev_9c6e94ec…f4a062a`; `j6.g0.k0` `ev_d4adc847…0b4720`. Raw
listings and offsets for the blocked branches: `blocked-branches-20261030.txt` in the
investigation directory.

## Branch classification (versions are per-PRG constants)

`CBS_INFO` never contacts the ECU. It returns a constant baked into the PRG
(KOMBRDCT `0x0E183B "CBS 6"`, `0x0E189D "0x06"`). The **version is therefore a
property of the identified variant**, decided by this chain: `22 F1 50` → address +
three-byte index → `ZuordnungsTabelleUDS` / app catalogue → PRG → version below.
No CBS-version DID exists to read.

| Class | PRGs | Disposition |
|---|---|---|
| E-series KWP (`83/89/8F FF F1` framing; CBS ≤4; 8-byte records) | 122 files (listed in JSON `excluded_kwp_e_series`) | Excluded |
| **CBS 5, UDS** (12-byte records, default 2E reset) | KOMB01, **KOMB25** (0x60); MEVD172/1724/1725/172Y, **DME_BX8**, D70BX7A0, D72N47A0, D73N57A0/E0, D75BX7A0, EDMEI1, MSD85L6, MSD85YL6, MSD87, MSD87_R0, MSV90, N55_ALP, N63TU_R0, S55, S63TU_R0 (0x12); S63TU_L0 (0x13); DSC_01, DSC_10, DSC_25 (0x29); LMV_01 (0x19); CMEDIA (0x36); EHC_01 (0x38) | Read and reset implementable; DSC_25 reset is the conditional sequence in "DSC_25 reset" below |
| **CBS 6, UDS** | KOMBRDCT, KOMBSP18, KOMB_G11 (0x60); D83BX7C0, DME8FF_R (0x12); DME8FF_L (0x13); GSGE01QW (0x18); DSC_G11/G20/G30N, **DSC_I1**, IB_G05, IB_G2X (0x29) | Read, reset and 22 10 02 detail read implementable |
| **CBS 6.3** (“fuer CBS-Version 6.3”) | D94BX7A0 (0x12, U06 DDE 9.45); KOMBSP21 (0x60, I20/U06/RR21/U26) | Read implementable (changed field meanings); D94 resets by routine `31 01 10 00` (contract below); KOMBSP21 reset stays blocked (no request in any supplied artifact) |
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
| 3 hi | status flags 0x10 substitute values, 0x20 Baukasten client, 0x40 data manipulated, 0xF0 invalid | `&0xF0` → `TAB_CBS_STATUS` (`0x0E4166`) | `(b>>4)&0x0F` → `CBS_STATUS_FLAG_DOP` (D94 `0x23E747`): bit0 substitute values, bit1 Baukasten client, bit2 data manipulated (0–7 = combinations, 0 "Status ok"); 8–F "Signal ungültig" |
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
BimmerLink lists only 1,2,3,4,6,0x0A,0x11,0x64 with count ≤30 (`j6.b.h`, `j6.b.i`
on `rec[4] & 0x1F`). That is a presentation filter, not a protocol limit: it hides
exactly the PRG's "nicht erlaubt" value 0x1F.

**Service count range (resolves "count wrap").** v5/v6 decode count as
`rec[4] & 0x1F` with only three cases: 0 "bisher kein Service", 0x1F "nicht erlaubt",
otherwise the count (KOMBRDCT `0x0E4335`–`0x0E44E3`). The reset argument accepts
0–30 explicitly or 31 = "+1" (`CBS_ANZAHL_SERVICE`, range check `< 0x20`, DSC_25
`0x0E7365`). No supplied PRG or BimmerLink path defines what the ECU does on "+1" at
count 30 (no wrap, saturate or reject logic exists on the tester side); bits 5–7 of
byte 4 are never decoded. 6.3 uses the full byte (≥0xFA invalid) and D94's routine
reports GG 0x09 "Servicezähler ist nicht zwischen 1 und 250". Contract: when the
before-count is 30 (v5/v6) or ≥250 (6.3), observed verification must not expect
before+1; it uses availability 100 and reports the after-count as observed.

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
- BimmerLink: `j6.g0.i.b`. It has one other form, `2E 10 01 01 II 64 1F FF FF`, used
  only when `j6.h.d` returns the 8-byte record type, which it does for a fixed list of
  E-series SGBD names (EDMEM12, DSC_85, KOMB60, KOMBRR, D50M57*, …). Every F/G/U/I
  SGBD, including DSC_25, D94BX7A0 and KOMBSP21, gets the 15-byte form above. BimmerLink
  has no item-, DSC- or 6.3-specific reset branch.
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

**6.3 D94BX7A0 (separate branch, primary implementation reference: `D94BX7A0.prg`
`CBS_RESET` `0x219880`–`0x21C18E`).** Job comment: "CBS Reset start (STR, 0x01), read
out (RRR, 0x03); UDS $31 Routine Control, $1000". No `10 xx` or `27 xx` is sent; the
job runs in whatever session is active (default for this app).

| Arg | Mapping in the job | Default |
|---|---|---|
| `SUBFUNC` | "STR"/0x01 → template `31 01 10 00 FF FF FF FF FF` (`0x219DAD`); "RRR"/0x03 → `31 03 10 00` (`0x219E1E`) | RRR (`S0[3]=3`, `0x2198A2`) |
| `CBS_ID` | `CBS_6_3_KENNUNG` name or number → byte 4 (`0x21A29C`/`0x21A3AA`) | none: missing → `ERROR_ARGUMENT` |
| `CBS_RESETART` | `TAB_RESET_ART` `ART` name or number → byte 5 (`0x21A7D2`/`0x21A8EC`) | none: missing → `ERROR_ARGUMENT` |
| `CBS_WERT` | unsigned long, > 0xFFFFFF rejected; big-endian into bytes 6–8 (`0x21AB0A`–`0x21ABE1`) | absent → `FF FF FF` (template) |

`TAB_RESET_ART` (D94): 0x01 plant "Werksreset", **0x02 standard "Standardreset"**,
0x03 service_counter, 0x04 time, 0x05 distance, 0x06 forecast_distance,
0x07 availability (all "Korrekturreset …"), 0x0A rda "Anlieferzustand herstellen",
0xFF not defined. The job has **no default reset type**; the caller must pass it.
The user service reset is therefore TT = 0x02: it is the only type the table labels
as a normal reset, every other type is a correction, plant or delivery operation.
This is *source-labelled* (table text), not a caller trace: no supplied artifact calls
the job (BimmerLink sends the 15-byte `2E` record to D94 instead; that is not in the
D94 PRG and is not used here). VV is the job's "input data" with default `FF FF FF`;
for TT 0x02 the app sends the default.

Response handling (identical for STR and RRR, `0x21B125`–`0x21C166`): positive SID
0x71 and address match (send macro); then length must be exactly 8 (`< 8`
`ERROR_ECU_RESPONSE_TOO_LESS_DATA`, `> 8` `…TOO_MUCH_DATA`), bytes 2–3 must be `10 00`
(`…INCORRECT_DATA_IDENTIFIER`), GG = byte 4 → `TAB_CBS_RETURN_CODE_ALLGEMEIN`,
KK = byte 5 → `TAB_CBS_RETURN_CODE_KOMPONENTE`, bytes 6–7 = `STAT_RESERVE_DATA`.
The job returns OKAY **whatever GG/KK say**; it never chains STR → RRR.

| GG | Text (source) | KK | Text |
|---|---|---|---|
| 0x00 | Okay, keine Verhinderungsgründe | 0x00 | Okay, keine Verhinderungsgründe |
| 0x01 | ungültiger km-Stand | 0xFE | keine Angabe |
| 0x02 | ungültiges Borddatum | 0xFF | ungültig |
| 0x03 | ungültige Codierung | | |
| 0x04 | SG nicht initialisiert oder im falschen Zustand | | |
| 0x05 | Fahrzeug im fahrenden Zustand | | |
| 0x06 | Reset bei CBR nicht erlaubt | | |
| 0x07 | Reset bei aktivem Ersatzwert nicht erlaubt | | |
| 0x09 | Servicezähler ist nicht zwischen 1 und 250 | | |
| 0x0A | Zieltermin ausserhalb des gültigen Wertebereichs | | |
| 0x0B | Restweg ist ausserhalb des gültigen Wertebereichs | | |
| 0xFE | keine Angabe | | |
| 0xFF | Wert ungültig | | |

Implementable contract (D94, owner 0x12, item from its own `22 10 01`):
1. Send `31 01 10 00 II 02 FF FF FF` once.
2. Require `71 01 10 00 GG KK RR RR`, length 8. GG = 0x00 and KK = 0x00 →
   *response-confirmed acceptance*. Any other GG/KK → *rejected*, show the table text
   (an unknown value is shown raw). A `7F 31 xx` NRC → rejected (0x78 per transport).
3. `31 03 10 00` is optional: it only re-reads the same GG/KK layout
   (`71 03 10 00 GG KK RR RR`). No source requires it after a start. Use it only to
   resolve an uncertain start (timeout) before any retry, never as an automatic replay.
4. Observed verification = re-read `22 10 01` at 0x12 using the 6.3 layout.
`STEUERN_CBS_DATEN_SICHERN` (`31 01 F0 ED`, "CBS-Reset relevante Größen sichern") is
not called by `CBS_RESET` and is not linked to it by any source; it is not sent.

**DSC_25 reset (primary implementation reference: `DSC_25.prg` `CBS_RESET`
`0x0E6F79`–`0x0EBD71`, job comment "fuer CBS-Version 5, $2E, Modus Default").** The
encoder is the generic v5 one. After argument parsing it branches; every request goes
to 0x29 and uses the standard send macro (positive iff `resp[0] == SID+0x40` and the
addresses match; `7F xx 21` → wait 1, bounded resend; any other failure → JobResult
text and `eoj`, i.e. later steps are not sent). No `10 xx` or `27 xx` anywhere.

```
C0  0x0E831D  S2[6] (service byte) == 0x01                     -> PLAIN
S1  0x0E8390  22 F1 01        (needs 62; else job ends, nothing written)
C1  0x0E8892  v = resp[0x29..0x2B]  (resp[0] = 0x62)
              v not in {34 05 01, 01 08 04, 01 0B 03}            -> PLAIN
S2  0x0E8D76  22 10 01        (needs 62; else job ends, nothing written)
C2  0x0E9278  item 0x02: rem = int16(resp[4..5])   (record 0, ID not checked)
              item 0x06: rem = int16(resp[16..17]) (record 1, ID not checked)
              other item: rem never assigned (S0[0x0C] uninitialised)
              rem > 0                                            -> PLAIN
EXT 0x0E9658  2E 10 01 01 II 64 1F 80 00 0F FF 0F 3F FF 00   (needs 6E)
    0x0E9A1C  86 00 02        ROE stop, eventWindowTime 02   (needs C6)
    0x0E9F2E  31 01 03 04 00  routine 0x0304, param 00       (needs 71)
    0x0EA442  14 FF FF FF     clear all DTCs                 (needs 54)
    0x0EA956  wait 2
    0x0EAAF3  2E 10 01 … (same 15 bytes again)               (needs 6E)
    0x0EAEB7  86 05 02        ROE start, eventWindowTime 02  (needs C6)
    -> OKAY (flag S0[0x0E]=1 suppresses PLAIN)
PLAIN 0x0EB3B9 2E 10 01 01 II 64 1F 80 00 0F FF 0F 3F FF 00  (needs 6E) -> OKAY
```

- **C1 meaning.** By `DSC_25.prg` `SVK_LESEN` (`0x012994`–`0x012C00`) the SVK header is
  7 + 13 bytes when `resp[0x0A]` bit 7 is set, and entries are 8 bytes (class, SGBM-ID,
  3-byte version). Offsets 0x29–0x2B are then the version (main.sub.patch) of SVK entry
  index 2: 52.5.1, 1.8.4 or 1.11.3. `CBS_RESET` compares the raw bytes only and checks
  neither header, class nor length; the app does the same raw compare.
- **`86 00 02` / `86 05 02`** are byte-identical to `STEUERN_ROE_STOP` (`0x0D7862`) and
  `STEUERN_ROE_START` (`0x0D9A8A`): "Temporäres Deaktivieren/Aktivieren der aktiven
  Fehlermeldung, gültig für LH Diagnosemaster V9 oder früher (pre 35up)".
- **`31 01 03 04 00`** is not named in DSC_25. The same RID is
  `STEUERN_TRIGGER_DUMMY_DTC_FUNKTIONAL` in ZFS_01 ("RID Trigger_Dummy_DTC, Param
  Dummy_DTC_Type 00/01", `0x058001`) and `DEBUG_DMCLIENT_TRIGGERDTCENTRY` in AMPT07/RSE_01
  ("0304 Debug DMClient, 1: NW DTC, 0: Application"). Param 00 = application dummy DTC.
- **`14 FF FF FF`** clears every DSC DTC. *Hypothesis* for the purpose: these three DSC
  software versions do not accept a brake-pad reset while the worn-pad state
  (`rem ≤ 0`, e.g. DTC 0x480A11/0x480A12 "Bremsbelagsensor … Verschleissgrenze
  erreicht") is latched, so the job silences ROE, provokes and clears the fault
  memory, waits 2, rewrites, and restores ROE. The bytes and order are not hypothetical.
- **Default path validity.** The single `2E` (PLAIN) is the source's own path whenever
  the service byte is 0x01, the SVK triple is any other value, or the item's remaining
  value is positive (`0x7FFF` "no info" included). `0x8000` ("invalid") is negative as
  int16 and takes EXT.

Implementable contract (app always sends service byte 0x1F, so C0 never selects PLAIN):
1. Only items 0x02/0x06. Before step S1, require the fresh `22 10 01` record 0 ID = 0x02
   (for item 2) or record 1 ID = 0x06 (for item 6); otherwise block (the PRG assumes this
   layout without checking it; other items are undefined in the source).
2. S1: require `62 F1 01` and length ≥ 0x2C, else block (a shorter response is
   undefined in the source). Compare bytes 0x29–0x2B.
3. PLAIN outcome: identical to the v5/v6 default reset and completion.
4. EXT outcome: needs an explicit confirmation that names its side effects (all DSC
   fault memory is cleared; an application dummy DTC is triggered; event reporting is
   stopped then restarted). Send the six requests in order, each once, requiring the
   listed positive SID. The first failure stops the sequence and is reported as
   *partial*, naming the last positive step. After an ROE stop without a restart, the
   instruction is an ignition cycle ("temporär" in the source); the app does not
   replay any step automatically (D-28). Completion = both `6E` and the final `C6`,
   then the normal 5 s re-read for observed verification.

**KOMBSP21 (6.3 cluster 0x60): stays blocked.** Exact reason: no supplied artifact
defines a reset request for it. The PRG has 65 jobs; only `CBS_DATEN_LESEN`
(`0x0E1C5B`) and `STATUS_CBS_HISTORIENSPEICHER_LESEN` (`0x0E578C`) are CBS jobs. The
XOR-decoded file contains no `2E 10 01` and no `31 01|03 10 00`; `SG_FUNKTIONEN` has
no RID 0x1000 or DID 0x1001 (its CBS rows are 0xD10A `CBS_KM_PRO_JAHR` and 0xD120
`CBS_SERVICE_AKTIVIERUNG`). `TAB_RESET_ART` (which here adds 0x08 "Anzeige-Reset")
is used only by the history job, and `TAB_CBS_RETURN_CODE_ALLGEMEIN/KOMPONENTE` are
present but referenced by no job. Those tables hint that the cluster shares D94's
routine, but a hint is not a request. Across all 2478 supplied PRG/GRP files,
`31 01 10 00` occurs only in D94BX7A0. BimmerLink would send the 15-byte `2E` to it
(type-o default), which the KOMBSP21 PRG does not define. Next source: a newer
KOMBSP21 SGBD or an ISTA test module that calls routine 0x1000 on 0x60.

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

- **Resolved 2026-10-30 (static):** DSC_25 reset (full conditional sequence above),
  D94 reset type/arguments/response tables and the optional role of `31 03`, D94 read
  status flags, service-count range, and BimmerLink's lack of DSC/6.3 branches. The
  EXT branch of DSC_25 clears all DSC DTCs; how that side effect is worded in the
  confirmation is a product item, not a protocol gap. The 2 in `wait 2` is taken as
  seconds (the same instruction is used with 1 in the NRC 0x21 retry loop).
- **KOMBSP21 reset:** blocked, reason above. DME9FF_R has no CBS read or reset job.
  Next: a newer cluster/DME9 PRG or ISTA data. Do not infer from D94's routine or
  from KOMBSP21's orphan return-code tables.
- **Item duplicated across ECUs.**
- **Physical (D94/DSC_25):** neither ECU is on the owner's F48; GG/KK behaviour,
  the count after "+1" at 30, and the EXT sequence are unobserved.
- **Exact v5 availability bound** (address-conditioned compare in MEVD172 `CBS_DATEN_LESEN` near 0x0712xx).
- **Physical:** no CBS bytes were read on the owner's KOMB25/DME_BX8/DSC_I1. The first validation is a read-only `22 10 01` at the three addresses.
- **Unreachable decoders** (11 PRGs) stay unrouted. `CBS_INTERNE_DATEN_LESEN` (`22 10 03`) and `CBS_RESET_KOR` are not needed.

Feature-matrix rows to add: **B-CBS-R** = v5/v6/6.3 read, owner-by-response;
**B-CBS-W** = v5/v6 default 2E reset with D-29 completion. Recovered and implementable
but not yet enabled in `app/cbs.py`: D94 routine (TT 0x02, GG/KK completion) and the
DSC_25 conditional sequence. KOMBSP21 and DME9 stay blocked.
