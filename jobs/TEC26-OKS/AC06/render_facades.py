"""new-case: AC06 facade renders (job-local variant of TEC26 renderer) of the delivered VPM and NPM FBX (headless Blender Workbench).

Usage: blender --background --factory-startup --python render_facades.py -- <spec.json> <vpm.fbx> <vpm_textures_dir>
                                                                          <npm.fbx> <new_out_dir>
Per package: 4 orthographic facades (south -Y, east +X, north +Y, west -X) with FLAT lighting (pixel colour = texture
colour, for the VPM-vs-NPM comparison) + one 3/4 STUDIO view. UCX hidden. A red line marks ±0.000.
VPM: the FBX carries no texture paths (reg p.30 §4.2), so the UDIM Diffuse set is attached for preview only.
NPM: the embedded atlas of the FBX is used as imported. Writes <out>/<vpm|npm>_<view>.png and renders.json.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
sys.path.insert(0, HERE)
import vpm_uv  # noqa: E402

spec_p, vfbx, vtex, nfbx, out = sys.argv[sys.argv.index("--") + 1:][:5]
if os.path.lexists(out):
    raise SystemExit(f"refusing to overwrite {out}")
os.makedirs(out)
spec = json.load(open(spec_p, encoding="utf-8"))
VIEWS = {"south": Vector((0, -1, 0)), "east": Vector((1, 0, 0)), "north": Vector((0, 1, 0)), "west": Vector((-1, 0, 0))}
meta = {}


def zero_line(lo, hi):
    pts = [(lo.x - 0.3, lo.y - 0.3, 0), (hi.x + 0.3, lo.y - 0.3, 0), (hi.x + 0.3, hi.y + 0.3, 0),
           (lo.x - 0.3, hi.y + 0.3, 0)]
    cu = bpy.data.curves.new("zero", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 0.01
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for p, c in zip(sp.points, pts):
        p.co = (*c, 1)
    sp.use_cyclic_u = True
    ob = bpy.data.objects.new("zero_line", cu)
    m = bpy.data.materials.new("zero_red")
    m.diffuse_color = (1, 0, 0, 1)
    cu.materials.append(m)
    bpy.context.scene.collection.objects.link(ob)


for tag, fbx in (("vpm", vfbx), ("npm", nfbx)):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    bpy.ops.import_scene.fbx(filepath=fbx)
    meshes = [o for o in sc.objects if o.type == "MESH"]
    for o in meshes:
        if o.name.startswith("UCX_"):
            o.hide_render = True
    vis = [o for o in meshes if not o.name.startswith("UCX_")]
    if tag == "vpm":
        mat = vpm_uv.main_material(bpy, spec, vtex)
        for o in vis:
            if o.name.endswith("_MainGlass"):
                continue  # Preserve map-free glass; do not attach the opaque UDIM.
            o.data.materials.clear()
            o.data.materials.append(mat)
    pts = [o.matrix_world @ v.co for o in vis for v in o.data.vertices]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    zero_line(lo, hi)
    c = (lo + hi) / 2
    size = (hi - lo).length
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.color_type = "TEXTURE"
    sc.display.shading.background_type = "WORLD"
    sc.display.shading.show_backface_culling = False
    sc.view_settings.view_transform = "Standard"
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    sc.render.image_settings.file_format = "PNG"
    sc.world = bpy.data.worlds.new("w")
    sc.world.color = (1, 1, 1)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = "ORTHO"
    cam.data.clip_end = size * 10
    shots = {k: (d, "FLAT") for k, d in VIEWS.items()}
    shots["iso"] = (Vector((1, -1.3, 0.8)).normalized(), "STUDIO")
    for name, (d, light) in shots.items():
        sc.display.shading.light = light
        ext = hi - lo  # fit width and height of this view (16:9 frame), 8 % margin
        wide = abs(d.x) * ext.y + abs(d.y) * ext.x if name != "iso" else size
        cam.data.ortho_scale = max(wide, ext.z * 16 / 9 if name != "iso" else size) * 1.08
        cam.location = c + d * size * 3
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        path = os.path.join(out, f"{tag}_{name}.png")
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
    meta[tag] = {"fbx": os.path.abspath(fbx), "objects": [o.name for o in meshes],
                 "bbox": [list(lo), list(hi)]}
json.dump(meta, open(os.path.join(out, "renders.json"), "w", encoding="utf-8"), indent=1)
print("RENDERS", json.dumps(meta))
