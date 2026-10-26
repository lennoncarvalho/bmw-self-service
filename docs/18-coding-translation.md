# English Coding Labels — Translation Spec

> Branch: `feat/english-coding-labels`
> Status: Planning. Do not start coding.

---

## Problem

The Easy Coding page shows German text for many option names and value labels.
The `coding_data/en.strings` file has 1537 entries, but 279 of them have
`en == de` — the German text was copied into the English file without
translation.

Example: a user sees "Außenspiegel automatisch ein-/ausklappen" instead of
"Auto-fold exterior mirrors."

## Scope

| File | Entries | German (en==de) | Truly German text | Used in UI presets |
|------|---------|----------------|-------------------|---------------------|
| `en.strings` | 1,537 | 279 | ~107 | ~19 |

Of the 279 untranslated entries, 172 are already international:
- `100 km/h`, `1000 ms`, `NORMAL`, `Orange` — same in German and English
- These need no translation

The remaining ~107 contain German words that should be translated.

## Approach

**One-off script, same pattern as DTC translation.**

The `translate_ollama.py` script in the repo root translated 71,439 DTC entries
from German to English using Ollama with `qwen2.5:3b`. We use the same approach
for the coding labels — a one-time, offline translation run.

### Script: `translate_coding_labels.py`

1. Read `coding_data/de.strings` and `coding_data/en.strings`
2. Find entries where `en == de` AND the text contains German words
   (filter out numbers-only, units-only, and international abbreviations)
3. For each German entry, get the English translation from the LLM
4. Update `en.strings` in place, preserving:
   - All existing translated entries (untouched)
   - Apple `.strings` file format (key = value pairs)
   - File encoding (UTF-8)
   - Original line ordering

### LLM prompt

```
Translate this BMW coding option label from German to English.
Keep it concise and natural — these appear in a car coding UI.
Do not translate proper nouns (BMW, ALPINA, Rolls Royce, etc.).
Do not translate units (km/h, ms, Ah, etc.).

German: "{german_text}"
English:
```

### Dry-run mode

Before modifying the file, run with `--dry-run` to preview all translations.
The script outputs a table of old → new and waits for confirmation.

## Non-goals

- `fr.strings` (French) and `ja.strings` (Japanese) — out of scope
- Runtime translation — this is a one-off static data update
- Changing the `.strings` file format
- Adding new keys or removing existing ones

## Files

| File | Action |
|------|--------|
| `translate_coding_labels.py` | New — one-off translation script |
| `coding_data/en.strings` | Modified — ~107 German entries translated to English |
| `docs/18-coding-translation.md` | New — documents the process and results |

## Verification

1. `python translate_coding_labels.py --dry-run` — preview all 107 translations
2. `python translate_coding_labels.py` — apply translations
3. `git diff coding_data/en.strings` — review changes manually
4. Launch app in DEMO mode → Easy Coding → verify labels are English

## Risk

| Risk | Mitigation |
|------|-----------|
| LLM mistranslates technical BMW terms | Dry-run review before applying |
| String escaping issues in `.strings` format | Use `re.escape` / `json.dumps` for safe writing |
| Script fails mid-translation | Process one key at a time; existing entries untouched |
| `fr.strings` / `ja.strings` also need updates | Out of scope for this task; documented as future work |

## Dependencies

- Ollama with `qwen2.5:3b` model (already available — used for DTC translation)
- No new Python packages needed (uses `subprocess` to call `ollama` CLI)

## Task list

- [ ] Write `translate_coding_labels.py` with dry-run mode
- [ ] Run dry-run, review the 107 translations
- [ ] Apply translations to `en.strings`
- [ ] Launch app in DEMO mode, verify labels are English
- [ ] Document process in `docs/18-coding-translation.md`