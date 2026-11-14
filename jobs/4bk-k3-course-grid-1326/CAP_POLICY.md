# Complete-edge chart checkpoint — #1326, v004

Status: **needs one combined main-cap/base seam-scope answer**. `pilot_passed=false`.
No production UVs, maps, geometry, source scenes or Max sessions have been changed.
This is not a tile overflow or a textured pilot acceptance result.

## Settled answers — do not reopen

- 771 existing ID1 faces (705 walls + 66 stair); 1,244 other-finish faces protected.
- Stair thin-return/underside existing-edge breaks: `seam-approval.json`.
- Main ring horizontal-phase breaks 0/54 and 1344/1398: **approved 2026-11-14**,
  exact answer in `main-wall-seam-approval.json`. Keep vertical courses continuous.
- Source Bricks1 and the 38-course / 3.15 m contract remain unchanged [D275].
- Separate versioned Max 2026 copy only, open only after Artem says **«открой»**.
  Existing source-only quads copy remains at
  `G:/Мой диск/AGR-evidence/1326-stylobate-course-grid/intake-v001/3k_intake_v001.max`.

## One combined scope question

**May the listed existing main-wall cap/base edges be UV pattern breaks, retaining
all 771 brick faces, the two approved vertical ring terminations and continuous
courses on the remaining main-wall joins, without new geometry cuts?**

Recommended: **yes to the explicit proposal in `cap-audit-v004.json`**:

1. Separate the **65 horizontal ID1 top-cap faces** into their own rigid charts;
   the proposal enumerates **195 existing shared cap boundary edges**, including
   cap-to-cap edges, not just vertical-wall boundaries. This is a sufficient
   conservative proposal, **not a claim that every one is mathematically necessary**.
2. Permit **horizontal-phase-only** termination at the **13 existing low plinth/base
   edges** below. Their endpoint heights are -0.355711 to +0.150004 m; keep their
   vertical course phase. These are conditional fixed-chart cycle witnesses, not
   a theorem that every alternative chart needs these same edges.
3. The approved outer vertical panel joint continues through **7 further collinear
   source-edge segments** below 0/54. These are separately enumerated in the proposal,
   not seven new joint locations. No continuation has been applied or silently approved.

All rows name `K3_StylobateWalls.001`. Indices are **0-based source indices**.
The complete cap list, endpoint XYZ, 13 base edges and continuation segments are in
`cap-audit-v004.json` and the immutable full evidence, not inferred from a picture.
If only a narrower list is acceptable, Artem should name the permitted subset;
the tool must not invent permission. Existing stair/ring answers remain in force.

| Base adjacent source faces | Existing source edge vertices |
|---|---|
| 925 / 926 | 819 / 1001 |
| 933 / 934 | 827 / 1009 |
| 948 / 1499 | 834 / 1016 |
| 1026 / 1500 | 912 / 1094 |
| 1027 / 1028 | 921 / 1103 |
| 1037 / 1038 | 931 / 1113 |
| 1045 / 1046 | 939 / 1121 |
| 1053 / 1054 | 947 / 1129 |
| 1061 / 1062 | 955 / 1137 |
| 1074 / 1075 | 968 / 1150 |
| 1084 / 1085 | 978 / 1160 |
| 1093 / 1094 | 987 / 1169 |
| 1102 / 1103 | 996 / 1178 |

## Why the earlier audit did not settle this

The earlier corner audit explicitly covered **exactly three incident faces** and
its ring audit covered complete **vertical edges only**. Top caps have four-face
closed links. Subdividing a face does not remove intrinsic curvature; the old
coverage limitation hid them. This was an audit gap, not a new user requirement.
The reusable audit now walks connected closed source-vertex links of any valence,
counts reflex polygon interior angles correctly and reports non-passing results.

Fresh source-copy readback contains **36** defective closed fans: **26 stair** and
**10 main-wall**. Of the latter, the newly approved two ring edges open **2**;
**8 main top-cap fans remain outside the existing seam permissions**:

| Source vertex | ID1 source faces | Intrinsic angle defect, degrees | Anisotropy angle budget, degrees |
|---:|---|---:|---:|
| 36 | 1306, 1307, 1361, 1362 | 40.387287 | 4.538354 |
| 40 | 1308, 1309, 1363, 1364 | 102.609710 | 4.538354 |
| 74 | 1326, 1380, 1467, 1484 | 38.808047 | 4.538354 |
| 88 | 1333, 1387, 1388, 1452 | 123.168772 | 4.538354 |
| 1380 | 19, 20, 1308, 1309 | 102.613057 | 4.538354 |
| 1382 | 17, 18, 1306, 1307 | 37.996517 | 4.538354 |
| 1410 | 43, 44, 1333, 1452 | 125.794566 | 4.538354 |
| 1417 | 36, 1326, 1467, 1468 | 39.396389 | 4.538354 |

For valence `n`, the affine anisotropy bound is
`n * 2*asin((1.02-1)/(1.02+1))`. The report additionally allows conservative endpoint
phase-error angular uncertainty from 0.1 px at 512 px/m and each witness's shortest
incident source edge; **all eight still exceed the combined budget**. This is a
necessary local chart-continuity obstruction, independent of packing capacity.
It does not prove every possible bitmap strategy impossible or choose a seam for Artem.

Source diagnostic:
`G:/Мой диск/AGR-evidence/1326-stylobate-course-grid/cap-policy-v004/main-cap-vertex40-labelled.png`.
Actual source geometry, temporary diagnostic colours only: yellow/red caps 1308/1309,
blue wall 1363; green wall 1364 is occluded in this camera. Not a brick render,
new finish assignment or visual acceptance evidence. No scene was saved.

## Three bounded chart experiments, not production changes

1. **Complete shared-edge chart**, existing answers only: 771 faces, 80 explicit
   candidate seam edges, 1,050 continuous edges, **148 conflicting edge records**.
   Raw stair-return classification and chart candidates are evidence, not new approval.
2. **Vertical main-wall subset + full existing outer panel line**: 640 vertical
   main-wall faces; **13 low-base cycle conflicts** remain after the cap faces are
   excluded diagnostically. Removing target faces is not proposed as the final output.
3. **Conditional proposal, not applied**: all 771 faces retained, 195 cap edges,
   13 base phase edges and 7 collinear continuation segments added to the candidate
   policy -> **835 measured continuous edges**, max wrapped endpoint residual
   **0.005616646064 px**, zero reported conflicts. This tests that the proposed scope
   resolves this adapter's complete-edge constraints, not packing or exported QA.

No attempt lowers density, changes source topology or adds a UDIM. Conditional
`chart_constructed` still has `passed=false`; partial-edge/vertex-only joins, distortion,
actual joint masks and full D/ERM/N appearance-equivalence remain separate checks.
The raw chart conflicts must not all be advertised as mathematical impossibilities.

## Freshness, tests and durable handoff

- Blender **5.1.2 background**, own hash-identical source copy, metric scale 1.0.
  New read-only v004 process exported **2,015 source faces / 771 ID1 / 1,244 protected**.
  XYZ, UV, topology and IDs exactly equal to v003. Original source/map hashes **10/10
  unchanged**, copied blend unchanged after diagnostic render. Daytime Max untouched.
- Shared chart RED: **9aa7643c**, missing public module. GREEN: **34 passed**.
  First fixture expectation incorrectly used a non-nearest repeat remainder; corrected
  to the independently known 8 m perimeter vs nearest 9 m repeat = 1 m = 512 px.
- General-link RED: **10210755**, **3 failed / 1 passed**, missed valence 4/5 fans.
  GREEN includes combined earlier ring/stair regressions, reflex flat polygons,
  disconnected links, empty/partial/NaN/inf, unknown/duplicate seam declarations,
  nonmanifold source edges and fresh-process audit CLI non-pass/path-alias tests.
- Affected suite:
  `uv run pytest -q tests/test_course_grid_general_fans.py tests/test_course_grid_chart.py tests/test_course_grid_audit.py tests/test_decisions.py tests/max_tools/test_agr_tools_vpm_layout.py -p no:cacheprovider --basetemp=C:/x/t_d517d7c6-affected-v004`
  -> **141 passed, 1 deselected, 0 failed**.
- Generated arbitrary-valence rigid-transform/reordered-source probe: **20/20**.
- Full suite and one implementation PR remain due on the finished pilot; no first
  review requested on this incomplete checkpoint. Not a delivery pass.

Immutable evidence directory:
`G:/Мой диск/AGR-evidence/1326-stylobate-course-grid/cap-policy-v004/`
contains fresh raw readback/script, chart experiments, exact seam proposal, source
render, labelled sheet, measurement code snapshots and **SHA256SUMS.txt**.
The tracked `cap-audit-v004.json` pins the files, source manifest and eight witnesses.
Reusable modules: `tools/materials/course_grid_chart.py` around existing
`uvlayout_core` / `facadeatlas_core`, and generalized `course_grid_audit.py`.
No job-only replacement packer or `agr unwrap-atlas` command is claimed.

## Research section 5 status

| Metric | Current evidence / gate |
|---|---|
| Course/bond | Conditional source-chart endpoint residual only; no new export or complete phase coverage. |
| Panel joints | 10 mm, owner-inside / centre 5 mm inward convention retained; new joint masks and D/ERM/N sampling not measured. |
| Density/anisotropy | Baseline 511.433889–512.566855 px/m fails lower legal bound; no new production UV density result. |
| Union usage | Not measured; **no tile-capacity verdict**. |
| Islands/reuse | All 771 source faces traced; exported island/equivalence counts not measured. |
| Tile/padding/orientation | No new UV tile or padding certificate. |
| Preservation | Fresh source readback unchanged, ten original hashes unchanged; no saved source/UV/geometry/material change. |
| Visual | Source diagnostic only; no Artem pilot verdict, no replication. |

Next after exact scope answer: record approved existing edges -> finalize common
chart and complete join checks -> classify joint masks and equivalent sampling ->
fixed-density one-tile fit -> versioned export/fresh readback and all section 5
metrics -> Artem visual verdict -> once-per-PR full suite and one PR. On a real fit
failure ask extra tile vs authorized loop cut; never infer overflow from this audit.
