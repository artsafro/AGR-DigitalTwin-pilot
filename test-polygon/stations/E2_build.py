"""new-case: #979 branch E2 polygon builder: make(obj, rt) -> node for the stations of ucx.triangulate,
export.pivot_place, udim.ids_to_udims and model.triangulate (bases 0.8). Synthetic geometry only.

obj['extra']['kind'] picks the node; obj['pos'] is the layout position (polygon_all) or extra['xy'] for the
far-from-zero scene. Called by test-polygon/build/build_scene.py inside Max (pymxs runtime `rt`).
"""
import math

_MXS = r'''
global agr979e2_poly
fn agr979e2_poly name pts counts = (
    local p = convertToPoly (Plane length:1 width:1 lengthsegs:1 widthsegs:1)
    polyop.deleteFaces p #{1} delIsoVerts:true
    local k = 0
    for c in counts do (
        local ids = for i = 1 to c collect (polyop.createVert p pts[k + i])
        k += c
        polyop.createPolygon p ids
    )
    polyop.weldVertsByThreshold p #all
    p.name = name
    p
)
'''

BOX_PTS = [(0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 0), (0, 0, 2), (2, 0, 2), (2, 2, 2), (0, 2, 2)]
BOX_Q = [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]


def _poly(rt, name, pts, polys):
    rt.execute(_MXS)
    flat = [rt.Point3(*(float(c) for c in pts[i])) for poly in polys for i in poly]
    node = rt.agr979e2_poly(name, flat, [len(p) for p in polys])
    rt.polyop.setVertSelection(node, rt.execute('#{}'))
    return node


def _valley(rt, name):
    """UCX box, top corner raised 0.6 m, top split along the valley diagonal (a reflex edge to turn)."""
    pts = [list(p) for p in BOX_PTS]
    pts[6][2] += 0.6
    tris = []
    for a, b, c, d in BOX_Q[:1] + BOX_Q[2:]:
        tris += [[a, b, c], [a, c, d]]
    a, b, c, d = BOX_Q[1]
    tris += [[a, b, d], [b, c, d]]
    return _poly(rt, name, [tuple(p) for p in pts], tris)


def _dart(rt, name):
    """Prism over the outline (0,0) (2,0) (2,2) (2.5,3); the lid edge is reflex inside a «dart» quad."""
    plan = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (2.5, 3.0)]
    pts = [(x, y, 0.0) for x, y in plan] + [(x, y, z) for (x, y), z in zip(plan, (1.0, 1.0, 1.0, 1.5))]
    polys = [[6, 4, 5], [4, 6, 7], [2, 1, 0], [0, 3, 2]] + \
            [[i, (i + 1) % 4, 4 + (i + 1) % 4, 4 + i] for i in range(4)]
    return _poly(rt, name, pts, polys)


def _cell(rt, name, angle, size):
    """L07 cell (4 x 1 x 0.5 m by default), rotation baked into the mesh, no node rotation."""
    b = rt.Box(name=name, width=size[0], length=size[1], height=size[2], widthsegs=8, lengthsegs=2, heightsegs=1)
    rt.convertTo(b, rt.Editable_Poly)
    a = math.radians(angle)
    for v in range(1, int(rt.polyop.getNumVerts(b)) + 1):
        p = rt.polyop.getVert(b.baseObject, v)
        x, y = float(p.x), float(p.y)
        rt.polyop.setVert(b.baseObject, v, rt.Point3(x * math.cos(a) - y * math.sin(a),
                                                     x * math.sin(a) + y * math.cos(a), float(p.z)))
    return b


def _udim(rt, name, ids):
    """Plane 2 x 2 segments, UVs 0..1 (each face inside tile 1001), material IDs per face."""
    p = rt.Plane(name=name, length=2, width=2, lengthsegs=2, widthsegs=2, mapcoords=True)
    rt.convertTo(p, rt.Editable_Poly)
    for f, mid in enumerate(ids, 1):
        rt.polyop.setFaceMatID(p, f, int(mid))
    return p


def make(obj, rt):
    extra = obj.get('extra') or {}
    kind = extra.get('kind')
    name = obj['name']
    if kind == 'ucx_box':
        node = rt.Box(name=name, length=2, width=2, height=2)
        rt.convertTo(node, rt.Editable_Poly)
    elif kind == 'ucx_valley':
        node = _valley(rt, name)
    elif kind == 'ucx_dart':
        node = _dart(rt, name)
    elif kind == 'pivot_cell':
        node = _cell(rt, name, float(extra.get('angle', 0.0)), extra.get('cell', [4.0, 1.0, 0.5]))
    elif kind == 'udim':
        node = _udim(rt, name, extra['ids'])
    elif kind == 'ngon':
        node = rt.Cylinder(name=name, radius=1.0, height=2.0, sides=8, heightsegs=1, capsegs=1)
        rt.convertTo(node, rt.Editable_Poly)
    else:
        raise RuntimeError('E2_build: unknown kind {!r} for {}'.format(kind, name))
    pos = extra.get('xy') or obj.get('pos') or [0.0, 0.0, 0.0]
    node.pos = rt.Point3(float(pos[0]), float(pos[1]), float(pos[2]) if len(pos) > 2 else 0.0)
    return node
