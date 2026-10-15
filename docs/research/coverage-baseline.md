# Research Baseline: Non-DCC Test Suite Branch and Statement Coverage

## Summary

This baseline measures branch and statement coverage for the non-DCC test suite on Windows at commit `d25e3ad5a8561ec9cc4c99f9b147bbc890e52990` (CPython 3.14.7, coverage.py 7.16.2).
The test suite executed with `pytest -q -m "not blender and not dcc"` passed completely: 1370 passed, 0 failed, 2 skipped, 11 deselected, and 1 expected duplicate ZIP name warning in 137.34s (exit code 0). The first attempt under inherited MSYS settings had 4 failures (all in `tests/test_kpp1_export_safety.py`, MSYS path conversion); with native Windows paths they pass. An independent rerun confirmed identical results in 144.36s with identical totals and per-file coverage metrics.
Across all 58 measured Python source files in `src/`, coverage reached 92.24% statement coverage (7403/8026 statements; 623 missing) and 85.80% branch coverage (2924/3408 branch destinations; 484 missing), yielding a combined total of 90.32%. Per package: `dt_ai` 92.80% statements / 86.53% branches; `twinqa` 89.78% / 82.53%.
The 10 largest uncovered functions, ranked by missing statements + missing branches, are led by `dt_ai.cli.main.main` (44+23=67) and `from_source.decor_primitive_first` (35+23=58); 5 of the 10 are on the verification path (`twinqa` V007/V011 validators, `dt validate` dispatch, check C004 in `validate/bundle.py`), 5 are other live code, none is likely dead (one likely-dead helper, `from_source.wall_line`, sits outside the top 10).
Coverage is not added to project dependencies; the coverage data and JSON were kept outside the repository and are not committed.
Subprocess auto-instrumentation is not configured, and non-`src` scripts (`tools/`, `jobs/`, `adapters/`) are excluded from this denominator; this report does not establish actual native export safety as job safety scripts lie outside the denominator and native subprocess/DCC execution was not measured.
Five ranked test-writing proposals target verification negatives and boundary handling using synthetic in-memory fixtures without launching external DCC applications.

## Findings with Sources

### 1. Execution Environment and Reproduction
- **Commit and Runtime**: Source tree commit `d25e3ad5a8561ec9cc4c99f9b147bbc890e52990` under Windows CPython 3.14.7 and `coverage.py` version 7.16.2. Coverage instrumentation is run via `uv run --with coverage==7.16.2` without adding coverage to project dependencies.
- **Initial Run Environment Failure** (verified, from the first run's log): `4 failed, 1366 passed, 2 skipped, 11 deselected, 1 warning in 119.06s`. The four failures, all MSYS2/Git Bash path conversion (the tests launch a shell stage with POSIX-converted paths):
  - `tests/test_kpp1_export_safety.py::test_pipeline_preserves_old_build_and_atlas_uses_fresh_version`
  - `tests/test_kpp1_export_safety.py::test_blender_error_is_not_hidden_by_successful_grep`
  - `tests/test_kpp1_export_safety.py::test_build_stage_failure_stops_before_export`
  - `tests/test_kpp1_export_safety.py::test_long_safe_version_works_through_real_stage_launcher`

  Fix (environment only, no code change): unset the MSYS path translation variables (`env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL`) and pass native Windows paths (`pwd -W`) for `TMP`, `TEMP`, `TMPDIR`, `COVERAGE_FILE` and pytest's `--basetemp`. With that, all four pass (0 failed).
- **Baseline Verification**: The original baseline run completed cleanly with exit code 0 in 137.34s: 1370 passed, 2 skipped, 11 deselected, and 1 warning (`UserWarning: Duplicate name: 'same'` in [`tests/integration/test_pipeline.py`](../../tests/integration/test_pipeline.py#L22-L24), an expected test verifying rejection of duplicate members in archives per the run's pytest log).
- **Driver Rerun**: An independent driver rerun completed in 144.36s with identical counts (1370 passed, 2 skipped, 11 deselected, 1 warning) and equal parsed JSON totals and per-file data; JSON file timestamps differ, so no byte identity is claimed.
- **Core command** (as given by the card; also the reference for upstream issue artsafro/AGR-DigitalTwin#147):
  ```bash
  env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run --with coverage coverage run --branch --source=src -m pytest -q -m 'not blender and not dcc'
  uv run --with coverage coverage report --skip-covered
  uv run --with coverage coverage json -o <path outside the repo>
  ```
- **Reproduction procedure (Git Bash, from the worktree root; all coverage data and temp files OUTSIDE the repository)**:
  ```bash
  OUT=$(cd "$TMPDIR" && pwd -W)/coverage-baseline   # any directory outside the repo
  mkdir -p "$OUT/tmp"
  export COVERAGE_FILE="$OUT/.coverage"
  env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL TMP="$OUT/tmp" TEMP="$OUT/tmp" TMPDIR="$OUT/tmp" \
    uv run --with coverage==7.16.2 coverage run --branch --source=src -m pytest -q -m "not blender and not dcc" --basetemp="$OUT/pt"
  uv run --with coverage==7.16.2 coverage report --skip-covered
  uv run --with coverage==7.16.2 coverage json -o "$OUT/coverage.json"
  ```
  `pwd -W` matters: with inherited MSYS variables a `/c/...` `COVERAGE_FILE` makes `coverage report` find no data. The measured runs used the same selectors and flags; their data directory was a git-untracked folder in the worktree, which was moved outside the repository after measurement and is not committed.
- **Evidence Artifacts** (local, not committed): `coverage.json` (SHA256 `0a7414ec71261cf1e6a1391b8ae66b28df350581c82a6673dd6a6d189c3cdd73`), the recheck JSON, `report.txt` and the pytest logs, kept in the worker's scratch directory outside the repository.

### 2. Overall and Per-Package Coverage Breakdown
Coverage metrics adhere to standard `coverage.py` branch definitions [1] and CLI report/JSON specifications [2][3]:
- **Total Statements**: 7,403 / 8,026 covered (92.24%); 623 missing.
- **Total Branch Destinations**: 2,924 / 3,408 covered (85.80%); 484 missing branch destinations. JSON `num_partial_branches=374` matches report `BrPart=374`; this is distinct from 484 missing branch destinations [1][2].
- **Combined Coverage Denominator**: Evaluated as `(covered_lines + covered_branches) / (num_statements + num_branches)` = `(7403 + 2924) / (8026 + 3408)` = `10327 / 11434` = **90.32%** [1].
- **Module Coverage Breadth**: Measured across 58/58 Python source files in `src/`. No non-empty file had zero coverage; 20 source files achieved 100% complete coverage and were omitted from report output by `--skip-covered` [2][3].

#### Ranking and Aggregation Method
- **Function Regions**: Metrics use `coverage.py` JSON function regions from the saved `coverage.json` (exact interpreter-observed executable statements, avoiding AST line-span heuristics).
- **Sorting Order** (card rule: missed statements plus missed branches): Functions are sorted by:
  1. Score = `missing_lines + missing_branches` descending (both from the function's `summary` in the JSON)
  2. Missing executable statements descending
  3. File path ascending, then start line ascending
- **Package Summaries**: Package and subpackage metrics are computed by summing integer counters (`covered_lines`, `num_statements`, `covered_branches`, `num_branches`), never by averaging file percentages. If a denominator is zero, the result is displayed as `N/A`.

#### Reproduction Script for Package Totals and Top Functions
The following script (run outside the repository) extracts package totals and the top 10 uncovered functions from the coverage JSON, normalizing Windows backslashes:

```python
import json, sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))  # path to coverage.json
files = data["files"]

# Top 10 functions by (missing statements + missing branches), then missing statements, path, start
funcs = []
for file_path, file_data in files.items():
    norm_path = file_path.replace("\\", "/")
    for name, info in file_data.get("functions", {}).items():
        if not name:
            continue
        s = info["summary"]
        funcs.append({
            "name": name,
            "path": norm_path,
            "start": info["start_line"],
            "missing_stmts": s["missing_lines"],
            "missing_branches": s.get("missing_branches", 0),
        })

funcs.sort(key=lambda f: (-(f["missing_stmts"] + f["missing_branches"]), -f["missing_stmts"], f["path"], f["start"]))
print("Top 10 Functions:")
for i, f in enumerate(funcs[:10], 1):
    print(f"{i}. {f['name']} ({f['path']}:{f['start']}): {f['missing_stmts']}+{f['missing_branches']}")

# Package counters summary
packages = {
    "dt_ai": [p for p in files if p.replace("\\", "/").startswith("src/dt_ai/")],
    "twinqa": [p for p in files if p.replace("\\", "/").startswith("src/twinqa/")],
}
for pkg, pkg_files in packages.items():
    cov_s = sum(files[p]["summary"]["covered_lines"] for p in pkg_files)
    tot_s = sum(files[p]["summary"]["num_statements"] for p in pkg_files)
    cov_b = sum(files[p]["summary"]["covered_branches"] for p in pkg_files)
    tot_b = sum(files[p]["summary"]["num_branches"] for p in pkg_files)
    pct_s = f"{cov_s / tot_s * 100:.2f}%" if tot_s else "N/A"
    pct_b = f"{cov_b / tot_b * 100:.2f}%" if tot_b else "N/A"
    print(f"{pkg}: stmts {cov_s}/{tot_s} ({pct_s}), branches {cov_b}/{tot_b} ({pct_b})")
```

#### Per-Package and Subpackage Metrics
Data summed from the per-file counters of the saved `coverage.json`. Note: Parent package totals subsume their immediate-directory files and subpackages; do not sum overlapping parent rows.

| Package / Directory | Covered / Total Stmts | Stmt % | Missing Stmts | Covered / Total Branches | Branch % | Missing Branches |
|---|---|---|---|---|---|---|
| **`dt_ai` (total)** | **6,059 / 6,529** | **92.80%** | **470** | **2,409 / 2,784** | **86.53%** | **375** |
| `dt_ai/cli` | 126 / 171 | 73.68% | 45 | 36 / 60 | 60.00% | 24 |
| `dt_ai/core` | 595 / 680 | 87.50% | 85 | 171 / 232 | 73.71% | 61 |
| `dt_ai/drawing` | 22 / 22 | 100.00% | 0 | 4 / 4 | 100.00% | 0 |
| `dt_ai/geometry` | 2,008 / 2,199 | 91.31% | 191 | 865 / 1,036 | 83.49% | 171 |
| `dt_ai/intake` | 232 / 251 | 92.43% | 19 | 105 / 118 | 88.98% | 13 |
| `dt_ai/materials` | 53 / 56 | 94.64% | 3 | 11 / 14 | 78.57% | 3 |
| `dt_ai/placement` | 0 / 0 | N/A | 0 | 0 / 0 | N/A | 0 |
| `dt_ai/publish` | 22 / 23 | 95.65% | 1 | 9 / 10 | 90.00% | 1 |
| `dt_ai/spec` | 2,866 / 2,963 | 96.73% | 97 | 1,187 / 1,282 | 92.59% | 95 |
| `dt_ai/validate` | 134 / 163 | 82.21% | 29 | 21 / 28 | 75.00% | 7 |
| **`twinqa` (total)** | **1,344 / 1,497** | **89.78%** | **153** | **515 / 624** | **82.53%** | **109** |
| `twinqa` (immediate / root files) | 518 / 648 | 79.94% | 130 | 192 / 282 | 68.09% | 90 |
| `twinqa/geometry` | 826 / 849 | 97.29% | 23 | 323 / 342 | 94.44% | 19 |

### 3. Top 10 Functions Ranked by Missing Statements + Missing Branches
Verified by recomputation from the saved coverage JSON (script above). Classes follow the card: **VERIFICATION PATH** (twinqa checks, validate, export safety), **Other live code**, **Likely dead code**. Missing-line ranges are the statements coverage.py reported as not executed.

| Rank | Function | Location | Score (miss stmts + miss branches) | Missing / Total Stmts | Missing / Total Branches | Missing Line Ranges | Class |
|---|---|---|---|---|---|---|---|
| 1 | `main` | [`src/dt_ai/cli/main.py:67`](../../src/dt_ai/cli/main.py#L67) | 44 + 23 = **67** | 44 / 109 | 23 / 54 | 72–73, 75–80, 82–83, 85–86, 89–90, 92–96, 99, 101–106, 115, 127, 143, 169–175, 177–184 | **VERIFICATION PATH** (lines 177–184: `dt build` / `dt validate` dispatch and exit codes; the rest is other CLI subcommands) |
| 2 | `decor_primitive_first` | [`src/dt_ai/geometry/from_source.py:1062`](../../src/dt_ai/geometry/from_source.py#L1062) | 35 + 23 = **58** | 35 / 103 | 23 / 52 | 1081–1082, 1085, 1088–1089, 1091, 1101–1102, 1151–1177 | Other live code (experimental OBJ03 builder) |
| 3 | `inspect_run` | [`src/dt_ai/core/run_inspection.py:43`](../../src/dt_ai/core/run_inspection.py#L43) | 27 + 20 = **47** | 27 / 149 | 20 / 86 | 52, 56, 59, 62, 64, 67, 73, 93–94, 96, 101, 106, 109, 112, 119, 127, 130, 172, 183–186, 192, 198–199, 207, 225 | Other live code (run-evidence inspector, not a delivery check) |
| 4 | `vpm_texture_findings` | [`src/twinqa/png.py:92`](../../src/twinqa/png.py#L92) | 23 + 18 = **41** | 23 / 52 | 18 / 36 | 102–103, 105, 108–110, 115, 118, 121, 126, 128, 130–133, 135–138, 140–141, 152–153 | **VERIFICATION PATH** (V007) |
| 5 | `build_from_modules` | [`src/dt_ai/geometry/from_source.py:1329`](../../src/dt_ai/geometry/from_source.py#L1329) | 20 + 18 = **38** | 20 / 147 | 18 / 66 | 1366, 1389, 1395, 1404–1405, 1448–1449, 1455–1459, 1462–1463, 1465–1468, 1479, 1496 | Other live code (experimental OBJ03 builder) |
| 6 | `validate` | [`src/dt_ai/validate/bundle.py:23`](../../src/dt_ai/validate/bundle.py#L23) | 28 + 7 = **35** | 28 / 128 | 7 / 22 | 137–138, 141–145, 147–154, 156–164, 166–169 | **VERIFICATION PATH** (check C004 readback) |
| 7 | `geojson_findings` | [`src/twinqa/geojson.py:86`](../../src/twinqa/geojson.py#L86) | 14 + 10 = **24** | 14 / 53 | 10 / 34 | 90–93, 97, 100, 103, 105, 110, 114, 119–120, 123, 139 | **VERIFICATION PATH** (V011) |
| 8 | `normal_convention` | [`src/twinqa/png.py:63`](../../src/twinqa/png.py#L63) | 15 + 6 = **21** | 15 / 15 | 6 / 6 | 71–85 | **VERIFICATION PATH** (V007 normal map) |
| 9 | `Spec.consistent` | [`src/dt_ai/spec/model.py:193`](../../src/dt_ai/spec/model.py#L193) | 10 + 10 = **20** | 10 / 70 | 10 / 72 | 204, 207, 209, 218, 221, 223, 227, 240, 252, 263 | Other live code (spec input validator) |
| 10 | `extract_exterior` | [`src/dt_ai/geometry/exterior.py:48`](../../src/dt_ai/geometry/exterior.py#L48) | 6 + 13 = **19** | 6 / 139 | 13 / 82 | 73, 77, 97, 166, 168, 170 | Other live code (exterior adapter) |

Next by score (outside the top 10): `RunRecord.run_stage` ([`src/dt_ai/core/run_record.py:142`](../../src/dt_ai/core/run_record.py#L142), 13 + 5 = 18), `face_planes` (`from_source.py:523`, 11 + 7 = 18), `inset_panels` (`from_source.py:695`, 9 + 9 = 18), `ValidationReport.summary` ([`src/twinqa/report.py:82`](../../src/twinqa/report.py#L82), 11 + 6 = 17), `run_blender` ([`src/dt_ai/core/build.py:17`](../../src/dt_ai/core/build.py#L17), 12 + 4 = 16).

### 4. Code Classification Details
Static inspection and call-site tracing (grep over `src/`, `tools/`, `jobs/`; read by me) indicate that the uncovered regions in the top 10 functions are reachable or experimental paths rather than dead code. `run_blender` and `RunRecord.run_stage` below are outside the top 10 but are discussed because they share the code path of ranked entries:
1. **Live Mixed Dispatch CLI** (`cli.main.main`): Lines 177–184 execute bundle build and validation orchestration and return specific process exit codes (exit 1 on check failure; exit 2 if `command == "validate"` and `not report.development_checks_passed`). Additional missing lines cover CLI subcommands (`inspect`, `index-pdf`, `from-source`, `registry`) and CLI argument error paths.
2. **Live Delivery Validation Paths** (`twinqa`):
   - `normal_convention` ([`src/twinqa/png.py:63`](../../src/twinqa/png.py#L63)): Has 100% missing statements in this parent run, but is statically wired at line 136 of `vpm_texture_findings`. Its curl correlation heuristic evaluates green/red channels to distinguish DirectX from OpenGL conventions or returns undecided; it does not provide a generic DirectX guarantee.
   - `vpm_texture_findings` ([`src/twinqa/png.py:92`](../../src/twinqa/png.py#L92)): Missing statements correspond to negative validation checks for delivery standard V007 ([docs/domain/validation.md](../domain/validation.md#L12)), including alpha detection in Normal/ERM maps, wrong map resolutions, a VPM ERM heuristic where R channel non-zero on >=95% pixels emits a REVIEW finding (a heuristic review flag, not a reliable channel swap detector), and resolution mismatch between Diffuse and ERM/Normal.
   - `geojson_findings` ([`src/twinqa/geojson.py:86`](../../src/twinqa/geojson.py#L86)): Missing statements represent defensive schema checks for V011 ([docs/domain/validation.md](../domain/validation.md#L16)), such as handling non-UTF-8 streams, invalid JSON syntax, non-Point geometries, decimal precision reviews (>3 decimal places), extra/missing property keys, and missing `Glasses` arrays.
3. **DCC-Excluded Verification Logic** (`dt_ai.validate.bundle.validate` and `dt_ai.core.build.run_blender`):
   - `bundle.validate` lines 137–138, 141–145, 147–154, 156–164, 166–169 implement check `C004` (a synthetic development bundle checker verifying binary FBX 7400 readback, face/vertex/UV topology, material assignment, and embedded texture hash match per [docs/domain/validation.md](../domain/validation.md#L29-L30); this is a synthetic development bundle check, not official delivery certification). This block is gated by `if blender:` (line 131) and emits `status="not_run"` when Blender is absent (line 174).
   - `run_blender` ([`src/dt_ai/core/build.py:17`](../../src/dt_ai/core/build.py#L17)): Invokes headless Blender subprocesses. Although excluded in `-m "not blender and not dcc"` test runs, the process orchestration and error handling (non-zero exit codes, missing output evidence) can be tested using a mock subprocess without launching real DCC.
   - *Discrepancy note (Seen, not mine, not fixed)*: The `run_blender` command construction at [`src/dt_ai/core/build.py:21`](../../src/dt_ai/core/build.py#L21) lacks `--disable-autoexec`, whereas [`docs/domain/export-import.md:18`](../domain/export-import.md#L18) recommends `--background --factory-startup --disable-autoexec --python-exit-code 1` for headless runs.
4. **Live Provenance & Defensive Envelope Validation** (`dt_ai.core`):
   - `inspect_run` ([`src/dt_ai/core/run_inspection.py:43`](../../src/dt_ai/core/run_inspection.py#L43)): Validates run manifests and execution ledgers. The function docstring and return payload explicitly state that it verifies evidence envelope consistency, **not** delivery certification (`delivery_passed: False`, lines 46–47, 232). Missing lines handle malformed IDs, fingerprint mismatches, non-consecutive attempts, and missing output manifests.
   - `RunRecord.run_stage` ([`src/dt_ai/core/run_record.py:142`](../../src/dt_ai/core/run_record.py#L142)): Missing lines represent failure branches during external process execution, specifically the Windows process tree cleanup (`taskkill /PID ... /T /F`), timeout escalation, ledger stop markings, and input fingerprint mutations during stage execution.
5. **Experimental Geometry Paths** (`dt_ai.geometry.from_source`):
   - `decor_primitive_first` and `build_from_modules` belong to the modular OBJ03 reconstruction pipeline. Per [docs/PROJECT_STATE.md](../PROJECT_STATE.md#L19), OBJ03 was marked unsuccessful on 2026-10-14 (#117) and remains paused. Call sites (grep): `build_from_modules` is called from `src/dt_ai/cli/main.py:99` (`dt from-source`) and `tools/qa/run_from_source.py:59`; `decor_primitive_first` is called from `from_source.py:1401` inside `build_from_modules`. Live but experimental, not a verification path.
6. **Input guards** (other live code):
   - `Spec.consistent` ([`src/dt_ai/spec/model.py:193`](../../src/dt_ai/spec/model.py#L193)) is a pydantic `model_validator(mode="after")`, so it runs on every `Spec` construction: `src/dt_ai/intake/check.py:214`, `src/dt_ai/spec/compare.py:100`, `src/dt_ai/spec/mesh.py:1896`, `tools/qa/check_geometry.py:37`. All 10 missing statements are `raise ValueError(...)` lines whose guard was never true (e.g. line 204 terraces with an old `spec_version`, 207 decor version, 209 `roof_structures` version, 218 parapet version, 263 decor wall index out of range). It protects spec input, not the delivery; not in the card's verification-path definition.
   - `extract_exterior` ([`src/dt_ai/geometry/exterior.py:48`](../../src/dt_ai/geometry/exterior.py#L48)) is called by `tools/run_exterior.py:38` (exterior adapter, see `docs/agr/EXTERIOR_ADAPTER.md` and `jobs/PSU275/STATE.md`) and tested in `tests/test_exterior_adapter.py`. Its 6 missing statements are guard raises (73 invalid microgap closure, 77 invalid window bounds, 97 footprint repair split) and the opening branches at 166–170 (unmatched wall-top gap, clipped-at-top opening); most of its 13 missing branches are loop exits. Live geometry code, not a verification path.
7. **Likely dead code**: none of the top 10. Outside the top 10, `from_source.wall_line` has zero static call sites (see below).

### 5. Notable Functions Outside the Top 10
- **`from_source.wall_line`** ([`src/dt_ai/geometry/from_source.py:198`](../../src/dt_ai/geometry/from_source.py#L198)): 11/11 statements missing, 4/4 branches missing. A repository-wide code search reveals zero static call sites. It is classified as an uncalled experimental candidate (not deletion proof, as it may have been retained for prototype algorithms).
- **`from_source.band_box`** ([`src/dt_ai/geometry/from_source.py:471`](../../src/dt_ai/geometry/from_source.py#L471)): Identified as reachable; statically invoked at line 1459 within `build_from_modules` for parapet band construction.
- **`ValidationReport.summary`** ([`src/twinqa/report.py:82`](../../src/twinqa/report.py#L82)): 11/11 statements missing in unit test execution, but actively invoked by the standalone CLI tool [`tools/qa/validate_package.py:233`](../../tools/qa/validate_package.py#L233) when `--json` is not requested.

### 6. Denominator and Instrumentation Boundaries
- **Subprocess Auto-Instrumentation**: No automatic subprocess coverage tracking (e.g. `sitecustomize.py`, pytest-cov subprocess wrappers) is configured. Coverage measures only statements executed directly within the pytest parent interpreter process. Child processes spawned via `subprocess.Popen` or shell scripts are not instrumented; absence of coverage in child runners does not imply code was unexecuted in subprocesses.
- **`src/`-Only Denominator**: Coverage measurement was restricted to `--source=src`. Tools ([`tools/qa/validate_package.py`](../../tools/qa/validate_package.py)), job scripts (e.g. `jobs/KPP1/scripts/export_safety.py`), and DCC bridge adapters ([`adapters/blender/bridge.py`](../../adapters/blender/bridge.py)) are excluded from the statement/branch denominator.
- **Shell Stage Tests vs Real DCC and Export Safety**: Existing tests in [`tests/test_kpp1_export_safety.py`](../../tests/test_kpp1_export_safety.py#L1-L160) pass using a mock Blender shell script (`mock_blender.py`). They exercise shell orchestration and output directory reservation, but do not execute `src/` modules or establish actual native export safety: job safety scripts (e.g. `jobs/KPP1/scripts/export_safety.py`) lie outside the measured denominator, and native subprocess or DCC execution was not measured.

## How It Applies to This Repository

- **Audit & Delivery Enforcement (`twinqa`)**:
  - The delivery validation rules V001–V017 ([docs/domain/validation.md](../domain/validation.md#L5-L26)) require strict enforcement of negative cases. Currently, happy-path delivery passes are exercised in tests, while these specific negative validation lines/branches were unobserved in this parent interpreter run (note: subprocess coverage is not tracked). We do not assert that negative criteria lack automated testing globally, but rather that these executable lines were not hit in this suite.
  - File paths: [`src/twinqa/png.py`](../../src/twinqa/png.py), [`src/twinqa/geojson.py`](../../src/twinqa/geojson.py), [`src/twinqa/fbx_header.py`](../../src/twinqa/fbx_header.py), [`src/twinqa/report.py`](../../src/twinqa/report.py).
- **Bundle Validation & DCC Readback (`dt_ai.validate`)**:
  - Check `C004` ([`src/dt_ai/validate/bundle.py:131-172`](../../src/dt_ai/validate/bundle.py#L131-L172)) is a synthetic development bundle checker (not official delivery certification) containing topology and UV readback comparison logic. Orchestrating this via synthetic audit dictionaries allows testing readback validation without depending on local Blender installations.
- **Provenance & Run Records (`dt_ai.core`)**:
  - The provenance integrity module ([`src/dt_ai/core/run_inspection.py`](../../src/dt_ai/core/run_inspection.py)) and stage execution engine ([`src/dt_ai/core/run_record.py`](../../src/dt_ai/core/run_record.py)) ensure verifiable audit trails for skills like `run-evidence`. Testing timeout cleanup and malformed envelopes hardens the execution ledger against corruption during aborted runs.
- **CLI Dispatch & Process Contracts (`dt_ai.cli`)**:
  - The CLI entrypoint ([`src/dt_ai/cli/main.py`](../../src/dt_ai/cli/main.py)) defines process contracts and exit codes. Adding tests for `dt build`, `dt validate`, and error conditions ensures CLI exit codes (0, 1, 2, 3) remain reliable for CI and scripting.
- **Research Scope**:
  - This document provides a research baseline and prioritized proposals; as a research task, it requires no production code changes and no regression test requirements.

## Proposed Next Tasks

Ranked by the card rule: verification-path gaps first, then by score from section 3. No proposal launches Blender, 3ds Max or Revit; all use small synthetic fixtures (marked synthetic).

### Proposal 1 (verification path, S): V007 texture checks — `vpm_texture_findings` and `normal_convention`
- **Scope**: Unit tests for [`src/twinqa/png.py:92`](../../src/twinqa/png.py#L92) `vpm_texture_findings` (rank 4, 23 + 18 = 41) and [`src/twinqa/png.py:63`](../../src/twinqa/png.py#L63) `normal_convention` (rank 8, 15 + 6 = 21). Synthetic in-memory PNGs/arrays: a DirectX-style and an OpenGL-style normal map plus a flat/undecided one (the curl heuristic may return undecided; it is no DirectX guarantee), alpha in ERM/Normal, wrong map size, ERM with R non-zero on >= 95% of pixels (REVIEW finding), Diffuse smaller than ERM/Normal. Missing lines to hit: png.py 71–85, 102–153 (see table).
- **Value**: High — V007 is a delivery check run by `tools/qa/validate_package.py:98`; its negative branches are unexecuted, so a regression that silences a finding would go unnoticed. Up to 38 statements + 24 branches.
- **Effort**: S.

### Proposal 2 (verification path, S): V011 GeoJSON negatives — `geojson_findings`
- **Scope**: Unit tests for [`src/twinqa/geojson.py:86`](../../src/twinqa/geojson.py#L86) `geojson_findings` (rank 7, 14 + 10 = 24): invalid UTF-8, invalid JSON, not a FeatureCollection, non-Point geometry, more than 3 decimal places, missing/extra property keys, missing `Glasses`. Missing lines 90–93, 97, 100, 103, 105, 110, 114, 119–120, 123, 139. Optionally the formatting of [`src/twinqa/report.py:82`](../../src/twinqa/report.py#L82) `ValidationReport.summary` (11 + 6 = 17, used by `tools/qa/validate_package.py:233`).
- **Value**: High — V011 is called from `tools/qa/validate_package.py:111` and `:205`; corrupt GeoJSON deliverables must produce findings.
- **Effort**: S.

### Proposal 3 (verification path, M): `dt validate` / `dt build` dispatch and check C004 readback
- **Scope**: Tests for [`src/dt_ai/cli/main.py:67`](../../src/dt_ai/cli/main.py#L67) `main` lines 177–184 (rank 1; build/validate dispatch, exit 1 on failed checks, exit 2 when `validate` and not `development_checks_passed`) and [`src/dt_ai/validate/bundle.py:23`](../../src/dt_ai/validate/bundle.py#L23) `validate` lines 137–169 (rank 6, 28 + 7 = 35; C004, gated by `if blender:` at line 131). Use a fake Blender executable or a monkeypatched [`src/dt_ai/core/build.py:17`](../../src/dt_ai/core/build.py#L17) `run_blender` (12 + 4 = 16) returning a synthetic `audit.json`, plus a synthetic archive with a binary FBX 7400 header, to drive the readback comparison both to pass and to fail. The other subcommands of `main` (`inspect`, `index-pdf`, `from-source`, `registry`, lines 72–143, 169–175) can be parametrised in the same file.
- **Value**: High — C004 and the CLI exit codes are what CI and agents read; today they run only with a real Blender (`-m blender`). Depends on open question 1.
- **Effort**: M.

### Proposal 4 (other live code, M): run-evidence inspector — `inspect_run` (+ `RunRecord.run_stage`)
- **Scope**: Tests for [`src/dt_ai/core/run_inspection.py:43`](../../src/dt_ai/core/run_inspection.py#L43) `inspect_run` (rank 3, 27 + 20 = 47; used by `tools/harness_status.py:20`): malformed run id, fingerprint mismatch, non-consecutive attempts, missing/unreadable output manifest (missing lines 52–225 per table). Optionally [`src/dt_ai/core/run_record.py:142`](../../src/dt_ai/core/run_record.py#L142) `RunRecord.run_stage` (13 + 5 = 18): timeout and process-tree kill path, input fingerprint change during a stage.
- **Value**: Medium — protects the evidence envelope that harness status relies on; not a delivery check (`delivery_passed` stays false by design).
- **Effort**: M.

### Proposal 5 (other live code, S): input-guard negatives — `Spec.consistent` and `extract_exterior`
- **Scope**: Parametrised `pytest.raises(ValueError)` tests for [`src/dt_ai/spec/model.py:193`](../../src/dt_ai/spec/model.py#L193) `Spec.consistent` (rank 9, 10 + 10 = 20; lines 204, 207, 209, 218, 221, 223, 227, 240, 252, 263 — version gates and level/decor/floor reference errors) and [`src/dt_ai/geometry/exterior.py:48`](../../src/dt_ai/geometry/exterior.py#L48) `extract_exterior` (rank 10, 6 + 13 = 19; lines 73, 77, 97 guard raises, 166–170 unmatched wall-top gap and clipped-at-top opening) in the existing `tests/test_exterior_adapter.py` style.
- **Value**: Medium — every `Spec` load (intake check, compare, mesh, `tools/qa/check_geometry.py`) passes through `consistent`; a broken guard would admit an inconsistent spec silently.
- **Effort**: S.

Not proposed: the experimental OBJ03 builders `decor_primitive_first` (rank 2) and `build_from_modules` (rank 5) while OBJ03 is paused (open question 2).

## Open Questions for User

Advisory for the follow-up test tasks; none blocks this baseline.

1. **C004 testing strategy**: should C004 and `dt validate` exit codes be exercised in the fast non-DCC suite with a fake Blender (Proposal 3), or stay covered only by real Blender runs (`-m blender`)?
2. **OBJ03 builders**: should tests be written for `decor_primitive_first` / `build_from_modules` while OBJ03 is paused, and should the uncalled `from_source.wall_line` be kept or removed in a cleanup task?
3. **Order of the two S tasks**: V007 (Proposal 1) or V011 (Proposal 2) first?

Sources:
- [1] **Coverage.py Branch Coverage Documentation**: Explains branch execution tracking, branch destinations, and combined report calculation: https://coverage.readthedocs.io/en/latest/branch.html
- [2] **Coverage.py Report Command (`cmd_report`)**: Documents `coverage report` CLI options including `--skip-covered`: https://coverage.readthedocs.io/en/latest/commands/cmd_report.html
- [3] **Coverage.py JSON Command (`cmd_json`)**: Documents `coverage json` command and output file options: https://coverage.readthedocs.io/en/latest/commands/cmd_json.html

### Local Repository Sources
- Baseline coverage artifacts (local evidence outside the repository, not committed; verified by me):
  - `coverage.json` (SHA256: `0a7414ec71261cf1e6a1391b8ae66b28df350581c82a6673dd6a6d189c3cdd73`), recheck JSON, `report.txt`, pytest logs
- Core implementation & validation modules (locally verified):
  - [`src/dt_ai/cli/main.py`](../../src/dt_ai/cli/main.py)
  - [`src/dt_ai/validate/bundle.py`](../../src/dt_ai/validate/bundle.py)
  - [`src/dt_ai/core/run_inspection.py`](../../src/dt_ai/core/run_inspection.py)
  - [`src/dt_ai/core/run_record.py`](../../src/dt_ai/core/run_record.py)
  - [`src/dt_ai/core/build.py`](../../src/dt_ai/core/build.py)
  - [`src/dt_ai/geometry/from_source.py`](../../src/dt_ai/geometry/from_source.py)
  - [`src/twinqa/png.py`](../../src/twinqa/png.py)
  - [`src/twinqa/geojson.py`](../../src/twinqa/geojson.py)
  - [`src/twinqa/report.py`](../../src/twinqa/report.py)
- Standalone tools and tests (locally verified):
  - [`tools/qa/validate_package.py`](../../tools/qa/validate_package.py)
  - [`tests/test_kpp1_export_safety.py`](../../tests/test_kpp1_export_safety.py)
- Project rules and state (locally verified):
  - [`docs/PROJECT_STATE.md`](../PROJECT_STATE.md)
  - [`docs/domain/validation.md`](../domain/validation.md)
  - [`docs/domain/export-import.md`](../domain/export-import.md)
