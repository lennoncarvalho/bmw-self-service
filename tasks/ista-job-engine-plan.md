# ISTA job engine — plan (D-60–D-64)

2026-10-30. Branch `codex/task-b-cbs-mil`. Decisions: [doc 21](../docs/21-product-decisions.md)
D-60–D-64. Evidence: [ISTA 4.29 architecture](../docs/evidence/ista-4.29-architecture.md),
[online research](../docs/evidence/ista-online-research.md).

## Boundaries

- **Scope:** ISTA 4.29 coverage only, over HSFZ. Personal use.
- **Protection:**
  - Encrypted CAFD/fafp files are not decrypted.
  - ISTA keys and licence material are not extracted or used.
  - DiagDocDb is used only if it is plain SQLite.
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
