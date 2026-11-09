"""TOW02 top: everything above z 64.7 - walls, reveals, caps, copings, roof boxes, glass, railings (runs inside Blender).

Engine gap: EG6 (panelised curtain-wall source: top built from measurements, docs/backlog.md).

Input: outputs/measure-v002/top_parts/top_parts.json (zones Z1-Z4 = closed CCW outlines with interval patterns, caps,
copings, railings, boxes; building-local frame) and the open top boundary loop of TOW02_body at z 64.7, read from the
scene. Reuses scripts/build_body_blender.py (exec'd into a namespace): Builder (1 cm weld, quad), to_world (local ->
world, 56.7 deg), offset_points (mitred reveal offset), material, _to_object, LOCAL_ANGLE_DEG, WELD_M, MAX_SIDE_M.

Objects (collection cfg["collection"]): TOW02_top (slots facade 0 / reveal 1 / band199 2), TOW02_coping (TOW02_coping),
TOW02_top_glass (opening planes at mid reveal + glass faces on the outline), TOW02_railing_glass. Face int attribute
`tow02_part` (PART codes below) tells walls, reveals, caps, soffits, boxes, copings, glass kinds apart.
Copings (user 2026-10-20: one mesh, one section, no invented steps): one rectangle (cfg coping: overhang_m out of the
wall line, inner_m in, height_m incl. embed_m below the cap) swept along the wall line (NW J_E -> J_W, open, ends
end_embed_m inside the M walls, capped; roof = closed ring on U), mitred, quads, stations < MAX_SIDE_M. The path is
the wall line with 10 cm jogs (Douglas-Peucker simplify_m) and steps < step_max_m removed.

No T-junctions:
- Z1 band 64.7-65.4 stands on the body's own top-loop vertices (seeded with the body's world coordinates, so the 64.7
  row is the body loop vertex for vertex); the M part (F edges 8..28) keeps these columns up to 72.2.
- Walls = columns x rows; rows are global per zone; outline parts shared by zones share their columns (coping ends
  are columns of Z2 and Z3; Z3 adds row 69.6 = coping top). Z2/Z3 follow F edge 7 (body columns) between J_W and
  F vertex 8 (the measured M north line passes 33 mm off F vertex 7; following it would leave a sliver cap).
- Every cap is filled from the exact boundary vertices of the walls around it, never adding boundary vertices:
  strips (cap 65.4, coping tops, ledge 72.2) by a DP ladder with 3:1 transitions (free side densified to >= 1 vertex
  per 2 fixed ones); terrace / roof / box roofs by constrained Delaunay with interior grid points -> triangle pairing
  -> remaining triangle pairs joined along quad chains (midpoints on interior edges only) -> smoothing of interior
  points. Odd boundary counts are fixed by one extra column along the chain cap65 -> NW coping top -> terrace ->
  ledge -> roof coping top -> roof. Remaining triangles are reported (info["triangles"]).
- Box tops are ladders 1:1 with the box wall columns. The terrace / roof caps run to the wall line; the copings sit
  on them embedded embed_m (no coplanar faces).
Reveal backs: a column closer to a convex corner than the reveal depth gets its back point between its neighbours'
(1 cm weld may then leave a sill/head triangle, reported).
Cap-band protrusion 71.5-72.2 on M edge 17 (F edge 25): own outline (band line measured from the source, cfg), soffit
at 71.5; costs 2 triangles (wedge tip at the east end, wall under the protruding corner).
Glass faces on the outline (NW storey 65.4-68.9, U volume 72.2-75.7): planes in TOW02_top_glass on the outline
vertices; TOW02_top has no face there. Railings: one glass plane per polyline segment from the base-frame bottom to the
top-frame top (frames folded into the plane), ends clipped to the M walls and embedded `railing_embed_m`; with
railing_z starting 10 mm below the caps the planes embed 10 mm into the caps and 0.16 m into the copings.

    ns = {"__file__": path}; exec(open(path).read(), ns); ns["build"](cfg)
"""
import json
import math
import os

import bmesh
import bpy
from mathutils import Vector, geometry

H = {}                                   # build_body_blender namespace (filled by build / load_helpers)
FAC, REV, B199, COP = 0, 1, 2, 3
MAT_IDX = {"#210": FAC, "#199": B199, "#201": FAC, "#194": FAC}
PART = {"wall": 1, "sill": 2, "head": 3, "jamb": 4, "cap": 5, "coping": 6, "underside": 7, "soffit": 8, "box": 9,
        "glass_face": 10, "opening_plane": 11, "railing": 12}
UP, DOWN = Vector((0, 0, 1)), Vector((0, 0, -1))


def load_helpers(path):
    ns = {"__name__": "tow02_body_helpers", "__file__": path}
    with open(path, encoding="utf-8") as fh:
        exec(compile(fh.read(), path, "exec"), ns)
    H.clear()
    H.update(ns)
    return H


# ------------------------------------------------------------------------------------------------ 2D helpers
def V2(p):
    return Vector((p[0], p[1]))


def to_local(co):
    a = math.radians(H["LOCAL_ANGLE_DEG"])
    c, s = math.cos(a), math.sin(a)
    return (co[0] * c + co[1] * s, -co[0] * s + co[1] * c, co[2])


def wdir(x, y, z=0.0):
    return H["to_world"](x, y, z)


def cross2(a, b):
    return a.x * b.y - a.y * b.x


def line_x(p, d, q, e):
    """Intersection of lines p + s d and q + u e."""
    den = cross2(d, e)
    if abs(den) < 1e-12:
        raise ValueError("parallel lines")
    return p + d * (cross2(q - p, e) / den)


def seg_dist(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.dot(ab), 1e-12)))
    return (a + ab * t - p).length


def area2(pts):
    return 0.5 * sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1] for i in range(len(pts))) * -1


def ccw(pts):
    pts = [tuple(p[:2]) for p in pts]
    return pts if area2(pts) > 0 else pts[::-1]


def on_edge_sorted(a, b, pts):
    A, d = V2(a), (V2(b) - V2(a)).normalized()
    return sorted(pts, key=lambda p: (V2(p) - A).dot(d))


def with_splits(fixed, extra=0):
    """Ordered points along a line plus splits so every gap < MAX_SIDE_M; `extra` more segments on the longest gap."""
    ms = H["MAX_SIDE_M"]
    gaps = [(V2(b) - V2(a)).length for a, b in zip(fixed[:-1], fixed[1:])]
    ns = [max(1, math.ceil(g / ms - 1e-9)) for g in gaps]
    if extra:
        ns[max(range(len(gaps)), key=lambda q: gaps[q])] += extra
    out = []
    for (a, b), n in zip(zip(fixed[:-1], fixed[1:]), ns):
        A, B = V2(a), V2(b)
        out += [tuple(A.lerp(B, s / n)) for s in range(n)]
    out.append(tuple(V2(fixed[-1])))
    return out


def ring_splits(pts, extra=0):
    """Closed polygon with every side split below MAX_SIDE_M (extra segments on the longest side)."""
    n = len(pts)
    L = [(V2(pts[(i + 1) % n]) - V2(pts[i])).length for i in range(n)]
    big = max(range(n), key=lambda i: L[i])
    out = []
    for i in range(n):
        out += with_splits([pts[i], pts[(i + 1) % n]], extra if i == big else 0)[:-1]
    return out


def dedupe(pts, closed=True, tol=None):
    tol = tol or H["WELD_M"]
    out = []
    for p in pts:
        if not out or (V2(p) - V2(out[-1])).length > tol:
            out.append(tuple(p[:2]))
    if closed and len(out) > 1 and (V2(out[0]) - V2(out[-1])).length <= tol:
        out.pop()
    return out


def simplify(pts, tol):
    """Douglas-Peucker on an open polyline (ends kept)."""
    if len(pts) < 3:
        return list(pts)
    A, B = V2(pts[0]), V2(pts[-1])
    k, dmax = 0, -1.0
    for i in range(1, len(pts) - 1):
        dd = seg_dist(V2(pts[i]), A, B)
        if dd > dmax:
            k, dmax = i, dd
    if dmax <= tol:
        return [pts[0], pts[-1]]
    return simplify(pts[:k + 1], tol)[:-1] + simplify(pts[k:], tol)


def offset_open(pts, d, start_line, end_line):
    """Polyline offset by d to the right (outward of a CCW outline part); ends on start_line / end_line (point, dir)."""
    P = [V2(p) for p in pts]
    n = len(P)
    out = []
    for i in range(n):
        if i in (0, n - 1):
            e = (P[1] - P[0]).normalized() if i == 0 else (P[-1] - P[-2]).normalized()
            nrm = Vector((e.y, -e.x))
            ln = start_line if i == 0 else end_line
            out.append(line_x(P[i] + nrm * d, e, ln[0], ln[1]))
            continue
        d0, d1 = (P[i] - P[i - 1]).normalized(), (P[i + 1] - P[i]).normalized()
        n0, n1 = Vector((d0.y, -d0.x)), Vector((d1.y, -d1.x))
        m = n0 + n1
        m = n1 if m.length < 1e-6 else m.normalized()
        out.append(P[i] + m * (d / max(m.dot(n1), 0.2)))
    _check_offset(P, out, closed=False)
    return [tuple(p) for p in out]


def offset_closed(pts, d):
    """Closed CCW polygon offset outward by d (body offset_points with negative depth)."""
    out = H["offset_points"]([tuple(p) for p in pts], -d)
    _check_offset([V2(p) for p in pts], out, closed=True)
    return [tuple(p) for p in out]


def _check_offset(P, out, closed):
    n = len(P)
    for i in range(n if closed else n - 1):
        j = (i + 1) % n
        if (out[j] - out[i]).dot(P[j] - P[i]) <= 0:
            raise ValueError(f"offset flips segment {i} at {tuple(round(c, 3) for c in P[i])}")


def clip_to_wall(pts, wa, wb, embed=0.0):
    """Cut a polyline whose FIRST end runs into the M volume at the wall line wa->wb (M interior = left of it); the
    first point becomes the crossing (moved `embed` further into the wall)."""
    A, d = V2(wa), (V2(wb) - V2(wa)).normalized()
    inside = lambda p: cross2(d, V2(p) - A) > 0
    k = 0
    while k < len(pts) and inside(pts[k]):
        k += 1
    if k >= len(pts) - 1:
        raise ValueError("polyline (almost) entirely inside the wall")
    p_out = V2(pts[k])                                          # first point outside M
    e = (V2(pts[k - 1]) - p_out) if k > 0 else (p_out - V2(pts[k + 1]))   # towards the wall
    e.normalize()
    x = line_x(p_out, e, A, d) + e * embed
    return [tuple(x)] + [tuple(p[:2]) for p in pts[k:]]


# ------------------------------------------------------------------------------------------------ mesh builder
class TopMesh:
    """Body Builder (1 cm weld, quads, duplicate/degenerate refusal) + seeded vertices, triangles, part attribute."""

    def __init__(self, label):
        self.b = H["Builder"]()
        self.bm = self.b.bm
        self.label = label
        self.part = self.bm.faces.layers.int.new("tow02_part")
        self.tris = []
        self.degenerate = []
        self.counts = {}

    def seed(self, p, co):
        cell = tuple(int(math.floor(c / H["WELD_M"])) for c in p)
        vert = self.bm.verts.new(co)
        self.b.grid.setdefault(cell, []).append((tuple(p), vert))
        return vert

    def v(self, p):
        return self.b.v(p)

    def face(self, pts, mat, want=None, tag="wall"):
        vs = [self.v(p) for p in pts]
        idx = [k for k in range(len(vs)) if vs[k] is not vs[k - 1]]
        pts, vs = [pts[k] for k in idx], [vs[k] for k in idx]
        if len(vs) != len(set(vs)) or len(vs) < 3:
            self.b.skipped["degenerate"] += 1
            self.degenerate.append({"part": tag, "local_xyz": [round(c, 3) for c in pts[0]], "verts": len(set(vs))})
            return None
        if len(vs) == 4:
            f = self.b.quad(pts, mat, want)
        elif len(vs) == 3:
            a, b, c = (Vector(p) for p in pts)
            if (b - a).cross(c - a).length < 1e-6:
                self.b.skipped["degenerate"] += 1
                self.degenerate.append({"part": tag, "local_xyz": [round(x, 3) for x in pts[0]], "verts": 3})
                return None
            key = frozenset(vs)
            if key in self.b.fset:
                self.b.skipped["duplicate"] += 1
                return None
            self.b.fset.add(key)
            f = self.bm.faces.new(vs)
            f.material_index = mat
            if want is not None:
                f.normal_update()
                if f.normal.dot(want) < 0:
                    f.normal_flip()
            cen = sum((Vector(p) for p in pts), Vector()) / 3
            self.tris.append({"part": tag, "local_xyz": [round(c, 3) for c in cen]})
        else:
            raise ValueError(f"{len(vs)}-gon requested ({tag})")
        if f is not None:
            f[self.part] = PART[tag]
            self.counts[tag] = self.counts.get(tag, 0) + 1
        return f


# ------------------------------------------------------------------------------------------------ cap fill
def _inside(p, loops):
    x, y = p
    c = False
    for L in loops:
        n = len(L)
        for i in range(n):
            (x1, y1), (x2, y2) = L[i - 1], L[i]
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                c = not c
    return c


def _steiner(loops, g):
    xs = [p[0] for p in loops[0]]
    ys = [p[1] for p in loops[0]]
    segs = [(V2(L[i - 1]), V2(L[i])) for L in loops for i in range(len(L))]
    x0, y0 = min(xs), min(ys)
    nx, ny = int((max(xs) - x0) / g) + 1, int((max(ys) - y0) / g) + 1
    ox, oy = x0 + 0.5 * ((max(xs) - x0) - (nx - 1) * g), y0 + 0.5 * ((max(ys) - y0) - (ny - 1) * g)
    out = []
    for i in range(nx):
        for j in range(ny):
            p = (ox + i * g, oy + j * g)
            if _inside(p, loops) and min(seg_dist(V2(p), a, b) for a, b in segs) > 0.5 * g:
                out.append(p)
    return out


def _quad_shape(f, co):
    """'ok' / 'flat' (a corner > 170 deg or < 3 deg, still convex) / 'concave' (reflex corner)."""
    P = [V2(co[i]) for i in f]
    n = len(P)
    flat = False
    for k in range(n):
        e0, e1 = P[k] - P[k - 1], P[(k + 1) % n] - P[k]
        if cross2(e0, e1) <= 1e-9:
            return "concave"
        ang = 180.0 - math.degrees(e0.angle(e1))
        flat |= ang > 170.0 or ang < 3.0
    return "flat" if flat else "ok"


def _quad_score(q, co):
    P = [V2(co[i]) for i in q]
    worst = 0.0
    for k in range(4):
        e0, e1 = P[k] - P[k - 1], P[(k + 1) % 4] - P[k]
        if cross2(e0, e1) <= 1e-9:
            return None                                     # not strictly convex
        ang = 180.0 - math.degrees(e0.angle(e1))            # interior angle
        if ang > 170.0 or ang < 3.0:
            return None
        worst = max(worst, abs(ang - 90.0))
    return -worst


def pair_triangles(tris, co):
    """Max pairing of adjacent triangles into convex quads: greedy by quality, then augmenting paths."""
    emap = {}
    for ti, t in enumerate(tris):
        for k in range(3):
            emap[(t[k], t[(k + 1) % 3])] = ti
    nb = {i: {} for i in range(len(tris))}
    pairs = []
    for ti, t in enumerate(tris):
        for k in range(3):
            u, v, w = t[k], t[(k + 1) % 3], t[(k + 2) % 3]
            tj = emap.get((v, u))
            if tj is None or tj < ti:
                continue
            d = next(x for x in tris[tj] if x not in (u, v))
            q = (u, d, v, w)
            s = _quad_score(q, co)
            if s is None:
                continue
            nb[ti][tj] = q
            nb[tj][ti] = q
            pairs.append((s, ti, tj))
    mate = [None] * len(tris)
    for s, a, b in sorted(pairs, reverse=True):
        if mate[a] is None and mate[b] is None:
            mate[a], mate[b] = b, a
    for t in range(len(tris)):
        if mate[t] is not None:
            continue
        prev, queue, found = {t: None}, [t], None
        while queue and found is None:
            u = queue.pop(0)
            for w in nb[u]:
                if w in prev:
                    continue
                if mate[w] is None:
                    prev[w], found = u, w
                    break
                x = mate[w]
                if x in prev:
                    continue
                prev[w], prev[x] = u, w
                queue.append(x)
        w = found
        while w is not None:
            u = prev[w]
            nxt = prev[u]
            mate[w], mate[u] = u, w
            w = nxt
    quads = [nb[a][mate[a]] for a in range(len(tris)) if mate[a] is not None and a < mate[a]]
    single = [tris[a] for a in range(len(tris)) if mate[a] is None]
    return quads, single


def fill_region(T, loops, z, mat, want, tag, grid=None, name=""):
    """Fill the planar region (outer loop + holes, exact boundary vertices) at z with quads (+ reported triangles)."""
    loops = [dedupe(L) for L in loops]
    pts, edges = [], []
    for L in loops:
        b0 = len(pts)
        pts += L
        edges += [(b0 + k, b0 + (k + 1) % len(L)) for k in range(len(L))]
    nbnd = len(pts)
    if grid:
        pts += _steiner(loops, grid)
    vc, _, faces, ov, _, _ = geometry.delaunay_2d_cdt([Vector(p) for p in pts], edges, [], 0, 1e-6, True)
    co, extra = [], 0
    for k, c in enumerate(vc):
        if ov[k]:
            co.append(pts[ov[k][0]])
        else:
            co.append((c.x, c.y))
            extra += 1
    tris = []
    for f in faces:
        if len(f) != 3:
            raise ValueError("CDT returned a non-triangle")
        c = tuple(sum(co[i][a] for i in f) / 3 for a in (0, 1))
        if _inside(c, loops):
            t = tuple(f)
            if area2([co[i] for i in t]) < 0:
                t = t[::-1]
            tris.append(t)
    quads, single = pair_triangles(tris, co)
    faces = fix_leftovers(list(quads) + list(single), co)
    faces, co, added = eliminate_triangles(faces, co)
    co = smooth_interior(faces, co, nbnd)
    tight = [[round(c, 3) for c in co[f[0]]] for f in faces
             if min((V2(co[f[a]]) - V2(co[f[b]])).length for a in range(len(f)) for b in range(a)) < H["WELD_M"]]
    for f in faces:
        T.face([(co[i][0], co[i][1], z) for i in f], mat, want, tag)
    return {"name": name, "z": z, "boundary_vertices": nbnd, "steiner": len(pts) - nbnd, "cdt_new_vertices": extra,
            "triangles_in": len(tris), "triangles_after_pairing": len(single), "chord_points_added": added,
            "faces_with_points_within_weld": tight,
            "quads": sum(1 for f in faces if len(f) == 4), "triangles": sum(1 for f in faces if len(f) == 3),
            "concave": sum(1 for f in faces if _quad_shape(f, co) == "concave"),
            "corner_over_170deg": sum(1 for f in faces if _quad_shape(f, co) == "flat")}


def smooth_interior(faces, co, nfixed, iters=15):
    """Laplacian smoothing of the interior points (index >= nfixed: Steiner and chord points); a move is kept only
    if every face around the point stays CCW and does not add a concave quad."""
    co = [tuple(p) for p in co]
    nbr, around = {}, {}
    for k, f in enumerate(faces):
        for q in range(len(f)):
            a, b = f[q], f[(q + 1) % len(f)]
            nbr.setdefault(a, set()).add(b)
            nbr.setdefault(b, set()).add(a)
            around.setdefault(a, []).append(k)

    def state(v):
        if any(area2([co[i] for i in faces[k]]) <= 1e-6 for k in around[v]):
            return None
        p = V2(co[v])
        for k in around[v]:                                  # keep >= 1.5 cm from the face's other edges
            f = faces[k]
            for q in range(len(f)):
                a, b = f[q], f[(q + 1) % len(f)]
                if v not in (a, b) and seg_dist(p, V2(co[a]), V2(co[b])) < 0.015:
                    return None
        return sum(1 for k in around[v] if len(faces[k]) == 4 and _quad_score(faces[k], co) is None)
    for _ in range(iters):
        for v in range(nfixed, len(co)):
            if v not in nbr:
                continue
            old, before = co[v], state(v)
            nb = list(nbr[v])
            co[v] = (sum(co[i][0] for i in nb) / len(nb), sum(co[i][1] for i in nb) / len(nb))
            after = state(v)
            if after is None or (before is not None and after > before):
                co[v] = old
    return co


def _split_face(f, ins, co):
    """Insert midpoints `ins` [(edge, point index)] into face f (CCW); triangle + 1 point -> quad, quad + 2 points ->
    2 quads (opposite edges) or 3 quads with a centre point (adjacent edges)."""
    H = []
    for q in range(len(f)):
        a, b = f[q], f[(q + 1) % len(f)]
        H.append(a)
        for e, m in ins:
            if e == frozenset((a, b)):
                H.append(m)
    mids = [m for _, m in ins]
    if len(f) == 3:
        return [H]
    p1, p2 = (H.index(m) for m in mids)
    rot = lambda s: H[s:] + H[:s]
    if (p2 - p1) % 6 == 3:                                           # opposite edges
        R = rot(p1)
        return [R[0:4], R[3:6] + R[0:1]]
    if (p2 - p1) % 6 == 2:
        R = rot(p1)
    elif (p1 - p2) % 6 == 2:
        R = rot(p2)
    else:
        raise ValueError("chord split: unexpected layout")
    m1, b, m2, c, d, a = R                                           # adjacent edges around corner b
    co.append(tuple(sum(co[i][k] for i in f) / 4 for k in (0, 1)))
    c0 = len(co) - 1
    return [[m1, b, m2, c0], [c0, m2, c, d], [a, m1, c0, d]]


def eliminate_triangles(faces, co):
    """Pair the remaining triangles through chains of quads: midpoints on the crossed (interior) edges, quads on the
    path split in 2 (or 3 with a centre point); the end midpoints are pushed 30 % into the next quad so the two end
    triangles become convex quads. Boundary edges are never split. Returns faces, points, number of points added."""
    faces = [list(f) for f in faces]
    co = [tuple(p) for p in co]
    n0 = len(co)
    blocked = set()
    nudges = 0
    while True:
        tris = [k for k, f in enumerate(faces) if len(f) == 3 and tuple(f) not in blocked]
        if len(tris) < 2 or sum(1 for f in faces if len(f) == 3) < 2:
            break
        emap = {}
        for k, f in enumerate(faces):
            for q in range(len(f)):
                emap.setdefault(frozenset((f[q], f[(q + 1) % len(f)])), []).append(k)
        t0 = tris[0]
        prev, queue, goal = {t0: None}, [t0], None
        while queue and goal is None:
            u = queue.pop(0)
            f = faces[u]
            for q in range(len(f)):
                e = frozenset((f[q], f[(q + 1) % len(f)]))
                for w in emap[e]:
                    if w == u or w in prev:
                        continue
                    if len(faces[w]) == 3:
                        if u == t0:
                            continue                                 # need at least one quad between
                        prev[w] = (u, e)
                        goal = w
                        break
                    prev[w] = (u, e)
                    queue.append(w)
                if goal is not None:
                    break
        if goal is None:
            # t0 only reaches another triangle directly (e.g. an ear at a boundary corner): move one of the two a
            # step into the mesh (triangle + quad = pentagon, re-split elsewhere) and try again
            nb = lambda k: [w for q in range(len(faces[k]))
                            for w in emap[frozenset((faces[k][q], faces[k][(q + 1) % len(faces[k])]))] if w != k]
            moved = False
            for t in [t0] + [w for w in nb(t0) if len(faces[w]) == 3]:
                if nudges > 40:
                    break
                for qk in nb(t):
                    if len(faces[qk]) != 4:
                        continue
                    P = _merge(tuple(faces[t]), tuple(faces[qk]))
                    if P is None or len(P) != 5:
                        continue
                    best = None
                    for k in range(5):
                        tri = (P[k], P[(k + 1) % 5], P[(k + 2) % 5])
                        quad = (P[(k + 2) % 5], P[(k + 3) % 5], P[(k + 4) % 5], P[k])
                        if set(tri) == set(faces[t]) or not (_valid(tri, co) and _valid(quad, co)):
                            continue
                        s = _quad_score(quad, co)
                        if best is None or s > best[0]:
                            best = (s, tri, quad)
                    if best:
                        faces[t], faces[qk] = list(best[1]), list(best[2])
                        moved = True
                        nudges += 1
                        break
                if moved:
                    break
            if not moved:
                blocked.add(tuple(faces[t0]))
            continue
        path, edges = [goal], []
        while prev[path[-1]] is not None:
            u, e = prev[path[-1]]
            edges.append(e)
            path.append(u)
        path.reverse()
        edges.reverse()
        mids = []
        for e in edges:
            a, b = tuple(e)
            co.append(((co[a][0] + co[b][0]) / 2, (co[a][1] + co[b][1]) / 2))
            mids.append(len(co) - 1)
        lerp = lambda p, q, s: (p[0] + (q[0] - p[0]) * s, p[1] + (q[1] - p[1]) * s)
        orig = [co[m] for m in mids]
        base_n = len(co)
        old = range(base_n - len(mids))
        clear = lambda q: all((q[0] - co[k][0]) ** 2 + (q[1] - co[k][1]) ** 2 > 0.02 ** 2 for k in old)
        repl = None
        for s in (0.3, 0.2, 0.4, 0.15, 0.45, 0.1):       # new points >= 2 cm from existing ones (1 cm weld) and
            del co[base_n:]                               # every new piece CCW and convex, else next push / block
            co[mids[0]] = lerp(orig[0], orig[1], s)
            co[mids[-1]] = lerp(orig[-1], orig[-2], s)
            if not all(clear(co[m]) for m in mids):
                continue
            trial = {}
            for i, k in enumerate(path):
                ins = []
                if i > 0:
                    ins.append((edges[i - 1], mids[i - 1]))
                if i < len(path) - 1:
                    ins.append((edges[i], mids[i]))
                trial[k] = _split_face(faces[k], ins, co)
            pieces = [f for v in trial.values() for f in v]
            if all(area2([co[j] for j in f]) > 1e-6 and _quad_shape(f, co) != "concave" for f in pieces) and \
                    all(clear(co[j]) for j in range(base_n, len(co))):
                repl = trial
                break
        if repl is None:
            del co[base_n - len(mids):]
            blocked.add(tuple(faces[t0]))
            continue
        out = []
        for k, f in enumerate(faces):
            out += repl.get(k, [f])
        faces = out
    return [tuple(f) for f in faces], co, len(co) - n0


def _merge(f, g):
    """Union of two CCW faces sharing one edge (u->v in f, v->u in g)."""
    for k in range(len(f)):
        u, v = f[k], f[(k + 1) % len(f)]
        if v in g and g[(g.index(v) + 1) % len(g)] == u:
            fr = list(f[(k + 1):]) + list(f[:k + 1])               # v ... u
            gi = g.index(u)
            gr = list(g[gi:]) + list(g[:gi])                        # u ... v
            return fr + gr[1:-1]
    return None


def _valid(face, co):
    if len(face) == 4:
        return _quad_score(face, co) is not None
    return area2([co[i] for i in face]) > 1e-6


def fix_leftovers(faces, co):
    """Remove triangle pairs: walk a triangle through the quads to another triangle (triangle + quad = pentagon,
    re-split so the triangle moves on), then merge the two triangles. Geometry is unchanged (no new vertices)."""
    faces = [tuple(f) for f in faces]
    failed = set()
    while True:
        tris = [k for k, f in enumerate(faces) if len(f) == 3]
        cand = [k for k in tris if k not in failed]
        if len(tris) < 2 or not cand:
            break
        emap = {}
        for k, f in enumerate(faces):
            for q in range(len(f)):
                emap[(f[q], f[(q + 1) % len(f)])] = k
        nbr = lambda k: [emap[(f2, f1)] for f1, f2 in zip(faces[k], faces[k][1:] + faces[k][:1])
                         if (f2, f1) in emap]
        t0 = cand[0]
        prev, queue, goal = {t0: None}, [t0], None
        while queue and goal is None:
            u = queue.pop(0)
            for w in nbr(u):
                if w in prev:
                    continue
                prev[w] = u
                if len(faces[w]) == 3:
                    goal = w
                    break
                queue.append(w)
        if goal is None:
            failed.add(t0)
            continue
        path = [goal]
        while prev[path[-1]] is not None:
            path.append(prev[path[-1]])
        path = path[::-1]                                           # t0, q1, ..., goal
        new = dict()
        cur = faces[t0]
        ok = True
        for a, b in zip(path[1:-1], path[2:]):
            P = _merge(cur, faces[a])
            if P is None or len(P) != 5:
                ok = False
                break
            nxt = faces[b]
            nedges = {(nxt[q], nxt[(q + 1) % len(nxt)]) for q in range(len(nxt))}
            shared = [(P[k], P[(k + 1) % 5]) for k in range(5) if (P[(k + 1) % 5], P[k]) in nedges]
            if not shared:
                ok = False
                break
            k = P.index(shared[0][0])
            best = None
            for tri, quad in (((P[k - 1], P[k], P[(k + 1) % 5]), (P[(k + 1) % 5], P[(k + 2) % 5], P[(k + 3) % 5],
                                                                   P[k - 1])),
                              ((P[k], P[(k + 1) % 5], P[(k + 2) % 5]), (P[(k + 2) % 5], P[(k + 3) % 5],
                                                                        P[(k + 4) % 5], P[k]))):
                if _valid(tri, co) and _valid(quad, co):
                    s = _quad_score(quad, co)
                    if best is None or s > best[0]:
                        best = (s, tri, quad)
            if best is None:
                ok = False
                break
            new[a] = best[2]
            cur = best[1]
        if ok:
            last = _merge(cur, faces[path[-1]])
            ok = last is not None and len(last) == 4 and _valid(last, co)
        if not ok:
            failed.add(t0)
            continue
        for a, q in new.items():
            faces[a] = q
        faces[path[-1]] = tuple(last)
        faces = [f for k, f in enumerate(faces) if k != t0]
        failed = set()
    return faces


def strip_mesh(A, B, closed):
    """Quads between polylines A and B running the same way. Open: the end rungs are A[0]-B[0] and A[-1]-B[-1];
    closed: rings, B rotated so B[0] is nearest A[0]. Steps: ladder 1:1, transition 3:1 / 1:3 (two interior points,
    4 quads), one triangle only when the segment counts differ by an odd number. DP minimises rung lengths and
    concave faces. Returns faces as lists of 2D points."""
    A = [V2(p) for p in A]
    B = [V2(p) for p in B]
    if closed:
        k = min(range(len(B)), key=lambda q: (B[q] - A[0]).length)
        B = B[k:] + B[:k] + [B[k]]
        A = A + [A[0]]
    nA, nB = len(A) - 1, len(B) - 1
    need = (nA + nB) % 2

    def bad(face):
        P = face
        if len(P) == 3:
            return 0.0 if abs(cross2(P[1] - P[0], P[2] - P[0])) > 1e-8 else 1e3
        s = [cross2(P[q] - P[q - 1], P[(q + 1) % 4] - P[q]) for q in range(4)]
        if not (all(x > 1e-9 for x in s) or all(x < -1e-9 for x in s)):
            return 1e3
        return 0.0

    def steps(i, j, t):
        if i < nA and j < nB:
            yield (i + 1, j + 1, t), [[A[i], A[i + 1], B[j + 1], B[j]]], 0.0
        if i + 3 <= nA and j < nB:
            m1 = A[i + 1].lerp(B[j].lerp(B[j + 1], 1 / 3), 0.5)
            m2 = A[i + 2].lerp(B[j].lerp(B[j + 1], 2 / 3), 0.5)
            yield (i + 3, j + 1, t), [[A[i], A[i + 1], m1, B[j]], [A[i + 1], A[i + 2], m2, m1],
                                      [A[i + 2], A[i + 3], B[j + 1], m2], [m1, m2, B[j + 1], B[j]]], 0.05
        if i < nA and j + 3 <= nB:
            m1 = B[j + 1].lerp(A[i].lerp(A[i + 1], 1 / 3), 0.5)
            m2 = B[j + 2].lerp(A[i].lerp(A[i + 1], 2 / 3), 0.5)
            yield (i + 1, j + 3, t), [[A[i], m1, B[j + 1], B[j]], [m1, m2, B[j + 2], B[j + 1]],
                                      [m2, A[i + 1], B[j + 3], B[j + 2]], [A[i], A[i + 1], m2, m1]], 0.05
        if need and not t:
            if i < nA:
                yield (i + 1, j, 1), [[A[i], A[i + 1], B[j]]], 1.0
            if j < nB:
                yield (i, j + 1, 1), [[A[i], B[j + 1], B[j]]], 1.0

    INF = float("inf")
    best = {(0, 0, 0): (0.0, None, None)}
    for i in range(nA + 1):
        for j in range(nB + 1):
            for t in (0, 1):
                cur = best.get((i, j, t))
                if cur is None:
                    continue
                for st, fs, pen in steps(i, j, t):
                    rung = (A[st[0]] - B[st[1]]).length
                    c = cur[0] + rung * rung + (1e4 if rung > H["MAX_SIDE_M"] else 0.0) + pen +                         sum(bad(f) for f in fs)
                    if c < best.get(st, (INF,))[0]:
                        best[st] = (c, (i, j, t), fs)
    end = (nA, nB, need)
    if end not in best:
        raise ValueError("strip_mesh: no path")
    out, s = [], end
    while best[s][1] is not None:
        out += best[s][2]
        s = best[s][1]
    return out[::-1], round(best[end][0], 3), sum(1 for f in out if bad(f) > 0)


def fill_strip(T, A, B, closed, z, mat, want, tag, name=""):
    A, B = dedupe(A, closed), dedupe(B, closed)
    faces, cost, _ = strip_mesh(A, B, closed)
    co, index = [], {}
    for p in [V2(q) for q in A + B]:
        key = (round(p.x, 9), round(p.y, 9))
        if key not in index:
            index[key] = len(co)
            co.append((p.x, p.y))
    nfixed = len(co)
    idx_faces = []
    for f in faces:
        ids = []
        for p in f:
            key = (round(p.x, 9), round(p.y, 9))
            if key not in index:
                index[key] = len(co)
                co.append((p.x, p.y))
            ids.append(index[key])
        idx_faces.append(tuple(i if area2([co[j] for j in ids]) > 0 else i for i in ids))
    idx_faces = [f if area2([co[j] for j in f]) > 0 else f[::-1] for f in idx_faces]
    co = smooth_interior(idx_faces, co, nfixed)
    for f in idx_faces:
        T.face([(co[i][0], co[i][1], z) for i in f], mat, want, tag)
    return {"name": name, "z": z, "A": len(A), "B": len(B), "quads": sum(1 for f in idx_faces if len(f) == 4),
            "triangles": sum(1 for f in idx_faces if len(f) == 3),
            "concave": sum(1 for f in idx_faces if _quad_shape(f, co) == "concave"),
            "corner_over_170deg": sum(1 for f in idx_faces if _quad_shape(f, co) == "flat")}


def ladder(T, A, B, za, zb, mat, want, tag, closed):
    """Quads between two point rows of equal length (A at za, B at zb)."""
    n = len(A)
    for i in range(n if closed else n - 1):
        j = (i + 1) % n
        T.face(((A[i][0], A[i][1], za), (A[j][0], A[j][1], za), (B[j][0], B[j][1], zb), (B[i][0], B[i][1], zb)),
               mat, want, tag)


def side_walls(T, pts, z0, z1, mat, tag, closed, outward=True):
    n = len(pts)
    for i in range(n if closed else n - 1):
        j = (i + 1) % n
        d = V2(pts[j]) - V2(pts[i])
        if d.length < 1e-9:
            continue
        d.normalize()
        want = wdir(d.y, -d.x) if outward else wdir(-d.y, d.x)
        T.face(((pts[i][0], pts[i][1], z0), (pts[j][0], pts[j][1], z0), (pts[j][0], pts[j][1], z1),
                (pts[i][0], pts[i][1], z1)), mat, want, tag)


# ------------------------------------------------------------------------------------------------ walls
def zone_kinds(zone, cols, rows, omit=()):
    """Per column segment and row span: ('solid'|'open'|'glass'|'none', pattern span)."""
    n = len(cols)
    K = []
    for i in range(n):
        j = (i + 1) % n
        E = zone["edges"][cols[i][2]]
        A, B = V2(E["a"]), V2(E["b"])
        d = (B - A).normalized()
        t = ((V2(cols[i]) + V2(cols[j])) / 2 - A).dot(d)
        iv = min(E["intervals"], key=lambda iv: 0.0 if iv["t0"] <= t <= iv["t1"] else
                 min(abs(t - iv["t0"]), abs(t - iv["t1"])))
        row = []
        for r in range(len(rows) - 1):
            if (i, r) in omit:
                row.append(("none", None))
                continue
            zm = 0.5 * (rows[r] + rows[r + 1])
            sp = next(s for s in zone["patterns"][iv["pattern"]] if s["z"][0] - 1e-6 <= zm <= s["z"][1] + 1e-6)
            row.append(({"solid": "solid", "opening": "open", "glass_face": "glass"}[sp["type"]], sp))
        K.append(row)
    return K


def monotone_offsets(cols, Q):
    """Offsets (reveal back / mid reveal) of columns closer to a convex corner than the offset depth land beyond the
    corner's mitred point (twisted sill quads, T-junction on the reveal back): such a column's point goes to the
    middle of its neighbours' points (it stays on the offset line)."""
    n = len(cols)
    Q = [q.copy() for q in Q]
    for _ in range(6):
        changed = False
        for i in range(n):
            j = (i + 1) % n
            if (Q[j] - Q[i]).dot(V2(cols[j]) - V2(cols[i])) > 0:
                continue
            for k in (i, j):
                a, b, p = V2(cols[(k - 1) % n]), V2(cols[(k + 1) % n]), V2(cols[k])
                straight = (p - a).length > 1e-9 and (b - p).length > 1e-9 and \
                    abs(cross2((p - a).normalized(), (b - p).normalized())) < 2e-3
                if straight:
                    Q[k] = (Q[(k - 1) % n] + Q[(k + 1) % n]) / 2
                    changed = True
                    break
        if not changed:
            break
    return Q


def build_walls(T, G, cols, rows, K, reveal):
    n = len(cols)
    inner = monotone_offsets(cols, H["offset_points"](cols, reveal))
    P = lambda i, z: (cols[i % n][0], cols[i % n][1], z)
    Q = lambda i, z: (inner[i % n].x, inner[i % n].y, z)
    for i in range(n):
        j = (i + 1) % n
        d = V2(cols[j]) - V2(cols[i])
        if d.length < 1e-9:
            continue
        d.normalize()
        out = wdir(d.y, -d.x)
        for r in range(len(rows) - 1):
            za, zb = rows[r], rows[r + 1]
            kind, sp = K[i][r]
            quad = (P(i, za), P(j, za), P(j, zb), P(i, zb))
            if kind == "solid":
                T.face(quad, MAT_IDX[sp["material"]], out, "wall")
            elif kind == "glass":
                G.face(quad, 0, out, "glass_face")
            elif kind == "open":
                oz0, oz1 = sp["open_z"]
                if abs(za - oz0) < 1e-6:
                    T.face((Q(i, za), Q(j, za), P(j, za), P(i, za)), REV, UP, "sill")
                if abs(zb - oz1) < 1e-6:
                    T.face((P(i, zb), P(j, zb), Q(j, zb), Q(i, zb)), REV, DOWN, "head")
                if K[(i - 1) % n][r][0] != "open":
                    T.face((P(i, za), P(i, zb), Q(i, zb), Q(i, za)), REV, wdir(d.x, d.y), "jamb")
                if K[j][r][0] != "open":
                    T.face((P(j, za), Q(j, za), Q(j, zb), P(j, zb)), REV, wdir(-d.x, -d.y), "jamb")


def opening_planes(G, cols, rows, K, reveal, ov):
    """Glass planes at mid reveal per run of opening segments, for openings that start in these rows."""
    n = len(cols)
    mid = monotone_offsets(cols, H["offset_points"](cols, reveal / 2))
    made = 0
    for r in range(len(rows) - 1):
        isopen = [K[i][r][0] == "open" and abs(K[i][r][1]["open_z"][0] - rows[r]) < 1e-6 for i in range(n)]
        if not any(isopen):
            continue
        start = next(i for i in range(n) if not isopen[i])
        runs, cur = [], []
        for s in range(1, n + 1):
            i = (start + s) % n
            if isopen[i]:
                cur.append(i)
            elif cur:
                runs.append(cur)
                cur = []
        for run in runs:
            idx = run + [(run[-1] + 1) % n]
            pts = [mid[q].copy() for q in idx]
            pts[0] -= (V2(cols[idx[1]]) - V2(cols[idx[0]])).normalized() * ov
            pts[-1] += (V2(cols[idx[-1]]) - V2(cols[idx[-2]])).normalized() * ov
            oz0, oz1 = K[run[0]][r][1]["open_z"]
            ga, gb = oz0 - ov, oz1 + ov
            for q in range(len(pts) - 1):
                d = (pts[q + 1] - pts[q]).normalized()
                G.face(((pts[q].x, pts[q].y, ga), (pts[q + 1].x, pts[q + 1].y, ga), (pts[q + 1].x, pts[q + 1].y, gb),
                        (pts[q].x, pts[q].y, gb)), 0, wdir(d.y, -d.x), "opening_plane")
                made += 1
    return made


# ------------------------------------------------------------------------------------------------ body loop
def body_columns(body, F, z):
    """Body top-loop vertices on the F outline at z: [(F edge k, t, local xy, world co)] in outline order."""
    mw = body.matrix_world
    bm = bmesh.new()
    bm.from_mesh(body.data)
    cand = set()
    for e in bm.edges:
        if e.is_boundary and all(abs((mw @ v.co).z - z) < 1e-4 for v in e.verts):
            cand.update(e.verts)
    n = len(F)
    cols, keep = [], set()
    for v in cand:
        co = mw @ v.co
        p = V2(to_local(co))
        best = None
        for k in range(n):
            A, B = F[k], F[(k + 1) % n]
            L = (B - A).length
            d = (B - A) / L
            t = max(0.0, min(L, (p - A).dot(d)))
            dist = (A + d * t - p).length
            if best is None or dist < best[0]:
                best = (dist, k, t, L)
        dist, k, t, L = best
        if dist > 0.003:
            continue                                         # reveal-head back (0.12 m inside)
        if t > L - 0.005:
            k, t = (k + 1) % n, 0.0
        elif t < 0.005:
            t = 0.0
        cols.append((k, t, (p.x, p.y), co.copy()))
        keep.add(v)
    loop_edges = sum(1 for e in bm.edges if e.is_boundary and all(v in keep for v in e.verts))
    bm.free()
    cols.sort(key=lambda c: (c[0], c[1]))
    corners = {c[0] for c in cols if c[1] == 0.0}
    missing = [k for k in range(n) if k not in corners]
    if missing or loop_edges != len(cols):
        raise ValueError(f"body top loop: missing F corners {missing}, {loop_edges} edges / {len(cols)} vertices")
    return cols


# ------------------------------------------------------------------------------------------------ layout
FACING_RATIO = 2.0          # free side of a strip gets >= 1 vertex per 2 vertices of the fixed side facing it


def facing_splits(base, closed, others, extra=0):
    """Points of polyline/ring `base` plus splits: sides < MAX_SIDE_M and at least one segment per FACING_RATIO
    `others` points facing it (nearest segment), so a strip against a denser fixed side needs only 1:1 and 3:1 steps
    (pieces >= 0.1 m). `extra` more segments on the longest segment. Returns [(x, y, segment index)]; an open
    polyline also gets its last point."""
    B = [V2(p) for p in base]
    n = len(B)
    segs = list(range(n if closed else n - 1))
    cnt = [0] * len(segs)
    for p in others:
        P = V2(p)
        cnt[min(segs, key=lambda s: seg_dist(P, B[s], B[(s + 1) % n]))] += 1
    L = [(B[(s + 1) % n] - B[s]).length for s in segs]
    ns = []
    for s in segs:
        need = max(1, math.ceil(L[s] / H["MAX_SIDE_M"] - 1e-9))
        ns.append(max(need, min(math.ceil(cnt[s] / FACING_RATIO), max(1, int(L[s] / 0.1)))))
    if extra:
        ns[max(segs, key=lambda s: L[s])] += extra
    out = []
    for s in segs:
        a, b = B[s], B[(s + 1) % n]
        for q in range(ns[s]):
            p = a.lerp(b, q / ns[s])
            out.append((p.x, p.y, s))
    if not closed:
        out.append((B[-1].x, B[-1].y, segs[-1]))
    return out


def _idx(cols, p):
    return next(k for k, c in enumerate(cols) if (V2(c) - V2(p)).length < 1e-6)


def layout(tp, bcols, cfg, extras):
    """All column lists, strips and region loops (pure python; extras = parity knobs). The copings are a separate
    swept object (build_copings), so walls and caps carry no coping vertices."""
    Z1, Z2, Z3, Z4 = tp["zones"]
    E2, E3, E4 = Z2["edges"], Z3["edges"], Z4["edges"]
    lay = {}
    on_f = lambda k: [c[2] for c in bcols if c[0] == k]
    z1c = lay["z1"] = [(c[2][0], c[2][1], c[0]) for c in bcols]
    F29, F7 = on_f(29)[0], on_f(7)[0]
    J_E, J_W = tuple(E2[21]["a"]), tuple(E2[51]["a"])
    # the M north wall J_W -> F vertex 8 passes 33 mm north of F vertex 7: Z2/Z3 take F edge 7 (body columns) as
    # their wall there, so the 65.4 cap has no 33 mm sliver along it
    i29, i7 = _idx(z1c, F29), _idx(z1c, F7)
    fpart = [z1c[k % len(z1c)][:2] for k in range(i29, i7 + len(z1c) + 1)]           # F vertex 29 .. F vertex 7
    # NW chain J_E .. J_W (Z2 edges 21..50) densified against the F side (cap 65.4 strip)
    base = [E2[e]["a"] for e in range(21, 51)] + [J_W]
    chain = [(x, y, 21 + s) for x, y, s in facing_splits(base, False, fpart, extras["chain"])][:-1]
    lay.update(chain=chain, J_E=J_E, J_W=J_W)
    # Z2 columns
    z2 = []
    for e in range(52):
        if e <= 19:
            pts = on_f(e + 8)
        elif e == 20:
            pts = on_f(28) + [F29]
        elif e <= 50:
            pts = [c[:2] for c in chain if c[2] == e]
        else:
            pts = [J_W] + on_f(7)
        z2 += [(p[0], p[1], e) for p in pts]
    lay["z2"] = z2
    # Z3 columns (M part shared with Z2)
    z3 = []
    for e in range(24):
        if e <= 19:
            pts = [c[:2] for c in z2 if c[2] == e]
        elif e == 20:
            pts = on_f(28) + [F29] + with_splits([J_E, E3[20]["b"]])[:-1]
        elif e in (21, 22):
            pts = with_splits([E3[e]["a"], E3[e]["b"]], extras["m21"] if e == 21 else 0)[:-1]
        else:
            pts = with_splits([E3[23]["a"], J_W]) + on_f(7)
        z3 += [(p[0], p[1], e) for p in pts]
    lay["z3"] = z3
    # cap-band outline 71.5-72.2: M with edge `pe` moved out by a linear offset (measured), corner on the next edge
    pr = cfg["cap_band_protrusion"]
    pe = pr["edge"]
    A, B = V2(E3[pe]["a"]), V2(E3[pe]["b"])
    L = (B - A).length
    d = (B - A) / L
    nrm = Vector((d.y, -d.x))
    A2, B2 = A + nrm * pr["offset_a_m"], B + nrm * pr["offset_b_m"]
    dn = (V2(E3[pe + 1]["b"]) - V2(E3[pe + 1]["a"])).normalized()
    corner = line_x(A2, (B2 - A2).normalized(), B, dn)
    band = []
    for c in z3:
        p = V2(c)
        if c[2] == pe:
            off = pr["offset_a_m"] + (pr["offset_b_m"] - pr["offset_a_m"]) * (p - A).dot(d) / L
            if abs(off) >= H["WELD_M"]:
                p = p + nrm * off
        elif c[2] == pe + 1 and (p - B).length < 0.005:
            p = corner
        band.append((p.x, p.y, c[2]))
    lay["band"] = band
    lay["band_corner"] = tuple(corner)
    # U columns densified against the band (ledge strip)
    u = facing_splits([E4[e]["a"] for e in range(36)], True, [c[:2] for c in band], extras["u"])
    lay["u"] = u
    # boxes: outer / inner rings with equal splits on opposite sides
    boxes = []
    for bx in tp["boxes"]:
        O, I = ccw(bx["footprint_outer"]), ccw(bx["footprint_inner"])
        k0 = min(range(4), key=lambda k: (V2(I[k]) - V2(O[0])).length)
        I = I[k0:] + I[:k0]
        side = lambda P, k: (V2(P[(k + 1) % 4]) - V2(P[k % 4])).length
        ns = [max(1, math.ceil(max(side(O, k), side(I, k), side(O, k + 2), side(I, k + 2)) / H["MAX_SIDE_M"] - 1e-9))
              for k in range(4)]
        Oc, Ic = [], []
        for k in range(4):
            Oc += [tuple(V2(O[k]).lerp(V2(O[(k + 1) % 4]), s / ns[k])) for s in range(ns[k])]
            Ic += [tuple(V2(I[k]).lerp(V2(I[(k + 1) % 4]), s / ns[k])) for s in range(ns[k])]
        boxes.append(dict(name=bx["name"], O=Oc, I=Ic, z0=bx["walls_z"][0], z1=bx["walls_z"][1],
                          zr=bx["roof_slab_z"][1]))
    lay["boxes"] = boxes
    # strips and regions
    ia, ib = _idx(z2, J_E), _idx(z2, J_W)
    lay["strip_cap65"] = (fpart, [z2[k][:2] for k in range(ia, ib + 1)], False)
    lay["strip_ledge"] = ([c[:2] for c in band], [c[:2] for c in u], True)
    ja, jb = _idx(z3, J_E), _idx(z3, J_W)
    lay["loop_terrace"] = [z2[k][:2] for k in range(ia, ib + 1)] + [z3[k][:2] for k in range(jb - 1, ja, -1)]
    lay["loops_roof"] = [[c[:2] for c in u]] + [b["O"] for b in boxes]
    return lay


REGIONS = [("cap65", "chain"), ("terrace", "m21"), ("ledge", "u"), ("roof", None)]


def parities(lay):
    n = lambda L, closed=True: len(dedupe(L, closed))
    st = lambda key: (n(lay[key][0], lay[key][2]) + n(lay[key][1], lay[key][2])) % 2
    return {"cap65": st("strip_cap65"), "terrace": n(lay["loop_terrace"]) % 2, "ledge": st("strip_ledge"),
            "roof": sum(n(L) for L in lay["loops_roof"]) % 2}


# ------------------------------------------------------------------------------------------------ copings
def coping_path(pts, closed, step_max, dp_tol, par_deg=15.0):
    """Wall line for the coping sweep: Douglas-Peucker (dp_tol, drops the 10 cm jogs; arcs keep a few facets), then
    small steps removed (an edge shorter than step_max between two parallel edges is dropped and its neighbours
    joined), collinear points dropped. Path ends are kept."""
    if closed:
        P = [V2(p) for p in simplify([tuple(q) for q in pts] + [tuple(pts[0])], dp_tol)[:-1]]
    else:
        P = [V2(p) for p in simplify([tuple(q) for q in pts], dp_tol)]
    cmax = math.cos(math.radians(par_deg))
    removed = []
    while True:
        n = len(P)
        best = None
        for i in (range(n) if closed else range(1, n - 2)):
            a, b = P[i], P[(i + 1) % n]
            L = (b - a).length
            if L >= step_max:
                continue
            dp, dn = a - P[(i - 1) % n], P[(i + 2) % n] - b
            if dp.length < 1e-9 or dn.length < 1e-9 or dp.normalized().dot(dn.normalized()) < cmax:
                continue
            if best is None or L < best[0]:
                best = (L, i)
        if best is None:
            break
        i = best[1]
        removed.append([round(c, 3) for c in P[i]] + [round(best[0], 3)])
        drop = {i, (i + 1) % n}
        P = [p for k, p in enumerate(P) if k not in drop]
    keep = []
    n = len(P)
    for k in range(n):
        if not closed and k in (0, n - 1):
            keep.append(P[k])
            continue
        d0, d1 = (P[k] - P[k - 1]).normalized(), (P[(k + 1) % n] - P[k]).normalized()
        if abs(cross2(d0, d1)) > 1e-3 or d0.dot(d1) < 0:
            keep.append(P[k])
    return keep, removed


def _offset_path(P, d, closed, ends=None):
    """Mitred offset (d > 0: right of the path). ends: ((point, dir), (point, dir)) lines for the open ends."""
    n = len(P)
    out = []
    for i in range(n):
        if not closed and i in (0, n - 1):
            e = (P[1] - P[0]).normalized() if i == 0 else (P[-1] - P[-2]).normalized()
            nrm = Vector((e.y, -e.x))
            q, dq = ends[0] if i == 0 else ends[1]
            out.append(line_x(P[i] + nrm * d, e, q, dq))
            continue
        d0, d1 = (P[i] - P[i - 1]).normalized(), (P[(i + 1) % n] - P[i]).normalized()
        n0, n1 = Vector((d0.y, -d0.x)), Vector((d1.y, -d1.x))
        m = n0 + n1
        m = n1 if m.length < 1e-6 else m.normalized()
        out.append(P[i] + m * (d / max(m.dot(n1), 0.2)))
    for i in range(n if closed else n - 1):
        j = (i + 1) % n
        if (out[j] - out[i]).dot(P[j] - P[i]) <= 0:
            raise _Flip(i, d)
    return out


class _Flip(Exception):
    def __init__(self, i, d):
        super().__init__(f"coping offset {d} flips at segment {i}")
        self.i = i


def sweep_coping(C, path, closed, cs, z0, z1, ends=None, tag="coping"):
    """One rectangular section (overhang_m right of the path, inner_m left, z0..z1) swept along the path, mitred
    at the corners, quads only, stations so every side < MAX_SIDE_M; open paths get end caps."""
    P = [V2(p) for p in path]
    dropped = []
    while True:                       # a segment whose offset flips: drop its end that deviates least from its
        try:                          # neighbours' line (path ends are kept)
            O = _offset_path(P, cs["overhang_m"], closed, ends)
            I = _offset_path(P, -cs["inner_m"], closed, ends)
            break
        except _Flip as fl:
            n = len(P)
            cand = [k for k in (fl.i, (fl.i + 1) % n) if closed or 0 < k < n - 1]
            if not cand or n < 4:
                raise
            k = min(cand, key=lambda k: seg_dist(P[k], P[k - 1], P[(k + 1) % n]))
            dropped.append([round(c, 3) for c in P[k]])
            P.pop(k)
    n = len(P)
    st = []
    for i in range(n if closed else n - 1):
        j = (i + 1) % n
        k = max(1, math.ceil(max((O[j] - O[i]).length, (I[j] - I[i]).length) / H["MAX_SIDE_M"] - 1e-9))
        st += [(O[i].lerp(O[j], s / k), I[i].lerp(I[j], s / k), (P[j] - P[i]).normalized()) for s in range(k)]
    if not closed:
        st.append((O[-1], I[-1], (P[-1] - P[-2]).normalized()))
    m = len(st)
    widths = []
    for a in range(m if closed else m - 1):
        b = (a + 1) % m
        (oa, ia, d), (ob, ib, _) = st[a], st[b]
        nr = Vector((d.y, -d.x))
        widths.append((((oa + ob) / 2) - ((ia + ib) / 2)).dot(nr))
        P3 = lambda p, z: (p.x, p.y, z)
        C.face((P3(oa, z0), P3(ob, z0), P3(ob, z1), P3(oa, z1)), 0, wdir(nr.x, nr.y), tag)
        C.face((P3(oa, z1), P3(ob, z1), P3(ib, z1), P3(ia, z1)), 0, UP, tag)
        C.face((P3(ib, z0), P3(ia, z0), P3(ia, z1), P3(ib, z1)), 0, wdir(-nr.x, -nr.y), tag)
        C.face((P3(ia, z0), P3(ib, z0), P3(ob, z0), P3(oa, z0)), 0, DOWN, tag)
    if not closed:
        for (o, i_, d), sgn in ((st[0], -1), (st[-1], 1)):
            C.face(((o.x, o.y, z0), (i_.x, i_.y, z0), (i_.x, i_.y, z1), (o.x, o.y, z1)), 0,
                   wdir(sgn * d.x, sgn * d.y), tag)
    return {"path_vertices": n, "stations": m, "closed": closed, "dropped_for_offset": dropped,
            "width_m": [round(min(widths), 4), round(max(widths), 4)], "z": [z0, z1],
            "length_m": round(sum((P[(i + 1) % n] - P[i]).length for i in range(n if closed else n - 1)), 3)}


def build_copings(C, tp, lay, cfg):
    """NW coping (open, J_E -> J_W, ends embedded into the M walls) and roof coping ring on the U outline."""
    cs = cfg["coping"]
    E2, E3, E4 = tp["zones"][1]["edges"], tp["zones"][2]["edges"], tp["zones"][3]["edges"]
    info = {"section": {"overhang_m": cs["overhang_m"], "inner_m": cs["inner_m"],
                        "width_m": round(cs["overhang_m"] + cs["inner_m"], 4), "height_m": cs["height_m"],
                        "bottom_embed_m": cs["embed_m"], "end_embed_m": cs["end_embed_m"]}}

    def wall_line(e, embed):
        a, b = V2(E3[e]["a"]), V2(E3[e]["b"])
        d = (b - a).normalized()
        return a + Vector((-d.y, d.x)) * embed, d            # shifted into M (M interior = left of its edges)
    nw_pts = [E2[e]["a"] for e in range(21, 51)] + [lay["J_W"]]
    path, rem = coping_path(nw_pts, False, cs["step_max_m"], cs["simplify_m"])
    top = tp["copings"][0]["z1"]
    info["NW"] = sweep_coping(C, path, False, cs, top - cs["height_m"], top,
                              ends=(wall_line(20, cs["end_embed_m"]), wall_line(23, cs["end_embed_m"])))
    info["NW"]["steps_removed"] = rem
    u_pts = [E4[e]["a"] for e in range(36)]
    path, rem = coping_path(u_pts, True, cs["step_max_m"], cs["simplify_m"])
    top = tp["copings"][1]["z1"]
    info["roof"] = sweep_coping(C, path, True, cs, top - cs["height_m"], top)
    info["roof"]["steps_removed"] = rem
    return info


def solve_parity(tp, bcols, cfg):
    extras = {k: 0 for _, k in REGIONS if k}
    for reg, knob in REGIONS[:-1]:
        if parities(layout(tp, bcols, cfg, extras))[reg]:
            extras[knob] = 1
    lay = layout(tp, bcols, cfg, extras)
    return lay, extras, parities(lay)


# ------------------------------------------------------------------------------------------------ build
def _objects(cfg, coll, meshes):
    out = {}
    for key, M in meshes.items():
        name = cfg["names"][key]
        if name in bpy.data.objects:
            if not cfg.get("replace_existing"):
                raise ValueError(f"object {name} exists; remove it or set replace_existing")
            old = bpy.data.objects[name]
            me = old.data
            bpy.data.objects.remove(old)
            if me.users == 0:
                bpy.data.meshes.remove(me)
        out[key] = H["_to_object"](M.bm, name, coll)
    return out


def _mat(name, rgba):
    return bpy.data.materials.get(name) or H["material"](name, rgba)


def build(cfg):
    """cfg: collection, top_json, body_object, body_script (optional), names {top, coping, glass, railing},
    cap_band_protrusion {edge, offset_a_m, offset_b_m}, cap_grid_m, coping {overhang_m, inner_m, height_m, embed_m,
    end_embed_m, step_max_m}, railing_z {name: [z0, z1]}, railing_embed_m, replace_existing (default False)."""
    load_helpers(cfg.get("body_script") or
                 os.path.join(os.path.dirname(globals()["__file__"]), "build_body_blender.py"))
    tp = json.load(open(cfg["top_json"], encoding="utf-8"))
    Z1, Z2, Z3, Z4 = tp["zones"]
    coll = bpy.data.collections.get(cfg["collection"])
    if coll is None:
        coll = bpy.data.collections.new(cfg["collection"])
        bpy.context.scene.collection.children.link(coll)
    body = bpy.data.objects[cfg["body_object"]]
    z0 = tp["transition_64.7"]["typical_rings_end"]
    F = [V2(e["a"]) for e in Z1["edges"]]
    bcols = body_columns(body, F, z0)
    lay, extras, par = solve_parity(tp, bcols, cfg)

    T, C, G, R = TopMesh("top"), TopMesh("coping"), TopMesh("glass"), TopMesh("railing")
    for c in bcols:
        T.seed((c[2][0], c[2][1], z0), c[3])
    rv = Z2["patterns"]["M_recessed"][0]
    reveal, ov = rv["reveal_m"], rv["plane_overlap_m"]
    info = {"body_top_loop_vertices": len(bcols), "parity_extras": extras, "parity_final": par, "regions": []}

    # Z1 band 64.7-65.4 on the body columns
    z1rows = Z1["rows"]
    build_walls(T, G, lay["z1"], z1rows, zone_kinds(Z1, lay["z1"], z1rows), reveal)
    # Z2 storey 65.4-69.45
    K2 = zone_kinds(Z2, lay["z2"], Z2["rows"])
    build_walls(T, G, lay["z2"], Z2["rows"], K2, reveal)
    info["opening_planes"] = opening_planes(G, lay["z2"], Z2["rows"], K2, reveal, ov)
    # Z3 walls 69.45-71.5; band 71.5-72.2 on its own outline
    z3, band = lay["z3"], lay["band"]
    za3, zb, zt = Z3["rows"]
    rows3 = [za3, zb]
    pe = cfg["cap_band_protrusion"]["edge"]
    i_corner = next(k for k, c in enumerate(z3) if c[2] == pe + 1)            # first column of the next edge
    K3 = zone_kinds(Z3, z3, rows3, {(i_corner, 0)})
    build_walls(T, G, z3, rows3, K3, reveal)
    nz3 = len(z3)
    j = (i_corner + 1) % nz3
    a, b, cpt = z3[i_corner], z3[j], band[i_corner]
    d = (V2(b) - V2(a)).normalized()
    out = wdir(d.y, -d.x)
    T.face(((a[0], a[1], za3), (b[0], b[1], za3), (b[0], b[1], zb), (cpt[0], cpt[1], zb)), FAC, out, "wall")
    T.face(((a[0], a[1], za3), (cpt[0], cpt[1], zb), (a[0], a[1], zb)), FAC, out, "wall")
    Kb = zone_kinds(Z3, z3, [zb, zt])
    build_walls(T, G, band, [zb, zt], Kb, reveal)
    for k in range(nz3):                                                       # soffit under the protrusion
        m = (k + 1) % nz3
        if z3[k][2] == pe and (V2(band[k]) - V2(z3[k])).length + (V2(band[m]) - V2(z3[m])).length > 1e-9:
            T.face(((z3[k][0], z3[k][1], zb), (z3[m][0], z3[m][1], zb), (band[m][0], band[m][1], zb),
                    (band[k][0], band[k][1], zb)), FAC, DOWN, "soffit")
    # Z4 upper volume 72.2-76.25
    u = lay["u"]
    build_walls(T, G, u, Z4["rows"], zone_kinds(Z4, u, Z4["rows"]), reveal)

    # caps (the copings sit on them as a separate object)
    reg = info["regions"]
    reg.append(fill_strip(T, *lay["strip_cap65"], tp["caps"][0]["z"], FAC, UP, "cap", name="cap_65.4_NW_band_top"))
    reg.append(fill_region(T, [lay["loop_terrace"]], za3, FAC, UP, "cap", grid=cfg["cap_grid_m"],
                           name="terrace_69.45"))
    reg.append(fill_strip(T, *lay["strip_ledge"], zt, FAC, UP, "cap", name="ledge_72.2"))
    zr = Z4["rows"][-1]
    reg.append(fill_region(T, lay["loops_roof"], zr, FAC, UP, "cap", grid=cfg["cap_grid_m"], name="roof_76.25"))
    for bx in lay["boxes"]:
        side_walls(T, bx["O"], bx["z0"], bx["z1"], FAC, "box", closed=True, outward=True)
        side_walls(T, bx["I"], bx["zr"], bx["z1"], FAC, "box", closed=True, outward=False)
        ladder(T, bx["O"], bx["I"], bx["z1"], bx["z1"], FAC, UP, "box", closed=True)
        reg.append(fill_region(T, [bx["I"]], bx["zr"], FAC, UP, "box", name=bx["name"] + "_roof"))
    info["copings"] = build_copings(C, tp, lay, cfg)

    # railings: one glass plane per (split) polyline segment
    rails = []
    E3 = Z3["edges"]
    for rl in tp["railings"]:
        za, zb2 = cfg["railing_z"][rl["name"]]
        pts = [tuple(p) for p in rl["polyline"]]
        if rl["closed"]:
            pts = ring_splits(ccw(pts))
            pts.append(pts[0])
        else:
            if (V2(pts[0]) - V2(lay["J_E"])).length > (V2(pts[-1]) - V2(lay["J_E"])).length:
                pts = pts[::-1]
            pts = clip_to_wall(pts, E3[20]["a"], E3[20]["b"], cfg["railing_embed_m"])
            pts = clip_to_wall(pts[::-1], E3[23]["a"], E3[23]["b"], cfg["railing_embed_m"])[::-1]
            seg = []
            for k in range(len(pts) - 1):
                seg += with_splits([pts[k], pts[k + 1]])[:-1]
            pts = seg + [pts[-1]]
        side_walls(R, pts, za, zb2, 0, "railing", closed=False, outward=True)
        rails.append({"name": rl["name"], "z": [za, zb2], "vertices": len(pts), "length_m": round(sum(
            (V2(b) - V2(a)).length for a, b in zip(pts[:-1], pts[1:])), 3)})
    info["railings"] = rails

    objs = _objects(cfg, coll, {"top": T, "coping": C, "glass": G, "railing": R})
    top, cop, glass, rail = objs["top"], objs["coping"], objs["glass"], objs["railing"]
    for nm, rgba in (("TOW02_facade", (0.12, 0.12, 0.12, 1)), ("TOW02_reveal", (0.35, 0.35, 0.35, 1)),
                     ("TOW02_band199", (0.3, 0.25, 0.4, 1))):
        top.data.materials.append(_mat(nm, rgba))
    cop.data.materials.append(_mat("TOW02_coping", (0.55, 0.2, 0.15, 1)))
    gm = _mat("TOW02_glass", (0.25, 0.5, 0.9, 1))
    glass.data.materials.append(gm)
    rail.data.materials.append(gm)
    info.update(top_faces=len(top.data.polygons), coping_faces=len(cop.data.polygons),
                glass_faces=len(glass.data.polygons), railing_faces=len(rail.data.polygons), part_counts=T.counts,
                glass_part_counts=G.counts, triangles=T.tris + C.tris + G.tris + R.tris, skipped=T.b.skipped,
                degenerate=T.degenerate + C.degenerate,
                columns={k: len(lay[k]) for k in ("z1", "z2", "z3", "band", "u", "chain")},
                junctions={k: [round(c, 4) for c in lay[k]] for k in ("J_E", "J_W", "band_corner")},
                interval_vs_columns=_interval_check(tp, lay))
    return info


def _interval_check(tp, lay):
    """Largest distance from an interval breakpoint of the M-part edges (Z2 0..20) to the nearest column there."""
    worst = (0.0, None)
    for zone, cols in ((tp["zones"][1], lay["z2"]), (tp["zones"][2], lay["z3"])):
        for e in range(21):
            E = zone["edges"][e]
            A, B = V2(E["a"]), V2(E["b"])
            d = (B - A).normalized()
            ts = [(V2(c) - A).dot(d) for c in cols if c[2] == e] + [E["length"]]
            for iv in E["intervals"]:
                for t in (iv["t0"], iv["t1"]):
                    dist = min(abs(t - q) for q in ts)
                    if dist > worst[0]:
                        worst = (dist, (zone["name"], e, t))
    return {"max_m": round(worst[0], 4), "where": worst[1]}
