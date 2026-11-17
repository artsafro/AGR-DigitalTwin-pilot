# KPP1 — cross-tile faces and NPM UV readback (#1580)

Evidence for issue #1580: `tools/derive/export_npm.py` now takes the face tile from
`udimtile_core.face_tile(strict=True)` and refuses a face that crosses UDIM tiles. `twinqa.npm_uv` reads the
exported NPM FBX back and checks every face against its `npm_atlas.json` region and the 8 px padding.
Blender 5.1.2 headless. The masters were checked as copies in `C:/x/ev_t_4cc96b1b/masters/`, and their hashes
were unchanged after the run (`master_unchanged: true` in every dry-check JSON).

## Straddling faces on the real NPM sources (dry check, no write)

`blender -b --factory-startup --python tools/derive/export_npm.py -- --dry-check <master copy>`

| Job | Master (copy of) | SHA-256 | Object | Faces | Straddling |
|---|---|---|---|---|---|
| KPP1 | `C:/x/bench-npm-kpp1/packet-r1-v002/master-r1-v001.blend` (R1, #1318 packet) | `492f20af…4de3` | SM_Kpp_1_Main | 30 162 | **0** |
| KPP1 | `C:/x/quad-1372/packet-quad-v002-r6/master-quad-v002.blend` (#1372) | `fb566ff5…53bb` | SM_Kpp_1_Main | 61 839 | **0** |
| KPP1 | `G:/Мой диск/AGR-evidence/1563-kpp1-quad-master-v003/master-quad-v003/master-quad-v003.blend` | `b54c5f72…ab53` | SM_Kpp_1_Main | 61 465 | **0** |
| PSU275 | not measured. The stage-6 masters (`jobs/PSU275/outputs/...`) are not on this PC (searched `C:/Users`, `C:/x`, `D:/`, Drive `AGR-assets` / `AGR-evidence`). PSU275 exports with its own `jobs/PSU275/scripts/export_npm.py`, not the shared tool or `agr vpm-to-npm`, so its delivered results are not affected by this change. | | | | — |

KPP1 is the only job that runs the shared exporter (`agr vpm-to-npm`: benchmark-1318, cold-run-1313,
build-manifest-1423, quad-1372). It has 0 straddling faces, so the default became **refuse**.
`--allow-cross-tile` keeps the legacy centroid move as an explicit option for any master that turns out to need
it. Every moved face is then listed in `export_npm_meta.json` under `cross_tile_moved`.

## The readback check on a real NPM export

`uv run agr vpm-to-npm --blender <5.1> spec.json run1/atlas --recipe-dir … --cell 512 --pad 8 --master M
--then-npm M spec.json run1/atlas run1/export/fbx 0000 --recipe-dir …` (M = R1 master copy). Exit 0:

- export: `cross_tile_policy: refuse`, `cross_tile_moved: []`, 30 162 Main triangles;
- route step 3 (`python -m twinqa.npm_uv`): `V006 UV atlas padding: PASS 0000_Kpp_1_01.fbx: 30162 faces in
  7 regions; nearest corner 17.69 px from its cell edge (>= 4 px)`;
- `validate_package.py 0000_Kpp_1_01.fbx --profile npm --scene --npm-atlas run1/atlas/npm_atlas.json`: V006
  pass (embedded textures, texture dimensions, UV atlas padding).

Witnesses on the same real export (synthetic edits of copies, not deliveries):

| Witness | Result |
|---|---|
| the same FBX against an `npm_atlas.json` whose regions shrink by 10 px per side | FAIL, 257 of 30 162 faces in the padding band, exit 1 |
| a master copy with face 0 corner pushed into tile 1002 (`witness/perturb_master.py`) | export refused before any write: `1 face(s) cross UDIM tiles … SM_Kpp_1_Main face 0: centroid tile 1001, corner tiles [1001, 1002]`, exit 1 |
| the same master with `--allow-cross-tile` | export lists `cross_tile_moved: [{SM_Kpp_1_Main, face 0, 1001, [1001, 1002]}]`, then the route readback FAILS (`face 0 (Plinth_RAL7004): crosses cell`), exit 1 |

Evidence: `G:/Мой диск/AGR-evidence/1580-npm-cross-tile/` with `SHA256SUMS.txt`. A copy of the hash list is in
`evidence-SHA256SUMS.txt` next to this file. The FBX and logs are kept outside git.
