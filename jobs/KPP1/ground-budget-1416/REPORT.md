# KPP1 #1416 — Ground copy under 180 000 NPM triangles; s_podz search; packages rebuilt — NOT PASSED

## Кратко (RU) — раунд 3 (решение Артёма [D313], «на все да»)

- **Исключение [D313]** (как [D256]): собственные дефекты моделирования Ground заказчика — V004 самопересечения
  Flora 150 567 / Ground 15 976 / GroundEl 63 537, V003 skirt «broken face geometry», V004 clearance 406 пар < 5 мм —
  приняты Артёмом для KPP1 package-v001. Валидатор их по-прежнему пишет как `fail`, поэтому `passed=false`
  в `validate-npm.json` остаётся честным; эти строки закрыты решением, а не валидатором.
- **Открыто (ждёт Артёма/заказчика):** `s_podz` (VPM V011, число заказчика [D306]); ручные приёмки V015 / V017;
  `not_run` V003 footprint/holes (нет ground_area_m2), V003 master quads, V014 (валидатора нет).
- **3ds Max не открывали** (решение Артёма). Вместо этого — wireframe Ground v003 (упакованный
  `package-v001/npm/0000_Kpp_1_Ground.fbx`, sha `29944746…`, 179 816 треугольников при чтении), в виде quad review
  (только для показа; FBX остаётся триангулированным): Flora 37 391 quad + 34 545 tri, Ground 7 956 + 2 979,
  GroundEl 24 666 + 2 266. Папка `G:/Мой диск/AGR-evidence/1416-kpp1-ground-budget/wire-v003/` + `SHA256SUMS.txt`:
  `01_overview_top.png` (весь участок, сверху), `02_densest_cell.png` (самая плотная ячейка 10 м, центр
  8165/−9665, 15 037 полигонов), `03_skirt_edge.png` (край/юбка, юг), `04_building_edge.png` (юго-восточный угол R1),
  сводный лист `wire-sheet-v003.png` (sha `b5f585c3…`), `wire-report.json`.
- 179 821 в раунде 2 — счёт скрипта до экспорта; чтение FBX и валидатор дают 179 816 (оба ≤ 180 000).

```bash
G="G:/Мой диск/AGR-evidence/1416-kpp1-ground-budget"; E="$G/package-v001/npm"
"$B" -b --factory-startup -noaudio --python wire_render.py -- "$E/0000_Kpp_1_Ground.fbx" "$E/0000_Kpp_1_01.fbx" "$G/wire-v003"
uv run python wire_sheet.py "$G/wire-v003"   # rerun on an existing dir -> "output exists" / "exists", nothing written
```

## Кратко (RU) — раунд 2 (после решения Артёма [D308])

- **Ground v003** (`G:/Мой диск/AGR-evidence/1416-kpp1-ground-budget/v003/0000_Kpp_1_Ground.fbx`, sha `29944746…`):
  принятая геометрия v002 + мост #1371 (абсолютная система R1) + имена `SM_Kpp_1_{Flora,Ground,GroundEl}` +
  ремонт V004 в копии. **179 821** треугольников (≤ 180 000). Текстуры заказчика вновь встроены (v002 их потерял),
  единицы 1 м (v002 писал 1 см). Оригинал заказчика не тронут (хэш d8770f47… проверен скриптом).
- **NPM пакет** `package-v001/0000_Kpp_1.zip` (`agr package-npm`, R1 байт-в-байт из #1371 v007):
  V001 / V002 / V005 / V006 / **V012 pass** (было fail). V004 MAF normals 606 → 4, MAF smoothing pass.
  **Итог `passed=false`** — остаются дефекты моделирования самого Ground заказчика (таблица ниже).
- **VPM** v008 (#1371, `db4bef46…`) не изменён (новых входов для VPM нет); свежий `--scene`: V011 fail только `s_podz`.
- **s_podz:** без изменений — ТЭП `TEC26_na_RR_1.pptx`, слайд 59: подземная часть «–»; ждём число заказчика ([D306]).

## Round 2: v003 and packages ([D308])

Command (Blender 5.1.2 headless):

```bash
"$B" -b --factory-startup -noaudio --python derive_ground_v003.py -- "$E/v002/0000_Kpp_1_Ground.fbx" 5cc8421f…f8d3 \
  "<1371 copies>/0607_77_05_0009005_117_Ground.fbx" d8770f47…aebd jobs/KPP1/delivered-1371/mapping.json "$E/v003"
uv run agr package-npm "$E/package-v001/npm"                       # exit 0, 2 FBX, no problems
uv run python tools/qa/validate_package.py "$E/package-v001/0000_Kpp_1.zip" --profile npm --scene --json   # exit 1
uv run python tools/qa/validate_package.py "<1371>/package-v008/SM_Kpp_1.zip" --profile vpm --scene --json   # exit 1
```

Repairs on the copy (`v003/repair-report.json`): weld <= 2 mm (GroundEl 18 verts), degenerate faces removed
(Flora 11, GroundEl 238 -> 179 899 -> 179 821 tris), 0 duplicate faces / loose elements found, GroundEl closed shells
oriented outward by signed volume (470 faces flipped, 566 flat components undetermined), 443 GroundEl edges > 40 deg
made hard. Three earlier attempts kept as evidence (`v003-attempt1..3`): FACE smoothing / no textures / 1 cm units
(attempt 1), smoothing 455 soft edges (attempt 2), flipped 2 + 9 soft edges from stale bmesh indices (attempt 3).

| Stage | NPM 1371 v007 (customer Ground) | NPM 1416 package-v001 (Ground v003) | Owner of what is left |
|---|---|---|---|
| V001 composition | pass | pass | — |
| V002 units / header | pass | pass | — |
| V003 Ground budget | fail 180 934 | **pass 179 816 (readback)** | — |
| V003 Flora share | review 110 362 / 70 000 | review 109 327 / 70 000 | Artem (indicative share) |
| V003 skirt | fail (broken face geometry) | fail (same) | customer Ground modelling |
| V003 footprint / holes | not_run | not_run (no ground_area_m2 / holes reference) | needs site-minus-footprint area |
| V003 master quads | not_run | not_run | #1372 quad master is for R1, not this package's cold-run R1 member |
| V004 topology | Flora 152 427 / Ground 16 745 / GroundEl 64 561 | Flora 150 567 / Ground 15 976 / GroundEl 63 537 | **all `self_intersections`, 0 duplicates**: crossed Flora cards and pieces sunk into terrain — customer modelling |
| V004 MAF normals | flipped 606, inconsistent 8 | flipped 4, inconsistent 0 | 4 faces on non-manifold edges |
| V004 MAF smoothing | pass | pass | — |
| V004 clearance | 1 498 pairs < 5 mm | 406 pairs < 5 mm | customer modelling, accepted as exception [D313] |
| V006 textures | pass | pass | — |
| V012 names | fail | **pass** | — |
| V014 / V015 / V017 | not_run | not_run | validator absent / manual sign-offs / no planting schedule |

xView of v003 (`v003-attempt2/xview-after.json` is the same geometry minus the hard-edge / normal changes):
overlapping faces remain (customer layers), so xView 0/0 is not reached.

## Round 1 summary (RU)

- **Ground (D307):** собрана наша производная копия NPM Ground заказчика: **180 934 → 179 899**
  треугольников (−1 035, лимит 180 000). Упрощена только Flora (collapse-decimate 0.9906, 1 035 треугольников);
  Ground и GroundEl — та же геометрия (дрейф ≤ 23 мкм — округление float32 при экспорте FBX), те же UV.
  Имена объектов, материалы, UV-слой `AtlasUV`, границы UV (UDIM) не изменены. Оригинал заказчика не тронут
  (хэш d8770f47… до и после). xView копии = xView оригинала (2263 / 0, 3482 пары, 0 новых пар) —
  **0/0 недостижимо без исправления дефектов самого заказного Ground** (GroundEl 2150 перекрывающихся граней).
- **Лист «до/после»** (одни и те же камеры, solid + wire):
  `G:/Мой диск/AGR-evidence/1416-kpp1-ground-budget/before-after-sheet-v002.png` (sha 307c1ee8…).
  Отклонение Flora: p95 0 мм, p99 0.10 мм, max 22.6 мм; 581 из 91 240 вершин сдвинуто > 1 мм.
- **s_podz (D306):** найдено в проекте: альбом ИД `TEC26_na_RR_1.pptx`, **слайд 59**, таблица ТЭП,
  строка 5 «Общая площадь объекта»: наземная часть **27124,36**, **подземная часть «–»** во всех колонках;
  слайд 60, примечание 4: «форма не допускает пустых полей, в случае отсутствия показателя проставляется «–»».
  То есть проект показывает «подземной части нет», но числа нет — по D306 поле ждёт числа Артёма (не 0).
- **Упаковка не выполнялась:** по D307 сначала приёмка листа «до/после» Артёмом; плюс открытые вопросы ниже.

## Inputs

| Input | SHA-256 |
|---|---|
| Customer NPM Ground copy `0607_77_05_0009005_117_Ground.fbx` (#1371 evidence copy of the delivered ZIP member) | `d8770f4796c8d68847af7b08f6b156d0d0fdd11809de3a1b44479747cab1aebd` (checked by the script) |
| Album `G:/Мой диск/AGR-assets/tec26/album/TEC26_na_RR_1.pptx` | `74e50277…` (sources.json) |

## Commands (Blender 5.1.2 headless, factory startup)

```bash
B="C:/Program Files/Blender Foundation/Blender 5.1/blender.exe"; S="G:/Мой диск/AGR-evidence/1371-kpp1-delivered/v001/copies/0607_77_05_0009005_117/0607_77_05_0009005_117_Ground.fbx"; E="G:/Мой диск/AGR-evidence/1416-kpp1-ground-budget"
# run 1 (v001): plain Flora decimation -> 179900 tris, but xView +8 overlapping Flora faces (+4 pairs)
"$B" -b --factory-startup -noaudio --python simplify_ground.py -- "$S" d8770f47...aebd "$E/v001"
uv run dt qa xview "$S" --out "$E/v001/xview-before.json" --profile NPM-GROUND        # 2263 faces, 3482 pairs
uv run dt qa xview "$E/v001/0000_Kpp_1_Ground.fbx" --out "$E/v001/xview-after.json" --profile NPM-GROUND  # 2271 / 3486
uv run python xview_new_pairs.py "$E/v001/xview-before.json" "$E/v001/xview-after.json" "$E/v001/protect.json" 0.3  # 4 new pairs
# run 2 (v002, candidate): the 80 Flora loose parts (838 tris) near the new pairs are kept out of the decimation
"$B" -b --factory-startup -noaudio --python simplify_ground.py -- "$S" d8770f47...aebd "$E/v002" 179900 "$E/v001/protect.json"
uv run dt qa xview "$E/v002/0000_Kpp_1_Ground.fbx" --out "$E/v002/xview-after.json" --profile NPM-GROUND  # 2263 / 3482
uv run python xview_new_pairs.py "$E/v001/xview-before.json" "$E/v002/xview-after.json" "$E/v002/protect-residual.json"  # 0 new
"$B" -b --factory-startup -noaudio --python readback_render.py -- "$S" "$E/v002/0000_Kpp_1_Ground.fbx" "$E/v002-renders"
```

## Result (fresh-process readback, `v002-renders/readback.json`)

| Mesh | Tris before → after | Materials / UV layer | UV bounds | Geometry |
|---|---|---|---|---|
| SM_…_Flora | 110 362 → 109 327 | same / same | inside source bounds | decimated; max 22.6 mm |
| SM_…_Ground | 18 891 → 18 891 | same / same | same UV hash | ≤ 22.5 µm (float32 FBX round trip) |
| SM_…_GroundEl | 51 681 → 51 681 | same / same | same UV hash | ≤ 22.6 µm |
| **Total** | **180 934 → 179 899** | | | |

Output `v002/0000_Kpp_1_Ground.fbx` sha `5cc8421f…58e`; all 27 evidence files in
[evidence-SHA256SUMS.txt](evidence-SHA256SUMS.txt). Object names stay the customer names
`SM_77_05_0009005_117_*` (ID unchanged per D307) — they fail the V012 package-stem mask (#1371 CHECKS).

## Why the packages are not rebuilt yet (open for Artem)

1. D307: before/after acceptance precedes packaging.
2. #1371 CHECKS: besides the triangle count the delivered Ground fails V003 skirt, V004 topology
   (Flora 152 427 / Ground 16 745 / GroundEl 64 561 duplicate/intersection counts, MAF normals 606 flipped),
   V004 clearance (1 498 pairs < 5 mm), V012 names, and sits in a LOCAL frame (X −231..231) while R1 is
   absolute MSK-like (X≈8056). D288 left "boundary, absolute placement and allowed fixes of a derived copy"
   to a separate decision; D307 covers only the triangle budget.
3. V014 (validator implementation absent) and V015–V017 (manual sign-offs) are `not_run` for every KPP1
   package, so `passed=true` cannot be reached by the agent alone.
