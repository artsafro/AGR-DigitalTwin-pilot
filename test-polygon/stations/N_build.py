"""#1024 branch N polygon builder: tex.dilate and udim.plugs stations.

Called by test-polygon/build/build_scene.py as `make(obj, rt) -> node` for fragment objects with
`"builder": "N_build"`. `obj['extra']['n']`:
* `png`: {"<file>": "rgba_island" | "rgb_white_island"} - synthetic 32x32 PNG written under <texture_dir>/N and set as
  the Diffuse bitmap of a Standard material (the run's own output folder; nothing outside is written);
* `matid`: Material ID of every face (the object is converted to Editable_Poly for udim.plugs).
Synthetic data only.
"""
import struct
import zlib
from pathlib import Path


def _chunk(kind, body):
    return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xffffffff)


def png(kind, size=32):
    alpha = kind == 'rgba_island'
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            inside = 12 <= x < 20 and 12 <= y < 20
            if alpha:
                row += bytes((200, 40, 40, 255) if inside else (0, 0, 0, 0))
            else:
                row += bytes((200, 40, 40) if inside else (255, 255, 255))
        rows.append(bytes(row))
    ihdr = struct.pack('>IIBBBBB', size, size, 8, 6 if alpha else 2, 0, 0, 0)
    return (b'\x89PNG\r\n\x1a\n' + _chunk(b'IHDR', ihdr) + _chunk(b'IDAT', zlib.compress(b''.join(rows), 6))
            + _chunk(b'IEND', b''))


def make(obj, rt):
    spec = (obj.get('extra') or {}).get('n') or {}
    folder = Path(obj.get('texture_dir') or '.') / 'N'
    sx, sy, sz = obj.get('size') or (2, 2, 2)
    node = rt.Box(name=obj['name'], length=float(sy), width=float(sx), height=float(sz))
    node.pos = rt.Point3(*obj['pos'])
    files = spec.get('png') or {}
    for name, kind in files.items():
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / name
        if not target.exists():
            target.write_bytes(png(kind))
    if files:
        mat = rt.Standardmaterial()
        mat.name = obj.get('mat_name') or 'M_' + obj['name'][3:] + '_1'
        node.material = mat
        safe = str(obj['name']).replace('"', '')
        name = sorted(files)[0]
        path = str(folder / name).replace('\', '/').replace('"', '')
        rt.execute('(getNodeByName "{0}").material.diffuseMap = Bitmaptexture fileName:"{1}"'.format(safe, path))
    if spec.get('matid') is not None:
        rt.convertToPoly(node)
        rt.polyop.setFaceMatID(node, rt.execute('#all'), int(spec['matid']))
    return node
