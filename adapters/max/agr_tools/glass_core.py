"""new-case: AGR Tools 1.0 (#1024) glass planes logic, stdlib only. owned by branch H (improve/issue-1024-grid-glass).

Pure logic for `model_glass_planes` (model.glass_planes); no pymxs. The glue (glass_max.py) reads the glass mesh of a
node (world space, metres) and rebuilds the export COPY from `planes()`; the working object is never touched.

Source: the pilot's own `jobs/vyatskaya-tow02/scripts/clean_glass_blender.py` (ported, the original stays in place),
rule of Artem 21.10.2026: a flat window keeps its 4 corners; a window on a bend keeps one quad per segment; a 90° corner
window is two quads sharing the corner edge (6 points), not two planes with one sticking out of the other.

Steps (mesh format of gridclean_core: {'verts': [[x, y, z]] m, 'faces': [{'v', 'uv', 'mat', 'sg'}], 'uv': bool}):
1. weld points closer than `weld_m` (a duplicate film 1 mm off collapses here), drop degenerate and duplicate faces;
2. group faces into planes (`angle_deg`, `plane_m`); a plane is *major* when its smaller in-plane extent > `thin_m`;
3. parallel major planes closer than `stack_m` that overlap form one window stack: the planes with the largest area
   are glass (double glazing: both panes), the smaller ones are the frame face and are dropped;
4. the glass of a stack goes to ONE plane: `place: keep` (default) = the area-weighted middle of its panes (library
   windows: the middle of the 20 mm package, 80.4 mm from the F100 frame face, docs/experiments/win.generate.md);
   `place: frame` = `from_frame_m` (0.08, owner answer 06.11.2026) behind the outer frame face of the stack;
5. thin faces are frame sides / pane edges and are dropped, unless they stand between two glass planes meeting at
   more than `corner_deg` (a corner sliver, kept for step 8);
6. coplanar neighbours with one MatID are dissolved into one face, 2-edge points on a straight line (`line_m`) go;
7. a corner sliver narrower than `sliver_m` is removed and its two neighbours share one vertical edge at the
   intersection of their plan lines (source join_corners);
8. two glass planes meeting at a corner whose ends stick out or fall short by less than `sliver_m` are stitched on
   the intersection line (no plane sticking out of the other);
9. every face must be a quad; anything else is `ambiguous` with the node name. MatID and corner UVs are kept.
"""
import importlib.util
import math
import os

TOOL = 'model.glass_planes'
PLACES = ('keep', 'frame')
DEFAULTS = {'weld_m': 0.001, 'plane_m': 0.0005, 'angle_deg': 0.5, 'line_m': 0.002, 'thin_m': 0.10,
            'stack_m': 0.12, 'sliver_m': 0.06, 'corner_deg': 45.0, 'place': 'keep', 'from_frame_m': 0.08}
OPTIONS = set(DEFAULTS)
VERTICAL_M = 0.5  # source: a side edge of a corner sliver rises more than 0.5 m


def _grid_core():
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location('agr_tools_gridclean_core_for_glass',
                                                  os.path.join(here, 'gridclean_core.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gc = _grid_core()
_sub, _add, _mul, _dot, _cross, _len, _unit = gc._sub, gc._add, gc._mul, gc._dot, gc._cross, gc._len, gc._unit


def options(raw):
    raw = dict(raw or {})
    unknown = set(raw) - OPTIONS
    if unknown:
        raise ValueError('unknown model.glass_planes options: ' + ', '.join(sorted(unknown)))
    out = dict(DEFAULTS)
    out.update(raw)
    if out['place'] not in PLACES:
        raise ValueError('options.place must be keep or frame')
    for k in DEFAULTS:
        if k == 'place':
            continue
        v = out[k]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            raise ValueError('options.{} must be a positive number'.format(k))
        out[k] = float(v)
    return out


# ---- weld / clean ----------------------------------------------------------------------------------------------
def weld_all(mesh, dist):
    """Merge points closer than dist (lowest index wins); faces remapped, collapsed corners dropped."""
    verts = mesh['verts']
    used = gc.used_verts(mesh)
    cell = max(dist * 4, 1e-6)
    g = {}
    for v in used:
        g.setdefault(tuple(int(math.floor(c / cell)) for c in verts[v]), []).append(v)
    parent = {v: v for v in used}

    def find(v):
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v
    lim = dist * (1 + 1e-6) + 1e-12
    for v in used:
        key = tuple(int(math.floor(c / cell)) for c in verts[v])
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for w in g.get((key[0] + dx, key[1] + dy, key[2] + dz), ()):
                        if w > v and _len(_sub(verts[w], verts[v])) <= lim:
                            a, b = find(v), find(w)
                            if a != b:
                                parent[max(a, b)] = min(a, b)
    remap = {v: find(v) for v in used}
    merged = sum(1 for v in used if remap[v] != v)
    _remap_faces(mesh, remap)
    return merged


def _remap_faces(mesh, remap):
    for f in mesh['faces']:
        ring, uvs = [remap.get(v, v) for v in f['v']], f['uv']
        nr, nu = [], [] if uvs is not None else None
        for i, v in enumerate(ring):
            if nr and nr[-1] == v:
                continue
            nr.append(v)
            if nu is not None:
                nu.append(uvs[i])
        while len(nr) > 1 and nr[0] == nr[-1]:
            nr.pop()
            if nu is not None:
                nu.pop()
        f['v'], f['uv'] = nr, nu
    mesh['faces'] = [f for f in mesh['faces'] if len(f['v']) >= 3]


def drop_degenerate(mesh, min_area=1e-6):
    """Drop faces with < 3 distinct points or area below min_area (m2), and duplicates (same point set)."""
    seen, out, dropped = set(), [], 0
    for f in mesh['faces']:
        key = frozenset(f['v'])
        if len(key) < 3 or gc.area(mesh['verts'], f['v']) < min_area or key in seen:
            dropped += 1
            continue
        seen.add(key)
        out.append(f)
    mesh['faces'] = out
    return dropped


# ---- planes ----------------------------------------------------------------------------------------------------
def _canon(n):
    """Unit normal with a fixed sign (largest component positive) and the sign that was applied."""
    n = _unit(n)
    k = max(range(3), key=lambda i: abs(n[i]))
    s = 1.0 if n[k] >= 0 else -1.0
    return _mul(n, s), s


def _axes(n):
    up = [0.0, 0.0, 1.0]
    u = _cross(up, n)
    if _len(u) < 1e-6:
        u = [1.0, 0.0, 0.0]
    u = _unit(u)
    return u, _unit(_cross(n, u))


def planes_of(mesh, opts):
    """[{'n', 'd', 'faces', 'area', 'extent', 'major', 'box', 'out'}]: faces grouped by plane."""
    verts = mesh['verts']
    out = []
    cos_lim = math.cos(math.radians(opts['angle_deg']))
    for fi, f in enumerate(mesh['faces']):
        raw = gc.normal(verts, f['v'])
        n, s = _canon(raw)
        c = _mul([sum(verts[v][k] for v in f['v']) for k in range(3)], 1.0 / len(f['v']))
        d = _dot(n, c)
        a = _len(raw) / 2.0
        for p in out:
            if _dot(p['n'], n) >= cos_lim and abs(p['d'] - d) <= opts['plane_m']:
                p['faces'].append(fi)
                p['area'] += a
                p['out'] += s * a
                break
        else:
            out.append({'n': n, 'd': d, 'faces': [fi], 'area': a, 'out': s * a})
    for p in out:
        u, w = _axes(p['n'])
        pts = {v for fi in p['faces'] for v in mesh['faces'][fi]['v']}
        us = [_dot(u, verts[v]) for v in pts]
        ws = [_dot(w, verts[v]) for v in pts]
        p['box'] = (min(us), max(us), min(ws), max(ws))
        p['extent'] = min(max(us) - min(us), max(ws) - min(ws))
        p['major'] = p['extent'] > opts['thin_m']
        p['out'] = 1.0 if p['out'] >= 0 else -1.0  # side the face normals point to (outside of the glass)
    return out


def _overlap(b1, b2, tol):
    return not (b1[1] < b2[0] - tol or b2[1] < b1[0] - tol or b1[3] < b2[2] - tol or b2[3] < b1[2] - tol)


def stacks_of(planes, opts):
    """Major parallel planes closer than stack_m that overlap in plan of the plane -> stacks [[plane index]]."""
    cos_lim = math.cos(math.radians(opts['angle_deg']))
    major = [i for i, p in enumerate(planes) if p['major']]
    fams = []
    for i in major:
        for fam in fams:
            if _dot(planes[fam[0]]['n'], planes[i]['n']) >= cos_lim:
                fam.append(i)
                break
        else:
            fams.append([i])
    stacks = []
    for fam in fams:
        fam.sort(key=lambda i: planes[i]['d'])
        groups = []
        for i in fam:
            for g in groups:
                if any(abs(planes[i]['d'] - planes[j]['d']) <= opts['stack_m'] and
                       _overlap(planes[i]['box'], planes[j]['box'], opts['weld_m']) for j in g):
                    g.append(i)
                    break
            else:
                groups.append([i])
        stacks.extend(groups)
    return stacks


def _project(p, constraints):
    """Closest point to p on the planes n.x = t (one or two planes)."""
    if len(constraints) == 1:
        n, t = constraints[0]
        return _sub(p, _mul(n, _dot(n, p) - t))
    (n1, t1), (n2, t2) = constraints[:2]
    a11, a12, a22 = _dot(n1, n1), _dot(n1, n2), _dot(n2, n2)
    b1, b2 = _dot(n1, p) - t1, _dot(n2, p) - t2
    det = a11 * a22 - a12 * a12
    if abs(det) < 1e-12:
        return _project(p, constraints[:1])
    l1 = (b1 * a22 - b2 * a12) / det
    l2 = (a11 * b2 - a12 * b1) / det
    return _sub(_sub(p, _mul(n1, l1)), _mul(n2, l2))


# ---- region dissolve -------------------------------------------------------------------------------------------
def _boundary_ring(mesh, region):
    """One boundary loop of a set of consistently wound faces -> (ring, uv) or None (holes, pinches, open fans)."""
    faces = mesh['faces']
    directed = {}
    for fi in region:
        ring = faces[fi]['v']
        for ci, a in enumerate(ring):
            b = ring[(ci + 1) % len(ring)]
            directed[(a, b)] = (fi, ci)
    bnd = {e: src for e, src in directed.items() if (e[1], e[0]) not in directed}
    nxt = {}
    for (a, b) in bnd:
        if a in nxt:
            return None
        nxt[a] = b
    if not nxt:
        return None
    start = min(nxt)
    ring, uv, v = [], [], start
    for _ in range(len(nxt) + 1):
        fi, ci = bnd[(v, nxt[v])]
        ring.append(v)
        f = faces[fi]
        uv.append(None if f['uv'] is None else f['uv'][ci])
        v = nxt[v]
        if v == start:
            break
    else:
        return None
    if len(ring) != len(nxt):
        return None  # more than one loop (a hole)
    return ring, (None if any(t is None for t in uv) else uv)


def dissolve_coplanar(mesh, opts):
    """Merge coplanar neighbours (same MatID, normal within angle_deg, same winding) into one face per region.
    Returns (regions merged, regions left as faces because of holes)."""
    verts, faces = mesh['verts'], mesh['faces']
    emap = gc.edges(mesh)
    parent = list(range(len(faces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    cos_lim = math.cos(math.radians(opts['angle_deg']))
    for (a, b), uses in emap.items():
        if len(uses) != 2:
            continue
        f1, f2 = uses[0][0], uses[1][0]
        F1, F2 = faces[f1], faces[f2]
        if F1['mat'] != F2['mat']:
            continue
        if _dot(_unit(gc.normal(verts, F1['v'])), _unit(gc.normal(verts, F2['v']))) < cos_lim:
            continue
        parent[find(f1)] = find(f2)
    groups = {}
    for i in range(len(faces)):
        groups.setdefault(find(i), []).append(i)
    out, merged, holes = [], 0, 0
    for root in sorted(groups, key=lambda r: min(groups[r])):
        region = groups[root]
        if len(region) == 1:
            out.append(faces[region[0]])
            continue
        got = _boundary_ring(mesh, region)
        if got is None:
            holes += 1
            out.extend(faces[i] for i in region)
            continue
        first = faces[region[0]]
        out.append(dict(first, v=got[0], uv=got[1]))
        merged += 1
    mesh['faces'] = out
    return merged, holes


# ---- corners ---------------------------------------------------------------------------------------------------
def _plan_line(mesh, f):
    bottom = sorted(f['v'], key=lambda v: mesh['verts'][v][2])[:2]
    return [mesh['verts'][v][:2] for v in bottom]


def _intersect2(p, q):
    (a, b), (c, d) = p, q
    r = [b[0] - a[0], b[1] - a[1]]
    s = [d[0] - c[0], d[1] - c[1]]
    den = r[0] * s[1] - r[1] * s[0]
    if abs(den) < 1e-9:
        return None
    t = ((c[0] - a[0]) * s[1] - (c[1] - a[1]) * s[0]) / den
    return [a[0] + r[0] * t, a[1] + r[1] * t]


def _face_angle(mesh, f1, f2):
    return gc._angle_deg(gc.normal(mesh['verts'], f1['v']), gc.normal(mesh['verts'], f2['v']))


def join_corners(mesh, opts):
    """Source join_corners: drop a quad sliver (plan width < sliver_m) between two faces meeting at > corner_deg and
    stitch them on one vertical edge at the intersection of their plan lines. Returns slivers removed."""
    joined = 0
    while True:
        emap = gc.edges(mesh)
        verts, faces = mesh['verts'], mesh['faces']
        hit = None
        for fi, f in enumerate(faces):
            if len(f['v']) != 4:
                continue
            bottom = sorted(f['v'], key=lambda v: verts[v][2])[:2]
            if math.hypot(verts[bottom[0]][0] - verts[bottom[1]][0],
                          verts[bottom[0]][1] - verts[bottom[1]][1]) >= opts['sliver_m']:
                continue
            ring = f['v']
            sides = [(ring[i], ring[(i + 1) % 4]) for i in range(4)
                     if abs(verts[ring[i]][2] - verts[ring[(i + 1) % 4]][2]) > VERTICAL_M]
            if len(sides) != 2:
                continue
            nbrs = []
            for a, b in sides:
                us = [u[0] for u in emap.get((min(a, b), max(a, b)), ()) if u[0] != fi]
                nbrs.append(us[0] if len(us) == 1 else None)
            if None in nbrs or _face_angle(mesh, faces[nbrs[0]], faces[nbrs[1]]) < opts['corner_deg']:
                continue
            p = _intersect2(_plan_line(mesh, faces[nbrs[0]]), _plan_line(mesh, faces[nbrs[1]]))
            if p is None:
                continue
            hit = (fi, sides, p)
            break
        if hit is None:
            return joined
        fi, sides, p = hit
        lows = [min(e, key=lambda v: verts[v][2]) for e in sides]
        highs = [max(e, key=lambda v: verts[v][2]) for e in sides]
        remap = {}
        for vs in (lows, highs):
            for v in vs:
                verts[v] = [p[0], p[1], verts[v][2]]
            for v in vs[1:]:
                remap[v] = vs[0]
            verts[vs[0]][2] = verts[vs[0]][2]
        del faces[fi]
        _remap_faces(mesh, remap)
        drop_degenerate(mesh, 1e-6)
        joined += 1


def stitch_corners(mesh, stack_of_face, opts):
    """Two glass quads of different stacks meeting at > corner_deg: a vertical end edge within sliver_m (plan) of the
    intersection of their plan lines goes onto it, then the two edges are welded. Returns corners stitched."""
    verts, faces = mesh['verts'], mesh['faces']
    stitched = 0
    for i in range(len(faces)):
        for j in range(i + 1, len(faces)):
            fa, fb = faces[i], faces[j]
            if len(fa['v']) != 4 or len(fb['v']) != 4 or stack_of_face[i] == stack_of_face[j]:
                continue
            if _face_angle(mesh, fa, fb) < opts['corner_deg']:
                continue
            if len(set(fa['v']) & set(fb['v'])) >= 2:
                continue  # already share an edge
            p = _intersect2(_plan_line(mesh, fa), _plan_line(mesh, fb))
            if p is None:
                continue
            ends = []
            for f in (fa, fb):
                ring = f['v']
                sides = [(ring[k], ring[(k + 1) % 4]) for k in range(4)
                         if abs(verts[ring[k]][2] - verts[ring[(k + 1) % 4]][2]) > VERTICAL_M]
                near = [e for e in sides if max(math.hypot(verts[v][0] - p[0], verts[v][1] - p[1]) for v in e)
                        < opts['sliver_m']]
                ends.append(near[0] if len(near) == 1 else None)
            if None in ends:
                continue
            remap = {}
            for which in (min, max):
                vs = [which(e, key=lambda v: verts[v][2]) for e in ends]
                for v in vs:
                    verts[v] = [p[0], p[1], verts[v][2]]
                z = verts[vs[0]][2]
                if abs(verts[vs[1]][2] - z) > opts['sliver_m']:
                    remap = None
                    break
                remap[vs[1]] = vs[0]
            if remap is None:
                continue
            _remap_faces(mesh, remap)
            stitched += 1
    return stitched


# ---- the row ---------------------------------------------------------------------------------------------------
def planes(mesh, opts):
    """Reduce one glass mesh to planes. Returns {'mesh', 'counts', 'findings', 'ambiguous', 'stacks', 'glass_from_frame_m'}.

    findings (preview codes, what apply changes): glass_merge, glass_frame, glass_double, glass_corner;
    ambiguous: faces that are not quads after the rule, holes in a glass region."""
    gc.check_mesh(mesh)
    m = gc.copy_mesh(mesh)
    before = len(m['faces'])
    counts = {'faces_before': before, 'welded': 0, 'frame_faces': 0, 'thin_faces': 0, 'stacks_collapsed': 0,
              'slivers': 0, 'stitched': 0, 'line_verts': 0, 'faces_after': 0, 'quads': 0}
    counts['welded'] = weld_all(m, opts['weld_m'])
    dup = drop_degenerate(m)
    pl = planes_of(m, opts)
    stacks = stacks_of(pl, opts)
    face_plane = {}
    for pi, p in enumerate(pl):
        for fi in p['faces']:
            face_plane[fi] = pi
    glass_planes_, frame_planes, target = set(), set(), {}
    from_frame = []
    for si, st in enumerate(stacks):
        big = max(pl[i]['area'] for i in st)
        glass = [i for i in st if pl[i]['area'] >= 0.5 * big]
        frame = [i for i in st if i not in glass]
        glass_planes_.update(glass)
        frame_planes.update(frame)
        n = pl[glass[0]]['n']
        side = pl[glass[0]]['out']
        mid = sum(pl[i]['d'] * pl[i]['area'] for i in glass) / sum(pl[i]['area'] for i in glass)
        t = mid
        if frame:
            outer = max(frame, key=lambda i: pl[i]['d'] * side)
            if opts['place'] == 'frame':
                t = pl[outer]['d'] - side * opts['from_frame_m']
            from_frame.append(abs(pl[outer]['d'] - t))
        if len(glass) > 1:
            counts['stacks_collapsed'] += 1
        for i in glass:
            target[i] = (si, n, t)
    stack_of_plane = {i: target[i][0] for i in target}
    keep, drop_frame, drop_thin = [], 0, 0
    emap = gc.edges(m)
    for fi, f in enumerate(m['faces']):
        pi = face_plane[fi]
        if pi in glass_planes_:
            keep.append(fi)
            continue
        if pi in frame_planes:
            drop_frame += 1
            continue
        # thin face: keep only a corner sliver between glass of two stacks meeting at > corner_deg
        nb = set()
        ring = f['v']
        for ci, a in enumerate(ring):
            b = ring[(ci + 1) % len(ring)]
            for u in emap.get((min(a, b), max(a, b)), ()):
                if u[0] != fi and face_plane[u[0]] in glass_planes_:
                    nb.add(u[0])
        st = {stack_of_plane[face_plane[g]] for g in nb}
        corner = len(st) >= 2 and any(
            _face_angle(m, m['faces'][g1], m['faces'][g2]) >= opts['corner_deg'] for g1 in nb for g2 in nb)
        if corner:
            keep.append(fi)
        else:
            drop_thin += 1
    counts['frame_faces'], counts['thin_faces'] = drop_frame, drop_thin
    # project glass points onto their stack plane (a point on two stacks: onto their intersection line)
    cons = {}
    for fi in keep:
        pi = face_plane[fi]
        if pi not in target:
            continue
        _, n, t = target[pi]
        for v in m['faces'][fi]['v']:
            lst = cons.setdefault(v, [])
            if not any(_dot(n, c[0]) > 0.9999 and abs(t - c[1]) < 1e-12 for c in lst):
                lst.append((n, t))
    for v, c in cons.items():
        m['verts'][v] = _project(m['verts'][v], c)
    stack_face = [target[face_plane[fi]][0] if face_plane[fi] in target else -1 for fi in keep]
    m['faces'] = [m['faces'][fi] for fi in keep]
    counts['welded'] += weld_all(m, opts['weld_m'])
    pairs = list(zip(m['faces'], stack_face))
    seen, faces2, stack2 = set(), [], []
    for f, s in pairs:
        key = frozenset(f['v'])
        if len(key) < 3 or gc.area(m['verts'], f['v']) < 1e-6 or key in seen:
            continue
        seen.add(key)
        faces2.append(f)
        stack2.append(s)
    m['faces'] = faces2
    for f, s in zip(m['faces'], stack2):
        f['_stack'] = s
    merged, holes = dissolve_coplanar(m, opts)
    lineopts = {'line_m': opts['line_m'], 'uv_tol': float('inf')}
    counts['line_verts'] = gc.remove_line_vertices(m, set(), lineopts)
    counts['slivers'] = join_corners(m, opts)
    counts['line_verts'] += gc.remove_line_vertices(m, set(), lineopts)
    stack_now = [f.get('_stack', -1) for f in m['faces']]
    counts['stitched'] = stitch_corners(m, stack_now, opts)
    drop_degenerate(m, 1e-6)
    counts['line_verts'] += gc.remove_line_vertices(m, set(), lineopts)
    for f in m['faces']:
        f.pop('_stack', None)
    m, _ = gc.compact(m)
    counts['faces_after'] = len(m['faces'])
    counts['quads'] = sum(1 for f in m['faces'] if len(f['v']) == 4)
    findings = []
    if counts['faces_after'] < before - drop_frame - drop_thin - dup:
        findings.append(('glass_merge', '{} faces -> {}'.format(before, counts['faces_after'])))
    if drop_frame or drop_thin:
        findings.append(('glass_frame', '{} frame face(s), {} thin side face(s) dropped'.format(drop_frame, drop_thin)))
    if counts['stacks_collapsed'] or dup:
        findings.append(('glass_double', '{} pane stack(s) to one plane, {} duplicate face(s)'.format(
            counts['stacks_collapsed'], dup)))
    if counts['slivers'] or counts['stitched']:
        findings.append(('glass_corner', '{} sliver(s) joined, {} corner(s) stitched'.format(
            counts['slivers'], counts['stitched'])))
    ambiguous = []
    sizes = sorted({len(f['v']) for f in m['faces']})
    if sizes != [4]:
        ambiguous.append('faces with {} corners after the rule (expected 4)'.format(
            ', '.join(str(s) for s in sizes if s != 4) or 'no faces'))
    if holes:
        ambiguous.append('{} glass region(s) with a hole kept as faces'.format(holes))
    return {'mesh': m, 'counts': counts, 'findings': findings, 'ambiguous': ambiguous,
            'stacks': len(stacks), 'glass_from_frame_m': [round(x, 6) for x in from_frame]}


def udim_tiles(mesh):
    """UDIM tiles (1001 + u + 10 v) used by the corner UVs; the glass mesh numbers its own tiles from 1001 (B9)."""
    tiles = set()
    for f in mesh['faces']:
        if not f['uv']:
            continue
        u = sum(t[0] for t in f['uv']) / len(f['uv'])
        v = sum(t[1] for t in f['uv']) / len(f['uv'])
        tiles.add(1001 + int(math.floor(u)) + 10 * int(math.floor(v)))
    return sorted(tiles)
