# Body form — VLM judge small-defect threshold, standing #45, round log R1

**Русское резюме.** Гипотеза H45 («рендер-судьи менее чувствительны к мелким дефектам формы, чем сценовой
readback C1 #43») по замороженному контракту (`autoresearch-body-form-judge-r45.md`): **опровергнута** — но только для
семейства «лишняя ниша». Оба судьи (свежий Claude CLI и Codex exec `gpt-6.1-sol`) верно отвечают «No» (Q1: «ровно 4
проёма в V1») на всех размерах ниши 0,20/0,11/0,06/0,03 м, 3 из 3 вызовов; порог T = 0,03 м ≤ C1 0,06 м. Причина
видна на кадре: затенение cavity рисует контур ниши независимо от её глубины, поэтому рендер показывает факт
лишней ниши, но **не глубину** (0,03 м: макс. разница яркости с A всего 14/255). Семейство «фаска угла» —
**не измерено**: у обоих судей контроль A по Q4 не «Да» (Claude: Unsure/Yes/Unsure, Codex: Unsure/No/Unsure) — та же
слабая рубрика Q4, что в #41. Справочно: Claude даёт ложное «Да» на фасках 0,10 и 0,05 м (2/8 ячеек лестницы), Codex
отвечает «No» на всё, включая A (не различает). Парное сравнение A против лестницы в обоих порядках сильнее
рубрики: у обоих судей 7/8 пар согласованы по порядку, A выбран 7/7, включая фаску 0,10 м, где рубрика Claude
ошибалась; несогласована только фаска 0,05 м (в допуске #43). Судья↔судья 7/7, каппа не определена (одна метка).
Рендеринг воспроизвёл кадры #41 байт-в-байт. Код не сохранён (OBSERVE), тела не трогались.

## Scope and inputs

Contract `3517007a` on base `49997a1d`. Inputs unchanged before/after (`sha256sum -c FROZEN-before-judge.sha256`: 18
entries OK — A.fbx `5b1e8d76…f200`, key, 11 composites, rig/judge/aggregate/compose/render scripts). Planted variants
are in-memory evaluator controls on a copy of A (geometry = `plant43.py`, parameter = recess depth / chamfer leg).

## Parity proof

`rig45.py` (= `rig41.py` + size argv) reproduced `comp/A.png`, `P_recess`(0.13) and `P_corner`(0.80) of #41
**byte-identically** (sha256 `8f46976a…`, `e9451756…`, `314c5df7…`). 0 repairs.

## Rendered signal (pixel contrast vs A, before judging; covariate, not scored)

| Variant | max |Δgrey| | px with Δ>30 |
|---|---|---|
| recess 0.20 / 0.13 / 0.11 / 0.06 / 0.03 | 43 / 38 / 35 / 25 / 14 | 57 / 28 / 17 / 0 / 0 |
| corner 0.80 / 0.40 / 0.20 / 0.10 / 0.05 | 103 / 103 / 103 / 102 / 71 | 8543 / 4165 / 2058 / 1181 / 505 |

The recess footprint stays visible (cavity outline) at every depth; the contrast falls with depth, the footprint does not.

## Results (`result45.json`, majority of 3 fresh calls per cell)

| Judge | A.Q1 | W_recess.Q1 | recess 0.20/0.11/0.06/0.03 | T_recess (C1 0.06) | A.Q4 | W_corner.Q4 | corner 0.40/0.20/0.10/0.05 | T_corner | yes_bias ladder | flips |
|---|---|---|---|---|---|---|---|---|---|---|
| claude | Yes | No | No/No/No/No | **0.03** | Unsure | No | No/No/**Yes**/**Yes** | not measured | 2/8 | 6/55 |
| codex | Yes | No | No/No/No/No | **0.03** | Unsure | No | No/No/No/No | not measured | 0/8 | 7/55 |

Weighted S (calibration, ladder < A): claude A 11, recess 0.03 = 8 but recess 0.20/0.11/0.06 = 11 (= A: the Q1 loss is
offset by Q4 Yes on those images vs Unsure on A), corner 0.10/0.05 = 14 (> A); codex A 11, every recess 8, every corner
11 (= A). So the summed rubric score is **not** calibrated on this ladder for either judge — the noisy Q4 cell
dominates; the per-cell Q1 verdict is.

Pairwise (order-consistent kept, A wins): claude 7/8, 7/7; codex 7/8, 7/7; dropped pair = corner 0.05 for both
(claude: X-first picks the chamfer, codex: chamfer / Unsure). Judge↔judge 7/7 on common pairs; kappa undefined (every
kept verdict is A). Artem's real verdict covers only A vs R (#41); these are construction-truth pairs.

## Hypothesis outcome vs review readiness

H45 = **refuted** by the frozen rule (all qualified (judge, family) have T ≤ T_C1; only the recess family qualified).
Not a claim that render beats scene in general: the render shows recess **presence**, not depth, so it cannot judge
reveal depth or in-tolerance shallow features; corners stay unmeasured on the absolute rubric. OBSERVE: nothing to keep.

## Budget

98 calls (66 rubric + 32 pair) ≤ 110, 0 failed invocations, 0 unparsed; batch wall rubric 211.5 s, pair 93.5 s
(4 workers), render 20.4 s for 11 variants. No budget stop.

## Not measured

Corner family T (both judges, A.Q4 not Yes); proxy mesh score for planted variants; opening shift / real reveal depth
(no rubric); KPP1 NW / Sokolniki (no exact labelled body pair); any other fragment.

## Replay

Evidence `C:/x/autoresearch-body-form-r45/` = `G:/Мой диск/AGR-evidence/standing45-body-form-judge-small/`
(`SHA256SUMS.txt` sha256 `98371ec8a72aac2f…`, 179 entries, verified on the Drive copy; `result45.json` `e34944cb…`).
`python mk_rig45.py && python mk_judge45.py` (derive from #41 evidence), `bash render45.sh`, `python judge45.py
rubric|pair` (cached by call id), `python aggregate45.py`. Replay limited to this PC (claude/codex CLIs, Blender 5.1,
`C:/x/autoresearch-body-form-r41/`, `C:/x/t_563a40f7/key/`).
