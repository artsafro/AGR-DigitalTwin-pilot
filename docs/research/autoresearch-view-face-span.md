# H165 — full-view length-agreement veto (OBSERVE)

## Кратко для Артёма

**H165 подтверждена на Силикатном (только этот фикстур).** Сверка длины: полный фасад должен совпадать по длине со
стеной на плане (±10 %, тот же допуск, что у #163). Ложное К–А → W19 снято (55,75 м против 72,07 м), верные
А′–К → W19 и фрагмент 1 → W19 сохранены. На пяти размеченных видах **2 верных / 0 неверных / 3 отказа** (у #164
было 1 / 0 / 4). Правило только запрещает ответ и никогда не создаёт новый.

Где правило бессильно: если растянуть К–А до 72 м, ложный ответ W19 возвращается. Значит, содержимое вида
(остекление) К–А от W19 не отличает, а различает их только масштаб. Без верной регистрации масштаба правило не
работает. Ещё оно опирается на ручную метку «полный фасад / фрагмент». Автоматически эту метку на безымянных видах
пока никто не определял. Вариант «отбирать кандидатов по двусторонней длине» отклонён: стен-соперников становится
меньше, отрыв от второго места растёт без оснований, и на непроверенном A–G появляется ответ W07.

Для шага «карта вид ↔ грань»: печатать сверку длины для полных фасадов как отказ, а не как выбор стены. Внутренние
углы этим не решаются. Сокольники не открывал. Код маршрута не менял.

## Frozen contract

Standing #165, `t_ce910adf`. Continues #163/#164 on the same Silikatny wall-segment fixture (#164 next (2):
plan corroboration for the singleton A'-K vs the exclusion K-A). Not the finish-partition work (#2073/#2074),
not the wall-exercise scorer (#2075). Readiness 2026-11-28_0836. #2001 is OPEN: no Sokolniki input or key opened.
Atlas, form and trainer targets stay parked.

**Problem.** #163 answers K-A -> W19 (false: K-A is a separate nine-column facade, #164 exclusion witness) and
A'-K -> W19 (correct). #164's singleton veto removed both. The #163 width gate is one-sided
(`view_w <= 1.10 * render_w`), so a 55.75 m full elevation may land on a 72 m wall.

**Hypothesis H165.** A pure veto on the #163 answer: for a view of kind `full` (frozen #161 fixture label), the answered
wall must also satisfy the plan length agreement `|view_w / render_w - 1| <= fit_tol` (the same frozen `fit_tol = 0.10`
and `render_w_m` the #163 gate uses; no new parameter, no sweep). Fragments are exempt. The veto never changes the
top wall, the margin or the competitor set, so it cannot create an answer. Expected on the clean native views:
K-A W19 -> abstain (55.75 / 72.068 = 0.774), A'-K W19 kept (74.25 / 72.068 = 1.030), fragment 1 W19 kept (exempt),
the four native abstentions unchanged. Expected directions were set from the published #163 receipt numbers.

**Diagnostic arm C (not a keep candidate).** Two-sided eligibility (rerank inside the narrowed set). Recorded to show
whether narrowing the competitor set manufactures margins; expected A-G (ungraded) to become an answer.

**Fixture.** Seven fixed #163 views (Silikatny AGR album PDF SHA-256 `785e4015…`, Revit OBJ `6ab64e6b…`, pinned in #161
fixture.json; Blender 4.4 hash pinned in #163). Revisions: #163 `56f608b577090a8f82cf4e2df2c722879199e378` (staged blobs
hash-pinned as in #164), #164 native baseline body SHA-256 `5cedce6e622d06b092a0b7be146623feee51a23a83b2ea0a6d79d03849709aca`
(must match in every pair). Graded rows: the five #163 GT rows; K-A only as the W19 exclusion witness; A-G diagnostic.

**Metric.** correct / wrong / abstain on the five graded rows + answered accuracy + abstain rate; K-A exclusion separately.

| Acceptance point | Concrete input | Expected | Check |
|---|---|---|---|
| Positive trigger | native K-A, A = W19 | B abstains | replay + `test_short_full_view_vetoed` |
| Correct answer kept | native A'-K (full), fragment 1 (fragment) | B = W19 for both | replay + `test_matching_full_view_kept`, `test_fragment_exempt` |
| Accepted control on which the rule fires | A'-K resampled x0.85 horizontally (I1) | B vetoes the A answer | replay |
| Lever isolation | K-A stretched to 72.068 m (I2) | veto does not fire (B = A, ungraded) | replay |
| Load-bearing label | fragment 1 relabelled `full` (I3) | veto fires -> abstain; reset (I4) restores W19 | replay |
| No invented answers | A abstentions, 7 blank masks, mirror/shuffle | B never answers where A abstains | replay + `test_never_creates_answer` |
| Stable evidence | three fresh Blender + PDF pairs | baseline hash = #164 body; B digest identical | replay |

**Keep predicate (follow-up recommendation only).** All three pairs finished, parity holds, graded B = 2/0/3, K-A B =
abstain, every other clean B equals A, I1 and I3 veto, I4 restores, B never answers where A abstains.
A completed series missing any bound = `refuted`; parity failure or budget stop = `inconclusive`.

**Budget and stop.** Three pairs, hard 10 min; after pair 1, continue only if 2x its wall time fits. No threshold sweep,
no other candidates. Forbidden: production code, delivered models/drawings, locked standards, other cards' files,
deselecting tests, loosening #163 parameters, protected holdout (Sokolniki).

**Not measured by design.** Automatic full/fragment detection on untitled views (the veto depends on the frozen label);
K-A's true wall; A-G truth; curved/developed walls; bay intervals; accepted/rejected delivery calibration; STOP 04.

**Replay** (pilot host with the owner's Weltbau folder and Blender 4.4):

```bash
git fetch origin research/autoresearch-standing-161 research/autoresearch-standing-162 research/autoresearch-standing-163
uv run --offline --locked --extra pdf-review python docs/research/autoresearch-view-face-span/run.py C:/x/ar165/<fresh>
```

## Round log

**Hypothesis: confirmed (all 10 frozen checks true). Run status: finished. Adoption readiness: no.** Three fresh
Blender wall-extraction + PDF pairs (`tmp/ar165-run1`, measured with runner SHA-256 `6c44d165…` = committed run.py): pair wall time
28.759 / 29.943 / 28.795 s, median 28.795 s, spread 1.184 s, total 91.6 s (budget 600 s). Baseline body SHA-256
`5cedce6e…` matched #164 in every pair; candidate digest `7ac62360…` identical in all three.

| Real view (kind) | view_w / render_w of A's wall | A (#163) | B (H165 veto) | C (two-sided eligibility, diagnostic) |
|---|---:|---|---|---|
| p15 K-A (full) | 55.75 / 72.068 = 0.774 | W19 (false, exclusion witness) | abstain | abstain |
| p15 A'-K (full) | 74.25 / 72.068 = 1.030 | W19 correct | W19 | W19 |
| p16 fragment 1 (fragment) | exempt | W19 correct | W19 | W19 |
| p14 4'-1, p14 1-4', p17 fragment 2 | — | abstain | abstain | abstain |
| p15 A-G (full, ungraded) | — | abstain | abstain | **W07 (new, ungraded)** |

Graded five: A 2/0/3, B 2/0/3, C 2/0/3 (answered accuracy 2/2, abstain 3/5, correct coverage 2/5 for B, vs #164 1/5).
K-A exclusion: one false assertion in A, none in B.

- **Injected (exercised):** I1 A'-K resampled x0.85 (63.0 m, 13,104 changed cells): A still W19, B vetoes (accepted
  control on which the rule fires). I2 K-A stretched to 72.0 m (14,976 cells): A W19, B **W19** — veto silent, the
  false answer returns: the score does not separate K-A from W19, only scale does. I3 fragment 1 relabelled `full`:
  B vetoes (ratio 0.149) — the frozen kind label is load-bearing. I4 reset (no change, `not_exercised` as a
  perturbation): W19 restored. Blank 7/7 abstain (2,067–9,924 changed cells); mirror (1,770–10,190) and shuffle (1,928–12,007) on all seven
  views: B equals A in every state (A'-K and fragment 1 keep W19 under mirror and shuffle, as in #163 — not a content
  witness).
- **Arm C:** two-sided eligibility leaves A-G with {W07, W08}; margin 0.448 (vs 0.077 among five) -> W07 on clean, mirror
  and shuffle alike, i.e. margin made by narrowing, not by content. Rejected as a candidate.
- **Not measured:** automatic full/fragment detection, K-A's true wall, A-G truth, curved/developed walls, bay
  intervals, other albums, accepted/rejected delivery calibration, STOP 04 removal (#2001 open, Sokolniki unopened).

Receipt: [receipt.json](autoresearch-view-face-span/receipt.json), SHA-256
`21628bb07c0edf8ee467bba424b87069abaa72c23b9a32e67e70c64d071d5d18`. Full run folder (3 pairs, 60 wall renders,
baseline/candidate JSON): `G:/Мой диск/AGR-evidence/165-view-face-span/` + `SHA256SUMS.txt` (76 entries verified,
SHA-256 `ca69f932c190dd416dd081ab95c61d67e7fc7cda21a579544afec03fc1e0425f`). Replay limited to a host with the
owner's Weltbau inputs and Blender 4.4 (hash-checked preflight before and after every pair).

Regression: RED on the #163 pass-through (2 failed, 3 passed), GREEN 5 passed. Branch-only research; no production
code. Full suite: deferred to merge batch (rule 68).
