"""new-case: OKS master mesh quality score by the [D336] split rule (#1616), stdlib core.

Input: per-object geometry ``{'name', 'verts': [[x,y,z]...], 'faces': [[i,j,k,...]...],
'materials': [name per face]}`` (written by tools/blender/mesh_quality_dump.py).
Output: one score 0..100 (higher = cleaner) plus its components.

Elements: an element is a vertex-connected face set (shared vertex indices) inside one object;
coincident but unwelded vertices make separate (inset) elements - except along an open seam (see
``open_seam_share``). The largest element (by area) of each body object is the body; every other
element is inset. Objects whose name matches ``glass_pattern`` are all-inset (stained glass / glazing).

Components (each a share 0..1; penalty = min(1, share)):
- ``tri_share``: triangles (quad masters must be quads; the export triangulates later).
- ``ngon_share``: polygons with more than 4 corners - an error, status ``fail``.
- ``sliver_share``: sliver triangles (min angle < ``tri_min_angle_deg``, default 10 deg) and
  sliver/degenerate quads (min corner angle < ``quad_min_angle_deg``, default 30 deg, or area 0).
  10 deg: a triangle this thin has aspect >= 5.7 and becomes a sub-texel strip at 1 px/mm
  (4096 px per 4 m tile); 30 deg: architectural quads are rectangles, a 30 deg corner is a
  triangle-to-quad split fan, never a modelled shape.
- ``pole_share``: irregular vertices on flat surfaces - interior vertices of a planar patch
  (all incident normals within ``flat_deg``) whose valence is not 4. A clean grid has none;
  triangle-to-3-quad splits and welded parts that drag cut lines leave valence 3/5/6 poles.
- ``one_mesh_share`` ([D336] inset elements vs body): faces of the body element as a share of the
  measured non-glass faces, rescaled above ``body_share_ok`` (default 0.5):
  ``max(0, body - ok) / (1 - ok)``. [D336] insets windows, roof, flashings and posts, which on an
  OKS facade carry at least half of the faces (accepted PSU275: body 0.37); a master welded into
  one mesh has body ~1.0 and gets the full penalty.
- ``weld_share`` (welds across element boundaries): crease edges INSIDE the body element where the
  surface turns concave by more than ``weld_deg`` (a part pressed into the body and vertex-welded
  to it), as a share of the body's two-face edges. An inset element has no welded contact.
- ``long_share``: faces whose longest side exceeds ``side_limit_m`` (default 3.9 m: one
  4096 px tile covers 4 m at 1 px/mm, minus a 0.1 m bleed margin; Artem: quads <= 4 x 4 m).
- ``irregular_area_share`` (review r1 P1-1, what Artem saw on the rejected KPP1 corners: an irregular
  wire): AREA share of measured faces with a corner more than ``irregular_deg`` (default 15 deg)
  off 90 deg. Facade quads are rectangles; a skewed quad is a cut line dragged across a surface.
  Area, not count: a large skewed quad on a wall is visible, a skewed 1 cm trim face is not.
  Triangles always count (one of their corners is at least 30 deg off 90).
- ``open_seam_share`` (review r1 P1-2, un-weld gaming): boundary edges that coincide (vertex positions
  on a ``seam_tol_m`` grid, default 0.1 mm) with another boundary edge - in the same object or in
  another one. Such a part is cut out of the body without the body keeping its opening/recess,
  which [D336] requires of an inset element. Seam-joined parts of one object are therefore measured
  as ONE welded element (elements, body, creases, poles), and the seam edges cost on top:
  share = seam edges / measured edges. Un-welding alone can only lower the score. Glass objects
  (``glass_pattern``) take no part in seams: a pane fills its frame opening by regulation
  (Main/MainGlass); accepted PSU275 glass shares 10 320 boundary edges with its Main frames.

score = 100 * (1 - sum(weight * penalty) / sum(weights)) (weights in ``WEIGHTS``), so every
component costs at most its weight share of the 100 points.
Pass/fail is NOT the score: ``status`` is ``fail`` on any n-gon or an empty measured set,
``measured`` otherwise. The score ranks masters; it never grants acceptance.
Calibration (KPP1 quad-v002/v003, PSU275): docs/research/mesh-quality-1616/REPORT.md.
"""
import math
import re

WEIGHTS = {'tri_share': 1.0, 'ngon_share': 2.0, 'sliver_share': 2.0, 'pole_share': 1.0,
           'one_mesh_share': 2.0, 'weld_share': 1.0, 'long_share': 1.0, 'irregular_area_share': 2.0,
           'open_seam_share': 2.0}
ANGLE_EPS_DEG = 1e-6  # float noise of acos: an angle exactly at the threshold is not a sliver
DEFAULTS = {'tri_min_angle_deg': 10.0, 'quad_min_angle_deg': 30.0, 'flat_deg': 1.0,
            'weld_deg': 30.0, 'side_limit_m': 3.9, 'body_share_ok': 0.5, 'collision_prefix': 'UCX_',
            'glass_pattern': r'(?i)glass', 'irregular_deg': 15.0, 'seam_tol_m': 0.0001}


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a):
    return math.sqrt(_dot(a, a))


def _newell(pts):
    nx = ny = nz = 0.0
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        nx += (p[1] - q[1]) * (p[2] + q[2])
        ny += (p[2] - q[2]) * (p[0] + q[0])
        nz += (p[0] - q[0]) * (p[1] + q[1])
    return (nx, ny, nz)


def _angles(pts):
    out = []
    n = len(pts)
    for i in range(n):
        a = _sub(pts[i - 1], pts[i])
        b = _sub(pts[(i + 1) % n], pts[i])
        la, lb = _norm(a), _norm(b)
        if la == 0 or lb == 0:
            out.append(0.0)
            continue
        c = max(-1.0, min(1.0, _dot(a, b) / (la * lb)))
        out.append(math.degrees(math.acos(c)))
    return out


def _params(params):
    p = dict(DEFAULTS)
    for key, value in (params or {}).items():
        if key not in DEFAULTS:
            raise ValueError('unknown parameter: ' + key)
        p[key] = value
    for key in ('tri_min_angle_deg', 'quad_min_angle_deg', 'flat_deg', 'weld_deg', 'side_limit_m',
                'irregular_deg', 'seam_tol_m'):
        v = p[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            raise ValueError(f'parameter {key} must be a finite positive number, got {v!r}')
    if not 0 < p['body_share_ok'] < 1:
        raise ValueError(f"parameter body_share_ok must be in (0, 1), got {p['body_share_ok']!r}")
    return p


def _in_box(c, z):
    return z[0] <= c[0] <= z[2] and z[1] <= c[1] <= z[3]


def _in_zone(c, zones, exclude=None):
    """Inside any of ``zones`` (everything when there are none) and outside every ``exclude`` box."""
    if zones and not any(_in_box(c, z) for z in zones):
        return False
    return not (exclude and any(_in_box(c, z) for z in exclude))


def _pkey(v, tol):
    return tuple(round(c / tol) for c in v)


def _edge_faces(faces):
    edges = {}
    for fi, f in enumerate(faces):
        for k, a in enumerate(f):
            b = f[(k + 1) % len(f)]
            edges.setdefault((a, b) if a < b else (b, a), []).append(fi)
    return edges


def _boundary_keys(obj, tol):
    """Position key of every boundary edge of the object -> [(a, b, face), ...]."""
    out = {}
    verts = obj['verts']
    for (a, b), fl in _edge_faces(obj['faces']).items():
        if len(fl) == 1:
            ka, kb = _pkey(verts[a], tol), _pkey(verts[b], tol)
            out.setdefault((ka, kb) if ka <= kb else (kb, ka), []).append((a, b, fl[0]))
    return out


def _check_object(obj):
    for key in ('name', 'verts', 'faces'):
        if key not in obj:
            raise ValueError(f'object without {key}: {obj.get("name", "?")}')
    verts, faces = obj['verts'], obj['faces']
    for v in verts:
        if len(v) != 3 or not all(isinstance(c, (int, float)) and math.isfinite(c) for c in v):
            raise ValueError(f'{obj["name"]}: non-finite or malformed vertex {v!r}')
    n = len(verts)
    for f in faces:
        if len(f) < 3 or len(set(f)) != len(f) or any(not isinstance(i, int) or i < 0 or i >= n for i in f):
            raise ValueError(f'{obj["name"]}: malformed face {f!r}')
    mats = obj.get('materials')
    if mats is not None and len(mats) != len(faces):
        raise ValueError(f'{obj["name"]}: {len(mats)} materials for {len(faces)} faces')


def _seam_welded_faces(obj, tol, seam_keys):
    """Faces with the vertices of coincident boundary edges (``seam_keys``) merged; positions unchanged.

    Returns (faces, {seam key: [face ids]}) for the seams of this object."""
    verts = obj['verts']
    parent = list(range(len(verts)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    seam_here = {}
    for key, owners in _boundary_keys(obj, tol).items():
        if key not in seam_keys:
            continue
        seam_here[key] = [fi for _, _, fi in owners]
        a0, b0, _ = owners[0]
        k0 = _pkey(verts[a0], tol)
        for a, b, _ in owners[1:]:
            if _pkey(verts[a], tol) != k0:
                a, b = b, a
            for x, y in ((a0, a), (b0, b)):
                rx, ry = find(x), find(y)
                if rx != ry:
                    parent[ry] = rx
    canon = [find(i) for i in range(len(verts))]
    faces = []
    for f in obj['faces']:
        g = [canon[i] for i in f]
        faces.append(g if len(set(g)) == len(g) else list(f))
    return faces, seam_here


def measure_object(obj, p, zones=None, exclude=None, seam_keys=frozenset()):
    """Stats of one object: faces whose centroid is inside ``zones`` and outside ``exclude``
    (topology from the whole object). ``seam_keys``: boundary-edge keys shared by >= 2 edges."""
    _check_object(obj)
    verts = obj['verts']
    nf = len(obj['faces'])
    faces, seam_here = _seam_welded_faces(obj, p['seam_tol_m'], seam_keys)
    # elements = vertex-connected face sets
    parent = list(range(len(verts)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for f in faces:
        r0 = find(f[0])
        for i in f[1:]:
            r = find(i)
            if r != r0:
                parent[r] = r0
    pts = [[verts[i] for i in f] for f in obj['faces']]
    normals, areas, cents = [], [], []
    for fp in pts:
        nv = _newell(fp)
        ln = _norm(nv)
        areas.append(ln / 2.0)
        normals.append((nv[0] / ln, nv[1] / ln, nv[2] / ln) if ln > 0 else (0.0, 0.0, 0.0))
        k = len(fp)
        cents.append((sum(q[0] for q in fp) / k, sum(q[1] for q in fp) / k, sum(q[2] for q in fp) / k))
    elem_of = [find(f[0]) for f in faces]
    elem_area = {}
    for fi, e in enumerate(elem_of):
        elem_area[e] = elem_area.get(e, 0.0) + areas[fi]
    glass = re.search(p['glass_pattern'], obj['name']) is not None
    body = None if glass or not elem_area else max(elem_area, key=lambda e: (elem_area[e], -e))
    in_zone = [_in_zone(c, zones, exclude) for c in cents]
    edges = _edge_faces(faces)
    vfaces = [[] for _ in verts]
    for fi, f in enumerate(faces):
        for a in f:
            vfaces[a].append(fi)
    zone_edges = sum(1 for fl in edges.values() if any(in_zone[fi] for fi in fl))
    zone_seams = {k for k, fl in seam_here.items() if any(in_zone[fi] for fi in fl)}
    vedges = [0] * len(verts)
    boundary = [False] * len(verts)
    weld_cos = math.cos(math.radians(p['weld_deg']))
    welded = manifold = 0
    for (a, b), fl in edges.items():
        vedges[a] += 1
        vedges[b] += 1
        if len(fl) != 2:
            boundary[a] = boundary[b] = True
            continue
        f1, f2 = fl
        if not (in_zone[f1] or in_zone[f2]) or elem_of[f1] != body:
            continue
        manifold += 1
        n1, n2 = normals[f1], normals[f2]
        if _dot(n1, n2) < weld_cos and _dot(n1, _sub(cents[f2], cents[f1])) > 1e-9:
            welded += 1
    flat_cos = math.cos(math.radians(p['flat_deg']))
    flat = poles = 0
    for v, fl in enumerate(vfaces):
        if boundary[v] or not fl:
            continue
        if not any(in_zone[fi] for fi in fl):
            continue
        n0 = normals[fl[0]]
        if all(_dot(n0, normals[fi]) >= flat_cos for fi in fl):
            flat += 1
            if vedges[v] != 4:
                poles += 1
    tris = quads = ngons = slivers = longs = irregular = 0
    area = irregular_area = 0.0
    ngon_faces = []
    measured = 0
    inset_faces = body_faces = 0
    for fi, fp in enumerate(pts):
        if not in_zone[fi]:
            continue
        measured += 1
        k = len(fp)
        if elem_of[fi] == body:
            body_faces += 1
        else:
            inset_faces += 1
        ang = _angles(fp)
        area += areas[fi]
        if max(abs(x - 90.0) for x in ang) > p['irregular_deg'] + ANGLE_EPS_DEG:
            irregular += 1
            irregular_area += areas[fi]
        if k == 3:
            tris += 1
            if min(ang) < p['tri_min_angle_deg'] - ANGLE_EPS_DEG or areas[fi] == 0:
                slivers += 1
        elif k == 4:
            quads += 1
            if min(ang) < p['quad_min_angle_deg'] - ANGLE_EPS_DEG or areas[fi] == 0:
                slivers += 1
        else:
            ngons += 1
            ngon_faces.append(fi)
        side = max(_norm(_sub(fp[i], fp[(i + 1) % k])) for i in range(k))
        if side > p['side_limit_m']:
            longs += 1
    zone_elems = {elem_of[fi] for fi in range(nf) if in_zone[fi]}
    elem_q = {}
    for fi in range(nf):
        if in_zone[fi]:
            q = elem_q.setdefault(elem_of[fi], [0, 0])
            q[0] += len(faces[fi]) == 4
            q[1] += 1
    elem_shares = [q / n for q, n in elem_q.values()]
    return {'name': obj['name'], 'faces': measured, 'tris': tris, 'quads': quads, 'ngons': ngons,
            'ngon_face_ids': ngon_faces[:50], 'slivers': slivers, 'long_faces': longs,
            'flat_vertices': flat, 'poles': poles, 'manifold_edges': manifold, 'welded_edges': welded,
            'elements': len(zone_elems), 'inset_elements': len(zone_elems - {body}),
            'body_elements': int(body in zone_elems), 'inset_faces': inset_faces, 'body_faces': body_faces,
            'irregular_faces': irregular, 'area': area, 'irregular_area': irregular_area,
            'edges': zone_edges, 'open_seam_edges': len(zone_seams), '_seam_keys': zone_seams,
            'quad_share': quads / measured if measured else None, 'glass_object': glass,
            'min_element_quad_share': min(elem_shares) if elem_shares else None,
            'elements_not_all_quads': sum(1 for s in elem_shares if s < 1.0)}


def _is_glass(obj, p):
    return re.search(p['glass_pattern'], str(obj['name'])) is not None


def _check_boxes(boxes):
    for z in boxes or []:
        if len(z) != 4 or not all(isinstance(c, (int, float)) and math.isfinite(c) for c in z) \
                or z[0] >= z[2] or z[1] >= z[3]:
            raise ValueError(f'malformed zone {z!r}')


def score(objects, params=None, zones=None, exclude_zones=None):
    """Score a master. ``objects`` as in the module docstring; ``zones`` / ``exclude_zones`` =
    [[x0, y0, x1, y1], ...] plan boxes: measure faces inside a zone and outside every exclude box."""
    p = _params(params)
    _check_boxes(zones)
    _check_boxes(exclude_zones)
    names = [o.get('name') for o in objects]
    dup = sorted({n for n in names if names.count(n) > 1})
    if dup:
        raise ValueError('duplicate object names: ' + ', '.join(map(str, dup)))
    kept, dropped = [], []
    for obj in objects:
        if str(obj.get('name', '')).startswith(p['collision_prefix']):
            dropped.append({'name': obj['name'], 'reason': 'collision hull (' + p['collision_prefix'] + ')'})
            continue
        _check_object(obj)
        kept.append(obj)
    counts = {}
    for obj in kept:
        if _is_glass(obj, p):
            continue  # glazing fills an opening by regulation (Main/MainGlass, [D336]); not a body seam
        for key, owners in _boundary_keys(obj, p['seam_tol_m']).items():
            counts[key] = counts.get(key, 0) + len(owners)
    seam_keys = frozenset(k for k, c in counts.items() if c >= 2)
    rows, seams = [], set()
    for obj in kept:
        row = measure_object(obj, p, zones, exclude_zones, frozenset() if _is_glass(obj, p) else seam_keys)
        seams |= row.pop('_seam_keys')
        rows.append(row)
    tot = {k: sum(r[k] for r in rows) for k in ('faces', 'tris', 'quads', 'ngons', 'slivers', 'long_faces',
                                                 'flat_vertices', 'poles', 'manifold_edges', 'welded_edges',
                                                 'elements', 'inset_elements', 'body_elements', 'body_faces',
                                                 'inset_faces', 'irregular_faces', 'area', 'irregular_area',
                                                 'edges', 'elements_not_all_quads')}
    tot['open_seam_edges'] = len(seams)  # a seam between two objects counts once
    solid = sum(r['faces'] for r in rows if not r['glass_object'])
    problems = []
    if not tot['faces']:
        problems.append('no measured faces (empty master or zone)')
    if tot['ngons']:
        problems.append(f'{tot["ngons"]} n-gons (> 4 corners)')
    f = tot['faces'] or 1
    comps = {'tri_share': tot['tris'] / f, 'ngon_share': tot['ngons'] / f, 'sliver_share': tot['slivers'] / f,
             'pole_share': tot['poles'] / tot['flat_vertices'] if tot['flat_vertices'] else 0.0,
             'one_mesh_share': tot['body_faces'] / solid if solid else 0.0,
             'weld_share': tot['welded_edges'] / tot['manifold_edges'] if tot['manifold_edges'] else 0.0,
             'long_share': tot['long_faces'] / f,
             'irregular_area_share': tot['irregular_area'] / tot['area'] if tot['area'] else 0.0,
             'open_seam_share': tot['open_seam_edges'] / tot['edges'] if tot['edges'] else 0.0}
    ok = p['body_share_ok']
    pen = {k: min(1.0, v) for k, v in comps.items()}
    pen['one_mesh_share'] = max(0.0, comps['one_mesh_share'] - ok) / (1.0 - ok)
    value = 100.0 * (1.0 - sum(WEIGHTS[k] * pen[k] for k in pen) / sum(WEIGHTS.values()))
    if not tot['faces']:
        value = 0.0
    tot['area'], tot['irregular_area'] = round(tot['area'], 6), round(tot['irregular_area'], 6)
    for r in rows:
        r['area'], r['irregular_area'] = round(r['area'], 6), round(r['irregular_area'], 6)
    return {'tool': 'mesh_quality_score', 'issue': 1616, 'score': round(value, 3),
            'status': 'fail' if problems else 'measured', 'problems': problems,
            'components': {k: round(v, 6) for k, v in comps.items()},
            'penalties': {k: round(v, 6) for k, v in pen.items()}, 'weights': dict(WEIGHTS),
            'params': p, 'zones': zones or [], 'exclude_zones': exclude_zones or [], 'totals': tot,
            'objects': rows, 'dropped': dropped}
