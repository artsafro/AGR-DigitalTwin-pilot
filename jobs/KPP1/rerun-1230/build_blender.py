"""KPP1 #1230 Blender build: one Exact-Boolean union of every opaque part (no touching / intersecting shells left
in SM_Kpp_1_Main, V004), all L01 mullions, the east Stair, finish UDIM UVs + textures, VPM FBX + ZIP, NPM FBX.

Pattern: new-case: real-object OKS body from the АС.03 drawings on the offline kernel route (agent-owned Blender
5.1.2 [D233], `path: deviation`, Max busy); successor of jobs/KPP1/rerun-1209/build_blender.py.

    blender --background --factory-startup --python-exit-code 1 --python jobs/KPP1/rerun-1230/build_blender.py -- \
        <parts.json> <tex_dir> <out_dir> <report.json>

- body: bands union, L01 openings cut (tools/methods/body/body_blender.cut_openings), frames / door leaves /
  mullions / stair / roof / parapet as closed boxes or prisms, then ONE Boolean UNION (Exact, self-intersection,
  material transfer) -> SM_Kpp_1_Main. Glass stays its own mesh (MainGlass), not unioned.
- texel cuts: the union is bisected by planes (z = finish band limits and a 0.9 m grid in x / y / z) so every
  face fits its 2.048 m UDIM tile after a whole-period shift; a plane closer than 5 mm to a vertex coordinate
  is moved off it (no new near-duplicate vertices).
- weld: vertices closer than 4 mm are merged and the slivers collapsed (V004 duplicate tolerance 2 mm).
- finish per face from the part material (finishes.json); body / parapet faces by band of the centroid height.
- UV: one channel, world-metre projection (no mirroring), tile = 1001 + finish index, density 1000 px/m;
  any face overflowing its tile -> RuntimeError naming the finish (fail-closed, no silent clamp).
- VPM FBX has no texture paths (reg p.30 §4.2); SM_Kpp_1.zip = FBX + the 21 PNG (no GeoJSON: placement deferred).
- NPM: same union without window frames and mullions [D238] 3, UV -> atlas cells, atlas embedded.
- UCX: four boxes inset 3 mm per side -> 6 mm neighbour gaps (V010 band 2-10 mm [D098]).
Output paths equal to an input -> exit 4 before anything is written.
"""
import json
import math
import sys
import traceback
import zipfile
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "methods" / "body"))
sys.path.insert(0, str(ROOT / "tools" / "methods"))
from body_blender import cut_openings  # noqa: E402

HERE = Path(__file__).resolve().parent
FINISH = json.loads((HERE / "finishes.json").read_text(encoding="utf-8"))
FRAME_W, FRAME_D, GLASS_BACK = 0.06, 0.07, 0.08
GRID_M, PAD_M, AVOID_M = 0.9, 0.04, 0.005
UCX_INSET = 0.003
WELD_M = 0.004                      # > the 2 mm V004 duplicate tolerance, with margin for chains
PART_MATS = ("Body", "Parapet", "Roof_Plate", "Windows", "CurtainWall_Mullions", "Doors", "Stair")


def link(name, me):
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def obj_from(name, verts, tris):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(t) for t in tris])
    me.validate()
    return link(name, me)


def add_box(bm, lo, hi):
    r = bmesh.ops.create_cube(bm, size=1.0)
    for v in r["verts"]:
        v.co = Vector(lo[i] + (v.co[i] + 0.5) * (hi[i] - lo[i]) for i in range(3))


def bm_obj(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return link(name, me)


def apply_bool(target, op, operand, use_self=False, collection=None):
    mod = target.modifiers.new("b", "BOOLEAN")
    mod.operation, mod.solver = op, "EXACT"
    if collection is not None:
        mod.operand_type, mod.collection = "COLLECTION", collection
    else:
        mod.object = operand
    mod.use_self = use_self
    if hasattr(mod, "material_mode"):
        mod.material_mode = "TRANSFER"
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=mod.name)


def set_mat(ob, mat):
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.material_index = 0


def fill_openings(sched, report):
    rep = {r["id"]: r for r in report}
    win, door, glass = bmesh.new(), bmesh.new(), bmesh.new()
    for o in sched:
        r = rep[o["id"]]
        lo, hi = list(o["min"]), list(o["max"])
        ax = 1 if r["facade"] in ("Южный", "Северный") else 0
        outward = -1 if r["facade"] in ("Южный", "Западный") else 1
        back = hi[ax] if outward < 0 else lo[ax]
        plane = back + outward * GLASS_BACK
        u_ax = 0 if ax == 1 else 1
        u0, u1, z0, z1 = lo[u_ax], hi[u_ax], lo[2], hi[2]

        def slab(bm, a0, a1, b0, b1, d0, d1):
            lo_, hi_ = [0, 0, 0], [0, 0, 0]
            lo_[u_ax], hi_[u_ax], lo_[2], hi_[2] = a0, a1, b0, b1
            lo_[ax], hi_[ax] = min(d0, d1), max(d0, d1)
            add_box(bm, lo_, hi_)
        p0, p1 = plane - FRAME_D / 2, plane + FRAME_D / 2
        frame = door if r["kind"] == "door" else win
        slab(frame, u0, u1, z0, z0 + FRAME_W, p0, p1)
        slab(frame, u0, u1, z1 - FRAME_W, z1, p0, p1)
        slab(frame, u0, u0 + FRAME_W, z0 + FRAME_W, z1 - FRAME_W, p0, p1)
        slab(frame, u1 - FRAME_W, u1, z0 + FRAME_W, z1 - FRAME_W, p0, p1)
        if r["kind"] == "door":
            slab(door, u0 + FRAME_W, u1 - FRAME_W, z0 + FRAME_W, z1 - FRAME_W, plane - 0.02, plane + 0.02)
        else:
            slab(glass, u0 + FRAME_W, u1 - FRAME_W, z0 + FRAME_W, z1 - FRAME_W, plane - 0.005, plane + 0.005)
    return {"Windows": bm_obj("Windows", win), "Doors": bm_obj("Doors", door), "Glass": bm_obj("Glass", glass)}


def boxes_obj(name, boxes):
    bm = bmesh.new()
    for b in boxes:
        add_box(bm, b["min"], b["max"])
    return bm_obj(name, bm)


def build_body(data):
    bands = data["parts"]["body_bands"]
    body = obj_from("Body", bands[0]["vertices"], bands[0]["triangles"])
    for b in bands[1:]:
        other = obj_from(b["name"], b["vertices"], b["triangles"])
        apply_bool(body, "UNION", other)
        bpy.data.objects.remove(other)
    cut = cut_openings(body, data["openings"])
    return body, cut


def union_parts(name, body, others, mats):
    """body UNION all others in one Exact Boolean with self-intersection; returns the joined object."""
    coll = bpy.data.collections.new(f"ops_{name}")
    bpy.context.scene.collection.children.link(coll)
    target = body.copy()
    target.data = body.data.copy()
    bpy.context.scene.collection.objects.link(target)
    set_mat(target, mats["Body"])
    for part, ob in others:
        c = ob.copy()
        c.data = ob.data.copy()
        set_mat(c, mats[part])
        coll.objects.link(c)
    apply_bool(target, "UNION", None, use_self=True, collection=coll)
    for c in list(coll.objects):
        bpy.data.objects.remove(c)
    bpy.data.collections.remove(coll)
    target.name = target.data.name = name
    return target


def finish_of(mat_name, z):
    f = FINISH["parts"][mat_name]
    if f != "@bands":
        return f
    for top, band in FINISH["body_bands"]:
        if z < top:
            return band
    raise RuntimeError(f"no band for z={z}")


def planes(coords, lo, hi, fixed=()):
    out = []
    vals = sorted(set(round(c, 6) for c in coords))
    import bisect as _b
    def clear(p):
        i = _b.bisect_left(vals, p)
        return all(abs(vals[j] - p) >= AVOID_M for j in (i - 1, i) if 0 <= j < len(vals))
    cands = list(fixed) + [lo + GRID_M * k for k in range(1, int((hi - lo) / GRID_M) + 1)]
    for p in cands:
        q = p
        for step in range(40):
            if clear(q):
                break
            q = p + (step // 2 + 1) * AVOID_M * (1 if step % 2 == 0 else -1)
        else:
            raise RuntimeError(f"no clear bisect plane near {p}")
        if lo < q < hi:
            out.append(q)
    return out


def texel_cut(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    xs, ys, zs = ([v.co[i] for v in bm.verts] for i in range(3))
    for axis, coords, fixed in ((2, zs, [b for b, _ in FINISH["body_bands"][:-1]]), (0, xs, ()), (1, ys, ())):
        for p in planes(coords, min(coords), max(coords), fixed):
            n = [0.0, 0.0, 0.0]
            n[axis] = 1.0
            co = [0.0, 0.0, 0.0]
            co[axis] = p
            geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
            bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=n, dist=1e-6)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-6)
    bm.to_mesh(ob.data)
    bm.free()


def project(co, n):
    ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
    if az >= ax and az >= ay:
        return Vector((co.x, co.y)) if n.z > 0 else Vector((co.x, -co.y))
    if ax >= ay:
        return Vector((co.y, co.z)) if n.x > 0 else Vector((-co.y, co.z))
    return Vector((-co.x, co.z)) if n.y > 0 else Vector((co.x, co.z))


def uv_finish(ob, tex, npm=False):
    """Assign the finish material index and the UDIM (VPM) or atlas (NPM) UV; returns per-finish QA."""
    me = ob.data
    names = [m.name.split(".")[0] for m in me.materials]
    S, table = tex["S_m"], tex["finishes"]
    cell, npm_size, npad = tex["npm"]["cell"], tex["npm"]["size"], tex["npm"]["pad"]
    bm = bmesh.new()
    bm.from_mesh(me)
    # V004 counts vertices closer than 2 mm as duplicates: weld at WELD_M, collapse the slivers it leaves
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=WELD_M)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=WELD_M)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-6)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    loose = [v for v in bm.verts if not v.link_faces] + [e for e in bm.edges if not e.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS" if all(isinstance(g, bmesh.types.BMVert) for g in loose) else "EDGES")
    loose_v = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose_v, context="VERTS")
    uvl = bm.loops.layers.uv.new("UVMap")
    order = FINISH["order"]
    qa = {}
    for f in bm.faces:
        part = names[f.material_index]
        fin = finish_of(part, f.calc_center_median().z)
        t = table[fin]
        uvs = [project(l.vert.co, f.normal) for l in f.loops]
        per = t["P"] or [0.1, 0.1]
        umin, vmin = min(u.x for u in uvs), min(u.y for u in uvs)
        su = math.floor((umin - PAD_M) / per[0]) * per[0]
        sv = math.floor((vmin - PAD_M) / per[1]) * per[1]
        local = [Vector(((u.x - su) / S, (u.y - sv) / S)) for u in uvs]
        hi = max(max(p.x, p.y) for p in local)
        q = qa.setdefault(fin, {"udim": t["udim"], "faces": 0, "overflow": 0, "max_local": 0.0})
        q["faces"] += 1
        q["max_local"] = round(max(q["max_local"], hi), 4)
        if hi > 1.0 - PAD_M / S / 2 or min(min(p.x, p.y) for p in local) < 0:
            q["overflow"] += 1
        if npm:
            cx, cy = t["cell"]
            scale = (cell - 2 * npad) / npm_size
            base = Vector(((cx * cell + npad) / npm_size, (cy * cell + npad) / npm_size))
            for l, p in zip(f.loops, local):
                l[uvl].uv = base + p * scale
        else:
            i = t["udim"] - 1001
            off = Vector((i % 10, i // 10))
            for l, p in zip(f.loops, local):
                l[uvl].uv = p + off
        f.material_index = order.index(fin)
    bm.to_mesh(me)
    bm.free()
    bad = {k: v for k, v in qa.items() if v["overflow"]}
    if bad:
        raise RuntimeError(f"{ob.name}: faces overflow their UV tile: {bad}")
    unused = [f for f in order if f not in qa and not (npm and f == "Frame_RAL9016")]
    return qa, unused


def glass_uv(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    uvl = bm.loops.layers.uv.new("UVMap")
    pts = {f: [project(l.vert.co, f.normal) for l in f.loops] for f in bm.faces}
    allu = [p for v in pts.values() for p in v]
    if allu:
        u0, v0 = min(p.x for p in allu), min(p.y for p in allu)
        ext = max(max(p.x for p in allu) - u0, max(p.y for p in allu) - v0) / 0.9 or 1.0
        for f, uvs in pts.items():
            for l, p in zip(f.loops, uvs):
                l[uvl].uv = Vector(((p.x - u0) / ext + 0.05, (p.y - v0) / ext + 0.05))
    bm.to_mesh(ob.data)
    bm.free()


def material(name, image=None, rgb=(0.7, 0.7, 0.7, 1.0), alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = rgb
    b.inputs["Alpha"].default_value = alpha
    if image is not None:
        t = m.node_tree.nodes.new("ShaderNodeTexImage")
        t.image = image
        m.node_tree.links.new(t.outputs["Color"], b.inputs["Base Color"])
    return m


def collapse_materials(ob, mat):
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.material_index = 0


def ucx_boxes(data, prefix):
    p = data["params"]
    x0, y0, x1, y1 = p["l1_rect_m"]
    rx0, rx1, ry1 = p["recess_m"]
    boxes = [((x0, y0, 0.0), (rx0, y1, 3.9)), ((rx1, y0, 0.0), (x1, y1, 3.9)), ((rx0, ry1, 0.0), (rx1, y1, 3.9)),
             ((x0, y0, 3.9), (x1, y1, p["parapet_top_m"]))]
    out = []
    for i, (lo, hi) in enumerate(boxes, 1):
        bm = bmesh.new()
        add_box(bm, [c + UCX_INSET for c in lo], [c - UCX_INSET for c in hi])
        bmesh.ops.triangulate(bm, faces=bm.faces)
        out.append(bm_obj(f"UCX_{prefix}_{i:03d}", bm))
    return out


def export(objs, out, embed=False):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    kw = dict(path_mode="COPY", embed_textures=True) if embed else dict(path_mode="STRIP")
    bpy.ops.export_scene.fbx(filepath=str(out), use_selection=True, object_types={"MESH"},
                             apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", mesh_smooth_type="FACE",
                             use_mesh_modifiers=True, add_leaf_bones=False, bake_anim=False,
                             axis_forward="-Z", axis_up="Y", **kw)


def tris(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    src, tex_dir, out_dir, rep_p = Path(argv[0]), Path(argv[1]), Path(argv[2]), Path(argv[3])
    inputs = {src.resolve(), tex_dir.resolve()}
    outs = [out_dir.resolve(), rep_p.resolve()]
    if any(o in inputs for o in outs) or rep_p.resolve().parent == tex_dir.resolve():
        print("an output path resolves to an input", file=sys.stderr)
        sys.exit(4)
    data = json.loads(src.read_text(encoding="utf-8"))
    tex = json.loads((tex_dir / "textures.json").read_text(encoding="utf-8"))
    if tex["finishes"].keys() != set(FINISH["order"]):
        raise RuntimeError(f"textures.json finishes {sorted(tex['finishes'])} != finishes.json order")
    out_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mats = {p: bpy.data.materials.new(p) for p in PART_MATS}
    body, cut = build_body(data)
    fills = fill_openings(data["openings"], data["openings_report"])
    mull = boxes_obj("CurtainWall_Mullions", data["mullions"])
    stair = boxes_obj("Stair", data["stair"])
    roof = obj_from("Roof_Plate", data["parts"]["Roof_Plate"]["vertices"], data["parts"]["Roof_Plate"]["triangles"])
    par = obj_from("Parapet", data["parts"]["Parapet"]["vertices"], data["parts"]["Parapet"]["triangles"])
    parts = [("Parapet", par), ("Roof_Plate", roof), ("Windows", fills["Windows"]), ("Doors", fills["Doors"]),
             ("CurtainWall_Mullions", mull), ("Stair", stair)]
    counts = {"Body_Walls": tris(body), **{n: tris(o) for n, o in parts}}
    vpm_main = union_parts("SM_Kpp_1_Main", body, parts, mats)
    npm_main = union_parts("SM_Kpp_1_001_Main", body, [p for p in parts if p[0] not in ("Windows", "CurtainWall_Mullions")], mats)
    for ob in (vpm_main, npm_main):
        texel_cut(ob)
    qa_vpm, unused_vpm = uv_finish(vpm_main, tex)
    qa_npm, unused_npm = uv_finish(npm_main, tex, npm=True)
    if unused_vpm or unused_npm:
        raise RuntimeError(f"finishes without faces (unused maps): VPM {unused_vpm}, NPM {unused_npm}")
    a = tex["address"]
    vpm_tris = tris(vpm_main)
    collapse_materials(vpm_main, material(f"M_{a}_Main_1"))
    glass = fills["Glass"]
    glass.name = glass.data.name = "SM_Kpp_1_MainGlass"
    glass_uv(glass)
    collapse_materials(glass, material(f"M_{a}_MainGlass_1", rgb=(0.6, 0.75, 0.8, 1.0), alpha=0.3))
    ucx = ucx_boxes(data, "SM_Kpp_1_Main")
    vpm = out_dir / "SM_Kpp_1.fbx"
    export([vpm_main, glass] + ucx, vpm)
    for o in [vpm_main] + ucx:
        bpy.data.objects.remove(o)
    atlas = bpy.data.images.load(str(tex_dir / f"T_{a}_001_Main_d_1.png"))
    collapse_materials(npm_main, material(f"M_{a}_001_Main_1", image=atlas))
    glass.name = glass.data.name = "SM_Kpp_1_001_MainGlass"
    npm = out_dir / "0000_Kpp_1_01.fbx"
    export([npm_main, glass], npm, embed=True)
    zpath = out_dir / "SM_Kpp_1.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(vpm, vpm.name)
        for png in sorted(tex_dir.glob(f"T_{a}_*_1.1*.png")):
            z.write(png, png.name)
    rep = {"ok": True, "issue": 1230, "vpm": str(vpm), "vpm_zip": str(zpath), "npm": str(npm),
           "triangles_parts_before_union": counts, "triangles_vpm_main": vpm_tris, "triangles_glass": tris(glass),
           "uv_qa_vpm": qa_vpm, "uv_qa_npm": qa_npm, "openings_cut": len(cut),
           "mullions_built": len(data["mullions"]), "mullions_dropped": len(data["mullions_dropped"]),
           "mullion_inserts": data["mullion_inserts"], "stair_boxes": len(data["stair"]),
           "ucx_inset_m": UCX_INSET, "blender": bpy.app.version_string}
    rep["triangles_npm_main"] = tris(npm_main)
    rep_p.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print("KPP1_BUILD", json.dumps(rep, ensure_ascii=False))


try:
    main()
except SystemExit:
    raise
except Exception:
    traceback.print_exc()
    sys.exit(1)
