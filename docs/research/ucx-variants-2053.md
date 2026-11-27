# UCX variants `section-boxes` (OKS) and `ground-coarse-faces` (Ground) vs the default (#2053)

Follow-up to the Codex UCX case study (#2042, PR #2047, report section 4, items 1 and 3). The user accepted the
#2047 recommendations and answered Q1 the same day: exceeding the triangle budget is allowed when the form needs it,
so this card measures the fit as well as the budget.

## What was built

Both are variants in the methods catalog ([VARIANTS.md](../methods/ucx-collisions/VARIANTS.md)). The default
`agr ucx` path (`ucx_build.build_main` / `build_ground`) is unchanged. The flag is the variant name of the methods
driver:

```
blender -b --factory-startup --python-exit-code 1 --python tools/methods/ucx/build_variant_blender.py -- \
    <model.fbx> <out.fbx> section-boxes|ground-coarse-faces
```

- **section-boxes** (Codex K9-K13): level bands, then a plan shadow of each band on a 0.25 m grid. Rooms are
  filled when they are enclosed by walls and roofed. A down-facing underside with clear height bins below it can
  admit the exterior flood even when the underside is too small to create a level. Where this opens a previously
  filled column, the upper collision starts at the underside; any pavement stays separate. Cells are grouped by
  height range into greedy rectangles. Each exposed side
  moves to the outermost facade sample. A rectangle that repeats over the bands becomes one taller box. The gap is
  4 mm. There is no triangle budget. The cell grows only when there would be more than 999 pieces (the 001..999
  name limit).
- **ground-coarse-faces** (Codex K16): faces steeper than 15° are treated as slope. All other faces go to the
  shared `build_ground` BSP (large planar prisms, tol 8 cm). Slope faces become prisms on their existing planes,
  merged while the plan union stays convex and the plane stays within 8 cm. A slope prism closer than 3 mm to any
  piece is shrunk and, after 6 rounds, dropped.

## Method

- Cases: the #2042 normalised render meshes `C:/x/ev_2042/run/<case>/model.fbx`. OKS: 01, 02, 03, 04, 10.
  Ground: 06, 11. The "default" and "Codex" rows use the same `ours.fbx` / `codex.fbx` as #2042, measured again
  with the same chain in the first run. Review rework repeated only the variant builds and readbacks on the same
  inputs; the unchanged default and Codex readbacks are reused from the sealed first run.
- Chain (Blender 5.1.2, headless): `tools/blender/ucx_audit.py` (bodies, triangles, [D012] limit, pairs, model->UCX
  `m2u` and exposed UCX->model `u2m`). The #2042 scripts `gapcheck.py` ([D339] bands), `convex_depth.py` (largest
  vertex distance outside its own face planes, counted above 0.1 mm and above 1 mm) and `passages.py` (covered
  through-passage heuristic). New: `u2m_faces.py`, the exposed UCX->model distance split by face direction:
  side = facade (|n_z| < 0.3), up = roof / top, down = underside. Exposed uses the `ucx_audit` contact rule (no other
  piece within 2 cm), 20 000 area-weighted samples.
- Runners: `scripts/run_all.sh` for the first run and `review-r2/ucx-2053-replay-r2.sh` for the review replay.
  Build times are `wall_time_s` from `<out>.variant.json`.

## Results: OKS (Main)

`m2u` = model surface -> UCX (one-sided [D134]; R12 <= 0.3 m pedestrian, R13 <= 1 m). `u2m` = exposed UCX -> model
(diagnostic). Facade / roof / underside use `u2m_faces.py`. The passage column gives blocked and free sampled volumes
separately; for example, "5 blocked / 65 free" is 70 m³ in total, not 5 out of 65.

| Case | Side | Bodies | Tris / limit | Non-convex > 1 mm (> 0.1 mm) | Overlap / < 2 mm | m2u max / p95 m (0-6 m) | u2m p50 / p95 m | Facade p50 / p95 m | Roof p50 m | Underside p50 m | Covered passage blocked / free m³ |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | default | 558 | 6 696 / 7 392 | 0 (0) | 0 / 0 | 0.016 / 0.002 (0.016) | 0.526 / 1.119 | 0.526 / 1.113 | 0.514 | 0.092 | - (none found) |
| 01 | section-boxes | 896 | 10 752 / 7 392 | 0 (0) | 0 / 0 | 0.125 / 0.002 (0.087) | 0.402 / 2.852 | 0.452 / 0.753 | 0.023 | 0.387 | - |
| 01 | Codex | 999 | 13 108 / 7 392 | 0 (1) | 0 / 0 | 0.896 / 0.005 (0.896) | 0.003 / 2.838 | 0.004 / 0.086 | 0.003 | 2.453 | - |
| 02 | default | 562 | 6 744 / 6 891 | 0 (0) | 0 / 0 | 0.009 / 0.002 (0.002) | 0.249 / 0.707 | 0.269 / 0.739 | 0.141 | 0.400 | 1.25 / 0 |
| 02 | section-boxes | 841 | 10 092 / 6 891 | 0 (0) | 0 / 0 | 0.062 / 0.000 (0.038) | 0.135 / 2.835 | 0.153 / 0.441 | 0.002 | 2.150 | 0 / 1.2 |
| 02 | Codex | 467 | 6 888 / 6 891 | 0 (0) | 0 / 0 | 1.058 / 0.013 (1.058) | 0.003 / 3.259 | 0.003 / 0.196 | 0.003 | 2.240 | 0 / 1.2 |
| 03 | default | 158 | 1 896 / 2 558 | 0 (0) | 0 / 0 | 0.031 / 0.000 (0.002) | 0.600 / 1.225 | 0.609 / 1.226 | 0.062 | 0.488 | 5 / 65 |
| 03 | section-boxes | 676 | 8 112 / 2 558 | 0 (0) | 0 / 0 | 0.043 / 0.002 (0.005) | 0.109 / 1.105 | 0.118 / 0.630 | 0.046 | 1.437 | 0 / 70 |
| 03 | Codex | 298 | 4 120 / 2 558 | 0 (0) | 0 / 0 | 2.002 / 0.006 (2.002) | 0.004 / 1.193 | 0.004 / 0.171 | 0.005 | 1.997 | 0 / 70 |
| 04 | default | 285 | 3 420 / 6 408 | 0 (0) | 0 / 0 | 0.009 / 0.000 (0.000) | 0.398 / 0.727 | 0.389 / 0.692 | 0.308 | 0.483 | 0 / 13.8 |
| 04 | section-boxes | 753 | 9 036 / 6 408 | 0 (0) | 0 / 0 | 0.011 / 0.002 (0.002) | 0.188 / 2.707 | 0.228 / 0.528 | 0.023 | 0.927 | 0 / 13.8 |
| 04 | Codex | 776 | 9 670 / 6 408 | 0 (0) | 0 / 0 | 1.566 / 0.003 (0.025) | 0.113 / 3.807 | 0.119 / 0.388 | 0.003 | 3.518 | 0 / 13.8 |
| 10 | default | 329 | 3 948 / 4 377 | 0 (0) | 0 / 0 | 0.008 / 0.001 (0.002) | 0.368 / 0.871 | 0.365 / 0.812 | 0.325 | 0.456 | 0 / 5 |
| 10 | section-boxes | 857 | 10 284 / 4 377 | 0 (0) | 0 / 0 | 0.043 / 0.002 (0.002) | 0.179 / 3.091 | 0.177 / 0.556 | 0.088 | 1.087 | 0 / 5 |
| 10 | Codex | 47 | 564 / 4 377 | 0 (0) | 0 / 0 | 0.989 / 0.208 (0.236) | 0.144 / 2.688 | 0.035 / 0.446 | 0.237 | 1.989 | 0 / 5 |

- Gaps: on every section-boxes row the minimum and p50 are 4.0 / 4.0 mm, the same as the default (Codex 2.97-6.75 /
  6.0-8.48 mm). Section-boxes has 0 pairs under 2 mm and 0 overlaps.
- Build time of section-boxes: 10–122 s per case (01 122 s, 04 78 s: the cell grew). The default took 37–371 s in
  #2042.
- Cell: 0.25 m on 03, 0.31 m on 02, 04 and 10, and 0.76 m on 01 to stay under 999 pieces (01 at 0.25 m
  would have 2 299 pieces). Case 01 has the loosest section-boxes facade (0.452 m) and the
  largest m2u (12.5 cm, still inside R12 / R13).
- The overall `u2m` p95 also includes undersides, which can be far from the render mesh. Filled rooms stand on
  their lowest sample (for example a ground-floor wall foot). Their bottoms can be far from a model that has no
  ground slab. Codex undersides are as far: 2.0-3.5 m p50.

## Results: Ground

R11: model -> UCX <= 10 cm.

| Case | Side | Bodies | Tris / limit | Non-convex > 1 mm (> 0.1 mm) | Overlap / < 2 mm | Gap min / p50 mm | m2u max / p95 m | m2u <= 1 cm | u2m p50 / p95 m | Top p50 m |
|---|---|---|---|---|---|---|---|---|---|---|
| 06 | default | 417 | 4 772 / 15 000 | 0 (0) | 0 / 0 | 4.0 / 4.0 | 0.076 / 0.042 | 72.7 % | 0.060 / 2.802 | 0.012 |
| 06 | ground-coarse-faces | 332 | 4 024 / 15 000 | 0 (0) | 0 / 0 | 3.07 / 4.0 | 0.087 / 0.042 | 71.8 % | 0.063 / 2.926 | 0.013 |
| 06 | Codex | 204 | 1 808 / 15 000 | 0 (0) | 0 / 0 | 6.62 / 11.35 | 0.072 / 0.017 | 86.6 % | 0.020 / 4.429 | 0.007 |
| 11 | default | 833 | 9 948 / 15 000 | 0 (0) | 0 / 0 | 3.99 / 4.0 | 1.275 / 0.029 | 84.1 % | 0.077 / 5.335 | 0.012 |
| 11 | ground-coarse-faces | 837 | 10 008 / 15 000 | 0 (0) | 0 / 0 | 3.99 / 4.0 | 1.275 / 0.029 | 84.2 % | 0.057 / 5.391 | 0.012 |
| 11 | Codex | 598 | 7 410 / 15 000 | 3 (14) | 1 / 14 | 0.15 / 4.65 | 2.098 / 0.053 | 66.7 % | 1.602 / 10.694 | 0.013 |

- 06: 382 of 2 440 up-facing faces are slope faces (> 15°). The BSP gives 221 prisms and the slope 120 clusters.
  Nine clusters were dropped by the clearance pass, representing 0.0166 m² of original projected triangle area
  (`dropped_plan_area_m2`), not uncovered Ground. Largest extra inset 7.1 mm; build time 4.1 s.
- 11: only three faces are steeper than 15° (834 BSP + 3 slope prisms). The default has 833 pieces; both our
  methods exceed R11 on this case (1.275 m maximum). No slope clusters were dropped.
- 06 BSP part and default differ (221 + 111 vs 417) because the BSP no longer splits the slope down to 0.5 m.
- For completeness, the raw covered-passage scan found 0 / 0 m³ blocked / free on all 06 sides. On 11, both
  our variant and default give 2 284.75 / 10 058.5 m³, and Codex gives 12 326.62 / 16.6 m³. The upward-ray
  heuristic can count space below terrain itself, so these Ground values are diagnostic, not walkability evidence.

## Repair attempts inside the card (COORDINATION_RULES 56)

1. **section-boxes, pillars.** The first build took each cell's whole z range. A cell with a pavement and a canopy
   above it became one pillar (case 10: a 1 m-thick box 3.4 m from the model). Fix: a cell keeps its lowest run
   of occupied height bins and, separately, the rest. Plan "walls" use only the middle bins, so a pavement does not
   enclose anything. Regression test: `test_section_boxes_canopy_over_pavement_is_not_a_pillar`.
2. **section-boxes, 999 pieces.** Case 01 at 0.25 m gave 2 246 pieces (VariantError). Fix: the cell grows ×1.25
   until there are at most 999 pieces (01: 0.76 m, 04: 0.31 m).
3. **section-boxes, facade trim (rejected).** I tried a Codex-like trim: each exposed side goes to the median of
   the rectangle's facade depth map, and projections may stand out by up to 0.25 m (< 6 m) / 0.5 m. The facade p50
   stayed at 0.18 m on case 10 and went from 0.165 to 0.170 m on case 03 (numpy diagnostic `diag_sides.py`). The code was not kept.
4. **ground-coarse-faces, pure face clusters (rejected).** Clustering every face with convex plan unions and no
   new cut lines gave 543 pieces / 6 832 tris on 06 (default 417) and 1 716 pieces on 11 (> 999). With a second
   pass that merges whole clusters: 447 / 1 681. Hence the hybrid: the BSP on flat parts, faces on slopes.
5. **ground-coarse-faces, overlaps.** The first hybrid build had 4 overlapping pairs (penetration up to 3.1 mm) and
   3 pairs under 2 mm on 06, because BSP prisms reach over the slope edge. Fix: shrink, then drop (above).
   Regression test: `test_ground_coarse_faces_never_overlaps_the_bsp_part`.
6. **section-boxes, covered arch (review R1).** An underside below the level-area threshold blocked the plan flood;
   the 4 × 15 × 5 m arch blocked all 27 probes. Ignoring the elevated barrier alone freed the path but left the
   middle of the bridge solid hollow. The repair keeps the previously filled upper volume above the underside and
   leaves the exterior below it free. `test_section_boxes_keep_low_share_covered_arch_open`: 0/27 blocked in each
   of four synthetic arches (three widths/depths, plus the original arch with pavement); piers and bridge remain covered.

## Limits of this measurement

- Codex rows are Codex's delivered UCX. Their m2u maxima of 0.9-2.1 m were not checked by eye (see #2047).
- Facade p50 compares exposed UCX sides with the render mesh. It also counts sides in front of balconies and
  loggias. On a 55 m × 6.6 m face of case 10, most model samples within the face's extent are 0.1-2 m behind it.
  That is relief of the model, not a grid step: 1 558 of 1 559 side faces are pulled to samples
  (`diag_sides.py`).
- No Unreal, no AGR Checker, no visual acceptance. The renders are review aids only.
- Section-boxes has no parapet rule (K12), no semantic split of balconies (K11) and no stair rule (R14).
- Passage results come from a sampled heuristic, not a walking test or a guarantee that any arch stays open.
  Inconsistent winding, steep undersides, insufficient clearance in the height bins or mouths narrower than the
  plan-grid closing can still hide a passage, especially after cell growth. Check required passages separately (R01).

Evidence: `G:/Мой диск/AGR-evidence/2053-ucx-variants/`. The original `SHA256SUMS.txt` binds the 184 files of the
first run (including the default and Codex baselines); `review-r2/` has a separate seal for the fresh variant
readbacks, scripts, logs and renders. `review-r2/summary.json` pins the build code, input and output FBX hashes.

## Отчёт для Артёма

**Коротко.** Оба варианта сделаны и измерены на тех же кейсах Кодекса. Дефолт не трогали, варианты включаются
именем.

- **section-boxes лучше нашего дефолта по медиане прилегания фасада и кровли на всех пяти ОКС.**
  - Фасад, медиана: 0,12–0,45 м против 0,27–0,61 м. p95 улучшился также на всех пяти кейсах.
  - Кровля, медиана: 2–88 мм против 62–514 мм.
  - В замере крытых проходов 02 — 0 м³ перекрыто, 1,2 м³ свободно (дефолт перекрывает 1,25 м³), 03 — 0 м³
    перекрыто, 70 м³ свободно (дефолт перекрывает 5 м³). На контрольной арке 4 × 15 × 5 м: 0 из 27 точек
    перекрыты после исправления, 27 из 27 до него.
- **Цена section-boxes.**
  - Бюджет [D012] превышен во всех пяти кейсах, на 03 в 3,17 раза (8 112 при лимите 2 558).
  - Тел 676–896 против 158–562.
  - До точности Кодекса на фасаде (3–4 мм) мы не дошли.
- **ground-coarse-faces даёт мало.** На откосе 06 — 332 тела / 4 024 tris против 417 / 4 772, максимум 8,7 см
  против 7,6 см (порог 10 см). На 11 откосов почти нет; вариант почти не меняет результат и не устраняет
  превышение порога 10 см (максимум 1,275 м у обоих).

### ОКС: section-boxes против дефолта

1. **Фасад (медиана расстояния от боковой грани UCX до модели).** Лучше во всех пяти кейсах:
   01 — 0,45 против 0,53 м; 02 — 0,15 против 0,27; 03 — 0,12 против 0,61; 04 — 0,23 против 0,39; 10 — 0,18 против
   0,37. У Кодекса 0,003–0,12 м.
2. **Кровля (медиана).** Лучше во всех пяти: 2–88 мм против 62–514 мм. У Кодекса 3–237 мм.
3. **Покрытие (модель -> UCX).** Максимум 1,1–6,2 см. Исключение — 01: 12,5 см, там ячейку пришлось укрупнить
   до 0,76 м из-за лимита 999 тел. Это в пределах R12 (0,3 м) и R13 (1 м). У дефолта 0,8–3,1 см, у Кодекса
   0,9–2,0 м.
4. **Чистота.** 0 нарушений выпуклости при допуске 1 мм, 0 пересечений, минимальный зазор 4,0 мм. Как у дефолта.
5. **Проходы.** Улучшение относительно дефолта измерили на 02 и 03. Это не гарантия для любой арки: метод
   зависит от направления граней, высоты просвета и размера ячеек. Обязательные проходы проверять отдельно.
6. **Цена.**
   - Треугольники над бюджетом [D012]: 01 — 10 752 / 7 392, 02 — 10 092 / 6 891, 03 — 8 112 / 2 558,
     04 — 9 036 / 6 408, 10 — 10 284 / 4 377.
   - Тел больше: 676–896. Ячейка выросла в четырёх кейсах из-за лимита имён 999.
   - Общий u2m p95 — 1,1–3,1 м против 0,7–1,2 м: он учитывает и нижние грани заполненных помещений без
     плиты пола. У Кодекса расстояние до нижних граней — 2,0–3,5 м по медиане.
7. **Чего нет.**
   - Правила парапета (K12) и отдельных тел для балконов (K11).
   - Медианная «подрезка» фасада, как у Кодекса. Я её попробовал, выигрыша нет (10: 0,18 м осталось 0,18 м;
     03: 0,165 -> 0,170 м), поэтому не оставил.
   - Разрыв с Кодексом на фасаде (мм против дециметров) идёт от рельефа модели: лоджии, балконы, пилястры. Кодекс
     ставит грань по плоскости стены и позволяет выступам торчать до 0,9–2,0 м. Мы закрываем всё.

### Ground: ground-coarse-faces против дефолта

- **06 (откос).** Тел на 20 % меньше: 332 против 417. Треугольников 4 024 против 4 772. Максимум отклонения
  8,7 против 7,6 см, p95 одинаковый (4,2 см). У Кодекса 204 тела / 1 808 tris при 7,2 см.
- **11.** Откосов почти нет (3 грани круче 15°). Тел 837 против 833, максимум одинаковый — 1,275 м.
- **Почему мало.** Без новых линий разреза «существующие грани» дробятся. Чисто граневый вариант давал 1 716 тел
  на 11 (больше лимита 999) и 543 на 06 (хуже дефолта). Поэтому на пологих частях остался наш BSP.

### Рекомендация (решение за вами)

1. **ОКС: сделать section-boxes дефолтом там, где допускается превышение бюджета (ваш ответ Q1).** Он лучше
   дефолта по медиане прилегания фасада и кровли во всех пяти кейсах; на 02 и 03 оставил больше свободного
   места в измеренных проходах. Оставить `kernel-boxes` для строгого бюджета. Перед переключением в `agr ucx`
   проверить обязательные проходы на целевых моделях; переключение — отдельная задача после вашего «да».
2. **Ground: дефолт не менять.** Выигрыш есть только на откосах (−20 % тел на 06), максимум отклонения при этом
   растёт на 1,1 см. Вариант оставить в каталоге для рельефа с большими откосами.
3. **Следующий шаг к точности Кодекса на фасаде** — правила K11/K12: отдельные тела для балконов и выступов,
   грань по плоскости стены с допуском R12/R13. Это отдельная задача, если нужна.

### Вопросы

- **Q1 (только для будущего переключения).** На 03 вышло 3,17× от [D012]. Нужен ли отдельный эксплуатационный
  потолок, при котором сохраняем `kernel-boxes`? Разрешение превысить бюджет ради формы в этом исследовании уже учтено.
- **Q2.** Допускаем ли, как у Кодекса, выступы модели за UCX в пределах R12/R13 ради посадки на плоскость стены?
  Сейчас оба метода ориентированы на покрытие выступов, а не на плоскость за ними.
