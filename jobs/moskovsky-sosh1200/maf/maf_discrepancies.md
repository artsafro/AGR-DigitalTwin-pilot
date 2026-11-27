# MAF discrepancies — moskovsky-sosh1200

Ledger (`intake/maf_ledger.json`) vs drawing blocks inside ГПЗУ (`maf_points.json`) vs the user's visualisation
scene `MOS_GP_26.11.2026.max` (3ds Max 2026, PID 489216, cm; read only: no selection, transform or save).
Rule (TASK.md 4-5): type from the ledger, count/position from the drawing; every difference gets a helper and a
viz check. Nothing here is decided — open items are questions for Artem.

## DWG -> viz transform

`viz_xy_m = R(-25.6965°) · dwg_xy_m + (11873.699, 2136.140)`, rigid, scale 1 (viz cm = m × 100).
Found by a seed search (canopy/table pairs) + iterative nearest same-type matching.
Residual: 88 pairs over 17 types, RMS 0.30 m, max 1.00 m (DWG block-extent centre vs viz bbox centre;
label text inflates DWG extents). Precise subset (canopies, tables, Аданат, urns, chess, ВСТ 9504, tennis,
Хитроу, drum, aerofon; 70 pairs): RMS 0.11 m, median 0.055 m, max 0.61 m. Canopy fill centroids vs `NAVES_260529_*`
pivots: 0.04–0.07 m. Machine form: `maf_points.json` → `viz_transform`; per point `viz_xy_cm` and nearest viz object.

## Count / type differences

| pos | item | ledger | drawing in ГПЗУ | viz | what the viz shows at the points | proposal |
|---|---|---|---|---|---|---|
| 4 | БУМ-Бревно ИК 0209Т-6.1 | 11 | 6 | 5 | 5 points have a `БУМ_БРЕВНО*` (0.07–0.17 m; one 3.4 m off). Point (-9788.49, -7061.86) [viz -891, 1855 cm]: **no object** in the viz. | 6 by the drawing; ask about the 6th and the ledger 11 |
| 5 | Переговорные трубы ИО 1215.1 | 4 | 4 | 2 meshes (`ИО 1215`, `ИО 1216`, each 2 tube sets) | all 4 covered | none (code 1215 vs 1215.1: ledger) |
| 8 | Шахматный стол 6U7004 | 4 | 10 | 10 (`boltu 011..020`) | every point has a table (≤0.09 m, one 0.61 m) | 10 by the drawing |
| 9 | Стрела-дуга 6U2023 | 3 | 3 | 2 | 2 points match `Стрела Дуга*` (0.35 / 1.48 m). Point (-9796.77, -7061.25) [viz -2076, 1820 cm]: **no object** | 3 by the drawing; confirm the 3rd |
| 10 | Плато 1 6W3000.1 | 9 | 9 | 9 | 6 match ≤0.8 m; south cluster of 3 shifted ~2 m in the viz | 9 by the drawing (positions from DWG) |
| 11 | Хитроу гранд 6W2006.1 | 12 | 3 | 3 (`Скамья_9_max*`) | all 3 match (0.01 m) | 3 by the drawing |
| 17 | Стол теннисный СО 0216-3 | 7 | 4 | 4 | all 4 match (≤0.07 m) | 4 by the drawing |
| 19 | Баскетбольная стойка СО-012 | — (empty) | 2 (+1 legend sample) | 2 (`backboard001/002`) | both match (~1.0 m) | 2 |
| 24 | Стол со скамейкой и диваном ВСТ 9504/1 | 4 | 7 (+1 legend) | 7 (`DET_STL-M-0007_*`) | all 7 match (≤0.12 m) | 7 by the drawing |
| 25 | Пергола ВСТ 9614/4 (blocks: ВСТ 9612_6) | 14 | 14 blocks | 7 (`Group4258..4264`, 5.82×2.0×2.7 m) | the 14 blocks are 7 back-to-back pairs of 3.0 m (9612/6); each viz pergola sits at a pair centre (1.5 m to each block). Type 9614/4 = 5.8 m = one pair | **question**: 7 × 9614/4 (viz) or 14 |
| 26 | Навес для МГН ВСТ 9624/3 | 2 | 1 (+1 legend) | 1 (`ВЫСОТА_ВСТ 9624/004`) | matches (0.02 m) | 1 by the drawing |
| 27 | Скамейка «Скарлет» 10027-1 | 16 | 19 | 19 (`10027-1.0.00 СБ003..021`, 14 inside pergola groups) | all 19 match (≤0.12 m) | 19 by the drawing |
| 28 | Урна «Город» Аданат 9004 (blocks: Робинзон 6W9006) | 14 | 11 | 11 (Робинзон cube urns) | all 11 match (≤0.2 m); viz type = Робинзон, ledger type = Аданат «Город» | 11 × Аданат 9004 (ledger type) |
| 32 | Контейнерная площадка на 3 конт. | 6 | 1 yard outline (`Усл конт площ`) | 4 enclosures `STF_Musor_Block_*` | enclosures sit on the 4 `ТБО непищ` points inside ГПЗУ (0.4–3.1 m); the 5th (`_002`) is on the ТБО point 2.6 m outside ГПЗУ | **question**: 4 yards inside (or 5 with the boundary one); which Аданат model |
| 34 | Контейнер МК001 | 18 | 4 groups `ТБО непищ` | 12 dumpster proxies (3 per enclosure) | see 32 | 12 (= 4 × 3), follows 32 |
| 37/38 | Калитки (shared block `Калитка 1.2`) | 3 + 3 | 4 (+1 on the boundary, +1 at 52 m outside, +1 at origin) | none on the MAF layer | — | **question**: fence scope |

Matching positions without differences: 1 (7/7/7), 2 (5/5/5), 3 (7/7/7), 6 (2/2/2), 7 (2/2/2), 21 (1/1/1), 23 (3/3/3).

## Ledger rows with no drawing point inside ГПЗУ

- 22 Стойки для большого тенниса ГЛАВСПОРТ 11.100, ledger 2: no block; the callout points at the rubber hatch
  `250_Покрытия_Тип3`. In the viz, `Group1276` (3.06 × 20.3 × 2.04 m, posts/cylinders) sits inside ГПЗУ at DWG
  (-9634.34, -6979.58) — possibly this item; unidentified.
- 33 Хозблок Аданат, ledger 1: callout inside ГПЗУ, no block (the arrow ends on a pine block). No point.
- 18 Ворота футбольные СО-002, ledger 2: callouts outside only. Viz `Group1053` / `Group4265` (1.38 × 3.22 × 2.08 m)
  sit 22 m and 20 m outside ГПЗУ (stadium).
- 29–31 полоса препятствий ВПП: ledger 0, blocks outside. 40 искусственная неровность: no block.
- Other viz objects inside ГПЗУ with no ledger/drawing match: `Rack_1` (0.98 × 0.62 × 0.95 m, chrome spheres) at DWG
  (-9591.6, -6954.0).

## Helpers to create later (not created now)

Created in the working scene at the DWG point, name `HLP_MAF_<pos>_<n>`, text = «ledger N / drawing M / viz K».

| helper | DWG XY (МСК-77 m) | reason |
|---|---|---|
| HLP_MAF_04_1 | -9788.49, -7061.86 | drawing point without a viz object; ledger 11 vs drawing 6 |
| HLP_MAF_08_1 | -9670.45, -6964.86 (cluster centre) | ledger 4 vs drawing 10 |
| HLP_MAF_09_1 | -9796.77, -7061.25 | drawing point without a viz object |
| HLP_MAF_11_1 | -9715.41, -7045.31 (cluster centre) | ledger 12 vs drawing 3 |
| HLP_MAF_17_1 | -9649.17, -6972.15 (cluster centre) | ledger 7 vs drawing 4 |
| HLP_MAF_19_1 | -9576.65, -6937.26 (cluster centre) | ledger count empty vs drawing 2 |
| HLP_MAF_22_1 | -9634.34, -6979.58 | ledger 2, no block; viz `Group1276` here |
| HLP_MAF_24_1 | -9666.78, -6972.71 (cluster centre) | ledger 4 vs drawing 7 |
| HLP_MAF_25_1 … _7 | pair centres (= viz pergola positions) | 14 blocks vs 7 pergolas 9614/4 |
| HLP_MAF_26_1 | -9702.20, -7050.10 | ledger 2 vs drawing 1 |
| HLP_MAF_27_1 | -9661.38, -6976.02 (cluster centre) | ledger 16 vs drawing 19 |
| HLP_MAF_28_1 | -9712.22, -7017.32 (cluster centre) | ledger 14 vs drawing 11; type Аданат vs block Робинзон |
| HLP_MAF_32_1 | -9774.09, -7126.82 | ledger 6 yards vs 1 outline + 4 groups inside |
| HLP_MAF_33_1 | (callout target, to be read) | ledger 1, no block |
| HLP_MAF_37_1 | -9621.70, -6972.16 (cluster centre) | gates: ledger 6 vs 4 inside, fence scope |

## Out of scope (outside ГПЗУ), list only

- Stadium workout Кенгуру: 12 KGTO-008, 13 K-009, 14 K-027, 15 K-013, 16 K-024 (1 each, ~20 m outside; in the viz).
- 20 Велопарковка ВЛП-0022 Деткки: 26 blocks outside (ledger 19); viz Corona proxy near them.
- 29–31 ВП005 / ВП002 / ВП001 obstacle course (outside), 36 Ворота 4.5 (2 blocks outside), 3 gates outside / on the boundary.
- 35 Сварное ограждение PRO H=2.5 (635 m, linework `232_Ог_Внешние_вар2`), 39 Ограждение спортивное H=4 (391 m,
  `232_Огр_СПОРТ`): fence lines.
- 1 ТБО непищ group 2.6 m outside ГПЗУ at (-9770.52, -7131.32) — part of the container yard straddling the boundary.
- Legend samples next to the ledger table (x ≈ -10325…-10340): СО-012, ВСТ 9504_1, 9624_3, Калитка.
