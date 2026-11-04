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
PIVOT_OPTIONS = {'target', 'floor_z', 'vpm_rotate_z'}
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


def ucx_plan(points, polygons, tol):
    """Plan for one UCX piece: {'action': 'diagonals'|'hull'|'none', 'pairs', 'hull', 'reason'}.

    points: object-space vertices; polygons: vertex-id lists (0-based) in Max winding (outward CCW)."""
    pts = _finite_points(points, 'UCX piece')
    fan = [(p[0], p[i], p[i + 1]) for p in polygons for i in range(1, len(p) - 1)]
    if not fan:
        raise ValueError('UCX piece without faces')
    vol = _signed_volume(pts, fan)
    sign = 1.0 if vol >= 0 else -1.0
    pairs, tris, ngons = [], [], 0
    convex = True
    for poly in polygons:
        poly = [int(v) for v in poly]
        got = ucx_polygon(pts, poly, [pts[v] for v in poly], tol, sign)
        if got is None:
            convex = False
            break
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
    if convex:
        return {'action': 'diagonals' if ngons else 'none', 'pairs': pairs, 'hull': None,
                'reason': '' if ngons else 'already triangles'}
    ucx = _ucx_core()
    hverts, htris = ucx._convex_hull(pts)
    return {'action': 'hull', 'pairs': [], 'hull': {'verts': [list(v) for v in hverts],
                                                     'tris': [list(t) for t in htris]},
            'reason': 'no supporting triangulation: the piece is not convex; rebuilt as its convex hull'}


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
