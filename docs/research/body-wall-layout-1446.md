# BODY wall-layout pre-show diagnostics (#1446)

`level: standard`. Implementation: [`twinqa.look.part_layout_report`](../../src/twinqa/look.py)
and [`tools/qa/body_layout.py`](../../tools/qa/body_layout.py). The R6 modelling
brief requires this receipt **before each BODY part is shown**, alongside xView
and the other applicable checks. No source/model changes, automatic retopology,
new delivery blocker, or acceptance waiver are introduced.

## Contract and defaults

All thresholds are **orchestrator default, user may change**, not regulation:

- `WALL_NORMAL_Z_MAX = 0.1`: near-vertical faces have `abs(unit normal.z) <= 0.1`.
- `WALL_AXIS_TOL_DEG = 1.0`: an indexed wall edge is diagonal if its inclination
  to XY is strictly between 1 and 89 degrees. Independent of facade azimuth;
  duplicate incidence on two wall faces counts only once.
- `WALL_SLIVER_SHORT_M = 0.05`, `WALL_SLIVER_LONG_M = 0.5`: a wall face is a
  sliver when its shortest side is **< 0.05 m AND** its longest side **> 0.5 m**.
  Exactly 0.05 / 0.5 m is not a sliver under the issue's strict inequalities.
- `WALL_FAN_MIN_TRIANGLES = 3`: count each vertex shared by at least three
  near-vertical triangular polygons, including open fans. Quads/n-gons are NOT
  implicitly triangulated to manufacture fans.

Each part has face ids, indexed edge/vertex ids and metre positions; every face
is accounted in `wall_face_ids` or `skipped_face_ids` (non-wall reason). A part
with no eligible wall faces is `not_measured`, never `clean`. Invalid/empty,
partial, nonfinite or degenerate geometry raises rather than passing. CLI
selection is explicit (`--part`, repeatable); unselected objects are listed with
reasons. Native ids refer to evaluated object-local polygons, not a flattened
multi-object inventory. Native scene readback uses the existing xview adapter;
JSON/NPZ inputs are explicitly labelled recorded evidence, not native freshness.

Wall layout is **report-only [D227]**: `review`/`clean`/`not_measured`, always
`report_only=true`, `blocking=false`. One diagonal between opening corners is
counted but never failed or automatically labelled as approved. `quad_dominance`
keeps its separate existing verdict [D129]; this diagnostic does not weaken it.
Promotion to blocking needs a later user decision after 2–3 accepted jobs run
without false failures. This one retrospective is not that calibration set.
CLI exit 0 means a measured receipt was published, **not** geometry acceptance;
invalid evidence returns 2. Reports/logs are new-only, source hashes are checked
before/after; no input is overwritten or deleted.

## Reproduce

Use original polygon masters before export triangulation; metre coordinates, Z up.
For code callers: `part_layout_report(work_fbx_mesh_rows, 'VPM-OKS')` returns
`parts[].wall_layout` and `parts[].quad_dominance` in the same receipt.

```bash
ROOT='C:/Users/artsafro/Desktop/!3D viz/!А101/63_4BK_vlad/build/gf_parts/gf_body_A'
# Use a fresh report path on every invocation; v001 / v004 / v008e.
uv run python tools/qa/body_layout.py "$ROOT/gf_body_A_v004.blend" --profile VPM-OKS --part K3GF_BodyA_Walls --out NEW-v004.json
```

CLI threshold overrides: `--normal-z-max`, `--axis-tol-deg`, `--sliver-short-m`,
`--sliver-long-m`, `--fan-min-triangles`. Values actually used are in each report.
Existing quad_dominance profile caps are unchanged.

## Real 4bk-k3 measurement

Read-only headless Blender **5.1.2**, factory startup, autoexec disabled through
`dt_ai.core.blender_runner`. Chosen for numerical polygon readback of existing
.blend files; no GUI scene opening, saving, conversion or user acceptance is
needed for this diagnostic. Sources are the issue's three original files.
Native units: METRIC, scale 1.0; active scene `Scene` (see raw receipts for exact
readback). Input SHA-256 is checked again after evaluation. No default was tuned
to match the retrospective.

| Version | Slivers (reference) | Diagonals (reference) | Diagonal deviation | Fan vertices | quad_dominance |
|---|---:|---:|---:|---:|---|
| v001 | 15 (15) | 170 (172) | -1.16% | 0 | false |
| v004 | 4 (4) | 123 (124) | -0.81% | 18 | false |
| v008e | 23 (23) | 122 (125) | -2.40% | 3 | false |

All six sliver/diagonal measurements are within the required ±10%. Reference
counts come from issue #1446 (the cited retrospective Markdown is absent in this
checkout); measured values are actual fresh native readbacks, not synthetic
fixtures. A small diagonal discrepancy is retained rather than changing the
angular default to force an exact match. Fan counts are polygon-topology facts,
not a retro acceptance oracle; v001's visible patterns need not be triangle faces.

Machine summary with source SHA-256, counts, deviations and full-report hashes:
[`body-wall-layout-1446.json`](body-wall-layout-1446.json).
Full per-face/edge/vertex reports and native logs:
`G:/Мой диск/AGR-evidence/1446-body-wall-layout/t_688f3a79-v001/`,
sealed by `SHA256SUMS.txt`. Source .blend files remain outside git.

## Tests

`tests/qa/test_wall_layout.py`: synthetic BODY A fan/sliver, orthogonal loops,
single allowed diagonal, unique edge incidence, arbitrary facade azimuth,
threshold boundaries, invalid/empty/partial/nonfinite geometry, independent
quad verdicts and per-part identity. `tests/qa/test_body_layout_cli.py`: fresh
process, NPZ/native adapter units, aliases/hardlinks, duplicate/unknown selection,
input mutation, stale report refusal, competing writer and foreign partials.
Historical RED commit: `2e06da84` (missing `part_layout_report`); CLI RED also
observed before adding its module. Full suite is deferred to merge batch (rule 68).
