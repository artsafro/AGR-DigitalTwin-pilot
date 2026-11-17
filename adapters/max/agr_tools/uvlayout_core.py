"""new-case: AGR Tools 1.0 (#1024) shared module uvlayout: K6 seam-to-seam UV layout, stdlib only (branch M).

Owned by branch M (improve/issue-1024-vpm-layout); read by branch P (npm.build) through `layout_seamless`.
No pymxs: the cores never take a host object (contract_core.HostAdapter gives plain data).

Rule of the core (lab L09, docs/experiments/vpm.build.md, measured in 3ds Max 2024):

* UV of facade panels and brick is a projection by module from the COMMON grid zero of the project (passport),
  in double precision on metres (the Max glue sums local coordinates and the pivot in double: float32 world
  coordinates at 2 345 678 m gave +2.1 % texel and degenerate faces, L09 r2):
  `u = (s0 + (p - A) . t) / P`, `v = (z - z0) / P`, P = the UDIM step (3.6 m, owner answer 06.11.2026: a whole
  number of 1.2 m / 0.6 m modules).
* `s0` is the length along the chain of walls of one material (unrolled along the perimeter), so the corners of
  a chain are continuous; a projection "by axes" tears the corners (L09: 2048 px at a corner).
* The texel is set once, before the layout; the layout never scales.
* Layout into UDIM only by WHOLE tile vectors: every face is cut by the integer lines of the UV grid (the idea of
  UDIM Slicer `GeoAGR.ms:5236-5280`, without its snapping of UV to integers `:5246-5255`), then each piece moves by
  `tile_origin(T) - floor(centroid)` into the tile T of its material. Only the integer part changes, so the seam
  metric (fractional UV mismatch on shared edges, in texels) is 0 by construction (L09: 0.0005 px float noise).
* GeoAGR defects not repeated: mode B shifts the island minimum by a fraction (`:31473-31598`, 945 px seam);
  Rapports shifts by whole repeats only (`:32515-32603`, 2048 px mod UDIM); everything lands in 1001 (no tile per
  material); islands across a tile line stick out instead of being cut; `fit_all_to_udim` (`:20050`) rescales.

Data model of a mesh here (all lists 0-based):
  {'verts': [[x, y, z]...] metres (world, double), 'tris': [[a, b, c]...], 'mat_ids': [int...],
   'uv': [[[u, v], [u, v], [u, v]]...] per triangle corner or None}.
A piece (output of `cut_grid`) is {'tri': i, 'w': [[w0, w1, w2]...] barycentric weights over the source
triangle corners, 'uv': [[u, v]...], 'mat': id}; the host interpolates its own coordinates with the weights.
"""
import importlib.util
import math
import os


def _sibling(name, alias):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
    spec = importlib.util.spec_from_file_location(alias, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


udimtile = _sibling('udimtile_core.py', 'agr_tools_udimtile_core_uvlayout')  # the one UDIM function (#1337)

STEP_M = 3.6          # UDIM step (owner answer 06.11.2026, ANSWERS-2026-11-06.md «Шаг UDIM»)
TILE_PX = 3600        # pixels of one UDIM tile: 3.6 m at 1000 px/m (owner answer 06.11 morning, audit Q1; was 4096)
TEXEL_PX_PER_M = 1000.0  # VPM texel density px/m (owner answer 06.11 morning: every module 0.3/0.6/1.2 m lies whole)
FIRST_UDIM = 1001
SEAM_TOL_PX = 0.01    # L09 acceptance: seam 0 px (mod 1, <= 0.01 px)
VERTICAL_NZ = 0.5     # |n.z| below: a wall (vertical projection); above: horizontal projection
_EPS_UV = 1e-9
_KEY_M = 1e-5         # position key for edge matching between pieces / islands (0.01 mm)


# ---- UDIM tiles ----------------------------------------------------------------------------------------------
def tile_origin(udim):
    """UDIM 1001.. -> integer (u0, v0) of the tile: 10 tiles per row."""
    if isinstance(udim, bool) or not isinstance(udim, int) or udim < FIRST_UDIM:
        raise ValueError('UDIM tile must be an integer >= 1001: {!r}'.format(udim))
    return udimtile.tile_origin(udim)


def udim_of_cell(cu, cv):
    """Integer UV cell -> UDIM number: udimtile_core.udim_of_cell (#1337). Cells with u outside 0..9 or v < 0
    raise udimtile.UdimDomainError (a ValueError; None before #1337); v >= 10 gives 1101+ (None before)."""
    return udimtile.udim_of_cell(cu, cv)


def piece_tile_or_zero(uv):
    """UDIM of the cell of a piece centroid for the vpm.build report; 0 = off the UDIM grid (the label the report
    used before #1337, when udim_of_cell returned None)."""
    try:
        return udim_of_cell(*_cell(uv))
    except udimtile.UdimDomainError:
        return 0


def renumber_dense(used_ids, start=FIRST_UDIM):
    """Library ids used by ONE mesh -> UDIM start.. without gaps in ascending library id (K3; owner answer V9:
    numbering per mesh, every mesh from 1001). Same contract as matlib_core.renumber_dense (branch L); the
    vpm core calls matlib_core first and uses this only while branch L's function is a stub."""
    ids = sorted(set(used_ids))
    for i in ids:
        if isinstance(i, bool) or not isinstance(i, int) or i <= 0 or i >= 1001:
            raise ValueError('library id must be an integer 1..1000 on working geometry: {!r}'.format(i))
    return {lid: start + k for k, lid in enumerate(ids)}


# ---- small vector helpers ------------------------------------------------------------------------------------
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a):
    return math.sqrt(_dot(a, a))


def tri_normal(verts, tri):
    """Unit normal and area (m²) of a triangle; degenerate -> (None, 0.0)."""
    a, b, c = (verts[i] for i in tri)
    n = _cross(_sub(b, a), _sub(c, a))
    ln = _norm(n)
    if ln <= 1e-14:
        return None, 0.0
    return (n[0] / ln, n[1] / ln, n[2] / ln), 0.5 * ln


def _check_mesh(mesh):
    if not isinstance(mesh, dict) or not mesh.get('tris'):
        raise ValueError('empty mesh: no triangles')
    nv = len(mesh['verts'])
    if len(mesh['mat_ids']) != len(mesh['tris']):
        raise ValueError('mat_ids must have one id per triangle')
    for t in mesh['tris']:
        if len(t) != 3 or any(not (0 <= i < nv) for i in t):
            raise ValueError('triangle index out of range: {!r}'.format(t))
    for p in mesh['verts']:
        if len(p) != 3 or not all(math.isfinite(c) for c in p):
            raise ValueError('non-finite vertex')
    if mesh.get('uv') is not None and len(mesh['uv']) != len(mesh['tris']):
        raise ValueError('uv must have three corners per triangle')


# ---- K6 projection with the perimeter unroll -----------------------------------------------------------------
def _pkey(x, y):
    return (round(x / 1e-3), round(y / 1e-3))  # 1 mm plan key of a wall corner


def _components(mesh, faces):
    """Edge-connected components (edges matched by position, 0.01 mm) of the given triangles, sorted lists."""
    verts, tris = mesh['verts'], mesh['tris']
    parent = {f: f for f in faces}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    seen = {}
    for f in faces:
        t = tris[f]
        for j in range(3):
            ka, kb = _edge_key(verts[t[j]]), _edge_key(verts[t[(j + 1) % 3]])
            k = (min(ka, kb), max(ka, kb))
            if k in seen:
                a, b = find(seen[k]), find(f)
                if a != b:
                    parent[max(a, b)] = min(a, b)
            else:
                seen[k] = f
    groups = {}
    for f in faces:
        groups.setdefault(find(f), []).append(f)
    return [sorted(g) for _, g in sorted(groups.items())]


def plane_regions(mesh, faces, tag='k'):
    """{face: (tag, region)}: edge-connected coplanar regions of one material (normal 1e-3, offset 1 mm), so the
    seam metric tells internal edges from folds also on faces that keep their own unwrap."""
    verts, tris = mesh['verts'], mesh['tris']
    keys = {}
    for f in faces:
        n = tri_normal(verts, tris[f])[0]
        key = (mesh['mat_ids'][f],) + ((round(n[0] * 1000), round(n[1] * 1000), round(n[2] * 1000),
                                        round(_dot(n, verts[tris[f][0]]) * 1000)) if n else ('degenerate', f))
        keys.setdefault(key, []).append(f)
    out = {}
    for r, comp in enumerate(c for key in sorted(keys, key=repr) for c in _components(mesh, keys[key])):
        for f in comp:
            out[f] = (tag, r)
    return out


def walls(mesh, faces, corner_xy=None):
    """Group the given triangles into planar walls: {'key', 'mat', 'n', 't', 'faces', 'area', 'corners'}.

    A wall is the EDGE-CONNECTED triangles of one material on one vertical plane (normal direction 1e-3, offset
    1 mm): two segments of one facade plane split by a bay are two walls of the perimeter chain. `t` is the
    horizontal tangent z x n (the texture reads left to right seen from outside); `corners` are the plan keys of
    its vertices (to find neighbours of the chain); `corner_xy` (filled when given) maps a key to the exact plan
    position of its smallest vertex, so a corner is never rounded (1 mm rounding gave 0.49 px)."""
    verts = mesh['verts']
    planes = {}
    for f in faces:
        n, area = tri_normal(verts, mesh['tris'][f])
        if n is None or abs(n[2]) >= VERTICAL_NZ:
            continue
        h = math.hypot(n[0], n[1])
        nx, ny = n[0] / h, n[1] / h
        p0 = verts[mesh['tris'][f][0]]
        d = nx * p0[0] + ny * p0[1]
        key = (mesh['mat_ids'][f], round(nx * 1000), round(ny * 1000), round(d * 1000))
        planes.setdefault(key, []).append((f, nx, ny, area))
    out = []
    for key in sorted(planes):
        info = {f: (nx, ny, area) for f, nx, ny, area in planes[key]}
        for k, comp in enumerate(_components(mesh, sorted(info))):
            g = {'key': key + (k,), 'mat': key[0], 'faces': comp, 'area': 0.0, 'corners': set()}
            sx = sy = 0.0
            for f in comp:
                nx, ny, area = info[f]
                g['area'] += area
                sx += nx * area
                sy += ny * area
                for i in mesh['tris'][f]:
                    x, y = verts[i][0], verts[i][1]
                    c = _pkey(x, y)
                    g['corners'].add(c)
                    if corner_xy is not None and (c not in corner_xy or (x, y) < corner_xy[c]):
                        corner_xy[c] = (x, y)
            h = math.hypot(sx, sy)
            g['n'] = (sx / h, sy / h, 0.0)
            g['t'] = (-sy / h, sx / h, 0.0)
            out.append(g)
    return out


def chain_walls(wall_list, zero, corner_xy=None):
    """Perimeter unroll: s0 and anchor A per wall, so u is continuous at every corner of the chain.

    A component starts at its largest wall with the axis projection from the common zero (A = zero, s0 = 0) and
    walks FORWARD along t (the next wall at the end corner, largest first) until the loop closes, so the one
    unavoidable seam of a closed perimeter whose length is not a whole number of periods is at the START corner
    of the root wall. Walls off that walk (reveals, bays reached from the side) hang on the first assigned wall
    sharing a plan corner. A neighbour at the plan corner C gets A = C and
    s0 = s0_parent + (C - A_parent) . t_parent. Returns {wall index: {'s0', 'A', 'parent', 'corner'}}."""
    by_corner = {}
    for i, w in enumerate(wall_list):
        for c in w['corners']:
            by_corner.setdefault(c, []).append(i)
    done = {}

    def rank(j):
        return (-round(wall_list[j]['area'], 6), wall_list[j]['key'])

    def attach(i, c, j):
        wi, di = wall_list[i], done[i]
        cx, cy = corner_xy[c] if corner_xy else (c[0] * 1e-3, c[1] * 1e-3)
        s0 = di['s0'] + (cx - di['A'][0]) * wi['t'][0] + (cy - di['A'][1]) * wi['t'][1]
        done[j] = {'s0': s0, 'A': (cx, cy), 'parent': i, 'corner': [cx, cy]}

    for root in sorted(range(len(wall_list)), key=rank):
        if root in done:
            continue
        done[root] = {'s0': 0.0, 'A': (zero[0], zero[1]), 'parent': None, 'corner': None}
        comp, cur = [root], root
        while True:
            w = wall_list[cur]
            end = max(sorted(w['corners']), key=lambda c: c[0] * w['t'][0] + c[1] * w['t'][1])
            cands = sorted((j for j in by_corner[end] if j not in done), key=rank)
            if not cands:
                break
            attach(cur, end, cands[0])
            cur = cands[0]
            comp.append(cur)
        k = 0
        while k < len(comp):
            i = comp[k]
            k += 1
            for c in sorted(wall_list[i]['corners']):
                for j in sorted(by_corner[c], key=rank):
                    if j not in done:
                        attach(i, c, j)
                        comp.append(j)
    return done


def _fn_uv(fn, p, P):
    O, a, b, u0, v0 = fn
    q = (p[0] - O[0], p[1] - O[1], p[2] - O[2])
    return [(u0 + _dot(q, a)) / P, (v0 + _dot(q, b)) / P]


def _edge_key(p):
    return tuple(round(c / _KEY_M) for c in p)


def project_k6(mesh, faces, grid_zero_m, period_of, unroll=True):
    """K6 UV of the given triangles: ({face: [[u, v] x 3]}, {face: plane id}, walls info for the report,
    chain pairs: {frozenset of two plane ids} joined by the unroll, where the seam must be 0).

    Every face gets an isometric affine projection `u = (u0 + (p - O) . a) / P`, `v = (v0 + (p - O) . b) / P`
    (P = period_of(mat) metres; the texel is exact by construction):
    * walls (|n.z| < 0.5): the perimeter unroll (`unroll=False`: projection by axes from the common zero, which
      tears corners - kept only for the lab comparison); u along t, v = z - z0;
    * other faces of the same material sharing a horizontal edge with a projected wall (sills, soffits, parapet
      caps, a roof at the wall): u continues the wall's u along the edge, v continues the wall's v at the edge and
      runs into the face (true distance in the face plane), oriented like the face; coplanar neighbours inherit;
    * the rest: plan projection (x, y) from the zero, mirrored for downward faces.
    Faces with one plane id are on one plane (internal edges); different ids meet at corners."""
    verts, tris = mesh['verts'], mesh['tris']
    z0 = grid_zero_m
    corner_xy = {}
    wl = walls(mesh, faces, corner_xy)
    chain = chain_walls(wl, z0, corner_xy) if unroll else {i: {'s0': 0.0, 'A': (z0[0], z0[1]), 'parent': None,
                                                     'corner': None} for i in range(len(wl))}
    fn, plane = {}, {}
    for i, w in enumerate(wl):
        c = chain[i]
        f_ = ((c['A'][0], c['A'][1], z0[2]), w['t'], (0.0, 0.0, 1.0), c['s0'], 0.0)
        for f in w['faces']:
            fn[f] = f_
            plane[f] = ('w', i)
    pairs = {frozenset((('w', i), ('w', c['parent']))) for i, c in chain.items() if c['parent'] is not None}
    rest = [f for f in faces if f not in fn]
    normal = {f: tri_normal(verts, tris[f])[0] for f in rest}
    regions = {}
    for f in rest:
        n = normal[f]
        if n is None:
            continue
        p0 = verts[tris[f][0]]
        key = (mesh['mat_ids'][f], round(n[0] * 1000), round(n[1] * 1000), round(n[2] * 1000),
               round(_dot(n, p0) * 1000))
        regions.setdefault(key, []).append(f)
    regs = [comp for key in sorted(regions) for comp in _components(mesh, regions[key])]
    edges = {}
    for f in faces:
        t = tris[f]
        for j in range(3):
            ka, kb = _edge_key(verts[t[j]]), _edge_key(verts[t[(j + 1) % 3]])
            if ka != kb:
                edges.setdefault((min(ka, kb), max(ka, kb)), []).append((f, t[j], t[(j + 1) % 3]))
    region_of = {f: r for r, comp in enumerate(regs) for f in comp}
    cands = {}
    for users in edges.values():
        for f, a, b in users:
            if f not in region_of:
                continue
            for g, _a, _b in users:
                if g in fn and plane[g][0] == 'w' and mesh['mat_ids'][g] == mesh['mat_ids'][f]:
                    pa, pb = verts[a], verts[b]
                    ed = _sub(pb, pa)
                    t = fn[g][1]
                    ln = _norm(ed)
                    if abs(pa[2] - pb[2]) <= 1e-6 and abs(_dot(ed, t)) >= 0.999 * ln:
                        cands.setdefault(region_of[f], []).append((-round(ln, 9), g, f, a, b))
    for r, comp in enumerate(regs):
        if r not in cands:
            continue
        _ln, g, f, a, b = min(cands[r])  # the longest horizontal edge on a wall (a sill over a jamb)
        pa = verts[a]
        t = fn[g][1]
        N = normal[f]
        m = _cross(N, t)
        lm = _norm(m)
        m = (m[0] / lm, m[1] / lm, m[2] / lm)
        third = [verts[i] for i in tris[f] if i not in (a, b)]
        if third and _dot(_sub(third[0], pa), m) < 0:
            m = (-m[0], -m[1], -m[2])
        sgn = 1.0 if _dot(_cross(t, m), N) > 0 else -1.0  # (a x b) . N > 0: not mirrored
        ua, va = _fn_uv(fn[g], pa, 1.0)
        f_ = (tuple(pa), t, (m[0] * sgn, m[1] * sgn, m[2] * sgn), ua, va)
        for h in comp:
            fn[h] = f_
            plane[h] = ('h', r)
        pairs.add(frozenset((('h', r), plane[g])))
    uv = {}
    for f in faces:
        P = period_of(mesh['mat_ids'][f])
        if f in fn:
            uv[f] = [_fn_uv(fn[f], verts[vi], P) for vi in tris[f]]
            continue
        n = normal.get(f)
        sign = -1.0 if (n is not None and n[2] < 0) else 1.0
        uv[f] = [[sign * (verts[vi][0] - z0[0]) / P, (verts[vi][1] - z0[1]) / P] for vi in tris[f]]
        plane[f] = ('p', region_of.get(f, -1))
    wall_of = plane
    info = [{'mat': w['mat'], 'faces': len(w['faces']), 'n': [round(w['n'][0], 6), round(w['n'][1], 6)],
             's0_m': round(chain[i]['s0'], 9), 'parent': chain[i]['parent'], 'corner': chain[i]['corner']}
            for i, w in enumerate(wl)]
    return uv, wall_of, info, pairs


# ---- cut by the integer UV grid --------------------------------------------------------------------------------
def _split(poly, axis, k):
    """Split a convex polygon [(w, uv)...] by the line uv[axis] = k -> (below, above); pieces may be None."""
    below, above = [], []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        da, db = a[1][axis] - k, b[1][axis] - k
        if da <= _EPS_UV:
            below.append(a)
        if da >= -_EPS_UV:
            above.append(a)
        if (da < -_EPS_UV and db > _EPS_UV) or (da > _EPS_UV and db < -_EPS_UV):
            # canonical order of the endpoints by UV (the same on both triangles of a shared edge of one
            # projection), so both triangles get the same cut point
            p, q = (a, b) if tuple(a[1]) <= tuple(b[1]) else (b, a)
            dp, dq = p[1][axis] - k, q[1][axis] - k
            s = dp / (dp - dq)
            w = [p[0][j] + (q[0][j] - p[0][j]) * s for j in range(3)]
            uv = [p[1][j] + (q[1][j] - p[1][j]) * s for j in range(2)]
            uv[axis] = float(k)
            pt = (w, uv)
            below.append(pt)
            above.append(pt)

    def ok(pp):
        if len(pp) < 3:
            return None
        area = 0.0
        for i in range(len(pp)):
            (u1, v1), (u2, v2) = pp[i][1], pp[(i + 1) % len(pp)][1]
            area += u1 * v2 - u2 * v1
        return pp if abs(area) > 1e-14 else None
    return ok(below), ok(above)


def cut_grid(uv_of_face, mat_of_face):
    """Cut every triangle by the integer lines u = k and v = k of its UV -> pieces inside one UV cell each.

    uv_of_face: {face: [[u, v] x 3]}. Returns [{'tri', 'w', 'uv', 'mat'}] in face order; a triangle that lies in
    one cell is one piece (its weights are the identity)."""
    pieces = []
    eye = ([1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0])
    for f in sorted(uv_of_face):
        poly = [(list(eye[j]), [float(c) for c in uv_of_face[f][j]]) for j in range(3)]
        work = [poly]
        for axis in (0, 1):
            nxt = []
            for pp in work:
                lo = min(p[1][axis] for p in pp)
                hi = max(p[1][axis] for p in pp)
                k = math.floor(lo + _EPS_UV) + 1
                rest = pp
                while rest is not None and k < hi - _EPS_UV:
                    below, rest = _split(rest, axis, k)
                    if below is not None:
                        nxt.append(below)
                    k += 1
                if rest is not None:
                    nxt.append(rest)
            work = nxt
        for pp in work:
            pieces.append({'tri': f, 'w': [p[0] for p in pp], 'uv': [p[1] for p in pp], 'mat': mat_of_face[f]})
    return pieces


def _cell(uv):
    cu = sum(p[0] for p in uv) / len(uv)
    cv = sum(p[1] for p in uv) / len(uv)
    return math.floor(cu), math.floor(cv)


def shift_into_tiles(pieces, tile_of_mat):
    """Move every piece by the WHOLE vector tile_origin(T) - floor(centroid) (K6). Returns the pieces (new uv)."""
    out = []
    for p in pieces:
        T = tile_of_mat[p['mat']]
        tu, tv = tile_origin(T)
        cu, cv = _cell(p['uv'])
        du, dv = tu - cu, tv - cv
        out.append(dict(p, uv=[[u + du, v + dv] for u, v in p['uv']], shift=[int(du), int(dv)], tile=T))
    return out


def crossing_pieces(pieces):
    """Pieces whose UV spans more than one tile (norm 0 after cut_grid)."""
    bad = []
    for i, p in enumerate(pieces):
        cu, cv = _cell(p['uv'])
        if any(u < cu - 1e-7 or u > cu + 1 + 1e-7 or v < cv - 1e-7 or v > cv + 1 + 1e-7 for u, v in p['uv']):
            bad.append(i)
    return bad


# ---- seam metric ---------------------------------------------------------------------------------------------
def _frac_px(a, b, tile_px):
    d = a - b
    return abs(d - round(d)) * tile_px


def piece_positions(mesh, pieces):
    """World metres of every piece corner (weights over the source triangle)."""
    verts, tris = mesh['verts'], mesh['tris']
    out = []
    for p in pieces:
        a, b, c = (verts[i] for i in tris[p['tri']])
        out.append([[w[0] * a[j] + w[1] * b[j] + w[2] * c[j] for j in range(3)] for w in p['w']])
    return out


def seam_metric(mesh, pieces, tile_px=TILE_PX, wall_of=None, chain_pairs=None):
    """Fractional UV mismatch on shared edges of pieces of the same material, in texels of tile_px.

    Edges are matched by position (0.01 mm), so unwelded neighbours count too. `wall_of` {face: plane id} and
    `chain_pairs` (project_k6) sort the edges: `internal` (one plane) and `chain` (two planes joined by the unroll)
    have the norm 0; `fold` (the closing corner of a perimeter whose length is not a whole number of periods, the
    three-plane corners of reveals) is reported, it cannot be 0 for every edge of a fold. Returns {'internal_max',
    'internal_mean', 'chain_max', 'fold_max', 'edges', 'bad': [{'faces', 'px', 'kind'}] over SEAM_TOL_PX}."""
    pos = piece_positions(mesh, pieces)
    edges = {}
    for pi, (p, pp) in enumerate(zip(pieces, pos)):
        n = len(pp)
        for j in range(n):
            ka = tuple(round(c / _KEY_M) for c in pp[j])
            kb = tuple(round(c / _KEY_M) for c in pp[(j + 1) % n])
            if ka == kb:
                continue
            ea, eb = (ka, j), (kb, (j + 1) % n)
            if kb < ka:
                ea, eb = eb, ea
            edges.setdefault((ea[0], eb[0]), []).append((pi, ea[1], eb[1]))
    vals = {'internal': [], 'chain': [], 'fold': []}
    bad, count = [], 0
    for key in sorted(edges):
        users = edges[key]
        for x in range(len(users)):
            for y in range(x + 1, len(users)):
                (pa, a0, a1), (pb, b0, b1) = users[x], users[y]
                A, B = pieces[pa], pieces[pb]
                if A['mat'] != B['mat']:
                    continue
                count += 1
                px = max(_frac_px(A['uv'][a][k], B['uv'][b][k], tile_px) for a, b in ((a0, b0), (a1, b1))
                         for k in (0, 1))
                if not wall_of or wall_of.get(A['tri']) == wall_of.get(B['tri']):
                    kind = 'internal'
                elif chain_pairs and frozenset((wall_of.get(A['tri']), wall_of.get(B['tri']))) in chain_pairs:
                    kind = 'chain'
                else:
                    kind = 'fold'
                vals[kind].append(px)
                if px > SEAM_TOL_PX:
                    bad.append({'faces': sorted({A['tri'], B['tri']}), 'px': round(px, 4), 'kind': kind})
    return {'internal_max': round(max(vals['internal'], default=0.0), 6),
            'internal_mean': round(sum(vals['internal']) / len(vals['internal']), 6) if vals['internal'] else 0.0,
            'chain_max': round(max(vals['chain'], default=0.0), 6),
            'fold_max': round(max(vals['fold'], default=0.0), 6), 'edges': count, 'bad': bad}


# ---- island-level contract of branch 0 (read by branch P) -----------------------------------------------------
def layout_seamless(islands, grid_zero_m, module_m, texel_px_per_m, tile_px, options=None):
    """K6 seam-to-seam layout: islands keep their texel, move only by whole tile vectors (bricks: whole repeats).

    islands: [{'id': ..., 'uv': [[u, v]...], 'world': [[x, y, z]...] metres, 'library_id': int}];
    grid_zero_m: the project grid zero from the passport; module_m: module per recipe; UDIM step 3.6 m
    (owner answer 06.11.2026). Returns {'islands': [{'id', 'shift': [du, dv] integers, 'tile': udim,
    'cut': bool}], 'seam_texels': float (norm 0), 'moved': [{'id', 'why'}]}.

    The tile of an island is chosen by the WHOLE island (area-weighted UV centroid, plain floor: no modulo or
    truncation, P41). An island across a tile line gets `cut: True`: the caller cuts it by the UV grid
    (`cut_grid`, geometry) before the shift; a module that does not divide the UDIM step is reported in `moved`
    (the shift stays whole, the repeat phase is kept). options: {'udim_table': {library_id: udim}} (default: dense
    from 1001 over the islands' library ids, per mesh)."""
    options = dict(options or {})
    unknown = set(options) - {'udim_table'}
    if unknown:
        raise ValueError('unknown layout_seamless options: ' + ', '.join(sorted(unknown)))
    for name, v in (('module_m', module_m), ('texel_px_per_m', texel_px_per_m), ('tile_px', tile_px)):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            raise ValueError('{} must be a positive number: {!r}'.format(name, v))
    if len(grid_zero_m) != 3:
        raise ValueError('grid_zero_m must be [x, y, z] metres')
    if not islands:
        raise ValueError('no islands to lay out')
    table = options.get('udim_table') or renumber_dense(isl['library_id'] for isl in islands)
    step = tile_px / float(texel_px_per_m)
    reps = step / float(module_m)
    out, moved, placed = [], [], []
    for isl in islands:
        uv = isl['uv']
        if not uv:
            raise ValueError('island without UV: {!r}'.format(isl.get('id')))
        lid = isl['library_id']
        if lid not in table:
            raise ValueError('library id without a UDIM: {!r}'.format(lid))
        T = table[lid]
        tu, tv = tile_origin(T)
        cu, cv = _island_centroid(uv)
        du, dv = tu - math.floor(cu), tv - math.floor(cv)
        lo_u, hi_u = min(p[0] for p in uv), max(p[0] for p in uv)
        lo_v, hi_v = min(p[1] for p in uv), max(p[1] for p in uv)
        cut = (math.floor(lo_u + _EPS_UV) != math.ceil(hi_u - _EPS_UV) - 1 or
               math.floor(lo_v + _EPS_UV) != math.ceil(hi_v - _EPS_UV) - 1)
        out.append({'id': isl['id'], 'shift': [int(du), int(dv)], 'tile': T, 'cut': bool(cut)})
        if cut:
            moved.append({'id': isl['id'], 'why': 'crosses a tile line: cut by the UV grid, pieces keep the fraction'})
        placed.append((isl, du, dv))
    if abs(reps - round(reps)) > 1e-6:
        moved.append({'id': None, 'why': 'UDIM step {:.4f} m is not a whole number of {:.4f} m modules: the tile '
                                         'edge is a seam of the pattern'.format(step, module_m)})
    seam = 0.0
    seen = {}
    for isl, du, dv in placed:
        for w, p in zip(isl.get('world') or (), isl['uv']):
            key = (isl['library_id'],) + tuple(round(c / _KEY_M) for c in w)
            q = (p[0] + du, p[1] + dv)
            if key in seen:
                o = seen[key]
                seam = max(seam, _frac_px(o[0], q[0], tile_px), _frac_px(o[1], q[1], tile_px))
            else:
                seen[key] = q
    return {'islands': out, 'seam_texels': round(seam, 6), 'moved': moved}


def _island_centroid(uv):
    """Area-weighted centroid of an island's UV polygon soup (fan over the listed points); falls back to the mean."""
    if len(uv) >= 3:
        a_sum, cx, cy = 0.0, 0.0, 0.0
        u0, v0 = uv[0]
        for i in range(1, len(uv) - 1):
            (u1, v1), (u2, v2) = uv[i], uv[i + 1]
            a = 0.5 * ((u1 - u0) * (v2 - v0) - (u2 - u0) * (v1 - v0))
            a_sum += a
            cx += a * (u0 + u1 + u2) / 3.0
            cy += a * (v0 + v1 + v2) / 3.0
        if abs(a_sum) > 1e-12:
            return cx / a_sum, cy / a_sum
    return sum(p[0] for p in uv) / len(uv), sum(p[1] for p in uv) / len(uv)
