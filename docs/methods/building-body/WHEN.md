# building-body - when to use which variant

From [RESULTS.md](RESULTS.md) (3 objects x 3 variants + the source-as-is reference; Blender 5.1.2, 3ds Max 2026.3; commit 7fd210b1). Contours are measured from the source mesh (no DWG in the benchmark set), so these rules compare tools on the same input, not drawings against models.

- Keep the supplied mesh (source-as-is or max-pymxs-cleanup) when it exists: deviation from the source 0.0001 m max (R1, R4, R5, R8, R9, R12) against 0.10-6.34 m for any from-contour rebuild (R6, R7, R10, R11).
- Use max-pymxs-cleanup to close open shells of a supplied body: closed-shell share 3.3 % -> 98.5 % on KPP1 (R1 -> R4), 24.6 % -> 97.3 % on TOW02 (R9 -> R12), 0 % -> 100 % on AC08 (R5 -> R8).
- Check xView after max-pymxs-cleanup: Cap Holes adds coincident caps, overlapping faces 0 -> 1 329 on KPP1 (R1 -> R4) and 147 -> 3 613 on TOW02 (R9 -> R12); it also adds triangles, 70 678 -> 82 117 on TOW02 (R12).
- Max cost is the start, not the work: 0.05-0.32 s of clean-up per object (R4, R8, R12) behind ~39 s of 3dsmaxbatch start per call (docs/evidence/727-building-body/*-max-pymxs-cleanup.log.txt).
- Use a from-contour rebuild only on a simple prismatic body: AC08 stays at 0.103 m max / 0.092 m p95 with 40-44 triangles (R6, R7); TOW02 reaches 6.34 m max / 0.94 m p95 (R10, R11), KPP1 0.75 m / 0.275 m (R2, R3).
- Prefer blender-gn-union over kernel-prisms when a single clean shell matters on a simple body: 0 overlapping faces and 1 closed shell on AC08 (R7) where stacked kernel prisms give 19 overlapping faces (R6).
- Neither contour variant is xView-clean on many bands: kernel-prisms 4 921 / 10 751 overlapping faces (R2, R10), blender-gn-union 1 946 / 3 533 (R3, R11); the source has 0 / 147 (R1, R9).
- Use kernel-prisms when triangles and time are the limit: TOW02 13 552 triangles in 0.20 s (R10) against 39 446 in 23.57 s for the GN boolean union (R11); KPP1 3 896 in 0.08 s against 7 539 in 4.30 s (R2, R3).
- Budget [D010] does not decide on this set: the largest row is 82 117 of 150 000 triangles, 54.7 % (R12).
- No variant makes UCX: contour rebuilds drop the source's UCX pieces (KPP1 33 -> 0, R1 -> R2, R3); max-pymxs-cleanup keeps them (33/33 closed convex, R4).
