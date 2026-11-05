"""elv-tc-vpm: orthographic workbench renders of the customer blank FBX and our delivery FBX in one frame.

blender -b --factory-startup --python customer_overlay_render_v001.py -- <theirs.fbx> <ours.fbx> <out_dir> [dx dy dz]
Theirs is moved by -(object location) (their origin sits on the MSK point) and then by (dx, dy, dz) if given.
Writes <view>_theirs.png / <view>_ours.png for top, S(-Y), N(+Y), E(+X), W(-X); UCX hidden. Read-only on inputs.
"""
import bpy, sys, os, math
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
theirs, ours, out = argv[0], argv[1], argv[2]
shift = Vector([float(x) for x in argv[3:6]]) if len(argv) >= 6 else Vector((0, 0, 0))
os.makedirs(out, exist_ok=True)
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)


def imp(path, tag):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        o["tag"] = tag
        if o.name.startswith("UCX_"):
            o.hide_render = True
    return new


T = imp(theirs, "theirs")
for o in T:
    o.location = shift.copy()
O = imp(ours, "ours")
bpy.context.view_layer.update()
pts = [o.matrix_world @ Vector(c) for o in T + O if o.type == "MESH" and not o.name.startswith("UCX_") for c in o.bound_box]
lo = Vector([min(p[i] for p in pts) for i in range(3)])
hi = Vector([max(p[i] for p in pts) for i in range(3)])
ctr = (lo + hi) / 2
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "STUDIO"
sh.color_type = "SINGLE"
sh.single_color = (0.8, 0.8, 0.8)
sh.show_object_outline = False
sh.show_cavity = True
sh.cavity_type = "WORLD"
sc.world = bpy.data.worlds.new("W") if not sc.world else sc.world
sc.world.color = (1, 1, 1)
sc.render.film_transparent = False
sc.view_settings.view_transform = "Standard"
cam_data = bpy.data.cameras.new("C")
cam_data.type = "ORTHO"
cam = bpy.data.objects.new("C", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam
PXM = 20  # px per metre
pad = 2.0
views = {
    "top": (Vector((ctr.x, ctr.y, hi.z + 50)), (0, 0, 0), hi.x - lo.x, hi.y - lo.y),
    "S_minusY": (Vector((ctr.x, lo.y - 50, ctr.z)), (math.pi / 2, 0, 0), hi.x - lo.x, hi.z - lo.z),
    "N_plusY": (Vector((ctr.x, hi.y + 50, ctr.z)), (math.pi / 2, 0, math.pi), hi.x - lo.x, hi.z - lo.z),
    "E_plusX": (Vector((hi.x + 50, ctr.y, ctr.z)), (math.pi / 2, 0, math.pi / 2), hi.y - lo.y, hi.z - lo.z),
    "W_minusX": (Vector((lo.x - 50, ctr.y, ctr.z)), (math.pi / 2, 0, -math.pi / 2), hi.y - lo.y, hi.z - lo.z),
}
info = {}
for name, (loc, rot, w, h) in views.items():
    w += 2 * pad
    h += 2 * pad
    cam.location = loc
    cam.rotation_euler = rot
    cam_data.ortho_scale = max(w, h)
    cam_data.clip_end = 1000
    sc.render.resolution_x = int(round(w * PXM)) if w >= h else int(round(w * PXM))
    sc.render.resolution_y = int(round(h * PXM))
    sc.render.resolution_percentage = 100
    for tag in ("theirs", "ours"):
        for o in T + O:
            o.hide_render = (o.get("tag") != tag) or o.name.startswith("UCX_")
        sc.render.filepath = os.path.join(out, f"{name}_{tag}.png")
        bpy.ops.render.render(write_still=True)
    info[name] = {"cam": list(loc), "w_m": w, "h_m": h, "px_per_m": PXM}
import json
json.dump({"bbox_union": [list(lo), list(hi)], "shift_theirs": list(shift), "views": info},
          open(os.path.join(out, "views.json"), "w"), indent=1)
print("DONE", out)
