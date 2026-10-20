# AGR-DigitalTwin — agent instructions

Shared by every agent (Claude Code, Codex, Antigravity). Agent-specific notes:
`CLAUDE.md`, `docs/agents/codex.md`, `GEMINI.md`. Talk to the user in Russian [D088]; write code,
commands, identifiers and docs in English.

A worker reads three things, then starts: this file, the card's area file `docs/domain/areas/<area>.md`, and the card.
Long form of the sections below: `docs/agents/agents-reference.md`.

## Goal

Produce delivery models from architectural sources — NPM and VPM per the Moscow
regulation, later IFC — for buildings (OKS), Ground, MAF (GroundEl), Flora and UCX
collisions, plus the interactive Unreal experience. Priorities, in order:
1. Architectural accuracy 2. Correct scale and transforms 3. Material correctness
4. Performance 5. Visual fidelity.

## Where things are

Read on demand, one line each. Read the domain file that matches the task before production work. Where sources disagree (`docs/domain/conflicts.md`), ask the user; never pick a side silently.

- Current state, next actions: `docs/PROJECT_STATE.md` (generated; `python tools/state/project_state.py`).
- Every dated user decision (`D<n>`): `docs/decisions.md`.
- Which kind of fact lives in which file: `docs/agents/WORKFLOW.md`, "Memory map".
- Who owns what (Claude / Codex / Antigravity): `docs/agents/ROLES.md`.
- Task loop, handoff, experience capture: `docs/agents/WORKFLOW.md`.
- Review questions, author receipts and how to run a Codex review: `docs/agents/REVIEW_CHECKLIST.md`, `docs/agents/WORKFLOW.md#before-requesting-review-author`.
- Tools, MCP routes and their verified status: `docs/agents/CAPABILITIES.md`.
- Production rules with citations (NPM/VPM, geometry, UV, materials, export, validation): `docs/domain/`.
- Open conflicts between sources: `docs/domain/conflicts.md`.
- Pipeline stages and their status: `docs/pipeline.md`.
- Unsolved work: `docs/backlog.md`.
- Accepted cases and lessons: `docs/cases.md`.
- Terms: `GLOSSARY.md`.
- Names for scripts, tools, jobs, outputs, branches and tags; object ids: `docs/agents/NAMING.md`, `jobs/REGISTRY.md`.
- Harness plan, benchmark etalons, pattern registry: `docs/HARNESS_PLAN.md`, `benchmark/`, `docs/domain/patterns/INDEX.md`.
- Machine-readable rules: `standards/` (locked; change procedure in `standards/README.md`).
- AGR knowledge base (Russian originals, read-only): `docs/agr/INDEX.md` only, then the file it names.
- Code map, checks and plugin configuration: `docs/agents/agents-reference.md`.
- Task skills: load the matching `.agents/skills/*/SKILL.md` and follow it step by step (details: `docs/agents/agents-reference.md#skills`).

A rule question ("is there a rule for ...?") is looked up in this order, and the first hit wins:
`docs/decisions.md` -> `docs/domain/patterns/INDEX.md` -> `docs/cases.md` -> `docs/domain/conflicts.md` ->
the matching `docs/domain/` file. `docs/agr/` is opened only through `docs/agr/INDEX.md`. A new user decision
gets a line in `docs/decisions.md` and its `[D<n>]` where it applies.

## Rules for every task

- One task = one branch = one worktree = one writing agent. Branch names, prefixes and tags:
  `docs/agents/NAMING.md`. `main` stays clean; work reaches it by reviewed merge.
  A second agent in someone else's worktree only reads, researches or reviews.
- A worktree branch with an auto-generated name (`claude/<words>-<hex6>`, e.g. `claude/laughing-hawking-e62961`)
  is renamed by `NAMING.md` before the first commit: the agent proposes one name in one line, the user
  confirms, then `git branch -m`. The pre-commit gate blocks commits on such a branch.
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
  (`python tools/state/project_state.py`; ≤ 80 lines, fixed sections; `docs/agents/WORKFLOW.md`);
  in task branches report state changes in the final summary.
- A new tool counts as shared only after it is listed in `docs/agents/CAPABILITIES.md` on `main`.
