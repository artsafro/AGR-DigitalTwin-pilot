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

(filled after the single measurement)
