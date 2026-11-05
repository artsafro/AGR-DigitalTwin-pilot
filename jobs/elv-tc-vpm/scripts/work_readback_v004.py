"""elv-tc-vpm: read back the work FBX against the delivered FBX (same vertices, materials, UV area, triangle count).

blender -b --factory-startup --disable-autoexec --python-exit-code 1 --python work_readback_v004.py -- <work.fbx> <delivery.fbx>
"""
import json
import sys
from collections import Counter

import bpy

work, deliv = sys.argv[sys.argv.index("--") + 1:][:2]


def load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    res = {}
    for o in bpy.data.objects:
        if o.type != "MESH" or o.name.startswith("UCX_"):
            continue
        me = o.data
        mw = o.matrix_world
        verts = {tuple(round(c, 4) for c in (mw @ v.co)) for v in me.vertices}
        uv = me.uv_layers.active.data if me.uv_layers else None
        uv_area = 0.0
        if uv:
            for p in me.polygons:
                pts = [uv[i].uv for i in p.loop_indices]
                uv_area += abs(sum(pts[i].x * pts[i - 1].y - pts[i - 1].x * pts[i].y for i in range(len(pts)))) / 2
        res[o.name] = {
            "verts": verts,
            "tris": sum(len(p.vertices) - 2 for p in me.polygons),
            "degrees": dict(Counter(min(len(p.vertices), 5) for p in me.polygons)),
            "materials": [m.name for m in me.materials if m],
            "mat_faces": dict(Counter(me.materials[p.material_index].name for p in me.polygons if me.materials)),
            "uv_area": round(uv_area, 3),
            "uv_layers": [u.name for u in me.uv_layers],
        }
    return res


a, b = load(work), load(deliv)
out = {"objects_work": sorted(a), "objects_delivery_non_ucx": sorted(b), "checks": {}}
for name in sorted(set(a) | set(b)):
    if name not in a or name not in b:
        out["checks"][name] = "missing in one file"
        continue
    x, y = a[name], b[name]
    area_by_mat_equal = None
    out["checks"][name] = {
        "work_degrees": x["degrees"],
        "same_vertex_set": x["verts"] == y["verts"],
        "same_triangle_count": x["tris"] == y["tris"],
        "same_materials": x["materials"] == y["materials"],
        "uv_area_work_vs_delivery": [x["uv_area"], y["uv_area"]],
        "uv_layers": [x["uv_layers"], y["uv_layers"]],
    }
print("WORK_READBACK", json.dumps(out))
