# H163 — Silikatny: view -> WALL by frontal per-segment renders (OBSERVE)

## Кратко для Артёма

Проверил следующий шаг #161/#162 на том же Силикатном: кандидат теперь — отдельная СТЕНА (отрезок плана), снятая
фронтально по своей нормали и обрезанная по своей длине и глубине, а не направление камеры. Вид может попасть только
на стену, в которую он помещается по ширине. Сокольники не открывал (#2001 открыт).

- **H163 по замороженному правилу подтверждена:** 2 верных, 0 неверных, 3 отказа из 5. Фасад А'-К (7 эркеров) теперь
  верно лёг на стену W19 (у #161/#162 была ошибка — соседнее направление 0°). Фрагмент 1 (реальный частичный вид,
  10,7 м) верно лёг на W19 среди 11 подходящих по ширине стен, с запасом 0,16. Изогнутая лестница (внутренний
  угол), развёртка двора и северный фасад из нескольких плоскостей — честный отказ: подходящей стены нет.
- **Но внедрять так нельзя.** Ответ по А'-К держится на исключении по ширине: W19 — единственная стена, куда влезает
  74 м. Тем же исключением метод отнёс к W19 и диагностический фасад К-А (55,8 м, 9 окон в ряд, без эркеров) — по
  листу видно, что это другой фасад. Перемешивание пролётов ответы на А'-К и фрагменте 1 не сняло: держит доля
  стекла, а не ритм. Правило «один кандидат — сравнивать с нулём» небезопасно.
- **Вывод для шага «карта вид↔грань»:** кандидаты по стенам убирают ошибку «соседнее направление»; частичный вид
  можно ставить на стену при запасе ≥ 0,10 над другими стенами, в которые он помещается. Ответ без соперника (одна
  подходящая стена) — только вопрос Артёму. Внутренние углы этим набором пока не измерены: изогнутая стена не
  стала кандидатом.

## Frozen contract (committed before any score was computed)

Card t_627437b1 (standing #163), focus 0 (view<->face map sheet). #2001 is OPEN: Sokolniki held out, not opened.
Takes #161/#162 next step (1): candidates per footprint WALL (plane segment), not per camera direction. #161 showed
every confusion was the 30-degree neighbour direction (the same wall compressed by cos 30); #162 showed datum scale does
not fix it (A'-K still wrong 0 instead of 330). #2073/#2074 own finish-partition scoring, #2075 wall exercise;
atlas/form/trainer not reopened.

**Fixture (unchanged from #161/#162).** Silikatny album PDF SHA-256 `785e4015…9131`, Revit OBJ by category
`6ab64e6b…ea62` (pinned in #161 `fixture.json` at `f4a7f22b`), Blender 4.4 `fd21f4b9…77b5`. Same 7 views and clips;
view masks = exact #162 `native_drawing` + `register` with the #162 datum anchors (pinned #162 `run.py` blob
`9492c08c…0f54` at `238e576d`). Grid 0.25 m, band z 0–12.9 m, NCC/offset/overlap 0.8 = #161 `best_offset`.

**Candidates (one variant, `blender_walls.py` + `params.json`, frozen).** Exterior vertical faces of `Ctx_steny`,
`Ctx_okna`, `Ctx_paneli_vitrazha` (|nz| < 0.2, area >= 0.05 m², centroid z 0–12.9; exterior = 45-degree sky ray
along the normal hits nothing within 300 m). Faces within ±12° of the 8 #161 directions; per direction cluster plane
offset (gap > 1.0 m splits) then connected u-runs (gap > 4.0 m splits); keep runs with area >= 10 m² and length >= 4 m.
Each wall is rendered frontally: ortho camera along its own normal, lateral window = run + 1 m each side, depth window
5 m in front of the plane to 3 m behind (camera clip), glass objects black, others grey, slabs hidden, 0.1 m/px.

**Decision.** Eligible wall: drawn view width <= 1.10 × wall render width (a view must fit on its wall). Answer = top
eligible wall if NCC >= 0.30 and margin over the best other eligible wall >= 0.10 (#140 values, inherited); with one
eligible wall the margin is against a null candidate (0). No eligible wall -> abstain.

**Pre-score geometry check (walls only, no view scored; `C:/x/ar163/probe1`).** 64 003 vertical facade faces in the band,
9 543 exterior; 20 walls W00–W19. Key: W19 az 330, L 70.07 m, (59.11,−18.53)–(94.15,42.15) = oblique wing curtain-wall
side with the 7 glazed boxes; W17 az 270 L 38.4 m = top wing courtyard side; W09 az 150 L 22.1 m = oblique wing
courtyard side; W13 az 180 L 38.3 m; W04/W06/W07/W08 north side pieces at three plane offsets (14–26 m each). The
curved glazed stair (courtyard) yields NO wall (its normals spread over many directions; runs < 4 m). Longest wall
70.07 m -> eligibility limit 79.3 m.

**Wall-level truth (frozen here, from geometry and #161 labels, before any score).**

| View | Truth | Expected non-wrong outcome |
|---|---|---|
| A'-K (73–74 m, 7 boxes) | W19 | correct = W19 |
| fragment 1 (box bay, 10.7 m) | W19 | correct = W19 |
| 4'-1 (92.8 m, north, several planes) | no single wall | abstain (wider than every wall) |
| 1-4' (84.3 m, developed courtyard, inner) | no single wall | abstain |
| fragment 2 (curved stair, inner) | curved zone, no candidate | abstain; any answer = wrong |
| K-A, A-G | none | diagnostic only |

So this design CANNOT score an inner view correct; inner rows test only that it does not guess. That is a declared
limit, not a result.

**Primary metric.** correct / wrong / abstain on the 5 scored rows; answered accuracy correct/(correct+wrong).
Secondary per row: truth-wall score vs best opposite-direction wall and best 30°-neighbour wall (hard negatives).

**Acceptance H163 (frozen).** All of: wrong = 0; A'-K = W19 (positive witness, #161/#162 wrong row flips); fragment 1 =
W19 (a real partial view placed on its wall among >= 2 eligible walls); fragment 2 abstains; `blank` abstains on 7/7;
on at least one clean-answered row the `shuffle` state abstains (content, not width elimination, carries the answer);
3 pairs byte-identical. Any miss refutes.

**Perturbations (per-state changed cells recorded).** `mirror` (left-right flip; reported, near-symmetric rows may
keep), `blank` (zero mask; must abstain), `shuffle` (2 m column blocks permuted, seed 163: same glass amount, bay order
destroyed; expected to lose the margin on content-carried answers). Candidate-order reversal must give the same
decision (checked in every state). Not measured: curved-wall candidates, multi-wall developed views, bay interval
inside the wall, rotated sheets, fresh Revit export, rejected deliveries (none), Sokolniki transfer (#2001 open).

**Stability / budget.** Replay: `git fetch origin research/autoresearch-standing-161 research/autoresearch-standing-162`;
`uv run --offline --locked --extra pdf-review python docs/research/autoresearch-view-face-wallseg/run.py C:/x/ar163/<fresh>`
(pilot host with the owner's Weltbau folder). Three pairs, each a fresh Blender extraction+render and PDF read; rows +
wall table must be byte-identical; median/spread wall time reported. One candidate, zero retunes; stop `inconclusive`
over 30 min or on parity failure. Pre-score geometry probe: one Blender run, 10 s.

**Forbidden.** Changing params, truth, clips or states after a score; opening Sokolniki; editing source drawings,
models, deliveries, production `src/` or other cards' files; weakening guards.

## Round log

**H163 confirmed by the frozen acceptance; not adopt-ready (see post-hoc).** Contract commit `8c8f6427` (frozen
before any score). Three pairs, each a fresh Blender extraction + 20 wall renders + fresh PDF read: rows + wall table
byte-identical (`5cedce6e…9aca`), status `finished`, wall 16.206 / 17.440 / 17.089 s (median 17.089 s, spread
1.234 s; Blender stage 9.2–10.4 s). Input, Blender and upstream-blob hashes checked before and after every pair;
candidate-order reversal gave the same decision in every state. Receipt
[`receipt.json`](autoresearch-view-face-wallseg/receipt.json) SHA-256
`279f5b5ee0b701e9219061297c72cfbeffe80788ea4ccad86594b7724ee1bcd9`. Evidence (wall table, 20 wall renders, 3 row
sets, plan with wall ids): `G:/Мой диск/AGR-evidence/163-view-face-wallseg/` + `SHA256SUMS.txt` (26 files, verified;
manifest SHA-256 `c779c139…7501`).

| View (truth) | Width m | Eligible walls | Top (NCC) | Margin | Outcome | #162 |
|---|---:|---:|---|---:|---|---|
| A'-K (W19) | 74.25 | 1 | W19 (0.562) | 0.562 vs null | **correct** | wrong (0) |
| 4'-1 (none) | 92.75 | 0 | — | — | abstain | correct (90) |
| 1-4' inner developed (none) | 84.25 | 0 | — | — | abstain | abstain |
| fragment 1 (W19) | 10.75 | 11 | W19 (0.684) | 0.164 over W01 | **correct** | abstain |
| fragment 2 inner curved (none) | 11.00 | 11 | W17 (0.344) | 0.085 | abstain | abstain |
| K-A (diagnostic) | 55.75 | 1 | W19 (0.359) | 0.359 vs null | diagnostic | — |
| A-G (diagnostic) | 27.00 | 5 | W07 (0.568) | 0.077 | diagnostic | — |

Primary 2 / 0 / 3 (correct/wrong/abstain), answered accuracy 2/2, abstain rate 3/5 (#162: 1/1/3). Hard negatives on
the scored answers (truth vs best opposite-direction wall vs best 30°-neighbour wall): A'-K 0.562 / 0.361 / 0.536;
fragment 1 0.684 / 0.349 / 0.521. Inner rows: both abstain (by construction; not an inner-view result).

**Perturbations (exercised).** `blank` changed 2 067–9 924 cells, abstained 7/7. `mirror` changed 1 770–10 190 cells:
A'-K and fragment 1 keep W19 (near-symmetric box rows), K-A drops to abstain. `shuffle` changed 1 928–12 007 cells:
A'-K keeps W19 (0.452, sole eligible), fragment 1 keeps W19 (0.610, margin 0.137), K-A drops below tau (0.250).
The frozen witness "shuffle vetoes at least one clean-answered row" fired only on K-A, an unscored diagnostic row.

**Post-hoc (diagnostic, NOT a keep, does not change the frozen verdict).**
1. K-A (p15, 9 window columns, solid ground floor, no boxes; the same sheet carries A'-K as a separate full facade)
   was answered W19 because W19 is the only wall wide enough. By sheet content it is not W19: a single-eligible
   null-margin answer is a false positive the scored set did not contain. The A'-K "correct" is carried by the same
   width elimination (its 30°-neighbour wall scores 0.536, 0.026 below truth).
2. Shuffle did not veto either scored answer: the score tracks glass density per wall, not bay order. The only
   content discrimination measured is fragment 1 among 11 eligible walls (margin 0.164, 0.137 shuffled).
3. Unclipped short walls score high against wide views under the 0.8 × narrower overlap (A'-K: W14 0.576 > W19), so
   eligibility by width is load-bearing; without it A'-K would be wrong again.

**Not measured:** curved / developed inner walls as candidates (the stair yields no wall), bay interval inside a wall,
wall identity of K-A / A-G, rotated sheets, rejected deliveries (none for this object), Sokolniki transfer (#2001).

## Recommendation for the shared OKS step 'view<->face map sheet' (OBSERVE, not built here)

1. Candidates per wall segment (frontal, clipped render) with a view-fits-wall width gate: this removes the #161
   neighbour-direction error (A'-K) and placed the one real exterior partial correctly.
2. Answer only with a real competitor: margin >= 0.10 over another eligible wall. A sole eligible wall (null margin)
   must become a question, not an answer (K-A false positive).
3. Inner corners stay a question until curved/developed walls are candidates (unrolled render of the curved run) and
   measured on real inner partials (Silikatny fragment 2, then Sokolniki STOP 04 after #2001 closes).

## Next measured steps

1. Same frozen fixture, rule B: abstain when fewer than 2 eligible walls; add unrolled curved-run candidates
   (contiguous exterior faces with turning normals) so fragment 2 and 1-4' have a candidate; truth for the curved run
   from the p17 horizontal section.
2. A shuffle-self margin (clean minus shuffled score on the same wall >= delta) as the content witness, frozen before
   scoring, on fragment 1 / A'-K / K-A.
3. Blind Sokolniki transfer only after #2001 closes.

Full suite: deferred to merge batch (rule 68).
