# Master mesh quality score by the OKS split rule [D336] (#1616)

Status: metric + calibration + one OBSERVE loop run. Nothing retained; no delivered package or
master touched. Evidence (rule 57): `G:/Мой диск/AGR-evidence/1616-mesh-quality/` + `SHA256SUMS.txt`
(31 files: calibration reports, loop log and round reports, wire sheets, PSU275 conversion).

## Tool

```
uv run python tools/qa/mesh_quality_score.py MASTER.(blend|fbx|obj|json) --out NEW.json [--zone X0,Y0,X1,Y1 ...] [--param key=value]
```

Blender 5.1.2 headless dump (`tools/blender/mesh_quality_dump.py`) -> stdlib core
(`tools/qa/mesh_quality_core.py`). Components, thresholds and their reasons are in the core docstring:
`tri_share`, `ngon_share` (error, status `fail`), `sliver_share` (tri min angle < 10 deg, quad min
corner < 30 deg), `pole_share` (flat interior vertices with valence != 4), `one_mesh_share` (body element
faces / non-glass faces, penalty above 0.5), `weld_share` (concave creases > 30 deg inside the body
element), `long_share` (side > 3.9 m). score = 100 * (1 - weighted mean penalty); it ranks, never accepts.

## Calibration (corners = plan boxes around the SW/NW posts of the #1563 sheet)

| Master | Acceptance | Score | sliver | pole | one-mesh (body share) | weld | elements | faces | input sha256 |
|---|---|---|---|---|---|---|---|---|---|
| KPP1 quad-v002 whole | none (superseded) | 72.754 | 0.2326 | 0.1689 | 0.9993 | 0.0933 | 45 | 62 091 | fb566ff5e10e |
| KPP1 quad-v002 SW/NW corners | none (before) | 72.924 | 0.2243 | 0.1695 | 0.9977 | 0.0985 | 8 | 6 197 | fb566ff5e10e |
| KPP1 quad-v003 whole | accepted except corners | 72.749 | 0.2332 | 0.1695 | 0.9992 | 0.0925 | 45 | 61 717 | b54c5f72cca6 |
| **KPP1 quad-v003 SW/NW corners** | **rejected** | **73.017** | 0.2210 | 0.1744 | 0.9976 | 0.0915 | 8 | 5 823 | b54c5f72cca6 |
| PSU275 SM_Psu_1_Main + MainGlass | accepted 2026-10-07 | 99.514 | 0.0071 | 0.0022 | 0.3720 | 0.0322 | 2 955 | 39 276 | 41200c110342 |

Machine form: `calibration.json` (test `test_committed_calibration_ranks_rejected_corners_below_accepted`).

Reading:
- The rejected v003 corners score far below the accepted PSU275 master (73.0 vs 99.5): the metric
  separates "one mesh with split-triangle quads" from a [D336]-style master. Drivers: body share 0.998
  vs 0.372 (KPP1 Main is ONE vertex-connected element; PSU275 Main has 509 inset elements), slivers
  22 % vs 0.7 %, poles 17 % vs 0.2 %.
- The corners are NOT worse than the rest of KPP1 v003 (73.0 vs 72.7) nor than v002 (72.9): the whole
  KPP1 quad master shares the defect (one welded mesh, triangle-to-3-quad fans). The metric cannot - and
  should not - rank the corners below the rest of the same master; whether the rest of v003 also needs
  the [D336] rebuild is Artem's call (open item, not decided here).
- PSU275 is available only as the editable `2PSU275_VPM_NPM_quads_v001.max` (#1420 evidence, sha256
  `376ad615...`). It was converted read-only by 3ds Max 2026 batch (`3dsmaxbatch`, no live Max, source
  hash unchanged) to a non-triangulated FBX of `SM_Psu_1_Main` + `SM_Psu_1_MainGlass` (36 556 + 2 720
  quads = the accepted clean-up v009 counts). Native cross-check of elements: Max `polyop` gives Main 607 /
  Glass 2 446 elements; the Blender-read FBX gives 509 / 2 446 (Max elements are edge-connected, the score
  uses vertex connectivity: parts touching at one vertex count as one element here).

## OBSERVE loop (Phase 2, run `loop-r1`, 2026-11-17)

`tools/qa/mesh_quality_observe.py` measured the v003 corners, ran the candidate body `after` hook
`tools/blender/split_welded_parts_candidate.py` (split concave creases, positions unchanged) at 80/60/45/30 deg on a copy,
re-measured, and logged keep/discard. Log: `observe-log-r1.jsonl` (copy of the evidence file).

| Round | Candidate | Score | Kept | sliver | pole | one-mesh | weld | split edges |
|---|---|---|---|---|---|---|---|---|
| 0 | baseline v003 corners | 73.017 | incumbent | 0.2210 | 0.1744 | 0.9976 | 0.0915 | - |
| 1 | split 80 deg | 87.322 | keep | 0.2210 | 0.1744 | 0.6601 | 0.0111 | 10 635 |
| 2 | split 60 deg | 88.052 | keep | 0.2210 | 0.1744 | 0.6422 | 0.0097 | 10 729 |
| 3 | split 45 deg | 88.205 | keep | 0.2210 | 0.1744 | 0.6392 | 0.0061 | 10 945 |
| 4 | split 30 deg | 89.486 | keep | 0.2210 | 0.1744 | 0.6087 | 0.0000 | 11 359 |

Would change (NOT applied): `jobs/KPP1` skeleton hooks += `{"script": "hooks/split_welded_parts.py" (copy of the candidate),
"stage": "body", "point": "after"}` with `angle_deg=30`.

Before/after wire sheet: `sheets/kpp1-v003-corners-observe-wire.png` (sha256 `a1fff15a...`), same
cameras as the rejected #1563 sheet. **Finding: the wire is visually unchanged** - the +16 points come
only from un-welding (one-mesh and weld components); slivers and poles are untouched. So:
1. The split hook is NOT a fix and must not be retained; the real fix stays the #1609 rebuild.
2. The metric can be raised by un-welding alone. Proposed metric v2 (needs Artem's view before it is
   added): an `open_seam_share` component - body boundary edges coincident with another element's boundary
   (an un-welded seam that leaves a hole instead of a body that keeps its opening/recess, [D336]).

## Reproduce

```
uv run python tools/qa/mesh_quality_score.py master-quad-v003.blend --out v003-corners.json --zone=-17.5,-8.2,-12.5,-3.2 --zone=-17.5,3.5,-12.5,8.5
uv run python tools/qa/mesh_quality_observe.py master-quad-v003.blend C:/x/ev_1616/<new-run-dir>
blender -b --factory-startup --python jobs/KPP1/quad-1372/render_before_after.py -- <fbx> <png> <out> <tag> corners
```
