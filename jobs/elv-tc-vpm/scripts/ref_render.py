"""elv-tc-vpm: Workbench renders of the clean reference scene, colour per category collection.

blender -b elv_ref_clean_v001.blend --python ref_render.py -- <out_dir> [prefix]
Flat light, light background, orthographic iso + 4 facades. Never overwrites existing PNGs.
"""
import bpy, sys, os
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
out_dir = argv[0]; prefix = argv[1] if len(argv) > 1 else "ref_clean_v001_"
COL = {"wall_ext": (0.80, 0.80, 0.76), "curtain_wall": (0.5, 0.7, 0.9), "mullion": (0.20, 0.22, 0.26),
       "glass": (0.55, 0.78, 0.95), "stemalit": (0.10, 0.25, 0.55), "wood_cassette": (0.85, 0.62, 0.35),
       "metal_cassette": (0.32, 0.34, 0.38), "sandwich": (0.55, 0.57, 0.60), "plinth": (0.45, 0.40, 0.36),
       "roof": (0.70, 0.66, 0.60), "parapet_flashing": (0.95, 0.30, 0.20), "rib_lamella": (0.95, 0.80, 0.20),
       "canopy": (0.60, 0.30, 0.70), "door": (0.80, 0.10, 0.20), "window": (0.20, 0.60, 0.80),
       "gate": (0.35, 0.55, 0.25), "railing": (1.0, 0.5, 0.0), "stair_ext": (0.4, 0.7, 0.4),
       "equipment": (0.5, 0.5, 0.2), "lights_arktos": (1.0, 1.0, 0.0), "sign_frame": (0.0, 0.0, 0.0),
       "other": (0.75, 0.75, 0.75)}
sc = bpy.context.scene
mn = Vector((1e9,) * 3); mx = Vector((-1e9,) * 3)
for c in bpy.data.collections:
    for o in c.objects:
        o.color = (*COL.get(c.name, (0.7, 0.7, 0.7)), 1.0)
        for v in o.bound_box:
            for i in range(3):
                mn[i] = min(mn[i], v[i]); mx[i] = max(mx[i], v[i])
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "FLAT"; sh.color_type = "OBJECT"; sh.show_object_outline = True; sh.object_outline_color = (0.1, 0.1, 0.1)
sh.background_type = "VIEWPORT"; sh.background_color = (0.96, 0.96, 0.95)
sc.world = sc.world or bpy.data.worlds.new("W")
sc.world.color = (0.96, 0.96, 0.95)  # Workbench final render uses the world colour as background
sc.display.render_aa = "8"
sc.render.resolution_x = 2400; sc.render.resolution_y = 1350; sc.render.film_transparent = False
sc.view_settings.view_transform = "Standard"
c = (mn + mx) / 2; size = mx - mn
cam_d = bpy.data.cameras.new("C"); cam_d.type = "ORTHO"
cam = bpy.data.objects.new("C", cam_d); sc.collection.objects.link(cam); sc.camera = cam
views = {"east_+X": (Vector((1, 0, 0)), size.y), "west_-X": (Vector((-1, 0, 0)), size.y),
         "south_-Y": (Vector((0, -1, 0)), size.x), "north_+Y": (Vector((0, 1, 0)), size.x),
         "iso_NE": (Vector((1, 0.6, 0.7)).normalized(), size.length * 0.85)}
for name, (d, w) in views.items():
    path = os.path.join(out_dir, prefix + name + ".png")
    if os.path.exists(path):
        print("SKIP exists", path); continue
    cam.location = c + d * 300
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    cam_d.ortho_scale = w * 1.05; cam_d.clip_end = 1000
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("WROTE", path)
