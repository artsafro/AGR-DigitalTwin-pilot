# Repository Health: Code, Test Infrastructure, and Architectural Soundness

Pinned baseline commit: `a1052e3d3a3c5ef096028fb68982e1337da4eba4`
Measurement date: 2026-10-15
Planned timebox: ~40–55 minutes (bounded audit)
Environment: Windows (CPython 3.14.7), CPU-only test execution (Blender and live DCC excluded; native DCC roundtrips unrun; tools/adapters/jobs not fully covered; static import survey does not measure branch metrics)
Ephemeral artifacts: Local `.health-*` files (`.health-pytest2.xml`, `.health-metrics.json`, etc.) are temporary inspection caches, not delivered repository assets.

---

## Summary

- **Audit Scope & Baseline**: Evaluated repository health at commit `a1052e3d3a3c5ef096028fb68982e1337da4eba4` within a planned timebox (~40–55 min bounded audit). Scope is restricted to CPU-only test execution (native DCC roundtrips unrun; `tools/`, `adapters/`, and `jobs/` not fully test-covered; static import survey does not measure dynamic branch metrics).
- **Repository Inventory**: 884 tracked files, 502 Python files across 7 roots (`jobs`: 208, `tools`: 98, `tests`: 63, `adapters`: 60, `src`: 58, `technical_library`: 12, `.claude`: 3). `src/` contains 45 non-init modules (11,062 lines); `tests/` contains 61 discovery test modules (12,183 lines).
- **Test Suite Profile**: Pytest execution completed in 122.93s pytest-reported elapsed time (122.906s suite XML duration) across 1,330 recorded testcases (1,328 passed, 2 skipped due to unprivileged Windows symlinks, 11 deselected by `-m 'not blender and not dcc'`, 1 expected zip warning, 0 failures in a clean environment).
- **Runtime Concentration**: Test execution is heavily concentrated: the top 10 test modules consume 77.6% (93.58s) of total testcase time, with the top 3 subprocess-heavy suites (`test_pipeline_gate`, `test_session_context`, `test_subagents`) consuming 37.7% (45.39s).
- **Static Reachability vs Execution Coverage**: All 10 modules flagged by naive import metrics have verified static reachability via direct package imports or transitive callers. There are zero proven wholly unreached modules statically, but true dynamic statement/branch coverage (proposed via `coverage run --branch --source=src`) has not been measured.
- **Code Duplication**: Identified 9 AST duplicate groups across `src/`, `tools/`, `adapters/`, and `technical_library/` (excluding `jobs/`), capturing clones where function names/signatures differ but body statements and variable names match, alongside unflagged one-statement and docstring-differentiated UV math utilities.
- **Checker Independence Risk**: `twinqa.geometry.checks.inner_outlines_match` shares identical body logic with generator `dt_ai.spec.mesh._inner_outlines_match` (function names differ), introducing a potential shared implementation risk that generator quirks could correlate failure modes rather than being caught independently (this is an architectural risk, not a proven false pass).
- **Geometry Kernel Semantics**: Weld and tolerance strategies differ intentionally by design: 3D multi-grid union-find (`dt_ai.spec.mesh`), 1D axis snapping with fixed anchors (`from_spec.py`), coordinate rounding at 8/9 decimal places (`connect.py`, `shell.py`), and single-grid voxel hashing (`twinqa.geometry.mesh`). Grid hashing exhibits voxel boundary splitting and diagonal inflation per its docstring semantics, which is not an automatic defect.
- **Documentation Granularity**: `docs/domain/validation.md:5` blanket statement `(spec only, not implemented)` is stale against existing verification tooling, while `docs/pipeline.md:26` correctly marks Stage 15 as partial. Pipeline stages 2 and 6 exhibit status and link granularity gaps relative to existing spec and decor code, though production stages require real-object acceptance to become proven.

---

## Findings

### 1. Test Suite Performance and Execution Profile

- **Measured Evidence**:
  - Initial run (`.health-pytest.log` / `.health-pytest.xml`): Recorded 1,330 testcase records (4 failed, 1,324 passed, 2 skipped) due to MSYS path translation inheriting environment exclusions (`C:\c\Users\...` path resolution in subprocess bash calls). No codebase modification was needed; unsetting conversion variables (`env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL`) resolved all 4 failures.
  - Driver run (`.health-pytest2.log` / `.health-pytest2.xml`): Executed `uv run pytest -q --durations=25 -m 'not blender and not dcc' --basetemp=docs/research/.health-tmp2 --junitxml=docs/research/.health-pytest2.xml`. Pytest-reported elapsed time was 122.93s (1,328 passed, 2 skipped, 11 deselected, 1 warning, 0 failed across 1,330 testcase records).
  - Scope boundary: This was a strictly CPU-only, non-DCC execution. Native DCC roundtrips and live Blender instances were deselected (`-m 'not blender and not dcc'`) and remain unrun. Subsystems in `tools/`, `adapters/`, and `jobs/` are not comprehensively covered by the automated test suite.
  - Ephemeral artifacts: Local `.health-*` files (`.health-pytest.log`, `.health-pytest2.xml`, `.health-metrics.json`) are temporary inspection files that reproduction commands regenerate locally; they are not tracked deliverables.
- **Timing Decomposition**:
  - Test suite XML duration attribute: 122.906s.
  - Sum of individual test case durations across all 61 discovery modules: 120.541s (across 1,330 recorded testcases).
  - Unallocated pytest suite overhead: 2.365s (122.906s suite XML - 120.541s testcase sum). This residual reflects test collection, test runner orchestration, and JUnit XML serialization/reporting within pytest (individual JUnit testcase times already include fixture setup, call, and teardown phases [1]). The residual relative to the pytest-reported 122.93s elapsed time is 2.389s (122.93s - 120.541s). This is unallocated framework overhead, not an end-to-end shell/uv wall clock or installation benchmark.
  - Test phase monitoring: Pytest measures durations across `setup`, `call`, and `teardown` phases [1]. In specific algorithmic bottlenecks such as `test_dense_wall_rows_keep_the_contour` (6.65s call phase), the call phase dominates execution time.
- **Concentration of Runtimes**:
  - The top 10 slowest test modules account for 93.581s (77.6% of total testcase execution time).
  - The top 3 slowest modules alone consume 45.387s (37.7%):
    - `tests.test_pipeline_gate`: 79 tests, 18.495s
    - `tests.test_session_context`: 19 tests, 15.184s
    - `tests.test_subagents`: 48 tests, 11.708s
  - The slowest modules are dominated by Git subprocess orchestration, filesystem operations, and CLI invocations rather than pure algorithmic computation.
  - Algorithmic bottlenecks in unit suites include `test_spec_contour_shapes.py::test_dense_wall_rows_keep_the_contour` (6.65s call phase) and `test_spec_floors.py::test_long_matching_chain_needs_no_recursion` (3.76s call phase), which function as long-chain regression tests.
- **Skipped Tests & Warnings**:
  - 2 skipped tests (`tests.test_kpp1_export_safety::test_output_root_alias_is_refused` and `tests.test_project_hygiene::test_duplicate_scan_does_not_follow_symlink`) skipped cleanly due to Windows unprivileged directory symlink restrictions (`WinError 1314`).
  - 1 warning in `tests/integration/test_pipeline.py::test_archive_traversal_and_duplicate_members_rejected`: standard `UserWarning: Duplicate name: 'same'` emitted by standard library `zipfile`, which is the intended behavior of the test verifying zip rejection.

### 2. Static Reachability and Import Gap Analysis

The static metric report `.health-metrics.json` flagged 10 modules under `no_direct_test_import`. Static import reachability surveys do not equate to dynamic statement or branch execution metrics; coverage.py uses `--source=src` and `--branch` to measure executed statements/branches dynamically and discover unexecuted files [2]. A manual and AST-level audit resolved all 10 candidates:

| Module | Physical Lines | Import / Reachability Path | Test Reachability Status |
|---|---|---|---|
| `dt_ai.geometry.from_source` | 1,519 | `tests/qa/test_from_source.py:10` (`from dt_ai.geometry import from_source as fs`) | **Directly imported**; 40 unit/QA tests (1.008s) exercise polygon slicing, snapping, and module building. |
| `dt_ai.geometry.grid_patches` | 19 | `src/dt_ai/geometry/exterior.py:13` (`from dt_ai.geometry.grid_patches import rectangles`) | **Transitive reachability**; exercised via `exterior.py` in `tests/test_exterior_adapter.py` and `tests/test_exterior_surface.py`. |
| `dt_ai.intake.model` | 127 | `src/dt_ai/core/models.py:191` and `src/dt_ai/intake/check.py:30` (`from dt_ai.intake.model import SourcesFile, SpecDraft` / `BLOCKS, REQUIRED...`) | **Transitive reachability**; data structures instantiated and validated throughout `tests/test_intake.py` (31 tests). |
| `dt_ai.spec.decor` | 473 | `tests/test_spec_decor.py:177` (`from dt_ai.spec import decor as dc`) | **Directly imported**; 52 tests in `test_spec_decor.py` and 93 tests in `tests/qa/test_from_spec_decor.py`. |
| `dt_ai.spec.markup` | 55 | `src/dt_ai/spec/mesh.py:23` (`from dt_ai.spec.markup import MarkupError, revit_level_helpers`) | **Transitive reachability**; level helper parsing path tested in `tests/test_spec_extract.py`. |
| `dt_ai.spec.openings` | 711 | `tests/test_spec_openings.py:135` (`from dt_ai.spec import openings as op`) | **Directly imported**; 46 tests in `test_spec_openings.py` and 26 tests in `test_spec_rough_openings.py`. |
| `twinqa.fbx_header` | 26 | `tools/qa/validate_package.py:20` (`from twinqa.fbx_header import check_fbx_header`), invoked by `tests/qa/test_validator.py:16` (`import validate_package as vp`) | **Transitive tool reachability**; `test_validator.py:24, 88-93` exercises binary FBX 7400 (`valid`) and FBX 7500 (`invalid`), though the module lacks a standalone test in `tests/`. (Tests do not verify ASCII headers). |
| `twinqa.geometry.checks` | 829 | `tests/qa/test_geometry_checks.py:18` (`from twinqa.geometry import checks`), plus `test_from_spec.py`, `test_from_source.py` | **Directly imported**; 63 dedicated tests in `test_geometry_checks.py` plus checks across QA suites. |
| `twinqa.geometry.measure` | 69 | `src/twinqa/geometry/checks.py:18` (`from twinqa.geometry import measure`) and `src/dt_ai/geometry/from_source.py:1206` (`from twinqa.geometry.measure import iou, silhouette`) | **Transitive reachability**; functions `iou` and `silhouette` exercised via geometry checks and source reconstruction tests. |
| `twinqa.report` | 96 | `src/twinqa/geojson.py:17`, `src/twinqa/png.py:16`, `src/twinqa/scene.py:16` (`from twinqa.report import Finding`) | **Transitive reachability**; finding and stage reporting structures verified across `tests/qa/test_validator.py` and `tests/qa/test_scene.py`. |

**Verdict**: All 10 flagged modules have **confirmed static reachability**. The static metric flag was an artifact of searching for top-level `from <full_module_path> import ...` while tests utilize package-level exports (`from dt_ai.geometry import from_source as fs`). However, a static import survey does not measure dynamic statement or branch execution metrics; zero proven wholly unreached modules under static analysis does not imply an absence of coverage gaps. True dynamic coverage measurement via `coverage run --branch --source=src` [2] has not yet been executed (coverage is not installed or declared in dev dependencies, making this a proposed future task), and indirect package imports do not provide an execution coverage guarantee.

### 3. AST Duplicate Groups and Scanner Limitations

The automated AST body metric identified 9 duplicate groups across tools, adapters, technical library, and source modules (specifically excluding `jobs/`). The scan identified functions with identical body AST statements where function names and signatures are ignored, but internal variable names must match exactly. Filtering required `len(body) > 1` and retained duplicate groups where the maximum member length was $\ge 5$ lines (permitting nested helper functions of 4 lines when grouped with $\ge 5$-line members):

1. **`unique_pairs`** (7 lines):
   - `src/dt_ai/core/io.py:21` and `src/twinqa/io.py:25`
   - Duplicate JSON key detection hook (`object_pairs_hook`).
2. **`clustered`** (8 lines):
   - `src/dt_ai/geometry/exterior.py:16` and `tools/build_exterior_surface.py:20`
   - 1D float coordinate grouping within a span tolerance.
3. **`rectangles`** (18 lines):
   - `src/dt_ai/geometry/grid_patches.py:2` and `tools/compact_floor_body.py:19`
   - Decomposing planar grid patches into rectangular bounds.
4. **`tile_quad`** (5 lines):
   - `src/dt_ai/geometry/uv.py:10` and `src/twinqa/uv.py:20`
   - UDIM quad coordinate calculation with padding offset.
5. **`augment`** (8 lines):
   - `src/dt_ai/spec/compare.py:59` and `tools/library/build_window_types.py:144`
   - Augmenting path helper for maximum bipartite matching within tolerance.
6. **Nested cycle/component helpers** (`find` / `root`, 4–5 lines):
   - `src/dt_ai/spec/decor.py:303` (`find`, 5 lines, nested in `_connected_components`)
   - `technical_library/uv_continuous/solve.py:40` (`find`, 5 lines, nested in `_components`)
   - `tools/build_shell_windows.py:14` (`root`, 4 lines, nested in `solve_cycles`)
   - Union-find root resolution helpers where function names differ but AST body structure matches.
7. **`inner_outlines_match`** (20 lines):
   - `src/dt_ai/spec/mesh.py:624` (`def _inner_outlines_match`) and `src/twinqa/geometry/checks.py:114` (`def inner_outlines_match`)
   - Polygon hole-to-plate outline inward buffering and Hausdorff distance matching.
8. **CLI entry point patterns** (`main`, 9 lines):
   - `tools/hooks/context_watch.py:115` and `tools/hooks/skill_gate.py:71`
   - Argument parsing and exit code handling in hook scripts.
9. **File hashing helpers** (`digest` / `sha`, 6 lines):
   - `tools/profile_snapshot_common.py:15` (`digest`) and `tools/run_profile_checks.py:55` (`sha`)
   - SHA256 chunked file digest calculation.

#### Scanner Limitations and Missed UV Primitives:
The AST scanner relies on body comparison heuristics that create blind spots:
1. **One-statement function exclusion**: Functions with only a single statement (`len(fn.body) == 1`) were filtered out by the metric script.
2. **Docstring AST mismatch**: In Python's AST, a docstring is represented as an initial `ast.Expr(value=ast.Constant(value=...))` statement. A function with a docstring and 7 body statements has `len(body) == 8`, whereas an otherwise identical function without a docstring has `len(body) == 7`, causing AST equality checks to fail.
3. **Signature and argument omission**: AST body comparisons compare only statements inside the function body, ignoring parameter defaults and signature annotations.

#### Scoping of UV Math Functions:
- `src/dt_ai/geometry/uv.py` contains 38 physical lines of code.
- Four candidate mathematical utility functions exist:
  - `tile_origin(tile)` (lines 4–7)
  - `tile_quad(tile, size, padding)` (lines 10–14)
  - `signed_area(uv)` (lines 17–18)
  - `edge_densities(vertices, uv, size)` (lines 30–38)
- Not all functions are mirrored across all files:
  - `tile_origin` and `tile_quad` are present in `src/twinqa/uv.py`.
  - `signed_area` is duplicated in `src/twinqa/uv.py:27`, and in specific job scripts: `jobs/KPP1/scripts/vpm_uv.py:146` and `jobs/MASHI-LP/scripts/mesh_patches.py:12` (missed by the AST script because `len(body) == 1`).
  - `edge_densities` is duplicated in `src/twinqa/uv.py:73` with an added docstring (missed by the AST script due to docstring statement count difference).
- Architectural precaution: Foundational math can be shared where appropriate, but forced import coupling between engine (`dt_ai`) and checker (`twinqa`) must be avoided to preserve checker independence. Job scripts should not be forcibly rewritten by default.

### 4. Geometry Implementations: Welds, Distance Metrics, and Independent Checker Risks

A detailed code comparison reveals distinct geometric semantics across modules and highlights an architectural verification risk.

#### A. Weld Semantics: Multi-Grid vs Single-Grid vs 1D Axis Snapping
1. **Multi-Grid 3D Union-Find Weld** (`src/dt_ai/spec/mesh.py:157-176`):
   - Implements `_weld(v)` using 8 half-shifted spatial grids (`product((0.0, 0.5), repeat=3)`) at cell size `WELD_M`.
   - Uses disjoint-set union across all 8 shifted representations, ensuring that vertices within `WELD_M / 2` along every axis will share a bin in at least one shifted grid.
   - Evaluates bounding extents per connected cluster: if a chained cluster exceeds `WELD_M`, it falls back to a single grid anchor to prevent runaway vertex drift.
2. **Single-Grid Rounding Weld** (`src/twinqa/geometry/mesh.py:63-69`):
   - Implements `weld(vertices, weld_m)` using coordinate quantization: `keys = np.round(vertices / weld_m).astype(np.int64)`.
   - Per its docstring (`"Vertex -> welded id; vertices on one weld_m grid cell are one vertex (across meshes)"`), this is explicitly designed as grid voxel hashing.
   - Executable reproduction of grid properties:
     ```python
     import numpy as np
     from twinqa.geometry.mesh import weld

     # 1. Boundary split: points separated by 0.0002 m straddling a rounding boundary
     v_split = np.array([[0.0049, 0.0, 0.0], [0.0051, 0.0, 0.0]])
     ids_split = weld(v_split, weld_m=0.01)
     dist_split = float(np.linalg.norm(v_split[1] - v_split[0]))
     # ids_split => array([0, 1]) (not welded, dist_split = 0.00020000000000000052 < 0.01 tol)

     # 2. Diagonal distance inflation: opposite corners of the same grid voxel
     v_diag = np.array([[-0.0049, -0.0049, -0.0049], [0.0049, 0.0049, 0.0049]])
     ids_diag = weld(v_diag, weld_m=0.01)
     dist_diag = float(np.linalg.norm(v_diag[1] - v_diag[0]))
     # ids_diag => array([0, 0]) (welded, dist_diag / 0.01 = 1.6974097914174997 > 1.0 tol)
     ```
   - Interpretation: These characteristics follow directly from grid cell partitioning semantics as documented in `twinqa`. They are not automatically an implementation defect. Replacing `weld` with multi-grid clustering without an agreed contract or user decision could alter established QA tolerances.
3. **Intentional Precision and Snapping Differences**:
   - `src/dt_ai/geometry/connect.py:29`: rounds grid point coordinates to 8 decimal places (`np.round(point, 8)`).
   - `src/dt_ai/geometry/shell.py:17`: rounds vertex coordinates to 9 decimal places (`np.round(v, 9)`).
   - `src/dt_ai/geometry/from_spec.py:149-182`: `_Weld` clusters coordinates along 1D plan axes while preserving fixed coordinate anchors.
   - These snapping and rounding strategies differ intentionally for their respective contexts (mesh welding vs parametric shell stitching vs architectural rectilinear axis alignment).

#### B. Distance Metric Differences
- **Point-to-Line vs Point-to-Segment**:
  - `src/dt_ai/spec/mesh.py:287-289` (`_line_distance`): Measures perpendicular distance from a point to an *infinite line* defined by `p1` and `p2` using the 2D cross product: `abs(d[0]*(c[1]-p1[1]) - d[1]*(c[0]-p1[0])) / norm(d)`. It does not clamp to the line segment.
  - `jobs/KPP1/scripts/qa_overlap.py:40-43` (`_seg_dist`): Measures distance from a point to a *finite segment*, projecting parameter $t$ and clamping to $[0.0, 1.0]$.
  - Call-site evaluation: Do not assert that any engine call-site uses the line metric inappropriately without reproducing a concrete failure.

#### C. Independent Checker Risk: `_inner_outlines_match`
- **Location**:
  - Generator: `src/dt_ai/spec/mesh.py:624-643` (`def _inner_outlines_match(hole, plate, overlap, weld):`)
  - Checker: `src/twinqa/geometry/checks.py:114-133` (`def inner_outlines_match(hole, plate, overlap, weld):`)
- **Risk Analysis**:
  - Both functions share identical AST function bodies (function names differ: `_inner_outlines_match` vs `inner_outlines_match`): buffering interior hole rings inward by `-overlap` with `mitre_limit=1e6`, validating `is_empty`, and checking bijective one-to-one correspondence using `hausdorff_distance(h) <= weld`.
  - In architectural QA, an independent checker (`twinqa`) must serve as an impartial verifier of the synthesis pipeline (`dt_ai`).
  - Identical function bodies between generator and checker introduce a **potential shared implementation risk**: if Shapely's negative buffering produces topological quirks on complex self-touching outlines, or if `hausdorff_distance` behaves unexpectedly, both the engine and the checker could correlate failure modes rather than having the discrepancy caught independently. This is an architectural potential shared-risk, not a proven false pass under existing test cases.
  - Addressing this requires developing independent negative fixtures and mutation tests before considering alternative implementations.

### 5. Documentation Staleness vs Code Reality

An audit of domain documentation against codebase reality confirmed three distinct documentation granularity gaps:

1. **`docs/domain/validation.md:5` vs Partial Validation Tooling**:
   - *Documentation statement*: `## Delivery validator spec (V001-V017) - local: standards/DELIVERY_VALIDATOR.yaml (spec only, not implemented)`
   - *Code reality*: The blanket "(spec only, not implemented)" tag is stale, but stages V001–V017 are NOT fully operational or completed customer delivery gates.
   - *Two Validator Entry Points*:
     - `tools/qa/validate_package.py`: delivery validator tool checking packages against `standards/DELIVERY_VALIDATOR.yaml` stages V001–V017. Lines 5–9 explicitly state that scene-dependent stages (units, triangles, UV islands, UCX, coordinates) are `not_run` unless `--scene` runs Blender readback (`tools/blender/fbx_readback.py`), and manual stages (V015–V017) always require signed review. Without `--scene`, an otherwise clean package retains `not_run`/`review` stages and cannot achieve a full pass (exiting 2 when only review/not_run remain, or 1 if any check fails); it never produces a silent full pass.
     - `src/dt_ai/validate/bundle.py` (invoked via `dt validate`): development bundle validator. Lines 174–188 execute limited synthetic checks (C001–C004) and explicitly mark all `DELIVERY_VALIDATOR.yaml` stages as `review` or `not_run` ("Full customer-delivery check not implemented or not supported by synthetic evidence"), recording explicit synthetic limitations (no GeoJSON, ground, UCX, etc.).
   - *Status Semantics*: `docs/pipeline.md:26` correctly marks Stage 15 as **partial**; per `docs/PROJECT_STATE.md:13`, no official customer delivery has passed yet. Thus `docs/domain/validation.md:5` is stale, whereas `docs/pipeline.md:26` is accurate.
2. **`docs/pipeline.md:17` (Stage 6) vs Existing Decor Tooling**:
   - *Documentation statement*: `Roof, decor, exterior equipment | missing | — | P4`
   - *Code reality*: Marking Stage 6 as entirely "missing" is too coarse relative to existing code. Roof extraction, parapet insets, and decorative profiles are actively handled in `src/dt_ai/spec/decor.py` (473 lines), `src/dt_ai/spec/mesh.py` (lines 1410–1460, 1858–1873), and `src/twinqa/geometry/checks.py` (`check_decor`), verified across unit suites (`tests/test_spec_roof.py`, `tests/test_spec_decor.py`, `tests/qa/test_from_spec_decor.py`).
   - *Status Semantics*: Per `docs/pipeline.md:5-6`, a stage is only **proven** once accepted on a real object. Existing decor tooling represents partial progress, not a completed production stage.
3. **`docs/pipeline.md:13` (Stage 2) vs Existing Spec Models**:
   - *Documentation statement*: `Master building layer (elements, floors, openings, materials, sources) | missing | concept in docs/agr/DIGITAL_TWIN_AI_PROJECT_BRIEF.md | P2`
   - *Code reality*: Marking Stage 2 as completely "missing" is too coarse. The building specification model is defined in `src/dt_ai/spec/model.py` (`Spec:165`, `Floor:63`, `Opening:32`, `Decor:125`, `Roof:87`; note: class `MaterialAssignment` does not exist; materials are tracked via `material_id` fields and registry), generated by `src/dt_ai/spec/mesh.py` (1,873 lines), and consumed by `src/dt_ai/geometry/from_spec.py` (960 lines).
   - *Status Semantics*: The specification pipeline is active and exercised across test suites, but has not achieved full real-object acceptance across all building topologies. Reporting this as a granularity gap aligns documentation with code without prematurely asserting completion.

---

## How It Applies to this Repository

1. **Test Suite Hygiene & Developer Feedback Loop**:
   - The CPU-only test suite requires ~2 minutes (122.93s pytest elapsed time) on local developer environments. While acceptable for pre-commit verification, it creates friction during rapid iteration.
   - Because 37.7% of runtime is concentrated in 3 test files performing Git/CLI process operations (`test_pipeline_gate`, `test_session_context`, `test_subagents`), measured profiling and evidence-based test partitioning can accelerate the inner unit test loop while preserving full Git regression coverage.
2. **Checker Independence**:
   - The primary objective of the AGR-DigitalTwin repository is delivering models conforming to strict regulatory criteria. Sharing identical polygon matching bodies between `dt_ai` and `twinqa` creates a potential shared implementation risk. A defect in `_inner_outlines_match` could correlate failure modes rather than being caught independently (an architectural risk, not a proven false pass in existing suites). Independent negative fixtures and mutation testing are required before considering alternative implementations.
3. **Code Duplication & Maintenance Overhead**:
   - 38 physical lines of UV utility functions in `src/dt_ai/geometry/uv.py` share math with `src/twinqa/uv.py` and specific job scripts (`tile_origin`, `tile_quad`, `signed_area`, `edge_densities`).
   - Common math primitives can be consolidated where beneficial, provided engine and checker remain architecturally decoupled, and job scripts are not forcibly modified without cause.
4. **Documentation Alignment**:
   - Distinguishing partial verification tooling from completed delivery gates prevents developer confusion while respecting the project standard that only real-object acceptance yields "proven" status.

---

## Proposed Next Tasks

### Summary of Proposed Tasks

| Task | Description | Value | Effort | Priority |
|---|---|---|---|---|
| **Task 1: Coverage Baseline & Adversarial QA Fixtures** | Propose `coverage run --branch --source=src -m pytest -q -m 'not blender and not dcc'` to measure true branch coverage; author negative fixtures & mutation tests for `inner_outlines_match`. Cross-reference checker blind spots (#126). | **L** | **M** | 1 (Safe, high value) |
| **Task 2: Documentation Freshness & Status Granularity** | Update `docs/domain/validation.md:5` to replace stale "not implemented" with partial tooling description; refine `docs/pipeline.md` Stage 2 & 6 granularity without overclaiming production readiness. | **M** | **S** | 2 (Low risk, clear truth) |
| **Task 3: Geometry Tolerance & Weld Characterization** | Document weld and tolerance contracts (multi-grid vs single-grid vs axis snapping); verify boundary behavior without replacing kernels absent user decision. | **M** | **M** | 3 (Contract clarification) |
| **Task 4: Measured Test Profiling & Evidence-Based Partitioning** | Profile slow testcases (`test_dense_wall_rows_keep_the_contour`, `test_long_matching_chain_needs_no_recursion`); evaluate `unit` test marker while preserving full Git regression tests. | **M** | **M** | 4 (Performance hygiene) |
| **Task 5: Utility De-duplication with Checker Independence Caveat** | Consolidate common math primitives (`unique_pairs`, `clustered`, UV helpers) where safe, maintaining architectural separation between engine and checker. | **S** | **S** | 5 (Code cleanliness) |

*(Scale: Value: L = High, M = Medium, S = Low; Effort: S = Small, M = Medium, L = Large)*

---

### Task 1: Coverage Baseline & Adversarial Negative QA Fixtures
- **Scope**: Propose establishing a true dynamic test execution coverage baseline using `coverage run --branch --source=src -m pytest -q -m 'not blender and not dcc'` [2] to measure statement and branch coverage across all 45 non-init modules, identifying unexecuted functions and branches (as coverage is not currently installed or declared in dev dependencies, this command is a proposed scoped task, not an executed run). For `inner_outlines_match`, author independent negative test fixtures and mutation tests to probe boundary edge cases (self-touching rings, complex decorative outlines) before altering implementation. Cross-reference existing checker blind spots (#117 / #126) from `docs/PROJECT_STATE.md:36` as recognized context (no new issues).
- **Value / Effort**: **Value: L (High) / Effort: M (Medium)**. Delivers verified test coverage data and hardens the verification gate against correlated false passes.

### Task 2: Documentation Freshness & Status Granularity Alignment
- **Scope**: Update `docs/domain/validation.md:5` to clarify that stages V001–V017 are partially implemented via `tools/qa/validate_package.py` and `src/dt_ai/validate/bundle.py`, retaining explicit notice of required DCC scene readback and manual review gates. In `docs/pipeline.md`, refine Stage 2 and Stage 6 status/link granularity to reference active spec models (`Spec:165`, `Floor:63`, `Opening:32`, `Decor:125`, `Roof:87`) and decor code without claiming unverified completion.
- **Value / Effort**: **Value: M (Medium) / Effort: S (Small)**. Eliminates stale documentation claims while strictly adhering to `docs/pipeline.md:5-6` status semantics.

### Task 3: Geometry Tolerance & Weld Characterization
- **Scope**: Document explicit geometric contracts across modules. Characterize single-grid voxel clustering in `twinqa.geometry.mesh.weld` as documented grid hashing semantics, contrasting it with multi-grid union-find (`dt_ai.spec.mesh._weld`), 1D axis snapping (`from_spec.py`), and coordinate rounding precision (8dp in `connect.py:29`, 9dp in `shell.py:17`). Do not replace or modify welding kernels absent an agreed specification or user decision.
- **Value / Effort**: **Value: M (Medium) / Effort: M (Medium)**. Prevents topological discrepancies between extractor and checker without adding unverified dependencies.

### Task 4: Measured Test-Loop Profiling & Evidence-Based Partitioning
- **Scope**: Systematically profile top time consumers, specifically algorithmic tests (`test_dense_wall_rows_keep_the_contour` at 6.65s, `test_long_matching_chain_needs_no_recursion` at 3.76s) and Git subprocess suites (`test_pipeline_gate`, `test_session_context`, `test_subagents`). Evaluate an optional `pytest -m unit` partitioning based on measured execution profiles, while preserving the full Git integration suite for pre-commit verification.
- **Value / Effort**: **Value: M (Medium) / Effort: M (Medium)**. Improves inner-loop developer velocity while preserving end-to-end regression safety.

### Task 5: Utility De-duplication with Checker-Independence Caveat
- **Scope**: Evaluate safe consolidation of non-critical mathematical helpers (`unique_pairs`, `clustered`, UV math) across tools and core modules. Maintain strict architectural decoupling between synthesis (`dt_ai`) and verification (`twinqa`) to preserve checker independence, and avoid mandatory rewrites of standalone job scripts.
- **Value / Effort**: **Value: S (Low) / Effort: S (Small)**. Modest code hygiene improvement without impacting runtime safety.

---

## Open Questions

1. **Checker Independence vs Shared Geometry Kernels**: Should `twinqa` share foundational geometric algorithms with `dt_ai`, or should it maintain deliberately divergent verification implementations to prevent correlated blind spots?
2. **Subprocess Test Execution in CI/Local Environments**: How should Git integration suites in `test_pipeline_gate` and `test_session_context` be optimized for local developer iteration while maintaining full end-to-end regression fidelity?
3. **Standalone Testing for Tool Utilities**: Should `twinqa.fbx_header` be provided with direct unit tests under `tests/qa/` rather than relying exclusively on indirect execution through `tools/qa/validate_package.py`?

---

## Reproducible Commands & Measurement Methodology

### 1. Test Suite Execution Command
To reproduce the measured baseline run without DCC/Blender dependencies:
```bash
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q \
  --durations=25 \
  -m 'not blender and not dcc' \
  --basetemp=docs/research/.health-tmp2 \
  --junitxml=docs/research/.health-pytest2.xml
```
*Note*: Local `.health-*` files are ephemeral outputs generated by this command; they are not tracked repository assets.

### 2. Python Metric Aggregation Recipe
The following recipe aggregates module durations and testcase counts directly from JUnit XML:
```python
import xml.etree.ElementTree as ET
from collections import defaultdict

def summarize_junit(xml_path: str):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")

    modules = defaultdict(lambda: {"tests": 0, "seconds": 0.0, "skipped": 0})
    for tc in root.iter("testcase"):
        # Use full classname: in this suite, pytest sets classname to the test module path
        # (e.g., 'tests.test_pipeline_gate'). Do NOT rsplit('.', 1)[0] as that would collapse
        # all test modules into the top-level 'tests' package.
        mod = tc.attrib["classname"]
        time_sec = float(tc.attrib.get("time", 0.0))
        modules[mod]["tests"] += 1
        modules[mod]["seconds"] += time_sec
        if tc.find("skipped") is not None:
            modules[mod]["skipped"] += 1

    sorted_mods = sorted(modules.items(), key=lambda kv: kv[1]["seconds"], reverse=True)
    return {
        "suite_xml_sec": float(suite.attrib.get("time", 0.0)),
        "testcase_sum_sec": sum(m["seconds"] for _, m in sorted_mods),
        "total_tests": sum(m["tests"] for _, m in sorted_mods),
        "total_skipped": sum(m["skipped"] for _, m in sorted_mods),
        "modules": sorted_mods,
    }
```
*Note*: Assumes module-level test functions as structured across the repository.

---

## Appendix: Complete Duration Breakdown (All 61 Test Modules)

Measured from `docs/research/.health-pytest2.xml` and recorded in `docs/research/.health-metrics.json`:

| # | Test Module | Tests | Duration (s) | Skipped | % of Tests Duration |
|---|---|---|---|---|---|
| 1 | `tests.test_pipeline_gate` | 79 | 18.495 | 0 | 15.34% |
| 2 | `tests.test_session_context` | 19 | 15.184 | 0 | 12.60% |
| 3 | `tests.test_subagents` | 48 | 11.708 | 0 | 9.71% |
| 4 | `tests.test_spec_contour_shapes` | 68 | 9.434 | 0 | 7.83% |
| 5 | `tests.integration.test_pipeline` | 17 | 9.277 | 0 | 7.70% |
| 6 | `tests.test_save_transcript` | 12 | 7.549 | 0 | 6.26% |
| 7 | `tests.test_kpp1_export_safety` | 28 | 7.071 | 1 | 5.87% |
| 8 | `tests.qa.test_from_spec` | 110 | 5.909 | 0 | 4.90% |
| 9 | `tests.test_usage_hooks` | 34 | 4.597 | 0 | 3.81% |
| 10 | `tests.test_spec_floors` | 19 | 4.357 | 0 | 3.61% |
| 11 | `tests.test_branch_names` | 18 | 3.463 | 0 | 2.87% |
| 12 | `tests.contracts.test_adapter_report_reader` | 6 | 3.188 | 0 | 2.64% |
| 13 | `tests.qa.test_geometry_checks` | 63 | 2.810 | 0 | 2.33% |
| 14 | `tests.test_run_record` | 13 | 2.549 | 0 | 2.11% |
| 15 | `tests.qa.test_from_spec_decor` | 93 | 2.503 | 0 | 2.08% |
| 16 | `tests.test_spec_openings` | 46 | 2.024 | 0 | 1.68% |
| 17 | `tests.test_spec_extract` | 64 | 1.708 | 0 | 1.42% |
| 18 | `tests.test_context_watch` | 18 | 1.138 | 0 | 0.94% |
| 19 | `tests.test_spec_decor` | 52 | 1.086 | 0 | 0.90% |
| 20 | `tests.qa.test_from_source` | 40 | 1.008 | 0 | 0.84% |
| 21 | `tests.test_spec_rough_openings` | 26 | 1.004 | 0 | 0.83% |
| 22 | `tests.test_spec_doors` | 33 | 0.895 | 0 | 0.74% |
| 23 | `tests.test_spec_roof` | 33 | 0.461 | 0 | 0.38% |
| 24 | `tests.test_run_inspection` | 26 | 0.382 | 0 | 0.32% |
| 25 | `tests.test_spec_revit_twin` | 19 | 0.372 | 0 | 0.31% |
| 26 | `tests.qa.test_uv` | 8 | 0.293 | 0 | 0.24% |
| 27 | `tests.test_spec_compare` | 18 | 0.278 | 0 | 0.23% |
| 28 | `tests.integration.test_pdf_index` | 1 | 0.261 | 0 | 0.22% |
| 29 | `tests.qa.test_standards` | 6 | 0.218 | 0 | 0.18% |
| 30 | `tests.test_intake` | 31 | 0.188 | 0 | 0.16% |
| 31 | `tests.qa.test_validator` | 24 | 0.183 | 0 | 0.15% |
| 32 | `tests.contracts.test_contracts` | 14 | 0.148 | 0 | 0.12% |
| 33 | `tests.test_spec_questions_file` | 13 | 0.107 | 0 | 0.09% |
| 34 | `tests.test_decisions` | 4 | 0.105 | 0 | 0.09% |
| 35 | `tests.test_profile_regressions` | 27 | 0.084 | 0 | 0.07% |
| 36 | `tests.test_body_contours` | 4 | 0.054 | 0 | 0.04% |
| 37 | `tests.test_connect_adapter` | 15 | 0.053 | 0 | 0.04% |
| 38 | `tests.test_psu275_assembly_safety` | 10 | 0.046 | 0 | 0.04% |
| 39 | `tests.test_body_optimization` | 3 | 0.044 | 0 | 0.04% |
| 40 | `tests.test_exterior_surface` | 2 | 0.035 | 0 | 0.03% |
| 41 | `tests.test_project_state` | 4 | 0.035 | 0 | 0.03% |
| 42 | `tests.test_agr_index` | 1 | 0.034 | 0 | 0.03% |
| 43 | `tests.test_glb_atlas` | 4 | 0.026 | 0 | 0.02% |
| 44 | `tests.test_facades_texture_pattern` | 14 | 0.018 | 0 | 0.01% |
| 45 | `tests.test_profile_snapshot_fixture` | 6 | 0.018 | 0 | 0.01% |
| 46 | `tests.test_project_hygiene` | 5 | 0.017 | 1 | 0.01% |
| 47 | `tests.contracts.test_window_atlas_config` | 15 | 0.015 | 0 | 0.01% |
| 48 | `tests.test_shared_uv` | 12 | 0.013 | 0 | 0.01% |
| 49 | `tests.test_window_types` | 19 | 0.012 | 0 | 0.01% |
| 50 | `tests.test_floor_uv` | 3 | 0.011 | 0 | 0.01% |
| 51 | `tests.test_exterior_adapter` | 11 | 0.010 | 0 | 0.01% |
| 52 | `tests.test_shell_windows` | 2 | 0.010 | 0 | 0.01% |
| 53 | `tests.test_skills_sync` | 2 | 0.010 | 0 | 0.01% |
| 54 | `tests.contracts.test_uv_stage_workspace` | 4 | 0.008 | 0 | 0.01% |
| 55 | `tests.qa.test_clearance` | 9 | 0.008 | 0 | 0.01% |
| 56 | `tests.test_floor_texture` | 6 | 0.008 | 0 | 0.01% |
| 57 | `tests.test_shared_library` | 9 | 0.007 | 0 | 0.01% |
| 58 | `tests.test_shell_adapter` | 13 | 0.006 | 0 | <0.01% |
| 59 | `tests.contracts.test_material_id_ranges` | 1 | 0.003 | 0 | <0.01% |
| 60 | `tests.contracts.test_adapter_report` | 5 | 0.002 | 0 | <0.01% |
| 61 | `tests.qa.test_scene` | 21 | 0.001 | 0 | <0.01% |
| **Total** | **All Modules** | **1,330** | **120.541 s** | **2** | **100.00%** |

- **Pytest-Reported Elapsed Time**: 122.93 s
- **Sum of Module Runtimes**: 120.541 s
- **Pytest Testsuite XML Duration**: 122.906 s
- **Unallocated Testsuite Overhead**: 2.365 s (122.906 s suite XML - 120.541 s testcase sum; covers test collection, framework reporting, and XML serialization within pytest; 2.389 s relative to pytest-reported elapsed 122.93 s)

---

## Sources

[1] https://docs.pytest.org/en/stable/how-to/usage.html
[2] https://coverage.readthedocs.io/en/latest/source.html
