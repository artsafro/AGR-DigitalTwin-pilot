"""new-case: KPP1 quad master corners as separate clean elements (#1609): pure planning kernel, no Blender.

Artem 2026-11-16 rejected the v003 corners: everything was welded into ONE mesh and the rules were forced onto
it. Decision [D336] and the body rules (docs/research/body-modelling.md BM-04/BM-05/BM-09): posts (стойки) are
geometry - separate inset elements with clean quads, never welded into the body; the wall under them is not cut;
panels are texture with a seam. This module plans:

1. `conform_rect` - the body wall rectangle [0, S] x [z0, z1] at a building corner (s = distance from the corner
   along the wall) to re-mesh: a union of whole wall faces (the posts' hidden contact strip is "don't care"),
   no opening, no other element attached inside, and a grid whose every line ends on a kept vertex of the
   border: no line ends inside a kept border edge (no T-junction), every kept border vertex is a line, every UV
   seam is a line (a slanted seam rejects the rectangle), no two lines closer than `min_gap` (no sliver
   rows/columns, BM-09). Largest area wins.
2. `post_cells` - the posts as a voxel set on the snapped global x/y/z lines of the R1 post triangles (inside =
   odd ray parity in two directions, both must agree), and `post_faces` - its boundary quads (conforming, one
   clean element), minus faces lying on the body wall that face into the body (hidden contact, would overlap).
3. `affine_uv` - exact planar UV map of a source face, used to give every new corner the source UV.

Every failure is an error naming the corner/wall/face; nothing falls back to a default.
"""
import math

TOL = 2e-5          # = twinqa.look.TJUNCTION_TOL_M [D200]
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




def _union_area(rects):
    """Area of a union of axis rectangles [(s0, s1, z0, z1)] (coordinate compression)."""
    xs = sorted({r[k] for r in rects for k in (0, 1)})
    ys = sorted({r[k] for r in rects for k in (2, 3)})
    area = 0.0
    for xa, xb in zip(xs, xs[1:]):
        for ya, yb in zip(ys, ys[1:]):
            cx, cy = (xa + xb) / 2, (ya + yb) / 2
            if any(r[0] <= cx <= r[1] and r[2] <= cy <= r[3] for r in rects):
                area += (xb - xa) * (yb - ya)
    return area


def _lines_ok(lines, kept_edges, min_gap, tol):
    """Sorted unique lines, or None if two are closer than min_gap or one ends inside a kept border edge."""
    out = []
    for v in sorted(lines):
        if out and v - out[-1] <= tol:
            continue
        out.append(v)
    if any(b - a < min_gap - tol for a, b in zip(out, out[1:])):
        return None
    for v in out:
        if any(lo + tol < v < hi - tol for lo, hi in kept_edges):
            return None
    return out


def _bump(why, key):
    why[key] = why.get(key, 0) + 1


def conform_rect(faces, items, edges, s_lo, s_hi, z_lo, z_hi, gone=frozenset(), dontcare=(), seams=(),
                 min_gap=0.03, tol=TOL, weight=None):
    """Plan the largest conforming wall rectangle [0, S] x [z0, z1], S in [s_lo, s_hi], z0/z1 in [z_lo, z_hi].

    faces: {fid: [(s, z), ...]} wall faces in the plane (s >= 0); items: [(s, z, fids)] every mesh vertex lying in
    the wall plane with ALL its faces (any orientation); edges: [((s, z), (s, z), fids)] every mesh edge lying in
    the plane with its faces; gone: faces deleted anyway (the posts); dontcare: [(s0, s1, z0, z1)] rectangles that
    need no wall face (the posts' hidden contact); seams: [((s, z), (s, z))] UV seams between two wall faces.
    weight: {fid: w} - when given, the plan maximises (sum of w inside, area) and a rectangle with no weight inside
    is not a plan (nothing to fix: the irregular faces carry the weight).
    Returns {'S', 'z0', 'z1', 'faces', 'cols', 'rows', 'area', 'score'}; raises ValueError naming why nothing fits."""
    if not faces:
        raise ValueError('no wall faces')
    for name, v in (('s_lo', s_lo), ('s_hi', s_hi), ('z_lo', z_lo), ('z_hi', z_hi), ('min_gap', min_gap)):
        if not math.isfinite(v):
            raise ValueError(f'{name} is not finite: {v!r}')
    if not (0 < s_lo <= s_hi and z_lo < z_hi and min_gap > 0):
        raise ValueError(f'empty search box s {s_lo}..{s_hi} z {z_lo}..{z_hi} (min_gap {min_gap})')
    boxes = {}
    for fid, poly in faces.items():
        if len(poly) < 3 or any(not (math.isfinite(s) and math.isfinite(z)) for s, z in poly):
            raise ValueError(f'bad wall face {fid}: {poly!r}')
        ss, zs = [p[0] for p in poly], [p[1] for p in poly]
        if min(ss) < -tol:
            raise ValueError(f'wall face {fid} beyond the corner: {poly!r}')
        boxes[fid] = (min(ss), max(ss), min(zs), max(zs), _area(poly))
    for s, z, _ in items:
        if not (math.isfinite(s) and math.isfinite(z)):
            raise ValueError(f'non-finite vertex {(s, z)!r}')
    s_cands = sorted({round(b[1], 6) for b in boxes.values() if s_lo - tol <= b[1] <= s_hi + tol})
    z_cands = sorted({round(z, 6) for b in boxes.values() for z in (b[2], b[3]) if z_lo - tol <= z <= z_hi + tol})
    best, why = None, {}
    pairs = sorted(((z0, z1) for i, z0 in enumerate(z_cands) for z1 in z_cands[i + 1:]), key=lambda p: p[0] - p[1])
    for S in reversed(s_cands):
        near = {f: b for f, b in boxes.items() if b[0] < S - tol}
        for z0, z1 in pairs:
            area = S * (z1 - z0)
            if weight is None and best is not None and area <= best['area'] + 1e-9:
                continue
            inside, ok = set(), True
            for f, b in near.items():
                if b[2] < z1 - tol and b[3] > z0 + tol:
                    if b[1] > S + tol or b[2] < z0 - tol or b[3] > z1 + tol:
                        ok = False
                        break
                    inside.add(f)
            if not ok:
                _bump(why, 'crossed')
                continue
            score = (round(sum(weight.get(f, 0.0) for f in inside), 9) if weight is not None else 0.0, round(area, 9))
            if weight is not None and (score[0] <= 0 or (best is not None and score <= best['score'])):
                _bump(why, 'nothing to fix' if score[0] <= 0 else 'smaller')
                continue
            dc = [(max(0.0, r[0]), min(S, r[1]), max(z0, r[2]), min(z1, r[3])) for r in dontcare]
            dc = [r for r in dc if r[1] > r[0] and r[3] > r[2]]
            cover = sum(boxes[f][4] for f in inside) + _union_area(dc) - sum(
                clip_area(faces[f], *r) for f in inside for r in dc)
            if abs(cover - area) > 1e-6 + 1e-5 * area:
                _bump(why, 'coverage')
                continue
            dead = inside | set(gone)
            border = {'b': set(), 't': set(), 'l': set(), 'r': set()}
            attached = False
            for s, z, fids in items:
                if not (set(fids) - dead):
                    continue
                if s < -tol or s > S + tol or z < z0 - tol or z > z1 + tol:
                    continue
                on = [k for k, c in (('l', abs(s) <= tol), ('r', abs(s - S) <= tol),
                                     ('b', abs(z - z0) <= tol), ('t', abs(z - z1) <= tol)) if c]
                if not on:
                    attached = True
                    break
                for k in on:
                    border[k].add(round(z if k in 'lr' else s, 6))
            if attached:
                _bump(why, 'attached')
                continue
            kept_e = {'b': [], 't': [], 'l': [], 'r': []}
            for p, q, fids in edges:
                if not (set(fids) - dead):
                    continue
                for k, ax, val, lo, hi in (('l', 0, 0.0, z0, z1), ('r', 0, S, z0, z1),
                                           ('b', 1, z0, 0.0, S), ('t', 1, z1, 0.0, S)):
                    if abs(p[ax] - val) <= tol and abs(q[ax] - val) <= tol:
                        a, c = sorted((p[1 - ax], q[1 - ax]))
                        if c > lo + tol and a < hi - tol:
                            kept_e[k].append((a, c))
            s_seam, z_seam, slanted = set(), set(), False
            for p, q in seams:
                if not all(-tol <= v[0] <= S + tol and z0 - tol <= v[1] <= z1 + tol for v in (p, q)):
                    continue
                if abs(p[0] - q[0]) <= tol:
                    if tol < p[0] < S - tol:
                        s_seam.add(round(p[0], 6))
                elif abs(p[1] - q[1]) <= tol:
                    if z0 + tol < p[1] < z1 - tol:
                        z_seam.add(round(p[1], 6))
                else:
                    slanted = True
                    break
            if slanted:
                _bump(why, 'slanted seam')
                continue
            cols = _lines_ok({0.0, S} | {v for v in border['b'] | border['t'] | s_seam if tol < v < S - tol},
                             kept_e['b'] + kept_e['t'], min_gap, tol)
            rows = _lines_ok({z0, z1} | {v for v in border['l'] | border['r'] | z_seam if z0 + tol < v < z1 - tol},
                             kept_e['l'] + kept_e['r'], min_gap, tol)
            if cols is None or rows is None:
                _bump(why, 'lines')
                continue
            best = {'S': S, 'z0': z0, 'z1': z1, 'faces': sorted(inside), 'cols': cols, 'rows': rows,
                    'area': area, 'score': score}
    if best is None:
        raise ValueError(f'no conforming rectangle (rejected: {why})')
    return best


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




def affine_uv(pts, uvs, tol=1e-5):
    """Exact affine map (s, t) -> (u, v) from a planar face's corners; raises if the face's UVs are not affine
    within `tol` (a seam inside the face). Returns f(s, t) -> (u, v)."""
    if len(pts) < 3 or len(pts) != len(uvs):
        raise ValueError('need >= 3 corners with UVs')
    s0, t0 = pts[0]
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
    boxes = [tuple((min(p[d] for p in t), max(p[d] for p in t)) for d in range(3)) for t in tris]
    column = {}   # (ray axis, voxel index on the other two axes) -> triangles whose bbox holds that ray line

    def near(c, ax, idx):
        key = (ax,) + tuple(idx[d] for d in range(3) if d != ax)
        if key not in column:
            column[key] = [t for t, bb in zip(tris, boxes)
                           if all(bb[d][0] - 1e-9 <= c[d] <= bb[d][1] + 1e-9 for d in range(3) if d != ax)]
        return column[key]
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            for k in range(len(zs) - 1):
                # off-centre by fixed irrational fractions: a centred ray would run along a square face's diagonal
                c = (xs[i] + (xs[i + 1] - xs[i]) * 0.4142, ys[j] + (ys[j + 1] - ys[j]) * 0.5772,
                     zs[k] + (zs[k + 1] - zs[k]) * 0.3679)
                if skip(c):
                    continue
                par = [_ray_hits(c, ax, sg, near(c, ax, (i, j, k))) % 2 for ax, sg in rays]
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
