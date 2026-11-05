"""new-case: #979 branch E1 polygon builder: boxes with Standard materials whose bitmaps point at synthetic files.

Called by test-polygon/build/build_scene.py as `make(obj, rt) -> node` for fragment objects with
`"builder": "E1_build"`. `obj['extra']['e1']` = {"maps": {"diffuseMap": "<file>"}, "files": {"<file>": "<kind>"},
"outside": {"<path relative to the run folder>": "<kind>"}}: `files` are written under <texture_dir>/E1 (the
run's own output folder), `outside` beside it (Maps/ next to the saved scene); a map whose file is not listed
stays missing on purpose. Kinds: rgb16 (64x64 16-bit RGB gradient), noise128 (128x128 random RGB), solid
(8x8 RGB), foreign (8x8 RGB of other content), jpg (JPEG marker bytes, an index candidate only).
Synthetic data only; nothing outside the run folder is written.
"""
import random
import struct
import zlib
from pathlib import Path


def _chunk(kind, body):
    return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xffffffff)


def _png(w, h, depth, rows):
    head = b'\x89PNG\r\n\x1a\n' + _chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, depth, 2, 0, 0, 0))
    return head + _chunk(b'IDAT', zlib.compress(b''.join(b'\x00' + r for r in rows), 6)) + _chunk(b'IEND', b'')


def data(kind):
    if kind == 'rgb16':
        return _png(64, 64, 16, [b''.join(struct.pack('>HHH', x * 1000, y * 1000, 40000) for x in range(64))
                                 for y in range(64)])
    if kind == 'noise128':
        rnd = random.Random(979)
        return _png(128, 128, 8, [bytes(rnd.getrandbits(8) for _ in range(128 * 3)) for _ in range(128)])
    if kind == 'solid':
        return _png(8, 8, 8, [bytes((120, 130, 140)) * 8] * 8)
    if kind == 'foreign':
        return _png(8, 8, 8, [bytes((1, 2, 3)) * 8] * 8)
    if kind == 'jpg':
        return b'\xff\xd8\xff\xe0E1-candidate\xff\xd9'
    raise ValueError('unknown E1 file kind: ' + repr(kind))


def _write(path, kind):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(data(kind))


def make(obj, rt):
    spec = (obj.get('extra') or {}).get('e1') or {}
    base = Path(obj.get('texture_dir') or '.')
    folder = base / 'E1'
    for name, kind in (spec.get('files') or {}).items():
        _write(folder / name, kind)
    for rel, kind in (spec.get('outside') or {}).items():
        _write(base.parent / rel, kind)
    sx, sy, sz = obj.get('size') or (2, 2, 2)
    node = rt.Box(name=obj['name'], length=float(sy), width=float(sx), height=float(sz))
    node.pos = rt.Point3(*obj['pos'])
    maps = spec.get('maps') or {}
    if maps:
        mat = rt.Standardmaterial()
        mat.name = obj.get('mat_name') or 'M_' + obj['name'][3:] + '_1'
        node.material = mat
        safe = str(obj['name']).replace('"', '')
        for prop, name in sorted(maps.items()):
            path = str(folder / name).replace('\\', '/').replace('"', '')
            # MAXScript keeps the file name of a missing bitmap (a pymxs property set drops it)
            rt.execute('(getNodeByName "{0}").material.{1} = Bitmaptexture fileName:"{2}"'.format(safe, prop, path))
    return node
