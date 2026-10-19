# Experiment: logic of the project's scripts and pipelines

Card t_e8a3e3a4. Report under test: `docs/research/scripts-logic.md` on local branch
`docs/research-scripts-logic` (commit e26eeda; the branch is **not on origin**, so the card's
`git show origin/...` command fails). Base: `main` @ 91131e9.

## Question

The report ranks five simplifications. Two have a measurable claim and touch code the project runs today:

- **M1 (report P1)**: `twinqa.scene.readback` accepts valid JSON from a Blender process that exits nonzero.
- **M2 (report P2)**: the headless Blender call sites differ in flags, exit/output/timeout handling;
  one shared runner removes those differences.

P3/P4 (job shell pipelines -> Python, cross-job decoupling) are multi-day refactors, outside the time box.
P5 (unused imports) is checked as a side note only.

## Setup

- Synthetic fake Blender: `experiments/scripts-logic/fake_blender.py`, launched through a `blender.cmd`
  wrapper in `%TEMP%\agr-exp-t_e8a3e3a4\` (set as `TWINQA_BLENDER` / passed as executable). Modes:
  `ok`, `valid_exit7` (writes valid JSON, exits 7), `no_output`, `malformed`, `empty`, `hang` (sleeps 120 s).
  No real Blender, no data/ or etalon files used.
- Sites probed with their real code (imported, not copied): `dt_ai.core.build.run_blender`,
  `twinqa.scene.readback`, `tools/qa/check_clearance.faces_from_fbx`,
  `tools/qa/run_benchmark.blender_run` + `produced` (what `run()` does after each step),
  `technical_library/uv_continuous/common.run_dcc`. `tools/run_profile_pilot.py` / `run_profile_checks.py`
  go through `RunRecord.run_stage` (already tree-kills on timeout) and were not probed.
- Prototype: `experiments/scripts-logic/blender_runner.py` (53 non-blank lines): fixed flags
  `--background --factory-startup --disable-autoexec --python-exit-code 1`, mandatory timeout,
  `Popen` + `taskkill /T /F` on timeout, log file, nonzero exit rejected, promised outputs must exist,
  be non-empty and parse as JSON.
- Commands:
  - `uv run python experiments/scripts-logic/probe_matrix.py %TEMP%/agr-exp-t_e8a3e3a4` (full matrix, ~6 min
    because two baseline hang probes take 120 s each)
  - `... probe_matrix.py <dir> runner` (prototype only, after the tree-kill change)
  - `uv run pytest -q experiments/scripts-logic/test_blender_runner.py` -> 7 passed
  - `uv run pytest -q tests/qa/test_scene.py tests/qa/test_from_spec.py tests/integration --basetemp=<scratch>`
    -> 175 passed, 1 skipped, 3 runs: 37.8 / 37.1 / 37.3 s (median 37.3 s). Project code untouched.
    (Without `--basetemp` 30 tests error: `%TEMP%\pytest-of-artsafro` is not writable on this host.)

## Results

Outcome per bad mode: `accepted` = bad run returned data (worst), `raw` = fails with an unrelated
exception type (`JSONDecodeError`, `CalledProcessError`, `FileNotFoundError`, `TimeoutExpired`),
`clear` = `RuntimeError` naming the step/exit.

| Site | valid JSON + exit 7 | exit 0, no output | malformed JSON | empty file | hang, timeout 2 s | `--disable-autoexec` |
|---|---|---|---|---|---|---|
| `dt_ai.core.build.run_blender` | clear | clear | raw | raw | not probed (timeout fixed 180 s) | no |
| `twinqa.scene.readback` | clear | clear | raw | raw | clear after **120.1 s** | no |
| `check_clearance.faces_from_fbx` | raw | raw | raw | raw | not probed (fixed 900 s) | no |
| `run_benchmark.blender_run` + `produced` | clear | clear | raw | clear | raw after **120.1 s** | yes |
| `uv_continuous.run_dcc` | raw | **accepted** | **accepted** | **accepted** | **no timeout at all** | yes |
| **prototype `blender_runner.run`** | clear | clear | clear | clear | clear after **2.6 s** | yes |

| Metric | Baseline (5 sites) | Prototype |
|---|---|---|
| Bad runs accepted (of 20) | 3 (all `run_dcc`; it checks no output) | 0 |
| Bad runs failing with an unrelated exception (of 20) | 10 | 0 |
| Bad runs rejected with a clear error (of 20) | 7 | 20 (4 modes, same for every caller) |
| Timeout 2 s honoured when the process has a child | no: 120.1 s (60x) | yes: 2.6 s |
| Python Blender command builders with `--disable-autoexec` (7 found) | 4 / 7 | 7 / 7 if adopted |
| Overhead, `ok` mode, median of 5 | 0.08 s (`readback`) | 0.08 s |
| Code at the 5 sites | ~59 lines of runner logic | 53-line module + ~3 lines per site (not smaller) |

The 120 s hang: `subprocess.run(..., timeout=)` kills only the direct child (`cmd.exe` here), then waits
for the pipes, which the grandchild still holds. Real `blender.exe` started directly would be killed, but
any shim or launcher on `TWINQA_BLENDER`/`PATH` (e.g. a `.cmd` or package-manager shim, `blender-launcher.exe`)
makes the timeout ineffective. `RunRecord` already handles this with `taskkill /T` (`run_record.py:185-215`).

Side check (P5): `ruff --select F401` confirms exactly the two unused imports the report names
(`src/dt_ai/core/build.py:3 tempfile`, `src/dt_ai/publish/bundle.py:1 BytesIO`).

## Verdicts

- **M1, exit code check in `scene.readback`: reject (already done).** `src/twinqa/scene.py:57-58`
  on `main` rejects nonzero exit; probe `valid_exit7` -> `RuntimeError`. The report's claim is stale.
  The real residual gaps are elsewhere (table above): malformed/empty JSON fails as a raw
  `JSONDecodeError`, `check_clearance` loses stderr, `run_dcc` accepts a missing output and has no timeout.
- **M2, one shared headless Blender runner: adopt.** 0 accepted / 0 raw of 20 bad runs vs 3 / 10,
  timeouts honoured with child processes (2.6 s vs 120 s), uniform isolation flags, no runtime cost.
  It does not reduce line count; the gain is one tested contract instead of five.

## Proposed follow-up (adopt)

**Title:** Shared headless Blender runner for Python call sites
**Scope:** move `experiments/scripts-logic/blender_runner.py` into `src/twinqa/` (or `dt_ai.core`), with its
tests; switch `dt_ai.core.build.run_blender`, `twinqa.scene.readback`, `tools/qa/check_clearance.faces_from_fbx`,
`tools/qa/run_benchmark.blender_run` (and `run_from_source.py` through it), `technical_library/uv_continuous/common.run_dcc`
(add a timeout and an output check there). Keep `RunRecord.run_stage` sites as they are (they already
tree-kill), but share the flag tuple. Drop the two unused imports in the same PR. Acceptance:
`tests/qa`, `tests/integration` green; probe matrix: 0 accepted, 0 raw.

Note for the research branch: push `docs/research-scripts-logic` to origin, or the card command fails.
