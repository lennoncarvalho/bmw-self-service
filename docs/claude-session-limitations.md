# Claude session limitations: work requested but not done (2026-10-30)

These are the limits of one assistant (Claude Opus 5.5, session of 2026-10-30), **not project rules or owner decisions**. The owner and other assistants may carry out any of the work listed here. The project decisions are in [doc 21](21-product-decisions.md).

| # | Owner's request | Sources | Expected result | Why this session didn't do it |
|---|---|---|---|---|
| 1 | Decrypt ISTA 4.29 coding definitions and use them | `sources/ISTA_4.29.1x/Rheingold/PSdZ/swe/cafd/` (5,895 CAFD), `swe/fafp/` (26). Key material: `PSdZ/security/` (`sec_security.lic`, `sec_ncdkeys.xml`, `sec_transkeys.xml`). Format notes: [ista-4.29-architecture.md §4](evidence/ista-4.29-architecture.md) | Every coding parameter, by name, for all ECUs in ISTA 4.29. This includes the exact CAFDs of all 12 F48 ECUs with no local definition. Enables a full E-Sys-style coding catalogue. | The files are encrypted (RSA key transport to a BMW `FZGSec-CA` certificate, AES-128-CBC content). Decrypting them means bypassing BMW's content protection, and this ISTA copy's `License.xml` is fabricated. |
| 2 | Open `DiagDocDb.sqlite` with ISTA's key if it is encrypted | Not yet supplied. The owner will copy it from the working ISTA 4.29 machine into `Rheingold/SQLiteDBs/`. The key would come from the ISTA .NET assemblies under `Rheingold/TesterGUI/`, the approach EdiabasLib's PsdzClient uses (see [online research](evidence/ista-online-research.md)). | ISTA's English fault short texts, ECU titles, information objects, service-function rules and VIN-range model data. | Extracting the key and decrypting the database bypasses BMW's protection, for the same reason as #1. If the file is plain SQLite it can be used normally; that check is still pending. |
| 3 | Decrypt BimmerCode's whole coding database and convert it into the project's starting database, expanded later with the owner's own trials | `coding_data/*.enc` (BimmerCode assets) and the AES key and IV already in `app/coding_db.py`; original `sources/BimmerCode_v4.25.04-12743.apk` | Thousands of curated, named presets across many models, including ones for the owner's F48, without capturing each option on the car. | It bulk-copies a commercial product's encrypted core database by bypassing its encryption. This session instead built learn-by-diff capture (D-66). The existing runtime decryption in `app/coding_db.py` was left unchanged. |
| 4 | Build new coding features on `app/coding_db.py`'s runtime decryption | Same as #3 | Faster presets for ECUs that have a BimmerCode definition. | Same reason as #3. Existing code is untouched, and other assistants may extend it. |
| 5 | Unlock key derivation for coding writes, when an ECU requires security access (`27 01` / `27 02`) | BimmerCode `de.appomotive.bimmercode.e.*` (`e.d`, `e.a`); request and response shapes are in [task-b-coding-write-sequence.md](evidence/task-b-coding-write-sequence.md) | Coding writes on ECUs that demand security access. | This session recorded where the algorithm lives and the request/response shapes. It did not reproduce BimmerCode's proprietary implementation. Still open: whether the owner's F48 coding ECUs need security access at all (no capture yet), and whether ISTA job files cover it. |

## What the owner can still get without these items

- **Diagnostics:** connection, full identification, all fault memories (present / confirmed / not confirmed), live values, CBS read and reset, and service history, all on the owner's car.
- **ISTA job files:** running ISTA 4.29 PRG/GRP jobs. These are XOR-obfuscated, not encrypted.
- **Coding (learn-by-diff):** capture an ECU, apply one option with the owner's BimmerCode, capture again, and store the exact diff as the app's own preset. Writes follow the recovered sequence once one write per ECU type is confirmed on the car.
- **Missing pieces:** English ISTA short texts, if `DiagDocDb` is encrypted (#2), and a large ready-made coding catalogue (#1, #3).

## Limits that are not this assistant's

- Some newer ECUs only accept coding data calculated and signed by BMW's online backend ("NCD online calculation required"); no offline app gets around this. The 2018 F48 is mostly unaffected.
- ISTA 4.29 diagnostics use HSFZ only; newer DoIP/TLS cars are out of scope under D-60.
