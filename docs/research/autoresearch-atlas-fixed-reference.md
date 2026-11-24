# Standing #60 — fixed-reference diffuse drift (OBSERVE)

## Frozen before implementation and measurement

H60: with one fixed VPM visual reference (AC08 v010), the rejected v007 NPM should have a larger diffuse error than the v010 NPM. Unlike #58 this is reference agreement, not contemporaneous NPM/VPM agreement. A builder can move the score by retaining the reference texture's appearance and registration. Even a positive separation cannot attribute the cause to seams alone (finish and colour also changed).

- Fixture and provenance: AC08 v007 (joint-pitch rejection, #559 comment 6341991856) and v010 (accepted visual reference only, #559 comment 6345392389). Four original packages and pinned render code/specs as in `d45e1ea44471de876f577b63a403f1be43c118ec:docs/research/atlas-drift-r58/replay.py`; pin and verify Blender 5.1.2 `ec6e62d40fa9` executable SHA-256 `1e6624af112b3c936f4b038b025ebd2bf00ae72c4b62881a6787166d71c58fa5`. Use the existing historical readback without changing staging or rendering; no Max. Same four cameras at 400 px/m, exact camera/frame and shape parity required. No rescoring old dumps for repeatability.
- Score: pooled mean `sum(abs(RGB_NPM-RGB_v010_VPM))/(765*n)` over the single mask common to both NPM labels and v010 VPM: all three fully opaque, no red datum pixels (R>200,G/B<30 in any operand). Each view requires common/union opaque coverage >=0.99 and nonempty mask. One number `D60 = median_3(E_v007-E_v010)`. Keep for further study only if each pair's delta is positive, D60 >=0.002, delta spread <=0.0005 and all controls and parity pass. Valid scores with insufficient separation refute H60; preflight, coverage, parity, control or stability failure is inconclusive. Record per-pair spread, times and status.
- Positive and collateral control: on each NPM label shift RGB horizontally +20 render px (+0.05 m) in memory, without shifting alpha. Evaluate shift and clean on the same interior mask, restricted to positions whose unshifted and source (`x-20`) pixels are both inside the frozen mask; never wrap scored pixels. Predict `delta E >=0.0005` on both labels and >0 actually changed pixels per view. This is a registration proxy, not a native UV edit. Negative: outside the fixed comparison mask replace NPM RGB with 17, expect `delta E = 0` and >0 actually changed pixels in each view per label. Hash reference and staged inputs, keep originals immutable, report per-case and per-variant changed pixel counts; zero changes in a probe mean not exercised. No rule applied to any delivered work.
- Budget: exactly three fresh pairs (six Blender processes), one metric variant, zero candidate code rounds. Reused R58 timing: first measured pair must take <=90 s and leave >=2x its time +15 s of the 270 s render+preflight budget; otherwise stop inconclusive and replay unchanged from a fresh directory when the budget fits. Reducer cap: 60 s for the three pairs, no shortened series. Do not tune masks/thresholds after seeing results, relax checks, edit packages, deselect tests or change files owned by another card.
- Wider calibration not inferred: #1817/#1818 own KPP1 v004 delivery and technical open rows, not a seam-rejection label; Vatutino #1745 lacks an authoritative seam-rejection pair; #1500 owns pending Staropetrovskiy etalons. #1649 owns G22 atlas-fit and #1809 cell numbering. Padding, texel, joint-count calibration and form check v1 are not scored here. Readiness: 2026-11-24 09:44, areas 4 and 11.

Replay from published branch (authorized Windows Drive inputs, pinned Git parent available from origin):

```bash
uv run --frozen python docs/research/atlas-fixed-reference-r60/replay.py tmp/r60-run-NEW
```

## R0 — confirmed on AC08; observe only

Three independently rendered pairs; all six Blender exits 0. Exact cross-label camera/frame parity,
opaque Jaccard 1.0 on all four views, 12,422,568 scored pixels per pair. Original ZIP hashes and
staged input hashes matched before/after. The paired result is identical at the printed precision:

| Pair | Native seconds | Reducer seconds | v007 NPM error | v010 NPM error | Paired difference |
|---|---:|---:|---:|---:|---:|
| 1 | 16.037 | 6.472 | 0.1394363112 | 0.0068311150 | +0.1326051962 |
| 2 | 17.976 | 5.867 | 0.1394363112 | 0.0068311150 | +0.1326051962 |
| 3 | 19.739 | 5.461 | 0.1394363112 | 0.0068311150 | +0.1326051962 |

Run status completed, wall 72.313 s; D60 = +0.1326051962, paired spread 0. The unchanged #58
same-revision comparison also replayed and remained reversed (−0.0043417467). The fixed-reference
number responds to disagreement with the accepted appearance; it is not a seam detector and does
not show that an atlas implementation caused the original rejection.

- Clean: delivered renders only. No measured input was changed.
- Injected: right shift test changed 7,959,107 pixels for v007 and 8,109,647 for v010 per pair
  (four views, identical counts across runs). Interior error rose by +0.000983829 and +0.011980921,
  respectively. Outside-mask test altered 2,162,616 pixels per label per pair; score delta was
  exactly 0. Every rendered view exercised both probes for both labels. Per-view counts and
  hashes are in the receipt.
- Not measured: native UV/atlas mutation, defect attribution, MAF, KPP1, other objects, padding,
  texel density, thresholds for enforcement, or downstream acceptance. No candidate to ship.

Measured script commit `47251baeecc018dd5bda110d8b37bdae3f5893a7`; reducer SHA-256
`aa0988dda70f8efefdf8035425667b772500bea9bbff646375af76de38652c7e`. See
`atlas-fixed-reference-r60/receipt.json` for the exact operand hashes and attempts. Drive evidence:
`G:/Мой диск/AGR-evidence/standing60-atlas-fixed-reference-r001/`, 50 destination files verified
against the source files; `SHA256SUMS.txt` SHA-256
`0fcf830741094f9ead568b3ed6b785a1ed5ee5502067bd7402d1c0f73ac43f8a`. Raw receipt SHA-256
`28894e216520eb6293075dec8833712979c83523e6e87bded64fb9ba1b605594`.
Replay is limited to authorized access to the pinned native ZIPs, Blender and Git history.

Next: isolate joint count and phase via the existing slide-49 oracle; then vary NPM registration
alone on a runtime copy, leaving VPM pixels, geometry and colours fixed. Neither is measured here.
