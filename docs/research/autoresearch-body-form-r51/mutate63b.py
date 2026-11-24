"""Standing #51 positive trigger witnesses: mutate a COPY of the accepted 63B v007 FBX (Blender 5.1, read-only source).
Same logic as t_563a40f7 detector/mutate.py, 63B coordinates (ring of source_sections_and_openings.json, seg 18-19).
mode shift_opening: window 6189f94 (floor +7.80, edges t=5.5946/7.3046 m on seg 18) jamb vertices +0.10 m along the facade.
mode shift_wall:    facade plane of ring seg 18-19 moved 0.10 m outward over the full height.
usage: blender -b --factory-startup --python mutate63b.py -- <src.fbx> <mode> <dst.fbx>"""
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
src, mode, dst = argv
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src)
objs = [x for x in bpy.context.scene.objects if x.type == "MESH"]
A, B = Vector((85.519, 16.334)), Vector((95.936, 27.133))   # ring[18], ring[19] (rounded to mm, see key)
L = (B - A).length
u = (B - A) / L
n_out = Vector((u.y, -u.x))          # ring is CCW (area +714.8 m2): interior on the left, outward = right normal
moved = 0
for o in objs:
    mw = o.matrix_world
    inv = mw.inverted()
    for v in o.data.vertices:
        w = mw @ v.co
        p = Vector((w.x, w.y)) - A
        t = p.dot(u)
        d_in = p.x * u.y * -1 + p.y * u.x   # signed distance to the left (inward) of the ring line
        if mode == "shift_opening":
            if -0.02 <= d_in <= 0.80 and 8.47 <= w.z <= 10.46 and (abs(t - 5.5946) < 0.05 or abs(t - 7.3046) < 0.05):
                v.co = inv @ (w + Vector((u.x, u.y, 0)) * 0.10)
                moved += 1
        elif mode == "shift_wall":
            if abs(d_in) < 0.003 and -0.003 <= t <= L + 0.003:
                v.co = inv @ (w + Vector((n_out.x, n_out.y, 0)) * 0.10)
                moved += 1
        else:
            raise SystemExit("unknown mode " + mode)
    o.data.update()
bpy.ops.export_scene.fbx(filepath=dst, use_selection=False, object_types={"MESH"}, apply_unit_scale=True,
                         global_scale=1.0, axis_forward="-Z", axis_up="Y")
print("MUTATE", mode, "moved", moved)
