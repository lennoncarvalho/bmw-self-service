# Source CAFD access — 2026-11-04

## Plan

Recover the supplied PSdZ data access path statically, using REA for the JAR
artifact identity and javap21 for class bytecode (no target class execution).
Implement a development-only decoder from the observed resource/PIN/PKCS12/CMS
chain, then export source-bound compressed plaintext definitions and a manifest.
The existing coding builder consumes these during development; the app must not
load originals, licences, images, JARs or decryptors at runtime. Exact stripped
names remain stripped; do not invent semantic labels or copy offsets from another
version. Preserve original files and report per-file decode failures explicitly.

## Result

Implemented `scripts/recover_cafd_assets.py` and decoded all5,895 CAFD plus26FAFP
files into a source-bound compressed XML export/manifest. Details, full source
identities, actual access chain and semantic trimming limits are in
`docs/evidence/source-cafd-access-20261104.md`. Coding-source agent owns the
plain-catalogue XML import and runtime integration. No new runtime crypto/tool
or source-folder dependency, commit, push or car traffic.
