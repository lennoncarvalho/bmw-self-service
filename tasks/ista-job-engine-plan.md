# ISTA job engine — plan (D-60–D-64)

2026-10-30. Branch `codex/task-b-cbs-mil`. Decisions: [doc 21](../docs/21-product-decisions.md)
D-60–D-64. Evidence: [ISTA 4.29 architecture](../docs/evidence/ista-4.29-architecture.md),
[online research](../docs/evidence/ista-online-research.md).

## Boundaries

- **Scope:** ISTA 4.29 coverage only, over HSFZ. Personal use.
- **Data status:** CAFD/fafp are encrypted and unused so far; DiagDocDb is pending
  from the owner.
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
5. **Features (M5).**
   - Fault details (`FS_LESEN_DETAIL`).
   - Live values from each job file's result tables.
   - Selected service functions rebuilt from their job calls (for example battery registration).
   - Coding stays deferred (D-64).

## Waiting on the owner

- `DiagDocDb.sqlite` from the working ISTA 4.29 machine.
- An EDIABAS `ApiTrace=3`/`IfhTrace=3` trace of ISTA identifying the F48, reading faults and opening the CBS screen (no resets).
