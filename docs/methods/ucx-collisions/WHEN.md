# ucx-collisions - when to use which variant

From [RESULTS.md](RESULTS.md) (3 objects x 5 variants, Blender 5.1.2, commits 13e4214 / 8b4bf02). No row has
UCX check `pass`: V010 "UCX shape and coverage" is not_run for every variant, so `open` is the best status;
the shares over 0.1 / 0.3 / 1 m are measurements, not the R11-R13 verdict. "Outside" = UCX volume outside the
model envelope (voxel closing 1 m), "uncovered" = envelope volume without UCX.

- Use kernel-boxes for a non-convex building or one with a passage: on KPP1 it is the only variant with 0% UCX outside the envelope (R1) against 85.5-88.5% for every other variant (R3, R4, R5, R16).
- Use kernel-boxes when the triangle budget is tight on a large model: TOW02 3456 / 3534 triangles, no failed check, model -> UCX max 3.5 mm (R11), while slice-prisms fails the budget there (R18).
- Use single-hull for a small near-convex box building: AC08 gets 1 piece, 12 triangles, 0% outside, model -> UCX max 0 (R10); kernel-boxes there leaves 73.6% of the envelope hollow with 7 pieces (R6).
- Do not expect part-boxes or part-hulls to keep parts apart on Revit or rebuilt exports: touching parts chain-merge into the single hull box (KPP1 R3, R4 = R5; AC08 R8, R9 = R10; TOW02 R13, R14 = R15).
- Do not use single-hull on a non-convex building: 88.5% of its volume is outside the KPP1 envelope (R5) and 32.0% on TOW02 (R15), which fills the passages and courtyards the regulation keeps open (ucx.md first row).
- Use slice-prisms only for few levels and a near-convex plan per level: AC08 2 pieces, 0% outside (R17); KPP1 11 pieces but 85.5% outside (R16); TOW02 49 bands exceed the budget, 4832 > 3534 (R18).
- Ignore rows R2, R7, R12: slice-prisms before the 1 cm plan simplification; TOW02 had 48 of 49 pieces non-convex (R12), fixed in R18 (49 of 49 closed convex).
- Build time does not decide: kernel-boxes takes 7.35 s on KPP1 (R1) and 28.63 s on TOW02 (R11), the others stay under 6 s (R14, R16, R18).
- The UCX variant does not change xView, MatID or texel: per object these are equal on every row (KPP1 R1-R5, R16; AC08 R6-R10, R17; TOW02 R11-R15, R18).
