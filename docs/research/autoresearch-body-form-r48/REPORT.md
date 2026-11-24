# Standing #48 — slice conflict, OBSERVE

**Гипотеза подтверждена на фрагменте G22 к.2 SE.** В трёх независимых импортах принятого v002r1 одна подложенная полоска в данных сечения превращала тот же проём одновременно в пропуск и в лишний проём. Наблюдатель вместо двух ошибок отмечает один конфликт сечений: **1 → 0 двойных записей**, размах 0. Это не восстановление проёма: число подтверждённых проёмов остаётся 5, размеры неизвестны. На отклонённом v001 остались все шесть пропусков, а контроль J2 с настоящим лишним проёмом сохранил один FP. Тела, штатная проверка и её баллы не менялись. PR нет.

[Contract](../autoresearch-body-form-slice-conflict.md) `86a36bb36da2283020e007c5488c412c1ad20310`. [Numeric receipt](receipt.json); measured [observer](probe.py) SHA-256 `fa79d05ae0ed8a99e2ce97902857296cd88e60e50314a5448c7a570af0d70f01`. Status `complete`, 16.098 s, first native pair 2.070 s, first diagnostic pair 0.0036 s, projected diagnostic remainder 0.0929 s; no budget stop. First invocation stopped before diagnostic scoring (`KeyError: raw_unknown_pct`); corrected the receipt field lookup to the prior trace's `baseline_unknown_pct`, kept the failed run locally, and reran the entire matrix without changing the rule or threshold.

## Clean controls and parity

Three new Blender 5.1.2 paired imports. A/R clean scores 100.00/4.55, median margin 95.455 pp, spread 0. Gap TP/FP/FN 6/0/0 vs 0/0/6, weighted unknown 0% vs 54.55%. A depths 0.100/0.130/0.150 m (two each); R depths not measured. Section outline maxima at 16.85/19.8 m, rounded: A 0.000/0.000 m, R 0.610/0.610 m. These are not per-facade maxima. Historical whole-body mesh proxy #40 ranks the pair in reverse (83.693/90.830; not remeasured). Raw report bytes unchanged by C1; prior #44 row parity holds excluding only documented path-dependent hashes. No clean input triggered a relabel (`not_exercised` for relabel invariance, but measured raw counts).

## Planted evidence (not changes to FBX)

| Section perturbation on A | Raw → diagnostic TP/FP/FN | Conflicts / repetition |
|---|---|---:|
| +110 mm at 17.8 only | 5/1/1 → 5/0/0 | 1 |
| +110 mm at 18.2 only | 5/0/1 → 5/0/0 | 1 |
| +60 or ±110 mm at both heights | 5/0/1 → 5/0/1 | 0 |
| +130 mm at both heights | 6/0/0 → 6/0/0 | 0 |

All six states on R: 0/0/6 → 0/0/6; inserted segments counted in each row. J1 retained one FN; J2 retained one FP; J3 unchanged. Stale J4 and masked slice abstained; their proposed diagnostic is **not measured**, not evidence of a pass. All 36 paired-matrix rows and 15 named controls met the predeclared bounds. Only the one-height accepted probes exercise a relabel; rejected probes exercise retention of independently missing mouths, not a relabel on genuinely rejected mixed-slice geometry. The output distinguishes a conflict in sampled inputs, not whether the projected support belongs to the exterior wall.

Not measured: native models with planted faults, a true mixed-height architectural opening, KPP1/Sokolniki exact verdict pairs, cross-site calibration, render/scene agreement beyond the prior rounds, new judge Yes-bias or κ. The accepted KPP1 contour A and Sokolniki v002/D375 sheet were not promoted to body verdicts. Ready to review the observation, **not** ready to use as a gate.

Replay: `python docs/research/autoresearch-body-form-r48/probe.py .ar48-replay-new` with unused output path. Requires prior #44/#42 Git objects and the full verified #40/held-out input packs on this PC; no private inputs in Git. If the wall cap trips, replay from a fresh output directory on an idle slot without changing the cap or shortening the series. No published candidate body. Affected tests: `env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run --offline pytest -q tests/test_body_contours.py tests/test_blender_exit_code_guard.py --basetemp .ar48-pytest` — 41 passed (1 warning: test runner relocated its temp directory outside repo). `bash C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh` — 542 passed, 1 warning; `repo_guards: GREEN`. Full suite: not run (no PR).
