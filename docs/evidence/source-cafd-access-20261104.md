# Supplied CAFD/FAFP access — 2026-11-04

Status: **all 5,895 supplied CAFDs and 26 FAFPs decoded successfully**, without
vehicle traffic or execution of reference Java classes. The previous blanket
undecrypted/key-unknown limitation no longer applies to these supplied files.
This is source recovery, not a claim of named preset completeness or physical
coding validation.

## Actual access chain

REA `open_binary` identified the supplied
`PSdZ/bin/psdz/psdz-core.jar` as a ZIP artifact, SHA-256
`b6ac1c52cec398e3467bd7ec500f2cf2af3b7b09fdd5c5ad3c5b672d6eac488e`.
The advertised REA tools do not expose standalone Java class decompilation;
existing JDK21 `javap -p -c -constants` provided static bytecode for the focused
classes instead. No classes, application entry points, licence checks or target
runtime were executed.

Observed class/method chain:

1. `com.bmw.psdz.security.parsers.TldParser` reads `sec_security.lic` as XML and
   decodes the root text as base64 PKCS12; it is not a raw PKCS12 file on disk.
2. `com.bmw.psdz.security.impl.LicenseValidatorCrypto.openLicenseFile` calls
   `ResourceImgReader.getMetaData(pid)` and `genHashedPIN`. The PIN is the uppercase
   hexadecimal SHA1 of the corresponding metadata passphrase.
3. `ResourceImgReader` loads `bmw_logo.png` and `bmw_mini_logo.png` from
   `PSdZ/bin/psdz/resource.jar`. `ResourceParser.processImg` skips row zero and
   column zero, takes the low two bits of RGB, assembles six-bit values plus32,
   stops on underscore, then interprets the resulting string as hex bytes.
4. The first resource yields 368 encrypted metadata bytes; the second yields
   the 16-byte AES key. `BasicCrypto.decrypt` uses AES/CBC/PKCS5Padding with a
   zero16-byte IV. The decoded XML contains passphrase IDs0,1,20. Licence pid0
   selects the actual PIN, without guessing a password or probing variants.
5. The source PKCS12 decrypts successfully through existing OpenSSL and contains
   two private keys plus their certificate chains. The actual coding recipient
   certificate is CN=Codier-Encrypt, serial4E87, issued by FZGSec-CA. The decoder
   matches certificate/private public-key DER rather than assuming key order.
6. CAFD/FAFP `encryptedData` is CMS EnvelopedData. OpenSSL CMS decrypts it with
   that matching key/certificate; the resulting GZIP decompresses to XML whose
   root has `isEncrypted="false"`. Exact process-class ID/version is retained.

Additional source identities:

| Material | SHA-256 |
|---|---|
| `bin/psdz/resource.jar` | `bde492bcdec0e43ecd071527e3c84184fe9425604fe6c4c619010d7123bda869` |
| `security/sec_security.lic` | `07fa8c2dd1b5d7e0ba0010d55cd49c42d0adb95036fbd2fb772194e126d17b82` |

Static class dumps and the first plain CAFD/FAFP samples remain local in
`/Users/lennon/BMW-Tool/investigations/source-cafd-access-20261104/`.
Private keys/PIN are temporary development material, not generated runtime data.
CMS decryption and XML parsing succeeded; this work does not claim independent
validation of the embedded XML digital signatures.

## Reproducible development export

`scripts/recover_cafd_assets.py <PSdZ> <output> --include-fafp` implements the
observed chain using existing Qt image decoding, PyCryptodome and generic OpenSSL.
It never modifies original files or executes reference applications. Temporary
key/PIN files are permission-restricted and removed after the run.

The successful export is:
`/Users/lennon/BMW-Tool/investigations/source-cafd-access-20261104/definitions/`.
It contains **5,921 documents** in `cafd/` and `fafp/`, each stored as deterministic
compressed plain XML, plus `manifest.json`. The manifest retains each exact
ID/version, source filename/hash, decoded XML hash/size and gzip hash. Manifest
SHA-256 `952cbc921510889ba6b9762d8e47f7f860c8505ae8dd7a4ae740f48296beac26`.

- Compressed export bytes: 278,687,720.
- Decoded XML bytes represented: 11,211,813,531; no 11GB plaintext copy is required.
- All source files decoded; no per-file failure was silently skipped.
- The coding catalogue builder imports the verified export during development.
  Runtime receives the resulting standalone database, not licences, keys, images,
  JARs, XML decryptors or a dependency on `sources/`.

## What the recovered data actually establishes

All13 exact CAFDs listed for the owner's previously missing12 ECU targets were
found in the export and their decoded hashes checked. They provide actual group
addresses, source widths (`units` hexadecimal), storage starts/ends/masks, rules,
parameter values and the `sweHeader.ncdSignAddress` signature destination.
These are concrete metadata for complete exact coding reads and signature layout.

However, the supplied data is semantically trimmed: most function/group/parameter
names are literal `.`. For example, exact ENTRYNAV
`00000DED-003-015-037` has1,050 functions with only2 named; FLE
`0000180B-008-060-000` has1,329 with only2 named. Across the13 checked definitions,
only2 functions per file are named except ZBE, which has3. Decryption does **not**
restore names already removed before encryption. Existing APK definitions retain
named functions and curated presets; those remain preferred for exact matches.

Do not invent a new-version named preset by matching a trimmed function by
position. Subsequent REA recovery of the APK's `k.q.b(k.v)` establishes an actual
source selection rule: exact APK definition first, otherwise the immediately
lower patch with the same ID/major/minor. That evidenced rule can select a named
layout while the ECU's reported F101 identity remains exact and separate. An
exact trimmed ISTA XML must not hide the source application's named fallback.
Read groups, byte composition and signatures must consistently use the selected
layout and bind its material hash; do not combine arbitrary old names and new
positions. See the source-coding catalogue evidence and loader resolution API.
The full FAFPs are available as source rule inputs; this increment does not
implement their entire FA-to-FP rule engine.
