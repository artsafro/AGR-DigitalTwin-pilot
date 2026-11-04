"""elv-tc-vpm: Eevee pictures of the TEXTURED pilot (UDIM maps through the Principled BSDF). Read-only on the blend.

blender -b <pilot_v002.blend> --python render_tex.py -- <out_dir> <prefix> [view ...]
views: ne, booklet (same cameras as render_pilot.py), corner (SE close-up: wood cassettes over metal cassettes),
       entrance. Never overwrites: an existing picture stops the run. Render-only ground and sun are not saved.
"""
import bpy, sys, os, math
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[sys.argv.index("--") + 1:]
out_dir, prefix = argv[0], argv[1]
views = argv[2:] or ["ne", "booklet", "corner"]
sc = bpy.context.scene
for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try:
        sc.render.engine = eng
        break
    except TypeError:
        continue
try:
    sc.eevee.taa_render_samples = 64
except AttributeError:
    pass
sc.view_settings.view_transform = "Standard"
sc.view_settings.look = "None"
sc.view_settings.exposure = 0.0
sc.world = sc.world or bpy.data.worlds.new("W")
sc.world.use_nodes = True
bg = sc.world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (0.62, 0.70, 0.80, 1.0)
bg.inputs["Strength"].default_value = 0.9
sun_d = bpy.data.lights.new("sun_render_only", "SUN")
sun_d.energy = 3.2
sun_d.angle = math.radians(3)
sun = bpy.data.objects.new("sun_render_only", sun_d)
sc.collection.objects.link(sun)
sun.rotation_euler = (math.radians(50), 0, math.radians(65))  # from the east-south-east, ~40 deg elevation

import bmesh  # noqa: E402
gm = bpy.data.meshes.new("ground_render_only")
bm = bmesh.new()
vs = [bm.verts.new(c) for c in ((0, -120, -0.002), (180, -120, -0.002), (180, 70, -0.002), (0, 70, -0.002))]
bm.faces.new(vs)
bm.to_mesh(gm)
gmat = bpy.data.materials.new("ground_render_only")
gmat.use_nodes = True
gmat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.09, 0.09, 0.09, 1)
gmat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
gm.materials.append(gmat)
sc.collection.objects.link(bpy.data.objects.new("ground_render_only", gm))

cam_data = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam


def look(loc, target, lens=35, res=(2400, 1500), shift_y=0.0):
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cam_data.type = "PERSP"
    cam_data.lens = lens
    cam_data.clip_end = 2000
    cam_data.shift_y = shift_y
    cam_data.sensor_fit = "HORIZONTAL"
    cam_data.sensor_width = 36
    sc.render.resolution_x, sc.render.resolution_y = res


VIEWS = {  # ne / booklet / entrance = render_pilot.py cameras
    "ne": dict(loc=(128, 22, 3.0), target=(77, -21, 6.0), lens=32),
    "booklet": dict(loc=(154.0, -23.73, 1.6), target=(76.0, -23.73, 1.6), lens=36.6, res=(1690, 950), shift_y=0.128),
    "entrance": dict(loc=(88.5, -16.5, 3.2), target=(73.5, -24.5, 3.0), lens=30),
    "corner": dict(loc=(87.0, -59.0, 2.2), target=(77.0, -48.6, 5.2), lens=40, res=(2000, 1500)),
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
