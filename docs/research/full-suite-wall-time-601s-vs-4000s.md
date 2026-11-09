# Research: why one full suite ran in 601 s while the same suite took 2050-4150 s

Card t_cf0086d9 (research, no GitHub issue). Date 2026-11-09. Evidence only; no full suite was run for this report.
The only pytest calls were two `--collect-only` runs that each take less than 20 s.

## Summary

- The fast runs used **pytest-xdist**: `-n 8` for t_1f111ba8 (601 s) and `-n 4` for t_8f276244 (1121 s).
  Every other card that day ran pytest single-process. The command, not the machine load, explains the 3-7x gap.
  Earlier xdist runs show the same pattern: t_96a3cc8a `-n 8` took 575 s, t_d01d4740 `-n 4` took 758 s and
  t_6a275c07 `-n 6` took 882 s.
- The missing "deselected" in their summaries comes from the xdist summary line, not from a different test selection.
  The `-m` filter from `pyproject.toml` `addopts` still applied: the number of tests that ran matches the serial
  runs from the same window (18 616 vs 18 521), not that number plus the 417 deselected tests.
- So the fast runs cover the same tests and the same markers, which is the selection a rule 49 run needs. But they
  break **rule 43** ("Never use xdist (-n) inside a slot"). That ban exists because xdist inside 3-4 slots exhausts
  the Windows desktop heap (0xC0000142, false mass errors). They also escape the slot accounting: one slot held
  4-8 worker processes.
- Load explains part of the serial spread on 2026-11-05/06: about 2 060 s at about 2 other suites, up to 3 410 s for
  t_9e27c5ff. It does **not** explain the 2026-11-06 jump. t_b10ac4ee (4 150 s) and the merge gates (3 946-5 726 s)
  ran at **lower** concurrency (0.4-0.85 other suites on average) than the 2 060 s runs (2.0). That points to suite
  growth or slow new tests (+~800 tests, +36 skipped), or to load outside the suites that suite_slot does not record.
  Those numbers alone cannot tell these causes apart.
- `suite_slot_runs.jsonl` does not record argv or cwd. Recovering a command needed the Hermes process records in
  `~/.hermes/profiles/dt-worker/logs/process-results/proc_*.json`.

## Findings

### F1. Exact commands (verified: read the process records)

Source: `C:/Users/artsafro/.hermes/profiles/dt-worker/logs/process-results/<proc>.json`, field `command`. The cwd of
every run is `C:/Users/artsafro/agr-pilot/AGR-DigitalTwin/.worktrees/<card>`.

| card | proc record | pytest part of the command | workers |
|---|---|---|---|
| t_1f111ba8 | proc_b564947bd3eb | `uv run --frozen python -m pytest -q -n 8 -p no:cacheprovider --basetemp=C:/x/t_1f111ba8` | 8 |
| t_8f276244 | proc_e1a7061a1ddd | `uv run --quiet pytest -q -p no:cacheprovider -x --basetemp=C:/x/t_8f276244_suite -n 4` | 4 |
| t_35abee5f | proc_c3f37e2a6c7b | `env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/t_35abee5f` | 1 |
| t_b10ac4ee | proc_c00056f85a96 | same as t_35abee5f with `--basetemp=C:/x/t_b10ac4ee` | 1 |
| t_6a275c07 (11-04) | proc_553c3d31beab | `uv run pytest -q -p no:cacheprovider -n 6 --basetemp=C:/x/t_6a275c07` | 6 |
| t_96a3cc8a (11-04) | (process record) | `uv run pytest -q -n 8 -p no:cacheprovider ...` | 8 |
| t_d01d4740 (11-04) | (process record) | `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider ... -n 4` | 4 |
| merge gates | `hermes_kanban/scripts/agr_automerge.py:77` | `uv run pytest -q -p no:cacheprovider --basetemp=C:/x/automerge -m "not blender and not dcc and not acad and not perf and not job and not max and not panel_texture and not native_max"`, cwd `~/.hermes/cache/scratch/automerge-main`, timeout 4200 | 1 |

There are 46 process records that call `suite_slot.py`. 5 of them pass `-n` to pytest, and they are exactly the 5 runs
that finished in under 1 130 s. A grep also matched t_6a258785, but its suite command has no `-n`; it ran
serially, with 224 deselected, in 3 417 s. t_8f276244 also used `-x`. It passed with no failures, so `-x` cut nothing short.

### F2. Load vs command (verified: computed from `hermes_kanban/kpi/suite_slot_runs.jsonl`)

"overlap avg" is the time-weighted average number of other suites running during the run, computed from the
`started`/`ended` windows. "deselected" is copied from the logged summary line.

| card | command | workers | holders_at_start | overlapping suites (avg) | passed | deselected | seconds |
|---|---|---|---|---|---|---|---|
| t_1f111ba8 | uv run pytest -n 8 | 8 | 4 | 2 (1.40) | 18 504 (+1 failed) | not shown (xdist) | 601 |
| t_8f276244 | uv run pytest -x -n 4 | 4 | 4 | 2 (2.00) | 18 241 | not shown (xdist) | 1 122 |
| t_35abee5f | uv run pytest (serial) | 1 | 4 | 3 (2.00) | 18 375 | 417 | 2 056 |
| t_1c2f5803 | serial | 1 | 4 | 3 (2.00) | 18 287 | 417 | 2 115 |
| t_0e57fd6b | serial | 1 | 4 | 3 (1.89) | 18 410 (+1 failed) | 417 | 2 589 |
| t_9e27c5ff | serial | 1 | 4 | 5 (1.99) | 18 368 | 417 | 3 402 |
| t_ceb55bbd | serial | 1 | 4 | 2 (1.53) | 18 346 | 417 | 3 138 |
| t_7beb60dc | serial | 1 | 2 | 1 (0.76) | 18 212 | 417 | 2 549 |
| t_b10ac4ee | serial | 1 | 3 | 2 (0.85) | 19 179 (+1 failed) | 417 | 4 143 |
| merge20261105g | automerge serial | 1 | 4 | 5 (1.54) | 18 528 (+3 failed) | 190 | 5 586 |
| merge20261106a | automerge serial | 1 | 4 | 6 (1.99) | 18 539 (+5 failed) | 190 | 4 276 |
| merge20261106b | automerge serial | 1 | 2 | 1 (0.45) | 19 341 (+4 failed) | 190 | 5 727 |
| merge20261106d | automerge serial | 1 | 3 | 2 (0.79) | 19 344 (+3 failed) | 190 | 3 947 |

How to read the table:
- At the same load (about 2 other suites), the serial runs took 2 056-3 402 s, and the `-n 4` and `-n 8` runs took
  1 122 s and 601 s. The worker count is the only thing that differs, and the speed-up roughly follows it, minus
  xdist and Windows process overhead. The host has 32 logical CPUs (`nproc`), and the suite_slot docstring measured
  a serial suite at about 1 core.
- The xdist runs ran the same test set. t_1f111ba8 ran 1+18 504+72+39 = 18 616 tests. t_0e57fd6b, a serial run
  that overlapped it, ran 18 521 + 417 deselected. If `-m` had been dropped, about 417 more tests would have run,
  among them blender/dcc/max tests that need DCC applications. Instead the count is within normal branch-to-branch
  drift and skipped is 72 vs 71. The xdist summary line just does not report a deselected count. That is an
  observation from these logs only; I found no pytest-xdist documentation page that states it.
- On this head, `pytest --collect-only -q` selects 19 520 of 19 938 tests (418 deselected) with the explicit
  automerge `-m` (verified, ran it). The gates on 2026-11-06 logged 190 deselected, so their tree deselected fewer
  tests than the card worktrees. They also show 137 skipped vs 107. They ran more tests than the card runs, which
  partly explains why they are slower. The exact reason for 190 vs 417 is not resolved here (open question 2).
- Load does not explain t_b10ac4ee or the 2026-11-06 merge gates. They ran at 0.45-0.85 average overlap, yet took
  3 947-5 727 s, while the 2026-11-05 serial runs took about 2 060 s at 2.0 overlap. Between those days the suite
  grew from about 18.4 k to 19.2 k passed. A few slow new tests or work outside the suites (DCC jobs, other CLIs)
  would fit. `-q` logs have no `--durations`, so these numbers cannot separate those causes.

### F3. Validity under rules 43 and 49 (verified: read `hermes_kanban/profiles/COORDINATION_RULES.md`)

- Rule 49 (line 455) asks for one full suite per PR on the head sent to the first review. The xdist runs select the
  same tests with the same markers, so as a **selection** they are a valid rule 49 full suite.
- Rule 43 (lines 417-424) says "Never use xdist (-n) inside a slot". The reason given is that 8 cards x `-n 8`
  exhausted the Windows desktop heap, child processes died with 0xC0000142, and runs reported false
  "1256 errors" (#318) and "107 failed" (#333). So the fast runs **break rule 43**.
- One related sign: t_6a275c07 has a row with `exit` 3221225794 (= 0xC0000142) and `ran_s` 0. It is followed by its
  successful `-n 6` rerun. Only the rerun's command is in the process records, so the crashed attempt's command
  is not proven.
- Load-sensitive tests (the #361 orientation budget, `measure_process_time` in `tests/conftest.py`) behave
  differently under xdist. A green xdist run is therefore not interchangeable with the serial merge gate for those
  tests.

## How it applies to this repository

- `pyproject.toml` `[tool.pytest.ini_options]`: `addopts` holds the default `-m` filter, and `pytest-xdist==3.8.0`
  is a dev dependency. That is why `-n` works in any worktree without extra setup.
- `C:/Users/artsafro/hermes_kanban/scripts/suite_slot.py`: one slot = one suite of any width. `log_run` writes
  card, timing, holders and the summary, but **no argv, cwd or worker count**.
- `C:/Users/artsafro/hermes_kanban/scripts/agr_automerge.py:77`: the merge gate is serial, with an explicit `-m`
  (adds `native_max`) and `timeout=4200`. At the current 3 947-5 727 s it exceeds that timeout in 3 of 4 runs
  on 2026-11-06.
- Card bodies and `docs/agents/WORKFLOW.md` do not give one canonical full-suite command, so workers write their own
  variants (`uv run --frozen python -m pytest`, `.venv/Scripts/python.exe -m pytest`, `env -u MSYS_* uv run pytest`,
  with or without `-n`/`-x`).

## Proposed next tasks

1. **suite_slot logs argv, cwd, worker count and refuses `-n` (or gives it more slots).** Scope: in
   `hermes_kanban/scripts/suite_slot.py`, add `argv`, `cwd`, `xdist_workers` (parsed from `-n`/`--numprocesses`) and
   the git head to every `log_run` row. Either reject `-n` with the rule 43 message, or let a `-n K` run take
   `ceil(K/2)` slots. The user decides which (open question 1). Add a test against a fake command. Value: high,
   because every later speed analysis becomes a one-line query. Effort: S. Archive: no roadmap link.
2. **One canonical full-suite command in the card template and in WORKFLOW.md.** Scope: define one line, e.g.
   `python .../suite_slot.py --card <id> -- uv run --frozen pytest -q -p no:cacheprovider --basetemp=C:/x/<id> --durations=30`,
   and put it in the card policy text produced by `agr_refill.py`, in `docs/agents/WORKFLOW.md` and in the receipt
   template (COORDINATION_RULES line 628). Card and merge-gate results then become comparable, and `--durations`
   shows slow new tests. Value: high. Effort: S. Archive: no roadmap link.
3. **Find the 2026-11-06 slowdown and the merge-gate timeout.** Scope: run one serial `--durations=50` suite on
   current main through a slot. Compare it with a 2026-11-05 head (both serial, both with 0-1 other holders). List
   the slowest tests added since then. Explain why the automerge tree deselects 190 vs 417 tests. Then propose
   either fixes for the slow tests or a new automerge timeout. Value: medium-high, because 3 of 4 gates went past
   4 200 s. Effort: M. Archive: no roadmap link.

## Open questions for the user

1. xdist is about 3.4x faster per suite (601 s vs about 2 060 s at the same load). Should rule 43 stay "never `-n`",
   or should a slot allow, say, `-n 4` while the slot count drops to 2 (about 8 worker processes machine-wide)?
   The rule exists because of the desktop-heap crash, so this is the user's decision, not a worker's.
2. Should the merge gate keep its own explicit `-m` list (190 deselected on 2026-11-06), or use the same `addopts`
   as the cards so that card and gate counts are comparable?

## Sources

All of the following were verified by me (read or computed):
`hermes_kanban/kpi/suite_slot_runs.jsonl`;
`.hermes/profiles/dt-worker/logs/process-results/proc_{b564947bd3eb,e1a7061a1ddd,c3f37e2a6c7b,c00056f85a96,553c3d31beab}.json` and two others;
`C:/x/ev_t_1f111ba8/full.log`, `C:/x/ev_t_35abee5f/suite.log`, `C:/x/ev_t_b10ac4ee_suite.log`;
`hermes_kanban/scripts/suite_slot.py`, `hermes_kanban/scripts/agr_automerge.py`;
`hermes_kanban/profiles/COORDINATION_RULES.md` rules 43 and 49;
`pyproject.toml`;
`pytest --collect-only` on this head.
External: pytest-xdist issue search (`gh search issues --repo pytest-dev/pytest-xdist deselected`) found no issue
that documents the missing deselected count, so that point rests on our own logs only.
