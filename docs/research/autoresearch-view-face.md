# Autoresearch #139 — elevation view -> model face map (OBSERVE)

## Кратко для Артёма

Гипотеза: «вид фасада без подписи/осей можно привязать к грани модели, сравнив его с ортографическим
рендером модели (силуэт + ритм вертикальных рёбер), и отказываться (спрашивать) при малом отрыве».
**Результат: опровергнута для предложенного метода V3** (силуэт + ритм): на синтетических частичных видах
3 уверенные ошибки из 19 ответов. **Безопасен только силуэт крыши (V1):** 0 уверенных ошибок на всех
80 случаях (8 реальных видов KPP1/AC08 + 72 синтетических обрезка), но отвечает редко: 2 из 4 полных видов
KPP1 (длинные фасады 1-4 / 4-1 — верно), 6 из 36 обрезков; короткие торцы и симметричный короб AC08 —
отказ (правильно: геометрически их не отличить). Текстуры NPM (R3) не помогли. Причина: в NPM-модели нет
окон геометрией, а ритм линий DXF засорён. Повтор 3 раза — результат байт-в-байт одинаковый.

Рекомендация для шага OKS-трассы «view<->face map sheet»: (1) сначала оси/ключевой план/названия видов —
они на KPP1 и AC08 однозначно дают ответ; (2) для неподписанных видов — силуэт крыши (V1) с порогом отрыва
0,10, только как «уверенный ответ или вопрос»; (3) при отказе — показать 2 лучших кандидата рядом и спросить
(или VLM-судья пары); (4) ритм окон сравнивать только с моделью-источником (Revit/VPM с окнами), не с NPM.
Sokolniki не открывался (#2001) — это следующий перенос-тест. Код в продукт не вносился.

**Hypothesis result:** H139 (V3 silhouette+rhythm, tau 0.10) **REFUTED** (3 confident-wrong);
V1 roofline-only **safe but low coverage** (0 wrong / 80, answered 8). Review readiness is separate (below).

Card t_8845bd2c, branch `research/autoresearch-standing-139`. Focus 0 of the card (Artem 2026-11-27 ~15:05):
tie every elevation view on a sheet, including untitled partial views, to the model face it shows, and
abstain (ask) below a threshold. Found in the Sokolniki cold run (#2001 STOP 04). Sokolniki is HELD OUT.

## Frozen contract (committed before any scoring)

- **Metric (one number + abstain):** view->face assignment accuracy on answered views and abstain rate, per
  variant and per view class (real full views; synthetic partial crops). Safety = confident-wrong count
  (must be 0 for a recommendation). Fixture and GT: `autoresearch-view-face-harness/fixture.json`
  (SHA-256 of every input, preflight-checked on every run).
- **Method under test (OBSERVE, research only):** model side = Blender headless orthographic ray-cast depth/normal
  maps from each candidate outward normal (`rays.py`); view side = DXF vector geometry inside the view,
  annotation layers (titles, axes, dimensions, notes, level marks) removed, rasterised at 0.1 m/px.
  1D signals along the facade: roofline (top profile relative to view max) and vertical-edge rhythm
  (column density). A view slides along each face (partial views allowed); face score = best NCC over offsets.
  Variants frozen: V0 width only, V1 roofline, V2 rhythm, V3 = mean(V1, V2) (proposed).
- **Decision rule frozen:** answer the best face only if score >= 0.30 and margin to the best other face >= 0.10;
  otherwise abstain. Thresholds are fixed a priori, not tuned on this fixture; the full margin table is published.
- **Fixtures:** KPP1 L01 (Revit vector export, 4 elevations, accepted delivered model) = positive set;
  TEC26 AC08 (AutoCAD sheet, 4 elevations, symmetric source box) = abstain control (within-pair abstain is
  correct; a confident within-pair pick counts as wrong). Synthetic partials: crops at 25/40/60 % width,
  left/centre/right, labelled synthetic. **Not measured:** real untitled partial views (only Sokolniki has them,
  held out), PDF-only raster sheets (AC06 slides), G22/OBR22/Vatutino (no vector elevation + model pair found
  locally within budget), non-orthogonal faces and inner corners (KPP1/AC08 are boxes).
- **Calibration requirement (card rule 3):** applies as GT accuracy here: a wrong face must not win with margin.
  Witnesses: positive = KPP1 full views (asymmetric stairs/canopies); abstain control = AC08 within-pair;
  perturbation = mirrored KPP1 view (expected: score drop or abstain, not a confident correct pick).
- **Repeatability:** 3 full runs (ray-cast + DXF + scoring), median; deterministic expected, spread published.
- **Budget / stop rule:** one card run; at most 3 rounds of method change after the first frozen scoring,
  each recorded; stop at 3 rounds or when V3 reaches 100 % answered-accuracy with 0 confident-wrong.
- **Forbidden:** editing sources/deliveries/other cards' files, tuning thresholds on the scored set without
  recording it as a new round, opening Sokolniki accepted outputs, presenting synthetic crops as real views.
- **Deliverable:** measured recommendation for a shared OKS-trail step "view<->face map sheet" (core + agr command),
  not the step itself.

## Round log

All rounds on the frozen fixture (`fixture.json` SHA-256 in the receipt), tau 0.10 / min score 0.30 unchanged.
Counts = answered / correct / wrong; n = 4 full KPP1, 36 synthetic partial KPP1, 4 full AC08, 36 partial AC08.

| Round | Change (code commit) | V1 full / partial KPP1 | V3 full / partial KPP1 | AC08 (all variants) |
|---|---|---|---|---|
| R0 | frozen harness (6ee6608a) | 1/1/0 · 8/7/1 | 0/0/0 · 12/9/3 | all abstain |
| R1 | span trim (columns with top >= 2 m) + depth jump 0.03 m | 2/2/0 · 6/6/0 | 2/2/0 · 19/16/3 | all abstain |
| R2 | V4 = V3 + 0.15 full-face prior (width within 5 %) | — | V4 = V3 (short views 8.8-9.4 % off the NPM face width, prior never fires) | all abstain |
| R3 | V5 = V3 + NPM UDIM diffuse luminance edges (4c87bb59) | — | V5 2/2/0 · 13/11/2 | all abstain |

Stop rule reached (3 rounds). Final state = R3 code; replay x3 identical (content hash `72fc8be99a4baa3c`,
total 13.32 / 13.14 / 13.21 s, median 13.21 s, spread 0 in every score).

Per-view facts (R3 run, receipt `autoresearch-view-face-harness/receipt_r139.json`):
- KPP1 long views: 1-4 -> az270 margin V1 0.147 / V3 0.259; 4-1 -> az90 margin V1 0.113 / V3 0.183. Correct.
- KPP1 short views В-А / А-В: best V3 face is a LONG face window (sliding allowed for untitled partials):
  V3 margins 0.075 / 0.027 -> abstain. The 3 V3 wrong answers are right-end 40-60 % crops of the short faces (margins 0.128-0.169).
- AC08: symmetric source box (201 vertices), drawing has only frame lines once hatches are dropped -> every
  variant abstains (correct per contract; within-pair confident picks = 0).
- Mirror perturbation (KPP1 full views flipped): V1 answers 2/4 with margin, picking the opposite face — the
  roofline carries handedness (stairs), so a mirrored drawing looks like the opposite facade. Recorded, not a GT case.
- V0 width-only abstains everywhere: opposite faces have equal width (pairs), as expected.

Clean vs not measured:
- Measured: KPP1 4 real full views (Revit vector export), AC08 4 real full views (AutoCAD), 72 synthetic crops.
- **Not measured:** real untitled partial views (Sokolniki held out), inner-corner / non-orthogonal faces
  (only 4 azimuths tested; boxes), PDF raster sheets, G22 / OBR22 / Vatutino (no local vector elevation + model
  pair found within budget), view localisation on a sheet for AC08 (boxes given from the job's sheet-facades.json;
  KPP1 views found automatically by x-gap clustering, 4/4), keyplan / axis reading (used as GT, not as a method).
- GT check: KPP1 GT derived from L03 plan axes + translation-only frame, cross-checked visually
  (`viz_kpp1.png`: stair side per facade matches 1-4 / 4-1 / А-В / В-А). AC08 GT = accepted vpm_textures normals.

## Recommendation (OBSERVE, not implemented)

Shared OKS-trail step "view<->face map sheet" (core function + `agr` command), in this order:
1. Read the deterministic anchors first: view titles, axis bubbles at both view ends (left axis -> right axis
   gives the outward normal: right = (-n) x Z), keyplan. On KPP1/AC08 these alone decide every view.
2. For an untitled view: roofline (V1) ortho match against every candidate face (faces from the footprint, not
   only 4 azimuths), answer only with margin >= 0.10; measured 0 confident-wrong / 80, coverage 10 %.
3. Otherwise abstain with the two best faces rendered next to the view (STOP question to Artem or a VLM pair judge).
4. Do not use NPM geometry/texture rhythm (R0-R3: unsafe or no gain); window rhythm needs a model with window
   geometry (Revit source / VPM) and layer-aware DXF (glazing layers only).

## Replay

```
uv run --offline --extra cad python docs/research/autoresearch-view-face-harness/view_face.py --out C:/x/ev_t_8845bd2c/repN
python docs/research/autoresearch-view-face-harness/compare_runs.py <run1>/result.json <run2>/result.json <run3>/result.json
```

Inputs are SHA-256 checked on every run (fixture.json). The KPP1 model is the accepted delivery ZIP member
(`G:/Мой диск/AGR-assets/KPP1/delivered-customer-2026-11-14/SM_77_05_0009005_117_002.zip`, unzip to the fixture path);
KPP1 L01 DXF is `C:/x/kpp1/r1209/dxf/L01.dxf`; a hash-identical copy is in the evidence folder `inputs/kpp1_L01.dxf`.
Evidence (all run JSONs, ray npz, viz): `G:/Мой диск/AGR-evidence/139-view-face/` + `SHA256SUMS.txt`.
