"""new-case: polygon station builder of branch J (#1024): synthetic facade shells ("badik") for win.place and opening
markers for win.generate. Own geometry (no GeoAGR code), metres; stdlib only so the unit tests use the same meshes.

A facade is an open polyline of vertical walls (single-sided surface, normal = street side) of height H. Every
opening is a hole with a reveal of depth `reveal` going INTO the building; the back loop of the reveal is an OPEN
border = the window plane (what Geo Window Placer GeoAGR.ms:56719 expects: «Wall with selected borders").
Opening kinds: rect, arch (semicircle top), corner (an L opening around a convex corner between two walls).
Front cells are a grid over all hole coordinates and every hole edge is split at the grid lines, so the mesh has no
T-junctions (a T-junction would show as a false border).

`make(obj, rt) -> node` (build/build_scene.py): obj['extra']['j'] = {'kind': 'facade', 'spec': {...}} builds an
Editable_Mesh of facade(spec) at the node position; {'kind': 'marker', 'type': 'WT-11'} builds an OPEN_<nnn>-like
Point marker with agr_role opening and agr_window_type (win.generate stations).
"""
import json
import math

REVEAL = 0.25
KPP1 = {'KPP1-W01': (1.18, 1.80), 'KPP1-W02': (1.18, 5.45), 'KPP1-W03': (2.00, 1.80)}


class Mesh:
    def __init__(self):
        self.verts, self.key, self.faces, self.mat_ids = [], {}, [], []

    def vid(self, p):
        k = tuple(round(c, 7) for c in p)
        if k not in self.key:
            self.key[k] = len(self.verts)
            self.verts.append([float(c) for c in k])
        return self.key[k]

    def face(self, pts, mat=1, want=None):
        ids = []
        for p in pts:
            i = self.vid(p)
            if not ids or ids[-1] != i:
                ids.append(i)
        if len(ids) > 1 and ids[0] == ids[-1]:
            ids.pop()
        if len(set(ids)) < 3:
            return
        if want is not None:
            n = _newell([self.verts[i] for i in ids])
            if n[0] * want[0] + n[1] * want[1] + n[2] * want[2] < 0:
                ids.reverse()
        self.faces.append(ids)
        self.mat_ids.append(mat)

    def data(self, name='facade'):
        return {'verts': [list(v) for v in self.verts], 'faces': [list(f) for f in self.faces],
                'mat_ids': list(self.mat_ids), 'ref': {'host': 'offline', 'doc': 'synthetic', 'handle': 1,
                                                       'name': name}}


def _newell(pts):
    nx = ny = nz = 0.0
    for a, b in zip(pts, pts[1:] + pts[:1]):
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    return nx, ny, nz


def _arch(h):
    u0, v0, w, ht = h['u'], h['sill'], h['w'], h['h']
    r = w / 2.0
    s = v0 + ht - r
    pts = [(u0, v0), (u0 + w, v0)]
    for i in range(0, 13):
        a = math.pi * i / 12
        pts.append((u0 + r + r * math.cos(a), s + r * math.sin(a)))
    return pts, s


def _split(a, b, us, vs):
    """Points of segment a..b (2D, axis-aligned or not) with every crossing grid line inserted."""
    out = [a]
    ts = []
    if abs(a[0] - b[0]) > 1e-12 and abs(a[1] - b[1]) > 1e-12:
        return [a, b]  # arc chords are never crossed by grid lines (checked by the unit test)
    for k, lines in ((0, us), (1, vs)):
        if abs(b[k] - a[k]) > 1e-12:
            for g in lines:
                t = (g - a[k]) / (b[k] - a[k])
                if 1e-9 < t < 1 - 1e-9:
                    ts.append(t)
    for t in sorted(set(round(t, 12) for t in ts)):
        out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    out.append(b)
    return out


def facade(spec):
    """Mesh dict (metres) of a facade spec:

    {'points': [[x, y], ...] plan polyline (convex corners turn right, street on the right-hand side when walking
     along it... normal n = (d.y, -d.x)), 'height': H, 'reveal': 0.25,
     'holes': [{'wall': i, 'kind': 'rect'|'arch', 'u': m from the wall start, 'sill': m, 'w': m, 'h': m}, ...],
     'corners': [{'at': i (vertex between wall i-1 and i), 'a': m on wall i-1, 'b': m on wall i, 'sill', 'h'}],
     'name': 'facade'}"""
    pts = [tuple(p) for p in spec['points']]
    H = float(spec['height'])
    R = float(spec.get('reveal', REVEAL))
    walls = []
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        d = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
        walls.append({'o': a, 'd': d, 'n': (d[1], -d[0]), 'L': L, 'holes': []})
    for h in spec.get('holes', ()):
        walls[h['wall']]['holes'].append(dict(h))
    corners = [dict(c) for c in spec.get('corners', ())]
    for c in corners:
        wa, wb = walls[c['at'] - 1], walls[c['at']]
        wa['holes'].append({'kind': 'cornerA', 'u': wa['L'] - c['a'], 'w': c['a'], 'sill': c['sill'], 'h': c['h']})
        wb['holes'].append({'kind': 'cornerB', 'u': 0.0, 'w': c['b'], 'sill': c['sill'], 'h': c['h']})
    vs = {0.0, H}
    for w in walls:
        for h in w['holes']:
            vs |= {h['sill'], h['sill'] + h['h']}
            if h.get('kind') == 'arch':
                vs.add(_arch(h)[1])
    vs = sorted(vs)
    m = Mesh()

    def P(w, u, v, depth=0.0):
        return (w['o'][0] + w['d'][0] * u - w['n'][0] * depth, w['o'][1] + w['d'][1] * u - w['n'][1] * depth, v)

    for wi, w in enumerate(walls):
        out3 = (w['n'][0], w['n'][1], 0.0)
        us = {0.0, w['L']}
        for h in w['holes']:
            us |= {h['u'], h['u'] + h['w']}
            if h.get('kind') == 'arch':
                us.add(h['u'] + h['w'] / 2.0)
        us = sorted(us)
        for i in range(len(us) - 1):
            for j in range(len(vs) - 1):
                cu, cv = (us[i] + us[i + 1]) / 2, (vs[j] + vs[j + 1]) / 2
                hole = next((h for h in w['holes'] if h['u'] < cu < h['u'] + h['w']
                             and h['sill'] < cv < h['sill'] + h['h']), None)
                if hole is None:
                    m.face([P(w, us[i], vs[j]), P(w, us[i + 1], vs[j]), P(w, us[i + 1], vs[j + 1]),
                            P(w, us[i], vs[j + 1])], 1, out3)
                elif hole.get('kind') == 'arch':
                    pass  # spandrels below
        for h in w['holes']:
            kind = h.get('kind', 'rect')
            u0, v0, u1, v1 = h['u'], h['sill'], h['u'] + h['w'], h['sill'] + h['h']
            if kind == 'arch':
                arc, s = _arch(h)
                arc_pts = arc[2:]  # angle 0 .. pi
                tr, tl = (u1, v1), (u0, v1)
                for k in range(6):
                    m.face([P(w, *tr), P(w, *arc_pts[k]), P(w, *arc_pts[k + 1])], 1, out3)
                for k in range(6, 12):
                    m.face([P(w, *tl), P(w, *arc_pts[k]), P(w, *arc_pts[k + 1])], 1, out3)
                outline = [(u0, v0), (u1, v0)] + arc_pts[:] + [(u0, v0)]
                outline = outline[:-1]
            elif kind in ('cornerA', 'cornerB'):
                continue
            else:
                outline = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
            fine = []
            for k in range(len(outline)):
                seg = _split(outline[k], outline[(k + 1) % len(outline)], us, vs)
                fine.extend(seg[:-1])
            for k in range(len(fine)):
                a, b = fine[k], fine[(k + 1) % len(fine)]
                # reveal quad faces the opening's inside
                m.face([P(w, a[0], a[1]), P(w, b[0], b[1]), P(w, b[0], b[1], R), P(w, a[0], a[1], R)], 2)
    for c in corners:
        wa, wb = walls[c['at'] - 1], walls[c['at']]
        v0, v1 = c['sill'], c['sill'] + c['h']
        # inner corner = intersection of the two back-offset lines
        pa = P(wa, 0.0, 0.0, R)
        pb = P(wb, 0.0, 0.0, R)
        da, db = wa['d'], wb['d']
        den = da[0] * db[1] - da[1] * db[0]
        t = ((pb[0] - pa[0]) * db[1] - (pb[1] - pa[1]) * db[0]) / den
        ci = (pa[0] + da[0] * t, pa[1] + da[1] * t)
        ua0, ub1 = wa['L'] - c['a'], c['b']
        usa = sorted({0.0, wa['L']} | {x for h in wa['holes'] for x in (h['u'], h['u'] + h['w'])})
        usb = sorted({0.0, wb['L']} | {x for h in wb['holes'] for x in (h['u'], h['u'] + h['w'])})
        for v in (v0, v1):
            fa = [q[0] for q in _split((ua0, v), (wa['L'], v), usa, [])]
            fb = [q[0] for q in _split((0.0, v), (ub1, v), usb, [])]
            want = (0, 0, 1) if v == v0 else (0, 0, -1)
            # two trapezoids sharing the mitre (outer corner .. inner corner)
            qa = [P(wa, u, v) for u in fa] + [(ci[0], ci[1], v), P(wa, ua0, v, R)]
            qb = [P(wb, u, v) for u in fb] + [P(wb, ub1, v, R), (ci[0], ci[1], v)]
            m.face(qa, 2, want)
            m.face(qb, 2, want)
        for wall, u, end in ((wa, ua0, 'a'), (wb, ub1, 'b')):
            col = [q[1] for q in _split((u, v0), (u, v1), [], vs)]
            for k in range(len(col) - 1):
                inward = (wall['d'][0], wall['d'][1], 0.0) if end == 'a' else (-wall['d'][0], -wall['d'][1], 0.0)
                m.face([P(wall, u, col[k]), P(wall, u, col[k + 1]), P(wall, u, col[k + 1], R),
                        P(wall, u, col[k], R)], 2, inward)
    return m.data(spec.get('name', 'facade'))


def truth(spec):
    """Expected window-plane frames of the rect/arch holes: [{'centre', 'z', 'x', 'w', 'h', 'kind', 'wall'}]."""
    pts = [tuple(p) for p in spec['points']]
    R = float(spec.get('reveal', REVEAL))
    out = []
    for h in spec.get('holes', ()):
        a, b = pts[h['wall']], pts[h['wall'] + 1]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        d = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
        n = (d[1], -d[0])
        u = h['u'] + h['w'] / 2
        c = (a[0] + d[0] * u - n[0] * R, a[1] + d[1] * u - n[1] * R, h['sill'] + h['h'] / 2)
        out.append({'centre': c, 'z': (n[0], n[1], 0.0), 'x': (d[0], d[1], 0.0), 'w': h['w'], 'h': h['h'],
                    'kind': h.get('kind', 'rect'), 'type': h.get('type')})
    return out


def kpp1_badik(name='J_Badik'):
    """The L10 acceptance facade: walls 24 m and 12 m with a shared corner (0 and 90 deg), KPP1-W01..W03 openings
    (one 10 cm from the wall end), a non-standard 1.5 x 1.5, an arch and one corner L opening; a 10 m wall at
    30 deg is `kpp1_badik_30()`."""
    holes = []
    u = 1.0
    for t in ('KPP1-W01', 'KPP1-W03', 'KPP1-W01', 'KPP1-W02', 'KPP1-W03', 'KPP1-W01'):
        w, h = KPP1[t]
        holes.append({'wall': 0, 'kind': 'rect', 'u': u, 'sill': 0.9 if h < 3 else 0.3, 'w': w, 'h': h, 'type': t})
        u += w + 1.6
    holes.append({'wall': 0, 'kind': 'rect', 'u': 0.10, 'sill': 4.2, 'w': 1.18, 'h': 1.8, 'type': 'KPP1-W01'})
    holes.append({'wall': 0, 'kind': 'rect', 'u': 18.0, 'sill': 4.2, 'w': 1.5, 'h': 1.5, 'type': None})
    holes.append({'wall': 0, 'kind': 'arch', 'u': 20.0, 'sill': 0.9, 'w': 1.18, 'h': 1.8, 'type': None})
    for i, t in enumerate(('KPP1-W01', 'KPP1-W03', 'KPP1-W01')):
        w, h = KPP1[t]
        holes.append({'wall': 1, 'kind': 'rect', 'u': 2.0 + 3.4 * i, 'sill': 0.9, 'w': w, 'h': h, 'type': t})
    return {'name': name, 'points': [[0, 0], [24, 0], [24, 12]], 'height': 7.0, 'reveal': REVEAL, 'holes': holes,
            'corners': [{'at': 1, 'a': 1.2, 'b': 1.2, 'sill': 4.2, 'h': 1.8}]}


def kpp1_badik_30(name='J_Badik30'):
    a = math.radians(30)
    p1 = [10 * math.cos(a), 10 * math.sin(a)]
    holes = [{'wall': 0, 'kind': 'rect', 'u': 1.0 + 3.0 * i, 'sill': 0.9, 'w': KPP1[t][0], 'h': KPP1[t][1], 'type': t}
             for i, t in enumerate(('KPP1-W01', 'KPP1-W03', 'KPP1-W01'))]
    return {'name': name, 'points': [[0, 0], p1], 'height': 3.5, 'reveal': REVEAL, 'holes': holes, 'corners': []}


# ---- Max side --------------------------------------------------------------------------------------------------
def _scale(rt):
    per = {'millimeters': 0.001, 'centimeters': 0.01, 'meters': 1.0, 'inches': 0.0254, 'feet': 0.3048}
    return per[str(rt.units.SystemType).lower().lstrip('#')] * float(rt.units.SystemScale)


def mesh_node(rt, data, name, pos=(0.0, 0.0, 0.0)):
    """Editable_Mesh from a metre mesh dict (fan-triangulated, edges of the fans hidden), placed at pos (metres)."""
    k = 1.0 / _scale(rt)
    verts = [rt.Point3(v[0] * k, v[1] * k, v[2] * k) for v in data['verts']]
    tris, ids, vis = [], [], []
    for f, mid in zip(data['faces'], data['mat_ids']):
        for i in range(1, len(f) - 1):
            tris.append(rt.Point3(f[0] + 1, f[i] + 1, f[i + 1] + 1))
            ids.append(mid)
            vis.append((i == 1, True, i == len(f) - 2))
    node = rt.mesh(vertices=rt.Array(*verts), faces=rt.Array(*tris), materialIDs=rt.Array(*ids))
    for fi, (a, b, c) in enumerate(vis, 1):
        rt.setEdgeVis(node, fi, 1, a)
        rt.setEdgeVis(node, fi, 2, b)
        rt.setEdgeVis(node, fi, 3, c)
    rt.update(node)
    node.name = name
    node.pos = rt.Point3(pos[0] * k, pos[1] * k, pos[2] * k)
    return node


def props_of(j):
    """User props a station node needs (build_scene._props rewrites the buffer of the node make() returns)."""
    if j.get('kind') == 'facade':
        return {'agr_role': 'body'}
    if j.get('kind') == 'marker':
        return {'agr_role': 'opening', 'agr_window_type': j['type'],
                'agr_opening': json.dumps({'corner': False, 'depth': 0.25, 'h': j.get('h', 1.8), 'sill': 0.9,
                                           'w': j.get('w', 1.18), 'wall': 'polygon'}, sort_keys=True)}
    return {}


def _restore_props(rt, current):
    """build_scene._props replaces the user-prop buffer of each node right after make(); every make() (the seal of
    the win.generate station is made last) writes the J props back onto the J nodes made before it."""
    from pathlib import Path
    doc = json.loads((Path(__file__).resolve().parent / 'J.json').read_text(encoding='utf-8'))
    for st in doc['stations']:
        for o in st['objects']:
            if o['name'] == current:
                continue
            node = rt.getNodeByName(o['name'])
            if node is None:
                continue
            for k, v in props_of(o['extra']['j']).items():
                rt.setUserProp(node, k, v)


def make(obj, rt):
    j = (obj.get('extra') or {}).get('j') or {}
    pos = obj.get('pos') or [0.0, 0.0, 0.0]
    _restore_props(rt, obj['name'])
    if j.get('kind') == 'facade':
        data = facade(dict(j['spec']))
        xs = [v[0] for v in data['verts']]
        ys = [v[1] for v in data['verts']]
        node = mesh_node(rt, data, obj['name'],
                         (pos[0] - (min(xs) + max(xs)) / 2.0, pos[1] - (min(ys) + max(ys)) / 2.0, pos[2]))
    elif j.get('kind') in ('marker', 'seal'):
        k = 1.0 / _scale(rt)
        node = rt.Point(name=obj['name'], size=0.3 * k, cross=True, box=True)
        node.pos = rt.Point3(pos[0] * k, pos[1] * k, pos[2] * k)
    else:
        raise ValueError('J_build: unknown station object ' + repr(obj.get('name')))
    for key, v in props_of(j).items():
        rt.setUserProp(node, key, v)
    return node
