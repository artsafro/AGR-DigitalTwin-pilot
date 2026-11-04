# Experiment: second FBX reader (`wm.fbx_import` vs legacy)

Card t_f24b8f78, issue #767. Research only: no checker, gate, threshold or `tools/blender/fbx_readback.py` change.
Diff logic: `tools/research/fbx_reader_compare.py` (`new-case`). Planted FBX copies stayed outside the repo.

## Question

Does a cold read through Blender 5 `bpy.ops.wm.fbx_import` agree with the legacy `bpy.ops.import_scene.fbx` used by readback, on names, triangle count, material id per face, UV layer count, UV bbox and packed images? And does each reader show a planted material-id swap, a removed UV layer and a renamed mesh?

## Setup

Installed Blender reports `5.1.2` (hash `ec6e62d40fa9`), the pin in `src/dt_ai/core/blender_runner.py`. Each import is a new process:

`blender --background --factory-startup --disable-autoexec --python-exit-code 1`

The shared lock is `%LOCALAPPDATA%/Temp/agr-blender-session.lock` (same file as `blender_exec.py`). `dcc_batch.py` has no Blender tool, so this script takes that lock itself and does not delete inputs.

`bench-k02-decor-fragment` has no FBX in this checkout (`data/benchmark/bench-k02-decor-fragment` is absent). K02 below is the existing job-output FBX, not that missing decor-fragment file.

| Object | Role | Bytes | SHA256 |
|---|---|---:|---|
| AC08 | v010, `benchmark/methods/benchmarks.json` `ac08.fbx_sha256` | 26364 | `ca4715a446db660d2c82766d4be8547fac954c4fab1363ef171bde4b99a4277b` |
| B01 | `benchmark/bench-b01-box/etalon.json` `etalon.fbx` | 49328 | `a109aa9a9f25c72e8d4869ee43b0b33aee009f5c248caf62388c4dcb0c7816d9` |
| K02 | `jobs/OBR22-K02/outputs/OBR22_K02_floor02_source.fbx` (main checkout) | 12958240 | `58a7b831e95c115bdf9b82c18a545c2214eb799c94133dd01b83418270606f58` |

Hashes matched before and after the run (`inputs_unchanged: true`).

## Cross-read (3 cold runs each)

Wall time is the whole Blender process. `stable` is the snapshot diff across the 3 runs of that importer (0 = identical).

| Object | Importer | Run seconds | Median s | Meshes | Triangles | UV layers | Packed images | Stable | Cross diff |
|---|---|---|---:|---:|---:|---|---:|---:|---:|
| AC08 | legacy | 1.904, 1.948, 2.928 | 1.948 | 2 | 398 | 1 and 0 | 0 | 0 | 0 |
| AC08 | wm | 1.751, 1.815, 3.410 | 1.815 | 2 | 398 | 1 and 0 | 0 | 0 | 0 |
| B01 | legacy | 1.852, 2.181, 2.394 | 2.181 | 1 | 150 | 0 | 0 | 0 | 0 |
| B01 | wm | 1.513, 1.603, 1.927 | 1.603 | 1 | 150 | 0 | 0 | 0 | 0 |
| K02 | legacy | 6.207, 5.887, 6.257 | 6.207 | 2561 | 590414 | 1 | 0 | 0 | 1 (names) |
| K02 | wm | 4.458, 4.301, 5.113 | 4.458 | 2561 | 590414 | 1 | 0 | 0 | 1 (names) |

AC08 is two meshes: the main mesh (386 triangles, one UV layer, bbox `[0.041795, 0.027607, 4.39343, 0.95]`) and the UCX mesh (12 triangles, no UV). Both readers agree, including material id per face. The catalog fact `model_triangles: 386` is the main mesh only.

B01 has no UV layer in this etalon. Both readers agree on the single mesh, 150 triangles, 75 faces, material ids and empty packed-image list.

K02 name diff, explained: 219 of 2561 names match and 2342 do not. Legacy shortens the node name and appends `_` plus 7 hex digits (longest legacy name 67 UTF-8 bytes). `wm.fbx_import` keeps a longer name and appends a space plus `[integer]` (longest 172 bytes). The multiset of `(triangles, material id per face, UV layer count, UV bbox)` is equal, 2561/2561, and both packed-image lists are empty. 1791 meshes share a geometry signature with at least one other mesh, so those instances are not a unique name pair; the multiset is the comparison. No other field differed.

None of the three files carried a packed image, so this run does not show an embedded-image drop.

## Planted defects

B01 has no UV, so the copies were exported from a legacy import of AC08 (scratch only). Control is that export with no edit. Each reader then did one cold import of the control and of the mutant.

| Defect | Legacy caught | wm caught | Legacy kinds | wm kinds |
|---|---|---|---|---|
| one face material id changed | yes | yes | `material_ids` (diff 1) | `material_ids` (diff 1) |
| UV layer removed | yes | yes | `uv_layer_count`, `uv_bbox` (diff 2) | `uv_layer_count`, `uv_bbox` (diff 2) |
| mesh renamed | yes | yes | `name` (diff 1) | `name` (diff 1) |

## Verdict

**advisory**

`wm.fbx_import` is present on the pinned Blender 5.1.2 and is faster on these three files (median of 3). It matches legacy on triangles, material ids, UV and packed images, and it catches the same three planted defects. It is not a drop-in second gate: on K02 it renames 2342 nodes that legacy also renames, but differently, so a raw name diff is importer behavior. Keep legacy readback. A later cross-check can compare the geometry multiset and treat names as a separate, explained field. This card does not change a checker.

## Reproduce

```text
uv run python tools/research/fbx_reader_compare.py measure ^
  --scratch <dir-outside-repo> --output <dir-outside-repo>/measure.json ^
  --ac08 <AC08-v010.fbx> --ac08-sha ca4715a446db660d2c82766d4be8547fac954c4fab1363ef171bde4b99a4277b ^
  --b01 <B01-etalon.fbx> --b01-sha a109aa9a9f25c72e8d4869ee43b0b33aee009f5c248caf62388c4dcb0c7816d9 ^
  --k02 <K02-job.fbx> --k02-sha 58a7b831e95c115bdf9b82c18a545c2214eb799c94133dd01b83418270606f58
```

A wrong SHA256 exits nonzero and writes no report. An output path that resolves to an input exits nonzero and writes nothing.
