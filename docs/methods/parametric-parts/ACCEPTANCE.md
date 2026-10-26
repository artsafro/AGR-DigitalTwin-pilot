# Parametric parts — acceptance

One row per review witness, plus the clean-cube controls. Inputs are fixtures in `tests/methods/test_parametric_parts_measure.py` unless the path is absolute.

| acceptance point | input | expected | test |
|---|---|---|---|
| Geometry with no Model connection | ASCII cube, Vertices and PolygonVertexIndex, no Connections | nonzero, status names Model, no row | `test_geometry_without_model_connection_nonzero_and_nothing_written` |
| DCC readback | writer cube plus `C:/x/methods/parametric-parts/bench-solidcraft.fbx` and `aerator-solidcraft.fbx` | fresh 3ds Max (or Blender if Max is absent) import, objects ≥ 1, triangles equal the parser; the test is `@pytest.mark.max`, so the default lane leaves the shared Max lock alone; skip reason `DCC readback unavailable: 3ds Max 2026 and Blender 5.1 are not installed` | `test_dcc_readback_imports_mesh_and_solidcraft_files` |
| Aerator is flange + pipe + cap | `C:/x/methods/parametric-parts/aerator-solidcraft.fbx` | not 12 triangles; max radius 0.195 m; a 0.05 m radius; flange near z=0; cap near the top; bbox 390 × 390 × 324 mm | `test_catalog_aerator_is_stepped_flange_pipe_cap` |
| Timing boundary | `WHEN.md`, `VARIANTS.md` | the words `build + FBX export` and an `Adoption:` line | `test_timing_boundary_is_documented` |
| Witness A, unterminated polygon | clean 1 m cube plus trailing indices `0,1` | nonzero, status contains `malformed polygon`, no row | `test_unterminated_polygon_nonzero_and_nothing_written` |
| Witness B, Lcl Scaling | 1 m cube, Model `Lcl Scaling` 2,1,1, spec 1000 mm | extents 2000, 1000, 1000 mm, dimension error 1000 mm, row written | `test_lcl_scaling_changes_world_extents` |
| Lcl Translation control | same cube, `Lcl Translation` 1,0,0 | minimum X is 1 m, X extent stays 1 m | `test_lcl_translation_moves_vertices_and_keeps_extents` |
| Unsupported rotation | same cube, `Lcl Rotation` 90,0,0 | nonzero, status contains `unsupported Lcl Rotation`, no row | `test_lcl_rotation_rejected` |
| Sentinel temp file | valid cube, pre-existing `row.json.partial` text `SENTINEL` | exit 0, sentinel bytes unchanged, row written | `test_preexisting_partial_sentinel_is_not_overwritten` |
| Output hardlink of the input | valid cube, `row.json` hard-linked to the FBX | exit 2, stderr contains `refusing`, input bytes and inode unchanged | `test_output_hardlink_of_input_is_refused` |
| Writer sentinel and scene | `mesh_recipe.write_ascii_fbx` of a cube, pre-existing `part.fbx.partial` | sentinel unchanged; readback is 12 triangles and a 1 m extent | `test_fbx_writer_sentinel_and_model_connection` |
| OBJ/FBX hardlink | OBJ hard-linked to the FBX path | `McpError` containing `refusing`, OBJ bytes unchanged | `test_obj_and_fbx_hardlink_is_refused` |
| Clean cube control | 1 m cube, identity Model, UnitScaleFactor 100 | exit 0, 12 triangles, error 0, topology valid, no `.partial` left behind | `test_clean_cube_writes_measured_row` |
| NaN, inf, empty control | cube with a NaN coordinate, an inf coordinate, or no polygons | exit 1, `not measured:`, nothing written | `test_bad_mesh_nonzero_and_nothing_written` |
| Same path control | `--out` equal to `--fbx` | exit 2, input bytes unchanged | `test_same_input_output_path_nonzero_and_input_unchanged` |
