# Standing #138 — matched-cell ordering in AC08 FLAT render-diff (OBSERVE)

## Frozen contract

H138: the v007 reversal seen at V2 facade p95 is broad, not merely aggregation: on every facade, at most half of the matched 1 m cells give rejected v007 a higher NPM-vs-VPM mean ΔE than the v010 visual reference by more than 0.01 ΔE. Count cells equally; ties and reverse ordering remain in the denominator. The one statistic is the share `mean(ΔE_v007 − ΔE_v010 > 0.01)` by facade; the case diagnostic is the largest facade share. Report each round and median/min/max/spread for each facade and the case. Confirm H138 if the case share is <= 0.5 in all three valid rounds; otherwise refute. This is retrospective failure localization, not an independent calibration or a change of metric for acceptance. Passing the separate native calibration would require every rejected facade's V2 p95 and case maximum to be strictly above the reference; missing cross-job pairs preclude a general result. No production KEEP.

- Fixture: AC08 v007 (rejected: wrong pitch shared by both profiles) and v010 (visual reference), exact two-profile ZIPs, all four FLAT facades from the pinned #128 replay `5c15100ee5631e2f5d75e697e14e1977a6361f3d`. Use its 400 px/m render, 100 px/m analysis, datum exclusion, coverage filter and one-metre grid intact. Require matching camera records, positive identical cell keys and exact equality of resampled common-mask bytes between labels; no arbitrary unmatched-cell dropping. Instrument only the already-computed cells and mask hash. Verify unmodified summaries, camera, controls, decoded RGBA, ZIPs, staged members and runtime against #128's sealed receipts; require instrumented summaries equal unchanged summaries. Pin the observer and contract by committing them before execution.
- Synthetic controls separately on each label, south: existing #128 P1 wrong-colour patch must change >0 NPM RGB pixels, preserve VPM, alpha and common mask, and produce >0 cells with mean delta >0.01 and at least one delta >=2 ΔE; other facades are not exercised. N0 identical-to-VPM must give zero every cell, preserve VPM/alpha/common mask, and change >0 NPM RGB pixels on every facade. These bounds test observation, not real seam/padding/density sensitivity. Reference control is exercised on v010. P2/P3 are replayed only as historical parity guards, not as new cell evidence.
- Budget: three confirmations, zero improvement candidates. Preserve #128's first-pair <=90 s and >=2× first-pair time +15 s remaining within its 300 s. Entire run cap 420 s; after first cell pass require >=2× first-cell-pass time +5 s remaining. Abort/inconclusive on budget, parity or witness failure; no cached frames, shortened series, deselection, relaxed rules, delivery edits, Max or other cards' files. Record actual wall/status separately.
- Admission: readiness `2026-11-27_1231`; reuse #128, with #130's v006 result historical only. KPP1 v004 #1817: #2020 shared-core refactor merged with accepted output unchanged, not a new texture refusal; Vatutino MAF #1499 closed without exact texture pair; Staropetrovskiy #1500 open and #1783 draft hashes are not paired visual labels. Cross-job rows not measured absent exact two-profile accepted/rejected texture versions. #1947 owns atlas/master binding; #2014 owns joint-gate binding, #1969 Ground, #559 presentation/joints. Trainer/form remain parked.

```bash
python docs/research/autoresearch-npm-vpm-cell-order-r138/replay.py tmp/r138-NEW
```

Requires the exact Drive ZIPs, Windows Blender and pinned Git objects #125/#127/#128; replay limited to readers with those assets. Conditional replay after a timing stop uses another fresh directory.

## Result — H138 confirmed; V2 calibration refuted; OBSERVE, no PR

**Итог:** на трёх свежих парах НПМ/ВПМ ни одна из **100** совпавших метровых ячеек не поставила отклонённому AC08 v007 балл выше визуального эталона v010. В 54 ячейках балл v007 ниже более чем на 0,01 ΔE, в 46 разница в пределах ±0,01. Обратный порядок не вызван свёрткой p95: уменьшать область подсчёта в этой сетке недостаточно. Не предлагать V2 как приёмочную проверку.

| Facade | Cells | v007 higher | v007 lower | Tied within ±0.01 ΔE | Median v007 − v010 ΔE |
|---|---:|---:|---:|---:|---:|
| South | 35 | 0 | 18 | 17 | −0.1291 |
| East | 15 | 0 | 9 | 6 | −0.8221 |
| North | 35 | 0 | 18 | 17 | −0.6315 |
| West | 15 | 0 | 9 | 6 | −0.6103 |

**Clean:** all three rounds (not three rescoring passes over the same frames) gave the same cell comparisons, including an exact maximum cell delta of 0.0 on all four facades. The case share was 0/0/0 (median 0, spread 0). V2 case score 0.8974 vs 1.8381 ΔE, reverse ordering on all four facades. All 60 decoded frame hashes, four ZIP and 31 staged-member hashes matched the prior references; camera, mask and V2 scoring parity passed. `series_complete`, wall 97.18 s (native replay 79.37 s); native pair timings 25.94/25.04/27.27 s; cell pass timings 5.75/5.61/5.53 s.

**Injected:** the south P1 patch changed 635,552 / 635,685 NPM RGB pixels in v007/v010 and increased nine cells on each label; maximum cell rises +7.8454 / +11.5995 ΔE, respectively. N0 gave exact zero in all cells, changed NPM RGB on every view, and both controls preserved VPM, alpha and common masks. P1 on east/north/west is `not_exercised`. The synthetic controls are evidence of observer activation, not an acceptance label.

**Not measured:** KPP1, Vatutino MAF and Staropetrovskiy MAF accepted/rejected texture pairs, actual UV/padding/density faults and any scale smaller than the frozen cells. Next: bind an exact NPM texture refusal and corrected NPM to byte-identical VPM, with the affected element identified before scoring; if Staropetrovskiy #1500 supplies a reviewed pair, verify that its decision is texture-specific and binds both profiles. No production changes or delivery checks promoted.

Measured head `a80a1531bae0d67f0d1033adfe578cfce7ca7367`. [Receipt](autoresearch-npm-vpm-cell-order-r138/receipt.json), Git LF SHA-256 `472264fcdf23aee7bb8d8708c209726ad8e75fc1f1230aba53e3e01077409de6`.
