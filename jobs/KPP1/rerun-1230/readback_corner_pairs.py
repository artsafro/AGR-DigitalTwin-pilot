"""#1246 read-back: inside/outside test of the exported VPM FBX at the corner posts and the old fin centres.

Pattern: new-case: Blender read-back witness for the KPP1 #1246 corner-pair fix (agent-owned factory-startup Blender).

    blender --background --factory-startup --python-exit-code 1 --python readback_corner_pairs.py -- <SM_Kpp_1.fbx> <out.json>
"""
import json
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

fbx, out = sys.argv[sys.argv.index("--") + 1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=fbx)
dg = bpy.context.evaluated_depsgraph_get()
trees = []
for ob in bpy.context.scene.objects:
    if ob.type == "MESH":
        me = ob.evaluated_get(dg).to_mesh()
        vs = [ob.matrix_world @ v.co for v in me.vertices]
        trees.append((ob.name, BVHTree.FromPolygons(vs, [p.vertices[:] for p in me.polygons])))


def inside(p):
    for name, t in trees:
        n, o = 0, Vector(p)
        while True:
            hit = t.ray_cast(o, Vector((0.0, 0.0, 1.0)))
            if hit[0] is None:
                break
            n += 1
            o = hit[0] + Vector((0.0, 0.0, 1e-6))
        if n % 2:
            return name
    return None


pts = {"SW post": (-15.03, -5.73, 5.7), "SW old West fin": (-15.13, -5.73, 5.7), "SW old South fin": (-15.03, -5.83, 5.7),
       "NW post": (-15.0303, 6.0196, 5.7), "NW old West fin": (-15.13, 6.0196, 5.7), "NW old North fin": (-15.0303, 6.12, 5.7),
       "S one-view z1.2-2.7 (guessed kept)": (-15.03, -5.83, 2.0)}
res = {k: inside(v) for k, v in pts.items()}
json.dump({"fbx": fbx, "blender": bpy.app.version_string, "points": pts, "inside_object": res}, open(out, "w"), indent=1)
print(res)
