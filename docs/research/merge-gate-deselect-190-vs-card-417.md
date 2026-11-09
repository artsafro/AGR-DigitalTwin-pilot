# Why the merge gate deselects 190 tests while cards deselect 417, and what the gate `-m` drift costs

Research card (no GitHub issue). Pilot PR #1114, open question 2 / proposed task #3.

## Summary

The 190-vs-417 gap is **not** caused by the marker list. The gate's `-m` differs from the card
`addopts` by exactly one token (`not native_max`), and on the *same* current main checkout that
difference deselects exactly **one** more test (417 → 418), not 227. The real cause is a **stale
tree**: the merge gate's suite last ran on 2026-11-06 10:00 (card `merge20261106c`), when
`origin/main` carried only ~190 marker-tagged tests (blender 127 + dcc 63); since then ~230
marker-tagged tests (job 179, max 36, perf 12, acad 2, panel_texture 2, native_max 1) were merged
to main, and the gate stopped re-running because open PRs (23) fell below the automerge threshold
(30). Separately, the gate `-m` has *drifted* from `addopts`: the exclusion list now lives in three
places and they already disagree. One test (`test_real_native_parity`) carries `native_max` without
`max` and without any other excluded marker, so cards run-and-skip it while the gate deselects it.

## Findings

### 1. The two commands and what they deselect (verified on current main = `origin/main` = `06d32a65`)

- **Card command** (pyproject `addopts`, `pyproject.toml:45`):
  `-m 'not blender and not dcc and not acad and not perf and not job and not max and not panel_texture'`
  ```
  $ uv run pytest --collect-only -q
  19521/19938 tests collected (417 deselected) in 65.99s
  ```
- **Gate command** (`hermes_kanban/scripts/agr_automerge.py:77-78`, its own `-m` on the CLI):
  `-m 'not blender and not dcc and not acad and not perf and not job and not max and not panel_texture and not native_max'`
  ```
  $ uv run pytest --collect-only -q -m 'not blender and not dcc and not acad and not perf and not job and not max and not panel_texture and not native_max'
  19520/19938 tests collected (418 deselected) in 20.60s
  ```

On the **same tree** the two commands deselect 417 vs 418. The only difference is `not native_max`,
worth exactly **+1** test — not 227.

### 2. A command-line `-m` **replaces** the `addopts -m` (verified)

pytest prepends `addopts` to `sys.argv` and then argparse's `-m` action is `store`, so the last
occurrence wins. Verified empirically:

```
$ uv run pytest --collect-only -q -m 'blender'
127/19938 tests collected (19811 deselected)
```

If the CLI `-m` *combined* (ANDed) with the `addopts -m`, this would collect 0 tests
(`blender and not blender …`). 127 selected proves replacement.

### 3. Per-marker counts on current main (in-process collection, total 19938)

| marker | tests | excluded by card | excluded by gate |
|---|---|---|---|
| job | 179 | yes | yes |
| blender | 127 | yes | yes |
| dcc | 63 | yes | yes |
| max | 36 | yes | yes |
| perf | 12 | yes | yes |
| acad | 2 | yes | yes |
| panel_texture | 2 | yes | yes |
| native_max | 1 | **no** | **yes** |

Union of the excluded markers = 417 (card) / 418 (gate). (Non-exclusion markers: parametrize 14339,
skipif 121, xfail 49, filterwarnings 1.)

### 4. The one `native_max` test

`tests/dcc/test_ac08_xview_native_parity.py::test_real_native_parity` carries `native_max` **without**
`max`, and carries none of the other excluded markers (blender/dcc/acad/perf/job/panel_texture). So
the card command does **not** deselect it: cards collect and run it, where it immediately `pytest.skip`
(the AC08 fixture/dump env vars are unset — the module docstring and body confirm "3ds Max is not
launched"). Cost: one spurious run+skip per card suite, plus the maintenance hazard in §6.

### 5. The 190/417 gap is a stale tree, not the marker list

`kpi/suite_slot_runs.jsonl` (hermes_kanban):

- Rows with `417 deselected`: **21 cards** (`t_*`), first 2026-11-05 22:20, last 2026-11-09 03:19.
- Rows with `190 deselected`: **6 rows, all `merge*`** (the gate), first 2026-11-05 11:28,
  **last 2026-11-06 10:00** (`merge20261106c`).

The gate's deselected count tracked main's growth over time — 180 → 181 → 185 → **190** — while the
cards read the current tree. The gate's 190 is exactly `blender(127) + dcc(63) = 190`: on 11-06 main
had only those two marker families; `job/max/perf/acad/panel_texture/native_max` (≈232 tests) were
still in feature branches and merged afterwards (e.g. AC08 kernel invariants `#1006` 11-06 07:45,
blender handoff `#1096`, AGR Tools 1.1.0 `#1097`, qa-decision-checks `#1100`, scenario-router
`#1103`/`#1111`). Today main collects 19938 with 417 marker tests.

Why the gate number is frozen: `agr_automerge.main()` returns early at the threshold check
(`if len(prs) < a.threshold: return`, `THRESHOLD = 30`) — currently **23** open PRs, so
`suite_on_main()` has not run since 11-06 10:00.

### 6. The `-m` drift: three divergent copies of the exclusion list

| location | expression | notes |
|---|---|---|
| `pyproject.toml:45` (`addopts`) | 8 `not …` markers | canonical for cards; **missing `not native_max`** |
| `hermes_kanban/scripts/agr_automerge.py:78` | 9 `not …` markers | gate; adds `not native_max` (commit `2f0e5fb`, 2026-11-06 09:02, "exclude all opt-in markers in automerge suite") |
| `tests/dcc/test_ac08_xview_native_parity.py:29` (`DEFAULT_MARKEXPR`) | 7 `not …` markers | **missing `not job` AND `not native_max`** |

Three copies, already disagreeing. Each new opt-in marker must be added in three places, and the
`native_max` addition (11-06) touched only one of them.

### 7. Gate rows with wall time > 4200 s (`kpi/suite_slot_runs.jsonl`, `ran_s` > 4200)

| card | date | ran_s | waited_s | exit | summary (deselected) |
|---|---|---|---|---|---|
| merge20261022d | 10-22 | 5435 | 0 | 0 | — |
| merge20261102g | 11-02 | 4439 | 0 | 1 | — |
| merge20261105a | 11-04 | 4281 | 514 | 1 | 185 |
| merge20261105e | 11-05 | 4938 | 0 | 1 | 185 |
| merge20261105f | 11-05 | 4358 | 150 | 1 | 190 |
| merge20261105g | 11-05 | 5601 | 960 | 1 | 190 |
| merge20261106a | 11-06 | 4288 | 1410 | 1 | 190 |
| merge20261106b | 11-06 | 5743 | 0 | 1 | 190 |
| merge20261106c | 11-06 | 5114 | 0 | 1 | 190 |

Note the gate's `subprocess.run(..., timeout=4200)` (added 2026-10-20, commit `75cdaf9`) is shorter
than these completed runs (up to 5743 s). These particular rows carry `--card merge<date><letter>`,
while the current `suite_on_main` uses `--card automerge` and there are **zero** `automerge` rows in
the jsonl — so the "190" runs and the current `--card automerge`/`timeout=4200` path may not be the
same invocation. When the gate next runs, a ~5000 s single-process suite will exceed 4200 s.

## How it applies to this repository (file paths)

- `pyproject.toml:43-56` — `addopts` (line 45) is the card-side exclusion list; `markers` declares
  `native_max` (line 55) but `addopts` never excludes it.
- `hermes_kanban/scripts/agr_automerge.py:77-78` — the gate's hard-coded `-m` (drifted), and
  `:76` (`--card automerge`) vs `:79` (`timeout=4200`).
- `tests/dcc/test_ac08_xview_native_parity.py:29` — a third copy (`DEFAULT_MARKEXPR`), already stale.
- `hermes_kanban/kpi/suite_slot_runs.jsonl` — the 190 (gate) vs 417 (card) evidence.
- `tests/dcc/test_ac08_xview_native_parity.py:434-455` — the `native_max` test that cards run and skip.

## Proposed next task

**Unify the opt-in test-marker exclusion list into one source of truth** (value/effort **S**).
Scope: add `not native_max` to `pyproject.toml` `addopts`; delete the hard-coded `-m` at
`agr_automerge.py:78` so the gate inherits `addopts`; fix `DEFAULT_MARKEXPR` in
`test_ac08_xview_native_parity.py` to match (and ideally have it import the value rather than
re-listing it); add one guard test asserting the three agree. This makes cards and the gate deselect
the identical set (418), removes the spurious `native_max` run+skip from every card suite, and stops
the three-way drift. (I only propose this; I did not change `agr_automerge.py` or `pyproject.toml`.)
**Archive: no roadmap link** — this is test-harness infrastructure; none of the open `roadmap`-labelled
issues (all delivery/feature work: #792, #426, #425, #352, #349, #298, #149) is advanced by it.

## Open questions for the user

1. Should the gate simply rely on `addopts` (drop its own `-m` entirely), or keep an explicit list but
   generate it from `pyproject.toml`? The former is simplest but means the gate can never override
   `addopts` without a code change.
2. The "190 deselected" rows carry `--card merge<date><letter>`, while `agr_automerge.py:76` uses
   `--card automerge` (no such rows exist). Which path actually runs the merge-gate suite today, and
   should they be one?
3. The gate `timeout=4200` (70 min) is now shorter than observed single-process suite runs
   (3436–5743 s). Should it be raised, or should the gate reuse the suite-slot parallelism instead of
   one process?

## Sources

- `pyproject.toml` (read), `hermes_kanban/scripts/agr_automerge.py` (read),
  `hermes_kanban/scripts/suite_slot.py` (read), `kpi/suite_slot_runs.jsonl` (parsed),
  `tests/dcc/test_ac08_xview_native_parity.py` (read).
- Commands run and numbers reproduced locally on this branch (collect-only only; no suite run).
- Git history: `git log`/`-S` for `native_max` (added `f7970bc7`, 2026-11-03) and the automerge
  `-m`/timeout changes (`2f0e5fb` 11-06 09:02, `75cdaf9` 10-20) in the `hermes_kanban` repo.
- pytest `-m` replacement behaviour verified empirically (`-m blender` → 127 selected), consistent
  with pytest's `addopts` prepend + argparse `store` action.
