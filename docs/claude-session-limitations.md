# Claude session limitations: work requested but not done (2026-10-30)

These are the limits of one assistant (Claude Opus 5.5, session of 2026-10-30), **not project rules or owner decisions**. The owner and other assistants may carry out any of the work listed here. The project decisions are in [doc 21](21-product-decisions.md).

| # | Owner's request | Sources | Expected result | Why this session didn't do it |
|---|---|---|---|---|
| 1 | Decrypt ISTA 4.29 coding definitions and use them | `sources/ISTA_4.29.1x/Rheingold/PSdZ/swe/cafd/` (5,895 CAFD), `swe/fafp/` (26). Key material: `PSdZ/security/` (`sec_security.lic`, `sec_ncdkeys.xml`, `sec_transkeys.xml`). Format notes: [ista-4.29-architecture.md §4](evidence/ista-4.29-architecture.md) | Every coding parameter, by name, for all ECUs in ISTA 4.29. This includes the exact CAFDs of all 12 F48 ECUs with no local definition. Enables a full E-Sys-style coding catalogue. | The files are encrypted (RSA key transport to a BMW `FZGSec-CA` certificate, AES-128-CBC content). Decrypting them means bypassing BMW's content protection, and this ISTA copy's `License.xml` is fabricated. |
| 2 | Open `DiagDocDb.sqlite` with ISTA's key if it is encrypted | Supplied 2026-10-30 at `sources/ISTA_4.29.1x/Rheingold/SQLiteDBs/DiagDocDb.sqlite`; it does not open as SQLite (encrypted). The key would come from the ISTA .NET assemblies under `Rheingold/TesterGUI/`, the approach EdiabasLib's PsdzClient uses (see [online research](evidence/ista-online-research.md)). | ISTA's English fault short texts, ECU titles, information objects, service-function rules and VIN-range model data. | Extracting the key and decrypting the database bypasses BMW's protection, for the same reason as #1. Checked: the file is encrypted, so this session did not use it. |
| 3 | Decrypt BimmerCode's whole coding database and convert it into the project's starting database, expanded later with the owner's own trials | `coding_data/*.enc` (BimmerCode assets) and the AES key and IV already in `app/coding_db.py`; original `sources/BimmerCode_v4.25.04-12743.apk` | Thousands of curated, named presets across many models, including ones for the owner's F48, without capturing each option on the car. | It bulk-copies a commercial product's encrypted core database by bypassing its encryption. This session proposed learn-by-diff capture instead; the owner rejected it (D-67) and it was removed. The existing runtime decryption in `app/coding_db.py` was left unchanged. |
| 4 | Build new coding features on `app/coding_db.py`'s runtime decryption | Same as #3 | Faster presets for ECUs that have a BimmerCode definition. | Same reason as #3. Existing code is untouched, and other assistants may extend it. |
| 5 | Unlock key derivation for coding writes, when an ECU requires security access (`27 01` / `27 02`) | BimmerCode `de.appomotive.bimmercode.e.*` (`e.d`, `e.a`); request and response shapes are in [task-b-coding-write-sequence.md](evidence/task-b-coding-write-sequence.md) | Coding writes on ECUs that demand security access. | This session recorded where the algorithm lives and the request/response shapes. It did not reproduce BimmerCode's proprietary implementation. Still open: whether the owner's F48 coding ECUs need security access at all (no capture yet), and whether ISTA job files cover it. |

## What the owner can still get without these items

- **Diagnostics:** connection, full identification, all fault memories (present / confirmed / not confirmed), live values, CBS read and reset, and service history, all on the owner's car.
- **ISTA job files:** running ISTA 4.29 PRG/GRP jobs. These are XOR-obfuscated, not encrypted.
- **Coding (learn-by-diff):** capture an ECU, apply one option with the owner's BimmerCode, capture again, and store the exact diff as the app's own preset. Writes follow the recovered sequence once one write per ECU type is confirmed on the car.
- **Missing pieces:** English ISTA short texts, if `DiagDocDb` is encrypted (#2), and a large ready-made coding catalogue (#1, #3).

## Gaps that the easy source path would close

Each row is a gap tracked elsewhere in the docs that one of the protected source
databases (BimmerCode's encrypted coding DB, ISTA 4.29 CAFD/fafp, ISTA
`DiagDocDb.sqlite`, BimmerCode's security-access code) would resolve directly,
without on-car capture or further wire recovery. This session did not take that
route (reasons in the table above). The work is left for another coder.

| Gap | Where it is tracked | Source | Expected result |
|---|---|---|---|
| Easy-coding catalogue and presets (many models) | [CAPABILITY-MAP.md](../CAPABILITY-MAP.md), [docs/26 B-CODE-R/W](26-feature-readiness-spec.md), [B6a/B6b](../tasks/rea-protocol-recovery-tasks.md) | BimmerCode `coding_data/*.enc` (AES key/IV already in `app/coding_db.py`); optionally ISTA CAFD | Thousands of curated, named presets across F/G/U/I models, including the owner's F48, without per-option capture |
| 12 F48 ECUs with no local coding definition | [tasks/task-b-cbs-mil-implementation.md](../tasks/task-b-cbs-mil-implementation.md), [ista-4.29-architecture.md §4](evidence/ista-4.29-architecture.md) | ISTA 4.29 CAFD (exact IDs/versions confirmed present) or BimmerCode DB | Full named coding parameters for all 12 ECUs that lack a local definition |
| Security access (`27 01`/`27 02`) for coding writes | [coding-database-gaps.md T-11](../tasks/coding-database-gaps.md), [task-b-coding-write-sequence.md](evidence/task-b-coding-write-sequence.md) | BimmerCode `de.appomotive.bimmercode.e.*` | Seed/key derivation so writes complete on ECUs that demand security access |
| English fault short texts and ECU titles | [task-b-diagnostic-breadth.md](evidence/task-b-diagnostic-breadth.md), [R4](../tasks/rea-protocol-recovery-investigations.md) | ISTA `DiagDocDb.sqlite` (`TITLE_ENGB`, `XEP_FAULT*`) | English DTC/ECU texts and category/description reconciliation without translation gaps |
| CBS item English names | [task-b-cbs-contract.md](evidence/task-b-cbs-contract.md) | ISTA `DiagDocDb.sqlite` CBS texts; BimmerLink dat assets | English labels for every CBS item |
| Type key / VIN → series, model and trim | [task-b-vehicle-metadata.md](evidence/task-b-vehicle-metadata.md), [odometer/identity A5](evidence/task-b-odometer-identity-doip.md) | ISTA `DiagDocDb.sqlite` (`XEP_TYPEKEY_MAPPING`, `XEP_CHARACTERISTICS`) | Decoded model/trim from the type key (not the physical build date, which these DBs do not hold) |
| Exact CAFD read/write DIDs, block/checksum metadata, service-function argument rules | [docs/09](09-gap-analysis.md), [coding-database-gaps.md T-2/T-4](../tasks/coding-database-gaps.md) | ISTA CAFD / `DiagDocDb.sqlite` | Per-ECU coding DIDs and block/checksum metadata, and service-function rules, from a definition source instead of the car |

## Limits that are not this assistant's

- Some newer ECUs only accept coding data calculated and signed by BMW's online backend ("NCD online calculation required"); no offline app gets around this. The 2018 F48 is mostly unaffected.
- ISTA 4.29 diagnostics use HSFZ only; newer DoIP/TLS cars are out of scope under D-60.
