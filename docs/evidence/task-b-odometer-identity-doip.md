# Odometer, identity extras and DoIP addressing — 2026-10-30

Static source recovery only. No vehicle traffic, no APK/PRG execution, no app
change. Labels: **primary-reference** = traced in a supplied original artifact;
**hypothesis** = plausible but not traced to bytes; **unresolved** = searched and
bounded, not found. Nothing here is physically validated on any car.

Raw listings, disassembly, decrypted definitions and scripts:
`/Users/lennon/BMW-Tool/investigations/task-b-odometer-doip-20261030/`.
REA bundle there: `rea-evidence.json`, 40,488 bytes, 10 records, SHA-256
`653e53fe919e817fdcc00169b23fc1dab47a888b822c436c7c3b1a431a10d478`.
Machine-readable companion: [task-b-odometer-identity-doip.json](task-b-odometer-identity-doip.json).

PRG/GRP parsing used `BimmerDaten/decoderPrg.py` (format-aware table/job
disassembly). Byte offsets below are BEST job entry addresses from that parser.

## Variant selection (shared by every contract below)

`sources/Ecu/T_GRTB.PRG` (SHA-256 `c66b5eb7…cb7ee`, rev 1.720), table
`ZuordnungsTabelleUDS`, is what `G_KOMBI.grp`/`g_cas.grp` `IDENTIFIKATION`
consults (`tabsetex "ZuordnungsTabelleUDS","t_grtb"`, `tabseek "ADR_INDEX"`,
`tabget "SGBD"`). Its `ADR_INDEX` is `"<1-byte address> <first 3 bytes of 22 F150>"`,
the same key the app's diagnostic catalogue already uses. Every KOMBI/BDC row below
matches the diagnostics APK's `dat/ecu-variants.enc` row exactly (independent
corroboration). Select a contract only from an exact address-index match; never from
chassis, model range or year. Unmatched → unavailable.

| Address-index (F150) | SGBD | GRTB series column |
|---|---|---|
| `60 0F1160`, `60 0F2070`, `60 0F2080`, `60 0F25E0` | KOMB01 | F01, F01, I12, F30 |
| `60 0F1630`, `60 0F1634`, `60 0F1638`, `60 0F163C`, `60 0F1C30`, `60 0F2440`, `60 0F2450` | KOMB25 | F25, F20, F20, F80, I01, F56, F56 |
| `60 0F1636`, `60 0F163A` | KOMBRDCT | F20 |
| `60 0F2270`, `60 0F2280`, `60 0F2360`, `60 0F2390`, `60 0F24C0`, `60 0F2540` | KOMB_G11 | G11, G11, G11, RR11, G30, F90 |
| `60 0F2710`, `60 0F2800`, `60 0F28A0` | KOMBSP18 | G15, G20, F56 |
| `60 0F2B70`, `60 0F2B74`, `60 0F2B78`, `60 0F2B80`, `60 0F2B84`, `60 0F2B90`, `60 0F2B94` | KOMBSP21 | I20, I20, I20, U06, U06, RR21, U26 |
| `60 0F27B0`, `60 0F2820` | KOMB_J29 | J29 — PRG not supplied; out of BMW scope |
| `40 0F16B0` / `40 0F19C0` / `40 0F2050` | FEM_20 / BDC / BDC_G11 | F20 / F15 / G11 |
| `40 0F2680` | BDC_G05 | G05 |

The series column is reference text, not a selector.

## Owner F48/NBT branch (identities observed 2026-10-29; reads below not yet observed)

The coordinator relayed these identities from the owner's read-only session.
Each one maps exactly in both T_GRTB and the APK catalogue:

| Address | F150 index | SGBD | Odometer/measurement contract |
|---|---|---|---|
| `0x60` | `0F1630` | KOMB25 | **A1b**: `22 D1 0D` + `22 D1 14`; displayed = RAM u32 − offset u8 km. `D122` is **not** defined for KOMB25, so do not send it to this car |
| `0x40` | `0F19C0` | BDC | **A2**: `22 17 00`, labelled body-controller copy (fallback) |
| `0x10` | `0F1310`/`0F1318` | ZGW_01 | **None.** ZGW_01 has no odometer job or `SG_FUNKTIONEN` row, only the snapshot identifier `0x1700`. This agrees with the session's rejection of `22 F4 06` (`7F 22 31`) |
| `0x12` | `0F1D22` | DME_BX8 | A4 rows (PRG SHA `2c199a99…7c7`): `4300` u8 ×0.75−48 °C, `5822` u8 −60 °C oil, `4807` u16 ×0.25 rpm, `4AB1` u16 ×512/65536 km/h, `5817` u8 ×0.75−48 °C ambient. Supply voltage stays the existing `402B` contract |

No odometer DID was read in that session, so A1b and A2 remain source-only for the
F48. The earlier `60 / 1A 00` attempt was a KWP-style request and is irrelevant to
A1b. The breadth below still covers every supplied KOMBI/BDC/FEM variant.

## A1 — Cluster displayed total distance (preferred odometer)

**primary-reference.** ECU address `0x60` (instrument cluster). "GWSZ" =
Gesamtwegstreckenzähler (total distance counter).

### A1a — KOMBRDCT, KOMB_G11, KOMBSP18, KOMBSP21: `22 D1 22`

`SG_FUNKTIONEN` row (identical in all four PRGs):
`GWSZ_ANZEIGE_WERT, 0xD122, STAT_GWSZ_ANZEIGE_WERT, "Aufruf liefert den angezeigten
Gesamtwegstreckenzähler", km, L/H "-", unsigned long, MUL 1.0, DIV 1.0, ADD 0.0, SERVICE 22`.
These are read through the generic `STATUS_LESEN` job (entries `0x150AC` KOMB_G11,
`0x150AD` KOMBRDCT, `0x183FE` KOMBSP18, `0x18406` KOMBSP21). The four job bodies are
one template; after normalising labels they differ only in one repeated constant,
`2` vs `5`, which is not on the decode path below. Its `unsigned long` branch
reads 4 bytes **big-endian** from the data cursor unless the row's `L/H` begins with
`l`/`L`, then advances the cursor by 4. The cursor starts after the 2-byte DID echo,
the same as in the MIL contract.

- Request: `22 D1 22` to `0x60`.
- Positive response: `62 D1 22 b0 b1 b2 b3`, value = `b0<<24|b1<<16|b2<<8|b3` km
  (×1, +0). Require the exact `62 D1 22` echo and exactly 7 bytes. That length rule
  is our own fail-closed choice: STATUS_LESEN can also read several DIDs in one
  request, and this app sends only one.
- Sentinel: no explicit sentinel is given for D122. **hypothesis:** treat `FFFFFFFF`
  as invalid, by analogy with the documented absolute-counter sentinel in A1b.
- The unit is fixed as `km` in the PRG. Whether a miles-market cluster converts
  the value is not established. Always show km and never convert silently.

### A1b — KOMB01, KOMB25: `22 D1 0D` then `22 D1 14`

Dedicated job `STATUS_GWSZ_ANZEIGE` (KOMB01 `0xE984D`, KOMB25 `0xFD685`). Its
header comment says `0xD122`, but the code sends two different requests. This
traced code is the authority:

1. `S2 = 22 D1 0D` → xsend to `0x60`, tester `F1`. Response S4 (header removed):
   SID `62`, source and target checked. The job does **not** check the DID echo; our
   code still must.
2. `S3 = 22 D1 14` → response S5.
3. Result = `(S4[3]<<24 | S4[4]<<16 | S4[5]<<8 | S4[6]) − S5[3]` emitted with
   `ergl STAT_GWSZ_ANZEIGE_WERT` (signed long), and `STAT_GWSZ_ANZEIGE_EINH = "km"`.

Response layouts: `RES_0xD10D` defines two `long` values, `STAT_ABSOLUT_GWSZ_RAM_WERT`
and then `STAT_ABSOLUT_GWSZ_EEP_WERT`, both km. That makes D10D `62 D1 0D` + RAM(4,
big-endian) + EEPROM(4, big-endian) = 11 bytes. The job only uses the RAM word.
D114 is `62 D1 14 off` (unsigned char, km; KOMBRDCT names it "Anzeigeoffset des
GWSZ").

Sentinel (traced): `STEUERN_GWSZ_OFFSET` (KOMB25 `0xF4E50`, KOMB01 `0xFE09E`)
reads the same D10D word and compares it with `-1`. Its message is
"OFFSET beim ungültigen Kilometerstand nicht möglich", so a RAM value of
`FFFFFFFF` = invalid odometer → unavailable. If RAM < offset, the source's
signed subtraction would go negative; treat that as unavailable (our policy).
Require the exact D10D echo with ≥7 bytes. **unresolved:** whether every KOMB01/25
software always returns 11 bytes. Policy: accept 7 or 11, reject anything else.
Require D114 to be exactly 4 bytes.

The other KOMBIs also expose D10D/D114 (`RES_0xD10D_D`, unsigned long). D122 is
their direct displayed value, so A1a is preferred there.

**Never send** `STEUERN_GWSZ_OFFSET` / `_SETZEN` / `_SETZEN_1KM`. Those jobs build
a write request after the D10D read and change the cluster offset.

## A2 — Body controller redundant odometer: `22 17 00`

**primary-reference.** ECU `0x40`, SGBDs BDC, BDC_G11 and FEM_20. Job
`STATUS_KILOMETERSTAND` at BDC `0x168D40`, BDC_G11 `0x162A61` and FEM_20 `0x147EB9`;
the three bodies are identical after normalising labels. Comment: the mileage is stored in the
access controller "als redundante Datenablage zum Kombi" (as a redundant copy of
the cluster's value); range `0-16777214`; `FFFFFF` = invalid.

- Request `22 17 00` to `0x40`. The job checks `S3[0]==0x62` and that bytes 1..2
  equal the request DID, otherwise `ERROR`.
- Value = `S3[3]<<24|S3[4]<<16|S3[5]<<8|S3[6]` (`ergd`, unsigned long), unit `km`.
  Require exactly 7 bytes. Only `0..16777214` is valid; anything higher, including
  `00FFFFFF`, is unavailable.
- **unresolved:** the job reads 4 data bytes while the comment describes a 24-bit
  range. A 6-byte reply would fail in the source as well, so do not accept it.
- BDC_G05 (`40 0F2680`) has no such job. Its `SG_FUNKTIONEN` row
  `MILE_KM_EEPROM 0x2540` is `data[3]` raw `DATA`, with no numeric scaling →
  **unresolved**; do not decode it as km.

Display rule: A1 is the cluster's displayed odometer. A2 is labelled the body
controller's stored copy. Prefer A1; show A2 only as a labelled fallback, never
merged.

## A3 — What the diagnostics APK itself shows as "Mileage" (not an odometer)

**primary-reference**, REA/JADX 0.7.1 on the original APK (SHA-256 `da6f5b39…0d5`):
`j6.v.a0.b()` sends `19 04 <DTC 3 bytes> FF` (ReadDTCSnapshotRecordByDTCNumber,
all records). In `j6.v.a0.a.b(c6.d)`: if the response SID is `0x59`, the code
hex-encodes the response, runs regex `1700([A-F0-9]{6})17` over it, keeps the
largest 24-bit match and stores it via `j6.j.h(int)`. Adapter `u5.d` displays it
as `kilometrage` ("Mileage") in **fault details**. In this branch, which the F/G
interface (`j6.v`) uses, it is the mileage **at the time of that fault**.
The PRG `DTCSNAPSHOTIDENTIFIER` table, the same in KOMB25, BDC and BDC_G05, says
`0x1700 KM_STAND`, type `0xFFFFFF` (3-byte unsigned), and `0xFFFFFF` is invalid.

Do not copy the regex. Because it searches the hex string, it can match at odd
nibble offsets. A structured snapshot-record parser is what an implementation needs.
The APK has no other F/G odometer read: smali/REA searches for
`D10D`/`D122`/`1700`/`mileage` find only this branch and battery-registration
history fields.

## A4 — Engine-local mileage copies and core measurements

**primary-reference (table level).** Every core row below appears in two places
with the same DID, result name, data type, byte order and scaling: the decrypted
APK definition (`dat/<name>.enc` → `sensorValues`) and the PRG with the same name
(`SG_FUNKTIONEN`, SERVICE `22;2C`). There are **151 such rows across 23 engine
definitions**; the list is in the JSON companion and in `core-measurements.json`.
One conflict is excluded: D94BX7A0 `0x4256` coolant, where the APK's ADD is
−273.14 and the PRG's is 0.

Reading these follows the same STATUS_LESEN template as MIL: an `unsigned/signed
char` is 1 byte; an `int` is 2 bytes and a `long` 4 bytes, big-endian unless
`L/H` starts with `l`/`L` (it does in no selected row). Physical value =
raw × MUL / DIV + ADD. The template is the same one used for KOMBI: identical
type-compare and `l`/`L` branch counts in MEVD172, DME8FF_R and KOMB_G11. The
int and long branches were read for KOMB_G11. **Not separately traced:** where signed
types are sign-extended. Treat them as two's complement because the type name says so.

Representative exact rows (engine address `0x12`; request `22 <DID>`; response
`62 <DID> <data>`):

| Definition | Coolant | Oil temp | Battery V | RPM | Speed | Engine mileage copy |
|---|---|---|---|---|---|---|
| MEVD172/172Y/1725 | 4300 u8 ×0.75−48 °C | 5822 u8 −60 °C | 5815 u8 ×0.0942 V | 4807 u16 ×0.25 | 4AB1 u16 ×0.0078125 km/h | — |
| N55_ALP | same as MEVD172 | 5822 u8 −60 | 5815 u8 ×0.0942 | 4807 ×0.25 | 4AB1 ×0.0078125 | — |
| MSD87 | 4300 u8 ×0.75−48 | 5822 u8 −40 (engine oil); 4402 s16 ×0.1 | 5815 u8 ×0.256 | 4807 u16 ×1 | — | 480A u32 ×1 km; 5867 u8 ×2560 km |
| DME9FF_R | EF49 s16 /100 °C | *APK only* | *APK only* | EF5F s16 /2 ¹ | EF8C s16 ×1 | *APK only* |
| D73N57A0 | 461B u16 ×0.01−100 | 4B60 u16 ×0.01−100 | 4200 u16 ×0.389105 mV | 5955 u16 ×0.5 | 4C14 u16 ×0.004578 | 46B1 u32 ×1 km |

¹ The DID, type and scale match, but the ARG name differs: the PRG says `INMOT`,
the APK says `MOTORDREHZAHL`. The ARG-keyed cross-check therefore did not count it,
although the row is equivalent.
*APK only*: DME9FF_R `4C9A` oil temperature (u8 −40), `4F8F` battery voltage
(s16 /512) and `4F6F` lifetime mileage (u32 /10 km) exist in the APK definition.
The supplied DME9FF_R.prg (rev 0.202) has **no** `SG_FUNKTIONEN` row for them.
They are hypothesis-level and should not be enabled until a matching PRG or
response confirms them.

Limits: none of these rows defines a sentinel or validity flag. Show raw values with
their units and label the engine mileage as "engine-reported". These mileage values
come from the engine and are not the displayed odometer; some are only 8-km or
2560-km resolution counters. Only exact address-index matches qualify. The APK
reads these through its dynamic `2C`/`F303` path; the PRG read is a single
`22 <DID>`. Use only the plain `22` read (see the existing dashboard findings).

## A5 — Exact model / build date

- Model, type key, paint, upholstery, options and time criterion: already
  implemented from gateway `22 3F 06` (see [vehicle order](task-b-vehicle-order.md)).
- **unresolved:** no vehicle production-date DID was found in ZGW_01, ZGW_SP18,
  BDC, BDC_G11, FEM_20, KOMB25 or KOMB_G11 (scan terms produktionsdatum, baudatum,
  zeitkriterium, herstelldatum, typschl, fahrzeugauftrag). The matches found are
  ECU-level only and must not be shown as the car's build date: `HERSTELLINFO_LESEN`
  reads `F18B`, the ECU manufacturing date; KOMBI `0xDA46` is a sensor production
  date; and `STATUS_VCM_GET_FA` / `STATUS_VCM_BACKUP_FAHRZEUGAUFTRAG_LESEN` return
  the raw vehicle order already covered by 3F06. The time criterion stays a time
  criterion; it is not a decoded build date.

## B — Full-width DoIP logical addressing and U/I selection

**Bounded negative. No address conversion exists in any supplied artifact.**

| Artifact | Search | Result |
|---|---|---|
| S-02 coding APK (SHA `fc6eedeb…b728`), 6,498 classes | REA class search `DoIP`, `Doip`; smali grep `0x3458`, `doip`, `13400`; simulations `enet-sim.json`, `sim-enet.json`, `sim-g20.json`, `sim-g81.json` | No classes or constants. All simulation keys are HSFZ frames (`…0001 F4 <1-byte target>`) or `{1-byte addr}` |
| S-01 diagnostics APK (SHA `da6f5b39…0d5`), 4,123 classes, single dex, only PDF/PNG/font/`libexternal` native libraries | REA class search `DoIP`; smali grep as above; native-library strings | None. `assets/sim-u-series.json` uses 1-byte addresses (`{10}`, `{37}`, `{63}`) and is not referenced by any smali; only `sim.json` is loaded (`y5.a`) |
| `ediabasx/reference/XEnet32.dll.c` (decompiled ENET interface, SHA `2259e442…a6`) | `doip`, `0x3458`, `13400` | 0 hits. Ports are `DiagnosticPort` default `0x1A91` (6801) and `ControlPort` `0x1A9B` (6811): HSFZ only. The other reference DLL decompiles also have 0 hits |
| `ediabasx/packages/protocol-doip/src/index.ts` | — | Placeholder only (`export const placeholder`). `interface-enet/EnetInterface.ts` is a 71-line skeleton, and the `protocol: 'doip'` config enum has no implementation |
| 2,482 PRG/GRP in `sources/` (plain and XOR-0xF7 byte scan) | `DOIP`, `DoIP`, `LOGICAL_ADDR`, `LogicalAddress`, `13400` | Only W2V.prg `STAT_ROUTETYPE` = HSFZ/DOIP, the result of a route-*creation routine* keyed by a 1-byte "Diagnoseadresse (z.B. 0x63)" plus an IP address. That is a mutation, not a mapping. The `13400` hits are DTC numbers |

A further positive bound comes from the PRGs: every UDS SGBD frames requests
as `80 <1-byte target> F1 <len>`. This was checked in KOMB01, BDC, KOMBSP21
(I20/U06 cluster) and DME9FF_R (listed for U06). BCP_SP21.prg, the U06 gateway SGBD,
is **not supplied**. T_GRTB lists 73 I20, 18 U06, 12 G70 and
1 U26 rows, all with 1-byte addresses. So the job layer is address-byte only for U/I.
Any 16-bit DoIP logical address must come from an interface-layer conversion, which
none of these artifacts implements.

**Next source path:** a DoIP-capable EDIABAS interface or its configuration. That
means ISTA+/EDIABAS ≥7.3 `EDIABAS.INI`/`xenet`/ICOM DoIP sections, or a pinned
upstream EdiabasLib `EdInterfaceEnet.cs` DoIP branch (source guide 27, option 2),
retained with a revision hash. Expected observation: a statement of how the
1-byte SGBD address becomes the DoIP target logical address, plus the tester and
gateway logical addresses. Until then, DoIP inventory and reads stay disabled, as
they are today (`read_inventory` raises).

U/I category: T_GRTB is older (567 rows) than the APK catalogue (691 UDS rows) and
names U06/U26/I20/G70 variants. That gives exact ECU-variant identities for newer
cars **by F150**, independent of any model picker. It is not a model or category
contract. The coding APK's 45 groups still have no U or I20 group (unchanged finding).

## Unresolved summary and exact next paths

1. Miles-market KOMBI units for D122/D10D: PRGs fix `km`. Next path: a KOMBI
   unit-setting DID or the owner's cluster reading compared with the D122 raw value.
2. BDC 1700 24-bit range vs 4-byte read: owner F48 observation, logging the full
   PDU.
3. BDC_G05 and ZGW_SP18 `2540` `MILE_KM_EEPROM` raw `data[3]`: needs an ISTA+
   result decoder or a capture.
4. Vehicle production date: no supplied source. ISTA+ FA/VCM data is the candidate.
5. DoIP logical-address conversion: as above.
6. Sign-extension site in STATUS_LESEN for signed rows: trace the `ergl`/`ergi`
   emit branch if a signed row is enabled.
