# KPP1 R1 rerun #1230 — latest run `issue-1246-r1-v003`

## #1246 corner pairs — run `r1-v003` (dt-worker, 2026-11-12)

A corner post seen edge-on in two perpendicular views (SW: Южный × Западный, NW: Северный × Западный)
was built twice in v002, each time with a guessed 210 mm depth, which made a cross with 120 mm fins.
`corner_members()` now pairs two perpendicular corner projections when their profile-depth boxes overlap
in plan and their heights overlap by more than 1 mm (`PAIR_MIN_MM`). Each pair becomes one member:
x and y come from the two measured extents, z is the overlap, and `views` names both inserts.
Height seen in one view only keeps the profile-depth guess (for example, Южный z 1.2–2.7).
Remainders of 1 mm or less (drawing round-off, e.g. 6.6501 vs 6.65) are listed as
`unbuilt_slivers_z_m`.

- `parts-schedule-r1-v003.json`: 244 inserts -> **240** members, 0 dropped. The first 217 members
  are unchanged. There are **7** reported pairs (SW 3, NW 4). Overlaps between perpendicular corner
  boxes went from 8 to **0**. Three z overlaps of 0.1 mm remain inside a single view; they come from
  the source drawing.
- SW post z 4.85–6.65: x −15.075..−14.985, y −5.7754..−5.6854 (90 × 90 mm). The measured posts
  touch the body rectangle or stand 0.3–0.4 mm off it. That is what the drawings measure; nothing
  is embedded. The visual / architect corner-joint gate is **still open**.
- Agent-owned factory-startup Blender 5.1.2: `build-report-r1-v003.json` (VPM Main 29,981 tris).
  - `SM_Kpp_1.zip.r1-v003.validate.json`: exit 1, `passed=false`, V004 topology 0, <5 mm 0,
    5–20 mm 98.
  - `0000_Kpp_1_01.r1-v003.validate.json`: exit 2, `passed=false`. NPM is unchanged because it has
    no mullions.
- `corner-pairs-readback-r1-v003.json`: ray-parity inside test on the exported VPM.
  - The SW and NW post centres are solid.
  - The four old fin centres are empty in v003. In the v002 control (the sealed FBX) all four
    were solid.
  - This is a scoped presence witness, not delivery acceptance.
- Evidence: `G:/Мой диск/AGR-evidence/1246-kpp1-corner-pairs/` with `evidence-1246-SHA256SUMS.txt`
  (11 files verified by `sha256sum -c`). Raw receipts name the staging paths `tmp/out-r1-v003b`.

```bash
uv run python jobs/KPP1/rerun-1230/build_parts.py C:/x/kpp1/r1209/plan-contours-L03.json \
  C:/x/kpp1/r1209/dxf/L01.dxf C:/x/kpp1/r1209/dxf/L03.dxf tmp/parts-r1-v003.json
uv run python jobs/KPP1/rerun-1230/make_textures.py tmp/tex-1246
blender --background --factory-startup --python-exit-code 1 --python jobs/KPP1/rerun-1230/build_blender.py -- \
  <abs>/tmp/parts-r1-v003.json <abs>/tmp/tex-1246 <abs>/tmp/out-r1-v003b <abs>/tmp/build-report-r1-v003.json
blender --background --factory-startup --python-exit-code 1 --python jobs/KPP1/rerun-1230/readback_corner_pairs.py -- \
  <abs>/tmp/out-r1-v003b/SM_Kpp_1.fbx <abs>/tmp/readback-v003b.json
```

Use absolute paths for Blender: with relative paths, texture loading fails
(`Cannot read 'tmp\tex-1246\...png'`).

## Review R1 correction (dt-worker-codex, 2026-11-11)

The v001 claim that all 27 dropped projections had built counterparts was unsupported.
The six reported West/East `200х75` members are now built. Matching is stricter than
same-height/profile: the perpendicular box must also reach the physical facade end
(within profile depth + 20 mm) and overlap the projected interval (20 mm tolerance).
No v001 drop meets all these conditions, so **all 244 source inserts are now built,
0 dropped**, including all 27 formerly omitted projections. Original 217 boxes and
all 17 stair boxes are byte-for-byte semantically unchanged in the new schedule.

Corner members preserve the measured facade rectangle and use the declared profile
depth at that facade's outer plane; they are not snapped or extended to touch the
body. This placement is the offline profile-depth construction rule, not proof of
an architect-confirmed corner joint; the visual gate remains open. A verified alias
would name its actual built counterpart index/block, never another dropped insert.

### Fresh exported-file evidence

- Agent-owned factory-startup Blender **5.1.2**, metres; no live Max or user scene used.
- `parts-schedule-r1-v002.json`, `build-report-r1-v002.json`: 244 mullions, 17 stair boxes;
  VPM Main 30,163 triangles, glass 504; NPM Main 18,332 triangles.
- `SM_Kpp_1.zip.r1-v002.validate.json`: exit **1**, `passed=false`; V004 topology **0**,
  co-directional <5 mm **0**, 5–20 mm **98** (`review`); V007/V009 pass, V010 gap pass.
- `0000_Kpp_1_01.r1-v002.validate.json`: exit **2**, `passed=false`; V004 topology **0**,
  co-directional <5 mm **0**, 5–20 mm **52**; V006 embedded atlas pass.
- `corner-readback-r1-v002.json`: clean-process import of the actual new VPM FBX,
  9 interior samples on the outer profile face of each of the six review witnesses,
  **54/54** within 4 mm; largest distance **0.000000954 m**. This is sampled presence
  evidence, not a complete shape-distance certificate or whole-delivery approval.
- Fresh `dt qa xview`: VPM **112 overlapping faces / 0 vertices**, NPM **12 / 0**,
  both exit **1** (not pass). These residuals and the 98/52 clearance band remain
  tracked by [#1244](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1244),
  explicitly nonblocking in review R1. No global topology/visual pass is claimed.
- New evidence is sealed under `G:/Мой диск/AGR-evidence/1230-kpp1-r1/r1-v002/`;
  `evidence-r1-v002-SHA256SUMS.txt`: **12/12** copied files independently verified.
  All three DXF/plan input hashes still match the #1209 inventory. Raw receipts name
  the staging `tmp/out-r1-v002` paths; the sealed copies have identical bytes/hashes.
  Prior v001 receipts/evidence remain untouched below and are historical, not current.

### Reproduction and tests

```bash
uv run python jobs/KPP1/rerun-1230/build_parts.py C:/x/kpp1/r1209/plan-contours-L03.json \
  C:/x/kpp1/r1209/dxf/L01.dxf C:/x/kpp1/r1209/dxf/L03.dxf tmp/parts-r1-v002.json
"C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --background --factory-startup \
  --python-exit-code 1 --python jobs/KPP1/rerun-1230/build_blender.py -- \
  tmp/parts-r1-v002.json C:/x/kpp1/r1230/tex tmp/out-r1-v002 tmp/build-report-r1-v002.json
uv run python tools/qa/validate_package.py tmp/out-r1-v002/SM_Kpp_1.zip --profile vpm --scene --json
uv run python tools/qa/validate_package.py tmp/out-r1-v002/0000_Kpp_1_01.fbx --profile npm --scene --json
uv run dt qa xview tmp/out-r1-v002/SM_Kpp_1.fbx --out tmp/xview-vpm-r1-v002.json
uv run dt qa xview tmp/out-r1-v002/0000_Kpp_1_01.fbx --out tmp/xview-npm-r1-v002.json
```

The sealed `check-corners-r1.py` reproduces the presence probe from the worktree
staging paths. Builder rerun after all code changes reproduced the exact parts bytes.

RED before the fix: **6 failed** (the review's six rectangles), committed as
`135c762e`; matching probes also exposed **2 failed / 4 passed** at exact ±20 mm
before replacing subtraction with inclusive endpoint bounds. NaN/inf direct-input
probes failed **3/3** before adding the finite-coordinate guard.
GREEN: **35 passed / 0 failed** (`tests/test_kpp1_rerun_1230.py` and
`tests/test_kpp1_roof_approval.py`), including earlier topology/texture/stair tests,
profile/height/corner mismatch controls, ±20 mm boundaries, source-order permutations,
interior-no-host and nonfinite rejection. No shared module changed: full suite is
not repeated after changes_requested (coordination rule 49); the initial suite
receipt remains 20,569 passed / 1 environment setup error (file rerun: 339 passed).

Remaining deferred and manual gates are unchanged; both whole-package verdicts stay false.

## Historical run `issue-1230-rerun-v001` (superseded)


Agent: dt-worker (Hermes Kanban card t_b1946208), 2026-11-11. Base: origin/main 4820e43b. Offline kernel route
(`path: deviation`, Max busy), Blender 5.1.2 agent-owned [D233]. Inputs = the #1209 copies (`C:/x/kpp1/r1209/`:
L01/L03 DXF, plan-contours-L03.json; hashes in `../rerun-1209/inputs-v001.json`).

## Result

Both FBX `passed=false` only on the deferred / not-run stages; every #1230 blocker is closed:

| #1230 item | #1209 | now (receipt) |
|---|---|---|
| V004 topology `SM_Kpp_1_Main` | duplicates_and_self_intersections 170 (fail) | **0**, isolated 0 — pass (VPM and NPM) |
| V004 co-directional < 5 mm | VPM 3, NPM 1 | **0 / 0**; 5-20 mm band VPM 98, NPM 52 (review, as the validator grades) |
| Stair | not built | **built**: 17 boxes (flight 1 from L03 treads, landing +2.100, flight 2, landing +3.600..+3.900), 204 tris |
| Mullions | 7 of 171 | **217 built of 244 L01 inserts**; 27 reported: edge-on views beyond a facade end (members of the perpendicular facade, built there) |
| Textures V007 / V009 (VPM ZIP) | not_run | **pass** (7 UDIM tiles 1001-1007, Diffuse 2048 at 1000 px/m, ERM/Normal 256 flat) |
| NPM atlas V006 | not_run | **pass** (one 2048 RGB atlas embedded) |
| V010 UCX piece gap | 5 pairs at 0 mm | **pass** (boxes inset 3 mm -> 6 mm gaps) |

Still open (not #1230 fixes): V001 GeoJSON / V011 / V013 / V014 (placement deferred by the user), V003 quad
master not given (`--master`), V010 coverage not_run, V012 archive-name review (conflict #20), manual V015-V017,
visual and checker gates.

## Commands

```bash
uv run python jobs/KPP1/rerun-1230/build_parts.py C:/x/kpp1/r1209/plan-contours-L03.json \
  C:/x/kpp1/r1209/dxf/L01.dxf C:/x/kpp1/r1209/dxf/L03.dxf C:/x/kpp1/r1230/parts-v002.json
uv run python jobs/KPP1/rerun-1230/make_textures.py C:/x/kpp1/r1230/tex
blender --background --factory-startup --python-exit-code 1 --python jobs/KPP1/rerun-1230/build_blender.py -- \
  C:/x/kpp1/r1230/parts-v002.json C:/x/kpp1/r1230/tex C:/x/kpp1/r1230/out-v004 C:/x/kpp1/r1230/out-v004-build-report.json
uv run python tools/qa/validate_package.py C:/x/kpp1/r1230/out-v004/SM_Kpp_1.zip --profile vpm --scene --json   # exit 1
uv run python tools/qa/validate_package.py C:/x/kpp1/r1230/out-v004/0000_Kpp_1_01.fbx --profile npm --scene --json  # exit 2
```

Receipts here: `SM_Kpp_1.zip.validate.json`, `0000_Kpp_1_01.validate.json`, `build-report.json`,
`parts-schedule-v001.json` (openings, every mullion with its placement, drops with reasons, stair boxes),
`textures.json`. Evidence (rule 57, not in git): `G:/Мой диск/AGR-evidence/1230-kpp1-r1/` (both FBX, the VPM ZIP,
parts JSON, NPM atlas), hashes in `evidence-SHA256SUMS.txt`.

## How V004 was closed (three attempts)

1. #1209: parts joined (`bpy.ops.object.join`) -> touching shells, 170.
2. One Exact Boolean UNION (collection operand, self-intersection, material transfer) of body + frames + doors
   + mullions + stair + roof + parapet: self_intersections 0, but 332 vertices closer than 2 mm (DXF slivers,
   bisect cuts) -> duplicates 1011.
3. Weld at 4 mm + collapse the slivers + delete loose vertices: **0**.

## Assumptions (not from the drawings; for the visual gate)

- Stair rises approximated from the L01 rungs (flight 1: 2.100 / 9, flight 2: 1.800 / 9); flight 2 run
  3.600 -> 5.600 and the top landing 5.600..8.580 from the Восточный view, x 27.63..28.83 from the Южный view;
  stringers and railings not modelled; stair finish RAL 7004 grey is an assumption.
- Mullions outside a cut opening stand on the facade face (profile depth outward, 10 mm embedded).
- Finishes by band of the face centroid height (plinth RAL 7004 <0.9, RAL 7047 0.9-2.7, RAL 5015 2.7-7.1,
  RAL 7047 above, from `jobs/KPP1/scripts/build_kpp1.py`); colours approximate RAL sRGB, not calibrated;
  Diffuse joints = the finish periods of `jobs/KPP1/scripts/vpm_textures.json`.
- Levels 3.900 / 7.909 and the roof / parapet values stay as in [D238] / [D249] (not architect-confirmed).
