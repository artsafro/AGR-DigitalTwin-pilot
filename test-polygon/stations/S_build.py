"""new-case: polygon builder of branch S (#1024): nodes of the stations ucx.gap (1.0.27), light.export (1.0.29) and
pack.deliver (1.0.26).

`make(obj, rt) -> node` is called by build/build_scene.py for objects with `builder: "S_build"` (and by
tests/max_tools/run_agr_tools_deliver_native.py the same way). `extra.kind`:
* "box": an Editable_Poly box from `extra.min` / `extra.max` in METRES (world, pivot at the origin);
* "light": a light of class `extra.light` ("Omnilight" | "freeSpot" | "targetSpot" | "Free_Light"), `pos` in metres,
  `extra.aim` (metres) = target position of a Target Spot / the look-at point of the other lights;
* "dummy": a Dummy at `pos` (metres).
`extra.units` ("meters" | "centimeters", default meters) sets the scene unit system before the node is made, so the
same metre geometry is checked in both unit systems. Parents are linked by build_scene (`parent`).
"""

SCALE = {'meters': 1.0, 'centimeters': 100.0}


def _units(rt, units):
    if units not in SCALE:
        raise ValueError('S_build: unknown units ' + repr(units))
    if str(rt.units.SystemType).lower() != units or float(rt.units.SystemScale) != 1.0:
        rt.units.SystemType = rt.Name(units)
        rt.units.SystemScale = 1.0
    return SCALE[units]


def _box(rt, name, lo, hi, k):
    xs, ys, zs = [(lo[i] * k, hi[i] * k) for i in range(3)]
    verts = [rt.Point3(x, y, z) for x in xs for y in ys for z in zs]
    # corners: index = 4 * ix + 2 * iy + iz (+1 for MAXScript); outward quads split in two triangles
    quads = [(1, 2, 4, 3), (5, 7, 8, 6), (1, 5, 6, 2), (3, 4, 8, 7), (1, 3, 7, 5), (2, 6, 8, 4)]
    faces = []
    for a, b, c, d in quads:
        faces += [rt.Point3(a, b, c), rt.Point3(a, c, d)]
    node = rt.mesh(name=name, vertices=verts, faces=faces)
    for i in range(1, len(faces) + 1):
        rt.setEdgeVis(node, i, 3, False) if i % 2 == 1 else rt.setEdgeVis(node, i, 1, False)
    rt.update(node)
    rt.convertToPoly(node)
    return node


def make(obj, rt):
    extra = obj.get('extra') or {}
    k = _units(rt, extra.get('units', 'meters'))
    kind = extra.get('kind')
    name = obj['name']
    if kind == 'box':
        return _box(rt, name, extra['min'], extra['max'], k)
    pos = rt.Point3(*(float(v) * k for v in obj.get('pos') or (0, 0, 0)))
    if kind == 'dummy':
        node = rt.Dummy(name=name)
        node.pos = pos
        return node
    if kind != 'light':
        raise ValueError('S_build: unknown kind ' + repr(kind))
    cls = extra.get('light')
    maker = {'Omnilight': rt.Omnilight, 'freeSpot': rt.freeSpot, 'targetSpot': rt.targetSpot,
             'Free_Light': rt.Free_Light}.get(cls)
    if maker is None:
        raise ValueError('S_build: unknown light class ' + repr(cls))
    aim = extra.get('aim')
    if cls == 'targetSpot':
        target = rt.Targetobject(name=name + '.Target')
        node = maker(name=name, target=target)
        node.pos = pos
        target.pos = rt.Point3(*(float(v) * k for v in (aim or (0, 0, 0))))
        return node
    node = maker(name=name)
    node.pos = pos
    if aim is not None:  # a free light turned to look at a point: a non-trivial rotation for the readback
        d = rt.Point3(*(float(v) * k for v in aim)) - pos
        node.dir = rt.normalize(d)
    return node
