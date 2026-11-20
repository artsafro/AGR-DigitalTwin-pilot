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


def raster(faces, tol=TOL):
    """Fine lines (hs, zs) and the state grid st[i][j] of the cell (hs[i]..hs[i+1], zs[j]..zs[j+1])."""
    _check(faces)
    hs = unique([p[0] for poly, _ in faces for p in poly], tol)
    zs = unique([p[1] for poly, _ in faces for p in poly], tol)
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


def lines(hs, zs, st, max_cell):
    """Coarse grid lines: fine lines across which the state changes, plus the outer ones; long intervals split."""
    if not max_cell > 0:
        raise ValueError('max_cell must be > 0')
    ni, nj = len(hs) - 1, len(zs) - 1
    keep_h = {0, ni} | {i for i in range(1, ni) if any(st[i - 1][j] != st[i][j] for j in range(nj))}
    keep_z = {0, nj} | {j for j in range(1, nj) if any(st[i][j - 1] != st[i][j] for i in range(ni))}

    def split(vals):
        out = [vals[0]]
        for b in vals[1:]:
            a = out[-1]
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


def plan(faces, max_cell, tol=TOL):
    """Whole plan: fine raster, coarse lines, coarse cells {(a, b): finish}, area check per finish. Vertex
    coordinates within `tol` collapse onto one line (the cluster centre); `snap_max_m` reports the largest move."""
    hs, zs, st = raster(faces, tol)
    fill_wild(st)
    H, Z = lines(hs, zs, st, max_cell)
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
