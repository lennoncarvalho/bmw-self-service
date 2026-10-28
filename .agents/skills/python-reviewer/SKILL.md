---
name: python-reviewer
description: Review Python changes for correctness, resource ownership, concurrency, data integrity and packaging in BMW Self Service.
---

# Python correctness review

Read `AGENTS.md` and the affected spec plus audit corrections. Start from the
actual diff and trace callers, results and failure paths before suggesting edits.

Check concrete failure triggers: truncated/empty input before indexing, checked
positive and negative protocol responses, bounds and integer widths, resource
cleanup on every exit, socket/thread ownership, shutdown races, stale callbacks,
mutable shared values and partial batch outcomes. Logging must preserve useful
diagnostics while user messages remain actionable. Broad exception handlers must
not convert failed work into empty data or success.

For writes, load `vehicle-write-safety`; for Qt, load `pyside6-reviewer` and its
project overlay; for database code, load `sqlite`. The error-handling skill's
generic advice to continue batches applies only when independent operations can
safely continue; uncertain vehicle writes require an explicit recovery policy.
Do not add Pydantic, asyncio, a framework, or a test suite just because an
upstream example uses it.

Use the configured Python 3.13 target and 100-column style. Verify actual local
runtime and dependency versions rather than assuming the venv matches CI. Check
fresh-install imports and bundled resource paths, including launch outside the
repository. Do not loosen mypy or suppress real defects to turn the gate green.

Run `scripts/preflight.sh` over all targets after approved fixes. Findings need
file/line, trigger, consequence and remedy; distinguish regressions from older
defects. Static-check success cannot establish correct vehicle communication.
