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
  filled when they are enclosed by walls and roofed. Courtyards and through-passages stay open. A canopy over a
  pavement keeps the space below it free. Cells are grouped by height range into greedy rectangles. Each exposed side
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
  with the same chain so that all rows are comparable.
- Chain (Blender 5.1.2, headless): `tools/blender/ucx_audit.py` (bodies, triangles, [D012] limit, pairs, model->UCX
  `m2u` and exposed UCX->model `u2m`). The #2042 scripts `gapcheck.py` ([D339] bands), `convex_depth.py` (largest
  vertex distance outside its own face planes, counted above 0.1 mm and above 1 mm) and `passages.py` (covered
  through-passage heuristic). New: `u2m_faces.py`, the exposed UCX->model distance split by face direction:
  side = facade (|n_z| < 0.3), up = roof / top, down = underside. Exposed uses the `ucx_audit` contact rule (no other
  piece within 2 cm), 20 000 area-weighted samples.
- Runner: `scripts/run_all.sh` in the evidence folder. Build times are `wall_time_s` from `<out>.variant.json`.

## Results: OKS (Main)

`m2u` = model surface -> UCX (one-sided [D134]; R12 <= 0.3 m pedestrian, R13 <= 1 m). `u2m` = exposed UCX -> model
(diagnostic). Facade / roof / underside are the p50 of `u2m_faces.py`.

| Case | Side | Bodies | Tris / limit | Non-convex > 1 mm (> 0.1 mm) | Overlap / < 2 mm | m2u max / p95 m (0-6 m) | u2m p50 / p95 m | Facade p50 / p95 m | Roof p50 m | Underside p50 m | Covered passage blocked m3 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | default | 558 | 6 696 / 7 392 | 0 (0) | 0 / 0 | 0.016 / 0.002 (0.016) | 0.526 / 1.119 | 0.526 / 1.113 | 0.514 | 0.092 | - (none found) |
| 01 | section-boxes | 874 | 10 488 / 7 392 | 0 (0) | 0 / 0 | 0.125 / 0.002 (0.079) | 0.425 / 2.866 | 0.453 / 0.759 | 0.023 | 0.799 | - |
| 01 | Codex | 999 | 13 108 / 7 392 | 0 (1) | 0 / 0 | 0.896 / 0.005 (0.896) | 0.003 / 2.838 | 0.004 / 0.086 | 0.003 | 2.453 | - |
| 02 | default | 562 | 6 744 / 6 891 | 0 (0) | 0 / 0 | 0.009 / 0.002 (0.002) | 0.249 / 0.707 | 0.269 / 0.739 | 0.141 | 0.400 | 1.25 (all) |
| 02 | section-boxes | 886 | 10 632 / 6 891 | 0 (0) | 0 / 0 | 0.041 / 0.002 (0.011) | 0.155 / 2.971 | 0.180 / 0.477 | 0.002 | 1.713 | 0 of 1.2 |
| 02 | Codex | 467 | 6 888 / 6 891 | 0 (0) | 0 / 0 | 1.058 / 0.013 (1.058) | 0.003 / 3.259 | 0.003 / 0.196 | 0.003 | 2.240 | 0 of 1.2 |
| 03 | default | 158 | 1 896 / 2 558 | 0 (0) | 0 / 0 | 0.031 / 0.000 (0.002) | 0.600 / 1.225 | 0.609 / 1.226 | 0.062 | 0.488 | 5 of 65 |
| 03 | section-boxes | 628 | 7 536 / 2 558 | 0 (0) | 0 / 0 | 0.043 / 0.002 (0.002) | 0.145 / 1.594 | 0.154 / 1.471 | 0.046 | 1.519 | 0 of 70 |
| 03 | Codex | 298 | 4 120 / 2 558 | 0 (0) | 0 / 0 | 2.002 / 0.006 (2.002) | 0.004 / 1.193 | 0.004 / 0.171 | 0.005 | 1.997 | 0 of 70 |
| 04 | default | 285 | 3 420 / 6 408 | 0 (0) | 0 / 0 | 0.009 / 0.000 (0.000) | 0.398 / 0.727 | 0.389 / 0.692 | 0.308 | 0.483 | 0 of 13.8 |
| 04 | section-boxes | 505 | 6 060 / 6 408 | 0 (0) | 0 / 0 | 0.007 / 0.002 (0.002) | 0.193 / 1.737 | 0.248 / 0.712 | 0.021 | 0.002 | 0 of 13.8 |
| 04 | Codex | 776 | 9 670 / 6 408 | 0 (0) | 0 / 0 | 1.566 / 0.003 (0.025) | 0.113 / 3.807 | 0.119 / 0.388 | 0.003 | 3.518 | 0 of 13.8 |
| 10 | default | 329 | 3 948 / 4 377 | 0 (0) | 0 / 0 | 0.008 / 0.001 (0.002) | 0.368 / 0.871 | 0.365 / 0.812 | 0.325 | 0.456 | 0 of 5 |
| 10 | section-boxes | 705 | 8 460 / 4 377 | 0 (0) | 0 / 0 | 0.017 / 0.002 (0.017) | 0.181 / 3.056 | 0.172 / 0.557 | 0.027 | 1.115 | 0 of 5 |
| 10 | Codex | 47 | 564 / 4 377 | 0 (0) | 0 / 0 | 0.989 / 0.208 (0.236) | 0.144 / 2.688 | 0.035 / 0.446 | 0.237 | 1.989 | 0 of 5 |

- Gaps: on every section-boxes row the minimum and p50 are 4.0 / 4.0 mm, the same as the default (Codex 2.97-6.75 /
  6.0-8.48 mm). Section-boxes has 0 pairs under 2 mm and 0 overlaps.
- Build time of section-boxes: 8-107 s per case (01 107 s, 04 91 s: the cell grew). The default took 37-371 s in
  #2042.
- Cell: 0.25 m on 02, 03 and 10. 04 needed 0.31 m and 01 needed 0.76 m to stay under 999 pieces (01 at 0.25 m
  would have 2 246 pieces). The cell growth is why 01 has the loosest section-boxes facade (0.453 m) and the
  largest m2u (12.5 cm, still inside R12 / R13).
- The underside column explains why the overall `u2m` p95 is 1.6-3.1 m for section-boxes. Filled rooms stand on
  their lowest sample (for example a ground-floor wall foot). Their bottoms are then far from a model that has no
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

- 06: 382 of 2 440 up-facing faces are slope faces (> 15°). The BSP gives 221 prisms, the slope gives 120
  clusters, and 9 clusters were dropped because they lay over BSP prisms. The largest extra slope inset was 7.1 mm.
  Build time 3.9 s.
- 11: only 3 faces are steeper than 15°, so this is the default plus 3 prisms (834 BSP + 3).
- 06 BSP part and default differ (221 + 111 vs 417) because the BSP no longer splits the slope down to 0.5 m.

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

## Limits of this measurement

- Codex rows are Codex's delivered UCX. Their m2u maxima of 0.9-2.1 m were not checked by eye (see #2047).
- Facade p50 compares exposed UCX sides with the render mesh. It also counts sides in front of balconies and
  loggias. On a 55 m × 6.6 m face of case 10, most model samples within the face's extent are 0.1-2 m behind it.
  That is relief of the model, not a grid step: 1 558 of 1 559 side faces are pulled to samples
  (`diag_sides.py`).
- No Unreal, no AGR Checker, no visual acceptance. The renders are review aids only.
- Section-boxes has no parapet rule (K12), no semantic split of balconies (K11) and no stair rule (R14).

Evidence: `G:/Мой диск/AGR-evidence/2053-ucx-variants/`. It holds per-case JSON, build logs, `summary.json`,
`tables.md`, renders (`png/`, the variant plus the #2042 default and Codex renders), scripts and `SHA256SUMS.txt`
(184 files). Working FBX: `C:/x/ev_2053/<case>/{sec,gcf,ours,codex}.fbx`.

## Отчёт для Артёма

**Коротко.** Оба варианта сделаны и измерены на тех же кейсах Кодекса. Дефолт не трогали, варианты включаются
именем.

- **section-boxes лучше нашего дефолта по посадке на всех пяти ОКС.**
  - Фасад, медиана: 0,15–0,45 м против 0,27–0,61 м.
  - Кровля, медиана: 2–46 мм против 62–514 мм.
  - Крытые проходы не перекрывает: 02 — 0 из 1,2 м³ (дефолт перекрывает 1,25), 03 — 0 из 70 м³ (дефолт 5).
- **Цена section-boxes.**
  - Бюджет [D012] превышен в 4 из 5 кейсов, на 03 в 2,9 раза (7 536 при лимите 2 558).
  - Тел 505–886 против 158–562.
  - До точности Кодекса на фасаде (3–4 мм) мы не дошли.
- **ground-coarse-faces даёт мало.** На откосе 06 — 332 тела / 4 024 tris против 417 / 4 772, максимум 8,7 см
  против 7,6 см (порог 10 см). На 11 откосов почти нет, поэтому результат равен дефолту.

### ОКС: section-boxes против дефолта

1. **Фасад (медиана расстояния от боковой грани UCX до модели).** Лучше во всех пяти кейсах:
   01 — 0,45 против 0,53 м; 02 — 0,18 против 0,27; 03 — 0,15 против 0,61; 04 — 0,25 против 0,39; 10 — 0,17 против
   0,37. У Кодекса 0,003–0,12 м.
2. **Кровля (медиана).** Лучше во всех пяти: 2–46 мм против 62–514 мм. У Кодекса 3–237 мм.
3. **Покрытие (модель -> UCX).** Максимум 0,7–4,3 см. Исключение — 01: 12,5 см, там ячейку пришлось укрупнить
   до 0,76 м из-за лимита 999 тел. Это в пределах R12 (0,3 м) и R13 (1 м). У дефолта 0,8–3,1 см, у Кодекса
   0,9–2,0 м.
4. **Чистота.** 0 невыпуклых, 0 пересечений, зазор ровно 4 мм. Как у дефолта.
5. **Проходы.** Крытые проходы не перекрывает (см. «Коротко»).
6. **Цена.**
   - Треугольники над бюджетом [D012]: 01 — 10 488 / 7 392, 02 — 10 632 / 6 891, 03 — 7 536 / 2 558,
     10 — 8 460 / 4 377. В бюджет уложился только 04 (6 060 / 6 408).
   - Тел больше: 505–886, на 01 и 04 упёрлись в лимит имён 999.
   - Нижние грани заполненных помещений стоят далеко от модели без плиты пола: общий u2m p95 1,6–3,1 м против
     0,7–1,2 м. Для игрока это не поверхность столкновения. У Кодекса так же: 2,0–3,5 м по медиане.
7. **Чего нет.**
   - Правила парапета (K12) и отдельных тел для балконов (K11).
   - Медианная «подрезка» фасада, как у Кодекса. Я её попробовал, выигрыша нет (10: 0,18 м осталось 0,18 м;
     03: 0,165 -> 0,170 м), поэтому не оставил.
   - Разрыв с Кодексом на фасаде (мм против дециметров) идёт от рельефа модели: лоджии, балконы, пилястры. Кодекс
     ставит грань по плоскости стены и позволяет выступам торчать до 0,9–2,0 м. Мы закрываем всё.

### Ground: ground-coarse-faces против дефолта

- **06 (откос).** Тел на 20 % меньше: 332 против 417. Треугольников 4 024 против 4 772. Максимум отклонения
  8,7 против 7,6 см, p95 одинаковый (4,2 см). У Кодекса 204 тела / 1 808 tris при 7,2 см.
- **11.** Откосов почти нет (3 грани круче 15°), поэтому результат равен дефолту.
- **Почему мало.** Без новых линий разреза «существующие грани» дробятся. Чисто граневый вариант давал 1 716 тел
  на 11 (больше лимита 999) и 543 на 06 (хуже дефолта). Поэтому на пологих частях остался наш BSP.

### Рекомендация (решение за вами)

1. **ОКС: сделать section-boxes дефолтом там, где допускается превышение бюджета (ваш ответ Q1).** Он лучше
   дефолта по фасаду, кровле и проходам во всех пяти кейсах, при том же покрытии и той же чистоте. kernel-boxes
   оставить запасным вариантом для случая «бюджет строго». Переключение дефолта в `agr ucx` — отдельная задача
   после вашего «да».
2. **Ground: дефолт не менять.** Выигрыш есть только на откосах (−20 % тел на 06), максимум отклонения при этом
   растёт на 1,1 см. Вариант оставить в каталоге для рельефа с большими откосами.
3. **Следующий шаг к точности Кодекса на фасаде** — правила K11/K12: отдельные тела для балконов и выступов,
   грань по плоскости стены с допуском R12/R13. Это отдельная задача, если нужна.

### Вопросы

- **Q1.** Дефолт ОКС переключаем на section-boxes с превышением бюджета до 2,9 раза (03)? Или ставим потолок,
  например 2× [D012], и укрупняем ячейку до него?
- **Q2.** Допускаем ли, как у Кодекса, выступы модели за UCX в пределах R12/R13 ради посадки на плоскость стены?
  Сейчас и дефолт, и section-boxes закрывают всё.
