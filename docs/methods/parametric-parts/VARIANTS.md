# Parametric parts — how each variant is built

Issue #713. `tools/methods/run_variant.py` (#706) is not on this tree. The same row is written by `tools/methods/parametric_parts_measure.py`.

FBX files are in `C:/x/methods/parametric-parts/`. This directory keeps the sha256 only (`SHA256SUMS`).

## Parts

Bench. Catalogue spec row 49, `Скамейка стальная «Андромеда»`, `library/maf/catalogue.json` `spec_dims` 1.800 × 0.500 × 0.720 m. The row is `availability: "Нет модели"`; the variant uses those overall dimensions, not a scan of `MAF_0411`. Silhouette: a concave YZ profile (two legs, seat, back) extruded along X. Profile and extrude: `tools/methods/parametric_parts/mesh_recipe.py`.

Roof unit. Issue #352 has no library paths in this repo (`docs/HANDOFF.md`: waits for project paths). The unit is the KPP1 `TN_Аэратор` profile in `jobs/KPP1/scripts/build_kpp1.py` (flange radius 0.195 m, height offset 0.064 m, pipe radius 0.05 m, cap radius 0.09 m, cap from 0.155 m to 0.005 m below the instance top) and `jobs/KPP1/REPORT.md` (flange Ø0.39, pipe Ø0.10, cap Ø0.18). The standalone spec stacks those pieces without the 10 mm production embeds: flange height 0.064 m, pipe length 0.110 m (the builder docstring's "pipe 110 mm"; the report's Ø0.10 is the diameter), cap height 0.150 m. Bbox 390 × 390 × 324 mm. A 16-gon revolve with a vertex on +X so the bbox hits the flange diameter. Max and Blender build that revolve. SolidCraft's aerator row is `solid.box` at those three extents (12 triangles), not the revolve.

Parameter change (one per tool, the bench): length 1800 mm → 1900 mm. Max and Blender also rebuilt the aerator with pipe length 0.110 m → 0.210 m (bbox height 424 mm). Those two extra rows are in `RESULTS.md`.

## Versions

| Tool | Version | How it was run |
|---|---|---|
| SolidCraft | solidcraft-cli 0.23.1 (GitHub release `v0.23.1`, portable zip under `C:/x/methods/solidcraft/app/`) | `solidcraft-cli mcp --allow-path C:/x/methods/parametric-parts`, JSON-RPC stdio, tools `batch` / `execute` / `export` |
| Blender | 5.1.2 (hash ec6e62d40fa9, built 2026-05-19) | `blender --background --factory-startup --python-exit-code 1 --python tools/methods/parametric_parts/blender_build.py` |
| 3ds Max | 2026.3 (28.3.0.30732) | `python hermes_kanban/scripts/dcc_batch.py max --file tools/methods/parametric_parts/max_build.py --version 2026 --card t_5fcef264` |

## Commands

SolidCraft bench: `sketch.create` plane `YZ`, `sketch.line` of the profile in millimetres, `sketch.finish`, `solid.extrude` distance 1800. Parameter change: `timeline.edit` on feature `Extrude1`, `set.extent.distance = 1900` (the field list comes from the engine error on `set.distance`). Export `format: obj`. SolidCraft does not export FBX (`export` formats are step, 3mf, stl, obj, urdf). `solidcraft_build.py` writes an ASCII FBX of those OBJ vertices and faces, dividing millimetres by 1000 and setting `UnitScaleFactor` 100. `build_s` is the MCP `batch` / `timeline.edit` time only.

A first bench parameter attempt edited a feature named `Box1` (no such feature on the extrude) and fell back to `solid.box` 1900 × 500 × 720. That OBJ read back with `xview_vertices_2mm` 4, so it is not the reported row. The reported param FBX is the `Extrude1` edit (`edit_s` 0.0013164 s, 40 triangles).

SolidCraft aerator: `solid.box` length 390, width 390, height 324 mm. `timeline.edit` of `Box1` height failed in that session (`no feature Box1`); the height-424 file is a second `solid.box`. Both read back clean.

Blender bench: recipe mesh extruded at length 1 m, Geometry Nodes `GeometryNodeTransform` scale X driven by a `Length` socket (1.8, then 1.9). Export FBX, selection only, `apply_unit_scale`, `bake_space_transform`, `axis_up=Z`, `axis_forward=-Y`, modifiers on. `build_s` includes the modifier and the export.

Blender aerator: recipe revolve at the pipe length. The same Geometry Nodes modifier is on the object with scale fixed at 1 (the pipe length is not a scale). An earlier export linked that socket to scale X and shrunk the diameter (390 × 0.11 = 42.9 mm, and 12 xView faces). That file was overwritten by the scale-1 export. The reported row is the overwrite.

Max: `units.SystemType = #meters`, `mesh()` from the recipe, `FBXExporterSetParam` UpAxis Z, Triangulate false, `exportFile` selected only. `build_s` is create plus export inside the session. The `dcc_batch` process for all four meshes was 37.2 s, exit status ok, with the known startup warning `polyunwrapper_autoload.mse` (native exit 4294967166, wrapper status ok).

## Measure

```
uv run python tools/methods/parametric_parts_measure.py --fbx <in.fbx> --out <row.json> --spec-mm L W H --part <part> --tool <tool> --kind build|param_change --build-s <seconds>
```

The script refuses an output path equal to the input, writes `<out>.partial`, then renames. It does not delete the input. xView is `dt_ai.ops.inv_xview` at 2 mm vertices and 5 mm faces (`<=` at the threshold). Dimension error is the max absolute difference of the three bbox extents in millimetres, after `UnitScaleFactor` (centimetres in the FBX spec) is applied: metres = file units × factor / 100. A hit, a non-finite coordinate, an empty mesh or an unreadable file exits 1 and writes nothing.
