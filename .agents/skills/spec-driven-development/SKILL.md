---
name: spec-driven-development
description: Maintain evidence-backed specs, implementation plans and verification for BMW Self Service; use at session start and before nontrivial app changes.
---

# Spec-driven development

Read `AGENTS.md`, `docs/README.md`, `docs/19-audit-and-readiness.md` and the
relevant feature spec before implementation. Historical research and completed
checkboxes do not prove vehicle behavior. User decisions define the product;
reproducible evidence defines protocol facts.

1. Identify the requested outcome, affected files and acceptance criteria.
2. List conflicting claims and missing evidence. Ask about behavior that only
   the owner can decide; investigate facts in the repository or primary sources.
3. Record the plan in `tasks/` for multi-file/module work. Keep unapproved
   product choices explicitly pending; progress with independent authorized work.
4. Implement one module at a time. Trace changes to the spec and evidence.
   Update the spec when evidence disproves it; do not copy a known-bad example.
5. Verify real behavior at the appropriate boundary: UI/demo, recorded bytes,
   and vehicle validation are different forms of evidence. Respect the current
   no-automated-test-suite policy; flag its release implications explicitly.
6. Run `scripts/preflight.sh` across all app targets. Report all three results
   and limitations. A green gate establishes static checks, not correct car I/O.

Use evidence labels: **observed locally**, **primary implementation reference**,
**historical report**, **hypothesis**, **owner decision pending**. A protocol
claim needs artifact/version/hash and class/method/offset or capture location.
Never invent missing REA evidence or convert simulation data into car proof.

For reviews, present actionable findings with trigger, consequence, source
location and suggested resolution; separate new PR regressions from older
blockers. Do not automatically fix, merge or publish during a read-only review.
