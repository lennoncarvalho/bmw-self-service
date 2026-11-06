# Development skills

Project rules are in [AGENTS.md](../AGENTS.md); product scope, source discoveries
and implementation steps live only in [plan.md](../plan.md), [docs.md](../docs.md)
and [tasks.md](../tasks.md). Load only the skills relevant to the work.

| Skill | Purpose |
|---|---|
| `spec-driven-development` | Implement against the compact plan/data/tasks without creating extra reports |
| `python-reviewer`, `python-error-handling` | Correctness, ownership, validation and partial failures |
| `pyside6-reviewer` plus `project-overlay.md` | Existing Qt Widgets/CarWorker architecture and visual checks |
| `sqlite` | Read-only assets, exact lookup keys and thread ownership |
| `bmw-enet-protocol` | Discovery, HSFZ/DoIP framing, UDS lifecycle and deadlines |
| `vehicle-write-safety` | Feature-specific baseline/intent/completion/recovery |
| `requirements-interview` | New product choices only; do not reopen answered decisions |
| `reverse-engineer-anything` | Supplied APK/managed/native artifacts and retained evidence |

Use each folder's `SKILL.md`. Project-authored guides and local overlays override
incompatible generic examples: no QML/model-view/asyncio migration, new test suite
or unsolicited dependency. Do not install tools or update all skills during a
feature change. `skills-lock.json`, `skill-provenance.json` and vendored licences
retain utility provenance; they do not claim that modified local guides match
upstream bytes. REA setup/recovery is needed only for an observed tool blocker;
its availability is checked from the live session, not old setup reports.
