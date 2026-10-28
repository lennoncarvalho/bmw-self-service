# Documentation and tooling audit plan

Date: 2026-10-28. Scope: initial cleanup and preparation for PR #8 review.
Runtime behavior changes and vehicle operations belong to subsequent work.

1. Read all 28 project-owned Markdown files; inventory local reference Markdown
   separately from dependencies and runtime caches.
2. Compare protocol claims with the current checkout, local source artifacts
   and primary protocol implementations. Record uncertainty and source identity.
3. Install selected upstream skills through pinned `npx skills` commands into
   `.agents/skills`; add focused project skills for uncovered BMW workflows.
   Review instructions, references, provenance and tool availability.
4. Repair `AGENTS.md`, resume guidance and misleading completion claims. Add a
   document index, findings, protocol corrections and owner decision queue.
   Preserve original research where it remains useful; label superseded content.
5. Validate skill structure, local links, source inventory, diff and full
   `scripts/preflight.sh`. Record what was and was not validated.

Acceptance: future sessions can discover the skills, distinguish evidence from
assumptions, reproduce tooling setup and begin a scoped connection/PR review.
No successful car connection, restorable write or production readiness is
claimed by this cleanup. No `tests/` directory is created.
