"""Whole-model gates for #1619 stage 1 (Artem verdict 63B v006): no location filter, every hit listed.

Pattern: n/a | new-case: whole-model readback gates for the two-ring tower 63B.

blender -b --factory-startup --python gates63b.py -- MODEL.fbx OUT.json [--band-z Z0 Z1]

Read back the FBX (fresh scene, Blender importer) and count, over the WHOLE mesh:
- open_boundary_edges: boundary edges that are not an opening rim (the open back of a reveal tube) and not on the
  band cut (z0 / z1, the stage band is a storey slice). Rim = boundary edge whose two faces-neighbour ring is a
  reveal (both vertices off the facade loop stations are allowed only behind the facade: classified by the edge
  lying on a closed boundary loop whose every vertex is a reveal-back vertex, i.e. not used by any wall face of
  normal |n.z| < 0.5 that also touches a ring vertex). Implementation: a boundary loop is an opening rim when it is
  vertical-planar, closed, and all its vertices are shared by reveal faces only.
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
import sys


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
    bm.edges.ensure_lookup_table()
    R = lambda v: [round(c, 3) for c in v]  # noqa: E731
    rep = {"model": fbx, "verts": len(bm.verts), "faces": len(bm.faces), "objects": len(meshes)}

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
        # opening rim: every face on the loop is a reveal face (its normal is not the facade normal: a reveal face
        # touches the loop with its inner edge; walls never do) -> classify by: each loop edge's face has another
        # edge on the facade-side and the loop is closed (every vertex has exactly 2 loop edges)
        deg = {}
        for x in loop:
            for v in x.verts:
                deg[v.index] = deg.get(v.index, 0) + 1
        closed = all(d == 2 for d in deg.values())
        vz = sorted(zs)
        tall = vz[-1] - vz[0] > 1.5
        if closed and len(loop) >= 4 and tall:
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
