# VATUTINO-SITE Ground v006 — review round 1 fixes (PR #308, #295)

Input: `C:/x/t_d94665f2/paving_ground_inputs_v2.json` (adapter output of the paving master, unchanged since v005).
Outputs (local, never committed): `C:/x/t_d94665f2/ground_v006/` — `ground_master_{npm,vpm}.json`,
`ground_report.json`, `SM_Vatutino_Ground_{npm,vpm}_v006.fbx` (sha256 `1b5ac7ea8e2a1fe6…` / `6e0d3f0ae15939ac…`),
`readback_*.json`, `render_*.json`, `validate_*.json`; renders `C:/x/vatutino-ground/v006/{npm,vpm}/`.

Command (historical record — run before `--python-exit-code` became mandatory):

```text
uv run python jobs/VATUTINO-SITE/build_ground.py C:/x/t_d94665f2/paving_ground_inputs_v2.json --out C:/x/t_d94665f2/ground_v006
blender --background --factory-startup --python tools/blender/ground_json_to_fbx.py -- build|readback|render ...
uv run python tools/qa/validate_package.py <fbx> --profile npm|vpm --scene --json
```

## Review round 1 table (failing input -> expected -> v006 measured)

| # | Failing input (c9ab292) | Expected | Fix | v006 measured | Regression test |
|---|---|---|---|---|---|
| 1 | real input: faces 448/767/1346/1347/2352 at 10.8–27.7 mm (snap moved TIN crossings across steep breaks) | every face <= 10 mm or nonzero exit | `_refine_relief`: insert the exact worst point (interior split, or shared-edge split in both triangles: no T-junction) until <= tol; raises when stuck | 5 points inserted, max 9.966 mm, 0 / 33 092 over 10 mm | `test_r1_steep_break_under_snap_within_tol`, `..._fail_closed_when_stuck`, `..._edge_split_keeps_neighbours_conforming` |
| 2 | real input: Mulch faces 3575–3579 (0.80 m², 0.478 m out); after the label fix 2 LawnRolled slivers 0.15 m out | every face inside its covering + 22 mm | labels per triangle (centroid) instead of per partition face (a snap spike of the face sat in Mulch); `_recover_outlines` inserts outline crossings into triangles that lie > 2 mm on the other side (slivers bisected); `measure_inside` buffer 64 segments/quarter | outline recovery 5 points in 4 cells, outside 0 / 33 092 | `test_r1_faces_inside_contour_with_sub_snap_outlines[93,138,272]` fail at c9ab292 (2/3/2 faces), `..._outline_recovery_splits_crossing_triangle` |
| 3 | VPM UV side 1.25 + per-face scaling: 17 049 / 33 023 straddling | 0 straddling, sequential tiles, no added seam | VPM: one 4 m cell = exactly UDIM 1001 `[0,1]²` (u = 1 and u = 0 of the next cell are the same texel), flat 1 024 px/m; faces under 520 px/m (31, 6.31 m², steep VP breaks) get a vertical-plane projection (no mirroring, whole-unit shift into the tile); NPM: world top-down UV, one repeat per 68.27 m | FBX readback VPM: straddling 0, tiles [1001], mirrored 0, density 634.3–1 029.4; NPM 11.58–30.88 | `test_r1_vpm_flat_cell_one_tile_continuous`, `test_r1_vpm_steep_faces_in_band_contained_not_mirrored` |
| 4 | adapter JSON named `<out>/ground_master_vpm.json`: exit 0, input overwritten | exit nonzero before any write, input unchanged | `check_aliases` on every planned output (resolve + samefile) before `mkdir`; exit 2 | — | `test_r1_alias_input_refused_unchanged[3 names]`, `..._out_is_input_and_dotted_path`, control `..._control_build_writes_and_passes_gates` |

Fail closed: `build_ground.py` computes 8 gates (relief, containment, projection misses, cracks, NPM budget, density NPM/VPM,
VPM tile containment) and writes the mesh JSON only when all pass; otherwise only the report and exit 1.
Real input: all 8 pass, exit 0.

## Measured (ground_report.json)

- Partition: 1 331 cells, 1 282 with extra cuts (covering edges), 361 with TIN cuts; 33 092 surface triangles,
  36 652 with skirt (budget 150 000; NPM surface limit 50 000; GND-06 VPM limit 4 500 000 for 16 743.96 m²).
- Relief: 0 projection misses; vertex step error 4.5e-13 mm; face relief error max 9.966 mm; stack gap
  min 5.99999999 mm, max error 1.3e-8 mm, same-level overlap 0 m².
- Coverage: uncovered beyond the 1 mm snap 0 m²; open base edges off the outline 0; shortest edge 1.0 mm in
  relief cells, 0.34 mm overall (an inserted outline point).
- VPM side-projected faces: 31 (6.31 m²): their crease to the top-down neighbours is a texture seam.

## Readback (Blender 5.1.2, clean process) and validator

- Both FBX: 36 652 triangles, material mismatch 0 (by order and by centre), unit scale 1, object at 0,0,0,
  surface faces facing down 0, open edges 8 452 (stacked plate borders + skirt bottom: method C).
- Face Orientation back px top/45/135/225/315 = 0/0/4/0/0 (both).
- validate_package --scene: NPM pass 3 / fail 2 (V004, V012) / not_run 5; VPM pass 3 / fail 3 (V004, V010, V012) /
  not_run 9. V004: duplicates_and_self_intersections 1 984, isolated 128, co-directional overlap 25 514 pairs (stacked
  plates of method C); V010: no UCX (`not checked: #166 open`); V012: no Ground mask (#315). `not_run` never counted as pass.

## Still open (need the user, not waived)

- Curbs (+150 / +50 mm), steps, ramps, walls: the adapter ignores their layers; no per-element list exists yet.
- VPM open polygons: 8 452 open edges are the borders of the stacked plates (method C) and the skirt bottom.
- V004 duplicates / isolated plates vs method C.
