# UCX etalon analysis: how collisions were built in delivered projects (#165)

Research note for spec #149 and [UCX sheet](../domain/areas/ucx.md). Measurement only:
no delivery was changed, no shared UCX tool is built here, no conflict is decided. The
user said on 2026-10-15 that KPP1/PSU275 hulls are not ideal etalons; this note measures
three delivered FBX files he named and compares them with KPP1/PSU275.

## Inputs (copies, hashes)

Originals were copied to `C:/x/t_46c46a77/in/` and only the copies were read. SHA-256 of
each original before and after the run is identical (checked again after the audit).
Nothing from these paths is committed.

| File | Origin | Bytes | SHA-256 (12) |
|---|---|---|---|
| `SM_BolshoyBulvar_64.fbx` | user, NTR/14_Skolkovo/pravki_15.09/HP/OKC | 2 566 304 | `aec28a9bb8b0` |
| `SM_MashiPoryvaevoj_34_001.fbx` | user, NTR/28_Mashi_Parivaevoy/maps | 2 199 184 | `52d16fb84a89` |
| `1113_77_17_0130206_5812_01.fbx` | user, A101/47_4BK_new/Pravki_IT2 | 5 213 424 | `0c6a32e2c72d` |
| `SM_Kpp_1.fbx` | KPP1 `outputs/package-vpm-v007` (local, upstream worktree) | 555 228 | `5b0869a1f989` |
| `SM_Psu_1.fbx` | PSU275 `outputs/delivery-v003/check` (local, upstream worktree) | 1 603 996 | `73e5090c66b1` |

## Method

Blender 5.1.2, headless factory startup:

```
blender --background --factory-startup --python-exit-code 1 --python tools/blender/fbx_readback.py -- <copy.fbx> <rb.json>
blender --background --factory-startup --python-exit-code 1 --python tools/blender/ucx_audit.py   -- <copy.fbx> <audit.json> 20000
```

`tools/blender/ucx_audit.py` (new, read-only) uses the pure geometry in
`src/twinqa/geometry/ucx_audit.py` (probed by `tests/qa/test_ucx_audit.py`):

- **Hull type**: welded vertices; `closed` = every edge in two triangles; `convex` = all
  vertices on one side of every face plane (0.1 mm); `box_aabb` / `box_oriented` = 8 vertices
  and three mutually orthogonal face directions; `convex` = any other closed convex piece;
  `custom` = open or non-convex. Face signature h-v-t = number of horizontal, vertical and
  tilted face directions (a box is 1-2-0).
- **Intersections and gaps** for every pair whose bounding boxes are within 10 cm: SAT over
  face normals and edge crosses (penetration depth, nesting counts as overlap), exact surface
  distance (vertex-triangle both ways + edge-edge). Classes against the project band
  2 mm - 1 cm inclusive ([D098], C15; reg p.36 §13.4): overlap (> 0.2 mm), touch (< 0.2 mm),
  below band (0.2-2 mm), in band (2-10 mm, 0.01 mm float32 tolerance), wide (10-100 mm).
- **Coverage of Main**: 20 000 area-weighted points on the Main surface (seed 165); a point
  inside a UCX piece has deviation 0, else the distance to the nearest UCX surface. Shares
  within 0.3 m and 1 m are the reg p.36 §13.5 tolerances; height bands use world Z (project
  zero, [D018]); the 0-6 m band only approximates the pedestrian zone. Indicative reverse
  metric: exposed UCX surface (not within 2 cm of another piece) to the Main surface.
- **Naming**: `UCX_SM_{Address}_{Main|Ground}_{001..999}` (reg p.34 §4.2), address taken from
  the Main object, duplicates, contiguous 001..N. Budget: [D012] formula, `n` excludes UCX.

## Comparison table (measured)

| Metric | Skolkovo `SM_BolshoyBulvar_64` | Mashi `SM_MashiPoryvaevoj_34_001` | A101 `1113_..._01` | KPP1 `SM_Kpp_1` | PSU275 `SM_Psu_1` |
|---|---|---|---|---|---|
| Model tris excl. UCX | 56 368 | 47 275 | 143 513 (2 Main) | 24 374 | 78 552 |
| UCX pieces | **215** | **139** | **0** | 33 | 23 |
| UCX tris / [D012] limit | 2 580 / 2 819 (91.5 %) | 1 692 / 15 000 (11.3 %) | 0 / 7 176 | 396 / 15 000 (2.6 %) | 276 / 3 928 (7.0 %) |
| Tris per piece | 12 x 215 | 12 x 135; 8, 16, 20, 28 x 1 | - | 12 x 33 | 12 x 23 |
| Hull type box_aabb / box_oriented / convex / custom | 0 / 194 / 21 / 0 | 0 / 54 / 85 / 0 | - | 31 / 0 / 2 / 0 | 23 / 0 / 0 / 0 |
| Pieces with tilted faces | 6 | 26 | - | 2 (stair flights) | 0 |
| Distinct piece bottom / top levels | 10 / 17 | 21 / 32 | - | 10 / 9 | 3 / 13 |
| Smallest piece dimension < 0.3 m | 5 | 9 | - | 0 | 0 |
| Neighbour pairs (<= 10 cm) | 550 | 484 | - | 49 | 28 |
| Overlaps (max penetration) | **0** | **8 (260 mm)** | - | 0 | 0 |
| Touching (< 0.2 mm) | 0 | 0 | - | 0 | 0 |
| Gap min / median, mm | 0.65 / 6.0 | 1.18 / 9.0 | - | 2.0 / 2.0 | 2.0 / 2.0 |
| Gaps below band / in band 2-10 / wide 10-100 mm | 2 / 483 / 65 | 1 / 269 / 206 | - | 0 / 48 / 1 | 0 / 28 / 0 |
| Main surface m² | 13 028 | 21 161 | 12 152 + 2 121 | 1 936 | 36 570 |
| Main inside UCX | 75.8 % | 97.5 % | 0 % | 84.1 % | 36.5 % |
| Main within 0.3 m / 1 m | **98.9 % / 99.8 %** | **99.6 % / 99.8 %** | 0 / 0 | 93.8 % / 99.4 % | 96.1 % / 97.3 % |
| Main max deviation | 6.03 m | 4.97 m | - | 1.24 m | 2.77 m |
| Z 0-6 m within 0.3 m | 98.9 % | 99.6 % | - | 97.8 % | 93.8 % |
| Ground target / Ground UCX | none / 0 | none / 0 | none / 0 | none / 0 | none / 0 |
| Names mask OK, contiguous 001..N | 215/215, yes | 139/139, yes | - | 33/33, yes | 23/23, yes |
| Material slots / UV on UCX | 0 / 0 | 0 / 0 | - | 0 / 0 | 0 / 0 |
| Transforms (scale 1, rotation 0) | all | all | - | all | all |
| Exposed UCX within 0.3 m of Main (indicative) | 50.3 % (p95 8.6 m) | 46.8 % (p95 10.1 m) | - | 80.5 % (p95 3.5 m) | 52.4 % (p95 25.6 m) |

Full numbers: [`ucx-etalon-audit-2026-10-15.json`](ucx-etalon-audit-2026-10-15.json)
(audit JSON without the per-piece list and local paths).

## Findings per file

**Skolkovo, `SM_BolshoyBulvar_64`.** 215 pieces, every one an 8-vertex / 12-triangle
hexahedron: 194 boxes oriented to the facade (not to world axes) and 21 parallelepipeds or
trapezoid prisms over non-rectangular plan quads, 6 with tilted faces. Built in height
slices: 18 pieces start at -2.48 (basement), 46 at 0.08 (body, p90 height 12.26 m), and
140 roof-level pieces start at 12.34 (82) or 13.31 (58) with tops up to 17.59 (parapets,
roof structures; 5 pieces thinner than 30 cm). 0 overlaps, 0 touches, gaps 0.65-100 mm, median
6 mm; 2 pairs below the 2 mm band of [D098] (min 0.65 mm). Coverage is the best of the OKS set: 98.9 % of the Main surface
within 0.3 m, 99.8 % within 1 m. It uses 91.5 % of the [D012] budget: the piece count is
budget-bound.

**Mashi, `SM_MashiPoryvaevoj_34_001`.** 139 pieces: a large five-sided core prism
(42 x 51 x 38.8 m, 10 vertices, 16 triangles) and facade pieces around it: 45 vertical
prisms over trapezoid plan quads (signature 1-4-0, pilasters and bays 22.88 m tall from
10.81), 54 oriented boxes, 26 pieces with tilted faces. 21 bottom and 32 top levels. Best
coverage (99.6 % / 99.8 %), but **8 intersecting pairs**: six podium/pilaster stacks
overlap by 43-48 mm in Z (pilasters start at 10.81, podium pieces end at 10.88), piece 004
x 008 by 2.3 mm, roof slab 106 x roof element 110 by 260 mm. These violate reg p.36 §13.4
("must not intersect") whatever the acceptance history of the delivery was.

**A101, `1113_77_17_0130206_5812_01`.** No UCX: the file holds
`SM_Kvartal_191_ZU_1_007_Main`, `..._007_MainGlass`, `..._008_Main` (143 513 tris) in
absolute coordinates (X about -1 170, Y about -14 200). The four `UCX` byte matches in the
raw FBX are inside compressed binary arrays, not names. Its file name follows the NPM
pattern, and NPM has no UCX (npm-vpm.md). It cannot serve as a UCX etalon.

**KPP1 / PSU275 (our builds).** Axis-aligned boxes only (KPP1 2 sloped stair slabs),
fixed 2 mm gap everywhere, 0 overlaps. KPP1 under-covers the plinth zone (z < 0: 69.9 %
within 0.3 m) and has 93.8 % within 0.3 m overall. PSU275 covers 97.3 % within 1 m with a
2.77 m maximum deviation, and its filled parapet wells leave collision far from the Main
surface (exposed UCX p95 25.6 m): one box per mass is too coarse for §13.5.

## How the delivered collisions were built

1. Primitive: a closed convex hexahedron with 12 triangles (8 vertices) in 350 of 354
   delivered pieces; 0 open or non-convex pieces. Larger hulls appear only for a core
   (Mashi 020: 16 triangles).
2. Orientation follows the facade: 0 axis-aligned boxes in either delivery; non-orthogonal
   plan corners become trapezoid / parallelogram prisms instead of overlapping boxes.
3. Decomposition by plan blocks and height slices (10-21 distinct bottom levels): body
   blocks, then roof-level parapets and structures as separate thin pieces, basement layer.
4. Gaps are small but not fixed: 752 of 1 034 neighbour pairs lie in the [D098] band
   2-10 mm (median 6 / 9 mm), 3 pairs below 2 mm (0.65 and 1.18 mm minimum), none below
   0.2 mm. Our fixed 2 mm sits on the lower edge of the same band.
5. Tilted faces are rare (6 and 26 pieces): sloped or chamfered parts, not the default.
6. Density: 16.5 (Skolkovo) and 6.6 (Mashi) pieces per 1 000 m² of Main surface, against
   17.0 for KPP1 and 0.6 for PSU275; delivered coverage within 0.3 m is 98.9-99.6 %.
7. Neither delivery contains a Ground target or Ground UCX; Ground collision ships
   elsewhere or was not required, so there is still no Ground etalon (T-UCX-4).

## Recommended etalon set

| Role | File | Why |
|---|---|---|
| Primary OKS etalon | Skolkovo `SM_BolshoyBulvar_64` | 0 overlaps, all pieces convex 12-tri, gaps 0.65-100 mm, 98.9 % / 99.8 % coverage, names clean; shows the budget-bound case (91.5 %) |
| Construction-style etalon + negative intersection fixture | Mashi `SM_MashiPoryvaevoj_34_001` | core prism + facade prisms, best coverage, but 8 known overlaps (max 260 mm) that a checker must report |
| Small regression fixture | KPP1 `SM_Kpp_1` | simple AABB build, fixed 2 mm gap, known 33 pieces; not a shape etalon |
| Coverage counterexample | PSU275 `SM_Psu_1` | 97.3 % within 1 m, 2.77 m max deviation, filled wells: coarse one-box-per-mass build |
| Not usable | A101 `1113_..._01` | no UCX (NPM-type file); a VPM file of the same object is needed |

The binaries stay outside the repository; a benchmark entry would reference them by
path and SHA-256 (`benchmark/` change is a separate, reviewed card).

## Construction rules proposed for the shared UCX tool

Derived from the measurements above; they are proposals for #149, not regulation and not
user decisions. Regulation limits stay those of the [UCX sheet](../domain/areas/ucx.md).

1. Piece = convex vertical prism over a convex plan polygon between two levels, default a
   quad (8 vertices, 12 triangles); tilted faces only where the shape is sloped (stairs as
   truncated pyramids, R14; sloped roofs).
2. Orient pieces to the facade segments; never approximate a non-orthogonal corner with
   overlapping axis-aligned boxes.
3. Split by plan blocks and by height levels (basement, body, roof-level parapets and
   structures); pieces thinner than 5 cm are not built (R04).
4. Target gap 3-6 mm, which keeps float32 read-back safely inside the [D098] band
   2 mm - 1 cm; measure every neighbour pair and report gaps outside the band, touches and
   any overlap, including a nested piece (R09/R10).
5. Coverage benchmark from the deliveries: Main surface >= 98.5 % within 0.3 m and
   >= 99.7 % within 1 m; maximum deviations by zone follow R11-R13.
6. Check the [D012] budget before export; the primary etalon shows the piece count can hit
   it (2 580 / 2 819).
7. Names `UCX_SM_{Address}_{Main|Ground}_{NNN}` contiguous from 001, no material slots, no
   UV, identity transforms, pivot free (R07, R08, R16, R17): all four UCX files comply.
8. Ground UCX: no delivered example; keep it a separate card with its own etalon.

## Limitations and open items

- Coverage is sampled (20 000 points per Main); the shares carry about +/-0.3 % sampling
  noise. The 0-6 m band is a proxy for the pedestrian zone, not its definition (R12).
- The exposed-UCX reverse metric counts bottoms and joints wider than 2 cm as exposed; it
  is indicative only and not used for the recommendations.
- Acceptance status of the two NTR deliveries with the customer is not known here; the
  Mashi overlaps are measured, not judged against what the customer accepted.
- The A101 input has no UCX; the user may name a VPM file of that object instead.
