# KPP1 #1255 — MSK-77 placement by fit to the customer's NPM: STOP (fit ambiguous)

Agent: dt-worker (Hermes card t_cd0d8792), 2026-11-12. Base: origin/main 5a9606d5.

User decision (Artem 2026-11-12, card comment): place KPP1 by fitting it to the existing MSK-77 NPM
`0607_77_05_0009005_117_02` (Telegram) and use the zero mark 171.050 (Revit); report the fit residuals;
**if the fit is ambiguous (residual > 0.05 m or no unique match), stop and say so.** The fit is ambiguous on
both counts, so no GeoJSON was written and the R1 package was not placed.

## Inputs (read-only)

| File | sha256 |
|---|---|
| customer NPM `0607_77_05_0009005_117_02.zip` (Telegram Desktop, 2026-10-27 inner FBX) | `219524eae5acec4f58fbf…` (zip), `fc08774a30058de2b2da296306946b1b60b65612ca73b7af563218a0c7b50b51` (fbx) |
| our NPM `0000_Kpp_1_01.fbx` r1-v002 (#1230, `G:/Мой диск/AGR-evidence/1230-kpp1-r1/r1-v002/`) | `9604a8f14f064495…` (matches `../rerun-1230/evidence-r1-v002-SHA256SUMS.txt`) |

## Commands

```
blender --background --factory-startup --python jobs/KPP1/site-1255/dump_vertices.py -- <fbx> <npz> <json>
uv run python jobs/KPP1/site-1255/fit_msk77.py dump-tg02.npz dump-npm.npz 171.05 fit-npm.json
```

Method (`fit_msk77.py` docstring): plan sections at +1.5 and +2.3 m above 0.000 (customer: 172.55 / 173.35),
2 cm raster, 1.5 m closing (door gaps), outer contour only (their NPM is an outer shell); 2D rigid ICP from the
4 axis-aligned starts; vertical offset fixed at 171.050, not fitted.

## Result (`fit-npm-r1-v002.json`)

| Solution | theta | origin (Blender X = MSK y, Y = MSK x) | median | p90 | max | share <= 0.05 m |
|---|---|---|---|---|---|---|
| best | -6.053° | (8056.144, -9581.270) | **0.099 m** | 0.262 m | 0.721 m | 25 % |
| second (180° turn) | 173.889° | (8053.885, -9580.830) | 0.122 m | 0.566 m | — | — |
| other two starts | 84.9° | | 3.39 m | 11.8 m | | |

- Residual 0.099 m > 0.05 m, and the 180°-turned solution is within 1.23x of the best -> **not unique**.
- Why: the two models differ in shape, not only in position (best fit, our frame, per 2 m strip): their main
  south face -5.73..-5.76 vs ours -5.60..-5.70; north +6.01..+6.09 vs +5.98; east wall +12.73..+12.92 vs +12.58;
  east porch +14.79..+14.90 vs +15.44 (0.55-0.65 m shorter). Min-area rectangles of the sections: theirs
  29.98 x 13.08 m, ours 30.44 x 13.08 m. A mirrored ours fits no better (0.119 m).
- Heights: their top 179.815 vs ours 8.650 + 171.050 = 179.700 (0.115 m); their floor vertices peak at 171.06.

Evidence (rule 57): `G:/Мой диск/AGR-evidence/1255-kpp1-msk77/` (overlay-1.5.png, contours, fit/dump JSON),
`SHA256SUMS.txt` 6/6 OK.

## Not done (waits for the user)

GeoJSON, placement of the R1 VPM/NPM, validate_package V001/V011/V013/V014, D-row. `passed` stays false.
