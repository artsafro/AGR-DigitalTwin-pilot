# KPP1 #1416 — Ground copy under 180 000 NPM triangles; s_podz search — PACKAGING WAITS FOR ARTEM

## Кратко (RU)

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
