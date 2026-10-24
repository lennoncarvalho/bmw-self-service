#!/usr/bin/env python3
"""
Batch-translate DTC descriptions: German → English via MyMemory (free, no key).
Resumable — safe to interrupt and re-run. Multi-threaded.

Usage:
    python3 translate_dtc.py                     # translate all
    python3 translate_dtc.py --check             # show count remaining
    python3 translate_dtc.py --sample 10         # translate only 10 entries (test)
"""

import sqlite3
import time
import sys
import os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

DB_PATH = "dtc_descriptions.db"
CHECKPOINT_FILE = ".dtc_translate_checkpoint"
API_URL = "https://api.mymemory.translated.net/get"
WORKERS = 5               # concurrent threads
REQUEST_DELAY = 0.3       # seconds between requests per thread (~17 req/s total)
COMMIT_EVERY = 200        # commit to DB every N translations


def fetch_remaining(conn):
    """Return list of (code, text_de) that still need translation."""
    return conn.execute("""
        SELECT code, text_de FROM dtc_descriptions
        WHERE translated = 0
        AND table_type IN ('FORTTEXTE', 'FARTTEXTE', 'IORTTEXTE', 'IARTTEXTE')
        ORDER BY code
    """).fetchall()


def load_checkpoint():
    """Return the last translated code, or None."""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            return f.read().strip()
    return None


def save_checkpoint(code):
    """Save the last successfully translated code."""
    with open(CHECKPOINT_FILE + ".tmp", "w") as f:
        f.write(code)
    os.replace(CHECKPOINT_FILE + ".tmp", CHECKPOINT_FILE)


def clear_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)


def translate_one(code, text):
    """Translate a single text via MyMemory. Returns (code, text_en) or (code, None)."""
    try:
        r = requests.get(API_URL, params={
            "q": text,
            "langpair": "de|en",
            "de": "bmw-dtc-extractor@tool.local"
        }, timeout=15)
        js = r.json()
        if js.get("responseStatus") == 200:
            return (code, js["responseData"]["translatedText"])
        else:
            print(f"  API warning [{code}]: {js.get('responseDetails', js.get('responseStatus'))}")
            return (code, None)
    except Exception as e:
        print(f"  Network error [{code}]: {e}")
        return (code, None)


def main():
    # Parse args
    limit = None
    check_only = False
    sample = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--limit':
            limit = int(args[i+1]); i += 2
        elif args[i] == '--sample':
            sample = int(args[i+1]); i += 2
        elif args[i] == '--check':
            check_only = True; i += 1
        else:
            i += 1

    if check_only:
        conn = sqlite3.connect(DB_PATH)
        remaining = len(fetch_remaining(conn))
        done = conn.execute(
            "SELECT COUNT(*) FROM dtc_descriptions WHERE translated=1"
        ).fetchone()[0]
        conn.close()
        print(f"Translated: {done:,}")
        print(f"Remaining:  {remaining:,}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    all_entries = fetch_remaining(conn)
    total = len(all_entries)

    if total == 0:
        print("All entries already translated.")
        conn.close()
        clear_checkpoint()
        return

    # Resume from checkpoint
    start_from = load_checkpoint()
    if start_from:
        start_idx = 0
        for idx, (c, _) in enumerate(all_entries):
            if c >= start_from:
                start_idx = idx
                break
        print(f"Resuming from checkpoint '{start_from}' at index {start_idx:,}")
    else:
        start_idx = 0

    if sample:
        effective_end = start_idx + sample
        total_to_do = sample
    elif limit:
        effective_end = start_idx + limit
        total_to_do = limit
    else:
        effective_end = total
        total_to_do = total - start_idx

    to_translate = all_entries[start_idx:effective_end]

    print(f"Entries to translate: {total_to_do:,}")
    print(f"Workers: {WORKERS}, delay: {REQUEST_DELAY}s/req")
    rate = WORKERS / REQUEST_DELAY
    eta_min = total_to_do / rate / 60
    print(f"~{rate:.0f} req/s, ETA: ~{eta_min:.0f} min")
    print()

    # Translate
    translated = 0
    errors = 0
    batch_errors = 0
    t_start = time.time()
    last_commit = time.time()

    # Process in batches for checkpointing
    BATCH = 1000
    for batch_start in range(0, len(to_translate), BATCH):
        batch_end = min(batch_start + BATCH, len(to_translate))
        batch = to_translate[batch_start:batch_end]

        futures = {}
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            for i, (code, text) in enumerate(batch):
                # Stagger submissions for rate limiting
                time.sleep(REQUEST_DELAY / WORKERS)
                future = pool.submit(translate_one, code, text)
                futures[future] = code

        # Collect results
        for future in as_completed(futures):
            code, result = future.result()
            if result:
                conn.execute(
                    "UPDATE dtc_descriptions SET text_en = ?, translated = 1 WHERE code = ?",
                    (result, code)
                )
                translated += 1
            else:
                errors += 1
                batch_errors += 1

        # Save checkpoint
        last_code = batch[-1][0]
        save_checkpoint(last_code)

        # Commit periodically
        conn.commit()

        # Progress
        pct = (batch_start + len(batch)) / len(to_translate) * 100
        elapsed = time.time() - t_start
        actual_rate = translated / elapsed * 60 if elapsed > 0 else 0
        remaining_count = len(to_translate) - batch_end
        eta = remaining_count / actual_rate * 60 if actual_rate > 0 else 0
        print(f"  [{pct:5.1f}%] {translated:,}/{total_to_do:,} "
              f"({actual_rate:.0f}/min, {batch_errors} errs, ETA {eta:.0f}s) "
              f"last={last_code}")

        if batch_errors > 50:
            print(f"\n  *** Too many errors ({batch_errors}), stopping.")
            print(f"  Re-run to resume from checkpoint.")
            break
        batch_errors = 0

    elapsed = time.time() - t_start
    conn.commit()

    # Final stats
    remaining_after = len(fetch_remaining(conn))
    conn.close()

    if remaining_after == 0 or (sample is not None):
        clear_checkpoint()

    print(f"\n{'='*50}")
    print(f"Time:       {elapsed/60:.1f} min")
    print(f"Translated: {translated:,}")
    print(f"Errors:     {errors:,}")
    print(f"Remaining:  {remaining_after:,}")
    if remaining_after > 0:
        print(f"Re-run to continue.")

    # Show samples
    if translated > 0:
        print(f"\nSample translations:")
        samp = sqlite3.connect(DB_PATH).execute(
            "SELECT code, text_de, text_en FROM dtc_descriptions WHERE translated=1 ORDER BY code LIMIT 8"
        ).fetchall()
        for code, de, en in samp:
            print(f"  {code}: {de[:55]}")
            print(f"  {'':8s}→ {en[:70]}")


if __name__ == '__main__':
    main()