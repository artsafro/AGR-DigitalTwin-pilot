# Agent instructions — on-demand reference

Read the matching section when navigating code, running checks, loading skills or using agent plugins.
Start with the per-card reading order in `AGENTS.md` [D121]; use the shared rules below before the relevant action.

- Four working principles (assumptions first, simplest fit, surgical changes, verified done): `docs/agents/working-principles.md`.

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
- Apply the [Permission matrix](WORKFLOW.md#permission-matrix) for action
  permissions and its named guard rules/gates; it is the single policy for all agents.
- Update `docs/PROJECT_STATE.md` only on `main` after a merge, by regenerating it
  (`python tools/state/after_merge.py --pr <N>` right after the merge; Claude's hook runs it on `gh pr merge`;
  ≤ 80 lines, fixed sections; `docs/agents/WORKFLOW.md`);
  in task branches report state changes in the final summary.
- A new tool counts as shared only after it is listed in `docs/agents/CAPABILITIES.md` on `main`.
- AGR Tools (Max, OKS stages 2-4) are frozen at 1.1.x and off the trail [D393], `agr-mcp` too [D394]:
  `docs/agr-tools/OVERVIEW.md`.

## Rule lookup

A rule question ("is there a rule for ...?") is looked up in this order, and the first hit wins:
`docs/decisions.md` -> `docs/domain/patterns/INDEX.md` -> `docs/cases.md` -> `docs/domain/conflicts.md` ->
the matching `docs/domain/` file. `docs/agr/` is opened only through `docs/agr/INDEX.md`. A new user decision
gets a line in `docs/decisions.md` and its `[D<n>]` where it applies.

## Code map

- `src/dt_ai/` — pipeline core: models, build, geometry (exterior, shell, connect, UV),
  materials, packaging, RunRecord. CLI: `uv run dt --help`.
- `src/twinqa/` — delivery validator V001–V017, standards loader, PNG/UV/GeoJSON/clearance.
- `technical_library/` — reviewed operation packages (atlases, UV, texture tiles, mesh audit).
- `tools/` — runnable scripts: `qa/`, `blender/`, `mcp/` (servers), `herdr/`, `git-hooks/`,
  plus object/operation scripts from accepted cases.
- `adapters/` — DCC bridges (Blender, SketchUp, Max/Revit/CAD notes).
- `jobs/<JOB>/` — per-object spec, STATE and evidence (text tracked; `outputs/`, `runs/` local only).
- `data/` — local only, git-ignored: heavy sources (`data/sources/`), archives.
- `docs/reference/` — factual implementation references, not requirements: `geometry-weld-contracts.md`
  (weld contracts of the geometry code, synthetic coordinates).

Setup `uv sync`. Checks: `uv run pytest -q`, `uv run dt profiles check`, `uv run dt schemas --check`. DCC tests use
an installed Blender (auto-detected) or `DT_BLENDER`.
The default suite is ~18.3k tests; a serial run takes over an hour, so run it in parallel (pytest-xdist):
`uv run pytest -q -n auto`. Default `addopts` deselect the opt-in lanes `blender`, `dcc`, `acad`, `max`,
`panel_texture`, `perf` (budgets and brute-force/exhaustive cases) and `job` (slow tests tied to one job's data:
TEC26 AC08, tow02); select one with `-m <marker>`. A command-line `-m` replaces the default expression, so name
every lane to keep excluded. Real delivery archives: `tests/qa/test_owner_decisions_081.py` runs its archive
check only with `AGR_REAL_DELIVERIES` set.

- Performance lane (#361): wall-clock / CPU-time budgets are marked `perf`. Run them through the suite-slot
  limiter — `uv run pytest -m perf -p no:cacheprovider` (via `C:\Users\artsafro\hermes_kanban\scripts\suite_slot.py`,
  outside the repo); not part of a card's full-suite receipt.
- Real 3ds Max lane (#518): a test that launches real 3ds Max (`max_adapter.default_adapter()` without a mocked
  `_call`, or any `dcc_batch.py` call) is marked `max`; `pyproject.toml` `addopts` is the single place of the
  default lane expression. Run it on purpose through the suite-slot limiter: `uv run pytest -m max -p no:cacheprovider`.
  It takes the shared cross-card Max lock and may report `busy`. `tests/test_max_marker_contract.py` fails any
  unmarked real-Max test.

## Skills

Canonical project skills live in `.agents/skills/*/SKILL.md` (Codex, Antigravity);
`.claude/skills/` is a generated copy (`py -3 tools/sync_skills.py`; a test checks parity).
Follow the matching skill step by step.

## Agent skills

Matt Pocock's engineering skills (`mattpocock-skills` plugin) read this configuration.

### Issue tracker

GitHub Issues of `artsafro/AGR-DigitalTwin-pilot` via `gh`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default triage labels plus area labels. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context; the glossary is `GLOSSARY.md` (not `CONTEXT.md`), ADRs in `docs/adr/`.
See `docs/agents/domain.md`.
