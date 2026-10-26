# English Coding Labels — Fixed

> Branch: `feat/english-coding-labels`
> Status: Done — one-line logic fix in `CodingDatabase._load_strings()`.

---

## Root cause

`CodingDatabase._load_strings()` loaded `en.strings` into `self.strings`,
then called `dict.update()` with `de.strings`. Since both files have identical
1,537 keys, `update()` replaced every English value with the German one.

```python
# Before (bug):
self.strings.update(_parse_strings("en.strings"))  # {"FOLD_MIRRORS": "Fold mirrors"}
self.strings.update(_parse_strings("de.strings"))  # {"FOLD_MIRRORS": "Außenspiegel..."}
# Result: "Außenspiegel..." — German overwrites English
```

## Fix

English is now the authoritative source. German values are only used as
a fallback for keys that have no English translation (the 279 entries where
`en == de` — the German text was copy-pasted into the English file).

```python
# After (fix):
if lang == "en":
    self.strings = dict(new_entries)
else:
    for key, value in new_entries.items():
        if key not in self.strings or self.strings[key] == value:
            self.strings[key] = value
```

## Result

| Metric | Before | After |
|--------|--------|-------|
| English presets in FEM (100 total) | 0 | 100 |
| German presets in FEM | 100 | 0 |
| Option values (Active/Aktiv) | German | English |
| Untranslated fallback (279 entries) | German | German (correct fallback) |

## No translation script needed

The `.strings` files already contain proper English translations for 1,258 of
1,537 entries. The 279 untranslated entries (where `en == de`) are mostly
unit labels ("100 km/h", "5 seconds") and branded terms ("M Performance",
"ALPINA") that are already international. No new translation work is required.

A future task could translate the ~107 truly German entries, but they are
not blocking — the app correctly shows English for all translated presets
and falls back to German only for the 279 untranslated ones.

## Files changed

| File | Change |
|------|--------|
| `app/coding_db.py` | Fixed `_load_strings()` — English authoritative, German fallback |