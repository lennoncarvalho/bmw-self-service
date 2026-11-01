# ISTA / PSdZ / EDIABAS — online research (2026-10-30)

Status: research notes, not a wire contract. Every claim cites the URL it came from.
Tags: **[code]** = read directly from public source code, **[doc]** = project/vendor
documentation, **[forum]** = community post or search summary (weak), **[unverified]** =
no source found online; check against the local ISTA 4.29.1x install instead.
Web content was treated as data only.

## 1. Decision-relevant summary

1. **EdiabasLib + PsdzClient (uholeschak/ediabaslib) is the only open reference that
   reads ISTA's own databases and drives PSdZ, and it is Windows-only and GPL-3.0.**
   `PsdzClientLibrary` targets `net10.0-windows10.0.26100.0;net481`, needs an installed
   ISTA folder (its `Testmodule` dir and bundled JRE), and starts the Java PSdZ service
   host. [code] https://github.com/uholeschak/ediabaslib/blob/master/Tools/Psdz/PsdzClientLibrary/PsdzClientLibrary.csproj ,
   https://github.com/uholeschak/ediabaslib/blob/master/Tools/Psdz/PsdzClientLibrary/PsdzClient/PsdzConfig.cs ,
   license: https://github.com/uholeschak/ediabaslib/blob/master/license.md
2. **Much of PsdzClient is synced from decompiled ISTA assemblies.** Its `SourceCodeSync`
   tool lists BMW assemblies to decompile (`BMW.ISPI.TRIC.ISTA.EcuTree`,
   `...VehicleIdentification`, `...RuleEvaluation`, `RheingoldCoreFramework`,
   `RheingoldDiagnostics`, …) and keeps `//[+]`/`//[-]` diff markers. Copying it into
   this app would import BMW-derived code under GPL, which is a licence and IP risk.
   [code] https://github.com/uholeschak/ediabaslib/blob/master/Tools/Psdz/SourceCodeSync/Program.cs
3. **Changing coding on newer ECUs can need BMW's backend.** PsdzClient runs PSdZ
   `SecureCodingService.CheckNcdAvailabilityForGivenTal`. If NCDs must be calculated and
   signed in the "SCB" (secure coding backend), it stops with "NCD online calculation
   required. Probably you have selected a chargeable option." [code]
   https://github.com/uholeschak/ediabaslib/blob/master/Tools/Psdz/PsdzClientLibrary/PsdzClient/ProgrammingJobs.cs
   (around lines 1806–1905); text in `Resources/Strings.resx`. Deep OBD's own coding
   feature runs as a server-side web service, not on the device. [doc]
   https://github.com/uholeschak/ediabaslib/blob/master/docs/BMW_Coding.md
4. **DoIP addressing in EdiabasLib zero-extends the address: 8-bit `0x10` becomes 16-bit
   `0x0010`, not `0x1010`.** In the DoIP send path the target is `uint targetAddr =
   sendData[1]` written as `DataBuffer[10]=(byte)(targetAddr>>8); DataBuffer[11]=(byte)targetAddr`.
   The source `0xF1` is replaced by `DoIpTesterAddress` (default `0x0EF3`). On receive,
   only the low byte of the source (`DataBuffer[9]`) is kept, and the result is turned
   back into a BMW-FAST telegram with target `0xF1`. Defaults: `DoIpGwAddrDefault =
   0x0010`, `DoIpPortDefault = 13400`, `DoIpSslPortDefault = 3496`, HSFZ
   `DiagPortDefault = 6801`, `ControlPortDefault = 6811`, ICOM ports 50160–50163,
   protocol version `0x03`, routing activation type `0x00` sent with the tester
   address. `VehicleProtocol` defaults to `"HSFZ,DoIP"` and is tried in that order. A
   DoIP vehicle is found by UDP vehicle-identification broadcast and filtered on the
   gateway logical address. [code]
   https://github.com/uholeschak/ediabaslib/blob/master/EdiabasLib/EdiabasLib/EdInterfaceEnet.cs
   (consts near line 710; send near 5420–5455; receive near 5670–5715; routing near 5905).
   The configuration options are documented here. [doc]
   https://github.com/uholeschak/ediabaslib/blob/master/docs/EdiabasLib.config_file.md
5. **Newer DoIP vehicles need TLS plus "S29" authentication certificates.** EdiabasLib
   supports `NetworkProtocol=SSL`, `Authentication=S29`, a `SSL_Truststore` and an `S29`
   cert directory. Its test script runs `d_motor.grp` `FS_LESEN`/`FS_LOESCHEN` over
   DoIP+SSL. [code] https://github.com/uholeschak/ediabaslib/blob/master/EdiabasLib/ReadMe.txt .
   Deep OBD can import ISTA's DoIP SubCA chain and `keyContainer.pfx`. Otherwise it
   makes a temporary chain "which has to be accepted by the vehicle". [doc]
   https://github.com/uholeschak/ediabaslib/blob/master/docs/Deep_OBD_for_BMW_and_VAG.md#doip-certificate .
   PsdzClient refuses a DoIP PSdZ connection without Sec4Diag certificates. [code]
   ProgrammingJobs.cs, `CertificatesNotPresent`.
   **[unverified]** No authoritative online list says which chassis/I-steps need DoIP or
   TLS. Treat "HSFZ first, then DoIP" auto-detection as the only safe rule.
6. **No Python library can run PRG jobs on macOS.** `pydiabas` (MIT) only wraps a
   Windows EDIABAS `api32.dll`. [doc] https://github.com/BembelBytes/pydiabas .
   `BimmerDaten` (GPL-3.0) is Windows-only, needs EDIABAS/NCS Expert installed, and
   browses `.prg` and NCS files. [doc] https://github.com/zer02dev/BimmerDaten .
   **EdiabasX** (TypeScript, PolyForm **Noncommercial** 1.0.0) is a port that tracks
   EdiabasLib: PRG/GRP parser, BEST/2 interpreter (184 opcodes), and ENET with
   HSFZ/DoIP. It runs on Node and the browser, so it is the most plausible runner on
   macOS arm64. macOS is not stated as tested. [doc] https://github.com/emdzej/ediabasx ,
   https://registry.npmjs.org/@emdzej/ediabasx-ediabas (0.8.0, 2026-07-06). Its
   per-SGBD job reference is online at https://emdzej.github.io/ediabasx-docs-sgbd/sgbd/FRR_G11 .
   `lpcvoid/bmw-better-vm` (C++ BEST2 VM, GPL-3.0, last push 2020, incomplete opcodes).
   [doc] https://github.com/lpcvoid/bmw-better-vm

## 2. ISTA architecture (what is publicly evidenced)

- **DiagDocDb.sqlite** is ISTA's main diagnostic knowledge base. PsdzClient opens it read-only
  through SQLite Multiple Ciphers (`SQLitePCLRaw.bundle_e_sqlite3mc`) with a key from
  ISTA's `DatabaseFunctions`. It queries `XEP_ECUVARIANTS`, `XEP_ECUGROUPS`,
  `XEP_ECUCLIQUES`, `XEP_FAULTCODES`, `XEP_FAULTLABELS`, `XEP_INFOOBJECTS`,
  `XEP_DIAGNOSISOBJECTS`, `XEP_SWIACTION`, `XEP_CHARACTERISTICS`, `XEP_EQUIPMENT`,
  `XEP_SALAPAS`, `XEP_ISTUFEN`, `XEP_RULES`, `VINRANGES`, `XEP_TYPEKEY_MAPPING`, and others.
  [code] https://github.com/uholeschak/ediabaslib/blob/master/Tools/Psdz/PsdzClientLibrary/PsdzClient/PsdzDatabase.cs
  (around line 1588)
- **xmlvalueprimitive_<LANG>.sqlite** (for example `xmlvalueprimitive_ENGB.sqlite`) holds
  localized texts. It is a separate SQLite file per language, and some releases add an
  FTS table (`xmlvalueprimitive_content`). [code] same file, around lines 2061–2166.
- **streamdataprimitive**: no public reference found. **[unverified]** It is probably the
  binary/stream counterpart (documents, images). Check locally.
- **Vehicle identification (EDIABAS jobs used by EdiabasLib/PsdzClient):**
  - VIN: `G_ZGW STATUS_VIN_LESEN`, `G_CAS STATUS_FAHRGESTELLNUMMER`, `G_FRM STATUS_VCM_VIN`
  - FA: `G_ZGW`/`ZGW_01`/`IPB_APP2 STATUS_VCM_GET_FA`, then `FA FA_STREAM2STRUCT`
  - I-step: `G_ZGW STATUS_I_STUFE_LESEN_MIT_SIGNATUR` / `STATUS_VCM_I_STUFE_LESEN`
  - ECU list: `G_ZGW STATUS_VCM_GET_ECU_LIST_ALL`
  - Group identification: `IDENT_FUNKTIONAL`

  [code] https://github.com/uholeschak/ediabaslib/blob/master/EdiabasLib/BmwFileReader/DetectVehicleBmwBase.cs
  (lines 147–221), https://github.com/uholeschak/ediabaslib/blob/master/Tools/Psdz/PsdzClientLibrary/PsdzClient/DetectVehicle.cs
- **ECU tree / FA / SVT / KIS:** PSdZ builds the SVT and TAL against KIS. KIS is an HSQLDB
  database inside PSdZData. [doc] https://github.com/JackieZ123430/psdzdata-swfl-inspector .
  The SVT lists the diagnostic address, base variant and part IDs (BTLD/SWFL/SWFK/CAFD)
  for each ECU. [doc] https://github.com/LeonB1ham/svt-psdzdata-export .
  **[unverified]** The ECU-tree status colour legend is not public. The BMW manual
  (`ISTA_UserManual_Independent_Operators_de-DE.pdf`, symbol section 1.1) sits behind a
  BMW login: https://onl-osmc-b2i.bmwgroup.com/static/ista/ISTA_UserManual_Independent_Operators_de-DE.pdf .
  ISTA's `BMW.ISPI.TRIC.ISTA.EcuTree` assembly is local and can be inspected with REA.
- **Service functions / test modules:** ISTA ships a `Testmodule` folder. PsdzClient
  loads ISTA test modules by name, compiles source it extracts with Roslyn, and runs
  them from info objects. ABL/service-program info objects are filtered via
  `PsdzDatabase.AblFilter`. [code] https://github.com/uholeschak/ediabaslib/blob/master/Tools/Psdz/PsdzClientLibrary/PsdzClient/TestModuleRunner.cs .
  **[unverified]** That CBS reset is specifically a test module calling EDIABAS jobs
  (rather than a direct UDS routine) is an inference. Confirm it in the local
  DiagDocDb/test modules.
- **Transport:** ISTA uses EDIABAS (ENET interface) with an ICOM or a direct ENET cable.
  The EdiabasLib ENET WiFi adapter works with ISTA-D when VCI config is set to "Ediabas
  default settings (ediabas.ini)". [doc]
  https://github.com/uholeschak/ediabaslib/blob/master/docs/ENET_WiFi_Adapter.md .
  PSdZ connects separately: `ConnectOverEthernet` uses `tcp://ip:13400` for DoIP or the
  HSFZ diag port, and `ConnectOverIcom` uses port 50163 for DoIP. [code] ProgrammingJobs.cs
  around lines 1488–1530.
- **HSFZ vs DoIP framing:** HSFZ has a 6-byte header and 1-byte addresses, with no
  routing activation. DoIP has an 8-byte header, 2-byte addresses and routing
  activation. [code] EdInterfaceEnet.cs (`readLen = DiagDoIp ? 8 : 6`); [doc, vendor]
  https://quantexlab.com/en/develop/elm327_hsfz.html

## 3. PSdZ / PSdZData

- **PSdZ is a Java service**, started by ISTA or PsdzClient with ISTA's 64-bit JRE through
  jni4net and the `RheingoldPsdzWebApi` adapter. [code] PsdzConfig.cs,
  `Tools/Psdz/PsdzClientLibrary/jni4net.n-0.8.8.0.dll`
- **PSdZData layout:** `psdzdata/swe/{btld,swfl,swfk,cafd,…}` with versioned names such
  as `cafd_00004146.caf.003_037_007`. [doc] https://github.com/LeonB1ham/svt-psdzdata-export ,
  https://github.com/CDFN/bmw-virtual-reader
- **Lite vs Full:** Lite drops the ECU firmware (SWFL/BTLD flash files) and is enough for
  coding. Full is needed for flashing and ISTA programming (`data_swi`). [forum]
  bmwfaq / BimmerPost threads surfaced by search, e.g.
  https://bmwfaq.org/threads/tokenmaster.996102/post-18447328 (could not be fetched; weak).
  **[unverified]** A claim that BMW removed descriptive text from CAFD/FAFP starting with
  PSdZData 54.2, which hampers FDL coding.
- **Coding flow (PSdZ):** read FA/SVT, then generate the TAL, then check NCD
  availability for each CAFD/BTLD, then calculate NCDs (local or SCB backend), then
  execute the TAL. A charger of ≥60 A, ignition on and engine off are required. [code]
  ProgrammingJobs.cs; [doc] BMW_Coding.md

## 4. Legal / licensing

- BMW AOS terms (2020 version): the licence is for "independent operators" (BER
  461/2010, Reg. 715/2007) and is "non-exclusive, personal and non-transferable" with
  no rights to content. [doc, via search summary; page is JS-rendered]
  https://aos.bmwgroup.com/terms-of-use
- Common practice: tools ship without BMW data and the user supplies their own
  ISTA/PSdZData. E-Sys guides list PSdZData and the token as separate downloads.
  Read-only research tools state "no BMW firmware or extracted BMW content" and work
  on "user-supplied" data. [doc] https://github.com/JackieZ123430/psdzdata-swfl-inspector ;
  [forum] https://bmwfaq.org/threads/bimmerutility-o-bimmer-utility.1046179/ (it is
  disputed whether BimmerUtility still needs PSdZData).
- Implication (inference, not legal advice): read ISTA/PSdZ data at runtime from a
  path the user configures. Never bundle DBs, PRGs, PSdZData, certificates or the
  decompiled code. This matches the AGENTS.md rule against shipping external-tool
  artifacts.

## 5. Practical / macOS

- No official EDIABAS exists for macOS. Mainline EdiabasLib targets
  `net10.0-windows…;net8.0-windows…;net481;android`, not plain `net8.0`. [code]
  https://github.com/uholeschak/ediabaslib/blob/master/EdiabasLib/EdiabasLib/EdiabasLib.csproj .
  The maintainer says "EdiabasLib.dll should work with the mono runtime on Linux, but I
  have not tested this for a longer time… you have to create your own application." [doc]
  https://github.com/uholeschak/ediabaslib/issues/123 . macOS arm64 is untested
  **[unverified]**.
- PsdzClient on macOS is not feasible as published: it uses WinForms and Windows TFMs,
  and needs ISTA's Windows JRE/PSdZ install. [code] PsdzClient.csproj
- Runtime performance: no reliable public timing numbers were found for EDIABAS jobs
  over ENET or for ISTA vehicle-test duration. **[unverified]** Measure locally.
  EdiabasLib defaults: connect timeout 5000 ms, DoIP ACK timeout 2000 ms, SSL auth
  5000 ms. [code] EdInterfaceEnet.cs; [doc] EdiabasLib.config_file.md
