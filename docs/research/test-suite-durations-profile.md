# Research: which tests dominate the full-suite wall time

Card `t_c9a06ef6` (research, no GitHub issue). Follows up on autoresearch #116 (PR #148,
`docs/experiments/autoresearch-tests-wall-time.md`), which timed out twice at 400 s and could not name the cost.
Base: `main` at `d040d58`. No code changed; `src/` and `tests/` untouched; the branch
`experiment/autoresearch-tests-wall-time` was only read.

## Summary

- One run (2026-10-15, about 19:15 local), fresh `--basetemp`, no A/B:
  `uv run pytest -q -p no:cacheprovider --durations=0 -m 'not blender and not dcc'`.
  Result: **3195 passed, 9 skipped, 13 deselected, 0 failed in 353.75 s** (pytest); **362 s** wall including `uv`.
- The suite is not slower per test; it is bigger. The historical baseline was 301 s for 2321 passed (0.130 s/test);
  tonight it is 354 s for 3195 passed (0.111 s/test, +38 % tests, +18 % time). Under machine load this crosses 400 s.
- The cost is concentrated: the top 1 % of tests (32) take **34 %** of the measured time, the top 5 % (160) take **68 %**.
  65 tests of 1 s or more take 163 s (48 %).
- **Call dominates: 304 s call vs 35 s setup vs ~0 s teardown** (of 339 s measured per-test time).
- Three files hold 36 % of the time: `tests/test_pi_guard_contract.py` (44 s), `tests/test_pipeline_gate.py` (42 s),
  `tests/test_pi_guard_adapter.py` (37 s). They spawn real subprocesses (Node + installed Pi, git, hook scripts).
- The repo-health slow tests are still on top: `test_dense_wall_rows_keep_the_contour` is **#1 (12.00 s)**,
  `test_long_matching_chain_needs_no_recursion` is **#4 (5.77 s)**; both grew since repo-health (6.65 s / 3.76 s),
  probably partly load.
- About 39 s (11 %) is pure waiting on fixed timeouts: two hook-timeout tests at 10 s each and two run-record
  cleanup tests at 5.5 s each.

## Method (verified: commands run in this worktree)

- Command above, `--basetemp=<scratch>/bt` (fresh dir), output saved to a local file.
- `--durations=0` prints setup/call/teardown per test; 7752 phase entries under 0.005 s are hidden by pytest
  (documented behaviour of `--durations`, https://docs.pytest.org/en/stable/how-to/usage.html#profiling-test-execution-duration).
  1462 tests had at least one visible phase; their sum is **339.4 s**. The remaining ~14 s of the 353.75 s is
  collection, the hidden <5 ms phases and reporting.
- Aggregation: a 40-line script (regex over the durations lines, sum per node id, then per file and directory).
  Shares "top 1 % / 5 %" are relative to all 3204 executed tests (passed + skipped), against the 339.4 s sum.

**Load caveat.** Other kanban cards were running: 37 python processes at start, 52 python/node processes and 26 %
average CPU load (`Win32_Processor.LoadPercentage`) right after the run, 32 logical CPUs. Absolute seconds are
inflated by contention; the ranking is the useful part. Not repeated (card: one run).

## Findings

### Totals

| Metric | Value |
|---|---|
| Wall time (`time`, incl. `uv`) | 362 s |
| pytest reported | 353.75 s |
| Sum of per-test phases (visible) | 339.4 s |
| setup / call / teardown | 35.3 s / 304.1 s / 0.0 s |
| Tests: passed / skipped / deselected / failed | 3195 / 9 / 13 / 0 |
| Top 1 % (32 tests) | 116.9 s = 34.4 % |
| Top 5 % (160 tests) | 229.0 s = 67.5 % |
| Top 10 % (320 tests) | 277.3 s = 81.7 % |
| Tests >= 1 s | 65 tests, 163.1 s |
| Tests >= 0.5 s | 159 tests, 228.5 s |

### Top 25 tests (setup + call, seconds)

| # | Total | Setup | Call | Test |
|---|---|---|---|---|
| 1 | 12.00 | 0.00 | 12.00 | `tests/test_spec_contour_shapes.py::test_dense_wall_rows_keep_the_contour` |
| 2 | 10.36 | 0.01 | 10.35 | `tests/test_pi_guard_adapter.py::test_hook_timeout_blocks[pipeline_gate.py]` |
| 3 | 10.12 | 0.01 | 10.11 | `tests/test_pi_guard_adapter.py::test_hook_timeout_blocks[guard.py]` |
| 4 | 5.77 | 0.00 | 5.77 | `tests/test_spec_floors.py::test_long_matching_chain_needs_no_recursion` |
| 5 | 5.59 | 0.01 | 5.58 | `tests/test_run_record.py::test_windows_timeout_cleanup_nonzero_returncode` |
| 6 | 5.55 | 0.00 | 5.55 | `tests/test_run_record.py::test_windows_timeout_cleanup_oserror` |
| 7 | 4.18 | 0.01 | 4.17 | `tests/test_kpp1_export_safety.py::test_pipeline_preserves_old_build_and_atlas_uses_fresh_version` |
| 8 | 4.05 | 0.26 | 3.79 | `tests/test_pipeline_gate.py::test_staged_attempts_limit` |
| 9 | 3.34 | 0.01 | 3.33 | `tests/test_kpp1_export_safety.py::test_long_safe_version_works_through_real_stage_launcher` |
| 10 | 2.80 | 0.58 | 2.22 | `tests/test_pipeline_gate.py::test_staged_old_state_untouched_passes_touched_needs_the_line` |
| 11 | 2.80 | 0.17 | 2.63 | `tests/test_session_context.py::test_precompact` |
| 12 | 2.71 | 0.03 | 2.68 | `tests/test_pi_guard_contract.py::test_special_outside_paths_match_installed_pi_policy[write]` |
| 13 | 2.69 | 0.04 | 2.65 | `tests/test_pi_guard_contract.py::test_supported_paths_equal_installed_pi_targets[write]` |
| 14 | 2.61 | 0.00 | 2.61 | `tests/test_spec_openings.py::test_pier_search_stays_fast_at_two_hundred_ends` |
| 15 | 2.55 | 0.21 | 2.34 | `tests/test_save_transcript.py::test_report_prints_the_handoff_transcript` |
| 16 | 2.52 | 0.00 | 2.52 | `tests/integration/test_pipeline.py::test_repeat_build_and_material_change_preserve_unrelated_assets` |
| 17 | 2.45 | 0.27 | 2.18 | `tests/test_pipeline_gate.py::test_pre_commit_gate_sees_the_index_after_linking` |
| 18 | 2.44 | 0.03 | 2.41 | `tests/test_pi_guard_contract.py::test_special_outside_paths_match_installed_pi_policy[edit]` |
| 19 | 2.26 | 0.22 | 2.04 | `tests/test_session_context.py::test_stale_foreign_and_old_handoffs_are_flagged` |
| 20 | 2.23 | 0.01 | 2.22 | `tests/test_pi_guard_contract.py::test_current_multi_edit_combines_paths_and_pipeline[False-True-locked-status]` |
| 21 | 2.22 | 0.28 | 1.94 | `tests/test_pipeline_gate.py::test_cli_exit_codes` |
| 22 | 2.09 | 0.01 | 2.08 | `tests/test_run_record.py::test_timeout_preserves_partial_stdout_and_stderr` |
| 23 | 2.09 | 0.68 | 1.41 | `tests/test_pipeline_gate.py::test_staged_denies_four_failures_in_the_first_commit_of_the_state` |
| 24 | 2.07 | 0.04 | 2.03 | `tests/test_kpp1_export_safety.py::test_blender_error_is_not_hidden_by_successful_grep` |
| 25 | 2.00 | 0.01 | 1.99 | `tests/test_pi_guard_contract.py::test_current_multi_edit_combines_paths_and_pipeline[False-False-locked-status]` |

### Top 10 files

| File | Total s | Setup s | Call s | Tests with timing | Share |
|---|---|---|---|---|---|
| `tests/test_pi_guard_contract.py` | 44.0 | 0.8 | 43.2 | 36 | 13.0 % |
| `tests/test_pipeline_gate.py` | 41.7 | 12.0 | 29.8 | 59 | 12.3 % |
| `tests/test_pi_guard_adapter.py` | 37.2 | 0.9 | 36.3 | 74 | 11.0 % |
| `tests/test_spec_contour_shapes.py` | 16.9 | 0.0 | 16.9 | 66 | 5.0 % |
| `tests/test_session_context.py` | 16.0 | 2.9 | 13.1 | 15 | 4.7 % |
| `tests/test_run_record.py` | 14.9 | 0.1 | 14.8 | 17 | 4.4 % |
| `tests/test_subagents.py` | 14.3 | 3.8 | 10.5 | 46 | 4.2 % |
| `tests/integration/test_pipeline.py` | 13.9 | 9.0 | 4.9 | 14 | 4.1 % |
| `tests/qa/test_from_spec.py` | 13.3 | 0.0 | 13.3 | 94 | 3.9 % |
| `tests/qa/test_geometry_checks.py` | 12.9 | 0.0 | 12.9 | 59 | 3.8 % |

### Per directory

| Directory | Total s | Tests with timing | Share |
|---|---|---|---|
| `tests/` (top level) | 276.4 | 989 | 81.4 % |
| `tests/qa/` | 46.2 | 449 | 13.6 % |
| `tests/integration/` | 14.4 | 15 | 4.2 % |
| `tests/contracts/` | 2.4 | 9 | 0.7 % |

### Setup vs call

- Call is 90 % of the measured time. Setup is noticeable only in two files: `tests/test_pipeline_gate.py`
  (12.0 s; the `repo` fixture at line 130 runs `git init` and commits per test) and
  `tests/integration/test_pipeline.py` (9.0 s; the fixture at line 43 builds a pipeline per test, 0.76-0.87 s each,
  e.g. every `test_corrupted_exports_fail[...]` parameter).
- Teardown is negligible everywhere.

### Root causes of the top entries (verified by reading the code)

| Cost | Where | Why |
|---|---|---|
| 20.5 s | `tests/test_pi_guard_adapter.py:142` `test_hook_timeout_blocks` x2 | The hook sleeps 30 s; the adapter kills it after the hard-coded `timeout=10` in `tools/hooks/pi_guard_adapter.py:104`. Each test waits the full 10 s. |
| 11.1 s | `tests/test_run_record.py:244` and the `nonzero_returncode` sibling | `run_stage(timeout=0.5)`, then the cleanup path in `src/dt_ai/core/run_record.py:207-210` waits `child.wait(timeout=5)` because the faked taskkill fails. Each test waits 5 s. |
| 12.0 s | `tests/test_spec_contour_shapes.py:310` | 32 000 wall quads (8001 rows x 4 walls), built in a Python loop, then `extract_spec`. Algorithmic cost in the spec extractor (and mesh construction), not I/O. |
| 5.8 s | `tests/test_spec_floors.py` `test_long_matching_chain_needs_no_recursion` | All-pairs floor matching in `src/dt_ai/spec/floors.py` (the #116 candidate target). |
| 44 s | `tests/test_pi_guard_contract.py` | Each test runs `node --input-type=module -e ...` against the installed Pi tools (lines 137, 161, 165, 183) plus the Python adapter; ~1-2.7 s per test is process start-up and module import. |
| 42 s | `tests/test_pipeline_gate.py` | Real `git` subprocesses (line 126) and the hook script via `sys.executable` (line 216). |

### External facts (source only claims; not re-verified here)

- `--durations=0` reports every phase but hides those under 0.005 s unless `-vv` is used:
  https://docs.pytest.org/en/stable/how-to/usage.html#profiling-test-execution-duration
- `pytest-xdist` (`pytest -n auto`) distributes tests over worker processes, one per CPU; `-s` does not work with it:
  https://pytest-xdist.readthedocs.io/en/stable/ . It is not a dependency of this repo today (verified: no
  `xdist` in `pyproject.toml` or `uv.lock`).

## How it applies to this repository

- The 400 s timeout of #116 is explained by growth (+874 tests since the 301 s baseline) plus contention from parallel
  cards; there is no single new regression. A 400 s cap on this machine with other cards running is now too tight
  for the full offline suite.
- `docs/research/repo-health.md` (lines 38-46) named the two algorithmic tests; they are still #1 and #4. But the
  subprocess-heavy hook/guard tests (`tests/test_pi_guard_*.py`, `tests/test_pipeline_gate.py`,
  `tests/test_session_context.py`, `tests/test_subagents.py`) together take ~153 s (45 %) and matter more.
- The #116 floors candidate (`src/dt_ai/spec/floors.py`) can at best save ~5.8 s (1.6 %) of the suite; it can not
  pass a 3 % acceptance gate on its own.

## Proposed next tasks (each keeps every test and assertion; no skips, no deselection)

1. **Make the two fixed waits injectable (value high, effort S).** Add a module-level constant or env override for
   the hook timeout in `tools/hooks/pi_guard_adapter.py:104` (default stays 10 s) and for the cleanup grace wait in
   `src/dt_ai/core/run_record.py:207-210` (default stays 5 s). The tests set them to ~1 s via `monkeypatch`/env and
   keep asserting `TimeoutExpired`, `decision == "block"` and the cleanup error text. Saves about 30 s of the 39 s of
   pure waiting (~8-9 % of the suite) with zero behaviour change in production. Needs the user to accept a small
   production-code seam.
2. **Run the suite with `pytest-xdist` (value highest, effort M).** Add `pytest-xdist` as a dev dependency and use
   `-n auto` (or a fixed `-n 8` to stay fair to parallel cards). With 32 logical CPUs and 90 % of time in call phases
   of independent tests, the expected wall time drops well below 100 s; must be proven by one measured run. Scope:
   find tests that share state outside `tmp_path` (fixed ports, files under the repo root, `.claude/` settings,
   env), fix them or group them with `--dist loadgroup`; the gate is the same counts (3195 passed, 9 skipped,
   13 deselected). Main risk: hidden ordering dependencies in the hook/guard tests.
3. **Template fixtures for git and pipeline setup (value medium, effort M).** Build the `repo` fixture of
   `tests/test_pipeline_gate.py:130` and the pipeline fixture of `tests/integration/test_pipeline.py:43` once per
   session in a template directory and `shutil.copytree` it into each test's `tmp_path`, so isolation is kept but
   `git init`/first build run once. Upper bound of the saving is the 21 s of setup in those files (~6 %). Must check
   that copied `.git` directories behave the same (absolute paths in config, hooks path).

Not proposed: speeding up `test_dense_wall_rows_keep_the_contour` by shrinking its data (that weakens the
regression); the right fix there is product performance of the spec extractor, which is #116's own scope.

## Open questions for the user

1. Is a test-only seam in production code (configurable hook timeout, configurable cleanup grace) acceptable, or
   must the timeout tests keep using the production constants?
2. May `pytest-xdist` become a dev dependency, and should the default `addopts` in `pyproject.toml` use it, or only
   an explicit `-n` in CI/autoresearch?
3. Should the #116 overnight protocol raise its 400 s timeout (for example to 600 s) or run only when no other card
   is active? Tonight's single run took 362 s with ~50 other python/node processes alive.

## Agent trace

- Card: `t_c9a06ef6` (research), profile `dt-worker-cursor`, model claude-opus (Hermes kanban worker).
- Written by: the worker directly; Cursor was not used (no code changes on this card).
- Commands: one full suite run (362 s), one aggregation script, `grep`/`sed` reads of the named files, two web
  page extracts (pytest docs, pytest-xdist docs).
- Sources: 2 external URLs; everything else verified by running or reading code in this worktree.
