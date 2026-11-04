# Source database access investigation — 2026-11-04

Owner request: reuse supplied databases and packages; do not replace missing
investigation with guessed constants or assistant-specific scope restrictions.
This slice owns only new source-access evidence and a narrowly useful development
extractor if the access contract is actually recovered. No car traffic or target
execution, original modifications, full database copy, runtime sources dependency,
new test suite or Git changes are part of the investigation.

## Plan

1. Inspect the restored SQLite connector assembly with REA to recover database
   access/password settings and exact managed/native boundary.
2. Consult existing reference implementation source for the matching codec.
3. Verify access read-only on the supplied DiagDocDb using existing local tools;
   do not claim encryption from the header alone or invent a password.
4. If access is established, extract a bounded portable text/model subset with
   source identity and a development-only script. Otherwise record the concrete
   tool/codec/key blocker and next useful recovery step.

## Completed source access and implementation

Recovered the RC4/read-only access contract from the existing pinned reference
and REA-inspected connector; the supplied encrypted database opens successfully.
Implemented `scripts/recover_ista_texts.py`, generated the 41 MB ordinary SQLite
runtime asset, and implemented `app/diagnostic_texts.py` exact-identity lookups.
Source identity, REA evidence, schemas, mapping cautions, counts and offline checks
are in `docs/evidence/source-database-access-20261104.md`.

Root integrates the new lookup into the diagnostic/UI path and owns final full
app preflight/review. No commit, push, app-source dependency or car traffic here.
