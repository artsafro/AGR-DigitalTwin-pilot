"""elv-tc-vpm: Workbench pictures of the pilot build (flat material colours, light background). Read-only on the blend.

blender -b <pilot.blend> --python render_pilot.py -- <out_dir> <prefix> [view ...]
views: east, ne, se, entrance, booklet, south, top  (default: east ne se entrance booklet)
Never overwrites: an existing picture stops the run.
"""
import bpy, sys, os, math
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
out_dir, prefix = argv[0], argv[1]
views = argv[2:] or ["east", "ne", "se", "entrance", "booklet"]
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "STUDIO"
sh.color_type = "MATERIAL"
sh.show_object_outline = False
sh.show_cavity = True
sh.cavity_type = "WORLD"
sh.show_specular_highlight = False
sh.show_backface_culling = False
sc.display.render_aa = "16"
sc.render.film_transparent = False
sc.world = sc.world or bpy.data.worlds.new("W")
sc.world.color = (0.80, 0.83, 0.86)  # light background (linear)
sc.view_settings.view_transform = "Standard"
glass = [o for o in sc.objects if o.name.endswith("MainGlass")]
for o in glass:
    for m in o.data.materials:
        m.diffuse_color = (m.diffuse_color[0], m.diffuse_color[1], m.diffuse_color[2], 0.35)
sh.show_xray = False
# render-only ground at 0.000 (hides the 1 m perimeter drop; not saved, the blend is never written)
import bmesh  # noqa: E402
gm = bpy.data.meshes.new("ground_render_only")
bm = bmesh.new()
vs = [bm.verts.new(c) for c in ((0, -120, -0.002), (160, -120, -0.002), (160, 70, -0.002), (0, 70, -0.002))]
bm.faces.new(vs)
bm.to_mesh(gm)
gmat = bpy.data.materials.new("ground_render_only")
gmat.diffuse_color = (0.55, 0.56, 0.55, 1.0)
gm.materials.append(gmat)
sc.collection.objects.link(bpy.data.objects.new("ground_render_only", gm))

cam_data = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam


def look(loc, target, lens=35, ortho=None, res=(2400, 1500), shift_y=0.0):
    cam.location = Vector(loc)
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    if ortho:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = ortho
    else:
        cam_data.type = "PERSP"
        cam_data.lens = lens
    cam_data.clip_end = 2000
    cam_data.shift_y = shift_y
    cam_data.sensor_fit = "HORIZONTAL"
    cam_data.sensor_width = 36
    sc.render.resolution_x, sc.render.resolution_y = res


# booklet sheet 14 "Вид 1": frontal east view from the parking axis, eye height ~1.6 m, building 54 m over ~73 %
# of the frame width -> camera 75 m east of the facade, 36.6 mm lens, horizon lowered with shift_y.
VIEWS = {
    "east": dict(loc=(160, -23.7, 6.5), target=(70, -23.7, 6.5), ortho=58, res=(2600, 900)),
    "ne": dict(loc=(128, 22, 3.0), target=(77, -21, 6.0), lens=32),
    "se": dict(loc=(128, -70, 3.0), target=(77, -27, 6.0), lens=32),
    "entrance": dict(loc=(88.5, -16.5, 3.2), target=(73.5, -24.5, 3.0), lens=30),
    "booklet": dict(loc=(154.0, -23.73, 1.6), target=(76.0, -23.73, 1.6), lens=36.6, res=(1690, 950), shift_y=0.128),
    "south": dict(loc=(58, -140, 6.5), target=(58, -50, 6.5), ortho=40, res=(2600, 900)),
    "top": dict(loc=(60, -24, 120), target=(60, -23.99, 0), ortho=62, res=(2000, 1600)),
}
os.makedirs(out_dir, exist_ok=True)
for v in views:
    p = os.path.join(out_dir, f"{prefix}_{v}.png")
    if os.path.exists(p):
        raise SystemExit("output exists: " + p)
    look(**VIEWS[v])
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    print("RENDER", p)
