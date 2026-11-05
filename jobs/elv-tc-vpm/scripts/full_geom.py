"""elv-tc-vpm full building: extra pure-Python helpers on top of pilot_geom (no bpy).

MB4      - MB welding on a 0.1 mm grid (the pilot mesh comes back from Blender in float32; 0.1 mm keys weld it to the
           new parts' exact coordinates; positions move <= 0.05 mm).
wall     - vertical rectangle between two plan points, split <= 3.9 m.
hgrid    - horizontal polygon filled by a grid of <= 3.9 m cells clipped to the polygon (Sutherland-Hodgman, convex cell
           window, any simple polygon), material chosen per cell centre.
obox     - oriented box along a segment (ladders, rails, rafters, lights on a skewed wall).
"""
import math
from pilot_geom import MB, E


class MB4(MB):
    def v(self, p):
        k = (round(p[0], 4), round(p[1], 4), round(p[2], 4))
        i = self.vidx.get(k)
        if i is None:
            i = len(self.verts)
            self.verts.append(k)
            self.vidx[k] = i
        return i


def lin(a, b, maxlen=3.9):
    k = max(1, math.ceil(abs(b - a) / maxlen - 1e-9))
    return [a + (b - a) * i / k for i in range(k + 1)]


def wall(mb, a, b, z0, z1, mat, part, normal, maxlen=3.9):
    """vertical rectangle a->b (plan points) z0..z1, normal = plan normal (nx, ny)"""
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    if L < 1e-6 or z1 - z0 < 1e-6:
        return
    ts = lin(0.0, 1.0, maxlen / L)
    zs = lin(z0, z1, maxlen)
    for t0, t1 in zip(ts, ts[1:]):
        p0 = (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0)
        p1 = (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)
        for za, zb in zip(zs, zs[1:]):
            mb.face([(p0[0], p0[1], za), (p1[0], p1[1], za), (p1[0], p1[1], zb), (p0[0], p0[1], zb)], mat, part,
                    (normal[0], normal[1], 0.0))


def hrect(mb, x0, x1, y0, y1, z, mat, part, up=True, maxlen=3.9):
    X, Y = lin(x0, x1, maxlen), lin(y0, y1, maxlen)
    for a, b in zip(X, X[1:]):
        for c, d in zip(Y, Y[1:]):
            mb.face([(a, c, z), (b, c, z), (b, d, z), (a, d, z)], mat, part, (0, 0, 1 if up else -1))


def clip_rect(poly, x0, x1, y0, y1):
    def clip(pts, inside, inter):
        out = []
        for i in range(len(pts)):
            p, q = pts[i - 1], pts[i]
            ip, iq = inside(p), inside(q)
            if iq:
                if not ip:
                    out.append(inter(p, q))
                out.append(q)
            elif ip:
                out.append(inter(p, q))
        return out

    def ix(x):
        return lambda p, q: (x, p[1] + (q[1] - p[1]) * (x - p[0]) / (q[0] - p[0]))

    def iy(y):
        return lambda p, q: (p[0] + (q[0] - p[0]) * (y - p[1]) / (q[1] - p[1]), y)
    pts = list(poly)
    for inside, inter in ((lambda p: p[0] >= x0 - 1e-9, ix(x0)), (lambda p: p[0] <= x1 + 1e-9, ix(x1)),
                          (lambda p: p[1] >= y0 - 1e-9, iy(y0)), (lambda p: p[1] <= y1 + 1e-9, iy(y1))):
        if not pts:
            break
        pts = clip(pts, inside, inter)
    # drop duplicates
    out = []
    for p in pts:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1e-7:
            out.append(p)
    if len(out) > 1 and math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) < 1e-7:
        out.pop()
    return out


def area2(pts):
    return sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(pts, pts[1:] + pts[:1])) / 2


def grid_lines(vals, maxlen=3.9):
    vals = sorted(set(round(v, 6) for v in vals))
    out = [vals[0]]
    for a, b in zip(vals, vals[1:]):
        if b - a < 1e-4:
            continue
        out += lin(a, b, maxlen)[1:]
    return out


def hgrid(mb, poly, z, matfn, part, extra_x=(), extra_y=(), up=True, maxlen=3.9, skipfn=None):
    """fill a simple polygon at height z; matfn(cx, cy) -> material id; skipfn(cx, cy) -> True drops the cell"""
    X = grid_lines([p[0] for p in poly] + list(extra_x), maxlen)
    Y = grid_lines([p[1] for p in poly] + list(extra_y), maxlen)
    n = 0
    for a, b in zip(X, X[1:]):
        for c, d in zip(Y, Y[1:]):
            pc = clip_rect(poly, a, b, c, d)
            if len(pc) < 3 or abs(area2(pc)) < 1e-6:
                continue
            cx = sum(p[0] for p in pc) / len(pc)
            cy = sum(p[1] for p in pc) / len(pc)
            if skipfn and skipfn(cx, cy):
                continue
            mb.face([(p[0], p[1], z) for p in pc], matfn(cx, cy), part, (0, 0, 1 if up else -1))
            n += 1
    return n


def _norm(v):
    L = math.sqrt(sum(c * c for c in v))
    return tuple(c / L for c in v)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def obox(mb, p0, p1, side, w, h, mat, part, skip=(), maxlen=3.9):
    """box along the centre line p0 -> p1; cross-section w along 'side' (unit, perpendicular to the axis) and h along
    up = axis x side. skip: any of 'start', 'end', '+s', '-s', '+u', '-u'"""
    ax = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
    L = math.sqrt(sum(c * c for c in ax))
    a = _norm(ax)
    s = _norm(side)
    u = _norm(_cross(a, s))
    ts = lin(0.0, L, maxlen)

    def P(t, ss, uu):
        return tuple(p0[i] + a[i] * t + s[i] * ss * w / 2 + u[i] * uu * h / 2 for i in range(3))
    sides = {"+s": ((1, -1), (1, 1), s), "-s": ((-1, 1), (-1, -1), tuple(-c for c in s)),
             "+u": ((1, 1), (-1, 1), u), "-u": ((-1, -1), (1, -1), tuple(-c for c in u))}
    for k, (c0, c1, nrm) in sides.items():
        if k in skip:
            continue
        for t0, t1 in zip(ts, ts[1:]):
            mb.face([P(t0, *c0), P(t1, *c0), P(t1, *c1), P(t0, *c1)], mat, part, nrm)
    if "start" not in skip:
        mb.face([P(0, -1, -1), P(0, 1, -1), P(0, 1, 1), P(0, -1, 1)], mat, part, tuple(-c for c in a))
    if "end" not in skip:
        mb.face([P(L, -1, -1), P(L, 1, -1), P(L, 1, 1), P(L, -1, 1)], mat, part, a)
