# Body mesh quality — standing #12 (OBSERVE)

**Кратко.** Разрыв с эталоном — не надёжный критерий приёмки: у отклонённого G22 к.1 v002 разрыв меньше, чем у принятого v003. Полная калибровка на 63B не завершена. Изменения ядра не испытывались и не применялись.

## Frozen contract

Continue #1616/#1634/#1619: reuse `tools/qa/mesh_quality_score.py` and the #1619 `band_compare.py` evidence, without a replacement evaluator. Primary metric is mean absolute difference (points) to the corresponding G22 NPM etalon over G22 k1–k3 on the recorded typical bands. For each operand use median of three independent CLI invocations: `uv run python tools/qa/mesh_quality_score.py INPUT.mq.json --out NEW.json` with unchanged defaults. A candidate must reduce the mean gap by at least 0.5 points with no individual gap worsening. Preserve exact input hashes, band boundaries, facade/part scopes and defaults. Do not compare a stage-2 joined mesh to a stage-1 body as an A/B experiment.

R0 calibration before any candidate: KPP1 quad-v003 rejected SW/NW zones must score at least 0.5 below accepted rest (same native model, frozen #1616 regions); 63B v001/v002/v003 rejected stage-1 bodies must each score at least 0.5 below accepted v007 on the same typical-body scope. Preserve raw results and do not refit weights on these cases. Review held-out accepted 63A/C as matched-stage controls where comparable snapshots exist. G22 k1 v002 vs accepted v003 is a same-building rejection control and must meet the same margin. A single failed or unavailable required calibration pair stops candidate work. A recorded historic receipt is supporting evidence, not a new run.

Stop after R0 if calibration fails; otherwise at most one shared-core candidate or 12 minutes of measurement, whichever comes first. OBSERVE only: scratch copies, unchanged validator/tolerances; no test deselection, weaker checks, retuned metric, edited outputs/packages, or other cards' files. Score-only changes are not mesh improvements. Before recommending retention, repeat baseline with byte-identical score payloads and require unchanged sources, units, scope, outline and openings, material/UV intent and no worse master topology, readback, or geometry guards. Never promote a build or apply changes to delivered work. No overlap with 63B stage 2 (t_1e388df4), G22 atlas (#1649) or KPP1 corner rebuild (#1609).

## R0 — baseline and calibration status

Base `833346dc1c57519e4ce63a1d6e6b86127af3e349`. Existing inputs under `C:/x/ev_1619`; identical receipt bytes within each set of three. Interpreter from `uv run --offline --no-dev`; used its Python executable directly for the repeats. Input labels from #1619 and its research journal.

| Snapshot (`.mq.json`) | Median/3 | Input SHA-256 |
|---|---:|---|
| `r2/etalon_k1` | 89.244 | `413515339be03d1aa8eb88d23c487ce81f1605eced51d3b822d2919141acefb1` |
| `r2/k1_v002` (rejected, inward faces) | 91.016 | `cbee5a4481d73c80ebe0a4c669393f5404308d112be894011879ae0883588bf9` |
| `r3/k1_v003` (accepted) | 92.044 | `0939980dc8e9717657f437d2c840a77e6241f27ea5171ae402677def11f80db1` |
| `r4/etalon_k2` | 86.883 | `50df5fb7252078a3fc1edc9076b9e0043051f897bb3aa363b2014b404e6f8d0d` |
| `r7/k2_v002r1` (accepted body) | 83.693 | `2e922754e8b77f854627267fc75b1ba9c22c41a7c4713333fc34ba0ffaff431b` |
| `r1/etalon_k3` | 92.182 | `dc389b008673016871591e1cb42f151379b63aa2ffe271590c52b3009a7d4a13` |
| `r1/k3_v006` (accepted) | 90.275 | `39d22ea93efd8ff93c9c8542a314b8b2533fc8f5784d2807a7d5d1581a30dab0` |

Mean absolute gap **2.632 points**. Raw score ranks k1 correctly by **1.028 points**, but the absolute gap ranks the rejection closer (**1.772 vs 2.800**). An optimization using the gap alone would reward that direction. KPP1 historic receipt only: corners 76.684 vs accepted remainder 77.402 (0.718); no new native rerun. The fresh #1619 comment confirms 63B stage-1 v007 acceptance; no matched-scope three-run series for 63B v001–v003/v007 or 63A/C was completed. Stop at R0; no rule, threshold or candidate adopted.

Verification: `tests/qa/test_mesh_quality_score_1616.py` — 291 passed; `repo_guards.sh` — 542 passed, 1 warning; `repo_guards: GREEN`. No full-suite run. Next: freeze same-stage 63B inputs by hash and rerun the #1616 KPP1 controls, then test an independent inward-envelope guard against the k1 pair before treating reference distance as an optimization objective.

## Standing #13 (t_5e774d68) — frozen contract, written before any measurement

**Target (one number).** `min_margin` = the smallest (accepted − rejected) median score over the frozen
same-building pairs below, unchanged `tools/qa/mesh_quality_score.py` defaults. Continues #12 R0 (which stopped
because 63B was not run and KPP1 was historic only). Calibration passes only if **every** pair has margin
≥ **0.5** points (the #1616 `margin_points`). Pairs (labels from #1619 verdicts / the card):
63B v007 (accepted 2026-11-20 «принимаю», sheets) vs v001–v006 (v001–v003 rejected per card; v004 verdict
2026-11-17; v005 2026-11-18 ×2; v006 2026-11-18 4th reject); 63C v002 (accepted 2026-11-18) vs v001
(rejected 2026-11-17, corner triangles); KPP1 quad-v003 rest vs SW/NW corners (#1616 r4 zones); G22 k1 v003
vs v002 (#12). Cross-building raw scores are not compared (63A v005 accepted at 83.9 is below rejected 63B).

**Command / replay.** `python docs/research/autoresearch-body-mesh-quality-harness/calibrate.py C:/x/ev_ar13/r0`
(venv `../../.venv/Scripts/python.exe`, Blender from `dt_ai.core.blender_runner`). Per-input SHA-256 is frozen in
`INPUTS` and checked before and after every input; repeats = 3, median; payloads (minus the provenance block)
must be byte-identical, else the row is `noisy` and the pair is not measured. Paired spread = max−min of the 3.

**Budget.** Confirm: 3 runs × 13 inputs (R0). New candidate: at most ONE, only if R0 calibrates, 3 runs on the
63B/63C/G22 inputs it touches, total ≤ 45 min wall. Stop after R0 if any pair fails (no candidate on an
uncalibrated metric) — then the round is a diagnosis: which component inverts the failing pair.

**Scope / fixture.** Stage-1 typical bodies as published (no zones except the frozen KPP1 boxes). Scope
mismatch between versions (different storey count, podium) is recorded from `totals` (faces, area, elements)
and the version REPORTs; a pair whose area differs by > 25 % is flagged `scope-mismatch` (measured, not
silently dropped).

**Forbidden.** Editing inputs/delivered packages or other cards' files (t_1e388df4 63B stage 2, #1649, #1609);
retuning weights/params to make calibration pass inside R0; deselecting tests; promoting any build.
OBSERVE: any proposed score or body-core change is written here as "would change" and goes through a
separate PR + review.

## Standing #13 — R0 result (OBSERVE, nothing kept)

**Кратко.** Все 9 пар одного здания ранжируются верно: принятая версия всегда выше отклонённой. Но по
замороженному порогу 0,5 калибровка **не пройдена**: у 63C v002/v001 отрыв **0,427**. Дефект 63C v001 метрика
видит полностью (176 искажённых граней против 0, при пороге угла 5–30° одинаково), но балл считает долю
площади по всему корпусу, и локальный дефект углов разбавляется. По правилу контракта кандидатов не запускал,
ядро и модели не менял.

Base `1ffdcb76` + contract commit `204ba805`. 13 inputs × 3 runs, every input's payload byte-identical across its
3 runs (paired spread 0.000), hashes unchanged before/after (`harness/r0.json`).

| Pair (accepted − rejected) | Accepted | Rejected | Margin | ≥ 0.5 |
|---|---:|---:|---:|---|
| 63B v007 − v001 | 84.332 | 82.368 | 1.964 | yes |
| 63B v007 − v002 | 84.332 | 82.354 | 1.978 | yes |
| 63B v007 − v003 | 84.332 | 82.363 | 1.969 | yes |
| 63B v007 − v004 | 84.332 | 82.370 | 1.962 | yes |
| 63B v007 − v005 | 84.332 | 82.244 | 2.088 | yes |
| 63B v007 − v006 | 84.332 | 83.385 | 0.947 | yes |
| 63C v002 − v001 | 83.906 | 83.479 | **0.427** | **no** |
| KPP1 v003 rest − corners | 77.402 | 76.684 | 0.718 | yes |
| G22 k1 v003 − v002 | 92.044 | 91.016 | 1.028 | yes |

`min_margin` = **0.427** → `calibrated: false`.

Diagnosis (clean measurements, not candidates):
- 63C pair differs only in `irregular_area_share` 0.0306 vs 0.0000 (176 of 4 125 faces; weight 2 of 15 →
  0.41 points) and `weld_share` 0.2516 vs 0.2532 (slightly favours the rejected one). `--param irregular_deg`
  = 5/10/20/30 gives the same 176 vs 0 faces and the same 0.427 (`sens/`): the corner faces are skewed > 30°,
  so the threshold is not the lever; the whole-body area average is.
- 63B v006 → v007 gains come from `irregular_area_share` 0.055 → 0.020, `sliver_share` 0.017 → 0.006,
  `weld_share` 0.183 → 0.142. Scope differs: v007 13 644 faces / 6 554 m² vs v006 10 747 / 7 253 m²
  (area −9.6 %, under the 25 % flag).
- Historic `score.json` receipts of 63B v002–v006 (88.9–90.4) are not comparable: the core changed since
  (#1631 fixes); fresh scores are 82.2–83.4. KPP1 and G22 k1 reproduce #1616/#12 exactly.
- Not measured: 63A (no labelled rejected version of the same stage); G22 k2/k3 (no rejected version).
  Injected checks: none this round (hash and payload-identity guards only).

Would change (separate PR + review, not applied): report a localized-defect signal next to the area share —
e.g. irregular faces per element or per facade cell — so a corner defect is not averaged away; or calibrate
63C-type pairs by defect count (176 vs 0) rather than points. Changing the 0.5 margin is Artem's/#1616's call,
not this loop's.

Replay: `../../.venv/Scripts/python.exe docs/research/autoresearch-body-mesh-quality-harness/calibrate.py <new dir>`.
Evidence: `G:/Мой диск/AGR-evidence/ar13-body-mesh-quality/` (`r0/`, `sens/`, `SHA256SUMS.txt` sha256
`612e9cdab5aa4683…`; `r0/r0.json` sha256 `4baab476898fa159…`).
