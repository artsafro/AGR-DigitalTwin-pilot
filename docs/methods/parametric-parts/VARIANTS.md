# Parametric parts — how each variant is built

Issue #713. `tools/methods/run_variant.py` (#706) is not on this tree. The same row is written by `tools/methods/parametric_parts_measure.py`.

FBX files are in `C:/x/methods/parametric-parts/`. This directory keeps the sha256 only (`SHA256SUMS`).

## Parts

Bench. Catalogue spec row 49, `Скамейка стальная «Андромеда»`, `library/maf/catalogue.json` `spec_dims` 1.800 × 0.500 × 0.720 m. The row is `availability: "Нет модели"`. The variant uses those overall dimensions, not a scan of `MAF_0411`. The silhouette is synthetic: a concave YZ profile (two legs, seat, back) drawn so that it fills that box. The leg, back and seat offsets are derived from the overall size, not from a measured library mesh. Profile and extrude: `tools/methods/parametric_parts/mesh_recipe.py`.

Roof unit. Issue #352 has no library paths in this repo (`docs/HANDOFF.md`: waits for project paths). The unit is the KPP1 `TN_Аэратор` profile in `jobs/KPP1/scripts/build_kpp1.py` (flange radius 0.195 m, height offset 0.064 m, pipe radius 0.05 m, cap radius 0.09 m) and `jobs/KPP1/REPORT.md` (flange Ø0.39, pipe Ø0.10, cap Ø0.18). Those radii and heights are sourced. The standalone stack does not include the 10 mm production embeds: flange height 0.064 m, pipe length 0.110 m, cap height 0.150 m. Bbox 390 × 390 × 324 mm. The mesh is a generated 16-gon of that profile (`AERATOR_SIDES`), with a vertex on +X so the bbox hits the flange diameter. It is not a scanned library part. Max and Blender build that revolve directly. SolidCraft builds the same three pieces as joined 16-gon extrudes (flange, pipe, cap). Its export triangulates them as 188 triangles; the recipe mesh is 192. Same radii, same heights.

Parameter change (bench, every tool): length 1800 mm → 1900 mm. Every tool also rebuilds the aerator with pipe length 0.110 m → 0.210 m (bbox height 424 mm).

## Versions

| Tool | Version | How it was run |
|---|---|---|
| SolidCraft | solidcraft-cli 0.23.1 (GitHub release `v0.23.1`, portable zip under `C:/x/methods/solidcraft/app/`) | `solidcraft-cli mcp --allow-path C:/x/methods/parametric-parts`, JSON-RPC stdio, tools `batch` / `execute` / `export` |
| Blender | 5.1.2 (hash ec6e62d40fa9, built 2026-05-19) | `blender --background --factory-startup --python-exit-code 1 --python tools/methods/parametric_parts/blender_build.py` |
| 3ds Max | 2026.3 (28.3.0.30732) | `python hermes_kanban/scripts/dcc_batch.py max --file tools/methods/parametric_parts/max_build.py --version 2026 --card t_5fcef264` |

## Commands

Timing boundary for every tool: build + FBX export. SolidCraft adds OBJ export and OBJ→FBX, because that conversion is required. Recipe math in Python stays outside the timer. Raw `build_s` values are in the three `*-build.json` receipts.

SolidCraft bench: `sketch.create` plane `YZ`, `sketch.line` of the profile in millimetres, `sketch.finish`, `solid.extrude` distance 1800. Parameter change: `timeline.edit` on feature `Extrude1`, `set.extent.distance = 1900`. Export `format: obj`. There is no `solid.box` fallback. An unsupported command is a `not_measured` row and no FBX.

SolidCraft aerator: parameter `pipe_length` (110 mm, then 210 mm), three sketches on XY, each a 16-gon, `solid.extrude` of the flange (new), the pipe (`start_offset` 64 mm, distance `pipe_length`, join) and the cap (`start_offset` `64 + pipe_length`, distance 150 mm, join). Parameter change: `parameters.change` of `pipe_length` to 210, then export again.

SolidCraft OBJ positions are millimetres. Vertices closer than 1e-9 m are welded; corners that are millimetres apart are not. The welded mesh is written as FBX by Blender 5.1's exporter (`axis_up=Z`, `axis_forward=-Y`, `bake_space_transform`, selection only). A hand-built FBX 7400 binary that contained Model, Geometry and Connections was read by this repo's parser and by Blender, and 3ds Max 2026 returned `importFile` false and zero objects for it. Max imports the Blender exporter's binary. `build_s` includes that Blender process.

Blender bench: recipe mesh extruded at length 1 m, Geometry Nodes `GeometryNodeTransform` scale X driven by a `Length` socket (1.8). Export FBX, selection only, `apply_unit_scale`, `bake_space_transform`, `axis_up=Z`, `axis_forward=-Y`, modifiers on. `build_s` is object build plus that export. The parameter row sets the Length socket to 1.9, updates the view layer, and exports again.

Blender aerator: recipe revolve at the pipe length. The Geometry Nodes modifier stays at scale 1. The parameter row replaces the mesh at pipe length 0.210 m and exports. Recipe evaluation is outside the timer.

Max: `units.SystemType = #meters`, `mesh()` from the recipe (the recipe call is outside the timer), `FBXExporterSetParam` UpAxis Z, Triangulate false, `exportFile` selected only. `build_s` is `mesh()` plus export. The parameter row is a new `mesh()` at the new length plus export. The `dcc_batch` process for all four meshes was 35.6 s, exit status ok, with the known startup warning `polyunwrapper_autoload.mse` (native exit 4294967166, wrapper status ok).

## Measure

```
uv run python tools/methods/parametric_parts_measure.py --fbx <in.fbx> --out <row.json> --spec-mm L W H --part <part> --tool <tool> --kind build|param_change --build-s <seconds> --dcc-objects <n> --dcc-triangles <n> --dcc-tool "3ds Max 2026.3 / dcc_batch"
```

The script refuses an output path that is the same file as the input (`os.path.samefile` and `st_ino`, so a hard link is refused). It publishes through `tempfile.mkstemp` in the output directory and does not open a predictable `.partial` sibling. It does not delete the input. xView is `dt_ai.ops.inv_xview` at 2 mm vertices and 5 mm faces (`<=` at the threshold). Dimension error is the max absolute difference of the three bbox extents in millimetres, after `UnitScaleFactor` (centimetres in the FBX spec) and the Model's Lcl Scaling and Lcl Translation. A non-zero Lcl Rotation, a parent other than the scene root, or a Geometry used by more than one Model is an error and writes nothing. The last `PolygonVertexIndex` must be negative; a trailing open polygon is an error and writes nothing. A hit, a non-finite coordinate, an empty mesh or an unreadable file exits 1 and writes nothing. Catalog rows pass the Max object count and triangle count; a mismatch exits 1 and writes nothing.
