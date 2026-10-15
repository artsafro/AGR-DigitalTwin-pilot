"""Live-Blender (bmesh + mathutils.bvhtree) orientation and intersection checks on mesh dumps.

Runs inside Blender 4.4 through blender_exec.py; creates NO scene objects (standalone BMesh only).
Set FILES (list of dump JSON paths) and REPEATS before exec. Prints one compact JSON line per file.

M1 orientation (report §5 / task B):
  winding_bad_edges  - manifold edges whose two faces traverse them in the same direction
  outside_back_faces - polygons that a ray from OUTSIDE the model hits first on their back side
                       (rays from above and horizontal only: the bottom of a from_spec body is open)
M2 intersections (report §6 / task C):
  self_pairs  - triangle pairs of one mesh that BVH overlap() reports, minus identity pairs, pairs from
                the same source polygon and pairs sharing a vertex (edge/vertex contact)
  cross_pairs - triangle pairs between two different meshes of the dump
  split into transverse (non-parallel planes) and coplanar
"""
import json
import math
import time

import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def bm_of(mesh):
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in mesh["vertices"]]
    bm.verts.ensure_lookup_table()
    for i, p in enumerate(mesh["polygons"]):
        f = bm.faces.new([vs[k] for k in p])
        f.index = i
    bm.normal_update()
    return bm


def winding_bad(bm):
    bad = 0
    for e in bm.edges:
        ls = e.link_loops
        if len(ls) == 2 and ls[0].vert == ls[1].vert:
            bad += 1
    return bad


def tri_bvh(mesh):
    """Triangles of the source polygons (fan), with source polygon id per triangle."""
    verts = [Vector(v) for v in mesh["vertices"]]
    tris, src = [], []
    for i, p in enumerate(mesh["polygons"]):
        for k in range(1, len(p) - 1):
            tris.append((p[0], p[k], p[k + 1]))
            src.append(i)
    return verts, tris, src, BVHTree.FromPolygons(verts, tris, epsilon=0.0)


def tri_normal(verts, t):
    return (verts[t[1]] - verts[t[0]]).cross(verts[t[2]] - verts[t[0]]).normalized()


def outside_back(meshes_t, grid=48):
    """Per mesh: set of source polygons hit first on their back side by outside rays."""
    allv = [v for verts, *_ in meshes_t for v in verts]
    lo = Vector((min(v.x for v in allv), min(v.y for v in allv), min(v.z for v in allv)))
    hi = Vector((max(v.x for v in allv), max(v.y for v in allv), max(v.z for v in allv)))
    c, r = (lo + hi) / 2, (hi - lo).length / 2 + 1.0
    back = [set() for _ in meshes_t]
    dirs = []
    for el in (0, 30, 60, 89):          # ray elevation below the horizon (rays go down or level)
        for az in range(0, 360, 360 // 16 if el < 89 else 360):
            a, e = math.radians(az), math.radians(el)
            dirs.append(Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), -math.sin(e))))
    for d in dirs:
        u = d.orthogonal().normalized()
        w = d.cross(u).normalized()
        for i in range(grid):
            for j in range(grid):
                o = c - d * (2 * r) + u * ((i + 0.5) / grid * 2 - 1) * r + w * ((j + 0.5) / grid * 2 - 1) * r
                best = None
                for m, (verts, tris, src, tree) in enumerate(meshes_t):
                    loc, nrm, idx, dist = tree.ray_cast(o, d, 4 * r)
                    if idx is not None and (best is None or dist < best[0]):
                        best = (dist, m, idx)
                if best:
                    _, m, idx = best
                    verts, tris, src, _ = meshes_t[m]
                    if tri_normal(verts, tris[idx]).dot(d) > 1e-9:
                        back[m].add(src[idx])
    return back, len(dirs) * grid * grid


PIERCE_M = 1e-4  # a vertex closer than this to the other plane counts as on it (contact, not crossing)


EMBED_M = 0.05   # tolerances.json geometry.roof_inset_embed_m max: a crossing this shallow is an inset embed


def straddles(v, t, n, p0):
    d = [n.dot(v[k] - p0) for k in t]
    return max(d) > PIERCE_M and min(d) < -PIERCE_M


def shallow(v, t, n, p0):
    """Depth of the shallower side of triangle t across plane (n, p0)."""
    d = [n.dot(v[k] - p0) for k in t]
    return min(max(d), -min(d))


def classify(pairs, va, ta, sa, vb, tb, sb, same):
    """-> (transverse crossings, coplanar overlaps, contacts). A crossing needs each triangle to have
    vertices strictly on both sides of the other's plane; otherwise the BVH pair is a touch/T-contact."""
    global embed
    trans = cop = touch = 0
    for i, j in pairs:
        if same:
            if i >= j or sa[i] == sb[j] or set(ta[i]) & set(tb[j]):
                continue
        na, nb = tri_normal(va, ta[i]), tri_normal(vb, tb[j])
        if abs(na.dot(nb)) > 1 - 1e-6:
            cop += abs(na.dot(va[ta[i][0]] - vb[tb[j][0]])) < PIERCE_M
            touch += abs(na.dot(va[ta[i][0]] - vb[tb[j][0]])) >= PIERCE_M
        elif straddles(va, ta[i], nb, vb[tb[j][0]]) and straddles(vb, tb[j], na, va[ta[i][0]]):
            depth = min(shallow(va, ta[i], nb, vb[tb[j][0]]), shallow(vb, tb[j], na, va[ta[i][0]]))
            if depth <= EMBED_M:
                embed += 1
            else:
                trans += 1
        else:
            touch += 1
    return trans, cop, touch


def check(path):
    dump = json.load(open(path, encoding="utf-8"))
    meshes = [m for m in dump["meshes"] if not m["name"].startswith("UCX_")]
    t0 = time.perf_counter()
    wb = 0
    for m in meshes:
        bm = bm_of(m)
        wb += winding_bad(bm)
        bm.free()
    t1 = time.perf_counter()
    mt = [tri_bvh(m) for m in meshes]
    back, rays = outside_back(mt)
    t2 = time.perf_counter()
    global embed
    embed = 0
    st = sc = xt = xc = touch = 0
    for a, (va, ta, sa, tra) in enumerate(mt):
        t, c, h = classify(tra.overlap(tra), va, ta, sa, va, ta, sa, True)
        st, sc, touch = st + t, sc + c, touch + h
        for b in range(a + 1, len(mt)):
            vb, tb, sb, trb = mt[b]
            t, c, h = classify(tra.overlap(trb), va, ta, sa, vb, tb, sb, False)
            xt, xc, touch = xt + t, xc + c, touch + h
    t3 = time.perf_counter()
    return {"file": path.replace("\\", "/").rsplit("/", 1)[-1][:-5],
            "polys": sum(len(m["polygons"]) for m in meshes), "meshes": len(meshes),
            "winding_bad_edges": wb, "outside_back_faces": sum(len(b) for b in back), "rays": rays,
            "self_transverse": st, "self_coplanar": sc, "cross_transverse": xt, "cross_coplanar": xc, "contacts": touch, "shallow_embeds": embed,
            "t_winding_ms": round((t1 - t0) * 1e3, 1), "t_rays_ms": round((t2 - t1) * 1e3, 1),
            "t_overlap_ms": round((t3 - t2) * 1e3, 1)}


for path in FILES:  # noqa: F821  (set by the caller)
    runs = [check(path) for _ in range(REPEATS)]  # noqa: F821
    out = runs[0]
    for k in ("t_winding_ms", "t_rays_ms", "t_overlap_ms"):
        out[k] = sorted(r[k] for r in runs)[len(runs) // 2]
    out["stable"] = all({k: v for k, v in r.items() if not k.startswith("t_")} ==
                        {k: v for k, v in runs[0].items() if not k.startswith("t_")} for r in runs)
    print(json.dumps(out))
