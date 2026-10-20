# VATUTINO-SITE Ground build v005 — evidence (#295)

2026-10-19, branch `improve/issue-295-site-slice-ground-build-for-vatutino-fro`, PR #308.
Outputs are local only: `C:/x/t_d94665f2/ground_v005/` (master JSON, report, FBX, readback, validator),
renders `C:/x/vatutino-ground/v005/{npm,vpm}/face_orientation_*.png`. Nothing binary is tracked.

Input: `C:/x/t_d94665f2/paving_ground_inputs_v2.json` (adapter `adapters.cad.spozu` on the paving DWG copy,
sha256 `231e4044774c520a…`). Command:

    uv run python jobs/VATUTINO-SITE/build_ground.py C:/x/t_d94665f2/paving_ground_inputs_v2.json --out C:/x/t_d94665f2/ground_v005
    blender --background --factory-startup --python tools/blender/ground_json_to_fbx.py -- build|readback|render ...
    uv run python tools/qa/validate_package.py <fbx> --profile npm|vpm --scene --json

## User decisions applied

- 4 x 4 m cut for one mid-poly master (correction of answer E); extra cuts only at covering edges/curves (chord
  2 cm) and, for relief, along TIN edges only where the 4 m mesh deviates more than 10 mm (user 2026-10-19
  "разница в 1 см не страшна"); TIN edges closer than 1 m allowed there (orchestrator clarification 14:57).
- Method C (layered cake), levels +6 mm / +12 mm, placeholders for textures, address token `Vatutino`.

## Method change against v002 (why)

v002/v004 triangulated every layer separately. With a 10 mm relief tolerance a base face could bend up to
10 mm away from the plate above it, so the 6 mm gap went to 0 or negative (measured on v004: 493 overlapping
base/plate pairs closer than 1 mm = poke-through / z-fighting), and independently snapped pieces left cracks.
v005 builds ONE planar partition (snap-rounded noding, 1 mm grid, of the surface outline, the covering outlines
and the 4 m grid lines; relief rounds add TIN edges inside the faces over tolerance) and emits each face once per
layer covering it. Stacked plates have identical triangles, so the gap is exact over any relief.

## Measured (ground_report.json, readback_*.json, render_*.json)

| Check | Result |
|---|---|
| 4 m XY cells / with extra cuts | 1 331 / 1 282 (covering edges or relief) |
| Cells cut along TIN edges for relief | 361 XY cells, relief region 3 694 m², 2 rounds |
| Relief error before refinement (4 m + covering cuts) | max 1 750 mm |
| Relief error after (exact max per face, not only centres) | max 27.65 mm; 5 of 33 023 faces > 10 mm (residual inside TIN-cut cells: contour lines closer than the 1 mm snap at steep VP breaks) — **open** |
| Shortest edge in relief-cut cells | 1.0 mm (= snap grid) |
| Layer gap (upper face centroid vs face below) | max error 1.3e-08 mm, min gap 6.000 mm; same-level overlap 0 m² |
| Vertex Z vs relief + level*step | 4.5e-13 mm; projection misses 0; XY/UV/material unchanged true |
| Base coverage of the surface | 99.99908 %; uncovered beyond the 1 mm snap 0 m²; outside beyond snap 0 m² |
| Cracks (base open edges off the outline) / non-manifold | 0 / 0 |
| Faces inside their covering contour (tol chord + snap = 22 mm) | 33 018 / 33 023; 5 Mulch faces (0.80 m²) up to 0.30 m outside — **open** |
| Triangles | surface 33 023 (NPM limit 50 000), + skirt = 36 575 (one-mesh budget 150 000); GND-06 limit for S_ter − S_pz = 16 744 m² → 4 500 000 |
| Density NPM on exported FBX (2K) | 11.58–30.71 px/m, 0 faces out of 10–40 (1 steep face UV-rescaled before export) |
| Density VPM on exported FBX (4K, 1 280 px/m flat) | 569.6–1 286.9 px/m, 0 faces out of 520–1 706 (24 steep faces UV-rescaled) |
| Readback (clean Blender 5.1.2) NPM / VPM | 36 575 tris = master; material mismatch by face order 0; surface normals down 0; unit scale 1.0; object at 0,0,0 |
| Face Orientation back-face pixels (5 fixed cameras, 1024²) | top 0, oblique45 0, oblique135 4, oblique225 0, oblique315 0 (same for NPM/VPM) |
| Placement | object origin at FBX zero, mesh XY centred; MSK-77 offset of the origin written by code to `<fbx>.placement.json`: (−7594.034145, −15287.745157, 0) |
| FBX sha256 | NPM `bed9bd37d8ef8e4e…`, VPM `66b56ec738b8e925…` |

## validate_package (--scene), not counted as pass where not run

- NPM: pass 3, fail 2, not_run 3 (V001, V005, V014; manual V015, V017).
- VPM: pass 3, fail 3, not_run 6 (V001, V005, V007, V009, V011, V013 MSK-77 point; manual V015, V016, V017).
- V004 topology: duplicates 1 906 at the 2 mm tolerance (vertices 1–2 mm apart where covering outlines nearly
  touch; with a 3 mm snap they drop to 0 but the relief residual rises to 20 faces / 251 mm, so 1 mm is kept) and
  122 isolated polygon groups = the separate plates of method C — a validator vs method-C question, **review**.
- V004 co-directional clearance: 97 of 25 444 pairs < 5 mm — the 6 mm vertical step measured perpendicular on
  steep faces; 319 > 20 mm are the +12 mm plates and the skirt.
- V010 UCX: not checked: #166 open (no hand-made UCX).
- V012 mesh names: the validator has no `SM_{Address}_Ground` mask (GND-11 names are used) — validator gap.

## Not done in this run (open)

- Curbs (+150 mm drives, +50 mm garden) and stairs: the curb/stair layers are in `ignore_layers` of the adapter
  config, the adapter returns no polylines for them and the DWG has no curb widths or stair dimensions; reading
  them needs an adapter extension outside the authorized contour scope. Listed, not modelled.
- 5 residual relief faces > 10 mm and 5 Mulch faces outside their contour (see table).
