# Master mesh quality score by the OKS split rule [D336] (#1616)

Status: metric (r3, after review r2) + calibration + three OBSERVE loop runs. Nothing retained; no
delivered package or master touched. Evidence (rule 57): `G:/Мой диск/AGR-evidence/1616-mesh-quality/`
+ `SHA256SUMS.txt` (r1: `calibration/`, `loop-r1/`, `sheets/`, `psu275-conversion/`; r2: `calibration-r2/`,
`loop-r2/`, `sheets-r2/`; r3: `calibration-r3/`, `loop-r3/`, `sheets-r3/`).

## Tool

```
uv run python tools/qa/mesh_quality_score.py MASTER.(blend|fbx|obj|json) --out NEW.json [--zone X0,Y0,X1,Y1 ...] [--exclude-zone X0,Y0,X1,Y1 ...] [--param key=value]
```

Blender 5.1.2 headless dump (`tools/blender/mesh_quality_dump.py`) -> stdlib core
(`tools/qa/mesh_quality_core.py`). Components, thresholds and their reasons are in the core docstring:
`tri_share`, `ngon_share` (error, status `fail`), `sliver_share` (tri min angle < 10 deg, quad min
corner < 30 deg), `pole_share` (flat interior vertices with valence != 4), `one_mesh_share` (body element
faces / non-glass faces, penalty above 0.5), `weld_share` (concave creases > 30 deg inside the body
element), `long_share` (side > 3.9 m), and since r2:
- `irregular_area_share` - AREA share of faces with a corner > 15 deg off 90 (skewed quads, triangles):
  the irregular wire Artem rejected on the corners.
- `open_seam_share` - open seams. Exact: boundary edges coincident (0.1 mm grid) inside one object are
  merged, so the parts are measured as one welded element. Near (r3, review r2 P1-1): a boundary edge
  running along a boundary edge of ANOTHER element (direction within 5 deg, <= 2 mm apart, shared
  stretch > min(1 cm, half the shorter edge)) - a part moved a fraction of a millimetre off its hole, or
  cut at other heights (T-junctions). In-object near pairs join the elements and count as the welded
  edge they replace. Un-welding alone can only lower the score. Glass objects take no part (a pane fills
  its frame opening by regulation).
- Window reveals vs seams: the reveal is body surface, so a frame inset into it has no body boundary
  edge within the gap. Measured on PSU275: 0 near pairs at 2 mm and at 5 mm
  (`calibration-r3/psu275-main-gap0.005.json`); the first 561 pairs appear at 10 mm, all between two
  inset elements, none on a body edge (score 99.507, `psu275-main-gap0.01.json`).

score = 100 * (1 - weighted mean penalty); it ranks, never accepts.

## Calibration r3 (corners = plan boxes around the SW/NW posts of the #1563 sheet)

Rerun of every row through the CLI on the real inputs with the r3 core (`calibration-r3/`). The near-seam
pass finds no pair on any row, so every score equals r2:
Corner zones `-17.5,-8.2,-12.5,-3.2` and `-17.5,3.5,-12.5,8.5`; `kpp1-quad-v003-rest` = the same master
with those boxes excluded (`--exclude-zone`).

| Master | Acceptance | Score | irregular area | sliver | pole | one-mesh (body share) | weld | open seam | elements | faces | input sha256 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| KPP1 quad-v002 whole | none (superseded) | 77.341 | 0.2238 | 0.2326 | 0.1689 | 0.9993 | 0.0933 | 0 | 45 | 62 091 | fb566ff5e10e |
| KPP1 quad-v002 SW/NW corners | none (before) | 76.423 | 0.2966 | 0.2243 | 0.1695 | 0.9977 | 0.0985 | 0 | 8 | 6 197 | fb566ff5e10e |
| KPP1 quad-v003 whole | partial (all except corners) | 77.346 | 0.2232 | 0.2332 | 0.1695 | 0.9992 | 0.0925 | 0 | 45 | 61 717 | b54c5f72cca6 |
| **KPP1 quad-v003 SW/NW corners** | **rejected** | **76.684** | 0.2830 | 0.2210 | 0.1744 | 0.9976 | 0.0915 | 0 | 8 | 5 823 | b54c5f72cca6 |
| KPP1 quad-v003 minus corners | accepted («Принимаю все кроме углов») | 77.402 | 0.2184 | 0.2344 | 0.1683 | 0.9993 | 0.0924 | 0 | 42 | 55 894 | b54c5f72cca6 |
| PSU275 SM_Psu_1_Main + MainGlass | accepted 2026-10-07 | 99.593 | 0.0042 | 0.0071 | 0.0022 | 0.3720 | 0.0322 | 0 | 2 955 | 39 276 | 41200c110342 |

Stated margin: the rejected corners must score at least **0.5 points** below every accepted row
(`calibration.json` `margin_points`, test `test_committed_calibration_ranks_rejected_corners_below_accepted`).
Observed: 0.718 below v003-rest, 22.9 below PSU275.

Reading:
- The corners/rest separation comes from `irregular_area_share` (0.283 vs 0.218, +30 %): the corners carry
  large skewed quads on the flat walls next to the posts (visible on the #1563 sheet). Count-based
  components do not separate them (slivers 0.221 vs 0.234 even favour the corners): the whole KPP1 quad
  master is one welded mesh with triangle-to-quad fans, the corners only have more of it per square metre.
- Sensitivity of the margin to the threshold (`--param irregular_deg=`): 10 deg 0.743, 15 deg 0.718,
  20 deg 0.695, 30 deg 0.518 points - positive over the whole range, so the ranking does not hang on the
  chosen 15 deg. The margin is small in points because the rest of KPP1 shares most defects; it is not a
  measure of how bad the corners look.
- The v002 corners (76.423) also score below v003-rest.
- PSU275 is available only as the editable `2PSU275_VPM_NPM_quads_v001.max` (#1420 evidence, sha256
  `376ad615...`). It was converted read-only by 3ds Max 2026 batch (`3dsmaxbatch`, no live Max, source
  hash unchanged) to a non-triangulated FBX of `SM_Psu_1_Main` + `SM_Psu_1_MainGlass` (36 556 + 2 720
  quads = the accepted clean-up v009 counts). Native cross-check of elements: Max `polyop` gives Main 607 /
  Glass 2 446 elements; the Blender-read FBX gives 509 / 2 446 (Max elements are edge-connected, the score
  uses vertex connectivity: parts touching at one vertex count as one element here).
- r1 numbers (before `irregular_area_share` / `open_seam_share`): `calibration/` in evidence; v003 corners
  73.017 were above v003 whole 72.749 - review r1 P1-1.

## OBSERVE loop

`tools/qa/mesh_quality_observe.py` measures the v003 corners, runs the candidate body `after` hook
`tools/blender/split_welded_parts_candidate.py` (split concave creases, positions unchanged) at
80/60/45/30 deg on a copy, re-measures, and logs keep/discard. Limitation: KPP1 has no `skeleton.json`,
so the loop post-processes a copy of the finished master with the hook script instead of rebuilding
through the skeleton; the "would change: body-stage after hook" line is what it would propose, not a
measured skeleton rebuild. The logs `observe-log-r1.jsonl` / `observe-log-r2.jsonl` are copies
(kept under docs/research, not jobs/: job folders hold deliveries only); the hashed originals are on G:.

### loop-r3 (metric r3, 2026-11-17) - log `observe-log-r3.jsonl`

Same rounds, same results as loop-r2: baseline 76.684 kept; split 80/60/45/30 deg 75.499 / 75.485 /
75.453 / 75.401, all discarded (split edges 10 635 / 10 729 / 10 945 / 11 359, as in r2). The hook keeps
positions, so its seams are exact and the near pass adds nothing. Wire sheet
`sheets-r3/kpp1-v003-corners-observe-r3-wire.png` (sha256 `d7053be03f3d968f...`, before = r2 baseline
views, after = round 4); the r3 after renders are pixel-identical to the r2 ones (PIL difference bbox
None for all 4 views).

### loop-r2 (metric r2, 2026-11-17) - log `observe-log-r2.jsonl`

| Round | Candidate | Score | Kept | irregular area | one-mesh | weld | open seam | split edges |
|---|---|---|---|---|---|---|---|---|
| 0 | baseline v003 corners | 76.684 | incumbent | 0.2830 | 0.9976 | 0.0915 | 0 | - |
| 1 | split 80 deg | 75.499 | discard | 0.2830 | 0.9976 | 0.0915 | 0.0829 | 10 635 |
| 2 | split 60 deg | 75.485 | discard | 0.2830 | 0.9976 | 0.0915 | 0.0840 | 10 729 |
| 3 | split 45 deg | 75.453 | discard | 0.2830 | 0.9976 | 0.0915 | 0.0861 | 10 945 |
| 4 | split 30 deg | 75.401 | discard | 0.2830 | 0.9976 | 0.0915 | 0.0898 | 11 359 |

Every non-seam component of rounds 1-4 equals the baseline: the seam-joined parts are measured as the
welded body they were, and only the open seams cost. Wire sheet `sheets-r2/kpp1-v003-corners-observe-r2-wire.png`
(sha256 `eaf643cf...`): before and after are visually identical, which the score now agrees with.
Would change: nothing; the loop retains no candidate. The real fix stays the #1609 rebuild of the corners.

### loop-r1 (metric r1) - log `observe-log-r1.jsonl`

Same candidates scored 87.3-89.5 (+14 to +16.5) on an unchanged wire (`sheets/kpp1-v003-corners-observe-wire.png`):
the r1 metric rewarded un-welding alone. Fixed in r2 by `open_seam_share` (review r1 P1-2).

## Reproduce

```
uv run python tools/qa/mesh_quality_score.py master-quad-v003.blend --out v003-corners.json --zone=-17.5,-8.2,-12.5,-3.2 --zone=-17.5,3.5,-12.5,8.5
uv run python tools/qa/mesh_quality_score.py master-quad-v003.blend --out v003-rest.json --exclude-zone=-17.5,-8.2,-12.5,-3.2 --exclude-zone=-17.5,3.5,-12.5,8.5
uv run python tools/qa/mesh_quality_observe.py master-quad-v003.blend C:/x/ev_1616/<new-run-dir>
blender -b --factory-startup --python jobs/KPP1/quad-1372/render_before_after.py -- <fbx> <grey.png> <out> after corners
```
