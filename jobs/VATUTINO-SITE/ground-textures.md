# Vatutino Ground texture binding (issue #340)

Status: **FBX written**. v003 diffuse maps are bound to every Ground slot of the #295 v014 NPM and VPM FBX. Geometry fingerprints match the source import byte for byte. `passed=true` is not claimed: `validate_package.py` without `--scene` leaves scene stages `not_run`, and those are not counted as pass.

## #295 inputs

`docs/PROJECT_STATE.md` lists #295 as open PR #308, not a merged commit. Git was not run, so no merge SHA was read from the repository. The v014 note records a local merge of `origin/main` (`433e4eb`) into that ground branch; that is not a merge of #295 into `main`. The FBX below are the v014 exports named in `jobs/VATUTINO-SITE/ground-build-v014.md` (no UCX). Their SHA-256 still matches that note after this bind.

| Input | Path | SHA-256 |
|---|---|---|
| NPM FBX | `C:/x/t_d94665f2/ground_v014/npm/SM_Vatutino_Ground.fbx` | `94357c5f048ba3343035dfa44c9d0d89d83b3d6697dcfd9cc81c54739a6dc2ef` |
| VPM FBX | `C:/x/t_d94665f2/ground_v014/vpm/SM_Vatutino_Ground.fbx` | `a41266757fe39958cae7a40a765b628aa7cbfeb74de48d3c82efc297b9cf75f1` |
| NPM readback | `C:/x/t_d94665f2/ground_v014/readback_npm.json` | 12 material slots, 46 343 triangles |
| VPM readback | `C:/x/t_d94665f2/ground_v014/readback_vpm.json` | same slot names |
| v002 manifest | `C:/x/vatutino-ground-textures/v002/manifest.json` | `64c48ca70a24f5d74f5b9eefef632db727bad50420abb4b644612cf9bcf70d2a` |
| v003 manifest | `C:/x/vatutino-ground-textures/v003/manifest.json` | `448f6462f79862bf25b6949e9e8b98b49ecda87b6316090cc46a4e207456abd8` |

v001 textures were not read. v002 files were not modified (manifest SHA-256 unchanged). The ten v002 map files are byte-identical inside v003. v003 adds `CurbGarden` and `Stairs` only. The final UCX VPM was not an input. No 3ds Max file was produced.

## Plan

`C:/x/vatutino-ground-textured/v001/plan.json`. Each of the twelve manifest slots has one verified map on both profiles (NPM 2048, VPM `.1001` 4096, file SHA-256 equal to the manifest). Ground slots with no map: none. Manifest slots with no Ground material: none.

| Slot | NPM SHA-256 | VPM SHA-256 |
|---|---|---|
| CurbGarden | `39faaa40637b3cfc7ed6d7bf08027dd8d276284f55f4a561a92122300bd0f5a5` | `7818f75ca0bdb51ded2db6bbd01e4e6f9bddd683ec86263b5c726768e7feadcd` |
| Stairs | `412239404901fdedf3eb7ad96773db5db8a320c3bb0addfdf8c2b3fa3d3e710c` | `69e0890dcfb3bfc5f7934e8f9da38fa2636f1f5d42e5509535c1d7075f0865da` |

The other ten SHA-256 values are the v002 maps recorded in the previous note.

## Bind

Blender 5.1.2 headless, on copies only. Output:

| Profile | FBX | SHA-256 | Triangles | Binding mismatches | Vertex/UV delta |
|---|---|---|---:|---:|---:|
| NPM | `C:/x/vatutino-ground-textured/v001/npm/SM_Vatutino_Ground.fbx` | `327b984cf077837c0812c2ca1389a9942ee3d8e8e85d7e07058d175f6ff201ed` | 46 343 | 0 | 0 |
| VPM | `C:/x/vatutino-ground-textured/v001/vpm/SM_Vatutino_Ground.fbx` | `b659dca3f9958224202405b387345b15f9e5a035b9888ab6c24053172fc7511f` | 46 343 | 0 | 0 |

Readback is `tools/blender/fbx_readback.py` (Base Color image name and size versus the plan). Source and bound fingerprints are byte-identical, so per-face material ids, UVs and vertex positions match.

Texel density is `texture_px * sqrt(uv_area / world_area)`. Skirt UV area is 0 on every skirt face (3 578 faces, min = max = 0). [D097] / TEX-17 applies the band to the relief surface and excludes the perimeter skirt, which is how v014 published its density. Every other slot is inside the band.

| Slot | NPM min | NPM max | VPM min | VPM max |
|---|---:|---:|---:|---:|
| CurbGarden | 29.965932 | 30.089995 | 790.347626 | 1026.857985 |
| FlowerBed | 29.947363 | 30.021107 | 999.182945 | 1024.227919 |
| Gravel | 29.707127 | 30.051492 | 835.963034 | 1024.186885 |
| LawnReinforced | 27.090118 | 30.063091 | 925.491260 | 1079.221555 |
| LawnRolled | 20.665561 | 30.213726 | 705.031403 | 1036.947013 |
| Mulch | 21.839868 | 30.114369 | 589.626414 | 1030.739818 |
| Pebbles | 25.342105 | 30.213726 | 865.225986 | 1025.196066 |
| Skirt | 0 | 0 | 0 | 0 |
| Stairs | 29.999406 | 30.001440 | 1023.987277 | 1024.039782 |
| TileDark | 28.558727 | 30.008454 | 966.748058 | 1024.325283 |
| TileLight | 11.572790 | 30.211414 | 590.908618 | 1442.061823 |
| TileRed | 11.555525 | 30.121883 | 590.982802 | 1024.505753 |

## validate_package.py

`uv run python tools/qa/validate_package.py <fbx> --profile <npm|vpm> --json`. No `--scene`, so scene stages stay `not_run` and `passed` is false. Exit code 2. Failures: 0. `not_run` is not counted as pass.

| Profile | exit | passed | machine counts | manual pending |
|---|---:|---|---|---|
| NPM | 2 | false | pass 0, fail 0, review 0, not_run 8 | V015, V017 |
| VPM | 2 | false | pass 0, fail 0, review 0, not_run 12 | V015, V016, V017 |

V002 records one FBX header pass and one `not_run` for units and scale. The stage is counted in `not_run`, not in `pass`.
