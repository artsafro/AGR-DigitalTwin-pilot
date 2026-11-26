# Fence kit — moskovsky-sosh1200 (NPM, design only)

Status: proposal, nothing built. Machine data: `fence_lines.json` (per-entity vertices clipped to ГПЗУ, МСК-77 m;
gates with points). Source: `C:/x/moskovsky-env/inspect/school.dxf` (read only), ГПЗУ = LWPOLYLINE `2B6`
(22 021.7 m², ring 863.1 m, 30 vertices, no arcs). "Inside" = clipped to ГПЗУ buffered 0.3 m, so a line lying on
the ГПЗУ line counts as inside; "on boundary" = the part within 0.3 m of the ring.

## 1. Fence layers

| layer | linetype | model-space entities | notes |
|---|---|---|---|
| `232_Ог_Внешние_вар2` | FENCELINE2, ltscale 4, width 0.2 | 8 LWPOLYLINE | perimeter (pos 35) |
| `232_Огр_СПОРТ` | FENCELINE2, ltscale 4, width 0.2 | 7 LWPOLYLINE | sport (pos 39) |
| `7--ГП--ОГРАЖДЕНИЕ проектируемое` | ограждение2 | 0 | only inside blocks `Калитка 1.2`, `Ворота 4.5` |
| `ГП_Ограждение` | ограждение2 | 0 | only inside unreferenced legend blocks `Усл забор`, `Усл ворота` |

Unreferenced blocks with fence linework (not inserted, ignored): `33_п.Московский Школа 1200_посадка_8`
(6 polylines, 1 004.9 m; two equal 11544B/C), `Ограждение`, `ограждение спорт`, `A$C4f7ae2fc`. Block `_МАФ`
(the ledger sheet, inserted at 0,0) repeats 95EDF9/95EDFA — not counted twice (model space only).

## 2. Lines (model space; no bulges anywhere, so no arc segmentation is needed)

| handle | layer | closed | verts | total m | inside m | strictly inside m | on boundary m | role | scope |
|---|---|---|---|---|---|---|---|---|---|
| 11544B | perim | no | 6 | 99.78 | 99.78 | 0.40 | 99.78 | on ГПЗУ line, NE | yes |
| 11544C | perim | no | 5 | 413.35 | 413.35 | 126.34 | 413.35 | on ГПЗУ line, W/NW | yes |
| 7D3188 | perim | no | 3 | 165.64 | 11.67 | 11.37 | 0.60 | spur sport corner -> stadium | 11.7 m |
| 7D3189 | perim | no | 2 | 1.70 | 1.70 | 1.70 | 0.30 | link sport N corner -> ГПЗУ line | yes |
| 95EDF9 | perim | no | 7 | 247.55 | 0.30 | 0 | 0.30 | around stadium, outside | no |
| 95EDFA | perim | no | 9 | 189.00 | 0.30 | 0 | 0.30 | around stadium, outside | no |
| 95088B | perim | no | 2 | 6.46 | 0 | 0 | 0 | legend sample | no |
| 95B4C2 | perim | yes | 2 | 0.00 | 0 | 0 | 0 | zero-length stub | no |
| 95B1AE | sport | no | 5 | 232.46 | 232.46 | 232.46 | 0 | court enclosure, 3 wickets | yes |
| 9506F9 / 9506FA / 95B1AB | sport | no | 2 each | 18.99 each | 18.99 each | same | 0 | partitions across the court | yes |
| 95B1AC / 95B1AD | sport | no | 2 each | 43.93 / 43.77 | 0 | 0 | 0 | stadium, outside | no |
| 950964 | sport | no | 2 | 7.68 | 0 | 0 | 0 | legend sample | no |

Totals vs the ledger:

| layer | total | inside ГПЗУ (incl. on line) | on ГПЗУ line | ledger |
|---|---|---|---|---|
| perimeter `232_Ог_Внешние_вар2` | 1 123.5 (1 117.0 without the sample) | **527.1** | 514.6 | 635 п.м. (pos 35) |
| sport `232_Огр_СПОРТ` | 384.8 (377.1 without the sample) | **289.4** | 0 | 391 п.м. (pos 39) |

- No sum of the perimeter lines gives 635 (513.1 on ГПЗУ; +165.6 spur = 678.8; outer stadium loop 436.6). Sport 391
  ≈ the full drawn sport linework 377–385 m (stadium included).
- The ГПЗУ ring is 863.1 m; the drawn perimeter covers 518.0 m of it. The SE 345.0 m of the ring (school/stadium side)
  has **no fence on the drawing** — the real fence there is 95EDF9/95EDFA around the stadium, outside ГПЗУ.
- 95B1AE is open: 13.3 m between its end (-9639.19, -6977.89) and its start (-9651.20, -6983.66) on the SW short side
  (collinear with the long side); 7D3188 starts at that corner.
- Linetype FENCELINE2 = "----[]----", pattern 1.45 × ltscale 4 = a square every 5.8 m: a drawing symbol, not a
  section step. No post blocks, hatches, ticks or text with «шаг/панель/секция/3D» on the fence linework.

## 3. Gates and wickets (`Калитка 1.2` x8, `Ворота 4.5` x1 in model space, all on layer `230_Зд_Контура`)

Block geometry: `Калитка 1.2` = hinge at the insert, leaf drawn 1.52 m along local −X, swing to +Y (name says 1.2).
`Ворота 4.5` = two leaves 2.25 m, opening 4.49 m centred on the insert.

| handle | block | insert X, Y (МСК-77) | rot° | ГПЗУ | on line (station m) | ledger pos | scope / gap |
|---|---|---|---|---|---|---|---|
| 95F3A7 | Калитка 1.2 | -9638.502, -6977.557 | 205.67 | inside | 95B1AE @231.7 | 38 | cut 1.2 |
| 95F3A8 | Калитка 1.2 | -9613.266, -6965.427 | 205.67 | inside | 95B1AE @203.7 | 38 | cut 1.2 |
| 95F3A9 | Калитка 1.2 | -9588.030, -6953.297 | 205.67 | inside | 95B1AE @175.7 | 38 | cut 1.2 |
| 95F3AB | Калитка 1.2 | -9532.787, -6979.300 | 122.34 | on line (0.05) | 11544B @95.8 | 37 | cut 1.2 |
| 95F3AD | Калитка 1.2 | -9646.987, -6992.373 | 115.99 | inside (1.68) | 7D3188 @9.7 | 37 | cut 1.2 |
| 95F3AC | Калитка 1.2 | -9593.732, -7022.729 | 205.65 | outside 52.5 m | 7D3188 @95.0 | 37 | out of scope |
| 95F3A6 | Ворота 4.5 | -9775.993, -7138.693 | 295.83 | outside 4.15 m | 95EDF9 @4.2 | 36 | out of scope |
| 95F3A5 | Калитка 1.2 | -10339.831, -7403.653 | 0 | legend | — | — | none |
| 95F3AA | Калитка 1.2 | 0.690, 0.332 | 205.67 | stray at origin | — | — | none |

Counts match the ledger on the drawing: sport wickets 3/3 (all inside), perimeter wickets 3/3 (2 in scope, 1 outside),
gate 1/1 (outside ГПЗУ, on the stadium loop). Each sport wicket stands 0.77 m from a partition T-joint.

## 4. Section step and component sizes — evidence

| number | value | source |
|---|---|---|
| DXF step | none (symbol 5.8 m only) | DXF, see §2 |
| PDF ЛСР-МОСК-ШК1200_ФР_03_09_2026 | no fence content (4 pages: situation plan + facade options) | pypdf text search |
| welded 3D panel width (= step) | 2 500 mm | Grand Line leaflet (fetched): Light/Medium/Profi/Expert panel table; 21vek.by Белзабор Medium 2030×2500 (fetched) |
| Profi panel max height | 2 430 mm; cell 200×55 mm (Grand Line); 50×200 (Белзабор) | Grand Line leaflet |
| Profi posts | 62×55 mm (also 80×80, 90×55) | Grand Line leaflet («PROFI для промышленных объектов») |
| Profi gates | wicket width 1.00 m; swing gates 3.0–9.0 m; heights up to 2.43 m | Grand Line leaflet |
| sport 2D panel (Bastion) | width 2 510 mm; 4 m = 2.03 + 2.03 stacked; posts 80×80 / 90×55 | Grand Line leaflet |
| colours | RAL 6005 / RAL 7040 standard (Grand Line) | Grand Line leaflet |

Sources: https://Grandline.ru/uploads/files/Sprav_ogragdeniya/liflet_panel_ograzhdeniya.pdf ,
https://www.21vek.by/fences/mediumral8017gl2030x2500_belzabor.html . «PRO» in the ledger = assumed Profi-class 3D
panel (individual project «или аналог»); the manufacturer is not named (ASSUMED).

## 5. Kit (NPM). Z 0 = ±0.000, posts sunk 0.10 m

| item | perimeter PRO H 2.5 | sport H 4 | source |
|---|---|---|---|
| step (max section) | 2.50 m, segments split evenly (ceil(L/2.5)) | 2.50 m (Bastion 2.51) | Grand Line |
| post box W×D×H | 0.06 × 0.06 × 2.60 (z −0.10…+2.50) | 0.08 × 0.08 × 4.10 (z −0.10…+4.00) | 62×55 / 80×80 rounded |
| post mesh | box without bottom, 10 tris | same | brief |
| post at | every polyline vertex, every step, both jambs of each gap, free ends at the ГПЗУ cut | same; T-joints of partitions share the enclosure post | brief |
| panel | 1 quad between post centres, z 0.05…2.48 (2.43 high, 0.05 bottom gap) | 1 quad, z 0.05…4.00 | Grand Line heights |
| rails | none (3D panel V-bends read from the opacity map) | none | proposal |
| post material | ID 2 paint_ral7016 | ID 2 paint_ral7016 | brief (Grand Line standard is 6005/7040 → ID 3 paint_ral7040 possible) |
| panel material | **ID 28 perforation («полоски»)** — the welded panel reads as vertical wires; alt. ID 27 | ID 27 mesh_chainlink | proposal, Artem |
| sidedness | single plane, two-sided material: 2 tris; duplicated back face: 4 tris | same | — |
| arcs | none in the source; rule kept: chord error ≤ 0.05 m | — | — |
| gaps | wicket: 1.20 m clear between jamb posts; gate 4.5 m (out of scope) | wicket 1.20 m | block names |
| wicket leaf | frame 4 boxes 0.04×0.04 (≈48 tris) + 1 opacity quad (2) ≈ 50 tris, height = fence panel | same, 2.0 m leaf height? (question) | proposal |
| gate 4.5 (if wanted) | 2 leaves × 2.25 m, ≈100 tris | — | block |

## 6. Tri estimate (variant A = drawn lines inside ГПЗУ)

| type | length m | posts | panels | single-sided | double-sided | cheap: one plane per straight segment |
|---|---|---|---|---|---|---|
| perimeter (11544B, 11544C, 7D3188 in, 7D3189) | 526.5 | 221 | 216 | 2 642 | 3 074 | 2 232 (11 planes) |
| sport (95B1AE + 3 partitions) | 289.4 | 126 | 119 | 1 498 | 1 736 | 1 274 (7 planes) |
| wickets in scope (2 perim. + 3 sport) | — | — | — | 250 | 260 | 250 |
| **total** | 815.9 | 347 | 335 | **4 390** | 5 070 | 3 756 |

Variant B (perimeter along the whole ГПЗУ ring 863.1 m: 361 posts, 359 panels): perimeter 4 328 / 5 046 →
total 6 076 / 7 042.

MAF budget 60 000; MAF plan ≈ 49 432 (7 pergolas) / 53 632 (14 pergolas).
- A single-sided: 53 822 / 58 022 — fits (headroom 6 178 / 1 978).
- A double-sided: 54 502 / 58 702 — fits.
- B single-sided: 55 508 / 59 708 — fits, ~0.3k left with 14 pergolas; B double-sided with 14 pergolas = 60 674 —
  over: then use single-sided or the per-segment planes.
Posts are ~80 % of the fence tris; the "cheap" variant saves only ~15 %. A further option if needed: posts as
3-face boxes (no back/top faces hidden) is not recommended for NPM review.

## 7. UV in the 512 atlas

Cells 27 and 28 are **solid dark cells (#2B2B2B)** in atlas v007; the opacity patterns are not in the atlas
(`atlas_512_v007.json` slots 12/13: "the opacity pattern itself is not in 53407"). At 512 a 56 px cell cannot carry a
2.5 m mesh pattern anyway (≈22 px/m). Proposal:
- UV0 (atlas): the whole panel quad mapped into the cell content rect minus the `id_corner_px` keep-out (bottom-right
  16 px), 2 px inset:
  - ID 28: px x 326…362, y 390…426 → u 0.6367…0.7070, v 0.1680…0.2383.
  - ID 27: px x 262…298, y 454…490 → u 0.5117…0.5820, v 0.0430…0.1133.
  (v = 1 − y/512, as the cell `uv` in the atlas JSON.)
- The see-through pattern comes from the opacity map of the material (library «карта опасити полоски/рабица»), tiled
  per panel; if the engine needs it on its own UV, add UV1 = 0…1 per panel (or 0…L/2.5 per segment plane).
- Visual result (dark plane vs see-through) is Artem's call.

## 8. Open questions (for Artem)

1. Perimeter extent: only the drawn line inside ГПЗУ (527 m, variant A) or the whole ГПЗУ ring 863 m (variant B; the
   SE 345 m has no fence on the drawing — the real fence goes round the stadium outside ГПЗУ)? Ledger 635 matches
   neither.
2. Panel material for the perimeter: ID 28 «полоски» (proposed) or ID 27 «рабица»? Post colour 7016 (ID 2) or 7040
   (ID 3, Grand Line standard)?
3. Single-sided (two-sided material, 2 tris) or duplicated back faces (4 tris)?
4. Sport enclosure 95B1AE is open 13.3 m on the SW short side — close it or leave it as drawn?
5. Wicket clear opening: 1.2 m (block name) vs leaf drawn 1.52 m vs Grand Line 1.0 m; sport wicket leaf height
   (full 4 m or 2 m with a panel above)?
6. Gate 4.5 (pos 36) and wicket 95F3AC lie outside ГПЗУ — skip (proposed) or include?
7. Step 2.5 m and post sizes are ASSUMED from Grand Line Profi/Bastion; no section step in the project sources.
