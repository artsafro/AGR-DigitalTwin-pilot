# Parametric parts — measured rows

Read back from the FBX in `C:/x/methods/parametric-parts/` by `tools/methods/parametric_parts_measure.py`. `build_s` is build + FBX export for every tool. SolidCraft's figure also includes OBJ export and the OBJ→FBX conversion. xView counts are overlapping-vertex pairs at 2 mm and xView contact faces at 5 mm. Dimension error is millimetres. Every listed row has `status: measured` and `fbx_readback_ok: true`.

`fbx_readback_ok` is the parser result and a fresh 3ds Max 2026.3 import through `dcc_batch.py`. Max had to report at least one object and a triangle count equal to the parser. `importFile` returning true is not the check. Receipts: `C:/x/t_5fcef264/dcc-catalog.json` (Blender and Max files, wrapper `ok`, 43.4 s, raw exit `4294967166`, known `polyunwrapper_autoload.mse` warning) and `C:/x/t_5fcef264/dcc-probe.json` (SolidCraft files after the FBX writer change, wrapper `ok`, 39.3 s, same raw exit and warning). Each file imported as 1 mesh. Raw build receipts: `solidcraft-build.json`, `blender-build.json`, `max-build.json` in `C:/x/methods/parametric-parts/`.

The Max build session that wrote the four Max meshes was 35.6 s, wrapper `ok`, raw exit `4294967166`, same startup warning. That figure is the process, not `build_s`.

## Six builds

| part | tool | build_s | triangles | xView 2 mm | xView 5 mm | dimension error mm | topology | Max objects |
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

| part | tool | build_s | triangles | xView 2 mm | xView 5 mm | dimension error mm | topology | Max objects |
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
