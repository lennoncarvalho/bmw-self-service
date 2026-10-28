# Project skills and tooling

Updated 2026-10-28. Load the relevant `SKILL.md` directly; do not assume a skill
name in AGENTS.md registers tools. New project skills become discoverable on
the next turn. No global skills or host MCP settings were changed.

## Catalog

| Skill | Purpose | Origin |
|-------|---------|--------|
| [spec-driven-development](skills/spec-driven-development/SKILL.md) | Specs, evidence, plans and verification | Project-authored |
| [python-reviewer](skills/python-reviewer/SKILL.md) | Correctness, concurrency, resource/packaging review | Project-authored |
| [python-error-handling](skills/python-error-handling/SKILL.md) | Validation, error taxonomy and partial results | wshobson/agents |
| [pyside6-reviewer](skills/pyside6-reviewer/SKILL.md) | Qt review and implementation guidance | akiselev/qt-llm-template, locally adapted |
| [sqlite](skills/sqlite/SKILL.md) | Embedded database/query/threading review | Project-authored |
| [bmw-enet-protocol](skills/bmw-enet-protocol/SKILL.md) | Discovery, transport, UDS and frame lifecycle | Project-authored |
| [vehicle-write-safety](skills/vehicle-write-safety/SKILL.md) | Backup, intended state, readback and recovery | Project-authored from owner requirement |
| [requirements-interview](skills/requirements-interview/SKILL.md) | Feature/failure-behavior interview | Project-authored |
| [reverse-engineer-anything](skills/reverse-engineer-anything/SKILL.md) | APK/native/packaged artifact investigation | morluto/rea |

No independently verified BMW-specific public skill was selected as a source
of wire constants. The local skill instead requires traceable evidence. The
public `grill-me` entry inspected was a forwarding alias requiring another skill;
the local interview skill is self-contained. No unavailable `opencode` skill is
required for this repository.

## Pinned upstream installation

Installed using the Vercel Skills CLI **1.7.4**, project scope, agent `codex`.
The CLI installed ordinary files under `.agents/skills`. `skills-lock.json`
records repository, Git ref, upstream skill path and computed source hash.
Use existing compatible Node/npm (installation used Node 24.22.1):

```bash
npx --yes skills@1.7.4 add https://github.com/akiselev/qt-llm-template/tree/6855e82e0c371d599b25c60f218c7f881939e4be/.claude/skills/qt-code-review --skill pyside6-reviewer --agent codex --yes
npx --yes skills@1.7.4 add https://github.com/wshobson/agents/tree/0874a27b17a22e2b7c2e2bcd725768e0803cad06/plugins/python-development/skills/python-error-handling --skill python-error-handling --agent codex --yes
npx --yes skills@1.7.4 add https://github.com/morluto/rea/tree/160d821ac9a0310afcb8d1fc427862dd6508add5/.agents/skills/reverse-engineer-anything --skill reverse-engineer-anything --agent codex --yes
npx --yes skills@1.7.4 list --agent codex
```

See [Skills CLI source](https://github.com/vercel-labs/skills) for command
behavior. Do not run blanket updates during a feature change. Review upstream
changes and reapply local adaptations deliberately; a restore/update can replace
those files. Keep project-authored skills under version control.

The Qt skill's seven `references/...` links pointed to files actually shipped in
its root directory. They were corrected, and
[project-overlay.md](skills/pyside6-reviewer/project-overlay.md) was added as the
first routing instruction. The source hash in the lock remains upstream identity,
not a claim that the adapted files are byte-identical. Local installed-file
hashes and modifications are in `skill-provenance.json`.

Root upstream licenses were preserved inside the three vendored skill folders.
Whitespace-only line endings/trailing blanks in vendored files were normalized.
The PySide6 source uses Apache-2.0; the other two use MIT.

Generic examples do not authorize QML/model-view/asyncio migrations, new packages,
120-column formatting, strictness changes or a test suite. For writes, generic
“continue batch after failure” advice is subject to an evidenced recovery policy.
Skill helper scripts are references, not automatically executed hooks.

## REA readiness and limitations

The official [REA project](https://github.com/morluto/rea) distinguishes skill
instructions from runtime registration and analysis engines. Installed skill
metadata is version **49**, pinned to the `rea-agents-6.8.0` release commit and
matched to CLI **6.8.0**. Use actual tool schemas for the chosen runtime. The
acquired package remains in npm's runner cache.

Verified read-only commands from a trusted directory outside `sources/`:

```bash
npx --yes rea-agents@6.8.0 --help
npx --yes rea-agents@6.8.0 doctor --client codex --json
```

The help command succeeds. Doctor exits nonzero and reports no setup-owned
Codex MCP registration, no configured JADX headless MCP JAR, and no configured
Ghidra/Hopper/IDA engine. `java_home -V` found no usable JDK. A project skill
installation is not evidence those engines are ready. The live session has no
REA tools. Ordinary source/ZIP inspection remains available.

Before future decompilation, follow the installed connection/recovery guide,
select a supported available engine and inspect a concrete setup plan. Package
acquisition, runtime paths and installed tools vary by host. The REA skill’s package-runner examples were pinned to `6.8.0`, and its
`tool_count` metadata was set to the published 229 tools, matching the release
bundle entrypoint. These are recorded local adaptations; no runtime installation
is implied.

No unrelated Java,
Ghidra, Hopper, system packages or global MCP registrations were installed here.
No source binary was executed or modified. APK/native analysis will require
completing that setup; CLI fallback avoids a host configuration change but still
needs the chosen analysis engine.

Do not treat doctor’s missing global skill copy as a missing project skill.
Do not install a duplicate MCP server over a plugin-owned registration. Avoid
copying credentials or complete personal configuration into the repository.
