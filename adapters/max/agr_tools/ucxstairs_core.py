"""AGR Tools 1.0 (#1024) UCX stairs logic, stdlib only. Owned by branch T (improve/issue-1024-deliver-small).

Pure logic for `ucx_stairs` (ucx.stairs, plan mode `read`); no pymxs, no host objects: the glue gives plain meshes in
METRES (world space). New code, no GeoAGR source (GeoAGR gap #8, issue #1024 section 24; requirements VPM-2.13-5/-6).

Rule: a stair is closed by ONE convex solid (truncated pyramid or prism) that covers the steps. The top plane of the
solid must follow the nosings (front top edges of the treads) within the class tolerance 10 / 30 / 100 cm:
  - a nosing is outside the solid by more than the tolerance       -> `stairs_outside`;
  - the solid is above a nosing by more than the tolerance         -> `ucx_too_high`;
  - several solids (a box per step), or a solid with parts         -> `ucx_not_single`;
  - the solid is not convex / not closed                           -> `ucx_not_convex` / `ucx_not_closed`;
  - no UCX at all                                                  -> `ucx_missing`.
Findings carry Russian details; ids are always empty (stairs are whole objects).
"""
import math
import re

TOOL = 'ucx.stairs'
TOLERANCES_CM = (10, 30, 100)
DEFAULT_TOLERANCE_CM = 30
STAIR_PATTERN = r'(?i)(stair|лестн)'
WELD_M = 1e-5
CONVEX_TOL_M = 1e-4
MIN_RISE_M = 0.05  # a "stair" that climbs less than this has no nosings


# ---- small vector helpers -----------------------------------------------------------------------------
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _len(a):
    return math.sqrt(_dot(a, a))


# ---- mesh preparation -----------------------------------------------------------------------------------
def weld(verts, tris, q=WELD_M):
    """Weld vertices by position (a UCX built with split vertices is still one closed solid) and drop degenerate
    triangles. Returns (points, faces)."""
    index, points, remap = {}, [], []
    for v in verts:
        key = tuple(int(round(c / q)) for c in v)
        if key not in index:
            index[key] = len(points)
            points.append((float(v[0]), float(v[1]), float(v[2])))
        remap.append(index[key])
    faces = []
    for t in tris:
        a, b, c = (remap[i] for i in t)
        if a != b and b != c and a != c:
            faces.append((a, b, c))
    return points, faces


def components(faces):
    """Connected components of faces by shared vertices -> list of face lists."""
    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b, c in faces:
        for u, v in ((a, b), (b, c)):
            ru, rv = find(u), find(v)
            if ru != rv:
                parent[ru] = rv
    groups = {}
    for f in faces:
        groups.setdefault(find(f[0]), []).append(f)
    return list(groups.values())


def solid_info(points, faces, tol=CONVEX_TOL_M):
    """Convexity/closedness of one solid. Outward is taken from the sign of the enclosed volume."""
    if not faces:
        return {'convex': False, 'closed': False, 'volume': 0.0, 'planes': []}
    origin = points[faces[0][0]]
    vol = 0.0
    for a, b, c in faces:
        vol += _dot(_sub(points[a], origin), _cross(_sub(points[b], origin), _sub(points[c], origin)))
    sign = 1.0 if vol >= 0 else -1.0
    planes, outside = [], 0
    for a, b, c in faces:
        n = _cross(_sub(points[b], points[a]), _sub(points[c], points[a]))
        ln = _len(n)
        if ln < 1e-12:
            continue
        n = (sign * n[0] / ln, sign * n[1] / ln, sign * n[2] / ln)
        planes.append((n, points[a]))
        if max(_dot(n, _sub(p, points[a])) for p in points) > tol:
            outside += 1
    directed = {}
    for a, b, c in faces:
        for e in ((a, b), (b, c), (c, a)):
            directed[e] = directed.get(e, 0) + 1
    open_edges = sum(1 for (a, b), k in directed.items() if k != 1 or directed.get((b, a)) != 1)
    return {'convex': outside == 0, 'closed': open_edges == 0, 'volume': abs(vol) / 6.0, 'planes': planes}


def outside_distance(info, p):
    """How far point p is outside the convex solid (0 when inside)."""
    return max(0.0, max((_dot(n, _sub(p, a)) for n, a in info['planes']), default=0.0))


def top_height(points, faces, x, y):
    """Highest z of the solid at (x, y), or None when the vertical line misses it."""
    best = None
    for a, b, c in faces:
        pa, pb, pc = points[a], points[b], points[c]
        d = (pb[1] - pc[1]) * (pa[0] - pc[0]) + (pc[0] - pb[0]) * (pa[1] - pc[1])
        if abs(d) < 1e-15:
            continue
        l1 = ((pb[1] - pc[1]) * (x - pc[0]) + (pc[0] - pb[0]) * (y - pc[1])) / d
        l2 = ((pc[1] - pa[1]) * (x - pc[0]) + (pa[0] - pc[0]) * (y - pc[1])) / d
        l3 = 1.0 - l1 - l2
        if min(l1, l2, l3) < -1e-9:
            continue
        z = l1 * pa[2] + l2 * pb[2] + l3 * pc[2]
        best = z if best is None else max(best, z)
    return best


# ---- the stair ---------------------------------------------------------------------------------------------
def run_direction(points):
    """Horizontal climbing direction: the one along which z grows (covariance of z with x and y). None when flat."""
    n = len(points)
    mx = sum(p[0] for p in points) / n
    my = sum(p[1] for p in points) / n
    mz = sum(p[2] for p in points) / n
    cx = sum((p[0] - mx) * (p[2] - mz) for p in points)
    cy = sum((p[1] - my) * (p[2] - mz) for p in points)
    ln = math.hypot(cx, cy)
    if ln < 1e-12:
        return None
    return (cx / ln, cy / ln)


def _upper_hull(pairs):
    """Upper convex hull of (s, z) pairs, left to right (monotone chain)."""
    pts = sorted(set(pairs))
    hull = []
    for p in pts:
        while len(hull) >= 2 and ((hull[-1][0] - hull[-2][0]) * (p[1] - hull[-2][1])
                                  - (hull[-1][1] - hull[-2][1]) * (p[0] - hull[-2][0])) > 1e-5:
            hull.pop()  # collinear points stay: every nosing of a straight flight is checked
        hull.append(p)
    while len(hull) >= 2 and hull[0][0] == hull[1][0]:
        hull.pop(0)  # the front riser: the nosing is its top, not its foot
    return hull


def nosings(points, d):
    """Nosing points of the stair: vertices on the upper (s, z) profile hull, without the last one (the back edge of
    the top tread is not a nosing). Returns [(x, y, z)] (every vertex of the hull vertices, across the width)."""
    pairs = [(round(p[0] * d[0] + p[1] * d[1], 6), round(p[2], 6)) for p in points]
    hull = _upper_hull(pairs)[:-1]
    keep = set(hull)
    return [p for p, pr in zip(points, pairs) if pr in keep]


def stair_options(options):
    o = dict(options or {})
    unknown = set(o) - {'tolerance_cm', 'stair_pattern'}
    if unknown:
        raise ValueError('unknown ucx.stairs options: ' + ', '.join(sorted(unknown)))
    tol = o.get('tolerance_cm', DEFAULT_TOLERANCE_CM)
    if isinstance(tol, bool) or tol not in TOLERANCES_CM:
        raise ValueError('tolerance_cm must be one of {}: {!r}'.format(TOLERANCES_CM, tol))
    pattern = o.get('stair_pattern', STAIR_PATTERN)
    re.compile(pattern)
    return {'tolerance_cm': tol, 'stair_pattern': pattern}


def is_stair_name(name, pattern=STAIR_PATTERN):
    return not str(name).upper().startswith('UCX_') and re.search(pattern, str(name)) is not None


def ucx_of(stair_name, nodes_names):
    """Names of the UCX nodes of a stair: `UCX_<stair name>` followed by nothing or `_<digits...>`."""
    prefix = 'UCX_' + str(stair_name)
    return [n for n in nodes_names if n == prefix or (n.startswith(prefix + '_') and n[len(prefix) + 1:].replace('_', '').isdigit())]


def finding(code, detail):
    return {'code': code, 'ids': [], 'detail': detail}


def evaluate_stair(stair, tol_m):
    """-> (findings [{code, ids, detail}], metrics dict) for one stair.

    stair: {'verts': [[x,y,z] m], 'tris': [[i,j,k]], 'ucx': [{'name', 'verts', 'tris'}]}."""
    points, faces = weld(stair['verts'], stair['tris'])
    metrics = {'nosings': 0, 'ucx_pieces': 0, 'ucx_parts': 0, 'max_outside_cm': None, 'max_excess_cm': None}
    d = run_direction(points) if points else None
    if d is None or max(p[2] for p in points) - min(p[2] for p in points) < MIN_RISE_M:
        return [], dict(metrics, skipped='нет подъёма: объект не похож на лестницу')
    noses = nosings(points, d)
    metrics['nosings'] = len(noses)
    if len(noses) < 2:
        return [], dict(metrics, skipped='меньше двух носков ступеней: нечего проверять')
    out = []
    pieces = stair.get('ucx') or []
    metrics['ucx_pieces'] = len(pieces)
    if not pieces:
        return [finding('ucx_missing', 'У лестницы нет UCX (ожидается UCX_<имя лестницы>).')], metrics
    solids = []  # (name, points, faces)
    for piece in pieces:
        pts, fcs = weld(piece['verts'], piece['tris'])
        for part in components(fcs):
            solids.append((piece['name'], pts, part))
    metrics['ucx_parts'] = len(solids)
    if len(solids) != 1:
        out.append(finding('ucx_not_single', 'UCX лестницы — {} тел вместо одной усечённой пирамиды (ступенька за ступенькой '
                                             'не допускается).'.format(len(solids))))
        return out, metrics
    name, pts, part = solids[0]
    info = solid_info(pts, part)
    if not info['closed']:
        out.append(finding('ucx_not_closed', 'UCX «{}» не замкнут: есть открытые рёбра.'.format(name)))
    if not info['convex']:
        out.append(finding('ucx_not_convex', 'UCX «{}» не выпуклый: нужна одна усечённая пирамида или призма.'.format(name)))
    if out:
        return out, metrics
    # vertical deviation of the top surface from every nosing (what "UCX 40 cm above the nosings" means); a nosing
    # that is not under the solid at all counts by its distance to the solid
    outside, excess = 0.0, 0.0
    for p in noses:
        h = top_height(pts, part, p[0], p[1])
        if h is None:
            outside = max(outside, outside_distance(info, p))
        else:
            outside = max(outside, p[2] - h)
            excess = max(excess, h - p[2])
    metrics['max_outside_cm'] = round(outside * 100.0, 1)
    metrics['max_excess_cm'] = round(excess * 100.0, 1)
    tol_cm = tol_m * 100.0
    if outside > tol_m + 1e-9:
        out.append(finding('stairs_outside', 'Носки ступеней выступают из UCX на {:.1f} см при допуске {:g} см.'.format(
            outside * 100.0, tol_cm)))
    if excess > tol_m + 1e-9:
        out.append(finding('ucx_too_high', 'UCX выше носков ступеней на {:.1f} см при допуске {:g} см.'.format(
            excess * 100.0, tol_cm)))
    return out, metrics


def ucx_stairs_report(edit, opts, rows, state_hash):
    """rows: [{'handle', 'name', 'findings', 'metrics'}] (findings from evaluate_stair); read-only report."""
    objects, skipped_, per = [], [], {}
    for r in rows:
        m = r['metrics']
        per[r['name']] = {k: v for k, v in m.items() if k != 'skipped'}
        if m.get('skipped'):
            skipped_.append(edit.skipped(r['name'], m['skipped']))
            continue
        objects.append(edit.entry(r['handle'], r['name'], r['findings']))
    if not rows:
        raise ValueError('no stairs to check: nothing matches ' + opts['stair_pattern'])
    done = [{'item': o['name'], 'result': 'pass'} for o in objects if not o['findings']]
    return edit.report(TOOL, 'preview', objects=objects, done=done, skipped_=skipped_, state_hash=state_hash,
                       extra={'tolerance_cm': opts['tolerance_cm'], 'stairs': len(rows), 'metrics': per})
