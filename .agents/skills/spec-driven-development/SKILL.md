---
name: spec-driven-development
description: Keep implementation aligned with the compact BMW Self Service plan, source guide and tasks.
---

# Implementation workflow

Read `AGENTS.md`, `plan.md`, `tasks.md` and the relevant section of `docs.md`.
Inspect current code and source contracts; documentation is not proof of behavior.

1. Identify the concrete outcome and affected code. Use existing `tasks.md` for
   nontrivial implementation steps; a routine fix needs no new document.
2. Resolve protocol facts from supplied artifacts/data/jobs. Ask only for genuinely
   unresolved product choices. Preserve exact source identity/decoder coordinates.
3. Implement the recovered behavior through the existing architecture. Continue
   through integration, meaningful verification and correction of findings.
4. Exercise source/native/error boundaries and actual Qt flows as appropriate.
   Distinguish offline checks from physical observations; no automated suite.
5. Run full `scripts/preflight.sh` before pushing. Deliver a concise result/PR.

Update only the relevant canonical document when useful facts or steps change.
Do not create specs, per-PR/session reports, handoffs, status indexes or Markdown
wrappers for evidence. Remove obsolete text; do not retain correction histories.
Keep raw machine-readable evidence when it actually supports builds/decoders;
large output and scratch checks belong outside the repository.
