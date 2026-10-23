# BimmerCode Encryption Key — Extracted & Verified

> **Date:** 2026-10-23
> **Source:** Decompiled from `ExternalLib` and `FileDecompression` classes

---

## The Keys

Extracted from `de.appomotive.bimmercode.external.ExternalLib`:

```java
// ExternalLib.c() — AES-128 key (hex string)
public static String c() {
    return "244326462948404D635166546A576E5A";
}

// ExternalLib.d() — AES IV (hex string)
public static String d() {
    return "7639792442264529482B4D6251655468";
}
```

| Parameter | Hex String | Raw Bytes (16 bytes) |
|-----------|-----------|---------------------|
| AES Key | `244326462948404D635166546A576E5A` | `24 43 26 46 29 48 40 4D 63 51 66 54 6A 57 6E 5A` |
| AES IV | `7639792442264529482B4D6251655468` | `76 39 79 24 42 26 45 29 48 2B 4D 62 51 65 54 68` |

## Algorithm

```
AES-128 / CBC / PKCS5Padding
  ↓
Optional GZIP decompress (try first, fall back to raw)
  ↓
JSON plaintext
```

## Decryption Code (Python)

```python
from Crypto.Cipher import AES
import gzip

KEY = bytes.fromhex("244326462948404D635166546A576E5A")
IV  = bytes.fromhex("7639792442264529482B4D6251655468")

def decrypt_bimmercode_enc(filepath: str) -> bytes:
    """Decrypt any .enc file from BimmerCode's database."""
    with open(filepath, "rb") as f:
        encrypted = f.read()
    
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    decrypted = cipher.decrypt(encrypted)
    
    # Remove PKCS5/PKCS7 padding
    pad_len = decrypted[-1]
    if 1 <= pad_len <= 16:
        decrypted = decrypted[:-pad_len]
    
    # Try GZIP decompress, fall back to raw
    try:
        return gzip.decompress(decrypted)
    except:
        return decrypted
```

## Decryption Code (JavaScript/Node.js)

```javascript
const crypto = require('crypto');
const zlib = require('zlib');

const KEY = Buffer.from("244326462948404D635166546A576E5A", "hex");
const IV  = Buffer.from("7639792442264529482B4D6251655468", "hex");

function decryptBimmercodeEnc(encryptedBuffer) {
    const decipher = crypto.createDecipheriv('aes-128-cbc', KEY, IV);
    decipher.setAutoPadding(true);
    let decrypted = Buffer.concat([
        decipher.update(encryptedBuffer),
        decipher.final()
    ]);
    
    // Try GZIP decompress
    try {
        return zlib.gunzipSync(decrypted);
    } catch {
        return decrypted;
    }
}
```

## How It Was Found

The decryption chain was traced through decompiled BimmerCode classes:

```
q(File) constructor
  → FileDecompression.b(file, ExternalLib.c(), ExternalLib.d())
    → e(keyStr)  — hex string → byte[]
    → e(ivStr)   — hex string → byte[]
    → new SecretKeySpec(key, "AES")
    → new IvParameterSpec(iv)
    → Cipher.getInstance("AES/CBC/PKCS5Padding")
    → cipher.init(DECRYPT_MODE, key, iv)
    → cipher.doFinal(fileBytes)
    → a(result)  — GZIP decompress (with IOException fallback to raw bytes)
    → return byte[] (plaintext JSON)
```

Key classes:
- `de.appomotive.bimmercode.external.ExternalLib` — stores key and IV
- `de.appomotive.bimmercode.asynctasks.FileDecompression` — decrypt + decompress
- `de.appomotive.bimmercode.exceptions.CryptoException` — error handling
- `de.appomotive.bimmercode.exceptions.KeyStorageException` — key retrieval failure

## Additional Keys Found

`ExternalLib` contains additional keys for other purposes:

| Method | Value | Likely Use |
|--------|-------|------------|
| `b()` | `3c9c328120efcc7e` | License server auth token |
| `f()` | `D79BC058046DBD081FE8C1EAF05791C3` | Data integrity checksum |
| `g()` | `FB69C011B6197B7245E40CF84BF209D2` | Another checksum |
| `h()` | `4cdedbf67cfd5d3d81dded7edfdd32d12e281b29befac5ab28e7cc3d5e3c01c9` | SHA-256 hash (license?) |

## Alternative Decrypt Method (Stream, AES/CBC/PKCS7Padding)

`FileDecompression.c()` uses a different variant for streaming:

```java
// IV comes from first 16 bytes of the encrypted stream
byte[] iv = new byte[16];
inputStream.read(iv);

// Key comes from Base64-encoded string
byte[] key = Base64.decode(keyStr, 0);

// AES/CBC/PKCS7Padding
Cipher cipher = Cipher.getInstance("AES/CBC/PKCS7Padding");
cipher.init(DECRYPT_MODE, new SecretKeySpec(key, "AES"), new IvParameterSpec(iv));
```

This variant is used for some data streams where the IV is prepended to
the encrypted data rather than stored separately.

## Verified: All Files Decrypt Successfully

Tested against the full bimmercode_data.zip database:

| File Type | Count | Decryption Status |
|-----------|-------|-------------------|
| CAFD variant files (`*.C*.enc`) | ~350 | ✓ All decrypt |
| CAFD root indexes (`*.enc`) | ~25 | ✓ All decrypt (no GZIP) |
| ECU list (`ecus.enc`) | 1 | ✓ Decrypts (80 KB JSON) |
| Coding-ECU info (`coding-ecu-infos.enc`) | 1 | ✓ Decrypts (19 KB JSON) |
| SWT translations (`swt.enc`) | 1 | ✓ Decrypts (202 KB JSON) |

## All ExternalLib Keys

```json
{
  "aes_key": "244326462948404D635166546A576E5A",
  "aes_iv": "7639792442264529482B4D6251655468",
  "license_token": "3c9c328120efcc7e",
  "checksum_1": "D79BC058046DBD081FE8C1EAF05791C3",
  "checksum_2": "FB69C011B6197B7245E40CF84BF209D2",
  "sha256_hash": "4cdedbf67cfd5d3d81dded7edfdd32d12e281b29befac5ab28e7cc3d5e3c01c9"
}
```