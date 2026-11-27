# Autoresearch #143: self-ambiguity abstain for elevation view -> face (OBSERVE)

**Итог: гипотеза H143 опровергнута (refuted), прогон завершён (finished), режим OBSERVE.** Проверка
«самонеоднозначности» (если крупный кусок вида так же хорошо ложится на тот же фасад в другом месте —
отказаться) убрала все 4 уверенно-неверных ответа OBR22 (короткие торцевые обрезки, NCC 0,99) и на
OBR22 R2 даёт 0 ошибок из 40. Но на периодическом фасаде OBR22 она же сняла 7 из 9 верных ответов по
длинным обрезкам (осталось 2, порог был ≥5): верные куски так же неоднозначны по положению (разрыв
0,0001–0,009), как и неверные (0,000). Значит, порог тут не поможет: по ритму окон одного этажа нельзя
отличить «верный фасад, неизвестное место» от «чужой фасад с тем же ритмом». На KPP1 (2D-линии) цена
почти нулевая: 21 из 22 верных сохранено, 0 ошибок из 80; AC08 и так отказывается всегда (не измерено).

Рекомендация для общего шага OKS «лист соответствия вид↔фасад»: включить эту проверку как защитный
фильтр (она только добавляет отказы, ни разу не создала ошибку), но не как способ ответить. Вид,
отклонённый как «периодический», должен уходить в вопрос с двумя кандидатами или на другие признаки
(оси, ключевой план, имя вида, соседняя геометрия угла). Для внутренних углов Сокольников это значит:
короткий вид с повторяющимся ритмом окон автоматически не привязывается — STOP 04 станет вопросом
с двумя кандидатами, а не исчезнет. Проверка на Сокольниках — после закрытия #2001.

## Frozen protocol (committed before any measurement)

Card t_7f65d2eb (standing #143), focus 0 (view <-> face map). #2001 is OPEN, so Sokolniki
(`jobs/sokolniki-uvk1000`) stays held out and is not opened. Continues #139-#142 instead of a new harness:
reuses the pinned #141 raster front end (Git `3716f5395667c17f8be8737313952aaa6285615c`) and the #140 2D
scorer / #139 native front end (Git `ab33b7e4249f41232501d0c05534bd2793a15358`, `38f7d95ee54a677ac744c0148fb1fce33b06d9d3`).

**Why:** #141 R2 and #142 A gave 4 confident-wrong answers on 4.4 m end crops of OBR22 K02 (NCC 0.99,
margin 0.54 to the next face): a short crop of repeating window rhythm fits a long periodic facade at
several offsets. A real untitled partial view of an inner corner is exactly that kind of short crop.
The existing margin compares faces only; it never asks whether the winning face explains the crop at
another, separate position equally well.

**H143:** adding a self-ambiguity gate to an answered decision — abstain when the winning face's best
score at any offset at least `D = max(10 px, ceil(view_px / 2))` (0.1 m/px, i.e. >= 1 m and >= half the
view) away from the best offset is within `TAU = 0.10` of the best — removes every confident-wrong answer
on the OBR22 clean cases while keeping most correct answers of the same scorer on OBR22 and KPP1.
The gate only adds abstentions; it never changes an answer or creates one. Thresholds, slack, smoothing,
MIN_SCORE 0.30 and TAU_MARGIN 0.10 of the upstream scorers stay unchanged.

Arms (one new candidate, applied to two existing scorers):
- **C/R2** = #141 R2 1D window-column NCC (OBR22 K02 raster PDF p14-15 vs accepted NPM v012), and
  **C/R2+SA** = same + gate. 40 clean cases (4 full + 36 synthetic crops) + 4 mirrors.
- **B2D** = #140 B 2D line scorer (KPP1 L01 DXF vs accepted delivered FBX; AC08 symmetric box), and
  **B2D+SA**. 80 clean cases + 8 mirrors.
- Perturbation P1 (reported, no bound): #141 R1 profiles (no tall-run removal, 22 wrong) + SA.
  Expected direction: wrong decreases.

Metric (ONE number): confident-wrong count on clean cases (answered accuracy) with abstain rate; plus
correct retained. Per-variant bounds, all must hold in each of 3 fresh pairs (median reported):
1. Positive trigger witness: the 4 R2 wrong cases (`А.2-Е.2` / `Е.2-А.2` crop0.25 @0.0 and @1.0) all
   abstain with reason `periodic`. Expected direction: wrong 4 -> 0.
2. OBR22 clean C/R2+SA wrong = 0 / 40; long full views 2/2 correct retained (the gate cannot fire
   there by construction: offsets span <= 12 px < D).
3. Accepted controls on which the gate may fire (collateral): OBR22 long crops retain >= 5 of R2's 9
   correct; KPP1 B2D+SA crops retain >= 16 of B's 22 correct (keeps >= +10 over #140 roofline A = 6),
   KPP1 full retains >= 2 of 3, 0 wrong on all 80 B2D+SA clean cases.
4. AC08 is all-abstain in B already: the gate cannot act -> labelled `not_exercised` (not measured).
5. Mirrors are a separate injected control: SA wrong <= baseline wrong per arm (reported, not pooled).
Confirmed if 1-3 hold in all three pairs; refuted if any is measured and missed; inconclusive on
budget stop or parity failure.

Parity proof: each pair re-runs both upstream front ends fresh (new Blender ray casts, new PDF/DXF reads).
OBR22: R1 and R2 cases with the SA field stripped must equal the #141 receipt `R1`/`R2` cases exactly.
KPP1/AC08: (fixture, title, gt, case) -> V1 answer must equal #139 receipt (as #140 does) and B answers
must equal the #140 receipt `views[*].B`. The per-offset maximum used by SA must equal the upstream score.

Budget: 3 fresh pairs, one candidate, no second candidate in this card. After pair 1, continue only if
2 more pairs at 2x pair-1 wall time fit in 15 min. Timeout 300 s per pair. No threshold change after
scoring. Stop on parity mismatch.

Forbidden: changing upstream thresholds/slack, editing delivered packages or the pinned inputs,
deselecting tests, touching other cards' files, opening Sokolniki outputs, scoring with GT or titles.
Inputs pinned by the upstream fixtures' SHA-256 (pre- and postflight), Blender 4.4 by
`fd21f4b9f9e7ae317d5bb7f27eada83aab3952cb27e245d0e3f8ab810eb277b5`, upstream code by full Git revision.

Replay (repo root, pilot host: Desktop OBR22 PDF, local OBR22 outputs, G: drive KPP1/AC08, Blender 4.4;
`git fetch origin research/autoresearch-standing-139 research/autoresearch-standing-140 research/autoresearch-standing-141`):
`uv run --offline --extra cad --extra pdf-review python docs/research/autoresearch-view-face-self-ambiguity/run.py tmp/r143-NEW`

## Round log

**Hypothesis H143: `refuted`** (bound 3 missed on OBR22 in every pair). **Run status: `finished`**,
3/3 pairs, byte-identical semantic payloads (pair SHA-256 `a575d00772ac472be442f0562b1bea302a1b4e102d99875f92417c6814dc293f` x3).
Wall time 45.113 / 49.394 / 46.516 s (median 46.516 s, total 142.794 s); budget never limiting.
Measured at candidate commit = this branch (run.py / sa.py SHA-256 in the receipt), uv.lock `ba1bb998b19d...`.

Parity (every pair): #141 R1 and R2 44/44 cases each equal to the #141 receipt; #140 88/88 V1 equal to the
#139 receipt and 88/88 B answers equal to the #140 receipt; per-offset maxima equal upstream scores
(asserted per case).

| Arm (clean cases) | correct / wrong / abstain | vs baseline |
|---|---:|---|
| OBR22 C/R2 long full | 2 / 0 / 0 -> SA 2 / 0 / 0 | bound 2 held (gate cannot fire) |
| OBR22 C/R2 long crops | 9 / 0 / 9 -> SA **2** / 0 / 16 | bound >= 5 **missed** |
| OBR22 C/R2 short full + crops | 0 / 4 / 16 -> SA 0 / **0** / 20 | witness 4/4 -> `periodic` (bound 1 held) |
| OBR22 total (40) | 11 / 4 / 25 -> SA 4 / 0 / 36 | bound 2 held (0 wrong) |
| KPP1 B2D full | 3 / 0 / 1 -> SA 3 / 0 / 1 | held |
| KPP1 B2D crops | 22 / 0 / 14 -> SA 21 / 0 / 15 | bound >= 16 held (lost `1-4 partial25@1.0`) |
| AC08 B2D full + crops | 0 / 0 / 40 -> 0 / 0 / 40 | gate never reached: **not measured** |
| P1 perturbation: OBR22 R1 (40) | 9 / 22 / 9 -> SA 3 / 3 / 34 | direction as expected; 1 full-view wrong cannot be gated |

Gate evidence on OBR22 R2 (best score - same-face second peak): the 4 wrong end crops 0.0000 (self2 0.99);
the 7 removed correct long crops 0.0001-0.0088; the 2 kept 0.177 and no far offset. The separations
overlap, so no TAU (pre-registered or not) separates them on this fixture: it is not a threshold problem.

Injected mirrors (separate): OBR22 R2 2/0/2 -> SA 2/0/2 (all 4 exercised); R1 1/1/2 -> 1/1/2 (full-view
length, gate cannot act); KPP1 0/0/4 both; AC08 1 exercised abstain, 3 `not_exercised`. SA never added a wrong.

Repair attempts in scope: (1) first run aborted in the KPP1 leg — `face_score_all` built a negative-length
array when the view is wider than the padded model (upstream loop is then empty and returns -1); fixed with
`max(0, ...)`, no change to scoring. Second run is the measured series above.

**Not measured:** real untitled partial views (all crops synthetic), inner corners / non-axis faces,
Sokolniki (held out, #2001 OPEN), AC08 (always abstains upstream), G22/Vatutino/TEC26 other buildings,
Revit names/keyplans/axes as algorithms.

Receipt: [`autoresearch-view-face-self-ambiguity/receipt.json`](autoresearch-view-face-self-ambiguity/receipt.json),
SHA-256 `44e29553ae206851bc51a3498cb60ed69fba3a8b476915d75ac33190071e919e`. Evidence (receipt, 3 pair
payloads, run log): `G:/Мой диск/AGR-evidence/143-view-face-self-ambiguity/` + `SHA256SUMS.txt`.
Replay limited to the pilot host (Desktop OBR22 PDF, local OBR22 outputs, G: drive, Blender 4.4).

Affected tests: `env -u PYTEST_ADDOPTS uv run --offline --extra cad --extra pdf-review pytest -q docs/research/autoresearch-view-face-self-ambiguity/test_sa.py` — 5 passed.

Full suite: deferred to merge batch (rule 68).
