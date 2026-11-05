"""new-case: AGR Tools 0.8 (#908) geom logic, stdlib only. Owned by branch A (improve/issue-908-geom).

Pure logic for `model_triangulate` (model.triangulate), `ucx_triangulate` (ucx.triangulate),
`export_pivot_place` (export.pivot_place); no pymxs. Reports, preview hashes and paths come from edit_core.py.

Lab findings fixed here (docs/experiments/<id>.md, no GeoAGR code, #853):

* model.triangulate. Thresholds are scale-relative: every polygon is projected on its own plane and normalised
  to a unit box before any orientation test, so a 0.1 mm octagon in a metre scene triangulates exactly like a
  1 km one. A polygon of n corners gets exactly n-3 non-crossing diagonals (ear clipping on the polygon chain,
  then Lawson flips inside strictly convex quads for a constrained Delaunay result without long slivers).
  `assert_triangulated` is the zero-n-gon assertion on the read-back degrees.
* ucx.triangulate. A planar polygon of a convex piece can take any triangulation; a non-planar one takes the
  triangulation whose triangles all support the piece (every vertex behind every plane, tolerance 1e-4 m).
  When no such triangulation exists the piece is not convex at all and the plan falls back to its convex hull
  (ucx_core._convex_hull); `ucx_core.convexity` is the post-check.
* export.pivot_place. Floor height is the min z of the selected floor faces/vertices or an explicit ±0.000
  (validated text, never an empty field read as 0, never the bbox bottom). Coordinates are doubles and every
  text form uses fixed decimals. Rotation is reported as the Max UI shows it (controller sign, Euler XYZ).

#979 rework (branch E2, improve/issue-979-rework-geom-udim): ucx.triangulate turns reflex diagonals
(`flip_concave`, ConcaveFixer idea with the T03 defects fixed); export.pivot_place orients the pivot
(`axes_long_side`, `axes_pca`, `new_offset`; L07/T06/T08/T03 defects fixed). See the sections below.
"""
import math
import re

TOOLS = {'model.triangulate': 'model_triangulate', 'ucx.triangulate': 'ucx_triangulate',
         'export.pivot_place': 'export_pivot_place'}
EPS = 1e-12            # orientation tests run on polygons normalised to a unit box: scale-free
INCIRCLE_EPS = 1e-12   # a flip needs a strict Delaunay violation (cocircular quads keep their diagonal)
PLANAR_REL = 1e-6      # out-of-plane distance / polygon extent below which a polygon is planar
CONVEX_TOL_M = 1e-4    # reg 2.13.1 post-check: every vertex behind every face plane within 0.1 mm
EXACT_MAX_CORNERS = 9  # non-planar UCX polygons up to this size are searched exhaustively (Catalan(7) = 429)
DECIMALS = 4           # fixed decimals of every coordinate text (0.1 mm in metres)
TARGETS = ('npm', 'vpm', 'both')
PIVOT_OPTIONS = {'target', 'floor_z', 'vpm_rotate_z', 'orient', 'pivot_at'}
UCX_OPTIONS = {'nonconvex'}
_NUMBER = re.compile(r'^[+-]?(\d+([.,]\d*)?|[.,]\d+)$')


# ---- small vector helpers -----------------------------------------------------------------------------
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _length(a):
    return math.sqrt(_dot(a, a))


def _finite_points(points, label='polygon'):
    out = []
    for p in points:
        if not isinstance(p, (list, tuple)) or len(p) != 3:
            raise ValueError('partial vertex in ' + label)
        q = []
        for c in p:
            if isinstance(c, bool) or not isinstance(c, (int, float)) or not math.isfinite(float(c)):
                raise ValueError('non-finite vertex in ' + label)
            q.append(float(c))
        out.append(tuple(q))
    return out


def newell_normal(points):
    """Area-weighted normal of a (possibly non-planar) polygon; its length is twice the projected area."""
    nx = ny = nz = 0.0
    n = len(points)
    cx = sum(p[0] for p in points) / n
    cy = sum(p[1] for p in points) / n
    cz = sum(p[2] for p in points) / n
    for i in range(n):
        x0, y0, z0 = points[i][0] - cx, points[i][1] - cy, points[i][2] - cz
        x1, y1, z1 = points[(i + 1) % n][0] - cx, points[(i + 1) % n][1] - cy, points[(i + 1) % n][2] - cz
        nx += (y0 - y1) * (z0 + z1)
        ny += (z0 - z1) * (x0 + x1)
        nz += (x0 - x1) * (y0 + y1)
    return (nx, ny, nz)


def extent(points):
    return max(max(p[a] for p in points) - min(p[a] for p in points) for a in range(3))


def project(points):
    """Polygon on its own plane, centred and scaled to a unit box: [(u, v)], normal, planarity ratio.

    The scale is the polygon's own extent, so every later threshold is relative (lab defect 1: absolute 1e-6
    thresholds left sub-millimetre faces as n-gons)."""
    pts = _finite_points(points)
    size = extent(pts)
    if size <= 0.0:
        return None, None, 0.0
    c = tuple(sum(p[a] for p in pts) / len(pts) for a in range(3))
    local = [tuple((p[a] - c[a]) / size for a in range(3)) for p in pts]
    nrm = newell_normal(local)
    ln = _length(nrm)
    if ln <= EPS:
        return None, None, 0.0
    nrm = (nrm[0] / ln, nrm[1] / ln, nrm[2] / ln)
    axis = min(range(3), key=lambda i: abs(nrm[i]))
    tmp = [0.0, 0.0, 0.0]
    tmp[axis] = 1.0
    u = _cross(nrm, tuple(tmp))
    u = tuple(x / _length(u) for x in u)
    v = _cross(nrm, u)
    flat = [(_dot(p, u), _dot(p, v)) for p in local]
    offplane = max(abs(_dot(p, nrm)) for p in local)
    return flat, nrm, offplane


def _orient2(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _in_triangle(p, a, b, c):
    """Inside or on the boundary of CCW triangle abc (scale-free coordinates)."""
    return _orient2(a, b, p) >= -EPS and _orient2(b, c, p) >= -EPS and _orient2(c, a, p) >= -EPS


def _quality(a, b, c):
    """Smallest angle (radians) of a 2D triangle; 0 for degenerate ones."""
    def ang(p, q, r):
        v1 = (q[0] - p[0], q[1] - p[1])
        v2 = (r[0] - p[0], r[1] - p[1])
        l1, l2 = math.hypot(*v1), math.hypot(*v2)
        if l1 <= EPS or l2 <= EPS:
            return 0.0
        cosv = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (l1 * l2)))
        return math.acos(cosv)
    return min(ang(a, b, c), ang(b, c, a), ang(c, a, b))


def _incircle(a, b, c, d):
    """> 0 when d lies strictly inside the circumcircle of CCW triangle abc."""
    adx, ady = a[0] - d[0], a[1] - d[1]
    bdx, bdy = b[0] - d[0], b[1] - d[1]
    cdx, cdy = c[0] - d[0], c[1] - d[1]
    return ((adx * adx + ady * ady) * (bdx * cdy - cdx * bdy)
            - (bdx * bdx + bdy * bdy) * (adx * cdy - cdx * ady)
            + (cdx * cdx + cdy * cdy) * (adx * bdy - bdx * ady))


# ---- polygon triangulation (model.triangulate) --------------------------------------------------------
def _ear_clip(flat):
    """Triangles (local indices, CCW in `flat`) and a degenerate flag. Always n-2 triangles."""
    n = len(flat)
    if n < 3:
        raise ValueError('polygon with fewer than 3 corners')
    ring = list(range(n))
    area = sum(_orient2((0.0, 0.0), flat[i], flat[(i + 1) % n]) for i in range(n))
    if area < 0:
        ring.reverse()
    tris = []
    degenerate = False
    while len(ring) > 3:
        m = len(ring)
        best = None
        for k in range(m):
            ia, ib, ic = ring[k - 1], ring[k], ring[(k + 1) % m]
            a, b, c = flat[ia], flat[ib], flat[ic]
            if _orient2(a, b, c) <= EPS:
                continue
            blocked = False
            for j in ring:
                if j in (ia, ib, ic):
                    continue
                p = flat[j]
                if p in (a, b, c):
                    continue  # a coincident duplicate corner never blocks
                if _in_triangle(p, a, b, c):
                    blocked = True
                    break
            if blocked:
                continue
            q = _quality(a, b, c)
            if best is None or q > best[0]:
                best = (q, k)
        if best is None:
            # No strict ear: collinear/duplicate or self-intersecting outline. Still cut the most convex corner,
            # so the face is fully triangulated (n-3 diagonals); the caller reports it as degenerate.
            degenerate = True
            k = max(range(m), key=lambda k: _orient2(flat[ring[k - 1]], flat[ring[k]], flat[ring[(k + 1) % m]]))
        else:
            k = best[1]
        tris.append((ring[k - 1], ring[k], ring[(k + 1) % m]))
        del ring[k]
    tris.append(tuple(ring))
    if _orient2(*(flat[i] for i in ring)) <= EPS:
        degenerate = True
    return tris, degenerate


def _diagonals(tris, n):
    edges = set()
    for t in tris:
        for e in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            a, b = min(e), max(e)
            if (b - a) % n not in (1, n - 1):
                edges.add((a, b))
    return edges


def _flip(tris, flat, n):
    """Lawson flips inside strictly convex quads: a constrained Delaunay triangulation of the outline."""
    tris = [tuple(t) for t in tris]
    for _ in range(4 * n * n + 10):
        changed = False
        owner = {}
        for ti, t in enumerate(tris):
            for e in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                owner[e] = (ti, 3 - t.index(e[0]) - t.index(e[1]))
        for (a, b), (ti, oi) in list(owner.items()):
            if (b, a) not in owner or a > b:
                continue
            tj, oj = owner[(b, a)]
            c = tris[ti][oi]
            d = tris[tj][oj]
            pa, pb, pc, pd = flat[a], flat[b], flat[c], flat[d]
            # quad a-d-b-c must be strictly convex for the new diagonal c-d to stay inside the outline
            if not (_orient2(pa, pd, pc) > EPS and _orient2(pd, pb, pc) > EPS):
                continue
            if _incircle(pa, pb, pc, pd) <= INCIRCLE_EPS:
                continue
            new1, new2 = (c, a, d), (d, b, c)
            if min(_quality(*(flat[i] for i in new1)), _quality(*(flat[i] for i in new2))) <= \
                    min(_quality(*(flat[i] for i in tris[ti])), _quality(*(flat[i] for i in tris[tj]))):
                continue  # only flips that improve the smallest angle: terminates, never slivers
            tris[ti], tris[tj] = new1, new2
            changed = True
            break
        if not changed:
            return tris
    return tris


def triangulate_polygon(points):
    """{'diagonals': [(i, j)], 'triangles': [(i, j, k)], 'degenerate': bool, 'planar': bool} for one polygon.

    i, j index the polygon's own corner list. Exactly n-3 diagonals, none an outline edge, none crossing;
    the same result for the same shape at any scale or position."""
    pts = _finite_points(points)
    n = len(pts)
    if n < 3:
        raise ValueError('polygon with fewer than 3 corners')
    if n == 3:
        return {'diagonals': [], 'triangles': [(0, 1, 2)], 'degenerate': False, 'planar': True}
    flat, nrm, offplane = project(pts)
    if flat is None:  # zero extent or all corners on a line: a fan keeps the face count right; reported
        tris = [(0, i, i + 1) for i in range(1, n - 1)]
        return {'diagonals': sorted(_diagonals(tris, n)), 'triangles': tris, 'degenerate': True, 'planar': True}
    tris, degenerate = _ear_clip(flat)
    if not degenerate:
        tris = _flip(tris, flat, n)
    diags = sorted(_diagonals(tris, n))
    if len(diags) != n - 3 or len(tris) != n - 2:
        raise AssertionError('triangulation lost a diagonal: {} for {} corners'.format(len(diags), n))
    return {'diagonals': diags, 'triangles': tris, 'degenerate': degenerate, 'planar': offplane <= PLANAR_REL}


def diagonals_cross(points, diagonals):
    """True when two diagonals of the projected polygon properly cross (test helper, scale-free)."""
    flat, _, _ = project(points)
    if flat is None:
        return False

    def proper(p1, p2, q1, q2):
        d1, d2 = _orient2(q1, q2, p1), _orient2(q1, q2, p2)
        d3, d4 = _orient2(p1, p2, q1), _orient2(p1, p2, q2)
        return ((d1 > EPS and d2 < -EPS) or (d1 < -EPS and d2 > EPS)) and \
               ((d3 > EPS and d4 < -EPS) or (d3 < -EPS and d4 > EPS))
    ds = list(diagonals)
    for x in range(len(ds)):
        for y in range(x + 1, len(ds)):
            a, b = ds[x]
            c, d = ds[y]
            if len({a, b, c, d}) < 4:
                continue
            if proper(flat[a], flat[b], flat[c], flat[d]):
                return True
    return False


def plan_faces(faces):
    """faces: [{'face': int, 'verts': [vertex ids], 'points': [(x, y, z)]}] -> plan rows and leftovers.

    Rows carry vertex-id pairs for Max (polyop.createEdge) and the expected triangle count of the face."""
    rows, degenerate = [], []
    for f in faces:
        verts = [int(v) for v in f['verts']]
        if len(verts) != len(f['points']) or len(set(verts)) != len(verts):
            raise ValueError('face {} has repeated or unmatched vertices'.format(f['face']))
        if len(verts) <= 3:
            continue
        t = triangulate_polygon(f['points'])
        pairs = [[verts[i], verts[j]] for i, j in t['diagonals']]
        rows.append({'face': int(f['face']), 'corners': len(verts), 'pairs': pairs})
        if t['degenerate']:
            degenerate.append(int(f['face']))
    return rows, degenerate


def assert_triangulated(degrees):
    """Zero-n-gon assertion on read-back face degrees: returns the 1-based ids of faces with degree > 3."""
    left = [i + 1 for i, d in enumerate(degrees) if int(d) > 3]
    return left


# ---- UCX convex triangulation (ucx.triangulate) -------------------------------------------------------
def _signed_volume(points, tris):
    total = 0.0
    o = points[0]
    for a, b, c in tris:
        pa, pb, pc = _sub(points[a], o), _sub(points[b], o), _sub(points[c], o)
        total += _dot(pa, _cross(pb, pc))
    return total / 6.0


def _supports(points, tri, tol, sign):
    """Every vertex of the piece behind the plane of `tri` (outward per `sign`) within `tol`."""
    a, b, c = (points[i] for i in tri)
    nrm = _cross(_sub(b, a), _sub(c, a))
    ln = _length(nrm)
    if ln <= 0.0:
        return False
    nrm = tuple(sign * x / ln for x in nrm)
    return all(_dot(nrm, _sub(p, a)) <= tol for p in points)


def _all_triangulations(n):
    """Every triangulation of a convex n-gon (index chain 0..n-1) as triangle lists (n small)."""
    memo = {}

    def rec(i, j):
        if j - i < 2:
            return [[]]
        key = (i, j)
        if key in memo:
            return memo[key]
        out = []
        for k in range(i + 1, j):
            for left in rec(i, k):
                for right in rec(k, j):
                    out.append(left + [(i, k, j)] + right)
        memo[key] = out
        return out
    return rec(0, n - 1)


def ucx_polygon(points, verts, poly_points, tol, sign):
    """Triangles (vertex ids) for one UCX polygon whose triangles all support the piece, or None.

    points: every vertex of the piece (object space); verts: the polygon's vertex ids into `points`."""
    n = len(verts)
    if n == 3:
        tri = tuple(verts)
        return [tri] if _supports(points, tri, tol, sign) else None
    t = triangulate_polygon(poly_points)
    first = [tuple(verts[i] for i in tri) for tri in t['triangles']]
    if not t['degenerate'] and all(_supports(points, tri, tol, sign) for tri in first):
        return first
    if n > EXACT_MAX_CORNERS:
        return None
    for cand in _all_triangulations(n):
        tris = [tuple(verts[i] for i in tri) for tri in cand]
        if all(_supports(points, tri, tol, sign) for tri in tris):
            return tris
    return None


MAX_BEND_DEG = 60.0  # a reflex edge between triangles bent more than this is a corner of the piece, not a diagonal


def _unit(v):
    ln = _length(v)
    return None if ln <= 0.0 else (v[0] / ln, v[1] / ln, v[2] / ln)


def _tri_normal(points, tri, sign):
    a, b, c = (points[i] for i in tri)
    n = _cross(_sub(b, a), _sub(c, a))
    return (sign * n[0], sign * n[1], sign * n[2])


def _edges_of(tris):
    """{directed edge (a, b): triangle index} of a triangle list."""
    out = {}
    for ti, (a, b, c) in enumerate(tris):
        for e in ((a, b), (b, c), (c, a)):
            out[e] = ti
    return out


def _reflex_depth(points, tri, d, sign):
    """Signed distance of vertex d in front of the outward plane of `tri` (> 0: the shared edge is reflex)."""
    n = _unit(_tri_normal(points, tri, sign))
    if n is None:
        return 0.0
    return _dot(n, _sub(points[d], points[tri[0]]))


def concave_edges(points, tris, tol, sign=1.0):
    """[(depth, a, b, ti, tj, c, d)] of the interior edges whose dihedral is reflex by more than `tol`.

    Edge a-b of triangle ti = (a, b, c) and tj = (b, a, d). `tol` is the 1e-4 m convexity tolerance in object
    units, so a 1e-6 fold is never called concave (T03 ConcaveFixer flagged 1e-6 noise). Deepest first."""
    edges = _edges_of(tris)
    out = []
    for (a, b), ti in edges.items():
        if a > b or (b, a) not in edges:
            continue
        tj = edges[(b, a)]
        t1, t2 = tris[ti], tris[tj]
        c = t1[3 - t1.index(a) - t1.index(b)]
        d = t2[3 - t2.index(a) - t2.index(b)]
        depth = max(_reflex_depth(points, t1, d, sign), _reflex_depth(points, t2, c, sign))
        if depth > tol:
            out.append((depth, a, b, ti, tj, c, d))
    out.sort(key=lambda r: (-r[0], r[1], r[2]))
    return out


def _flip_check(points, tris, row, tol, sign, edge_set):
    """'' when edge a-b can be turned into c-d, else the reason it is refused.

    Conditions (T03/ConcaveFixer card): the quad a-d-b-c is strictly convex in its own plan (a «dart» is not:
    turning it folds a triangle face-down), the new edge does not exist yet, both new triangles keep the outward
    side of the old pair, and the new edge itself is not reflex."""
    _, a, b, ti, tj, c, d = row
    if (min(c, d), max(c, d)) in edge_set:
        return 'edge_exists'
    n1 = _unit(_tri_normal(points, tris[ti], sign))
    n2 = _unit(_tri_normal(points, tris[tj], sign))
    if n1 is None or n2 is None:
        return 'degenerate'
    if _dot(n1, n2) < math.cos(math.radians(MAX_BEND_DEG)):
        return 'sharp'
    nrm = _unit((n1[0] + n2[0], n1[1] + n2[1], n1[2] + n2[2]))
    if nrm is None:
        return 'folded'
    axis = min(range(3), key=lambda i: abs(nrm[i]))
    tmp = [0.0, 0.0, 0.0]
    tmp[axis] = 1.0
    u = _unit(_cross(nrm, tuple(tmp)))
    v = _cross(nrm, u)
    o = points[a]
    span = max(_length(_sub(points[i], o)) for i in (b, c, d)) or 1.0
    flat = {i: (_dot(_sub(points[i], o), u) / span, _dot(_sub(points[i], o), v) / span) for i in (a, b, c, d)}
    pa, pb, pc, pd = flat[a], flat[b], flat[c], flat[d]
    eps = 1e-9
    # proper crossing of a-b and c-d in plan <=> strictly convex quad
    d1, d2 = _orient2(pc, pd, pa), _orient2(pc, pd, pb)
    d3, d4 = _orient2(pa, pb, pc), _orient2(pa, pb, pd)
    if not (((d1 > eps and d2 < -eps) or (d1 < -eps and d2 > eps)) and
            ((d3 > eps and d4 < -eps) or (d3 < -eps and d4 > eps))):
        return 'dart'
    new1, new2 = (c, a, d), (d, b, c)
    for t in (new1, new2):
        nt = _unit(_tri_normal(points, t, sign))
        if nt is None or _dot(nt, nrm) <= 0.0:
            return 'folded'
    if max(_reflex_depth(points, new1, b, sign), _reflex_depth(points, new2, a, sign)) > tol:
        return 'still_concave'
    return ''


def flip_concave(points, tris, tol, sign=1.0, locked=()):
    """Turn reflex diagonals until a fixed point. Returns (tris, flips, refused).

    flips: [[a, b, c, d]] (edge a-b became c-d); refused: [{'edge': [a, b], 'reason', 'depth'}] for every reflex
    edge left at the fixed point. `locked`: undirected edges that are outlines of the source polygons (a real
    crease of the piece, never turned). Vertex count and the triangle count never change."""
    tris = [tuple(int(i) for i in t) for t in tris]
    locked = {(min(e), max(e)) for e in locked}
    flips = []
    blocked = set()

    def check(row, edge_set):
        if (row[1], row[2]) in locked:
            return 'crease'
        return _flip_check(points, tris, row, tol, sign, edge_set)
    for _ in range(4 * len(tris) + 10):
        rows = concave_edges(points, tris, tol, sign)
        edge_set = {(min(e), max(e)) for e in _edges_of(tris)}
        done = False
        for row in rows:
            key = (row[1], row[2])
            if key in blocked:
                continue
            why = check(row, edge_set)
            if why:
                blocked.add(key)
                continue
            _, a, b, ti, tj, c, d = row
            tris[ti], tris[tj] = (c, a, d), (d, b, c)
            flips.append([a, b, c, d])
            blocked = set()  # a turn changes the neighbours: re-judge every edge
            done = True
            break
        if not done:
            break
    refused = []
    edge_set = {(min(e), max(e)) for e in _edges_of(tris)}
    for row in concave_edges(points, tris, tol, sign):
        refused.append({'edge': [row[1], row[2]], 'depth': row[0], 'reason': check(row, edge_set) or 'cycle'})
    return tris, flips, refused


NONCONVEX = ('report', 'hull')
REFUSE_TEXT = {'sharp': 'the triangles meet at more than {}°: a real corner of the piece, not a diagonal'.format(
                   MAX_BEND_DEG),
               'crease': 'an outline edge of the source polygons: a real crease of the piece, not a diagonal',
               'dart': 'the quad around the edge is not convex in plan («dart»): turning it would fold a triangle',
               'edge_exists': 'the turned edge already exists in the piece',
               'still_concave': 'the turned edge would be reflex as well',
               'folded': 'a turned triangle would face inward', 'degenerate': 'zero-area triangle at the edge',
               'cycle': 'no turn removes it'}


def ucx_plan(points, polygons, tol, nonconvex='report'):
    """Plan for one UCX piece: {'action': 'none'|'diagonals'|'mesh'|'hull', 'pairs', 'tris', 'flips',
    'refused', 'hull', 'reason'}.

    points: object-space vertices; polygons: vertex-id lists (0-based) in Max winding (outward CCW).
    1. every n-gon takes a triangulation whose triangles support the piece (or its ear-clip triangulation);
    2. a flip pass turns reflex diagonals inside convex-in-plan quads until a fixed point (T03 ConcaveFixer idea,
       with its defects fixed: no dart flip, new edge checked, 1e-4 m epsilon, post-check);
    3. 'diagonals': only n-gons were split (polyop.createEdge keeps UVs/IDs); 'mesh': flips happened, the copy
       gets the whole triangle list (vertex count unchanged); 'none': nothing to do.
    A piece that is still not convex is reported (`refused`, reason) and left as triangulated; nonconvex='hull'
    rebuilds it as its convex hull instead (the 0.8 behaviour)."""
    if nonconvex not in NONCONVEX:
        raise ValueError('nonconvex must be report or hull')
    pts = _finite_points(points, 'UCX piece')
    fan = [(p[0], p[i], p[i + 1]) for p in polygons for i in range(1, len(p) - 1)]
    if not fan:
        raise ValueError('UCX piece without faces')
    vol = _signed_volume(pts, fan)
    sign = 1.0 if vol >= 0 else -1.0
    pairs, tris, ngons = [], [], 0
    for poly in polygons:
        poly = [int(v) for v in poly]
        got = ucx_polygon(pts, poly, [pts[v] for v in poly], tol, sign)
        if got is None:
            if len(poly) == 3:
                got = [tuple(poly)]
            else:
                t = triangulate_polygon([pts[v] for v in poly])
                got = [tuple(poly[i] for i in tri) for tri in t['triangles']]
        tris.extend(got)
        if len(poly) > 3:
            ngons += 1
            n = len(poly)
            for tri in got:
                for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                    ia, ib = poly.index(a), poly.index(b)
                    if (ib - ia) % n not in (1, n - 1):
                        pr = sorted((a, b))
                        if pr not in pairs:
                            pairs.append(pr)
    locked = set()  # outline edges of source n-gons are real creases; edges between source triangles may be
    for poly in polygons:  # the diagonals of an earlier triangulation and stay candidates (ConcaveFixer input)
        if len(poly) > 3:
            for i in range(len(poly)):
                a, b = int(poly[i]), int(poly[(i + 1) % len(poly)])
                locked.add((min(a, b), max(a, b)))
    tris, flips, refused = flip_concave(pts, tris, tol, sign, locked)
    convex = not refused and _ucx_core().convexity(pts, tris, tol)['convex']
    out = {'pairs': pairs, 'tris': [list(t) for t in tris], 'flips': flips, 'refused': refused, 'hull': None,
           'convex': convex}
    if not convex and nonconvex == 'hull':
        ucx = _ucx_core()
        hverts, htris = ucx._convex_hull(pts)
        out.update(action='hull', pairs=[], tris=[], flips=[],
                   hull={'verts': [list(v) for v in hverts], 'tris': [list(t) for t in htris]},
                   reason='not convex after {} turn(s); rebuilt as its convex hull (nonconvex=hull)'.format(len(flips)))
        return out
    if flips:
        out.update(action='mesh', reason='{} reflex diagonal(s) turned'.format(len(flips)))
    elif ngons:
        out.update(action='diagonals', reason='')
    else:
        out.update(action='none', reason='already triangles')
    if not convex:
        why = sorted({r['reason'] for r in refused}) or ['no supporting triangulation']
        out['reason'] = (out['reason'] + '; ' if out['reason'] else '') + \
            'still not convex: {}; the piece is left triangulated, rebuild it (ucx.build) or split it'.format(
                ', '.join(REFUSE_TEXT.get(w, w) for w in why))
    return out


def _ucx_core():
    import importlib.util
    import os
    import sys
    name = 'agr_tools_ucx_core'
    if name in sys.modules:
        return sys.modules[name]
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ucx_core.py')
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---- pivot and position (export.pivot_place) ----------------------------------------------------------
def fmt(x, decimals=DECIMALS):
    """Fixed decimals, never exponent notation (lab: '2.34568e+06' and 2.35 m lost at 1e6)."""
    x = float(x)
    if not math.isfinite(x):
        raise ValueError('non-finite coordinate')
    s = '{:.{}f}'.format(x, decimals)
    if float(s) == 0.0:
        s = s.lstrip('-')
    return s


def fmt_point(p, decimals=DECIMALS):
    return [fmt(c, decimals) for c in p]


def parse_level(text):
    """±0.000 as typed: a plain decimal (dot or comma). Empty, exponent, inf/nan and words are refused."""
    if isinstance(text, bool):
        raise ValueError('±0.000 must be a number, got ' + repr(text))
    if isinstance(text, (int, float)):
        value = float(text)
    else:
        if not isinstance(text, str):
            raise ValueError('±0.000 must be a number, got ' + repr(text))
        s = text.strip().replace('−', '-')
        if not s:
            raise ValueError('±0.000 is empty: type the floor height, an empty field is not 0')
        if not _NUMBER.match(s):
            raise ValueError('±0.000 is not a plain decimal number: ' + repr(text))
        value = float(s.replace(',', '.'))
    if not math.isfinite(value):
        raise ValueError('±0.000 is not finite')
    return value


def check_options(options):
    """Validated pivot options: target npm|vpm|both (default both), floor_z (optional), vpm_rotate_z (deg)."""
    options = dict(options or {})
    unknown = set(options) - PIVOT_OPTIONS
    if unknown:
        raise ValueError('unknown pivot options: ' + ', '.join(sorted(unknown)))
    target = options.get('target', 'both')
    if target not in TARGETS:
        raise ValueError('target must be one of ' + '/'.join(TARGETS))
    out = {'target': target}
    if options.get('floor_z') is not None:
        out['floor_z'] = parse_level(options['floor_z'])
    rot = options.get('vpm_rotate_z', 0.0)
    if isinstance(rot, bool) or not isinstance(rot, (int, float, str)):
        raise ValueError('vpm_rotate_z must be degrees')
    out['vpm_rotate_z'] = parse_level(rot) if isinstance(rot, str) else float(rot)
    if not math.isfinite(out['vpm_rotate_z']) or abs(out['vpm_rotate_z']) > 360.0:
        raise ValueError('vpm_rotate_z must be within ±360 degrees')
    orient = options.get('orient', 'keep')
    if orient not in ORIENTS:
        raise ValueError('orient must be one of ' + '/'.join(ORIENTS))
    at = options.get('pivot_at', 'floor')
    if at not in PIVOT_AT:
        raise ValueError('pivot_at must be one of ' + '/'.join(PIVOT_AT))
    if at != 'floor' and 'floor_z' in out:
        raise ValueError('floor_z belongs to pivot_at=floor')
    if orient != 'keep' or at != 'floor':  # 0.8 defaults stay out of the report shape
        out['orient'], out['pivot_at'] = orient, at
    return out


def floor_level(selected_z, explicit=None):
    """(z, source). Explicit ±0.000 wins; else the min z of the selected floor faces/vertices; else refuse.

    Never the bbox bottom (lab: 0.6 m below the clean floor over a slab) and never a face centre (lab: sloped
    face, vertex-neighbour faces 149.7 / 154.2 instead of 150.0)."""
    if explicit is not None:
        return parse_level(explicit), 'explicit'
    zs = [float(z) for z in selected_z]
    if zs:
        if not all(math.isfinite(z) for z in zs):
            raise ValueError('non-finite floor vertex')
        return min(zs), 'selection'
    raise ValueError('no floor selection and no ±0.000: select the floor faces or vertices (min z) '
                     'or give floor_z; the bbox bottom is never used')


def pivot_point(world_min, world_max, floor_z):
    """Common pivot of all copies: XY centre of the union world bbox, Z the clean floor (double precision)."""
    return [(float(world_min[0]) + float(world_max[0])) / 2.0, (float(world_min[1]) + float(world_max[1])) / 2.0,
            float(floor_z)]


def euler_ui(rows):
    """Euler XYZ degrees as the Max UI (rotation controller) shows them, from transform rows 1..3.

    Max is row-vector: M = Rx * Ry * Rz with Rz = [[c, s, 0], [-s, c, 0], [0, 0, 1]], so a node turned +30°
    about Z has row1 = (cos30, sin30, 0). The quaternion `node.rotation` carries the opposite sign (lab: -30)."""
    r1, r2, r3 = [tuple(float(c) for c in r) for r in rows[:3]]
    s1 = math.sqrt(_dot(r1, r1)) or 1.0
    s2 = math.sqrt(_dot(r2, r2)) or 1.0
    s3 = math.sqrt(_dot(r3, r3)) or 1.0
    m0 = tuple(c / s1 for c in r1)
    m1 = tuple(c / s2 for c in r2)
    m2 = tuple(c / s3 for c in r3)
    y = math.degrees(math.asin(max(-1.0, min(1.0, -m0[2]))))
    if abs(m0[2]) < 1.0 - 1e-12:
        z = math.degrees(math.atan2(m0[1], m0[0]))
        x = math.degrees(math.atan2(m1[2], m2[2]))
    else:  # gimbal lock: put everything in X
        z = 0.0
        x = math.degrees(math.atan2(-m2[1], m1[1]))
    return [0.0 if abs(v) < 1e-9 else v for v in (x, y, z)]


def pivot_targets(target):
    return ['npm', 'vpm'] if target == 'both' else [target]


def vpm_translate(positions, pivot):
    """VPM placement of several copies sharing one pivot: each moves by -pivot, so their offsets are kept
    (lab: GeoAGR "Combine near zero" aligned the bbox centres and lost the offset between the models)."""
    return [[float(p[i]) - float(pivot[i]) for i in range(3)] for p in positions]


# ---- pivot axes (export.pivot_place, #979 rework) -----------------------------------------------------
# Ideas, not code (#853): AC Pivot Align `rotate_pivot_tool.ms` sha256 6344571f…5e20 (X along the long side,
# Z up, dry-run, one undo), straighten_object.ms 94005fef…0221 (principal axes), align_door_pivots_to_bottom.ms
# e22ab117…1608 (pivot at the bottom of a door). Measured defects fixed here (L07, T06, T08, T03):
# * the axis was fitted on world float32 vertices: 1.43° off at 2 345 678 m without a warning -> fitted on
#   translation-free double coordinates (object vertices times the rotation part of the object transform);
# * O(n³) pair search and a 3..512 vertex limit -> convex hull + rotating calipers, O(n log n), no limit;
# * the sign of X was arbitrary (cell at 135° -> X at -45°) -> X angle in [0°, 180°), stated in the report;
# * PCA ran before the rotation and nothing was straightened; «pivot bottom» left the object by 858 units ->
#   PCA in double on centred coordinates, the frame is written, the bottom is the oriented bbox bottom;
# * the door pivot used world axes and moved the mesh by 491 / 1675 units -> the object's own frame, the mesh
#   stays (objectOffset is recomputed in double so that object-to-world is unchanged).
ORIENTS = ('keep', 'long_side', 'pca')
PIVOT_AT = ('floor', 'bottom_centre', 'centre')
ANGLE_TOL_DEG = 0.01        # L07 acceptance: axis error <= 0.01°
SQUARE_REL = 1e-3           # long and short side within 0.1 %: the long side is undefined
EIGEN_REL = 1e-3            # principal values within 0.1 %: the principal axes are undefined
SCALE_TOL = 1e-6            # unit node scale


def _f32_spacing(x):
    """Spacing of float32 numbers around |x| (3ds Max stores vertices and matrices as float32)."""
    x = abs(float(x))
    if x == 0.0:
        return 2.0 ** -149
    m, e = math.frexp(x)
    return 2.0 ** (e - 24)


def hull2d(points):
    """Convex hull (CCW, no collinear points) of 2D points, monotone chain in double precision."""
    pts = sorted({(float(p[0]), float(p[1])) for p in points})
    if len(pts) < 3:
        return pts

    def half(seq):
        out = []
        for p in seq:
            while len(out) >= 2 and _orient2(out[-2], out[-1], p) <= 0.0:
                out.pop()
            out.append(p)
        return out
    lower, upper = half(pts), half(reversed(pts))
    return lower[:-1] + upper[:-1]


def min_area_rect(points):
    """Minimum-area enclosing rectangle of 2D points: rotating calipers over the hull edges.

    Returns {'angle': degrees of the long side in [0, 180), 'long', 'short', 'centre': (x, y), 'hull': n}."""
    hull = hull2d(points)
    if len(hull) < 3:
        raise ValueError('degenerate footprint: fewer than 3 hull corners in plan')
    n = len(hull)
    best = None
    j = k = m = None
    for i in range(n):
        p, q = hull[i], hull[(i + 1) % n]
        ex, ey = q[0] - p[0], q[1] - p[1]
        ln = math.hypot(ex, ey)
        if ln <= 0.0:
            continue
        ux, uy = ex / ln, ey / ln

        def along(t):
            return t[0] * ux + t[1] * uy

        def across(t):
            return -t[0] * uy + t[1] * ux
        if j is None:
            j = max(range(n), key=lambda t: along(hull[t]))
            k = max(range(n), key=lambda t: across(hull[t]))
            m = min(range(n), key=lambda t: along(hull[t]))
        for _ in range(n):  # the calipers only move forward (CCW hull); n steps bound every pointer
            if along(hull[(j + 1) % n]) > along(hull[j]):
                j = (j + 1) % n
            else:
                break
        for _ in range(n):
            if across(hull[(k + 1) % n]) > across(hull[k]):
                k = (k + 1) % n
            else:
                break
        for _ in range(n):
            if along(hull[(m + 1) % n]) < along(hull[m]):
                m = (m + 1) % n
            else:
                break
        lo_a, hi_a = along(hull[m]), along(hull[j])
        lo_c, hi_c = across(p), across(hull[k])
        w, h = hi_a - lo_a, hi_c - lo_c
        area = w * h
        if best is None or area < best[0] * (1.0 - 1e-12):
            ca, cc = (lo_a + hi_a) / 2.0, (lo_c + hi_c) / 2.0
            centre = (ca * ux - cc * uy, ca * uy + cc * ux)
            best = (area, w, h, math.atan2(uy, ux), centre)
    _, w, h, ang, centre = best
    if h > w:
        w, h, ang = h, w, ang + math.pi / 2.0
    return {'angle': canonical_angle(math.degrees(ang)), 'long': w, 'short': h, 'centre': centre, 'hull': n}


def canonical_angle(deg):
    """Direction of an undirected axis as an angle in [0, 180) (the X sign rule, T06: 135° stays 135°)."""
    a = math.fmod(float(deg), 180.0)
    if a < 0.0:
        a += 180.0
    if a >= 180.0 - 1e-9:
        a = 0.0
    return a


def angle_uncertainty(points_obj, long_side):
    """Degrees of axis uncertainty from the float32 storage of the object vertices over the long side."""
    if long_side <= 0.0:
        return 180.0
    mag = max((abs(c) for p in points_obj for c in p), default=0.0)
    return math.degrees(math.atan2(2.0 * _f32_spacing(mag), long_side))


def mat3_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def vec_mat(v, m):
    """Row vector times 3x3 matrix (Max convention)."""
    return [v[0] * m[0][j] + v[1] * m[1][j] + v[2] * m[2][j] for j in range(3)]


def transpose(m):
    return [[m[j][i] for j in range(3)] for i in range(3)]


def oriented(points_obj, obj_rot):
    """Translation-free world-oriented coordinates: object vertex times the 3x3 part of objectTransform."""
    return [vec_mat(p, obj_rot) for p in points_obj]


def _jacobi(a):
    """Eigenvalues and eigenvectors (columns) of a symmetric 3x3 matrix."""
    a = [row[:] for row in a]
    v = [[1.0 if i == j else 0.0 for j in range(3)] for i in range(3)]
    for _ in range(64):
        p, q = max(((0, 1), (0, 2), (1, 2)), key=lambda t: abs(a[t[0]][t[1]]))
        if abs(a[p][q]) <= 1e-300 or abs(a[p][q]) <= 1e-18 * (abs(a[p][p]) + abs(a[q][q])):
            break
        theta = (a[q][q] - a[p][p]) / (2.0 * a[p][q])
        t = (1.0 if theta >= 0 else -1.0) / (abs(theta) + math.sqrt(theta * theta + 1.0))
        c = 1.0 / math.sqrt(t * t + 1.0)
        s = t * c
        for k in range(3):
            akp, akq = a[k][p], a[k][q]
            a[k][p], a[k][q] = c * akp - s * akq, s * akp + c * akq
        for k in range(3):
            apk, aqk = a[p][k], a[q][k]
            a[p][k], a[q][k] = c * apk - s * aqk, s * apk + c * aqk
        for k in range(3):
            vkp, vkq = v[k][p], v[k][q]
            v[k][p], v[k][q] = c * vkp - s * vkq, s * vkp + c * vkq
    return [a[i][i] for i in range(3)], [[v[r][i] for r in range(3)] for i in range(3)]


def _axis_sign(x):
    """X sign rule: plan angle in [0, 180); a vertical X points up."""
    xy = math.hypot(x[0], x[1])
    if xy > 1e-9:
        ang = math.degrees(math.atan2(x[1], x[0]))
        if abs(canonical_angle(ang) - (ang % 360.0)) > 1e-6:
            return [-c for c in x]
        return list(x)
    return list(x) if x[2] >= 0 else [-c for c in x]


def frame_rows(x_axis, z_axis):
    """Orthonormal right-handed rows (X, Y, Z) from X and an approximate Z."""
    z = _unit(tuple(z_axis))
    x = tuple(x_axis)
    d = _dot(x, z)
    x = _unit((x[0] - d * z[0], x[1] - d * z[1], x[2] - d * z[2]))
    y = _cross(z, x)
    return [list(x), list(y), list(z)]


def axes_long_side(points_obj, obj_rot):
    """{'rows', 'angle', 'long', 'short', 'uncertainty'} — X along the long side of the plan, Z world up.

    Refuses (ValueError with the exact reason) a square or degenerate footprint and an axis whose float32
    uncertainty exceeds ANGLE_TOL_DEG."""
    world = oriented(points_obj, obj_rot)
    rect = min_area_rect([(p[0], p[1]) for p in world])
    if rect['long'] <= 0.0 or (rect['long'] - rect['short']) <= SQUARE_REL * rect['long']:
        raise ValueError('square or degenerate footprint: long side {:.6g} vs short side {:.6g}, the long side '
                         'is undefined'.format(rect['long'], rect['short']))
    unc = angle_uncertainty(points_obj, rect['long'])
    if unc > ANGLE_TOL_DEG:
        raise ValueError('axis uncertainty {:.4f}° > {}°: object vertices are stored too far from the pivot '
                         '(float32); move the pivot near the object first'.format(unc, ANGLE_TOL_DEG))
    a = math.radians(rect['angle'])
    rows = frame_rows((math.cos(a), math.sin(a), 0.0), (0.0, 0.0, 1.0))
    return {'rows': rows, 'angle': rect['angle'], 'long': rect['long'], 'short': rect['short'],
            'uncertainty': unc}


def axes_pca(points_obj, obj_rot):
    """Principal axes in double: X the major axis, Z the minor axis turned up. Refuses ties."""
    world = oriented(points_obj, obj_rot)
    n = len(world)
    if n < 4:
        raise ValueError('degenerate object: fewer than 4 vertices for principal axes')
    c = [sum(p[i] for p in world) / n for i in range(3)]
    cov = [[sum((p[i] - c[i]) * (p[j] - c[j]) for p in world) / n for j in range(3)] for i in range(3)]
    vals, vecs = _jacobi(cov)
    order = sorted(range(3), key=lambda i: -vals[i])
    lam = [vals[i] for i in order]
    if lam[0] <= 0.0 or (lam[0] - lam[1]) <= EIGEN_REL * lam[0] or (lam[1] - lam[2]) <= EIGEN_REL * lam[0]:
        raise ValueError('principal axes undefined: principal values {} are not distinct'.format(
            ', '.join('{:.6g}'.format(v) for v in lam)))
    x = _axis_sign(vecs[order[0]])
    z = list(vecs[order[2]])
    if z[2] < 0 or (abs(z[2]) <= 1e-12 and _dot(_cross(tuple(z), tuple(x)), (0.0, 0.0, 1.0)) < 0):
        z = [-v for v in z]
    rows = frame_rows(x, z)
    ext = max(math.sqrt(max(v, 0.0)) for v in lam)
    return {'rows': rows, 'angle': canonical_angle(math.degrees(math.atan2(rows[0][1], rows[0][0]))),
            'principal': lam, 'uncertainty': angle_uncertainty(points_obj, 2.0 * ext)}


def frame_bounds(points_obj, obj_rot, rows):
    """(min, max) of the object in the frame `rows` (translation-free, double)."""
    world = oriented(points_obj, obj_rot)
    local = [vec_mat(p, transpose(rows)) for p in world]
    return ([min(p[i] for p in local) for i in range(3)], [max(p[i] for p in local) for i in range(3)])


def frame_point(local, rows):
    """Translation-free world vector of a point given in the frame `rows`."""
    return vec_mat(local, rows)


def f32(x):
    import struct
    return struct.unpack('<f', struct.pack('<f', float(x)))[0]


def check_unit_scale(node_rows):
    """Refusal text when the node scale is not 1 (the offset recomputation keeps rotation and position only)."""
    s = [_length(tuple(r)) for r in node_rows[:3]]
    if any(abs(v - 1.0) > SCALE_TOL for v in s):
        return 'node scale is {} not 1: reset the scale (Reset XForm) on the copy first'.format(
            ', '.join('{:.6g}'.format(v) for v in s))
    return ''


def new_offset(node_rows, offset_rows, new_rows, new_pos32):
    """objectOffset of a node turned to `new_rows` and moved to `new_pos32`, with object-to-world unchanged.

    node_rows: 4 rows of the node transform; offset_rows: 4 rows of the objectOffset matrix (scale*rot, pos).
    Max row-vector: world = x*Mo*R + po*R + t. New: Mo' = Mo R R'^T; po' = (po R + (t - t')) R'^T, where
    t - t' is taken in double from the float32 values, so nothing is lost at 2 345 678 m."""
    r_old = [list(map(float, r)) for r in node_rows[:3]]
    t_old = [float(c) for c in node_rows[3]]
    mo = [list(map(float, r)) for r in offset_rows[:3]]
    po = [float(c) for c in offset_rows[3]]
    rt_new = transpose(new_rows)
    mo_new = mat3_mul(mat3_mul(mo, r_old), rt_new)
    shift = [t_old[i] - float(new_pos32[i]) for i in range(3)]
    po_r = vec_mat(po, r_old)
    po_new = vec_mat([po_r[i] + shift[i] for i in range(3)], rt_new)
    return mo_new, po_new


def world_points(points_obj, offset_rows, node_rows):
    """World vertices in double: x*Mo*R + po*R + t (for the before/after drift check)."""
    mo = [list(map(float, r)) for r in offset_rows[:3]]
    po = [float(c) for c in offset_rows[3]]
    r = [list(map(float, row)) for row in node_rows[:3]]
    t = [float(c) for c in node_rows[3]]
    pr = vec_mat(po, r)
    out = []
    for p in points_obj:
        q = vec_mat(vec_mat(p, mo), r)
        out.append([q[i] + pr[i] + t[i] for i in range(3)])
    return out


REFUSAL_CODES = (('square or degenerate footprint', 'pivot_axis_undefined'),
                 ('degenerate footprint', 'pivot_axis_undefined'),
                 ('principal axes undefined', 'pivot_axis_undefined'),
                 ('degenerate object', 'pivot_axis_undefined'),
                 ('no vertices', 'pivot_axis_undefined'),
                 ('axis uncertainty', 'pivot_axis_uncertain'),
                 ('node scale', 'pivot_node_scale'))


def refusal_code(text):
    """Finding code of a pivot refusal (the reason text stays the detail)."""
    for words, code in REFUSAL_CODES:
        if words in str(text):
            return code
    return 'pivot_refused'


def axis_error_deg(rows, expected_deg):
    """Angle between X in plan and an expected undirected direction (degrees, 0..90)."""
    got = math.degrees(math.atan2(rows[0][1], rows[0][0]))
    d = abs(canonical_angle(got) - canonical_angle(expected_deg))
    return min(d, 180.0 - d)


# ---- piece classification (ucx.triangulate / model.triangulate) ---------------------------------------
def classify(base_class, modifiers, convertible):
    """('poly', '') | ('convert', why) | ('skip', reason) for one node on its export copy.

    The source silently skipped Box primitives, Editable Mesh and Editable Poly with modifiers (lab defect 2);
    here those copies are converted (and listed), anything that cannot become a poly is skipped with a reason."""
    if not convertible:
        return 'skip', 'not geometry convertible to Editable Poly ({})'.format(base_class)
    if base_class == 'Editable_Poly' and not modifiers:
        return 'poly', ''
    why = base_class if not modifiers else '{} with {} modifier(s)'.format(base_class, modifiers)
    return 'convert', 'copy converted to Editable Poly from ' + why


def is_ucx_name(name):
    return str(name).upper().startswith('UCX_')
