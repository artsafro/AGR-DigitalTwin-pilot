"""Whole-wall grid plan for a flat facade wall (#1609, option A: Artem 2026-11-20 «по кпп ок», [D357]).

Pattern: n/a | new-case: rebuild one flat facade wall as a clean grid whose lines lie only where the wall outline or the
finish changes (BM-01..03, BM-09, BM-11, D344), with a continuous planar UV per finish.

Pure Python (stdlib only) so Blender and pytest load the same code. Coordinates are 2D in the wall plane: h (along the
wall, metres) and z (height). Input faces are polygons [(h, z), ...] with a finish id; `None` = wildcard (a hidden
contact area under a separate element: it belongs to the wall and takes the finish of its neighbour along the row).

1. `raster`: every distinct vertex coordinate of the input splits h and z into fine intervals; each fine cell takes the
   state (finish id or EMPTY) of the input face that contains its centre. Faces are axis-aligned in the expected input;
   a slanted outline or finish border can only be followed as a staircase, so the area of every input finish is
   compared with the raster and the difference is reported (`area_error_m2`), never hidden.
2. `lines`: a fine boundary becomes a grid line only if the state differs across it somewhere (outline, hole, finish
   border); tessellation vertices inside one finish leave no line. Intervals longer than `max_cell` are split evenly.
3. `uv_segments`: greedy segments of at most `span` along the facade direction (and in z): UV runs continuously inside
   a segment, the seam lies on an existing grid line.
Fail-closed: empty input, NaN/inf coordinates, a face with < 3 corners, a non-positive tolerance, a wildcard row with no
finish neighbour raise ValueError naming the item.
"""
import bisect
import math

EMPTY = -1
WILD = -2
TOL = 1e-6


def _check(faces):
    if not faces:
        raise ValueError('no wall faces')
    for i, (poly, fin) in enumerate(faces):
        if len(poly) < 3:
            raise ValueError(f'face {i}: fewer than 3 corners')
        for p in poly:
            if len(p) != 2 or not all(math.isfinite(c) for c in p):
                raise ValueError(f'face {i}: bad corner {p!r}')
        if fin is not None and (not isinstance(fin, int) or fin < 0):
            raise ValueError(f'face {i}: finish must be an int >= 0 or None, got {fin!r}')


def slanted_outline(faces, tol=1e-3, key=1e-7):
    """Number of outline edges (used by one finish face) that run slanted: both in-plane deltas > `tol`.

    w12g: a sill/head whose outline follows a sloped flashing was rasterised to whole axis cells that poke past the
    slanted edge (1201 pierce pairs with the v003 flashings); such a plane is not rebuilt. Wildcard (None) faces are
    ignored. Vertices are matched by coordinates rounded to `key`. Fail-closed: no faces, bad corners (`_check`)."""
    _check(faces)
    cnt = {}
    for poly, fin in faces:
        if fin is None:
            continue
        ks = [(round(p[0] / key), round(p[1] / key)) for p in poly]
        for a, b, pa, pb in zip(ks, ks[1:] + ks[:1], poly, poly[1:] + poly[:1]):
            if a == b:
                continue
            e = (min(a, b), max(a, b))
            if e in cnt:
                cnt[e][0] += 1
            else:
                cnt[e] = [1, pa, pb]
    return sum(1 for c, pa, pb in cnt.values()
               if c == 1 and abs(pa[0] - pb[0]) > tol and abs(pa[1] - pb[1]) > tol)


def quad_twisted(pts):
    """True when the 2D quad `pts` (a, b, c, d) is a bow-tie: edge ab crosses cd or bc crosses da (proper crossing).
    w13: the 2.1 mm body weld twisted one 4 mm v003 sliver; `dt qa xview` refuses a self-intersecting polygon.
    Fail-closed: not 4 corners, a non-finite coordinate."""
    if len(pts) != 4:
        raise ValueError(f'a quad needs 4 corners, got {len(pts)}')
    for p in pts:
        if len(p) != 2 or not all(math.isfinite(c) for c in p):
            raise ValueError(f'bad corner {p!r}')

    def o(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def cross(p, q, r, s):
        return o(p, q, r) * o(p, q, s) < 0 and o(r, s, p) * o(r, s, q) < 0
    a, b, c, d = pts
    return cross(a, b, c, d) or cross(b, c, d, a)


def unique(values, tol=TOL):
    """Sorted cluster centres: a value within `tol` of the cluster's first value joins the cluster."""
    if not tol > 0:
        raise ValueError('tolerance must be > 0')
    groups = []
    for v in sorted(values):
        if not groups or v - groups[-1][0] > tol:
            groups.append([v])
        else:
            groups[-1].append(v)
    return [(g[0] + g[-1]) / 2 for g in groups]


def snap_error(values, lines_):
    """Largest distance from an input value to its nearest line."""
    worst = 0.0
    for v in values:
        k = bisect.bisect_left(lines_, v)
        worst = max(worst, min(abs(v - lines_[i]) for i in (k - 1, k) if 0 <= i < len(lines_)))
    return worst


def area(poly):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1]))) / 2


def inside(p, poly, tol=1e-9):
    """Point in polygon; a point on the outline counts as inside."""
    hit = False
    n = len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        l2 = dx * dx + dy * dy
        if l2 > 0:
            t = max(0.0, min(1.0, ((p[0] - x1) * dx + (p[1] - y1) * dy) / l2))
            if math.hypot(x1 + t * dx - p[0], y1 + t * dy - p[1]) <= tol:
                return True
        if (y1 > p[1]) != (y2 > p[1]):
            if x1 + (p[1] - y1) * dx / dy > p[0]:
                hit = not hit
    return hit


def _forced(values, lo, hi, tol):
    out = []
    for v in values:
        if not isinstance(v, (int, float)) or not math.isfinite(v):
            raise ValueError(f'forced line {v!r} is not a finite number')
        if lo - tol <= v <= hi + tol:
            out.append(float(v))
    return sorted(set(out))


def snap_forced(vals, forced, tol):
    """Every cluster centre within `tol` of a forced value becomes that value exactly (the smallest forced value of
    the cluster wins, so neighbour planes converge on one value)."""
    out = list(vals)
    for f in sorted(forced, reverse=True):
        k = bisect.bisect_left(out, f)
        near = [i for i in (k - 1, k) if 0 <= i < len(out) and abs(out[i] - f) <= tol]
        if near:
            out[min(near, key=lambda i: abs(out[i] - f))] = f
    return sorted(out)


def raster(faces, tol=TOL, forced=((), ())):
    """Fine lines (hs, zs) and the state grid st[i][j] of the cell (hs[i]..hs[i+1], zs[j]..zs[j+1]). `forced`:
    (h values, z values) that must be lines (a neighbour plane's lines on the shared edge, #1609 variant A)."""
    _check(faces)
    hv = [p[0] for poly, _ in faces for p in poly]
    zv = [p[1] for poly, _ in faces for p in poly]
    fh, fz = _forced(forced[0], min(hv), max(hv), tol), _forced(forced[1], min(zv), max(zv), tol)
    hs = snap_forced(unique(hv + fh, tol), fh, tol)
    zs = snap_forced(unique(zv + fz, tol), fz, tol)
    st = [[EMPTY] * (len(zs) - 1) for _ in range(len(hs) - 1)]
    for poly, fin in faces:
        h0, h1 = min(p[0] for p in poly), max(p[0] for p in poly)
        z0, z1 = min(p[1] for p in poly), max(p[1] for p in poly)
        i0, i1 = max(bisect.bisect_left(hs, h0 - tol), 0), bisect.bisect_right(hs, h1 + tol) - 1
        j0, j1 = max(bisect.bisect_left(zs, z0 - tol), 0), bisect.bisect_right(zs, z1 + tol) - 1
        rect = len(poly) == 4 and all(abs(a[0] - b[0]) <= tol or abs(a[1] - b[1]) <= tol
                                      for a, b in zip(poly, poly[1:] + poly[:1]))
        for i in range(i0, i1):
            c0 = (hs[i] + hs[i + 1]) / 2
            for j in range(j0, j1):
                c = (c0, (zs[j] + zs[j + 1]) / 2)
                if rect or inside(c, poly):
                    st[i][j] = WILD if fin is None else fin
    return hs, zs, st


def fill_wild(st):
    """Wildcard cells take the finish of the nearest finish cell in the same row (z), ties to the higher h."""
    ni = len(st)
    for j in range(len(st[0]) if st else 0):
        row = [st[i][j] for i in range(ni)]
        for i in range(ni):
            if row[i] != WILD:
                continue
            best = None
            for d in range(1, ni):
                for k in (i + d, i - d):
                    if 0 <= k < ni and row[k] >= 0:
                        best = row[k]
                        break
                if best is not None:
                    break
            if best is None:
                raise ValueError(f'wildcard cell ({i}, {j}) has no finish cell in its row')
            st[i][j] = best
    return st


def lines(hs, zs, st, max_cell, forced=((), ()), lattice=False):
    """Coarse grid lines: fine lines across which the state changes, forced lines, plus the outer ones; long
    intervals split - evenly, or with `lattice` at the global multiples of max_cell / 2 that lie >= max_cell / 8
    inside the interval (every plane then splits at the same world values, so conforming neighbours converge)."""
    if not max_cell > 0:
        raise ValueError('max_cell must be > 0')
    ni, nj = len(hs) - 1, len(zs) - 1
    fh, fz = set(forced[0]), set(forced[1])
    keep_h = {0, ni} | {i for i in range(1, ni) if hs[i] in fh or any(st[i - 1][j] != st[i][j] for j in range(nj))}
    keep_z = {0, nj} | {j for j in range(1, nj) if zs[j] in fz or any(st[i][j - 1] != st[i][j] for i in range(ni))}

    def split(vals):
        out = [vals[0]]
        for b in vals[1:]:
            a = out[-1]
            if lattice and b - a > max_cell + 1e-9:
                step, margin = max_cell / 2, max_cell / 8
                k0, k1 = math.ceil((a + margin) / step - 1e-9), math.floor((b - margin) / step + 1e-9)
                out += [k * step for k in range(k0, k1 + 1)] + [b]
                continue
            n = math.ceil((b - a) / max_cell - 1e-9)
            out += [a + (b - a) * k / n for k in range(1, n)] + [b]
        return out
    return split([hs[i] for i in sorted(keep_h)]), split([zs[j] for j in sorted(keep_z)])


def coarse(hs, zs, st, H, Z, tol=TOL):
    """State of every coarse cell; every fine cell inside it must agree (by construction), else ValueError."""
    out = {}
    for a in range(len(H) - 1):
        # fine cells overlapping the coarse cell (an evenly split interval lies inside one fine cell)
        i0, i1 = bisect.bisect_right(hs, H[a] + tol) - 1, bisect.bisect_left(hs, H[a + 1] - tol)
        for b in range(len(Z) - 1):
            j0, j1 = bisect.bisect_right(zs, Z[b] + tol) - 1, bisect.bisect_left(zs, Z[b + 1] - tol)
            s = {st[i][j] for i in range(i0, i1) for j in range(j0, j1)}
            if len(s) != 1:
                raise ValueError(f'coarse cell {a},{b} mixes states {sorted(s)}')
            v = s.pop()
            if v != EMPTY:
                out[(a, b)] = v
    return out


def finish_areas(faces):
    out = {}
    for poly, fin in faces:
        out[fin] = out.get(fin, 0.0) + area(poly)
    return out


def raster_areas(hs, zs, st):
    out = {}
    for i in range(len(hs) - 1):
        for j in range(len(zs) - 1):
            if st[i][j] != EMPTY:
                out[st[i][j]] = out.get(st[i][j], 0.0) + (hs[i + 1] - hs[i]) * (zs[j + 1] - zs[j])
    return out


def uv_segments(vals, span):
    """Segment start for every interval of the sorted lines `vals`: an interval starts a new segment when the
    segment would get longer than `span`. An interval longer than span itself is an error (split it first)."""
    if not span > 0:
        raise ValueError('span must be > 0')
    starts, s0 = [], vals[0]
    for a, b in zip(vals, vals[1:]):
        if b - a > span + 1e-9:
            raise ValueError(f'interval {a}..{b} is longer than the UV span {span}')
        if b - s0 > span + 1e-9:
            s0 = a
        starts.append(s0)
    return starts


def embed_shifts(cells, H, Z, emb, keep=0.45):
    """Shift of every grid node that lies on the wall outline (D336 / SKELETONS 'embed/offset', never welding).

    The wall is its own element: no node may sit on a vertex of the body it was cut from. A node with an empty
    quadrant moves `emb` (metres) towards the empty side on each axis where the empty quadrants agree, so the wall
    reaches `emb` past its old outline (into the opening, past the corner, under the cap) and the body's border
    vertices stay >= emb away. Quadrant direction (dh, dz) in {-1, 1}^2; shift = emb * sign(sum of empty quadrants).
    A shift (along one axis) is clamped to `keep` x the size of the column/row it moves into (full or empty), so the two nodes of a cell
    never cross and no quad flips (a 2.5 mm cell next to a hole corner).
    Returns ({(a, b): (dh, dz)} for moved nodes, [(a, b), ...] nodes with empty quadrants but no direction
    (checkerboard, the wall touches itself at one node) - the caller reports them, they are not moved -,
    [(a, b), ...] nodes whose shift was clamped (may stay closer than `emb` to the old outline).
    """
    if not (math.isfinite(emb) and emb > 0):
        raise ValueError(f'embed must be a finite value > 0, got {emb!r}')
    if not 0 < keep < 0.5:
        raise ValueError(f'keep must lie in (0, 0.5), got {keep!r}')
    nh, nz = len(H), len(Z)
    shifts, stuck, clamped = {}, [], []
    for a in range(nh):
        for b in range(nz):
            sh = sz = n_empty = n_full = 0
            for dh, dz in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
                key = (a + (dh - 1) // 2, b + (dz - 1) // 2)
                if key in cells:
                    n_full += 1
                else:
                    n_empty += 1
                    sh += dh
                    sz += dz
            if not n_full or not n_empty:
                continue
            if sh == 0 and sz == 0:
                stuck.append((a, b))
                continue
            sgh, sgz = (sh > 0) - (sh < 0), (sz > 0) - (sz < 0)
            mh = mz = emb
            # the column/row the node moves into, full or empty, caps the move at `keep` x its size: along a full
            # cell no quad flips; across an empty slot the parts on both sides never cross (w8, a 3.6 mm slot at
            # W -3.655 made two cells of one element overlap). Off the grid there is nothing to cross.
            if sgh:
                ka = a if sgh > 0 else a - 1
                if 0 <= ka < nh - 1:
                    mh = min(mh, keep * (H[ka + 1] - H[ka]))
            if sgz:
                kb = b if sgz > 0 else b - 1
                if 0 <= kb < nz - 1:
                    mz = min(mz, keep * (Z[kb + 1] - Z[kb]))
            if mh < emb and sgh or mz < emb and sgz:
                clamped.append((a, b))
            shifts[(a, b)] = (mh * sgh, mz * sgz)
    return shifts, stuck, clamped


def relax_shifts(cells, H, Z, shifts, min_d, rounds=60):
    """Shrink embed shifts until no two nodes of the wall are closer than `min_d` (the xView vertex limit, judged per
    element [D336]). A node pair closer than `min_d` halves both shifts (direction kept, never grows; below 1 um the
    shift is dropped); the embed clamp of `embed_shifts` (<= 0.45 of the cell) keeps every partial shift flip-free.
    A pair that is still too close with both shifts dropped means two grid lines closer than `min_d`: ValueError
    naming the nodes (the caller snaps lines with a larger tolerance). Returns a new {(a, b): (dh, dz)}."""
    if not (isinstance(min_d, (int, float)) and math.isfinite(min_d) and min_d > 0):
        raise ValueError(f'min_d must be a finite value > 0, got {min_d!r}')
    if not cells:
        raise ValueError('relax_shifts: no cells')
    keys = sorted({(a + i, b + j) for (a, b) in cells for i in (0, 1) for j in (0, 1)})
    sh = {k: tuple(v) for k, v in shifts.items() if k in keys}
    for _ in range(rounds + 1):
        pos = {k: (H[k[0]] + sh.get(k, (0.0, 0.0))[0], Z[k[1]] + sh.get(k, (0.0, 0.0))[1]) for k in keys}
        grid = {}
        for k, (x, y) in pos.items():
            grid.setdefault((math.floor(x / min_d), math.floor(y / min_d)), []).append(k)
        bad = set()
        for k, (x, y) in pos.items():
            gx, gy = math.floor(x / min_d), math.floor(y / min_d)
            for i in (-1, 0, 1):
                for j in (-1, 0, 1):
                    for m in grid.get((gx + i, gy + j), ()):
                        if m > k and math.dist(pos[k], pos[m]) < min_d:
                            bad.add((k, m))
        if not bad:
            return sh
        stuck = [(k, m) for k, m in bad if k not in sh and m not in sh]
        if stuck:
            k, m = stuck[0]
            raise ValueError(f'nodes {k} and {m} are closer than {min_d} m without any shift ({len(stuck)} pairs): '
                             f'grid lines closer than the xView limit')
        for k in {n for pair in bad for n in pair}:
            if k in sh:
                dh, dz = sh[k][0] / 2, sh[k][1] / 2
                if abs(dh) < 1e-6 and abs(dz) < 1e-6:
                    del sh[k]
                else:
                    sh[k] = (dh if abs(dh) >= 1e-6 else 0.0, dz if abs(dz) >= 1e-6 else 0.0)
    raise ValueError(f'relax_shifts did not converge in {rounds} rounds')


def plan(faces, max_cell, tol=TOL, forced=((), ()), lattice=False):
    """Whole plan: fine raster, coarse lines, coarse cells {(a, b): finish}, area check per finish. Vertex
    coordinates within `tol` collapse onto one line (the cluster centre, or the forced value in it); `snap_max_m`
    reports the largest move."""
    hs, zs, st = raster(faces, tol, forced)
    fill_wild(st)
    H, Z = lines(hs, zs, st, max_cell, forced, lattice)
    cells = coarse(hs, zs, st, H, Z)   # H, Z are copies of hs, zs (or inside one fine cell)
    fa = finish_areas([f for f in faces if f[1] is not None])
    ra = raster_areas(hs, zs, st)
    gaps = sorted(b - a for v in (H, Z) for a, b in zip(v, v[1:]))
    snap = max(snap_error([p[0] for poly, _ in faces for p in poly], hs),
               snap_error([p[1] for poly, _ in faces for p in poly], zs))
    return {'H': H, 'Z': Z, 'cells': cells, 'fine': (len(hs), len(zs)), 'snap_max_m': snap,
            'area_input_m2': fa, 'area_raster_m2': ra,
            'area_error_m2': {k: ra.get(k, 0.0) - fa.get(k, 0.0) for k in set(fa) | set(ra)},
            'min_gap_m': gaps[0] if gaps else None}


def conform(planes, adj, max_cell, tol=TOL, rounds=50, log=None):
    """Plans for planes that share edges, with the same nodes on every shared edge (#1609 variant A, Artem
    2026-11-20 «принимаю рекомендации»: walls are one body with the reveals, wall lines continue along the reveals).

    planes: {pid: {'faces': faces2d, 'axes': (a1, a2) world axes of h and z, 'ax': normal axis, 'pos': position}}.
    adj: {(p, q): [(t, lo, hi), ...]} - p and q share edges along world axis t over lo..hi. Each plane gets the
    neighbour's position as a line (the shared edge) and, to a fixpoint, every neighbour line along t inside a
    shared span (closure over the spans; own lines stay, splits on the global lattice). Returns ({pid: plan},
    {'closure_steps', 'mismatched_spans'}). Fail-closed: no planes, unknown plane, parallel neighbours, an edge axis
    that is not in both planes, no fixpoint."""
    if not planes:
        raise ValueError('no planes')
    for (p, q), spans in adj.items():
        for k in (p, q):
            if k not in planes:
                raise ValueError(f'unknown plane {k!r} in adjacency')
        if planes[p]['ax'] == planes[q]['ax']:
            raise ValueError(f'parallel planes {p!r} and {q!r} cannot share an edge')
        for t, _lo, _hi in spans:
            if t not in planes[p]['axes'] or t not in planes[q]['axes']:
                raise ValueError(f'edge axis {t} of {p!r}/{q!r} is not an in-plane axis of both')
    # 1. own lines (outline, finish borders, lattice splits) - sticky: a later forced line only shortens intervals,
    #    so no new lattice value can appear (lattice splits never cascade)
    forced = {}
    for k, pl in planes.items():
        p0 = plan(pl['faces'], max_cell, tol, lattice=True)
        forced[k] = {pl['axes'][0]: set(p0['H']), pl['axes'][1]: set(p0['Z'])}
    for (p, q) in adj:
        forced[p][planes[q]['ax']].add(planes[q]['pos'])
        forced[q][planes[p]['ax']].add(planes[p]['pos'])
    # 2. closure over the shared spans (set operations only)
    nb = {}
    for (p, q), spans in adj.items():
        for t, lo, hi in spans:
            nb.setdefault(p, []).append((q, t, lo, hi))
            nb.setdefault(q, []).append((p, t, lo, hi))
    work, n = set(nb), 0
    while work:
        n += 1
        if n > rounds * max(len(planes), 1):
            raise ValueError(f'no conforming fixpoint after {n} steps')
        k = min(work, key=str)
        work.discard(k)
        for q, t, lo, hi in nb[k]:
            new = {v for v in forced[k][t] if lo - tol <= v <= hi + tol} - forced[q][t]
            if new:
                forced[q][t] |= new
                work.add(q)
    # 3. one value per cluster along each world axis (no two planes keep 1-3 mm different copies of a line)
    for a in range(3):
        vals = sorted({v for k in forced for v in forced[k].get(a, ())})
        if not vals:
            continue
        canon, c0, group = {}, vals[0], []
        for v in vals + [math.inf]:
            if v - c0 > tol:
                for g in group:
                    canon[g] = (group[0] + group[-1]) / 2
                c0, group = v, []
            group.append(v)
        for k in forced:
            if a in forced[k]:
                forced[k][a] = {canon[v] for v in forced[k][a]}
    plans = {}
    for k, pl in planes.items():
        a1, a2 = pl['axes']
        plans[k] = plan(pl['faces'], max_cell, tol, (forced[k][a1], forced[k][a2]), lattice=True)
    bad = 0
    for (p, q), spans in adj.items():
        for t, lo, hi in spans:
            side = [[v for v in (plans[s]['H'] if planes[s]['axes'][0] == t else plans[s]['Z'])
                     if lo - tol <= v <= hi + tol] for s in (p, q)]
            bad += side[0] != side[1]
    if log:
        log(n, bad)
    return plans, {'closure_steps': n, 'mismatched_spans': bad}
