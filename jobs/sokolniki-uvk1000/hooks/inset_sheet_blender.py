"""#1784 step 3 hook (stage `body`, point `after`), Blender side: straight elevations for the v005 | v006 | Revit sheet.

Pattern: n/a | new-case: evidence-only workbench renders (no model edits, never saves a .blend). One orthographic
camera per facade, looking at it from outside; everything more than `front_m` in front of the facade plane is clipped
(so the other wings do not hide it) and nothing behind it is. Plus one iso view.

    blender44 -b --factory-startup --python jobs/sokolniki-uvk1000/hooks/inset_sheet_blender.py -- \
        MODEL(.blend|.fbx) VIEWS.json NEW_OUT_DIR TAG

VIEWS.json: {"front_m": 3.0, "px_per_m": 14, "facades": [{"id", "a": [x, y], "t": [tx, ty], "n": [nx, ny],
"s": [s0, s1], "z": [z0, z1]}], "iso": {"target": [x, y, z], "dir": [dx, dy, dz], "scale": m}}.
Writes NEW_OUT_DIR/<TAG>_<id>.png and <TAG>_iso.png.
"""
import json
import math
import os
import sys

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402


def setup(tag):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "SINGLE" if tag == "revit" else "MATERIAL"
    sh.single_color = (0.78, 0.78, 0.76)
    sh.show_cavity = True
    sh.show_object_outline = True
    sh.show_backface_culling = False
    sc.render.film_transparent = False
    sc.world = sc.world or bpy.data.worlds.new("W")
    sc.render.image_settings.file_format = "PNG"
    cam = bpy.data.objects.new("CAM", bpy.data.cameras.new("CAM"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = "ORTHO"
    return sc, cam


def aim(cam, loc, direction):
    cam.location = Vector(loc)
    cam.rotation_euler = Vector(direction).to_track_quat("-Z", "Y").to_euler()


def main(argv):
    src, views_path, out, tag = argv
    os.makedirs(out, exist_ok=True)
    if src.lower().endswith(".blend"):
        bpy.ops.wm.open_mainfile(filepath=src)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=src)
    with open(views_path, encoding="utf-8") as fh:
        views = json.load(fh)
    sc, cam = setup(tag)
    front, ppm = views["front_m"], views["px_per_m"]
    far = 400.0
    for f in views["facades"]:
        s0, s1 = f["s"]
        z0, z1 = f["z"]
        w, h = (s1 - s0) + 4.0, (z1 - z0) + 4.0
        sm, zm = (s0 + s1) / 2.0, (z0 + z1) / 2.0
        a, t, n = f["a"], f["t"], f["n"]
        dist = 60.0
        loc = (a[0] + t[0] * sm + n[0] * dist, a[1] + t[1] * sm + n[1] * dist, zm)
        aim(cam, loc, (-n[0], -n[1], 0.0))
        cam.data.ortho_scale = max(w, h)
        cam.data.clip_start = dist - front
        cam.data.clip_end = far
        sc.render.resolution_x = int(round(w * ppm))
        sc.render.resolution_y = int(round(h * ppm))
        cam.data.sensor_fit = "HORIZONTAL" if w >= h else "VERTICAL"
        sc.render.filepath = os.path.join(out, "%s_%s.png" % (tag, f["id"]))
        bpy.ops.render.render(write_still=True)
    iso = views.get("iso")
    if iso:
        d = Vector(iso["dir"]).normalized()
        aim(cam, Vector(iso["target"]) - d * 300.0, d)
        cam.data.ortho_scale = iso["scale"]
        cam.data.clip_start, cam.data.clip_end = 1.0, 1000.0
        cam.data.sensor_fit = "HORIZONTAL"
        sc.render.resolution_x, sc.render.resolution_y = 1800, 1200
        sc.render.filepath = os.path.join(out, "%s_iso.png" % tag)
        bpy.ops.render.render(write_still=True)
    print("RENDERED", tag, len(views["facades"]) + (1 if iso else 0))


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:])
