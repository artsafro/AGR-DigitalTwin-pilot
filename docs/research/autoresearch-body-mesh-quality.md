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
