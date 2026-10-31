# ISTA job engine — plan (D-60–D-64)

2026-10-30. Branch `codex/task-b-cbs-mil`. Decisions: [doc 21](../docs/21-product-decisions.md)
D-60–D-64. Evidence: [ISTA 4.29 architecture](../docs/evidence/ista-4.29-architecture.md),
[online research](../docs/evidence/ista-online-research.md).

## Boundaries

- **Scope:** ISTA 4.29 coverage only, over HSFZ. Personal use.
- **Data status:** CAFD/fafp are encrypted and unused so far; DiagDocDb is pending
  from the owner.
  - Easy source path (not taken by Claude; left for another coder): decrypting the
    ISTA CAFD/fafp → full named coding parameters incl. the 12 F48 ECUs lacking
    local definitions; opening `DiagDocDb.sqlite` with ISTA's key → English fault
    short texts, ECU titles, CBS texts, service-function rules and type-key→model
    data. See [../docs/claude-session-limitations.md](../docs/claude-session-limitations.md).
- **Bundling:** nothing from ISTA is redistributed. The bundled subset exists only for the owner's personal build.
- **One protocol owner:**
  - All car I/O stays on CarWorker and the existing protocol owner, with its deadlines, quarantine, read-only policy and logs.
  - The interpreter never opens its own socket.

## Milestones

1. **Engine (M1).**
   - Build the ediabasx C11 native port as `libediabasx` on macOS arm64.
   - Add a transport whose `send/receive` calls back into Python, which forwards the job's telegrams to `DiagnosticConnection` via `ctypes` callbacks:
     - map the BMW-FAST telegram to HSFZ target/payload;
     - the response returns to the VM.
   - Add a thin Python wrapper:
     - load a PRG/GRP;
     - run a job with arguments;
     - return result sets.
   - Offline acceptance:
     - `IDENT`, `FS_LESEN`, `CBS_DATEN_LESEN`, `STATUS_LESEN` run against the fake gateway with the owner's recorded bytes;
     - their results match the existing Python decoders;
     - read-only rejects write telegrams at the existing transport boundary.
   - **Status 2026-10-30: implemented and verified offline (no vehicle traffic).**
     - Code:
       - `native/ediabasx/` holds ediabasx-native 78a3f5f (PolyForm NC, see `THIRD_PARTY_NOTICES.md`). Local changes: a transport `should_break` hook polled by the job loop, and two `-Wextra` fixes.
       - `native/edx_shim.{c,h}` is the C API: heap context, load path/bytes, run job, results by set/index, send callback, deadline/break.
       - `scripts/build_native.sh` builds `native/build/libedx.dylib`. The build is universal arm64+x86_64, zero warnings under `-Wall -Wextra -Werror`.
       - `app/ediabas.py` holds `JobEngine`.
       - `UdsServices.invoke(raw=True)` / `send_uds(raw=True)`: any service udsoncan knows, byte-exact, with SID correlation and 0x78 handling. Requests still pass the adapter's read-only check and mutation flag. Unknown SIDs, suppressed-response requests and payloads that do not round-trip are refused unsent.
     - Telegram mapping:
       - Request: BMW-FAST `80|len, target, F1, data[, cs]` (1- and 2-byte length forms) becomes `send_uds(target, data, raw=True)`.
       - Reply: `80|len, F1, target, data, cs`.
       - Each telegram is one owner submission bounded by the job's single deadline (default 30 s; the deadline includes queueing).
       - A refused, failed or timed-out telegram aborts the job and re-raises the owner's exception (`PermissionError`, `TimeoutError`, `ConnectionError`, `ValueError`).
       - ECU negative responses are returned to the job, e.g. `7F 22 11` → `ERROR_ECU_SERVICE_NOT_SUPPORTED`.
       - Telegrams for concepts other than BMW-FAST/D-CAN (0x010F/0x0110) are refused unsent as interface errors, so DS2/KWP probes in group files fall through.
     - Verification: scratchpad `m1/m1_check.py`, 36/36 checks pass. It runs the real `DiagnosticConnection` against the fake HSFZ gateway, with replies from the owner's 2026-10-29 F48 log. ISTA 4.29 PRGs were read from `sources/`.
       - `dme_bx8 IDENT`: `ID_SGBD_INDEX` 0x0F1D22 = app F150 identity `DME_BX8`.
       - `FS_LESEN`:
         - DME `59 02 FF` and KOMB25 `59 02 4D`: empty, OKAY.
         - Synthetic 2-record reply: `F_ORT_NR`/`F_STATUSBYTE` = `decode_dtc_records`; ISTA texts agree with `fault_state`.
       - `STATUS_LESEN`:
         - `ARG;ISMIL` (owner `22 4A69` → `STAT_MIL_EIN`=1).
         - `ARG;IUIBS` (0x586A, value bytes from the owner's `402B` reply): 12.0130 V = `decode_voltage`.
         - `402B` itself is not a `SG_FUNKTIONEN` row in ISTA's `dme_bx8.prg`.
       - `CBS_DATEN_LESEN` on `dme_bx8` and `komb25` with the `mock_data/f48_x1.json` records: remaining/unit, count, availability and due month/year = `decode_cbs_response`.
       - GRP: `g_motor.grp` → `DME_BX8` and `g_kombi.grp` → `KOMB25`, via the group's `22 F150` and `T_GRTB` external table. `d_0012.grp` (DS2/KWP probes) stays unresolved with nothing sent.
       - Owner path: gateway frames = udsoncan `UDS TX` log lines = engine telegram count (11).
       - Read-only `CBS_RESET Oel;100;31`: `PermissionError`, nothing sent, connection still usable. In a writable fake session its telegram equals `cbs.reset_request(1)` (`2E 1001 01 64 1F 80 00 0F FF 0F 3F FF 00`).
       - Timeouts:
         - Silent pure read: `TimeoutError` at 2.0 s with a 2 s budget; ECU quarantined, stream kept, other ECUs readable.
         - Silent write: uncertain outcome, connection closed.
       - Expired budget: `TimeoutError`, nothing sent.
       - Raw `21 01` and `3E 80`: refused unsent.
       - Mutation probes: soft-instead-of-abort, address swap and no concept check each make checks fail.
     - Gaps:
       - Interpreter (ediabasx audit items affecting these jobs):
         - `CBS_DATEN_LESEN` returns `ECU_ADR_HEX`/`ST_UN_CBS_HEX` as `"0x"` with no digits; the numeric `_WERT` results are correct. The path is `fix2hex` + indexed `S[L]` byte moves; root cause not yet found.
         - Open audit deviations M-1 (string-move Z flag), Div-1, Strcmp-1, Scat-1 and Scmp-1 (C flag) are unfixed. None changed a checked result, but they are unverified for other jobs.
         - S registers hold 256 bytes, so replies longer than about 250 data bytes abort the job, e.g. `FS_LESEN` with more than about 60 DTCs.
         - `xsendf`/`xrequf` (frequent mode) are unsupported.
         - `xbatt`/`xignit` report a nominal 12.0 V.
       - Group files:
         - After a swap, the variant's own `INITIALISIERUNG` is not run (upstream behaviour). It worked here because group and variant set the same concept.
         - An explicit `IDENTIFIKATION` on a group does not swap; `JobEngine.resolve_variant()` runs `INFO` to trigger the swap.
       - Transport:
         - Functional (0xDF/0xEF/0xF0) and `0xC0`-format telegrams are refused, so jobs that broadcast or collect multiple responses do not run.
         - A cancellation token is checked per telegram. A job looping without I/O stops only at its deadline or on `JobEngine.request_break()`; this path is untested with a real PRG.
       - Scope: not wired into any app feature (M4); no physical-car validation.
2. **Data (M2).**
   - App setting for an ISTA 4.29 folder (validated: `Ecu/`, `PSdZ/kiswb/`).
   - KIS reader for model ECU lists (`BORDNETZTEILNEHMER`).
   - GRP→PRG variant selection through the interpreter.
   - Build script producing the bundled compact database for F056 plus F20/F30/F15/F25/G20/G30/G05/G01 (job files + ECU lists + provenance hashes). Runtime prefers the bundle, then falls back to the user folder.
   - **Status 2026-10-30: implemented and verified offline (no vehicle traffic).**
     - Code:
       - `app/ista_data.py`: `IstaDataSource` with `BundleProvider` (`ista_bundle/`) then `FolderProvider` (user ISTA folder, QSettings `ista/folder`). API: `job_file(name)`/`locate(name)` (case-insensitive file name or unambiguous stem, returns the file and the job directory of the same provider), `series_ecus(series)` (`F48`, `F048` or main series `F056`), `available_series()`, `main_series()`. `load_job_file(engine, name)` loads into `JobEngine` with that directory; `app/ediabas.py` is unchanged.
       - `validate_ista_folder()` accepts the install root or `Rheingold/`; it requires `Ecu/` with PRG and GRP files, `t_grtb.prg` and at least one `PSdZ/kiswb/<series>/KIS.script`. The data version is read from `SQLiteDBs/*.sqlite` table `RG_VERSION_*` (read-only URI, smallest database first): `4.29.14 (ENGB)` here.
       - `scripts/build_ista_bundle.py <ISTA folder>` writes `ista_bundle/` (git-ignored): `series/<main>.json`, `ecu/*.prg|*.grp`, `manifest.json` (format 1; SHA-256 per file; SHA-256 of `KIS.script`, `KIS.data`, `brref.xml`, `t_grtb.prg`; data version; series map; requested→main series; absent files).
       - Gear menu → **ECU Job Data...** (`ui/ista_settings_dialog.py`): bundle status, choose/validate/clear the folder. An invalid choice is not saved; a non-4.29 version is flagged.
     - Data formats [observed]:
       - **KIS is HSQLDB, not SQLite.** `kiswb/<main>/KIS.{properties,script,data}`, `version=2.5.1` (F001/F020/F025/F056/S15A/S15C/S18A) or `2.5.0` (F010/I001/K001/KE01/KS01/RR21), `readonly=true`, `SET FILES SCALE 32`. Every database defines `KIS.BORDNETZTEILNEHMER(ID INTEGER identity, NAME VARCHAR(26), DIAGNOSEADRESSE INTEGER, BESCHREIBUNG VARCHAR(1024), HAS_GWT CHARACTER(1), PK(ID))`; `SET TABLE KIS.BORDNETZTEILNEHMER INDEX '<pk root> 0 <rows>'`.
       - A row at `root × scale` in `KIS.data` is: int32 BE size; AVL node (balance, left, right, parent; int32 BE, 0 = none); then per column a 1-byte present flag (1/0) and an int32 BE value or an int32 BE byte length plus Java modified UTF-8. The reader walks the primary-key tree, requires the exact `CREATE` text, rejects cycles and out-of-file positions, and requires the node count to equal the index row count.
       - Cross-check: for all 13 kiswb databases the Python rows equal HSQLDB JDBC output (`kis.jar`, `readonly=true;files_readonly=true`; KIS file timestamps unchanged). Mutating the node size, the column order or the `CREATE` text makes the reader fail.
       - `DIAGNOSEADRESSE` is decimal; `NAME` is a KIS logistic name (`DME-84T1-DME`), not a job file name. F056: 78 rows, 43 addresses; `HAS_GWT=Y` only on `BDC-LR01-GATEWAY` (0x10).
       - Series map: `PSdZ/mapping/brref.xml` `mainSeries/series`. Requested series → KIS main series: F056→F056 (F48 is in F056), F020→F020, F030→F020, F015→F025, F025→F025, G020→S18A, G005→S18A, G030→S15A, G001→S15A. None absent. There is no separate F030/F015/G0xx KIS database.
       - GRP→PRG candidates: `Ecu/t_grtb.prg` table `ZUORDNUNGSTABELLEUDS(ADR_INDEX "AA IIIIII", SGBD, GRUPPE, BAUREIHE, STEUERGERAET, VERANTWORTUNG)`, 621 rows (one `?? ??????` terminator). Each group serves exactly one address. `BAUREIHE` is the series a row was introduced with, not where the variant is used (`KOMB25` rows say F20/F25/F80/I01/F56, yet F048 uses it), so the bundle does not filter by it.
       - Job files reference external table files by name (`T_GRTB` in groups; `T_PCOD`, `T_SCOD`, `T_MSA` in variants) and USES files. ISTA 4.29 lacks the USES files `_bfh_ext`, `_bfs_ext`, `_cas4`, `_fah_ext`, `_fas_ext` (used by `bfh_01/12`, `bfs_01/12`, `cas4_2`, `fah_01/12`, `fas_01`).
     - Bundle from `sources/ISTA_4.29.1x` (main series F020, F025, F056, S15A, S18A):
       - ECU lists: F020 119 rows/53 addresses, F025 128/67, F056 78/43, S15A 140/76, S18A 102/66.
       - Job files: every group serving a listed address (121 groups), every variant those groups can resolve to, `t_grtb`, `t_pcod`, `t_scod`, `t_msa`: 507 files, 553.1 MiB (ISTA `Ecu/` is 1.0 GB). Every bundled group resolves within the bundle. 86 variants named by `t_grtb` for these groups are not in ISTA 4.29 either.
     - Verification (scratchpad `m2/m2_check.py`, 29/29; M1 `m1/m1_check.py` still passes):
       - Manifest hashes match all 507 files; no unlisted file.
       - The owner's 19 inventory addresses (01 06 0D 10 12 18 29 2C 30 40 43 44 56 60 61 63 67 6D 78) are all in the F056 list, each with a bundled group. The F056 list has 24 more addresses: 07 0B 14 15 19 1A 1D 22 24 2D 31 32 34 35 37 3A 3F 49 50 51 5D 5E 5F 71.
       - `g_motor.grp`, `dme_bx8.prg`, `komb25.prg` resolve from the bundle and, with an empty bundle, from the user folder. The bundle wins when both have a file; the folder supplies files and series (I001) the bundle lacks.
       - Through `load_job_file` + `JobEngine.resolve_variant()` on the fake gateway with the owner's replies: bundle `g_motor.grp` → `DME_BX8`, bundle `g_kombi.grp` → `KOMB25`, folder `g_motor` → `DME_BX8`.
       - Offscreen render of the dialog: empty, rejected (`/tmp`, not saved) and valid states; the setting persists and clears.
     - Gaps:
       - The bundle is the address-complete superset for the five main series, not the variants of a specific car; per-car narrowing needs DiagDocDb data.
       - The packaged app does not yet include `ista_bundle/` (PyInstaller `--add-data` is a later packaging step).
       - Not wired into any app feature (M4).
3. **Owner trace (M3).**
   - Replay the owner's F48 EDIABAS trace through the fake gateway.
   - Compare the interpreter's results with ISTA's for identification, faults and CBS.
   - Record differences.
4. **Migration (M4).**
   - Move reads to jobs, then writes:
     - faults: `FS_LESEN` / `FS_LOESCHEN` / `IS_*`;
     - CBS: `CBS_DATEN_LESEN` / `CBS_RESET` with the arguments seen in ISTA's `ABL_GEN_AS6100_CBS_RESET` and the trace;
     - odometer and measurements: `STATUS_*`.
   - Writes keep the existing safety wrapper:
     - durable journal before send;
     - exact job result checks;
     - lockout, power acknowledgement, no replay.
   - Remove the hand-written code per feature once the trace matches.
   - **Status 2026-10-30: faults and CBS are job-backed; verified offline (no vehicle traffic).**
     Odometer and measurements (`STATUS_*`) are not migrated.
     - Code:
       - `app/ista_jobs.py` `JobBackend`: loads the identified variant's PRG (never a GRP; the app already identified the variant) from the data source and runs jobs. Each run goes through a connection view that records every request/reply, refuses telegrams to any other ECU address, and refuses any granted service whose bytes are not exactly an expected request (`JobRequestMismatch`, nothing sent). `JobRun` carries result, exchanges, error, `state()` and a source label (`ISTA job FS_LESEN (dme_bx8.prg)`). No interpreter, no data or no job file → the app path, labelled `app decoder (…reason…)`.
       - The saved ISTA folder is cached on the GUI thread (`remember_ista_folder()` at main window start and in the settings dialog). Creating `QSettings` in a CarWorker left its deletion to the GUI thread and crashed the CBS UI check.
       - Faults (`app/diagnostics.py`): `FS_LESEN`/`IS_LESEN` per identified ECU; with a job file, the file decides whether an information memory exists. Permanent memory (`19 15`) stays on the app request. Records: code (`F_ORT_NR`), status (`F_STATUSBYTE`, else byte 4 of `F_HEX_CODE`; PMA_15's `IS_LESEN` omits `F_STATUSBYTE`), ISTA state (present/stored/not confirmed), memory, English catalogue text, else `F_ORT_TEXT` labelled "German text from the ECU job file". Coverage rows and DTC rows carry the source. An interpreter failure (`JobError`) falls back to the app read; a vehicle failure keeps its state, no retry.
       - Clear All: `FS_LOESCHEN` (grant `0x14`, only `14 FF FF FF`) and `IS_LOESCHEN` (grant `0x31`, only `31 01 0F 06`). Accepted only if the exact reply (`54` / `71 01 0F 06`) and `JOB_STATUS` OKAY; `JobUncertain` → `outcome-uncertain`; re-read through the job readers. A job file without a clear job is reported, not replaced by the app request.
       - D-59 engine indicator: same `FS_LESEN` job results; detail names the source.
       - CBS read (`app/cbs.py`): owners are identified ECUs with a recovered definition or a `CBS_DATEN_LESEN` job. Mapping uses the job's own unit/validity texts (`RMMI_CBS_EINH`, `ST_UN_CBS_WERT`/`_TEXT`, `COU_RSTG_CBS_MESS_EINH`, `AVAI_CBS_EINH`, `ZIEL_YY_EINH`). Observed: v6 jobs (DSC_I1) report `RMMI_CBS_EINH` "x 10 km" even for % and day units, so the unit comes from `ST_UN_CBS_*`. Raw 12-byte record from the owner's own `62 10 01` reply (`_RESPONSE`); none or ambiguous → not resettable. Label: English from `cbs_definitions.json`, else job text; job text shown too. A job-only owner answering 11/12/31 is `not-held` (counts as read for coverage).
       - CBS reset: default policy only, `CBS_RESET "<CBS_K>;100;31"` (CBS_K from the job's `CBSKENNUNG` table; NR = item), grant `0x2E`, expected request `reset_request(item)`. Journal intent adds `execution` (job file, SHA-256, job, args, grant, expected request) before identity and exact before-record checks (`22 F150`, `22 1001`, one owner operation). Accepted needs the exact `6E 10 01` reply **and** `JOB_STATUS` OKAY **and** `JobResult.mutated`; otherwise uncertain. `JobUncertain` → uncertain. Re-read via `CBS_DATEN_LESEN` (app read only if the interpreter fails); v6 `22 1002` detail as before. Never replayed. A job file that has no identifier for the item refuses before the journal.
       - Kept on the app request path: `dsc25-plain` (DSC_25's job adds an SVK-gated sequence that also clears DSC fault memory) and `routine-6.3` (D94BX7A0 is not in ISTA 4.29).
     - Facts [observed offline]:
       - `CBS_RESET "<CBS_K>;100;31"` produced bytes identical to `reset_request(item)` for DME_BX8 Oel, KOMB25 Brfl/Sic/TUV and DSC_I1 Br_v/Br_h.
       - The owner's 18 identified F48 ECUs all have bundled PRGs with `FS_LESEN`, `IS_LESEN`, `FS_LOESCHEN`, `IS_LOESCHEN`; `CBS_DATEN_LESEN`/`CBS_RESET` only in DME_BX8, DSC_I1 and KOMB25. Job files load in 1–4 ms.
     - Verification (scratchpad `m4/m4_check.py`, 45/45; fake HSFZ gateway with the owner's 2026-10-29 F48 replies plus `mock_data/f48_x1.json` CBS records):
       - Fault scan of 18 ECUs: job records = app records (48 records incl. TCB1 `B7F325` stored, ENTRYNAV `B7F85A`/`B7F8C3` present, the `22 2000` information records); identical wire requests (38); identical coverage and completeness. Unknown code → German job text labelled.
       - Engine indicator: job = app on the owner replies (off); synthetic present+confirmed → on; rejected → unavailable.
       - CBS: job items = app items on all decoded fields, raw and resettable (5 items, 3 owners); sentinel/unit edge records for v5 and v6 equal; a rejecting owner blocks resets; duplicate item → no raw.
       - Reset: wire = `22 F150`, `22 1001`, `2E 1001 01 01 64 1F 80 00 0F FF 0F 3F FF 00`, `22 1001`; verified; journal events and execution recorded; app fallback sends identical bytes; read-only, changed before-record, ECU rejection, wrong echo, silent write (uncertain, connection closed), non-OKAY job status (uncertain), a job write differing from the journal (refused unsent), no item identifier (refused before journal), replay refused.
       - Clear: per-target outcomes, only `14 FF FF FF`/`31 01 0F 06` sent, app fallback sends the same sequence, read-only `policy-blocked` with nothing sent, silent clear → `outcome-uncertain` and no further sends.
       - Fallbacks: interpreter missing and no job data → app path, labelled, same results.
       - Telegram to another ECU address refused unsent.
       - Offscreen render of the CBS panel and the Diagnostics page from job results.
       - Mutation probes (each reverted): dropping the expected-write restriction, the address check, the km scaling, the clear reply check or the reset job-status check each make a check fail.
       - Existing checks still pass: `cbs_check`, `cbs_branch_check`, `diag_variant_check`, `cbs_ui_check`, `engine_ui_check`, `odometer_check`, `quarantine_check`, M1 37/37, M2 29/29. They now run the job path where the bundle has the file. `cbs_ui_check` was changed to collect its abandoned DEMO window on the GUI thread (see gaps).
     - Gaps:
       - Not validated on the car; M3 (owner EDIABAS trace) is still pending, so the hand-written readers/writers remain as the fallback rather than being removed.
       - GC from a CarWorker thread: when Python's cyclic GC runs in a worker thread and collects Python-owned Qt wrappers, PySide deletes them via the GUI thread and can crash. Reproduced at the previous HEAD (5425bff) by one `gc.collect()` inside the CBS read worker in `cbs_ui_check`. Job runs allocate more in workers, so the GC runs there more often. Proposed follow-up (not done): run the cyclic GC only on the GUI thread (`gc.disable()` plus a GUI-thread timer).
       - Odometer/measurements (`STATUS_*`) are still app-decoded.
       - Interpreter gaps from M1 apply: replies over ~250 data bytes (e.g. more than ~60 DTCs) abort the job, and the read then falls back to the app request.
       - The load-bearing check of a job write is the exact-bytes restriction. Write jobs that send several different writes (DSC_25 extra sequence, coding) need a per-job expected-request list first.
5. **Features (M5).**
   - Fault details (`FS_LESEN_DETAIL`).
   - Live values from each job file's result tables.
   - Selected service functions rebuilt from their job calls (for example battery registration).
   - Coding: D-64's deferral was revised by D-66 and then D-67 (learn-by-diff
     rejected). Easy source path (not taken by Claude; left for another coder):
     BimmerCode `coding_data/*.enc` or ISTA CAFD → a named preset catalogue. See
     [../docs/claude-session-limitations.md](../docs/claude-session-limitations.md).

## Waiting on the owner

- `DiagDocDb.sqlite` from the working ISTA 4.29 machine. The copy now in `sources/ISTA_4.29.1x/Rheingold/SQLiteDBs/` (5.9 GB) has no SQLite header and does not open ("file is not a database"); it appears encrypted.
- An EDIABAS `ApiTrace=3`/`IfhTrace=3` trace of ISTA identifying the F48, reading faults and opening the CBS screen (no resets).
