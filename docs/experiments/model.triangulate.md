# Lab experiment L01: `model.triangulate` (AGR Tools 0.8)

Source checked: GeoAGR 13.64 "Triangulate" LMB -> Delaunay dialog (`GeoAGR.ms:47088`, `GeoAGR.ms:50991`,
`GeoAGR.ms:51169-51325`) with `DelaunayCore.dll`. No GeoAGR code here (#853); details, job scripts and raw outputs are
in the private GeoAGR repository, branch `lab-exp/L01`, `work/lab-experiments/model.triangulate/`.

Run: 3ds Max 2024.2 via the AGR Lab runner (3dsmaxbatch), synthetic scenes only (`synthetic_*`), metres.
Jobs: `20261104-225803-af05edbc`, `20261104-230309-c1a56e5d`.

## What the source does (measured)
- Triangulates the selected faces of one Editable Poly (face level) by projecting each face on its plane, picking
  Delaunay triangles in a .NET DLL and applying the returned vertex pairs with Max Connect.
- Correct on: octagons, concave U and comb outlines, thin 10 m x 0.5 mm strips, 64-gons, 400 hexagons, nodes rotated
  and moved (world space is consistent), cylinder caps with UVs.
- Preserves UV area, material IDs and smoothing groups; unselected faces are untouched; one Undo reverts the run.

## Defects
1. **Small faces stay n-gons silently.** The DLL uses absolute 1e-6 thresholds (scene units). Octagons of radius
   0.5 / 0.3 / 0.1 mm and a 0.6 x 0.3 mm concave outline in a metre scene got zero pairs and stayed 8-gons; the only
   signal is a dialog label. Such leftovers fail 2.3.17 at SINTEZ.
2. The DLL returns many redundant and crossing pairs (octagon 20 for 5 needed; 400 hexagons 2120 for 1200). Max Connect
   drops the impossible ones, so correctness depends on that, and time grows with the extra pairs (≈4 ms per pair:
   400 hexagons 9 s, ~10 000 n-gons ≈ 4 min).
3. UI-bound: floating dialog, Editable Poly at face level with a face selection; DLL path tied to the Max install folder.
4. Works on the scene object; the plan's "export copy" is not in the source.
5. Minor: unpaired re-enable calls after the run (`GeoAGR.ms:51300-51301`); RMB "check" prints added faces as
   "not triangulated" (`GeoAGR.ms:51346`).

Not run: CTRL ("normal") and SHIFT paths (outside this row).

## Recommendation
`take_fix` (plan says `take`). Keep the method; fix scale-independence and leftover reporting before 0.8.

## Requirements the tool must meet
- NPM-2.3-11, VPM-2.3-17 (reg 2.3.11 / 2.3.17, `docs/domain/requirements-2026.md:60`, `:161`): all geometry
  triangulated before FBX export.
- Plan mode `copy`: operate on the export copy, never on the source scene.

## Minimal acceptance test (proposal)
Synthetic scene in metres, run the tool on a copy, then read the copy back:
1. Octagons r = 1 km, 1 m, 1 mm, **0.1 mm**; concave U at 6 m and **0.6 mm**; 12-vertex comb; non-planar hexagon;
   cylinder 24 sides with UVs, SG and 3 material IDs; node rotated 90° about X and moved.
2. Pass when: zero faces with degree > 3 on the copy; vertex count unchanged; per-face area sum unchanged within 1e-6
   relative for planar faces; no crossing edges inside any original face; UV area, material IDs and smoothing groups
   unchanged; source scene unchanged; the tool reports 0 leftovers (or lists them).
3. Timing: 400 hexagons under 2 s.
