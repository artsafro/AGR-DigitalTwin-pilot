# ground-terrain - when to use which variant

All rows: vatutino-ground, input adapter v4 (sha256 3b6b433d...), reference = v014 VPM FBX (R1 = 0 m zero line).
- Delivery Ground with layers, kerbs, stairs and gates: builder at cell 4 m only; it rebuilds v014 exactly (dz 0 m, 46343 tris, 3/3 holes, R2 vs R1) in 96.96 s; at 2 m and 8 m its own gates refuse (no mesh, no row).
- Fast relief-only surface that keeps the plan edges: cdt; boundary within +2.184 m of 902.5 m and 3/3 holes at every cell (R3, R5, R7), built in 2.2-2.9 s.
- cdt at 2 m for the closest relief: dz p95 0.0129 m with 10290 tris (R5) vs 0.0333 m at 4 m (R3) and 0.0692 m at 8 m (R7).
- Do not judge a single-surface variant by dz max: 0.56-1.90 m comes from kerbs and stairs only the builder models (R3-R8 vs R2); read p95.
- bgrid only when grid-stepped edges are acceptable: boundary +209.5 m at 4 m (R4), +213.5 m at 2 m (R6), 828 / 483 reference samples uncovered.
- Never bgrid at 8 m: it loses 2 of 3 footprint holes and adds 985.5 m of boundary (R8).
- Lowest triangle count for a preview: bgrid 2118 tris at 4 m (R4) vs cdt 3424 (R3), but dz p95 doubles (0.068 vs 0.0333 m).
- Clean xView overlaps: bgrid has 0 / 0 vertices / faces (R4, R6, R8); cdt keeps 10-16 near-coincident plan vertices (R3, R5, R7).
