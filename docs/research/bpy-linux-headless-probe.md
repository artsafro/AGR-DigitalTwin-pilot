# Probe: `bpy` wheel headless on Linux (cloud card C1)

Card C1 of `docs/grill/modeling-architecture-2026-10-16.md` [D110]. Date: 2026-10-18. Follows
`docs/research/bpy-wheel-viability.md` (measured on Windows); this note repeats the same checks on the cloud Linux
container. All fixture data is SYNTHETIC. Nothing in the repository dependency graph was changed.

## Verdict

**GO on Linux** for the headless operation kernel: the `bpy==5.1.2` manylinux wheel installs in a separate
Python 3.13 venv, imports, and does the FBX export / import round trip with the same results as on Windows.

## What was run (measured)

```text
uv venv -p 3.13 venv                                   # system CPython 3.13.16
UV_CACHE_DIR=<scratch>/uvcache uv pip install -p venv/bin/python bpy==5.1.2 numpy==2.5.3
venv/bin/python -I fixture.py -- <out>                 # scratch script, not committed
venv/bin/python tools/blender/fbx_readback.py -- <fbx> <json>
venv/bin/python tests/dcc/connect_readback.py -- <dir>
```

`fixture.py`: `read_factory_settings(use_empty=True)`; cube via `bmesh.ops.create_cube(size=2)` + `recalc_face_normals`;
`UVMap` layer; object at (1, 2, 3); `export_scene.fbx(use_selection, apply_unit_scale, axis_forward=-Z, axis_up=Y,
mesh_smooth_type=FACE)`; reset; `import_scene.fbx`; compare counts, sorted rounded (1e-4) face normals, world vertex
coordinates and transform.

## Results

| Check | Linux wheel |
|---|---|
| wheel | `bpy 5.1.2`, `build_platform` Linux, build date 2026-05-19 (same date as the Windows wheel) |
| install | 5.4 s for 12 packages on the first install in this container (390.9 MB wheel); venv 937 MB, uv cache 6.6 MB |
| Python / numpy | 3.13.16 / 2.5.3 (the repo pin) |
| `bpy.app.binary_path` | `''` (module build, as documented) |
| FBX operators | `export_scene.fbx` and `import_scene.fbx` present; `io_scene_fbx` enabled out of the box |
| export / import | FINISHED / FINISHED, FBX version 7400, exporter `Blender (stable FBX IO) - 5.1.2 - 5.15.0` |
| round trip | 8 vertices / 6 faces / 12 triangles before and after; UV layer `UVMap`; normals, world vertex coordinates, location (1,2,3), rotation, scale equal |
| FBX size | 12 236 B on Linux (12 252 B on Windows); three runs differ from each other in ~27 bytes, the first at offsets 340 / 369 (`CreationTimeStamp`) |
| `tools/blender/fbx_readback.py` | runs unchanged under plain `python script -- args`, exit 0, 1 448 B JSON, `readback_ok: true` |
| `tests/dcc/connect_readback.py` | runs unchanged, `synthetic_readback_passed: true`, `.blend` saved and reopened |
| wall time | `import bpy` 1.5 s cold / 0.5 s warm; whole fixture 1.9 s / 0.7 s |

## Not checked

- Whether all differing FBX bytes are timestamp fields (only offsets up to 11 980 were listed, not decoded).
- Bytes of the Linux FBX against the Windows FBX (sizes differ by 16 B, cause not decoded; geometry readback equal).
- Large meshes, materials, several UV sets, custom normals, textures: the same gaps as the Windows note.
- The AGR checker add-ons (SINTEZ) inside the module build.
- Install time outside this container's package proxy, and the cache size when the wheel is fetched without it.

## Consequence

The cloud can run and unit-test the C3 / C4 operation library on synthetic inputs without the user's PC [D110].
The kernel runs as `venv/bin/python script.py -- args`, one blend file per process. Next cards: C2 `parts.json`
schema, C3 invariant checks. Not decided here: where the venv lives in the repository and the CI or setup-script
route to create it.
