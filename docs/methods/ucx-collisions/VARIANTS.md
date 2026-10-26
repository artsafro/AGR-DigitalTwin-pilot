# ucx-collisions - variants

VPM UCX collision for the Main (OKS) target (reg p.36-37 §13, [docs/domain/areas/ucx.md](../../domain/areas/ucx.md)).
Every variant reads ALL non-UCX meshes of the FBX (Main + MainGlass), drops the input's UCX, writes new pieces
`UCX_SM_<Address>_Main_NNN` (no material, no UV, identity transform) into a new FBX (triangulated export) and
`<out>.variant.json` (`ok`, `wall_time_s`, pieces). The source is never written.
Driver: `tools/methods/ucx/build_variant_blender.py` (factory Blender 5.1); geometry: `tools/methods/ucx/ucx_variants.py`
(numpy). Batch over the benchmark set: `tools/methods/ucx/run_benchmarks.py`.

Common limits: none of the variants classifies thin elements (R04 <= 5 cm), stairs (R14) or target
exclusions (R03); Ground UCX is a separate target (`ub.build_ground`), not in this round.

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

## single-hull

- Idea: one convex hull of the whole mesh. Baseline: always one valid piece, loosest fit.
- Tool: Blender bmesh convex hull (`single_hull`).
- Limits: fills every courtyard, recess and passage; violates R01 (preserve arches/courtyards) on any
  non-convex building.
