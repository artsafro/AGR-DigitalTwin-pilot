# AGR-DigitalTwin — agent instructions

Shared by every agent (Claude Code, Codex, Antigravity). Agent-specific notes:
`CLAUDE.md`, `docs/agents/codex.md`, `GEMINI.md`. Talk to the user in Russian [D088]; write code,
commands, identifiers and docs in English.

A worker reads three things: this file, `docs/domain/areas/<area>.md`, and the card.
Details: `docs/agents/agents-reference.md`.
For NPM/OKS tasks read `routes/npm-oks.md`; call `agr --help` before writing a script.
For Revit-source tasks read `routes/revit-intake.md` (read-only intake first, [D237]).

## Goal

Produce delivery models from architectural sources — NPM and VPM per the Moscow
regulation, later IFC — for buildings (OKS), Ground, MAF (GroundEl), Flora and UCX
collisions, plus the interactive Unreal experience. Priorities, in order:
1. Architectural accuracy 2. Correct scale and transforms 3. Material correctness
4. Performance 5. Visual fidelity.

## Where things are

Read on demand. Read the domain file that matches the task before production work. Where sources
disagree (`docs/domain/conflicts.md`), ask the user; never pick a side silently.

- State: `docs/PROJECT_STATE.md` (generated: `python tools/state/project_state.py`).
- Every dated user decision (`D<n>`): `docs/decisions.md`.
- Fact locations: `docs/agents/WORKFLOW.md`, "Memory map".
- Who owns what (Claude / Codex / Antigravity): `docs/agents/ROLES.md`.
- Task loop, handoff, experience capture, snags: `docs/agents/WORKFLOW.md`.
- Review/author receipts: `docs/agents/REVIEW_CHECKLIST.md`, `docs/agents/WORKFLOW.md#before-requesting-review-author`.
- Tools/MCP status: `docs/agents/CAPABILITIES.md`.
- Production rules with citations (NPM/VPM, geometry, UV, materials, export, validation): `docs/domain/`.
- Open conflicts between sources: `docs/domain/conflicts.md`.
- Pipeline stages and their status: `docs/pipeline.md`.
- Unsolved work: `docs/backlog.md`.
- Archive (tag `archive/2026-11`): `docs/ARCHIVE.md`.
- Accepted cases and lessons: `docs/cases.md`.
- Terms: `GLOSSARY.md`.
- Naming (scripts, jobs, outputs, branches, tags): `docs/agents/NAMING.md`; object ids: `jobs/REGISTRY.md`.
- Etalons: `benchmark/`; patterns: `docs/domain/patterns/INDEX.md`.
- Customer sources, outside git: `G:/Мой диск/AGR-assets/<object>/source/` + `SHA256SUMS.txt`; `jobs/<ID>/sources.json`.
- Machine-readable rules: `standards/` (locked; see `standards/README.md`).
- AGR knowledge base (Russian, read-only): `docs/agr/INDEX.md` only.
- Code map, checks and plugin configuration: `docs/agents/agents-reference.md`.
- Production task (NPM / VPM, OKS / Ground / MAF / Flora / UCX): name its cell in `docs/scenarios/scenarios.json` and follow the `scenario` skill.
- Model work: `docs/procedure/TASK_TO_MODEL.md` (gates); node edits: [R1–R7](docs/procedure/NODE_RECIPES.md).
- Task skills: load the matching `.agents/skills/*/SKILL.md` and follow it step by step (details: `docs/agents/agents-reference.md#skills`).

Rule lookup / new decisions: follow `docs/agents/agents-reference.md#rule-lookup`.

## Rules for every task

- A new task from Artem: task intake BEFORE code, issues or cards (sources first, one batch of <= 5 questions
  with recommendations, «Не трогать» + numbers, first piece accepted, then the rest). A card worker runs the
  preflight and asks all open questions once at the start: `docs/agents/task-intake.md` [D186].
- One task = one branch = one worktree = one writing agent. Branch names, prefixes and tags:
  `docs/agents/NAMING.md`. `main` stays clean; work reaches it by reviewed merge.
  A second agent in someone else's worktree only reads, researches or reviews.
- A worktree branch with an auto-generated name (`claude/<words>-<hex6>`, e.g. `claude/laughing-hawking-e62961`)
  is renamed by `NAMING.md` before the first commit: the agent proposes one name in one line, the user
  confirms, then `git branch -m`. The pre-commit gate blocks commits on such a branch.
- DCC per step: choose Blender/Max with a reason [D270]; `docs/agents/CAPABILITIES.md#dcc-acceptance-defaults`.
- Ask once per task: «по завершении этапов открывать тебе сцену для приёмки?» Retain answer: yes = auto-open new version at each stage + absolute path; no = path only [D270].
- Acceptance: 3ds Max 2026 QUAD review copy (user preference); triangulate only required delivery exports [D270].
- One owner per DCC scene, MCP port and export folder at a time; worktrees do not isolate them.
- Before any DCC call confirm the application, document, units and version; start read-only.
  Saves and exports go to a new versioned path. Never overwrite sources or approved versions.
- A successful import or exit code 0 is not a finished model: read the exported file back
  and check topology, UV, materials and transforms (`validate-delivery` skill).
- `passed=true` is forbidden while any mandatory check or manual gate is open.
  Technical QA, user acceptance and publication are separate statuses.
- Mark synthetic data as synthetic. Never present it as data of a real object.
- Apply the [Permission matrix](docs/agents/WORKFLOW.md#permission-matrix) for action
  permissions and its named guard rules/gates; it is the single policy for all agents.
- Update `docs/PROJECT_STATE.md` only on `main` after a merge, by regenerating it
  (`python tools/state/after_merge.py --pr <N>` right after the merge; Claude's hook runs it on `gh pr merge`;
  ≤ 80 lines, fixed sections; `docs/agents/WORKFLOW.md`);
  in task branches report state changes in the final summary.
- A new tool counts as shared only after it is listed in `docs/agents/CAPABILITIES.md` on `main`.
- AGR Tools (Max panel, `agr-mcp`, OKS conveyor 1.0): `docs/agr-tools/OVERVIEW.md`; rules: `docs/agents/agr-tools-1.0-rules.md`. Mandatory passport (К1): `jobs/<ID>/passport.json`, `schemas/ProjectPassport.schema.json`.
