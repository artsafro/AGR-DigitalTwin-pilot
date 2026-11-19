"""Gate-1 pictures of candidate buildings (#1619). new-case: read-only workbench renders for the floor pick list.

blender -b --factory-startup --python render_candidates.py -- IN.fbx BOXES.json OUTDIR
BOXES.json: [{"id": "A", "min": [x, y, z], "max": [x, y, z]}, ...]. Objects whose XY bbox centre lies in a box
are shown for that box; per box: iso views from SE and NW (orthographic, workbench, cavity + outline) and a
site top view with all objects. Never saves the scene; OUTDIR must not contain the input.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

src, boxes_path, outdir = sys.argv[sys.argv.index("--") + 1:]
if os.path.realpath(os.path.dirname(src)) == os.path.realpath(outdir):
    sys.exit("OUTDIR must differ from the input folder")
os.makedirs(outdir, exist_ok=True)
boxes = json.load(open(boxes_path, encoding="utf-8"))
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src)
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "STUDIO"
sh.color_type = "SINGLE"
sh.single_color = (0.85, 0.85, 0.82)
sh.show_cavity = True
sh.show_object_outline = True
sc.render.resolution_x = 1200
sc.render.resolution_y = 1200
sc.render.film_transparent = False
meshes = [o for o in sc.objects if o.type == "MESH"]
centre = {}
for o in meshes:
    cs = [o.matrix_world @ Vector(c) for c in o.bound_box]
    centre[o.name] = (sum(c.x for c in cs) / 8, sum(c.y for c in cs) / 8)
cam_data = bpy.data.cameras.new("cam")
cam_data.type = "ORTHO"
cam = bpy.data.objects.new("cam", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam


def shoot(target, size, direction, path, tilt=0.6):
    d = Vector((direction[0], direction[1], tilt)).normalized()
    cam.location = target + d * 400
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    cam_data.ortho_scale = size
    cam_data.clip_end = 2000
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


for o in meshes:
    o.hide_render = False
lo = Vector([min(b["min"][i] for b in boxes) for i in range(3)])
hi = Vector([max(b["max"][i] for b in boxes) for i in range(3)])
mid = (lo + hi) / 2
shoot(mid, max(hi.x - lo.x, hi.y - lo.y) * 1.15, (0, 0), os.path.join(outdir, "site_top.png"), tilt=1.0)
for b in boxes:
    for o in meshes:
        x, y = centre[o.name]
        o.hide_render = not (b["min"][0] <= x <= b["max"][0] and b["min"][1] <= y <= b["max"][1])
    bl = Vector(b["min"])
    bh = Vector(b["max"])
    c = (bl + bh) / 2
    size = max((bh - bl).length * 0.85, 10)
    for tag, dirn in (("se", (1, -1)), ("nw", (-1, 1))):
        shoot(c, size, dirn, os.path.join(outdir, "bld_%s_%s.png" % (b["id"], tag)))
print("rendered", len(boxes))
