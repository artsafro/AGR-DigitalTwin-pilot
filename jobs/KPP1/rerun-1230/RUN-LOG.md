# KPP1 R1 rerun #1230 (after #1209) — run `issue-1230-rerun-v001`

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
