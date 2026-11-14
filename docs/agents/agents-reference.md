# Agent instructions — on-demand reference

Read the matching section when navigating code, running checks, loading skills or using agent plugins.
Per-card reading order and shared safety rules stay in `AGENTS.md` [D121].

- Four working principles (assumptions first, simplest fit, surgical changes, verified done): `docs/agents/working-principles.md`.

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
