"""Blender headless: orthographic ray-cast Revit TYPE label maps from N horizontal directions (#149, OBSERVE).

Same frame as #139 rays.py (az = outward normal azimuth, 0=+X, 90=+Y; screen right = (-n) x Z). UCX/collision
and >30 m outlier objects are skipped exactly as #145 rays_elv.py. Label = 1 + index into the global Revit type
table (object name minus the trailing instance suffix); 0 = no hit. No saves, no exports.
Usage: blender -b --factory-startup -P rays_type.py -- <model.fbx> <out.npz> <m_per_px> <az,az,...>
"""
import sys, math, json, re
import bpy, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
src, out, res, azs = argv[0], argv[1], float(argv[2]), [float(a) for a in argv[3].split(",")]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src)
dg = bpy.context.evaluated_depsgraph_get()
SUFFIX = re.compile(r"(\.\d{3}|_[0-9a-f]{7}|_?\[\d+\]|\s+)$")


def type_name(name):
    """R1b: Revit type = object name minus trailing _<7 hex>, [<id>], _[<id>], .NNN and spaces (repeated)."""
    prev = None
    while prev != name:
        prev, name = name, SUFFIX.sub("", name)
    return name


verts, tris, tri_lab, types = [], [], [], {}
for ob in sorted(bpy.context.scene.objects, key=lambda o: o.name):
    if ob.type != "MESH" or ob.name.upper().startswith(("UCX_", "UBX_", "USP_", "UCP_", "COLIZ")) or (len(ob.data.vertices) > 0 and max((ob.matrix_world @ v.co).z for v in ob.data.vertices) > 30.0):
        continue
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    off = len(verts)
    mw = ob.matrix_world
    verts += [tuple(mw @ v.co) for v in me.vertices]
    label = types.setdefault(type_name(ob.name), len(types) + 1)
    for t in me.loop_triangles:
        tris.append(tuple(off + i for i in t.vertices))
        tri_lab.append(label)
    ev.to_mesh_clear()
V = np.array(verts)
TL = np.array(tri_lab, np.int32)
bvh = BVHTree.FromPolygons([Vector(v) for v in verts], tris)
lo, hi = V.min(0), V.max(0)
print("RAYST tris", len(tris), "types", len(types), "bbox", lo.round(3).tolist(), hi.round(3).tolist())
result = {"bbox": np.array([lo, hi]), "res": np.array(res), "az": np.array(azs),
          "types": np.array(json.dumps(sorted(types, key=types.get), ensure_ascii=False))}
for az in azs:
    n = np.array([math.cos(math.radians(az)), math.sin(math.radians(az)), 0.0])
    right = np.cross(-n, [0, 0, 1.0])
    us = V @ right
    ds = V @ n
    u0, u1 = us.min(), us.max()
    z0, z1 = lo[2], hi[2]
    W, H = int(math.ceil((u1 - u0) / res)) + 1, int(math.ceil((z1 - z0) / res)) + 1
    lab = np.zeros((H, W), np.int32)
    start = ds.max() + 1.0
    d = Vector(tuple(-n))
    for j in range(H):
        z = z1 - (j + 0.5) * res
        for i in range(W):
            u = u0 + (i + 0.5) * res
            p = n * start + right * u
            hit = bvh.ray_cast(Vector((p[0], p[1], z)), d)
            if hit[0] is not None:
                lab[j, i] = TL[hit[2]]
    key = f"az{int(round(az)) % 360:03d}"
    result[key + "_type"] = lab
    result[key + "_origin"] = np.array([u0, z1])
    print("RAYST", key, W, H, "hit%", round(float((lab > 0).mean() * 100), 1), "labels", len(np.unique(lab)))
np.savez_compressed(out, **result)
print("RAYST saved", out)
