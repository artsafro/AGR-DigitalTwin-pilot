"""new-case: polygon fragment builder of branch M (#1024): vpm.build, udim.rescale, udim.distortion.

Pure generators (no pymxs, loaded by path by tests/max_tools/test_agr_tools_vpm_layout.py and the native run) plus
`make(obj, rt) -> node` for build/build_scene.py. Synthetic only (IMPL.md): the facade of lab L09
(docs/experiments/vpm.build.md: 4 walls, one at 30 degrees, a bay, openings with reveals, panels id 3 and brick id 7,
glass id 31 in the openings) and the 16-quad plane of udim.distortion (5 quads stretched x3 along U, 3 sheared).

Mesh dict: {'verts': [[x, y, z]] metres, 'faces': [[i...]] polygons (CCW seen from outside), 'mat_ids',
'uvs': [[u, v]] | None, 'face_uvs': [[i...]] | None}.
"""
import math

PANEL, BRICK, GLASS = 3, 7, 31
FOOTPRINT = [(0.0, 0.0), (4.0, 0.0), (4.0, -1.2), (8.0, -1.2), (8.0, 0.0), (12.0, 0.0),
             (12.0 + 6.0 * math.cos(math.radians(30)), 6.0 * math.sin(math.radians(30))),
             (12.0 + 6.0 * math.cos(math.radians(30)), 10.0), (0.0, 10.0)]


class _B:
    def __init__(self):
        self.verts, self.faces, self.ids, self.key = [], [], [], {}

    def v(self, p):
        k = tuple(round(c, 9) for c in p)
        if k not in self.key:
            self.key[k] = len(self.verts)
            self.verts.append([float(c) for c in p])
        return self.key[k]

    def quad(self, pts, mid):
        self.faces.append([self.v(p) for p in pts])
        self.ids.append(mid)


def facade(height=12.0, floor=3.0, col=1.5, brick_from=6.0, openings=True, depth=0.2, margin=0.3,
           footprint=FOOTPRINT, offset=(0.0, 0.0, 0.0), glass=True):
    """Walls along the closed CCW footprint, cells col x floor; panels below brick_from, brick above; every
    other cell of the floors 1..3 is an opening with 4 reveals and a glass pane (id 31)."""
    b = _B()
    ox, oy, oz = offset
    n = len(footprint)
    rows = int(round(height / floor))
    for w in range(n):
        (ax, ay), (bx, by) = footprint[w], footprint[(w + 1) % n]
        length = math.hypot(bx - ax, by - ay)
        cols = max(1, int(round(length / col)))
        tx, ty = (bx - ax) / length, (by - ay) / length
        nx, ny = ty, -tx  # outward of a CCW footprint
        for r in range(rows):
            z0, z1 = r * floor, (r + 1) * floor
            mid = PANEL if z1 <= brick_from + 1e-9 else BRICK
            for c in range(cols):
                s0, s1 = length * c / cols, length * (c + 1) / cols

                def P(s, z, d=0.0):
                    return (ox + ax + tx * s - nx * d, oy + ay + ty * s - ny * d, oz + z)
                hole = openings and 1 <= r <= rows - 1 and (c + r) % 2 == 1 and (s1 - s0) > 2 * margin + 0.2
                if not hole:
                    b.quad([P(s0, z0), P(s1, z0), P(s1, z1), P(s0, z1)], mid)
                    continue
                i0, i1, j0, j1 = s0 + margin, s1 - margin, z0 + margin, z1 - margin
                # ring of 4 quads around the opening (outer face)
                b.quad([P(s0, z0), P(s1, z0), P(i1, j0), P(i0, j0)], mid)
                b.quad([P(s1, z0), P(s1, z1), P(i1, j1), P(i1, j0)], mid)
                b.quad([P(s1, z1), P(s0, z1), P(i0, j1), P(i1, j1)], mid)
                b.quad([P(s0, z1), P(s0, z0), P(i0, j0), P(i0, j1)], mid)
                # reveals (same material), facing into the opening
                b.quad([P(i0, j0), P(i1, j0), P(i1, j0, depth), P(i0, j0, depth)], mid)
                b.quad([P(i1, j0), P(i1, j1), P(i1, j1, depth), P(i1, j0, depth)], mid)
                b.quad([P(i1, j1), P(i0, j1), P(i0, j1, depth), P(i1, j1, depth)], mid)
                b.quad([P(i0, j1), P(i0, j0), P(i0, j0, depth), P(i0, j1, depth)], mid)
                if glass:
                    b.quad([P(i0, j0, depth), P(i1, j0, depth), P(i1, j1, depth), P(i0, j1, depth)], GLASS)
    return {'verts': b.verts, 'faces': b.faces, 'mat_ids': b.ids, 'uvs': None, 'face_uvs': None}


def artist_uv(mesh, seed=7):
    """An «artist» unwrap: every face planar-mapped in its own plane at 1 UV/m with a random island offset
    (the input of L09 that gave 729 px mod repeat in Rapports). Per-face UV vertices."""
    import random
    rnd = random.Random(seed)
    uvs, fuv = [], []
    for face in mesh['faces']:
        pts = [mesh['verts'][i] for i in face]
        a, b, c = pts[0], pts[1], pts[-1]
        e1 = [b[k] - a[k] for k in range(3)]
        l1 = math.sqrt(sum(x * x for x in e1))
        e1 = [x / l1 for x in e1]
        e2 = [c[k] - a[k] for k in range(3)]
        d = sum(e2[k] * e1[k] for k in range(3))
        e2 = [e2[k] - d * e1[k] for k in range(3)]
        l2 = math.sqrt(sum(x * x for x in e2)) or 1.0
        e2 = [x / l2 for x in e2]
        du, dv = rnd.uniform(-3, 3), rnd.uniform(-3, 3)
        idx = []
        for p in pts:
            q = [p[k] - a[k] for k in range(3)]
            idx.append(len(uvs))
            uvs.append([sum(q[k] * e1[k] for k in range(3)) + du, sum(q[k] * e2[k] for k in range(3)) + dv])
        fuv.append(idx)
    return dict(mesh, uvs=uvs, face_uvs=fuv)


def plane16(size=4.0, px_per_m=256.0, tile_px=4096, stretched=(1, 6, 9, 12, 14), sheared=(3, 8, 15)):
    """4 x 4 quads on a 4 x 4 m plane (z = 0, normal +z). UV: px_per_m texel, every quad its own UV island;
    `stretched` quads x3 along U, `sheared` quads skewed by 30 % of their width (same area). Face numbers 1-based."""
    k = px_per_m / tile_px
    cell = size / 4
    verts, faces, uvs, fuv, ids = [], [], [], [], []
    n = 0
    for j in range(4):
        for i in range(4):
            n += 1
            x0, y0 = i * cell, j * cell
            base = len(verts)
            verts += [[x0, y0, 0.0], [x0 + cell, y0, 0.0], [x0 + cell, y0 + cell, 0.0], [x0, y0 + cell, 0.0]]
            faces.append([base, base + 1, base + 2, base + 3])
            ids.append(1)
            u0, v0 = i * cell * k * 1.5, j * cell * k * 1.5  # islands apart
            w = cell * k * (3.0 if n in stretched else 1.0)
            h = cell * k
            sk = 0.3 * cell * k if n in sheared else 0.0
            ub = len(uvs)
            uvs += [[u0, v0], [u0 + w, v0], [u0 + w + sk, v0 + h], [u0 + sk, v0 + h]]
            fuv.append([ub, ub + 1, ub + 2, ub + 3])
    return {'verts': verts, 'faces': faces, 'mat_ids': ids, 'uvs': uvs, 'face_uvs': fuv}


def triangulate(mesh):
    """Fan triangulation of a polygon mesh -> core mesh of uvlayout/udim10 (verts, tris, mat_ids, uvs, uv_tris)
    and the polygon groups (triangles of each polygon)."""
    tris, ids, uvt, groups = [], [], [], []
    for f, face in enumerate(mesh['faces']):
        g = []
        for i in range(1, len(face) - 1):
            g.append(len(tris))
            tris.append([face[0], face[i], face[i + 1]])
            ids.append(mesh['mat_ids'][f])
            if mesh.get('face_uvs'):
                fu = mesh['face_uvs'][f]
                uvt.append([fu[0], fu[i], fu[i + 1]])
        groups.append(g)
    out = {'verts': mesh['verts'], 'tris': tris, 'mat_ids': ids,
           'uvs': mesh.get('uvs'), 'uv_tris': uvt if mesh.get('face_uvs') else None}
    return out, groups


# ---- polygon stations (3ds Max) --------------------------------------------------------------------------------
def make(obj, rt):
    """Editable_Mesh node of a station object: extra.kind facade | facade_small | facade_ids_bad | plane16 |
    plane16_clean | plane16_nouv (extra.artist: an artist unwrap). Sizes in metres, written in system units
    (units.SystemScale); `pos` of the polygon layout moves the node."""
    extra = obj.get('extra') or {}
    kind = extra.get('kind', 'facade')
    if kind == 'plane16':
        mesh = plane16()
    elif kind == 'plane16_clean':
        mesh = plane16(stretched=(), sheared=())
    elif kind == 'plane16_nouv':
        mesh = dict(plane16(), uvs=None, face_uvs=None)
    else:
        small = [(0.0, 0.0), (3.6, 0.0), (3.6, 3.6), (0.0, 3.6)]
        mesh = facade(height=6.0, footprint=small, openings=False, glass=False) if kind == 'facade_small' else \
            facade(height=6.0, footprint=small)
        if kind == 'facade_ids_bad':
            mesh['mat_ids'] = [1005 if i == BRICK else i for i in mesh['mat_ids']]
        if extra.get('artist'):
            mesh = artist_uv(mesh)
    node = build_node(rt, mesh, obj['name'])
    if obj.get('pos'):  # the polygon layout: XY of the station (metres)
        k = 1.0 / _m_per_unit(rt)
        node.position = rt.point3(*[float(c) * k for c in obj['pos']])
    return node


def build_node(rt, mesh, name, pivot_m=(0.0, 0.0, 0.0)):
    """Editable_Mesh from a polygon mesh in metres, built at the origin (the pivot moved to `pivot_m`)."""
    k = 1.0 / _m_per_unit(rt)
    tm, groups = triangulate(mesh)
    node = rt.mesh(numverts=len(tm['verts']), numfaces=len(tm['tris']))
    for i, p in enumerate(tm['verts'], 1):
        rt.setVert(node, i, rt.point3(p[0] * k, p[1] * k, p[2] * k))
    for f, (t, mid) in enumerate(zip(tm['tris'], tm['mat_ids']), 1):
        rt.setFace(node, f, t[0] + 1, t[1] + 1, t[2] + 1)
        rt.setFaceMatID(node, f, mid)
    for g in groups:  # hide the fan diagonals: Max shows the polygons
        for j, f in enumerate(g):
            last = len(g) - 1
            rt.setEdgeVis(node, f + 1, 1, j == 0)
            rt.setEdgeVis(node, f + 1, 2, True)
            rt.setEdgeVis(node, f + 1, 3, j == last)
    if tm['uvs']:
        rt.meshop.setMapSupport(node, 1, True)
        rt.meshop.setNumMapVerts(node, 1, len(tm['uvs']))
        for i, (u, v) in enumerate(tm['uvs'], 1):
            rt.meshop.setMapVert(node, 1, i, rt.point3(u, v, 0.0))
        for f, t in enumerate(tm['uv_tris'], 1):
            rt.meshop.setMapFace(node, 1, f, rt.point3(t[0] + 1, t[1] + 1, t[2] + 1))
    rt.update(node)
    node.name = name
    node.pivot = rt.point3(pivot_m[0] * k, pivot_m[1] * k, pivot_m[2] * k)
    return node


def _m_per_unit(rt):
    per = {'millimeters': 0.001, 'centimeters': 0.01, 'meters': 1.0, 'kilometers': 1000.0, 'inches': 0.0254,
           'feet': 0.3048, 'miles': 1609.344}
    return per[str(rt.units.SystemType).lower().lstrip('#')] * float(rt.units.SystemScale)
