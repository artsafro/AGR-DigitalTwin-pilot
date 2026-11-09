"""elv-tc-vpm customer-clarify-v001: Workbench renders of OUR delivery v002 and the customer blank in one frame (ours).

blender -b --factory-startup --python clarify_render_v001.py -- <ours_pkg_dir> <theirs.fbx> <nakl_verts.json> <out_dir>

Variants per view:
  ours_tex    our Main with the delivered UDIM Diffuse (joints are in the texture), glass light cyan
  ours_id     our Main coloured by UDIM tile (= material ID), glass cyan
  theirs_id   customer Main coloured by UDIM tile (1001 reveals, 1002 frames, 1003 fake rooms ...), glass hidden
  theirs_nakl customer Main light grey + the 131 SRC_Накладки outlines as 12 cm thick strips coloured by family
Theirs is placed with location = register shift (-0.064, 0.578, 0) (their object origin = their MSK pivot; mesh is
local to it), exactly as customer_overlay_render_v001.py. Read-only on all inputs; never overwrites.
"""
import bpy, bmesh, sys, os, math, json
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "KPP1", "scripts"))
import vpm_uv  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
pkg, theirs_fbx, nakl_p, out = argv[:4]
only = set(argv[4:])
os.makedirs(out, exist_ok=True)
SHIFT = Vector((-0.064, 0.578, 0.0))
ADDR = "Elevatornaya_1A"
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
sc = bpy.context.scene


def imp(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path, axis_forward="Y", axis_up="Z")
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        if o.name.startswith("UCX_"):
            o.hide_render = True
    return new


def flat(name, rgb, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*[(c / 255.0) ** 2.2 for c in rgb], alpha)
    return m


def tile_of(me, p):
    uv = me.uv_layers.active.data[p.loop_start].uv
    lu = [me.uv_layers.active.data[i].uv for i in range(p.loop_start, p.loop_start + p.loop_total)]
    u = sum(x.x for x in lu) / len(lu)
    v = sum(x.y for x in lu) / len(lu)
    return 1001 + int(math.floor(u)) + 10 * int(math.floor(v))


def colour_by_tile(ob, table, default):
    me = ob.data.copy()
    ob.data = me
    me.materials.clear()
    keys = sorted(table) + ["other"]
    mats = {k: flat(f"{ob.name}_{k}", table.get(k, default)) for k in keys}
    for k in keys:
        me.materials.append(mats[k])
    idx = {k: i for i, k in enumerate(keys)}
    for p in me.polygons:
        t = tile_of(me, p)
        p.material_index = idx[t] if t in idx else idx["other"]
    return me


# ---------------------------------------------------------------- ours
O = imp(os.path.join(pkg, f"SM_{ADDR}.fbx"))
o_main = bpy.data.objects[f"SM_{ADDR}_Main"]
o_glass = bpy.data.objects[f"SM_{ADDR}_MainGlass"]
for o in O:
    o.location = (0, 0, 0)
tex_mat = vpm_uv.main_material(bpy, {"address": ADDR}, pkg)
o_main_tex_mesh = o_main.data
for i in range(len(o_main_tex_mesh.materials)):
    o_main_tex_mesh.materials[i] = tex_mat
gimg = bpy.data.images.new("glass_px", 4, 4)
gimg.pixels = [0.62, 0.80, 0.88, 1.0] * 16
gtex = bpy.data.materials.new("glass_tex")
gtex.use_nodes = True
gn = gtex.node_tree.nodes.new("ShaderNodeTexImage")
gn.image = gimg
gtex.node_tree.nodes.active = gn
gtex.diffuse_color = (0.36, 0.62, 0.74, 1)
for i in range(len(o_glass.data.materials)):
    o_glass.data.materials[i] = gtex
OURS_ID = {  # udim -> colour (tex-v003 uv_layout: ID -> UDIM)
    1001: (110, 112, 118),  # ID01 sandwich 7021
    1002: (70, 72, 78),     # ID02 metal cassette
    1003: (214, 180, 120),  # ID03 wood cassette
    1004: (90, 90, 90),     # ID04 plinth
    1005: (255, 150, 40),   # ID06 reveal 7021
    1006: (255, 60, 60),    # ID11 window W72 frames
    1007: (40, 40, 40),     # ID12 F50 frames
    1008: (40, 90, 220),    # ID13 stemalit 5024
    1009: (200, 40, 200),   # ID14 metal doors
    1010: (120, 120, 120),  # ID16 sign frames
    1011: (190, 150, 90),   # ID17 ribs
    1012: (230, 200, 140), 1013: (60, 130, 140), 1016: (60, 60, 60),  # ID18 flashings
    1014: (240, 210, 150),  # ID19 canopy / soffit
    1015: (170, 170, 165),  # ID21 roof
    1017: (100, 100, 100), 1018: (160, 165, 175), 1019: (80, 80, 80), 1020: (130, 130, 130),
    1021: (120, 110, 100), 1022: (20, 20, 20), 1023: (80, 80, 80),
}
ours_id_mesh = colour_by_tile(o_main, OURS_ID, (150, 150, 150))
o_main.data = o_main_tex_mesh
glass_cyan = flat("glass_cyan", (120, 220, 240))
o_glass_mesh_tex = o_glass.data
o_glass_mesh_id = o_glass.data.copy()
for i in range(len(o_glass_mesh_id.materials)):
    o_glass_mesh_id.materials[i] = glass_cyan

# ---------------------------------------------------------------- theirs
T = imp(theirs_fbx)
for o in T:
    o.location = SHIFT.copy()
t_main = [o for o in T if o.name.endswith("_Main") and not o.name.startswith("UCX_")][0]
t_glass = [o for o in T if o.name.endswith("_MainGlass")]
THEIRS_ID = {
    1001: (255, 150, 40),   # reveals
    1002: (255, 60, 60),    # window / door frames + leaves
    1003: (230, 0, 200),    # fake rooms
    1004: (240, 210, 150),  # soffit
    1005: (170, 170, 165),  # roof + parapet tops
    1006: (214, 180, 120),  # facade wood 1001
    1007: (110, 112, 118),  # facade 7021 sandwich
    1008: (70, 72, 78),     # facade 7024 cassette
    1009: (60, 70, 70), 1010: (70, 70, 80), 1011: (60, 70, 70),
}
theirs_id_mesh = colour_by_tile(t_main, THEIRS_ID, (150, 150, 150))
grey = {k: (205, 205, 205) for k in THEIRS_ID}
grey[1003] = (225, 190, 225)
theirs_grey_mesh = colour_by_tile(t_main, grey, (205, 205, 205))
t_main.data = theirs_id_mesh

# ---------------------------------------------------------------- nakl strips
GROUPS = [  # (key, test(fam, name), rgb)
    ("joint_h", lambda f, n: "FS-8P" in f, (230, 0, 0)),
    ("base", lambda f, n: f.startswith("(SC)-Batten (SC)-Batten_RAL7021"), (255, 140, 0)),
    ("cap", lambda f, n: "Batten_top" in f or "parapet_170" in f, (0, 90, 255)),
    ("gate", lambda f, n: "Batten_Gate" in f, (0, 170, 0)),
    ("edge_4_7", lambda f, n: "FS11" in f, (140, 70, 20)),
    ("vertical", lambda f, n: n.startswith("RZ_Nakl_V"), (0, 200, 220)),
    ("roof", lambda f, n: True, (150, 0, 200)),
]
NK = json.load(open(nakl_p, encoding="utf-8"))
nk_objs = []
gmat = {k: flat("nakl_" + k, c) for k, _, c in GROUPS}
for r in NK:
    g = next(k for k, t, _ in GROUPS if t(r["fam"], r["name"]))
    vs = [Vector(v) for v in r["verts"]]
    n = (vs[1] - vs[0]).cross(vs[2] - vs[1])
    if n.length < 1e-9:
        continue
    n.normalize()
    bm = bmesh.new()
    th = 0.06
    a = [bm.verts.new(v + n * th) for v in vs]
    b = [bm.verts.new(v - n * th) for v in vs]
    bm.faces.new(a)
    bm.faces.new(list(reversed(b)))
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new([a[i], a[j], b[j], b[i]])
    me = bpy.data.meshes.new("nk_" + r["name"])
    bm.to_mesh(me)
    me.materials.append(gmat[g])
    ob = bpy.data.objects.new("nk_" + r["name"], me)
    sc.collection.objects.link(ob)
    nk_objs.append(ob)

# ---------------------------------------------------------------- render setup
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "STUDIO"
sh.show_cavity = True
sh.cavity_type = "WORLD"
sh.show_object_outline = False
sh.show_specular_highlight = False
sc.display.render_aa = "16"
sc.view_settings.view_transform = "Standard"
sc.render.film_transparent = False
sh.background_type = "VIEWPORT" if hasattr(sh, "background_type") else None
if hasattr(sh, "background_color"):
    sh.background_type = "VIEWPORT"
    sh.background_color = (1, 1, 1)
sc.world = sc.world or bpy.data.worlds.new("W")
sc.world.color = (1, 1, 1)
cam_d = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_d)
sc.collection.objects.link(cam)
sc.camera = cam
PXM = 30
VIEWS = {
    # name: (loc, target, ortho_w or None, res or lens, extra)
    "S": dict(loc=(0, -150, 7.5), tgt=(0, 0, 7.5), w=92.0, h=19.0),
    "N": dict(loc=(0, 150, 7.5), tgt=(0, 0, 7.5), w=92.0, h=19.0),
    "E": dict(loc=(150, 0, 7.5), tgt=(0, 0, 7.5), w=58.0, h=19.0),
    "W": dict(loc=(-150, 0, 7.5), tgt=(0, 0, 7.5), w=58.0, h=19.0),
    "T": dict(loc=(0, 0, 150), tgt=(0, 0, 0), w=92.0, h=58.0),
    "pS": dict(loc=(-11.0, -44.0, 4.0), tgt=(-19.0, -26.3, 5.6), lens=28, res=(1800, 1100)),
    "pN": dict(loc=(26.0, 40.0, 2.2), tgt=(19.5, 27.3, 2.6), lens=30, res=(1800, 1100)),
    "pW": dict(loc=(-57.0, 9.0, 2.6), tgt=(-43.5, 16.5, 2.3), lens=30, res=(1800, 1100)),
    "pE": dict(loc=(70.0, -24.0, 4.0), tgt=(42.0, -3.0, 4.5), lens=30, res=(1800, 1100)),
    "pE2": dict(loc=(62.0, 1.0, 2.2), tgt=(41.0, 0.5, 3.0), lens=35, res=(1800, 1100)),
}
info = {}


def setup(v):
    d = VIEWS[v]
    cam.location = Vector(d["loc"])
    cam.rotation_euler = (Vector(d["tgt"]) - Vector(d["loc"])).to_track_quat("-Z", "Y").to_euler()
    cam_d.clip_start = 0.1
    cam_d.clip_end = 1000
    cam_d.sensor_fit = "HORIZONTAL"
    cam_d.sensor_width = 36
    if "w" in d:
        cam_d.type = "ORTHO"
        cam_d.ortho_scale = d["w"]
        sc.render.resolution_x = int(d["w"] * PXM)
        sc.render.resolution_y = int(d["h"] * PXM)
    else:
        cam_d.type = "PERSP"
        cam_d.lens = d["lens"]
        sc.render.resolution_x, sc.render.resolution_y = d["res"]
    sc.render.resolution_percentage = 100


def show(objs):
    for o in sc.objects:
        if o.type == "MESH":
            o.hide_render = o not in objs or o.name.startswith("UCX_")


for v in VIEWS:
    if only and v not in only:
        continue
    setup(v)
    info[v] = {k: list(x) if isinstance(x, tuple) else x for k, x in VIEWS[v].items()}
    for var in ("ours_tex", "ours_id", "theirs_id", "theirs_nakl"):
        fp = os.path.join(out, f"{v}_{var}.png")
        if os.path.exists(fp):
            continue
        if var == "ours_tex":
            o_main.data = o_main_tex_mesh
            o_glass.data = o_glass_mesh_tex
            sh.color_type = "TEXTURE"
            show([o_main, o_glass])
        elif var == "ours_id":
            o_main.data = ours_id_mesh
            o_glass.data = o_glass_mesh_id
            sh.color_type = "MATERIAL"
            show([o_main, o_glass])
        elif var == "theirs_id":
            t_main.data = theirs_id_mesh
            sh.color_type = "MATERIAL"
            show([t_main])
        else:
            t_main.data = theirs_grey_mesh
            sh.color_type = "MATERIAL"
            show([t_main] + nk_objs)
        sc.render.filepath = fp
        bpy.ops.render.render(write_still=True)
json.dump({"px_per_m_ortho": PXM, "views": info, "shift_theirs": list(SHIFT)},
          open(os.path.join(out, "views_clarify.json"), "w"), indent=1)
print("DONE", out)
