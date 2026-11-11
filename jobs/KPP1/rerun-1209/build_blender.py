"""KPP1 rerun [D238] (#1209): Blender side - union bands, cut L01 openings, frames/glass/mullions, UV, FBX (VPM, NPM).

Pattern: new-case: real-object OKS body from the АС.03 drawings on the offline kernel route (Blender only does
the Boolean union / opening cuts of the kernel prisms and writes the FBX; agent-owned Blender 5.1.2 [D233]).

    blender --background --factory-startup --python-exit-code 1 --python jobs/KPP1/rerun-1209/build_blender.py -- \
        <parts-mesh.json> <out_dir> <report.json>

Writes <out_dir>/SM_Kpp_1.fbx (VPM, first) and <out_dir>/0000_Kpp_1.fbx (NPM derived from the same scene:
mullions and window/door frames dropped to texture detail, glass kept opaque) [D238] 3. Code 0000 = placeholder,
the 4-digit code is issued by SINTEZ (as in [D235]).
"""
import json
import sys
import traceback
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "methods" / "body"))
sys.path.insert(0, str(ROOT / "tools" / "methods"))
from body_blender import cut_openings  # noqa: E402

FRAME_W, FRAME_D, GLASS_BACK = 0.06, 0.07, 0.08


def obj_from(name, verts, tris):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(t) for t in tris])
    me.validate()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def union_into(target, other):
    mod = target.modifiers.new("u", "BOOLEAN")
    mod.operation, mod.solver, mod.object = "UNION", "EXACT", other
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(other)


def add_box(bm, lo, hi):
    r = bmesh.ops.create_cube(bm, size=1.0)
    for v in r["verts"]:
        v.co = Vector(lo[i] + (v.co[i] + 0.5) * (hi[i] - lo[i]) for i in range(3))


def fill_openings(sched, report):
    rep = {r["id"]: r for r in report}
    win, door, glass = bmesh.new(), bmesh.new(), bmesh.new()
    for o in sched:
        r = rep[o["id"]]
        lo, hi = list(o["min"]), list(o["max"])
        ax = 1 if r["facade"] in ("Южный", "Северный") else 0
        outward = -1 if r["facade"] in ("Южный", "Западный") else 1
        back = hi[ax] if outward < 0 else lo[ax]           # recess back = inner end of the cutter
        plane = back + outward * GLASS_BACK                 # glass / leaf plane, GLASS_BACK in front of the back
        u_ax = 0 if ax == 1 else 1
        u0, u1, z0, z1 = lo[u_ax], hi[u_ax], lo[2], hi[2]
        def slab(bm, a0, a1, b0, b1, d0, d1):
            l, h = [0, 0, 0], [0, 0, 0]
            l[u_ax], h[u_ax], l[2], h[2] = a0, a1, b0, b1
            l[ax], h[ax] = min(d0, d1), max(d0, d1)
            add_box(bm, l, h)
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
    out = {}
    for name, bm in (("Windows", win), ("Doors", door), ("Glass", glass)):
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        out[name] = ob
    return out


def mullions(mboxes, sched):
    bm = bmesh.new()
    kept = 0
    for m in mboxes:
        c = [(m["min"][i] + m["max"][i]) / 2 for i in range(3)]
        inside = any(all(o["min"][i] - 1e-3 <= c[i] <= o["max"][i] + 1e-3 for i in range(3)) for o in sched)
        if inside:
            add_box(bm, m["min"], m["max"])
            kept += 1
    me = bpy.data.meshes.new("CurtainWall_Mullions")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("CurtainWall_Mullions", me)
    bpy.context.scene.collection.objects.link(ob)
    return ob, kept


def finish(ob, mat):
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-6)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.01)
    bpy.ops.object.mode_set(mode="OBJECT")
    ob.data.materials.clear()
    ob.data.materials.append(mat)


def export(objs, out):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.fbx(filepath=str(out), use_selection=True, object_types={"MESH"},
                             apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", mesh_smooth_type="FACE",
                             use_mesh_modifiers=True, add_leaf_bones=False, bake_anim=False, axis_forward="-Z", axis_up="Y")


UCX_NAMES = []


def join(objs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = ob.data.name = name
    return ob


def ucx_boxes(data):
    """Convex collision boxes (VPM V010): band 0.000-3.900 as three boxes around the south recess, band above one box."""
    p = data["params"]
    x0, y0, x1, y1 = p["l1_rect_m"]
    rx0, rx1, ry1 = p["recess_m"]
    boxes = [((x0, y0, 0.0), (rx0, y1, 3.9)), ((rx1, y0, 0.0), (x1, y1, 3.9)), ((rx0, ry1, 0.0), (rx1, y1, 3.9)),
             ((x0, y0, 3.9), (x1, y1, p["parapet_top_m"]))]
    out = []
    UCX_NAMES.clear()
    for i, (lo, hi) in enumerate(boxes, 1):
        bm = bmesh.new()
        add_box(bm, lo, hi)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        name = f"UCX_SM_Kpp_1_Main_{i:03d}"
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        out.append(ob)
        UCX_NAMES.append(name)
    return out


def tris(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    src, out_dir, rep_p = Path(argv[0]), Path(argv[1]), Path(argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads(src.read_text(encoding="utf-8"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bands = data["parts"]["body_bands"]
    body = obj_from("Body_Walls", bands[0]["vertices"], bands[0]["triangles"])
    for b in bands[1:]:
        union_into(body, obj_from(b["name"], b["vertices"], b["triangles"]))
    cut = cut_openings(body, data["openings"])
    fills = fill_openings(data["openings"], data["openings_report"])
    mull, kept = mullions(data["mullions"], data["openings"])
    roof = obj_from("Roof_Plate", data["parts"]["Roof_Plate"]["vertices"], data["parts"]["Roof_Plate"]["triangles"])
    par = obj_from("Parapet", data["parts"]["Parapet"]["vertices"], data["parts"]["Parapet"]["triangles"])
    mats = {n: bpy.data.materials.new(n) for n in ("M_Kpp_1_1", "M_Kpp_1_2", "M_Kpp_1_3", "M_Kpp_1_4", "M_Kpp_1_MainGlass_1")}
    plan = [(body, "M_Kpp_1_1"), (par, "M_Kpp_1_1"), (roof, "M_Kpp_1_2"), (fills["Windows"], "M_Kpp_1_3"),
            (fills["Doors"], "M_Kpp_1_4"), (mull, "M_Kpp_1_3"), (fills["Glass"], "M_Kpp_1_MainGlass_1")]
    for ob, m in plan:
        finish(ob, mats[m])
    counts = {ob.name: tris(ob) for ob, _ in plan}   # per part, before the regulation join (Glass = Windows glass)
    # NPM derived from the VPM parts [D238] 3: window frames and mullions dropped to texture detail
    npm_counts = {k: v for k, v in counts.items() if k not in ("Windows", "CurtainWall_Mullions")}
    npm_src = [ob.copy() for ob, _ in plan if ob.name not in ("Windows", "CurtainWall_Mullions")]
    for c in npm_src:
        c.data = c.data.copy()
        bpy.context.scene.collection.objects.link(c)
    vpm_main = join([ob for ob, _ in plan if ob.name != "Glass"], "SM_Kpp_1_Main")
    vpm_glass = join([fills["Glass"]], "SM_Kpp_1_MainGlass")
    ucx = ucx_boxes(data)
    vpm = out_dir / "SM_Kpp_1.fbx"
    export([vpm_main, vpm_glass] + ucx, vpm)
    for o in [vpm_main, vpm_glass] + ucx:
        bpy.data.objects.remove(o)
    npm_opaque = [c for c in npm_src if not c.name.startswith("Glass")]
    npm_glass_src = [c for c in npm_src if c.name.startswith("Glass")]
    npm_main = join(npm_opaque, "SM_Kpp_1_001_Main")
    npm_glass = join(npm_glass_src, "SM_Kpp_1_001_MainGlass")
    npm = out_dir / "0000_Kpp_1_01.fbx"
    export([npm_main, npm_glass], npm)
    rep = {"ok": True, "vpm": str(vpm), "npm": str(npm), "triangles_vpm_parts": counts,
           "triangles_vpm_total": sum(counts.values()), "triangles_npm_parts": npm_counts,
           "triangles_npm_total": sum(npm_counts.values()), "ucx": [o_name for o_name in UCX_NAMES],
           "meshes_vpm": ["SM_Kpp_1_Main", "SM_Kpp_1_MainGlass"] + UCX_NAMES,
           "meshes_npm": ["SM_Kpp_1_001_Main", "SM_Kpp_1_001_MainGlass"],
           "openings_cut": cut, "mullions_kept": kept, "mullions_listed": len(data["mullions"]),
           "blender": bpy.app.version_string}
    rep_p.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print("KPP1_BUILD", json.dumps({k: v for k, v in rep.items() if k != "openings_cut"}, ensure_ascii=False))


try:
    main()
except Exception:
    traceback.print_exc()
    sys.exit(1)
