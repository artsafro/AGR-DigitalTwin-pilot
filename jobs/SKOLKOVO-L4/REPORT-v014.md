# Skolkovo L4 — v014: mast hub-node rebuild (variant 1), FBX only

**`passed=false`. Masts: 3/5 pass the kernel, 2/5 have one coplanar fold left. KNS K1 and the rest of
the L4 chain are not done. No export, no PR.** Revit was not used.

## Decision applied

Artem 2026-10-21 22:57: masts variant 1 (rebuild only the node where the 8 legs converge; faces hidden
inside other legs may be deleted; outside <=2 mm; +1-3k tris from the reserve allowed). KNS: K1 (proxies
from contours <=2 cm, no quad/texel gates for details <0.2 m, target 10k). Gate 1 v010 / PartsList
`fca5b23b…` unchanged.

## Recipe (job-only scripts `tmp/skolkovo-l4-v014/`, copies + SHA256SUMS on Drive `353-skolkovo-l4/evidence-v014/`)

1. `prep.py` — split the source buffer (`tmp/skolkovo-l4-v006/mast-system/object-<row>.bin`, SHA in
   `evidence-v014/mast-hub-v014.json` via v013) into rods (unchanged) and base members: vertical tube,
   8 legs, 198-tri hub cap fan (non-manifold, coplanar with the leg tops).
2. `hub_union_blender.py` — Blender 5.1: each member closed by planar hole fill (tube bottom, leg tops,
   one missing triangle per leg at ~0.45 m), boolean UNION with the MANIFOLD solver. The EXACT solver was
   tried first on 3628 and rejected (125 border / 613 non-manifold edges). Manifold: 0 border, 12-23
   non-manifold edges, all at the node.
3. `weld.py` — cluster the union vertices at the BODY-J tolerance (2 mm) and snap each cluster to its
   medoid (an existing union vertex = a point on the source surface); drop collapsed triangles. Fail-closed:
   exits 2 if any duplicate lies outside the node radius (witnessed: 3697/3719 at R=0.15 m → exit 2;
   their node reaches 0.158 m, run with R=0.16 m).
   `weld_cl.py` (repair 2, used for 3697/3719) — the same, but clusters are split by complete linkage so
   no vertex moves more than 2 mm (medoid recipe moved up to 3.93 mm there).
4. `tjunction.py` — the unchanged tip/middle rods had 158-240 border edges: T-junction seams (two seam
   sides with different vertex spacing). Stitched by splitting the border edge at the opposite side's
   vertex; no vertex moved or added (`vertices_not_in_source` 0), so zero deviation. One 3-edge hole left
   by a dropped sliver on 3719 was closed with one triangle. Probe `probe_tjunction.py` 6/6.
5. `deviation_blender.py` — two-sided sampled distance (31 samples/triangle: corners, edge midpoints,
   centroid, 24 random, seed 353014) via Blender BVH. A source sample counts as hidden (deleted on
   purpose) when both offsets ±0.5 mm along its normal are inside member solids.
6. `eval_final.py` — BODY-J (`twinqa count_defects`, tol 0.002) and kernel
   `run_operation(contour_rebuild)` isolated per mast (source mesh → final mesh).

## Results (`evidence-v014/mast-hub-v014.json`)

| Mast | tris src → final | BODY-J (limit 100) | out→src max / p95 mm | src→out max / p95 mm | kernel |
|---|---|---:|---|---|---|
| 3628 | 11098 → 10998 | 22 | 0.344 / 0.008 | 0.435 / 0.008 | **applied** (0/0/0/0) |
| 3651 | 11940 → 11884 | 31 | 0.446 / 0.004 | 0.533 / 0.004 | **applied** |
| 3674 | 11940 → 11886 | 31 | 0.760 / 0.004 | 0.871 / 0.004 | **applied** |
| 3697 | 10114 → 10120 | 61 | 0.317 / 0.004 | 0.383 / 0.004 | rollback: no_close_overlap 2 |
| 3719 | 10138 → 10068 | 54 | 0.426 / 0.004 | 0.613 / 0.004 | rollback: no_close_overlap 2 |

- Total 55,230 → 54,956 tris: under the mast allocation; the 3,000 reserve is untouched.
- Before (v011/v013): BODY-J 1292-1307 per mast; kernel on 3628: 250 open borders, 5448 overlaps.
- Base meshes are closed 2-manifold (every edge used twice) on all five.
- BODY-J left: tip duplicate vertices 0-6 and 10-13 rod/base contact intersections (both unchanged
  source), plus 21-44 sub-2 mm vertex pairs left by the complete-linkage weld on 3697/3719.
- 13.4-14.0k samples per mast classified hidden and removed (~4 %); samples over 2 mm: 0 both ways.
- Outside the node is NOT byte-identical everywhere: 16 tris per mast at the closed one-triangle leg
  holes (~0.45 m), 38 tube triangles retriangulated by Manifold on 3651/3674, and on 3697/3719 the node
  reaches ~0.2 m. Deviation of all of them is inside the numbers above.
- Rejected, kept as evidence: EXACT union (3628); medoid weld on 3697/3719 (moves 3.93 mm, kernel
  no_close_overlap 4/3, logs `final36{97,19}-recipeA-rejected.log`).

## Open: the fold on 3697/3719 (in scope, repair 3 not yet tried)

Both masts: one long sliver (69 mm², from the hub point (0.025, 0, 0) to z −0.055 m relative to the hub,
normal (0.99, 0.13, 0)) overlaps two small coplanar triangles on the same tube facet — a fold left by the
weld. Planned repair 3 (different approach): collect the coplanar triangles of that facet inside the node,
take their 2D union outline and re-triangulate it (constrained, no new vertices), then BODY-J, deviation
and kernel again. Not a user question.

## L5 timing for this run (wall clock, 2026-10-21/22)

Context + plan 10 min; member split + union + weld 15 min; deviation 5 min; kernel 10 min per batch of
five (562-613 s per mast, parallel) ×2; rod stitch + repair 2 10 min; report/evidence 15 min. Total ≈ 1 h 45 min.

## Next steps

1. Repair 3 for the fold on 3697/3719 (above); rerun eval_final + deviation.
2. KNS K1: per-type proxies from source contours, silhouette <=0.02 m, target 10,000 (108 objects,
   source 90,168 tris; types in MAST-HUB-VARIANTS-v013.md).
3. Then: 49 parts / joints on the kernel, versioned export + FBX readback, comparison with the delivered
   final and the album, review tool, SINTEZ, suite via suite_slot.py, PR, dt-reviewer.
