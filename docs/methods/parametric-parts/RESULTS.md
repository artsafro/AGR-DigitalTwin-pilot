# Parametric parts — measured rows

Read back from the FBX in `C:/x/methods/parametric-parts/` by `tools/methods/parametric_parts_measure.py`. `build_s` is defined in `VARIANTS.md` (in-tool create/export, not process launch). xView counts are overlapping-vertex pairs at 2 mm and xView contact faces at 5 mm. Dimension error is millimetres. Every listed row has `status: measured` and `fbx_readback_ok: true`.

## Six builds

| part | tool | build_s | triangles | xView 2 mm | xView 5 mm | dimension error mm | topology |
|---|---|---:|---:|---:|---:|---:|---|
| bench | solidcraft | 0.005197 | 40 | 0 | 0 | 0 | valid |
| bench | blender | 0.0239359 | 36 | 0 | 0 | 4.76837158203125e-05 | valid |
| bench | max | 0.0722662 | 36 | 0 | 0 | 4.76837158203125e-05 | valid |
| aerator | solidcraft | 0.0008746 | 12 | 0 | 0 | 0 | valid |
| aerator | blender | 0.0055122 | 192 | 0 | 0 | 1.430511474609375e-05 | valid |
| aerator | max | 0.0372673 | 192 | 0 | 0 | 1.430511474609375e-05 | valid |

Max's four-mesh `dcc_batch` session was 37.2 s. That figure is the process, not `build_s`.

## Three parameter changes (bench length 1800 → 1900 mm)

| part | tool | build_s | triangles | xView 2 mm | xView 5 mm | dimension error mm | topology |
|---|---|---:|---:|---:|---:|---:|---|
| bench | solidcraft | 0.0013164 | 40 | 0 | 0 | 0 | valid |
| bench | blender | 0.0050702 | 36 | 0 | 0 | 2.86102294921875e-05 | valid |
| bench | max | 0.0244939 | 36 | 0 | 0 | 2.86102294921875e-05 | valid |

Topology stayed valid on all three. Triangle count did not change.

## Also measured (aerator pipe 110 → 210 mm, or a second box at height 424 mm)

| part | tool | build_s | triangles | xView 2 mm | xView 5 mm | dimension error mm | topology |
|---|---|---:|---:|---:|---:|---:|---|
| aerator | blender | 0.0054208 | 192 | 0 | 0 | 1.430511474609375e-05 | valid |
| aerator | max | 0.0247511 | 192 | 0 | 0 | 1.430511474609375e-05 | valid |
| aerator | solidcraft | 0.0006498 | 12 | 0 | 0 | 0 | valid |

The SolidCraft height-424 row is a new `solid.box`, not `timeline.edit`. Its `build_s` is that execute. The earlier bench `solid.box` fallback (1900 mm) read back with 4 vertex pairs at 2 mm and was not kept as the bench param row.

## sha256

`SHA256SUMS` in this directory. Files themselves stay in `C:/x/methods/parametric-parts/`.
