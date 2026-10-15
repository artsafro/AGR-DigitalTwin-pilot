# Experiment: Blender — headless bpy automation and geometry checks

Card t_fea03fc1. Report tested: `docs/research/blender-bpy-automation.md` (branch
`docs/research-blender-bpy-automation`). All defect fixtures are **synthetic**.

## Question

The report claims (§5, §6, tasks B and C) that the current checkers have blind spots for face
orientation and transverse intersections, and that BMesh + `mathutils.bvhtree` can close them.
Does the current checker miss these defects on the project's own benchmark models, and does a BMesh/BVH
check in the live Blender 4.4 detect them without false positives on clean engine output?

## Methods picked (2 of the report's 6 tasks)

- **M1 orientation (§5 / B):** (a) winding consistency along shared edges (BMesh: an edge whose two loops
  start at the same vertex); (b) outwardness by outside rays: 52 directions (horizontal and from above;
  the from_spec body bottom is open by pattern) × 48×48 rays; a polygon hit first on its back side is
  inward-facing.
- **M2 intersections (§6 / C):** `BVHTree.FromPolygons(...).overlap()` on fan triangles that keep their
  source polygon id; drop identity, same-polygon and vertex-sharing pairs; classify the rest: coplanar,
  contact (a vertex within 0.1 mm of the other plane) or crossing (both triangles strictly straddle the
  other's plane). Crossings no deeper than `roof_inset_embed_m` max (0.05 m) are counted as embeds.

Not picked: A/D (would need a separate `blender -b` launch; this card may drive Blender only through
`blender_exec.py`), E (bpy wheel — no Python 3.13/5.x wheel lane here), F (no blocking geometry case
in the time box). The sibling card covers mesh_audit vs BMesh counts.

## Setup

```bash
uv run python experiments/blender-bpy-automation/make_fixtures.py "%TEMP%/agr-exp-t_fea03fc1"
python C:/Users/artsafro/hermes_kanban/scripts/blender_exec.py --code \
  "FILES=[...];REPEATS=3;exec(open('experiments/blender-bpy-automation/bmesh_checks.py').read(), globals())"
```

- Inputs: engine `from_spec` dumps of `benchmark/bench-b01-box`, `bench-b02-corner-niche`,
  `bench-b02t-terrace` (spec.json + object.json), plus 4 synthetic defects each: `flip1` (one facade
  polygon reversed), `flipall` (all body polygons reversed), `cross` (a 0.4 m closed box in a separate
  mesh, centred on a facade wall plane), `selfx` (the same box inside `body`). Plus a stress copy:
  B02t ×10 (3240 polygons). Files in `%TEMP%\agr-exp-t_fea03fc1\` only.
- Baseline: `twinqa.geometry.checks.run` (what `tools/qa/check_geometry.py` runs), model against itself
  as etalon, so only the mesh checks can fail.
- Prototype: standalone BMesh / BVH in Blender 4.4.0 via `blender_exec.py`; no scene objects created
  (scene 0 objects before and after). Results: `experiments/blender-bpy-automation/results_*.json*`.

## Results

| Fixture (×3 benches) | Baseline `checks.run` | M1 winding bad edges | M1 outside back faces | M2 crossings (self / cross-mesh) | M2 embeds |
|---|---|---|---|---|---|
| clean | pass ×3 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 | 17 / 32 / 88 |
| flip1 | **pass** ×3 (missed) | 4 / 4 / 4 | 1 / 1 / 1 | 0 / 0 | same as clean |
| flipall | **pass** ×3 (missed) | 0 / 0 / 0 (consistent) | 139/141, 234/236, 321/324 | 0 / 0 | ≈ clean |
| cross | **pass** ×3 (missed) | 0 | 0 | 0 / 10 each | same |
| selfx | **pass** ×3 (missed) | 0 | 0 | 10 each / 0 | same |
| stress B02t×10 (3240 polys) | — | 0 | 0 | 0 / 0 | 880 |

- Detection: baseline 0 of 12 defect fixtures; prototype 12 of 12 (M1: 6/6, M2: 6/6). False positives on
  clean engine models: 0 for both methods. Results identical across 3 runs (`stable: true`).
- The 17/32/88 embeds on clean models are the `roof-inset-plane` pattern (plate at +5 mm, embedded
  20 mm into parapet inner faces, [D038]): real triangle crossings, allowed by the pattern. Without the
  depth rule M2 reports them as crossings (first run: 17/32/88 false positives).
- Runtime (median of 3, inside Blender): winding 0.3–1.0 ms (5.1 ms at 3240 polys); rays 135–210 ms
  (constant ~120k rays; 114 ms on the stress file); overlap 0.4–1.5 ms (9.4 ms at 3240 polys). Plus
  ~0.12 s per `blender_exec` call (t_b4af19e2). Baseline `checks.run`: 81–187 ms per fixture.
- Code size: `bmesh_checks.py` ~170 lines incl. docstrings; `make_fixtures.py` ~110 lines. No project
  code changed; `tests/qa/test_from_spec.py` + `test_geometry_checks.py`: 178 passed.

## Verdicts

| Method | Verdict | Reason |
|---|---|---|
| M1a winding along shared edges | **adopt** | Catches every single-polygon flip, 0 false positives, < 1 ms; needs no Blender: it is an edge-direction count that fits `twinqa.geometry` (pure numpy). |
| M1b outwardness by outside rays | **adopt** | Only method that caught a consistently inverted mesh (`flipall`: winding check sees 0). 0 false positives on B01/B02/B02t; ~0.15 s. Limit: faces invisible from outside (inner niche/courtyard back faces) are not judged; rays from below are skipped because the body bottom is open. |
| M2 BVH transverse crossings | **maybe** | Detects 10/10 box crossings (self and cross-mesh) that `near_parallel_overlaps` misses, but only after a depth rule; a depth-only embed rule would hide any defect ≤ 50 mm. Needs binding to the actual inset slabs (`check_mesh` slab/loop data) before it can gate. |

## Proposed follow-up tasks (no issues created)

1. **twinqa: winding + outside-ray orientation check (M1)** — scope: add `check_orientation` to
   `src/twinqa/geometry/checks.py` (pure numpy port: shared-edge direction count, first-hit back-face test of rays from
   outside with a numpy triangle ray caster), wire it into `checks.run` for every render mesh incl. decor;
   tests: flip1/flipall/mirrored fixtures fail, B01/B02/B02t engine models pass. Keep the BMesh script as
   the native cross-check lane. Coordinate with #117/#126.
2. **twinqa: transverse crossing classifier (M2), report-only first** — scope: BVH-equivalent candidate
   search (numpy AABB sweep) + straddle test; mark a crossing as an allowed embed only when one triangle
   belongs to an inset plate found by `check_mesh` and its depth is within `roof_inset_embed_m`; report
   `crossings` separately from `overlaps`; gate only after the user accepts on K01.
