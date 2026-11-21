"""Research prototype (#1742): body by construction - envelope ring x global levels lattice + depth field.

Pattern: n/a | new-case: construction-first body prototype (facade lattice, reason-filtered cut lines, depth field
cells, welded reveals) for the #1742 method comparison; research folder only, not a pipeline stage.

blender -b --factory-startup --python proto_lattice.py -- SRC.(fbx|blend) OUT_DIR --objects SUBSTR
        (--ring-bbox | --ring-json FLOOR.json) --zmin Z --zmax Z [--sides 0,1,2,3] [--reveal 0.25]
        [--plane-share 0.08] [--snap 0.02]

1. Ring: the outer envelope polygon (CCW). --ring-bbox = plan bbox of the source objects; --ring-json = rings[0].xy
   of a floor JSON (63A floor_v005.json). --sides keeps only those ring edges (KPP1: W/S/N walls).
2. Candidate cut lines: every source vertex within 3 m inside the ring is projected to the ring (perimeter s)
   and its z kept; s and z are clustered at --snap. Ring corners are always stations.
3. Depth field: one ray per lattice cell from 0.5 m outside along the inward normal. Hits are classified against
   the facade's wall planes (depths covering >= --plane-share of the side's cell area): on/in front of a plane ->
   that plane (protrusions = posts = inset elements, D336: the wall under them stays whole); more than 8 cm behind
   it -> opening of that plane at plane + --reveal (stage-1 reveal tube; mullions/frames never cut the body);
   no hit within 3.5 m -> void.
4. Reason filter (BM-02/03 by construction): a station or level is kept only where the cell class differs on
   its two sides somewhere along it; all others are dropped before any face exists.
5. Faces: one quad per non-void cell at its depth; one quad per depth step between neighbour cells, split at every
   depth present at either node (no T-junction); vertices keyed by rounded world position (welded across walls,
   corners and reveals). Writes OUT_DIR/proto.blend, proto.fbx, proto.json. OUT_DIR must be new.
"""
import bisect
import collections
import json
import math
import os
import sys


def cluster(vals, snap):
    vals = sorted(vals)
    out = []
    for v in vals:
        if out and v - out[-1][0] <= snap:  # cluster span <= snap (no chaining)
            out[-1].append(v)
        else:
            out.append([v])
    return [sum(c) / len(c) for c in out]


def main():
    import bmesh
    import bpy
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    a = sys.argv[sys.argv.index("--") + 1:]
    src, out = a[0], a[1]

    def arg(k, d=None, f=str):
        return f(a[a.index(k) + 1]) if k in a else d
    objs = arg("--objects", "").split(",")
    z0, z1 = arg("--zmin", None, float), arg("--zmax", None, float)
    reveal, share, snap = arg("--reveal", 0.25, float), arg("--plane-share", 0.08, float), arg("--snap", 0.02, float)
    if z0 is None or z1 is None or not (math.isfinite(z0) and math.isfinite(z1) and z1 > z0):
        sys.exit("need finite --zmin < --zmax")
    if os.path.exists(out):
        sys.exit("refused: OUT_DIR exists")
    if src.lower().endswith(".blend"):
        bpy.ops.wm.open_mainfile(filepath=src, load_ui=False)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=src)
    obs = [o for o in bpy.context.scene.objects if o.type == "MESH" and any(s and s in o.name for s in objs)
           and not o.name.startswith("UCX_") and "Glass" not in o.name]
    if not obs:
        sys.exit("no source object matches %r" % objs)
    bm = bmesh.new()
    for o in obs:
        t = bmesh.new()
        t.from_mesh(o.data)
        t.transform(o.matrix_world)
        me = bpy.data.meshes.new("t")
        t.to_mesh(me)
        t.free()
        bm.from_mesh(me)
    bvh = BVHTree.FromBMesh(bm)
    pts = [v.co.copy() for v in bm.verts]
    if "--ring-json" in a:
        ring = [tuple(p) for p in json.load(open(arg("--ring-json"), encoding="utf-8"))["rings"][0]["xy"]]
    else:
        xs, ys = [p.x for p in pts], [p.y for p in pts]
        ring = [(min(xs), min(ys)), (max(xs), min(ys)), (max(xs), max(ys)), (min(xs), max(ys))]
    area = sum(ring[i][0] * ring[(i + 1) % len(ring)][1] - ring[(i + 1) % len(ring)][0] * ring[i][1]
               for i in range(len(ring)))
    if area < 0:
        ring = ring[::-1]
    n = len(ring)
    sides = [int(s) for s in arg("--sides", ",".join(map(str, range(n)))).split(",")]
    seg = []  # (s0, L, a, t, nin)
    s = 0.0
    for i in range(n):
        p, q = Vector((*ring[i], 0)), Vector((*ring[(i + 1) % n], 0))
        L = (q - p).length
        t = (q - p) / L
        seg.append((s, L, p, t, Vector((-t.y, t.x, 0))))
        s += L
    perim = s

    def at(sv):  # ring point and inward normal at perimeter s (segment normal; corner = bisector)
        sv = sv % perim
        k = max(0, bisect.bisect_right([g[0] for g in seg], sv + 1e-9) - 1)
        s0, L, p, t, nin = seg[k]
        u = sv - s0
        if u < 1e-6:
            nin = (nin + seg[k - 1][4]).normalized()
            nin = nin / max(1e-6, nin.dot(seg[k][4]))  # mitre: keeps the offset depth on both walls
        return p + t * u, nin, k

    # 2. candidate lines
    cand_s = set(round(g[0], 4) for g in seg)
    cand_z = {z0, z1}
    for v in pts:
        if not (z0 - 1e-3 <= v.z <= z1 + 1e-3):
            continue
        best = None
        for s0, L, p, t, nin in seg:
            u = max(0.0, min(L, (v - p).dot(t)))
            d = (Vector((v.x, v.y, 0)) - (p + t * u)).dot(nin)
            if -0.05 <= d <= 3.0 and (best is None or d < best[0]):
                best = (d, s0 + u)
        if best:
            cand_s.add(best[1])
            cand_z.add(v.z)
    S = cluster(cand_s, snap)
    for g in seg:  # ring corners exactly
        S = [x for x in S if abs(x - g[0]) > snap] + [g[0]]
    S = sorted(set(round(x, 5) for x in S))
    Z = cluster([z for z in cand_z if z0 - 1e-3 <= z <= z1 + 1e-3], snap)
    Z[0], Z[-1] = z0, z1
    # 3. depth field on the candidate lattice
    raw = {}
    for i in range(len(S)):
        sa, sb = S[i], S[(i + 1) % len(S)] if i + 1 < len(S) else perim
        pc, nin, k = at((sa + sb) / 2)
        if k not in sides:
            continue
        for j in range(len(Z) - 1):
            zc = (Z[j] + Z[j + 1]) / 2
            o = Vector((pc.x, pc.y, zc)) - nin * 0.5
            hit = bvh.ray_cast(o, nin, 4.0)
            raw[(i, j)] = (None if hit[0] is None else round(hit[3] - 0.5, 2), (sb - sa) * (Z[j + 1] - Z[j]), k)
    planes = {}
    for k in sides:
        acc = collections.Counter()
        tot = 0.0
        for (i, j), (d, ar, kk) in raw.items():
            if kk == k and d is not None:
                acc[d] += ar
                tot += ar
        planes[k] = sorted(d for d, ar in acc.items() if tot and ar / tot >= share) or [min(acc) if acc else 0.0]
    cls = {}
    for key, (d, ar, k) in raw.items():
        if d is None:
            cls[key] = None
            continue
        pl = [p for p in planes[k] if p <= d + 0.02]
        base = pl[-1] if pl else planes[k][0]
        cls[key] = round(base + reveal, 3) if d - base > 0.08 else base
    # 4. reason filter (+ --min-reason: a line whose class change runs shorter than that is texture, BM-08/D344)
    mr = arg("--min-reason", 0.0, float)
    perim_s = S + [perim]

    def reason_s(i):
        return sum(Z[j + 1] - Z[j] for j in range(len(Z) - 1) if cls.get(((i - 1) % len(S), j)) != cls.get((i, j)))

    def reason_z(j):
        return sum(perim_s[i + 1] - perim_s[i] for i in range(len(S)) if cls.get((i, j - 1)) != cls.get((i, j)))
    keep_s = [i for i in range(len(S)) if any(abs(S[i] - g[0]) < 1e-6 for g in seg) or (
        reason_s(i) > 0 and reason_s(i) >= mr)]
    keep_z = [j for j in range(len(Z)) if j in (0, len(Z) - 1) or (reason_z(j) > 0 and reason_z(j) >= mr)]
    # rebuild cells on the kept lattice: class of a merged cell = class of its first candidate cell
    S2, Z2 = [S[i] for i in keep_s], [Z[j] for j in keep_z]
    c2 = {}
    for a_i, i in enumerate(keep_s):
        for b_j, j in enumerate(keep_z[:-1]):
            c2[(a_i, b_j)] = cls.get((i, j), "skip")
    # 5. faces
    out_bm = bmesh.new()
    V = {}

    def vert(si, zj, d):
        p, nin, k = at(S2[si % len(S2)] if si < len(S2) else perim)
        co = Vector((p.x, p.y, Z2[zj])) + nin * d
        key = (round(co.x, 3), round(co.y, 3), round(co.z, 3))
        if key not in V:
            V[key] = out_bm.verts.new(co)
        return V[key]
    nodes = collections.defaultdict(set)
    NS, NZ = len(S2), len(Z2)
    for (i, j), d in c2.items():
        if d in (None, "skip"):
            continue
        for di, dj in ((0, 0), (1, 0), (0, 1), (1, 1)):
            nodes[((i + di) % NS, j + dj)].add(d)
    sides_q = []
    for (i, j), d in c2.items():  # depth steps to the right and up
        if d in (None, "skip"):
            continue
        r = c2.get(((i + 1) % NS, j))
        if r not in (None, "skip") and r != d:
            sides_q.append((((i + 1) % NS, j), ((i + 1) % NS, j + 1), d, r))
            for nd in (((i + 1) % NS, j), ((i + 1) % NS, j + 1)):
                nodes[nd] |= {d, r}
        u = c2.get((i, j + 1))
        if u not in (None, "skip") and u != d:
            sides_q.append((((i + 1) % NS, j + 1), (i, j + 1), d, u))
            for nd in (((i + 1) % NS, j + 1), (i, j + 1)):
                nodes[nd] |= {d, u}
    faces = 0

    def face(vs, want):
        nonlocal faces
        if len({id(v) for v in vs}) < len(vs):
            return
        try:
            f = out_bm.faces.new(vs)
        except ValueError:
            return
        f.normal_update()
        if f.normal.dot(want) < 0:
            f.normal_flip()
        faces += 1
    for (i, j), d in c2.items():
        if d in (None, "skip"):
            continue
        p, nin, k = at((S2[i] + (S2[i + 1] if i + 1 < NS else perim)) / 2)
        face([vert(i, j, d), vert(i + 1 if i + 1 < NS else 0, j, d), vert(i + 1 if i + 1 < NS else 0, j + 1, d),
              vert(i, j + 1, d)], -nin)
    for pa, pb, d1, d2 in sides_q:
        lo, hi = min(d1, d2), max(d1, d2)
        ds = sorted({lo, hi} | {x for x in nodes[pa] | nodes[pb] if lo < x < hi})
        p, nin, k = at(S2[pa[0]])
        want = Vector((0, 0, 1)) if pa[1] == pb[1] else None
        for x0, x1 in zip(ds, ds[1:]):
            vs = [vert(pa[0], pa[1], x0), vert(pb[0], pb[1], x0), vert(pb[0], pb[1], x1), vert(pa[0], pa[1], x1)]
            if want is None:  # vertical step face: normal along the ring tangent toward the shallower cell
                t = seg[k][3]
                want_v = t if (d1 > d2) else -t
            else:
                want_v = want if (d1 > d2) else -want
            face(vs, want_v)
    os.makedirs(out)
    me = bpy.data.meshes.new("SM_Proto_Body")
    out_bm.to_mesh(me)
    ob = bpy.data.objects.new("SM_Proto_Body", me)
    bpy.context.scene.collection.objects.link(ob)
    names = [o.name for o in obs]
    for o in list(bpy.context.scene.objects):
        if o is not ob:
            bpy.data.objects.remove(o)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "proto.blend"), copy=True)
    bpy.ops.export_scene.fbx(filepath=os.path.join(out, "proto.fbx"), use_selection=False, mesh_smooth_type="FACE")
    rep = {"source": os.path.abspath(src), "objects": names, "ring_points": n, "sides": sides,
           "planes": {str(k): v for k, v in planes.items()}, "candidate_stations": len(S), "candidate_levels": len(Z),
           "kept_stations": len(S2), "kept_levels": len(Z2), "levels_z": [round(z, 3) for z in Z2],
           "faces": faces, "verts": len(V), "reveal_m": reveal}
    json.dump(rep, open(os.path.join(out, "proto.json"), "x"), indent=1)
    print("PROTO", json.dumps({k: rep[k] for k in ("candidate_stations", "candidate_levels", "kept_stations",
                                                    "kept_levels", "faces", "verts", "planes")}))


if __name__ == "__main__":
    main()
