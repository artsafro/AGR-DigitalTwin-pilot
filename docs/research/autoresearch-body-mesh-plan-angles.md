# Standing #30 — source-derived angle grid for 63B (OBSERVE)

## Frozen contract

Continue standing #29 (`8aa66dc6a402e394f357d1c10cc5c6732d86a6a1`). At fixed 45° increments accepted 63B v007 was the only accepted sample with nonzero Q. Hypothesis: adding source-derived plan angles for 63B alone makes the worst accepted/rejected gap strictly positive. This tests calibration, not a better body builder or a new score. Readiness 2026-11-21 06:50: do not duplicate #1736/#1742 (builder/causes), #1722 (stage 2), #1649 (atlas), #1609 (KPP1), #1315/#1622/#1738 (cold runs), #1748/#1751 (skeleton), #1772 (main repair). Speed not considered while quality calibration has a runnable target.

**Fixture:** identical 15 inputs, labels, frames and SHA-256 from #27 `FIXTURE` (`bd0194a8e876a2602eafc4c98e686811f04c4a0d`), as reused by #29. Eight rejected including 63B v001–v006, 63C v001 and KPP1 corner crop; seven accepted including the band-limited #1619 G22 k1–k3 NPM etalons. Mixed coverage unchanged. The project-side inputs for 63B only are `tests/fixtures/poly63b/floor_A.json` and `floor_B.json` from `ed4c418e087391cd453182c985a7a8b38a4fb601`: source-crop-derived stack floor contours independent of scoring dumps, not pristine approved CAD or proof of face attribution. No geometry is inferred for other families.

**Variant and metric:** reuse #29 `read_quads`, `_angles` and Newell frame unchanged (horizontal means |n_z| ≥ cos 1°). Compute the unsigned smaller angle between the two incident plan segments at each vertex of each closed `rings[].xy`. Exclude values ≤1° or ≥179°. For 63B only, add the resulting angles to the fixed 45°/90°/135° grid as whole-building allowances (no location filter, no rounding); for every other sample keep #29 exactly. Flag a horizontal quad only when some corner is farther than 1° from all allowed angles. Q remains flagged quad area / all horizontal area. One number `M = min(rejected median3 Q) − max(accepted median3 Q)`. Require `M > 0` also on each pose to nominate the feature for a separate independent calibration. No keep or score rollout here.

**Frozen series / budget:** one exact baseline confirmation against the complete #29 receipt; one variant only, zero retunes. Three paired poses for every sample: identity, Z rotation +17° then translation (+3,−4,+7) m, and Z rotation −31° then translation (−9,+6,−2) m. Plan angles are rigid-motion invariant, so the plan is evaluated once. Both variants must preserve face count and their own flagged face counts across poses, with max within-variant Q deviation ≤ 1e-9 and paired delta spread ≤ 2e-9 (absolute shares). Candidate Q must not increase beyond 1e-9 on 63B; no change outside 63B per pose. Positive trigger witness: synthetic 48° rhombus scored with a 48°/132° rhombus plan, Q 1→0; injected unmatched 72° rhombus must stay 1→1. Real affected accepted control: 63B v007 must decrease by >1e-9 on each pose, otherwise separately report the missing real trigger (a negative M still refutes separation). Real rejected sentinel 63C v001 must stay flagged as in #29; synthetic square 0→0. No stability claim from repeated reads alone.

**Time/stop:** cap measurement at 180 s or remaining card time, whichever is smaller. Time one complete identity paired pass over all 15 (after confirmation) and reserve 3× that duration for the two remaining poses. If the remaining budget cannot fit that reserve, return inconclusive; do not shorten. Stop at first full receipt, parity failure or timeout. Up to three distinct harness-only repairs, no changed sampling or hypothesis. No weakening checks, dropping tests or inputs, editing delivery/job files, production scorer or builders, or touching other cards’ files.

**Replay (same workstation with C:/x inputs; off-host replay limited):**

```sh
git fetch origin research/autoresearch-standing-27 research/autoresearch-standing-28 research/autoresearch-standing-29
uv run python docs/research/autoresearch-body-mesh-plan-angles-harness/replay.py C:/x NEW.json
```

Clean: exact #29 full receipt, both immutable contour blobs, area/topology parity, unaffected samples, square. Injected: matched/unmatched rhombi. Not measured: raw source CAD verification, independent labels, face/plan ownership, native rebuild/readback, `mesh_quality_score` change and package QA.
