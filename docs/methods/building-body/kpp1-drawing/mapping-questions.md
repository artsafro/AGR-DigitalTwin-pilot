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

## Answers

Accepted as written. The runnable contour is `plan-contours.json` (metres, origin axis 1 / axis А at 25884.5, 0 mm, then `frame_shift_m` −14.655, −5.355).

1. **Interior walls.** `I-WALL-____-MCUT` and `I-WALL-____-OTLN` stay out of the exterior contour. Only `A-WALL-____-MCUT` is the wall cut.
2. **Insert base point.** Not proven, so no cutter is written (`openings` is empty). On plan L03 the insert is the gap centre for some doors and not for others: handle 59E (1000×2100, rotation 270°, insert 32904.5, 8489.8 mm) has wall-cut ends at −500 and +500 mm, midpoint 0 mm from the insert; handle 617 (1000×2100, rotation 0°, insert 35736.7, 11275 mm) is the same, gap 1000 mm; handle 82E (1960×2080, rotation 180°, insert 35384.5, −275 mm) has ends at −1000 and +1000 mm, midpoint 0 (named leaf 1960 mm, gap 2000 mm). Handle 529 is 270 mm off the gap midpoint and handle A17 is 530 mm off. On facade L01 the placed 1000×2100 doors sit at y = 0 and y = 3900 mm, the floor marks 0.000 and +3.900, not at mid-height 1050 or 4950. An AGS68 window on L01 sits at y = 0 and y = 3650 mm. The insert is therefore not the opening centre for the set.
3. **Mullions and the grille.** Imposts (`Прямоугольный импост`) and `Решетка 1000х500` are not openings. They stay dropped.
4. **Storey height.** Bands are 0.000–3.900 and 3.900–7.909 from `jobs/KPP1/object.json`. Both bands reuse the 0.000 plan: this set has no L1 plan and no section. +9.500 is not a band top.
5. **Gap close.** The constant stays 0.75 m. Nine pieces are kept and 13 pieces at or under 0.5 m² are dropped. The piece bbox is 27.66 × 12.36 m (x −14.985…12.675, y −6.385…5.975). It does not close into the synthetic mesh footprint of 33.28 × 14.75 m (9 bands, 10 pieces).
6. **Frame.** Axis 1 / axis А plus the object.json shift, as above. The measured drawing rows are R14 (kernel-prisms, 1008 triangles, deviation 7.0361 / 4.8894 m, 0/9 closed shells) and R15 (blender-gn-union, 737 triangles, the same deviation, 0/9 closed shells). R13 and R16 are not measured: source-as-is is the supplied FBX, and max-pymxs-cleanup does not read the plan.
