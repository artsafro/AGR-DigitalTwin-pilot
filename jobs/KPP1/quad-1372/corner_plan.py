"""new-case: KPP1 quad master corners as separate clean elements (#1609): pure planning kernel, no Blender.

Artem 2026-11-16: the v003 corners were rejected because everything was welded into ONE mesh and the rules
were forced onto it. Decision (same day): posts (стойки) are geometry - separate inset elements with clean quads,
not welded into the body; panels are texture with a seam; windows/roof/flashings inset. This module plans:

1. `wall_strip` - the body wall strip at a building corner to re-mesh: a rectangle [0, S] x [z0, z1] in wall
   coordinates (s = distance from the corner along the wall) that is exactly a union of whole wall faces (no
   face crosses its border, no opening inside), largest area for S in [s_min, s_max].
2. `grid_lines` - clean rows / columns for that rectangle: the border, every finish (UDIM tile) change, then
   even splits to <= `step` (no line closer than `min_gap` to another: no sliver rows).
3. `post_cells` - the posts as a voxel set on the snapped global x/y/z lines of the R1 post triangles (inside =
   odd ray parity in two directions, both must agree), and `post_faces` - its boundary quads (conforming, one
   clean element), minus faces lying on the body wall that face into the body (hidden contact, would overlap).
4. `affine_uv` - exact planar UV map of a source face, used to give every new corner the source UV.

Every failure is an error naming the corner/wall/face; nothing falls back to a default.
"""
import math

TOL = 2e-5          # = twinqa.look.TJUNCTION_TOL_M [D200]
MERGE_M = 1e-4      # two required grid lines this close are one line
SNAP_M = 6e-4       # R1 post planes 0.3-0.4 mm apart (e.g. -15.0753 / -15.075, -5.6854 / -5.685) are one plane


def snap_values(values, tol=SNAP_M, prefer=()):
    """Cluster sorted values within `tol` (chain); each cluster maps to a preferred value inside it, else its
    rounded mean. Returns (sorted representatives, {value: representative})."""
    vals = sorted(set(values) | set(prefer))
    if not vals:
        return [], {}
    for v in vals:
        if not math.isfinite(v):
            raise ValueError(f'non-finite coordinate {v!r}')
    clusters, cur = [], [vals[0]]
    for v in vals[1:]:
        if v - cur[-1] <= tol:
            cur.append(v)
        else:
            clusters.append(cur)
            cur = [v]
    clusters.append(cur)
    reps, mapping = [], {}
    for c in clusters:
        pref = [p for p in prefer if c[0] - 1e-12 <= p <= c[-1] + 1e-12]
        if len(pref) > 1:
            raise ValueError(f'preferred values {pref} fall into one {tol} m cluster')
        r = pref[0] if pref else round(sum(c) / len(c), 4)
        reps.append(r)
        for v in c:
            mapping[v] = r
    return reps, mapping


def _area(poly):
    return abs(sum(poly[i][0] * poly[i - 1][1] - poly[i - 1][0] * poly[i][1] for i in range(len(poly)))) / 2


def wall_strip(faces, s_min, s_max, z_min=-math.inf, z_max=math.inf, tol=TOL):
    """faces: [(poly [(s, z), ...], tile)], the wall-plane faces near one corner (s >= 0 on the wall).
    Returns {'S', 'z0', 'z1', 'faces': [indices fully inside]} of the largest valid rectangle, or raises."""
    if not faces:
        raise ValueError('no wall faces')
    boxes = []
    for poly, _ in faces:
        if len(poly) < 3 or any(not (math.isfinite(s) and math.isfinite(z)) for s, z in poly):
            raise ValueError(f'bad wall face {poly!r}')
        ss, zs = [p[0] for p in poly], [p[1] for p in poly]
        if min(ss) < -tol:
            raise ValueError(f'wall face beyond the corner: {poly!r}')
        boxes.append((min(ss), max(ss), min(zs), max(zs), _area(poly)))
    s_cands = sorted({round(b[1], 6) for b in boxes if s_min - tol <= b[1] <= s_max + tol})
    best = None
    for S in s_cands:
        cols = [b for b in boxes if b[0] < S - tol]           # faces touching the strip columns
        cross = [b for b in cols if b[1] > S + tol]           # crossing the s = S line
        z_cands = sorted({round(z, 6) for b in cols for z in (b[2], b[3]) if z_min - tol <= z <= z_max + tol})
        for i, z0 in enumerate(z_cands):
            for z1 in z_cands[i + 1:]:
                if any(b[2] < z1 - tol and b[3] > z0 + tol for b in cross):
                    continue
                inside, ok = [], True
                for k, b in enumerate(boxes):
                    if b[0] < S - tol and b[2] < z1 - tol and b[3] > z0 + tol:
                        if b[1] > S + tol or b[2] < z0 - tol or b[3] > z1 + tol:
                            ok = False
                            break
                        inside.append(k)
                if not ok:
                    continue
                area = S * (z1 - z0)
                if abs(sum(boxes[k][4] for k in inside) - area) > 1e-6 + 1e-5 * area:
                    continue                                   # an opening or a missing face inside
                if best is None or area > best[0] + 1e-9:
                    best = (area, S, z0, z1, inside)
    if best is None:
        raise ValueError('no rectangle of whole wall faces with full coverage')
    return {'S': best[1], 'z0': best[2], 'z1': best[3], 'faces': best[4]}


def clip_area(poly, s0, s1, z0, z1):
    """Area of a polygon [(s, z)] clipped to the rectangle (Sutherland-Hodgman)."""
    pts = list(poly)
    for axis, val, keep_ge in ((0, s0, True), (0, s1, False), (1, z0, True), (1, z1, False)):
        out = []
        for i in range(len(pts)):
            p, q = pts[i - 1], pts[i]
            pin = p[axis] >= val if keep_ge else p[axis] <= val
            qin = q[axis] >= val if keep_ge else q[axis] <= val
            if qin:
                if not pin:
                    t = (val - p[axis]) / (q[axis] - p[axis])
                    out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
                out.append(q)
            elif pin:
                t = (val - p[axis]) / (q[axis] - p[axis])
                out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
        pts = out
        if not pts:
            return 0.0
    return _area(pts) if len(pts) >= 3 else 0.0


def cut_kind(poly, S, tol=TOL):
    """How the vertical line s = S meets a face: 'left' / 'right' (no cut), 'clean' (a quad cut through two
    opposite edges -> two quads), 'bad' (through a corner or adjacent edges -> a triangle / pentagon)."""
    side = [(-1 if p[0] < S - tol else (1 if p[0] > S + tol else 0)) for p in poly]
    if all(x <= 0 for x in side):
        return 'left'
    if all(x >= 0 for x in side):
        return 'right'
    if 0 in side or len(poly) != 4:
        return 'bad'
    crossed = [i for i in range(4) if side[i] != side[(i + 1) % 4]]
    return 'clean' if len(crossed) == 2 and (crossed[1] - crossed[0]) == 2 else 'bad'


def strip_kind(poly, S, z0, z1, tol=TOL):
    """`cut_kind`, and a clean cut through the strip's top / bottom border edge is 'bad' (the face beyond would split)."""
    kd = cut_kind(poly, S, tol)
    if kd == 'clean':
        for i in range(4):
            a, b = poly[i], poly[(i + 1) % 4]
            if (a[0] - S) * (b[0] - S) < 0 and any(abs(a[1] - z) <= tol and abs(b[1] - z) <= tol for z in (z0, z1)):
                return 'bad'
    return kd


def lone_corner(poly, S, tol=TOL):
    """Index of the corner alone on its side of s = S in a badly cut quad/triangle (the one to snap onto the line),
    or None."""
    side = [(-1 if p[0] < S - tol else (1 if p[0] > S + tol else 0)) for p in poly]
    lone = [i for i, x in enumerate(side) if x != 0 and side.count(x) == 1]
    if not lone:
        return None
    return min(lone, key=lambda i: abs(poly[i][0] - S))


def strip_cut(faces, z0, z1, s_min, s_max, target, step=1e-3, tol=TOL, allow_bad=False, can_snap=None):
    """Plan the wall strip [0, S] x [z0, z1] with S cut through faces where needed. faces: [poly [(s, z)]] of the
    wall near the corner. z0 / z1 must already be face borders inside [0, s_max] (no face straddles them) and the
    strip must be covered by wall faces (no opening). S minimises (bad cuts, cuts, |S - target|).
    Returns {'S', 'cut': [face indices cut cleanly], 'inside': [face indices left of S]} or raises.
    `can_snap(k, i, S)`: the lone corner i of badly cut face k can move onto the line (the caller snaps it); such
    faces rank as 'fixable', after the unfixable ones (`allow_bad` returns the best S with its 'bad' count)."""
    if not faces:
        raise ValueError('no wall faces')
    if not all(math.isfinite(v) for v in (z0, z1, s_min, s_max, target)) or z1 - z0 <= tol or s_max <= s_min:
        raise ValueError(f'bad strip bounds z {z0}..{z1}, s {s_min}..{s_max}')
    band = []
    for k, poly in enumerate(faces):
        if any(not (math.isfinite(a) and math.isfinite(b)) for a, b in poly):
            raise ValueError(f'non-finite wall face {k}')
        zs = [p[1] for p in poly]
        if min(zs) < z1 - tol and max(zs) > z0 + tol:
            if min(zs) < z0 - tol or max(zs) > z1 + tol:
                if min(p[0] for p in poly) < s_max - tol:
                    raise ValueError(f'wall face {k} straddles z0 {z0} / z1 {z1}: {poly}')
                continue
            band.append(k)
    cands = sorted({round(s_min + i * step, 6) for i in range(int((s_max - s_min) / step) + 1)}
                   | {round(p[0], 6) for k in band for p in faces[k] if s_min <= p[0] <= s_max})
    best = None
    for S in cands:
        kinds = {k: strip_kind(faces[k], S, z0, z1, tol) for k in band}
        fixable = 0
        if can_snap is not None:
            for k, v in kinds.items():
                if v == 'bad':
                    i = lone_corner(faces[k], S, tol)
                    if i is not None and can_snap(k, i, S):
                        fixable += 1
        bad = sum(1 for v in kinds.values() if v == 'bad') - fixable
        cut = [k for k, v in kinds.items() if v == 'clean']
        area = sum(clip_area(faces[k], 0.0, S, z0, z1) for k in band)
        if abs(area - S * (z1 - z0)) > 1e-6 + 1e-5 * S * (z1 - z0):
            continue
        key = (bad, fixable + len(cut), abs(S - target))
        if best is None or key < best[0]:
            best = (key, S, cut, [k for k, v in kinds.items() if v == 'left'], bad + fixable)
    if best is None:
        raise ValueError(f'no S in {s_min}..{s_max} gives a strip fully covered by wall faces')
    if best[4] and not allow_bad:
        raise ValueError(f'every S cuts a face badly (best S {best[1]}: {best[4]} triangle/pentagon cuts)')
    return {'S': best[1], 'cut': best[2], 'inside': best[3], 'bad': best[4]}


def grid_lines(lo, hi, required=(), step=0.6, min_gap=0.05):
    """Sorted lines lo..hi: the border, every required line inside, even splits to <= step."""
    if not (math.isfinite(lo) and math.isfinite(hi)) or hi - lo <= min_gap:
        raise ValueError(f'empty span {lo}..{hi}')
    req = [lo]
    for r in sorted(r for r in required if lo + MERGE_M < r < hi - MERGE_M):
        if r - req[-1] > MERGE_M:          # one line per 0.1 mm (float32 / rounded copies of the same line)
            req.append(r)
    if hi - req[-1] <= MERGE_M:
        req.pop()
    req.append(hi)
    for a, b in zip(req, req[1:]):
        if b - a < min_gap - 1e-12:
            raise ValueError(f'required lines {a} and {b} closer than {min_gap} m (sliver)')
    out = [req[0]]
    for a, b in zip(req, req[1:]):
        n = max(1, math.ceil((b - a) / step - 1e-9))
        out += [a + (b - a) * k / n for k in range(1, n)] + [b]
    return out


def affine_uv(pts, uvs, tol=1e-5):
    """Exact affine map (s, t) -> (u, v) from a planar face's corners; raises if the face's UVs are not affine
    within `tol` (a seam inside the face). Returns f(s, t) -> (u, v)."""
    if len(pts) < 3 or len(pts) != len(uvs):
        raise ValueError('need >= 3 corners with UVs')
    (s0, t0), (s1, t1), (s2, t2) = pts[0], pts[1], pts[2]
    best = None
    for i in range(1, len(pts)):
        for j in range(i + 1, len(pts)):
            d = (pts[i][0] - s0) * (pts[j][1] - t0) - (pts[j][0] - s0) * (pts[i][1] - t0)
            if best is None or abs(d) > abs(best[0]):
                best = (d, i, j)
    d, i, j = best
    if abs(d) < 1e-12:
        raise ValueError('degenerate face')
    (si, ti), (sj, tj) = pts[i], pts[j]
    coef = []
    for c in range(2):
        a0, ai, aj = uvs[0][c], uvs[i][c], uvs[j][c]
        ds = ((ai - a0) * (tj - t0) - (aj - a0) * (ti - t0)) / d
        dt = ((aj - a0) * (si - s0) - (ai - a0) * (sj - s0)) / d
        coef.append((a0, ds, dt))

    def f(s, t):
        return tuple(a0 + ds * (s - s0) + dt * (t - t0) for a0, ds, dt in coef)
    for p, uv in zip(pts, uvs):
        got = f(*p)
        if max(abs(got[0] - uv[0]), abs(got[1] - uv[1])) > tol:
            raise ValueError(f'UVs of the face are not affine at {p} ({got} vs {uv})')
    return f


def _ray_hits(origin, axis, sign, tris):
    """Crossings of the ray origin + sign*t*e_axis (t > 0) with triangles (exact for axis-aligned rays)."""
    a, b = [k for k in range(3) if k != axis]
    n = 0
    for tri in tris:
        (p, q, r) = tri
        d = (q[a] - p[a]) * (r[b] - p[b]) - (r[a] - p[a]) * (q[b] - p[b])
        if abs(d) < 1e-14:
            continue                                   # triangle parallel to the ray
        l1 = ((q[a] - origin[a]) * (r[b] - origin[b]) - (r[a] - origin[a]) * (q[b] - origin[b])) / d
        l2 = ((r[a] - origin[a]) * (p[b] - origin[b]) - (p[a] - origin[a]) * (r[b] - origin[b])) / d
        l3 = 1 - l1 - l2
        if min(l1, l2, l3) < 0:
            continue
        hit = l1 * p[axis] + l2 * q[axis] + l3 * r[axis]
        if (hit - origin[axis]) * sign > 0:
            n += 1
    return n


def post_cells(tris, xs, ys, zs, rays=((0, -1), (2, 1)), skip=lambda centre: False):
    """Voxels (i, j, k) of the global lines xs/ys/zs whose centre is inside the post triangles (odd parity on
    every ray in `rays`). The voxel centres are off every line, so no ray grazes an edge of an axis plane.
    A disagreement between the rays is an error naming the voxel. `skip(centre)` voxels (inside the body: the
    hidden inset part of a post, open in the source) are never post cells."""
    cells = set()
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            for k in range(len(zs) - 1):
                # off-centre by fixed irrational fractions: a centred ray would run along a square face's diagonal
                c = (xs[i] + (xs[i + 1] - xs[i]) * 0.4142, ys[j] + (ys[j + 1] - ys[j]) * 0.5772,
                     zs[k] + (zs[k + 1] - zs[k]) * 0.3679)
                if skip(c):
                    continue
                par = [_ray_hits(c, ax, sg, tris) % 2 for ax, sg in rays]
                if len(set(par)) != 1:
                    raise ValueError(f'ray parity disagrees at voxel {(i, j, k)} centre {c}: {par}')
                if par[0]:
                    cells.add((i, j, k))
    return cells


def post_faces(cells, xs, ys, zs, hidden=lambda centre, normal: False):
    """Boundary quads of the voxel set: [(corners [4 x (x, y, z)] counter-clockwise from outside, normal)].
    `hidden(centre, normal)` drops faces in contact with the body (they would overlap the wall)."""
    lines = (xs, ys, zs)
    out = []
    for cell in sorted(cells):
        for ax in range(3):
            for sg in (-1, 1):
                nb = list(cell)
                nb[ax] += 1 if sg > 0 else 0
                nb[ax] -= 0 if sg > 0 else 1
                if tuple(nb) in cells:
                    continue
                a, b = [k for k in range(3) if k != ax]
                plane = lines[ax][cell[ax] + (1 if sg > 0 else 0)]
                lo_a, hi_a = lines[a][cell[a]], lines[a][cell[a] + 1]
                lo_b, hi_b = lines[b][cell[b]], lines[b][cell[b] + 1]
                quad2 = [(lo_a, lo_b), (hi_a, lo_b), (hi_a, hi_b), (lo_a, hi_b)]
                corners = []
                for pa, pb in quad2:
                    p = [0.0, 0.0, 0.0]
                    p[ax], p[a], p[b] = plane, pa, pb
                    corners.append(tuple(p))
                # (a, b, ax) is a right-handed cycle for ax = 0, 2 and left-handed for ax = 1
                if (sg > 0) != (ax == 1):
                    pass
                else:
                    corners.reverse()
                normal = [0, 0, 0]
                normal[ax] = sg
                centre = tuple(sum(c[k] for c in corners) / 4 for k in range(3))
                if hidden(centre, tuple(normal)):
                    continue
                out.append((corners, tuple(normal)))
    return out
