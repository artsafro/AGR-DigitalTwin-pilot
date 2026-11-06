"""new-case: AGR Tools 1.0 (#1024) grid cleanup logic, stdlib only. owned by branch H (improve/issue-1024-grid-glass).

Pure logic for `model_grid_cleanup` (model.grid_cleanup); no pymxs. The glue (gridclean_max.py) reads one polygon mesh
per node and rebuilds the export COPY from `clean()`; the working object is never touched.

Mesh (host-neutral, contract_core: the core never takes a host object):
    {'verts': [[x, y, z], ...]   world space, METRES (host_max: units.SystemScale);
     'faces': [{'v': [i, ...], 'uv': [[u, v], ...] | None, 'mat': int, 'sg': int}, ...],
     'uv': True | False          map channel 1 present on the object}

Modes (#1024 «редакция 1», row 17; team audit T03 / runtime findings T08 name the source defects):
* `tjunctions` — a vertex lying on another face's edge (T-vertex) is inserted into that edge (`t_mode: cut`, default),
  so every T disappears without moving a vertex; `t_mode: weld` merges vertices closer than `weld_m` but ONLY inside the
  vertex selection (source: Edges Weld welded the whole object, T08-04; Corners Weld without a selection welded all at
  1 mm, T08-16); a weld is computed on the data in one pass, so no index shifts (Target Weld, T08-07). An empty
  selection in weld mode is `skipped`, never a whole-object weld.
* `detriangulate` — two triangles sharing their mutual longest edge become one quad, only when MatID, smoothing group
  and UV island agree (no seam on the edge), the pair is coplanar within `coplanar_deg` and the quad is convex. SG and
  MatID are kept (source Detriangulator set SG 0); a mesh without map channel 1 is `skipped` (source crashed).
* `loops` — an edge loop across a flat region is dissolved only when every face it touches stays a convex quad and no
  UV seam, MatID or SG border lies on it (Border Loop Cleaner merged UV islands, T03); then 2-edge vertices on a
  straight line (geometry within `line_m`, UV linear) are removed.
Opening corners are protected: a vertex is removed only when it lies on a straight line in every face that uses it,
so a corner never goes; in weld mode a protected vertex (auto: border corners; plus `protect`) never moves.
All thresholds are metres (source: millimetres of the scene units, T03); the glue converts scene units once.
No hidden copies: the core returns data; the glue rebuilds exactly one copy per node.
"""
import math

TOOL = 'model.grid_cleanup'
MODES = ('tjunctions', 'detriangulate', 'loops')
T_MODES = ('cut', 'weld', 'off')
DEFAULTS = {'modes': list(MODES), 't_mode': 'cut', 'tol_m': 0.001, 'weld_m': 0.001, 'line_m': 0.001,
            'coplanar_deg': 1.0, 'uv_tol': 1e-4}
OPTIONS = set(DEFAULTS) | {'protect'}
UV_EQ = 1e-6


# ---- options ---------------------------------------------------------------------------------------------------
def options(raw):
    """Validated options (unknown keys, wrong types and non-positive thresholds are errors)."""
    raw = dict(raw or {})
    unknown = set(raw) - OPTIONS
    if unknown:
        raise ValueError('unknown model.grid_cleanup options: ' + ', '.join(sorted(unknown)))
    out = dict(DEFAULTS)
    out.update({k: v for k, v in raw.items() if k != 'protect'})
    modes = out['modes']
    if isinstance(modes, str):
        modes = [modes]
    if not isinstance(modes, list) or not modes or any(m not in MODES for m in modes):
        raise ValueError('options.modes must be a non-empty list of ' + ', '.join(MODES))
    out['modes'] = [m for m in MODES if m in modes]
    if out['t_mode'] not in T_MODES:
        raise ValueError('options.t_mode must be one of ' + ', '.join(T_MODES))
    for k in ('tol_m', 'weld_m', 'line_m', 'coplanar_deg', 'uv_tol'):
        v = out[k]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            raise ValueError('options.{} must be a positive number'.format(k))
        out[k] = float(v)
    return out


# ---- vector helpers --------------------------------------------------------------------------------------------
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


def _len(a):
    return math.sqrt(_dot(a, a))


def _dist_to_line(p, a, b):
    ab = _sub(b, a)
    n = _len(ab)
    if n < 1e-12:
        return _len(_sub(p, a))
    return _len(_cross(_sub(p, a), ab)) / n


def _seg_param(p, a, b):
    ab = _sub(b, a)
    d = _dot(ab, ab)
    return _dot(_sub(p, a), ab) / d if d > 1e-24 else 0.0


def normal(verts, ring):
    """Newell normal (unnormalised) of a polygon ring."""
    n = [0.0, 0.0, 0.0]
    for i, a in enumerate(ring):
        p, q = verts[a], verts[ring[(i + 1) % len(ring)]]
        n[0] += (p[1] - q[1]) * (p[2] + q[2])
        n[1] += (p[2] - q[2]) * (p[0] + q[0])
        n[2] += (p[0] - q[0]) * (p[1] + q[1])
    return n


def area(verts, ring):
    return _len(normal(verts, ring)) / 2.0


def _unit(a):
    n = _len(a)
    return [a[0] / n, a[1] / n, a[2] / n] if n > 1e-18 else [0.0, 0.0, 0.0]


def _angle_deg(n1, n2):
    a, b = _unit(n1), _unit(n2)
    return math.degrees(math.acos(max(-1.0, min(1.0, _dot(a, b)))))


def convex(verts, ring, tol=1e-9):
    """Strictly convex polygon (every turn has the sign of the face normal; no collinear corner)."""
    n = _unit(normal(verts, ring))
    if _len(n) == 0:
        return False
    k = len(ring)
    for i in range(k):
        a, b, c = verts[ring[i - 1]], verts[ring[i]], verts[ring[(i + 1) % k]]
        t = _dot(_cross(_sub(b, a), _sub(c, b)), n)
        if t <= tol * max(_len(_sub(b, a)), 1e-9) * max(_len(_sub(c, b)), 1e-9):
            return False
    return True


# ---- mesh model ------------------------------------------------------------------------------------------------
def copy_mesh(mesh):
    faces = []
    for f in mesh['faces']:
        faces.append({'v': list(f['v']), 'uv': None if f.get('uv') is None else [list(t) for t in f['uv']],
                      'mat': int(f.get('mat', 1)), 'sg': int(f.get('sg', 0))})
    return {'verts': [list(map(float, p)) for p in mesh['verts']], 'faces': faces, 'uv': bool(mesh.get('uv'))}


def check_mesh(mesh):
    if not isinstance(mesh, dict) or not isinstance(mesh.get('verts'), list) or not isinstance(mesh.get('faces'), list):
        raise ValueError('mesh must be {verts, faces, uv}')
    nv = len(mesh['verts'])
    for i, f in enumerate(mesh['faces']):
        v = f.get('v')
        if not isinstance(v, list) or len(v) < 3 or any(not isinstance(x, int) or not 0 <= x < nv for x in v):
            raise ValueError('face {} has invalid vertex ids'.format(i + 1))
        if f.get('uv') is not None and len(f['uv']) != len(v):
            raise ValueError('face {} uv corners != vertices'.format(i + 1))
    return mesh


def edges(mesh):
    """Undirected edge (a, b), a < b -> [(face index, corner index of a->b)]."""
    out = {}
    for fi, f in enumerate(mesh['faces']):
        ring = f['v']
        for ci, a in enumerate(ring):
            b = ring[(ci + 1) % len(ring)]
            out.setdefault((min(a, b), max(a, b)), []).append((fi, ci))
    return out


def _uv_at(face, vid):
    if face['uv'] is None:
        return None
    return face['uv'][face['v'].index(vid)]


def _uv_same(p, q, tol=UV_EQ):
    if p is None or q is None:
        return p is None and q is None
    return abs(p[0] - q[0]) <= tol and abs(p[1] - q[1]) <= tol


def seam(mesh, f1, f2, a, b):
    """True when faces f1 and f2 do not share UVs on the edge (a, b): a UV seam (island border)."""
    F1, F2 = mesh['faces'][f1], mesh['faces'][f2]
    return not (_uv_same(_uv_at(F1, a), _uv_at(F2, a)) and _uv_same(_uv_at(F1, b), _uv_at(F2, b)))


def uv_islands(mesh):
    """Number of UV islands: faces joined through edges without a seam (faces without UV: geometric connectivity)."""
    parent = list(range(len(mesh['faces'])))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for (a, b), uses in edges(mesh).items():
        for i in range(len(uses)):
            for j in range(i + 1, len(uses)):
                f1, f2 = uses[i][0], uses[j][0]
                if not seam(mesh, f1, f2, a, b):
                    parent[find(f1)] = find(f2)
    return len({find(i) for i in range(len(parent))})


def stats(mesh):
    faces = mesh['faces']
    return {'verts': len(mesh['verts']), 'faces': len(faces),
            'tris': sum(1 for f in faces if len(f['v']) == 3),
            'quads': sum(1 for f in faces if len(f['v']) == 4),
            'ngons': sum(1 for f in faces if len(f['v']) > 4),
            'uv_islands': uv_islands(mesh) if mesh['uv'] else None,
            'mat_ids': sorted({f['mat'] for f in faces}), 'sgs': sorted({f['sg'] for f in faces}),
            't_vertices': len(t_vertices(mesh, DEFAULTS['tol_m']))}


def used_verts(mesh):
    return sorted({v for f in mesh['faces'] for v in f['v']})


def compact(mesh):
    """Drop unused vertices; returns (mesh, old->new map). Faces keep their order."""
    keep = used_verts(mesh)
    remap = {old: new for new, old in enumerate(keep)}
    out = {'verts': [mesh['verts'][i] for i in keep], 'uv': mesh['uv'], 'faces': []}
    for f in mesh['faces']:
        out['faces'].append(dict(f, v=[remap[v] for v in f['v']]))
    return out, remap


# ---- protected vertices ----------------------------------------------------------------------------------------
def border_corners(mesh, line_m):
    """Vertices where a border (opening or outline) turns: the opening corners. They never move or go."""
    border = {}
    for (a, b), uses in edges(mesh).items():
        if len(uses) != 1:
            continue
        border.setdefault(a, []).append(b)
        border.setdefault(b, []).append(a)
    corners = set()
    verts = mesh['verts']
    for v, nb in border.items():
        if len(nb) != 2:
            corners.add(v)  # a T on the border or a pinch: keep it
            continue
        p, q = verts[nb[0]], verts[nb[1]]
        if _dist_to_line(verts[v], p, q) > line_m or not 0.0 < _seg_param(verts[v], p, q) < 1.0:
            corners.add(v)
    return corners


# ---- T-junctions -----------------------------------------------------------------------------------------------
def _grid(verts, cell):
    g = {}
    for i, p in enumerate(verts):
        g.setdefault(tuple(int(math.floor(c / cell)) for c in p), []).append(i)
    return g


def _near_segment(g, cell, verts, a, b, tol):
    lo = [min(verts[a][k], verts[b][k]) - tol for k in range(3)]
    hi = [max(verts[a][k], verts[b][k]) + tol for k in range(3)]
    span = [int(math.floor(hi[k] / cell)) - int(math.floor(lo[k] / cell)) for k in range(3)]
    if span[0] * span[1] * span[2] > 20000:  # very long edge: scan all vertices once
        return range(len(verts))
    out = []
    for x in range(int(math.floor(lo[0] / cell)), int(math.floor(hi[0] / cell)) + 1):
        for y in range(int(math.floor(lo[1] / cell)), int(math.floor(hi[1] / cell)) + 1):
            for z in range(int(math.floor(lo[2] / cell)), int(math.floor(hi[2] / cell)) + 1):
                out.extend(g.get((x, y, z), ()))
    return out


def t_vertices(mesh, tol_m):
    """[(face index, corner index, vertex, t)]: vertex lies strictly inside edge corner->corner+1 of a face that does
    not use it (distance <= tol_m). Only border-like edges (used by one face) can carry a T."""
    verts = mesh['verts']
    used = set(used_verts(mesh))
    cell = 0.5
    g = _grid([verts[i] if i in used else [1e18, 1e18, 1e18] for i in range(len(verts))], cell)
    out = []
    for (a, b), uses in edges(mesh).items():
        if len(uses) != 1:
            continue
        fi, ci = uses[0]
        ring = mesh['faces'][fi]['v']
        length = _len(_sub(verts[b], verts[a]))
        if length <= 2 * tol_m:
            continue
        for v in _near_segment(g, cell, verts, a, b, tol_m):
            if v in (a, b) or v not in used or v in ring:
                continue
            t = _seg_param(verts[v], verts[a], verts[b])
            if t * length <= tol_m or (1 - t) * length <= tol_m:
                continue
            if _dist_to_line(verts[v], verts[a], verts[b]) <= tol_m:
                s, e = ring[ci], ring[(ci + 1) % len(ring)]
                out.append((fi, ci, v, t if s == a else 1 - t))
    return out


def cut_tjunctions(mesh, tol_m):
    """Insert every T-vertex into the edge it lies on (all of them: source VES split one per edge). Returns count."""
    found = t_vertices(mesh, tol_m)
    by_edge = {}
    for fi, ci, v, t in found:
        by_edge.setdefault((fi, ci), []).append((t, v))
    for fi in sorted({fi for fi, _ in by_edge}, reverse=False):
        f = mesh['faces'][fi]
        ring, uvs = f['v'], f['uv']
        new_ring, new_uv = [], [] if uvs is not None else None
        for ci, a in enumerate(ring):
            new_ring.append(a)
            if uvs is not None:
                new_uv.append(uvs[ci])
            for t, v in sorted(by_edge.get((fi, ci), ())):
                new_ring.append(v)
                if uvs is not None:
                    p, q = uvs[ci], uvs[(ci + 1) % len(ring)]
                    new_uv.append([p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t])
        f['v'], f['uv'] = new_ring, new_uv
    return len(found)


def weld_selected(mesh, selected, weld_m, protect):
    """Merge vertices closer than weld_m when BOTH are selected; a protected vertex is the target and never moves.
    Computed in one pass on the data (no index shift between welds). Returns [(from, to)]."""
    verts = mesh['verts']
    sel = sorted(set(selected) & set(used_verts(mesh)))
    parent = {v: v for v in sel}

    def find(v):
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v
    g = _grid([verts[v] for v in sel], max(weld_m * 4, 1e-6))
    pos = {v: i for i, v in enumerate(sel)}
    for v in sel:
        p = verts[v]
        key = tuple(int(math.floor(c / max(weld_m * 4, 1e-6))) for c in p)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for j in g.get((key[0] + dx, key[1] + dy, key[2] + dz), ()):
                        w = sel[j]
                        if w > v and _len(_sub(verts[w], p)) <= weld_m:
                            ra, rb = find(v), find(w)
                            if ra != rb:
                                parent[max(ra, rb)] = min(ra, rb)
    del pos
    groups = {}
    for v in sel:
        groups.setdefault(find(v), []).append(v)
    pairs = []
    for members in groups.values():
        if len(members) < 2:
            continue
        fixed = [m for m in members if m in protect]
        target = min(fixed) if fixed else min(members)  # a protected point is the target and stays where it is
        for m in members:
            if m != target:
                pairs.append((m, target))
    remap = dict(pairs)
    for f in mesh['faces']:
        ring = [remap.get(v, v) for v in f['v']]
        uvs = f['uv']
        new_ring, new_uv = [], [] if uvs is not None else None
        for i, v in enumerate(ring):
            if new_ring and new_ring[-1] == v:
                continue
            new_ring.append(v)
            if uvs is not None:
                new_uv.append(uvs[i])
        if len(new_ring) > 1 and new_ring[0] == new_ring[-1]:
            new_ring.pop()
            if new_uv is not None:
                new_uv.pop()
        f['v'], f['uv'] = new_ring, new_uv
    mesh['faces'] = [f for f in mesh['faces'] if len(f['v']) >= 3]
    return pairs


# ---- detriangulation -------------------------------------------------------------------------------------------
def _longest(verts, ring):
    best, key = -1.0, None
    for i, a in enumerate(ring):
        b = ring[(i + 1) % len(ring)]
        d = _len(_sub(verts[b], verts[a]))
        if d > best + 1e-12:
            best, key = d, (min(a, b), max(a, b))
    return key


def _merge_rings(f1, f2, a, b):
    """Polygon of f1 + f2 joined on the shared edge (a, b), with per-corner UV of the faces."""
    r1, r2 = f1['v'], f2['v']
    i = r1.index(a)
    if r1[(i + 1) % len(r1)] != b:  # make f1 run a -> b
        a, b = b, a
        i = r1.index(a)
    j = r2.index(b)
    if r2[(j + 1) % len(r2)] != a:
        return None  # inconsistent winding: not merged
    ring, uv = [], [] if f1['uv'] is not None else None
    # f1 from b around to a (skips edge a->b), then f2 after a around to before b (skips b->a)
    k = len(r1)
    for s in range(1, k + 1):
        idx = (i + s) % k
        ring.append(r1[idx])
        if uv is not None:
            uv.append(f1['uv'][idx])
    k2 = len(r2)
    for s in range(2, k2):
        idx = (j + s) % k2
        ring.append(r2[idx])
        if uv is not None:
            uv.append(f2['uv'][idx])
    return ring, uv


def _same_attrs(mesh, f1, f2, a, b):
    F1, F2 = mesh['faces'][f1], mesh['faces'][f2]
    return F1['mat'] == F2['mat'] and F1['sg'] == F2['sg'] and not seam(mesh, f1, f2, a, b)


def detriangulate(mesh, opts):
    """Merge triangle pairs on their mutual longest edge into convex quads. Returns the number of quads made."""
    verts = mesh['verts']
    emap = edges(mesh)
    faces = mesh['faces']
    longest = {fi: _longest(verts, f['v']) for fi, f in enumerate(faces) if len(f['v']) == 3}
    used, merged, made = set(), {}, 0
    for fi in sorted(longest):
        if fi in used:
            continue
        e = longest[fi]
        uses = emap.get(e, ())
        if len(uses) != 2:
            continue
        other = uses[0][0] if uses[1][0] == fi else uses[1][0]
        if other in used or other == fi or longest.get(other) != e:
            continue
        a, b = e
        if not _same_attrs(mesh, fi, other, a, b):
            continue
        if _angle_deg(normal(verts, faces[fi]['v']), normal(verts, faces[other]['v'])) > opts['coplanar_deg']:
            continue
        got = _merge_rings(faces[fi], faces[other], a, b)
        if got is None or len(got[0]) != 4 or not convex(verts, got[0]):
            continue
        used.update((fi, other))
        merged[fi] = dict(faces[fi], v=got[0], uv=got[1])
        made += 1
    mesh['faces'] = [merged.get(fi, f) for fi, f in enumerate(faces) if fi not in used or fi in merged]
    return made


# ---- loops and 2-edge vertices ---------------------------------------------------------------------------------
def _vertex_edges(mesh):
    out = {}
    for (a, b) in edges(mesh):
        out.setdefault(a, set()).add(b)
        out.setdefault(b, set()).add(a)
    return out


def _removable(mesh, v, protect, opts, nbrs=None):
    """A 2-edge vertex lying on a straight line (geometry within line_m, UV linear) in every face that uses it."""
    if v in protect:
        return False
    nbrs = nbrs if nbrs is not None else _vertex_edges(mesh)
    if len(nbrs.get(v, ())) != 2:
        return False
    verts = mesh['verts']
    seen = False
    for f in mesh['faces']:
        ring = f['v']
        if v not in ring:
            continue
        seen = True
        if len(ring) <= 3:
            return False
        i = ring.index(v)
        p, q = ring[i - 1], ring[(i + 1) % len(ring)]
        if _dist_to_line(verts[v], verts[p], verts[q]) > opts['line_m']:
            return False
        t = _seg_param(verts[v], verts[p], verts[q])
        if not 0.0 < t < 1.0:
            return False
        if f['uv'] is not None:
            up, uq, uv = f['uv'][i - 1], f['uv'][(i + 1) % len(ring)], f['uv'][i]
            want = [up[0] + (uq[0] - up[0]) * t, up[1] + (uq[1] - up[1]) * t]
            if abs(want[0] - uv[0]) > opts['uv_tol'] or abs(want[1] - uv[1]) > opts['uv_tol']:
                return False
    return seen


def drop_vertices(mesh, vs):
    vs = set(vs)
    for f in mesh['faces']:
        keep = [i for i, v in enumerate(f['v']) if v not in vs]
        f['v'] = [f['v'][i] for i in keep]
        if f['uv'] is not None:
            f['uv'] = [f['uv'][i] for i in keep]


def remove_line_vertices(mesh, protect, opts):
    """Remove 2-edge vertices on a straight line (ShivaTools Vertex Cleaner idea, metres). Returns count."""
    total = 0
    while True:
        nbrs = _vertex_edges(mesh)
        gone = set()
        for v in sorted(nbrs):
            if v in gone or any(n in gone for n in nbrs[v]):
                continue  # neighbours of a removed vertex are re-checked next round
            if _removable(mesh, v, protect, opts, nbrs):
                gone.add(v)
        if not gone:
            return total
        drop_vertices(mesh, gone)
        total += len(gone)


def _edge_loops(mesh):
    """Edge loops through quad-grid vertices: at a vertex with 4 edges and 4 quads the loop goes straight on."""
    emap = edges(mesh)
    faces = mesh['faces']
    nbrs = _vertex_edges(mesh)

    def opposite(v, prev):
        # edge leaving v that shares no face with edge (prev, v)
        if len(nbrs.get(v, ())) != 4:
            return None
        around = [fi for (fi, _) in [u for e, us in emap.items() if v in e for u in us]]
        if len(set(around)) != 4 or any(len(faces[fi]['v']) != 4 for fi in set(around)):
            return None
        side = {fi for fi, _ in emap[(min(prev, v), max(prev, v))]}
        for w in nbrs[v]:
            if w == prev:
                continue
            fs = {fi for fi, _ in emap[(min(v, w), max(v, w))]}
            if not fs & side:
                return w
        return None
    seen, loops = set(), []
    for e in sorted(emap):
        if e in seen or len(emap[e]) != 2:
            continue
        chain = [e]
        seen.add(e)
        for start, prev in ((e[1], e[0]), (e[0], e[1])):
            v, p = start, prev
            while True:
                w = opposite(v, p)
                if w is None:
                    break
                k = (min(v, w), max(v, w))
                if k in seen or len(emap.get(k, ())) != 2:
                    break
                seen.add(k)
                chain.append(k)
                p, v = v, w
        loops.append(chain)
    return loops


def dissolve_loops(mesh, protect, opts):
    """Dissolve whole edge loops whose removal leaves only convex quads (no seam / MatID / SG / bend on the loop).
    Returns (loops dissolved, edges dissolved)."""
    done_loops = done_edges = 0
    changed = True
    while changed:
        changed = False
        for loop in sorted(_edge_loops(mesh), key=len, reverse=True):
            trial = copy_mesh(mesh)
            ok = True
            for (a, b) in loop:
                emap = edges(trial)
                uses = emap.get((a, b), ())
                if len(uses) != 2:
                    ok = False
                    break
                f1, f2 = uses[0][0], uses[1][0]
                F1, F2 = trial['faces'][f1], trial['faces'][f2]
                if not _same_attrs(trial, f1, f2, a, b) or _angle_deg(
                        normal(trial['verts'], F1['v']), normal(trial['verts'], F2['v'])) > opts['coplanar_deg']:
                    ok = False
                    break
                got = _merge_rings(F1, F2, a, b)
                if got is None:
                    ok = False
                    break
                trial['faces'][f1] = dict(F1, v=got[0], uv=got[1])
                del trial['faces'][f2]
            if not ok:
                continue
            ends = {v for e in loop for v in e}
            nbrs = _vertex_edges(trial)
            gone = {v for v in ends if _removable(trial, v, protect, opts, nbrs)}
            drop_vertices(trial, gone)
            touched = [f for f in trial['faces'] if set(f['v']) & ends or not set(f['v']).isdisjoint(gone)]
            if any(len(f['v']) != 4 or not convex(trial['verts'], f['v']) for f in touched):
                continue
            if trial['uv'] and uv_islands(trial) != uv_islands(mesh):
                continue
            mesh['faces'] = trial['faces']
            done_loops += 1
            done_edges += len(loop)
            changed = True
            break
    return done_loops, done_edges


# ---- the whole row ---------------------------------------------------------------------------------------------
def clean(mesh, opts, selected=None):
    """Clean one mesh (a COPY's data). Returns {'mesh', 'counts', 'before', 'after', 'protected', 'findings',
    'skipped'}; `skipped` is a reason string when the mesh is left as is (no map channel 1 for detriangulation /
    loops, empty selection for weld)."""
    check_mesh(mesh)
    mesh = copy_mesh(mesh)
    before = stats(mesh)
    protect = border_corners(mesh, opts['line_m']) | set(opts.get('protect') or ())
    corners = {v: list(mesh['verts'][v]) for v in sorted(protect)}
    counts = {'t_cut': 0, 'welded': 0, 'quads_made': 0, 'loops': 0, 'loop_edges': 0, 'line_verts': 0}
    needs_uv = {'detriangulate', 'loops'} & set(opts['modes'])
    if needs_uv and not mesh['uv']:
        return {'mesh': mesh, 'counts': counts, 'before': before, 'after': before, 'protected': corners,
                'findings': [], 'skipped': 'no map channel 1: UV islands cannot be kept, object left as is'}
    if 'loops' in opts['modes']:  # noise first: a collinear point keeps a triangle from pairing
        counts['line_verts'] = remove_line_vertices(mesh, protect, opts)
    if 'detriangulate' in opts['modes']:  # before the T cut: a cut triangle is no longer a triangle
        counts['quads_made'] = detriangulate(mesh, opts)
    if 'tjunctions' in opts['modes']:
        if opts['t_mode'] == 'cut':
            counts['t_cut'] = cut_tjunctions(mesh, opts['tol_m'])
        elif opts['t_mode'] == 'weld':
            if not selected:
                return {'mesh': mesh, 'counts': counts, 'before': before, 'after': before, 'protected': corners,
                        'findings': [], 'skipped': 'weld mode needs a vertex selection; nothing welded'}
            pairs = weld_selected(mesh, selected, opts['weld_m'], protect)
            counts['welded'] = len(pairs)
            for src, _ in pairs:  # a selected corner welded onto its partner (<= weld_m): asked for by the user
                corners.pop(src, None)
    if 'loops' in opts['modes']:
        counts['loops'], counts['loop_edges'] = dissolve_loops(mesh, protect, opts)
        counts['line_verts'] += remove_line_vertices(mesh, protect, opts)
    after = stats(mesh)
    findings = verify(before, after, mesh, corners, opts)
    mesh, remap = compact(mesh)  # the rebuild gets no isolated points
    corners = {remap[v]: p for v, p in corners.items() if v in remap}
    after['verts'] = len(mesh['verts'])
    return {'mesh': mesh, 'counts': counts, 'before': before, 'after': after, 'protected': corners,
            'findings': findings, 'skipped': None}


def verify(before, after, mesh, corners, opts):
    """Acceptance of #1024 row 17 on the result: [(code, detail)]; empty = clean."""
    out = []
    t = t_vertices(mesh, opts['tol_m'])
    if t and 'tjunctions' in opts['modes'] and opts['t_mode'] == 'cut':
        out.append(('t_left', '{} T-vertices left'.format(len(t))))
    if before['uv_islands'] != after['uv_islands']:
        out.append(('uv_islands', '{} -> {}'.format(before['uv_islands'], after['uv_islands'])))
    if before['mat_ids'] != after['mat_ids']:
        out.append(('mat_ids', '{} -> {}'.format(before['mat_ids'], after['mat_ids'])))
    if before['sgs'] != after['sgs']:
        out.append(('smoothing', '{} -> {}'.format(before['sgs'], after['sgs'])))
    used = set(used_verts(mesh))
    moved = [v for v, p in corners.items() if v not in used or _len(_sub(mesh['verts'][v], p)) > 1e-9]
    if moved:
        out.append(('corner_moved', '{} protected corner(s) gone or moved'.format(len(moved))))
    return out


def preview_findings(before, opts):
    """What a preview reports per object (polygon station codes): what apply would clean."""
    out = []
    if before['t_vertices'] and 'tjunctions' in opts['modes']:
        out.append(('t_junction', '{} T-vertices'.format(before['t_vertices'])))
    if before['tris'] and 'detriangulate' in opts['modes']:
        out.append(('triangles', '{} triangles'.format(before['tris'])))
    return out


def plan_counts(result):
    """Short done text of one object."""
    c = result['counts']
    b, a = result['before'], result['after']
    return ('T cut {t_cut}, welded {welded}, quads from triangles {quads_made}, loops {loops} ({loop_edges} edges), '
            'line vertices {line_verts}; faces {fb} -> {fa}, tris {tb} -> {ta}').format(
        fb=b['faces'], fa=a['faces'], tb=b['tris'], ta=a['tris'], **c)
