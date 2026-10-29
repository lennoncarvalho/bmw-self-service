# Task B recovered contracts and current implementation boundary

2026-10-29. Branch `codex/task-b-feature-recovery`. This is a partially implemented
Task B; it is **not feature-complete or vehicle-accepted**. Owner-directed REA
reconstruction remains the fundamental implementation rule in `AGENTS.md`.

## Inputs and retained evidence

- Diagnostics APK 2.36.1-6731: SHA-256
  `da6f5b39efaa590fce68782f439c1b8f1b9f09ed41344055b8ff80666cae00d5`.
  Native `lib/x86_64/libexternal.so` SHA-256
  `4fa35fb97573dadbebcf084e4c3318a6ea0d0e5a4f524756e376c29224cfaacb`.
  REA/JADX 0.7.1 and Ghidra 12.1.4; native c/d at `0x1009d0`/`0x1009f0`
  recover the data key/IV. This decrypts packaged assets, not ECU authorization.
- Coding APK 4.25.04-12743: use the full hash in
  [the original inventory](local-artifact-inventory.json). Exact Android member
  observations below are retained in local REA bundles with their original identity.
- SHM Lite/Free `SHM.exe`: SHA-256
  `2d6bb52808f1754ac9334958530c5b2c60ec373fa35b674f28bdb34dc93cf92a`.
  REA identifies native x86/Delphi, with no CLI metadata. Do not use a .NET route.

Local research evidence (not shipped application dependencies):

| File under `/Users/lennon/BMW-Tool/investigations/` | Contents |
|---|---|
| `task-b-diagnostics-retained-records.json` | 26 complete inline native/Android records; SHA `9988a3eb7a30a3df8871923f7c7d11ee6f509e6c748f3bab9de97fe716e75b57` |
| `task-b-diagnostics-final-evidence.json` | Later description/memory selection records; SHA `267ca296a4483a38436cb5694c35b6139e2f6eeee41f83ec0c12c9f9a3a9c44f` |
| `task-b-coding-read-review-evidence.json` | 28 coding selection/group-read records; SHA `bd91fa61a16cc62dd44cd347d17f185bfb7fa96c05c02b7b51428896079c7b10` |
| `task-b-shm-read-action.json` | Native SHM read-action bytes and retained observations; export contains 12 records |

Full bundle digests for additional current observations are recorded in the
verification record. REA close clears session records: earlier exports and the
retained inline objects are preserved rather than assuming IDs survive a restart.
Ghidra did not identify the Delphi event method as a procedure; its attempted
pseudocode failed. The native conclusion below is from REA-observed mapped bytes,
RTTI/resource coordinates and local `objdump` decoding, not invented decompilation.

## Recovered operations enabled in code

These are **primary implementation references**, with offline replay checks.
None establishes new physical vehicle acceptance.

| Operation | Source location / Evidence | Contract and implementation |
|---|---|---|
| Inventory | `j6.v.Y`, `v$g0.b`, `v$g0$a.b`; `ev_133448555e0ef7de8c53c0b7cfef51afed2fabab17dd1f263c6a15c0bec75525`, `ev_9c3b13cafe4caa0ebca928c9feeeb2b0477785700758d76d708adc7af11df560`, `ev_ee80e75c099fddf1e522ad23a588e26f1041f9d5587f25d1b0f76d16918b3298` | HSFZ gateway `0x10`, `22 3F 07`; `62 3F 07` + BE16 byte count + one-byte addresses. Y changes adapter timeout, not UDS session. `app/vehicle.py` validates count/duplicates and retains each failed/unidentified target. No F000/XML/name heuristic. |
| Variant | `j6.v.O`, `v$d0.b`, `j6.h.f`; `ev_152b77d785ba9e8f41a45827c6c992a7180fd1664444630b497e0a3763823c95`, `ev_75be6daefed929284a25afdf141cc5502096ec4fdd3f7a1b00d94cfb974d0cc3` | `22 F1 50`; first three data bytes are hex, not text. Exact lookup `address + variant`, no name-prefix or directory-first matching. All 1,307 records retained, including non-UDS rows explicitly unsupported by this UDS path. |
| Normal faults | `j6.v.b0` and `v$e0.b` | `19 02 0C`, pending OR confirmed. `59 02 availability` then four-byte records `[DTC3,status1]`. No gratuitous session change. Complete alignment and echo checked; standard records decoded by udsoncan. |
| Information faults | Same source, information-memory branch | `22 20 00`; exact `62 20 00` then four-byte records. Separate information-description dictionary. |
| Permanent faults | Same source, permanent-memory branch | `19 15`; source legacy `59 15 + 4n`, and standard `59 15 availability + 4n`. Length disambiguates instead of the source's first-code-byte heuristic. Permanent memory has no clear action. |
| Clear All | `j6.v.j`, `v$f0.b`, `v$f0$a.b` | Normal `14 FF FF FF` / `54`; information `31 01 0F 06` / checked `71 01 0F 06`. Per-target response and post-read state stay separate. Unknown routine-result extensions are not called accepted. Only observed-empty memory establishes that the addressed memory is empty; recurrence stays visible. Local rejection allows later targets; lost/uncertain streams do not. No saved clear report/backup. |
| VIN alternative | `j6.v.f0`, `v$k.b`; `ev_f221b43a7381abffe697db70d6056042bc1ed665ffa9e6d536b0836781941ccc`, `ev_687f8c25493b3d9395c3045ba78cfda748a2f2dbc2aa63f4e43be7bcce46db3b` | HSFZ body controller `0x40`, `22 F1 90`, 17 characters, not all zero. Retained gateway VIN path remains first. Alternate only after definite rejection, never after transport ambiguity. Discovery identity mismatch blocks connection. |
| Integration levels | Coding `s0.s`, `s0$c.b`, `s0.R`; `ev_3f6732f497b424a19899f2ec9f3db32ec3a33c74503f379db3fec8b9cfe9616b`, `ev_ec9325446cb746ba61b41cad09636b9362160d8cc23d844faa2633d2a452ffac` | Gateway `22 10 0B`; three eight-byte entries, four-character family, year/month bytes, BE16 integration version. Replaces F18A-as-I-level guess. |
| Voltage | Coding `s0.S`, `s0$e.b`; `ev_5a525e7127b8343bb7c35a67babfa4c45e7882f4fa9b794d47b2a734f28ff04c`, `ev_4d606a60546bd2988d66c215080a9e051df7763acc984529fea09bb0bcd16cba` | DME `0x12`, `22 40 2B`, exact 31-byte positive PDU; BE16 at PDU[5:7] × 0.00025 + 6 V. No invented battery threshold or F40C decoder. |
| Coding snapshot | Coding `s0.U`, `s0$f.b`, `h0.b`, `q.e`, `y.a`, `codingtasks.d.c`, `p.n`, `p$a.b`; `ev_524cef66939840f3e6ff6c2d24fbc1dd96fee8e8d065f4419c0f6ef079aee26e`, `ev_591b2c17727376bcbbf66a7903bccedd5f49d67b7b76ea492c6e9d3f060d2e78`, `ev_b06e2e2055d25d919da5a5127ec1f5772a24c5cd949f94b70a2ff0c274a90b81` | `22 F1 01`, count at PDU[6], trailing eight-byte records. Role5 = CAFD, role6 = bootloader. ID4 + version3 matches an exact local definition filename. All declared groups supply DID addresses; each read is `22 DID`. Preserve opaque data bytes, reread F101 before saving. Partial/missing definitions do not make a complete snapshot. This is not restore permission or an implemented easy preset. |

The recovered inventory/optional-info path uses **one-byte HSFZ addresses**.
DoIP discovery/routing/VIN retain Task A's standard implementation and full-width
entity address, but source-specific ECU-inventory/address translation remains
open. The HSFZ feature mapping is not silently applied to a DoIP logical address.
This restriction records a research gap; it does not narrow Task B's required
F/G/U/I goal or assert a chassis-specific transport.

Per memory/group request budgets are at most 30 seconds including queueing.
Diagnostics, Clear All and coding snapshots have five-minute absolute batch
budgets, with remaining work explicitly unattempted when exhausted. Dashboard
post-connect tasks retain their 30-second shared task deadlines. Lazy page
loading publishes each initial batch only after settlement. Definite optional
read failures preserve connection; a tainted stream still closes.

## Reproducible description data

[Member provenance and explicit missing assets](task-b-diagnostic-catalog.json)
records every input hash. `scripts/recover_diagnostic_catalog.py` checks the
original APK digest, decrypts data, separates normal/information English entries,
and reproduces `coding_data/diagnostic_catalog.json.gz` deterministically.

- 1,307 exact address-index rows; 691 UDS rows.
- 446 available UDS description assets.
- 138,721 normal + 87,094 information English entries = 225,815.
- 156 unique referenced UDS description assets are absent from this APK.
- None of the present mapped error/info entries lacked English. Missing assets
  and unknown DTCs display an English unavailable state and keep their codes.
- Permanent descriptions use normal errors, matching `j6.e.e`; information
  uses `infoErrors`. Do not mix these dictionaries or the old PRG table types.

## Durable file foundation

`app/operation_store.py` writes version1 ordinary JSON with separate original
baseline/intended bytes, exact identities, original hash, ordered events and whole
record hash. Temp-file fsync → atomic replace → directory fsync happens before
preparation returns. Every original is retained until explicit user deletion.
Imports/exports validate schema/size/integrity and cannot send vehicle requests.
Old metadata-only manifests remain preview-only, never rollback material.

Observation/response containers are opaque: feature recovery must independently
validate exact compatibility and completion semantics before interpreting an
imported `verified`/`recovered` event. There is no vehicle restore action yet.
Read-only coding snapshots explicitly say no write occurred and restoration is
not available. The foundational state vocabulary supports D-29's eventual
response-confirmed/cycle-required distinction without claiming it is wired to
history/coding writes.

## SHM history-read blocker: direct native evidence

The supplied Lite executable's Delphi method table names
`TFMain.hdrcntrl1SectionClick` at VA `0x628d28` (method metadata file offsets
`0x227603` and `0x22771f`). The six-item header menu's resource caption at file
`0x35d996` is “Read from car” (index3).

REA `read_bytes` records:

- `ev_08a43ba1b3de1961e9a5eb6849cb61dfa4ae05c13cd284efa5ce066d2d5f6018`:
  method code at `0x628d28`, including six-entry jump table.
- `ev_4d24e2cab2c3cb9619e4101a5590079467c8922c1836e407d38d76b6488cdbbf`:
  table at `0x628d55`; case3 points to `0x628e1d`.
- `ev_2c534f3187c3274d0d1f59c277b383903e83e4c81c5ee0812e57600051c5db22`:
  Delphi UTF16 string at `0x628f1c`, “Only in PRO version”.

Local objdump independently decodes case3 as loading that string, calling the
message helper, then returning to event cleanup. The supplied help PDF separately
states that vehicle history reads are Pro-only. This exact Lite read action does
not contain the needed vehicle read flow. This is a specific bounded conclusion,
not proof that no diagnostic history-read method could exist elsewhere.

All four supplied CIC/NBT/NBTEVO/MGU PRG job inventories were parsed with the
existing BEST parser: history ADD/ERASE appear; no history read job was recovered.
NBT's SERVICEHISTORY table describes business results (0 okay,1 memory,2 data
inconsistency,4 no permission,5 unknown), not a history readback format. The
`.bmwsh` example remains local serialization and cannot establish original car
history or permission to erase it. A Pro artifact, matching captured read flow,
or another source containing this operation is needed to finish history backup
and preserving append. Do not enable destructive rewriting from the Lite path.

## Remaining work keeps Task B open

- Genuine history read and complete preservation, add/restore encoder, exact
  write result and ignition/reconnection semantics.
- Complete applicable easy preset selection and writes, composed blocks,
  authorization/signature handling, power prerequisites and checked restoration.
  Type1 roots are **dynamic angel-eyes options**, not malformed empty presets:
  source EcuActivity.Q0 → AngelEyesBrightnessCodingOptionActivity/a0 chooses
  functions from current DRL module/DRL_Idx/POLI matrices. Type0 also needs all
  applicability predicates (ID8, series, excluded variants, definition functions).
- Real emissions MIL endpoint/decoder: a bounded sensor search found no genuine
  MIL read; a warning-indicator-requested fault bit is insufficient.
- DoIP inventory/address mapping, remaining optional vehicle information,
  missing source data and full regional presentation acceptance.
- Owner Mac/car execution and write validation. Local venv is Python3.15.2,
  while repository/static configuration targets3.13; no3.13 vehicle run is claimed.

These are open requirements, not completed checkboxes or relabelled exclusions.
The current PR must remain a draft recovery slice; no all-BMW compatibility or
full Task B completion claim follows from these changes or static gates.
