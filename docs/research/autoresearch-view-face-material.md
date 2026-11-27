# #149 — Finish-partition agreement for elevation view -> model face (OBSERVE)

## Кратко для Артёма

Новый признак для привязки вида фасада к грани модели: **цветовая заливка отделки на листе АГР** против
**имён типов Revit** на гранях модели (кассета «WOOD», сэндвич-панель, Стемалит, ламели RAL 7021 и т.п.).
Мера не зависит от того, каким цветом нарисован материал: сравнивается только разбиение на зоны
(взаимная информация с поправкой на случайность). Проверено на ТЦ «Среда» (ELV), 80 видов с известным ответом,
3 свежих прогона дали одинаковый результат.

- Полные фасады: 6 верно / 0 ошибок / 1 воздержание (было у лучшего прошлого метода #147: 5/0/2).
- Реальные фрагменты Д–Г и 8–9: **2/0/0** (раньше 1/0/1; фрагмент 8–9 впервые привязан). Фрагмент с обрезанным
  верхом — воздержание.
- Синтетические вырезки 25–60 % ширины: **40/0/23** (было 14/1/48). Ни одной уверенной ошибки на чистых видах.
- Слабое место: зеркально отражённый вид северного фасада метод уверенно отдал южному (1 ошибка из 7 зеркал).
  9 из 48 верных ответов прошли с запасом < 0,15 при пороге 0,10 — запас тонкий.
- Гипотеза **подтверждена только на ELV**. KPP1, AC08, OBR22, G22, Vatutino не измерены (нет цветных
  векторных видов или имён типов в закреплённых входах); Сокольники не открывались (#2001 открыт).
- Первый прогон R1 был с ошибкой: имена объектов Revit не обрезались до типа (7132 «типа» вместо 204) — так он дал
  2 уверенные ошибки на полных фасадах. Вывод: признак работает только на уровне ТИПА, не экземпляра.

Рекомендация для общего шага OKS «view<->face map sheet»: если вид на листе залит цветами отделки и в модели есть
имена типов Revit, первым ставить этот признак (D) с порогом 0,30/0,10 и отказом при меньшем запасе; линии (#140/#147)
— только при отсутствии заливок; зеркальную неоднозначность (противоположные фасады) всегда выносить вопросом, если
ось/подпись не разрешает её. Код в продукт не вносился (OBSERVE).

## Frozen contract (committed before any score was computed)

Card t_141c9690 (standing #149), focus 0 (view<->face map sheet). #2001 is OPEN: Sokolniki is held out and was
not opened. Rounds #139-#148 used line/edge or raster-luma cues and plateaued on two confounders: the
dense-edge attractor (ELV east curtain wall, #145) and periodic bays (#143/#144). This round measures a cue that
uses neither edge density nor rhythm.

**H149.** On the ELV TC Sreda vector booklet the elevation views are colour-filled by finish (vector fill paths),
and the Revit FBX keeps the Revit family type name per object (`Базовая стена (AR)_metall kasset WOOD`,
`Системная панель Стемалит`, `(SC)-Batten_RAL 7021`, ...). The FBX has a single Blender material, so object
type, not material, is the model finish label (feasibility probe: 1 material, 9773 mesh objects). A
label-permutation-invariant agreement between the view's fill-colour partition and the model's type partition
assigns views to faces with fewer confident errors than #147 C at equal or better coverage.

- **Fixture (pinned).** Exactly the #145 ELV inputs and views (`autoresearch-view-face-elv/fixture.json` at
  `origin/research/autoresearch-standing-145`, PDF SHA-256 `49c10527...9545`, FBX `7ccf502d...b961`), the same
  80 cases (7 full, 7 mirror, 63 synthetic crops 25/40/60 % at 0/0.5/1.0, 2 real fragments, 1 top-cut
  fragment), same view extents and crop offsets computed by the #145 segment raster at 0.1 m. Row identity
  parity (view, case, width_m) against the #147 receipt rows is checked; any mismatch stops the run.
  Candidate faces: az 0/90/180/270 (as #145). GT: #145 fixture `gt_az` (title convention + roof footprint);
  titles, axis bubbles and level marks are outside the boxes and are not read for the face.
- **Model labels (D).** Blender 4.4 (hash-checked) orthographic ray cast, same frame and skip list as #145
  `rays_elv.py`, 0.2 m/px, label = Revit type name = object name with the trailing instance suffix removed
  (`re.sub(r"[\d_.\[\]#-]+$", "", name)`), 0 = no hit.
- **View labels (D).** Fill paths (`get_drawings()` with a fill, fill_opacity > 0) fully inside the #145 box,
  painted in drawing order (later on top) as polygons (`re`, `qu`, `l`/`c` endpoints; even-odd holes ignored),
  rasterised at 0.05 m and reduced to 0.2 m by majority of filled sub-pixels; label = fill RGB rounded to 0.02;
  0 = unfilled. View raster spans the #145 metric x-extent and the segment y-extent.
- **Score (D).** For each candidate and each horizontal offset (1 px step, ±0.6 m slack, as #140) with the view top
  aligned to the model top in that column window and vertical shifts −3..+3 px: over pixels where the view is
  filled AND the model has a hit, `U = (I(V;M) − (|V|−1)(|M|−1)/(2N)) / H(V)` (nats, Miller–Madow chance term,
  |V|,|M| = labels present in the overlap). Score −1 if the overlap N < 30 % of the view's filled pixels.
  Face score = max over offsets/shifts. Decision = #140 `decide` unchanged: best ≥ 0.30 and best − second ≥ 0.10,
  else abstain.
- **E (pre-declared secondary).** C (#147 receipt, raw/chance agreement) where C answers; D only where C abstains.
- **Primary metric.** correct / wrong / abstain per class (full, synthetic_crop, fragment, fragment_top_cut,
  mirror). Mirror = injected negative scored under the #145 oracle; changed filled-label pixels recorded per row,
  0 changed = `not_exercised`.
- **Acceptance (frozen).** H149 confirmed iff D has 0 wrong on full and on real fragments, ≤ 1 wrong on synthetic
  crops, and ≥ 15 correct crops (> C 14, = A 15). E bound: clean wrong (full+fragments+crops) ≤ 1 and crop
  correct ≥ 20. Positive witness: `p18 I-A` full (east curtain wall) answered correct. C residual witness:
  `p19 A-I partial25@1.0` (C wrong) must be abstain or correct under D. Invariance witness: permuting the view
  colour labels must leave every D score bit-identical (exercised on all 80 rows).
- **Not measured.** KPP1, AC08, OBR22 (pinned inputs have no colour-fill views / not checked for type labels),
  G22, Vatutino, Sokolniki transfer; accepted-vs-rejected delivery quality. Synthetic crops test face identity,
  not localisation within the face.
- **Replay and budget.** `uv run --offline --locked --extra pdf-review python
  docs/research/autoresearch-view-face-material/run.py C:/x/ar149/<fresh>` (pilot host, mounted inputs). Three
  fresh runs (ray cast + scoring each), byte-identical row JSON required; report median/min/max wall. One
  candidate (D, plus E derived), no threshold or label tuning, no second candidate under this contract. Stop
  `inconclusive` if elapsed + 1.15 × first-run seconds × remaining runs > 1500 s or on any parity failure.
  Timing stop and hypothesis verdict are reported separately.
- **Forbidden.** Threshold/label search after seeing scores, fixture substitution, reading Sokolniki outputs,
  editing source drawings, models, deliveries, production `src/` or other cards' files, weakening guards.

## R1 — aborted as implemented (defect), amendment R1b frozen before any R1 score was read

R1 at `ec6eb642` ran one fresh run (1149.6 s incl. the invariance re-score), then hit the budget stop
(1149.6 + 1.15 × 1149.6 × 2 > 1500 s) and crashed in `combine` (the #147 receipt mixes ELV rows, keyed `case`,
with OBR22 rows keyed `kind`). The ray log showed the frozen *quantity* was not computed: 9773 objects gave
**7132 "types"** — Revit FBX names end in `_<7 hex>`, ` [<element id>]`, `_[<id>]` and `.001`, which the frozen
regex does not strip, so labels were near-instance ids, not Revit type names. R1 is recorded as a defective
implementation (`status: aborted_defect`); its single-run scores are diagnostic only and are reported below
next to R1b, never as the hypothesis test.

R1b changes only the implementation, all derived from the name format and the crash, none from scores:
1. Type name = object name with trailing `(\.\d{3}|_[0-9a-f]{7}|_?\[\d+\]|\s+)` removed repeatedly until stable.
2. Model labels compacted per face (`np.unique` inverse) before scoring — U is label-permutation invariant, so
   scores are unchanged; this only shrinks the joint histogram (speed).
3. `combine` uses the 80 #147 rows that carry `case` (ELV); row identity parity unchanged.
4. Budget re-frozen from the one measured R1 run: stop `inconclusive` if elapsed + 1.15 × first-run s ×
   remaining runs > 3600 s. Everything else in the contract above is unchanged (labels for the view, score,
   decision 0.30/0.10, acceptance bounds, witnesses, 3 fresh runs).

## R1b — result: H149 CONFIRMED on ELV only (OBSERVE, nothing applied to production)

Measured at `200726691ee7317bc1710ecc3f8e1bbf1456937b`, CPython via `uv run --offline --locked` (uv.lock
`ba1bb998...`), Blender 4.4 `fd21f4b9...`. Status `finished`; three fresh runs (ray cast + scoring each), row JSON
byte-identical (`200fe696...e4cb` x3); wall 91.959 / 59.101 / 60.120 s (run 1 includes the invariance re-score),
median 60.120 s, total 211.7 s; loaded workstation, not an idle-host benchmark. Model: 9773 mesh objects -> 204
Revit types, 31-47 visible per face. Receipt: [`receipt.json`](autoresearch-view-face-material/receipt.json)
(SHA-256 `603872c823c41ed768a1f8a47503c4f35b4d86af290f6ee45ebea7ed02b223a9`); evidence
`G:/Мой диск/AGR-evidence/149-view-face-material/` + `SHA256SUMS.txt` (R1 and R1b runs, label npz, Blender logs).

Correct / wrong / abstain (ELV, 80 rows):

| Class | A #140 raw | C #147 | **D #149** | E = C else D |
|---|---|---|---|---|
| full (7) | 5/0/2 | 5/0/2 | **6/0/1** | 6/0/1 |
| real fragments (2) | 1/0/1 | 1/0/1 | **2/0/0** | 2/0/0 |
| fragment, top cut (1) | 0/0/1 | 0/0/1 | 0/0/1 | 0/0/1 |
| synthetic crops (63) | 15/13/35 | 14/1/48 | **40/0/23** | 43/1/19 |
| mirror, injected (7) | 2/1/4 | 2/1/4 | 2/1/4 | 2/1/4 |

Checks (all frozen): full wrong 0 ✔; fragments wrong 0 ✔; crop wrong ≤ 1 ✔ (0); crop correct ≥ 15 ✔ (40);
positive witness `p18 I-A` full (east curtain wall, the #145 attractor) correct ✔; C residual witness
`p19 A-I partial25@1.0` -> D abstains ✔ (0.685 vs 0.634); invariance: reversed view-palette relabelling changed
0 of 80 rows ✔ (exercised on every row in run 1). E bounds pass (clean wrong 1 ≤ 1, crop correct 43 ≥ 20), but
E's only wrong is C's inherited crop: D alone dominates E on safety.

Residuals (not hidden): the wrong mirror is `p19 10-1` mirrored -> az 270 (0.440 vs 0.160): a mirrored north
elevation reads as the south one — opposite-face mirror ambiguity is not resolved by finish partition. `p19 6-1`
full abstains (0.851 vs 0.787 az 270, the same finish set on the opposite wall). Margins are thin: 9 of 48 correct
clean answers have margin < 0.15 (minimum 0.104), so a small threshold change would move coverage; no threshold
was searched. Abstentions concentrate on the narrowest crops (25 %: 11, 40 %: 9, 60 %: 3).

R1 (defective instance-level labels, 7132 labels, single run, diagnostic only; `G:/.../r1/run-1.json`
`f634aef6...ba75`): full 0/2/5, crops 8/0/55, fragments 0/0/2, mirror 1/0/6. Instance labels produce confident
wrong full assignments — the cue must be type-level (or material-level), never per-object.

Not measured: KPP1, AC08, OBR22, G22, Vatutino (no colour-fill vector views / model type names in the pinned
inputs), within-face localisation (which bay), footprint-edge candidates (inner corners; only 4 azimuths here),
NPM/VPM deliveries whose material names replace Revit types, and Sokolniki (#2001 open, held out).

Recommendation for the shared OKS-trail step 'view<->face map sheet' (measured part, OBSERVE): per view, if the
sheet view has vector finish fills and the model carries Revit type (or finish-material) names, score D first
(0.30/0.10, abstain below) and expose top-2 with scores; fall back to #147 C (A=B agreement) only when the view has
no fills; route every abstain and every opposite-face pair (az and az+180 within the margin, or a mirrored-looking
view) to a 2-candidate question. Before implementing: (1) transfer test on a second coloured AGR booklet + Revit
model (and on Sokolniki after #2001 closes, without retuning); (2) footprint-edge candidates for inner corners.
