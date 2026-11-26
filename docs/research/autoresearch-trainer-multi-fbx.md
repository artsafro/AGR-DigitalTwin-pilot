# Autoresearch #123 — several-FBX runs: how much the scoring rule matters (OBSERVE)

Russian summary: 9 из 68 сохранённых прогонов тренажёра не оценены, потому что агент оставил
несколько FBX (`pick_built` → TrainerError). Правило выбора FBX — решение Артёма (#115 next 3, #121 A).
Эта карточка правило НЕ выбирает и код НЕ меняет: она оценивает каждый FBX отдельно существующей
командой `agr trainer score --built FILE` и показывает, сколько прогонов прошли бы `artifact` и
какой шаг стал бы первым проваленным при каждом кандидатном правиле. Это данные для решения.

Frozen 2026-11-26 before any measurement, head = origin/main 8531433d.

## Contract

- Fixture (frozen): the 9 run dirs under `C:/x/trainer/runs` with no `score.json` and >= 2 FBX under
  `built/` (list from `multi123.py`, census of 68 dirs): 63a r87-3, 63b r87-3, g22 r111-1, r115-C3,
  r95-C3, r97-C1, r97-C3, kpp1 r95-C2, r95-C3 — 25 FBX in total. SHA-256 of every FBX goes to the receipt.
- Command per FBX: `uv run agr trainer score <etalon> --built <fbx> --out C:/x/ev_123/<run>/<n>.json`
  (unchanged scorer, no `--vlm`).
- Candidate rules (applied offline to the per-FBX reports, none is implemented):
  N = newest mtime; L = largest file; P = top-level / `result`/`assembled`/`typical`/`body` dir name
  (agent's "final" naming); O = oracle best-of (upper bound only, not a rule a scorer can use).
- Metric: per rule, count of the 9 runs whose `first_failing_step` != `artifact`, and the resulting
  first-failing-step tally of the whole 68-run census (does the most frequent step change?).
- Determinism (instead of median of 3, the scorer is deterministic): re-score 2 FBX twice; reports must
  match on verdict and first_failing_step. Mismatch → the census is inconclusive.
- Not measured is reported as not measured: a G22 FBX whose key cannot be read (#1955, PR #1970 open)
  is `not_measured`, never a fail.
- Budget: <= 45 min wall for scoring; stop rule = all 25 scored or budget hit (then inconclusive with the
  remaining command list).
- Forbidden: editing `tools/trainer/*`, the bank, run dirs or keys; choosing a rule; writing score.json
  into run dirs (outputs only in `C:/x/ev_123`).
- Hypothesis H123: the choice of rule changes the verdict of >= 3 of the 9 runs (rule matters for the
  decision). Refuted if all rules N/L/P agree on >= 7/9.

## Result (2026-11-26, one round, 2 min 15 s wall for 25 FBX)

Русское резюме: гипотеза H123 **опровергнута**. Правила N, L и P дают одинаковый вердикт во всех 9 прогонах из 9. Все 9 прогонов прошли бы
`artifact`. Шаг `artifact` остаётся самым частым первым провалом (20 прогонов). За него отвечают PR #1917/#1928. Выбор правила
для нескольких FBX на эти 9 прогонов почти не влияет. Иначе было бы только при правиле «самый старый файл»: тогда 7 из 9 упали бы на `bounds`.

| run | N newest | L largest | P final-name | oldest (contrast) |
|---|---|---|---|---|
| 63a r87-3 | vlm* (result) | vlm* | vlm* | bounds (pilot) |
| 63b r87-3 | vlm* (partial_v2) | vlm* (partial_v2) | vlm* (assembled) | bounds (pilot) |
| g22 r111-1 / r115-C3 / r97-C1 / r97-C3 | form_v2 (typical) | form_v2 | form_v2 | bounds (module/pilot) |
| g22 r95-C3 | form (body) | form | form | bounds (module) |
| kpp1 r95-C2 / r95-C3 | bounds | bounds | bounds | bounds |

\* `vlm` = `not_run` (scored without `--vlm`): every key-based step passed. On both 63A/63B "final" files form is p95 = 0.0 m
and polygons == key polygons, though FBX SHA-256 != key SHA-256. These files are **suspected key-derived**
(same lineage as the #121 63A r111-1 key copy, owned by #112-#116). They must not count as practice passes.

- Census of 68 runs if any of N/L/P were adopted: artifact 20, unscored 24 (0 FBX), bounds 9, form_v2 11, form 1, vlm-not_run 3.
  Before: artifact 20, unscored 33, bounds 7, form_v2 7, vlm 1.
- Determinism: 63a result and g22 r95-C3 body were re-scored 2x. Both repeats are identical (vlm/0.8333 and form/0.5714, p95 6.6202).
- Not measured: VLM step (no `--vlm`); G22 `form_v2` scored against the current bank key (#1955 / PR #1970 repins it). The
  G22 form_v2 verdicts can move after #1970.
- Fixture/receipt: `index.tsv` here (per-FBX SHA-256, size, mtime, scorer line; sha256 3c21e5cc...). Full reports and work dirs in
  `G:/Мой диск/AGR-evidence/123-trainer-multi-fbx/` + `SHA256SUMS.txt` (sha256 c4f67b1f...). Replay: `bash docs/research/trainer_multi_fbx_r123/score_all.sh` at this head
  (writes `C:/x/ev_123`; run dirs are not touched). Replay is limited to this PC, because the run dirs under `C:/x/trainer/runs` are local.
- Nothing kept, no code change. OBSERVE.
