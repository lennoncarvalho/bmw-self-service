#!/usr/bin/env python3
"""
Translate DTC descriptions German→English using local Ollama (qwen2.5:3b).
Runs entirely offline on Apple Silicon. Resumable with checkpointing.

Usage:
    python3 translate_ollama.py              # translate all remaining
    python3 translate_ollama.py --check      # show progress
    python3 translate_ollama.py --sample 20  # test with 20 entries
"""

import sqlite3
import subprocess
import json
import time
import sys
import os

DB_PATH = "dtc_descriptions.db"
CHECKPOINT_FILE = ".dtc_translate_checkpoint"
MODEL = "qwen2.5:3b"
BATCH_SIZE = 50
COMMIT_EVERY = 5  # batches between commits

SYSTEM_PROMPT = """You are a BMW automotive diagnostic translator. Translate German DTC descriptions to English.

BMW terminology rules:
- "Klemme" = "Terminal" (not "clamp" or "fault code")
- "Leitungsunterbrechung" = "line disconnection" or "open circuit"
- "Kurzschluss" = "short circuit"
- "Bordnetz" = "vehicle electrical system"
- "Steuergerät" = "control unit"
- "Fehlerspeicher" = "fault memory"
- "entprellt" = "debounced"
- "unplausibel" = "implausible"
- "Unterspannung" = "undervoltage"
- "Überspannung" = "overvoltage"
- "Abschaltung" = "shutdown" or "deactivation"
- "Botschaft" = "message" (CAN bus message)
- "Datenbus" = "data bus"
- "Endstufenfehler" = "output stage fault"
- "sporadisch" = "sporadic" or "intermittent"
- "Fehlerort" = "fault location"
- "Fehlerart" = "fault type"

Translate each line. Return ONLY the translations, one per line, in the same order. No numbering, no explanations."""


def fetch_remaining(conn):
    """Return list of (code, text_de) that still need translation."""
    return conn.execute("""
        SELECT code, text_de FROM dtc_descriptions
        WHERE translated = 0
        AND table_type IN ('FORTTEXTE', 'FARTTEXTE', 'IORTTEXTE', 'IARTTEXTE')
        ORDER BY code
    """).fetchall()


def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            return f.read().strip()
    return None


def save_checkpoint(code):
    with open(CHECKPOINT_FILE + ".tmp", "w") as f:
        f.write(code)
    os.replace(CHECKPOINT_FILE + ".tmp", CHECKPOINT_FILE)


def clear_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)


def translate_batch(texts):
    """Translate a batch of German texts using Ollama. Returns list of English strings."""
    lines = "\n".join(texts)
    prompt = f"{SYSTEM_PROMPT}\n\n{lines}"

    try:
        result = subprocess.run(
            ["ollama", "run", MODEL, prompt],
            capture_output=True, text=True, timeout=120
        )
        output = result.stdout.strip()
        translations = [l.strip() for l in output.split("\n") if l.strip()]

        # Handle case where model returns fewer or more lines
        if len(translations) != len(texts):
            # Pad with None or truncate
            if len(translations) < len(texts):
                print(f"  WARNING: got {len(translations)} translations for {len(texts)} inputs, padding")
                translations.extend([None] * (len(texts) - len(translations)))
            else:
                translations = translations[:len(texts)]

        return translations
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT on batch, retrying with smaller batch...")
        return [None] * len(texts)
    except Exception as e:
        print(f"  ERROR: {e}")
        return [None] * len(texts)


def main():
    check_only = '--check' in sys.argv
    sample = None

    for i, arg in enumerate(sys.argv):
        if arg == '--sample' and i + 1 < len(sys.argv):
            sample = int(sys.argv[i + 1])

    if check_only:
        conn = sqlite3.connect(DB_PATH)
        remaining = len(fetch_remaining(conn))
        done = conn.execute("SELECT COUNT(*) FROM dtc_descriptions WHERE translated=1").fetchone()[0]
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

    # Resume
    start_from = load_checkpoint()
    start_idx = 0
    if start_from:
        for idx, (c, _) in enumerate(all_entries):
            if c >= start_from:
                start_idx = idx
                break
        print(f"Resuming from checkpoint '{start_from}' at index {start_idx:,}")

    if sample:
        effective_end = start_idx + sample
    else:
        effective_end = total

    to_translate = all_entries[start_idx:effective_end]
    total_to_do = len(to_translate)

    print(f"Entries to translate: {total_to_do:,}")
    print(f"Model: {MODEL}, batch size: {BATCH_SIZE}")
    print(f"Estimated: ~{total_to_do / BATCH_SIZE / 8:.0f} min at ~8 entries/sec")
    print()

    translated = 0
    errors = 0
    t_start = time.time()
    batch_count = 0

    for batch_start in range(0, len(to_translate), BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, len(to_translate))
        batch = to_translate[batch_start:batch_end]
        codes = [c for c, _ in batch]
        texts = [t for _, t in batch]

        results = translate_batch(texts)
        batch_count += 1

        # Write results
        for code, result in zip(codes, results):
            if result and len(result) > 1 and result != "None":
                conn.execute(
                    "UPDATE dtc_descriptions SET text_en = ?, translated = 1 WHERE code = ?",
                    (result, code)
                )
                translated += 1
            else:
                errors += 1

        # Checkpoint
        save_checkpoint(codes[-1])

        # Commit periodically
        if batch_count % COMMIT_EVERY == 0:
            conn.commit()

        # Progress
        pct = batch_end / len(to_translate) * 100
        elapsed = time.time() - t_start
        rate = translated / elapsed if elapsed > 0 else 0
        remaining_count = len(to_translate) - batch_end
        eta_min = (remaining_count / (rate * BATCH_SIZE)) if rate > 0 else 0
        print(f"  [{pct:5.1f}%] {translated:,}/{total_to_do:,} "
              f"({rate * BATCH_SIZE:.0f} entries/sec, ETA {eta_min:.0f}min) "
              f"last={codes[-1]}")

    conn.commit()

    remaining_after = len(fetch_remaining(conn))
    conn.close()

    if remaining_after == 0 or sample is not None:
        clear_checkpoint()

    elapsed = time.time() - t_start
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
            "SELECT code, text_de, text_en FROM dtc_descriptions WHERE translated=1 ORDER BY code LIMIT 6"
        ).fetchall()
        for code, de, en in samp:
            print(f"  {code}: {de[:50]}")
            print(f"  {'':8s}→ {en[:70]}")


if __name__ == '__main__':
    main()