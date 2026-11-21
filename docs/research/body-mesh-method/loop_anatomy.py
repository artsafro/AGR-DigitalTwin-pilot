"""Research tool (#1742): measure how edge loops run on a body mesh (loop anatomy), Blender headless, read-only.

Pattern: n/a | new-case: loop-anatomy census of accepted/rejected OKS bodies (global levels, through stations,
corner wrap, fans, cross-wall diagonals, unwelded seams, worst facade cell) for the #1742 construction recipe.

blender -b --factory-startup --python loop_anatomy.py -- IN.(fbx|blend) OUT.json [--objects SUBSTR,...]
        [--exclude SUBSTR,...] [--rejoin] [--zmin Z --zmax Z] [--step 3.15]

Nothing is saved back; OUT.json must be new and differ from IN. Objects are taken in world space and NOT welded
across objects. --rejoin joins coplanar rectangle-like triangle pairs within 1 deg (triangulated deliveries,
as #1618/#1634). Facade face: |n.z| < 0.1. Bands: ground = centroid below zmin+6.5 m, top = above zmax-4 m.
Metrics (facade faces only, inside [zmin, zmax] when given):
- quad/tri/ngon counts per band; fans = facade vertices with >= 3 incident facade triangles;
- cross-wall diagonals = facade edges neither horizontal nor vertical (> 1 deg) whose two faces are coplanar
  (< 1 deg) - an edge with no feature reason; long = > 1 m;
- levels = z of horizontal facade edges (1 cm clusters); continuity(z) = their length / plan perimeter
  (median facade width at floor mid-heights); global >= 0.9, partial 0.1-0.9, local < 0.1;
- stations = vertical facade edges clustered by xy (1 cm); through share = stations spanning >= 90 % of the
  measured height range at that xy;
- corner wrap = corner vertices (on a vertical edge whose faces differ > 20 deg) with horizontal facade edges
  on both sides / those with at least one;
- unwelded seams = boundary-edge pairs within 2 mm (same segment, different vertices) - V004-style crack;
- cells = facade plane (normal 5 deg + offset 5 cm) x floor band (--step): irregular = tri + ngon + diagonal
  edges + fan vertices per cell; worst cell and share of cells with >= 1 irregularity (local signal, #1724).
"""
import collections
import json
import math
import os
import sys


def parse(argv):
    a = argv[argv.index("--") + 1:]
    if len(a) < 2:
        sys.exit("usage: IN OUT [--objects ..] [--exclude ..] [--rejoin] [--zmin --zmax] [--step]")
    opt = {"in": a[0], "out": a[1], "objects": [], "exclude": [], "rejoin": "--rejoin" in a,
           "zmin": None, "zmax": None, "step": 3.0}
    for k in ("objects", "exclude"):
        if "--" + k in a:
            opt[k] = [s for s in a[a.index("--" + k) + 1].split(",") if s]
    for k in ("zmin", "zmax", "step"):
        if "--" + k in a:
            v = float(a[a.index("--" + k) + 1])
            if not math.isfinite(v):
                sys.exit("non-finite --%s" % k)
            opt[k] = v
    if os.path.abspath(opt["in"]).lower() == os.path.abspath(opt["out"]).lower():
        sys.exit("refused: OUT equals IN")
    if os.path.exists(opt["out"]):
        sys.exit("refused: OUT exists")
    if opt["step"] <= 0:
        sys.exit("--step must be > 0")
    return opt


def main():
    import bmesh
    import bpy
    from mathutils import Vector
    from mathutils.kdtree import KDTree

    opt = parse(sys.argv)
    src = opt["in"]
    if not os.path.isfile(src):
        sys.exit("no input %s" % src)
    if src.lower().endswith(".blend"):
        bpy.ops.wm.open_mainfile(filepath=src, load_ui=False)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=src)
    obs = [o for o in bpy.context.scene.objects if o.type == "MESH"
           and (not opt["objects"] or any(s in o.name for s in opt["objects"]))
           and not any(s in o.name for s in opt["exclude"])]
    if not obs:
        sys.exit("no mesh object matches %r" % opt["objects"])
    bm = bmesh.new()
    for o in obs:  # world space, objects stay separate shells (no weld)
        t = bmesh.new()
        t.from_mesh(o.data)
        t.transform(o.matrix_world)
        me = bpy.data.meshes.new("tmp")
        t.to_mesh(me)
        t.free()
        bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    if not all(math.isfinite(c) for v in bm.verts for c in v.co):
        sys.exit("non-finite vertex")
    if opt["rejoin"]:
        bmesh.ops.join_triangles(bm, faces=list(bm.faces), angle_face_threshold=math.radians(1),
                                 angle_shape_threshold=math.radians(1))
    zs = [v.co.z for v in bm.verts]
    z0 = opt["zmin"] if opt["zmin"] is not None else min(zs)
    z1 = opt["zmax"] if opt["zmax"] is not None else max(zs)
    if not z1 > z0:
        sys.exit("empty z range")

    def inside(f):
        return all(z0 - 0.01 <= v.co.z <= z1 + 0.01 for v in f.verts)

    fac = [f for f in bm.faces if abs(f.normal.z) < 0.1 and f.calc_area() > 1e-6 and inside(f)]
    if not fac:
        sys.exit("no facade faces in range")
    facs = set(fac)

    def band(f):
        c = f.calc_center_median().z
        return "ground" if c < z0 + 6.5 else ("top" if c > z1 - 4.0 else "typical")

    cnt = collections.defaultdict(collections.Counter)
    for f in fac:
        n = len(f.verts)
        cnt[band(f)]["quad" if n == 4 else ("tri" if n == 3 else "ngon")] += 1
    bands = {b: dict(c, faces=sum(c.values()), quad_share=round(c["quad"] / max(1, sum(c.values())), 4))
             for b, c in cnt.items()}
    allc = sum((collections.Counter(c) for c in cnt.values()), collections.Counter())
    # fans
    fan_verts = [v for v in {v for f in fac for v in f.verts}
                 if sum(1 for f in v.link_faces if f in facs and len(f.verts) == 3) >= 3]
    # edges
    hor, ver, diag = [], [], []
    for e in {e for f in fac for e in f.edges}:
        a, b = e.verts[0].co, e.verts[1].co
        L = (b - a).length
        if L < 1e-6:
            continue
        dz = abs(b.z - a.z)
        lf = [f for f in e.link_faces if f in facs]
        if dz / L < math.sin(math.radians(1)):
            hor.append((e, L))
        elif math.hypot(b.x - a.x, b.y - a.y) / L < math.sin(math.radians(1)):
            ver.append((e, L))
        elif len(lf) == 2 and lf[0].normal.angle(lf[1].normal, 0.0) < math.radians(1):
            diag.append((e, L))
    # plan perimeter: median facade width at floor mid-heights
    step = opt["step"]
    mids = [z0 + step * (k + 0.5) for k in range(max(1, int((z1 - z0) / step)))]
    widths = []
    for zm in mids:
        w = 0.0
        for f in fac:
            fz = [v.co.z for v in f.verts]
            if min(fz) < zm < max(fz):
                xs = [(v.co.x, v.co.y) for v in f.verts]
                w += max(math.dist(p, q) for p in xs for q in xs)
        widths.append(w)
    widths.sort()
    perim = widths[len(widths) // 2]
    lev = collections.defaultdict(float)
    for e, L in hor:
        lev[round((e.verts[0].co.z + e.verts[1].co.z) / 2, 2)] += L
    levels = sorted(lev.items())
    glob = [z for z, L in levels if perim > 0 and L / perim >= 0.9]
    part = [z for z, L in levels if perim > 0 and 0.1 <= L / perim < 0.9]
    loc = [z for z, L in levels if perim > 0 and L / perim < 0.1]
    floors = max(1.0, (z1 - z0) / step)
    # stations
    st = collections.defaultdict(list)
    for e, L in ver:
        p = e.verts[0].co
        st[(round(p.x, 2), round(p.y, 2))].append((min(e.verts[0].co.z, e.verts[1].co.z),
                                                    max(e.verts[0].co.z, e.verts[1].co.z)))
    through = 0
    for k, spans in st.items():
        tot = sum(b - a for a, b in spans)
        if tot >= 0.9 * (z1 - z0):
            through += 1
    # corner wrap
    wrap = one = 0
    for e, L in ver:
        lf = [f for f in e.link_faces if f in facs]
        if len(lf) != 2 or lf[0].normal.angle(lf[1].normal, 0.0) < math.radians(20):
            continue
        for v in e.verts:
            hs = [h for h in v.link_edges if abs(h.verts[0].co.z - h.verts[1].co.z) < 1e-3
                  and any(f in facs for f in h.link_faces)]
            ns = set()
            for h in hs:
                for f in h.link_faces:
                    if f in facs:
                        ns.add(tuple(round(c, 1) for c in f.normal))
            if hs:
                one += 1
                if len(ns) >= 2:
                    wrap += 1
    # unwelded seams (all faces, any object)
    bnd = [e for e in bm.edges if len(e.link_faces) == 1]
    kd = KDTree(len(bnd))
    for i, e in enumerate(bnd):
        kd.insert((e.verts[0].co + e.verts[1].co) / 2, i)
    kd.balance()
    seams = 0
    for i, e in enumerate(bnd):
        m = (e.verts[0].co + e.verts[1].co) / 2
        for co, j, d in kd.find_range(m, 0.002):
            if j > i and not (set(e.verts) & set(bnd[j].verts)):
                seams += 1
    nonman = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    # poles
    fv = {v for f in fac for v in f.verts}
    poles = sum(1 for v in fv if len(v.link_edges) >= 6)
    # cells: facade plane x floor band
    cells = collections.defaultdict(lambda: collections.Counter())
    def cell_of(co, n):
        n2 = Vector((n.x, n.y, 0)).normalized()
        ang = round(math.degrees(math.atan2(n2.y, n2.x)) / 5) * 5
        off = round(n2.dot(Vector((co.x, co.y, 0))) / 0.05) * 0.05
        return (ang, round(off, 2), int((co.z - z0) // step))
    for f in fac:
        c = cell_of(f.calc_center_median(), f.normal)
        cells[c]["faces"] += 1
        if len(f.verts) != 4:
            cells[c]["irr"] += 1
    for e, L in diag:
        f = [f for f in e.link_faces if f in facs][0]
        cells[cell_of((e.verts[0].co + e.verts[1].co) / 2, f.normal)]["irr"] += 1
    for v in fan_verts:
        f = next(f for f in v.link_faces if f in facs)
        cells[cell_of(v.co, f.normal)]["irr"] += 1
    # module repeat: station sets at level z and z + step (Jaccard of facade vertex xy, 1 cm)
    at = collections.defaultdict(set)
    for v in fv:
        at[round(v.co.z, 2)].add((round(v.co.x, 2), round(v.co.y, 2)))
    jac = []
    for z in glob:
        z2 = round(z + step, 2)
        if z2 in at and z in at and at[z] and at[z2]:
            jac.append(len(at[z] & at[z2]) / len(at[z] | at[z2]))
    # all faces in range (caps, reveals included): shells, T-cracks, cap fans, skewed quads, slivers
    allf = [f for f in bm.faces if inside(f) and f.calc_area() > 1e-6]
    hz = [f for f in allf if abs(f.normal.z) > 0.9]
    cap_tri = sum(1 for f in hz if len(f.verts) == 3)
    cap_fan = sum(1 for v in {v for f in hz for v in f.verts}
                  if sum(1 for f in v.link_faces if f in set(hz) and len(f.verts) == 3) >= 3) if hz else 0

    def corner_angles(f):
        out = []
        for lp in f.loops:
            a = lp.link_loop_prev.vert.co - lp.vert.co
            b = lp.link_loop_next.vert.co - lp.vert.co
            if a.length > 1e-9 and b.length > 1e-9:
                out.append(math.degrees(a.angle(b)))
        return out
    skew = sum(1 for f in allf if len(f.verts) == 4 and any(abs(x - 90) > 30 for x in corner_angles(f)))
    sliver = sum(1 for f in allf if len(f.verts) == 3 and min(corner_angles(f) or [0]) < 5)
    for f in allf:  # skewed quads and non-facade faces (caps, reveal sills/heads) feed the local cell signal
        c = f.calc_center_median()
        key = cell_of(c, f.normal) if f in facs else ("h", round(c.z, 1), int((c.z - z0) // step))
        if f not in facs:
            cells[key]["faces"] += 1
        if (len(f.verts) == 4 and any(abs(x - 90) > 30 for x in corner_angles(f))) or (
                f not in facs and len(f.verts) != 4):
            cells[key]["irr"] += 1
    bverts = {v for e in bnd for v in e.verts}
    tcrack = 0
    for v in bverts:
        for co, j, d in kd.find_range(v.co, 1.0):
            e = bnd[j]
            if v in e.verts:
                continue
            a, b = e.verts[0].co, e.verts[1].co
            ab = b - a
            t = (v.co - a).dot(ab) / max(ab.length_squared, 1e-12)
            if 0.001 < t < 0.999 and (a + ab * t - v.co).length < 0.002:
                tcrack += 1
                break
    seen, shells = set(), 0
    for f in allf:
        if f in seen:
            continue
        shells += 1
        stack = [f]
        seen.add(f)
        while stack:
            g = stack.pop()
            for e in g.edges:
                for h in e.link_faces:
                    if h not in seen:
                        seen.add(h)
                        stack.append(h)
    extra = {"faces_all": len(allf), "shells": shells, "t_cracks": tcrack, "cap_faces": len(hz),
             "cap_tris": cap_tri, "cap_fans": cap_fan, "skewed_quads_30deg": skew, "slivers_5deg": sliver,
             "module_repeat_jaccard": round(sum(jac) / len(jac), 3) if jac else None}
    big = {k: c for k, c in cells.items() if c["faces"] >= 4}
    worst = max(big.items(), key=lambda kv: kv[1]["irr"], default=(None, collections.Counter()))
    rep = {
        "input": os.path.abspath(src), "objects": [o.name for o in obs], "rejoin": opt["rejoin"],
        "z_range": [round(z0, 3), round(z1, 3)], "step": step, "facade_faces": len(fac),
        "quad_share": round(allc["quad"] / len(fac), 4), "tris": allc["tri"], "ngons": allc["ngon"],
        "bands": bands, "fans": len(fan_verts),
        "diagonals": len(diag), "diagonals_long_1m": sum(1 for e, L in diag if L > 1.0),
        "diagonal_len_m": round(sum(L for e, L in diag), 2),
        "poles_v6_share": round(poles / max(1, len(fv)), 4),
        "perimeter_m": round(perim, 2), "levels_total": len(levels),
        "levels_global": len(glob), "levels_partial": len(part), "levels_local": len(loc),
        "global_per_floor": round(len(glob) / floors, 2), "partial_per_floor": round(len(part) / floors, 2),
        "stations": len(st), "stations_through_share": round(through / max(1, len(st)), 3),
        "corner_vertices": one, "corner_wrap_share": round(wrap / max(1, one), 3),
        "boundary_edges": len(bnd), "unwelded_seam_pairs": seams, "nonmanifold_edges": nonman,
        "cells": len(big), "cells_irregular_share": round(sum(1 for c in big.values() if c["irr"]) / max(1, len(big)), 4),
        "worst_cell": {"key": list(worst[0]) if worst[0] else None, **dict(worst[1])},
        **extra,
    }
    with open(opt["out"], "x", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=1)
    print("ANATOMY", json.dumps({k: rep[k] for k in ("facade_faces", "quad_share", "fans", "diagonals",
                                                       "global_per_floor", "stations_through_share",
                                                       "corner_wrap_share", "unwelded_seam_pairs",
                                                       "cells_irregular_share", "shells", "t_cracks",
                                                       "cap_tris", "cap_fans", "skewed_quads_30deg",
                                                       "slivers_5deg", "module_repeat_jaccard")}))


if __name__ == "__main__":
    main()
