# windows-glazing - when to use which variant

From [RESULTS.md](RESULTS.md) (3 objects x 3 variants + the source-as-is reference, Blender 5.1.2, commit f02b689e; atlas / trim / frame materials sample our generated diffuse PNG, every non-glass source mesh kept); C35 (frames as geometry vs baked under 5 cm) and C25 are open: these rules measure cost, they do not decide them.

- No glazing in the source: every variant returns the source unchanged, 386 triangles, 0 glass objects (AC08 R5 = R6 = R7 = R8); skip the choice.
- Use atlas-planes when the triangle budget (WIN-07, 150 000) is tight: TOW02 70 028 triangles, below the source 70 678 (R11 vs R9); modelled-frames nearly doubles it to 136 690 (R10).
- Do not use atlas-planes for a VPM: it leaves 0 glass objects (R3, R11) where VPM needs one `MainGlass` (WIN-11); modelled-frames and inset-glass-trim keep 1 (R2, R4, R10, R12).
- Do not put modelled-frames on a body that already has frames or reveal faces in the glass plane: xView overlapping faces go 0 -> 1 409 on KPP1 (R1 vs R2) and 147 -> 10 914 on TOW02 (R9 vs R10).
- Use inset-glass-trim as the VPM option on such bodies: 0 overlapping faces on KPP1 (R4) and 103 on TOW02 (R12), with the glass object kept.
- Weld atlas planes and trim rings to the reveal before delivery: both add 96 overlapping vertices on KPP1 (R3, R4; source 0, R1) and 1 274 on TOW02 (R11, R12).
- Use modelled-frames only when a 3D frame is required: frame depth 0.07 m (R2, R10); inset-glass-trim reads 0.0 m (R4, R12), atlas-planes has no frame (R3, R11).
- Triangle cost of the glass-keeping options on many openings: inset-glass-trim adds 9 536 triangles on TOW02 (R12 79 564 vs R11 70 028), modelled-frames 66 662 (R10).
- File size follows the triangles: TOW02 3 186 KB modelled-frames, 1 938 KB inset-glass-trim, 1 712 KB atlas-planes (package incl. the 2048 px generated PNG) (R10, R12, R11).
- Build time does not decide: at most 3.94 s on 1 192 TOW02 openings (R10) and under 0.21 s on 24 KPP1 openings (R2, R3, R4).
- Texel min is set by the body, not the window variant: 40.813 px/m on every KPP1 row (R1-R4), 0.431 on every TOW02 row (R9-R12).
