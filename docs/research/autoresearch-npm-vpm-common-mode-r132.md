# Standing #132 — NPM/VPM shared-stripe sensitivity (OBSERVE)

## Frozen contract

Real calibration first: the #128 fresh three-pair series disproved the proposed universal ordering for AC08 v007 (wrong joint pitch); #130 ordered v006 (horizontal joints) correctly but did not establish independent transfer. No additional customer rejection is inferred in this round. H132: on both #128 real labels, the **same** synthetic stripe footprint in both profiles is substantially less visible to V2 than in either profile alone. This is a causal image-space sensitivity limit, not a held-out label or native texture intervention.

- Metric: unchanged #125 V2 south-facade 1 m cell mean CIE76 ΔE p95 at 100 px/m. Let N, V and B be the score shifts from clean for the NPM-only, VPM-only and both-profile arms. Scalar `R132 = abs(B) / min(N,V)`; record per-label median of three fresh paired renders and min/max. H132 confirmed only if N and V are each ≥ +0.25 ΔE and R132 ≤ 0.25 on both labels in every round. If either unilateral control fails, the measurement is inconclusive for attenuation; otherwise a parity-valid R132 above the bound refutes it. No KEEP threshold for production: no adoption in this round.
- Fixture and parity: original AC08 pilot-v007 (rejected) and pilot-v010 (visual reference), both ZIPs per label as pinned in #127 by #128, reuse #128 adapter unmodified at `5c15100ee5631e2f5d75e697e14e1977a6361f3d`. Pin scorer/renderer/UV/spec/Blender through that adapter. Require clean score rows and decoded RGBA hashes equal to #128, input parity, exact paired cameras, Python 3.14.9 / NumPy 2.5.4 / Pillow 13.0.0. The four facades are rendered; only south is intervened on. KPP1 v004, Vatutino MAF and Staropetrovskiy MAF require a texture-specific decision bound to both exact profile exports before/after; without it they stay not measured.
- Synthetic witness: from south common alpha ≥128 excluding the scorer's red datum in both inputs, paint 12-native-pixel-wide vertical dark-neutral (40,40,40) stripes at 240 px spacing (nominal 0.60 m at native 400 px/m), starting one interval after the leftmost eligible column. NPM-only (positive trigger + accepted control), VPM-only (symmetric positive control), and both (test), using the same footprint per label/round. Require >0 changed RGB per targeted profile, unchanged other profile in unilateral arms, unchanged alpha/datum everywhere, exact same rendered RGB at targeted pixels in both arm. Report changed counts per input/arm: zero changes are `not_exercised`, not positive perturbation evidence. Retain #128 clean renderer/scorer sanity checks; not a texture, padding, density, or whole-package acceptance test.
- Budget: three fresh paired confirmations, zero new metric candidates. Native budget is the unchanged #128 first-pair ≤90 s, remaining ≥2× first-pair wall +15 s, cap 300 s; whole replay cap 360 s. Before the second image-scoring pair require remaining ≥2× first image pair +5 s. Failure to complete all three with parity is inconclusive; replay in a new directory if load trips the stop. No Max, shortening the series, cached substitution, changing tolerances/checks, delivered packages or other cards' files. The output is a branch-only receipt, not a production patch.

```bash
python docs/research/autoresearch-npm-vpm-common-mode-r132/replay.py tmp/r132-NEW
```

Limited replay: exact Drive archives and Blender 5.1 on Windows plus the Git objects from `origin/research/autoresearch-standing-{125,127,128}`. All image witnesses are in memory; no customer files are edited.

## Result — H132 confirmed for this synthetic intervention; OBSERVE, no PR

**Итог:** одинаковые тёмные полосы в обоих профилях не подняли балл ни на одной из двух версий AC08. В трёх свежих парах полосы только в НПМ или только в ВПМ подняли p95 ячеек южного фасада на **23,23–23,92 ΔE**; те же полосы в обоих профилях слегка **снизили** балл. Render-diff пригоден для наблюдения за расхождением профилей, но не для приёмки общих дефектов текстуры. Пакеты и производственный код не менялись.

| AC08 | Clean south p95 | NPM only | VPM only | Both | Median R132 | Spread |
|---|---:|---:|---:|---:|---:|---:|
| [v007 rejected](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/559#issuecomment-6341991856) | 0.8877 | 24.1190 | 24.1190 | 0.8646 | 0.000994 | 0 |
| [v010 visual reference](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/559#issuecomment-6345392389) | 1.6980 | 25.6222 | 25.6222 | 1.6142 | 0.003503 | 0 |

**Clean:** unchanged #128 whole-case max 0.8974 vs 1.8381 ΔE (reverse ordering, not rescued by this result). In all six fresh render sets, cameras, clean and historical-control score rows, and 60 decoded RGBA hashes matched #128. Original ZIP and staged file hash parity passed. `series_complete`; 151.32 s wall, native 120.67 s; native pairs 43.61 / 39.43 / 36.64 s; witness pairs 7.67 / 10.17 / 12.14 s.

**Injected:** each targeted input changed 219,720 RGB pixels, each untargeted input 0; alpha, datum and RGB outside the footprint were unchanged. Both-profile signed shifts were −0.0231 and −0.0838 ΔE. Untargeted profiles and other facades are `not_exercised` for the image intervention; no native texture, UV, padding or density perturbation was measured.

**Not measured:** 0/3 eligible external pairs. #1817 KPP1 v004 has both profiles but no paired texture refusal; Vatutino MAF v005 has both profiles but no exact texture-rejection pair bound by #1499; the November 20 Staropetrovskiy set has both ZIPs, November 24 only VPM, and #1500 remains open without a reviewed two-profile pair for T02. No held-out package ordering is inferred. #1947 owns atlas/master validation, #1969 Ground atlas/assembly, #559 the drawing-based comparison; none were changed. Trainer remains parked by the focus override.

Measured head `c891188aabf2830580d2f424d48c686338bf02bc`; [receipt](autoresearch-npm-vpm-common-mode-r132/receipt.json) SHA-256 (Git bytes) `da18dbbbdb2eedd4fa68edf37a414ec6ec4a853edf5af4a757f71557809d4c30`.

Affected tests: `uv run --frozen pytest -q tests/test_facades_texture_pattern.py tests/test_npm_atlas_udim.py tests/test_npm_atlas_padding.py` — 123 passed. Pilot guard: `bash C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh` — duplicate guard green and 567 passed. Full suite: deferred to merge batch (rule 68).
