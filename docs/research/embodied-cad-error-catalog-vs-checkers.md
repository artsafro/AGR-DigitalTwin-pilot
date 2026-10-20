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
polycount, topology, UV, materials, UCX), and only a smaller layer (`src/twinqa/geometry/checks.py`) checks
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

| # | Error class | Our check (module → test) | Status | One-line why |
|---|---|---|---|---|
| E1 | Wrong coordinate frame | `scene.py` transforms/pivot/scale (`tests/qa/test_scene.py`); `checks.py` `check_bbox` (`tests/qa/test_geometry_checks.py`) | PARTIAL | reset/pivot/scale and gross bbox drift are caught, but a component in a wrong *local* frame relative to the assembly (window 180° flipped, cutter offset) is only caught if it moves the bbox/silhouette or fails orientation; no per-component frame-vs-source check |
| E2 | Stale local face selection | `check_material_ids` (`tests/qa/test_geometry_checks.py`); `surface_identity.py` (`tests/test_surface_identity.py`) | MISSING | `check_material_ids` validates id *ranges*, not source assignment; `surface_identity` compares whole-mesh area coverage, not which face carries which source attribute — there is no per-face source-attribute identity check |
| E3 | Incorrect offset on repeated features | `check_levels`/`check_floor_areas`/`check_silhouettes` (`tests/qa/test_geometry_checks.py`) | PARTIAL | gross displacement of a whole storey is caught; a repeated-feature *pitch/offset* (window grid, hole grid, rib pitch) has no dedicated check against the source |
| E4 | Stacking components at origin | `topology.py` (`tests/qa/test_topology.py`); `clearance.py` (`tests/qa/test_clearance.py`) | PARTIAL | exact coincident faces and near-parallel overlap are caught *within* a mesh, but two distinct parts coincident at the origin across meshes is not flagged as a cross-object coincidence |
| E5 | Inconsistent state-dependent argument | — (umbrella) | MISSING | no construction-state-vs-spec per-feature check; E3/E6/E7/E8 are its concrete forms and each is at best PARTIAL |
| E6 | Wrong height feature placement | `check_levels` (`tests/qa/test_geometry_checks.py`); `check_bbox` | PARTIAL | level elevations are checked at storey granularity; a per-feature height vs source (post, sill, ring) is not |
| E7 | Wrong target removal | `check_silhouettes`/`check_floor_areas`/`check_bbox` (`tests/qa/test_geometry_checks.py`) | PARTIAL | gross missing geometry changes the silhouette/area; "the wrong plate was removed while totals look similar" is not distinguished |
| E8 | Wrong mirror origin | `winding.py` + `check_orientation` (`tests/qa/test_orientation.py`); `component_volume.py` (`tests/qa/test_component_volume.py`) | PARTIAL | an inside-out (mirrored) component is caught via winding/signed volume, but a mirror around the wrong origin that stays outward-oriented is a positional error, not caught |
| E9 | Family confusion | `ops/operations.py` `run_operation`/`check_operation` (`tests/ops/test_operations.py`) | MISSING | the kernel checks pre/post *invariants* of a single op, but no checker validates the *order* of operations against an expected plan (delivery FBX carries no feature history) |
| E10 | Reward sparsity | `evals/graders.py`, `evals/receipt.py` (`tests/test_evals*.py`) | N/A | a training/eval-signal issue, not a delivery-geometry defect; our analogue is the "unmeasured check is an open gate, never a pass" rule in `checks.py` |

### Counts

- mapped (fully covered): **0**
- PARTIAL: **6** (E1, E3, E4, E6, E7, E8)
- MISSING: **3** (E2, E5, E9)
- N/A: **1** (E10)

The headline: the paper's errors are intent-conformance failures; our conformance checkers are strong
(topology, clearance, orientation, transforms) but our intent-conformance layer covers only *whole-model*
quantities (bbox, levels, floor areas, silhouettes). The missing layer is **per-component / per-feature
identity and placement vs the source**, which is exactly where the paper's four categories live.

---

## 4. Ranked checker candidates (≤ 8)

Ranked by expected catch rate against the paper's classes, then by reuse of existing primitives.
Size S / M / L is relative to the existing checker modules (`clearance.py` ≈ S, `checks.py` ≈ M, `placement/engine.py` ≈ L).

### C1 — Per-component frame-vs-source check (E1, E6, E8) — size M
- **Detects**: each instanced/repeated component (window, floor ring, pier, decor element, hole grid) placed,
  rotated, scaled or mirrored differently from its source placement; a component in a wrong local frame.
- **Job evidence**: backlog **EG5** (OBJ03 v009: 1 328 piers → 798 types because the type key had no rotation —
  "instances by translation only"); `jobs/REVIT-OPENINGS` window 180° flip lesson (`docs/domain/geometry.md`
  line 105); PR #392 dumper negative-scale (backlog P13).
- **SINTEZ overlap**: `lp_transforms` (2.3.14), `hp_meshes_transforms` (2.3.18/2.9.3) — both are "transforms applied"
  (reset), not per-component-vs-source; this candidate extends them with a source reference.

### C2 — Repeated-feature pitch/offset vs source (E3, E5) — size M
- **Detects**: spacing/offset of a repeated feature array (window grid, hole grid, rib pitch, ring step) vs the
  source/spec, so an "incorrect offset on repeated holes" or an ungrounded instance index fails.
- **Job evidence**: vyatskaya-tow02 PR #392 — 889 ribbon openings unsized by the extractor, no checker verified
  grid pitch (retro §1/P13); the mid-poly "44 faces < 2 cm" list had "no independent check yet" (retro §1 row 4).
- **SINTEZ overlap**: none (SINTEZ has no spec comparison); adjacent groups `lp_fbx_objects`/`hp_fbx_objects`
  (object composition) only.

### C3 — Cross-object coincidence / origin-stacking (E4) — size S/M
- **Detects**: two *distinct* logical parts whose bbox/vertices fully coincide (stacked at origin) and
  near-coincident coplanar overlaps below the 5 mm band *across* mesh boundaries (current `topology.py` is
  per-mesh; `clearance.py` needs classifying, not a verdict).
- **Job evidence**: OBR22-K02 raw Revit import "440 duplicate faces" (`docs/domain/geometry.md` line 90); the
  "stacking at origin" class is the direct paper example.
- **SINTEZ overlap**: `lp_duplicates` (2.3.7), `hp_duplicates` (2.3.11), `hp_collision` (2.13.x nested/intersect).

### C4 — Per-feature surface identity vs source (E2, E7) — size M
- **Detects**: a face/feature carries the wrong source attribute (stale face) or the wrong part was removed while
  the total stays similar — by comparing per-material/per-face-group area and attribute against the source, not
  just whole-mesh coverage.
- **Job evidence**: ad-hoc **R12** (BVH nearest-distance checker) already does a per-part version in the retro;
  `surface_identity.py` (issue #305) is the reusable primitive to extend.
- **SINTEZ overlap**: `hp_materials` (2.4.x), `lp_materials` (2.1.5 etc.), `lp_color_attributes` (4.1.1, MISSING in us).

### C5 — Per-component orientation / inside-out delivery finding (E8) — size S
- **Detects**: a component whose signed volume is negative or whose manifold edges wind the same way, surfaced as
  a *delivery* finding (today `component_volume.py`/`winding.py` are diagnostic or harness-only).
- **Job evidence**: PR #392 dumper mirror-matrix writes meshes inward (P13); `maf_surface.py` already reports
  flipped faces for MAF (issue #185) — same idea for OKS components.
- **SINTEZ overlap**: `hp_uv` (flipped UV 2.5.2.1.4b), `hp_collision` (unclosed/nonmanifold 2.13.4).

### C6 — Moscow elevation range (E1) — size S
- **Detects**: a model whose Z is outside the Moscow elevation band 110–250 m — a coordinate-frame/origin error
  that lands the whole model at the wrong site height (a cheap, high-signal frame check).
- **Job evidence**: the Ground FBX that came in 100× too large / wrong units (`docs/domain/geometry.md` line 35);
  SINTEZ `lp_height`/`hp_height` are already marked **MISSING** in `sintez_checks_1.6.1.json`.
- **SINTEZ overlap**: `lp_height` (4.1.4), `hp_height` (4.1.4) — direct.

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
- Counts: mapped 0 / PARTIAL 6 / MISSING 3 / N/A 1. No code changed (docs-only card).
