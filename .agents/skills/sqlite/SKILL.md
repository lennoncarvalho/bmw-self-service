---
name: sqlite
description: Inspect SQLite schemas, description lookup correctness and Python sqlite3 concurrency for the embedded diagnostic database.
---

# Embedded SQLite review

Read `docs/14-dtc-database.md` and inspect the actual schema with a read-only
connection. Use a properly escaped file URI and `mode=ro`; parameterize values.
Do not rebuild, translate, migrate or change journal mode on the shipped asset
as a side effect of a lookup or audit.

`mode=ro` does not remove Python connection thread affinity. Choose a documented
per-thread connection strategy or deliberate synchronization/lifetime design;
do not merely set `check_same_thread=False` and declare thread safety.
An application-level singleton need not mean one connection across threads.

Check lookup keys against ECU/variant and table semantics. `LIMIT 1` without a
specific table/context can select an unrelated description. A UDS DTC status
byte is not a fault-type byte; dictionary tables need their actual code types.
Unknown manufacturer-specific DTCs must remain unknown rather than receive a
guessed generic P-code description. Machine translations remain unverified.

Use `EXPLAIN QUERY PLAN` for performance claims. Ordinary B-tree indexed lookup
is logarithmic, not guaranteed O(1). Check missing/corrupt database behavior,
fallback distinctions, path resolution in packaged builds, connection close
ownership and whether read-only access requires existing WAL sidecars.
