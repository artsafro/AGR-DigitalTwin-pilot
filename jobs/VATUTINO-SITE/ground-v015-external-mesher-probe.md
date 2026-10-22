# Ground v015 option (b): external mesher per patch — measured, does not meet the gates (NOT_DELIVERY)

Decision followed: Artem 2026-10-22 ("принимаю рекомендации"): try an external open-licence mesher
per patch under the same gates; if it does not give a conforming mesh in budget, record the numbers and
park #371 (option c); #298 stays on Ground v014. Base `49ef72d`; input CPU v009 `master-vpm.json`
(sha256 `59310ac9ffc2a932…`, unchanged). VPM probed first because its gates are the strictest
(edge <= 4 m). Gates unchanged: strict `texel_ready` (aspect <= 8, VPM edge <= 4 m), surface <= 50,000,
NPM <= 180,000 triangle-equivalent, triangles <= 35 % (D157), contours 2.2 mm, relief 10 mm, xView
0.002 / 0.005 m. Numbers are diagnostic (`face_metrics` aspect and `vertex_pairs` OV at 2 mm, the same
primitives the public checks use); no candidate was exported, nothing was published.

Machine-readable: `ground-v015-external-mesher-probe.json`. Scripts, logs, summaries and the v002
mesh: `C:/x/ev_t_eb1c51ca/external-mesher-v001/` and
`G:/Мой диск/AGR-evidence/371-ground-v015-external-mesher-20261022/` (11 files, `SHA256SUMS.txt`
sha256 `b84676fb…1e0fb4`, `sha256sum -c` 11/11 OK on Drive).

## Results (VPM)

| run | mesher / construction | patches | faces | quads / tris | tri share | tri-eq | texel offenders | OV 2 mm | conforming |
|---|---|---|---|---|---|---|---|---|---|
| v014 (ref) | delivered (NPM readback counts; texel offenders = VPM) | — | 46,343 | 0 / 46,343 | 100 % | 46,343 | 22,556 | 0 | yes |
| v009 CPU (ref) | paired fan, VPM master | — | 28,167 | 18,312 / 9,855 | 34.99 % | 46,479 | 11,430 | 0 | yes |
| gmsh v002 | Gmsh 4.15.2 builtin, one Plane Surface per exact-plane patch (10 µm), shared source boundary lines, Frontal-Delaunay-quads + Blossom recombine, point size = min(3.9, longest incident boundary edge) | 18,557 | **64,626** (>50k) | 38,496 / 26,130 | **40.4 %** (>35 %) | 103,122 | **13,991** | **109** | yes: boundary 9,776.587 m = source, 3 nonmanifold edges |
| gmsh v004 | as v002, point size = min(3.9, 6 x shortest incident edge) | 18,557 | **158,148** | 114,444 / 43,704 | 27.6 % | **272,592** (>180k) | **15,777** | **987** | yes: boundary = source, 0 nonmanifold |
| gmsh v003 | patches merged within 4 mm of a root plane (relief budget), interior nodes lifted to the TIN | 4,637 | — | — | — | — | — | — | Gmsh did not finish 2-D meshing of the non-planar plane surfaces in 1,800 s (killed by timeout; same symptom as Codex's discrete-topology route) |
| QuadriFlow v001 | Blender 5.1.2 `quadriflow_remesh` per texture slot, preserve boundary + sharp, target 0.9 x source faces | 12 slot objects | 22,770 | 22,770 / 0 | 0 % | 45,540 | 196 quads > 8 | — | **no**: 10/12 slots move source boundary vertices by > 2.2 mm (max **125.0 m**, TileDark collapsed to 74 faces); slots are remeshed independently, so slot borders cannot conform |

Where the gmsh v002 texel offenders sit (corners, corners on source vertices -> count): quads with 2
source corners 6,272; triangles with 1 source corner 4,634; triangles with 2 source corners 1,831;
triangles of 3 source corners 635; quads of 4 source corners 583. Aspect p50/p90/p99 = 20.7 / 65 / 566.
They are the narrow bands (curbs, tile joints, tongues down to 1.12 mm) where an isotropic frontal
mesher places elements longer than 8x the band width; CurbGarden 6,939 and TileLight 3,465 of 13,991.
Refining the size field (v004) does not remove them (15,777) and breaks the budget.

## Why the route stops here

1. The exact-plane patch structure is a TIN: 10,802 of 18,557 patches are single triangles and 5,255
   two triangles. A per-patch mesher keeps each single-triangle patch a triangle (or splits it into
   3 quads and grows the count), so the triangle share stays above 35 % at budget (v002) and the
   budget breaks when it falls (v004).
2. Strict texel needs anisotropic, contour-following strips in the narrow bands with matching node
   counts across shared edges (transition elements, census section 2). Gmsh's quad recombination is
   isotropic; QuadriFlow is a global field-aligned remesher that does not keep material contours.
3. Merging patches by the relief tolerance (the only way to cut the TIN count) produced non-planar
   surfaces Gmsh did not mesh in bounded time.

So option (b) does not give a conforming mesh that meets strict texel, 50k/180k and 35 % at the
same time. Per the decision, **#371 is parked (option c); #298 stays on Ground v014**. Nothing in this
probe changes v014, D150, D157, D169 or any threshold.

## What a later restart would need (not started)

A dedicated conforming quad mesher for narrow planar bands: medial-axis/strip decomposition with
count-matching transition templates (1->3, 2->4) and interior apex quads for tongue tips below 7.2 deg
(census section 3), plus relief-aware patch merging with TIN lifting. Gmsh can still serve the wide
regions (v002 shows conforming shared lines work with 18,557 surfaces in ~4 min).
