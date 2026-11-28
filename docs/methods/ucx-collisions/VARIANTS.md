# ucx-collisions - variants

VPM UCX collision for the Main (OKS) target (reg p.36-37 §13, [docs/domain/areas/ucx.md](../../domain/areas/ucx.md)).
Every variant reads ALL non-UCX meshes of the FBX (Main + MainGlass), drops the input's UCX, writes new pieces
`UCX_SM_<Address>_Main_NNN` (no material, no UV, identity transform) into a new FBX (triangulated export) and
`<out>.variant.json` (`ok`, `wall_time_s`, pieces). The source is never written.
Driver: `tools/methods/ucx/build_variant_blender.py` (factory Blender 5.1); geometry: `tools/methods/ucx/ucx_variants.py`
(numpy). Batch over the benchmark set: `tools/methods/ucx/run_benchmarks.py`.

Common limits: none of the variants classifies thin elements (R04 <= 5 cm), stairs (R14) or target
exclusions (R03); Ground UCX is a separate target (`ub.build_ground`); `ground-coarse-faces` is the only Ground
variant here and is measured on the #2042 replay cases, not in `results.jsonl`.

## kernel-boxes

- Idea: voxelise the surface in the dominant facade frame (cell 0.25 m), flood the exterior from the grid
  border, merge the solid cells greedily into boxes, shrink each box by gap/2 (4 mm gap). The cell grows
  until the boxes fit the [D012] budget.
- Tool: our kernel `src/dt_ai/geometry/ucx_build.py::build_main` (the shared builder of pipeline stage #10).
- Inputs: world triangles; model triangle count for the budget. Steps: rotate -> voxelise -> flood -> greedy
  boxes -> retract to the surface -> shrink -> rotate back.
- Limits: openings wider than a cell (windows, doors) let the exterior flood into rooms, so pieces follow
  the walls and leave rooms hollow; many pieces (hundreds); slowest of the five.

## slice-prisms

- Idea: cut the mesh at its levels (z of horizontal faces with >= 1 m2 area at one height; levels closer
  than 0.5 m are one), take the plan convex hull of each band (vertices in the band plus edge crossings of
  the band planes), extrude it over the band, bands 3 mm apart.
- Tool: our code, numpy (`slice_prisms`).
- Plan vertices within 1 cm of their neighbours' chord are dropped (commit 8b4bf02): before that, near-collinear
  points gave sliver cap triangles that read back non-convex (TOW02 48 of 49 pieces, rows R2 / R7 / R12 are
  the pre-fix measurements; R16-R18 are the current code).
- Limits: a concave plan (L, U, courtyard) is filled by its convex hull per band; projections inside one
  band are not followed vertically; one piece per level band, so many levels can exceed the budget.

## part-boxes

- Idea: one box per connected part (welded at 0.1 mm) in the facade frame; boxes closer than 3 mm are
  merged until every pair is at least 3 mm apart. A flat part (glass) gets a 2 cm thick box.
- Tool: our code, numpy (`part_boxes`). Common practice in team tools (one box per element), own code.
- Limits: parts that touch (walls meeting slabs in a Revit export) chain-merge into one box.

## part-hulls

- Idea: as part-boxes with a convex hull per part (bmesh.ops.convex_hull); hulls closer than 3 mm by a
  numpy SAT test are merged and re-hulled.
- Tool: Blender bmesh for the hull + our numpy merge (`part_hulls`).
- Limits: as part-boxes; a hull can have many triangles on curved parts.

## section-boxes

- Idea (#2053, Codex K9-K13): box decomposition by level sections instead of voxels. Levels are z of
  horizontal faces with >= 20 % of the largest level's area (slabs, roofs, terraces; window sills do not cut
  a band). Per band, the band's surface samples are projected to a 0.25 m plan grid in the facade frame and
  the band is split into ~0.5 m height bins. A plan flood from the border, blocked by "wall" cells (samples
  above the floor bin and below the ceiling bin, one-cell closing), marks the exterior. A down-facing
  underside with empty bins below it does not block this flood, even when too small to start a level.
  Where this opens a previously filled column, the upper solid starts at the underside and pavement stays
  separate. Roofed interior cells are still filled; unroofed courtyard interiors stay empty. Other occupied
  cells keep their lowest run of bins and, separately, the rest. Cells are grouped by their height bins;
  rectangle side with no used cell beyond it moves to the outermost sample inside it (the facade plane, not
  the grid); the same rectangle in consecutive bands is one taller box; a new bottom stands on its lowest
  sample, a top on its highest. Boxes shrink by gap/2 (4 mm gap, as kernel-boxes).
- Tool: our code, numpy (`section_boxes`), the shared `sample_surface` / `greedy_boxes` / `facade_angle` of
  `ucx_build`. Flag: variant name `section-boxes` (the default `agr ucx` path is unchanged).
- Limits: no triangle budget (Q1 of #2047: the form wins); no parapet rule (K12: the parapet ring gets its
  own thin boxes); a curved or diagonal facade becomes a 0.25 m staircase of boxes; an atrium inside an
  enclosed band is filled when the band is roofed. The passage heuristic depends on down-facing winding,
  clearance in the height bins and a plan opening that survives grid coarsening and one-cell closing.

## ground-coarse-faces

- Idea (#2053, Codex K16): "large volumes on flat parts, existing faces on slopes". Faces steeper than 15 deg
  (up-facing, highest surface only) are the slope; every other face goes to the shared Ground builder
  `ucx_build.build_ground` (BSP prisms, tol 8 cm, unchanged). The slope faces grow into planar clusters
  (minimax plane within the same 8 cm) whose plan union stays convex, then whole neighbouring clusters
  merge while the union stays convex and planar; each cluster is a prism over its plan shrunk by gap/2,
  its bottom 0.5 m below its lowest top (or below the foot of a steep face at its edge).
- Tool: our code, numpy (`ground_coarse_faces`) + the kernel `build_ground`. Flag: variant name
  `ground-coarse-faces`; the driver then writes `UCX_SM_<Address>_Ground_NNN`.
- A slope cluster lost during inset contributes its original projected face area to `dropped_plan_area_m2`.
  This is not uncovered Ground area: a BSP prism may already cover its footprint.
- Limits: on a terrain without slopes it is the default (case 11: 3 slope faces); the convex-union rule
  without new cut lines keeps irregular triangulations in many small clusters (pure face clusters gave
  1 716 pieces on case 11, over the 999-name limit, so flat parts stay on the BSP).

## single-hull

- Idea: one convex hull of the whole mesh. Baseline: always one valid piece, loosest fit.
- Tool: Blender bmesh convex hull (`single_hull`).
- Limits: fills every courtyard, recess and passage; violates R01 (preserve arches/courtyards) on any
  non-convex building.
