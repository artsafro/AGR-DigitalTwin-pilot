# Standing #29 — off-grid horizontal quads on body faces (OBSERVE)

## Frozen contract

Continue standing #28 (`b6e0d8839` on `research/autoresearch-standing-28`; next target recorded there and in the
autoresearch backlog). Question: does the share of horizontal quad area whose corners leave the 45° grid (the
48°/132° cap quads of rejected 63C v001, standing #22-#24) separate Artem's rejected bodies from accepted ones?
This round only tests whether the feature is a valid calibration signal. Do not change the scorer, a body core or
a builder. No speed fallback: quality data are available. Readiness 2026-11-21 06:50 and open pilot work are not
duplicated: builder #1736/PR #1770, KPP1 rebuild #1609, atlas #1649, 63B stage 2 #1722, cold runs
#1315/#1608/#1738, skeleton #1748/#1751, main-log repair #1772.

**Fixture (frozen, unchanged from #27/#28):** exact 15 inputs, frames, labels and SHA-256 from `FIXTURE` in
`docs/research/autoresearch-body-mesh-horizontal-tris-harness/replay.py` at #27 revision
`bd0194a8e876a2602eafc4c98e686811f04c4a0d`. Eight rejected (63B v001-v006, 63C v001, KPP1 v003 corner crop), four
accepted bodies (63B v007, 63C v002, 63A v005, G22 k2 v002r1), three accepted G22 NPM etalon bands k1-k3 (#1619).
Mixed scopes stay as in #27: etalon band-limited, KPP1 a crop, other dumps as stored. No claim of equal coverage
or independent validation.

**Metric:** `M = min(median3(Q) over rejected) - max(median3(Q) over accepted)`. `Q` = Newell area of horizontal
faces (#27 Newell normal, `|n_z| >= cos(1°)`, zero-area faces skipped) that have exactly 4 stored corners and at
least one corner angle farther than 1.0° from every one of 45°, 90°, 135° (unchanged `_angles` of
`tools/qa/mesh_quality_core.py` at `afa6fb2017eab81ec8207efb208df7e7ea8e8ed4`), divided by ALL horizontal face area
(all degrees, same denominator as #27/#28). No clipping, welding or re-triangulation. Keep threshold `M > 0` with all
15 included. A positive result only nominates the feature for independent calibration; it is not a score change.
Descriptive only (not a keep criterion, frozen now): count of (rejected, accepted) pairs with rejected `Q` strictly
greater, out of 8 x 7 = 56.

**Budget / stop:** one baseline confirmation (#27 receipt exact, plus #28 `D` recomputed bit-exact per sample),
one candidate feature, three reads per sample. No tuning, no alternative tolerance, no replacement candidate in
this card. Per-sample paired candidate-minus-baseline spread must be 0 and repeats exact. Stop after one receipt,
any parity/provenance failure, or 5 minutes measurement wall time. Forbidden: dropping samples or tests, relaxing
checks or tolerances, editing deliveries, job files or other cards' files.

**Replay** (Git root, Python 3.14; needs commits `bd0194a8` and `b6e0d883` locally:
`git fetch origin research/autoresearch-standing-27 research/autoresearch-standing-28`):

```sh
uv run python docs/research/autoresearch-body-mesh-offgrid-quads-harness/replay.py C:/x NEW.json
```

**Clean:** #27 receipt parity exact; #28 `D` parity exact; every input hash checked before and after the reads;
horizontal area and face counts equal #27; unit square gives `Q=0`; a 45°/135° parallelogram gives `Q=0`.
**Injected:** wrong input SHA-256 must be refused; a 48°/132° rhombus must give `Q=1`; a pentagon with off-grid
corners must give `Q=0` (degree filter). **Not measured:** native DCC readback, face ownership / design intent,
non-quad off-grid faces, collapsed faces, recalibrated score, body-core changes, package QA.

## Round log

**Итог OBSERVE:** признак не прошёл порог. `M = −0,10622445` (−10,62 п. п.; порог > 0). Все шесть принятых
корпусов вне 63B (63C v002, 63A v005, G22 k2 v002r1, эталон G22 к.1–к.3) дают 0 %, все восемь отклонённых —
от 4,94 % до 28,71 %. Срывает только принятый 63B v007 (15,561 %): у 63B косые грани заложены в проекте (скосы
45° и излом 7,1°, #19/#23), и отклонённый v005 (15,558 %) от него этим признаком не отличается. Упорядочено 50 из
56 пар (только для описания). Оценка, ядра, построитель и поставки не менялись. PR нет.

| Corpus | Label | Horizontal quads | Off-grid quads | Q (%) |
|---|---|---:|---:|---:|
| 63B v001 | rejected | 1090 | 160 | 4.94875 |
| 63B v002 | rejected | 1090 | 160 | 4.94875 |
| 63B v003 | rejected | 1090 | 160 | 4.94846 |
| 63B v004 | rejected | 1091 | 160 | 4.93872 |
| 63B v005 | rejected | 1091 | 364 | 15.55766 |
| 63B v006 | rejected | 1910 | 647 | 28.71033 |
| 63C v001 | rejected | 814 | 176 | 20.87950 |
| KPP1 v003 corners | rejected | 18795 | 12501 | 15.28339 |
| 63B v007 | accepted | 2620 | 664 | 15.56116 |
| 63C v002 | accepted | 726 | 0 | 0 |
| 63A v005 | accepted | 864 | 0 | 0 |
| G22 k2 v002r1 | accepted | 882 | 0 | 0 |
| G22 etalon k1 | accepted | 8996 | 0 | 0 |
| G22 etalon k2 | accepted | 3066 | 0 | 0 |
| G22 etalon k3 | accepted | 3337 | 0 | 0 |

- **Sealed:** contract `1c36e6df`; replay `4d53b9f6`, SHA-256
  `5cb25d5ba307762ce62e7b37f7b4c967c7d5e58170cca0b6ac30184254a30827`.
  [Receipt](autoresearch-body-mesh-offgrid-quads-harness/r29.json) SHA-256
  `ccb2fb6159d12efc98691d17f9a8fff0b0345d6e268cdfdef4b29cce979c11f5`. Measurement wall time 9.7 s (one run).
- **Clean:** #27 receipt parity exact (`baseline_M` unchanged); #28 `D` recomputed bit-exact for all 15; input
  hashes before/after; horizontal area and face counts equal #27; three reads, paired spread 0 for every sample;
  unit square `Q=0`, 45°/135° parallelogram `Q=0`.
- **Injected:** wrong input digest refused; 48°/132° rhombus `Q=1`; off-grid pentagon `Q=0` (degree filter).
- **Not measured:** native readback, ownership / design intent, non-quad off-grid faces, collapsed faces,
  recalibrated score, body-core changes, package QA.
- **Would change (OBSERVE):** no generic off-45° penalty — on 63B it measures the design plan, not the defect.
  The grid must come from the object: corner angles of the horizontal quads compared with the angles of the
  project plan contour of the same object (63B: 45° chamfers + 7.1° kink), then re-measure the same 15 bodies.
