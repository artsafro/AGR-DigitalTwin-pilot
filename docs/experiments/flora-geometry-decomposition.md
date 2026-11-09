# Flora geometry-role decomposition (#369)

## Question and verdict

Can an offline geometry-aware decomposition remove the unknown-role bottleneck in the Flora
texture diagnosis without assigning roles from UV placement or texture colour?

- **Adopt, diagnostic scope only:** enumerate UV charts across the same geometry edge when both
  endpoint UV coordinates and material ID are equal, even if map indices differ. Do not weld
  coordinates, close genuine seams or modify any asset.
- **Maybe:** manifold/normal-based card and branch role candidates. This removes the recorded
  unknown geometry roles but does not establish semantic accuracy or calibrated source acceptance.
  Keep behind the job's `geometry_parts: true` flag.

## Setup and baseline

Inputs are the already extracted 99 originals: Union 68 + FLORIO 31 from
`inventory-all-v005.json`, exclusively on task-owned copies. No DCC ran in this continuation.
No production code or published maps/scenes were changed. The source/library UV hashes remain
identical as measured earlier in the main report.

Baseline = `sprite_coverage.uv_components` plus the existing connected-element `island_role`.
Prototype = `tools/flora/geometry_parts.py`, then the existing native-pixel metric implementation.
The benchmark uses exactly the same source records, includes exact face accounting, runs each
method three times in one process and stores all per-object role counts. This measures topology
and role enumeration, not bitmap decoding, rendering or full-sweep runtime.

```bash
uv run python experiments/flora-texture-diagnosis/benchmark_geometry.py \
  --job tmp/geometry-job-v007.json \
  --output <fresh geometry-benchmark.json>
uv run python tools/flora/compare_sprite_diagnostics.py \
  --job tmp/geometry-job-v007.json \
  --output <fresh review directory>
uv run python experiments/flora-texture-diagnosis/source_crop_witness.py \
  --job tmp/geometry-job-v007.json \
  --output <fresh original-only witness.png>
```

`tmp/geometry-job-v007.json` is the preceding annotated job with `geometry_parts: true`.
The small benchmark receipt, including the inventory hash, is
[`geometry-benchmark-v003.json`](../../experiments/flora-texture-diagnosis/geometry-benchmark-v003.json).

| Same 99 originals | Baseline | Prototype |
|---|---:|---:|
| Runtime samples, seconds | 1.086303 / 0.974928 / 1.229105 | 2.454621 / 2.352815 / 2.372741 |
| Median, seconds | 1.086303 | 2.372741 |
| UV index components / edge-continuous charts | 27,947 | 17,332 |
| Unknown geometric chart roles | 16,323 | 0 |
| Original records with exact face accounting | 99/99 | 99/99 |
| Source calibration passed | No | **No** |
| Asset coordinate deviation introduced, mm | 0 (read-only) | 0 (read-only) |

The fair benchmark is **2.18424× slower**, not a speedup. An earlier exploratory timing included
costly witness bookkeeping and is not used for this comparison. No accuracy percentage is claimed
from an unknown-count reduction.

## Geometry-only evidence

The classifier accepts vertices and triangle faces, not UVs, images, names or profile labels.
Edge-connected manifold disks with a coherent normal cone are flat/bent card candidates.
Disk/annulus surfaces whose radial normals wrap the longest PCA axis are tube/branch candidates,
including tilted branches. Non-wrapping folded disks may instead supply an explicit strict
open-hemisphere normal certificate. Degenerate/nonmanifold/unresolved shapes stay unknown.
These are geometric candidates, not botanical or material ground truth.

The measured source parts are 6,876 flat cards, 1,293 bent cards, 505 folded cards and 244 tubes.
The former Tilia 9-triangle witness is a tapered tube, not an unclassifiable card. Cornus's
80 triangles now yield 11 edge-continuous UV charts with geometric card roles, rather than
65 index components with unknown roles. Exact UV seams remain: two Cornus edges differ by
0.00223826 UV units, and the script does not silently weld them.

The existing NPM full-height flat-card candidate rule is retained separately; it is not inferred
from the NPM catalogue suffix. Full star-arrangement/botanical acceptance is not established.

Code footprint: new geometry helper 155 lines; existing measurement driver 406 -> 425 lines;
benchmark driver 81 lines; original-only witness driver 67 lines. This is more code, not a
simplicity claim. The default measurement path is unchanged.

## Recalibration outcome and a new source witness

The full raw comparison actually ran for **201 records** (99 originals + 99 v003 + 3 light).
All 201 exact face ledgers and all 99 unique route entries were checked independently after
writing the files. No unknown geometry roles remain, but only 25/99 originals have all raw rows
passing. Provisional routes are 24 original-atlas rebind / 1 star / 74 source-validation-required;
**0 definitive routes**. Generic RGB masks remain display candidates, not semantic truth.

A new issue is visible in the original itself, not in bark policy:
`Padus_maackii_VPM`, faces `[182,183,184,185,298,299,300,301]` are one intact 8-triangle foliage chart.
Its original atlas contains two separate branch sprites on the left and bark on the right.
The bottom-left sprite's independently derived opaque bbox is `[488,2403,1803,3845]`.

- Exact geometric sprite coverage: **0.6759422436446174**, below the unchanged 0.80 threshold.
- Island polygon area: 1,357,745.1371401856 px²; sprite bbox: 1,896,230 px².
- Opaque pixels outside the chart at 1-pixel tolerance: **29,353**; neighbouring sprite pixels: 0.
- I opened the original atlas and the annotated witness with `vision_analyze`. It is one branch
  sprite, not a mistaken union of touching sprites. The right-hand branch leaves visibly extend
  outside the red UV boundary. This is not the superseded opaque-density or bark-strip question.

Current evidence:
`C:/x/review/2026-10-20/flora-texture-diagnosis/geometry-diagnostics-v005/index.html` and
`../padus-original-sprite-crop-v002.png`. All six revised species sheets were personally viewed.
The v002 witness is SHA-256-identical to the viewed v001. The portable compact ZIP is
`review-geometry-v005-compact.zip`, 16,237,384 bytes, 15 members, CRC checked.

## Verification and decision needed

Affected tests: **126 passed**. This includes synthetic bent cards, folded sheets, tilted tubes,
12 seeded rotation/translation/scale + winding probes, material seams, disconnected coincident
cards, nonmanifold/degenerate geometry, empty/NaN/inf input, exact face accounting and fresh-process
CLI rejection of input/output aliases including hardlinks. RED was observed and committed as
`20bfb85` before the helper was implemented; the flagged measurement integration also failed
with 2 charts instead of 1 before implementation.

Protected input hashes: **236/236 unchanged**, receipt `source-integrity-v003.json`.
Regression evals: 0 passed / 0 failed / 10 not measured, exit 2 (no Claude transcript),
`tmp/evals/flora-geometry-v003/report.json`. The preceding full-suite receipt remains in the
main report; it is not rerun in this rework. CI: not run (billing lock).

**The card is not complete.** The requirement that all originals pass calibration is now in
conflict with a visually confirmed partial original sprite, even after geometry roles were
resolved. Do not relax 0.80 or certify the source by changing its label. A decision is needed:
may known source crops/non-star NPM constructions be reported as source limitations/defects and
routed explicitly, while calibrating the metric on independent valid controls, or is a specific
source exception/other acceptance definition required? Semantic mask validation and final 99
repair routes remain open, not out of scope. No fix issue or asset modification was created.

## Proposed follow-up for the adopted diagnostic method

**Title:** Integrate edge-continuous Flora UV chart diagnostics.

**Scope:** reuse geometry-edge + material + exact endpoint-UV continuity in the diagnostic
inventory, retain both legacy and edge-chart counts, preserve all genuine seams and exact face
ledgers, and add duplicate-index/disconnected-card regressions. Do not rewrite UVs or change
production acceptance until the source-calibration decision is settled. This is a proposal,
not a created issue/card or permission to fix published assets.
