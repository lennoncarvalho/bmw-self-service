#!/usr/bin/env python3
"""
One-time extraction: BMW PRG files → SQLite DTC database.

Run once to produce dtc_descriptions.db — a static app asset.
Never part of the app build process.

Usage:
    python3 extract_dtc.py --extract --prg-dir sources/Ecu
    python3 extract_dtc.py --translate           # DeepL German→English
"""

import sys, os, sqlite3, time, glob
from multiprocessing import Pool, cpu_count

sys.path.insert(0, os.path.join(os.path.dirname(__file__) or '.', 'BimmerDaten'))
from decoderPrg import parse_prg

# Tables to extract — fault descriptions, types, environment, class, P-codes
TABLE_NAMES = {
    'FORTTEXTE', 'IORTTEXTE',      # fault location (FOR=I for non-German)
    'FARTTEXTE', 'IARTTEXTE',      # fault type (FAR=IAR for non-German)
    'FARTTEXTEERWEITERT', 'IARTTEXTEERWEITERT',  # extended fault type
    'FARTTEXTEINDIVIDUELL',        # individual fault type variants
    'FUMWELTTEXTE', 'IUMWELTTEXTE',# environmental conditions
    'FEHLERKLASSE',                # fault class/severity
    'PCODETEXTE',                  # OBD-II P-code to BMW code mapping
    'HORTTEXTE', 'HARTTEXTE',      # variants
    'FARTYP',                      # fault type classification
    'FARTERWTEXTE',                # extended fault texts
    'FARTSTATUSTEXTE',             # fault status texts
    'STATDABKENTTEXTE',            # status texts
    'POSWHEBELTEXTE',              # position texts (e.g. gear lever)
}

SKIP_KEYWORDS = {'dummy', 'test', 'nicht belegt', 'nicht definiert',
                  'reserviert', 'unbenutzt', 'unbelegt', 'reserved', 'unused'}


def parse_prg_file(args):
    """Parse a single PRG file and extract DTC entries. Runs in worker process."""
    path, prg_dir = args
    fname = os.path.basename(path)
    entries = []
    
    try:
        prg = parse_prg(path)
    except Exception:
        return path, entries
    
    # Determine ECU name from PRG metadata or filename
    ecu = fname.rsplit('.', 1)[0]
    if hasattr(prg, 'info') and hasattr(prg.info, 'ecu') and prg.info.ecu:
        ecu = prg.info.ecu
    if hasattr(prg, 'info') and hasattr(prg.info, 'description') and prg.info.description:
        desc = prg.info.description.replace('\x00', '').strip()
        if desc:
            ecu = desc
    
    for table in prg.tables:
        if table.name not in TABLE_NAMES:
            continue
        
        table_type = table.name  # FORTTEXTE, FARTTEXTE, etc.
        
        for row in table.rows:
            if len(row.values) < 2:
                continue
            
            code = str(row.values[0]).strip()
            text = str(row.values[1]).strip()
            
            if not code or not text:
                continue
            
            # Skip obvious dummy/test entries
            text_lower = text.lower()
            if any(kw in text_lower for kw in SKIP_KEYWORDS):
                continue
            
            # Normalize code: "0xB7F805" → "B7F805"
            code = code.replace('0x', '').replace('0X', '').upper().strip()
            if not code or len(code) > 8:
                continue
            
            # Clean text: remove control chars, normalize whitespace
            text = text.replace('\x00', '').replace('\r', '').replace('\n', ' ').strip()
            text = ' '.join(text.split())  # collapse multiple spaces
            
            if len(text) < 3:
                continue
            
            entries.append((code, text, ecu, table_type))
    
    return path, entries


def extract_all(prg_dir, output_db, workers=None):
    """Extract DTC descriptions from all PRG files into SQLite."""
    if workers is None:
        workers = max(1, cpu_count() - 1)
    
    prg_files = sorted(
        glob.glob(os.path.join(prg_dir, '*.prg')) +
        glob.glob(os.path.join(prg_dir, '*.PRG'))
    )
    
    if not prg_files:
        print(f"No PRG files found in {prg_dir}")
        return
    
    print(f"Found {len(prg_files)} PRG files")
    print(f"Parsing with {workers} workers...")
    
    t0 = time.time()
    
    tasks = [(path, prg_dir) for path in prg_files]
    
    with Pool(workers) as pool:
        results = pool.map(parse_prg_file, tasks)
    
    parse_time = time.time() - t0
    print(f"Parsed in {parse_time:.1f}s")
    
    # Create SQLite database
    if os.path.exists(output_db):
        os.remove(output_db)
    
    conn = sqlite3.connect(output_db)
    conn.execute('PRAGMA journal_mode=OFF')
    conn.execute('PRAGMA synchronous=OFF')
    
    conn.execute('''
        CREATE TABLE dtc_descriptions (
            code        TEXT NOT NULL,     -- hex code, e.g. "B7F805"
            text_de     TEXT NOT NULL,     -- original German description
            text_en     TEXT,              -- English translation (filled later)
            ecu         TEXT,              -- source ECU name
            table_type  TEXT,              -- FORTTEXTE / FARTTEXTE / FEHLERKLASSE / ...
            translated  INTEGER DEFAULT 0,
            PRIMARY KEY (code, table_type)
        )
    ''')
    
    # Use an index on code for lookups (partial index for FORTTEXTE-type tables)
    conn.execute('CREATE INDEX idx_code ON dtc_descriptions(code)')
    conn.execute('CREATE INDEX idx_type ON dtc_descriptions(table_type)')
    
    total_entries = 0
    files_with_data = 0
    
    for path, entries in results:
        if entries:
            files_with_data += 1
            conn.executemany(
                'INSERT OR IGNORE INTO dtc_descriptions(code, text_de, ecu, table_type) '
                'VALUES(?,?,?,?)',
                entries
            )
            total_entries += len(entries)
    
    # Deduplicate: prefer FORTTEXTE over IORTTEXTE, keep the one with longest description
    conn.execute('''
        DELETE FROM dtc_descriptions WHERE rowid NOT IN (
            SELECT MIN(rowid) FROM dtc_descriptions
            GROUP BY code
            ORDER BY CASE table_type
                WHEN 'FORTTEXTE' THEN 0
                WHEN 'IORTTEXTE' THEN 1
                WHEN 'FARTTEXTE' THEN 2
                WHEN 'IARTTEXTE' THEN 3
                WHEN 'PCODETEXTE' THEN 4
                ELSE 5
            END
        )
    ''')
    
    conn.commit()
    
    final_count = conn.execute('SELECT COUNT(*) FROM dtc_descriptions').fetchone()[0]
    conn.execute('ANALYZE dtc_descriptions')
    conn.commit()
    conn.close()
    
    db_size_mb = os.path.getsize(output_db) / (1024 * 1024)
    
    print(f"Files with data: {files_with_data}/{len(prg_files)}")
    print(f"Raw entries:     {total_entries}")
    print(f"Unique DTCs:     {final_count}")
    print(f"Database size:   {db_size_mb:.1f} MB")
    print(f"Output:          {output_db}")


def translate_german_to_english(db_path):
    """Translate all German texts to English using DeepL API."""
    try:
        import deepl
    except ImportError:
        print("ERROR: deepl package not installed. Run: pip install deepl")
        return
    
    api_key = os.environ.get('DEEPL_API_KEY')
    if not api_key:
        print("ERROR: DEEPL_API_KEY environment variable not set")
        print("Get a free key at https://www.deepl.com/pro-api")
        return
    
    conn = sqlite3.connect(db_path)
    
    # Only translate FORTTEXTE and FARTTEXTE entries (the most useful for users)
    # Skip FEHLERKLASSE, UMWELTTEXTE etc. — technical metadata, not user-facing
    rows = conn.execute(
        """SELECT code, text_de FROM dtc_descriptions
           WHERE translated = 0
           AND table_type IN ('FORTTEXTE', 'FARTTEXTE', 'IORTTEXTE', 'IARTTEXTE')
           ORDER BY code"""
    ).fetchall()
    
    if not rows:
        print("All entries already translated.")
        conn.close()
        return
    
    print(f"Translating {len(rows)} entries via DeepL...")
    translator = deepl.Translator(api_key)
    codes, texts = zip(*rows)
    
    # DeepL batch translate in chunks of 50 (API limit)
    BATCH = 50
    total = len(texts)
    translated_count = 0
    
    for i in range(0, total, BATCH):
        batch_texts = list(texts[i:i + BATCH])
        batch_codes = codes[i:i + BATCH]
        
        try:
            results = translator.translate_text(batch_texts, source_lang='DE', target_lang='EN-US')
            for code, result in zip(batch_codes, results):
                conn.execute(
                    'UPDATE dtc_descriptions SET text_en = ?, translated = 1 WHERE code = ?',
                    (str(result.text), code)
                )
            translated_count += len(batch_texts)
            print(f"  {min(i + BATCH, total)}/{total} ({translated_count} translated)")
        except Exception as e:
            print(f"  Batch {i}-{i + BATCH} failed: {e}")
    
    conn.commit()
    conn.close()
    print(f"Done. {translated_count} entries translated.")


def translate_offline(db_path):
    """Translate using argostranslate (offline, free)."""
    try:
        import argostranslate.package
        import argostranslate.translate
    except ImportError:
        print("ERROR: argostranslate not installed.")
        print("Run: pip install argostranslate")
        print("Then: python -m argostranslate.package install translate-de_en")
        return
    
    conn = sqlite3.connect(db_path)
    
    rows = conn.execute(
        """SELECT code, text_de FROM dtc_descriptions
           WHERE translated = 0
           AND table_type IN ('FORTTEXTE', 'FARTTEXTE', 'IORTTEXTE', 'IARTTEXTE')
           ORDER BY code"""
    ).fetchall()
    
    if not rows:
        print("All entries already translated.")
        conn.close()
        return
    
    print(f"Translating {len(rows)} entries via argostranslate (offline)...")
    
    for i, (code, text) in enumerate(rows):
        try:
            result = argostranslate.translate.translate(text, 'de', 'en')
            conn.execute(
                'UPDATE dtc_descriptions SET text_en = ?, translated = 1 WHERE code = ?',
                (result, code)
            )
        except Exception:
            pass
        
        if (i + 1) % 500 == 0:
            conn.commit()
            print(f"  {i + 1}/{len(rows)}")
    
    conn.commit()
    conn.close()
    print(f"Done. {len(rows)} entries translated.")


def print_stats(db_path):
    """Show database statistics."""
    conn = sqlite3.connect(db_path)
    
    total = conn.execute('SELECT COUNT(*) FROM dtc_descriptions').fetchone()[0]
    by_type = conn.execute(
        'SELECT table_type, COUNT(*) FROM dtc_descriptions GROUP BY table_type ORDER BY COUNT(*) DESC'
    ).fetchall()
    translated = conn.execute(
        'SELECT COUNT(*) FROM dtc_descriptions WHERE translated = 1'
    ).fetchone()[0]
    sample = conn.execute(
        'SELECT code, text_de, text_en, ecu FROM dtc_descriptions WHERE table_type = "FORTTEXTE" LIMIT 10'
    ).fetchall()
    
    print(f"\n=== DTC Database Statistics ===")
    print(f"Total unique DTC entries: {total}")
    print(f"Translated (DE→EN):       {translated}")
    print(f"\nBy table type:")
    for ttype, count in by_type:
        print(f"  {ttype:<30s} {count:>6d}")
    
    print(f"\nSample FORTTEXTE entries:")
    for code, de, en, ecu in sample:
        print(f"  {code:<10s} [{ecu:<15s}] {de}")
        if en:
            print(f"  {'':10s} {'':17s}→ {en}")
    
    conn.close()


if __name__ == '__main__':
    import argparse
    
    p = argparse.ArgumentParser(
        description='One-time BMW DTC database extraction from PRG files'
    )
    p.add_argument('--extract', action='store_true',
                   help='Extract DTC descriptions from PRG files into SQLite')
    p.add_argument('--translate', action='store_true',
                   help='Translate German→English (requires DEEPL_API_KEY or argostranslate)')
    p.add_argument('--translate-offline', action='store_true',
                   help='Translate using argostranslate (offline, no API key needed)')
    p.add_argument('--stats', action='store_true',
                   help='Show database statistics')
    p.add_argument('--prg-dir', default='sources/Ecu',
                   help='Directory containing PRG files (default: sources/Ecu)')
    p.add_argument('--output', default='dtc_descriptions.db',
                   help='Output SQLite database (default: dtc_descriptions.db)')
    p.add_argument('--workers', type=int, default=None,
                   help='Number of worker processes (default: CPU count - 1)')
    
    args = p.parse_args()
    
    if args.extract:
        extract_all(args.prg_dir, args.output, args.workers)
        print_stats(args.output)
    
    if args.translate:
        translate_german_to_english(args.output)
        print_stats(args.output)
    
    if args.translate_offline:
        translate_offline(args.output)
        print_stats(args.output)
    
    if args.stats:
        print_stats(args.output)
    
    if not (args.extract or args.translate or args.translate_offline or args.stats):
        p.print_help()