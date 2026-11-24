# Standing #62 — AC08 native NPM atlas phase sensitivity (OBSERVE)

## Frozen before implementation and measurement

H62: the unchanged #61 slide-49 joint oracle flags an NPM-only horizontal UV registration error applied after native FBX import, with VPM unchanged. This is a sensitivity test, not a new submission gate. The existing v007 rejection (#559 comment 6341991856) and v010 accepted *visual reference* (#559 comment 6345392389) must still separate on the clean runs; the native injections are synthetic, not new human labels.

- Fixture: the four original AC08 ZIPs pinned by #58 driver `d45e1ea44471de876f577b63a403f1be43c118ec` and slide/checker `d45346548e06847167b386c2c0c71b50ccdfb18e` (#61). Pin historical renderer and specs as in #58; additionally use each revision's `pilot-<revision>/npm_atlas.json` at its pinned spec commit. Require Blender 5.1.2 build `ec6e62d40fa9`, exe SHA-256 `1e6624af112b3c936f4b038b025ebd2bf00ae72c4b62881a6787166d71c58fa5`. Headless only, no Max. Use existing atlas metadata/readback and coordinate transform of `export_npm.py`; don't rebuild an atlas or a delivered model.
- Variant: on fresh FBX import, select faces whose entire active loop-UV polygon belongs to one `PanelVJ*` cell, using its pinned rectangle; fail on partially assigned panel faces. Add exactly +5 atlas px (`5/2048` in U, about 51.6 mm at 96.9 px/m) to these loops only; all selected loops must remain inside the cell including its declared right extrusion allowance (6 px; a guard against crossing to another cell, not proof of padding compliance). Also apply +0.5 px (~5.16 mm) as a separate near-tolerance control. Both variants executed on both labels. Clean uses the original renderer; variant renderer adds one hook after import, never exports FBX or changes maps.
- Single score: `D62 = median_3(JE(v010,+5 px) − JE(v010,clean))`, same eight NPM rows and tolerance as #61, same v010 VPM frame. Pass for further research only if every pair delta >= 8, paired spread 0, v007 clean JE > v010 clean JE = 0, v010 +0.5 px ΔJE = 0, with all parity and coverage checks passing. Valid +5 measurements below the bound refute H62; clean label-order, stability, near-tolerance, parity, coverage or budget failures are inconclusive. v007 perturbation deltas recorded with no directional bound (already wrong at clean). Report counts rather than assuming robustness to all sub-tolerance offsets.
- Parity: #61 `score_version` recomputes oracle rows and compares to unchanged `compare_facades` for every state. All cameras and four scored VPM images must match across variant and clean for each label and across rounds (VPM pixel equality, not equality between labels); NPM alpha unchanged. Check that only selected UV U coordinates change, exactly the requested delta at float32 precision; geometry, transforms, polygon material slots, other UVs (if present), images and scene files are not edited. Report selected/changed UV loops, changed rendered RGB pixels per view/state, including clean-vs-clean repeat; any zero-coverage probe is `not_exercised` and not measured. Record separately whether VPM remained unchanged under an exercised NPM probe. Hash input files before and after, code and effective renderer, record per-round scores and walls.
- Budget: three fresh rounds, two labels, three states, one metric variant, zero production or new candidate code rounds. First full paired round <= 105 s; cap 360 s total and require after round 1 at least 2 × round 1 + 15 s remaining. Otherwise `budget_stop`, `inconclusive` for this run; replay identical command in a fresh directory when timing permits. No rescoring frozen images as stability evidence. No tuning rows, tolerances or labels; no deselecting tests, weakening checks, editing delivered packages or other cards' files. Standalone metric observation, no automatic application.
- Coverage excluded: form check v1 is closed for research. G22 #1649, KPP1 v004 #1817/#1818, Staropetrovskiy #1500, MAF numbering #1809; no authoritative Vatutino MAF rejection pair found in prior rounds. Padding 8/32 px and textured-ID density are distinct hypotheses, not measured here. Readiness 2026-11-24 13:45, areas 4/11.

Replay from this branch with pinned Windows Blender and Drive inputs: `uv run --frozen python docs/research/atlas-native-phase-r62/replay.py tmp/r62-run-NEW`. Replay limited to readers with those inputs and #58/#61 Git objects.

## R0 — confirmed (OBSERVE)

**Итог:** на АС.08 изолированный сдвиг UV на +5 px атласа НПМ дал ΔJE = +320
(размах 0) относительно чистого v010. Камеры и пиксели ВПМ совпали, исходники
не изменились. +0.5 px не поднял JE на v010. Это чувствительность к синтетическому сдвигу,
не доказательство причины исходного отклонения v007 и не порог приёмки.

Run status `completed`; wall 284.155 s. Measured script commit `01ac9d1e7e06fd016a131549a7c287c34dd21b19`.
First-round budget gate passed; all rounds use fresh native imports and renders.

| Round | Wall, s | v007 JE (clean / +0.5 / +5) | v010 JE (clean / +0.5 / +5) | D62 |
|---|---:|---|---|---:|
| 1 | 87.728 | 202 / 194 / 203 | 0 / 0 / 320 | 320 |
| 2 | 106.347 | 202 / 194 / 203 | 0 / 0 / 320 | 320 |
| 3 | 88.989 | 202 / 194 / 203 | 0 / 0 / 320 | 320 |

**Clean:** identical historical checker, direct row parity in all states; clean v007 is worse than visual
reference v010 in every round. **Injected:** all four NPM facade images changed in both variants on both
labels and all rounds. NPM alpha, exact camera/frame and the four scored VPM decoded images were unchanged;
full per-view counts (including vs round 1) and hashes are in the receipt. The perturbation never needed
edge extrusion, hence bleed at the cell boundary was not exercised.

- v007 +0.5 px: {'PanelVJ_RAL5015': 114} UV loops; extrusion loops 0; changed NPM RGB pixels per round: [4333323, 4333323, 4333323].
- v007 +5 px: {'PanelVJ_RAL5015': 114} UV loops; extrusion loops 0; changed NPM RGB pixels per round: [5336443, 5336443, 5336443].
- v010 +0.5 px: {'PanelVJ30_RAL5015': 90, 'PanelVJ12_RAL5015': 24} UV loops; extrusion loops 0; changed NPM RGB pixels per round: [4657513, 4657513, 4657513].
- v010 +5 px: {'PanelVJ30_RAL5015': 90, 'PanelVJ12_RAL5015': 24} UV loops; extrusion loops 0; changed NPM RGB pixels per round: [5434841, 5434841, 5434841].

**Not measured:** other objects (KPP1 / Vatutino / Staropetrovskiy), UV padding, texel density,
cell bleed, a production false-positive rate, or user acceptance. No checker or delivery change applied.

Receipt: `atlas-native-phase-r62/receipt.json` SHA-256 `d7028637c7b8333d2efb8b8cb9ade95334ecb0d1b38889a1d8d14d29e4cf0124`.
Verified evidence: `G:/Мой диск/AGR-evidence/standing62-atlas-native-phase-r001/`, `SHA256SUMS.txt`
SHA-256 `40468e97f2c0e3b14e5c6f33395d33162e1eadaef94e9f1174fb4bba9b7e35f5`. Replay needs the pinned Windows Blender and access to the original packages/slide.

Affected tests: `uv run --frozen pytest -q -o addopts= docs/research/atlas-native-phase-r62/test_phase.py tests/jobs/test_tec26_ac08_pilot.py tests/jobs/test_tec26_ac08_slide_overlay.py tests/jobs/test_tec26_joint_visibility_controls.py tests/test_kpp1_export_safety.py tests/test_npm_atlas_padding.py` — 200 passed, 26 skipped (fixture gates), 1 warning. New selection test initially failed to import the absent probe; then passed.

`bash C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh` — 542 passed, `repo_guards: GREEN`.

Full suite: deferred to merge batch (rule 68)
