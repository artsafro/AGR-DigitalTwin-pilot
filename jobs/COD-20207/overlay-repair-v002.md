# COD 20207 overlay repair and curb-joint decision (#420)

Status: **partial; model joint policy requires approval; no delivery acceptance**.
Earlier footprint, covering, flat datum and method-C decisions remain CLOSED.
The GEOS overlay blocker in `build-attempt-v001.md` is resolved. This is not a
request for permission to repair pipeline code.

## Verified repair

`ground_cake.plan_layers(normalize_clips=True)` makes clipped results valid,
extracts polygon constituents, discards pieces below 1e-6 m2 and snap-rounds
with the existing 1e-6 m GRID before overlay. Empty/non-area/tiny dispositions
name their covering and stage. Configured-site runs enable this; legacy runs
leave it disabled to preserve their accepted ordering and coordinates.

- Synthetic mixed-dimensional clip RED: **1 failed**, exit 1; test-first `60eddee`.
- Synthetic clip plus existing configured-site tests (including actual COD copy):
  **16 passed**, exit 0. Previously failing real COD overlay now succeeds.
- Legacy affected tests: **90 passed**, exit 0.
- Combined focused selection: **114 passed**, exit 0 (`tmp/cod-focused-v002.log`).
- Final curb tests after nonnegative-trim/report-doc adjustment: **7 passed**, exit 0.
- Read-only `uv run python tmp/cod_legacy_parity.py`: exit 0, **1/1** complete
  ordered synthetic legacy mesh JSON and plan report byte-identical to pre-repair
  module `9c3a67a`; mesh JSON SHA-256
  `6c33802ea4f60cf9f9634720b73325a6849b26a01c266fe5c1ed7994769ab399`.
  This is NOT an actual Vatutino FBX/master replay; that remains required.

Focused command family: `uv run pytest -q <test files> -p no:cacheprovider
--basetemp=C:/x/t_3e9518e5-<run>` (no full suite). Selection: new clip/joint
regressions, site settings, ground details/cake/cleanup/review_r1/review_r2,
Vatutino parts, gap exceptions, COD config. No full-suite/eval receipt claimed.

## Real builds and isolation of the next finding

Common command: `uv run python jobs/VATUTINO-SITE/build_ground.py
C:/x/ground-cod-22/intake-v001/cod_ground_inputs.json
--site-settings jobs/COD-20207/build-settings.json --out <version>`.
Input SHA-256 stays `5438c651b30a3b1f91a8f8f0d35d0acc9942cd1c9eccc313fc2b2f7201fc3700`.
Settings SHA-256 stays `107bd4f536b381c074bda82f1c83e848aab5b6a4ea53c5005075c0436addc32b`.

1. `C:/x/ground-cod-22/ground-v003`, default 1 mm snap: **exit 1**, 10/11
   geometry gates. V004 finds 32 pairs (16 float64 + 16 float32): surface and
   curb pairs. No master JSON written. All other gates pass.
2. Read-only instrumented diagnostic `tmp/cod_geometry_diagnostic.py` retained
   stage measurements in `tmp/cod-stages.log` / `tmp/cod-geometry-stages.log`:
   surface cleanup changes 0 -> 20 pairs; combined curb solids already have 12
   pairs. These diagnostics are not failed repair attempts or passing builds.
3. `C:/x/ground-cod-22/ground-v006`, **`--snap 0.003`**, same value as Vatutino
   v014: **exit 1**, 10/11 gates. Surface-weld pairs disappear; only 12 curb
   pairs remain (6 per representation), xView **6** face pairs, 0 vertex pairs.
   No master JSON written. No checker/threshold was relaxed.

## Exact model question: two mixed-section curb junctions

Read-only `uv run python tmp/cod_curbs_overlap.py`: exit 0.
Drive centreline length **293.54458970733845 m**, garden **92.12016678552924 m**.
There is no exactly duplicated centreline (intersection length 0 m).
After approved section widths 150/80 mm are applied, their footprints intersect:
**0.002974243244639959 m2** in total before Ground-surface clipping. Principal
source pairs inside the boundary:

| Drive handle | Garden handle | Overlap m2 | WCS XY bounds, m |
|---|---|---:|---|
| 5252CE | 527511 | 0.0002793473137050432 | 6642.700525,15434.694232 .. 6642.723559,15434.719451 |
| 527BBC | 527511 | 0.002670038935531794 | 6669.056360,15435.644918 .. 6669.130030,15435.684443 |

Both solids have the common +18 mm bottom, hence real coplanar bottom overlap.
Choosing which section continues through the junction and whether it has a gap
is a model decision, not a GEOS repair. Source zoom (blue drive / orange garden /
red overlap): **`C:/x/ground-cod-22/curb-joints-source-v001.png`**. The image
shows the source footprints, NOT an approved model or a proposed crop hidden as source.

**Question for Artem:** approve continuous 150 mm drive curb with the garden
curb shortened to a **6 mm joint**, or specify a different joint (e.g. touching
joined solid / other section authority)? Recommendation: the 6 mm joint, preserving
both prescribed section heights and avoiding duplicated coplanar bottoms.

## Explicitly unapproved diagnostic candidate

A tests-first optional primitive `build_details(..., separate_curbs=True)`
implements the recommended taller-continuous / shorter-section 6 mm joint;
`654347e` records **1 RED** before this flag existed, then the synthetic mixed
curb regression and associated tests are GREEN. Default remains **False**.
**The committed build_ground.py does NOT enable this option**, even for configured
sites. User approval must be represented explicitly before production wiring.

During investigation only, a temporary builder invocation enabled the proposed
primitive with `--snap 0.003 --out C:/x/ground-cod-22/ground-v007`:
**exit 0**, **11/11** geometry gates, xView **0 vertex / 0 face pairs**.
The temporary caller edit was removed. This is feasibility evidence for the
question, NOT a deliverable or authorization. Do not publish these candidate
masters or claim full acceptance. Proposed role-union garden trim **0.004442854181313294 m2**;
per-entity rows label its role-union scope (do not sum repeated rows).

Candidate-only numbers: both profiles **5852 total / 2514 surface triangles**;
plot **5101.59 m2**, approved footprint **1670.09 m2**; NPM surface cap 50000,
master cap 150000, VPM site-area cap 1650000. These are pre-FBX master counts.
No D150 exception; flat datum, offsets and 5–20 mm gates stay unchanged.

## Receipt hashes

| Receipt | SHA-256 |
|---|---|
| tmp/clip-red.log | a647b2366b49ed31d8ae48d93fa5b4b17779d0fd18d82e86e81ef9d2694bb374 |
| tmp/clip-green.log | e371faf0278b3c209b5cdaec38ac4598e12e96fca22bebae473f1679b2169eab |
| tmp/curb-red.log | e92645b15108db2660c99d4a705961ccce9b7452a2b14c2589ff6ceb8c94b280 |
| tmp/cod-focused-v002.log | b27b3d73cb0ab9400e2bb91ef34db6c29a01341bcdfb87284b0ade560117745c |
| tmp/cod-build-v003.log | 43a4bbea2ff458fe6762ca252865da9d05b9aea6b754fe8006fee7532638295e |
| tmp/cod-build-v006.log | 37fab07f41b2c05b34d874028ab9b2979178e2e959ac91b56a8bd570054010fc |
| tmp/cod-build-v007.log | 63c7250686c8b8c8bd7d0770cb0b7c30ba2ff7ad4a4c1d0eb072c1629e84eae4 |
| ground-v007/ground_report.json | 894bdb47f0660c4b46d257c7424e3ce92a31d98bcd89a0ed963d5dd43f0fcfd0 |
| ground-v007/ground_master_npm.json | 18f6f06343e6c424ca90e6afbe65b9de0089f8f7cf8ddacc0c23840b9ea1da83 |
| ground-v007/ground_master_vpm.json | 5d89fc885eaed34715147dc6a4515c1ca9c6f92e66d58b756ac3b4c2277f065e |
| curb-joints-source-v001.png | cf5fbcd80b89dedbfb0f3acc7221fc18b355f09c440f8a2a8a308e4909154b23 |

## Handoff / remaining acceptance

Resolve only the joint policy above; do not reopen flatness/footprint choices.
Then wire explicit approved policy, rerun into a new versioned output, finish real
Vatutino parity, FBX export/readback, original-reference material/texture transfer,
UCX, independent xView, flatness, both comparison tables, versioned review publication,
full suite through suite_slot.py, eval receipts and hostile self-review before PR.
No FBX, UCX, PR or pending.json was produced in this run. No DCC process launched;
all diagnostics/tests were foreground and finished. Existing defaults never bypass
the V004 failure. Optional candidate functionality is not an accepted design.
