# Recovered standalone coding catalogue and composition — 2026-11-04

Authority: owner source-reuse request; source inspection and offline checks only.
No ECU, source application, external research service or reference executable is
required at runtime. The embedded asset is generated during development.

## Artifact and reproducibility

Coding package: `sources/BimmerCode_v4.25.04-12743.apk`, SHA-256
`fc6eedeb741cbec49f46c126f8c72dac6a3dd1455f8a993c028695642459b728`.
Original local `coding_data/*.enc` documents retain per-file source hashes in the
built manifest. Existing extracted strings have their own hashes. The decoded
resource XML is a development input; its hash and the package identity are
retained, without asserting a cryptographically verified ARSC/XML pairing.

```sh
.venv/bin/python3 scripts/build_coding_bundle.py coding_data coding_data/coding_catalog.db \
  --apk sources/BimmerCode_v4.25.04-12743.apk \
  --selection-evidence docs/evidence/source-coding-selection-20261104.json \
  --resource-strings bimmercode_extracted/res/values/strings.xml
```

`coding_catalog.db` contains bounded gzip-compressed plaintext JSON members,
English/German labels and a schema-1 provenance manifest. SQLite opens read-only
with per-call connection ownership. Runtime never opens `.enc`, `sources/`, APKs
or extracted research trees and contains no asset-decryption key. Development
AES material lives only in the builder. Runtime cryptographic code derives actual
source AS/NCDS responses from the compiled entries, without key probing.

Inventory: 2,305 original JSON documents, including 2,163 definition documents;
1,979 of those match exact eight-hex CAFD ID plus three-part version identities.
There are 80 hex root indexes with 1,034 entries and 3,074 English/German labels.
The earlier 1,566 count included eight-character non-hex legacy names; it is not
the ENET CAFD preset count. Preserve non-ENET documents as source data without
enabling E-series vehicle operations.

Additional generated documents retain 2,829 authorization/signing records,
40 series-tag selectors, 13 primary-definition preferences and 45 source category
descriptions with 71 explicit normalized F/G/U/I model codes. These counts are
source inventory, not installed ECUs or physically validated support.

## Actual source contracts

REA full records are retained outside shipped assets at
`/Users/lennon/BMW-Tool/investigations/source-runtime-20261104/coding-evidence.json`.
The committed selection evidence includes exact methods/provenance for rebuilds.
All observations used JADX 0.7.1 through the connected REA provider; method output
below was complete Java except where the retained record explicitly says smali.

| Behavior | Class/method | REA record |
|---|---|---|
| Apply all values at start + relative position, with optional value-mask intersection and trailing-zero alignment | `k.a.c(h0,c0)` | `ev_dd11646f990148c6cb96f4479b82ed93cdad75f44f5e0e5d29c4354d5127a723` |
| Read inclusive start/end from the enclosing group, mask/shift each byte | `k.a.g(s,w)` | `ev_82c0d8616c0276f4a54a13180090c4a0469faade4d480b2b3a6842e4eb9f4b5b` |
| Curated selector: ID8 flag, source category tags and excluded variant indexes | `asynctasks.b.doInBackground` | `ev_d28e868bb4fb25d468167bd5bd2d616b46a350aca90cd4e4670e08084b8ca2d5` |
| Primary CAFD preferences then first reported identity | `models.r0.i` | `ev_1970da24e51cd2f8540ccc6835c33a5172edb42a2f7a2187ca75b6781008a568` |
| Function-name lookup uses the first match in declared group order | `models.q.f` | `ev_4464a7d4a353dbbf03fb38ac508efab732340a760a6a878143ad9a52885329cd` |
| F-series normal baseline writes sign each definition; E-series checksum work is not called here | `models.s0.A`, `k.a.i` | `ev_eaa616036d39e6dce0e4ae22b6dbbcbc0d227fd0a441061294b2560332ca8dd9`, `ev_0e2c91dd31914634271e12efa8731fb7ecaaca14765a0bc9710a97cd0a46eced` |
| Signature group selected by exact name `SIGNATURE`; concatenate other declared groups in order | `models.q.i/c/d`, `k.a.a(q)` | `ev_26e86b7b0bcc528a1fa06eb0c8de9c3d72cfb322fc74dbefe12bea5fd5150dc8`, `ev_b513e6c8ba009deb24cbfbdb0061bfc87551d80951041d1cbfbf529018a29303`, `ev_44e32c4313a8aec72987f1231ca9604254a0a12a271a2fa75b068061f1207923` |
| AS digest preimage is FFFFFFFF + raw four-byte bootloader ID + raw seed; request 2702 uses the derived bytes | `codingtasks.l$a.b` | `ev_d63efabd78a06ebec15b2abb6d25e0886d7727e647de284e91508e8b996cacc3` |
| RSA digest, reverse padded bytes, raw private exponent operation, reverse four-byte words and prefix word count | `e.a.b/c/a` | `ev_3a687afcf1ba6a227f02a05f52ac6cc6b2436d9479db727c2e9cdd64b09837ed`, `ev_d4ebc8e6becb0bb450498e2180c4506c6fad9190400a061cbbde8fb40b4769e9` |
| AS entries are plain gzip JSON; NCDS entries use a separate source AES key/IV | `e.d.b/c`, `external.ExternalLib.f/g` | `ev_a7fcc700f60d65fb8a6d647fcfb000f47da9114c6854efc5e5b13e5190cdd91f`, `ev_c67e252eb541b751003d9524e69e51cc9a1618ef083e15c55917c2b907d47d82`, `ev_ca3c890639de9c58ab72c4068b5673b851ddaf92940caa3786a7f5a30b0c23ae` |
| Exact bootloader/key-type lookup returns the first ordered matching entry | `e.d.f` | `ev_4818cd10900738e25ee1d2f1f3c54916cec3dc9eefb4938261ff88a09340e2a2` |
| Dynamic lighting reads module/matrix/current intensity and offers current or 100%, not arbitrary percentages | `AngelEyesBrightnessCodingOptionActivity.a0/b0/c0/d0` | `ev_2488034b3810827d6a0b372b015fb44a7af70b9fc6f042aa10d1e56025e88515`, `ev_e7afed4add19f2f2970a9a9f247ce95d813a6c807e59f0e41b4b96a3f3c795cd`, `ev_03bd15cb60180a2e85eca1882ab4332cdd897d1133807d0d11db1c4659f2ac15`, `ev_3b083954e0fde91b54210d3fed67ff453b329a10c02c18ab1a8e2b317cf1a572` |

The source names the alternate NCD signature algorithm DES, but actually computes
MD5(key || coding bytes || key). Unknown digest labels fall back to MD5 in this
source; do not substitute guessed SHA-384/SHA3 handling. Some RSA private-key
records omit CRT/public-exponent fields. The source uses modulus/private exponent
only; the Python helper parses PKCS8 accordingly rather than rejecting zero CRT.

## Verification and concrete limits

- Compared all 2,305 original source JSON documents and their provenance hashes
  against standalone runtime reads. All comparisons passed.
- Exercised multi-position values, group-specific current detection, untouched
  bytes/groups, value masks, conflicting choices, absent baseline, unsupported
  mapping, malformed compressed member and standalone loading with no source
  assets beside the DB. No persistent suite was created.
- Synthesized source-described lighting bytes from the real
  `000024C3-008-005-000` definitions. Current 79% and target 100% matrix choices
  resolved and round-tripped through the actual composer/current matcher.
- Independently compared RSA output with Java 21 KeyFactory/Cipher and digest
  primitives across usable AS/NCDS digest/width families, including zero-CRT keys,
  plus the alternate MD5 sandwich. No key material was printed or exported in
  verification reports. Scratch scripts are retained locally, not a test suite.
- 83 stored entries have empty or EC formats that this APK's RSA implementation
  does not support. Preserve the records, fail selected unsupported entries, and
  do not silently try another key. Two empty RSA entries precede later alternate
  entries under the same ID; source lookup ordering remains explicit.
- Resource descriptions for i3/i8 omit actual model codes; no I01/I12 mapping
  is inferred from their dates or marketing names. Unknown/ambiguous model codes
  remain explicit until another source establishes the mapping.
- `excludedSeries` is retained from the supplied catalogue, but its semantics
  are absent from this APK's parsed option fields. Rows carrying it are not
  silently enabled by the new predicate evaluator.
- Current matching/composition alone does not supply vehicle identity, complete
  baseline, write sequencing, authorization, journal, completion or restore.
  Those belong to the shared coding engine and its separate review/verification.

## Exact reported identity versus source-selected layout

Later investigation recovered `models.q.b(k.v)`
(`ev_fff2ec74bfdc59d3eec49a675868bed08e828c2ca7b9f6377519a3de55bb2047`):
exact package file first; otherwise filter the same ID/major/minor and select the
immediate lower patch after sorting. `k.v.i`
(`ev_f94a4a68977996fe91f927703ba04ca1bb37ea1c78dab01613d46cca706f06f2`)
and `q0.b` (`ev_5d01a6d008347b6c18e7496b7b32d159e1803ac5deffed9b798dd900db9847dd`)
confirm the prefix and numeric version comparison. This disproves our earlier
exact-file-only prerequisite. The original F101/software identity stays exact;
the selected source layout and its provenance are recorded separately.

The loader freezes `definition_resolution` (reported, selected, method, source
hash, document hash and exact-source cross-check). New exact XML is used for
read coverage where no package layout applies. A lower-patch layout is compared
against available exact XML group sets, signature address and byte bounds;
contradictions select read-only unnamed XML rather than guessed named fields.
The source lower-patch rule does not permit another major/minor or a higher patch.

Observed owner-version resolutions include `00000DED-003-015-037` →
`00000DED-003-015-006` and `00001413-001-034-003` → `00001413-001-034-000`, plus
three ACSM definitions. All five pass the independent exact XML group/signature
cross-check. This is source/offline evidence, not a vehicle write observation.

The full build now includes 4,127 additional converted exact XML definitions,
6,106 total available exact CAFD versions, and explicit dispositions for three
CAF version-2 records (`000058AA-001-001-001`, `000058AA-001-001-002`,
`00005C0A-049-001-020`). Those have codingArea/sigId/sigLen metadata and no
byte-layout data/datagroup collection; do not infer UDS DIDs from that schema.

Whole-source group units are enforced for complete baselines. Runtime document
limit is 32 MiB, based on the observed 24,314,756-byte converted definition
`000011AC-007-001-008`; this changes the generated-asset bound, not coding backup
or history storage contracts. The full SQLite asset is about 242 MiB.

Runtime labels adapt eight source-brand references to generic coding/diagnostic
instructions, retaining battery-registration and software-version restrictions.
Source label-file hashes still identify the originals. Duplicate source preset
names retain exact root indices; duplicate option names with different color
payloads receive scoped ordinal keys and source color labels, not guessed values.

Independent Qt checks used actual MainWindow/CodingPage/CarWorker signal delivery
with fake execution workers: global mutation lockout and close refusal, release
only on finished, persistence-failure evidence/export gating, read-only/DEMO
zero-live-preparation, and distinct restore acknowledgement/cancel. The 650×560
confirmation screenshot was visually inspected and fits. No car traffic occurred.

The final aggregate `scripts/build_runtime_assets.py` invocation completed with
all thirteen source job series, this complete catalogue, native runtime and
description assets. The coding database is 254,234,624 bytes, SHA-256
`5e24ba9fd55909be6a05bb6d4961307156b1fdbf2ca11c234e4377f23551736d`.
Its generated selection document includes the source climate critical-code guard
(address `0x78`, request `19 02 0C`, sticky codes `801225`/`801224`). Runtime
asset-manifest hashes must be refreshed after any other producer publishes.

## Additional reader prerequisites recovered during final review

`models.s0.r/L`, `codingtasks.u` and `codingtasks.p.n` distinguish ordinary
direct `22 <group>` reads from special head-unit prerequisites. Ordinary group
reads have no general session transition. For `n0.t()` targets (address `0x63`
or primary CAFD `00004224`), the source first runs its unlock-code backup task:
`10 03`, `10 42`, then `31 01 0F 1F 04`; its callbacks and retained response
contract must be carried through, not replaced by an assumed success.

For address `0x63` with exact F150 variant `0F2230`, `s0.L` additionally rejects
the first `22 10 0B` integration-level field when it contains
`F056-16-11-5`, `S15A-16-11-5`, `I001-16-11-5` or `F025-16-11-5`.
Otherwise it requests `22 D0 0A` (positive response length exactly 21), extracts
big-endian signed 32-bit RAM size from raw response bytes `[12:16]` (Java int
expression widened to long), then requests `22 D0 3F`.
Its HMI string is response bytes `[3:]`; case-insensitive `NBTevo_ID5_` with RAM
below 4,000,000 is rejected. These are source branches, not claims about the
owner's NBT or a new dependency on another physical vehicle.

The twelve complete retained REA records are in development evidence
`/Users/lennon/BMW-Tool/investigations/source-runtime-20261104/coding-read-prerequisites.json`.
Key method evidence: `ev_24b3d386240f939480181a3cc93155aefe44c88e8c1a2a9e2a82434b0c871fa0`,
`ev_ceab41625fcde03633d2959e1b79cd1b722a180bc95a71c8edf79ab2b4caacea`,
`ev_003d34081ede04b0df228e1a273fbc7e7b1f3ed3471599989e9aa92c0f46cda4`.
The parent integration owns these reader prerequisites; catalogue availability
alone must not be reported as completing that branch.

`scripts/build_coding_reader_contracts.py` now compiles this separate small asset
without rebuilding the full catalogue. Run it with the two retained evidence
JSON paths above (the second is `coding-unlock-backup-contracts.json`) and output
`coding_data/reader_contracts.json`. It checks complete same-artifact methods,
the exact selector, request bytes, list/payload offsets, critical I-level branches
and the two source RSA public moduli; the generated file retains evidence hashes.

Unlock-code listing entries are seven bytes: big-endian identifier `[0:2]`,
upgrade `[2:4]`, signed status byte `[5]`. Source lists begin at raw response
offset 9 and require at least one seven-byte entry; accepted status 2 entries
without a retained file are retrieved using `31 01 0F 1F 0B` plus identifier and
upgrade. The file payload is the positive response from offset 6. For exact
variant `0F2230`, retained files are checked using exponent 3 and either of two
source moduli against the trailing MD5 digest; other variants have no such
signature check. The task cleans up with `10 01` and refuses backup failure.
Explicit unlock-code upload is a separate UI manager (`codingtasks.v.w`, command
`31 01 0F 1F 07` with security access), not an automatic coding-restore step.
These files are additional retained source prerequisites; they do not replace
the complete original ECU coding baseline contract.

Independent checks of the integrated helper used actual runtime parsing with
offline request callbacks: exact session/list/retrieve/cleanup order, durable
payload retention and cache reuse, conditional status-4 behavior, Java signed RAM
refusal and read-only zero-I/O all passed. The reader asset is 1,730 bytes with
SHA-256 `75e2c23ac7d675e6bc997102b2b15818656155097d1e41774417b1bfbb1ec775`.
