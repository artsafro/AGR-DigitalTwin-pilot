# POLY63-A stage 2 - #1619 polygon, site 63 tower A: windows + glazing capsules

Stage 2 on the stage-1 body Artem ACCEPTED in Blender (63A v005, 2026-11-18). The body is not rebuilt or edited:
it is appended unchanged from `C:/x/review-63A/63A_Stage1_v005.blend`; read back from the stage-2 FBX its 5 128
vertices match the accepted dump within 3.7e-6 m. Same typical band as stage 1 (+10.15..+47.95, 12 x 3.15 m).
Review draft, not accepted VPM.

Modelling split [D336]: plinth=one_with_body; inset=windows,capsules; texture=panels,sashes; reason=stage 2 of the polygon adds only the window frame grid (frame, mullions, transom as in Revit), glass and capsules, each opening its own objects; sash profiles and panel seams stay texture

| v001 (read back from FBX) | value |
|---|---|
| openings (openings_core, rect) | 432 ok, 0 ambiguous |
| Revit windows in the band / types | 432; 1 Ств 0.80/1.00, 2 Ств 1.51/1.71, 3 Ств 2.30/2.50 |
| frame profile measured from the Revit glass | side 78 mm, bottom 88, head 78, mullion/transom 116, depth 68 |
| objects | 432 frames + 432 glass + 432 capsules, separate, 3 collections + `Body_Stage1` |
| faces | 36 864 stage-2 quads, 0 triangles, 0 n-gons (body 4 560 quads unchanged) |
| frame front on the reveal end | max corner offset 0.0 mm (432/432) |
| capsules | 432 made by `capsule_core.plan`, 0 ambiguous/overlapping, 0 failing `check_capsule` |
| AC baskets | 0 in the band in Revit (17 total: +4.95 x10, +48.2 x4, +69.3 x1, +72.45 x2) - question to Artem |

84 openings (7 per floor) of the accepted body are 4-84 mm narrower/wider than their Revit window (stage-1 contour
snap); the window takes the body opening and its mullions scale (listed in `misfit` of the report).

Evidence: `G:/Мой диск/AGR-evidence/1619-body-training/stage2-63A/` (+ `SHA256SUMS.txt`); review copy
`C:/x/review-63A/63A_Stage2_v001.blend` / `.fbx`.

Reproduce (D = `C:/x/ev_poly63a`, stage-1 inputs; H = `jobs/POLY63-A/stage2-1619/hooks`; B = Blender 5.1):

```
uv run python H/stage2_plan.py D/dump_v005/SM_Body_Main.npz D/a63A_src.npz stage2_v001.json --keys D/keys63.json
B -b --factory-startup --python H/stage2_blend.py -- stage2_v001.json C:/x/review-63A/63A_Stage1_v005.blend v001 63A_Stage2_v001 --dump D/dump_v005/SM_Body_Main.npz
B -b --factory-startup --python H/stage2_sheet.py -- v001/63A_Stage2_v001.blend stage2_v001.json sheet/63A_Stage2_v001_sheet.png
```
