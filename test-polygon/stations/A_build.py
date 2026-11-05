"""new-case: polygon station objects of #979 branch A (place.*): node kinds the polygon builder does not make.

build_scene.py calls make(obj, rt) -> node for every A.json object with `"builder": "A_build"`; obj['extra'] says
what to build (metres; the station scenes frag_a_* are in metres):
* {"kind": "ground", "size": [w, l], "slope_deg": s, "at": [x, y, z]} - a two-triangle Ground rising along +X;
* {"kind": "box", "size": [w, l, h], "at": [x, y, z], "rot_z": deg, "mesh": bool} - a Box (pivot at the base
  centre, UV on), rotated about Z; `mesh: true` collapses it to an Editable_Mesh (triangles, no n-gons).
"""
import math


def make(obj, rt):
    ex = obj.get('extra') or {}
    kind = ex.get('kind')
    if kind == 'ground':
        w, l = ex['size']
        x, y, z = ex.get('at', (0.0, 0.0, 0.0))
        t = math.tan(math.radians(float(ex.get('slope_deg', 0.0))))
        pts = [(-w / 2, -l / 2), (w / 2, -l / 2), (w / 2, l / 2), (-w / 2, l / 2)]
        verts = rt.Array(*[rt.Point3(px, py, px * t) for px, py in pts])
        faces = rt.Array(rt.Point3(1, 2, 3), rt.Point3(1, 3, 4))
        node = rt.mesh(name=obj['name'], vertices=verts, faces=faces)
        node.pos = rt.Point3(x, y, z)
        return node
    if kind == 'box':
        w, l, h = ex['size']
        node = rt.Box(name=obj['name'], width=w, length=l, height=h, mapcoords=True)
        if ex.get('rot_z'):
            rt.rotate(node, rt.EulerAngles(0, 0, float(ex['rot_z'])))
        node.pos = rt.Point3(*ex.get('at', (0.0, 0.0, 0.0)))
        if ex.get('mesh'):
            rt.convertToMesh(node)
        return node
    raise RuntimeError('A_build: unknown kind {!r} for {}'.format(kind, obj['name']))
