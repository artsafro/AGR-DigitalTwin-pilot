# Parametric parts — measured rows

Read back from the FBX in `C:/x/methods/parametric-parts/` by `tools/methods/parametric_parts_measure.py`. `build_s` is build + FBX export for every tool. SolidCraft's figure also includes OBJ export and the OBJ→FBX conversion. xView counts are overlapping-vertex pairs at 2 mm and xView contact faces at 5 mm. Dimension error is millimetres. Every listed row has `status: measured` and `fbx_readback_ok: true`, where `fbx_readback_ok` is the **parser result only** (`tools/methods/parametric_parts_measure.py`). It is not a fresh 3ds Max import.

## Native (Max) evidence status: historical, not re-verified

The `Max objects` column and the native claims below are **historical observations**, not a current verified-Max result. The receipts this file originally cited are unavailable: `C:/x/t_5fcef264/dcc-catalog.json` and `C:/x/t_5fcef264/dcc-probe.json` do not exist (checked read-only; `C:/x/t_5fcef264/` is a pytest `--basetemp` and holds only test temp dirs). Their contents are not reconstructed here. Orchestrator vacation check, 2026-10-27: https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/720#issuecomment-6452439360 (the SHA256SUMS match 12/12, but the Max readback is unverifiable until re-run).

- Historical, as originally recorded in this file (original numbers kept, attributed, not re-checked): Blender and Max files, wrapper `ok`, 43.4 s; SolidCraft files after the FBX writer change, wrapper `ok`, 39.3 s; each file imported as 1 mesh; known `polyunwrapper_autoload.mse` warning. Max build session that wrote the four Max meshes: 35.6 s (the process, not `build_s`).
- Historical reviewer evidence on PR #720, not freshly rerun: 12/12 fresh Max 2026.3 imports with matching triangle counts at head `ff5efd00` (https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/720#issuecomment-6427316201); round 3 states DCC was not rerun (https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/720#issuecomment-6427599940).
- Raw process exit `4294967166` (the same value in every Max session above) is **not a clean native process exit**; it is not exit 0. The wrapper's `ok` status is not a substitute for a clean exit.
- Still available: raw build receipts `solidcraft-build.json`, `blender-build.json`, `max-build.json` in `C:/x/methods/parametric-parts/` (not re-read for this correction).
- Native readback is **not currently re-verified**. Re-running it via `dcc_batch.py` and committing a text receipt is the open step. Not adopted; this is not production acceptance.

## Six builds

| part | tool | build_s | triangles | xView 2 mm | xView 5 mm | dimension error mm | topology | Max objects (historical) |
|---|---|---:|---:|---:|---:|---:|---|---:|
| bench | solidcraft | 0.8411376000149176 | 40 | 0 | 0 | 4.76837158203125e-05 | valid | 1 |
| bench | blender | 0.022990999976173043 | 36 | 0 | 0 | 4.76837158203125e-05 | valid | 1 |
| bench | max | 0.062177599989809096 | 36 | 0 | 0 | 4.76837158203125e-05 | valid | 1 |
| aerator | solidcraft | 1.072084499988705 | 188 | 0 | 0 | 1.430511474609375e-05 | valid | 1 |
| aerator | blender | 0.005639799986965954 | 192 | 0 | 0 | 1.430511474609375e-05 | valid | 1 |
| aerator | max | 0.04162400000495836 | 192 | 0 | 0 | 1.430511474609375e-05 | valid | 1 |

SolidCraft's 188 triangles and Max/Blender's 192 triangles are the same flange/pipe/cap solid. The counts differ by triangulation, not by a box substitute.

## Parameter changes

Bench length 1800 → 1900 mm. Aerator pipe 110 → 210 mm (bbox height 424 mm).

| part | tool | build_s | triangles | xView 2 mm | xView 5 mm | dimension error mm | topology | Max objects (historical) |
|---|---|---:|---:|---:|---:|---:|---|---:|
| bench | solidcraft | 0.8420836000004783 | 40 | 0 | 0 | 2.86102294921875e-05 | valid | 1 |
| bench | blender | 0.004701300000306219 | 36 | 0 | 0 | 2.86102294921875e-05 | valid | 1 |
| bench | max | 0.023779399984050542 | 36 | 0 | 0 | 2.86102294921875e-05 | valid | 1 |
| aerator | solidcraft | 0.9706543000065722 | 188 | 0 | 0 | 1.430511474609375e-05 | valid | 1 |
| aerator | blender | 0.005453700025100261 | 192 | 0 | 0 | 1.430511474609375e-05 | valid | 1 |
| aerator | max | 0.02662900002906099 | 192 | 0 | 0 | 1.430511474609375e-05 | valid | 1 |

Topology stayed valid. Triangle count did not change inside a tool.

## sha256

`SHA256SUMS` in this directory. Files themselves stay in `C:/x/methods/parametric-parts/`.
