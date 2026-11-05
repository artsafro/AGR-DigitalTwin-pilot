"""elv-tc-vpm: Eevee pictures of the TEXTURED whole building (UDIM maps through the Principled BSDF), day or night.
Read-only on the blend; render-only ground / sun / lamps are never saved.

blender -b <elv_full_v004_tex.blend> --python render_tex_full.py -- <out_dir> <prefix> day|night <lights.json> [view ...]
day:   sky + sun; views ne se sw nw (render_full.py cameras), s14 (render_tex.py 'booklet'), s15 s16 s17.
night: dark world; the glow faces emit through ERM R (material); RENDER-ONLY lamps at the housings stand in for the
       light the luminaires throw on the facade (the real light sources are the user's _Light.fbx, later):
       parapet lines wash down, belt lines wash up, canopy lines down, TUBE M up + down, DECO out-down, FOCUS / PLAT up.
       views n38_1..3 (sheet 38 'Общий вид 1-3'), n39_4 n39_5 (sheet 39), n36_1 n36_3, n37_1 n37_2 n37_3 (close-ups).
Cameras matched by eye to the booklet renders (they are a reference only). Never overwrites.
"""
import bpy, bmesh, sys, os, math, json
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
argv = sys.argv[sys.argv.index("--") + 1:]
out_dir, prefix, mode, lights_p = argv[0], argv[1], argv[2], argv[3]
DAY = ["ne", "se", "sw", "nw", "s14", "s15", "s16", "s17"]
NIGHT = ["n38_1", "n38_2", "n38_3", "n39_4", "n39_5", "n36_1", "n36_3", "n37_1", "n37_2", "n37_3"]
views = argv[4:] or (DAY if mode == "day" else NIGHT)
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 48 if mode == "day" else 64
for a in ("use_raytracing",):
    if hasattr(sc.eevee, a):
        setattr(sc.eevee, a, True)
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
gmat = bpy.data.materials.new("ground_render_only")
gmat.use_nodes = True
gp = gmat.node_tree.nodes["Principled BSDF"]
gp.inputs["Roughness"].default_value = 0.85
gm.materials.append(gmat)
sc.collection.objects.link(bpy.data.objects.new("ground_render_only", gm))


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
    spec = json.load(open(os.path.join(HERE, "tex_spec_v002.json"), encoding="utf-8"))
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
            # area lamps of <= 2 m along the strip, aimed along the wall (wash), 5 cm in front of the lens
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


def look(loc, target, lens=35, res=(2400, 1500), shift_y=0.0):
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cam_data.lens = lens
    cam_data.clip_end = 3000
    cam_data.shift_y = shift_y
    cam_data.sensor_fit = "HORIZONTAL"
    cam_data.sensor_width = 36
    sc.render.resolution_x, sc.render.resolution_y = res


B = dict(res=(1690, 950))
VIEWS = {
    "ne": dict(loc=(135, 55, 45), target=(35, -24, 4), lens=35),
    "se": dict(loc=(135, -110, 45), target=(35, -24, 4), lens=35),
    "sw": dict(loc=(-60, -110, 45), target=(35, -24, 4), lens=35),
    "nw": dict(loc=(-60, 55, 45), target=(35, -24, 4), lens=35),
    "s14": dict(loc=(154.0, -23.73, 1.6), target=(76.0, -23.73, 1.6), lens=36.6, shift_y=0.128, **B),
    "s15": dict(loc=(112, -98, 1.6), target=(52, -40, 7.0), lens=30, shift_y=0.10, **B),
    "s16": dict(loc=(-55, -74, 1.6), target=(-6, -31, 7.0), lens=30, shift_y=0.10, **B),
    "s17": dict(loc=(118, 48, 1.6), target=(58, -4, 7.0), lens=30, shift_y=0.10, **B),
    "n38_1": dict(loc=(-48, 48, 5.0), target=(18, 0, 7.0), lens=28, **B),
    "n38_2": dict(loc=(150, -23.7, 3.0), target=(76, -23.7, 7.5), lens=32, **B),
    "n38_3": dict(loc=(-28, -84, 4.0), target=(30, -50, 7.0), lens=28, **B),
    "n39_4": dict(loc=(128, -108, 26), target=(50, -26, 5.0), lens=30, **B),
    "n39_5": dict(loc=(138, 52, 26), target=(50, -22, 5.0), lens=30, **B),
    "n36_1": dict(loc=(-7, -63, 1.7), target=(16, -50.5, 4.5), lens=24, **B),
    "n36_3": dict(loc=(-4, -57, 1.6), target=(40, -50.5, 12.5), lens=24, **B),
    "n37_1": dict(loc=(96, -23.7, 1.7), target=(75, -23.7, 3.6), lens=24, **B),
    "n37_2": dict(loc=(93, -40, 2.0), target=(78, -29, 9.0), lens=30, **B),
    "n37_3": dict(loc=(-24, -32, 1.7), target=(0, -32, 3.2), lens=24, **B),
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
