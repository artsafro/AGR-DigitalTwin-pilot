# KPP1 drawing — mapping questions (#967)

Provisional extract only. Nothing below was chosen as the body contour or as a cutter.
Sheets, from the title block of each DWG (see `sheet-census.json`):

| File | Sheet | What it is | Scale (viewport view height / paper height) |
|---|---|---|---|
| L01 | П 1, «Центральная проходная» | Facades 1-4, 4-1, А-В, В-А | 1:100 (four views), 1:50 (one legend view) |
| L02 | П 2 | Same facades, «Цветовые решения» | 1:100 (four views), 1:50 (schedule view) |
| L03 | П 3 | «План на отметке 0,000» | 1:100 (plan), 1:50 (one view), 1:20 (three detail views) |

There is no section sheet in this set. `22Е56-АР2-1002-АС.03-R1_L02_без подписей.pln` is a plot file, not a sheet (sha256 `8b7b4253…`, not opened for geometry). Units: DWG `$INSUNITS` = 4 (millimetres), read from the file header; AutoCAD reported the same when the copy was opened. The provisional coordinates are metres in the benchmark FBX frame: grid axis «1» (x = 25884.5 mm) and axis «А» (y = 0) are project (0, 0), then minus `jobs/KPP1/object.json` `to_object` (14.655 m, 5.355 m). Wall-cut pieces that survive the 0.5 m² rule span x −14.985…12.675, y −6.385…5.975 in that frame (the 0.000 facade rectangle in project metres is x −0.330…27.330, y −0.330…11.330).

The synthetic kpp1 contour (`C:/x/methods/building-body/kpp1/contours.json`) is 9 bands from the mesh, footprint about 33.28 × 14.75 m, no openings. This plan is one storey at 0.000 and does not close into that footprint, so RESULTS.md still has no kpp1 drawing row.

1. **Interior walls.** `I-WALL-____-MCUT` has 263 lines and `I-WALL-____-OTLN` 118. `A-WALL-____-MCUT` has 262 lines and is the layer used as the wall cut. Recommendation: leave the `I-WALL` layers out of the exterior contour (the name is the interiors discipline, and their extent sits inside the architectural cut). Confirm before they are added.

2. **Insert base point.** 40 inserts whose block name contains «Дверь» or «Окно» (layers `A-DOOR-____-OTLN` 30, plus windows on `A-GLAZ-____-OTLN` / `A-GLAZ-CWMG-OTLN`) were not made into cutter boxes. Recommendation: do not cut until the insert is known to be the opening centre or the hinge. The reader accepts only an explicit `centre` and was not given one.

3. **Mullions and the grille on `A-GLAZ-CWMG-OTLN`.** That layer has 87 inserts. Names that are «Прямоугольный импост» (50×100 mm or 200×75 mm) were dropped as not a door or a window. One insert is «Решетка 1000х500». Recommendation: imposts are frame members, not openings; the grille stays out until you say it is a wall opening.

4. **Storey height.** L03 states the plan elevation 0.000 and nothing else. The four facades share only the marks 0.000 and +9.500; other marks (+3.300, +3.900, +4.850, +8.650, …) are not on every facade. `jobs/KPP1/object.json` already records L0 0.000, L1 3.900 and roof 7.909, and says +8.650 is a parapet, not a floor. Recommendation: do not extrude a band to +9.500. Which of the drawn marks are the band tops for this rerun?

5. **Gap close.** The #727 rule closes gaps strictly under 1.5 m. The plan has a 1960 mm double door, so the architectural wall cut stays in pieces (9 kept above 0.5 m², 13 smaller pieces dropped). Recommendation: do not raise the 0.75 m constant for this one sheet. The kept pieces are wall strips, not one outline.

6. **Frame.** Recommendation: keep the axis-1 / axis-А origin plus the object.json shift above, because the outer wall faces then land on the recorded 0.000 corners (−0.330 / 27.330 × −0.330 / 11.330 m) within a millimetre. Confirm before any measured deviation row is written.
