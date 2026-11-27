# AGR-DigitalTwin — agent instructions

Shared by every agent (Claude Code, Codex, Antigravity). Agent-specific notes:
`CLAUDE.md`, `docs/agents/codex.md`, `GEMINI.md`. Talk to the user in Russian [D088]; write code,
commands, identifiers and docs in English.

One door [D324-D327]: `docs/agents/SKELETONS.md` -> your cell's block
(`uv run python tools/architecture/skeleton_guard.py --show <cell>`) -> its trail -> rule + command at the step.
Passport first [D397]: `jobs/<ID>/passport.json` (`schemas/ProjectPassport.schema.json`).
Trails: OKS `routes/npm-oks.md`, site `routes/site.md`.
For Revit-source tasks read `routes/revit-intake.md` (read-only intake first, [D237]).
Read `docs/domain/areas/<area>.md` and the card when the step links them; `agr --help` before any script.

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
- Dated user decisions (`D<n>`): `docs/decisions.md`.
- Fact locations: `docs/agents/WORKFLOW.md`, "Memory map".
- Who owns what (Claude / Codex / Antigravity): `docs/agents/ROLES.md`.
- Task loop, handoff, experience capture, snags: `docs/agents/WORKFLOW.md`.
- Before PR `scripts/hygiene.sh`; author receipts `docs/agents/REVIEW_CHECKLIST.md`, `docs/agents/WORKFLOW.md#before-requesting-review-author`.
- Tools/MCP status: `docs/agents/CAPABILITIES.md`.
- Production rules with citations (NPM/VPM, geometry, UV, materials, export, validation): `docs/domain/`.
- Pipeline stages and their status: `docs/pipeline.md`.
- Unsolved work: `docs/backlog.md`.
- Archive (tag `archive/2026-11`): `docs/ARCHIVE.md`.
- Accepted cases and lessons: `docs/cases.md`.
- Terms: `GLOSSARY.md`.
- Naming (scripts, jobs, outputs, branches, tags): `docs/agents/NAMING.md`; object ids: `jobs/REGISTRY.md`.
- Etalons: `benchmark/`; patterns: `docs/domain/patterns/INDEX.md`.
- Customer sources, outside git: `G:/Мой диск/AGR-assets/<object>/source/` + `SHA256SUMS.txt`; `jobs/<ID>/sources.json`.
- Machine-readable rules: `standards/` (locked: `standards/README.md`).
- AGR knowledge base (Russian, read-only): `docs/agr/INDEX.md` only.
- Code map, checks and plugin configuration: `docs/agents/agents-reference.md`.
- Production task (NPM / VPM, OKS / Ground / MAF / Flora / UCX): name its cell in `docs/scenarios/scenarios.json` and follow the `scenario` skill.
- Model work: `docs/procedure/TASK_TO_MODEL.md` (gates); node edits: [R1–R7](docs/procedure/NODE_RECIPES.md).
- Task skills: load the matching `.agents/skills/*/SKILL.md` and follow it step by step (details: `docs/agents/agents-reference.md#skills`).

Rule lookup / new decisions: follow `docs/agents/agents-reference.md#rule-lookup`.

[Rules for every task](docs/agents/agents-reference.md#rules-for-every-task):
read the relevant rule before acting. Start with `docs/agents/task-intake.md` [D186];
check the [Permission matrix](docs/agents/WORKFLOW.md#permission-matrix) before restricted actions.
AGR Tools and `agr-mcp` are off the trail [D393] [D394]; see `docs/agr-tools/OVERVIEW.md`.
