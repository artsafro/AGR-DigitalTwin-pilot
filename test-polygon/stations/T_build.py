"""AGR Tools 1.0 (#1024) polygon station builder of branch T: ucx.stairs, qa.omk_te, export.place_by_passport.

`make(obj, rt) -> node` (build/build_scene.py). Everything is synthetic and stdlib only; the pure helpers
(`stair_parts`, `omk_table`, `passport_bytes`, `fbx_bytes`) are checked by the unit tests, the live run uses the same
bytes. Files go to C:/x/test-polygon/t/... (outside the repository, like FBX_DIR); the table and the passport are
USER data of the tools, the package ships none.
"""
import json
import os

RISE, RUN, WIDTH, STEPS = 0.17, 0.28, 1.2, 10
OMK_DIR = 'C:/x/test-polygon/t/omk'
PLACE_DIR = 'C:/x/test-polygon/t/place'


def _box(x0, x1, y0, y1, z0, z1):
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    t = [(0, 3, 2), (0, 2, 1), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6),
         (3, 0, 4), (3, 4, 7)]
    return v, t


def _merge(parts):
    verts, tris = [], []
    for v, t in parts:
        base = len(verts)
        verts += list(v)
        tris += [(a + base, b + base, c + base) for a, b, c in t]
    return verts, tris


def _prism(profile):
    n = len(profile)
    v = [(s, 0.0, z) for s, z in profile] + [(s, WIDTH, z) for s, z in profile]
    t = []
    for i in range(1, n - 1):
        t += [(0, i, i + 1), (n, n + i + 1, n + i)]
    for i in range(n):
        j = (i + 1) % n
        t += [(i, n + j, j), (i, n + i, n + j)]
    return v, t


def _wedge(lift=0.0):
    last = (STEPS - 1) * RUN
    return _prism([(0.0, 0.0), (last, 0.0), (last, STEPS * RISE + lift), (0.0, RISE + lift)])


def stair_parts(variant):
    """(stair mesh, [UCX meshes]) in metres, local origin. variants: ok | no_ucx | per_step | high."""
    stair = _merge([_box(k * RUN, (k + 1) * RUN, 0, WIDTH, 0, (k + 1) * RISE) for k in range(STEPS)])
    if variant == 'ok':
        return stair, [_wedge()]
    if variant == 'high':
        return stair, [_wedge(0.4)]
    if variant == 'per_step':
        return stair, [_box(k * RUN, (k + 1) * RUN, 0, WIDTH, 0, (k + 1) * RISE) for k in range(STEPS)]
    if variant == 'no_ucx':
        return stair, []
    raise ValueError('unknown stair variant: ' + variant)


def omk_table():
    names = ['Здание', 'Окно', 'Крыша', 'Дверь', 'Пол', 'Потолок', 'Лестница', 'Колонна', 'Балка', 'Фундамент']
    lines = ['place\tcode']
    for i in range(50):
        name = names[i % 10] + ' {:02d}'.format(i)
        if i in (7, 19, 31, 43):
            name = 'Стена {:02d}'.format(i)
        lines.append('{}\t{}'.format(name, 1000 + i * 7))
    return ('\n'.join(lines) + '\n').encode('utf-8')


def passport_bytes():
    doc = {'type': 'FeatureCollection', 'features': [{
        'type': 'ObjectFeature', 'geometry': {'type': 'Point', 'coordinates': [12345.678, -6789.012]},
        'properties': {'address': 'synthetic', 'h_relief': '152,3'}, 'Glasses': []}]}
    return json.dumps(doc, ensure_ascii=False).encode('utf-8')


def fbx_bytes():
    return b'Kaydara FBX Binary  \x00\x1a\x00' + (7400).to_bytes(4, 'little') + b'\x00' * 64  # header only: a preview never imports


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.isfile(path):
        with open(path, 'rb') as fh:
            if fh.read() == data:
                return
    with open(path, 'wb') as fh:
        fh.write(data)


def _mesh(rt, name, mesh, pos):
    verts, tris = mesh
    node = rt.mesh(name=name, vertices=rt.Array(*[rt.Point3(*v) for v in verts]),
                   faces=rt.Array(*[rt.Point3(a + 1, b + 1, c + 1) for a, b, c in tris]))
    node.pos = rt.Point3(*[float(c) for c in pos])
    return node


def make(obj, rt):
    extra = obj.get('extra') or {}
    kind = extra.get('kind')
    if kind == 'stairs':
        stair, pieces = stair_parts(extra['variant'])
        node = _mesh(rt, obj['name'], stair, obj['pos'])
        for i, piece in enumerate(pieces, 1):
            _mesh(rt, 'UCX_{}_{:02d}'.format(obj['name'], i), piece, obj['pos'])
        return node
    if kind == 'omk':
        _write(OMK_DIR + '/OMK_synth.tsv', omk_table())
    elif kind == 'place':
        _write(PLACE_DIR + '/model.fbx', fbx_bytes())
        _write(PLACE_DIR + '/model.geojson', passport_bytes())
    else:
        raise ValueError('unknown T station object kind: ' + repr(kind))
    node = rt.Box(name=obj['name'], length=1.0, width=1.0, height=0.5)
    node.pos = rt.Point3(*[float(v) for v in obj['pos']])
    return node
