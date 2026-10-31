# Vehicle metadata and source category accounting

2026-10-29. **Primary implementation reference**, statically recovered with
REA/JADX0.7.1 from supplied S-02 APK4.25.04-12743, SHA-256
`fc6eedeb741cbec49f46c126f8c72dac6a3dd1455f8a993c028695642459b728`.
No reference application or vehicle operation was executed.

## Vehicle-order display and equipment catalogue

`de.appomotive.bimmercode.a.g0.<init>(Context,b1,w0)` displays the observed
`b1.g()` as **model range**, `h()` as **time criterion**, `i()` as **type key**,
`e()` as **paint code**, and `j()` as **upholstery code**. It does not decode a
trim/model from the type key, convert the time criterion into a proven build
date, or normalize a four-character model range into a chassis string.

Easy source path (not taken by Claude; left for another coder): ISTA
`DiagDocDb.sqlite` (`XEP_TYPEKEY_MAPPING`, `XEP_CHARACTERISTICS`) maps type key → 
series/model/trim, which would decode the trim/model honestly. The physical build
date is **not** in these databases (it comes from FA/VCM; see
[odometer/identity A5](task-b-odometer-identity-doip.md)), so that gap stays open.
See [../claude-session-limitations.md](../claude-session-limitations.md).
Evidence `ev_6122b4e2add3ae4c9153750009a2cf869e49d74edd70ac4ed1bfb8eedc552e34`.
These distinctions prevent the previously conceptual FA/model examples from
becoming guesses in the dashboard.

The same constructor iterates all observed `b1.f()` option codes, calls
`models.y0.c(context,code)`, and displays the raw code if the catalogue does not
have a matching row. For this app an explicit unavailable English description
preserves that same unknown-code boundary.

| Exact source method | Recovered rule | REA Evidence |
|---|---|---|
| `models.y0.d(Context)` | Load `assets/salapa.enc` through `FileDecompression.d` and `ExternalLib.f/g` | `ev_0a975fff7e10306316226136fd39e35a6fc4e575c0c9ab3fd4d43e422953c185` |
| `models.y0.c(Context,String)` | Case-insensitive exact code; require `type==P` | `ev_d39df52f56f5ed68e7a01a61f3f9641bd11f90d96a463fb140cc4f601204cc65` |
| `models.y0.a()` | Default English `en` field when no listed locale matches | `ev_9f7753aa7b5162bdd20f3dd37e4fc93299ac6aaf2394ca5043a97d7e00c9a0c7` |
| `asynctasks.FileDecompression.d(InputStream,String,String)` | AES/CBC/PKCS5Padding then `a` decompression | `ev_98b51aa20b0b344797aa710bf3029fb2e13407b2f4f65dc131a976a37820284d` |
| `external.ExternalLib.f/g()` | Exact data-key/IV constants | `ev_60770b1e9f2c578934539bdd5393c8efd54589722df691c39c924812ceb3f337`, `ev_7b3413823f141e2bc4cdee7e199dfbb790c3d6cb17e4285ed04ce4942bfac562` |

The original asset contains5640rows:4735unique `P` passenger-vehicle rows and
905`M` motorcycle rows. Including both would mix562same-name collisions.
For example249means passenger **Multifunction for steering wheel**, while its
motorcycle row says **Country-specific control00207**. All4735passenger rows
have English descriptions;4162codes have three characters and573have four.
No runtime source names, decryption tool, reference executable or REA dependency
is introduced. `app/vehicle_metadata.py` only reads a bounded generic JSON asset,
checks its schema/entries and labels exact observed codes. Unknowns stay visible.

`scripts/recover_vehicle_metadata.py` requires the original exact APK digest,
reads the original ZIP member (not an extracted tree), validates padding,
decompresses, filters exact`P` rows and rejects duplicate/missing English rows.
The deterministic asset and all original/plain/generated hashes are recorded in
[the manifest](task-b-vehicle-metadata.json). The generated239076-byte asset has
SHA-256`6f9c5e8ec94a6ffb03c6e9f21d0e972322a9d82de0930b48b275f0b85a1f1567`.
The app's English-only policy uses the existing English source field, without
German fallback. No claim of independently translated every technical label.

One explicit editorial substitution keeps a development tool name out of the
shipped labels, as required by AGENTS.md: code `IST1` originally says
`ISTA simulation tests`; its label is `Diagnostic simulation checks`. The exact
code and its catalogue membership are unchanged. The extraction script verifies
the original source text before substituting it, and the internal manifest
retains the original, replacement and reason. All other4734English labels are
retained verbatim. This is a display-label edit, not a new equipment identity.

## Complete supplied series catalogue and U/I boundary

`models.o.K(Context,int)` enumerates IDs1through45for category0, `m()` for1,
`q()` for2, and `s()` plus38for3. Evidence
`ev_1f42d6444649362b84fb51cb86653a5b6cdb38c2a830cc9920e35e25ccbd5533`.
Complete45-case label/description methods `o.P/N` are retained as
`ev_6bb3c724d70763697a424f5414889782c98bec86a277646b95d180228f181335`
and`ev_75dfca41a115ea6afe98320361895d08fc9d923ad697f90973c8acd62b5a2464`.
These are catalogue groups selected by the user, not a live type-key database.

| Catalogue branch | Exact IDs | Relevant interpretation |
|---|---|---|
| `o.m()` category1 |28,29,30,31,32,33,34,35,36|E/R source groups outside this app's current scope|
| `o.q()` category2 |1,2,3,4,5,6,7,9,11,13,14,15,17,19,21,22,23,24|F interface also includes i3(ID22),i8(ID23),MINI(ID24)|
| `o.s()` category3 |8,10,12,16,18,20,25,42,27,26,37,39,41,40,43,44,45|G interface includes i4(ID43),iX3(ID45),F40(ID39),F44(ID41)|
| additional category3 |38|Supra group, outside BMW scope|

`o.q/s/m` evidence:
`ev_960d780f03c20748f28cbc7b5cdb6721a2c0cc78f29a990e372c794fbdbbf6e1`,
`ev_1424c5d79a1fed8c69069f3d3142fa9e955dfd41a02981cb70d0e30e6959d634`,
`ev_17e2c4c8c16f498319e7f9aa0632914916efbefe791781dd52c73c0fc192922c`.
`o.y()` returns22,23plus all`s()`; the source's`i`preset category is therefore
not equivalent to electric models or I-prefixed chassis. Evidence
`ev_eb13c471147434913c939991b15bdea65129fcb3fe4f1635c8213c68b36adbc5`.

`ConnectCarActivity.onCreate` gets category from the intent;`A0` chooses
`t0` for3,`s0` for2, E interface for1, errors otherwise. Evidence
`ev_7f128cd38a924aa0ce720e9af332bba9690f2ce75e7237d741f4953014e07636`,
`ev_e28170fb18836dcfd653d75b39021431038fb5797ad8a9ca0d83337c621b2b20`.
The supplied exact45groups do not contain a U chassis group or I20/iX group.
That is a bounded observation about this supplied catalogue, not a universal
unsupported classification. The app must not transform this source limitation
into a guessed U/I decoder or require physical access to those cars. Newer
U/I model selection needs a concrete matching source contract; existing exact
ECU identification/candidate coverage remains independent of the picker label.

No new full-width DoIP logical-address conversion is established here. The
already recovered ENET factory and inherited F/G interfaces use HSFZ; see
[topology evidence](task-b-topology-selection.md). Neither `i`preset categories,
F40/F44 being in the G user group, nor vehicle-order model-range text establishes
transport selection. No mapping is added to runtime from any of those labels.

## Retained evidence and offline verification

Portable REA bundle:
`/Users/lennon/BMW-Tool/investigations/task-b-vehicle-metadata-evidence.json`,
339526bytes/29records, SHA-256
`4e536677b48aa159426c5ceedab75c312d735f0c6b970e667912245a98bce014`.

One-off check retained locally at
`/Users/lennon/BMW-Tool/investigations/task-b-vehicle-metadata-20261029/offline-check.py`.
It exercised all4735exact/lowercase lookups, passenger/motorcycle collision249,
unknown codes, empty list, invalid/oversized codes, malformed/oversized catalogue,
and byte-identical asset/manifest recovery from the original APK. All passed.
Full `scripts/preflight.sh` passed Ruff lint/format and mypy35modules at this
checkpoint; the parent increment reruns the gate after final integration.
The development extraction script separately passed Ruff lint/format. No car,
reference-application runtime or physical lamp observation was involved.

After the editorial substitution, all4735lookup/error/reproduction checks passed
again and the extraction script passed Ruff lint/format. The asset remains
4735codes, now239076bytes with the SHA-256 above.
