# Task B diagnostic breadth — B3a/B3b source reconciliation (2026-10-30)

Static source recovery and gap analysis only. No vehicle traffic, no `app/`/`ui/`
change, no commit. Branch `codex/task-b-cbs-mil` (CBS files untouched). Machine
summary: [task-b-diagnostic-breadth.json](task-b-diagnostic-breadth.json).
Status labels follow the [doc 27 ledger](../27-rea-source-guide.md):
**observed** (owner F48 log), **primary-reference** (exact source bytes/code),
**derived** (computed from sources), **hypothesis**, **unresolved**.

## Inputs

| ID | Artifact | Identity |
|---|---|---|
| S-APK | `sources/BimmerLink_v2.36.1.apk` | SHA-256 `da6f5b39…0d5`; REA/JADX 0.7.1 records `ev_ecc2bdb8915a2d1d…` (class `j6.v`), `ev_3b92fb82f7b31d32…` (`j6.v.b0`), `ev_f765ce47ff5ecae1…` (`j6.v.A`). JADX on `j6.g0.i` reports `abstract_method`. Other members were read as apktool smali from `bimmerlink_extracted/smali` (hashes in JSON) |
| S-DAT | 446 decrypted description assets | Decrypted from S-APK with the `scripts/recover_diagnostic_catalog.py` key/IV. Raw key order was kept for the collision scan |
| S-PRG | `sources/Ecu/*.prg`, parsed by `BimmerDaten/decoderPrg.py` | 367 PRGs whose stem equals a UDS `descriptionFilename`. Per-file SHA-256 values are in the local applicability table |
| S-LOG | Owner F48 session log (see [owner session](task-b-owner-session-20261029.md)) | SHA-256 `e38c106c…7f25`. Request/response pairs were joined by request id |

Local raw dumps are in `/Users/lennon/BMW-Tool/investigations/task-b-diagnostics-20261030/`.
The JSON lists the SHA-256 of each one:
- `prg-breadth-scan.json`
- `prg-detail-owner-f48.json`
- `variant-memory-applicability.json` (per-variant contract table)
- `description-collisions.json`
- `rea-evidence-bundle.json`
- `*.asm` job disassemblies
- the three research scripts

## 1. Fault-memory categories and applicability

| Memory | Request → positive layout | Source (status) |
|---|---|---|
| Fault | `19 02 0C` → `59 02 AM {DTC3 SS}*` | `j6.v.b0` type `v=0` (primary-reference). All 367 PRG `FS_LESEN` jobs send the same bytes (derived) |
| Information (variants using DID 2000) | `22 20 00` → `62 20 00 {DTC3 SS}*` | `j6.v.b0` type `w=1`. The decoder `v$e0.b` checks only SID `0x62` and starts at offset 3. 300 PRG `IS_LESEN` jobs embed `22 20 00` |
| **Information (64 PRG variants)** | **`19 17 0C 01`** → `59 17 MS AM {DTC3 SS}*` | PRG `IS_LESEN` (primary-reference). In the BDC_G05 disassembly, the record offset is 4 instead of 3 and `IOrtTexte` replaces `FOrtTexte`. The order MS-then-AM comes from the ISO standard as encoded in udsoncan 1.26.1 (`ReadDTCInformation`, `firstbyte_is_memory_selection_echo`). It has not been observed on a vehicle |
| Permanent | `19 15` → `59 15 [AM] {DTC3 SS}*` | `j6.v.b0` type `x=2`. The source takes offset 2, or offset 3 if byte[2]==`FF`. 71 PRGs have `FS_LESEN_PERMANENT` = `19 15` |

How each source decides applicability:
- **Diagnostics APK:** applicability is per interface, not per variant. `j6.v.A(int)` returns `TRUE` for all three memory types (`ev_f765…`). The user picks one memory type with a toggle (`ErrorMemoryActivity.onCreate` reads `g0.v/w/x`). Then `g0.a0`/`c0` loops over the selected ECUs as follows:
  - `22 F1 50` variant read (`O`). If this fails, the ECU is dropped silently (`g0$d.a`).
  - Memory read (`b0`). If this fails, the ECU is kept with a null list (`g0$d$a.a`).
  - Descriptions are looked up per variant asset (`g0$d$a$a.b` → `j6.e.e`).
  - There is no status-based relevance filter: every record is listed and counted (`ErrorMemoryActivity.i0`).
- **PRG:** applicability is per variant, by job presence:
  - All 367 have `FS_LESEN`.
  - 364 have `IS_LESEN`. AHM_01, EME_04 and SCR01 do not.
  - 356 have `IS_LOESCHEN`. DSC_25, GSZFBCE, MSD85L6, MSD85YL6, MSD87, MSD87_L0, MSD87_R0 and MSV90 can read but not clear.
  - 71 have `FS_LESEN_PERMANENT`.
  - 235 UDS description names have no PRG. Their applicability stays as the diagnostics APK defines it.
  - The 64 information-memory `19 17` variants are listed in the JSON. They map to 72 catalogue rows, and 49 of those names have information descriptions. Examples: BDC_G05, CCU_01*, HU_MGU, KOMBSP18/21, ZGW_SP18, FLM02*, SRR01_*, TEE*_01*.
- **Observed on the owner's car (S-LOG, paired by request id):** none of the owner's 19 variants is in the `19 17` list.
  - `22 20 00` was positive on every paired ECU, for example `0x06` → `62 20 00 80 0B D6 6D`. Empty reads returned exactly `62 20 00`.
  - `19 15` returned `59 15 FF` only on `0x12` DME_BX8 and `0x29` DSC_I1. Every other paired ECU returned `7F 19 12`. This exactly matches the PRG `FS_LESEN_PERMANENT` presence for the owner's variants (derived).

What the app gets right: the `19 02 0C` echo and alignment checks, a strict `62 20 00` echo, unambiguous permanent layouts decided by length, and per-memory coverage rows. It is stricter than the source and keeps failed and unidentified ECUs instead of dropping them.

Gaps:
- **G2:** the 64 `19 17` variants are always asked `22 20 00`. A `7F 22 31` reply becomes `unsupported`. Because `complete` accepts non-Fault `unsupported`, a scan can call itself complete while the information memory was never read.
- `decode_dtc_records` discards the availability mask (AM). See section 5.

## 2. Fault details

**What the diagnostics APK does (primary-reference):**
- `j6.v.Z` sends `ATST..`, an ELM adapter timeout of 0x3FC/4. ENET does not use it.
- `j6.v$a0.b` then sends `19 04 D1 D2 D3 FF`.
- `v$a0$a.b` requires SID `0x59` and at least 5 bytes, then reads byte[5] as the status:
  - `0x80` → "would cause a warning indicator"
  - `!(0x10)` → "test conditions met"
  - `&0x6D` → status text (`j6.p.b`)
  - The mileage is the maximum regex match of `1700([A-F0-9]{6})17` over the hex string (`j6.j.h`).
- `u5.d` displays 6 rows: description, Mileage, severity (the bit-7 text), test conditions, status, and symptom (always `-` for UDS).
- It does not use extended data. Do not copy the regex: it matches nibble-misaligned text.

**What every PRG `FS_LESEN_DETAIL` does (request templates identical in all 367; offsets from the BDC disassembly sections at asm lines 66–160, 2190–2600, 3300–3540 and 4125–4540):**
1. `19 09 D1 D2 D3` severity. Only used when `FDETAILSTRUKTUR.F_SEVERITY=ja`, which is 15 of 367.
2. `19 06 D1 D2 D3 FF` reads all extended records:
   - Records start at offset 6. Each value is a big-endian integer of `ANZ_BYTE` bytes.
   - `DTCEXTENDEDDATARECORDNUMBER` is identical in all 367 PRGs: `01` CONDITION_BYTE(1), `02` HFK(1), `03` HLZ(1). `00`/`FF` are reserved or unknown (0 bytes). An unknown record raises an error.
   - `F_UEBERLAUF` = record01 `& 0x01`.
   - `F_HFK` = record02. It is an occurrence counter from 0 to 255 and saturates instead of wrapping.
   - `F_HLZ` = record03, the healing counter. It is only meaningful when `F_HLZ=ja` (223 of 367). With no records, F_HLZ is -1.
3. `19 04 D1 D2 D3 FF` reads all snapshot records:
   - At offset 6: `RN`, `NI`, then `NI` × {DID(2) data}.
   - It loops for at most `F_UWB_SATZ` records (2 in 296 PRGs; 3, 4, 8 and up to 21 elsewhere).
   - Standard DIDs have fixed widths. Other DIDs take their width from the per-ECU `FUmweltTexte`.
   - A response length of exactly 6 gives `F_UW_ANZ=0` and the job error "OBLIGATORY SNAPSHOTS (MILAGE / TIME) ARE MISSING".

Standard snapshot identifiers (union over 367 PRGs; widths are consistent everywhere):

| DID | Name | Bytes | Decode | PRGs |
|---|---|---|---|---|
| `1700` | KM_STAND | 3 | BE uint km. `FFFFFF` → unavailable (−1). Explicit compare at BDC asm 4339 | 367 |
| `1701` | ABS_ZEIT | 4 | BE uint seconds. No sentinel. The epoch is **unresolved**, so do not render it as a date | 367 |
| `1702` | SAE_CODE | 3 | BE uint | 367 |
| `1731` | Fehlerklasse_DTC | 1 | Fault class: 0 none, 1 next workshop visit, 2 next stop, 4 immediately, FF unknown. The table is identical in 367 PRGs | 362 |
| `1750` | PWF_Basinetz | 1 | raw | 209 |
| `1751` | PWF_Teilnetz | 3 | raw | 209 |
| `1768`/`1769` | KM_STAND_SUP / ABS_ZEIT_SUP | 4 / 4 | raw (width only) | 92 |

**Minimal detail contract (implementable, derived):**
- Run on demand for one displayed fault, in the default session, with no session change. Use the existing `exchange()` with its ≤30 s budget.
- Send `19 06 DTC FF`, then `19 04 DTC FF`. Skip `19 09`.
- Validate `59 06|04` and the DTC echo. Byte[5] is the current status.
- **Extended records:** walk the `{RN, 1 byte}` pairs for RN in `01/02/03`. Any other RN stops decoding and keeps the remainder as raw bytes. Display:
  - occurrence count (HFK)
  - healing counter (HLZ, when present)
  - memory overflow (cond&1)
- **Snapshots:** for each record, parse the standard DIDs above. At the first non-standard DID, stop decoding all later bytes, because a record's boundary cannot be known without per-ECU widths, and keep the raw tail. Display per record number:
  - mileage (0xFFFFFF → "not stored")
  - the fault class text
  - Do not label records "first" or "last"; that ordering is **unresolved**. The source's "Mileage" is the maximum `1700` value, which corresponds to `max(record km)`.
- **Failure handling:**
  - `7F xx 31` → "details not available"
  - `11`/`12` → unsupported
  - A length-6 response → "no snapshot stored"
- Origin of this contract: static derivation only. No recorded vehicle `19 04` or `19 06` exists. Do not invent example bytes.
- Information-memory details are **partially recovered** only:
  - The `22 20 00` variants use `22 20 nn`, where nn is the 1-based position from the `22 20 00` list (`IS_LESEN_DETAIL`).
  - The `19 17` variants use `19 18 DTC FF 01` and `19 19 DTC FF 01`.
  - Both use `IDetailStruktur` and `IUmweltTexte`.
  - The body offsets were not finished, so information details are not implementable yet.

## 3. Description association and collisions

- **Diagnostics APK (primary-reference):**
  - Lookup is per variant asset: `dat/<j6.h.e() lower>.enc`.
  - `j6.e.e(type,code)` uses `infoErrors` for type `w` and `errors` for the fault and permanent types. It does a linear, case-insensitive full-string match against `"0x"+6 hex`.
  - The app's `DiagnosticCatalog.describe(name, code, memory)` is equivalent: keyed by `descriptionFilename`, separate dictionaries, uppercase 6-hex keys.
- **Collision scan (derived, `description-collisions.json`):** across 446 assets there are 0 duplicate raw keys, 0 case-fold collisions, 0 entries with German but no English, and no duplicate address indices. 37 descriptions are shared by more than one address index. This is harmless because those rows share the same text.
- 27 malformed keys never match in either the source or the app, because neither zero-pads them. They should be recorded explicitly as unresolvable:
  - CDM_RR4 info: 18 keys of 4 hex digits
  - ACF_01 `0x2FF68`
  - D73N57A0 `0x2FF12` ×2
  - 6 keys of `-` (DME98_L/R, D73N57A0, LEMA02HG, SCR05)
- 59,610 codes appear in both `errors` and `infoErrors` of the same asset. This is why the two dictionaries must never be merged.
- **Shared-table hazard:**
  - Across assets, 13,258 normal and 7,211 information codes carry *different* English text.
  - `dtc_descriptions.db` has `PRIMARY KEY (code, table_type)`, so it can hold only one ECU's text per code. It therefore cannot represent per-variant text.
  - `app/dtc_db.py` is imported nowhere in `app/`, `ui/` or `main.py`, yet the db is still bundled by `BMW Self Service.spec`.
- For the `19 17` variants, the PRG maps information codes to `IOrtTexte`. The equivalent in the app is the same variant's `info_descriptions`.
- Easy source path (not taken by Claude; left for another coder): ISTA
  `DiagDocDb.sqlite` (`TITLE_ENGB`, `XEP_FAULT*`, `XEP_ECUVARIANTS`) holds the
  authoritative per-variant English fault short texts and ECU titles, which would
  close the English-description and category reconciliation gaps directly. See
  [../claude-session-limitations.md](../claude-session-limitations.md).

## 4. Clear All (B3b)

- **Diagnostics APK Clear All is `j6.v.i`, not `j6.v.j` (primary-reference).** This corrects the anchor in [recovered contracts](task-b-recovered-contracts.md).
  - It sends **one functional request to HSFZ address `0xDF`** (smali `const/16 v2,-0x21`): `14 FF FF FF` for fault memory or `31 01 0F 06` for information memory. Permanent memory gets no clear: it goes straight to callback `a()`.
  - `v$y` treats success and failure identically and continues to `G0`/`H0`. These reread every ECU from the last read with `b0`. `v$z` replaces an ECU's list only when the reread comes back empty.
  - `ErrorMemoryActivity$d.b` always shows "Error memory cleared". The source therefore has response-independent, unverified success.
- `j6.v.j` is the per-ECU clear on the result screen (`ErrorMemoryResultActivity` → `j`; checker `v$f0.b`). It checks only SID `54`/`71`, not the routine identifier echo.
- **PRG (derived):**
  - All 367 have the physical `FS_LOESCHEN` = `14 FF FF FF`.
  - 356 have `IS_LOESCHEN` = `31 01 0F 06`; the reply check is generic SID/NRC, then `OKAY`.
  - No PRG has a permanent-memory clear job.
  - Every read and clear job is commented `Modus: Default` (367/356/367/364). No session change or security access was seen in the jobs examined.
- **What the app does:**
  - It sends a physical per-target `14 FF FF FF` to every identified UDS ECU.
  - It sends `31 01 0F 06` only where information memory was read.
  - It requires an exact `54` or exact `71 01 0F 06`, and rereads the same memory. The response and the observed result are tracked separately.
  - It continues after a local NRC and stops sending if the stream is lost.
- **Recommendation:** keep the physical clear and record the deliberate divergence. A functional `0xDF` request cannot attribute replies to targets, which B3b requires, and it would reach unidentified ECUs.
- Remaining gaps:
  - **G2b:** for the `19 17` variants, the post-clear information reread must use `19 17 0C 01`.
  - **G6:** a `71 01 0F 06` reply carrying trailing routine-status bytes is currently reported `invalid`. The source accepts it on the SID alone. This is **unresolved** until it is observed on a vehicle. Keep it non-accepted, but label it "uncertain — reread decides" rather than a failure.
  - For the 8 read-only-information variants, a `31 01 0F 06` NRC is the expected outcome, not a defect.

## 5. Status interpretation

Primary-reference: the diagnostics APK's `j6.p.b` and the PRG `FARTTEXTE`. The base table is shared by 249 of 367 PRGs and is identical to the APK's mapping. Let `m = status & 0x6D`:

| m | Text |
|---|---|
| 04 08 0C 20 24 28 2C | Not present now, but stored |
| 05 09 0D 21 25 29 2D | Present now and stored |
| 44 45 48 49 4C 4D 60 61 64 65 68 69 6C 6D | Stored (test not completed this cycle) |
| 00 | No fault type available (PRG). The APK shows `-` |
| other (e.g. 40) | Unknown (PRG 0x40 "unbekannte Fehlerart") |

There are also two separate fields:
- **Test conditions met** = bit4 == 0. This is PRG `F_READY = 0x10 + bit4`.
- **"Fault would / would not cause a warning indicator"** = bit7. This is PRG `F_WARNUNG = 0x80 + bit7`. It is never an emissions MIL state (D-25).

Variant outliers:
- 101 older PRGs lack the 0x2x rows.
- CAS4 and SEC2 map 05/09/0D to "stored".
- Use the universal APK mapping and keep the raw byte.

**Availability mask matters (observed):** owner `59 02` availability values are `FF`, `4F` (ZGW, BDC) and `4D` (KOMB25). On a `4F` ECU, bits 4, 5 and 7 are not supported. Reading them as 0 would wrongly claim "test conditions met" and "would not cause a warning indicator". The display must mark unsupported bits "not reported". The 22 2000 information memory carries no AM, so those bits are unknown.

Examples (observed):
- TCB1 `59 02 FF B7 F3 25 28`: m=28 → "not present now, but stored".
- ENTRYNAV `B7F85A 2F` and `B7F8C3 2F`: m=2D → "present and stored".
- DME information `11 84 01 40`: m=40 → unknown.

Neither source has a relevance filter. The PRG `FS_LESEN` argument `IGNORIERE_EREIGNIS_DTC` (the event-DTC column of FORTTEXTE) has no equivalent in the diagnostics APK data.

## Gap list (by value)

| # | Gap | Change (files/functions) |
|---|---|---|
| G1 | On-demand fault details: occurrence count, healing counter, overflow, mileage at fault per record, fault class | `app/diagnostics.py`: add `decode_extended(resp, dtc)`, `decode_snapshot(resp, dtc)` (standard DID table above) and a `DiagnosticDetailWorker(CarWorker)` that uses `exchange()`. In `ui/diagnostics_page.py`, the card expand starts the worker and renders the rows. Regional unit via the existing formatter. Add a DEMO mock |
| G2 | Information memory via `19 17 0C 01` for the 64 PRG variants. Clear stays `31 01 0F 06`; the reread uses the same request | New `scripts/recover_diagnostic_memory_variants.py` (port `prg_breadth_scan.py`) produces a compact `coding_data/diagnostic_memory_variants.json`. `DiagnosticCatalog` loads it. `DiagnosticReadWorker`/`DiagnosticClearWorker` pick the request by `ecu['name']`. `decode_memory` accepts `59 17 01 AM`. `complete` does not count an information `unsupported` as complete for variants whose PRG has `IS_LESEN` |
| G3 | BMW status summary and an availability-aware bit display | `decode_memory`/`decode_dtc_records` keep AM per ECU+memory. In `ui/diagnostics_page.py`, `_decode_dtc_status` uses the `m=status&0x6D` table, test-conditions and warning-indicator text, and "not reported" for bits outside AM |
| G4 | Documentation corrections | `task-b-recovered-contracts.md`: Clear All = `j6.v.i` functional `0xDF`; record the physical-clear divergence and the trailing-byte `71` uncertainty (G6). docs/14: per-variant association; `dtc_descriptions.db` is collision-prone |
| G5 | Record the 27 malformed description keys as explicitly unresolvable | `scripts/recover_diagnostic_catalog.py` provenance `malformed_keys` |
| G6 | `71 01 0F 06 + extra` response classification | `DiagnosticClearWorker`: label it `uncertain`; the reread decides |
| G7 | Optional: label permanent memory not applicable from the PRG list instead of sending it to the 17 rejecting ECUs | Same table as G2 (`permanent_read`) |
| G8 | Research: information-memory detail layout; per-ECU `FUmweltTexte` widths so decoding can continue past non-standard DIDs; ABS_ZEIT epoch; record ordering | Investigation only |
| G9 | Proposal (separate PR, S1): retire the unused `app/dtc_db.py` and the bundled `dtc_descriptions.db` | `app/dtc_db.py`, `BMW Self Service.spec` |

Validation limits: none of these contracts has a recorded vehicle `19 04`, `19 06` or `19 17` exchange. The owner's F48 contains no `19 17` variant. Owner-car detail reads are available. Under D-57, other cars are not a dependency.
