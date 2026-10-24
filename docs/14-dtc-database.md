# DTC Description Database — Extraction & Integration

> **Status:** Approach documented. One-time data preparation task.

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

## One-Time Data Preparation

This is a **one-time programming task**, not a build step. Run once to produce
a static SQLite database that ships as an app asset. Never re-run during builds.

**Output:** `dtc_descriptions.db` — shipped as a read-only app asset.

## Extraction + Translation Script

One-time run. Produces an indexed SQLite database. Commit the `.db` file — it's
a static asset, like an image or font.

```python
#!/usr/bin/env python3
"""One-time extraction: PRG files → SQLite DTC database."""
import sys, sqlite3, os, glob
sys.path.insert(0, 'BimmerDaten')
from decoderPrg import parse_prg

PRG_DIR  = "C:/EDIABAS/Ecu"
OUTPUT   = "dtc_descriptions.db"

def extract_for_ech_prg(db_path: str, prg_dir: str):
    """Parse all PRG files, write DTC entries to SQLite."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dtc_descriptions (
            code        TEXT PRIMARY KEY,   -- "B7F805"
            text_de     TEXT NOT NULL,       -- original German
            text_en     TEXT,                -- translated English
            ecu         TEXT,                -- which ECU this came from
            translated  INTEGER DEFAULT 0    -- 0=still German, 1=translated
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_code ON dtc_descriptions(code)")
    
    prg_files = sorted(glob.glob(os.path.join(prg_dir, "*.prg")))
    
    for path in prg_files:
        try:
            prg = parse_prg(path)
        except Exception:
            continue
        
        ecu = os.path.splitext(os.path.basename(path))[0]
        
        for table in prg.tables:
            if table.name in ("FORTTEXTE", "IORTTEXTE"):
                for row in table.rows:
                    code = row.values[0]  # "0xB7F805"
                    text = row.values[1]  # German description
                    
                    # Skip dummy/test entries
                    if any(w in text.lower() for w in ('dummy', 'test', 'nicht definiert')):
                        continue
                    
                    # Normalize code: "0xB7F805" -> "B7F805"
                    code = code.replace("0x", "").replace("0X", "").upper()
                    
                    conn.execute(
                        "INSERT OR IGNORE INTO dtc_descriptions(code, text_de, ecu) VALUES(?,?,?)",
                        (code, text, ecu)
                    )
    
    count = conn.execute("SELECT COUNT(*) FROM dtc_descriptions").fetchone()[0]
    conn.commit()
    conn.close()
    print(f"Extracted {count} DTC descriptions from {len(prg_files)} PRG files")
    return count


def translate_german_to_english(db_path: str):
    """Translate all German texts to English using DeepL."""
    import deepl
    
    conn = sqlite3.connect(db_path)
    
    # Get all untranslated texts
    rows = conn.execute(
        "SELECT code, text_de FROM dtc_descriptions WHERE translated = 0"
    ).fetchall()
    
    if not rows:
        print("All entries already translated.")
        conn.close()
        return
    
    print(f"Translating {len(rows)} entries via DeepL...")
    translator = deepl.Translator(os.environ["DEEPL_API_KEY"])
    codes, texts = zip(*rows)
    
    results = translator.translate_text(list(texts), source_lang="DE", target_lang="EN-US")
    
    for code, result in zip(codes, results):
        conn.execute(
            "UPDATE dtc_descriptions SET text_en = ?, translated = 1 WHERE code = ?",
            (result.text, code)
        )
    
    conn.commit()
    conn.close()
    print(f"Translated {len(rows)} entries.")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--extract", action="store_true", help="Extract from PRG files")
    p.add_argument("--translate", action="store_true", help="Translate DE→EN via DeepL")
    p.add_argument("--prg-dir", default=PRG_DIR)
    p.add_argument("--output", default=OUTPUT)
    args = p.parse_args()
    
    if args.extract:
        extract_for_ech_prg(args.output, args.prg_dir)
    
    if args.translate:
        translate_german_to_english(args.output)
    
    if not (args.extract or args.translate):
        p.print_help()
```

## Offline Translation Alternative

If no DeepL API key, use `argos-translate` for offline German→English:

```bash
pip install argostranslate
python -m argostranslate.package install translate-de_en
```

```python
import argostranslate.translate

def translate_offline(text: str) -> str:
    return argostranslate.translate.translate(text, "de", "en")
```

## SQLite Schema

```sql
CREATE TABLE dtc_descriptions (
    code        TEXT PRIMARY KEY,   -- "B7F805"
    text_de     TEXT NOT NULL,      -- original German
    text_en     TEXT,               -- translated English
    ecu         TEXT,               -- ECU name (e.g. "NBT", "DME")
    translated  INTEGER DEFAULT 0
);
CREATE INDEX idx_code ON dtc_descriptions(code);
```

## Runtime Integration

```python
import sqlite3

class DtcDatabase:
    def __init__(self, db_path="assets/dtc_descriptions.db"):
        # Read-only connection — no writes, thread-safe
        self.conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    
    def describe(self, code: str) -> str | None:
        """Look up a DTC code. O(1) indexed lookup."""
        code = code.upper().replace("0X", "").replace("0x", "")
        
        # Try BMW database first
        row = self.conn.execute(
            "SELECT text_en, text_de FROM dtc_descriptions WHERE code = ?",
            (code,)
        ).fetchone()
        
        if row:
            return row[0] or row[1]  # English if translated, else German
        
        # Fallback: standard OBD-II P-codes
        return self._obd2_lookup(code)
    
    def _obd2_lookup(self, code: str) -> str | None:
        return OBD2_CODES.get(code)  # public domain dict


# Usage — single connection, used everywhere
dtc_db = DtcDatabase()

def read_and_describe_dtcs(conn, ecu_addr: int) -> list[tuple]:
    """Read DTCs and return (code, status, description, ecu)."""
    dtcs = []
    conn.send_uds(ecu_addr, bytes([0x10, 0x03]))
    resp = conn.send_uds(ecu_addr, bytes([0x19, 0x02, 0x08]))
    if resp[0] != 0x59:
        return dtcs
    
    offset = 2
    while offset + 4 <= len(resp):
        code = resp[offset:offset+3].hex().upper()
        status = resp[offset+3]
        desc = dtc_db.describe(code) or "(no description)"
        dtcs.append((code, status, desc))
        offset += 4
    
    return dtcs
```

## Why SQLite over JSON

| Factor | SQLite | JSON |
|--------|--------|------|
| Lookup | O(1) indexed | O(n) scan or O(1) with full load into dict |
| Memory | Queries on disk, no full load | Must load entire file into RAM |
| Startup | Instant, no parsing | Must parse entire file |
| Size | ~2-4 MB uncompressed | ~3-6 MB uncompressed |
| Shipping | Single file, read-only mode | Single file |

For ~20K entries, SQLite is measurably faster at cold start and uses zero
heap for the database itself.

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