# Body scorer calibration: chamfer exception (standing #20, OBSERVE)

**Кратко для Артёма.** Проверяем один вариант: не считать штатные горизонтальные скосы 45°/135° локальным дефектом. Бадики и штатную оценку не меняем.

## Frozen contract

Continue the #19 `localize.py` harness at `987f418a237e5931d695c278bcca177c789de3da` (script SHA-256 `e84c7bef192e1aa3f7a9a3295869d26a4d8e961bc6d976514e6f730340f160d7`); inherit its input hashes, zones, parity and witness checks. Fixture: all 13 frozen #13 inputs in nine same-building comparisons (63B v007 against v001–v006, 63C v002/v001, KPP1 v003 rest/corners, G22 k1 v003/v002); accepted-only 63A v005 and G22 k2 v002r1 from #18. No cross-building ranking. G22 k1 distance to etalon rewards the rejected result; don't optimize it. G22 k3 and independently labelled rejected/control pairs are not measured.

One primary metric: minimum accepted-minus-rejected margin in score points across all nine pairs and both shifts `(0,0,0)` and `(-5,7,11)` m, using the median of three runs per input/variant/shift. Threshold ≥0.500 with complete per-pair results and paired spread (max−min of paired differences). Gates: v007 and each holdout drop vs R0 ≤0.500; translation parity and repeatability exact; complete canonical report parity outside `score`, `penalties.irregular_area_share`, `local_irregular_area_share`. An in-sample pass does not license adopting or optimizing against R5; independent labelled data and a clean accepted oblique/curved control exercising its trigger are still required.

Budget: one R0/R3 confirmation replay of #19 (all 13 inputs, zero shift, triple repeat); one R5 candidate (same inputs at both shifts, holdouts unshifted, triple repeat) only after confirmation and the same #19 localization gate; no retunes; stop at first complete verdict or 10 min of measurement, up to three distinct harness-mechanics repairs recorded separately. R5 changes only `bad` membership: exempt a face only when flat by R3's existing `flat_cos`, exactly four vertices, and each corner lies within 1° inclusive of 45°, 90° or 135° (nondegenerate multiples of 45°; 0°/180° are not chamfers). Global irregular area is unchanged. Clean control: unchanged #14 rectangle and reset; added acceptance witness for an aligned horizontal eligible quad, refusal for 1° boundary exceedance, a triangle, a 180° corner and non-horizontal orientation. Injected: unchanged #14 skew. Not measured: new native readbacks, body cores, delivery QA or source-design confirmation of v007.

Replay: `../../.venv/Scripts/python.exe docs/research/autoresearch-body-mesh-chamfer-harness/replay.py C:/x/ar15/r1/tmp <new-receipt.json>`; the script loads only the exact pinned #19 harness and applies an exact-anchor research splice. Receipt must record source/candidate SHA-256 and the full result, not just an aggregate.

Forbidden: changing thresholds, zones, weights, inputs, delivered models or packages, production code, deselecting tests, touching another card's files. Ownership exclusions: readiness `2026-11-21_0249.json`: #1315/#1622/#1738 cold Ground, #1748/#1751 cold entry/skeleton, #1722 stage 2, #1649 atlas, #1609/#1627 KPP1, #1736/#1742 builder/causes, #1615 suite. Continue quality calibration rather than switching to timing.

## Round log — R5 rejected

**Итог.** R5 прошёл порог разделения на размеченных парах (минимальный отрыв **0,718** при пороге **0,500**), но почти не снял штраф с принятого 63B v007: **4,293 → 4,158** балла при допустимых **0,500**. Не внедрять. После исключения максимум локальной доли снизился лишь с 0,620771 до 0,601876; какие именно грани удерживают максимум, в этом раунде не измеряли.

Contract `a6498fd8`, measured replay `19f9742e`; only one candidate, no retunes or measurement retries. All 13 R0/R3 confirmation rows matched #17. Both R5 shifts matched exactly, and all paired spreads were 0.000. R0 minimum 0.427; R3 and R5 minima 0.718, although the weakest pair shifts from 63C (R0) to KPP1 (R3/R5). Holdout drops: 63A v005 and G22 k2 v002r1 each 0.000. These accepted-only holdouts do not show independent defect discrimination.

| Accepted minus rejected | R5 margin (both shifts) | Paired spread |
|---|---:|---:|
| 63B v007 / v001 | 3.531 | 0.000 |
| 63B v007 / v002 | 3.545 | 0.000 |
| 63B v007 / v003 | 3.536 | 0.000 |
| 63B v007 / v004 | 3.529 | 0.000 |
| 63B v007 / v005 | 3.558 | 0.000 |
| 63B v007 / v006 | 2.852 | 0.000 |
| 63C v002 / v001 | 3.357 | 0.000 |
| KPP1 v003 rest / corners | 0.718 | 0.000 |
| G22 k1 v003 / v002 | 1.028 | 0.000 |

Receipt: [`r20.json`](autoresearch-body-mesh-chamfer-harness/r20.json), SHA-256 `ab9ac3034ac2777aa05d7ddbe445ab706248f2596887ded7b78c90ff4009ca15`. R5 generated scorer SHA-256 `0e2ff061dc8e9c23737ceaa2926a74846fb0786d5298801e9ffebaefef6bf095`, including the call to the predicate supplied by the replay (`3e56e1db54a82c260d9fec9e52ceba5cc0196fa4b9f3ddeb7cbcd71371838b3a`). Fixture hashes and flags are in the receipt. The existing native dumps are required for replay; the branch publishes the replay code and full numerical evidence, not the meshes.

- Clean: #14 rectangle/reset, the six predicate checks (`--witness`, RED `aligned_quad` with no exception → GREEN 6/6), canonical report parity, frozen hashes. Affected `tests/qa/test_mesh_quality_score_1616.py`: 291 passed. `repo_guards: GREEN`: 542 passed, 1 warning.
- Injected: #14 skew witness passed with R3 and R5.
- Not measured: fresh native readback, independent labelled rejected/accepted pair, triggered clean curved/oblique control, body builders, delivery QA or design-source confirmation of v007. Full suite not run.

Next: localize R5's surviving maximum on accepted 63B v007 and compare its face IDs, angle ranges and element ownership with design contours. Freeze an independently labelled pair and a clean control that actually triggers the penalty before proposing another exception. No changes to production scoring or models.
