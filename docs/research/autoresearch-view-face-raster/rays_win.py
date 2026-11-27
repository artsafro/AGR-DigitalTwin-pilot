"""Blender headless: orthographic ray-cast per facade azimuth -> window-hit column profile (#141, OBSERVE).

Usage: blender -b --factory-startup <model.blend> -P rays_win.py -- <out.npz> <m_per_px> <az,az,...>
az = outward facade normal azimuth in the model frame (0 = +X, 90 = +Y). Screen right = (-n) x Z.
A pixel is a window hit when the first surface hit belongs to an object named WINDOW_*.
Opens the model read-only (never saves).
"""
import math
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
out, res, azs = argv[0], float(argv[1]), [float(a) for a in argv[2].split(",")]
dg = bpy.context.evaluated_depsgraph_get()
verts, tris, owner = [], [], []
for ob in bpy.context.scene.objects:
    if ob.type != "MESH" or ob.hide_render:
        continue
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    off = len(verts)
    mw = ob.matrix_world
    verts += [tuple(mw @ v.co) for v in me.vertices]
    for t in me.loop_triangles:
        tris.append(tuple(off + i for i in t.vertices))
        owner.append(1 if ob.name.upper().startswith("WINDOW") else 0)
    ev.to_mesh_clear()
V = np.array(verts)
OWN = np.array(owner, np.int8)
bvh = BVHTree.FromPolygons([Vector(v) for v in verts], tris)
lo, hi = V.min(0), V.max(0)
print("RAYS tris", len(tris), "window tris", int(OWN.sum()), "bbox", lo.round(3).tolist(), hi.round(3).tolist())
result = {"res": np.array(res), "az": np.array(azs)}
for az in azs:
    n = np.array([math.cos(math.radians(az)), math.sin(math.radians(az)), 0.0])
    right = np.cross(-n, [0, 0, 1.0])
    us = V @ right
    u0, u1 = us.min(), us.max()
    z0, z1 = lo[2], hi[2]
    W, H = int(math.ceil((u1 - u0) / res)) + 1, int(math.ceil((z1 - z0) / res)) + 1
    hitmap = np.zeros((H, W), np.int8)  # 0 miss, 1 wall, 2 window
    start = (V @ n).max() + 1.0
    d = Vector(tuple(-n))
    for j in range(H):
        z = z1 - (j + 0.5) * res
        for i in range(W):
            p = n * start + right * (u0 + (i + 0.5) * res)
            hit = bvh.ray_cast(Vector((p[0], p[1], z)), d)
            if hit[0] is not None:
                hitmap[j, i] = 2 if OWN[hit[2]] else 1
    key = f"az{int(round(az)) % 360:03d}"
    result[key + "_hit"] = hitmap
    print("RAYS", key, W, H, "hit%", round(float((hitmap > 0).mean() * 100), 1),
          "win%", round(float((hitmap == 2).mean() * 100), 2))
np.savez_compressed(out, **result)
print("RAYS saved", out)
