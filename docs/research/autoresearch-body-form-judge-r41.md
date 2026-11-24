# Body form — VLM judge qualification, standing #41, round log R1

**Русское резюме.** Гипотеза H41 по замороженному контракту (`autoresearch-body-form-judge.md`): **подтверждена**
на этом риге, с оговорками ниже. Оба судьи (свежий Claude CLI и свежий Codex exec `gpt-6.1-sol`) дали 0 ложных «Да»
из 5 размеченных отрицательных ячеек (R Q1/Q2, P_fill Q2, P_recess Q1, P_corner Q4), большинство из 3 вызовов.
Верные «Да» на положительных: Claude 6/6, Codex 5/6 (промах — A Q4 «углы прямые»: No/Unsure/Unsure). «Не уверен» на
размеченных: 0/11 и 1/11. Взвешенный балл рубрик S: Claude A 14 > R 3, Codex A 11 > R 3 (калибровка выполнена).
Парное сравнение A против R/P_fill/P_recess/P_corner в обоих порядках: 4/4 пар согласованы по порядку у обоих судей,
все выбрали A; совпадение с вердиктом Артёма (A лучше R) — да у обоих; заложенные пары 3/3. Каппа не определена: все
сохранённые вердикты одной метки (A), согласие судей 4/4. Прокси-метрика сетки #40 ранжирует наоборот (A 83.693 <
R 90.830). Вывод: на заметных дефектах формы (нет проёмов, лишняя ниша, заложенный проём, срезанный угол) оба судьи
на нейтральных выровненных кадрах надёжны, а балл сетки — нет. Это не точность судей вообще: n = 5 отрицательных,
один фрагмент, дефекты крупные. Код не сохранён (OBSERVE), сборка тел не трогалась.

## Scope and inputs

Base `a0e8ec1d` (contract) on `aba60c66` (#40 receipt). Inputs unchanged before/after (`sha256sum -c
FROZEN-before-judge.sha256`: inputs, composites, views, key OK; only `judge41.py` differs — invocation repairs below).
A = v002r1 `5b1e8d76c81de07d…`, R = v001 `8e97a80af2de0a22…`. Planted P_* are in-memory evaluator controls on a copy of A.

## Rig preflight log (3 repairs, all before the first judge call)

| Step | Problem | Repair |
|---|---|---|
| pre | empty output dir (attempt 1, crashed run) | — |
| pre1 → pre2 | made by attempt 1; its reasons were lost with the crashed session (renders kept under `pre1/`, `pre2/`) | counted as repairs 1–2 |
| pre2 → pre3b | V4 plan showed only edge-on slivers; V1 showed a partial neighbour opening (would break «exactly 4») | repair 3: plan copy capped at crop top, cropped in the facade u/n frame and at crop bottom (a P_corner ledge at z 10 hid the chamfer); V1/V2 spans trimmed to key segments ±0.3 m |

Deviation, recorded: attempt 1 (pre2) and this run (`pre3b/check5.png`) rendered all five variants during preflight
to check that each planted defect is visible; no judge saw them and nothing was tuned on judge output.
Known rig confound: the A openings render as white through-holes, the planted P_recess as a closed grey niche.

## Judge invocation log (not judge answers)

1. Codex default model `gpt-6.2-sol` → HTTP 400 `model_not_found` for this ChatGPT account → `-m gpt-6.1-sol`.
2. Codex npm `.cmd` shim cut the multi-line argv prompt at the first newline (answer was a clarifying question) →
   prompt via stdin. Both failed raw records kept in `calls_failed/`.
3. Pair job ids collided with rubric ids (same seed) → 0 calls made, re-seeded; no record overwritten.

Calls: 46 valid (30 rubric + 16 pair) + 2 failed invocations = 48 ≤ 70. Wall: timed pair 11.7 s / 13.4 s; rubric
batch 95.0 s, pair batch 39.5 s (4 workers). No budget stop.

## Results (`result41.json`)

| Judge | yes_bias | true No on negatives | true Yes | Unsure (labelled) | flip cells | S: A / R / P_fill / P_recess / P_corner | qualified |
|---|---|---|---|---|---|---|---|
| claude | 0/5 | 5/5 | 6/6 | 0/11 | 5/25 | 14 / 3 / 8 / 8 / 11 | yes |
| codex | 0/5 | 5/5 | 5/6 (A.Q4) | 1/11 | 3/25 | 11 / 3 / 8 / 8 / 11 | yes |

Pairwise (order-consistent retained): claude 4/4, codex 4/4; A over R matches Artem: both; planted 3/3 both;
judge↔judge raw agreement 4/4, kappa undefined (single label). Proxy (#40 mesh score) ranks R over A: wrong.

Unlabelled noise (reported, not scored): Q4 (corners) is the weak rubric — Unsure/flips on unchanged corners
(P_fill Q4, P_recess Q4, R Q4) for both judges, and Codex misses A Q4; for Codex S(P_corner) = S(A) = 11, so its
rubric score does not separate the chamfer variant even though the Q4 cell itself is a correct No.
Claude P_recess Q5 = Yes 2/3 (the planted niche shares sill/head, consistent).

## Not measured

KPP1 NW and Sokolniki pairs (no exact labelled body pair, #40); scene (readback) rubrics; small defects such as the
0.10 m `C_shift_opening` / `C_shift_wall` (not exercised); judge precision beyond n = 5 negatives; any other fragment.

## Replay

Evidence: `G:/Мой диск/AGR-evidence/standing41-body-form-judge/` (copy of `C:/x/autoresearch-body-form-r41/`),
`SHA256SUMS.txt` sha256 `775b206adc40a72e…`, 58 entries, verified on the copy; `result41.json` `15e38eb635e64c7a…`.
`python judge41.py rubric|pair` (calls are cached by id; delete `calls/` to re-judge), `python aggregate41.py`.
Rig: see contract Replay. Replay limited to this PC (claude/codex CLIs, Blender 5.1, `C:/x/t_563a40f7/key/`).
