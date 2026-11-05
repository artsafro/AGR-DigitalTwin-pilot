"""elv-tc-vpm delivery v004: prove the v004 FBX geometry equals v003 (texture-only change).

blender -b --factory-startup --disable-autoexec --python-exit-code 1 --python compare_fbx_geometry_v004.py -- \
    <v003.fbx> <v004.fbx> <out.json>

Each FBX is imported into an empty scene (clean process state per file); per mesh object: vertex / face / loop counts,
SHA-256 of the vertex coordinates (float32 bytes, file order), of the face corner indices, of the material indices,
of every UV layer (float32 loop UVs) and of the material slot names; transforms. Exit 1 on any difference.
"""
import bpy
import hashlib
import json
import os
import sys

import numpy as np

a, b, out = sys.argv[sys.argv.index("--") + 1:][:3]
if os.path.exists(out):
    raise SystemExit("output exists: " + out)


def h(arr):
    return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()


def snap(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    res = {}
    for o in bpy.context.scene.objects:
        if o.type != "MESH":
            res[o.name] = {"type": o.type}
            continue
        me = o.data
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", co)
        lv = np.empty(len(me.loops), np.int32)
        me.loops.foreach_get("vertex_index", lv)
        ls = np.empty(len(me.polygons), np.int32)
        me.polygons.foreach_get("loop_start", ls)
        mi = np.empty(len(me.polygons), np.int32)
        me.polygons.foreach_get("material_index", mi)
        uvs = {}
        for uvl in me.uv_layers:
            uv = np.empty(len(me.loops) * 2, np.float32)
            uvl.data.foreach_get("uv", uv)
            uvs[uvl.name] = h(uv)
        res[o.name] = {"verts": len(me.vertices), "faces": len(me.polygons), "loops": len(me.loops),
                       "co": h(co), "faces_idx": h(np.concatenate([ls, lv])), "mat_idx": h(mi), "uv": uvs,
                       "materials": [m.name if m else None for m in me.materials],
                       "transform": [round(x, 9) for r in o.matrix_world for x in r]}
    return res


A, B = snap(a), snap(b)
diff = sorted(set(A) ^ set(B)) + sorted(k for k in set(A) & set(B) if A[k] != B[k])
main = [k for k in A if not k.startswith("UCX_")]
rep = {"v003": a, "v004": b, "objects": [len(A), len(B)], "identical": not diff, "differences": diff[:50],
       "summary_non_ucx": {k: {x: A[k][x] for x in ("verts", "faces", "co", "faces_idx", "uv")} for k in main},
       "ucx_objects": sum(k.startswith("UCX_") for k in A),
       "ucx_verts_faces": [sum(A[k]["verts"] for k in A if k.startswith("UCX_")),
                           sum(A[k]["faces"] for k in A if k.startswith("UCX_"))],
       "all_objects_digest": hashlib.sha256(json.dumps(A, sort_keys=True).encode()).hexdigest()}
json.dump(rep, open(out, "w", encoding="utf-8"), indent=1)
print("GEOM_COMPARE", json.dumps({k: rep[k] for k in ("objects", "identical", "differences", "ucx_objects")}))
sys.exit(0 if not diff else 1)
