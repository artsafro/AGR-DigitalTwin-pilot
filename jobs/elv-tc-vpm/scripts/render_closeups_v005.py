"""elv-tc-vpm renders-v005: close-ups for the Max-review rework of v004 (before = build-v007 tex master with the tex-v005
set = delivery v004; after = build-v008 tex master with tex-v006 = delivery v005). Workbench, studio light, TEXTURE colour
(the Diffuse UDIM set), so the joint lines read exactly as mapped. Cameras in DELIVERED metres (build = delivered + OFF).

blender -b --factory-startup --disable-autoexec <tex master .blend> --python render_closeups_v005.py -- \
    <tex_dir> <out_dir> <prefix> [view ...]
Views: j_upper_s (ID01 upper row under the parapet, south facade), j_upper_n (same, north slanted facade),
j_id02 (metal cassette ID02, south base), strip_sw (cover strip run: SW convex corner + DECO lights moved out),
strip_arktos (strip under a raised Arktos box), glass_cut_s / glass_cut_concave / glass_cut_t1 (corner glazing cut at
a height, top view: the two faces of the 6 mm shell show as a double line). Never overwrites.
"""
import bpy, bmesh, math, os, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
tex_dir, out_dir, prefix = argv[:3]
views = argv[3:]
OFF = Vector((35.1000, -24.2535, 0.0))
os.makedirs(out_dir, exist_ok=True)
for im in bpy.data.images:
    if im.filepath and "_1.<UDIM>.png" in im.filepath:
        im.filepath = os.path.join(os.path.abspath(tex_dir), os.path.basename(bpy.path.abspath(im.filepath)))
        im.reload()
for m in bpy.data.materials:
    if m.node_tree:
        for n in m.node_tree.nodes:
            if n.type == "TEX_IMAGE" and n.image and "_Diffuse_" in n.image.name:
                m.node_tree.nodes.active = n
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sc.display.shading.light = "STUDIO"
sc.display.shading.color_type = "TEXTURE"
sc.display.shading.show_backface_culling = False
sc.render.resolution_x, sc.render.resolution_y = 1400, 900
sc.render.film_transparent = False
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
sc.collection.objects.link(cam)
sc.camera = cam
main = next(o for o in bpy.data.objects if o.name.endswith("_Main"))
glass = next(o for o in bpy.data.objects if o.name.endswith("_MainGlass"))

V = {  # name: (eye delivered, target delivered, lens or ('ortho', scale))
    "j_upper_s": ((-4.0, -31.5, 9.0), (-4.0, -26.2, 11.3), 40),
    "j_upper_n": ((-14.0, 31.0, 9.5), (-14.0, 25.0, 11.2), 40),
    "j_id02": ((8.4, -30.5, 3.2), (8.4, -26.4, 3.6), 40),
    "strip_sw": ((-40.5, -30.0, 5.4), (-35.4, -18.5, 4.6), 32),
    "strip_arktos": ((-2.2, -28.6, 5.4), (-2.2, -26.25, 4.75), 30),
}
CUTS = {  # name: (centre delivered xy, z cut, ortho scale)
    "glass_cut_s": ((42.4, -4.6), 8.0, 4.2),
    "glass_cut_concave": ((41.0, -2.85), 8.0, 0.45),
    "glass_cut_t1": ((17.85, 17.95), 13.0, 0.6),
}


def shoot(name):
    p = os.path.join(out_dir, f"{prefix}_{name}.png")
    if os.path.exists(p):
        raise SystemExit("output exists: " + p)
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    print("RENDER", p)


# strip views: the cover strips P44 in orange (render-only material slot; nothing is saved)
import json  # noqa: E402
_pids = json.loads(main["part_ids"])
_hl = bpy.data.materials.new("hl_strip")
_hl.diffuse_color = (1.0, 0.45, 0.0, 1.0)
_orig_idx = None


def highlight(on):
    global _orig_idx
    me = main.data
    att = me.attributes["part_idx"].data
    if on:
        if _hl.name not in me.materials:
            me.materials.append(_hl)
        k = list(me.materials).index(_hl)
        _orig_idx = [p.material_index for p in me.polygons]
        for p in me.polygons:
            if _pids[att[p.index].value] == "P44_CoverStrips":
                p.material_index = k
        sc.display.shading.color_type = "MATERIAL"
    elif _orig_idx is not None:
        for p, i in zip(me.polygons, _orig_idx):
            p.material_index = i
        sc.display.shading.color_type = "TEXTURE"


for v in views:
    highlight(v.startswith("strip"))
    if v in V:
        eye, tgt, lens = V[v]
        e, t = Vector(eye) + OFF, Vector(tgt) + OFF
        cam.data.type = "PERSP"
        cam.data.lens = lens
        cam.location = e
        cam.rotation_euler = (t - e).to_track_quat("-Z", "Y").to_euler()
        cam.data.clip_start, cam.data.clip_end = 0.05, 500
        shoot(v)
    elif v in CUTS:
        (cx, cy), zc, sc_ = CUTS[v]
        # section lines: the cut edges of Main (grey) and MainGlass (cyan) at zc as thin round curves, top ortho view
        tmp = []
        half = sc_ * 0.75
        for o, col, r in ((main, (0.25, 0.25, 0.25, 1.0), 0.0012), (glass, (0.0, 0.7, 1.0, 1.0), 0.0012)):
            bm = bmesh.new()
            bm.from_mesh(o.data)
            res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, zc),
                                         plane_no=(0, 0, 1))
            cu = bpy.data.curves.new(o.name + "_cut", "CURVE")
            cu.dimensions = "3D"
            cu.bevel_depth = r * sc_
            n = 0
            for e in [g for g in res["geom_cut"] if isinstance(g, bmesh.types.BMEdge)]:
                p0, p1 = e.verts[0].co, e.verts[1].co
                if abs(p0.x - OFF.x - cx) > half and abs(p1.x - OFF.x - cx) > half:
                    continue
                if abs(p0.y - OFF.y - cy) > half and abs(p1.y - OFF.y - cy) > half:
                    continue
                sp = cu.splines.new("POLY")
                sp.points.add(1)
                sp.points[0].co = (p0.x, p0.y, zc, 1)
                sp.points[1].co = (p1.x, p1.y, zc, 1)
                n += 1
            bm.free()
            mt = bpy.data.materials.new("cut_" + o.name)
            mt.diffuse_color = col
            cu.materials.append(mt)
            t = bpy.data.objects.new(o.name + "_cut", cu)
            sc.collection.objects.link(t)
            tmp.append(t)
            print("CUT", v, o.name, n)
        for o in (main, glass):
            o.hide_render = True
        bpy.context.scene.world = bpy.context.scene.world or bpy.data.worlds.new("W")
        sc.display.shading.color_type = "MATERIAL"
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = sc_
        cam.location = Vector((cx, cy, zc + 5)) + OFF
        cam.rotation_euler = (0, 0, 0)
        cam.data.clip_start, cam.data.clip_end = 0.01, 50
        sc.render.resolution_x = sc.render.resolution_y = 900
        shoot(v)
        for t in tmp:
            bpy.data.objects.remove(t)
        for o in (main, glass):
            o.hide_render = False
        sc.display.shading.color_type = "TEXTURE"
        sc.render.resolution_x, sc.render.resolution_y = 1400, 900
    else:
        raise SystemExit("unknown view " + v)
