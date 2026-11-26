"""R109 observation only: the pinned Revit FBX census plus per-object loose-part (layer) records.

blender -b --factory-startup --python docs/research/trainer_layer_r109/layer_dump_blender.py -- SRC.fbx NEW.json

`objects[*]` (name, verts, tris, z, hull) is computed exactly as tools/methods/body/revit_fbx_dump_blender.py
(schema `revit-fbx-dump/1`, same import and object order), so the pinned r105 runner reads it unchanged and the
S107 baseline must reproduce #107 within 1e-6 m. Each object also gets `parts`: its connected vertex components
(Revit exports a compound wall as one solid per layer; Blender's FBX import drops the unnamed per-polygon layer
indices because the bank FBX has zero Material nodes). Per part: vertex count, world AABB, |signed volume|,
surface area and thickness_m = 2*volume/area (slab thickness, rotation invariant). Source-only; never a key
input; never saves a .blend.
"""
import hashlib
import json
import os
import sys

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.geometry import convex_hull_2d  # noqa: E402


def components(n, edges):
    lab = np.arange(n)
    if not len(edges):
        return lab
    a, b = edges[:, 0], edges[:, 1]
    while True:
        m = np.minimum(lab[a], lab[b])
        new = lab.copy()
        np.minimum.at(new, a, m)
        np.minimum.at(new, b, m)
        new = new[new]
        if np.array_equal(new, lab):
            return lab
        lab = new


def parts(me, w):
    ne = len(me.edges)
    e = np.empty(ne * 2, dtype=np.int64)
    me.edges.foreach_get("vertices", e)
    lab = components(len(me.vertices), e.reshape(ne, 2))
    me.calc_loop_triangles()
    nt = len(me.loop_triangles)
    t = np.empty(nt * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("vertices", t)
    t = t.reshape(nt, 3)
    p0, p1, p2 = w[t[:, 0]], w[t[:, 1]], w[t[:, 2]]
    vol = np.einsum("ij,ij->i", p0, np.cross(p1, p2)) / 6.0
    area = np.linalg.norm(np.cross(p1 - p0, p2 - p0), axis=1) / 2.0
    tl = lab[t[:, 0]]
    out = []
    for k in np.unique(lab):
        v = lab == k
        sel = tl == k
        V, A = abs(float(vol[sel].sum())), float(area[sel].sum())
        q = w[v]
        out.append({"verts": int(v.sum()), "tris": int(sel.sum()),
                    "lo": [round(float(x), 4) for x in q.min(0)], "hi": [round(float(x), 4) for x in q.max(0)],
                    "volume_m3": round(V, 6), "area_m2": round(A, 6),
                    "thickness_m": round(2 * V / A, 6) if A > 0 else 0.0})
    return out


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(argv) != 2:
        print("usage (inside Blender 4.4): layer_dump_blender.py -- SRC.fbx NEW.json", file=sys.stderr)
        sys.exit(2)
    src, out = argv
    if os.path.exists(out) or os.path.realpath(out) == os.path.realpath(src):
        print("refused: NEW.json exists or is the input", file=sys.stderr)
        sys.exit(2)
    h = hashlib.sha256()
    with open(src, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=src)
    objs = []
    for ob in bpy.context.scene.objects:
        if ob.type != "MESH":
            continue
        me, mw = ob.data, ob.matrix_world
        n = len(me.vertices)
        rec = {"name": ob.name, "verts": n, "tris": sum(len(p.vertices) - 2 for p in me.polygons)}
        if n:
            co = np.empty(n * 3, dtype=np.float64)
            me.vertices.foreach_get("co", co)
            co = co.reshape(n, 3)
            m = np.array(mw, dtype=np.float64)
            w = co @ m[:3, :3].T + m[:3, 3]
            xy = [Vector((x, y)) for x, y in np.unique(np.round(w[:, :2], 4), axis=0)]
            idx = convex_hull_2d(xy)
            rec["z"] = [round(float(w[:, 2].min()), 4), round(float(w[:, 2].max()), 4)]
            rec["hull"] = [[round(xy[i][0], 4), round(xy[i][1], 4)] for i in idx]
            rec["parts"] = parts(me, w) if ob.name.startswith("Базовая стена ") else []
        else:
            rec["z"], rec["hull"], rec["parts"] = None, [], []
        objs.append(rec)
    doc = {"schema": "revit-fbx-dump/1", "source": os.path.realpath(src), "sha256": h.hexdigest(), "objects": objs}
    with open(out, "x", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)


main()
