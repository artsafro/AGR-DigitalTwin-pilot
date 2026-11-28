# Autoresearch #161 — view -> wall direction by drawn glass vs model glazing (Silikatny, OBSERVE)

## Кратко для Артёма

Нашёл в твоих проектах новую пару «альбом + модель» с настоящими видами внутреннего угла: Силикатный, учебный
корпус УК350/ДО150 (Моспроект-4). Альбом АГР на 35 листов: 5 схем фасадов и 2 реальных фрагмента 1:20 (один — зона
изогнутой лестницы со стороны двора), модель Revit из DWFx (R23) по категориям, план V-образный, с вогнутым двором.
Ни один раунд #139-#160 эту пару не использовал. Сокольники не открывал: #2001 ещё открыт.

Проверил один способ: маска остекления с листа (цвета, которых нет в легенде) против окон и витражей модели в
ортопроекции с 8 направлений стен. Порог ответа и запас взял из #140 без подстройки.

- **Гипотеза H161 опровергнута:** 0 верных, 1 неверный, 4 отказа из 5 видов с известным ответом. Фасад А'-К
  (7 эркеров) отнесён к направлению 0° вместо 330°: это та же стена, видимая под углом 30°. По замороженному
  правилу это ошибка.
- Оба вида внутреннего угла (развёртка 1-4' и фрагмент 2) — отказ. Верное направление в обоих случаях на первом
  месте, но два соседних верных направления 240°/270° отличаются меньше чем на 0.10.
- Правильное направление всегда входит в два лучших (5 из 5). Путаются только соседние направления, отстоящие на
  30°: ортопроекция с соседнего направления показывает ту же стену, сжатую в 0.87 раза. Дополнительно масштаб вида
  завышен примерно на 8 % (в рамку попадает линия земли), а это сжатие подыгрывает соседу.
- Для шага «карта вид↔грань»: сравнивать вид надо с фронтальным рендером каждой стены отдельно (стена = отрезок
  плана, а не направление камеры), с проверкой ширины. Ответ давать только при запасе над несоседними стенами. По
  одному направлению камеры отвечать нельзя.

## Frozen contract (committed before any score was computed)

Card t_4246c1cc (standing #161), focus 0 (view<->face map sheet). #2001 is OPEN: Sokolniki is held out and was not
opened. Rounds #145-#160 all ended with next step (1) "an independent album with REAL inner-corner views"; ELV,
Olimpijsky, OBR22, KPP1, AC08, Savelovskaya and Moskovsky have none. #2073/#2074 own finish-partition scoring,
#2075 owns wall exercise; atlas / form / trainer targets were not reopened.

**Fixture (never used by #139-#160; screened in this card).** Silikatny UK350/DO150 school (Mosproekt-4), Weltbau
`Silikatniy_UVK`: AGR album `Альбом АГР_Силикатный_ корр. Гранель 08.04.25 (2).pdf` (35 p, SHA-256 `785e4015…9131`)
and the Revit model exported from DWFx R23 by category, `context_full_model_by_category.obj` (17 category objects,
1.72 M tris, SHA-256 `6ab64e6b…ea62`). The plan is V/7-shaped (left wing, top wing, oblique wing at 60 deg) with a
concave courtyard side carrying a curved glazed stair. Views: 5 full facade schemes (p14 1-4', 4'-1; p15 K-A, A-G,
A'-K) and 2 real 1:20 fragments (p16 box bay, p17 curved stair zone, both titled only «Фрагмент фасада»). The
GRN_2_SLK FBX in the same folder is the neighbouring residential complex, not this school (checked: heights to 245 m).
Known confound, recorded before scoring: the album is dated 08.04.25 and the model is R23 (28.08.26) with renamed axes
(1-12 / A-1..Ж-1 in the R23 facade DWG vs 1-4' / A..K in the album); content drift is part of the test.

**GT (model geometry + visibility only, labelled before scoring; titles not used by the method).** Candidate
directions = the 8 peaks of the area-weighted horizontal normal histogram of `Ctx_steny` (0, 60, 90, 150, 180, 240,
270, 330). A'-K and fragment 1 = the oblique wing's curtain-wall side with 7 projecting glazed boxes, normal 330 (box
glass normals 150/330 at x 62-89 m; the boxes are visible from 330 and only obliquely from 0/270) -> {330}. 4'-1 = the
large glazed truss block on the top wing's north side -> {90}. 1-4' (developed courtyard facade) and fragment 2 (the
truss/screen/stair zone on the concave side) -> {240, 270} (the V-truss block is seen frontally between those two
directions; both accepted). K-A and A-G: no independent GT within this card -> diagnostic rows, not scored.
Inner (courtyard) views: 1-4' (full, developed) and fragment 2 (real partial). Hard negatives: the opposite direction
(reported per row) and the near-parallel neighbour 0 for the 330 views.

**Candidate G (one, frozen in `autoresearch-view-face-glass/fixture.json`).** View: page raster at zoom 4 inside a
fixture clip; building = pixels with RGB sum < 760; view box = bbox after a 7 px opening; glass = building pixel, not
red, farther than 45 RGB units from every legend swatch on p15 (RAL 1013 panel, RAL 5001, RAL 7031, white) and
luminance 100-225. Vertical scale: the box spans 0.000-12.900 (parapet level on every sheet; fragment 1 dimension
chain sums to 12 900); isotropic. Model: Blender 4.4 Workbench orthographic renders per candidate az at 0.1 m/px,
`Ctx_okna` + `Ctx_paneli_vitrazha` black, all else grey, slabs hidden; band z 0-12.9 m. Both masks resampled to
0.25 m. Score(az) = max Pearson NCC over horizontal offsets with overlap >= 0.8 x the narrower width. Answer = top az
if score >= 0.30 and margin to the best other az >= 0.10 (the #140 frozen values, inherited, not tuned), else
abstain. Pre-score check (boxes and masks only, no NCC) is recorded below.

**Primary metric.** correct / wrong / abstain on the 5 scored views; answered accuracy = correct / answered (undefined
if 0). Secondary: inner views separately (2), fragments separately (2), opposite-direction score per row.

**Acceptance H161 (frozen).** wrong = 0 on the 5 scored rows, AND correct >= 3/5, AND at least one of the
two inner views correct. Wrong >= 1 or correct < 3 refutes. Positive trigger witness: A'-K must answer (it has the
strongest unique glazing pattern); abstention witness: every `blank` state must abstain.

**Perturbations (constructed, per state changed-pixel counts recorded).** `mirror`: view mask flipped left-right —
expected: the true az no longer wins with margin (abstain or other az); a pattern-blind scorer would still answer. Near-symmetric views (A'-K, F1) may legitimately keep the true az; mirror is reported per row and is not part of acceptance.
`blank`: glass mask zeroed — expected abstain (NCC undefined -> 0). Not measured: rotated sheets, fresh native
re-export from Revit, rejected deliveries (none exist for this object), Sokolniki transfer (held out), wall
interval/bay localisation (a fragment's offset is reported, not scored), K-A / A-G identity.

**Stability / budget.** Replay `uv run --offline --locked --extra pdf-review python
docs/research/autoresearch-view-face-glass/run.py C:/x/ar161/<fresh>` (pilot host with the owner's Weltbau folder;
Blender 4.4). Three fresh runs, each re-renders the model and re-reads the PDF; row JSON must be byte-identical;
median / spread wall time reported. One candidate, no retuning after the first score; a failed row is reported, not
fixed. Stop `inconclusive` if the three runs exceed 30 min in total or on a parity failure.

**Forbidden.** Changing params, GT, clips or states after a score; opening Sokolniki outputs; editing source drawings,
models, deliveries, production `src/` or other cards' files; weakening guards.

## Pre-score check (no NCC computed)

View boxes / widths (m) / glass fraction: A'-K 73.4 / 0.49; 4'-1 91.6 / 0.28; 1-4' 83.4 / 0.25; F1 10.7 / 0.58;
F2 10.9 / 0.79; K-A 54.9 / 0.22; A-G 27.2 / 0.32. The masks show window rows, the 7 boxes and the truss blocks;
F1/F2 boxes touch their clips (the 1:20 sheets carry dimension chains inside the clip) — kept as frozen.

## Round log

**H161 refuted.** Contract `a5b2ca7e` (frozen before any score). Runner SHA-256 `978ad7d4…`, fixture `9ce8c9eb…`.
Three fresh runs, each a new Blender render plus a new PDF read: rows byte-identical (`f1209644…6b6d`). Wall time
10.321 / 10.115 / 10.677 s, median 10.321 s, spread 0.562 s, `finished`. Input hashes were checked before and after
each run. Receipt: [`receipt.json`](autoresearch-view-face-glass/receipt.json). Evidence (renders, masks, 3 results,
sheet previews): `G:/Мой диск/AGR-evidence/161-view-face-glass/` + `SHA256SUMS.txt` (20 files, verified).

| View (GT az) | Top az (score) | Runner-up | Margin | Outcome |
|---|---|---|---:|---|
| A'-K, 7 boxes ({330}) | 0 (0.735) | 330 (0.522) | 0.213 | **wrong** |
| 4'-1, truss block ({90}) | 90 (0.632) | 60 (0.560) | 0.072 | abstain |
| 1-4', courtyard, developed ({240,270}) | 240 (0.394) | 270 (0.380) | 0.014 | abstain |
| fragment 1, box bay ({330}) | 0 (0.681) | 330 (0.677) | 0.003 | abstain |
| fragment 2, curved stair ({240,270}) | 240 (0.355) | 270 (0.353) | 0.002 | abstain |
| K-A (no GT) | 180 (0.610) | 90 (0.362) | 0.249 | diagnostic |
| A-G (no GT) | 270 (0.525) | 60 (0.468) | 0.058 | diagnostic |

Primary: correct 0 / wrong 1 / abstain 4 of 5. Answered accuracy is 0/1, abstain rate 4/5. Inner views: 0 correct,
2 abstain. Fragments: 0 correct, 2 abstain. Acceptance fails on all three counts (wrong 1, correct < 3, no inner view
correct). The positive witness, A'-K, answered, but in the preregistered hard-negative direction 0.

**Perturbations (exercised; the receipt has per-row changed cells).** `blank` changed 2 067-9 810 cells per view and
abstained on 7 of 7, so the abstention witness passes. `mirror` changed 1 768-10 108 cells per view and abstained on 6
of 7. Near-symmetric A'-K kept 0; the true direction was not answered on any mirrored row.

**Failure analysis.** These are reported, not fixed, and the verdict does not change.
(1) The true direction is in the top two on 5 of 5 views. Every confusion is with a direction 30 deg away. An
orthographic render along a neighbouring direction shows the same wall compressed by cos 30 = 0.87. A direction-level
candidate set therefore holds near-duplicates, so a margin over "best other az" cannot separate them, and on the
inner views it also penalises the second correct direction.
(2) Scale bias: the view box includes the ground line, so the box spans about 370 px against about 340 px for
0.000-12.900 from the p15 level marks. That makes the view about 8 % too short, which favours the compressed
neighbour; A'-K reads 73.4 m against about 80 m.
(3) Drift: the album (04.2025) shows a wider glazed stair zone on 1-4' than the R23 model.

**Post-hoc D1 (diagnostic, NOT a keep, computed from the same frozen scores).** This takes the margin against the
best direction more than 30 deg away. 4'-1 gives correct 90 with margin 0.252. A'-K is still wrong (0, margin 0.361).
1-4', F1 and F2 abstain (margins 0.087 / 0.054 / 0.089). Result: 1 / 1 / 3 — still refuted, and the direction-cluster
cue alone does not resolve inner views.

**Not measured:** wall identity and bay interval (a fragment's offset is recorded, not scored); K-A and A-G identity;
fresh Revit re-export; rejected deliveries (none exist for this object); Sokolniki transfer (#2001 open).

## Recommendation for the shared OKS step 'view<->face map sheet' (OBSERVE, not built here)

1. Make candidates per wall, not per camera direction. Render each footprint wall segment frontally (camera along
   its own normal, clipped to the segment) and score the view against each wall. Width compatibility should come
   from level-mark scale (0.000 / parapet ticks), not from the box height. The opposite wall and the 30 deg neighbour
   stay hard negatives.
2. Do not answer from a direction-level glass NCC. On this fixture it gives 1 wrong out of 1 answer, and the wrong
   answer is the neighbour direction.
3. Inner-corner views need a wall-level answer or a question. Both real inner views here abstained, which is the
   behaviour STOP 04 should keep until (1) is measured.

## Next measured steps

1. Re-run on the same frozen Silikatny fixture with per-wall frontal renders and a level-mark scale. GT walls come
   from this contract; the score is wall-level correct / wrong / abstain.
2. Add GT for K-A and A-G from the album's p6 axis bubbles registered to the model footprint, which brings the
   fixture to 7 scored views.
3. Blind Sokolniki transfer only after #2001 closes.

Full suite: deferred to merge batch (rule 68).
