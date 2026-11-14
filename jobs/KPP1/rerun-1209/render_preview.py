"""KPP1 rerun [D238] (#1209): workbench preview renders of a built FBX (evidence only, not committed).

Pattern: new-case: preview of the offline KPP1 rerun FBX.

    blender --background --factory-startup --python jobs/KPP1/rerun-1209/render_preview.py -- <model.fbx> <out_prefix>
"""
import math
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=argv[0])
for o in list(bpy.data.objects):
    if o.name.startswith("UCX_"):
        bpy.data.objects.remove(o)
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sc.display.shading.light = "STUDIO"
sc.display.shading.show_cavity = True
sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
sc.collection.objects.link(cam)
sc.camera = cam
for name, az, el in (("SE", -35, 22), ("NW", 145, 22)):
    d = 45.0
    a, e = math.radians(az), math.radians(el)
    cam.location = Vector((d * math.cos(e) * math.sin(a), -d * math.cos(e) * math.cos(a), d * math.sin(e) + 4))
    cam.rotation_euler = (Vector((0, 0, 4)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = f"{argv[1]}_{name}.png"
    bpy.ops.render.render(write_still=True)
