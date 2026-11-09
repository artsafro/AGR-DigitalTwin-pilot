"""new-case: #1024 branch G polygon builder: make(obj, rt) -> node for the stations of body.prepare (1.0.4),
model.attach_by_material (1.0.5) and model.move_apart (1.0.6). Synthetic geometry only, metres.

obj['extra']['kind'] picks the node:
  level    - Point helper (a LEVEL_* height helper) at obj['pos'];
  box_mat  - 1 m Editable_Poly box; extra.mat = material name (a NEW material instance per object, so two objects
             with one name carry two different materials), no extra.mat = no material;
  double   - Editable_Poly of two 1x1 m quads back to back, extra.gap_mm apart (a double plane for move_apart).
Called by test-polygon/build/build_scene.py inside Max (pymxs runtime `rt`).
"""


def _box(rt, name, mat):
    node = rt.Box(name=name, length=1, width=1, height=1)
    rt.convertTo(node, rt.Editable_Poly)
    if mat:
        m = rt.StandardMaterial(name=mat)
        node.material = m
    return node


def _double(rt, name, gap_m):
    """Two quads: the lower one faces -Z at z=0, the upper one +Z at z=gap (back to back)."""
    node = rt.Plane(name=name, length=1, width=1, lengthsegs=1, widthsegs=1)
    rt.convertTo(node, rt.Editable_Poly)
    obj = node.baseObject
    rt.polyop.flipNormals(obj, [1])
    vs = [rt.polyop.createVert(obj, rt.Point3(x, y, gap_m)) for x, y in
          ((-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5))]
    rt.polyop.createPolygon(obj, vs)
    return node


def make(obj, rt):
    extra = obj.get('extra') or {}
    kind = extra.get('kind')
    name = obj['name']
    if kind == 'level':
        node = rt.Point(name=name, size=1.0, cross=True, box=False)
    elif kind == 'box_mat':
        node = _box(rt, name, extra.get('mat'))
    elif kind == 'double':
        node = _double(rt, name, float(extra.get('gap_mm', 1.0)) / 1000.0)
    else:
        raise RuntimeError('G_build: unknown kind {!r} for {}'.format(kind, name))
    pos = obj.get('pos') or [0.0, 0.0, 0.0]
    node.pos = rt.Point3(float(pos[0]), float(pos[1]), float(pos[2]) if len(pos) > 2 else 0.0)
    return node
