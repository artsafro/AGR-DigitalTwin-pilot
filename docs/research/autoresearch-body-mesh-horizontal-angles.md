# Standing #28 — extreme angles on horizontal body faces (OBSERVE)

## Frozen contract

Continue standing #27 (`bd0194a8e876a2602eafc4c98e686811f04c4a0d`), not the rejected R3 triangle penalty. Test whether an existing mesh-quality corner-angle primitive identifies poorly laid-out horizontal faces regardless of polygon degree. A future builder change could remove nearly collinear or needle corners; this round only tests whether that feature is a valid calibration signal. Do not change the scorer or a builder until known rejections rank worse. No speed fallback: quality data are available. Readiness 2026-11-21 06:50 and current pilot issues/PRs: do not duplicate builder #1736/PR #1770, KPP1 rebuild #1609, atlas #1649, 63B stage 2 #1722, cold runs #1315/#1608, Ground #1738, or the main-log repair #1772.

**Fixture:** exact 15 inputs, frames, labels and SHA-256 from `FIXTURE` in `docs/research/autoresearch-body-mesh-horizontal-tris-harness/replay.py` at the pinned #27 revision, with reference `r27.json` there. Eight rejected samples (63B v001–v006, 63C v001, KPP1 v003 corner crop), four accepted bodies (63B v007, 63C v002, 63A v005, G22 k2 v002r1), three accepted G22 NPM etalon bands (k1–k3, #1619). Unchanged mixed scopes: etalon is band-limited, the KPP1 sample is a crop, and other body dumps are used as stored. No claim of equal coverage or independent validation.

**Metric:** `M = min(median3(D) for rejected) - max(median3(D) for accepted)`. `D` = Newell area of horizontal faces with at least one corner strictly `<5°` or `>175°` divided by all horizontal face area. Use #27 Newell normal and `|n_z| >= cos(1°)`; use unchanged `_angles` in `tools/qa/mesh_quality_core.py` at `afa6fb2017eab81ec8207efb208df7e7ea8e8ed4` (unsigned smaller angle, repeated adjacent point yields 0°). Include all degrees; skip zero-Newell-area faces as in #27, so collapsed faces alone do not contribute. No clipping or welding. Feature keep threshold `M > 0`, all 15 included. A positive result only nominates the feature for independent calibration, not a score change or a PR for production.

**Budget / stop:** one baseline confirmation (#27, three reads per sample), one candidate feature (strict extreme corner share, three reads per sample), no tuning or replacement candidates. Record each corpus's paired candidate-minus-baseline max–min spread and require zero, as well as exact repeats. Stop after one receipt, parity/provenance failure, or 5 minutes measurement wall time. No dropping samples or tests, relaxing checks or tolerances, editing deliveries, job files or another card's files.

**Replay** (Git root, Python 3.14, reference commit available locally; if needed `git fetch origin research/autoresearch-standing-27`):

```sh
uv run python docs/research/autoresearch-body-mesh-horizontal-angles-harness/replay.py C:/x NEW.json
```

**Clean:** verify baseline receipt equals the pinned #27 receipt, candidate reads all hash-bound inputs (before and after), agrees on triangle counts and horizontal area, and a unit square produces no signal. **Injected:** wrong input SHA-256 must fail the candidate read; split one side of a unit square by adding a collinear vertex, leaving its area unchanged: `D` must go from 0 to 1. **Not measured:** new native readback, face ownership or design intent, fully collapsed faces, recalibrated score, changes to body cores, package QA.
