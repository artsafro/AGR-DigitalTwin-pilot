# Standing #44 — parallel section evidence (OBSERVE)

**Резюме.** На принятом G22 к.2 v002r1 отдельный параллельный отрезок в обоих сечениях скрыл реальный проём `4259581` от проверяющего: при 60 и ±110 мм он дал **3 ложные отметки «неприменимо»** в каждом из трёх повторов. Исходный FBX не менялся. При 130 мм эффект исчез. Односторонняя подстановка (только на 17,8 м) не дала ложных отметок, но счётчик выдал одновременно FN и FP для того же проёма. Поэтому итог H44 по замороженному контракту **inconclusive**: граница для побочных изменений нарушена. Локальный контрпример воспроизведён, правила #42 нельзя использовать как автоматический допуск. Внедрения и PR нет.

## Round receipt

Frozen contract `4270731a409e0a58c78c013e88ca77183e53647e`, probe locked in `d2f4176d` before execution. [Contract](../autoresearch-body-form-mouth.md) and [numeric receipt](receipt.json); SHA-256 of receipt `fa92b2855811397436a3d7f61a645b32113320e7884eabce700ce07d14c08273`. One full run, status `complete`, wall 14.969 s (first native A/R pair 2.150 s, prior evaluation 10.295 s, first synthetic A/R pair 0.286 s, remaining-matrix estimate 6.015 s). No time stop. Each of six baseline FBX reads used a fresh Blender process (5.1.2, metre source frame, stage-1 SE typical-floor fixture). All #42 machine-independent row fields matched exactly under the original path normalization. All protocol/#40 manifests and staged FBX hashes passed before/after. Replay from repo root: `python docs/research/autoresearch-body-form-r44/probe.py tmp/form-r44-fresh` with a nonexistent destination; the budget check may stop on a slower host. Replay limited to the workstation with the hash-bound #40 and evaluator packets and #42 Git revision. Private source/key and mutated extracts are not published; receipt has per-state digests and counts.

| Accepted A evidence state | Section records added (17.8 / 18.2) | Detector TP/FP/FN | False N/A rows (three repeats) | A−R raw form margin, median / spread (pp) |
|---|---:|---:|---:|---:|
| Clean | 0/0 | 6/0/0 | 0/0/0 (`not_exercised`) | 95.454545 / 0 |
| +110 mm, one height | 1/0 | 5/1/1 | 0/0/0 (`not_exercised`) | 77.272727 / 0 |
| +60 mm, both heights | 1/1 | 5/0/1 | 3/3/3 | 81.818182 / 0 |
| +110 mm, both heights | 1/1 | 5/0/1 | 3/3/3 | 81.818182 / 0 |
| −110 mm, both heights | 1/1 | 5/0/1 | 3/3/3 | 81.818182 / 0 |
| +130 mm, both heights | 1/1 | 6/0/0 | 0/0/0 (`not_exercised`) | 95.454545 / 0 |

**Clean and positive trigger.** R v001 remained 0/0/6 and 18 annotation rows on each repeat in every state, with zero changed raw items. Clean A/R raw scores 100.00 / 4.55 separated Artem's same-stage verdicts; historical whole-body geometry validity scores 83.693 / 90.830 ranked in reverse (different scope; no new mesh metric run). Clean two-sided section maxima at 16.85 / 19.8 m: A 0.000 / 0.000 and R 0.610 / 0.610, rounded. A measured depths 2×0.100, 2×0.130, 2×0.150 m; R absent-aperture depths not measured. Existing clean, shift, J1–J4 and missing-section controls reproduced #42.

**Evidence injection only.** All synthetic rows derive from the fresh FBX reads; only the specified section records changed. No fresh extraction of mutated geometry. Both-height in-band cases changed exactly four raw items at the selected aperture; three returned `not_measured` (edges, reveal, sill/head) and the #42 annotation treated those three as inapplicable. R retained its ranking against A in every state. `F=3`, repeat spread zero in all states. For the one-height check, presence requires both slices but the extra-gap pass scans only 18.2 m and compares against already matched gaps. It therefore reports the same opening on segment 24→25 as an extra in the surviving slice. This changed a global rubric item and violated the frozen no-extra/unchanged-other-items bound. This is a measured detector interaction, not a second actual aperture or reason to relax the gate. No thresholds changed.

**Not measured:** real parallel surfaces in an accepted independent body; signed source-shell ownership; per-facade contour breakdown (the detector reports section maxima); new KPP1/Sokolniki scores and new Yes-bias, ordering or kappa (#41 is separate). KPP1 contour A and Sokolniki v002/D375 are specification authorities, not accepted model bytes. Study evidence is ready for review; the metric is not ready for adoption.

Affected tests: `env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run --offline pytest -q tests/test_body_contours.py tests/test_blender_exit_code_guard.py --basetemp C:/x/t_ef67aeb3-affected` — 41 passed. `bash C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh` — 542 passed, 1 warning; `repo_guards: GREEN`. Full suite: not run (rule 68, no PR).
