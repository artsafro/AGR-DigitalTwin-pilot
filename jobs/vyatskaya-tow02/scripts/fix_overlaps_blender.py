"""TOW02 overlap fixes for xView Overlapping Faces (5 mm) / Overlapping Vertices (2 mm) on the mid-poly master (runs
inside Blender, headless).

Engine gap: EG6 (panelised curtain-wall source: parts built from measurements, docs/backlog.md).

    blender -b outputs/build-v019/tow02_master.blend --python scripts/fix_overlaps_blender.py -- <out_dir>

Saves ONLY <out_dir>/tow02_master.blend (save_as, never over the input) and <out_dir>/fix_overlaps_info.json.
Diagnosis: outputs/xview-v002/findings.json, qa/groups.json (group ids F1-F15, V1-V5 below).

User rules 2026-10-21: no geometry is deleted and nothing is cut; parts that butt into each other are embedded one into
the other by a few mm; parallel faces closer than 5 mm are MOVED apart to >= CLEAR_M (6.5 mm; the checks below test
6 mm); vertices are merged only where two points must be one (F7). Every move is <= 1 cm unless reported.

Fixes (one function each, applied in this order; parts built by build_review_fixes_blender.py - AC coping/posts/glass
F3 F4 F5 V4 and louvre F1 F2 - are fixed there by parameters):
- fix_orientation_reveals (orientation): TOW02_body faces with material TOW02_reveal (6 418, sill / head / jamb quads
  of build_body_blender.build_stack wound into the wall) and the 16 step slivers listed in BODY_SLIVERS
  (outputs/xview-v002/orient/orient_faces.npz) are reversed explicitly. Not recalc_face_normals (it turns whole
  islands inward).
- fix_F7_bowtie_reveals (F7): a horizontal reveal quad whose front and back edges cross (convex corner with a short
  edge: the mitred back points of the two columns pass each other) gets its two back points merged at the
  intersection of the neighbouring back lines (user: merge the crossed inner points); the quad becomes a triangle.
- fix_F9_nonconvex_caps (F9): a non-convex horizontal TOW02_top quad gets the shared edge with a neighbour quad
  rotated (re-pairing the hexagon) when both new quads are convex.
- fix_F14_fin_vs_jamb (F14): a fin whose side lies within 6 mm of a window jamb plane is translated (whole fin) away
  into the wall solid (-jamb normal) by the minimum that clears it.
- fix_F10_soffit_step_into_fins (F10): soffit step-wall faces (6.9-7.3) parallel to a colonnade fin side within 6 mm
  get their vertices moved into the fin to CLEAR_M behind the fin face.
- fix_F12_V5_railing_inward (F12, V5): every TOW02_railing_glass strip is offset (mitred) toward the side away from
  TOW02_coping by the minimum that puts it >= 6 mm off the coping faces; its bottom is lowered RAIL_DROP_M (5 mm) into
  the cap below, away from the coping bottom.
- fix_F6_basket_assemblies (F6): an AC unit whose floor lies on a window sill (horizontal reveal face within 6 mm and
  overlapping in plan) is moved down whole (basket, floor, glass shell, coping, posts) so the floor sits CLEAR_M below
  the sill (embedded in the wall); shift per unit reported.
- fix_F13_stubs_vs_jambs (F13 + the coping stub of the same kind): the wall-end points of an AC glass / coping stub
  lying in a window jamb plane are moved into the wall solid (-jamb normal) by the minimum that clears 6 mm.
- fix_F11_F15_louvre (F11, F15): louvre blades / rails are boxes in the louvre frame (s, d, z); an s-face within 6 mm
  of a parallel face of a fin, the roof coping or the walls is moved into its element (the element narrows, nothing
  else moves); then every blade end keeps its rail sides >= CLEAR_M proud (F1) by narrowing the blade.
Not fixed here: F8 (zero-width step strips at ring joins; user decision pending, analysed separately) and the seams
V1-V3 (welded in join_export_blender.py).
"""
import json
import math
import os
import sys
import time
from collections import defaultdict

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

CLEAR_M = 0.0065          # target distance between parallel faces (>= 6 mm)
TEST_M = 0.006            # a pair closer than this still counts as overlapping in the local tests
PAR_DEG = 5.0             # parallel within (xView / QA)
AREA_MIN = 1e-6
RAIL_DROP_M = 0.005
STEP_M = 0.0005
LOCAL_ANGLE_DEG = 56.7
# outputs/xview-v002/orient/orient_faces.npz: TOW02_body step slivers (finish 3 / 8) wound the wrong way
BODY_SLIVERS = [14253, 14335, 14336, 14359, 14360, 14417, 14531, 14576, 14593, 14640, 14641, 14732, 14736, 14810,
                14827, 14918]
C0 = np.array([376.870, 185.218])            # louvre frame (build_review_fixes_blender.py)
SD = np.array([-0.0924, 0.9957])
DD = np.array([-0.9957, -0.0924])


# ------------------------------------------------------------------------------------------------ helpers
def obj(name):
    return bpy.data.objects[name]


def to_local2(p):
    a = math.radians(LOCAL_ANGLE_DEG)
    return np.array([p[0] * math.cos(a) + p[1] * math.sin(a), -p[0] * math.sin(a) + p[1] * math.cos(a)])


def world_dir(v2):
    a = math.radians(LOCAL_ANGLE_DEG)
    return np.array([v2[0] * math.cos(a) - v2[1] * math.sin(a), v2[0] * math.sin(a) + v2[1] * math.cos(a), 0.0])


S_W, D_W = world_dir(SD), world_dir(DD)


def polys(ob, idx=None):
    """[(key, pts (k,3) world)] of an object's faces."""
    me, mw = ob.data, ob.matrix_world
    out = []
    for i in (range(len(me.polygons)) if idx is None else sorted(idx)):
        p = me.polygons[i]
        out.append(((ob.name, i), np.array([tuple(mw @ me.vertices[v].co) for v in p.vertices])))
    return out


def newell(P):
    n = np.zeros(3)
    for i in range(len(P)):
        n += np.cross(P[i], P[(i + 1) % len(P)])
    a = np.linalg.norm(n)
    return (n / a if a > 0 else n), a / 2


def _clip(subject, clipper):
    def inside(p, a, b):
        return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= -1e-12

    def inter(p, q, a, b):
        x1, y1, x2, y2 = p[0], p[1], q[0], q[1]
        x3, y3, x4, y4 = a[0], a[1], b[0], b[1]
        den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(den) < 1e-18:
            return q
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
        return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
    out = subject
    for k in range(len(clipper)):
        a, b = clipper[k], clipper[(k + 1) % len(clipper)]
        inp, out = out, []
        if not inp:
            break
        s = inp[-1]
        for e in inp:
            if inside(e, a, b):
                if not inside(s, a, b):
                    out.append(inter(s, e, a, b))
                out.append(e)
            elif inside(s, a, b):
                out.append(inter(s, e, a, b))
            s = e
    return out


def _parea(poly):
    s = cx = cy = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        cr = x1 * y2 - x2 * y1
        s += cr
        cx += (x1 + x2) * cr
        cy += (y1 + y2) * cr
    if abs(s) < 1e-15:
        return 0.0, (0.0, 0.0)
    return s / 2, (cx / (3 * s), cy / (3 * s))


def overlap(Pf, Pg):
    """QA overlap (outputs/xview-v002/scripts/qa_checks.py): area of g projected on f's plane, plane gap at its
    centroid, parallel flag. None when not parallel / no overlap."""
    nf, af = newell(Pf)
    ng, ag = newell(Pg)
    if af == 0 or ag == 0 or abs(nf @ ng) < math.cos(math.radians(PAR_DEG)):
        return None
    o = Pf.mean(0)
    a = np.array((1.0, 0, 0)) if abs(nf[0]) < 0.9 else np.array((0, 1.0, 0))
    u = np.cross(nf, a)
    u /= np.linalg.norm(u)
    w = np.cross(nf, u)
    tl = lambda P: [[((P[i] - o) @ u, (P[i] - o) @ w) for i in t] for t in
                    ([(0, 1, 2)] if len(P) == 3 else [(0, j, j + 1) for j in range(1, len(P) - 1)])]
    ccw = lambda t: t if _parea(t)[0] >= 0 else t[::-1]
    tot, cxy = 0.0, np.zeros(2)
    for t1 in tl(Pf):
        for t2 in tl(Pg):
            pl = _clip(ccw(t1), ccw(t2))
            if len(pl) >= 3:
                ar, c = _parea(pl)
                if ar > 0:
                    tot += ar
                    cxy += ar * np.array(c)
    if tot <= AREA_MIN:
        return None
    c = o + u * (cxy[0] / tot) + w * (cxy[1] / tot)
    return tot, abs(float((c - Pg.mean(0)) @ ng)), c


def _samples(P):
    c = P.mean(0)
    return [c] + [c + (p - c) * t for p in P for t in (0.5, 0.95)]


def _bvh(F):
    verts, faces = [], []
    for _, P in F:
        faces.append(tuple(range(len(verts), len(verts) + len(P))))
        verts += [Vector(p) for p in P]
    return BVHTree.FromPolygons(verts, faces, epsilon=0.0)


class Near:
    """Faces B in a BVH; pairs(A) = [(a_key, b_key, gap, area, overlap centroid)] parallel, closer than tol and
    overlapping. Candidates
    are searched both ways (samples of A near B and samples of B near A), as the QA does over all faces."""

    def __init__(self, B):
        self.B = B
        self.bvh = _bvh(B)
        self.lo = np.array([P.min(0) for _, P in B]) if B else np.zeros((0, 3))
        self.hi = np.array([P.max(0) for _, P in B]) if B else np.zeros((0, 3))

    def pairs(self, A, tol=TEST_M):
        if not A or not self.B:
            return []
        cand = set()
        for ia, (ka, P) in enumerate(A):
            for p in _samples(P):
                for loc, nn, idx, dist in self.bvh.find_nearest_range(Vector(p), tol):
                    cand.add((ia, idx))
        lo = np.min([P.min(0) for _, P in A], axis=0) - tol
        hi = np.max([P.max(0) for _, P in A], axis=0) + tol
        near_b = np.where(np.all(self.hi >= lo, axis=1) & np.all(self.lo <= hi, axis=1))[0]
        if len(near_b):
            abvh = _bvh(A)
            for ib in near_b:
                for p in _samples(self.B[ib][1]):
                    for loc, nn, idx, dist in abvh.find_nearest_range(Vector(p), tol):
                        cand.add((idx, int(ib)))
        out = []
        for ia, ib in cand:
            ka, P = A[ia]
            kb, Q = self.B[ib]
            if kb == ka:
                continue
            r = overlap(P, Q)
            if r and r[1] <= tol:
                out.append((ka, kb, r[1], r[0], r[2]))
        return out


def islands(me):
    parent = list(range(len(me.vertices)))

    def f(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for p in me.polygons:
        vs = list(p.vertices)
        for v in vs[1:]:
            a, b = f(vs[0]), f(v)
            if a != b:
                parent[a] = b
    groups = defaultdict(lambda: dict(verts=set(), faces=[]))
    for p in me.polygons:
        g = groups[f(p.vertices[0])]
        g["faces"].append(p.index)
        g["verts"].update(p.vertices)
    return list(groups.values())


def mat_index(ob, name):
    for i, m in enumerate(ob.data.materials):
        if m is not None and m.name == name:
            return i
    return None


def reveal_faces(names=("TOW02_body", "TOW02_top"), vertical=None):
    out = []
    for n in names:
        ob = obj(n)
        mi = mat_index(ob, "TOW02_reveal")
        idx = {p.index for p in ob.data.polygons if p.material_index == mi and
               (vertical is None or (abs(p.normal.z) < 0.1) == vertical)}
        out += polys(ob, idx)
    return out


def move_verts(ob, vids, vec):
    me = ob.data
    mwi = ob.matrix_world.inverted().to_3x3()
    dv = mwi @ Vector(vec)
    for i in vids:
        me.vertices[i].co += dv


# ------------------------------------------------------------------------------------------------ orientation
def fix_orientation_reveals(info):
    ob = obj("TOW02_body")
    mi = mat_index(ob, "TOW02_reveal")
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.faces.ensure_lookup_table()
    rev = [f for f in bm.faces if f.material_index == mi]
    sl = [bm.faces[i] for i in BODY_SLIVERS]
    if any(f.calc_area() > 2e-4 or f.material_index == mi for f in sl):
        raise RuntimeError("BODY_SLIVERS do not match the step slivers of this TOW02_body")
    bmesh.ops.reverse_faces(bm, faces=rev + sl)
    bad = sum(1 for e in bm.edges if len(e.link_faces) == 2 and
              next(l for l in e.link_faces[0].loops if l.edge == e).vert ==
              next(l for l in e.link_faces[1].loops if l.edge == e).vert)
    bm.to_mesh(ob.data)
    bm.free()
    info["orientation"] = dict(reveal_faces_flipped=len(rev), slivers_flipped=len(sl),
                               body_inconsistent_edges_after=bad)


# ------------------------------------------------------------------------------------------------ F7
def _seg_x(a, b, c, d):
    """Proper intersection of 2D segments ab and cd."""
    def cr(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    return cr(a, b, c) * cr(a, b, d) < 0 and cr(c, d, a) * cr(c, d, b) < 0


def _line_x(p, d, q, e):
    den = d[0] * e[1] - d[1] * e[0]
    if abs(den) < 1e-9:
        return None
    t = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / den
    return p + d * t


def fix_F7_bowtie_reveals(info):
    """A horizontal reveal quad has 2 front points (on facade faces or the 64.7 seam) and 2 back points. Where the back edge runs
    opposite to the front edge (bow-tie, or a fold over the next column at a convex corner), the two back points
    are merged at the intersection of the neighbouring back lines; repeated until no reversed quad is left (a fold
    can span two columns)."""
    ob = obj("TOW02_body")
    mi = mat_index(ob, "TOW02_reveal")
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    top = obj("TOW02_top")
    kd = KDTree(len(top.data.vertices))
    for i, v in enumerate(top.data.vertices):
        kd.insert(top.matrix_world @ v.co, i)
    kd.balance()
    mwb = ob.matrix_world
    # front point = on a facade face of the body, or on the top band seam at 64.7 (the facade above is TOW02_top)
    facade = lambda v: any(f.material_index != mi for f in v.link_faces) or kd.find(mwb @ v.co)[2] < 1e-5
    merged, passes = 0, 0
    for passes in range(1, 8):
        todo = []
        for f in bm.faces:
            if f.material_index != mi or len(f.verts) != 4 or abs(f.normal.z) < 0.99:
                continue
            V = list(f.verts)
            fr = [facade(v) for v in V]
            if sum(fr) != 2:
                continue
            k = next((i for i in range(4) if fr[i] and fr[(i + 1) % 4]), None)
            if k is None:
                continue
            fa, fb, bb, ba = V[k], V[(k + 1) % 4], V[(k + 2) % 4], V[(k + 3) % 4]
            if (bb.co - ba.co).xy.dot((fb.co - fa.co).xy) < 0:
                todo.append((f, ba, bb))
        if not todo:
            break
        done = set()
        for f, a, b in todo:
            if not f.is_valid or not a.is_valid or not b.is_valid or a in done or b in done:
                continue
            lines = []
            for v in (a, b):
                nb = None
                for e in v.link_edges:
                    w = e.other_vert(v)
                    if w not in (a, b) and not facade(w) and abs(w.co.z - v.co.z) < 1e-6 and \
                            not any(g is f for g in e.link_faces):
                        nb = w
                        break
                lines.append(None if nb is None else (np.array(v.co.xy), np.array((v.co - nb.co).xy)))
            X = _line_x(lines[0][0], lines[0][1], lines[1][0], lines[1][1]) if all(lines) else None
            mid = np.array(((a.co + b.co) / 2).xy)
            if X is None or np.linalg.norm(X - mid) > 0.2:
                X = mid
            bmesh.ops.pointmerge(bm, verts=[a, b], merge_co=Vector((X[0], X[1], a.co.z)))
            done.update((a, b))
            merged += 1
    sizes = defaultdict(int)
    for g in bm.faces:
        sizes[len(g.verts)] += 1
    bm.to_mesh(ob.data)
    bm.free()
    info["F7"] = dict(merged_pairs=merged, passes=passes, body_face_sizes=dict(sizes))


# ------------------------------------------------------------------------------------------------ F9
def _convex_pts(P, n):
    s = [((P[(i + 1) % 4] - P[i]).cross(P[(i + 2) % 4] - P[(i + 1) % 4])).dot(n) for i in range(4)]
    return all(x > 1e-9 for x in s) or all(x < -1e-9 for x in s)


def _convex(f):
    return _convex_pts([v.co for v in f.verts], f.normal)


def _strip_width(f):
    """Largest distance of a face's points from the line of its longest edge."""
    e = max(f.edges, key=lambda x: x.calc_length())
    a, b = e.verts[0].co, e.verts[1].co
    d = (b - a).normalized()
    return max(((v.co - a) - d * (v.co - a).dot(d)).length for v in f.verts)


def fix_F9_nonconvex_caps(info, names=("TOW02_top", "TOW02_body")):
    """A non-convex quad is triangulated by viewers / FBX importers along the diagonal from its first vertex; when
    that diagonal misses the reflex vertex the two triangles fold over the neighbour. The face is rebuilt with the
    reflex vertex first (same points, same winding, same attributes): its diagonal now runs through the reflex
    vertex (user: flip the diagonal)."""
    rep = {}
    for name in names:
        ob = obj(name)
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bad = [f for f in bm.faces if len(f.verts) == 4 and f.calc_area() > 1e-9 and not _convex(f)
               and _strip_width(f) >= 0.006]                   # zero-width step strips (F8) are left as they are
        n = 0
        for f in bad:
            V, nrm = list(f.verts), f.normal.copy()
            P = [v.co for v in V]
            s_ = [((P[i] - P[i - 1]).cross(P[(i + 1) % 4] - P[i])).dot(nrm) for i in range(4)]
            r = min(range(4), key=lambda i: s_[i])                            # the reflex corner
            if r == 0:
                continue
            keep = (f.material_index, f.smooth, {L: f[L] for L in bm.faces.layers.int.values()})
            bm.faces.remove(f)
            g = bm.faces.new(V[r:] + V[:r])
            g.material_index, g.smooth = keep[0], keep[1]
            for L, val in keep[2].items():
                g[L] = val
            g.normal_update()
            n += 1
        bm.to_mesh(ob.data)
        bm.free()
        rep[name] = dict(nonconvex=len(bad), reordered=n)
    info["F9"] = rep


# ------------------------------------------------------------------------------------------------ F14
def fix_F14_fin_vs_jamb(info):
    jam = reveal_faces(vertical=True)
    near = Near(jam)
    nrm = {k: newell(P)[0] for k, P in jam}
    rep = []
    for ob in [o for o in bpy.data.objects if o.name.startswith("TOW02_fin_")]:
        hits = near.pairs(polys(ob))
        if not hits:
            continue
        n = nrm[hits[0][1]]
        d = -np.array([n[0], n[1], 0.0])
        d /= np.linalg.norm(d)
        s = 0.0
        while hits and s < 0.02:
            s += STEP_M
            move_verts(ob, range(len(ob.data.vertices)), d * STEP_M)
            hits = near.pairs(polys(ob))
        rep.append(dict(fin=ob.name, shift_mm=round(s * 1000, 1), dir=[round(x, 3) for x in d], left=len(hits)))
    info["F14"] = rep


# ------------------------------------------------------------------------------------------------ F10
def fix_F10_soffit_step_into_fins(info):
    """Soffit step-wall faces parallel to a fin side within 6 mm are pushed (all their points by one vector along
    the fin normal, measured at the overlap centroid) into the fin to CLEAR_M behind its face; repeated for
    neighbours that become parallel."""
    so = obj("TOW02_soffit")
    fins = [o for o in bpy.data.objects if o.name.startswith("TOW02_fin_")]
    F = sum((polys(o) for o in fins), [])
    near = Near(F)
    fp = dict(F)
    me, mw = so.data, so.matrix_world
    moved, total, it = defaultdict(lambda: np.zeros(3)), 0, 0
    for it in range(6):
        hits = near.pairs(polys(so))
        if not hits:
            break
        total += len(hits)
        for (on, fi), kb, gap, area, c in hits:
            Q = fp[kb]
            n, _ = newell(Q)
            q0 = Q.mean(0)
            m = float((c - q0) @ n) + CLEAR_M                  # overlap centroid in front of the fin face + clearance
            if m <= 0:
                m = STEP_M
            for v in me.polygons[fi].vertices:
                move_verts(so, [v], -n * m)
                moved[v] += -n * m
    left = near.pairs(polys(so))
    info["F10"] = dict(pairs_seen=total, iterations=it + 1, verts_moved=len(moved),
                       max_move_mm=round(max((np.linalg.norm(v) for v in moved.values()), default=0) * 1000, 1),
                       left=len(left))


# ------------------------------------------------------------------------------------------------ F12 / V5
def _inside(bvh, p, d):
    """Ray parity: p inside the closed mesh of bvh."""
    n, o = 0, Vector(p)
    dv = Vector(d).normalized()
    while n < 50:
        loc, nn, idx, dist = bvh.ray_cast(o, dv)
        if loc is None:
            break
        n += 1
        o = loc + dv * 1e-5
    return n % 2 == 1


def _chain(me, verts, zb):
    """Bottom vertices of a vertical strip in order (open or closed) and their top partners."""
    bot = [v for v in verts if abs(me.vertices[v].co.z - zb) < 1e-4]
    bs = set(bot)
    adj = defaultdict(list)
    for e in me.edges:
        a, b = e.vertices
        if a in bs and b in bs:
            adj[a].append(b)
            adj[b].append(a)
    ends = [v for v in bot if len(adj[v]) == 1]
    start = ends[0] if ends else bot[0]
    order, prev = [start], None
    while True:
        nx = [w for w in adj[order[-1]] if w != prev and w not in order]
        if not nx:
            break
        prev = order[-1]
        order.append(nx[0])
    top = {}
    for v in order:
        c = me.vertices[v].co
        top[v] = min((w for w in verts if w not in bs), key=lambda w: (me.vertices[w].co.xy - c.xy).length)
    return order, top, not ends


def fix_F12_V5_railing_inward(info):
    """Every railing glass segment moves on its own normal away from the coping (side chosen by majority vote of the
    strip) by the minimum t that clears 6 mm from every coping face (t = 0 when it already does); columns sit at the
    intersection of the two neighbouring offset lines. The bottom drops RAIL_DROP_M into the cap (V5)."""
    rg, cp = obj("TOW02_railing_glass"), obj("TOW02_coping")
    near = Near(polys(cp))
    cb = BVHTree.FromObject(cp, bpy.context.evaluated_depsgraph_get())
    me = rg.data
    rep = []
    for isl in islands(me):
        zb = min(me.vertices[v].co.z for v in isl["verts"])
        zt = max(me.vertices[v].co.z for v in isl["verts"])
        order, top, closed = _chain(me, isl["verts"], zb)
        P0 = [np.array(me.vertices[v].co.xy) for v in order]
        N = len(P0)
        K = N if closed else N - 1
        seg = [(P0[k], P0[(k + 1) % N]) for k in range(K)]
        nrm, votes = [], 0
        for a, b in seg:
            d = (b - a) / np.linalg.norm(b - a)
            n = np.array([d[1], -d[0]])
            c = np.array([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, zb + 0.06])
            n3 = np.array([n[0], n[1], 0.0])
            ip = _inside(cb, c + n3 * 0.008, (0.3, 0.7, 0.05))
            im = _inside(cb, c - n3 * 0.008, (0.3, 0.7, 0.05))
            votes += (im and not ip) - (ip and not im)
            nrm.append(n)
        sgn = 1.0 if votes >= 0 else -1.0
        nrm = [n * sgn for n in nrm]
        rect = lambda k, a, b: [(("r", k), np.array([[a[0], a[1], zb], [b[0], b[1], zb], [b[0], b[1], zt],
                                                      [a[0], a[1], zt]]))]
        T = []
        for k in range(K):
            t = 0.0
            while t < 0.03 and near.pairs(rect(k, seg[k][0] + nrm[k] * t, seg[k][1] + nrm[k] * t)):
                t += STEP_M
            T.append(t)

        def column(j):
            ks = [k for k in ((j - 1) % K if closed else j - 1, j) if 0 <= k < K]
            if len(ks) == 1:
                return P0[j] + nrm[ks[0]] * T[ks[0]]
            k1, k2 = ks
            p1, p2 = P0[j] + nrm[k1] * T[k1], P0[j] + nrm[k2] * T[k2]
            d1, d2 = seg[k1][1] - seg[k1][0], seg[k2][1] - seg[k2][0]
            cr = abs(d1[0] * d2[1] - d1[1] * d2[0]) / (np.linalg.norm(d1) * np.linalg.norm(d2))
            X = _line_x(p1, d1, p2, d2) if cr > 0.05 else None
            if X is None or np.linalg.norm(X - P0[j]) > 3 * max(T[k1], T[k2]) + 0.002:
                X = (p1 + p2) / 2                              # near-collinear neighbours: no far mitre point
            return X

        bad = []
        for it in range(60):
            cols = [column(j) for j in range(N)]
            bad = [k for k in range(K) if near.pairs(rect(k, cols[k], cols[(k + 1) % N]))]
            if not bad:
                break
            for k in bad:
                T[k] += STEP_M
        for j, v in enumerate(order):
            c = cols[j]
            for w in (v, top[v]):
                me.vertices[w].co.x, me.vertices[w].co.y = c[0], c[1]
            me.vertices[v].co.z = zb - RAIL_DROP_M
        rep.append(dict(faces=len(isl["faces"]), closed=closed, z_bottom=round(zb, 3), votes=votes,
                        offsets_mm=[round(t * 1000, 1) for t in T], left=len(bad)))
    info["F12_V5"] = rep


# ------------------------------------------------------------------------------------------------ F6
def fix_F6_basket_assemblies(info):
    bas = obj("TOW02_ac_baskets")
    fl = mat_index(bas, "TOW02_ac_floor")
    sills = reveal_faces(vertical=False)
    near = Near(sills)
    sz = {k: float(P[:, 2].mean()) for k, P in sills}
    parts = []
    for name in ("TOW02_ac_railing_glass", "TOW02_ac_coping"):
        o = obj(name)
        for isl in islands(o.data):
            P = np.array([o.matrix_world @ o.data.vertices[v].co for v in isl["verts"]])
            parts.append(dict(ob=o, verts=isl["verts"], c=P[:, :2].mean(0), zmin=float(P[:, 2].min())))
    rep = []
    for isl in islands(bas.data):
        ff = [f for f in isl["faces"] if bas.data.polygons[f].material_index == fl]
        if not ff:
            continue
        FP = polys(bas, set(ff))
        z0 = float(np.mean([P[:, 2].mean() for _, P in FP]))
        c = np.mean([P[:, :2].mean(0) for _, P in FP], axis=0)
        hits = near.pairs(FP)
        if not hits:
            rep.append(dict(xy=[round(x, 2) for x in c], z0=round(z0, 3), shift_mm=0.0, sills=0))
            continue
        top = max(sz[h[1]] for h in hits)
        shift = math.ceil((z0 - top + CLEAR_M) * 10000) / 10000
        mine = [p for p in parts if np.linalg.norm(p["c"] - c) < 1.6 and
                (abs(p["zmin"] - (z0 - 0.005)) < 0.02 or abs(p["zmin"] - (z0 + 1.2)) < 0.02)]
        move_verts(bas, isl["verts"], (0, 0, -shift))
        for p in mine:
            move_verts(p["ob"], p["verts"], (0, 0, -shift))
        left = Near(sills).pairs(polys(bas, set(ff)))
        rep.append(dict(xy=[round(x, 2) for x in c], z0=round(z0, 3), shift_mm=round(-shift * 1000, 1), sills=len(hits),
                        parts_moved=len(mine), left=len(left)))
    info["F6"] = rep


# ------------------------------------------------------------------------------------------------ F13
def fix_F13_stubs_vs_jambs(info):
    """For each window jamb face that an AC glass / coping face lies on (within 6 mm, parallel), the wall-end points of
    the AC glass (both shells) and of the AC coping near that jamb move together into the wall solid (-jamb normal)
    by the minimum that clears 6 mm; the stub faces tilt, the rest of the parts stays (glass stays 7 mm inside the
    coping outline)."""
    jam = reveal_faces(vertical=True)
    jp = dict(jam)
    objs = [obj("TOW02_ac_railing_glass"), obj("TOW02_ac_coping")]
    keys = sorted({h[1] for o in objs for h in Near(jam).pairs(polys(o))})
    rep = []
    for kb in keys:
        Q = jp[kb]
        near = Near([(kb, Q)])
        n, _ = newell(Q)
        q0 = Q.mean(0)
        a = np.cross(n, (0, 0, 1.0))
        a /= np.linalg.norm(a)
        qa, qz = (Q - q0) @ a, Q[:, 2]
        sel = {}
        for o in objs:
            me, mw = o.data, o.matrix_world
            vs = []
            for v in range(len(me.vertices)):
                p = np.array(mw @ me.vertices[v].co)
                if abs((p - q0) @ n) < 0.03 and qa.min() - 0.01 <= (p - q0) @ a <= qa.max() + 0.01 and                         qz.min() - 0.03 <= p[2] <= qz.max() + 0.03:
                    vs.append(v)
            sel[o.name] = (o, vs, {p.index for p in me.polygons if any(v in vs for v in p.vertices)})
        d = -np.array([n[0], n[1], 0.0])
        d /= np.linalg.norm(d)
        hit = lambda: sum(len(near.pairs(polys(o, fs))) for o, vs, fs in sel.values() if fs)
        s_, h = 0.0, hit()
        while h and s_ < 0.02:
            s_ += STEP_M
            for o, vs, fs in sel.values():
                move_verts(o, vs, d * STEP_M)
            h = hit()
        rep.append(dict(jamb=list(kb), xyz=[round(float(x), 3) for x in q0],
                        verts={k: len(v[1]) for k, v in sel.items()}, shift_mm=round(s_ * 1000, 1), left=h))
    info["F13"] = rep


# ------------------------------------------------------------------------------------------------ F11 / F15
def fix_F11_F15_louvre(info):
    lv = obj("TOW02_louvre")
    me = lv.data
    foreign = sum((polys(o) for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("TOW02_")
                   and o.name != "TOW02_louvre" and (o.name.startswith("TOW02_fin_") or
                                                      o.name in ("TOW02_coping", "TOW02_body", "TOW02_top"))), [])
    near = Near(foreign)
    mw = lv.matrix_world
    els = []
    for isl in islands(me):
        P = {v: np.array(mw @ me.vertices[v].co) for v in isl["verts"]}
        s = {v: float((to_local2(p) - C0) @ SD) for v, p in P.items()}
        z = [p[2] for p in P.values()]
        sv = sorted(set(round(x, 5) for x in s.values()))
        e = dict(isl=isl, s=s, s0=min(s.values()), s1=max(s.values()), z0=min(z), z1=max(z),
                 d=[float((to_local2(p) - C0) @ DD) for p in P.values()], ns=len(sv))
        e["kind"] = "blade" if e["z1"] - e["z0"] > 1 else ("rail" if max(e["d"]) - min(e["d"]) > 1 else "crossbar")
        els.append(e)

    def set_s(e, side, val):
        cur = e["s0"] if side == 0 else e["s1"]
        vs = [v for v, x in e["s"].items() if abs(x - cur) < 1e-4]
        move_verts(lv, vs, S_W * (val - cur))
        for v in vs:
            e["s"][v] = val
        e["s0" if side == 0 else "s1"] = val

    def side_faces(e, side):
        cur = e["s0"] if side == 0 else e["s1"]
        return {f for f in e["isl"]["faces"] if all(abs(e["s"][v] - cur) < 1e-4 for v in me.polygons[f].vertices)}

    moved = []
    for it in range(4):
        changed = 0
        for e in els:
            if e["kind"] == "crossbar":
                continue
            for side in (0, 1):
                hits = near.pairs(polys(lv, side_faces(e, side)))
                k = 0
                while hits and k < 30 and e["s1"] - e["s0"] > 0.02:
                    set_s(e, side, (e["s0"] + STEP_M) if side == 0 else (e["s1"] - STEP_M))
                    hits = near.pairs(polys(lv, side_faces(e, side)))
                    k += 1
                if k:
                    changed += 1
                    moved.append(dict(kind=e["kind"], side=side, z=[round(e["z0"], 3), round(e["z1"], 3)],
                                      narrowed_mm=round(k * STEP_M * 1000, 1), left=len(hits)))
        # F1: blade ends inside rails keep the rail sides CLEAR_M proud
        for b in [e for e in els if e["kind"] == "blade"]:
            for r in [e for e in els if e["kind"] == "rail"]:
                if r["s1"] < b["s0"] or r["s0"] > b["s1"] or not (r["z0"] - 0.02 < b["z0"] < r["z1"] or
                                                                   r["z0"] < b["z1"] < r["z1"] + 0.02):
                    continue
                if b["s0"] < r["s0"] + CLEAR_M - 1e-6:
                    set_s(b, 0, r["s0"] + CLEAR_M)
                    changed += 1
                if b["s1"] > r["s1"] - CLEAR_M + 1e-6:
                    set_s(b, 1, r["s1"] - CLEAR_M)
                    changed += 1
        if not changed:
            break
    left = near.pairs(polys(lv))
    info["F11_F15"] = dict(elements=len(els), moves=moved, iterations=it + 1, left=len(left),
                           min_width_mm=round(min(e["s1"] - e["s0"] for e in els) * 1000, 1))


# ------------------------------------------------------------------------------------------------ main
def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not argv:
        raise SystemExit("usage: ... --python fix_overlaps_blender.py -- <out_dir>")
    out_dir = os.path.abspath(argv[0])
    src = os.path.abspath(bpy.data.filepath)
    out = os.path.join(out_dir, "tow02_master.blend")
    if os.path.normcase(out) == os.path.normcase(src) or os.path.exists(out):
        raise SystemExit(f"refusing to write {out}: input file or existing output")
    os.makedirs(out_dir, exist_ok=True)
    faces0 = {o.name: len(o.data.polygons) for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("TOW02_")}
    info = dict(input=src)
    for fn in (fix_orientation_reveals, fix_F7_bowtie_reveals, fix_F9_nonconvex_caps, fix_F14_fin_vs_jamb,
               fix_F10_soffit_step_into_fins, fix_F12_V5_railing_inward, fix_F6_basket_assemblies,
               fix_F13_stubs_vs_jambs, fix_F11_F15_louvre):
        t0 = time.time()
        fn(info)
        for o in bpy.data.objects:
            if o.type == "MESH" and o.name.startswith("TOW02_"):
                o.data.update()
        print("FIX", fn.__name__, f"{time.time() - t0:.1f}s", json.dumps(info[list(info)[-1]], default=str)[:600],
              flush=True)
    faces1 = {o.name: len(o.data.polygons) for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("TOW02_")}
    info["faces"] = {k: [faces0[k], faces1[k]] for k in faces0 if faces0[k] != faces1[k]}
    bpy.ops.wm.save_as_mainfile(filepath=out, check_existing=True, copy=False)
    json.dump(info, open(os.path.join(out_dir, "fix_overlaps_info.json"), "w", encoding="utf-8"), indent=1, default=str)
    print("FIX_OVERLAPS saved", out, json.dumps(info["faces"]))


main()
