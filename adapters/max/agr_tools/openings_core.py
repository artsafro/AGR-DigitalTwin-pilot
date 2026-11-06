"""new-case: AGR Tools 1.0 (#1024) shared module openings logic, stdlib only; owned by branch J (improve/issue-1024-windows).

The ONE opening recognition of the conveyor (K1/K2): win.place (J), body.capsules (K) and npm.to_vpm (Q) read it.
Pure logic, no pymxs: the input is the HostAdapter.mesh() dict (world metres), so the same code runs on Max and,
later, on a Blender adapter.

Idea from Geo Window Placer (GeoAGR.ms:56719 borders, :56942-57025 opening frame; lab L10, docs/experiments/
win.place.md). The source frame is exact for flat rectangular openings with reveals; what the lab measured as
broken is rewritten here:

* outer facade contours were candidates, filtered only by size -> a border whose inside is covered by the mesh
  (sample segments across the border plane hit a face) is an outer contour and is rejected (`external`);
* arches were read as rectangles by their bounding box -> a loop is `rect` only when its area fills its frame
  rectangle (`rect_fill`) and it has 4 corners; otherwise `nonrect` (ambiguous);
* corner (L) openings got a diagonal frame -> a non-planar border on two vertical planes is `corner`, with one
  branch per wall plane;
* the frame normal pointed into the building (`:57001-57002` says outwards) -> z is the street side: from the
  border towards its reveal (the reveal leads from the window plane to the facade), or the face normals of the
  coplanar wall when there is no reveal;
* thresholds were system units -> everything here is metres (the host converts with units.SystemScale).
"""
import math

DEFAULTS = {
    'min_side_m': 0.1,     # a border with a side below this is not an opening
    'max_side_m': 12.0,    # a border with a side above this is an outer contour
    'max_depth_m': 1.0,    # reveal deeper than this: an outer contour (e.g. the bottom loop of a shell)
    'plane_tol_m': 0.002,  # a border is planar within this
    'weld_m': 0.0001,      # vertices closer than this are one vertex (snapshot meshes are not welded)
    'rect_fill': 0.985,    # area / frame rectangle area of a rectangular border
    'perp_cos': 0.17,      # |cos| below this: a face is perpendicular to the border plane (a reveal face)
    'ground_z_m': None,    # sill reference; default: the lowest vertex of the mesh
}
KINDS = ('rect', 'nonrect', 'corner', 'nonplanar')
UP = (0.0, 0.0, 1.0)


# ---- vectors -------------------------------------------------------------------------------------------------
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _len(a):
    return math.sqrt(_dot(a, a))


def _unit(a):
    n = _len(a)
    if n < 1e-12:
        raise ValueError('zero vector')
    return (a[0] / n, a[1] / n, a[2] / n)


def newell(points):
    """Area-weighted normal of a polygon (length = 2 x area)."""
    nx = ny = nz = 0.0
    for a, b in zip(points, points[1:] + points[:1]):
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    return (nx, ny, nz)


def check_options(options=None):
    opts = dict(DEFAULTS)
    for k, v in (options or {}).items():
        if k not in DEFAULTS:
            raise ValueError('unknown openings option: ' + repr(k))
        if k == 'ground_z_m' and v is None:
            opts[k] = None
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise ValueError('openings option {} must be a finite number: {!r}'.format(k, v))
        if k != 'ground_z_m' and v <= 0:
            raise ValueError('openings option {} must be > 0: {!r}'.format(k, v))
        opts[k] = float(v)
    if opts['rect_fill'] > 1:
        raise ValueError('rect_fill must be <= 1')
    return opts


# ---- topology ------------------------------------------------------------------------------------------------
def weld(verts, faces, tol):
    """Merge vertices within `tol` (grid key), drop degenerate faces. Returns (verts, faces, kept face index)."""
    key, out, remap = {}, [], []
    for p in verts:
        k = (round(p[0] / tol), round(p[1] / tol), round(p[2] / tol))
        if k not in key:
            key[k] = len(out)
            out.append(tuple(float(c) for c in p))
        remap.append(key[k])
    fs, kept = [], []
    for fi, f in enumerate(faces):
        ids = []
        for i in f:
            j = remap[i]
            if not ids or ids[-1] != j:
                ids.append(j)
        if len(ids) > 1 and ids[0] == ids[-1]:
            ids.pop()
        if len(set(ids)) >= 3:
            fs.append(ids)
            kept.append(fi)
    return out, fs, kept


def boundary_loops(faces):
    """Closed chains of the edges used by exactly one face, in the direction of that face.

    Returns [(vertex loop, [face index per loop edge])]. A pinch vertex (two loops through it) is resolved by
    taking the outgoing edge that turns least; each edge is used once."""
    count, owner = {}, {}
    for fi, f in enumerate(faces):
        for a, b in zip(f, f[1:] + f[:1]):
            k = (a, b) if a < b else (b, a)
            count[k] = count.get(k, 0) + 1
            owner[(a, b)] = fi
    out_edges = {}
    for (a, b), fi in owner.items():
        k = (a, b) if a < b else (b, a)
        if count[k] == 1:
            out_edges.setdefault(a, []).append(b)
    used, loops = set(), []
    for start in sorted(out_edges):
        for first in sorted(out_edges[start]):
            if (start, first) in used:
                continue
            loop, fl = [start], []
            a, b = start, first
            ok = True
            while True:
                used.add((a, b))
                fl.append(owner[(a, b)])
                if b == start:
                    break
                loop.append(b)
                nxt = [c for c in out_edges.get(b, ()) if (b, c) not in used]
                if not nxt:
                    ok = False
                    break
                a, b = b, nxt[0]
                if len(loop) > len(owner) + 1:
                    ok = False
                    break
            if ok and len(loop) >= 3:
                loops.append((loop, fl))
    return loops


def face_normal(verts, f):
    n = newell([verts[i] for i in f])
    ln = _len(n)
    return (n[0] / ln, n[1] / ln, n[2] / ln) if ln > 1e-15 else (0.0, 0.0, 0.0)


def _triangles(verts, faces, idx):
    for fi in idx:
        f = faces[fi]
        p0 = verts[f[0]]
        for i in range(1, len(f) - 1):
            yield p0, verts[f[i]], verts[f[i + 1]]


def segment_hits(p, q, tris):
    """Does the segment p..q cross one of the triangles (Moller-Trumbore, both sides)?"""
    d = _sub(q, p)
    for a, b, c in tris:
        e1, e2 = _sub(b, a), _sub(c, a)
        h = _cross(d, e2)
        det = _dot(e1, h)
        if abs(det) < 1e-14:
            continue
        inv = 1.0 / det
        s = _sub(p, a)
        u = _dot(s, h) * inv
        if u < -1e-9 or u > 1 + 1e-9:
            continue
        qv = _cross(s, e1)
        v = _dot(d, qv) * inv
        if v < -1e-9 or u + v > 1 + 1e-9:
            continue
        t = _dot(e2, qv) * inv
        if -1e-9 <= t <= 1 + 1e-9:
            return True
    return False


# ---- frames --------------------------------------------------------------------------------------------------
def frame_axes(z):
    """x along the wall (right as seen from the street), y up in the plane, z = the given outward normal."""
    z = _unit(z)
    y = _sub(UP, _mul(z, _dot(UP, z)))
    if _len(y) < 0.1:  # a horizontal border (skylight): y follows world Y
        w = (0.0, 1.0, 0.0)
        y = _sub(w, _mul(z, _dot(w, z)))
    y = _unit(y)
    x = _unit(_cross(y, z))
    return x, y, z


def _to2d(points, origin, x, y):
    return [(_dot(_sub(p, origin), x), _dot(_sub(p, origin), y)) for p in points]


def _area2d(poly):
    s = 0.0
    for a, b in zip(poly, poly[1:] + poly[:1]):
        s += a[0] * b[1] - b[0] * a[1]
    return s / 2.0


def _inside2d(pt, poly):
    x, y = pt
    inside = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y):
            xc = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if xc > x:
                inside = not inside
    return inside


def corners2d(poly, tol_deg=2.0):
    """Vertices of a 2D polygon where the direction turns by more than tol_deg (collinear points dropped)."""
    out = []
    n = len(poly)
    for i in range(n):
        a, b, c = poly[i - 1], poly[i], poly[(i + 1) % n]
        u = (b[0] - a[0], b[1] - a[1])
        v = (c[0] - b[0], c[1] - b[1])
        lu, lv = math.hypot(*u), math.hypot(*v)
        if lu < 1e-9 or lv < 1e-9:
            continue
        cosang = (u[0] * v[0] + u[1] * v[1]) / (lu * lv)
        if cosang < math.cos(math.radians(tol_deg)):
            out.append(b)
    return out


# ---- one border ----------------------------------------------------------------------------------------------
class _Mesh:
    def __init__(self, mesh, opts):
        raw_v = mesh.get('verts') or []
        raw_f = mesh.get('faces') or []
        self.verts, self.faces, _ = weld(raw_v, raw_f, opts['weld_m'])
        self.normals = [face_normal(self.verts, f) for f in self.faces]
        self.adj = {}
        for fi, f in enumerate(self.faces):
            for a, b in zip(f, f[1:] + f[:1]):
                self.adj.setdefault((a, b) if a < b else (b, a), []).append(fi)
        self.boxes = []
        for f in self.faces:
            ps = [self.verts[i] for i in f]
            self.boxes.append((tuple(min(p[k] for p in ps) for k in range(3)),
                               tuple(max(p[k] for p in ps) for k in range(3))))

    def near(self, lo, hi):
        return [fi for fi, (a, b) in enumerate(self.boxes)
                if all(a[k] <= hi[k] and b[k] >= lo[k] for k in range(3))]


def _reveal(m, loop_faces, n, origin, extent, opts):
    """(signed depth along n, side) of the reveal behind a planar border, BFS over faces perpendicular to n
    starting at the faces of the border edges, kept within the border's frame (+5 cm). side: +1 / -1, or 0 if the
    border faces are not perpendicular (no reveal)."""
    perp = opts['perp_cos']
    seeds = [fi for fi in set(loop_faces) if abs(_dot(m.normals[fi], n)) < perp]
    if not seeds:
        return 0.0, 0
    seen, todo, ds = set(seeds), list(seeds), []
    x, y, _ = frame_axes(n)
    (x0, x1), (y0, y1) = extent
    while todo:
        fi = todo.pop()
        f = m.faces[fi]
        for i in f:
            ds.append(_dot(_sub(m.verts[i], origin), n))
        for a, b in zip(f, f[1:] + f[:1]):
            for g in m.adj.get((a, b) if a < b else (b, a), ()):
                if g in seen or abs(_dot(m.normals[g], n)) >= perp:
                    continue
                pts = _to2d([m.verts[i] for i in m.faces[g]], origin, x, y)
                if all(x0 - 0.05 <= u <= x1 + 0.05 and y0 - 0.05 <= v <= y1 + 0.05 for u, v in pts):
                    seen.add(g)
                    todo.append(g)
    hi, lo = max(ds), min(ds)
    if hi <= 1e-6 and lo >= -1e-6:
        return 0.0, 0
    return (hi, 1) if hi >= -lo else (-lo, -1)


def _covered(m, origin, x, y, z, poly, extent, depth):
    """Is the inside of the border covered by the mesh between the border plane and the facade? Sample points
    inside the polygon (5x5 grid, 8 % inset), segments from 5 mm behind the plane to 5 mm beyond the reveal."""
    (x0, x1), (y0, y1) = extent
    eps = 0.005
    lo_pts, samples = [], []
    for i in range(5):
        for j in range(5):
            u = x0 + (x1 - x0) * (0.08 + 0.84 * i / 4.0)
            v = y0 + (y1 - y0) * (0.08 + 0.84 * j / 4.0)
            if _inside2d((u, v), poly):
                samples.append(_add(origin, _add(_mul(x, u), _mul(y, v))))
    if not samples:
        return False
    for p in samples:
        lo_pts.append(_sub(p, _mul(z, eps)))
        lo_pts.append(_add(p, _mul(z, depth + eps)))
    lo = tuple(min(p[k] for p in lo_pts) - 1e-6 for k in range(3))
    hi = tuple(max(p[k] for p in lo_pts) + 1e-6 for k in range(3))
    tris = list(_triangles(m.verts, m.faces, m.near(lo, hi)))
    return any(segment_hits(_sub(p, _mul(z, eps)), _add(p, _mul(z, depth + eps)), tris) for p in samples)


def _side_from_faces(m, loop_faces, n):
    s = sum(_dot(m.normals[fi], n) for fi in set(loop_faces))
    return 1 if s >= 0 else -1


def _planar(m, loop, loop_faces, opts):
    pts = [m.verts[i] for i in loop]
    nn = newell(pts)
    if _len(nn) < 1e-12:
        return None, 'degenerate border (zero area)'
    n = _unit(nn)
    c = _mul(pts[0], 0.0)
    for p in pts:
        c = _add(c, p)
    c = _mul(c, 1.0 / len(pts))
    off = max(abs(_dot(_sub(p, c), n)) for p in pts)
    if off > opts['plane_tol_m']:
        return None, 'border is not planar ({:.1f} mm off its plane)'.format(off * 1000)
    x, y, _ = frame_axes(n)
    poly = _to2d(pts, c, x, y)
    extent = ((min(u for u, _ in poly), max(u for u, _ in poly)), (min(v for _, v in poly), max(v for _, v in poly)))
    depth, side = _reveal(m, loop_faces, n, c, extent, opts)
    if side == 0:
        side = _side_from_faces(m, loop_faces, n)
    z = _mul(n, side)
    x, y, z = frame_axes(z)
    poly = _to2d(pts, c, x, y)
    (u0, u1), (v0, v1) = ((min(u for u, _ in poly), max(u for u, _ in poly)),
                          (min(v for _, v in poly), max(v for _, v in poly)))
    origin = _add(c, _add(_mul(x, (u0 + u1) / 2.0), _mul(y, (v0 + v1) / 2.0)))
    poly = _to2d(pts, origin, x, y)
    hw, hh = (u1 - u0) / 2.0, (v1 - v0) / 2.0
    return {'pts': pts, 'origin': origin, 'x': x, 'y': y, 'z': z, 'poly': poly, 'w': u1 - u0, 'h': v1 - v0,
            'extent': ((-hw, hw), (-hh, hh)), 'depth': depth}, None


def _corner(m, loop, loop_faces, opts):
    """Two vertical wall planes: horizontal border edges in two plan directions (> 20 deg apart)."""
    pts = [m.verts[i] for i in loop]
    n = len(pts)
    dirs = []
    for k in range(n):
        a, b = pts[k], pts[(k + 1) % n]
        d = _sub(b, a)
        lh = math.hypot(d[0], d[1])
        if lh > 1e-4 and abs(d[2]) <= 1e-3 * max(lh, 1e-9):
            dirs.append((k, math.degrees(math.atan2(d[1], d[0])) % 180.0, lh))
    if not dirs:
        return None
    clusters = []
    for k, ang, lh in sorted(dirs, key=lambda t: -t[2]):
        for cl in clusters:
            dd = abs(cl['ang'] - ang) % 180.0
            if min(dd, 180.0 - dd) <= 2.0:
                cl['edges'].append(k)
                break
        else:
            clusters.append({'ang': ang, 'edges': [k]})
    if len(clusters) != 2:
        return None
    dd = abs(clusters[0]['ang'] - clusters[1]['ang']) % 180.0
    if min(dd, 180.0 - dd) < 20.0:
        return None
    branches = []
    for cl in clusters:
        idx = sorted({k for k in cl['edges']} | {(k + 1) % n for k in cl['edges']})
        bp = [pts[i] for i in idx]
        a = math.radians(cl['ang'])
        d = (math.cos(a), math.sin(a), 0.0)
        nrm = (d[1], -d[0], 0.0)
        c = _mul(bp[0], 0.0)
        for p in bp:
            c = _add(c, p)
        c = _mul(c, 1.0 / len(bp))
        off = max(abs(_dot(_sub(p, c), nrm)) for p in bp)
        if off > opts['plane_tol_m'] * 5:
            return None
        bf = [loop_faces[k] for k in cl['edges']]
        x, y, _ = frame_axes(nrm)
        poly = _to2d(bp, c, x, y)
        extent = ((min(u for u, _ in poly), max(u for u, _ in poly)), (min(v for _, v in poly), max(v for _, v in poly)))
        depth, side = _reveal(m, bf, nrm, c, extent, opts)
        if side == 0:
            side = _side_from_faces(m, bf, nrm)
        x, y, z = frame_axes(_mul(nrm, side))
        poly = _to2d(bp, c, x, y)
        (u0, u1), (v0, v1) = ((min(u for u, _ in poly), max(u for u, _ in poly)),
                              (min(v for _, v in poly), max(v for _, v in poly)))
        origin = _add(c, _add(_mul(x, (u0 + u1) / 2.0), _mul(y, (v0 + v1) / 2.0)))
        hw, hh = (u1 - u0) / 2.0, (v1 - v0) / 2.0
        rect = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        branches.append({'origin': origin, 'x': x, 'y': y, 'z': z, 'w': u1 - u0, 'h': v1 - v0, 'depth': depth,
                         'poly': rect, 'extent': ((-hw, hw), (-hh, hh))})
    branches.sort(key=lambda b: -b['w'])
    return branches


def _vec(v):
    return [round(float(c), 9) for c in v]


def _frame(f):
    return {'origin': _vec(f['origin']), 'x': _vec(f['x']), 'y': _vec(f['y']), 'z': _vec(f['z'])}


def find_openings_report(mesh, options=None):
    """find_openings plus the rejected borders: {'openings': [...], 'rejected': [{'centre', 'why'}]}."""
    opts = check_options(options)
    m = _Mesh(mesh, opts)
    ref = mesh.get('ref') or {}
    wall = str(ref.get('name') or 'mesh')
    if not m.verts:
        return {'openings': [], 'rejected': []}
    ground = opts['ground_z_m'] if opts['ground_z_m'] is not None else min(p[2] for p in m.verts)
    found, rejected = [], []
    for loop, loop_faces in boundary_loops(m.faces):
        pts = [m.verts[i] for i in loop]
        centre = _vec(_mul(_add(_mul(pts[0], 0.0), tuple(sum(p[k] for p in pts) for k in range(3))), 1.0 / len(pts)))
        border = [_vec(p) for p in pts]
        bottom = min(p[2] for p in pts)
        fr, why = _planar(m, loop, loop_faces, opts)
        if fr is not None:
            w, h = fr['w'], fr['h']
            if min(w, h) < opts['min_side_m']:
                rejected.append({'centre': centre, 'why': 'side {:.3f} m below min_side_m'.format(min(w, h))})
                continue
            if max(w, h) > opts['max_side_m']:
                rejected.append({'centre': centre, 'why': 'external: side {:.3f} m above max_side_m'.format(max(w, h))})
                continue
            if fr['depth'] > opts['max_depth_m']:
                rejected.append({'centre': centre, 'why': 'external: reveal {:.3f} m deeper than max_depth_m'.format(
                    fr['depth'])})
                continue
            if _covered(m, fr['origin'], fr['x'], fr['y'], fr['z'], fr['poly'], fr['extent'], fr['depth']):
                rejected.append({'centre': centre, 'why': 'external: the inside of the border is covered by the mesh'})
                continue
            area = abs(_area2d(fr['poly']))
            fill = area / (w * h) if w * h > 0 else 0.0
            ncorners = len(corners2d(fr['poly']))
            rect = fill >= opts['rect_fill'] and ncorners == 4
            item = {'border': border, 'frame': _frame(fr), 'w': round(w, 6), 'h': round(h, 6),
                    'sill': round(bottom - ground, 6), 'depth': round(fr['depth'], 6), 'wall': wall,
                    'corner': False, 'kind': 'rect' if rect else 'nonrect', 'status': 'ok' if rect else 'ambiguous',
                    'why': [] if rect else ['not a rectangle: fills {:.1%} of its frame, {} corners'.format(
                        fill, ncorners)], 'fill': round(fill, 4)}
            found.append(item)
            continue
        branches = _corner(m, loop, loop_faces, opts)
        if branches:
            if any(max(b['w'], b['h']) > opts['max_side_m'] for b in branches):
                rejected.append({'centre': centre, 'why': 'external: corner border larger than max_side_m'})
                continue
            if any(b['depth'] > opts['max_depth_m'] for b in branches):
                rejected.append({'centre': centre, 'why': 'external: corner reveal deeper than max_depth_m'})
                continue
            if any(_covered(m, b['origin'], b['x'], b['y'], b['z'], b['poly'], b['extent'], b['depth'])
                   for b in branches):
                rejected.append({'centre': centre, 'why': 'external: the inside of the corner border is covered'})
                continue
            b0 = branches[0]
            found.append({'border': border, 'frame': _frame(b0), 'w': round(sum(b['w'] for b in branches), 6),
                          'h': round(max(b['h'] for b in branches), 6), 'sill': round(bottom - ground, 6),
                          'depth': round(max(b['depth'] for b in branches), 6), 'wall': wall, 'corner': True,
                          'kind': 'corner', 'status': 'ambiguous',
                          'why': ['corner opening on two wall planes ({} + {} m)'.format(
                              round(branches[0]['w'], 3), round(branches[1]['w'], 3))],
                          'branches': [dict(_frame(b), w=round(b['w'], 6), h=round(b['h'], 6),
                                            depth=round(b['depth'], 6)) for b in branches], 'fill': None})
            continue
        if max(max(p[k] for p in pts) - min(p[k] for p in pts) for k in range(3)) > opts['max_side_m']:
            rejected.append({'centre': centre, 'why': 'external: non-planar border larger than max_side_m'})
            continue
        found.append({'border': border, 'frame': None, 'w': None, 'h': None, 'sill': round(bottom - ground, 6),
                      'depth': None, 'wall': wall, 'corner': False, 'kind': 'nonplanar', 'status': 'ambiguous',
                      'why': [why], 'fill': None})
    found.sort(key=lambda o: tuple(round(c, 3) for c in (o['frame']['origin'] if o['frame'] else o['border'][0])))
    for i, o in enumerate(found, 1):
        o['id'] = i
    rejected.sort(key=lambda r: tuple(round(c, 3) for c in r['centre']))
    return {'openings': found, 'rejected': rejected}


def find_openings(mesh, options=None):
    """The ONE opening recognition (K1/K2), read by win.place (J), body.capsules (K) and npm.to_vpm (Q).

    mesh: contract_core HostAdapter.mesh() dict {'verts': [[x, y, z]...] metres world, 'faces': [[i...]...],
    'mat_ids': [...], 'ref': ObjRef}. options: DEFAULTS (metres).
    Returns [{'id': int, 'border': [[x, y, z]...] metres, 'frame': {'origin': [x, y, z], 'x': [..], 'y': [..],
    'z': [..]} (z = wall normal outwards), 'w': m, 'h': m, 'sill': m, 'depth': m, 'wall': ObjRef['name'],
    'corner': bool}]: the fields of the agr_opening marker (contract_core.OPENING_FIELDS) plus border and frame.
    Extra keys: kind (rect | nonrect | corner | nonplanar), status (ok | ambiguous), why [str], fill; a corner
    opening has `branches` (one frame per wall plane, the longer first; frame = branches[0], w = their sum); a
    non-planar one has frame/w/h/depth None. Outer contours are not returned (find_openings_report lists them)."""
    return find_openings_report(mesh, options)['openings']


def marker_fields(opening):
    """The agr_opening marker dict (contract_core.OPENING_FIELDS) of a found opening; None if it has no frame."""
    if not opening.get('frame') or not opening.get('w') or not opening.get('h'):
        return None
    return {'w': round(opening['w'], 4), 'h': round(opening['h'], 4), 'sill': round(max(opening['sill'], 0.0), 4),
            'depth': round(max(opening['depth'] or 0.0, 0.0001), 4), 'wall': opening['wall'],
            'corner': bool(opening['corner'])}
