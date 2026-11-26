"""#1784 step 3 hook (stage `body`, point `after`), Blender side: v006 = accepted body v005 + inset objects.

Pattern: n/a | new-case: thin Blender writer - opens the v005 body.blend read-only (the body objects are not edited),
adds one object per inset family from inset_build.py's insets_meshes.json with its own material slots, saves a new
body_v006.blend + body_v006_quad.fbx (quad review copy; triangulation is the delivery step [D270]).

    blender44 -b --factory-startup --python jobs/sokolniki-uvk1000/hooks/inset_write_blender.py -- \
        BODY.blend INSETS_MESHES.json NEW_OUT_DIR [TAG=v006]

v007 [D410]: BODY.blend is the roof-well body (volume_body.py with body_config_v007.json), TAG v007.

Writes NEW_OUT_DIR/blender_write.json: per object verts/faces/materials and, for every v005 body object, the
sha256 of its world vertex coordinates + face indices before and after (equal = body untouched).

Render mode (folded in from inset_sheet_blender.py, the job keeps <= 5 listed hooks [D324]): straight orthographic
elevations for the v005 | v006 | v007 | Revit sheets - one camera per facade looking at it from outside, everything
more than `front_m` in front of the facade plane clipped - plus the iso and the close-ups of VIEWS.json:

    blender44 -b --factory-startup --python jobs/sokolniki-uvk1000/hooks/inset_write_blender.py -- \
        render MODEL(.blend|.fbx) VIEWS.json NEW_OUT_DIR TAG

Writes NEW_OUT_DIR/<TAG>_<id>.png, <TAG>_iso.png and <TAG>_<closeup id>.png.
"""
import hashlib
import json
import math  # noqa: F401  (render helpers)
import os
import sys


import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

COLORS = {"04_cassette_fin_RAL8023": (0.55, 0.30, 0.20, 1), "05_cw_structural_RAL7016": (0.30, 0.50, 0.68, 1),
          "10_mesh_20_RAL9003": (0.45, 0.62, 0.50, 1), "12_frame_RAL9003": (0.95, 0.95, 0.93, 1),
          "14_flashing_RAL7016": (0.22, 0.24, 0.26, 1), "M_Glass_01": (0.62, 0.82, 0.86, 1),
          "13_decor_relief_RAL9003": (0.97, 0.96, 0.92, 1), "15_roof_hatch_RAL7016": (0.25, 0.27, 0.30, 1),
          "16_pier_facade": (0.80, 0.78, 0.74, 1),
          # v008 (plan #1896): openings and roof decks moved out of the body keep the v007 body colours (same picture)
          "17_window_glass": (0.25, 0.45, 0.65, 1), "18_door_glass": (0.20, 0.38, 0.55, 1),
          "19_curtain_glass": (0.30, 0.50, 0.68, 1), "20_stemalit_texture": (0.35, 0.40, 0.45, 1),
          "21_roof_deck_RAL7016": (0.45, 0.45, 0.47, 1)}


def geo_hash(ob):
    h = hashlib.sha256()
    mw = ob.matrix_world
    for v in ob.data.vertices:
        h.update(("%.5f,%.5f,%.5f;" % tuple(mw @ v.co)).encode())
    for p in ob.data.polygons:
        h.update((",".join(str(i) for i in p.vertices) + "|%d;" % p.material_index).encode())
    return h.hexdigest()


def material(name):
    if name not in COLORS:
        raise ValueError("unmapped inset material %r" % name)
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = COLORS[name]
    return m


def make(name, data):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in data["verts"]], [], [tuple(f["v"]) for f in data["faces"]])
    me.validate(clean_customdata=False)
    mats = sorted({f["mat"] for f in data["faces"]})
    for m in mats:
        me.materials.append(material(m))
    uv = me.uv_layers.new(name="UVMap")
    for p, f in zip(me.polygons, data["faces"]):
        p.material_index = mats.index(f["mat"])
        for j in range(p.loop_total):
            uv.data[p.loop_start + j].uv = f["uv"][j]
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob, mats


def setup(tag):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "SINGLE" if tag == "revit" else "MATERIAL"
    sh.single_color = (0.78, 0.78, 0.76)
    sh.show_cavity = True
    sh.show_object_outline = True
    sh.show_backface_culling = False
    sc.render.film_transparent = False
    sc.world = sc.world or bpy.data.worlds.new("W")
    sc.render.image_settings.file_format = "PNG"
    cam = bpy.data.objects.new("CAM", bpy.data.cameras.new("CAM"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = "ORTHO"
    return sc, cam


def aim(cam, loc, direction):
    cam.location = Vector(loc)
    cam.rotation_euler = Vector(direction).to_track_quat("-Z", "Y").to_euler()


def texture_mode(tag):
    """#1925: Workbench shows the atlas (`atlas`) or a 0.5 m UV checker laid over the same atlas UVs (`checker`:
    2048 px image, 47 px squares = 0.5 m at the 377 px / 4 m region scale)."""
    img = None
    if tag == "checker":
        import numpy as np
        n, sq = 2048, 47
        ii = (np.arange(n) // sq) % 2
        board = (ii[:, None] ^ ii[None, :]).astype(np.float32)
        rgba = np.ones((n, n, 4), np.float32)
        rgba[..., 0] = 0.15 + 0.8 * board
        rgba[..., 1] = 0.15 + 0.8 * board
        rgba[..., 2] = 0.35 + 0.6 * board
        img = bpy.data.images.new("uv_checker_0p5m", n, n)
        img.pixels.foreach_set(rgba.ravel())
    for m in bpy.data.materials:
        if not m.use_nodes:
            continue
        nodes = [nd for nd in m.node_tree.nodes if nd.type == "TEX_IMAGE" and nd.image]
        base = [nd for nd in nodes if nd.image.name.endswith("_d_1") or "_d_1." in nd.image.name] or nodes
        if base:
            if img is not None:
                base[0].image = img
            m.node_tree.nodes.active = base[0]


def render(argv):
    """Straight elevations + iso + close-ups of MODEL for the sheet (evidence only, never saves a .blend).
    #1925: TAG `atlas` / `checker` shows the NPM atlas / a UV checker; optional 5th arg `dx,dy` moves the imported
    objects back into the views' frame (dt derive npm re-pivots to the plan centre)."""
    src, views_path, out, tag = argv[:4]
    shift = [float(x) for x in argv[4].split(",")] if len(argv) > 4 else None
    os.makedirs(out, exist_ok=True)
    if src.lower().endswith(".blend"):
        bpy.ops.wm.open_mainfile(filepath=src)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=src)
    if shift:
        for ob in bpy.context.scene.objects:
            ob.location = ob.location + Vector((shift[0], shift[1], 0.0))
    with open(views_path, encoding="utf-8") as fh:
        views = json.load(fh)
    sc, cam = setup(tag)
    if tag in ("atlas", "checker"):
        sc.display.shading.color_type = "TEXTURE"
        texture_mode(tag)
    front, ppm = views["front_m"], views["px_per_m"]
    far = 400.0
    for f in views["facades"]:
        s0, s1 = f["s"]
        z0, z1 = f["z"]
        w, h = (s1 - s0) + 4.0, (z1 - z0) + 4.0
        sm, zm = (s0 + s1) / 2.0, (z0 + z1) / 2.0
        a, t, n = f["a"], f["t"], f["n"]
        dist = 60.0
        loc = (a[0] + t[0] * sm + n[0] * dist, a[1] + t[1] * sm + n[1] * dist, zm)
        aim(cam, loc, (-n[0], -n[1], 0.0))
        cam.data.ortho_scale = max(w, h)
        cam.data.clip_start = dist - front
        cam.data.clip_end = far
        sc.render.resolution_x = int(round(w * ppm))
        sc.render.resolution_y = int(round(h * ppm))
        cam.data.sensor_fit = "HORIZONTAL" if w >= h else "VERTICAL"
        sc.render.filepath = os.path.join(out, "%s_%s.png" % (tag, f["id"]))
        bpy.ops.render.render(write_still=True)
    iso = views.get("iso")
    if iso:
        d = Vector(iso["dir"]).normalized()
        aim(cam, Vector(iso["target"]) - d * 300.0, d)
        cam.data.ortho_scale = iso["scale"]
        cam.data.clip_start, cam.data.clip_end = 1.0, 1000.0
        cam.data.sensor_fit = "HORIZONTAL"
        sc.render.resolution_x, sc.render.resolution_y = 1800, 1200
        sc.render.filepath = os.path.join(out, "%s_iso.png" % tag)
        bpy.ops.render.render(write_still=True)
    shots = views.get("closeups", [])
    for c in shots:
        d = Vector(c["dir"]).normalized()
        aim(cam, Vector(c["target"]) - d * 200.0, d)
        cam.data.ortho_scale = c["scale"]
        cam.data.clip_start, cam.data.clip_end = 1.0, 1000.0
        cam.data.sensor_fit = "HORIZONTAL"
        sc.render.resolution_x, sc.render.resolution_y = c.get("res", [1400, 1000])
        sc.render.filepath = os.path.join(out, "%s_%s.png" % (tag, c["id"]))
        bpy.ops.render.render(write_still=True)
    print("RENDERED", tag, len(views["facades"]) + (1 if iso else 0) + len(shots))


def main(argv):
    body_blend, src, out = argv[:3]
    tag = argv[3] if len(argv) > 3 else "v006"  # v007 [D410]: the body is the v007 roof-well build
    if os.path.exists(os.path.join(out, "body_%s.blend" % tag)):
        print("refused: output exists", file=sys.stderr)
        sys.exit(2)
    os.makedirs(out, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=body_blend)
    body = {ob.name: geo_hash(ob) for ob in bpy.context.scene.objects if ob.type == "MESH"}
    with open(src, encoding="utf-8") as fh:
        meshes = json.load(fh)
    stats = {}
    for name in sorted(meshes):
        if name in body:
            raise ValueError("inset object %s collides with a body object" % name)
        ob, mats = make(name, meshes[name])
        stats[name] = {"verts": len(ob.data.vertices), "faces": len(ob.data.polygons), "materials": mats}
    after = {n: geo_hash(bpy.data.objects[n]) for n in body}
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "body_%s.blend" % tag), copy=True)
    bpy.ops.export_scene.fbx(filepath=os.path.join(out, "body_%s_quad.fbx" % tag), use_selection=False,
                             mesh_smooth_type="FACE", apply_unit_scale=True, axis_forward="-Y", axis_up="Z")
    doc = {"blender": bpy.app.version_string, "source_body": os.path.realpath(body_blend), "insets": stats,
           "body_unchanged": {n: {"before": body[n], "after": after[n], "equal": body[n] == after[n]} for n in body}}
    with open(os.path.join(out, "blender_write.json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    print("WROTE", len(stats), "insets; body unchanged:", all(v["equal"] for v in doc["body_unchanged"].values()))


def edge_census(bm):
    """Open (1 face) and non-manifold (> 2 faces) edge counts of one object; open_len_m proves a cut only
    subdivides existing borders (same length) and opens none."""
    return {"open": sum(1 for e in bm.edges if len(e.link_faces) == 1),
            "open_len_m": round(sum(e.calc_length() for e in bm.edges if len(e.link_faces) == 1), 4),
            "nonmanifold": sum(1 for e in bm.edges if len(e.link_faces) > 2)}


def split_overflow(bm, names, cfg, vpm_uv):
    """#1925: vpm_uv.texel_cut grids quads only; a textured n-gon larger than its tile is bisected here on
    world-axis planes of its own projection every lmax metres. The split edges are shared, so neighbours only
    gain collinear vertices (no T-junction, no vertex moves). Returns the number of n-gons split."""
    import bmesh
    fl = bm.faces.layers.int["finish"]
    out = bm.loops.layers.uv["UVMap"]
    bad = []
    for f in bm.faces:
        t = cfg["finishes"][names[f[fl]]]
        if t["kind"] != "full":
            continue
        tu, tv = vpm_uv.tile_offset(t["udim"])
        uvs = [l[out].uv for l in f.loops]
        if min(min(u.x - tu, u.y - tv) for u in uvs) < 0 or max(max(u.x - tu, u.y - tv) for u in uvs) > 1:
            bad.append(f)
    for f in bad:
        lm = vpm_uv.lmax(cfg, names[f[fl]])
        n = f.normal
        ax = [abs(n.x), abs(n.y), abs(n.z)]
        dom = ax.index(max(ax))
        pieces = [f]
        for axis in [a for a in range(3) if a != dom]:
            lo = min(v.co[axis] for v in f.verts)
            hi = max(v.co[axis] for v in f.verts)
            k = math.ceil((hi - lo) / lm - 1e-9)
            for i in range(1, k):
                co, no = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
                co[axis], no[axis] = lo + (hi - lo) * i / k, 1.0
                geom = list({e for p in pieces if p.is_valid for e in p.edges}) + \
                    [p for p in pieces if p.is_valid] + list({v for p in pieces if p.is_valid for v in p.verts})
                res = bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-4, plane_co=co, plane_no=no)
                pieces = [g for g in res["geom"] if isinstance(g, bmesh.types.BMFace)]
    bm.normal_update()
    return len(bad)


def window_faces(bm, fl, names, cfg, ib):
    """#1925 r4 [D417] windows shown as texture: every face of a `pattern: elevations` finish gets explicit
    tile-metre UVs (layer UVM + face flag uvx, honoured by vpm_uv.texel_cut / pack_uv) - the box of its Revit
    instance (uv_config window_texture.instances) onto that instance's drawing cell; without an instance the
    face's own extent onto the `_face` drawing. No vertex is touched. Returns per-cell face counts."""
    uvm = bm.loops.layers.uv.get("UVM") or bm.loops.layers.uv.new("UVM")
    flag = bm.faces.layers.int.get("uvx") or bm.faces.layers.int.new("uvx")
    wt = cfg["window_texture"]
    stats = {"faces": 0, "matched": 0, "fallback": 0, "reversed": 0, "cells": {}}
    for f in bm.faces:
        t = cfg["finishes"][names[f[fl]]]
        if t.get("pattern") != "elevations":
            continue
        cells, n = t["cells"], f.normal
        row = ib.match_window(tuple(f.calc_center_median()), (n.x, n.y, n.z), cells, wt["instances"],
                              wt["match_tol_m"]) if abs(n.z) < 0.3 else None
        if row:
            uvs = [ib.window_uv(tuple(l.vert.co), row, cells[row[0]]) for l in f.loops]
            if n.x * row[4] - n.y * row[3] < 0:       # face normal against the instance's outward normal
                stats["reversed"] += 1
            name = row[0]
        else:
            if abs(n.z) < 0.3:
                ln = math.hypot(n.x, n.y)
                pts = [((l.vert.co.x * -n.y + l.vert.co.y * n.x) / ln, l.vert.co.z) for l in f.loops]
            else:
                pts = [(l.vert.co.x, l.vert.co.y) for l in f.loops]
            name = "_face"
            uvs = ib.face_uv(pts, cells[name])
        for l, uv in zip(f.loops, uvs):
            l[uvm].uv = uv
        f[flag] = 1
        stats["faces"] += 1
        stats["matched" if row else "fallback"] += 1
        stats["cells"][name] = stats["cells"].get(name, 0) + 1
    return stats


def uv(argv):
    """#1925 step 4: finish IDs + texel cuts + periodic UDIM UV on a NEW master copy of the accepted v009 assembly.

    Body faces get their finish from inset_build.body_finish (uv_config.json `zoning`), inset faces from
    `material_map`; glass objects become SM_<A>_MainGlass, everything else is joined into SM_<A>_Main (the
    dt derive npm contract). Cuts and UVs are the shared tools/blender/vpm_uv.py (edge-ring splits, no
    T-junctions, no vertex of the accepted mesh moves); flat-colour-only objects are not cut. Writes
    NEW_OUT_DIR/master_v001.blend + uv_report.json (faces per finish, cuts, UV QA, density, vertex check)."""
    import importlib.util
    import bmesh
    from mathutils.kdtree import KDTree
    src, cfg_path, vl_path, out = argv
    master = os.path.join(out, "master_v001.blend")
    if os.path.exists(master):
        print("refused: output exists", file=sys.stderr)
        sys.exit(2)
    os.makedirs(out, exist_ok=True)
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.normpath(os.path.join(here, "..", "..", ".."))
    sys.path.insert(0, os.path.join(root, "tools", "blender"))
    import vpm_uv
    spec_ib = importlib.util.spec_from_file_location("inset_build_1925", os.path.join(here, "inset_build.py"))
    ib = importlib.util.module_from_spec(spec_ib)
    spec_ib.loader.exec_module(ib)
    with open(cfg_path, encoding="utf-8") as fh:
        cfg = json.load(fh)
    with open(vl_path, encoding="utf-8") as fh:
        rings = {k: v["ring"] for k, v in json.load(fh)["volumes"].items()}
    names = sorted(cfg["finishes"], key=lambda k: cfg["finishes"][k]["udim"])
    with open(src, "rb") as fh:
        src_sha = hashlib.sha256(fh.read()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=src)
    report = {"source": os.path.realpath(src), "source_sha256": src_sha, "blender": bpy.app.version_string,
              "objects": {}, "body_reasons": {}, "finish_faces_before": {}}
    orig_pts = []
    parts, glass = [], []
    for ob in sorted((o for o in bpy.context.scene.objects if o.type == "MESH"), key=lambda o: o.name):
        me, mw = ob.data, ob.matrix_world
        mats = [m.name if m else None for m in me.materials]
        if set(mats) <= set(cfg["glass_materials"]):
            gb = bmesh.new()
            gb.from_mesh(me)
            gb.transform(mw)
            gb.normal_update()
            orig_pts.extend(v.co.copy() for v in gb.verts)
            gl = gb.faces.layers.int.new("finish")
            for f in gb.faces:
                f[gl] = 0
            report["glass_uv_qa"] = vpm_uv.pack_uv(gb, ["glass"], cfg, glass=True)
            glass.append((ob.name, gb))
            continue
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.transform(mw)
        bm.normal_update()
        orig_pts.extend(v.co.copy() for v in bm.verts)
        fl = bm.faces.layers.int.new("finish")
        vol = cfg["body_objects"].get(ob.name)
        for f in bm.faces:
            mat = mats[f.material_index]
            if mat == cfg["body_material"]:
                c = f.calc_center_median()
                zs = [v.co.z for v in f.verts]
                d, cos = ib.ring_relation((c.x, c.y), (f.normal.x, f.normal.y), rings[vol])
                fin, why = ib.body_finish(vol, tuple(f.normal), (min(zs), c.z, max(zs)), d, cos, f.calc_area(),
                                          cfg["zoning"])
                key = "%s:%s" % (vol, why)
                report["body_reasons"][key] = report["body_reasons"].get(key, 0) + 1
            else:
                fin = cfg["material_map"][mat]
            f[fl] = names.index(fin)
            report["finish_faces_before"][fin] = report["finish_faces_before"].get(fin, 0) + 1
        textured = any(cfg["finishes"][names[f[fl]]]["kind"] == "full" for f in bm.faces)
        if any(cfg["finishes"][names[f[fl]]].get("pattern") == "elevations" for f in bm.faces):
            report.setdefault("window_texture", {})[ob.name] = window_faces(bm, fl, names, cfg, ib)
        before = (len(bm.faces), sum(len(f.verts) - 2 for f in bm.faces), edge_census(bm))
        nb = vpm_uv.texel_cut(bm, names, cfg) if textured else bm
        qa = vpm_uv.pack_uv(nb, names, cfg)
        split = 0
        if textured and any(q["overflow"] for q in qa.values()):
            split = split_overflow(nb, names, cfg, vpm_uv)
            qa = vpm_uv.pack_uv(nb, names, cfg)
        report["objects"][ob.name] = {"faces_before": before[0], "tris_before": before[1], "cut": textured,
                                      "faces_after": len(nb.faces), "overflow_ngons_split": split,
                                      "edges_before": before[2], "edges_after": edge_census(nb),
                                      "tris_after": sum(len(f.verts) - 2 for f in nb.faces), "uv_qa": qa,
                                      "density_px_per_m": vpm_uv.density_qa(nb, names, cfg)}
        parts.append((ob.name, nb))

    def to_object(name, bm, finish_names):
        for lay in [l for l in bm.loops.layers.uv.keys() if l != "UVMap"]:
            bm.loops.layers.uv.remove(bm.loops.layers.uv[lay])
        fl = bm.faces.layers.int["finish"]
        for f in bm.faces:
            f.material_index = f[fl]
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        for n in finish_names:
            m = bpy.data.materials.get(n) or bpy.data.materials.new(n)
            m.diffuse_color = tuple(c / 255 for c in cfg["finishes"][n]["rgb"]) + (1,) if n in cfg["finishes"] \
                else (0.62, 0.82, 0.86, 0.4)
            me.materials.append(m)
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        return ob

    for ob in list(bpy.context.scene.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    objs = [to_object(n + "_uv", bm, names) for n, bm in parts]
    # per-object quad copy (the accepted v009 xView scope) before the dt derive npm join into one *_Main
    bpy.ops.export_scene.fbx(filepath=os.path.join(out, "parts_quad.fbx"), use_selection=False,
                             mesh_smooth_type="FACE", axis_forward="-Y", axis_up="Z")
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    main = bpy.context.view_layer.objects.active
    main.name = main.data.name = "SM_%s_Main" % cfg["address"]
    main["finish_names"] = ",".join(names)  # dt derive npm contract: face int `finish` indexes this list
    if len(glass) > 1:
        raise ValueError("one glass object expected, got %s" % [g[0] for g in glass])
    if glass:
        gob = to_object("SM_%s_MainGlass" % cfg["address"], glass[0][1], cfg["glass_materials"])
        report["glass"] = {"source": glass[0][0], "faces": len(gob.data.polygons)}
    main_pts = [v.co.copy() for v in main.data.vertices] + ([v.co.copy() for v in gob.data.vertices] if glass else [])
    report["main"] = {"faces": len(main.data.polygons), "verts": len(main.data.vertices),
                      "tris": sum(p.loop_total - 2 for p in main.data.polygons),
                      "ngons": sum(1 for p in main.data.polygons if p.loop_total > 4)}
    kd = KDTree(len(main_pts))
    for i, co in enumerate(main_pts):
        kd.insert(co, i)
    kd.balance()
    report["orig_vertex_max_move_m"] = max(kd.find(p)[2] for p in orig_pts)
    report["orig_vertices"] = len(orig_pts)
    bpy.ops.wm.save_as_mainfile(filepath=master, copy=True)
    with open(os.path.join(out, "uv_report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, ensure_ascii=False)
    print("UV", report["main"], "max move", report["orig_vertex_max_move_m"])


def winscan(argv):
    """#1925 r4 [D417] read-only: every v009 window / door face -> the Revit window / door instance whose box holds
    it; per instance the frame (c, r = right as seen from outside), its box (u along r from c, world z) and the
    glass pane rectangles (Revit triangles facing out and thicker than 0.12 m). Never saves.

        blender44 -b --factory-startup --python inset_write_blender.py -- winscan V009.blend REVIT.fbx NEW.json"""
    import collections
    import re
    import numpy as np
    v009, revit, out = argv
    if os.path.exists(out):
        print("refused: output exists", file=sys.stderr)
        sys.exit(2)
    bpy.ops.wm.open_mainfile(filepath=v009)
    win = re.compile(r"OKS_(Windows|Doors)$")
    faces = []
    for o in bpy.context.scene.objects:
        if o.type != "MESH" or not win.search(o.name):
            continue
        for p in o.data.polygons:
            n = np.array((o.matrix_world.to_3x3() @ p.normal).normalized())
            pts = np.array([o.matrix_world @ o.data.vertices[i].co for i in p.vertices])
            if abs(n[2]) <= 0.3:
                n[2] = 0.0
                faces.append((o.name, p.index, pts.mean(0), n / np.linalg.norm(n)))
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=revit, use_image_search=False)
    fam = re.compile(r"^(WB_Окно|WB_Дверь|AC_Дверь)")
    inst = []
    for o in bpy.data.objects:
        if o in before or o.type != "MESH" or not fam.search(o.name):
            continue
        o.data.calc_loop_triangles()
        V = np.array([o.matrix_world @ v.co for v in o.data.vertices])
        T = np.array([t.vertices[:] for t in o.data.loop_triangles], dtype=np.int64).reshape(-1, 3)
        if len(T):
            inst.append((o.name, re.sub(r"_[0-9a-f]{6,8}$", "", o.name).strip(), V, T))

    def panes(V, T, n, r, c):
        P = V[T]
        cr = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
        a = np.linalg.norm(cr, axis=1)
        nn = cr / np.maximum(a[:, None], 1e-12)
        e = np.stack([P[:, 1] - P[:, 0], P[:, 2] - P[:, 1], P[:, 0] - P[:, 2]], 1)
        glass = (np.abs(nn @ n) > 0.98) & (a / np.maximum(np.linalg.norm(e, axis=2).max(1), 1e-9) > 0.12)
        idx = np.where(glass)[0]
        parent = list(range(len(idx)))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        key = {}
        for k, f in enumerate(idx):
            for v in T[f]:
                kk = tuple(np.round(V[v] / 0.01).astype(int))
                if kk in key:
                    parent[find(k)] = find(key[kk])
                else:
                    key[kk] = k
        groups = collections.defaultdict(list)
        for k, f in enumerate(idx):
            groups[find(k)].append(f)
        rects = []
        for fs in groups.values():
            W = V[np.unique(T[fs])]
            u = (W - c) @ r
            rr = [float(u.min()), float(u.max()), float(W[:, 2].min()), float(W[:, 2].max())]
            if not any(all(abs(x - y) < 0.02 for x, y in zip(rr, q)) for q in rects):
                rects.append([round(x, 3) for x in rr])
        return sorted(rects)

    res, unmatched = {}, []
    for oname, pi, c, n in faces:
        r = np.cross([0.0, 0.0, 1.0], n)
        best = None
        for name, typ, V, T in inst:
            d = V.mean(0) - c
            if abs(d @ n) > 0.6:
                continue
            u, z = (V - c) @ r, V[:, 2]
            if u.min() - 0.05 <= 0 <= u.max() + 0.05 and z.min() - 0.05 <= c[2] <= z.max() + 0.05:
                dd = math.hypot(float(d @ r), float(d[2]))
                if best is None or dd < best[0]:
                    best = (dd, name, typ, V, T)
        if best is None:
            unmatched.append([oname, pi, [round(float(x), 3) for x in c]])
            continue
        _, name, typ, V, T = best
        if name not in res:
            u = (V - c) @ r
            res[name] = {"type": typ, "c": [round(float(x), 3) for x in c[:2]], "r": [round(float(x), 5) for x in r[:2]],
                         "box": [round(float(u.min()), 3), round(float(u.max()), 3), round(float(V[:, 2].min()), 3),
                                 round(float(V[:, 2].max()), 3)], "panes": panes(V, T, n, r, c), "faces": 0,
                         "tris": int(len(T))}
        res[name]["faces"] += 1
    with open(revit, "rb") as fh:
        sha = hashlib.sha256(fh.read()).hexdigest()
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"source": {"revit": os.path.basename(revit), "sha256": sha[:16], "v009": os.path.basename(v009)},
                   "faces": len(faces), "unmatched": unmatched, "instances": res}, fh, ensure_ascii=False, indent=1)
    print("WINSCAN faces", len(faces), "instances", len(res), "unmatched", len(unmatched))


def cwscan(argv):
    """#1925 r5 [D418] read-only: every vertical v009 curtain-wall face (material -> a finish of uv_config
    window_texture.cw.codes) -> its frame (c, r = right seen along -n), box (u along r from c, world z) and the
    Revit curtain panels ('Системная панель ...', flat, parallel) overlapping it as (u, z) rectangles - only the
    Revit layer nearest to the face within cw.search_depth_m (the F05 ground wall sits 2.1 m behind its inset). Never saves.

        blender44 -b --factory-startup --python inset_write_blender.py -- cwscan V009.blend REVIT.fbx UV_CONFIG NEW.json"""
    import collections
    import re
    import numpy as np
    v009, revit, cfg_path, out = argv
    if os.path.exists(out):
        print("refused: output exists", file=sys.stderr)
        sys.exit(2)
    with open(cfg_path, encoding="utf-8") as fh:
        cfg = json.load(fh)
    fins = set(cfg["window_texture"]["cw"]["codes"])
    depth = cfg["window_texture"]["cw"]["search_depth_m"]
    bpy.ops.wm.open_mainfile(filepath=v009)
    faces = []
    for o in sorted((o for o in bpy.context.scene.objects if o.type == "MESH"), key=lambda o: o.name):
        mats = [m.name if m else None for m in o.data.materials]
        for p in o.data.polygons:
            fin = cfg["material_map"].get(mats[p.material_index]) if mats else None
            if fin not in fins:
                continue
            n = np.array((o.matrix_world.to_3x3() @ p.normal).normalized())
            if abs(n[2]) > 0.3:
                continue
            n[2] = 0.0
            n /= np.linalg.norm(n)
            P = np.array([o.matrix_world @ o.data.vertices[i].co for i in p.vertices])
            faces.append((o.name, p.index, fin, P, n))
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=revit, use_image_search=False)
    pan = []
    for o in bpy.data.objects:
        if o in before or o.type != "MESH" or not o.name.startswith("Системная панель"):
            continue
        V = np.array([o.matrix_world @ v.co for v in o.data.vertices])
        if len(V):
            pan.append((re.sub(r"_[0-9a-f]{6,8}$", "", o.name).strip(), V))
    res, kinds = [], collections.Counter()
    for oname, pi, fin, P, n in faces:
        c = P.mean(0)
        r = np.cross([0.0, 0.0, 1.0], n)
        u = (P - c) @ r
        box = [float(u.min()), float(u.max()), float(P[:, 2].min()), float(P[:, 2].max())]
        rects = []
        for name, V in pan:
            dn = (V - c) @ n
            if abs(float(dn.mean())) > depth or float(dn.max() - dn.min()) > 0.15:
                continue
            uu = (V - c) @ r
            rr = [float(uu.min()), float(uu.max()), float(V[:, 2].min()), float(V[:, 2].max())]
            if rr[1] < box[0] + 0.02 or rr[0] > box[1] - 0.02 or rr[3] < box[2] + 0.02 or rr[2] > box[3] - 0.02:
                continue
            rects.append((abs(float(dn.mean())), name, [round(x, 3) for x in rr]))
        near = min((d for d, _, _ in rects), default=0.0)     # the Revit wall layer nearest to the face only
        rects = [(d, k, rr) for d, k, rr in rects if d <= near + 0.3]
        for _, k, _ in rects:
            kinds[k[:40]] += 1
        res.append({"obj": oname, "i": pi, "finish": fin, "c": [round(float(x), 3) for x in c[:2]],
                    "r": [round(float(x), 5) for x in r[:2]], "box": [round(x, 3) for x in box],
                    "depth_m": round(near, 2), "panes": sorted(rr for _, _, rr in rects)})
    with open(revit, "rb") as fh:
        sha = hashlib.sha256(fh.read()).hexdigest()
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"source": {"revit": os.path.basename(revit), "sha256": sha[:16], "v009": os.path.basename(v009)},
                   "panel_kinds": dict(kinds), "faces": res}, fh, ensure_ascii=False, indent=1)
    print("CWSCAN faces", len(res), "without panels", sum(1 for f in res if not f["panes"]), "kinds", dict(kinds))


if __name__ == "__main__":
    _args = sys.argv[sys.argv.index("--") + 1:]
    if _args and _args[0] == "render":
        render(_args[1:])
    elif _args and _args[0] == "uv":
        uv(_args[1:])
    elif _args and _args[0] == "winscan":
        winscan(_args[1:])
    elif _args and _args[0] == "cwscan":
        cwscan(_args[1:])
    else:
        main(_args)
