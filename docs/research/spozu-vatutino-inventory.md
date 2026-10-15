# Research: SPOZU inventory, Vatutino Дом 2 (detailed concept) -> layer map for Ground

Card t_27ae0dd8, issue #194 (parent spec #149, user story 16). First real SPOZU for the CAD adapter.
Read-only research on **copies** of the user's two DWG files; nothing from them is committed (no DWG, no DXF,
no images). Real project data, not synthetic. Grilling context: `docs/domain/areas/ground-surface.md`
(Project practice), D100.

## Summary

- Both DWGs convert cleanly with the AutoCAD 2025 core console (`DXFOUT`, DXF 2018, 16 digits) and read with
  ezdxf 1.4.3. Units are **metres** (`$INSUNITS=6`), local CAD coordinates without geodata.
- The Ground plot is **one closed LWPOLYLINE** (handle `568BF`) on layer `ПР_ЛГР_предлагаемые`, the layer the
  legend row «Граница проектирования» uses: 20 vertices, 25 725.1 m², perimeter 639.2 m, about 213 x 199 m,
  no self-intersections. The layers named in the grilling (`ГП_ГраницаЗУ`, `ГП_ГраницаРабот`) exist but are **empty**.
- Coverings are hatches on `!_А101_*` layers, one layer per covering type, which the model-space legend table names
  (9 covering rows -> 18 hatch layers, see the layer map). Most coverings also have closed contours (LWPOLYLINE) on the
  same layer. Inside the boundary the covering hatches add up to more than the plot area, so they overlap.
- Planting and MAF are block INSERTs. The block name is the species or MAF name. 5 plant blocks also carry
  attributes (`Имя`, `Имя латынь`, `Класс`, `Группа`, ...). Model space holds 4 specification tables
  (`ACAD_TABLE`): legend, planting schedule, two MAF schedules. The MAF schedules have no position numbers.
- Probe: the schedule quantity matches the INSERT count inside the boundary for 36/41 items (main file) and
  37/41 (paving file). The rest are listed under open questions.
- Vertical planning: only a **preliminary** one (`!_А101_предварительная ВП`, frozen; two blocks dated 2024-10-10/11).
  It has 48 spot heights inside the plot (141.83–154.40 m) and 2.5D contour polylines (0.1 m step, labels every
  0.5 m). The plot drops about 9–12 m, so it is not flat.
- The paving file contains everything in the main file plus the paving layout `Мощение`: 4 tile types, laying
  arrays `РМ_*`, a «Типы мощения» table. Its planting counts are closer to the schedule.

## Inputs and conversion

| File (copy) | Original size | sha256 (before = after) | DXF size | Load (ezdxf) |
|---|---|---|---|---|
| `main.dwg` = `ППТ8_1_Дом2_Детализированная концепция.dwg` | 25 795 928 B | `64e22677454affce7071a823123b13742c8d68cd39c1ec0ee761c4cfa3b546e4` | 155 614 523 B | 31–36 s |
| `paving.dwg` = `..._мощение.dwg` | 28 642 060 B | `d24df23219fe1357830b3628ca31fa9acacedb158a9d3c8b9f9bc8a16cc3ece2` | 178 169 362 B | 30–37 s |

The originals were hashed before the copy and again after all runs. The hashes are identical and the mtimes
are unchanged (2025-06-19). Work dir: `C:/x/t_27ae0dd8/` (local, not committed).

Conversion, one call per file (`main` / `paving`):

```
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py acad --file C:/x/t_27ae0dd8/main.scr \
    --dwg C:/x/t_27ae0dd8/main.dwg --out C:/x/t_27ae0dd8/main_acad.log
# -> accoreconsole.exe /i C:/x/t_27ae0dd8/main.dwg /s C:\x\t_27ae0dd8\main.scr /l en-US   (status ok, 5.8 s)
```

`main.scr`:

```
(setvar "FILEDIA" 0)
(setvar "CMDECHO" 1)
(princ (strcat "AGR INSUNITS=" (itoa (getvar "INSUNITS")) " LUNITS=" (itoa (getvar "LUNITS")) " MEASUREMENT=" (itoa (getvar "MEASUREMENT")) " ACADVER=" (getvar "ACADVER")))
(princ (strcat "\nAGR EXTMIN=" (vl-princ-to-string (getvar "EXTMIN")) " EXTMAX=" (vl-princ-to-string (getvar "EXTMAX"))))
(command "_.DXFOUT" "C:/x/t_27ae0dd8/main.dxf" "_V" "2018" "16")
```

Console output: `INSUNITS=6 LUNITS=2 MEASUREMENT=1 ACADVER=25.0`. The console also printed
"Custom object(s) encountered": AEC objects are present, and the AEC enablers load in the core console. Fonts
`Consultant` and `gost_win.shx` were replaced by `simplex.shx`, which affects text display only.
Analysis scripts: `inventory.py`, `deep.py`, `pass3.py`, `probe.py`, `rot.py`, `ocs.py` in the work dir, run with
`uv run python <script> <dxf>` after `uv sync --extra cad`. Note: the card says "group `cad`", but in
`pyproject.toml` `cad` is an optional-dependency **extra**, not a dependency group.

## Per file: layouts, entities, layers

| | main | paving |
|---|---|---|
| Layouts | Model, `ГП_1.500`, `ГП_1000_2`, `ГП_1200`, `Сечения` | same + `Мощение` |
| Model-space entities | 9 880 | 10 080 |
| By type (model) | INSERT 5904, LWPOLYLINE 2174, HATCH 778, MTEXT 644, LINE 163, ARC 99, DIMENSION 89, SPLINE 12, POLYLINE 8, CIRCLE 5, ACAD_TABLE 4 | INSERT 5942, LWPOLYLINE 2281, HATCH 786, MTEXT 644, LINE 163, DIMENSION 105, ARC 99, MULTILEADER 22, CIRCLE 14, SPLINE 12, POLYLINE 8, ACAD_TABLE 4 |
| Layers (table / used in model) | 277 / 94 | 308 / 105 |
| Block definitions (anonymous) | 3 512 (116) | 4 664 (1 231) |
| Blocks inserted in model space | 130 | 167 |
| Xrefs | none (the neighbourhood plan is **bound**: prefix `ППТ8-1_1 очередь от Вовы$0$`) | same |
| Paper-space content | only viewports + 3 title inserts per sheet | `Мощение`: 499 entities, paving plan 1:500 and fragments 1:100, «Типы мощения» table |

The paving file has 31 extra layers and no layers missing compared with the main file: `РМ_*`, `!_А101_плитка_*_РМ`, the tile
catalogue layers `!коллекция GRANIT/PROFI ...`, `ГП_начало раскладки плитки`, `ПП_маркировка мощения_500 А1`, `00`.
Model-space counts differ on 25 layers. The Ground-relevant differences: `!_А101_борт_садовый_бетонный` 83 -> 105,
`!_А101_борт_деревянный` 30 -> 39, `!_А101_ограждение` LWPOLYLINE 30 -> 7, `!_А101_маф` 191 -> 188,
`!_А101_Лиственные кустарники` 4585 -> 4587, `!_А101_лестница` 11 -> 13, and ±1 hatch on 6 flower-bed layers.

Layer families:
- `!_А101_*` (≈ 45 layers): the A101 landscaping concept, which is the content of this plot.
- `ППТ8-1_1 очередь от Вовы$0$*` (≈ 45 layers, bound xref): the surrounding planning project (buildings, roads,
  other yards). All of it is outside the plot; only one hatch has its centroid inside (`Десна_проезды_заливка`, 3 014 m²).
- `ГП_*` (Civil 3D style, e.g. `ГП_Вертикалка_*`, `ГП_Поверхности_*`, `ГП_Благоустройство_*`, `ГП_ГраницаЗУ`):
  template layers. They are empty in model space; only `ГП_Вертикалка_*` is used, inside the ВП blocks.
- Building plans as blocks (`!_А101_ТЭТ`, frozen: 18 Revit plan exports at scale 0.001; `Первый этаж В2 23.01.2025`
  on `0`): out of scope.

Frozen in model space: `!_А101_освещение`, `!_А101_ТЭТ`, `ГП_пож.площадки`, `ГП_пож.радиусы`,
`!_А101_движение пешеходов_*`, `ГП_СмещенныеПП`, `ПР_Подземный_Паркинг`, `!_А101_предварительная ВП`,
`!_А101_площадки_развороты`. Off: `A-GLAS` (19 hatches, 76 135 m², mostly outside).

## Specification tables (texts that are legends / schedules)

All four model-space tables are `ACAD_TABLE` entities on layer `0`, placed in a row east of the plot.
The cell text is in the anonymous table blocks (`*T3397`, `*T3508`, `*T3509`, `*T3510`). Each schedule's
"Условное обозначение" column holds **one real sample INSERT/HATCH per row** on the production layer. These samples
are outside the plot, so a reader must filter by the boundary (see the probe).

| Table | Content |
|---|---|
| `*T3397` «УСЛОВНЫЕ ОБОЗНАЧЕНИЯ» | 21 rows: boundary, SOS button, lighting (3), curbs (3), stairs, coverings (8), flower bed, MAF, tree, shrub |
| `*T3509` «Деснаречье. Дом 2. Ведомость озеленения / Ассортиментная ведомость» | Поз. 1–17: 5 trees (94), 10 deciduous shrubs (4 532), 2 conifer shrubs (169); Поз. 18–20 areas: «Газон универсальный рулонный» 1 326.29, «Мульча» 3 646.97, «Газон укрепленный» 2 460.11 (total 7 433.37, m² by context) |
| `*T3508` «Общие маФ» (custom) | 9 benches «Верона» types 1–9, bar counter, MGN handrail, canopy «Андромеда» types 1–4, sandbox; qty 1 each |
| `*T3510` «Общие маФ» + playground / workout / senior / general-rest groups | 31 products: name + article, maker, size (mm), material/RAL 7047, qty, link |
| paving `*T3530` «Типы мощения» (layout `Мощение`) | 4 tile types «Готика» 100x300x60(80): 1 red (Silver №9), 2 grey (Bronze №25), 3 white stripes ≤ 0.6 m (Gold №22), 4 white large areas (Profi №8) |

The other MTEXT in model space: 627 on `...$0$Марки формообразующих элементов` (marks of the neighbourhood plan) and
17 house numbers. None of them are Ground data.

## Layer map for Ground

The legend row -> layer mapping comes from the sample entities in the legend's symbol column (`pass3.py`), not from
guessing names. Areas are net hatch areas (outer minus inner loops; arcs flattened at 0.2 rad, spline edges by
control points). Counted: entities whose centroid or insert point lies inside boundary `568BF`. File: paving
(main differs by < 1 % unless noted).

| Ground item | Layer | Kind | In plot | Area in plot, m² | Legend / schedule |
|---|---|---|---|---|---|
| **Plot boundary** | `ПР_ЛГР_предлагаемые` | 1 closed LWPOLYLINE `568BF`, DASHED, colour 5, width 0.3 | 1 | 25 725.1 | «Граница проектирования» |
| Tile, light (base) | `!_А101_плитка_светлая` | HATCH AR-B816 ×35 + SOLID ×6; 202 LWPOLYLINE (27 closed) | 41 | 18 291.1 | «Покрытие из плитки тротуарной бетонной»; paving types 3/4 |
| Tile, red | `!_А101_плитка_красная` | HATCH AR-B816 | 8 | 887.8 | same row; paving type 1 |
| Tile, dark | `!_А101_плитка_темная` | HATCH AR-B816 | 13 | 130.2 | same row; paving type 2 |
| Stepping slabs 900x300 | `!_А101_плитка_светлая пошаговая` | INSERT `Бет пл пошаговая 300х900` (0.9 x 0.3 m) | 248 | (248 x 0.27 = 67) | «...пошаговой 900х300» |
| Pebbles | `!_А101_покр_галька` | HATCH AR-SAND ×2, AR-CONC ×1 | 3 | 298.5 | «Покрытие из гальки» |
| Gravel screening 2–8 mm | `!_А101_покр_гравийный отсев фр 2-8` | HATCH AR-SAND | 16 | 914.4 | «...гравийного трамбованного отсева» |
| Decking (larch) | `!_А101_покр_декинг` | HATCH ANSI31 ×2 (both outside the plot); 1 LWPOLYLINE in plot | 0 hatch | — | «...деревянного настила» |
| Mulch | `!_А101_мульча` | HATCH AR-CONC; 21 LWPOLYLINE | 65 | 3 808.0 | «Покрытие из мульчи»; schedule Поз. 19: 3 646.97 |
| Reinforced lawn (Ecoraster, fire lanes) | `!_А101_укрепленный газон` | HATCH GRATE | 40 | 2 506.4 | schedule Поз. 20: 2 460.11 |
| Rolled lawn | `!_А101_озел_штрих_газон` | HATCH SOLID ×279 + 171 closed LWPOLYLINE | 279 | 968.4 | schedule Поз. 18: 1 326.29 |
| Flower beds (8 species) | `!_А101_укрепленный цветник 0N <species>` N = 01–08; outline `!_А101_укрепленный цветник` | HATCH ZIGZAG (+1 SOLID each in paving) | 30 | ≈ 69 | «Цветник»; **not in the planting schedule** |
| Fire lane outline | `_ГП_ПожПроезд` | 1 closed LWPOLYLINE | 1 | 3 866.3 | — |
| Shifted parking spaces (frozen) | `ГП_СмещенныеПП` | HATCH SOLID | 4 | 464.1 | — |
| Curbs | `!_А101_борт_садовый_бетонный`, `!_А101_борт_деревянный`, `!_А101_борт_металлический_заглубленный` | open LWPOLYLINE | 95 / 38 / 26 | — | 3 legend rows |
| Stairs | `!_А101_лестница` | INSERT `лестница 1..8` | 10 | — | «Лестница» |
| Fence, gates | `!_А101_ограждение` | LWPOLYLINE + INSERT `Калитка` | 7 + 4 | — | — |
| Trees (points) | `!_А101_деревья` | INSERT, block = species | 76 | — | Поз. 1–5 |
| Shrubs, deciduous large (points) | `!_А101_кустарники` | INSERT | 92 | — | Поз. 6–8 |
| Shrubs, deciduous (points) | `!_А101_Лиственные кустарники` | INSERT; 3 blocks with 6 attributes | 4 571 | — | Поз. 9–15 (+ Ива швейцарская, not in the schedule) |
| Shrubs, conifer (points) | `!_А101_Хвойные кустарники` | INSERT; attributes on both blocks | 176 | — | Поз. 16–17 |
| MAF (points) | `!_А101_маф`, `!_А101_маф_парковые`, plus `0` (springers, swings `ио 0118т-1`, 18 waste containers) and `__ТБО` (container yards) | INSERT, block = product | 167 + 17 (WCS) + 13 + 1 | — | `*T3508`, `*T3510` (no positions) |
| Lighting (frozen) | `!_А101_освещение`, `НО_SP 12м ...`, `!ГИП_НО_опоры` | INSERT | 99 / 63 / 1 | — | 3 legend rows; not Ground |
| Paving laying (paving file) | `!_А101_плитка_{светлая,темная,красная}_РМ`, `РМ_контур`, `РМ_массивы`, `РМ_штр_*` | INSERT arrays of 100x300 tiles, closed contours | 26 + 34 contours | 785.8 (РМ_контур) | «Типы мощения» |
| Vertical planning (preliminary, frozen) | `!_А101_предварительная ВП` -> blocks `Д2_ВП_2024.10.10`, `Дороги_ВП_2024.10.11`; inner layers `ГП_Вертикалка_ОпорнаяТочка_New`, `..._ГоризонталиОсновные`, `..._ГоризонталиВспомогательные`, `..._ГоризонталиМетка` | spot heights (MTEXT, Z = value), contour LWPOLYLINE with elevation | 48 spot heights; contours in both blocks: 103 main + 408 auxiliary (the road block's half outside the plot) | — | — |

Sum of the covering areas inside the plot ≈ 27 900 m² against the 25 725 m² plot. The light tile (18 291 m²)
lies under the other coverings, so draw order or a "layered cake" reading is required (open question 3).

Species labels: for every planting block the **block name** is the species (Russian, sometimes with the Latin name). Only
`Облепиха`, `Рябинник`, `Дерен белый 'Red Gnome'`, `Сосна горная ф. Мугус`, `Ель нидиформис` also carry
attributes `Имя / Имя латынь / Класс / Группа / Тип крепления / Размер`. Schedule names differ slightly from block
names (e.g. block «Дерен белый 'Red Gnome'» / schedule «Дерен отпрысковыи 'Red Gnome'», `Cornus alba` vs `Cornus sericea`),
so the adapter needs a mapping table (`probe.py` holds one for 41 items).

## Units, coordinates, extents

- Units: `$INSUNITS = 6` (m), `$MEASUREMENT = 1` (metric), `$LUNITS = 2` (decimal). Block sizes confirm metres at 1:1:
  `Урна` 0.62 x 0.47 (schedule 620x470 mm), `Кресло Парк 12750` 0.61 x 0.63 (765x530 mm), `Качели парковые`
  0.7 x 3.0 (3000x700), `Бет пл пошаговая 300х900` 0.9 x 0.3, `Бетонные раскопки` 0.5 x 0.5 (500x500).
- Coordinate base: local CAD coordinates, no `GEODATA` object, no named UCS, `$INSBASE` 0,0,0. Which geodetic system
  the coordinates are in (for example MSK-77) is not recorded in the file (open question 6).
- Header extents (`$EXTMIN` -21 985.5, -48 427.1, -589.2 / `$EXTMAX` 33 081.8, 7 997.7, 438.2) span ~55 x 56 km
  because of stray objects. Do not use them. Real content: model-space layer extents x -8 671 … -6 281, y -15 885 … -13 634
  (the neighbourhood plan plus the tables).
- **Site extents** (boundary `568BF`): x -7 700.08 … -7 487.29, y -15 387.12 … -15 188.37 (212.8 x 198.8 m), Z = 0.
  The tables and legend samples sit east of the plot (x ≈ -7 240 … -6 300, y ≈ -14 905 … -15 130).
- Z: almost all Ground entities are at Z = 0 (2D plan). Exceptions: 1–2 hatches each on `плитка_светлая`, `плитка_темная`,
  `мульча` at elevation 146–438 m, 4 MAF inserts at Z 147.7, 2 conifers at 147.2, `!_А101_маф_парковые` at
  Z -319.9 … 5.6. These look like stray snaps. The only elevations meant as data are inside the ВП blocks.
- OCS: 59 entrance inserts, 6 `лежак2` and 6 light-tile LWPOLYLINEs have extrusion (0, 0, -1), i.e. mirrored OCS. Their raw
  `insert`/vertices are OCS coordinates. Without `ocs().to_wcs()` the 6 loungers come out 2 x 7 600 m away (outside the plot),
  which is a pitfall for the adapter.
- Rotations: planting inserts **are** rotated (2 064 of 4 587 deciduous shrubs, 107 of 178 conifers) and scaled 0.333–2.0
  (symbol size). This is consistent with D100 ("SPOZU points have no rotation" applies to the model, not the symbol).
  MAF inserts are rotated (141 of 188) and mirrored (`xscale = -1`, 29). MAF orientation therefore comes from the DWG.

## Boundary polygon

Found and closed. `568BF` has the `closed` flag set, 20 vertices, 0 self-intersections (O(n²) segment test),
segments 0.0–112.4 m. There is **one duplicate vertex** (a zero-length segment), and the first and last vertices are 0.568 m
apart; the closed flag joins them with a 0.568 m segment. Both must be cleaned (drop duplicate vertices) before
triangulation. No other polyline repeats this outline (bbox ±2 m: none). The other 26 polylines on
`ПР_ЛГР_предлагаемые` are open or belong to other plots of the neighbourhood plan.

## Vertical planning (heights)

- Only a **preliminary** vertical planning is present, as two blocks on the frozen layer `!_А101_предварительная ВП`
  (inserted at 0,0,0, scale 1, no rotation, so the block coordinates are model coordinates).
- `Д2_ВП_2024.10.10` (yard): 48 spot heights `ГП_Вертикалка_ОпорнаяТочка_New` (MTEXT, all inside the plot bbox,
  141.83–154.40 m; for 37/48 the text Z equals the printed value). Also 43 main and 175 auxiliary contours (LWPOLYLINE
  with `elevation`, 0.1 m step, main every 0.5 m) and 268 contour labels (145.5–154.0).
- `Дороги_ВП_2024.10.11` (roads): 60 main + 233 auxiliary contours, 278 labels, 145.5–155.5 m; about half of them inside the plot bbox.
- The heights look like absolute (Baltic) metres; the system is not stated. The relief inside the plot is ~9–12 m, so the "flat first"
  practice (ground-surface.md Project practice) applies only as a first pass.

## Probe (invariants of the inventory)

| Invariant | Probe | Result |
|---|---|---|
| Originals are never modified | sha256 + mtime of both originals before the copy and after all runs | 2/2 identical |
| Schedule quantity == INSERTs inside the plot (planting Поз. 1–17 + 24 MAF items) | `probe.py`: 41 block <-> schedule pairs, point-in-polygon on `568BF`, OCS -> WCS for mirrored inserts | main 36/41, paving 37/41. Container TBO: 18 = total (8 in plot). Mismatches: Ольха 8 in plot / 24 total vs 23; Яблоня 21 / 25 vs 24; Сосна горная 106 vs 99; Стефанандра 1 000 vs 1 002 (main only; paving 1 002) |
| Every legend row maps to ≥ 1 production layer | `pass3.py`, entities in the legend symbol column | 21/21 rows have a sample on a named layer |
| Boundary is a simple closed ring | closed flag, O(n²) segment intersection, duplicate-vertex scan | closed, 0 crossings, 1 duplicate vertex |
| Main and paving files agree on boundary and layer set | same handle/area/bbox; layer set difference | boundary identical; paving = main + 31 layers |

Each schedule "Условное обозначение" column holds one sample per row. This explains why the total is schedule + 1 for most plants (+2 with the legend for Липа and Рябинник).

## Open questions for the user

1. **Boundary**: is `ПР_ЛГР_предлагаемые` / `568BF` (25 725 m², legend «Граница проектирования») the Ground boundary? The
   layers `ГП_ГраницаЗУ` and `ГП_ГраницаРабот` exist but are empty, and no layer is named «граница проектируемого участка».
2. **Planting outside the plot**: 15 Ольха and 3 Яблоня from the schedule stand outside `568BF` (all other points
   outside the plot are schedule/legend samples). Is the schedule wider than the Ground boundary (street planting)? Should they go into Flora or be dropped?
   Сосна горная has 106 points but 99 in the schedule. Which count is right?
3. **Overlapping coverings**: the light-tile hatches (18 291 m²) cover most of the plot under the other coverings. Is the light tile the
   base layer of the "layered cake" (method C, the default per grilling Q7), with every other covering inset on top?
4. **Tile types**: the paving sheet has 4 tile types, but the model has 3 tile layers (`светлая`, `красная`, `темная`). Type 3
   (white stripes ≤ 0.6 m, Gold №22) and type 4 (white, Profi №8) both look like `светлая`. One Ground material or two?
5. **Vertical planning**: is the preliminary ВП (2024-10-10/11, frozen) the height source, or will a separate VP sheet come?
   Use the spot heights, the contours, or both?
6. **Coordinate system**: what system are the local coordinates (x ≈ -7 600, y ≈ -15 300 m) in, and are the heights Baltic?
   This is needed only if Ground must be georeferenced; otherwise the plot is moved to a local origin.
7. **Master file**: the two DWGs differ. The paving file (saved 00:21) matches the schedule better; the main file (02:24) has
   23 more fence polylines and 3 more MAF. Which one is the master?
8. **Flower beds**: the 8 flower-bed species (`укрепленный цветник 01–08`, ≈ 69 m² in the plot) are not in the planting
   schedule. Are they Ground material (texture) or Flora (instances)?
9. **Hatch or contour**: most covering layers have both hatches and closed polylines (e.g. light tile: 41 hatches,
   27 closed polylines). The grilling says "if contours exist, take them". Here the contours are partial. Hatch boundaries
   first, contours as a check?

## For the adapter (not implemented here)

- Filter by the boundary polygon first. The schedule samples and legend symbols are real entities on production layers.
- Convert OCS -> WCS for every INSERT/LWPOLYLINE (`ocs().to_wcs`), clean duplicate vertices, ignore `$EXTMIN/$EXTMAX`.
- Map layers by the legend table (sample entities in the symbol column), not by name patterns. The `ГП_*` template
  layers are empty in this project.
- Read the planting species from the block name; use the attributes when present; join to the schedule through a name table.
- ezdxf load is ~35 s per 160–180 MB DXF. `bbox.extents` per layer over the whole model space cost 175–200 s
  (nested building blocks), so restrict it to the plot layers.
