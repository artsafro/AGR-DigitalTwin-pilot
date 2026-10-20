# Vatutino Ground texture binding (#340)

Status: **technical binding verified; delivery acceptance not claimed**. The authorized
2026-10-20 card/issue comment extends scope to CurbGarden and Stairs and changes the
texture source from v002 to **v003**. Maps remain provisional; no texture appearance,
whole-site, SINTEZ or package acceptance is inferred [D104].

## Versions and source preservation

- #295 / PR #308 merged at `5eb945a`; Blender route, no MAX required.
- #330 / PR #336 merged at `eed5074a3fad597fce5608ea832dccbd0edaf527`;
  incorporated through `origin/main` `8e539b9`. Its address override, physical layout,
  visual parameters, provenance and full contact labels are retained.
- Recipe seed 319. v003 contains 24 maps (12 slots x two profiles), including
  provisional concrete recipes for CurbGarden and Stairs. The historical density
  source text in manifest.source_versions is supplemented by the merged #295 evidence here.
- v002 manifest SHA-256: `64c48ca70a24f5d74f5b9eefef632db727bad50420abb4b644612cf9bcf70d2a`; **20/20 v002 map bytes unchanged** in v003;
  v002 itself remains untouched. v001 textures were not used.
- v003 manifest SHA-256: `4255185a307935bddc46f9564f12dce88091f4b3d1cdd2d74ea4ce158a8b222a`; visual parameter provenance is present.
- Incomplete, unapproved outputs from the previous Cursor attempt were archived
  under `C:/x/vatutino-ground-textured/cursor-attempt-714/` before regeneration with
  merged #330. A first Codex bind was also preserved there when moving all DCC staging
  inside the output tree. No #295 FBX or published v001/v002 source textures were overwritten.
- The final #295 VPM **with UCX** is used, not its intermediate no-UCX FBX.
  Its 715 collision meshes / 8,788 triangles remain exactly unchanged. They are not textured.

## Input/output FBX and exact geometry identity

| Profile | Kind | Path | SHA-256 |
|---|---|---|---|
| npm | input | `C:/x/t_d94665f2/ground_v014/npm/SM_Vatutino_Ground.fbx` | `94357c5f048ba3343035dfa44c9d0d89d83b3d6697dcfd9cc81c54739a6dc2ef` |
| npm | output | `C:/x/vatutino-ground-textured/v001/npm/SM_Vatutino_Ground.fbx` | `1259cb925fa1275c22445b572e493c97e5370908be3a36dc8e8b7e17e22397b5` |
| vpm | input | `C:/x/t_d94665f2/ground_v014/vpm_ucx/SM_Vatutino_Ground.fbx` | `a5f7d3963ffbe3003f4dd7d706395a84f30a3548c5281f3402b1c1694cfa3b6c` |
| vpm | output | `C:/x/vatutino-ground-textured/v001/vpm/SM_Vatutino_Ground.fbx` | `a7d5bdd547a499fe73228d5319bf1304643a01e3727f52d97433c6f742a43bb7` |

Both profiles: 46,343 render triangles; every ordered world vertex and UV is identical
(max XYZ delta **0**, max UV delta **0**). All 46,343 imported face material IDs and
raw FBX `LayerElementMaterial` entries, mapping/reference modes and ordered topology
match. Collision vertices, polygons, material IDs, UV-layer inventories, names and
triangle counts also match exactly (NPM 0; VPM 715 pieces / 8,788 triangles).

Evidence root: `C:/x/vatutino-ground-textured/v001/`. It contains `plan.json`,
`density.json`, `receipt.json`, and per-profile `SM_Vatutino_Ground.{source-fingerprint,fingerprint,readback}.json`
plus `validate.json`. No FBX, PNG, render or large JSON evidence is committed.

## Binding table and clean-process readback

Texture root: `C:/x/vatutino-ground-textures/v003/`. Every row has exactly one Base Color map;
NPM packed PNG hash and VPM resolved external PNG hash also match the manifest.

| Slot | Profile | File | Planned / readback px | SHA-256 | Mismatches |
|---|---|---|---|---|---:|
| CurbGarden | npm | `T_Vatutino_Ground_Diffuse_CurbGarden.png` | 2048 / 2048 x 2048 | `39faaa40637b3cfc7ed6d7bf08027dd8d276284f55f4a561a92122300bd0f5a5` | 0 |
| FlowerBed | npm | `T_Vatutino_Ground_Diffuse_FlowerBed.png` | 2048 / 2048 x 2048 | `60b70163597159e9d6662409a89c2a0e57e255e2cf9b9900ec7f303b36b6841f` | 0 |
| Gravel | npm | `T_Vatutino_Ground_Diffuse_Gravel.png` | 2048 / 2048 x 2048 | `c62a627d8bb3daec14753b3ee3186d7f57ccae44f66180370137a92876da33ac` | 0 |
| LawnReinforced | npm | `T_Vatutino_Ground_Diffuse_LawnReinforced.png` | 2048 / 2048 x 2048 | `b9eedbf63636d0d72c950daed1789bd51226aece2e5faa4360d88622d46d8dd5` | 0 |
| LawnRolled | npm | `T_Vatutino_Ground_Diffuse_LawnRolled.png` | 2048 / 2048 x 2048 | `6a9e20e4e44ea7d87fa77a842642a96712ac49928b8a5c87aa860f6a7f9be6b7` | 0 |
| Mulch | npm | `T_Vatutino_Ground_Diffuse_Mulch.png` | 2048 / 2048 x 2048 | `d5fa15c0f60502616adef2fc133ee46bea94ddb580f667382c27318edd48e166` | 0 |
| Pebbles | npm | `T_Vatutino_Ground_Diffuse_Pebbles.png` | 2048 / 2048 x 2048 | `22dce49d3de18cf19e1af19c5d4fe0c61d97c31dcaf1b4b69741767b336cadda` | 0 |
| Skirt | npm | `T_Vatutino_Ground_Diffuse_Skirt.png` | 2048 / 2048 x 2048 | `74c17663ff4b5eaa415abcdbae0166b7bdc0ec8ea7a9d44d11caae07030427a5` | 0 |
| Stairs | npm | `T_Vatutino_Ground_Diffuse_Stairs.png` | 2048 / 2048 x 2048 | `412239404901fdedf3eb7ad96773db5db8a320c3bb0addfdf8c2b3fa3d3e710c` | 0 |
| TileDark | npm | `T_Vatutino_Ground_Diffuse_TileDark.png` | 2048 / 2048 x 2048 | `51a8966ed321584abf8eb7f068fdaa71f94ed1226f2f65dc2a22645eec626700` | 0 |
| TileLight | npm | `T_Vatutino_Ground_Diffuse_TileLight.png` | 2048 / 2048 x 2048 | `79ad9d6696ac150a1177015affba6db697d7ead32a3f75b85e7de422a699b2b9` | 0 |
| TileRed | npm | `T_Vatutino_Ground_Diffuse_TileRed.png` | 2048 / 2048 x 2048 | `77a7333263e97448035e605522bcd7f3cabbc4e4f45e1bd1ff883db138acf586` | 0 |
| CurbGarden | vpm | `T_Vatutino_Ground_Diffuse_CurbGarden.1001.png` | 4096 / 4096 x 4096 | `7818f75ca0bdb51ded2db6bbd01e4e6f9bddd683ec86263b5c726768e7feadcd` | 0 |
| FlowerBed | vpm | `T_Vatutino_Ground_Diffuse_FlowerBed.1001.png` | 4096 / 4096 x 4096 | `f26e99c56915241d805155ca5fb4205ae6c443a68fd7d7f44f5614d9fa44f187` | 0 |
| Gravel | vpm | `T_Vatutino_Ground_Diffuse_Gravel.1001.png` | 4096 / 4096 x 4096 | `6d7a968ccc3bc9e2edef0fcc4d391688538e853162d755adfe4d7c8be1adb035` | 0 |
| LawnReinforced | vpm | `T_Vatutino_Ground_Diffuse_LawnReinforced.1001.png` | 4096 / 4096 x 4096 | `f40eb62cf14d71c8a29d2f7b4ef4b9fa9b93280e31d7d0df7c8ad51173fdad11` | 0 |
| LawnRolled | vpm | `T_Vatutino_Ground_Diffuse_LawnRolled.1001.png` | 4096 / 4096 x 4096 | `a2d170045b83693d17be399c9ad309df76dac89ca67225f22c4f722e138c8247` | 0 |
| Mulch | vpm | `T_Vatutino_Ground_Diffuse_Mulch.1001.png` | 4096 / 4096 x 4096 | `b50968f8492ba54b33c170d9fa39e543a13867b43732c31da0c8c69e5fadd209` | 0 |
| Pebbles | vpm | `T_Vatutino_Ground_Diffuse_Pebbles.1001.png` | 4096 / 4096 x 4096 | `aa67a76555d0b4b9312e8e65f05b059691abf72f586ebff1ac006281ca6b2521` | 0 |
| Skirt | vpm | `T_Vatutino_Ground_Diffuse_Skirt.1001.png` | 4096 / 4096 x 4096 | `b151bae59b31e98b87592606f7e2973407f81d4272dc281c8ac86f114f243b85` | 0 |
| Stairs | vpm | `T_Vatutino_Ground_Diffuse_Stairs.1001.png` | 4096 / 4096 x 4096 | `69e0890dcfb3bfc5f7934e8f9da38fa2636f1f5d42e5509535c1d7075f0865da` | 0 |
| TileDark | vpm | `T_Vatutino_Ground_Diffuse_TileDark.1001.png` | 4096 / 4096 x 4096 | `94caa2a50d5edaba399656148f0d23ab4681266583e34fe8dbac284aa765f6b0` | 0 |
| TileLight | vpm | `T_Vatutino_Ground_Diffuse_TileLight.1001.png` | 4096 / 4096 x 4096 | `721a7f641a0b029db835fc3e8c222ecfd3bc21b4d06444fc8875af6f4b37bc2b` | 0 |
| TileRed | vpm | `T_Vatutino_Ground_Diffuse_TileRed.1001.png` | 4096 / 4096 x 4096 | `d5d88b93c066b39149a65f8adfbfabaf683ef1f43698c8089b4841e4d5b63244` | 0 |

## Exported texel density (px/m)

Per triangle: `texture_px * sqrt(uv_area / world_area_m2)`. Perimeter Skirt is excluded from the relief band (GND-03/08); its zero UV density is reported, not concealed.

| Slot | NPM min | NPM max | VPM min | VPM max |
|---|---:|---:|---:|---:|
| CurbGarden | 29.965932 | 30.089995 | 790.347626 | 1026.857985 |
| FlowerBed | 29.947363 | 30.021107 | 999.182945 | 1024.227919 |
| Gravel | 29.707127 | 30.051492 | 835.963034 | 1024.186885 |
| LawnReinforced | 27.090118 | 30.063091 | 925.491260 | 1079.221555 |
| LawnRolled | 20.665561 | 30.213726 | 705.031403 | 1036.947013 |
| Mulch | 21.839868 | 30.114369 | 589.626414 | 1030.739818 |
| Pebbles | 25.342105 | 30.213726 | 865.225986 | 1025.196066 |
| Skirt | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| Stairs | 29.999406 | 30.001440 | 1023.987277 | 1024.039782 |
| TileDark | 28.558727 | 30.008454 | 966.748058 | 1024.325283 |
| TileLight | 11.572790 | 30.211414 | 590.908618 | 1442.061823 |
| TileRed | 11.555525 | 30.121883 | 590.982802 | 1024.505753 |

## Validator outputs (not delivery approval)

`uv run python tools/qa/validate_package.py <fbx> --profile <npm|vpm> --json`
returned **exit 2** for both. Raw outputs: `<evidence root>/<profile>/validate.json`.
An attempted literal `py -3` used the machine interpreter without shapely (exit 1);
self-repaired with the synced project interpreter above, no global installation.

- **npm**: `passed=false`; machine stage counts `{"pass": 0, "fail": 0, "review": 0, "not_run": 8}`.
  All `not_run` stage IDs (including manual): V001, V002, V003, V004, V005, V006, V012, V014, V015, V017.
  Manual pending: V015, V017.
- **vpm**: `passed=false`; machine stage counts `{"pass": 0, "fail": 0, "review": 0, "not_run": 12}`.
  All `not_run` stage IDs (including manual): V001, V002, V003, V004, V005, V007, V008, V009, V010, V011, V012, V013, V015, V016, V017.
  Manual pending: V015, V016, V017.

V002 has a header finding pass but units/scale finding not_run; its aggregate stage
is not_run, not pass. Machine counts exclude the separate manual gates. No not_run
stage is counted as passing. Normal/roughness maps, GeoJSON and delivery packaging
are outside #340; no checker or visual verdict is substituted.

## Actual commands and exit codes

```text
uv sync                                                   -> 0
uv run python tools/materials/ground_recipes.py deliver --version v003 --address Vatutino --out C:/x/vatutino-ground-textures/v003 -> 0 (24 maps)
blender.exe --background --factory-startup --python-exit-code 1 --python tools/blender/fbx_readback.py -- C:/x/t_d94665f2/ground_v014/vpm_ucx/SM_Vatutino_Ground.fbx <worktree>/tmp/issue340/source-vpm-final-readback.json -> 0
uv run python tools/materials/bind_ground_textures.py bind --npm-readback C:/x/t_d94665f2/ground_v014/readback_npm.json --vpm-readback <worktree>/tmp/issue340/source-vpm-final-readback.json --manifest C:/x/vatutino-ground-textures/v003/manifest.json --textures C:/x/vatutino-ground-textures/v003 --npm-fbx C:/x/t_d94665f2/ground_v014/npm/SM_Vatutino_Ground.fbx --vpm-fbx C:/x/t_d94665f2/ground_v014/vpm_ucx/SM_Vatutino_Ground.fbx --out C:/x/vatutino-ground-textured/v001 -> 0
```

`<worktree>` = `C:/Users/artsafro/agr-pilot/AGR-DigitalTwin/.worktrees/t_b979c32d`.
Blender = `C:/Program Files/Blender Foundation/Blender 5.1/blender.exe`, version **5.1.2**,
factory scene, metre-space source imports. The source-readback call precedes writes.
The bind logs every complete Blender command plus its return code in `bind.log`:
for **each profile**, source-copy fingerprint / bind+export / exported fingerprint /
clean `tools/blender/fbx_readback.py` = **0 / 0 / 0 / 0** (8/8). Temporary copies and
binding specs are inside the profile output tree and removed afterwards. Replaying
against this nonempty version is deliberately refused. `delivery.log` records the
outer commands and exit codes; `generate.log` records 24 generated maps.

## Regression evidence and remaining gates

- Pre-fix detached worktree at `5eb945a` loaded its own ground_recipes.py:
  `test_regression_curb_garden_and_stairs_are_provisional_recipes` **1 failed**
  because CurbGarden was missing (exit 1), not an environment error.
- Additional witnessed RED cases: fractional manifest dimensions (3), duplicate
  readback material (1), hardlink alias (1), raw layer/topology identity (1),
  partial DCC rollback into an existing empty folder (1), final materialless UCX
  inventory/collision identity (2), local staging (1), direct DCC overwrite (2).
  Focused follow-up GREEN groups: 9, 2 and 3 passed respectively.
- Final focused command: `env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest tests/test_bind_ground_textures.py tests/test_ground_recipes.py -q -p no:cacheprovider --basetemp=C:/x/t_b979c32d-targeted-green`
  -> **205 passed**, exit 0, 259.24 s (`tmp/issue340/targeted-green.log`).
- Generated expected-verdict probes: exact geometry **206/206** (2 accepted,
  204 rejected mutations); density/endpoints **4009/4009** (1905 accepted,
  2104 rejected), invoking the same regression functions with call counters;
  `tmp/issue340/probes.json`. Thresholds stay inclusive; adjacent out-of-band
  floats fail. Invalid zero/non-finite inputs are independently regressed.
- Full suite attempt 1 through `suite_slot.py`, `pytest -q -n 8 -p no:cacheprovider --basetemp=C:/x/t_b979c32d-4`:
  **7052 passed / 3 failed / 14 skipped**, 437.84 s, exit 1. Failures were the
  two orientation wall-clock budgets (box 19.61 s >= 10; slivers 15.24 s >= 5)
  and the KPP1 shell launcher exceeding its 30 s timeout, not binding tests.
- Process-local BLAS/OMP thread limits and serial focused recheck: **2 passed /
  1 failed**, 21.66 s. Shell launcher and box pass; slivers 5.49 s >= 5.
  Detached `origin/main` `8e539b9`, with the baseline module path explicitly printed,
  reproduces slivers **1 failed**, 7.04 s >= 5. The baseline worktree was removed.
  Existing owner [#361](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/361)
  covers these load-sensitive wall-clock budgets; no orientation code, thresholds
  or test selection changed in this branch (COORDINATION rule 11).
- A second unchanged-selection full run (`-n 2`, process-local BLAS/OMP limits)
  remained queued for more than 14 minutes and never acquired a slot. It was
  cancelled before handoff; its waiter/pytest process inventory was verified empty.
  `tmp/issue340/full-suite-final.log` is a queue log, **not a second test result**.
- Verification uses the completed full run plus the focused self-repair recheck:
  shell and box cases pass on recheck; the remaining sliver timing failure is
  reproduced on origin/main and owned by #361. Per rule 11 this known baseline
  failure is reported, not repaired in #340 or disguised as a literal exit-0 suite.
  Full-run log: `tmp/issue340/full-suite-parallel.log`; recheck:
  `tmp/issue340/timing-recheck.log`; baseline: `tmp/issue340/baseline-timing.log`.
  Regression eval receipt: `tmp/evals/report.json`, 0 passed /
  0 failed / 10 not measured (no Claude transcript / expected PR evidence), exit 2.
- Automated binding/geometry/density checks above are measured. User appearance
  approval of provisional maps, #295's existing geometry/visual findings,
  SINTEZ and whole-site/package approval remain separate gates, not pass.
