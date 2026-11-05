"""new-case: #979 branch B station builder (base 0.9): nodes and synthetic textures of the B stations.

build/build_scene.py calls make(obj, rt) -> node for every fragment object with `builder: "B_build"`. The node kind is
obj['extra']['kind']; textures are written by the stdlib PNG writer of the package (texqa_core.write_png) into
obj['texture_dir'] (the run's NEW output folder). Synthetic only; metres.
"""
import importlib.util
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_TQ = None

LEGEND = {'finishes': [{'name': 'Plaster_White', 'ral': 'RAL 9010', 'color': '#F1ECE1'},
                       {'name': 'Plaster_Grey', 'ral': 'RAL 7044', 'color': '#B7B3A8'},
                       {'name': 'Brick_Red', 'color': '#8E402A'},
                       {'name': 'Metal_Graphite', 'ral': 'RAL 7024', 'color': '#474A51'},
                       {'name': 'Glass_Dark', 'color': '#20262B'}],
          'ids': [{'id': 1, 'finish': 'Plaster_White'}, {'id': 2, 'finish': 'Plaster_Grey'},
                  {'id': 3, 'finish': 'Brick_Red'}, {'id': 4, 'finish': 'Metal_Graphite'}],
          'seams_m': [1.5, 3.0]}


def _tq():
    global _TQ
    if _TQ is None:
        spec = importlib.util.spec_from_file_location('agr_polygon_b_texqa',
                                                      ROOT / 'adapters' / 'max' / 'agr_tools' / 'texqa_core.py')
        _TQ = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_TQ)
    return _TQ


def _dir(obj):
    d = Path(obj.get('texture_dir') or '.') / 'B'
    d.mkdir(parents=True, exist_ok=True)
    return d


def _png(obj, name, w, h, px, ch):
    p = _dir(obj) / name
    if not p.is_file():
        p.write_bytes(_tq().write_png(w, h, px, ch))
    return str(p).replace('\\', '/')


def _bitmap(rt, path):
    t = rt.Bitmaptexture()
    t.filename = path
    return t


def _pattern(side, seed):
    return bytes(v for y in range(side) for x in range(side)
                 for v in ((x * 7 + seed * 40) % 256, (y * 5 + seed * 20) % 256, (x + y + seed * 9) % 256))


def _dome(size, directx):
    px = bytearray()
    c, r = (size - 1) / 2.0, 0.42 * size
    for y in range(size):
        for x in range(size):
            dx, dy = (x - c) / r, (y - c) / r
            r2 = dx * dx + dy * dy
            if r2 < 0.98:
                hz = math.sqrt(1 - r2)
                nx, g = dx / hz, -dy / hz
                ln = math.sqrt(nx * nx + g * g + 1)
                nx, g, nz = nx / ln, g / ln, 1 / ln
            else:
                nx, g, nz = 0.0, 0.0, 1.0
            g = -g if directx else g
            px += bytes((int(round((nx + 1) * 127.5)), int(round((g + 1) * 127.5)), int(round((nz + 1) * 127.5))))
    return bytes(px)


def _box(rt, name, w, l, h, pos):
    b = rt.Box(name=name, width=w, length=l, height=h)
    b.pos = rt.Point3(*pos)
    rt.convertToPoly(b)
    return b


def _ermn(obj, rt):
    ex = obj['extra']
    node = _box(rt, obj['name'], 2, 2, 2, obj['pos'])
    m = rt.Standardmaterial(name='M_' + obj['name'])
    if ex['normal'] == 'flat':
        n = _png(obj, 'T_BErmnFlat_Normal_1.1001.png', 64, 64, bytes((128, 128, 255)) * 4096, 3)
    else:
        n = _png(obj, 'T_BErmnGl_Normal_1.1001.png', 96, 96, _dome(96, False), 3)
    e = _png(obj, 'T_BErmn_ERM_1.1001.png', 32, 32, bytes((0, 140, 0)) * 1024, 3)
    nb = rt.Normal_Bump()
    nb.normal_map = _bitmap(rt, n)
    m.bumpMap = nb
    m.specularLevelMap = _bitmap(rt, e)
    node.material = m
    return node


def _finish(obj, rt):
    ids = obj['extra']['ids']
    node = _box(rt, obj['name'], 4.0, 3.0, 5.0, obj['pos'])
    for f, mid in zip(range(1, 7), (ids[0], ids[0]) + tuple(ids)):
        rt.polyop.setFaceMatID(node, f, mid)
    node.material = rt.Standardmaterial(name='M_' + obj['name'])
    legend = _dir(obj) / 'B_legend.json'
    if not legend.is_file():
        legend.write_text(json.dumps(LEGEND), encoding='utf-8')
    return node


def _maf(obj, rt):
    ids = obj['extra']['ids']
    sizes = ((0.5, 0.5, 0.8), (1.2, 0.4, 0.4), (0.3, 0.3, 2.0), (2.0, 1.0, 0.1), (0.8, 0.8, 0.8))
    x0, y0, z0 = obj['pos']
    parts = []
    for k, (mid, (w, l, h)) in enumerate(zip(ids, sizes)):
        b = _box(rt, obj['name'] + '_part{}'.format(k), w, l, h, (x0 + k * 0.7 - 1.4, y0, z0))
        for f in range(1, int(rt.polyop.getNumFaces(b)) + 1):
            rt.polyop.setFaceMatID(b, f, mid)
        parts.append(b)
    base = parts[0]
    for p in parts[1:]:
        rt.polyop.attach(base, p)
    base.name = obj['name']
    if obj['extra'].get('bad'):
        rt.polyop.setFaceMatID(base, 1, 101)
    base.material = rt.Standardmaterial(name='M_' + obj['name'])
    return base


def _slots(obj, rt):
    names = obj['extra']['files']
    tiny = _tq().write_png(4, 4, bytes(48), 3)
    mm = rt.MultiMaterial(numsubs=len(names))
    mm.name = 'M_' + obj['name']
    for k, name in enumerate(names):
        p = _dir(obj) / name
        if not p.is_file():
            p.write_bytes(tiny)
        sub = rt.Standardmaterial(name='{}_{}'.format(obj['name'], k + 1))
        sub.diffuseMap = _bitmap(rt, str(p).replace('\\', '/'))
        mm.materialList[k] = sub
    node = _box(rt, obj['name'], 2, 2, 2, obj['pos'])
    node.material = mm
    return node


def _texture(obj, which):
    if which == 'leaf':
        px = bytes(v for y in range(64) for x in range(64) for v in (40, 120 + x % 50, 30, 255 if x < 48 else 0))
        return _png(obj, 'T_BLeaf_d_1.png', 64, 64, px, 4)
    if which == 'grass':
        return _png(obj, 'T_BGrass_d_1.png', 128, 128, bytes((30, 140, 40)) * (128 * 128), 3)
    if which == 'tga':
        import struct
        p = _dir(obj) / 'T_BTga_d_1.tga'
        if not p.is_file():
            p.write_bytes(bytes([0, 0, 2]) + bytes(9) + struct.pack('<HH', 4, 4) + b'\x18\x00' + bytes(48))
        return str(p).replace('\\', '/')
    side = int(which)
    return _png(obj, 'T_BGroundEl_{}_d_1.png'.format(side), side, side, _pattern(side, side // 256), 3)


def _card(obj, rt):
    ex = obj['extra']
    if ex.get('instance_of'):
        src = rt.getNodeByName(ex['instance_of'])
        node = rt.instance(src)
        node.name = obj['name']
        node.pos = rt.Point3(*obj['pos'])
        return node
    side = ex.get('side_m', 1.0)
    node = rt.Plane(name=obj['name'], length=side, width=side * ex.get('aspect', 0.5),
                    lengthsegs=ex.get('segs', [4, 8])[1], widthsegs=ex.get('segs', [4, 8])[0])
    node.pos = rt.Point3(*obj['pos'])
    rt.convertToPoly(node)
    m = rt.Standardmaterial(name='M_' + obj['name'])
    m.diffuseMap = _bitmap(rt, _texture(obj, ex['tex']))
    node.material = m
    return node


KINDS = {'ermn': _ermn, 'finish': _finish, 'maf': _maf, 'slots': _slots, 'card': _card}


def make(obj, rt):
    return KINDS[obj['extra']['kind']](obj, rt)
