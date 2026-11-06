"""new-case: polygon station objects of #1024 branch F (project.passport, source.intake, scene.source_class,
scene.small_parts): node kinds the polygon builder does not make.

build_scene.py calls make(obj, rt) -> node for every F.json object with `"builder": "F_build"`; obj['extra'] says
what to build (system units of the frag_f_* scenes, which are metres):
* {"kind": "box", "size": [w, l, h], "at": [x, y, z]} - an Editable_Mesh box with its minimum corner at `at`
  (numbers as given: an FBX in cm read 1:1 is a box of 2000 x 1500 x 3000 units at 234 567 800);
* {"kind": "panels", "count": n, "size": [w, h], "gap": g, "at": [x, y, z]} - ONE mesh of n separate quads in a
  row (a panel facade without a shell: n connected parts of equal area).
"""


def _mesh(rt, name, verts, faces):
    node = rt.mesh(name=name, vertices=rt.Array(*[rt.Point3(*p) for p in verts]),
                   faces=rt.Array(*[rt.Point3(*(i + 1 for i in f)) for f in faces]))
    return node


def make(obj, rt):
    ex = obj.get('extra') or {}
    kind = ex.get('kind')
    x0, y0, z0 = ex.get('at', (0.0, 0.0, 0.0))
    if kind == 'box':
        w, l, h = ex['size']
        verts = [(x0 + dx * w, y0 + dy * l, z0 + dz * h) for dz in (0, 1) for dy in (0, 1) for dx in (0, 1)]
        faces = [(0, 2, 1), (1, 2, 3), (4, 5, 6), (5, 7, 6), (0, 1, 4), (1, 5, 4), (2, 6, 3), (3, 6, 7), (0, 4, 2),
                 (2, 4, 6), (1, 3, 5), (3, 7, 5)]
        return _mesh(rt, obj['name'], verts, faces)
    if kind == 'panels':
        n = int(ex['count'])
        w, h = ex['size']
        gap = float(ex.get('gap', 0.5))
        verts, faces = [], []
        for i in range(n):
            x = x0 + i * (w + gap)
            b = len(verts)
            verts += [(x, y0, z0), (x + w, y0, z0), (x + w, y0, z0 + h), (x, y0, z0 + h)]
            faces += [(b, b + 1, b + 2), (b, b + 2, b + 3)]
        return _mesh(rt, obj['name'], verts, faces)
    raise RuntimeError('F_build: unknown kind {!r} for {}'.format(kind, obj['name']))
