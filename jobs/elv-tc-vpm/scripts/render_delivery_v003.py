"""elv-tc-vpm renders-v003 = render_delivery_v002.py on the delivery-v003 package (stem SM_Elevatornaya_Vl_1_A_001) +
close-up views: c_strip (cover strip, south facade), c_cap1..c_cap4 (interior capsules through the glass at a grazing
angle), c_door30 (west door No 30), c_south (south entrance doors No 4 / 5 / 9). Day only for the close-ups.
v002 header follows.
elv-tc-vpm: visual-acceptance renders of the DELIVERED package (delivery-v002 FBX + its UDIM textures), Eevee.

blender -b --factory-startup --python render_delivery_v002.py -- <package_dir> <out_dir> <prefix> day|night <lights.json> [view ...]

- Imports <package_dir>/SM_Elevatornaya_1A.fbx as delivered (meshes, metres, Z up). The FBX carries no texture paths
  (export strips image nodes, reg p.30 §4.2), so the Main material is rebuilt from the package UDIM maps with the
  project preview tree (jobs/KPP1/scripts/vpm_uv.main_material: ERM R emissive, G rough, B metal; DirectX normal) +
  the same emission wiring as uv_tex_full.py (Emission = Diffuse x ERM R x 6). MainGlass gets vpm_uv.glass_material.
- UCX_ objects are hidden in renders. Imported objects are moved back by the export pivot offset (render-only) so the
  cameras / night lamps of render_full.py / render_tex_full.py (build frame) apply unchanged. Nothing is saved.
- day: sky + sun; ortho elevations south north east west, roof top, perspectives p_se (= booklet sheet 15 camera,
  main facade I-A corner), p_nw (opposite corner), s14 (= booklet sheet 14, main facade front).
- night: dark world; glow faces emit; render-only lamps from <lights.json> as in render_tex_full.py;
  views p_se, p_nw, main (main facade I-A, sheet 38 'Общий вид 2' camera).
Never overwrites.
"""
import bpy, bmesh, sys, os, math, json
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "KPP1", "scripts"))
import vpm_uv  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
pkg, out_dir, prefix, mode, lights_p = argv[:5]
DAY = ["south", "north", "east", "west", "top", "p_se", "p_nw", "s14"]
NIGHT = ["p_se", "p_nw", "main"]
views = argv[5:] or (DAY if mode == "day" else NIGHT)
ADDR = "Elevatornaya_Vl_1_A_001"
OFFSET = Vector((35.1, -24.2535, 0.0))  # delivery-v003 export_meta pivot offset (= v002)
EMIT_K = 6.0
os.makedirs(out_dir, exist_ok=True)
for v in views:
    p = os.path.join(out_dir, f"{prefix}_{v}.png")
    if os.path.exists(p):
        raise SystemExit("output exists: " + p)

# ---------------------------------------------------------------- import the delivered FBX
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.import_scene.fbx(filepath=os.path.join(pkg, f"SM_{ADDR}.fbx"), axis_forward="Y", axis_up="Z",
                         use_custom_normals=True)
sc = bpy.context.scene
imp = [o for o in sc.objects if o.type == "MESH"]
ucx = [o for o in imp if o.name.startswith("UCX_")]
main = bpy.data.objects[f"SM_{ADDR}_Main"]
glass = bpy.data.objects[f"SM_{ADDR}_MainGlass"]
rep = {"imported": len(imp), "ucx": len(ucx), "main_tris": len(main.data.polygons),
       "main_uv": [u.name for u in main.data.uv_layers], "main_mats_fbx": [m.name for m in main.data.materials],
       "glass_mats_fbx": [m.name for m in glass.data.materials],
       "transforms": {o.name: [list(o.location), list(o.rotation_euler), list(o.scale)] for o in (main, glass)}}
for o in imp:
    o.location = o.location + OFFSET
for o in ucx:
    o.hide_render = True
    o.hide_viewport = True
mat = vpm_uv.main_material(bpy, {"address": ADDR}, pkg)
nt = mat.node_tree
bsdf = nt.nodes["Principled BSDF"]
dif = bsdf.inputs["Base Color"].links[0].from_node
sep = bsdf.inputs["Roughness"].links[0].from_node
mul = nt.nodes.new("ShaderNodeMath")
mul.operation = "MULTIPLY"
mul.inputs[1].default_value = EMIT_K
nt.links.new(sep.outputs["Red"], mul.inputs[0])
nt.links.new(mul.outputs["Value"], bsdf.inputs["Emission Strength"])
nt.links.new(dif.outputs["Color"], bsdf.inputs["Emission Color"])
for i in range(len(main.data.materials)):
    main.data.materials[i] = mat
gmat = vpm_uv.glass_material(bpy, {"address": ADDR})
for i in range(len(glass.data.materials)):
    glass.data.materials[i] = gmat
rep["tiled_images"] = {img.name: [t.number for t in img.tiles] for img in bpy.data.images if img.source == "TILED"}
print("IMPORT_REPORT", json.dumps(rep))

# ---------------------------------------------------------------- scene (as render_tex_full.py)
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 48 if mode == "day" else 64
if hasattr(sc.eevee, "use_raytracing"):
    sc.eevee.use_raytracing = True
sc.view_settings.view_transform = "Standard" if mode == "day" else "AgX"
sc.view_settings.look = "None"
sc.view_settings.exposure = 0.0
sc.world = sc.world or bpy.data.worlds.new("W")
sc.world.use_nodes = True
bg = sc.world.node_tree.nodes.get("Background")
gm = bpy.data.meshes.new("ground_render_only")
bm = bmesh.new()
vs = [bm.verts.new(c) for c in ((-150, -200, -0.002), (250, -200, -0.002), (250, 150, -0.002), (-150, 150, -0.002))]
bm.faces.new(vs)
bm.to_mesh(gm)
grm = bpy.data.materials.new("ground_render_only")
grm.use_nodes = True
gp = grm.node_tree.nodes["Principled BSDF"]
gp.inputs["Roughness"].default_value = 0.85
gm.materials.append(grm)
gob = bpy.data.objects.new("ground_render_only", gm)
sc.collection.objects.link(gob)


def lamp(name, kind, loc, direction, energy, color, size=None, spot_deg=None):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = color
    if kind == "AREA":
        ld.shape = "RECTANGLE"
        ld.size, ld.size_y = size
    if kind == "SPOT":
        ld.spot_size = math.radians(spot_deg)
        ld.spot_blend = 0.6
        ld.shadow_soft_size = 0.02
    if hasattr(ld, "use_shadow"):
        ld.use_shadow = True
    o = bpy.data.objects.new(name, ld)
    sc.collection.objects.link(o)
    o.location = Vector(loc)
    o.rotation_euler = Vector(direction).to_track_quat("-Z", "Y").to_euler()
    return o


if mode == "day":
    bg.inputs["Color"].default_value = (0.62, 0.70, 0.80, 1.0)
    bg.inputs["Strength"].default_value = 0.9
    gp.inputs["Base Color"].default_value = (0.09, 0.09, 0.09, 1)
    sun_d = bpy.data.lights.new("sun_render_only", "SUN")
    sun_d.energy = 3.2
    sun_d.angle = math.radians(3)
    sun = bpy.data.objects.new("sun_render_only", sun_d)
    sc.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50), 0, math.radians(65))
else:
    from light_paths import POLYS  # noqa: E402
    bg.inputs["Color"].default_value = (0.010, 0.012, 0.020, 1.0)
    bg.inputs["Strength"].default_value = 1.0
    gp.inputs["Base Color"].default_value = (0.05, 0.05, 0.05, 1)
    LJ = json.load(open(lights_p, encoding="utf-8"))
    spec = json.load(open(os.path.join(HERE, "tex_spec_v003.json"), encoding="utf-8"))
    COLS = {t["ids"][0]: t["rgb"] for t in spec["tiles"] if t.get("emit")}

    def col(gid):
        return tuple((c / 255.0) ** 2.2 for c in COLS[gid])

    def at(pk, u, h, z):
        P = POLYS[pk]
        b, n = P.base(u), P.unit_normal(u)
        return (b[0] + n[0] * h, b[1] + n[1] * h, z), (n[0], n[1], 0.0)

    k = 0
    for r in LJ["runs"]:
        z0, z1 = r["z"]
        zc = 0.5 * (z0 + z1)
        down = zc > 13.0 or zc < 3.5
        for a, b, inner in r["pieces"]:
            n_ = max(1, math.ceil((b - a) / 2.0))
            for i in range(n_):
                u = a + (b - a) * (i + 0.5) / n_
                p, n = at(r["outline"], u, inner + 0.10, zc + (-0.05 if down else 0.05))
                d = (n[0] * 0.25, n[1] * 0.25, -1.0 if down else 1.0)
                lamp(f"L{k}", "AREA", p, d, 70.0 * (b - a) / n_, col(r["glow_id"]), size=((b - a) / n_, 0.05))
                k += 1
    for p in LJ["points"]:
        pos, n = at(p["outline"], p["u"], p["inner"] + 0.12, p["z"])
        c = col(p["glow_id"])
        if p["type"] == "TUBE_M":
            lamp(f"P{k}u", "SPOT", (pos[0], pos[1], pos[2] + 0.12), (n[0] * 0.15, n[1] * 0.15, 1), 25, c, spot_deg=60)
            lamp(f"P{k}d", "SPOT", (pos[0], pos[1], pos[2] - 0.12), (n[0] * 0.15, n[1] * 0.15, -1), 25, c, spot_deg=60)
        elif p["type"] == "DECO":
            lamp(f"P{k}", "SPOT", pos, (n[0], n[1], -0.8), 60, c, spot_deg=35)
        else:
            lamp(f"P{k}", "SPOT", pos, (n[0] * 0.2, n[1] * 0.2, 1), 8 if p["type"] == "PLAT_A4" else 14, c,
                 spot_deg=12 if p["type"] == "PLAT_A4" else 20)
        k += 1
    print("LAMPS", k)

cam_data = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam


def look(loc, target, lens=35, ortho=None, res=(1920, 1080), shift_y=0.0):
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cam_data.type = "ORTHO" if ortho else "PERSP"
    if ortho:
        cam_data.ortho_scale = ortho
    else:
        cam_data.lens = lens
    cam_data.clip_start = 0.1
    cam_data.clip_end = 3000
    cam_data.shift_y = shift_y
    cam_data.sensor_fit = "HORIZONTAL"
    cam_data.sensor_width = 36
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100


VIEWS = {  # build frame (render_full.py / render_tex_full.py cameras)
    "south": dict(loc=(35, -200, 7.5), target=(35, -24, 7.5), ortho=94, res=(1920, 448)),
    "north": dict(loc=(35, 150, 7.5), target=(35, -24, 7.5), ortho=94, res=(1920, 448)),
    "east": dict(loc=(220, -24, 7.5), target=(35, -24, 7.5), ortho=60, res=(1920, 640)),
    "west": dict(loc=(-150, -24, 7.5), target=(35, -24, 7.5), ortho=60, res=(1920, 640)),
    "top": dict(loc=(35, -24, 200), target=(35, -23.99, 0), ortho=95, res=(1920, 1200)),
    "p_se": dict(loc=(112, -98, 1.6), target=(52, -40, 7.0), lens=30, shift_y=0.10),   # booklet sheet 15
    "p_nw": dict(loc=(-48, 48, 5.0), target=(18, 0, 7.0), lens=28),                   # sheet 38 'Общий вид 1'
    "s14": dict(loc=(154.0, -23.73, 1.6), target=(76.0, -23.73, 1.6), lens=36.6, shift_y=0.128),  # sheet 14
    "main": dict(loc=(150, -23.7, 3.0), target=(76, -23.7, 7.5), lens=32),             # sheet 38 'Общий вид 2'
    # v003 close-ups (build frame)
    "c_strip": dict(loc=(9.0, -55.5, 3.2), target=(12.5, -50.46, 4.62), lens=50),
    "c_cap1": dict(loc=(4.4, -51.3, 3.3), target=(7.16, -50.45, 3.62), lens=45),          # S window ELV-01, grazing
    "c_cap2": dict(loc=(54.6, 4.2, 7.3), target=(57.79, 2.9, 7.67), lens=45),             # N window ELV-01, grazing
    "c_cap3": dict(loc=(84.0, -47.0, 8.2), target=(79.0, -38.0, 8.4), lens=40),           # upper CW (pilot), grazing
    "c_cap4": dict(loc=(80.5, -50.0, 1.5), target=(76.3, -41.0, 1.6), lens=35),           # lower CW + glass doors
    "c_door30": dict(loc=(-11.0, -9.0, 1.7), target=(-4.42, -12.36, 1.2), lens=35),       # west door No 30
    "c_south": dict(loc=(17.0, -61.0, 1.8), target=(13.5, -50.46, 2.0), lens=28),        # south entrance No 4 / 5 / 9
    # second pass (the first c_cap1 / c_cap2 / c_door30 cameras were blocked or too close)
    "c_cap1b": dict(loc=(36.6, -51.45, 7.35), target=(40.46, -50.45, 7.67), lens=40),     # S window ELV-01 z 6.90, grazing
    "c_cap2b": dict(loc=(52.5, 4.35, 7.35), target=(57.79, 2.90, 7.67), lens=50),         # N window ELV-01 z 6.90, grazing
    "c_door30b": dict(loc=(-8.5, -15.6, 1.6), target=(-4.42, -12.36, 1.1), lens=30),      # west door No 30 from SW
}
for v in views:
    p = os.path.join(out_dir, f"{prefix}_{v}.png")
    look(**VIEWS[v])
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    print("RENDER", p)
