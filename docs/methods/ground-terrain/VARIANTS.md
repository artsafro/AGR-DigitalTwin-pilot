# ground-terrain - variants

Ground surface: relief, plan holes, boundary (the layered paving cake only in the builder). Status: **measured**
(3 variants; cells 4 / 2 / 8 m; benchmark vatutino-ground). Rows: [RESULTS.md](RESULTS.md); guide: [WHEN.md](WHEN.md).

Common to all variants:
- Input: the typed adapter v4 `C:/x/methods/src/vatutino-ground/paving_ground_inputs_v4.json`
  (sha256 `3b6b433d718c0292f472293849f3363fd2ae90d4892e598efca52be44cd9d502`, a read-only copy of
  `C:/x/t_d94665f2/paving_ground_inputs_v4.json`); every variant row has `input.kind = adapter-v4` and that sha256.
  No variant is built from the reference FBX.
- Reference (deviation only, never an input): the v014 VPM FBX of benchmarks.json and its `.placement.json`
  sidecar (sha256 `c105161eb2a9f6b397a0f590abe4fb97684080f4e5e8a8e37fc4d732b9287f7b`), copied next to it. Row
  `reference-v014` measures a copy of it against itself: the zero line of the metric.
- Export: the shared `tools/blender/ground_json_to_fbx.py build` (object `SM_Vatutino_Ground`, XY bbox-centre pivot,
  placement sidecar), so the variants differ only in the mesher. Driver: `tools/methods/ground/build_variant.py`;
  batch: `tools/methods/ground/run_benchmarks.py` (build in a fresh process, then `run_variant.py`).
- Metrics: `class_metrics.ground` ([README](../README.md#row-fields)): dz on a fixed 1 m XY grid against the
  reference top surface, triangles, holes >= 1000 m2, exterior boundary length, UV present.

## 1. builder - our Ground builder (method C layers)

- Idea: the production layered cake: coverings as stacked plates (+6 / +12 mm), 4 x 4 m cells cut along TIN edges
  where the relief deviates > 10 mm, steep-face raise, 1 m skirt, kerbs and stairs as details, Ground gates.
- Tool: Python (shapely / numpy, `dt_ai.geometry.ground_cake`); `jobs/VATUTINO-SITE/build_ground.py` run unchanged.
- Steps: `build_ground.py <adapter> --cell <c> --snap 0.003 --gap-exceptions jobs/VATUTINO-SITE/ground-gap-exceptions.json
  --out <work>/builder` (the v014 arguments), then its `ground_master_vpm.json` through the shared FBX writer.
- Script: `tools/methods/ground/build_variant.py builder`.
- Limits: fail closed. Only cell 4 m passes its gates: the [D150] gap exceptions are pinned to the v014 surface
  sha256, so any other cell changes the surface and fails `normal_gap_max_20mm`; cell 2 m and 8 m also fail
  `density_vpm` (8 m also `vpm_uv_tile_contained`); cell 6 m fails only `normal_gap_max_20mm`. A failed build writes
  no mesh, so it has no row (logs: `C:/x/methods/ground-terrain/builder-{2,8}m/work/builder.log`,
  `C:/x/methods/ground-terrain/logs/probe_c6.log`). Slowest: its gates run inside the build.
  Review round 1 probe, same v014 arguments, one parameter changed: cell 3, 3.5, 4.5, 5 m and chord 0.01 / 0.04 m at
  cell 4 all fail `normal_gap_max_20mm` (3.5 and 5 m also `density_vpm`); logs `C:/x/methods/ground-terrain/probes2/`.
  Every CLI parameter feeds the pinned surface or a gate tolerance, so a second builder row needs a user decision.

## 2. cdt - constrained Delaunay on the plan, then height projection

- Idea: one surface without layers: the plan polygon (boundary minus footprints >= 1000 m2, same planner as the
  builder) is split on a cell x cell grid; each cell piece is triangulated by constrained Delaunay keeping every plan
  edge; vertices welded at 1 um; Z from the adapter TIN (all 5188 elevations, the builder's TIN); world-planar UV.
- Tool: shapely 2.1 / GEOS `constrained_delaunay_triangles`, numpy, `dt_ai.geometry.ground_cake` TIN sampler.
- Steps: `gv.plan_polygon` -> `gv.cdt_mesh(plan, cell)` -> `gv.project_relief` -> `gv.mesh_dict` -> FBX writer.
- Script: `tools/methods/ground/build_variant.py cdt` (pure parts in `tools/methods/ground/ground_variants.py`).
- Limits: no covering layers, kerbs, stairs or skirt (one `Surface` slot); relief is sampled only at the vertices,
  so between them the surface is linear and misses TIN ridges inside a cell; a vertex outside the TIN would take the
  nearest relief point and be counted (`relief_misses`, 0 on vatutino-ground).

## 3. bgrid - Blender regular grid projected onto the relief, plan holes cut

- Idea: a regular cell x cell grid over the plan bbox; a quad is kept when its centre is inside the plan (even-odd,
  so the holes and the boundary are cut on the grid, stair-stepped); quads triangulated; every vertex Z by a downward
  BVH raycast onto a relief TIN built in Blender.
- Tool: Blender 5.1.2 factory, bpy / bmesh / mathutils (`delaunay_2d_cdt`, `BVHTree`, `KDTree`).
- Steps: driver writes local-metre `prep.json` (plan rings, elevations) -> `build_grid_blender.py` -> mesh JSON ->
  FBX writer.
- Script: `tools/methods/ground/build_variant.py bgrid` + `tools/methods/ground/build_grid_blender.py`.
- Limits: boundary and holes follow the grid, not the plan edges (boundary length and coverage error grow with the
  cell); no layers, kerbs, stairs or skirt; relief sampled only at grid vertices.
