"""KPP1 #1416: derived NPM Ground copy under the 180 000 triangle budget [D298].

Pattern: n/a | new-case: job script, collapse-decimate only the Flora mesh of a COPY of the
customer NPM Ground until the whole Ground is <= the target; customer original untouched.

Run (Blender 5.1.2, headless):
  blender -b --factory-startup -noaudio --python simplify_ground.py -- <src.fbx> <sha256> <new_out_dir> [target] [protect.json]

protect.json (optional): {"radius_m": r, "points": [[x, y, z], ...]} - every Flora loose part with a
vertex within r of a point is kept out of the decimation (used to stop the decimation from adding
xView overlaps: points = centres of face pairs new in the first run's xView, see REPORT.md).

Fail-closed: wrong input hash, output dir existing or equal to / inside the input dir, NaN/inf
vertices, unchanged non-Flora geometry drift, renamed objects/materials/UV layers, UV bounds
outside the source bounds, or a result above the target all exit nonzero (the output dir is
written as `<out>.partial` and renamed only at the very end).
"""
import bpy
import hashlib
import json
import math
import os
import sys

from mathutils.bvhtree import BVHTree

LIMIT = 180000
FLORA = "SM_77_05_0009005_117_Flora"


def die(msg):
    print("SIMPLIFY-FAIL", msg)
    sys.exit(2)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def census():
    out = {}
    for o in sorted((o for o in bpy.data.objects if o.type == "MESH"), key=lambda o: o.name):
        me = o.data
        uv = me.uv_layers.active
        us = [d.uv for d in uv.data] if uv else []
        for v in me.vertices:
            if not all(math.isfinite(c) for c in v.co):
                die(f"non-finite vertex in {o.name}")
        out[o.name] = {
            "tris": sum(len(p.vertices) - 2 for p in me.polygons),
            "polys": len(me.polygons),
            "verts": len(me.vertices),
            "materials": [m.name if m else None for m in me.materials],
            "uv_layers": [l.name for l in me.uv_layers],
            "uv_bounds": [min(u.x for u in us), min(u.y for u in us), max(u.x for u in us), max(u.y for u in us)] if us else None,
            "matrix": [list(r) for r in o.matrix_world],
        }
    return out


def geom_key(o):
    return sorted(tuple(round(c, 6) for c in v.co) for v in o.data.vertices)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    if len(argv) < 3:
        die("usage: <src.fbx> <sha256> <new_out_dir> [target]")
    src, want, out = os.path.realpath(argv[0]), argv[1], os.path.realpath(argv[2])
    target = int(argv[3]) if len(argv) > 3 else 179900
    protect = {"radius_m": 0.0, "points": []}
    if len(argv) > 4:
        with open(argv[4], encoding="utf-8") as f:
            protect = json.load(f)
        r0 = protect.get("radius_m", float("nan"))
        if not protect.get("points") or not isinstance(r0, (int, float)) or not math.isfinite(r0) or r0 <= 0:
            die("protect.json needs points and a finite radius_m > 0")
    if not 0 < target <= LIMIT:
        die(f"target {target} outside 1..{LIMIT}")
    if os.path.exists(out) or os.path.exists(out + ".partial"):
        die(f"output exists: {out}")
    sdir = os.path.dirname(src)
    if out == sdir or out.startswith(sdir + os.sep) or out == src:
        die("output dir aliases / sits inside the input dir")
    got = sha(src)
    if got != want:
        die(f"input hash {got} != {want}")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=src)
    before = census()
    if FLORA not in before:
        die(f"mesh {FLORA} absent; meshes: {sorted(before)}")
    total0 = sum(c["tris"] for c in before.values())
    need = total0 - target
    if need <= 0:
        die(f"already {total0} <= {target}; nothing to simplify")
    flora = bpy.data.objects[FLORA]
    keep = {n: geom_key(bpy.data.objects[n]) for n in before if n != FLORA}
    orig_verts = [flora.matrix_world @ v.co for v in flora.data.vertices]
    n0 = before[FLORA]["tris"]

    # Protected loose parts go to a separate object and are joined back after the decimation.
    prot, protected = None, {"parts": 0, "tris": 0}
    if protect["points"]:
        import bmesh
        from mathutils import Vector
        from mathutils.kdtree import KDTree
        kd = KDTree(len(protect["points"]))
        for i, p in enumerate(protect["points"]):
            kd.insert(Vector(p), i)
        kd.balance()
        bm = bmesh.new()
        bm.from_mesh(flora.data)
        bm.verts.ensure_lookup_table()
        mw = flora.matrix_world
        seen, pv, parts = set(), set(), 0
        for v in bm.verts:
            if v.index in seen:
                continue
            comp, stack = [], [v]
            seen.add(v.index)
            while stack:
                x = stack.pop()
                comp.append(x.index)
                for e in x.link_edges:
                    y = e.other_vert(x)
                    if y.index not in seen:
                        seen.add(y.index)
                        stack.append(y)
            if any(kd.find(mw @ bm.verts[i].co)[2] <= protect["radius_m"] for i in comp):
                pv.update(comp)
                parts += 1
        if not pv:
            die("protect.json matched no Flora vertex")
        bm.faces.ensure_lookup_table()
        keep_idx = {f.index for f in bm.faces if all(x.index in pv for x in f.verts)}
        prot_bm = bm.copy()
        prot_bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index in keep_idx], context="FACES")
        bmesh.ops.delete(prot_bm, geom=[f for f in prot_bm.faces if f.index not in keep_idx], context="FACES")
        pme = flora.data.copy()
        prot_bm.to_mesh(pme)
        bm.to_mesh(flora.data)
        bm.free()
        prot_bm.free()
        prot = bpy.data.objects.new("protected_flora", pme)
        prot.matrix_world = flora.matrix_world
        bpy.context.scene.collection.objects.link(prot)
        protected = {"parts": parts, "tris": len(pme.polygons)}
        n0 -= protected["tris"]
        if n0 + protected["tris"] != before[FLORA]["tris"]:
            die("protected split lost triangles")
        print("PROTECT", json.dumps(protected))

    # Binary search over the collapse ratio on copies until the Flora loses >= need triangles
    # with the fewest removals (smallest error edges go first in collapse decimation).
    base = flora.data.copy()
    lo, hi, best = 0.90, 1.0, None
    for _ in range(25):
        r = (lo + hi) / 2
        flora.data = base.copy()
        m = flora.modifiers.new("dec", "DECIMATE")
        m.decimate_type = "COLLAPSE"
        m.ratio = r
        m.use_collapse_triangulate = True
        bpy.context.view_layer.objects.active = flora
        bpy.ops.object.modifier_apply(modifier=m.name)
        t = sum(len(p.vertices) - 2 for p in flora.data.polygons)
        if n0 - t >= need:
            best = (r, flora.data.copy(), t)
            lo = r
        else:
            hi = r
    if best is None:
        die("no ratio reached the target")
    r, mesh, t = best
    flora.data = mesh
    flora.data.name = base.name
    if prot is not None:
        bpy.ops.object.select_all(action="DESELECT")
        prot.select_set(True)
        flora.select_set(True)
        bpy.context.view_layer.objects.active = flora
        bpy.ops.object.join()
    after = census()
    total1 = sum(c["tris"] for c in after.values())
    if total1 > target:
        die(f"result {total1} > target {target}")
    for n, c in before.items():
        a = after.get(n)
        if a is None or a["materials"] != c["materials"] or a["uv_layers"] != c["uv_layers"] or a["matrix"] != c["matrix"]:
            die(f"identity changed on {n}")
        lo_ok = all(a["uv_bounds"][i] >= c["uv_bounds"][i] - 1e-6 for i in (0, 1))
        hi_ok = all(a["uv_bounds"][i] <= c["uv_bounds"][i] + 1e-6 for i in (2, 3))
        if not (lo_ok and hi_ok):
            die(f"UV bounds of {n} left the source bounds (UDIM change)")
    for n, k in keep.items():
        if geom_key(bpy.data.objects[n]) != k:
            die(f"non-Flora mesh {n} changed")

    # Deviation of every original Flora vertex from the simplified surface.
    mw = flora.matrix_world
    bvh = BVHTree.FromPolygons([mw @ v.co for v in flora.data.vertices], [p.vertices[:] for p in flora.data.polygons])
    d = sorted(bvh.find_nearest(p)[3] for p in orig_verts)
    dev = {"max_m": d[-1], "p99_m": d[int(len(d) * 0.99)], "p95_m": d[int(len(d) * 0.95)],
           "moved_gt_1mm": sum(1 for x in d if x > 0.001), "verts": len(d)}

    part = out + ".partial"
    os.makedirs(part)
    fbx = os.path.join(part, "0000_Kpp_1_Ground.fbx")
    bpy.ops.export_scene.fbx(filepath=fbx, use_selection=False, object_types={"MESH"},
                             apply_unit_scale=True, use_mesh_modifiers=False, add_leaf_bones=False,
                             mesh_smooth_type="FACE", bake_anim=False, path_mode="AUTO")
    report = {"source": src, "source_sha256": got, "limit": LIMIT, "target": target,
              "ratio": r, "protected": protected, "protect_input": protect, "before": before, "after": after, "total_before": total0, "total_after": total1,
              "removed": total0 - total1, "flora_deviation": dev, "output_fbx": "0000_Kpp_1_Ground.fbx",
              "output_sha256": sha(fbx), "blender": bpy.app.version_string}
    for c in list(report["before"].values()) + list(report["after"].values()):
        c.pop("matrix", None)
    with open(os.path.join(part, "simplify-report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    os.rename(part, out)
    print("SIMPLIFY-OK", json.dumps({k: report[k] for k in ("total_before", "total_after", "removed", "ratio")}), json.dumps(dev))


main()
