# DTC Description Database — Extraction & Integration

> **Status:** Approach documented. Extraction script TBD.

---

## Source: BMW PRG Files

Every BMW PRG file contains embedded fault code description tables. For example,
NBT.PRG alone has 120+ fault descriptions in its `FORTTEXTE` table:

| Code | German | English (translated) |
|------|--------|---------------------|
| `0xB7F805` | Verbindung Head-Unit zum DAB L-Band Antennenfuß: Leitungsunterbrechung | Head unit to DAB L-band antenna base: line disconnection |
| `0xB7F807` | Verbindung Head-Unit zum DAB L-Band Antennenfuß: Kurzschluss | Head unit to DAB L-band antenna base: short circuit |
| `0x026300` | Energiesparmode aktiv | Energy saving mode active |
| `0xB7F815` | HDD Kartenmaterial: Installation oder Update nötig | HDD map data: installation or update required |

## PRG Data Sources

| Source | Files | Coverage |
|--------|-------|----------|
| BMW Standard Tools 2024 | `C:\EDIABAS\Ecu\*.prg` | ~2,110 PRG files, all ECUs, all models |
| Motorcarsoft PRG Collection (2023) | ~2,000+ files | Same |

The PRG files are XOR-obfuscated with key `0xF7`. BimmerDaten's `decoderPrg.py`
handles the decoding.

## Extraction Script

Run once at build time — outputs a JSON file shipped with the app:

```python
#!/usr/bin/env python3
"""Extract DTC descriptions from all BMW PRG files."""
import sys, json, glob, os
sys.path.insert(0, 'BimmerDaten')
from decoderPrg import parse_prg

PRG_DIR = "C:/EDIABAS/Ecu"  # or wherever PRG files live
OUTPUT  = "dtc_descriptions.json"

def extract_all():
    db = {}
    prg_files = glob.glob(os.path.join(PRG_DIR, "*.prg"))
    
    for path in sorted(prg_files):
        try:
            prg = parse_prg(path)
            ecu = prg.info.ecu if hasattr(prg.info, 'ecu') else os.path.basename(path)
            
            for table in prg.tables:
                if table.name in ("FORTTEXTE", "IORTTEXTE"):
                    for row in table.rows:
                        code = row.values[0]          # "0xB7F805"
                        text = row.values[1]          # German description
                        flag = row.values[2] if len(row.values) > 2 else "0"
                        
                        # Some entries are test/dummy — skip those
                        if "Dummy" in text or "Test" in text:
                            continue
                        
                        db[code] = {
                            "text": text,
                            "ecu": ecu,
                            "lang": "de"
                        }
        except Exception as e:
            print(f"  Skipping {os.path.basename(path)}: {e}", file=sys.stderr)
    
    print(f"Extracted {len(db)} DTC descriptions from {len(prg_files)} PRG files")
    return db


def translate_batch(db: dict) -> dict:
    """Translate German descriptions to English using DeepL API."""
    import deepl
    
    # Collect unique texts
    texts = list(set(entry["text"] for entry in db.values()))
    print(f"Translating {len(texts)} unique texts...")
    
    # DeepL batch translate (free tier: 500K chars/month)
    translator = deepl.Translator(os.environ["DEEPL_API_KEY"])
    results = translator.translate_text(texts, source_lang="DE", target_lang="EN-US")
    
    # Build translation map
    de_to_en = {text: result.text for text, result in zip(texts, results)}
    
    # Apply translations
    for entry in db.values():
        entry["text_en"] = de_to_en.get(entry["text"], entry["text"])
    
    return db


if __name__ == "__main__":
    db = extract_all()
    
    # Optionally translate (comment out to keep German)
    # db = translate_batch(db)
    
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    
    print(f"Written {OUTPUT}")
```

## Offline Translation Alternative

If no API key is available, use `argos-translate` for offline German→English:

```bash
pip install argostranslate
python -c "import argostranslate.package; argostranslate.package.install_from_path('translate-de_en-1_7.argosmodel')"
```

```python
import argostranslate.translate

def translate_offline(text: str) -> str:
    return argostranslate.translate.translate(text, "de", "en")
```

## Output Format

```json
{
  "0xB7F805": {
    "text": "Verbindung Head-Unit zum DAB L-Band Antennenfuß: Leitungsunterbrechung",
    "text_en": "Head unit to DAB L-band antenna base: line disconnection",
    "ecu": "NBT",
    "lang": "de"
  },
  "0x026300": {
    "text": "Energiesparmode aktiv",
    "text_en": "Energy saving mode active",
    "ecu": "HU_MGU",
    "lang": "de"
  }
}
```

## Runtime Integration

```python
import json

class DtcDatabase:
    def __init__(self, path="dtc_descriptions.json"):
        with open(path) as f:
            self.bmw_db = json.load(f)
    
    def describe(self, code: str) -> str:
        """Look up a DTC code. Returns description or None."""
        # BMW hex DTCs from PRG
        hex_key = f"0x{code.upper()}"
        if hex_key in self.bmw_db:
            entry = self.bmw_db[hex_key]
            return entry.get("text_en") or entry["text"]
        
        # Standard OBD-II P-codes (P0xxx-P3xxx)
        return self._obd2_lookup(code)
    
    def _obd2_lookup(self, code: str) -> str | None:
        """Public domain OBD-II P-code descriptions."""
        # Source: SAE J2012 / ISO 15031-6
        OBD2_CODES = {
            "P0100": "Mass or Volume Air Flow Circuit Malfunction",
            "P0101": "Mass or Volume Air Flow Circuit Range/Performance Problem",
            # ... full public domain database
        }
        return OBD2_CODES.get(code.upper())


# Usage in diagnostics module
dtc_db = DtcDatabase()

def read_and_describe_dtcs(conn, ecu_addr: int) -> list:
    """Read DTCs and return list of (code, status, description)."""
    dtcs = []
    
    # Extended session
    conn.send_uds(ecu_addr, bytes([0x10, 0x03]))
    
    # Read DTCs by status mask
    resp = conn.send_uds(ecu_addr, bytes([0x19, 0x02, 0x08]))
    if resp[0] != 0x59:
        return dtcs
    
    # Parse: skip header, each DTC is 4 bytes
    offset = 2
    while offset + 4 <= len(resp):
        code = resp[offset:offset+3].hex().upper()
        status = resp[offset+3]
        desc = dtc_db.describe(code)
        dtcs.append((code, status, desc))
        offset += 4
    
    return dtcs
```

## DTC Code Format

BMW diagnostic trouble codes from PRG files use a 6-digit hex format:

```
0xB7F805
  ││││└── Specific fault code (0x05)
  │││└─── Fault sub-category
  ││└──── ECU identifier (0xF8 = headunit)
  └└───── Platform prefix (0xB7 = F/G-series)
```

When reading DTCs from the car via UDS 0x19, the response contains 3-byte
DTC codes. These map directly to the PRG table indices.

Standard OBD-II P-codes (P0xxx-P3xxx) use a different format and are
covered by a public domain database per SAE J2012.

## Estimated Size

| PRG files | Unique DTCs | JSON size |
|-----------|-------------|-----------|
| ~2,000 | ~15,000-25,000 | ~2-4 MB (uncompressed) |
| ~2,000 (translated) | ~15,000-25,000 | ~3-6 MB (uncompressed) |

Compress with gzip for distribution: ~500 KB-1 MB.