# Source database access and standalone diagnostic texts — 2026-11-04

Status: **observed read-only source access and generated runtime asset**. No
vehicle traffic or reference-application execution. Prior refusal/unknown-key
statements are historical: access to the supplied DiagDocDb was established.

## Source and access contract

- Source: `sources/ISTA_4.29.1x/Rheingold/SQLiteDBs/DiagDocDb.sqlite`, 5,945,655,296
  bytes, SHA-256 `247682de1535d6e6aeef7d641001a7bc253410f198f130111eb01785213ee28a`.
- Connector: `TesterGUI/bin/Release/RheingoldDatabaseSQLiteConnector.dll`, SHA-256
  `b4c43353b2cd4a99f4bcafdfd3a5f19b3e2390e7b8ab88afe4f8e76d2e05b06b`, MVID
  `140e8b25-cfe7-4ca7-9b6c-6bf16ccaa933`, assembly 4.29.15.23407.
- REA `inspect_managed_members` parent
  `ev_d6ed9f9fa963d186610a3bdd5a74d06a9eecc6b33c895ae50450a0cb8381bbf2`;
  focused method view `ev_d23f19804f4b720448ae04d368264a8c6604ba8833d990374466ab67ce6cdbab`.
  `SQLiteConnectionMgr.GetEntryAssemblyKey`, token `0x060001dc`, file offset
  384760, raw CIL SHA-256 `4ce6740ae70ff47772aca1de5f1185b717b7cef9655620ff10e5f8309afbf183`,
  calls `Assembly.GetEntryAssembly`, `GetName`, `GetPublicKeyToken`, followed by
  per-byte string formatting/concatenation. `SetPassword` is a managed reference
  to `System.Data.SQLite.SQLiteConnection.SetPassword(string)` (`0x0a000032`).
- Existing open-source implementation confirms the matching RC4 codec and ASCII
  token password: [DatabaseFunctions.cs](https://github.com/uholeschak/ediabaslib/blob/928cc36047f78721a70388e201c47e3922fbc3d8/Tools/ExtractEcuFunctions/Common/DatabaseFunctions.cs)
  and [PsdzDatabase.cs](https://github.com/uholeschak/ediabaslib/blob/928cc36047f78721a70388e201c47e3922fbc3d8/Tools/Psdz/PsdzClientLibrary/PsdzClient/PsdzDatabase.cs)
  constructor uses `cipher=rc4&hexkey=<ASCII password hex>` with read-only mode.
  No key guessing, login bypass, car security probing or proprietary executable
  execution was used to establish database access.
- Development reader: SQLite3MultipleCiphers 2.6.1 / SQLite 3.54.0, source
  amalgamation release [v2.6.1](https://github.com/utelle/SQLite3MultipleCiphers/releases/tag/v2.6.1),
  source ZIP SHA-256 `3f25af603566a23c821d8e581778b5ece2a541d2435776de57b8d845c176815a`,
  matching upstream SHA256SUMS. Compiled locally under `/tmp/bmw-source-db-reader`
  with clang; binary SHA-256 `dd764f82e6041d4bb9bf9a1012c45a1449a86ac0d0a835885c4ef20231a63b89`.
  No global installation or project runtime dependency was added.

REA's complete member response exceeded its 10 MiB transport budget; its retained
parent remained available and focused paged views succeeded. A redundant
class-filtered inspection hit the client's 450-second tools/call deadline; its
unchanged call was not repeated. The retained paged result already established
the needed methods/references, so this did not block source access or require
changing server configuration. Retained evidence exported to
`/Users/lennon/BMW-Tool/investigations/source-database-access-20261104/rea-evidence.json`
(19,874,087 bytes, six records), SHA-256
`2a529c4dc8a9ae926ac0840cd9fc3bfdb38581157df95ffd6d66f7d138e71fca`.
Pinned reference source copies and reader build notes are retained beside it.

## Extracted asset and lookup semantics

`python3 scripts/recover_ista_texts.py <DiagDocDb.sqlite> --reader <sqlite3mc>`
produces `coding_data/diagnostic_texts.db`, an ordinary plain SQLite file.
The source is opened `mode=ro&immutable=1`; no source database copy or rekey occurs.
The script checks release 4.29.14, source identity, code widths, output integrity
and atomically publishes the result. It stores source/reader hashes and counts.

Source join follows the existing reference lookup:
`XEP_ECUVARIANTS.ID → XEP_FAULTCODES.ECUVARIANTID → XEP_REFFAULTLABELS.ID →
XEP_FAULTLABELS.ID`, with **label CODE equal to fault CODE**. Without that final
code condition the reference table includes additional related labels, not the
specific fault description. Source codes are decimal strings; conversion is
base ten before display as UDS hex. Source datatypes F and I remain distinct.

The source has 163,944 fault rows (163,667 F and 277 I). Exporting the exact join
with existing ECU variants produces **162,757 linked fault/info descriptions**
and **1,227 ECU titles**; it does not synthesize the unmatched rows. English GB,
English US fallback and original German text are extracted. Conditions/validity
remain in the asset; they are not silently evaluated as vehicle applicability.

Asset size 41,050,112 bytes, SHA-256
`f62f002ba038e55fdc1802856423ef9d296ce1c4f00e224ddece8cb3db6714e0`.
`app/diagnostic_texts.py` opens only this standalone asset through Python's
standard sqlite3, with a connection created/closed on the caller's thread.
`describe(code, ecu=identified_variant, fault_type='F'|'I')` never substitutes
another ECU or memory. Distinct conflicting candidate texts return unavailable;
it does not arbitrarily select a row or assume an unimplemented rule engine.
ECU titles are description data, not proof of an installed ECU or write support.

## Offline verification

- Read-only schema and version queries succeed on the encrypted source.
- Source lookup DME_BX8 / decimal 1048577 (`0x100001`) produces
  `Throttle valve, function: Jammed briefly`; its title is
  `Digital Motor Electronics`. Generated-asset lookups match.
- Wrong ECU and wrong memory return empty; an SQL-injection-shaped ECU name
  remains a parameter, not SQL. Four concurrent threads repeat the same lookup
  without sharing connections.
- The owner's 2026-11-05 clarification supersedes the earlier English-only
  fallback interpretation: preserve every fault code and prefer English, while
  showing available descriptions in another language. English is selected only
  if **every** exact-identity candidate has nonempty, agreeing English text.
  Missing, null, whitespace-only or conflicting English candidates trigger a
  separate German agreement query; there is no per-row language mixing or
  arbitrary first-row selection. Conflicting German candidates remain empty.
  Explicit German requests retain their existing lookup behavior. This applies
  to both fault descriptions and ECU titles. No automated suite or `tests/`
  was created.
- Retained one-off 2026-11-05 checks cover 40 fault/title assertions across
  complete/partial translations, null/empty/whitespace English, shared and
  conflicting German, and ambiguous English. Actual asset English DME fault and
  title lookups pass; the current generated asset contains no nonempty-German /
  missing-English row, so that fallback boundary is exercised with standalone
  SQLite fixtures. An actual Qt diagnostics page renders both supplied codes,
  including an empty-description row. The worker appends every decoded record;
  description lookup is not a filter. Checks/logs are retained under
  `/Users/lennon/BMW-Tool/investigations/diagnostic-language-fallback-20261105/`.
- Python audit observations show runtime lookup opens only the generated asset,
  with no path under `sources/` and no codec/provider subprocess.
- Generated SQLite `PRAGMA integrity_check` returns `ok`.

This does not complete model/trim mapping, service-function rule execution or
coding CAFD decryption. Those are now concrete source queries/investigations,
not a blanket unknown-key limitation. The 40 GB long-document store was not
copied or exported; this increment extracts short diagnostic descriptions.
