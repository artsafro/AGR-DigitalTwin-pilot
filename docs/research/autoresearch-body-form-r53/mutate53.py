"""Standing #53 positive trigger witness W_deep: on a COPY of accepted 63B v007, move the back-rim vertices of window
6189f94 (ring seg 18, t 5.5946..7.3046 m, d_in 0.50 m, real z 8.47..10.46) inward to d_in 0.71 m. Read-only source.
Frame and axis convention copied from #51 mutate63b.py.
usage: blender -b --factory-startup --python mutate53.py -- <src.fbx> <dst.fbx>"""
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
src, dst = argv
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src)
objs = [x for x in bpy.context.scene.objects if x.type == "MESH"]
A, B = Vector((85.519, 16.334)), Vector((95.936, 27.133))   # ring[18], ring[19] (rounded to mm, see key)
u = (B - A) / (B - A).length
n_in = Vector((-u.y, u.x))           # ring is CCW: interior on the left
E0, E1, D_OLD, D_NEW = 5.5946, 7.3046, 0.50, 0.71
moved = 0
for o in objs:
    mw = o.matrix_world
    inv = mw.inverted()
    for v in o.data.vertices:
        w = mw @ v.co
        p = Vector((w.x, w.y)) - A
        t = p.dot(u)
        d_in = p.dot(n_in)
        if E0 - 0.01 <= t <= E1 + 0.01 and abs(d_in - D_OLD) <= 0.01 and 8.47 <= w.z <= 10.46:
            v.co = inv @ (w + Vector((n_in.x, n_in.y, 0)) * (D_NEW - d_in))
            moved += 1
    o.data.update()
bpy.ops.export_scene.fbx(filepath=dst, use_selection=False, object_types={"MESH"}, apply_unit_scale=True,
                         global_scale=1.0, axis_forward="-Z", axis_up="Y")
print("MUTATE deep moved", moved)
