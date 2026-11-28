# H169 — refuse one-label support in the finish-partition score D (OBSERVE)

## Кратко для Артёма

**H169: ОПРОВЕРГНУТА по замороженному критерию 2** (прогон завершён, OBSERVE, в продакшн ничего не внесено).

Отказ от опоры на одну подпись чертежа (`pv.size < 2`) сделал то, ради чего вводился, и лучше прогноза:
- ложный ответ на зеркальном фрагменте `p20 frag 9-10` (`W12`) исчез — теперь «не знаю»; уверенно-неверных 2 → 1;
- чистые виды: 0 неверных, все 10 пустых видов — «не знаю», `p18 I-A` по-прежнему `W08`;
- из 1020 оценок «вид×стена×состояние» изменились ровно 3, все три были 1.0 от опоры с одной подписью;
- покрытие полных видов **не упало** (3/7; я предсказывал 2/7): `p19 6-1` по-прежнему верно отвечает `W16`,
  теперь с честной оценкой 0.891 от опоры с ≥2 подписями.

Почему всё же «опровергнута»: замороженная проверка 2 требовала, чтобы победитель `p19 6-1` имел опору ≥2 подписей
в старой оценке D или исчез; победа сохранилась, а опора в D — одна подпись. Задним числом критерий не меняю.
Остаток: зеркало `p24 frag 8-9` → `W16` (5 подписей) — это вопрос «лево/право», а не опоры; ожидался.

Рекомендация для шага «вид↔фасад»: отказ от одноподписной опоры в D — кандидат в обязательную защиту (без
порогов, трогает только вырожденные оценки), но только после отдельного подтверждающего прогона с заранее
записанным правильным критерием (победитель D' с опорой ≥2 или «не знаю»). Следующая цель — проверка зеркала для `p24`.

## Frozen contract (written before the runner and before any score)

**Question.** #168 found that the #149 finish scorer `U(V|M)` returned 1.0 on overlaps that contain exactly one
drawing label: true `H(V) = 0`, but float summation gave `H(V) = 1.1e-16`, so the `hv <= 0` guard missed it. Two
answers came from such supports: the clean slanted full view `p19 6-1` (`W16`, side-correct, the only full gain of
F over A) and the injected top-cut mirror `p20 frag 9-10` (`W12`, wrong side). Does an explicit refusal of
one-label supports remove the degenerate answers while leaving every multi-label score unchanged?

**Arms (one variant, no search).** F = #168 fusion, unchanged (A = #167 C166 glass stack + D = #149 score).
F' = the same fusion with D' = D whose `uncertainty()` also returns -1.0 when the overlap holds fewer than two
distinct drawing labels (`pv.size < 2`); this is a one-token source change of the pinned #149 `score.py` blob
(`if hv <= 0:` -> `if hv <= 0 or pv.size < 2:`), applied in memory. No threshold, margin, overlap floor, slack or
candidate changes. Both arms are computed in the same fresh pair on the same native label maps.

**Fixture.** ELV TC Sreda, the #145/#167/#168 pinned PDF (`49c10527…`) and FBX (`7ccf502d…`), Blender 4.4
(`fd21f4b9…`); all 7 full views and 3 real fragments, 34 wall candidates, states clean / blank / mirror exactly as
#168. Side-level truth from the #145 oracle (within-project ablation, not external validation). Sokolniki is not
opened (#2001 OPEN).

**Parity.** Each pair must reproduce the #167 A digest `04f67ea6…` (inside the pinned #168 runner) and the #168 F
body digest `9355a8c728aa40305caaf1b9a74046b283d2aeabc98aabfc52cc5bbdcef6c3a7` with the original scorer; F' body
must be byte-identical over the three pairs. Every per-wall score that differs between D and D' is listed; a
difference is admissible only where the D maximum came from a one-label support, i.e. by construction of D'.

**Metric.** Primary: confident-wrong answers of the fused arm over exercised rows (clean + injected mirror,
full + fragments); F has 0 clean + 2 mirror = 2. Secondary: correct / wrong / abstain per cohort, full-view
coverage (F 3/7), changed per-wall score count.

**Frozen predictions and acceptance.** H169 is **confirmed** iff all hold:
1. `p20 frag 9-10` mirror no longer answers `W12` (expected: abstain) — positive trigger witness;
2. `p19 6-1` clean no longer wins by a one-label support (expected: abstain or a different, multi-label winner;
   its side-correct answer may be lost — this is an expected coverage cost, F' full 2/7 is predicted);
3. retention control `p18 I-A` clean keeps `W08` (glass route; D' must not create a conflict);
4. clean wrong stays 0 on all ten views, blanks 10/10 abstain;
5. primary metric F' <= 1 (expected 1: `p24 frag 8-9` mirror keeps `W16`, five labels — support refusal is not a
   handedness check; recorded as the known residual, not a failure of H169);
6. every changed per-wall score has D = 1.0 or came from a one-label support (the runner records, for each changed
   score, the D value; any changed score with a multi-label D maximum refutes the "invariance" claim).
Otherwise refuted. A budget/parity stop is `inconclusive`.

**Budget and stop.** One variant, three fresh pairs (one budget-setting + two confirmations), no new candidate.
Budget 2100 s elapsed (#168: median 338 s/pair); stop as inconclusive if `elapsed + 1.15 × first pair × remaining`
exceeds it. No report-based tuning, no second variant in this card.

**Forbidden.** Editing delivered packages, source files, other cards' files or production code; weakening checks;
deselecting tests; opening Sokolniki outputs; rescoring the #168 dump as stability evidence.

**Replay.**

```
git fetch origin research/autoresearch-standing-161 research/autoresearch-standing-162 research/autoresearch-standing-163 research/autoresearch-standing-165 research/autoresearch-standing-166 research/autoresearch-standing-167 research/autoresearch-standing-168
uv run --offline --locked --extra pdf-review python docs/research/autoresearch-view-face-support/run.py tmp/ar169-NEW
```

The output directory must sit two levels below the repo root (`tmp/<name>`): the pinned #161–#168 modules derive
`REPO` from it (setup failures R1/R2 below).

Pinned blobs: #168 `run.py` (71fe3bd5, SHA-256 `1aa51f79…01ef`), `label_tail.py` (`800f8de0…9cfb`), #149
`score.py` (ef84ca41, `4a125268…ed24`). Replay is limited to a host with the #145 named-folder inputs and Blender 4.4.

## Result

Run R4 (R1/R2: setup failures, output dir outside `tmp/`; R3: Blender stalled during the board pause, 1500 s
timeout, no output). `measured_head` 61dce544 (the runner is unchanged by the result commit), three fresh pairs,
wall 469.161 / 501.543 / 408.538 s, median 469.161 s, spread 93.005 s, elapsed 1380.6 s < 2100 s, status `finished`.
Parity: A `04f67ea6…` and F `9355a8c7…` reproduced in all 3 pairs; F' payload byte-identical
`a371dff9ad1a73a288e05817ccf6f33ce246013e62dfbd9579ba2773ec9f2923` ×3; 1020 scores logged per pair.
Receipt: `docs/research/autoresearch-view-face-support/receipt.json` SHA-256
`000cd2d15c6a69d0a0d5dfd23645e254124916eda71206b02246db336dbfa7c2`.

| check (frozen) | result |
|---|---|
| 1 `p20 frag 9-10` mirror not `W12` | pass (abstain) |
| 2 `p19 6-1` clean: degenerate win gone | **fail** — still `W16`; D' 0.891 (≥2 labels by construction), D support 1 label |
| 3 `p18 I-A` keeps `W08` | pass |
| 4 clean wrong 0 / blanks 10/10 abstain | pass / pass |
| 5 primary confident-wrong F' ≤ 1 | pass (F 2 -> F' 1; residual `p24 frag 8-9` mirror `W16`) |
| 6 changed scores only from one-label supports | pass (3 changed, all D = 1.0, 1 label) |

Changed per-wall scores (D -> D'): `p19 6-1` clean W16 1.0 -> 0.891; `p19 6-1` mirror W16 1.0 -> 0.878;
`p20 frag 9-10` mirror W12 1.0 -> 0.895. Fused tally F -> F' (correct/wrong/abstain): clean full 3/0/4 and clean
fragments 1/0/2 unchanged; mirror full 3/0/4 unchanged; mirror fragments 1/2/0 -> 1/1/1; blanks 0/0/7 + 0/0/3 both.

Outcome: **refuted** on frozen check 2. The prediction was wrong in the favourable direction (coverage kept, loss
predicted), and check 2 was coded against D's support rather than D''s; not re-labelled post hoc. Not measured:
any album other than ELV; independent physical-wall truth (side-level oracle only); Sokolniki (held out, #2001 open).
