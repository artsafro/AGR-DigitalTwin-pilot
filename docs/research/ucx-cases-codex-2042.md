# Codex UCX cases (22) vs our UCX pipeline (#2042)

OBSERVE research. Nothing in the UCX cores, rules or jobs changed. Sources were read from copies only; no
scene is committed. Evidence: `G:/Мой диск/AGR-evidence/ucx-cases-codex-v001/` (scripts, per-case JSON,
renders, side-by-side sheets, `SHA256SUMS.txt`, 173 files); working copies and normalised FBX:
`C:/x/ev_2042/run/<case>/`.

## Inputs

| Item | Value |
|---|---|
| Original | `G:/Мой диск/AGR-evidence/UCX_Cases.zip`, SHA-256 `96025784cabb1c2dd62edf66b350c9dda4e5fe831fa5006c56447ed67365c991` |
| Unpacked copy | `C:/x/ucx-cases-codex/src/UCX_Cases/` (README, catalog.json, knowledge/*.md, 22 case folders) |
| Scenes | 10 .blend (Blender 5.2), 2 .fbx, 2 .max (05, 09: need Max, not opened) |
| Our side | main `7c077ed0`: `agr ucx` (build + readback + `ucx10_core` gap census [D339] + V010), `tools/blender/ucx_audit.py` |
| DCC | Blender 5.1.2 headless (`--factory-startup`); no Max |

## Method

1. `census.py`: open each scene, list meshes, UCX objects, triangles, collections, units (all scenes: metres, scale 1).
2. `normalise.py`: the render target renamed `SM_C<case>_<Main|Ground>`, every UCX object split into loose
   parts (one part = one body) and renamed `UCX_SM_C<case>_<role>_NNN`; the scene is shifted so the model plan
   centre is at 0,0 and the model bottom at z=0 (metrics unchanged; height bands become relative). Two FBX:
   `codex.fbx` (model + Codex UCX) and `model.fbx` (model only). 07/08: the hidden reference `UCX_ADD` is excluded.
3. Codex UCX measured with OUR checks: `tools/blender/ucx_audit.py` (kinds, budget, pairs, model -> UCX
   coverage 20 000 samples, exposed UCX -> model), `ucx_command.gap_check` (the `agr ucx` step 3: `ucx10_core.plan`
   + `pair_census` bands, gap 2 mm), `convex_depth.py` (how far a vertex lies outside an own face plane).
4. Ours: `agr ucx model.fbx ours.fbx Main|Ground` (defaults), then the same audit on `ours.fbx`.
5. `passages.py` (heuristic, 0.5 m grid, 0-5 m above the model bottom): a point is in a covered
   through-passage when the ray up hits the model and an opposite pair of horizontal rays both leave it.
6. `render.py`: UCX-only renders (random colour per body), sheets Codex | ours per case.

## 1. Census

Status from catalog.json. Etalon = accepted by Artem (01-08); method = 09-12; history = 13-22.

| ID | Object / operation | Method | DCC | Version | Status | Bodies / tris (Codex) | Render mesh in scene | What Artem accepted |
|---|---|---|---|---|---|---|---|---|
| 01 | Garibaldi K1 | OKS | Blender | v010 | etalon | 999 / 13 108 | `SM_Garibaldi_22_001_Main` 147 826 tris | geometry v010 (504 facade baskets kept, 24 roof heads removed) |
| 02 | Garibaldi K2 | OKS | Blender | user v015 | etalon | 467 / 6 888 | `..._002_Main` 137 803 | user-finished v015, budget 6 891 |
| 03 | Garibaldi K3 | OKS | Blender | full-v014 | etalon | 298 bodies in ONE object / 4 120 | `..._003_Main` 51 146 (hidden) | v014 after joint fixes, min gap 6.753 mm |
| 04 | Domashniy K3, OKS 001 | OKS | Blender + FBX | v007 | etalon | 776 / 9 670 | `SM_Doneckaya_Vl_30_001_Main` 128 142 | v007 profile to first belt, 23 baskets, 135 mm pockets removed |
| 05 | Mnevniki 3 contour | Ground | Max | contour-v007 | etalon | 719 / 8 670 (card) | - | contour near building only (2026-11-06) |
| 06 | Geo_019 steep slope | Ground | Blender | SLOPE_REFINED | etalon | 204 / 1 808 | `SM_Ground_Coordinate001` 2 857 (hidden) | slope shape (2026-10-08) |
| 07 | Geo_004 arch insertion | arch | Blender | v3 pilot | approved pilot | 17 / 212 (+ frozen main 341 parts) | none (main collision only) | economy of this opening's split |
| 08 | Geo_004 round arch | arch | Blender | v4 pilot | approved pilot | 38 / 602 (+ main 358 parts) | none | no intersections / broken parts seen |
| 09 | Mnevniki 3 Ground | Ground | Max | full_v004 | method | 690 / 8 756 (card) | - | method 2026-11-04 after his finishing |
| 10 | Polyani orthogonal LP body | OKS | Blender + FBX | UCX_OKS_001 v002 | method | 47 / 564 | `SM_Polyani_ZU_50_D_20_003` 87 524 | method narrowly (2026-10-29) |
| 11 | Geo_007 author's Ground | Ground | Blender | GROUND_UCX_DONE | method (Artem's own scene) | 598 / 7 410 | `SM_Garibaldi_22_Ground` 9 353 | his own economical split |
| 12 | Geo_017 tower with pipes | details | Blender | COMPLETED_FIX | method (author fix) | 66 / 3 968 | none | author's split of 3 elbows into 6 bodies |
| 13 | Mnevniki 3 doors | Ground | - | doors-v008 | history | 737 / 8 886 (card) | - | visual review pending |
| 14 | Khodynka 4 | Ground | - | v002 | history | 395 / 6 340 | - | reopened after joint remark |
| 15 | Desnarechye | Ground | - | v001 | history | 767 / 9 084 | - | not reviewed |
| 16 | OKS glass tower | details | - | OKS_UCX_009 | history | 812 / - | - | not recorded |
| 17 | Geo_005 garage doors | arch | - | v5 pilot | history | 46 / - | - | not recorded |
| 18 | Geo_008 Ground check | Ground | - | WORKING | history | - | - | unsolved node |
| 19 | Geo_016 stairs + rails | details | - | COMPLETED_REVIEW | history | 211 (54 new) / - | - | local checks only |
| 20 | Geo_018 building | OKS | - | COMPLETED_REVIEW | history | 43 / 1 156 | - | not confirmed |
| 21 | Geo_021 KPP | details | - | REVIEW_v2 | history | 8 / 96 | - | not confirmed |
| 22 | Geo_029 optimisation | details | - | Codex_v001 | history | 409 / 7 948 (from 10 828) | - | not confirmed |

None of the 22 cards claims AGR Checker or Unreal import (every card lists them as open).

## 2. Knowledge diff (Codex knowledge/*.md vs our main)

SAME = our rule says the same; NEW = Codex has it, we do not; CONFLICT = both quoted, nothing adopted;
N/A = outside our scope.

| # | Codex rule (source) | Ours | Class |
|---|---|---|---|
| K1 | Convex, closed, no holes, no material slots, named by mask (requirements 1) | R06-R08, V010/V012 | SAME |
| K2 | Targets: Ground, existing OKS, every OKS incl. arches, courtyards, projections; no UCX for canopies/fences/railings <= 5 cm (requirements 2) | R01-R04; [D298]: MAF fences and canopies get no UCX at any thickness | SAME (ours stricter by D298) |
| K3 | Own UCX per FBX except lighting (requirements 3) | R05 | SAME |
| K4 | Gap: requirements 4 "рекомендуется 0,02 - 1 см"; oks.md "рекомендуемый зазор 0,2–10 мм (последний пользовательский диапазон 4–5…10 мм, номинал 6 мм — технический выбор)" | [D098] "collision-piece gap 2 mm - 1 cm inclusive (reg p.36 §13.4 is a typo)"; [D162] SINTEZ too-close < 0.2 mm as a separate finding; [D339] bands report only | CONFLICT in wording (Codex floor 0.2 mm vs ours 2 mm); the practice (4-10 mm, nominal 6 mm) lies inside D098. Not adopted |
| K5 | Tolerances 10 cm Ground / 30 cm pedestrian OKS / 1 m other OKS (requirements 5) | R11-R13 same numbers | SAME |
| K6 | ground.md checks: "Отклонение поверхности в обе стороны, внешний контур и отдельная проверка узких/почти вертикальных участков" | [D134] "one-sided, model surface -> UCX ... UCX -> model distance is diagnostic only" | CONFLICT (two-sided vs one-sided). Not adopted; oks.md (vertices of the source outside tolerance) is one-sided = SAME |
| K7 | Entrance stairs = truncated pyramid (requirements 6) | R14 | SAME; but details.md / case 19 build "простые наклонные тела маршей" - see question Q3 |
| K8 | Budget: 15 000 if < 50 000, else ceil(n x 0.05); +100 000 extra when the model hits its limit (requirements 7-8) | [D012] min(ceil 5 %, 100 000), n = FBX model triangles excl. UCX | SAME text; Codex budgets 01/03 against the final HP composition, not the scene mesh - see Q1 |
| K9 | OKS: building's own axes from the edge-direction histogram, then refine by constant wall coordinate (oks 2) | `ucx_build` rotates into the dominant facade frame | SAME idea |
| K10 | OKS: depth maps of 4 facades + roof height map at 0.25 m; window "false dips" removed by min->max filter ~3 m (1st floor ~1.25 m) (oks 3) | none (we voxelise the surface) | NEW |
| K11 | OKS: plan/height steps -> large bodies; projections > tolerance (balconies, columns, roof equipment > ~1 m) -> own bodies; cut-outs > tolerance in the pedestrian zone (entrances, arcades, passages) -> cut the lower belt (oks 4) | none (greedy merge of voxels, no semantics) | NEW |
| K12 | Body top chosen so the parapet stands out by no more than the tolerance (oks 5) | none | NEW |
| K13 | Boxes on a common grid, each shrunk by half the gap -> planned joints get exactly the nominal gap (oks 6) | `ucx_build` shrinks every box by gap/2 | SAME |
| K14 | Save, reopen, check; group source vertices outside tolerance by place and explain each group; coverage check is mandatory (oks 7, "Ошибка агента ... найдено только проверкой покрытия") | `agr ucx` readback + `ucx_audit` coverage (numbers, no grouping) | SAME (check) / NEW (grouping by place) |
| K15 | FBX model + UCX and reverse import (oks 8) | `agr ucx` readback step | SAME |
| K16 | Ground: large simple volumes on flat parts; keep existing faces and real break lines on slopes (ground "Основной принцип") | `build_ground`: BSP prisms, steep-face traces and layer edges as cut lines, leaf cut to tol 10 cm | Partly SAME; "reuse existing faces on slopes" NEW |
| K17 | One object with several elements: split into elements, each element its own body (ground) | one piece per object (V010/V012) | SAME; note Codex's own accepted 03 is ONE object with 298 bodies (Q4) |
| K18 | Pilot a representative fragment first (flat + slope + break + passage), before/after from the same angle with bodies and tris, then spread (ground 2) | none in the UCX route | NEW (process) |
| K19 | Inset in verified units; gap ~ sum of two insets; measure at sharp corners; unitless "0.1" never carried over (ground 5) | [D339] measured SAT gaps in bands | SAME |
| K20 | Skirts down to an agreed Z + cap; check normals, degenerate faces, positive volume, convexity (ground 6) | ground prisms closed by construction | SAME |
| K21 | Joint heights at the middle of a shared edge and at T-joints (ground 8) | none | NEW |
| K22 | Free passages: separate floor and upper volume under an overpass, check several XY/Z sections (ground 9; arch 4 "Проверьте проход с обеих сторон") | R01 "passage preservation" = none (L2 gap); `ucx_build` keeps passages wider than one cell | NEW |
| K23 | Separate statuses: visual acceptance, local calc, AGR Checker, FBX, Unreal (ground) | evidence ladder (WORKFLOW) | SAME |
| K24 | Ground v004 inset 8 mm -> 16 mm gap above "до 10 мм", named a known limit, not a parameter (ground) | D098 band; D339 reports 10-100 mm | SAME |
| K25 | Arch insertion: freeze main collision, sections at the real intersection, subtract main, cut planes tied to the opening, merge neighbours while convexity/clearance/gap hold, check against the FULL main, re-measure after save, check passage both sides (arch 1-4) | `ucx10_core.resolve` only cuts the smaller of two existing convex pieces by a face plane; no "insert a new element into a frozen main" | NEW |
| K26 | Pipe elbow: one convex shell fills the inside of the bend -> split each elbow into 2 bodies (details) | none | NEW |
| K27 | Stairs: sloped body per flight, railing shells along the contour to the turn (details) | R14 truncated pyramid, no tool | NEW / possible conflict with R14 (Q3) |
| K28 | Optimisation: keep raw measurements first; compare connected bodies, convexity, extents, real joints; check convexity even when the budget is met (details, case 22) | V010 convexity + budget | SAME check; edge-reduction method NEW |
| K29 | Check the real FBX and Simple Collision in the target Unreal (AGENTS 4) | Unreal outside the UCX sheet scope | N/A (gap on both sides) |
| K30 | UCX keeps the model's object transform; no materials (oks "Сохраняемые свойства") | R16 transforms applied, R17 pivot free, R07 | SAME |

## 3. Replay (OBSERVE; Blender only)

Our numbers come from `agr ucx` with default options (exit 0 on every case; V010: present / slots / budget /
intersections / shape pass, gap advisory review, coverage not_run). Limit = [D012] on the render mesh IN THE SCENE.
`m2u` = model surface -> UCX (one-sided, [D134]); `u2m` = exposed UCX surface -> model (diagnostic).
"0-6 m" = 0-6 m above the model bottom (proxy of the pedestrian zone).

### OKS (Main)

| Case | Side | Bodies | Tris / limit | Non-convex (> 0.1 mm) | Overlap / < 2 mm | Gap min / p50 mm | Bands 2-10 / 10-100 / 100 mm-1 m | m2u max all / 0-6 m | 0-6 m share <= 0.3 m | u2m p50 / p95 m | Covered passage blocked |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | Codex | 999 | 13 108 / 7 392 (over; Codex ref. 14 770 = HP) | 1 (0.14 mm, `_066`) | 0 / 0 | 2.97 / 6.01 | 1 842 / 156 / 1 119 | 0.896 / 0.896 | 99.87 % | 0.003 / 2.84 | 0 of 0 m3 |
| 01 | ours | 558 | 6 696 / 7 392 | 0 | 0 / 0 | 4.0 / 4.0 | 1 207 / 9 / 81 | 0.016 / 0.016 | 100 % | 0.526 / 1.12 | 0 of 0 m3 |
| 02 | Codex | 467 | 6 888 / 6 891 | 0 | 0 / 0 | 4.62 / 6.0 | 791 / 209 / 872 | 1.058 / 1.058 | 99.93 % | 0.003 / 3.26 | 0 of 1.2 m3 |
| 02 | ours | 562 | 6 744 / 6 891 | 0 | 0 / 0 | 4.0 / 4.0 | 1 305 / 11 / 551 | 0.009 / 0.002 | 100 % | 0.249 / 0.71 | 1.25 of 1.25 m3 |
| 03 | Codex | 298 (1 object) | 4 120 / 2 558 (over) | 0 | 0 / 0 | 6.75 / 8.48 | 630 / 99 / 401 | 2.002 / 2.002 | 90.4 % | 0.004 / 1.19 | 0 of 70 m3 |
| 03 | ours | 158 | 1 896 / 2 558 | 0 | 0 / 0 | 4.0 / 4.0 | 396 / 2 / 34 | 0.031 / 0.002 | 100 % | 0.600 / 1.23 | 5 of 70 m3 (7 %) |
| 04 | Codex | 776 | 9 670 / 6 408 (over) | 0 | 0 / 0 | 5.9 / 6.0 | 1 891 / 331 / 1 001 | 1.566 / 0.025 | 100 % | 0.113 / 3.81 | 0 of 13.8 m3 |
| 04 | ours | 285 | 3 420 / 6 408 | 0 | 0 / 0 | 4.0 / 4.0 | 535 / 6 / 298 | 0.009 / 0.0 | 100 % | 0.398 / 0.73 | 0 of 13.8 m3 |
| 10 | Codex | 47 | 564 / 4 377 | 0 | 0 / 0 | 5.99 / 6.0 | 69 / 0 / 14 | 0.989 / 0.236 | 100 % | 0.144 / 2.69 | 0 of 5 m3 |
| 10 | ours | 329 | 3 948 / 4 377 | 0 | 0 / 0 | 4.0 / 4.0 | 1 122 / 8 / 70 | 0.008 / 0.002 | 100 % | 0.368 / 0.87 | 0 of 5 m3 |

Our build cell grew to 1.45 / 0.86 / 1.34 / 0.88 / 1.04 m (01 / 02 / 03 / 04 / 10) to fit [D012] (10-12 attempts,
37-371 s per case).

### Ground

| Case | Side | Bodies | Tris / limit | Non-convex (> 0.1 mm) | Overlap / < 2 mm | Gap min / p50 mm | Bands 2-10 / 10-100 / 100 mm-1 m | m2u max / p95 m | m2u <= 1 cm | u2m p50 / p95 m |
|---|---|---|---|---|---|---|---|---|---|---|
| 06 | Codex | 204 | 1 808 / 15 000 | 0 | 0 / 0 | 6.62 / 11.35 | 446 / 545 / 129 | 0.072 / 0.017 | 86.6 % | 0.020 / 4.43 |
| 06 | ours | 417 | 4 772 / 15 000 | 0 | 0 / 0 | 4.0 / 4.0 | 1 256 / 166 / 757 | 0.076 / 0.042 | 72.7 % | 0.060 / 2.80 |
| 11 | Codex (Artem's scene) | 598 | 7 410 / 15 000 | 14 (max 1.7 mm); our strict check flags 202 | 1 (1.58 mm) / 11 | 0.15 / 4.65 | 817 / 424 / 454 | 2.098 / 0.053 | 66.7 % | 1.60 / 10.69 |
| 11 | ours | 833 | 9 948 / 15 000 | 0 | 0 / 0 | 3.99 / 4.0 | 2 575 / 248 / 967 | 1.275 / 0.029 | 84.1 % | 0.077 / 5.34 |

### Arch insertion and details (no render mesh in the scene: UCX only)

| Case | Bodies (pilot) | Tris | Kinds | Pilot-pilot / pilot-main overlap | Min gap pilot-pilot / pilot-main mm | Frozen main collision (not Codex's work) |
|---|---|---|---|---|---|---|
| 07 | 17 (140 vertices, as the card says) | 212 | 17 convex | 0 / 0 | 4.98 / 5.0 | 341 parts in ONE object; 4 overlaps (to 33 mm), 2 pairs < 2 mm, 24 parts non-convex (7 > 10 cm) |
| 08 | 38 | 602 | 37 convex + `UCX_V4_011` non-convex by 0.11 mm | 0 / 0 | 4.98 / 4.99 | same main (358 parts), same findings |
| 12 | 66 | 3 968 | 59 convex, 4 boxes, 3 non-convex (`_011` 51.8 mm, `_031` 0.64 mm, `_006` 0.14 mm) | 0 / 0 (whole set) | 3.4 (whole set) | - |

Ours on 07/08/12: not replayed. `agr ucx` has no "insert into a frozen main" operation (K25) and there is no
render mesh; `--resolve` would cut existing pieces, which is not what these cases do.

### Gaps of this replay

- 05, 09 (.max only): need Max - skipped. 13-22: cards only (no scenes) - census from the card.
- `passages.py` is a heuristic (rays can leave through glass-less windows; columns stop rays): it found covered
  through-passages only in 02 (1.2 m3), 03 (70 m3), 04 (13.8 m3), 10 (5 m3). The 0-6 m band is relative to the
  model bottom, not the real pedestrian zone.
- Codex 03: 9.6 % of the 0-6 m surface is farther than 0.3 m from the UCX (max 2.0 m). Not inspected visually;
  it may be a below-grade part or a thin element (R04). Codex 01/02 have single points to 0.9-1.06 m in 0-6 m.
- Case 11 (Ground): m2u max is above R11 = 10 cm on both sides: ours 1.275 m, Codex 2.098 m (p95 0.029 /
  0.053 m). Not inspected visually; it may be a thin or below-grade element of Artem's scene.
- Case 11 Codex overlap: `ucx_audit` reports 1 overlapping pair (1.58 mm penetration), while the `gap_check`
  bands report `overlap: 0` for the same set. The "Overlap / < 2 mm" column uses `ucx_audit`; the bands column
  uses `gap_check`. The two tools disagree on this pair.
- Codex's 01 K1 budget reference 14 770 assumes a 295 400-tri HP; the scene mesh is 147 826 tris. The final HP
  was not available here.
- No Unreal and no AGR Checker on either side.

## 4. Отчёт для Артёма

**Коротко.** Набор Кодекса экономнее и точнее «облегает» фасад, в нём есть отдельные приёмы (арка, откос,
секции, трубы), которых у нас нет. Наш `agr ucx` всё делает автоматически за минуты, всегда укладывается в бюджет
[D012], все тела выпуклые и с ровным зазором 4 мм, а покрытие модели почти полное (модель -> UCX ≤ 3,1 см на
всех пяти ОКС). Но наша сетка под бюджет растёт до 0,9–1,45 м, поэтому коллизия стоит от фасада в среднем на
0,25–0,6 м (p95 до 1,2 м). У Кодекса медиана 3–4 мм.

### Где Кодекс лучше

1. **Плотная посадка на фасад.** Медиана расстояния от открытой грани UCX до модели (u2m p50): 3 мм (01),
   3 мм (02), 4 мм (03), 0,11 м (04). У нас 0,53 / 0,25 / 0,60 / 0,40 м. На фасаде игрок упрётся в «невидимую
   стену» перед зданием: у 95 % открытой поверхности UCX это расстояние не больше 1,2 м (p95, не максимум).
   По [D134] это диагностика, не ошибка, но визуально это хуже.
2. **Экономия на простых корпусах.** Поляны (10): 47 коробок / 564 tris (13 % бюджета) против наших 329 / 3 948
   (90 %). Откос Geo_019 (06): 204 тела / 1 808 tris против 417 / 4 772 при том же максимуме 7,2 vs 7,6 см.
3. **Врезка арки в замороженную коллизию** (07/08): 17 и 38 выпуклых тел. Зазор между ними и до основной
   коллизии от 4,98 мм, пересечений нет. У нас такой операции нет.
4. **Смысловая раскладка:** балконы, оборудование на кровле, корзины и парапеты делаются отдельными телами, а
   разрезы режут нижний пояс у входов (K10–K12). У нас — жадное объединение вокселей без семантики.
5. **Порядок работы:** сначала пилот на показательном фрагменте, до/после с одного ракурса; проверка высот стыков
   в середине ребра и в Т-узлах; проходы под перекрытиями проверяются сечениями (K18, K21, K22).

### Где выигрываем мы

1. **Бюджет [D012] на меше сцены.** Мы укладываемся всегда, потому что бюджет закрыт. У Кодекса 3 из 4 принятых
   ОКС его превышают: 01 — 13 108 / 7 392, 03 — 4 120 / 2 558, 04 — 9 670 / 6 408. Кодекс считает бюджет по HP
   (вопрос Q1).
2. **Покрытие модели (модель -> UCX, односторонне [D134]).** Наши ОКС: максимум 0,8–3,1 см во всех пяти
   кейсах. У Кодекса пороги регламента превышены. Это кандидаты: глазами не проверялись, это могут быть
   подземные части или тонкие элементы R04.
   - R13 (<= 1 м, прочие части ОКС): 02 — 1,058 м, 03 — 2,002 м, 04 — 1,566 м.
   - R12 (<= 0,30 м, пешеходная зона; здесь её прокси — 0–6 м от низа модели): 01 — 0,896 м, 02 — 1,058 м,
     03 — 2,002 м (в 03 дальше 0,30 м лежит 9,6 % поверхности зоны).
   - R11 (<= 10 см, Ground), кейс 11: превышено с обеих сторон — у нас 1,275 м, у Кодекса 2,098 м. Здесь мы
     тоже не проходим. В 06 обе стороны в норме (7,6 / 7,2 см).
3. **Чистота тел.** У нас 0 невыпуклых и 0 пар < 2 мм. У Кодекса: 01 — одно тело невыпукло на 0,14 мм;
   12 — тело `_011` невыпукло на 5,2 см; 11 (ваша сцена) — 14 тел до 1,7 мм, 11 пар < 2 мм, одно пересечение
   1,58 мм. В 03 все 298 тел лежат в одном объекте. Unreal построит из такого объекта одну оболочку, поэтому
   перед экспортом его нужно разделить.
4. **Автоматизация и замеры:** от 22 с до 6 мин на корпус без ручной работы. Readback, полосы зазоров [D339] и
   V010 идут одной командой.

### Что стоит взять (по пунктам, ядра не менялись)

1. **Вариант «section-boxes» для ОКС** (K10–K12, Поляны).
   - Что: карты глубины по осям здания, фильтр окон, отдельные тела для выступов и вырезов, высота корпуса по
     парапету.
   - Зачем: экономия и посадка на фасад.
   - Эффект: на 10 — 564 tris против 3 948, u2m p50 0,14 м против 0,37 м.
   - Рекомендация: отдельный вариант в `docs/methods/ucx-collisions`, мерить на тех же кейсах 01–04 и 10.
2. **Операция «врезка в замороженную коллизию»** (K25, кейсы 07/08).
   - Зачем: арки, ворота и порталы. Сейчас у нас по этим пунктам [R01] покрытие `none`.
   - Эффект: 17 тел / 212 tris, зазор ≥ 4,98 мм, 0 пересечений.
   - Рекомендация: follow-up issue на ядро (`ucx10_core` + Blender driver).
3. **Ground: существующие грани на откосах, крупные ячейки на пологой части** (K16, кейс 06).
   - Эффект: в 2,6 раза меньше tris при том же отклонении (1 808 против 4 772, 7,2 против 7,6 см).
   - Рекомендация: вариант Ground в каталоге методов.
4. **Проверка свободных проходов сечениями** (K22).
   - Зачем: закрыть пробел [R01] «passage preservation».
   - Эффект: эвристика нашла крытый проход 70 м³ в 03. Кодекс оставил его свободным, мы перекрыли 5 м³ (7 %).
     В 02 нагляднее: проход 1,25 м³ мы перекрыли целиком (100 %), Кодекс — 0.
   - Рекомендация: добавить в `agr ucx` отчётную метрику (OBSERVE, без отказа).
5. **Проверка «один UCX-объект = одно связное тело»** (K17, кейс 03).
   - Эффект: 03 — 1 объект на 298 тел.
   - Рекомендация: предупреждение в readback/V010.
6. **Проверка высот стыков Ground в середине ребра и в Т-узлах** (K21) как отчётная метрика.
7. **Пилот на фрагменте с до/после** (K18) как шаг маршрута `routes/site.md` (шаг 6) и в UCX-части OKS.
8. **Группировка точек вне допуска по месту** (K14): отчёт «где не покрыто», а не только числа.

Каждый пункт — отдельный follow-up issue после вашего выбора. В этой карточке ничего не внедрено.

### Вопросы (решение за вами, ничего не принято молча)

- **Q1 Бюджет.** По [D012] бюджет считается от треугольников модели в FBX. Кодекс в 01/03 считал от финального
  HP (14 770 для K1). На меше сцены 01/03/04 его превышают. Какой меш база бюджета: сданный FBX или HP?
- **Q2 Отклонение Ground.** У Кодекса «в обе стороны» (K6), у нас [D134] одностороннее. Оставляем [D134]?
- **Q3 Лестницы.** У Кодекса — наклонные тела маршей и оболочки перил (кейс 19). По регламенту [R14] — усечённая
  пирамида. Считать ли наклонное тело марша допустимой формой?
- **Q4 Порог выпуклости.** Наша проверка выпуклости отмечает 202 из 598 тел вашей сцены 11, хотя дальше 0,1 мм от
  своих граней выходят только 14 (максимум 1,7 мм). Нужен ли допуск, например 1 мм?
- **Q5 Зазор.** Кодекс читает нижнюю границу как 0,2 мм (номинал 6 мм), у нас [D098] 2 мм – 1 см. Ground v004 /
  кейс 06 имеют зазоры 10–16 мм. Подтверждаете, что остаётся [D098] + отчёт [D339]?

### В эталонный банк / тренер (с вашего OK)

| Кейс | Почему | Оговорка |
|---|---|---|
| 02 Garibaldi K2 | принят, в бюджете (6 888 / 6 891), 0 невыпуклых, 0 пар < 2 мм | модель -> UCX 1,058 м: выше R13 и R12 (кандидат, глазами не проверено) |
| 10 Polyani | чистый, 47 коробок, метод «section-boxes» | принят узко (метод) |
| 06 Geo_019 откос | чистый Ground, 204 тела, ≤ 7,2 см | Checker/Unreal не проверялись |
| 07 + 08 арки | чистые врезки, зазор ≥ 4,98 мм | основная коллизия в сцене с дефектами (4 пересечения, 24 невыпуклых) |
| 04 Domashniy | принят, есть FBX | превышен бюджет на меше сцены (Q1); модель -> UCX 1,566 м, выше R13 (кандидат, глазами не проверено) |
| 01 / 03 Garibaldi | приняты | 01: бюджет, одно тело 0,14 мм, 0,896 м в зоне 0–6 м (R12); 03: один объект на 298 тел, бюджет, 2,002 м (R12/R13) (Q1, Q4) |
| 11 Geo_007 | ваш «стиль» Ground | не эталон чистоты (Q4); модель -> UCX 2,098 м при R11 = 10 см (у нас 1,275 м) |

## Side finding (not changed here)

`tools/blender/ucx_audit.py`, `ucx_build.py`, `ucx_resolve.py` and `fbx_readback.py` import FBX with the default
`use_image_search=True`. An FBX that references a missing texture makes the importer walk the disk: `ucx_audit` on
the first export of case 10 hung for over 10 minutes (faulthandler stack: `bpy_extras.image_utils._recursive_search`).
The replay worked around it by dropping images before export. Worth a one-line follow-up: `use_image_search=False`.
