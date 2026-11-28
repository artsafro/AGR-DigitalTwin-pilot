"""Dump the render mesh and the UCX meshes of an FBX (world metres) for `agr ucx --simplify-report` (#2097).

Pattern: n/a | new-case: read-only Blender FBX -> npz triangle dump for a CPython measurement.

    blender --background --factory-startup --python-exit-code 1 \
        --python tools/blender/ucx_mesh_dump.py -- <in.fbx> <meta.json> <meshes.npz>

Program: Blender, headless (why: the FBX importer; the report itself runs in CPython with numpy). Read-only on the
FBX; writes only the two given outputs. Import as `tools/blender/fbx_readback.py` (bake_space_transform=True).
meta.json: {ok, model_meshes, ucx: [names], model_triangles}; meshes.npz: model_verts, model_tris, ucx_verts,
ucx_tris, ucx_vert_offsets, ucx_tri_offsets (CSR by UCX object, in meta order).
"""
import json
import sys
from pathlib import Path

import bpy
import numpy as np

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if len(args) != 3:
    print("UCX_MESH_DUMP refused: usage -- <in.fbx> <meta.json> <meshes.npz>", file=sys.stderr)
    sys.exit(4)
src, meta_path, npz_path = (Path(a).resolve() for a in args)
if src in (meta_path, npz_path) or meta_path == npz_path:
    print("UCX_MESH_DUMP refused: an output aliases the input", file=sys.stderr)
    sys.exit(4)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(src), bake_space_transform=True, use_image_search=False)


def world(obj):
    me = obj.data
    me.calc_loop_triangles()
    mw = obj.matrix_world
    v = np.array([tuple(mw @ p.co) for p in me.vertices], float).reshape(-1, 3)
    t = np.array([tuple(x.vertices) for x in me.loop_triangles], np.int64).reshape(-1, 3)
    return v, t


model_v, model_t, names, uv, ut, voff, toff = [], [], [], [], [], [0], [0]
model_names, base = [], 0
for obj in sorted((o for o in bpy.data.objects if o.type == "MESH"), key=lambda o: o.name):
    v, t = world(obj)
    if obj.name.upper().startswith("UCX_"):
        names.append(obj.name)
        uv.append(v)
        ut.append(t)
        voff.append(voff[-1] + len(v))
        toff.append(toff[-1] + len(t))
    else:
        model_names.append(obj.name)
        model_v.append(v)
        model_t.append(t + base)
        base += len(v)

empty_v, empty_t = np.zeros((0, 3)), np.zeros((0, 3), np.int64)
np.savez_compressed(npz_path, model_verts=np.vstack(model_v) if model_v else empty_v,
                    model_tris=np.vstack(model_t) if model_t else empty_t,
                    ucx_verts=np.vstack(uv) if uv else empty_v, ucx_tris=np.vstack(ut) if ut else empty_t,
                    ucx_vert_offsets=np.array(voff), ucx_tri_offsets=np.array(toff))
meta = {"ok": True, "source": str(src), "model_meshes": model_names, "ucx": names,
        "model_triangles": int(sum(len(t) for t in model_t))}
meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
print("UCX_MESH_DUMP", len(model_names), len(names))
