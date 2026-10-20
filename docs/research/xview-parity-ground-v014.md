# xView parity on Ground v014 (#370)

Kernel invariant `xview_overlaps` (`src/dt_ai/ops/inv_xview.py`) against the real 3ds Max xView checkers
"Overlapping Vertices" (0.002 m) and "Overlapping Faces" (0.005 m), Artem's production thresholds.
Technical evidence only; no Ground output file was changed. Acceptance of the gate is a separate, human step.

## How it was measured

- 3ds Max 2026.3, headless (`hermes_kanban/scripts/dcc_batch.py max`), on COPIES of
  `C:/x/t_d94665f2/ground_v014/npm/SM_Vatutino_Ground.fbx` (SHA-256 `94357c5f048b...`) and
  `.../vpm/SM_Vatutino_Ground.fbx` (`a41266757fe3...`) in `%LOCALAPPDATA%/Temp/agr-max-t_3013550d/`.
- MAXScript interfaces `OverlappingVertices` / `OverlappingFaces` (`.tolerance`, `.Check <time> <node> &results`) -
  the same checkers the xView menu runs (`xViewChecker` ids 7 / 2). System units metres, tolerance read back
  0.002 / 0.005. Max returns 1-based vertex / face ids.
- `tools/qa/xview_dump.ms` writes the Max ids plus the node's vertices (metres, 7 decimals) and faces;
  `uv run python tools/qa/xview_parity.py <dump.json>` runs our invariant on exactly that mesh and compares ids.
- Two node states: the FBX as imported (`Editable_mesh`, 27 281 vertices, 46 343 triangles) and after
  `convertToPoly` (`Editable_Poly`, 27 340 vertices, 46 343 faces) - the state Artem works in.
- NPM and VPM have identical geometry (they differ in materials / UV), so their results are identical.

## Result

| file / node state | Max OV vertices | ours OV vertices (pairs) | Max OF faces | ours `contact` faces | ours all faces (`contact` + `area`) | ids equal |
|---|---|---|---|---|---|---|
| NPM, Editable_mesh | 0 | 0 (0) | 146 | 146 | 167 | yes |
| VPM, Editable_mesh | 0 | 0 (0) | 146 | 146 | 167 | yes |
| NPM, Editable_Poly | 118 | 118 (59) | 351 | 351 | 372 | yes |
| VPM, Editable_Poly | 118 | 118 (59) | 351 | 351 | 372 | yes |

Face pairs by kind (both states): `area+contact` 136, `area` 67; `contact` only 19 (mesh) / 225 (poly).

### Differences, case by case

1. **Editable_Poly adds 59 vertex pairs at 0.000 mm** (118 vertices). `convertToPoly` splits the 59 non-manifold
   vertices of the imported mesh into coincident copies; xView and our invariant both count them (distance 0 <= 2 mm).
   This is what Artem saw as "small errors" in Overlapping Vertices. Not a checker difference.
2. **Our `area` rule flags 21 more faces (67 pairs) than xView.** All 67 pairs are opposite-facing; 65 share no
   vertex, 62 of them are vertical faces back-to-back about 1.3 mm apart (e.g. faces 36330 / 36458, 0.047 m2 overlap).
   They cross edge over edge with no vertex of one face inside the other, so xView's vertex-in-face rule cannot see
   them. Isolated in Max, the pair 36330 / 36458 returns `f=[]`; the synthetic `cross_no_vertex_in` case likewise.
   Kept on purpose: the issue defines an overlapping face pair by overlapping area, either orientation.
3. No face or vertex flagged by Max is missed by us (`faces_only_max` = `vertices_only_max` = []).

## What xView actually checks (measured on synthetic meshes in Max)

| case | Max result | our invariant |
|---|---|---|
| two vertices 1.5 mm / 2.0 mm / 2.5 mm apart | 1.5 flagged, 2.0 and 2.5 not | 1.5 and 2.0 flagged (`<=`, fail-closed), 2.5 not |
| unused vertex 1 mm from a used one | flagged | flagged |
| quads 50 % overlap, z = 0 / 1 / 4 / 4.9 mm, same or opposite facing | flagged | flagged |
| same, z = 5.0 mm | flagged | flagged |
| same, z = 5.1 / 6 mm | not | not |
| quads touching along an edge (unwelded coincident vertices) | faces + 4 vertices flagged | `contact` pair + 2 vertex pairs |
| quads 3 mm apart in plane | not | not |
| T-vertex on the middle of the other face's edge, z <= 5 mm | flagged | `contact` |
| vertex inside the other face, tilt 0.600-0.810 deg | flagged | flagged |
| same, tilt 0.815-0.95 deg | not | not (`PARALLEL_COS_MIN` = 0.9999 = 0.8103 deg) |
| faces crossing at 5 deg / 90 deg | not | not |
| two faces crossing edge over edge, no vertex inside (1 mm apart) | **not** | `area` pair |
| duplicate face with the same vertex ids | **not** | `area` pair |
| Editable_Poly: ids returned | polygon ids | polygon ids |

So xView "Overlapping Faces" = a vertex of one face, not shared with the other, projects into the other face
(boundary included) at a plane distance <= tolerance, with |cos| of the normals >= 0.9999. That rule (`contact` in our
report) reproduces all 146 / 351 faces on v014. The issue's area rule is added on top.

## Status

- `xview_overlaps` is wired report-only: `check_operation_xview(..., gating=False)` appends a non-gating result, and
  `jobs/VATUTINO-SITE/build_ground.py` writes `ground_report.json["xview_overlaps"]` outside `gates`.
- It becomes a gate (`gating=True`, and a `gates` entry in the Ground build) once a person accepts this parity.
- v014 is not xView-clean under the delivery rule [D152]: 146 / 351 faces and 0 / 118 vertices. Fixing the Ground is
  a separate task.
