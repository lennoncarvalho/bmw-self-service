# ISTA 4.29 install: architecture evidence for an ISTA-data re-architecture

Status: **static, read-only analysis**, 2026-10-30. No ISTA binary was executed, no
vehicle traffic was sent. Target: `sources/ISTA_4.29.1x/Rheingold` (owner-supplied).
Raw dumps and scripts: `~/BMW-Tool/investigations/ista-20261030/`
(SHA-256 of key files in `sha256_key_files.txt`).

Labels: **[observed]** read directly from the artifact; **[derived]** computed from
observed data; **[inferred]** reasoning not yet backed by a byte-level trace.

Owner scope update (2026-10-30): the app targets ISTA 4.29 coverage only; the owner
will supply `DiagDocDb.sqlite` and an EDIABAS trace from the F48. DiagDocDb content
is therefore not reconstructed here; §1 lists what to look for once it arrives.

## 0. Identity of the install

| Item | Value | Evidence |
|---|---|---|
| App | ISTA 4.29.15.23407 (DB 4.29.14, BLP 4.29.11) | `readme_standalone.txt`; SQLite connector assembly version 4.29.15.23407 [observed] |
| EDIABAS | 7.3.0 (`api32.dll`, `ebas32.dll`, `XEnet32.dll`) | PE `FileVersion` [observed] |
| PSdZ | 5.11.03 (Java, ProDiaS) | `PSdZ/bin/RELEASENOTES.TXT` [observed] |
| SQLite text DBs | `RG_VERSION_* = 4.29.14 / ENGB / 2021-04-13` | [observed] |
| Distribution | unofficial "ISTA Standalone" repack | `License.xml` is a fabricated licence ("THIS IS FREE SOFTWARE", expiry 2050); readmes describe disabling "Reject fake FSC's" [observed] |

## 1. Vehicle identification and the text databases

**Flow and classes [observed symbol names; bodies not decompiled].**
`RheingoldDiagnostics.dll` holds the identification chain: `DoVehicleIdentification`,
`G_ZGW_SGBD` / `G_ZGW_AUSLESEN` (gateway SGBD resolution), `doECUReadFA` (vehicle
order), `doECUIdent`, `doEcuReadSvk`, `GetVehicleIdentByTypeKey`,
`LoadBordnetsData` / `GetBordnetXmlFromDatabase`, `CreateEcuTree`,
`DoEcuTreeNaming`. `RheingoldProgramming.dll` builds SVT/SVK (`BuildSvt`,
`RequestSvtFromVcm`, `GetStandardSvtActual`, `FindEcuInPsdzSvt`,
`GetEcuGroupByDiagnosticAddress`). The .NET `#US` string heaps of the Rheingold
assemblies are **encrypted** (obfuscator); 49,276 literals in
`RheingoldDiagnostics.dll` decode to ciphertext. Job names/SQL cannot be read
statically without a deobfuscation step. Testmodule DLLs are *not* obfuscated (§3).

**DiagDocDb is the logic store; it is absent.** `RheingoldCoreFramework.dll` maps
`XEP_*` entities from DiagDocDb; e.g. `XEP_ECUVARIANTS` has `NAME`, `TITLEID`,
`TITLE_DEDE … TITLE_ENGB …` (per-language columns), `ECUGROUPID`,
`FAULTMEMORYDELETEWAITINGTIME`, `SICHERHEITSRELEVANT`, `VALIDFROM/TO` [observed,
REA `inspect_managed_members`, sha256 `cc307114…b520`]. 52 `XEP_*` table names are
referenced by `RheingoldDatabaseSQLiteConnector.dll` (`sqliteconnector_xep_strings.txt`).
The connector also exposes `IsDatabaseEncrypted` / `DatabasePassword` settings
[observed] — check whether the supplied DiagDocDb opens without a key.

What to look for when DiagDocDb arrives: `XEP_ECUVARIANTS` (variant→group, ECU
titles), `XEP_ECUGROUPS` (group/diag address), `XEP_FAULTCODE(S)` +
`XEP_FAULTLABELS` + `XEP_REF_DIAGCODE_ECU` (DTC→variant→title/TITLEID),
`XEP_CHARACTERISTICS`/`XEP_CHARACTERISTICROOTS`/`XEP_TYPEKEY_MAPPING` (type key/VIN
→ series/model), `XEP_ECUJOBS(EX)`/`XEP_ECURESULTS(EX)`, `XEP_INFOOBJECTS`/
`XEP_SWIACTION` (links to ABL test modules), bordnet XML for the ECU tree.

**Present text DBs [observed].**

| DB | Tables | Rows | Content / key |
|---|---|---|---|
| `SQLiteDBs/xmlvalueprimitive_ENGB.sqlite` (40.9 GB) | `xmlvalueprimitive(id, modified, deleted, data, compressed_data)`, FTS4 `fts`, `DELTA_INFO`(0) | 266,753 (max rowid = max FTS docid) | Long XML documents keyed only by numeric `id` (e.g. `200000634155104`). 1-in-400 sample: `FKB` fault-detail docs (~45 %), repair-manual docs, SVG graphics, `DIAGNOSISDOCUMENT`, `spe:TEXTCOLLECTION` (test-plan texts), technical data. `data` is plain UTF-8 XML; `compressed_data` NULL in sample. |
| `SQLiteDBs/streamdataprimitive_ENGB.sqlite` (224 KB) | `streamdataprimitive(id, modified, deleted, stream)` | **0** | empty in this language pack |
| `IDESModule/IdesModule.sqlite` (478 MB) | `IdesModule`, `IdesBstModule` | not counted | IDES runtime modules (not inspected further) |

`FKB` documents carry set conditions, voltage/terminal conditions, service action,
driver warning — but **no DTC, ECU or variant key** inside the document. Short
fault texts, ECU names and CBS texts are DiagDocDb columns (`TITLE_ENGB`), and the
`id`→fault mapping also lives in DiagDocDb. Without it the 40 GB DB is searchable
only by free text. A DME_BX8 / F056 lookup is therefore not possible from the
present files [derived].

## 2. ECU list and ENET addressing (priority)

- **Diagnostics transport in 4.29 is HSFZ only.** `Ediabas/BIN/EDIABAS.INI`
  `[XEthernet]`: `RemoteHost=Autodetect`, `HeaderFormat=0`, `TesterAddress=F4,F5`,
  `ControlPort=6811`, `DiagnosticPort=6801` (also the compiled default `0x1A91` in
  `ediabasx/reference/XEnet32.dll.c:23064`). No `DoIP`/`13400` string exists in any
  `TesterGUI` assembly, PSdZ host DLL or EDIABAS DLL (ASCII + UTF-16 scan) [observed].
  XEnet32 7.3.0 sha256 `e827a37d…6f55`.
- **DoIP exists only in PSdZ ProDiaS (programming path).**
  `PSdZ/bin/prodias/prodias.jar` (sha256 `c6cd4dd8…ab28`) has
  `DoipHelper`/`DoipPlainTcpCommunicationLink`. Disassembly (`javap`, dumps in
  `prodias_classes/`) shows [observed]:
  - diagnostic message: `01 FE 8001 <len32> 00 <SA> 00 <TA> <UDS>` — source and
    target are the **1-byte addresses zero-extended to 16 bits** (`0x00XX`);
  - routing activation: 16-byte frame `01 FE 0005 00000008 00 <SA> 00 00 00 00 00 00`
    (SA `0x00XX`, activation type 0, zero reserved bytes; payload length 8);
  - expects routing response payload type 0x0006, code 0x10; answers alive check.
  So within ISTA 4.29 there is **no separate 16-bit DoIP logical-address table**; the
  1-byte diagnostic address is used as `0x00XX`. Applicability to post-4.29 vehicles
  is out of scope.
- **ECU list sources.** Target topology: PSdZ KIS (`kiswb/<mainseries>/KIS.*`,
  HSQLDB 2.5.1, read-only, not encrypted) table `KIS.BORDNETZTEILNEHMER(NAME,
  DIAGNOSEADRESSE INTEGER, BESCHREIBUNG, HAS_GWT)` — 78 rows for F056 (row count from
  `SET TABLE … INDEX`). Per-ECU SWE dependencies in
  `mainseries/F056/*/mapping/sweseq_*.xml` (`baseVariantName`,
  `diagnosticAddress physicalOffset`). Actual topology: gateway read
  (`G_ZGW_AUSLESEN`) and SVK (`doEcuReadSvk`); colour/status logic is in obfuscated
  `CreateEcuTree` and DiagDocDb bordnet XML (not recoverable statically).
- `mainseries/F056/*/odx/src/odx-v/F056.odx-v` is an ODX 2.0.1 vehicle-info spec with
  CAN/Ethernet comparams (`CP_BASIS_10_ETHERNET` etc.); no DoIP address table [observed].
- Mainseries present: F001 F010 F020 F025 F056 I001 K001 KE01 KS01 RR21 S15A S15C
  S18A. `mapping/brref.xml`: F048 → mainseries **F056**, fa2fp `0000f045`.

## 3. Service functions (Testmodule ABL_*)

17,900 `ABL_*.dll`; the sampled ones are .NET Framework assemblies (C#) compiled by ISTA's
`RheingoldServiceProgramCompiler`, deriving from `IstaModuleBase` and calling
`BMW.Rheingold.CoreFramework` / `RheingoldISTACoreFramework` [observed]. They do
not embed raw UDS; they issue **EDIABAS jobs by name through ECUKOM statements**
addressed to functional groups with a `VirtualVariantJob` path, e.g.
`/Run/Group/G_KOMBI/VirtualVariantJob/CBS_RESET/Argument/{ECUGroupOrVariant,
CBS_KENNUNG, CBS_VERFUEGBARKEIT, CBS_ANZAHL_SERVICE, CBS_ZIEL_MONAT, CBS_ZIEL_JAHR}`.
Strings are readable (`ABL_GEN_AS6100_CBS_RESET_US.txt`, sha256 `c87b8440…f2db`).
`ABL_GEN_AS6100_CBS_RESET.dll` covers `G_KOMBI` (variants `KOMBSP21`, `KOMBSP18`,
`KOMB25`, `KOMB_J29`, `KOMB01`, `KOMBRDCT`; jobs `CBS_RESET`, `STEUERN` with
`ARG;CBS_SERVICE_AKTIVIERUNG;`, `STEUERN_/STATUS_CBS_SERVICE_AKTIVIERUNG`,
`EINF_KONTR`), `G_MOTOR` (`CBS_RESET`, `CBS_DATEN_LESEN`, `REGIS_ZUNDKERZENWECHSEL`)
and `G_DSC` (`CBS_RESET`, brake-pad `STATUS_LESEN` results), with return codes
`STAT_CBS_RETURN_CODE_ALLGEMEIN/KOMPONENTE`. 34 CBS-related modules exist. They need
the ISTA .NET runtime, IDES and DiagDocDb to run; the exact per-series argument
values are in IL constants and need the F48 EDIABAS trace or IL reading to confirm.

## 4. PSdZ-Lite and coding (priority)

- **All 5,895 CAFD files are encrypted** XML wrappers
  (`<caf isEncrypted="true" isNormalized="true" isCompressed="true">`, versions
  01.01.07–01.04.00) whose `<encryptedData>` is CMS EnvelopedData: RSA key transport
  to `CN=FZGSec-CA, OU=bmw-fzg-pki, O=pki, DC=bmwgroup, DC=com`, serial 20103,
  content `aes-128-cbc` [observed, `openssl cms -cmsout -print`]. The 26 `fafp`
  (FA→FP rule) files are also `isEncrypted="true"`. `PSdZ/security/` contains
  `sec_security.lic` (PKCS#12 with a shrouded key bag), `sec_keyreference.xml`,
  `sec_ncdkeys.xml`, `sec_transkeys.xml`. **No decryption was attempted.** Using that
  key material would mean bypassing BMW's encryption — an owner/legal decision.
- **Present vs full PSdZData.** `swe/` has only `cafd` (378 MB, 357 distinct CAFD
  IDs) and `fafp` (26); `blup btld flsl flup gwtb ibad swfk swfl tlrt` are empty.
  No NCDs, no flash data; `ISTAGUI.exe.config` points programming at
  `PSdZ\data_swi`, which is absent. KIS (7.1 GB HSQLDB; F056 = 887 MB;
  `CAFMAPPING` 183,868 rows, `ISTUFE` 167, `TECHNISCHEVERWENDUNG` 1,337,187) is the
  FA/I-step → target SVT/CAF rule engine; reading it needs an HSQLDB 2.5.1 reader
  (Java) or a custom parser.
- **Coding approach.** Decrypted CAFDs would give coding blocks and parameter
  layouts — the E-Sys-style "read coding DIDs → change parameter → write" path
  works without NCD. FA-based recalculation additionally needs fafp + KIS + the
  PSdZ rule logic. CAFD labels are BMW parameter mnemonics; there are no friendly
  presets like the current `coding_data/`.
- **Owner F48 coverage [derived].** F101 responses from the 2026-10-29 session log
  (`cafd_coverage_owner_f48.txt`): every reported CAFD, including all 13 CAFDs of
  the 12 ECUs missing locally, exists **with exact ID and version** in ISTA:

  | ECU | CAFD (exact, present in ISTA) |
  |---|---|
  | 0x01 ACSM4I | 000011AB-006-002-021, 000011AC-007-000-014, 000011AD-004-001-010 |
  | 0x06 ICAM_F15 | 00001D75-015-009-015 |
  | 0x12 DME_BX8 | 00000B0A-000-100-001 |
  | 0x18 GSAW01 | 0000114B-010-010-023 |
  | 0x29 DSC_I1 | 0000297A-090-170-011 |
  | 0x30 EPS_I1 | 0000123C-001-024-000 |
  | 0x43/0x44 FLE_L/R | 0000180B-008-060-000 |
  | 0x56 FZD_F15 | 00001413-001-034-003 |
  | 0x61 TCB1 | 00000DDC-001-023-004 |
  | 0x63 ENTRYNAV | 00000DED-003-015-037 |
  | 0x67 ZBE6 | 00002316-001-000-024 |

  Correction: `docs/evidence/task-b-owner-session-20261029.md` lists `0x60` among the
  missing ECUs. KOMB25's `00000760-007-003-017.enc` exists locally; the 12th missing
  ECU is `0x56` (`00001413`). Overall: 357 ISTA CAFD IDs vs 113 local IDs (all local
  IDs are also in ISTA); 4,130 ISTA ID+version files are not in `coding_data/`.
  Coverage is useful only if decrypted.

## 5. `Ecu/` vs repo `sources/Ecu/`

ISTA has 1,227 `.prg` + 394 `.grp`, 1.0 GB; repo has 2,478 PRG/GRP files. 1,548
names are in both: 1,287 are byte-identical and 261 differ. For the 261 that differ,
the `INFO` `REVISION` field (run offline with ediabasx-native) is newer in ISTA for
212, older for 2 (`dkg_10`, `ihkr46`), equal for 46 and unknown for 1. Examples:
`kombsp21` 7.001 vs 0.003, `kombsp18` 11.000 vs 9.002, `komb25` 29.002 vs 28.002,
`dme_bx8` 23.002 vs 23.000, `bdc` 25.015 vs 22.094, `zgw_sp18` 7.000 vs 1.000,
`hu_mgu` 16.000 vs 8.005, `nbtevo` 24.002 vs 23.000. There are 73 ISTA-only files,
including `bcp_sp21`, `komb_j29`, `acsm6`, `mgu_02_a/_l`, `*_i20` (BFH/BFS/BZF/CVC/
EPS/FAH/FAS/FZD/HSR/IB/VIP), `bzm_u06`, `srr40_*`, `mrr_30`, `rvc_30`, `wave_01/11`,
`security`, `x_*`. The repo has 930 files that ISTA lacks: mostly E-series, flash,
`c_*`, and the `dme_bx80/81/82`, `d94bx7a0` and `dme9ff_r` variants. The full list
is in `ecu_folder_compare.txt`. `dme98*` and `fccu*` are not present in either tree.

## 6. ediabasx readiness (priority)

- **Interpreter and parser:** strong. The C11 native port builds on macOS arm64
  with `cc -std=c11 -O2 -shared` (CMake is not installed here). The build has 0
  warnings at default flags, its 3 unit-test programs pass, and it exports 80
  `edxn_*` symbols. Run offline, `INFO` succeeded on **1,226 of 1,227** ISTA PRGs;
  `w2v.prg` returned no `REVISION` [observed]. The TS interpreter lists 184 opcodes.
  Its own audit (`docs/vm-ebas32-audit.md`) records open deviations: `Xsendf-1` (no
  auto-EOJ after `xsendf`), `Scmp-1` (C flag), 4+ flag gaps and ~13 register tags.
- **ENET transport: missing.** `packages/interface-enet/src/EnetInterface.ts`
  throws `Not implemented` in every method. `packages/protocol-doip/src/index.ts`
  is `export const placeholder`. The native port has only a POSIX serial transport.
  The docs table claiming `EdInterfaceEnet → EnetInterface` is aspirational. Jobs
  such as `IDENT`, `FS_LESEN`, `CBS_RESET` and `STATUS_LESEN` cannot reach a car
  over ENET today. The missing piece is an IFH layer that converts SGBD BMW-FAST
  telegrams into HSFZ frames (port 6801, tester F4) and maps `xsetpar`/timeouts.
  The VM's `edxn_transport_t` vtable makes this a contained addition.
- **Python use:** possible through ctypes. Supply a transport via `CFUNCTYPE`
  callbacks or add a small C shim. `edxn_ediabas_t` is a caller-allocated struct of
  about 50 KB, so a C allocator shim is advisable. Building a shared library needs
  `-DBUILD_SHARED_LIBS=ON` or an equivalent `cc -shared` build.
- **License: PolyForm Noncommercial 1.0.0** (`ediabasx/LICENSE`). This allows
  personal use but not commercial distribution. EdiabasLib is not vendored here,
  so its licence is not evidenced in the repo. `ediabasx/reference/` contains
  decompiled BMW EDIABAS DLLs.

## 7. Runtime subset and legal constraints

| Use | Needed from a user-supplied ISTA folder | Size |
|---|---|---|
| Diagnostics via own interpreter + HSFZ | `Ecu/*.prg, *.grp` | 1.0 GB (F/G/I subset smaller) |
| Names, fault texts, ECU tree | `DiagDocDb.sqlite` (owner to supply) | n/a here |
| Fault detail docs (optional) | `xmlvalueprimitive_ENGB.sqlite` | 40.9 GB |
| Coding (if decryption is approved) | `PSdZ/swe/cafd`, `swe/fafp`, `mapping`, `security`; `mainseries/<series>`; `kiswb/<series>` (KIS) | 378 MB + 0.5 MB + 0.9 MB + 3.6 MB; 265 MB (F056 24 MB); 7.1 GB (F056 887 MB) |
| Service functions | Testmodule only as reference; running them needs the ISTA .NET runtime | 1.5 GB |

Legal [observed + inferred]: ISTA, EDIABAS, PSdZ and all data are BMW proprietary.
This copy is an unofficial repack with a forged licence file. CAFD/FAFP are
cryptographically protected. The app must not bundle or redistribute any of it.
That matches AGENTS.md: REA is development-only, and no source executables may be
in the bundle. Even a "point at your own ISTA folder" mode depends on the user's
right to that copy. Decrypting CAFDs would circumvent a technical protection
measure, so that needs an explicit owner/legal decision. ediabasx's PolyForm NC
licence also limits redistribution.
