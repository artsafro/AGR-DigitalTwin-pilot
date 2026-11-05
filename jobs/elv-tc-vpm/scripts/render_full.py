"""elv-tc-vpm: Workbench pictures of the whole building (flat RAL colours per material ID). Read-only on the blend.

blender -b <full.blend> --python render_full.py -- <out_dir> <prefix> [view ...]
views: south east north west ne sw nw se top s15 s16 s17 (default: all but s15-17)
Never overwrites: an existing picture stops the run. A render-only ground plane at -0.002 hides the 1 m drop.
"""
import bpy, bmesh, sys, os
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
out_dir, prefix = argv[0], argv[1]
views = argv[2:] or ["south", "east", "north", "west", "ne", "sw", "nw", "se", "top"]
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
sc.world = sc.world or bpy.data.worlds.new("W")
sc.world.color = (0.80, 0.83, 0.86)
sc.view_settings.view_transform = "Standard"
for o in sc.objects:
    if o.name.endswith("MainGlass"):
        for m in o.data.materials:
            m.diffuse_color = (m.diffuse_color[0], m.diffuse_color[1], m.diffuse_color[2], 0.35)
gm = bpy.data.meshes.new("ground_render_only")
bm = bmesh.new()
vs = [bm.verts.new(c) for c in ((-80, -140, -0.002), (160, -140, -0.002), (160, 80, -0.002), (-80, 80, -0.002))]
bm.faces.new(vs)
bm.to_mesh(gm)
gmat = bpy.data.materials.new("ground_render_only")
gmat.diffuse_color = (0.55, 0.56, 0.55, 1.0)
gm.materials.append(gmat)
gob = bpy.data.objects.new("ground_render_only", gm)
sc.collection.objects.link(gob)
cam_data = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam


def look(loc, target, lens=35, ortho=None, res=(2400, 1500), shift_y=0.0, ground=True):
    cam.location = Vector(loc)
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    cam_data.type = "ORTHO" if ortho else "PERSP"
    if ortho:
        cam_data.ortho_scale = ortho
    else:
        cam_data.lens = lens
    cam_data.clip_end = 3000
    cam_data.shift_y = shift_y
    cam_data.sensor_fit = "HORIZONTAL"
    cam_data.sensor_width = 36
    sc.render.resolution_x, sc.render.resolution_y = res
    gob.hide_render = not ground


C = (35.0, -24.0)
VIEWS = {
    "south": dict(loc=(35, -200, 7.5), target=(35, -24, 7.5), ortho=94, res=(3000, 700)),
    "north": dict(loc=(35, 150, 7.5), target=(35, -24, 7.5), ortho=94, res=(3000, 700)),
    "east": dict(loc=(220, -24, 7.5), target=(35, -24, 7.5), ortho=60, res=(2400, 800)),
    "west": dict(loc=(-150, -24, 7.5), target=(35, -24, 7.5), ortho=60, res=(2400, 800)),
    "ne": dict(loc=(135, 55, 45), target=(35, -24, 4), lens=35),
    "se": dict(loc=(135, -110, 45), target=(35, -24, 4), lens=35),
    "sw": dict(loc=(-60, -110, 45), target=(35, -24, 4), lens=35),
    "nw": dict(loc=(-60, 55, 45), target=(35, -24, 4), lens=35),
    "top": dict(loc=(35, -24, 200), target=(35, -23.99, 0), ortho=95, res=(2400, 1500)),
    # booklet render cameras (matched by eye, eye height 1.6 m): sheet 15 "Вид 2" from SE, 16 "Вид 3" from SW
    # (west facade with the gates), 17 "Вид 4" from NE
    "s15": dict(loc=(112, -98, 1.6), target=(52, -40, 7.0), lens=30, res=(1690, 950), shift_y=0.10),
    "s16": dict(loc=(-55, -74, 1.6), target=(-6, -31, 7.0), lens=30, res=(1690, 950), shift_y=0.10),
    "s17": dict(loc=(118, 48, 1.6), target=(58, -4, 7.0), lens=30, res=(1690, 950), shift_y=0.10),
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
