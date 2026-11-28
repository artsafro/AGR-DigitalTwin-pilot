# #151 — Transfer of finish-partition view -> face (#149 D) to a second pair: Olimpijsky FOK (OBSERVE)

## Кратко для Артёма

Проверили, переносится ли признак #149 (цветовые заливки отделки на листе против имён типов Revit) без
перенастройки на второй объект — ФОК «Олимпийский» (лист АР.2 «Фасадные решения», 4 фасада + Revit FBX, 116 типов).
**Гипотеза опровергнута: признак не переносится.** 3 свежих прогона дали одинаковый результат.

- Полные фасады: 0 верно / **1 уверенная ошибка** / 3 воздержания. Фасад в осях 890ф-952.9ф (восточный) отдан
  южному фасаду с большим запасом (0,77 против 0,21).
- Причина 1 (видна ещё до подсчёта): на листах нарисованы соседние этапы (Котельная, Водный комплекс), поэтому вид
  шире своей грани модели (70 м против 60,6 м; 157 м против 147 м). Метод не может положить вид на свою грань и
  кладёт его на более длинную чужую — так и возникает уверенная ошибка.
- Причина 2: даже если резать вид окнами по ширине грани (диагностика G), разбиение «цвет ↔ тип Revit» почти
  одинаково хорошо совпадает со всеми гранями (0,7–0,94): здесь типы Revit (импосты, ламели, кассеты, окна)
  одинаковы на всех фасадах. G: полные 1/0/3, вырезки 9/2/25, зеркала 1/3/0 — тоже не годится.
- Вырезки 25–60 %: D 10 верно / 1 ошибка / 25 воздержаний (на ELV было 40/0/23).

Рекомендация для шага OKS «view<->face map sheet»: признак D нельзя ставить первым; это только подсказка. До
сравнения обязательно (1) обрезать вид по границе этапа / контуру модели и (2) проверять, что ширина вида
совпадает с шириной грани (±1 м); иначе — вопрос, не ответ. Противоположные фасады всё так же требуют вопроса,
если подпись/ось не разрешает. Код в продукт не вносился (OBSERVE).

## Frozen contract (committed before any score was computed)

Card t_a117effc (standing #151), focus 0 (view<->face map sheet). #2001 is OPEN: Sokolniki is held out and was not
opened. #149 (PR #2073, OPEN) confirmed D (PDF fill-colour partition vs Revit type partition, chance-corrected U,
#140 decide 0.30/0.10) on ELV only; its next step (1) and #150 next (2) ask for a transfer test of D **unchanged**
on a second coloured PDF + Revit FBX pair. This round is that test. No threshold, label or score change.

**Pair (never used by #139-#150).** Olimpijsky FOK (MFK «Олимпийский», vl. 16, etap 6, str. 4):
`АР.2_ Фасады_29.07.2026.pdf` (21 pages; p5-p8 = four 1:150 elevations, vector finish fills with 9-13 colours,
one view per sheet, title «Фасад в осях A-B» + situation plan with a red line on the shown side) and
`ZЦИМ01_Олимпийский02_ФОК02_АГР02_FBX.fbx` (Revit FBX for AGR: 48645 mesh objects, 116 Revit types after the
#149 R1b suffix strip, 0 materials, bbox 147.0 x 60.6 x 50.5 m, max object z 46.5 m). Both on the owner's PC
(`C:/Users/artsafro/Desktop/!3D viz/Dima_Andrew/`), SHA-256 in [`fixture.json`](autoresearch-view-face-transfer/fixture.json);
copies + `SHA256SUMS.txt` in `G:/Мой диск/AGR-evidence/151-view-face-transfer/inputs/`.

- **GT** (independent of any score): title convention (left axis -> right axis seen from outside) plus the red
  line on each sheet's situation plan, registered to the model by the roof ray-cast footprint (curved low podium
  on the -Y side and the +X end, stepped block at +X/+Y; same as the situation plan with 86ф left, 228.8ф right,
  952.2ф top). p5 «228.8ф-86.8ф» = az 90 (+Y), p6 «86.8ф-228.8ф» = az 270, p7 «952.9ф-890ф» = az 180 (-X),
  p8 «890ф-952.9ф» = az 0 (+X). Candidates az 0/90/180/270.
- **Boxes / scale** (frozen in the fixture, before scores): view drawing only; titles, axis bubbles, level marks,
  legend, situation plan and the callout-label row above the roof are outside. Scale from level marks +41.600 to
  +8.850 (18.901 pt/m on all four sheets = 1:150). Preflight (no scores): axis-bubble distances gave 19.12 (p6)
  and 19.40 (p8) pt/m, inconsistent with the level marks, so `scale_levels` is used for all views.
- **Cases** (#145 `cases`, unchanged): per view full, mirror (injected), 9 synthetic crops (25/40/60 % at
  0/0.5/1.0) = 44 rows.
- **Code**: #149 `run.py` `measure`/`summarize`, `score.py`, `rays_type.py` at `94b74bca` and #145 helpers at
  `640b3678`, staged from git and executed as is. Only byte change: the #145 ELV outlier-height skip in
  `rays_type.py` `> 30.0` -> `> 60.0` (this building is 46.5 m; 0 objects skipped by the probe).
- **Preflight geometry finding (recorded before scores).** The drawn views are wider than the model faces:
  p5 151.3 m, p6 156.8 m (model az 90/270 face 147.0 m), p7 72.9 m, p8 69.9 m (model az 0/180 face 60.6 m); the
  sheets draw parts of the neighbouring stages (Котельная, Водный комплекс, red «Граница этапов»). D slides the
  view inside the model face ± 0.6 m, so a wider view scores −1 on its own face: p5/p6 full can only abstain,
  and p7/p8 full can only fit the long faces — the wrong ones. This is the transfer hazard measured here.
- **Primary metric (D, unchanged).** correct / wrong / abstain per class (full, synthetic_crop, mirror).
- **Acceptance H151 (frozen).** D: full wrong 0, full correct ≥ 3 of 4, crop wrong ≤ 1, crop correct ≥ 15 of 36,
  witness `p5 228.8-86.8 full` correct. (By the preflight geometry full correct ≥ 3 and the witness are
  infeasible for D; they stay as the transfer bar. The informative D numbers are the wrong counts.)
  Invariance: reversed view-palette relabelling must change 0 of 44 rows (run 1, every row exercised).
- **Secondary, pre-declared diagnostic G** (not a keep; candidate for the shared step if it holds): D unchanged
  when the view fits the face; when the view is wider than face + 2 slack, slide face-width windows of the view
  (step 2·slack+1 px, gap-free with D's ±slack search), trim each window to its own top row, score with D, take
  the max. Bounds: G full wrong 0, full correct ≥ 3, crop wrong ≤ 1, G = D on every non-windowed row.
- **Not measured.** Real untitled partial views (this set has none; only synthetic crops), inner-corner /
  footprint-edge candidates, KPP1/AC08/OBR22/G22/Vatutino, Sokolniki (held out), within-face localisation,
  accepted-vs-rejected delivery quality, line-based A/C on this pair.
- **Replay and budget.** `git fetch origin research/autoresearch-standing-145 research/autoresearch-standing-149`,
  then `uv run --offline --locked --extra pdf-review python docs/research/autoresearch-view-face-transfer/run.py
  C:/x/ar151/<fresh>` (pilot host, inputs mounted; Blender 4.4 hash-checked). Three fresh runs (Blender import +
  ray cast + scoring each), byte-identical row JSON required; median/min/max wall reported. One candidate (D) +
  one pre-declared diagnostic (G). Stop `inconclusive` if elapsed + 1.15 × first-run s × remaining runs > 3600 s
  or on any parity failure; timing stop and hypothesis verdict are reported separately.
- **Forbidden.** Threshold/label/box/GT changes after seeing scores, fixture substitution, reading Sokolniki
  outputs, editing source drawings, models, deliveries, production `src/` or other cards' files, weakening guards.

## Result — H151 REFUTED (D does not transfer); G diagnostic refuted (OBSERVE, nothing applied)

Measured at contract commit `afb974f862885bf681c0aa143bc5459aa60edd5c` (runner unchanged after it), CPython via
`uv run --offline --locked`, Blender 4.4 `fd21f4b9...`. Status `finished`; three fresh runs (import + ray cast +
scoring each), row JSON byte-identical (`4305f98d...2636` x3); wall 240.965 / 205.637 / 198.174 s (run 1 includes
the invariance re-score), median 205.637 s, total 645.9 s; loaded workstation. Model: 1 667 525 tris, 116 types,
38-61 labels visible per face. Receipt: [`receipt.json`](autoresearch-view-face-transfer/receipt.json) (runner-written SHA-256
`dba5d8784ad25421e751b20c6d0f84c7700761eee437802b379872283a7fcca2`; Git LF `da62bd3072fb6ee4cfa919c7c5962738b87fe315388d41ba24b847828a83d971`); evidence
`G:/Мой диск/AGR-evidence/151-view-face-transfer/` + `SHA256SUMS.txt` (inputs, run JSON, label npz, Blender logs,
probe scripts).

Correct / wrong / abstain (44 rows):

| Class | ELV #149 D (ref.) | **D, this pair** | G (diagnostic) |
|---|---|---|---|
| full (4) | 6/0/1 of 7 | **0/1/3** | 1/0/3 |
| synthetic crops (36) | 40/0/23 of 63 | **10/1/25** | 9/2/25 |
| mirror, injected (4; all exercised) | 2/1/4 of 7 | 0/2/2 | 1/3/0 |

Checks (frozen): full wrong 0 ✘ (1); full correct ≥ 3 ✘ (0); crop wrong ≤ 1 ✔ (1); crop correct ≥ 15 ✘ (10);
witness `p5 full` ✘ (abstain, all −1). Invariance: reversed palette relabelling changed 0 of 44 rows ✔. G: full
wrong 0 ✔, full correct ≥ 3 ✘ (1), crop wrong ≤ 1 ✘ (2), G = D on all non-windowed rows ✔.

What happened (not hidden):
- **Width hazard, confident wrong.** `p8 890-952.9 full` (GT az 0, view 69.9 m) cannot fit its own 60.6 m face
  (−1) and is assigned to the 147 m south face az 270 (0.768 vs 0.214). Same mechanism on `p7 full` (only long
  faces score, 0.962 vs 0.871 → abstain by margin) and on both short-view mirrors (wrong). p5/p6 full score −1 on
  every face. The preflight predicted this before scoring.
- **Saturation, low specificity.** Once the width is removed (G), the true face often wins but other faces score
  almost as high: p5 full G 0.905 (az 0) / 0.869 (GT az 90); p6 full 0.872 (GT) / 0.784; p8 full G correct 0.940
  vs 0.768. Revit types here (imposts, lamellas, cassettes, windows) repeat on all facades, so U(V|M) is high for
  any face; on ELV the finish types differed per facade.
- **Crops** answer mainly where elimination does the work: 40/60 % crops of the long views (61-94 m) are wider than
  the short faces, so D picks between the two long faces; p6 crops 6/0/3 with margins 0.62-0.85, p7 crops 0/0/9,
  p8 1/0/8. Wrong crop `p5 partial25@0.0` (37.8 m, the «Спортивный комплекс» end) → az 0 (0.885 vs 0.741).
- Palettes 7-10 colours per view; fills fully inside the boxes only.

Not measured: real untitled partial views (none in this set), inner-corner/footprint-edge candidates, line-based
A/C on this pair, other cohort projects, Sokolniki (held out, #2001 OPEN), within-face localisation.

Recommendation for the shared OKS-trail step 'view<->face map sheet' (measured, OBSERVE): D is **not** a primary
assigner across projects. Before any content score, the step must (1) clip the view to the model's own stage
(stage-boundary lines «Граница этапов» / the model outline at the same scale) and (2) gate candidates by physical
width (|view width − face width| ≤ 1-2 m at the level-mark scale) — abstain-and-ask when no face passes; this gate
alone would have turned the one confident full-view wrong into an abstain. Use D only as a tie-breaker among
width-compatible candidates whose type sets differ per facade (measure "type-set distinctness" per model first);
keep opposite-face pairs and every abstain as a 2-candidate question. Sheet title + situation-plan red line was
an exact, cheap GT source on this booklet (4/4 views): reading that keyplan mark is the first cue to measure next.

Replay: `git fetch origin research/autoresearch-standing-149` (the #145 commit `640b3678` is in `main` via
PR #2055), then the command in the contract. Replay is limited to the pilot host (inputs on the owner's PC;
copies with hashes in the evidence folder above).
