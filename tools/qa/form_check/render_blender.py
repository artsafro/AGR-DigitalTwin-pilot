"""Form check v1 - neutral judge renders (Blender workbench, read-only import, never saves).

Same look as the #41 rig: untextured grey (0.8), studio light, cavity on, white background, orthographic.
The scene is cropped by bisecting at the six crop-box planes (no caps), so both variants of a pair are cut and
framed identically. One PNG per panel; `compose` in `pairs.py` builds the labelled 2x2 judge image.

usage: blender -b --factory-startup --python render_blender.py -- <in.fbx> <out_dir> <spec.json>
spec: {"crop": [x0, y0, z0, x1, y1, z1] | "bbox", "name_re": "..." | null, "x_offset": [dx, dy, dz] | null,
       "panels": [{"name": "V1", "dir": [dx, dy, dz]}, ...]}   (dir = view direction, from camera to scene)

new-case: tools/qa/form_check/render_blender.py - form check v1 neutral judge renders
"""
import json
import math
import re
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
fbx, out_dir, spec = argv[0], argv[1], json.load(open(argv[2], encoding="utf-8"))
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=fbx)
name_re = re.compile(spec["name_re"]) if spec.get("name_re") else None
objs = [o for o in bpy.context.scene.objects if o.type == "MESH" and (name_re is None or name_re.search(o.name))]
obj_names = [o.name for o in objs]
off = Vector(spec.get("x_offset") or (0, 0, 0))
bm = bmesh.new()
for o in objs:
    tmp = bmesh.new()
    tmp.from_mesh(o.data)
    tmp.transform(o.matrix_world)
    tmp.transform(Matrix.Translation(off))
    me = bpy.data.meshes.new("tmp")
    tmp.to_mesh(me)
    tmp.free()
    bm.from_mesh(me)
for o in list(bpy.context.scene.objects):
    bpy.data.objects.remove(o, do_unlink=True)
if spec["crop"] == "bbox":
    vs = [v.co for v in bm.verts]
    x0, y0, z0 = (min(c[i] for c in vs) for i in range(3))
    x1, y1, z1 = (max(c[i] for c in vs) for i in range(3))
else:
    x0, y0, z0, x1, y1, z1 = spec["crop"]
    for co, no in (((x0, 0, 0), (-1, 0, 0)), ((x1, 0, 0), (1, 0, 0)), ((0, y0, 0), (0, -1, 0)),
                   ((0, y1, 0), (0, 1, 0)), ((0, 0, z0), (0, 0, -1)), ((0, 0, z1), (0, 0, 1))):
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=co, plane_no=no,
                               clear_outer=True)
me = bpy.data.meshes.new("FormCheckCrop")
bm.to_mesh(me)
nfaces = len(bm.faces)
bm.free()
ob = bpy.data.objects.new("FormCheckCrop", me)
bpy.context.scene.collection.objects.link(ob)
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light, sh.color_type, sh.single_color = "STUDIO", "SINGLE", (0.8, 0.8, 0.8)
sh.show_cavity, sh.cavity_type = True, "BOTH"
sh.background_type = "VIEWPORT"
sh.background_color = (1.0, 1.0, 1.0)
sc.render.film_transparent = False
sc.render.resolution_x, sc.render.resolution_y = 1200, 700
cam = bpy.data.objects.new("FormCheckCam", bpy.data.cameras.new("FormCheckCam"))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.type = "ORTHO"
centre = Vector(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
corners = [Vector((x, y, z)) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
diag = (Vector((x1, y1, z1)) - Vector((x0, y0, z0))).length
asp = sc.render.resolution_y / sc.render.resolution_x
rows = {}
for p in spec["panels"]:
    d = Vector(p["dir"]).normalized()
    cam.location = centre - d * (diag + 5)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    cam.data.clip_start, cam.data.clip_end = 0.01, 2 * diag + 20
    bpy.context.view_layer.update()
    inv = cam.matrix_world.inverted()
    loc = [inv @ c for c in corners]
    span_x = max(v.x for v in loc) - min(v.x for v in loc)
    span_y = max(v.y for v in loc) - min(v.y for v in loc)
    cam.data.ortho_scale = max(span_x, span_y / asp) * 1.05
    sc.render.filepath = f"{out_dir}/{p['name']}.png"
    bpy.ops.render.render(write_still=True)
    rows[p["name"]] = {"dir": list(d), "ortho_scale": cam.data.ortho_scale}
json.dump({"fbx": fbx, "objects": obj_names, "faces_after_crop": nfaces, "panels": rows},
          open(f"{out_dir}/render.json", "w"), indent=1)
print("FORMCHECK_RENDER", nfaces, list(rows))
