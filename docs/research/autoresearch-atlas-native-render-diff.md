# Standing #64 — native atlas drift through the existing paired render metric (OBSERVE)

## Frozen before implementation and measurement

**Цель:** выяснить, годится ли уже измеряемая RGB-разница между НПМ и ВПМ для более узкой задачи: обнаружения сдвига только атласа НПМ при неизменном источнике ВПМ. Это не оценка качества швов и не порог приёмки.

H64: the #58 paired render metric responds to a real +5 atlas-px NPM-only U offset, relative to each version's own clean baseline. #58 already refuted clean-label calibration for design quality (v007 rejected for seam pitch, v010 accepted visual reference, #559 comments 6341991856 and 6345392389); #62 proved the native mutation is exercised. Do not relabel a synthetic perturbation as a human rejection. Record the clean-label order again; if it stays inverted, the metric is not eligible for a delivery gate, regardless of H64.

- Fixture: AC08 v007 and v010, exact four delivered ZIPs + slide 49 + Blender 5.1.2 exe, full SHA-256 pre/postflight inherited from #62 (`75257229cb561c64bace8250f632c13bc4d694af`) and its pinned #58 (`d45e1ea44471de876f577b63a403f1be43c118ec`) and #61 (`d45346548e06847167b386c2c0c71b50ccdfb18e`) replay paths. Historical renderer and `vpm_uv.py` remain at #58's `a1f41ee216ba881ada1d1460e6b67f048446e14e`; no generator/export rewrite, Max, or delivery writes. Stage the same native copy, cameras, exporter layout and readback as #62. Scope: four orthographic FLAT facades at 400 px/m, no iso, jointed PanelVJ cells only for mutation; the reducer pools whole facades.
- Variant: untouched #62 `phase.py` adds `shift_px/2048` to U on all loops of whole faces inside the pinned PanelVJ cells. Both labels, freshly imported/rendered clean, +0.5 px and +5 px in each of three rounds. +5 px on accepted v010 is the positive trigger (unchanged #61 JE=320, versus v010 clean=0; small v010 JE=0; v007 clean JE=202 is the rejected label witness). +0.5 px is an exercised smaller perturbation, not an invariance claim. Report changed UV loops by cell and NPM RGB counts by view per state; NPM alpha, VPM decoded pixels, camera tuples, non-target geometry/material/UV and input bytes must not change. No-op perturbation = `not_exercised`, not a successful check.
- Reuse unchanged #58 `score`: normalized mean RGB L1 E over common fully opaque pixels, excluding the red datum; opaque Jaccard >= 0.99, report p95 descriptive only. Require identical per-view mask counts across shifts within each label (no evidence of scope drift; not a general mask identity proof). One scalar `D64 = median_3(min_label(E(+5) - E(clean)))`; range is max minus min of those paired values. Valid round requires prior JE witnesses, exercised perturbations and parity. Confirm H64 if D64 >= 0.002, both labels have delta(+5) >= 0.002 and strictly greater than delta(+0.5) in all rounds, and |delta(+0.5)| <= 0.002 in all rounds. The 0.002 bound is an R&D effect size carried from #58, not a regulation. Valid measurement outside effect bounds refutes H64; bad parity, witness failure, paired spread > 0.0005, incomplete series, timeout or budget stop is inconclusive. Record natural v007-v010 clean deltas separately; #58's D >= 0.002 and every paired clean delta > 0 would be needed even for calibration on this single object.
- Budget: one diagnostic variant, zero candidate code rounds, three rounds (6 native pairs each round). Reuse #62 watchdog: first complete round <= 105 s; remaining >= twice the first round plus 15 s, total native cap 360 s. Stop on budget check; same command to a new directory under a suitable slot, not a shortened replay. Forbidden: retuning variant, mask, labels or tolerance; deselecting tests, modifying packages, touching other cards' files, replacing fresh renders with cached images, auto-enabling any gate.
- Readiness `2026-11-24_1345`, areas 4/11. Not taken: form check v1 (closed), G22 #1649, KPP1 #1817/#1818, Staropetrovskiy #1500, MAF numbering #1809. KPP1 technical rows, Vatutino solid diagnostic and unresolved Staropetrovskiy etalons are not human-labelled seams. Vertical shift, padding/bleed, texel density and MAF transfer not measured here.

Replay (requires the pinned Windows Blender, Drive ZIPs/slide and Git objects; replay limited to that environment):

```bash
uv run --frozen python docs/research/atlas-native-render-diff-r64/replay.py tmp/r64-run-NEW
```

## R0 — inconclusive (OBSERVE; no PR)

**Итог:** свежий прогон показал рост RGB-разницы на обеих версиях АС.08 при сдвиге атласа НПМ на +5 px, но успел закончить только **1 из 3** раундов. На принятом визуальном эталоне v010 даже +0,5 px превысили исследовательскую границу 0,002. На чистой паре повторилась обратная сортировка #58: RGB-разница у отклонённого v007 меньше, чем у v010. Метрику не предлагаю для приёмки. Производственный код и пакеты не менялись.

| AC08 | E clean | E +0.5 px | E +5 px | JE clean / +0.5 / +5 |
|---|---:|---:|---:|---:|
| v007 (rejected pitch) | 0.00248937 | 0.00365033 | 0.00771173 | 202 / 194 / 203 |
| v010 (accepted visual reference) | 0.00683112 | 0.00899838 | 0.01726433 | 0 / 0 / 320 |

Run status `budget_stop`, hypothesis `inconclusive`, wall 125.387 s; round 1 took 123.348 s (>105 s, which also leaves less than `2 × round1 + 15 s` within 360 s). The first round's minimum +5 px response was +0.00522236; v010 small response was +0.00216727. Median and paired spread are **not measured**. Do not infer stability or revise the hypothesis from the budget stop. Replay the exact command above in a fresh directory on an idle slot; the same timing check can stop it again. First attempt (`refused`, 17.079 s, no score): #62 camera reference values were lists, #58 compares tuples. Fixed the adapter to keep separate exact reference maps; no fixture, threshold or render change. Measured commit `1fb5052e5e844e04c36e011b664f61e9d5e118dc`; Python 3.14.7 / NumPy 2.5.3 / Pillow 12.3.0.

- **Clean (round 1 only):** all camera tuples matched; each state used 12,422,568 pixels over four facades, opaque Jaccard 1.0; clean design-label delta −0.00434175, consistent with #58's independent result (not a new median).
- **Injected (round 1 only):** 114 UV loops shifted per version and state; every NPM view changed RGB (625,899–2,057,200 pixels); decoded VPM images and NPM alpha exact; immutable input and staged checks passed. +5 on v010 reproduced JE=320. The mutation guard preserved active UV outside targeted loops and other recorded scene state.
- **Not measured:** three-round stability, no shift touched the extrusion band (`not_exercised`, all zero), V-axis, other objects, required 8/32 px island spacing, texel density and transfer to MAF. Do not use this as a work-return rule.

Receipt `atlas-native-render-diff-r64/receipt.json` (LF SHA-256 `f67b9ce50594442dfd99a884742e3767a59c2d2d3a269363356b43a5149a3882`); refused attempt beside it. Shared evidence `G:/Мой диск/AGR-evidence/standing64-native-render-diff-r001/` (134 files, copy hashes verified; SHA256SUMS `bd0794b4367ec6adb48e5f801c753381baa3f2f97cef0802bca81c019f9f8000`). The Drive receipt hash is `576fb2a84f4c164831ea143d016da81b6aab8ad0e640ed4d73c4a4b11beeb6d6` (CRLF). Replay is limited to the pinned renderer, Drive originals and Git revisions named above.

Affected tests: `uv run --frozen pytest -q -o addopts= docs/research/atlas-native-render-diff-r64/test_replay.py` — 4 passed; no production modules changed or import the adapter. Initial RED: absent replay module. Pilot guards: `bash C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh` — 553 passed, 1 warning, `repo_guards: GREEN`.

Related checks: `uv run --frozen pytest -q -o addopts= -n 4 --basetemp C:/x/pytest-t-f177057f-affected-03 docs/research/atlas-native-render-diff-r64/test_replay.py tests/jobs/test_tec26_ac08_pilot.py tests/jobs/test_tec26_ac08_slide_overlay.py tests/jobs/test_tec26_joint_visibility_controls.py tests/test_npm_atlas_padding.py` — 157 passed, 25 skipped in 177.80 s. First serial attempt hit the outer 120 s tool timeout; the first parallel attempt had 3 `FileNotFoundError`s under the shared fallback temp path. A unique absolute `--basetemp` restored the unchanged suite.

Full suite: deferred to merge batch (rule 68)
