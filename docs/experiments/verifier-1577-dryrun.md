# Verifier step dry run (#1577, observe mode)

**Кратко.** Шаг `verifier` (`tools/qa/verifier.py`, observe) прогнан на принятом объекте TEC26-OKS AC08 pilot-v010
(рендеры уже в evidence): 12/12 ответов чек-листа согласованы по порядку видов, 0 замечаний, материалы 4–5 из 5,
главного расхождения нет. Контроль на отклонённом pilot-v007: главное расхождение `material:base_color` (рамка и
цоколь перепутаны), 7/7 известных дефектов найдены, 1 лишнее (`no_extra`). Модель не менялась, бинарники не в git.

## Inputs (existing evidence, not committed)

- Renders: `G:/Мой диск/AGR-evidence/559-tec26-oks-ac08-pilot-v010/renders/` (6 views of `vlm_checklist.VIEWS`),
  slide `G:/Мой диск/AGR-evidence/559-tec26-oks-ac08-pilot-v010/slide49.png`, legend
  `jobs/TEC26-OKS/AC08/vpm_textures.json`, facades `south=2-1,north=1-2,east=Б-А,west=А-Б`.
- Hashes of the 7 inputs: `G:/Мой диск/AGR-evidence/1577-verifier-dryrun/input-SHA256SUMS.txt`.
- VLM: Claude CLI `sonnet` (`claude-sonnet-5-5`), 2 calls per run (views forward + reversed).

## Command

```
uv run python tools/qa/verifier.py --job jobs/TEC26-OKS/AC08 \
  --renders "G:/Мой диск/AGR-evidence/559-tec26-oks-ac08-pilot-v010/renders" \
  --slide "G:/Мой диск/AGR-evidence/559-tec26-oks-ac08-pilot-v010/slide49.png" \
  --facades "south=2-1,north=1-2,east=Б-А,west=А-Б" --legend jobs/TEC26-OKS/AC08/vpm_textures.json \
  --out "G:/Мой диск/AGR-evidence/1577-verifier-dryrun/verifier.json"
```

`--out` points to the evidence folder so no report lands in the delivered job folder (rule 57: path + hash only).

## Results

| Run | Object | kept / items | flagged | material min / mean | main discrepancy | cost, time |
|---|---|---|---|---|---|---|
| `verifier.json` | AC08 pilot-v010 (accepted) | 12/12 | 0 | 4 / 4.5 | none | $0.25, 51 s |
| `verifier.v007-control.json` | AC08 pilot-v007 (rejected) | 12/12 | 8 | 2 / 2.83 | `material:base_color` | $0.20, 39 s |

pilot-v010 material axes (score: reason): missing 5, base_color 4 (RAL not measured), borders 5, scale 5, finish 4,
consistency 4 (NPM seams slightly darker; forward 5 / reverse 4 → the lower score is kept).

pilot-v007 control findings: material base_color 2, borders, scale, finish; checklist frame_color, plinth_color,
rib_count on all 4 facades, field_outline, no_extra. Against the #768 ground truth (7 known defects): 7/7 found,
1 false positive (`no_extra`), the same bar as #768 (recall >= 80 %, FP <= 1).

Rib counts in these findings name *what* to check; the positions and counts come from the model and the DXF
(CrossProjection rule, docs/agents/SKELETONS.md).

## Evidence

`G:/Мой диск/AGR-evidence/1577-verifier-dryrun/` + `SHA256SUMS.txt`:

```
111cb3c94ee659c9fdd9bad436017f9e99bea04963ae038813f09bd60a743f9f *verifier.json
d9168588b03f4b92a399372ee8d0459632995dc70641432b768ae789a1e2f0c7 *verifier.v007-control.json
```

`uv run python tools/qa/verifier_summary.py --jobs "G:/Мой диск/AGR-evidence/1577-verifier-dryrun"` → 2 runs,
0 reviewed, match_rate null (no `verifier_review.json` yet: Artem's review comes after a week of observe mode).
