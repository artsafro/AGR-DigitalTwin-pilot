# POLY63-B stage 2 - #1619 polygon, site 63 tower B: windows + capsules + AC baskets

Stage 2 on the stage-1 body v007 (PR #1661; Artem 2026-11-20 accepted it from the sheet). The body is not rebuilt or
edited: it is appended unchanged from `C:/x/review-63B/63B_Stage1_v007.blend`; read back from the stage-2 FBX its
14 758 vertices match the v007 dump within 1.9e-6 m. Band +4.65..+51.90. Review draft, not accepted VPM.

Route as 63A/63C: shared POLY63-A helpers (`stage2_plan.py`, `stage2_blend.py`) and the owner cores (openings_core,
windowgen_core, winplace_core, capsule_core); 63B deltas are listed in `hooks/stage2_63b.py`.

Decisions of Artem 2026-11-20 (card t_1e388df4):
1. Capsules [D205] 1.0 m deep; only the 8 inner-corner capsules that cross at 1.0 m (openings 210/211, 226/227 at
   +24.45, 373/374, 389/390 at +40.20; body ids 27, 28, 57, 58, 209, 210, 226, 227) are 0.9 m.
2. The 12 AC baskets entirely inside the band: low-poly closed box (6 quads) on the Revit bounding box.
3. Openings narrower than their Revit window are expected (the window is fitted into the accepted opening).

| v001 (read back from FBX) | value |
|---|---|
| openings / Revit types | 491 ok, 0 without a Revit type (rule 1a); 8 types; 13 bent rims (frame on the chord) |
| objects | 491 frames + 491 glass + 491 capsules + 12 baskets + `SM_Body_Main` |
| faces | 51 943, 100 % quads, 0 triangles, 0 n-gons, 0 thin |
| capsules | 491, 0 crossing, 0 failing `check_capsule`; 8 at 0.9 m |
| baskets | 12 of 34 built; 3 (06, 09, 12) overlap the body by 0.03-0.05 m (Revit bbox vs v007) |
| #1616 score | 84.54 (body v007 alone 84.32) |

Evidence: `G:/Мой диск/AGR-evidence/1619-body-training/stage2-63B/v001/` (+ `SHA256SUMS.txt`, copy in
`stage2_v001_SHA256SUMS.txt`); review copy `C:/x/review-63B/63B_Stage2_v001.blend` / `.fbx`.

Reproduce (E = `C:/x/ev_s2_63b`, B = Blender 5.1, A = `jobs/POLY63-A/stage2-1619/hooks`, C = `jobs/POLY63-C/hooks`):

```
uv run python hooks/stage2_63b.py E/dump_v007/SM_Body_Main.npz C:/x/ev_poly63b7/b63B_src.npz E/stage2_v001.json
B -b --factory-startup --python A/stage2_blend.py -- E/stage2_v001.json C:/x/review-63B/63B_Stage1_v007.blend E/v001 63B_Stage2_v001 --dump E/dump_v007/SM_Body_Main.npz
B -b E/v001/63B_Stage2_v001.blend --python C/stage2_views.py -- E/views_v001b 255 100
uv run python hooks/sheet_63b.py E/views_v001b E/stage2_v001.json E/v001/63B_Stage2_v001.readback.json E/sheet/63B_Stage2_v001_sheet_r2.png --opening 255
uv run python tools/qa/mesh_quality_score.py E/v001/63B_Stage2_v001.fbx --out E/score1616_v001.json
```
