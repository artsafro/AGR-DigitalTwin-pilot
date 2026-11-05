"""new-case: node kinds of the #979 branch C stations (qa.normals, qa.facade_compare, qa.procedural_objects).

Called by build/build_scene.py for objects with `"builder": "C_build"`: make(obj, rt) -> node. The mesh is built
around the node pivot and the node is put at obj['pos'] (the station layout); every face gets smoothing group 1
(a delivery mesh has them; only `sg_none` fixtures would not). Kinds in obj['extra']['kind'].
"""
import math


def _quad(x0, x1, y, z0, z1, facing='-y'):
    """A vertical quad in the plane y, facing -y (or +y)."""
    v = [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)]
    f = [(0, 1, 2), (0, 2, 3)] if facing == '-y' else [(0, 2, 1), (0, 3, 2)]
    return v, f


def _hquad(z, size=1.0, flip=False):
    h = size / 2.0
    v = [(-h, -h, z), (h, -h, z), (h, h, z), (-h, h, z)]
    f = [(0, 1, 2), (0, 2, 3)] if not flip else [(0, 2, 1), (0, 3, 2)]
    return v, f


def _box(size=(1.0, 1.0, 1.0), flip=False):
    a, b, c = (s / 2.0 for s in size)
    v = [(-a, -b, 0), (a, -b, 0), (a, b, 0), (-a, b, 0), (-a, -b, 2 * c), (a, -b, 2 * c), (a, b, 2 * c), (-a, b, 2 * c)]
    f = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7),
         (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    if flip:
        f = [(p, r, q) for p, q, r in f]
    return v, f


def _merge(*parts):
    v, f = [], []
    for pv, pf in parts:
        n = len(v)
        v += pv
        f += [(a + n, b + n, c + n) for a, b, c in pf]
    return v, f


def geometry(kind):
    if kind == 'box':
        return _box()
    if kind == 'box_flipped':
        return _box(flip=True)
    if kind == 'double_1mm':
        return _merge(_hquad(0.5), _hquad(0.501))
    if kind == 'card_single':
        return _hquad(0.5)
    if kind == 'card_double_5mm':
        return _merge(_hquad(0.5), _hquad(0.495, flip=True))
    if kind == 'facade_7_panels':
        parts, x = [], -3.49
        for _ in range(7):
            parts.append(_quad(x, x + 0.98, 0.0, 0.0, 3.0))
            x += 1.0
        return _merge(*parts)
    raise ValueError('unknown C_build kind: ' + kind)


def make(obj, rt):
    extra = obj.get('extra') or {}
    kind = extra.get('kind')
    if kind == 'populate_idle_area':
        node = rt.IdleAreaObj()
        node.name = obj['name']
        node.pos = rt.Point3(*obj['pos'])
        return node
    v, f = geometry(kind)
    vertices = rt.Array(*[rt.Point3(*p) for p in v])
    faces = rt.Array(*[rt.Point3(a + 1, b + 1, c + 1) for a, b, c in f])
    node = rt.mesh(name=obj['name'], vertices=vertices, faces=faces)
    for i in range(1, len(f) + 1):
        rt.setFaceSmoothGroup(node, i, 1)
    rt.update(node)
    rt.convertToPoly(node)
    node.pos = rt.Point3(*obj['pos'])
    return node
