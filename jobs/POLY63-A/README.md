# POLY63-A - #1619 polygon stage 1, site 63 tower A

Body with openings only on the typical floors (+10.15..+47.95, 12 x 3.15 m). No windows, glass, capsules or AC
boxes (stage 2). Review draft, not accepted VPM. Evidence:
`G:/Мой диск/AGR-evidence/1619-body-training/tower-A/v004/` (+ `SHA256SUMS.txt`); review copy
`C:/x/review-63A/63A_Stage1_v004.fbx`.

The floor and module steps use the hooks of `jobs/garibaldi22/body-training-1619/` (floor_from_dump gets
`--pre-simplify` / `--start-corner` here); this job adds only its own three hooks.

Zones: Revit 2025 was not running (no process, port 7891 closed), so the finish zones come from the Revit wall
TYPE names in the FBX crop (`zonemap63.json`), not from the .rvt material list.

Reproduce (H = `jobs/garibaldi22/body-training-1619/hooks`, P = `jobs/POLY63-A/hooks`, E = `C:/x/ev_poly63a`;
`a63A_src.npz` = tower A crop of `STLB-04_RR_AR.fbx` read in Blender 4.4, `keys63.json` = class keys):

```
uv run python H/floor_from_dump.py E/a63A_src.npz f0.json --keys E/keys63.json --seal windows --openings --pre-simplify 0.03 --start-corner
uv run python P/pockets_self.py f0.json pk0.json --fill fill.json                # fail: 12 pockets < 0.4 m to fill, 4 niches kept
uv run python H/floor_from_dump.py E/a63A_src.npz f1.json --keys E/keys63.json --seal windows --openings --pre-simplify 0.03 --start-corner --fill fill.json
uv run python P/pockets_self.py f1.json pk1.json --fill fill_b.json              # pass
uv run python P/contour_d337.py f1.json f2.json                                   # D341 steps + D337 fillets (2 cm sagitta, 0.6 m step)
uv run python P/zones_from_types.py f2.json E/a63A_src.npz jobs/POLY63-A/zonemap63.json floor_v004.json
blender -b --factory-startup --python H/module_build.py -- floor_v004.json a63A_v004 --max-side 3.6
blender -b --factory-startup --python docs/research/body-modelling-1618/dump_mesh.py -- a63A_v004/body.fbx dump_v004
uv run python docs/research/body-training-1619/readback_openings.py dump_v004/SM_Body_Main.npz floor_v004.json rb_v004.json
uv run python docs/research/body-training-1619/band_compare.py dump_v004/SM_Body_Main.npz 10.15 47.95 a63A_v004 --step 3.15
uv run python tools/qa/mesh_quality_score.py a63A_v004.mq.json --out a63A_v004.score.json
```
