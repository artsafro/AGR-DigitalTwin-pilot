# Lab experiment L01: `ucx.triangulate` (AGR Tools 0.8)

Source checked: GeoAGR 13.64 "UCX Triangulate" (`GeoAGR.ms:60285` button, handler `GeoAGR.ms:62890-62905`). No GeoAGR
code here (#853); job script and raw output are in the private GeoAGR repository, branch `lab-exp/L01`,
`work/lab-experiments/ucx.triangulate/`.

Run: 3ds Max 2024.2 via the AGR Lab runner (3dsmaxbatch), synthetic UCX-like pieces, metres.
Job: `20261104-225353-1628515a`.

## What the source does (measured)
- For each selected Editable Poly: unhide all, select all vertices, Max Connect. That triangulates boxes, n-gon prisms
  (8-, 64-gon caps), outlines with collinear vertices (no zero-area triangles) and concave L outlines (no flips).
- Selection is restored after a multi-object run.

## Defects
1. **Convexity can break.** On a box with one raised top corner (non-planar quad) the chosen diagonal made the piece
   non-convex in one of two cases. The source never checks convexity (reg 2.13.1).
2. Silently skips Box primitives, Editable Mesh and Editable Poly with modifiers; no list of skipped pieces. This is a
   plausible (untested) path to the TEC26 SINTEZ 2.3.17 failure.
3. Unhides hidden faces/vertices as a side effect.
4. No undo record for a script call; works on the scene object, not a copy; drives the Modify panel per object
   (~0.5 s per piece).
5. The plan's "checks convexity afterwards" is not in the source.

## Recommendation
`take_fix` (plan says `take`): keep the simple triangulation, add convexity-aware diagonal choice and a post-check.

## Requirements the tool must meet
- VPM-2.3-17 (reg 2.3.17, `docs/domain/requirements-2026.md:161`): triangulated before FBX export.
- VPM-2.13-1.a (reg 2.13.1, `requirements-2026.md:236`): each collision piece convex, closed, no holes, no material slots.
- Plan mode `copy`.

## Minimal acceptance test (proposal)
Synthetic scene in metres, run on the export copy:
1. Box; octagonal prism; square prism with mid-edge vertices; box with top corner raised 0.6 m (both corners, two
   pieces); 64-gon prism; one Box primitive, one Editable Mesh and one Editable Poly with an Edit Poly modifier; one piece
   with two hidden faces.
2. Pass when: every UCX on the copy has only triangles; every piece passes a convexity test (all vertices behind every
   face plane, tolerance 1e-4 m) and is closed; no zero-area triangles; vertex count unchanged; non-Editable-Poly pieces
   are either converted or listed; hidden state of the source unchanged; source scene unchanged.
