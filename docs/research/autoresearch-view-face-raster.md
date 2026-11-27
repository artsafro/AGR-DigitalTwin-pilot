# Autoresearch #141: raster elevation view -> model face by window rhythm (OBSERVE)

## Кратко для Артёма

Проверил новый проект, которого не было в #139/#140: Обр22 корпус 2 — PDF-буклет (стр. 14-15, фасад растром,
подписи вектором) и принятая НПМ v012, где окна есть геометрией. Идея: привязать вид к грани по ритму окон.
Правильный ответ взят независимо — из плана этажа (стр. 36), совмещённого со стенами модели.

**Результат: гипотеза опровергнута.** Версия R1 (окна = тёмные пиксели) дала 22 уверенные ошибки на 40 чистых
случаях, в том числе один из двух длинных фасадов (2.25-2.1) отнесён не к той стороне. Причина: тёмная
облицовка RAL 7024 на лестничных узлах читается как стекло; торцевые виды без окон не с чем сравнить, и их
обрезки «притягиваются» к длинным граням. Проверка по ширине (V0) не ответила ни разу (пары граней одинаковые).

R2 (после разбора, на тех же данных — только диагностика): убрал тёмные полосы выше 2,5 м и отказ при малом
числе окон. Длинные фасады стали верными: 2 из 2 целых видов, 9 из 18 обрезков, ни одной ошибки. Но 4 узкие
обрезки торцов (4,4 м у края) всё равно уверенно ушли на длинную грань. Значит, порог отрыва 0,10 сам по себе
не защищает: если у грани нет окон, её нельзя сравнить, и метод выбирает из неполного списка.

Три прогона каждой версии дали одинаковый результат байт в байт. Каждый прогон занимает около 4 с.

**Рекомендация для шага «карта вид↔грань»:** ритм окон годится только (1) если окна в листе берутся как объекты
(слой/категория окон Revit или векторные заливки стекла), а не по яркости растра, (2) если у каждой грани-
кандидата есть сравнимый сигнал (у грани без окон оценивать совпадение «пустоты», а не исключать её),
(3) для узкого вида с повторяющимся ритмом — отказ, если тот же рисунок встречается в нескольких местах.
До этого — оси/ключевой план/имя вида, иначе показать 2 лучших кандидата и спросить. Сокольники не открывались
(#2001 открыт). В продукт ничего не вносилось.

## Frozen protocol (committed before scoring)

Card t_c97df96b, branch `research/autoresearch-standing-141`, focus 0 (Artem 2026-11-27 ~15:05): tie every
elevation view to the model face it shows; abstain (ask) below a threshold. Sokolniki (#2001, still OPEN) is
held out and not opened. Continues #139 (`research/autoresearch-standing-139@38f7d95e`) and #140
(`research/autoresearch-standing-140@ab33b7e4`), whose next step (2) was "a second asymmetric, independently
labelled PDF/model pair". #139 diagnosed rhythm failure as "NPM without window geometry"; #140 left raster/vector
PDF, G22/OBR22/Vatutino unmeasured.

- **H141:** on a held-out project (OBR22 K02, never used by #139/#140) with a **raster** PDF elevation sheet and an
  accepted model **with window geometry**, a 1D window-column rhythm matcher (variant C) assigns both long
  facades correctly from the image alone, with zero confident-wrong answers on all clean cases, where the #139
  width baseline V0 cannot answer (both face pairs have equal widths).
- **Cohort (fixture.json, SHA-256 per input):** `АГР_зона 2.1 — 1.pdf` pages 14-15 (Корпус 2, four facades;
  facade = raster tiles, annotation = vector) and the accepted NPM v012 `OBR22_K02_v012_NPM_ATLAS.blend`
  (one typical floor, 88.9 × 16.3 m, 45 `WINDOW_*` objects). Full views 4 (2 long, 2 short); synthetic
  horizontal crops 25/40/60 % at left/centre/right = 36 (labelled synthetic); injected horizontal mirror of
  each full view = 4. There are no real untitled partial views and no inner corners in this cohort.
- **GT (independent of the elevations):** PDF plan p36 (vector cut walls) registered to the Revit wall
  footprint (`plan_reg.py`): rot180 0.9097, mirror_y 0.9018, identity 0.6902, mirror_x 0.6853. Both top/bottom
  flips agree on the long faces: 2.1-2.25 = model +Y (az 90), 2.25-2.1 = -Y (270). Short ends: Revit sheets are
  not mirrored -> rot180: А.2-Е.2 = -X (180), Е.2-А.2 = +X (0); weak (margin 0.008) and reported separately.
  Cross-check: the plan stair cores are on the Е side; model -Y has the three narrow core windows. Titles are
  read only to label GT; the matcher never reads page text except level marks for scale.
- **Method C (frozen):** view = raster images only (all vector paths dropped), rendered at 0.1 m/px using the
  page scale from signed level marks (Theil-Sen, median); views split on >= 3 m empty columns; window pixels
  luma < 0.45; body rows = non-white >= 90 % and dark <= 60 % (drops plinth, roof plant, ground line); profile =
  window fraction per column. Model = Blender 4.4 orthographic first-hit ray cast per azimuth 0/90/180/270 at
  0.1 m, profile = fraction of `WINDOW_*` first hits per column. Gaussian s=1.5 px, sliding NCC with 0.6 m
  slack; answer only if best >= 0.30 and margin >= 0.10 (#139 thresholds, unchanged). Empty/flat view -> no
  score -> abstain. Baseline A = #139 V0 width-only.
- **Bounds / outcome:** confirmed if, at the median of 3 fresh runs, C answers both long full views correctly,
  >= 9/18 long crops correctly, and makes 0 confident-wrong answers on all 40 clean cases in every run.
  Short-end answers count wrong if they differ from the rot180 GT. Refuted if measured and any bound is missed.
  Mirror control (separate, not pooled): count changed pixels per view (`not_exercised` if 0); a confident
  answer on a mirrored view that differs from the original face is recorded as a handedness risk.
- **Expected direction:** long faces differ in window rhythm (core windows on -Y, loggias on +Y), so C should
  separate them; short ends have no windows in the elevation -> C should abstain; V0 abstains everywhere.
- **Budget / stop:** one candidate, one baseline, three fresh runs (new ray cast + PDF read each). After run 1,
  continue only if 2 more runs at 2× run-1 wall time fit in 20 minutes. No threshold or variant change after
  scoring; a failure is published as refuted, not retuned. Stop at run 3 or on hash/extraction mismatch.
- **Forbidden:** editing the PDF, the accepted model or other cards' files; opening Sokolniki outputs; tuning
  on the scored set; deselecting tests; presenting synthetic crops as real untitled views.
- **Round 2 addendum (frozen after R1 scoring, before R2 scoring; post-hoc, in-sample — cannot confirm H141):**
  R1 showed two structural flaws (see Round log): dark cladding bands counted as glass, and an end view with
  no windows had no admissible windowless candidate. R2 = C with (a) vertical dark runs taller than 25 px
  (2.5 m, below the 3.0 m storey; glass is one storey at most) removed before the column profile and (b)
  abstain when the view's mean window fraction < 0.02 (low evidence). Model side, thresholds 0.30/0.10, crops
  and GT unchanged. Same three-run rule; R1 must replay byte-identical cases after the code change (parity).
  R2 outcome is labelled `diagnostic` (tuned on the scored cohort); the bounds above are reported for it but a
  pass would only justify a held-out test, never adoption.
- **Replay:** `uv run --offline --extra pdf-review python docs/research/autoresearch-view-face-raster/run.py <new_dir>`
  (pilot host: needs the Desktop PDF, `C:/Users/artsafro/.AGR_Project/jobs/OBR22-K02/outputs/` and Blender 4.4;
  preflight and postflight hash every input). Regression: `uv run --offline pytest -q
  docs/research/autoresearch-view-face-raster/test_score.py`.

## Round log and acceptance

**Hypothesis H141: `refuted`** (R1, measured, stable). **R2 (post-hoc diagnostic): refuted** under the same
bounds. **Run status:** finished within budget. **Handoff:** OBSERVE; review of the research branch only; no
production adoption or delivery claim.

Inputs were hash-checked before and after each of the 7 runs; all matched (receipt `postflight_equal_all_runs`).
Page scale from level marks: p14 0.141129 m/pt (60 marks), p15 0.141142 m/pt (59). The plan registration gave
0.14119 m/pt. Views found: 4/4, widths 89.0/17.5/88.9/17.5 m vs faces 89.0/16.4 m. Model ray cast: 5206 tris,
3564 window tris; window first hits: +Y 9072 px, -Y 7740 px, ±X 0 px (no end windows).

| Variant (3 fresh runs each, cases byte-identical) | Long full c/w/a | Long crops c/w/a | Short full c/w/a | Short crops c/w/a | Clean wrong / 40 |
|---|---:|---:|---:|---:|---:|
| V0 width (#139 baseline) | 0/0/2 | 0/0/18 | 0/0/2 | 0/0/18 | 0 (answers none) |
| R1 = C (frozen H141) | 1/1/0 | 8/6/4 | 0/0/2 | 0/15/3 | **22** |
| R2 = C + tall-run removal + low-evidence abstain (post-hoc) | 2/0/0 | 9/0/9 | 0/0/2 | 0/4/14 | **4** |

- R1 failure witness: `2.25-2.1/full`, NCC to its true face -Y = -0.2639 and to +Y = 0.4521 (margin 0.716):
  three full-height RAL 7024 bands are below the 0.45 luma limit and dominate the profile.
- R2 failure witness: `А.2-Е.2` and `Е.2-А.2` crop 0.25 at both edges (4.4 m) -> -Y with NCC 0.99, margin 0.54;
  the ±X faces have no windows and score -1 (not comparable), so the abstain margin is computed only between long faces.
- Mirror control (separate, all 4 exercised: changed px 236418 / 42904 / 198142 / 47450): R1 1 correct, 1 wrong
  (same as its clean result), 2 abstain; R2 2 correct, 2 abstain. A 1D column profile cannot detect handedness:
  a mirrored long view is still assigned (correctly here). Not evidence of handedness safety.
- Wall time per run 3.20-4.25 s (Blender ray cast 1.33-1.51 s); budget never limiting.
- **Not measured:** real untitled partial views, inner corners or non-axis faces (OBR22 K02 is a slab), vector-
  window input, Revit names/keyplans as algorithms, cross-project transfer of R2, finish-callout transfer and
  Sokolniki STOP 04 (#2001 open, held out).

Receipt: [`autoresearch-view-face-raster/receipt.json`](autoresearch-view-face-raster/receipt.json) (code and
input SHA-256, per-run result hashes, all per-case scores of R1 and R2). Evidence (7 run dirs, 2 view crops):
`G:/Мой диск/AGR-evidence/141-view-face-raster/` + `SHA256SUMS.txt`. Replay is limited to the pilot host
(Desktop PDF, local OBR22 outputs, Blender 4.4): `... run.py <new_dir> R1` and `... run.py <new_dir> R2`.

Affected tests: `env -u PYTEST_ADDOPTS uv run --offline --extra pdf-review pytest -q -p no:cacheprovider --basetemp C:/x/pt_t_c97df96b docs/research/autoresearch-view-face-raster/test_score.py` — 6 passed.

Full suite: deferred to merge batch (rule 68).
