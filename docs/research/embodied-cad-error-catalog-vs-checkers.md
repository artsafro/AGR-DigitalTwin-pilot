# Embodied CAD error catalog vs our checkers — which checks are we missing

Date: 2026-10-21. Card: `docs/research-embodied-cad-vs-checkers` (#441). Author: dt-worker-deepseek.

Scope: compare the catalogue of "token-invisible" CAD errors from the Embodied CAD paper with the project's
checkers and list the gaps as checker candidates. Implementation is out of scope (follow-up issues after the
user picks).

Sources read:
- Paper: **Embodied CAD: Solver-Grounded LLM Agents for Parametric B-Rep Assembly Modeling**, arXiv:2606.31252v1
  (`https://arxiv.org/html/2606.31252v1`, HTML snapshot fetched 2026-10-21).
- Our checkers: `src/twinqa/` (delivery validators), `src/twinqa/geometry/checks.py` (spec-vs-model harness checks),
  `src/dt_ai/` (operation kernel + spec), `docs/domain/geometry.md`, `docs/agr/sintez_checks_1.6.1.json`.
- Job evidence: `docs/research/job-retro-vyatskaya-tow02-pr392.md`, `docs/backlog.md` (EG5, P13, R11–R14).

---

## 1. The paper's error catalogue

The paper has **no numbered "error table"**. Its error catalogue is a small taxonomy of failure *classes* plus
concrete examples scattered over four sections. The canonical taxonomy is §6.4 "Failure Modes" (four recurring
categories); §1 and §6.3 add concrete examples, §3 adds the state-dependence umbrella. We enumerate every
distinct class below with its section reference; the ten rows E1–E10 are the mapping units used in §3.

| # | Error class | Section | What the paper says |
|---|---|---|---|
| E1 | Wrong coordinate frame | §1 (cutter in wrong frame); §6.4 "Coordinate-frame errors" | "placing a cutter in the wrong coordinate frame"; "local and global frames are mixed, especially for mirrored or rotated features" |
| E2 | Stale local face selection | §1 | "selecting a stale local face" (a face that was renumbered/removed by an earlier op) |
| E3 | Incorrect offset on repeated features | §1 ("duplicating repeated holes with an incorrect offset"); §6.4 "Index ambiguity" | repeated instances/holes placed at the wrong spacing because the instance index is not grounded to the construction state |
| E4 | Stacking components at origin | §1 | "stacking components at the origin" — distinct parts coincident |
| E5 | Inconsistent state-dependent argument | §3 (Problem Formulation) | "a hole center, chamfer target, mirrored instance, or repeated fastener index must be selected consistently with previous operations" — the umbrella for E3/E6/E7/E8 |
| E6 | Wrong height feature placement | §6.3 | "a guide post can be created at the wrong height" |
| E7 | Wrong target removal | §6.3 | "a cutter can remove the wrong plate" |
| E8 | Wrong mirror origin | §6.3 | "an array can be mirrored around the wrong origin" |
| E9 | Family confusion | §6.4 | "the model selects a plausible but wrong next operation, such as a chamfer before all cuts have been applied" |
| E10 | Reward sparsity | §6.4 | "many sampled candidates are parseable and executable but have identical group rewards" — a training/eval signal issue, not a geometry defect |

Out of scope per the paper (§7): free-form surfacing, organic shapes, tolerance-stack analysis, downstream
manufacturing simulation — none of these is a "checker gap" for us.

Key observation: **every class E1–E9 is a *planning* error whose outcome is "wrong geometry vs intent"**, not a
malformed B-Rep. Our delivery validators mostly check *conformance* (well-formedness, naming, transforms reset,
polycount, topology, UV, materials, UCX), and a smaller layer (`src/twinqa/geometry/checks.py`) checks
*intent-conformance* against an etalon/spec. That distinction drives the mapping below.

---

## 2. Our checker inventory (the mapping targets)

Two layers, plus the kernel:

- **Delivery validators** (`src/twinqa/`, run on the produced FBX/GLB/GeoJSON/PNG package):
  `fbx_header.py`, `naming.py`, `scene.py` (transforms/pivot/scale/polycount/UCX pairs), `geometry/topology.py`
  (duplicates/self-intersections/isolated/zero-length), `geometry/winding.py` (same-direction manifold edges),
  `geometry/component_volume.py` (closed-manifold + signed volume), `geometry/ucx_audit.py`,
  `geometry/maf_surface.py`, `clearance.py` (near-parallel overlap 5 mm–2 cm + co-directional pairs), `uv.py`,
  `png.py`, `geojson.py`, `flora.py`, `maf_checks.py`, `profiles.py`/`bundle.py`/`report.py`.
- **Spec-vs-model harness checks** (`src/twinqa/geometry/checks.py`, benchmark §5): `check_bbox`, `check_levels`,
  `check_floor_areas`, `check_silhouettes`, `check_mesh` (weld/T-junction/non-manifold), `check_budget`,
  `check_material_ids`, `check_opening_planes`, `check_decor`, `check_orientation`.
- **Operation kernel + spec** (`src/dt_ai/`): `ops/operations.py` (`run_operation` pre/post invariant check),
  `ops/invariants.py`, `geometry/surface_identity.py` (two-way surface coverage), `spec/compare.py` (spec-vs-spec),
  `spec/mesh.py`, `spec/openings.py`, `placement/engine.py`.
- **Evals** (`src/twinqa/evals/`): `graders.py`, `receipt.py`, `runner.py`, `capability.py`.

---

## 3. Mapping: error class → our check(s) → status

Status legend: **mapped** = an existing checker catches the class; **PARTIAL** = an existing checker catches a
gross/consequent form but not the class itself; **MISSING** = no checker; **N/A** = not a delivery-geometry defect.

Two per-feature checks are the key inputs and are mapped explicitly (review round 1 corrected an earlier omission):

- **`check_opening_planes`** (`src/twinqa/geometry/checks.py:522–555`) verifies **every** spec opening (window/door)
  against its wall, horizontal offset, height, outward facing, profile seat and **specified material id** —
  all per-feature, not whole-model.
- **`check_decor`** (`src/twinqa/geometry/checks.py:633–748`) matches facade decor **one-to-one** against the spec:
  kind, wall line, absolute height, extent, projection (`_matches`, `:615–630`) and exact material ids
  (`ids == [e.material_id]`, `:678`); extra decor ("the spec does not list") and missing decor ("not built") both fail.

| # | Error class | Our check (module → test) | Status | One-line why |
|---|---|---|---|---|
| E1 | Wrong coordinate frame | `scene.py` transforms/pivot/scale (`tests/qa/test_scene.py`); `check_opening_planes` facing/seat/wall/offset (`tests/qa/test_geometry_checks.py::test_window_on_another_wall_fails`); `check_decor` `_matches` (`tests/qa/test_from_spec_decor.py`) | PARTIAL | per-feature placement vs the spec is checked for openings and facade decor; a component that is *neither* (pier, ring, cutter, fastener) in a wrong local frame is caught only if it moves bbox/silhouette or fails orientation |
| E2 | Stale local face selection | `check_opening_planes` exact `material_id` (`:549`); `check_decor` one-to-one ids (`:678`, `tests/qa/test_from_spec_decor.py::test_wrong_ids_fail`); `surface_identity.py` (`tests/test_surface_identity.py`) | PARTIAL | opening/decor attribute identity is checked one-to-one vs the spec; per-face source-attribute identity on arbitrary body faces (which Revit id/type/material a face carries) is not |
| E3 | Incorrect offset on repeated features | `check_opening_planes` per-opening s/z vs spec; `check_decor` per-element x/w; `check_levels`/`check_floor_areas`/`check_silhouettes` (`tests/qa/test_geometry_checks.py`) | PARTIAL | window/door/decor grid pitch and offset are checked per-feature; repeated features that are *not* openings/decor (hole grid, rib pitch, ring step) have no dedicated check |
| E4 | Stacking components at origin | `topology.py` (`tests/qa/test_topology.py`); `clearance.py` (`tests/qa/test_clearance.py`) | PARTIAL | exact coincident faces and near-parallel overlap are caught *within* a mesh, but two distinct parts coincident at the origin across meshes is not flagged as a cross-object coincidence |
| E5 | Inconsistent state-dependent argument | `check_opening_planes` + `check_decor` (its concrete per-feature forms for openings/decor); umbrella over E3/E6/E7/E8 | PARTIAL | for openings and decor the state-dependent placement/identity is checked per-feature vs the spec; for arbitrary features and cross-op order (chamfer-before-cuts) it is not |
| E6 | Wrong height feature placement | `check_opening_planes` (z0+h_m per opening); `check_decor` `_matches` absolute height (`:620–621`); `check_levels` (`tests/qa/test_geometry_checks.py`); `check_bbox` | PARTIAL | opening and decor heights are checked per-feature; a feature at the wrong height that is neither opening nor decor (guide post, ring) is not |
| E7 | Wrong target removal | `check_decor` one-to-one (`test_missing_decor_fails`, `test_decor_the_spec_does_not_list_fails`); `check_opening_planes` (missing plane → cover 0); `check_silhouettes`/`check_floor_areas` | PARTIAL | removing the wrong opening/decor element is caught one-to-one; removing the wrong plate among arbitrary body faces while totals look similar is not distinguished |
| E8 | Wrong mirror origin | `winding.py` + `check_orientation` (`tests/qa/test_orientation.py`); `component_volume.py` (`tests/qa/test_component_volume.py`); `check_opening_planes` facing; `check_decor` wall-line match | PARTIAL | an inside-out (mirrored) component is caught via winding/signed volume; a mirror around the wrong origin that stays outward-oriented is caught if it is an opening/decor (position/wall mismatch), not for arbitrary features |
| E9 | Family confusion | `ops/operations.py` `run_operation`/`check_operation` (`tests/ops/test_operations.py`) | MISSING | the kernel checks pre/post *invariants* of a single op, but no checker validates the *order* of operations against an expected plan (delivery FBX carries no feature history) |
| E10 | Reward sparsity | `evals/graders.py`, `evals/receipt.py` (`tests/test_evals*.py`) | N/A | a training/eval-signal issue, not a delivery-geometry defect; our analogue is the "unmeasured check is an open gate, never a pass" rule in `checks.py` |

### Counts

- mapped (fully covered): **0**
- PARTIAL: **8** (E1, E2, E3, E4, E5, E6, E7, E8)
- MISSING: **1** (E9)
- N/A: **1** (E10)

The headline: the paper's errors are intent-conformance failures. Our conformance checkers are strong
(topology, clearance, orientation, transforms), and the intent-conformance layer covers **both** whole-model
quantities (bbox, levels, floor areas, silhouettes) **and per-feature openings + facade decor**: each window/door's
wall, height, offset, outward facing, seat and material id, and each decor element's one-to-one geometry and exact
ids. The residual gap is **per-feature identity/placement for features that are neither openings nor decor**
(holes, cutters, plates, fasteners, guide posts, rings) and **per-face source-attribute provenance on arbitrary
body faces** — exactly where the paper's non-opening classes live.

### Evidence: the per-feature checks reproduce

Generated probes on the synthetic B01 box (`tests/qa/test_geometry_checks.py::box_dump`, two windows on wall 0,
both mutated while whole-model bbox/levels stay unchanged). Reviewer independently ran the same probes 4/4 and the
two focused suites (390 passed / 2 deselected for geometry+orientation+volume+topology+clearance; 94 passed for decor).

| Input (openings) | Expected verdict | Probe / test |
|---|---|---|
| control: 2 windows on wall 0 (default `WINDOWS`) | `opening_planes` pass, cover 1.0 | `uv run python` probe → pass |
| both windows shifted **+0.15 m in Z** | `opening_planes` fail, cover 0.0 | `uv run python` probe → fail |
| both windows shifted **+0.25 m along-wall** | `opening_planes` fail, cover 0.0 | `uv run python` probe → fail |
| first window moved to **wall 1** | `opening_planes` fail; it is the **only** failed check | `tests/qa/test_geometry_checks.py::test_window_on_another_wall_fails` |

| Input (decor) | Expected verdict | Test |
|---|---|---|
| decor built to spec (belt/pilaster/column/band) | pass | `tests/qa/test_from_spec_decor.py::test_built_decor_passes` |
| spec lists decor, none built | fail "not built" | `::test_missing_decor_fails` |
| built decor with wrong material id (3, not 26) | fail "ids [3]" | `::test_wrong_ids_fail` |
| decor built that the spec does not list | fail "the spec does not list" | `::test_decor_the_spec_does_not_list_fails` |

---

## 4. Ranked checker candidates (≤ 8)

Ranked by expected catch rate against the paper's classes, then by reuse of existing primitives.
Size S / M / L is relative to the existing checker modules (`clearance.py` ≈ S, `checks.py` ≈ M, `placement/engine.py` ≈ L).

### C1 — Per-component frame-vs-source check for non-opening/non-decor features (E1, E6, E8) — size M
- **Detects**: each instanced/repeated component that is *not* an opening or facade decor (floor ring, pier, rib,
  hole grid, guide post, fastener) placed, rotated, scaled or mirrored differently from its source placement.
  Openings and facade decor are already covered by `check_opening_planes` / `check_decor`; this candidate extends
  the same idea to the remaining component classes.
- **Job evidence**: backlog **EG5** (OBJ03 v009: 1 328 piers → 798 types because the type key had no rotation —
  "instances by translation only"); the analogous window-flip class is now caught by `check_opening_planes` facing
  (`docs/domain/geometry.md` line 105), so the residual is the pier/ring counterpart. PR #392 dumper negative-scale
  (backlog P13) overlaps C5.
- **SINTEZ overlap**: `lp_transforms` (2.3.14), `hp_meshes_transforms` (2.3.18/2.9.3) — both are "transforms applied"
  (reset), not per-component-vs-source; this candidate extends them with a source reference.

### C2 — Repeated-feature pitch/offset vs source for non-opening/non-decor features (E3, E5) — size M
- **Detects**: spacing/offset of a repeated feature array that is *not* openings/decor (hole grid, rib pitch, ring
  step) vs the source/spec, so an "incorrect offset on repeated holes" or an ungrounded instance index fails.
  Window/door/decor grids are already checked per-feature by `check_opening_planes` / `check_decor`.
- **Job evidence**: EG5 pier type key is the closest real repeated-feature case; vyatskaya-tow02 PR #392's 889
  ribbon openings are openings — now covered by `check_opening_planes` *once the extractor sizes them* (the
  unsized-extractor issue is a source gap, not a checker gap). No dedicated retro yet for a hole/rib pitch defect;
  the class is the paper's own §1 example, listed as a candidate rather than a confirmed catch.
- **SINTEZ overlap**: none (SINTEZ has no spec comparison); adjacent groups `lp_fbx_objects`/`hp_fbx_objects`
  (object composition) only.

### C3 — Cross-object coincidence / origin-stacking (E4) — size S/M
- **Detects**: two *distinct* logical parts whose bbox/vertices fully coincide (stacked at origin) and
  near-coincident coplanar overlaps below the 5 mm band *across* mesh boundaries (current `topology.py` is
  per-mesh; `clearance.py` needs classifying, not a verdict).
- **Job evidence**: OBR22-K02 raw Revit import "440 duplicate faces" (`docs/domain/geometry.md` line 90); the
  "stacking at origin" class is the direct paper example.
- **SINTEZ overlap**: `lp_duplicates` (2.3.7), `hp_duplicates` (2.3.11), `hp_collision` (2.13.x nested/intersect).

### C4 — Per-face source-attribute identity on arbitrary body faces (E2, E7) — size M
- **Detects**: a face carries the wrong source attribute (stale face) or the wrong plate was removed among
  arbitrary body geometry, by comparing per-face Revit id/type/material provenance against the source — not just
  whole-mesh coverage. Opening and decor attribute identity are already one-to-one (`check_opening_planes`
  material_id, `check_decor` exact ids); the residual is arbitrary body faces and non-decor parts.
- **Job evidence**: ad-hoc **R12** (BVH nearest-distance checker) already does a per-part version in the retro;
  `surface_identity.py` (issue #305) is the reusable primitive to extend from whole-mesh coverage to per-face.
- **SINTEZ overlap**: `hp_materials` (2.4.x), `lp_materials` (2.1.5 etc.), `lp_color_attributes` (4.1.1, MISSING in us).

### C5 — Per-component orientation / inside-out delivery finding (E8) — size S
- **Detects**: a component whose signed volume is negative or whose manifold edges wind the same way, surfaced as
  a *delivery* finding (today `component_volume.py`/`winding.py` are diagnostic or harness-only; openings are
  already covered via `check_opening_planes` facing).
- **Job evidence**: PR #392 dumper mirror-matrix writes meshes inward (P13); `maf_surface.py` already reports
  flipped faces for MAF (issue #185) — same idea for OKS components.
- **SINTEZ overlap**: `hp_uv` (flipped UV 2.5.2.1.4b), `hp_collision` (unclosed/nonmanifold 2.13.4).

### C6 — Moscow elevation range, profile-aware (E1) — size S
- **Detects** a coordinate-frame/origin error that lands the model at the wrong site height. It must be
  **profile-aware** because NPM and VPM carry elevation in different places:
  - **NPM**: model geometry is in MSK coords + project heights (`docs/domain/geometry.md:31`), so the model Z is
    the elevation → check model Z within 110–250 m (SINTEZ `lp_height`, req 4.1.4, "model Z within Moscow elevation
    range").
  - **VPM**: the FBX is at local/project zero (`docs/domain/geometry.md:32–33`: origin 0,0,0, Z = project zero) and
    the real elevation lives in the GeoJSON `h_relief` → check `h_relief` within 110–250 m (SINTEZ `hp_height`,
    req 4.1.4, "h_relief within 110-250 m"). Applying the NPM model-Z rule to VPM would reject every correct VPM.
- **Job evidence**: the Ground FBX that came in 100× too large / wrong units (`docs/domain/geometry.md:35`) is a
  *units-on-import* error, **not necessarily caught by an elevation-only check** (a 100× scale can leave Z
  accidentally in range, or an out-of-band Z can come from a scaling an elevation check is blind to) — this job
  connection is **unproven** for C6 and must not be claimed.
- **SINTEZ overlap**: `lp_height` (4.1.4) for the NPM model-Z branch, `hp_height` (4.1.4) for the VPM GeoJSON
  branch — two distinct measures, both direct and both currently **MISSING** in `sintez_checks_1.6.1.json`.

Candidate specification (not yet implemented; expected verdicts):

| Input | Expected verdict |
|---|---|
| NPM control: model Z ≈ 150 m (in 110–250 m) | accept (NPM model-Z branch) |
| NPM: model Z ≈ 50 m | reject (NPM model-Z branch) |
| VPM: local/project-zero FBX, GeoJSON `h_relief=150` | accept (VPM `h_relief` branch — must NOT reject on local model Z) |
| VPM: same local mesh, GeoJSON `h_relief=300` | reject (VPM `h_relief` branch) |

### C7 — Operation-order / provenance invariant (E9) — size L
- **Detects**: "family confusion" — a plausible but wrong *next* operation relative to an expected plan. Our
  kernel already checks pre/post invariants per op (`ops/operations.py`); the candidate adds an expected
  operation-sequence validator over `run_record.py`/`provenance.py` against a spec-derived plan.
- **Job evidence**: the Shell/opening ordering rules (`docs/domain/geometry.md` line 73 "Shell inward … then
  windows") are enforced by hand today; no checker verifies them.
- **SINTEZ overlap**: none (no feature-history concept in SINTEZ).

### Not a checker candidate
- **E10 reward sparsity** → `src/twinqa/evals/` discriminability improvement, not a delivery checker. Out of
  scope here; noted for the evals lane.

---

## 5. Out of scope

- Implementing any candidate (C1–C7) — follow-up issues after the user picks.
- E10 reward sparsity (evals-lane work, not a checker).
- Free-form surfacing / organic shapes / tolerance-stack / manufacturing simulation (paper §7, not our scope).

---

## Agent trace

- Read `AGENTS.md`, `docs/PROJECT_STATE.md`, `docs/domain/geometry.md`, `docs/agr/sintez_checks_1.6.1.json`.
- Fetched the paper (`arxiv.org/html/2606.31252v1`) and extracted the error catalogue (§1, §3, §6.3, §6.4).
- Inventoried `src/twinqa/`, `src/dt_ai/`, `tests/` and mapped each error class to a module + test.
- Round 1 (2590f0d) mapped 0 / PARTIAL 6 / MISSING 3 / N/A 1; review round 1 (P1=2) corrected the omission of the
  per-feature `check_opening_planes`/`check_decor` checks and the NPM-vs-VPM elevation conflation in C6.
- Round 2 (this commit): counts 0 / PARTIAL 8 / MISSING 1 / N/A 1; added the reproducible per-feature evidence
  table (4/4 probes reproduced locally: control pass, +0.15 m Z / +0.25 m along-wall / wrong-wall all fail, value
  0.0) and the named decor identity tests; narrowed C1/C2/C4 to the residual non-opening/non-decor classes; made C6
  profile-aware with the NPM/VPM input table and dropped the unproven 100×-scale claim. No code changed (docs-only).
