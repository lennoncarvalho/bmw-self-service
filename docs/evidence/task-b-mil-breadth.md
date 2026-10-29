# MIL source catalogue expansion — 2026-10-29

Status: **primary implementation reference**, implemented and exercised offline.
No vehicle traffic, physical lamp comparison, actuation or reference executable
execution. This expands the three original exact engine definitions in
[the initial contract](task-b-mil-read-contract.md); it does not assign a universal
MIL DID to petrol/diesel/chassis families.

## Exhaustive selection boundary

The unchanged diagnostic catalogue contains 62 exact `12 <F150 first3 bytes>`
UDS engine rows, representing 26 engine definition names. The original APK is
`BimmerLink_v2.36.1.apk`, SHA-256
`da6f5b39efaa590fce68782f439c1b8f1b9f09ed41344055b8ff80666cae00d5`.
Its source selection/decryption and member hashes remain in
[the catalogue manifest](task-b-diagnostic-catalog.json).

REA/JADX reinspection of `j6.h.f(String)` establishes exact case-insensitive
address-index equality, with no prefix/family fallback:
`ev_7a56ad0c951048cb3561a52e3ff26680c0ee1bac8e69c266d2acfb481735418d`.
Portable export:
`/Users/lennon/BMW-Tool/investigations/task-b-mil-breadth-20261029/rea-evidence.json`.
Export SHA-256 `ac663954f0750ad7a86e4ee836067217f3f54e9f68fe3602d9ebb622f925d785`.
REA 6.8.0/JADX 0.7.1, static Java representation, complete returned method body;
no Android execution. Exact engine addresses still require the recovered
transport mapping; these source-byte-addressed MIL contracts remain HSFZ scoped.

The format-aware BEST parser inspected all 24 present exact-name PRGs, their
SG_FUNKTIONEN rows and relevant job dispatch. Neither a filename-prefix match
nor an unstructured keyword hit enables a read. Complete original PRG hashes,
row indices/metadata, job offsets and normalized whole-job fingerprints are in
[the breadth manifest](task-b-mil-breadth.json).

| Source branch | Engine definition names | Implementation |
|---|---|---|
| Direct `22 4A69`, unsigned char, unit0/1 | DME8FF_R, DME_BX8, MEVD172, MEVD1724, MEVD1725, MEVD172Y, MSD87_R0, N63TU_R0, S55, S63TU_R0 | Enabled after exact F150/name/address match |
| Direct `22 50D8`, unsigned char, unscaled MIL request | D70BX7A0, D72N47A0, D73N57A0, D73N57E0, D75BX7A0, D83BX7C0 | Enabled for exact raw0/1 only; other request values unavailable |
| Direct `22 42BC`, unsigned char, unscaled MIL request | D94BX7A0 | Enabled for exact raw0/1 only |
| Block lifecycle traced; runtime implementation pending | MSD85L6, MSD85YL6, MSD87, MSV90, N55_ALP | STATUS_BLOCK_LESEN clear/define/read traced; definition-disabled path still reads F3nn. Exclusive sequence ownership, checked cleanup, uncertainty handling and read-only enforcement remain; no metadata-only direct probe |
| No direct ISMIL table row | DME9FF_R, EDMEI1 | No guessed4A69/50D8 request; recover actual alternate MIL selection/decoder next |
| Exact PRG absent | DME98_R, FCCU | Specific missing source definition retained; no related-name substitution |

Result: 53 exact address-index rows /17 definitions enabled;9 rows /9 definitions
remain accounted for above. These are source-definition counts, not counts of
physically validated vehicles. Engine definitions not represented in this
catalogue, other addresses and other transports remain outside this inventory.

## Complete direct request/decoder trace

For the17 enabled definitions, STATUS_LESEN starts with service22, resolves the
selected `SG_FUNKTIONEN.ID`, appends its high byte then low byte and sends to12.
It does not change session, dynamically define a DID or actuate the lamp.
Transport wrappers are stripped before the positive PDU decoder; the app uses
the existing single owner and a30-second queued request budget.

All17 complete STATUS_LESEN listings have the same control flow and scalar
extraction. After normalizing only absolute BEST labels, differences are the
maximum count of arguments and some non-MIL identifier special-case lists.
The latter do not contain4A69,50D8 or42BC. All six observed fingerprints are
explicitly reviewed by the generator; an unseen fingerprint fails reproduction.
Existing three MEVD listings remain unchanged. D94BX7A0's old DIG_DDE_KOMBI row
still mentions50D8; the actual selected SG_FUNKTIONEN row is42BC. The implementation
uses only the latter traced direct path.

D94BX7A0 coordinates (other exact job offsets/hashes in the manifest):

- STATUS_LESEN entry `0x183FE`: service22.
- `0x19897` onward: selected ID converted to integer; high/low bytes appended.
- `0x19E45` / `0x19F81`: testerF1 / target12, followed by xsend.
- `0x1A35B` onward: initialize positive-PDU cursor1, consume/compare BE16 DID,
  advance cursor to3, reject truncated/mismatched fields.
- `0x1EA35`–`0x1EBFA`: unsigned-char scalar extraction and cursor+1 for the
  unscaled numeric branch. Scaling metadata is identity (MUL1/DIV1/ADD0).
- The unit0/1 branch uses the same one-byte extraction plus the original explicit
  zero/one range check; see the initial contract for its precise MEVD coordinates.

For every enabled DID, require exactly `62 DIDhigh DIDlow value`. Raw0 is Off,
raw1 is On. Wrong echoes, negatives, truncation, extensions and all other values
are unavailable. Diesel numeric source rows have no explicit unit0/1 constraint;
restricting them to0/1 is a deliberate conservative display policy rather than
coercing an arbitrary nonzero request into On. The corresponding source
DIG_DDE_KOMBI labels independently identify value1 as active and0 as inactive;
no bitwise coercion is implemented. This is the ECU-reported request/condition,
not physical bulb verification. DTC count/status never establishes MIL state.

## Reproduction, implementation and checks

`scripts/recover_mil_contracts.py` consumes the pinned existing diagnostic
catalogue and original `sources/Ecu` PRGs with the existing BEST parser. It
accounts for every engine row, validates scalar metadata/scaling, and requires
reviewed whole-job fingerprints before generating
`coding_data/mil_contracts.json`. No runtime PRG parser, research application,
REA service or source executable is used. The new asset is included by the
existing coding_data resource inclusion rule.

`app/vehicle.py` loads the small bounded embedded asset, matches exact engine
identity/name/address and obtains its DID. Missing, ambiguous, unidentified or
mismatched engines send nothing; unresolved definitions display their specific
reason. The decoder retains the default4A69 parameter for compatibility and
accepts only one raw0/1 byte for the selected DID. Existing shared MIL freshness,
stale/unavailable states, dashboard/Diagnostics publication and lockout remain.

One-off offline checks exercised all62 exact rows: exactly53 generate the
correct source-selected request, while9 issue no request. All three DIDs passed
Off/On; negatives, wrong-DID, short/extended,2 and255 were rejected. Missing,
duplicate, unidentified and mismatched engine rows generated no traffic.
Deterministic reproduction produced byte-identical asset and manifest. Ruff
lint/format checks and mypy for the edited module pass; the parent increment
records the mandatory full-app gate and independent review separately.
No suite or tests directory was created.

Remaining concrete implementation: own the five recovered STATUS_BLOCK_LESEN
clear/define/read sequences exclusively, with checked cleanup, explicit uncertain
outcomes and read-only enforcement. Source tracing establishes no independent
direct/no-dynamic branch; disabling definition still reads F3nn. Trace alternate
MIL selection for DME9FF_R/EDMEI1 from their actual engine readers; reconcile
missing DME98_R/FCCU PRGs against other supplied sources; recover DoIP engine
address selection before enabling these MIL requests there. Those are open
implementation tasks, not hardware dependencies or a final support restriction.

## Post-PR14 block lifecycle trace

[The exact block follow-up](task-b-mil-block-recovery.md) now records the five
identical STATUS_BLOCK_LESEN paths and the Android fixed-F303 allocation/polling
contract. It disproves an assumed generic direct branch: disabling definition
still reads F3nn, not4A69. A fully owned dynamic clear/define/read/cleanup
operation, with explicit read-only rejection and uncertain-cleanup handling,
is the next concrete implementation prerequisite. No dynamic mutations or
additional runtime MIL rows are enabled by that investigation.
