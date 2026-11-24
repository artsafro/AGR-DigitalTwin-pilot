# Standing #50 — neighboring opening, OBSERVE

**Гипотеза подтверждена на фрагменте G22 к.2 SE.** В трёх свежих парных импортах наблюдатель #48 заменил двойной FN+FP одной отметкой конфликта и сохранил отдельный лишний проём на том же фасаде и на принятом v002r1, и на отклонённом v001. **Потери соседнего проёма: 0 / 0 / 0, медиана 0, размах 0.** Это проверка на копиях данных сечений, не на перестроенных телах. Штатные отчёты, пороги и модели не изменены. Без PR и внедрения.

## Clean calibration and controls

[Contract](../autoresearch-body-form-neighbor-gap.md) `a2a770b7a7fc2cb36fc9e7319f7b24fd8405f1c5`, sealed driver at `55cb0c0054954016fbe5a0a76faa0a1bec58e62f`. [Receipt](receipt.json), SHA-256 `b8bc9b29e1e9317f93b2b18b196e3400ce7e594c3365862458b946373cb7f8c1`. Status `complete`; wall 17.140 s (prior replay 15.293 s, first native pair 2.040 s; first #50 mixed pair 0.285 s, projected remainder 2.139 s). Full-manifest checks before/after; no budget stop. All 51 inherited #48 bounds passed (its 36 planted rows and 15 controls, not 51 independent tests). Original A/R raw scene score 100.00/4.55, paired margin 95.455 pp each time, spread 0. TP/FP/FN 6/0/0 and 0/0/6, weighted unmeasured 0% and 54.55%. Section maxima at 16.85/19.8 m: A 0/0, R 0.610/0.610 m (not per-facade maxima). A reveal depths 0.100/0.130/0.150 m (two each), R depths not measured. Historical whole-body mesh proxy reverses the order (83.693/90.830, not remeasured). The original cross-corpus coverage gate remains unmet.

## Injected controls (section data only)

| Variant / state | Raw → diagnostic TP/FP/FN | Conflicts | Surviving planted extra |
|---|---|---:|---|
| A neighbor only | 6/1/0 → 6/1/0 | 0 | [3.20, 3.70] m |
| A mixed | 5/2/1 → 5/1/0 | 1 | [3.20, 3.70] m |
| R neighbor only | 0/1/6 → 0/1/6 | 0 | [3.20, 3.70] m |
| R mixed | 0/2/6 → 0/1/5 | 1 | [3.20, 3.70] m |

Same outcomes all three repetitions. Of the two mixed-state raw extras on segment 24–25, only [1.14, 2.94] m was relabelled. Neither became a TP. For all 12 rows, the neighbor injection removed 1 and added 2 segments at each of 17.8/18.2 m. Mixed A added one target segment at 17.8 m; mixed R removed 2 and added 2 at 18.2 m. No changes elsewhere in extraction; scorer item differences confined to the frozen allowlist, observer did not write the report. Clean and neighbor-only rows did not exercise relabelling. J1 retained the missing aperture, J2 the other extra; stale and masked operands remain not measured.

## Boundaries and replay

Not measured: a native variable-height aperture, a second accepted physical fragment or alternate facade frame, exact human-labelled KPP1/Sokolniki body pairs, new render ratings or judge agreement. KPP1 contour A and Sokolniki v002/D375 are authorities for geometry, not approval of model bytes. Review readiness: the observation is ready to review; not a production gate. Next discriminator: use a known variable-height aperture (e.g. a source-bound stepped head) to test when a conflict is legitimate rather than an apparent missing primary mouth.

`python docs/research/autoresearch-body-form-r50/probe.py .ar50-replay-new` (directory must not exist). PC-limited: prior #48/#44/#42 Git objects and the exact #40 + evaluator packs, locations and SHA-256 preflight in the pinned replay. Raw local outputs `C:/x/t_1113cdd6-r50/run1/`, hashes per row in receipt; no held-out key or meshes in Git. If wall cap stops the run, replay unchanged in a new directory on an idle slot.

Affected tests: `env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run --offline pytest -q tests/test_body_contours.py tests/test_blender_exit_code_guard.py --basetemp C:/x/t_1113cdd6-pytest` — 41 passed. `bash C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh` — 542 passed, 1 warning; `repo_guards: GREEN`. Full suite not run (no PR).
