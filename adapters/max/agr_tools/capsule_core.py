"""new-case: AGR Tools 1.0 (#1024) interior capsules logic, stdlib only; owned by branch K (improve/issue-1024-capsules-roof).

Pure logic for `body_capsules` (body.capsules, station 1.0.12); no pymxs. The glue (capsule_max.py) reads the
openings through the ONE recognition `openings_core.find_openings` (branch J) and creates the meshes; reports,
preview hashes and roles go through edit_core.py / contract_core.py.

Logic of the owner (ANSWERS-2026-11-06 «Капсулы»): a «cap» on the reveal contour, outlined 100 mm outwards,
turned 90° and put onto the recessed opening.
* The open rim of the capsule lies on the plane of the middle of the window frame by depth (border plane + half
  the frame depth towards the street, default 50 mm) and is 100 mm wider than the opening contour, so it goes into
  the wall body behind the reveal and never cuts the reveals.
* The capsule goes 1.0 m into the building from the border plane (the plane on which win.place puts the rear
  contour of the window) and wraps the inner part of the opening; all faces look INTO the capsule, the rim is the
  only open loop.
* A corner opening gets ONE L-capsule: two branches, each parallel to its wall.

Lab L10 (docs/experiments/body.capsules.md, job 20261106-021309-5342b103): the Max chain (createShape -> cap ->
Edit_Poly outline -> Shell) is NOT used - empty caps without an error (arch, corner, non-planar), system units,
normals outwards, ~1 s per opening. This module is the own extrusion of the lab prototype: plane by Newell, side
from the wall normal, mitre offset in the plane, prism, faces inwards; metres only (the glue converts with
units.SystemScale). A border the module cannot take is `ambiguous` with a code, never an empty object.
"""
import math

TOOL = 'body.capsules'
ROLE = 'capsule'
LAYER = 'CAPSULE_interior'
MATERIAL = 'LIB_Interior_Stub'  # library placeholder «интерьер» (stub material made by the glue when absent)
DEFAULTS = {
    'outline_m': 0.1,          # owner: outline 100 mm outwards of the reveal contour
    'interior_depth_m': 1.0,   # owner: 1.0 m of interior behind the border plane
    'frame_depth_m': 0.1,      # F100 window family (ANSWERS «Окна»): rim on the frame middle = depth / 2
    'rim': 'frame_middle',     # frame_middle | border_plane (the lab alternative, rim on the window plane)
    'corner': 'L',             # owner: a corner opening is one L-capsule
    'nonplanar_tol_m': 0.005,  # lab L10: 20 / 50 mm out of plane shifts the rim by 16 / 41 mm -> ambiguous
    'wall_angle_tol_deg': 5.0,  # border plane against the wall normal of the opening frame
    'corner_angle_tol_deg': 1.0,
    'overlap_tol_m': 0.0001,   # acceptance: 0.1 mm
}
CODES = ('no_openings', 'border_short', 'border_nonplanar', 'border_not_in_wall', 'frame_missing',
         'offset_invalid', 'reveal_too_shallow', 'corner_shape', 'corner_concave', 'corner_unsupported',
         'capsules_overlap')
EPS = 1e-9


# ---- small vector algebra -------------------------------------------------------------------------------------
def _sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def _add(a, b):
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def _mul(a, k):
    return [a[0] * k, a[1] * k, a[2] * k]


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _norm(a):
    return math.sqrt(_dot(a, a))


def _unit(a):
    n = _norm(a)
    if n < EPS:
        raise ValueError('zero vector')
    return [a[0] / n, a[1] / n, a[2] / n]


def newell(loop):
    """Newell normal (not normalised; length = 2 x area) of a closed 3D loop."""
    n = [0.0, 0.0, 0.0]
    for i, p in enumerate(loop):
        q = loop[(i + 1) % len(loop)]
        n[0] += (p[1] - q[1]) * (p[2] + q[2])
        n[1] += (p[2] - q[2]) * (p[0] + q[0])
        n[2] += (p[0] - q[0]) * (p[1] + q[1])
    return n


def centroid(points):
    k = 1.0 / len(points)
    return [sum(p[0] for p in points) * k, sum(p[1] for p in points) * k, sum(p[2] for p in points) * k]


# ---- 2D polygon helpers (shared with roof_core by import of this file) -----------------------------------------
def area2(poly):
    """Signed area of a 2D polygon (CCW > 0)."""
    s = 0.0
    for i, p in enumerate(poly):
        q = poly[(i + 1) % len(poly)]
        s += p[0] * q[1] - q[0] * p[1]
    return 0.5 * s


def clean2(poly, tol=1e-7):
    """Drop repeated and collinear points of a closed 2D polygon."""
    pts = []
    for p in poly:
        if not pts or math.hypot(p[0] - pts[-1][0], p[1] - pts[-1][1]) > tol:
            pts.append([float(p[0]), float(p[1])])
    if len(pts) > 1 and math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) <= tol:
        pts.pop()
    changed = True
    while changed and len(pts) > 3:
        changed = False
        for i in range(len(pts)):
            a, b, c = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
            cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
            la, lc = math.hypot(b[0] - a[0], b[1] - a[1]), math.hypot(c[0] - b[0], c[1] - b[1])
            if abs(cr) <= tol * max(la, lc, tol) and (b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1]) >= 0:
                pts.pop(i)
                changed = True
                break
    return pts


def _seg_cross(p, q, r, s):
    """Proper intersection of segments pq and rs (shared end points do not count)."""
    def orient(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    d1, d2, d3, d4 = orient(r, s, p), orient(r, s, q), orient(p, q, r), orient(p, q, s)
    return (d1 > EPS and d2 < -EPS or d1 < -EPS and d2 > EPS) and (d3 > EPS and d4 < -EPS or d3 < -EPS and d4 > EPS)


def is_simple(poly):
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            if _seg_cross(a, b, poly[j], poly[(j + 1) % n]):
                return False
    return True


def offset2(poly, d):
    """Mitre offset of a CCW 2D polygon by d (> 0 outwards). None if a mitre degenerates (spike > 10 d)."""
    n = len(poly)
    normals = []
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy)
        if ln < EPS:
            return None
        normals.append((dy / ln, -dx / ln))  # outward normal of a CCW edge
    out = []
    for i in range(n):
        n1, n2 = normals[i - 1], normals[i]
        k = 1.0 + n1[0] * n2[0] + n1[1] * n2[1]
        if k < 0.02:  # turn sharper than ~164 degrees
            return None
        out.append([poly[i][0] + d * (n1[0] + n2[0]) / k, poly[i][1] + d * (n1[1] + n2[1]) / k])
    return out


def point_seg_dist(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln2 = dx * dx + dy * dy
    t = 0.0 if ln2 < EPS else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / ln2))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def poly_dist(p, poly):
    return min(point_seg_dist(p, poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly)))


def inside(p, poly):
    """Point in polygon (even-odd); points on the boundary count as inside."""
    if poly_dist(p, poly) < 1e-9:
        return True
    c = False
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        if (a[1] > p[1]) != (b[1] > p[1]):
            x = a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if x > p[0]:
                c = not c
    return c


def ear_clip(poly):
    """Triangles [(i, j, k)] (CCW, indices into poly) of a simple CCW polygon."""
    idx = list(range(len(poly)))
    tris = []
    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        for t in range(len(idx)):
            i, j, k = idx[t - 1], idx[t], idx[(t + 1) % len(idx)]
            a, b, c = poly[i], poly[j], poly[k]
            if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) <= EPS:
                continue
            if any(_in_tri(poly[m], a, b, c) for m in idx if m not in (i, j, k)):
                continue
            tris.append((i, j, k))
            idx.pop(t)
            break
        else:
            raise ValueError('polygon cannot be triangulated (not simple)')
    tris.append(tuple(idx))
    return tris


def _in_tri(p, a, b, c):
    def s(u, v, w):
        return (v[0] - u[0]) * (w[1] - u[1]) - (v[1] - u[1]) * (w[0] - u[0])
    return s(a, b, p) >= -EPS and s(b, c, p) >= -EPS and s(c, a, p) >= -EPS


# ---- mesh helpers ---------------------------------------------------------------------------------------------
def signed_volume(verts, faces):
    v = 0.0
    for f in faces:
        a = verts[f[0]]
        for i in range(1, len(f) - 1):
            v += _dot(a, _cross(verts[f[i]], verts[f[i + 1]])) / 6.0
    return v


def open_edges(faces):
    """Undirected edges used by exactly one face."""
    count = {}
    for f in faces:
        for i in range(len(f)):
            e = tuple(sorted((f[i], f[(i + 1) % len(f)])))
            count[e] = count.get(e, 0) + 1
    return sorted(e for e, c in count.items() if c == 1)


def bad_edges(faces):
    """Edges used by more than two faces or twice in the same direction (non-manifold / inconsistent winding)."""
    seen, bad = {}, []
    for f in faces:
        for i in range(len(f)):
            e = (f[i], f[(i + 1) % len(f)])
            seen[e] = seen.get(e, 0) + 1
    for e, c in seen.items():
        if c > 1:
            bad.append(e)
    return bad


def triangles(faces):
    return [(f[0], f[i], f[i + 1]) for f in faces for i in range(1, len(f) - 1)]


def face_normal(verts, f):
    return _unit(newell([verts[i] for i in f]))


def bbox(verts):
    return [[min(v[i] for v in verts) for i in range(3)], [max(v[i] for v in verts) for i in range(3)]]


def _bbox_hit(a, b, tol):
    return all(a[0][i] <= b[1][i] + tol and b[0][i] <= a[1][i] + tol for i in range(3))


def _seg_tri(p, q, a, b, c, tol):
    """Segment pq crosses the interior of triangle abc (Moller-Trumbore, tol shrinks the triangle and segment)."""
    e1, e2, d = _sub(b, a), _sub(c, a), _sub(q, p)
    h = _cross(d, e2)
    det = _dot(e1, h)
    if abs(det) < 1e-14:
        return False
    f = 1.0 / det
    s = _sub(p, a)
    u = f * _dot(s, h)
    qv = _cross(s, e1)
    v = f * _dot(d, qv)
    t = f * _dot(e2, qv)
    ln = _norm(d)
    lt = tol / ln if ln > EPS else 1.0
    area = _norm(_cross(e1, e2))
    w = tol * max(_norm(e1), _norm(e2), _norm(_sub(c, b))) / area if area > EPS else 1.0
    return lt < t < 1.0 - lt and u > w and v > w and u + v < 1.0 - w


def tri_hit(t1, t2, tol=1e-4):
    """Two triangles (3 points each) intersect beyond tol (edge of one through the interior of the other)."""
    for x, y in ((t1, t2), (t2, t1)):
        for i in range(3):
            if _seg_tri(x[i], x[(i + 1) % 3], y[0], y[1], y[2], tol):
                return True
    return False


def mesh_hits(m1, m2, tol=1e-4, limit=1):
    """Up to `limit` triangle pairs (i, j) of meshes {'verts','faces'} that intersect beyond tol."""
    if not _bbox_hit(bbox(m1['verts']), bbox(m2['verts']), tol):
        return []
    t2 = [[m2['verts'][i] for i in t] for t in triangles(m2['faces'])]
    b2 = [bbox(t) for t in t2]
    out = []
    for i, t in enumerate(triangles(m1['faces'])):
        a = [m1['verts'][k] for k in t]
        ba = bbox(a)
        for j, b in enumerate(t2):
            if _bbox_hit(ba, b2[j], -tol) and tri_hit(a, b, tol):
                out.append((i, j))
                if len(out) >= limit:
                    return out
    return out


def orient(faces):
    """Consistent winding over each connected patch (BFS: a shared edge runs in opposite directions)."""
    faces = [list(f) for f in faces]
    by_edge = {}
    for k, f in enumerate(faces):
        for i in range(len(f)):
            by_edge.setdefault(tuple(sorted((f[i], f[(i + 1) % len(f)]))), []).append(k)
    done = [False] * len(faces)
    for start in range(len(faces)):
        if done[start]:
            continue
        done[start] = True
        todo = [start]
        while todo:
            k = todo.pop()
            f = faces[k]
            for i in range(len(f)):
                a, b = f[i], f[(i + 1) % len(f)]
                for j in by_edge[tuple(sorted((a, b)))]:
                    if done[j]:
                        continue
                    g = faces[j]
                    same = any(g[t] == a and g[(t + 1) % len(g)] == b for t in range(len(g)))
                    if same:
                        faces[j] = list(reversed(g))
                    done[j] = True
                    todo.append(j)
    return faces


def _inward(verts, faces, caps):
    """Orient every face so that the normals look INTO the volume (signed volume of the closed shell < 0)."""
    allf = orient(list(faces) + list(caps))
    if signed_volume(verts, allf) > 0:
        allf = [list(reversed(f)) for f in allf]
    return allf[:len(faces)], allf[len(faces):]


# ---- options ----------------------------------------------------------------------------------------------------
def options(raw=None):
    """Defaults + the caller's options, validated (metres, degrees)."""
    raw = dict(raw or {})
    unknown = sorted(set(raw) - set(DEFAULTS))
    if unknown:
        raise ValueError('body.capsules: unknown option(s) ' + ', '.join(unknown))
    out = dict(DEFAULTS, **raw)
    for k in ('outline_m', 'interior_depth_m', 'frame_depth_m', 'nonplanar_tol_m', 'wall_angle_tol_deg',
              'corner_angle_tol_deg', 'overlap_tol_m'):
        v = out[k]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            raise ValueError('body.capsules: option {} must be a number >= 0: {!r}'.format(k, v))
        out[k] = float(v)
    if out['outline_m'] <= 0 or out['interior_depth_m'] <= 0:
        raise ValueError('body.capsules: outline_m and interior_depth_m must be > 0')
    if out['rim'] not in ('frame_middle', 'border_plane'):
        raise ValueError('body.capsules: rim must be frame_middle or border_plane')
    if out['corner'] not in ('L', 'skip'):
        raise ValueError('body.capsules: corner must be L or skip')
    return out


def rim_offset(opts):
    """Distance of the open rim in front of the border plane (towards the street), metres."""
    return opts['frame_depth_m'] / 2.0 if opts['rim'] == 'frame_middle' else 0.0


# ---- capsules ---------------------------------------------------------------------------------------------------
class Ambiguous(ValueError):
    def __init__(self, code, detail):
        ValueError.__init__(self, '{}: {}'.format(code, detail))
        self.code, self.detail = code, detail


def _frame_z(opening):
    fr = opening.get('frame') or {}
    z = fr.get('z')
    if not z or len(z) != 3:
        raise Ambiguous('frame_missing', 'opening {} has no frame.z (wall normal outwards)'.format(opening.get('id')))
    return _unit([float(c) for c in z])


def planar_capsule(opening, opts):
    """Prism capsule of a planar (not corner) opening: {'verts', 'faces', 'rim', ...}; Ambiguous on refusal."""
    loop = [[float(c) for c in p] for p in opening.get('border') or ()]
    if len(loop) < 3:
        raise Ambiguous('border_short', 'opening {}: border has {} points'.format(opening.get('id'), len(loop)))
    zout = _frame_z(opening)
    nn = newell(loop)
    if _norm(nn) < EPS:
        raise Ambiguous('border_short', 'opening {}: border has no area'.format(opening.get('id')))
    n = _unit(nn)
    if _dot(n, zout) < 0:
        n = _mul(n, -1.0)
    ang = math.degrees(math.acos(max(-1.0, min(1.0, _dot(n, zout)))))
    if ang > opts['wall_angle_tol_deg']:
        raise Ambiguous('border_not_in_wall', 'opening {}: border plane {:.1f} deg off the wall normal'.format(
            opening.get('id'), ang))
    c = centroid(loop)
    ds = [_dot(_sub(p, c), n) for p in loop]
    dev = max(ds) - min(ds)  # thickness of the border across its best plane
    if dev > opts['nonplanar_tol_m']:
        raise Ambiguous('border_nonplanar', 'opening {}: border {:.1f} mm out of its plane > {:.1f} mm'.format(
            opening.get('id'), dev * 1000, opts['nonplanar_tol_m'] * 1000))
    r = rim_offset(opts)
    depth = opening.get('depth')
    if isinstance(depth, (int, float)) and not isinstance(depth, bool) and 0 < depth <= r + 1e-6:
        raise Ambiguous('reveal_too_shallow', 'opening {}: reveal {:.0f} mm, the rim stands {:.0f} mm in front of '
                        'the border plane'.format(opening.get('id'), depth * 1000, r * 1000))
    # in-plane frame: u horizontal (or frame x), v = n x u; the polygon in (u, v) is made CCW about +n (outwards)
    fx = (opening.get('frame') or {}).get('x')
    u = _sub([float(t) for t in fx], _mul(n, _dot([float(t) for t in fx], n))) if fx else _cross([0.0, 0.0, 1.0], n)
    if _norm(u) < 1e-6:
        u = _cross([0.0, 1.0, 0.0], n)
    u = _unit(u)
    v = _cross(n, u)
    poly = clean2([[_dot(_sub(p, c), u), _dot(_sub(p, c), v)] for p in loop])
    if len(poly) < 3 or abs(area2(poly)) < 1e-8:
        raise Ambiguous('border_short', 'opening {}: border degenerates'.format(opening.get('id')))
    if area2(poly) < 0:
        poly.reverse()
    if not is_simple(poly):
        raise Ambiguous('offset_invalid', 'opening {}: border crosses itself'.format(opening.get('id')))
    o = opts['outline_m']
    off = offset2(poly, o)
    if off is None or not is_simple(off) or area2(off) <= area2(poly) or \
            min(poly_dist(q, poly) for q in off) < o * (1 - 1e-6):
        raise Ambiguous('offset_invalid', 'opening {}: the {:.0f} mm outline of this contour is not a clean '
                        'offset (arch too tight / spike)'.format(opening.get('id'), o * 1000))
    D = opts['interior_depth_m']
    m = len(off)

    def world(q, h):
        return _add(_add(_add(c, _mul(u, q[0])), _mul(v, q[1])), _mul(n, h))
    verts = [world(q, r) for q in off] + [world(q, -D) for q in off]
    sides = [[i, (i + 1) % m, m + (i + 1) % m, m + i] for i in range(m)]
    back = [[m + t[0], m + t[1], m + t[2]] for t in ear_clip(off)]
    rim_cap = [list(range(m))]
    faces, caps = _inward(verts, sides + back, rim_cap)
    return {'kind': 'planar', 'verts': verts, 'faces': faces, 'caps': caps, 'rim': list(range(m)),
            'normal': n, 'outline_m': o, 'depth_m': D, 'rim_offset_m': r,
            'size_m': [round(max(q[0] for q in off) - min(q[0] for q in off), 6),
                       round(max(q[1] for q in off) - min(q[1] for q in off), 6)]}


def _rect_union(r, x1, y1, x2, y2):
    """Union of [-r, x1] x [-r, y1] and [-r, x2] x [-r, y2] (both from the corner (-r, -r)), CCW, cleaned."""
    if x1 <= x2 and y1 <= y2:
        pts = [[-r, -r], [x2, -r], [x2, y2], [-r, y2]]
    elif x2 <= x1 and y2 <= y1:
        pts = [[-r, -r], [x1, -r], [x1, y1], [-r, y1]]
    elif x1 > x2:  # branch A longer along e1, branch B higher along e2
        pts = [[-r, -r], [x1, -r], [x1, y1], [x2, y1], [x2, y2], [-r, y2]]
    else:
        pts = [[-r, -r], [x2, -r], [x2, y2], [x1, y2], [x1, y1], [-r, y1]]
    return clean2(pts)


def corner_capsule(opening, opts):
    """ONE L-capsule of a corner opening (owner 06.11): a vertical prism of the union of two branches, each
    parallel to its wall; the two front faces (rim on the frame-middle planes of both walls) stay open."""
    loop = [[float(c) for c in p] for p in opening.get('border') or ()]
    oid = opening.get('id')
    if len(loop) < 4:
        raise Ambiguous('border_short', 'corner opening {}: border has {} points'.format(oid, len(loop)))
    zout = _frame_z(opening)
    tol = max(opts['nonplanar_tol_m'], 1e-4)
    plan = []
    for p in loop:
        if not any(math.hypot(p[0] - q[0], p[1] - q[1]) <= tol for q in plan):
            plan.append([p[0], p[1]])
    best = None
    for i in range(len(plan)):
        for j in range(i + 1, len(plan)):
            d = math.hypot(plan[i][0] - plan[j][0], plan[i][1] - plan[j][1])
            if best is None or d > best[0]:
                best = (d, plan[i], plan[j])
    if best is None or best[0] < EPS:
        raise Ambiguous('corner_shape', 'corner opening {}: no plan extent'.format(oid))
    _, ea, eb = best
    corner = max(plan, key=lambda p: point_seg_dist(p, ea, eb))
    a, b = math.hypot(ea[0] - corner[0], ea[1] - corner[1]), math.hypot(eb[0] - corner[0], eb[1] - corner[1])
    if a < 0.05 or b < 0.05:
        raise Ambiguous('corner_shape', 'corner opening {}: one branch is shorter than 50 mm'.format(oid))
    if any(min(point_seg_dist(p, corner, ea), point_seg_dist(p, corner, eb)) > tol for p in plan):
        raise Ambiguous('corner_shape', 'corner opening {}: the border is not two straight wall runs in plan'.format(
            oid))
    e1 = [(ea[0] - corner[0]) / a, (ea[1] - corner[1]) / a]
    e2 = [(eb[0] - corner[0]) / b, (eb[1] - corner[1]) / b]
    ang = math.degrees(math.acos(max(-1.0, min(1.0, e1[0] * e2[0] + e1[1] * e2[1]))))
    if abs(ang - 90.0) > opts['corner_angle_tol_deg']:
        raise Ambiguous('corner_unsupported', 'corner opening {}: walls meet at {:.1f} deg, the L-capsule needs '
                        '90 deg'.format(oid, ang))
    # convex corner: the building is the quadrant (e1 >= 0, e2 >= 0); outward normals -e2 (wall A), -e1 (wall B)
    zh = [zout[0], zout[1]]
    lz = math.hypot(*zh)
    if lz < 0.5:
        raise Ambiguous('corner_shape', 'corner opening {}: frame.z is not horizontal'.format(oid))
    zh = [zh[0] / lz, zh[1] / lz]
    da, db = -(zh[0] * e2[0] + zh[1] * e2[1]), -(zh[0] * e1[0] + zh[1] * e1[1])
    if max(da, db) < 0.9:
        raise Ambiguous('corner_concave', 'corner opening {}: re-entrant corner (wall normal points into the '
                        'quadrant of the walls); not supported, ask the agent'.format(oid))
    zs = [p[2] for p in loop]
    o, D, r = opts['outline_m'], opts['interior_depth_m'], rim_offset(opts)
    z0, z1 = min(zs) - o, max(zs) + o
    poly = _rect_union(r, a + o, D, D, b + o)  # coords (s along e1, t along e2)
    if area2(poly) < 0:
        poly.reverse()

    def world(q, z):
        return [corner[0] + q[0] * e1[0] + q[1] * e2[0], corner[1] + q[0] * e1[1] + q[1] * e2[1], z]
    m = len(poly)
    verts = [world(q, z0) for q in poly] + [world(q, z1) for q in poly]
    sides, caps, rim_edges = [], [], []
    for i in range(m):
        p, q = poly[i], poly[(i + 1) % m]
        quad = [i, (i + 1) % m, m + (i + 1) % m, m + i]
        front = (abs(p[1] + r) < 1e-9 and abs(q[1] + r) < 1e-9) or (abs(p[0] + r) < 1e-9 and abs(q[0] + r) < 1e-9)
        (caps if front else sides).append(quad)
        if front:
            rim_edges.append(i)
    if len(caps) != 2:
        raise Ambiguous('corner_shape', 'corner opening {}: L-capsule without two front faces'.format(oid))
    tris = ear_clip(poly)
    floor = [[t[0], t[1], t[2]] for t in tris]
    ceil = [[m + t[0], m + t[1], m + t[2]] for t in tris]
    faces, caps = _inward(verts, sides + floor + ceil, caps)
    return {'kind': 'corner', 'verts': verts, 'faces': faces, 'caps': caps, 'rim': None, 'outline_m': o, 'depth_m': D,
            'rim_offset_m': r, 'branches_m': [round(a, 6), round(b, 6)], 'corner_xy': corner,
            'axes': [e1, e2], 'height_m': round(z1 - z0, 6)}


def capsule(opening, opts):
    if opening.get('corner'):
        if opts['corner'] == 'skip':
            raise Ambiguous('corner_unsupported', 'corner opening {}: corner capsules switched off'.format(
                opening.get('id')))
        return corner_capsule(opening, opts)
    return planar_capsule(opening, opts)


def same_wall_overlap(r1, r2, tol=1e-4):
    """Two planar capsules of one wall plane whose outlined contours overlap: their faces are coplanar (rims,
    backs) and only touch, so the triangle test cannot see it; compare the rim polygons in the wall plane."""
    if r1['kind'] != 'planar' or r2['kind'] != 'planar':
        return False
    n1, n2 = r1['normal'], r2['normal']
    if _dot(n1, n2) < 1 - 1e-6:
        return False
    a0, b0 = r1['verts'][r1['rim'][0]], r2['verts'][r2['rim'][0]]
    if abs(_dot(_sub(a0, b0), n1)) > tol:
        return False
    u = _unit(_sub(r1['verts'][r1['rim'][1]], a0))
    v = _cross(n1, u)
    pa = [[_dot(r1['verts'][i], u), _dot(r1['verts'][i], v)] for i in r1['rim']]
    pb = [[_dot(r2['verts'][i], u), _dot(r2['verts'][i], v)] for i in r2['rim']]
    for x, y in ((pa, pb), (pb, pa)):
        cx, cy = sum(p[0] for p in x) / len(x), sum(p[1] for p in x) / len(x)
        for p in x:  # each corner, and the corner pulled 10 tol into its own polygon (coincident edges)
            d = math.hypot(cx - p[0], cy - p[1]) or 1.0
            q = [p[0] + (cx - p[0]) * 10 * tol / d, p[1] + (cy - p[1]) * 10 * tol / d]
            if any(inside(t, y) and poly_dist(t, y) > tol for t in (p, q)):
                return True
    return any(_seg_cross(pa[i], pa[(i + 1) % len(pa)], pb[j], pb[(j + 1) % len(pb)])
               for i in range(len(pa)) for j in range(len(pb)))


def capsule_name(body_name, opening_id):
    return 'CAPSULE_{}_{:03d}'.format(body_name, int(opening_id))


def plan(bodies, raw_options=None):
    """bodies: [{'handle': int, 'name': str, 'openings': [find_openings rows]}] -> pure plan.

    Returns {'options', 'rows': [{'body', 'handle', 'opening', 'name', 'kind', 'verts', 'faces'}],
    'findings': {handle: [(code, detail)]}, 'done', 'skipped', 'ambiguous'}. Capsules that would cross each other
    (beyond overlap_tol_m) are refused both (`capsules_overlap`)."""
    if not bodies:
        raise ValueError('body.capsules: empty target set')
    opts = options(raw_options)
    rows, findings, skipped, ambiguous = [], {}, [], []
    for b in bodies:
        findings.setdefault(b['handle'], [])
        ops = list(b.get('openings') or ())
        if not ops:
            findings[b['handle']].append(('no_openings', '{}: no opening borders found'.format(b['name'])))
            skipped.append({'item': b['name'], 'reason': 'no opening borders found (openings_core.find_openings)'})
            continue
        for op in sorted(ops, key=lambda x: int(x.get('id', 0))):
            try:
                cap = capsule(op, opts)
            except Ambiguous as exc:
                findings[b['handle']].append((exc.code, exc.detail))
                ambiguous.append('{} opening {}: {}'.format(b['name'], op.get('id'), exc))
                continue
            rows.append(dict(cap, body=b['name'], handle=b['handle'], opening=int(op.get('id', 0)),
                             name=capsule_name(b['name'], op.get('id', 0))))
    bad = set()
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            if mesh_hits(rows[i], rows[j], opts['overlap_tol_m']) or                     same_wall_overlap(rows[i], rows[j], opts['overlap_tol_m']):
                bad.update((i, j))
                for k, other in ((i, j), (j, i)):
                    findings[rows[k]['handle']].append(('capsules_overlap', '{} crosses {}'.format(
                        rows[k]['name'], rows[other]['name'])))
                ambiguous.append('{} x {}: capsules cross (adjacent openings closer than 2 x outline)'.format(
                    rows[i]['name'], rows[j]['name']))
    rows = [r for k, r in enumerate(rows) if k not in bad]
    done = ['{} <- {} opening {} ({}, outline {:.0f} mm, depth {:.2f} m, rim +{:.0f} mm)'.format(
        r['name'], r['body'], r['opening'], r['kind'], r['outline_m'] * 1000, r['depth_m'], r['rim_offset_m'] * 1000)
        for r in rows]
    return {'options': opts, 'rows': rows, 'findings': findings, 'done': done, 'skipped': skipped,
            'ambiguous': ambiguous}


def check_capsule(row):
    """Self-check of one capsule mesh (tests and the native run): the open edges are exactly the edges of the
    omitted rim faces, the closed shell is manifold with one winding, every face looks inwards (signed volume of
    the closed shell < 0). Returns {'open_edges', 'open_off_rim', 'closed_open_edges', 'bad_edges', 'inward'}."""
    faces, caps = row['faces'], row['caps']
    closed = faces + caps
    rim = {tuple(sorted((f[i], f[(i + 1) % len(f)]))) for f in caps for i in range(len(f))}
    opened = set(open_edges(faces))
    return {'open_edges': len(opened), 'open_off_rim': len(opened - rim),
            'closed_open_edges': len(open_edges(closed)), 'bad_edges': len(bad_edges(closed)),
            'inward': signed_volume(row['verts'], closed) < 0}
