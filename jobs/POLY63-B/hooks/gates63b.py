"""Whole-model gates for #1619 stage 1 (Artem verdict 63B v006): no location filter, every hit listed.

Pattern: n/a | new-case: whole-model readback gates for the two-ring tower 63B.

blender -b --factory-startup --python gates63b.py -- MODEL.fbx OUT.json [--band-z Z0 Z1] [--drop-face-at X Y Z]

--drop-face-at: mutation probe, deletes the face nearest to the point before the gates (acceptance: a deleted wall
quad must give open_boundary_edges >= 4 and passed_zero_gates false).

Read back the FBX (fresh scene, Blender importer) and count, over the WHOLE mesh:
- open_boundary_edges: boundary edges that are not an opening rim and not on the band cut (z0 / z1, the stage band
  is a storey slice). Opening rim (the open back of a reveal tube, body with openings only) is classified by
  STRUCTURE, not size (review P1, PR #1661): the boundary loop is one simple closed cycle and every face on it is a
  reveal face, i.e. perpendicular to the local hole plane at its edge (plane of the edge and the direction to the
  loop centre, |cos| < 0.3; local, so a window wrapping a facade kink keeps its bent rim). A hole left by a missing
  wall or reveal face is bounded by faces lying in the hole surface and stays open at any size
  (classify_boundary_loop, tests/test_poly63b_gates.py).
- nonmanifold_edges: edges with more than 2 faces.
- gap_vertices: vertices within 5 cm of a face that does not contain them (and is not adjacent to them) but not on
  it (> 0.1 mm).
- tjunctions: vertices lying on (< 0.1 mm) a face or edge they do not belong to.
- nonplanar_faces: faces whose corners are > 1 mm off their best-fit plane.
- triangles: every triangle with its centre.
- inverted_winding_edges: manifold edges walked the same way by both faces (one face inside-out).
Writes OUT.json with counts and the first 200 locations of each class.
"""
import json
import math
import sys

RIM_PERP_TOL = 0.3  # max |cos| between a rim face normal and the local hole-plane normal (reveal face: ~0)


def classify_boundary_loop(edges, face_normals):
    """'rim' when the boundary loop is the open back of a reveal tube, else 'open'.

    edges: [((x, y, z), (x, y, z)), ...] = one boundary component; face_normals: the normal of each edge's only face.
    """
    if len(edges) < 4 or len(face_normals) != len(edges):
        return "open"
    key = lambda p: tuple(round(c, 6) for c in p)  # noqa: E731
    nxt = {}
    for a, b in edges:
        nxt.setdefault(key(a), []).append(key(b))
        nxt.setdefault(key(b), []).append(key(a))
    if any(len(q) != 2 for q in nxt.values()):
        return "open"  # not a simple closed loop
    start = key(edges[0][0])
    order, prev, cur = [start], None, start
    while True:
        a, b = nxt[cur]
        step = b if a == prev else a
        if step == start:
            break
        order.append(step)
        prev, cur = cur, step
        if len(order) > len(edges):
            return "open"
    if len(order) != len(edges):
        return "open"  # more than one cycle in the component
    c0 = [sum(p[k] for p in order) / len(order) for k in range(3)]
    for (a, b), fn in zip(edges, face_normals):
        # local hole plane at this edge: spanned by the edge and the in-plane direction towards the loop centre
        d = _unit([b[k] - a[k] for k in range(3)])
        if d is None:
            return "open"
        w = [c0[k] - (a[k] + b[k]) / 2 for k in range(3)]
        t = sum(w[k] * d[k] for k in range(3))
        w = [w[k] - t * d[k] for k in range(3)]
        n_loc = _unit([d[1] * w[2] - d[2] * w[1], d[2] * w[0] - d[0] * w[2], d[0] * w[1] - d[1] * w[0]])
        f = _unit(fn)
        if n_loc is None or f is None:
            return "open"
        if abs(sum(f[k] * n_loc[k] for k in range(3))) > RIM_PERP_TOL:
            return "open"  # the face lies in the hole surface: a missing wall / reveal face, not a reveal back
    return "rim"


def _unit(v):
    ln = math.sqrt(sum(c * c for c in v))
    return None if ln < 1e-9 else [c / ln for c in v]


def _run():
    import bmesh
    import bpy
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    args = sys.argv[sys.argv.index("--") + 1:]
    fbx, out = args[0], args[1]
    z0 = z1 = None
    if "--band-z" in args:
        k = args.index("--band-z")
        z0, z1 = float(args[k + 1]), float(args[k + 2])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=fbx)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    bm = bmesh.new()
    for o in meshes:
        tmp = o.data.copy()
        tmp.transform(o.matrix_world)
        bm.from_mesh(tmp)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    dropped = None
    if "--drop-face-at" in args:  # mutation probe
        k = args.index("--drop-face-at")
        pt = Vector([float(a) for a in args[k + 1:k + 4]])
        f = min(bm.faces, key=lambda g: (g.calc_center_median() - pt).length)
        dropped = {"at": [round(c, 3) for c in f.calc_center_median()], "verts": len(f.verts),
                   "height": round(max(v.co.z for v in f.verts) - min(v.co.z for v in f.verts), 3)}
        bmesh.ops.delete(bm, geom=[f], context="FACES_ONLY")
        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    R = lambda v: [round(c, 3) for c in v]  # noqa: E731
    rep = {"model": fbx, "verts": len(bm.verts), "faces": len(bm.faces), "objects": len(meshes),
           "dropped_face": dropped}

    # boundary edges and their loops
    bnd = [e for e in bm.edges if len(e.link_faces) == 1]
    nonman = [e for e in bm.edges if len(e.link_faces) > 2]
    band_cut, rim, open_e = [], [], []
    seen = set()
    for e in bnd:
        if e.index in seen:
            continue
        loop, stack = [], [e]
        while stack:  # boundary component
            x = stack.pop()
            if x.index in seen:
                continue
            seen.add(x.index)
            loop.append(x)
            for v in x.verts:
                for y in v.link_edges:
                    if len(y.link_faces) == 1 and y.index not in seen:
                        stack.append(y)
        zs = [v.co.z for x in loop for v in x.verts]
        if z0 is not None and (max(abs(z - z0) for z in zs) < 1e-3 or max(abs(z - z1) for z in zs) < 1e-3):
            band_cut += loop
            continue
        kind = classify_boundary_loop([(tuple(x.verts[0].co), tuple(x.verts[1].co)) for x in loop],
                                      [tuple(x.link_faces[0].normal) for x in loop])
        if kind == "rim":
            rim += loop
            rep["opening_rim_loops"] = rep.get("opening_rim_loops", 0) + 1
        else:
            open_e += loop
    rep["boundary_edges"] = len(bnd)
    rep["band_cut_edges"] = len(band_cut)
    rep["opening_rim_edges"] = len(rim)
    rep["open_boundary_edges"] = len(open_e)
    rep["open_boundary_at"] = [R((x.verts[0].co + x.verts[1].co) / 2) for x in open_e[:200]]
    rep["nonmanifold_edges"] = len(nonman)
    rep["nonmanifold_at"] = [R((x.verts[0].co + x.verts[1].co) / 2) for x in nonman[:200]]

    # planarity, triangles
    nonplanar, tris = [], []
    for f in bm.faces:
        if len(f.verts) == 3:
            tris.append(R(f.calc_center_median()))
        if len(f.verts) > 3:
            c = f.calc_center_median()
            n = f.normal
            dev = max(abs((v.co - c).dot(n)) for v in f.verts)
            if dev > 1e-3:
                nonplanar.append([R(c), round(dev * 1000, 2)])
    rep["nonplanar_faces"] = len(nonplanar)
    rep["nonplanar_at_mm"] = nonplanar[:200]
    rep["triangles"] = len(tris)
    rep["triangles_at"] = tris[:200]

    # winding: a manifold edge must be walked in opposite directions by its two faces (else one face is inside-out)
    flipped = []
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        a, b = e.verts
        fwd = []
        for f in e.link_faces:
            vs = list(f.verts)
            fwd.append(vs[(vs.index(a) + 1) % len(vs)] is b)
        if fwd[0] == fwd[1]:
            flipped.append(R((a.co + b.co) / 2))
    rep["inverted_winding_edges"] = len(flipped)
    rep["inverted_winding_at"] = flipped[:200]

    # gaps and T-junctions: nearest non-incident face per vertex
    verts = [v.co.copy() for v in bm.verts]
    polys = [[v.index for v in f.verts] for f in bm.faces]
    bvh = BVHTree.FromPolygons(verts, polys, epsilon=0.0)
    gaps, tj = [], []
    for v in bm.verts:
        near = {f.index for f in v.link_faces}
        for f in v.link_faces:  # topological neighbourhood: faces sharing a vertex with v's faces (one part)
            for w in f.verts:
                near |= {g.index for g in w.link_faces}
        own = {f.index for f in v.link_faces}
        hits = bvh.find_nearest_range(v.co, 0.05)
        best = None
        for co, nrm, idx, dist in hits:
            if idx in own or (dist > 1e-4 and idx in near):
                continue
            if best is None or dist < best[0]:
                best = (dist, idx)
        if best is None:
            continue
        if best[0] <= 1e-4:
            f = bm.faces[best[1]]
            tj.append([R(v.co), R(f.calc_center_median()), len(f.verts), R(f.normal)])
        else:
            gaps.append([R(v.co), round(best[0] * 1000, 1)])
    short = [[R((e.verts[0].co + e.verts[1].co) / 2), round(e.calc_length() * 1000, 1)]
             for e in bm.edges if e.calc_length() < 0.05]
    rep["short_edges_lt_5cm"] = len(short)
    rep["short_edges_at_mm"] = short[:200]
    rep["tjunctions"] = len(tj)
    rep["tjunctions_at"] = tj[:200]
    rep["gap_vertices"] = len(gaps)
    rep["gap_at_mm"] = gaps[:200]
    rep["passed_zero_gates"] = all(rep[k] == 0 for k in ("open_boundary_edges", "nonmanifold_edges", "nonplanar_faces",
                                                        "triangles", "tjunctions", "gap_vertices",
                                                        "inverted_winding_edges"))
    json.dump(rep, open(out, "w"), indent=1)
    print("GATES", json.dumps({k: v for k, v in rep.items() if not k.endswith("_at") and not k.endswith("_mm")}))


if __name__ == "__main__":
    _run()
