# Reusable experimental course-grid steps (#1326 / candidate for #1296)

No `agr unwrap-atlas` command is registered by this pilot. These scripts expose
the exercised source-bound steps without a job-only copy of the underlying math.
They are experimental, not delivery validators; each output preserves `passed=false`.

## Page plan

The existing `tools.materials.course_grid_pages` fresh-process CLI assembles the
explicit approved page/member catalog around the chart/cut/fit cores. Its tests
cover stale sources, incomplete members, aliases, unsupported and duplicate input.
See `TWO_TILE_NORMAL_RESULT.md`; no fit-scale fallback or new tile is selected.

## Actual D/ERM/Normal bake

`python -m tools.materials.course_grid_bake --config <json> --output <NEW directory>`
uses the saved page plan and existing `course_grid_native.raster_cell_intersections`
core. `--validate-only` hashes all inputs without creating output. Run via the
project `uv` environment with SciPy (`uv run --with scipy python -m ...`).

The `course-grid-bake/1` config names15hash-bound roles: layout, source face
references/chart, placements1001/1002, no-groove base fields, historical support
classification, actual signed source fields, independently measured boundary
repair set, sourceD/ERM/N and unchanged Bricks1D/ERM/N. It also explicitly names
physical repeat/density, tile size/budget, DirectX convention, colour/ERM joint
RGB, background phase, dilation and scope decision references. Do not infer a
source from a filename or use the first available material.

Execution on this pilot:

```bash
uv run --with scipy python -m tools.materials.course_grid_bake --config "G:/Мой диск/AGR-evidence/1326-stylobate-course-grid/normal-v179/bake-config.json" --output "<NEW absolute directory>"
```

The actual run wrote `normal-v180`; its six4096PNG files are byte-identical to
all six accepted-stage linked maps in v157. The output prefix is deliberately
experimental `T_CourseGrid_`, not a claim of final delivery naming. Repeating the
command with an existing directory fails; never delete a sealed run to reuse it.
The postflight rehashes every input. The v200synthetic timing attack on an
agent-owned reference COPY exits2 after actual two-tile baking and leaves no
successful report; its partial PNGs in v201are explicitly **not a model**.

## Native finalization without live DCC access

`course_grid_native.plan_boundary_finalization(readback_rows, targets,
method='cyclic-anchor')` prepares an explicit source/material-bound plan outside
Blender. `method='triangulate'` is a distinct, explicit fixed-node operation; do
not apply it to a protected polygon when only cyclic serialization is needed.
The chosen cyclic mode preserves each polygon and every directed edge and
corner association. Missing, duplicate, bool-valued or stale target IDs refuse.

The plan schema is `course-grid-native-finalize/1`: `source_scene` path/SHA256,
`blender_version`, explicit `export_objects`, scope decision refs, and the
source-bound `faces` from the helper. The current example is
`normal-v191/native-plan.json`; every input XYZ/UV/material/source association is
checked again before any mesh mutation. Custom normals, seam edges, extra UV
channels and unpreserved custom attributes are unsupported and **refused**, not
silently lost. Source export visibility and exact selected-object set are checked.

```bash
"C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --background "G:/Мой диск/AGR-evidence/1326-stylobate-course-grid/normal-v160/stylobate_two_tiles_repaired_v160.blend" --python-exit-code 1 --python tools/blender/course_grid_finalize.py -- --plan "G:/Мой диск/AGR-evidence/1326-stylobate-course-grid/normal-v191/native-plan.json" --output "<NEW absolute directory>"
```

The actual selected run wrote v192; the hardened adapter replay v204 independently
reimports to exactly the same6,393-record dataset. v183is the retained explicit-diagonal trial,
not the selected protected-topology result. The adapter saves a native copy and
FBX; exit0 only means the operation executed. It does not certify either one.
Fresh-process native/export readback and actual linked image decoding remain
mandatory. The v192clean import matches6,393/6,393polygons, UVdelta0, maxXYZ9.005µm.

## Independent measurement helpers

- `joint_cross_section` measures the **1D union**, merging only touching or
  sub-nanometre arithmetic interval splits; a real2mm gap remains a failure.
- `union_joint_footprints(..., precision_m=1e-10)` declares a measurement-only
 0.1nm snap grid. It never changes a model or PNG. Keep unsnapped receipts and
  area-change accounting. Use exact WKB for a cached geometry; rounded WKT can
  turn microscopic valid touching polygons into an invalid replay.
- Keep source-empty endpoint rays explicit, with no invented numeric centre.
  Whole-face positive/negative mask coverage and bounded endpoint taper checks
  remain separate from a local source-positive centre/width measurement.
- Ordinary ERM brick pixels can equal the joint RGB. Use actual source-defined
  Diffuse-core/ERM numerical correspondence, not an unqualified green-pixel mask.

## Verification boundary

This pilot does not install dependencies globally, launch live Max, register a
shared capability or publish a delivery. Sources, accepted native files and the
Bricks1bitmap are never overwritten. The working source-stair checker baseline
[D296], final4BK/SINTEZ package checks and arbitrary engine/mip4 filtering remain
explicit boundaries. No replication is authorized [D310,D317].
