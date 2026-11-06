"""new-case: node kinds of the #1024 branch H stations (model.grid_cleanup 1.0.7, model.glass_planes 1.0.11).

Pure generators (`facade`, `glass`) return the host-neutral mesh of gridclean_core ({'verts' m, 'faces' [{v, uv, mat,
sg}], 'uv'}); unit tests use them without Max. Called by build/build_scene.py for objects with `"builder": "H_build"`:
make(obj, rt) -> node, an Editable Poly built from the mesh around the node pivot, put at obj['pos']. Kinds in
obj['extra']['kind']; obj['extra']['scale'] multiplies the coordinates (a scene in centimetres gets 100).
"""
import math

# Facade 12 x 9 m in the plane y = 0 with 6 openings (#1024 row 17 acceptance).
XS = [0.0, 1.5, 3.0, 4.0, 5.25, 6.75, 9.0, 10.5, 12.0]  # x = 4.0: a UV seam (two islands), never dissolved
ZS = [0.0, 1.0, 2.5, 4.0, 5.5, 7.0, 9.0]                 # z = 4.0: an intermediate loop, dissolved
OPENINGS = [(1.5, 3.0), (5.25, 6.75), (9.0, 10.5)]      # x ranges, rows z 1..2.5 and 5.5..7
OPEN_ROWS = [(1.0, 2.5), (5.5, 7.0)]
BAND_Z = 7.0                                             # band z 7..9: MatID 2, SG 2


def _is_opening(x0, x1, z0, z1):
    return any(a <= x0 and x1 <= b for a, b in OPENINGS) and any(c <= z0 and z1 <= d for c, d in OPEN_ROWS)


def opening_corners(scale=1.0):
    out = []
    for a, b in OPENINGS:
        for c, d in OPEN_ROWS:
            out += [(a * scale, 0.0, c * scale), (b * scale, 0.0, c * scale), (b * scale, 0.0, d * scale),
                    (a * scale, 0.0, d * scale)]
    return out


def facade(triangulate=True, tjunctions=True, noise=True, seam=True, uv=True, loop=True, scale=1.0):
    """The facade mesh. Faces wind counter-clockwise seen from -y (normal -y)."""
    verts, index = [], {}

    def vid(x, z):
        key = (round(x, 6), round(z, 6))
        if key not in index:
            index[key] = len(verts)
            verts.append([x * scale, 0.0, z * scale])
        return index[key]

    def uvof(x, z):
        island_b = seam and x >= 4.0 - 1e-9
        return [(0.5 if island_b else 0.0) + x / 24.0, z / 9.0]

    def uvface(ring_xz, x_ref):
        if not uv:
            return None
        b = seam and x_ref >= 4.0 - 1e-9
        return [[(0.5 if b else 0.0) + x / 24.0, z / 9.0] for x, z in ring_xz]
    zs = ZS if loop else [z for z in ZS if z != 4.0]
    faces = []
    splits = {(10.5, 7.0): 11.25, (0.0, 0.0): 0.75} if tjunctions else {}
    for i in range(len(XS) - 1):
        for j in range(len(zs) - 1):
            x0, x1, z0, z1 = XS[i], XS[i + 1], zs[j], zs[j + 1]
            if _is_opening(x0, x1, z0, z1):
                continue
            mat, sg = (2, 2) if z0 >= BAND_Z - 1e-9 else (1, 1)
            xc = (x0 + x1) / 2.0
            cells = [(x0, x1)]
            if (x0, z0) in splits:
                xm = splits[(x0, z0)]
                cells = [(x0, xm), (xm, x1)]
            for a, b in cells:
                ring = [(a, z0), (b, z0), (b, z1), (a, z1)]
                if noise and (a, z0) == (1.5, 0.0):
                    ring = [(a, z0), (2.2, z0), (b, z0), (b, z1), (a, z1)]  # a collinear point on the border
                ids = [vid(x, z) for x, z in ring]
                uvs = uvface(ring, xc)
                if triangulate and len(ring) == 4:
                    for tri in ((0, 1, 2), (0, 2, 3)):
                        faces.append({'v': [ids[k] for k in tri], 'uv': None if uvs is None else [uvs[k] for k in tri],
                                      'mat': mat, 'sg': sg})
                elif triangulate:  # the noisy pentagon: fan, the collinear point stays in the first triangle
                    for tri in ((0, 1, 2, 3), (0, 3, 4)):
                        faces.append({'v': [ids[k] for k in tri], 'uv': None if uvs is None else [uvs[k] for k in tri],
                                      'mat': mat, 'sg': sg})
                else:
                    faces.append({'v': ids, 'uv': uvs, 'mat': mat, 'sg': sg})
    return {'verts': verts, 'faces': faces, 'uv': bool(uv)}


def facade_weld(scale=1.0):
    """A clean quad facade (no triangles, no T) plus a 0.5 mm crack: the cell x 12..13.5 z 0..1 is a separate
    piece whose left edge points sit 0.5 mm off the facade's right border (weld mode, selection test)."""
    m = facade(triangulate=False, tjunctions=False, noise=False, seam=False, scale=scale)
    base = len(m['verts'])
    d = 0.0005
    pts = [(12.0 + d, 0.0), (13.5, 0.0), (13.5, 1.0), (12.0 + d, 1.0)]
    m['verts'] += [[x * scale, 0.0, z * scale] for x, z in pts]
    m['faces'].append({'v': [base, base + 1, base + 2, base + 3],
                       'uv': [[x / 24.0, z / 9.0] for x, z in pts], 'mat': 1, 'sg': 1})
    return m


# ---- glass ---------------------------------------------------------------------------------------------------
def _grid_quads(origin, du, dv, nu, nv, mat=1, uv0=(0.0, 0.0), uvs=1.0):
    """nu x nv quads on the parallelogram origin + s*du + t*dv; returns (points, faces with local ids)."""
    pts, faces = [], []
    for j in range(nv + 1):
        for i in range(nu + 1):
            s, t = i / nu, j / nv
            pts.append([origin[k] + du[k] * s + dv[k] * t for k in range(3)])
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            ring = [a, a + 1, a + nu + 2, a + nu + 1]
            faces.append({'v': ring, 'mat': mat, 'sg': 1,
                          'uv': [[uv0[0] + uvs * (r % (nu + 1)) / nu, uv0[1] + uvs * (r // (nu + 1)) / nv]
                                 for r in ring]})
    return pts, faces


def _join(*parts):
    verts, faces = [], []
    for pts, fs in parts:
        n = len(verts)
        verts += [list(p) for p in pts]
        faces += [dict(f, v=[v + n for v in f['v']]) for f in fs]
    return {'verts': verts, 'faces': faces, 'uv': True}


def _quad(p0, p1, p2, p3, mat=1):
    return [list(p0), list(p1), list(p2), list(p3)], [{'v': [0, 1, 2, 3], 'mat': mat, 'sg': 1,
                                                      'uv': [[0, 0], [1, 0], [1, 1], [0, 1]]}]


def _box_faces(x0, x1, y0, y1, z0, z1, mat):
    """Six quads of an axis box, outward normals."""
    p = [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [x0, y0, z1], [x1, y0, z1], [x1, y1, z1],
         [x0, y1, z1]]
    rings = [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
    return p, [{'v': r, 'mat': mat, 'sg': 1, 'uv': [[0, 0], [1, 0], [1, 1], [0, 1]]} for r in rings]


def glass(kind, scale=1.0):
    """Glass test pieces of #1024 row 2 (in the plane y = 0 facing -y unless said otherwise)."""
    if kind == 'flat_12':        # flat window 3 x 1 m from 12 quads -> 1 quad
        m = _join(_grid_quads([0, 0, 0], [3, 0, 0], [0, 0, 1], 6, 2))
    elif kind == 'single':       # already one quad: nothing to do (PASS station)
        m = _join(_quad([0, 0, 0], [1.2, 0, 0], [1.2, 0, 1.4], [0, 0, 1.4]))
    elif kind == 'bend_30':      # window on a 30 deg bend, 3 x 3 quads per segment -> 2 quads
        a = math.radians(30)
        m = _join(_grid_quads([0, 0, 0], [1.5, 0, 0], [0, 0, 1.5], 3, 3),
                  _grid_quads([1.5, 0, 0], [1.5 * math.cos(a), 1.5 * math.sin(a), 0], [0, 0, 1.5], 3, 3))
    elif kind == 'corner_sliver':  # 90 deg corner with a 3 cm chamfer sliver -> 2 quads sharing the corner edge
        m = _join(_grid_quads([0, 0, 0], [1.97, 0, 0], [0, 0, 1.5], 2, 2),
                  _quad([1.97, 0, 0], [2.0, 0.03, 0], [2.0, 0.03, 1.5], [1.97, 0, 1.5]),
                  _grid_quads([2.0, 0.03, 0], [0, 1.97, 0], [0, 0, 1.5], 2, 2))
    elif kind == 'corner_stick':  # 90 deg corner, plane A sticks 3 cm out past plane B -> 2 quads, 6 points
        m = _join(_grid_quads([0, 0, 0], [2.03, 0, 0], [0, 0, 1.5], 2, 2),
                  _grid_quads([2.0, 0.0, 0], [0, 2.0, 0], [0, 0, 1.5], 2, 2))
    elif kind == 'frame_5cm':    # glass 1.2 x 1.4 with a 57 mm frame 5 cm deep (front y=-0.025, back y=+0.025)
        w, h, p, d = 1.2, 1.4, 0.057, 0.025
        parts = [_grid_quads([0, 0, 0], [w, 0, 0], [0, 0, h], 2, 2)]
        for y0, y1 in ((-d, d),):
            # four frame bars as boxes around the glass, MatID 2
            parts.append(_box_faces(-p, 0, y0, y1, -p, h + p, 2))
            parts.append(_box_faces(w, w + p, y0, y1, -p, h + p, 2))
            parts.append(_box_faces(0, w, y0, y1, -p, 0, 2))
            parts.append(_box_faces(0, w, y0, y1, h, h + p, 2))
        m = _join(*parts)
    elif kind == 'double_film':  # the same 1 x 1 glass twice, 1 mm apart -> 1 quad
        m = _join(_grid_quads([0, 0, 0], [1, 0, 0], [0, 0, 1], 2, 2),
                  _grid_quads([0, 0.001, 0], [1, 0, 0], [0, 0, 1], 2, 2))
    elif kind == 'package_f100':  # library F100: frame face y=0, two panes at 70.4 / 90.4 mm, one plane at 80.4 mm
        w, h, p = 1.2, 1.4, 0.057
        m = _join(_grid_quads([0, 0.0704, 0], [w, 0, 0], [0, 0, h], 1, 1),
                  _grid_quads([0, 0.0904, 0], [w, 0, 0], [0, 0, h], 1, 1),
                  _quad([-p, 0, -p], [w + p, 0, -p], [w + p, 0, 0], [-p, 0, 0], 2),
                  _quad([-p, 0, h], [w + p, 0, h], [w + p, 0, h + p], [-p, 0, h + p], 2),
                  _quad([-p, 0, 0], [0, 0, 0], [0, 0, h], [-p, 0, h], 2),
                  _quad([w, 0, 0], [w + p, 0, 0], [w + p, 0, h], [w, 0, h], 2))
    elif kind == 'triangle':     # a triangular pane: not a quad after the rule -> ambiguous with the node name
        m = {'verts': [[0, 0, 0], [1, 0, 0], [0.5, 0, 0.8]],
             'faces': [{'v': [0, 1, 2], 'mat': 1, 'sg': 1, 'uv': [[0, 0], [1, 0], [0.5, 0.8]]}], 'uv': True}
    else:
        raise ValueError('unknown glass kind: ' + kind)
    if scale != 1.0:
        m['verts'] = [[c * scale for c in p] for p in m['verts']]
    return m


def mesh_of(extra):
    kind = extra.get('kind')
    scale = float(extra.get('scale', 1.0))
    if kind == 'facade_dirty':
        return facade(scale=scale)
    if kind == 'facade_clean':
        return facade(triangulate=False, tjunctions=False, noise=False, loop=False, scale=scale)
    if kind == 'facade_no_uv':
        return facade(uv=False, scale=scale)
    if kind == 'facade_weld':
        return facade_weld(scale=scale)
    if kind and kind.startswith('glass_'):
        return glass(kind[len('glass_'):], scale=scale)
    raise ValueError('unknown H_build kind: ' + repr(kind))


# ---- Max ---------------------------------------------------------------------------------------------------------
def build_poly(rt, name, mesh):
    """Editable Poly from the mesh (object space = the given coordinates, scene units), MatIDs, SGs, channel 1."""
    # Editable_Poly has no constructor in Max 2024 (job 20261106-044607-93526f70): a box to poly, then emptied
    node = rt.box(name=name, width=1, length=1, height=1)
    rt.convertToPoly(node)
    rt.polyop.deleteVerts(node, rt.execute('#{1..' + str(int(rt.polyop.getNumVerts(node))) + '}'))
    rt.polyop.collapseDeadStructs(node)
    obj = node
    for p in mesh['verts']:
        rt.polyop.createVert(obj, rt.Point3(*p))
    for f in mesh['faces']:
        fi = rt.polyop.createPolygon(obj, rt.Array(*[v + 1 for v in f['v']]))
        rt.polyop.setFaceMatID(obj, fi, int(f['mat']))
        rt.polyop.setFaceSmoothGroup(obj, fi, int(f['sg']))
    if mesh['uv']:
        uvs, keys, ids = [], {}, []
        for f in mesh['faces']:
            row = []
            for t in f['uv']:
                k = (round(t[0], 9), round(t[1], 9))
                if k not in keys:
                    keys[k] = len(uvs) + 1
                    uvs.append(k)
                row.append(keys[k])
            ids.append(row)
        rt.polyop.setMapSupport(obj, 1, True)
        rt.polyop.setNumMapVerts(obj, 1, len(uvs))
        for i, (u, v) in enumerate(uvs):
            rt.polyop.setMapVert(obj, 1, i + 1, rt.Point3(u, v, 0))
        for fi, row in enumerate(ids):
            rt.polyop.setMapFace(obj, 1, fi + 1, rt.Array(*row))
    else:
        rt.polyop.setMapSupport(obj, 1, False)
    return node


def make(obj, rt):
    extra = obj.get('extra') or {}
    node = build_poly(rt, obj['name'], mesh_of(extra))
    node.pos = rt.Point3(*obj['pos'])
    return node
