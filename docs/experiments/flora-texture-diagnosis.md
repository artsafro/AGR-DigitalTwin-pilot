# Experiment: Flora texture diagnosis

**Preliminary / rework requested.** The expanded island-role/pixel-class acceptance is not complete.
Original VPM Tilia calibrates at only 13.5573% opaque / whole UV area, incompatible with a literal
95% whole-area foreground-class threshold. See the main report rework gate and the tested
`experiments/flora-texture-diagnosis/calibrate_uv_area.py` before extending the scorer.

Main deliverable: [diagnosis report](../research/flora-texture-diagnosis.md), #369.
Question: are the review-scene defects caused by paths, UV correspondence, opacity or native rendering?
No production fix, generated map, catalogue change or published-asset edit is part of this experiment.

| Method / measurement | Baseline | Diagnostic comparison | Verdict |
|---|---|---|---|
| Rebind whole-plant maps without UV adaptation | Original component/project atlases | 99/99 original UV hashes retained, 99/99 bitmap sets replaced; visible defects in 6/6 selected species | Reject as an appearance-preserving route |
| Original render + direct slot paths + UV overlay | File-path/geometry checks cannot see semantic layout mismatch | 51 native renders, six visually inspected sheets; missing trunks, square crops, invisible Spiraea | Adopt as an appearance prerequisite |
| Indexed-PNG native decoding | Alpha 0 at tested opaque bark points | Pixel-identical scratch RGBA copies read alpha 255 at those points, 3/3 files | Maybe: build-specific diagnostic workaround, not a production conversion |
| Scene color management | Union Gamma / FLORIO Unmanaged / v003 OCIO | Common Gamma + explicit save gamma 2.2; all 17 front backgrounds equal; layout defects persist | Adopt explicit control in comparison scripts |

Setup, copied inputs, commands, per-species measurements and follow-up issue draft are in the main report.
Final native rendering cost: median 1.103 s across 51 view renders; wrapper wall 195.5 s. This is not an
identical-workload repeated-run speed comparison. Output UV deviation: zero for 99/99 pairs. Maximum
bbox-centered same-index vertex deviation across the six NPM pairs: 0.041962 mm. Protected inputs:
236/236 before/after SHA-256 equal. Pure-Python RED 13 failures; final focused tests 28 passed.

Proposed adopt follow-up: **Flora: rebuild map-to-UV correspondence before republishing the library**;
scope: classify original atlas/component/multi-material layouts, choose reviewed remap/bake/rebuild
routes, verify original-vs-new views, then regenerate light/readbacks. No follow-up issue was created.
