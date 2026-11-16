"""new-case: synthetic binary FBX version-diff public CLI regression fixtures."""
import json
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'tools/qa/archive_diff.py'


def prop(v):
    if isinstance(v, str):
        b = v.encode('utf-8')
        return b'S' + struct.pack('<I', len(b)) + b
    if isinstance(v, int):
        return b'L' + struct.pack('<q', v)
    if isinstance(v, float):
        return b'D' + struct.pack('<d', v)
    code = 'i' if all(isinstance(x, int) for x in v) else 'd'
    b = struct.pack('<' + code * len(v), *v)
    return code.encode() + struct.pack('<III', len(v), 0, len(b)) + b


def node(name, values=(), children=()):
    return name, values, children


def encode(n, offset):
    name, values, children = n
    bname = name.encode()
    p = b''.join(prop(v) for v in values)
    body = b''
    start = offset + 13 + len(bname) + len(p)
    for child in children:
        body += encode(child, start + len(body))
    if children:
        body += bytes(13)
    return struct.pack('<IIIB', start + len(body), len(values), len(p), len(bname)) + bname + p + body


def fbx(*, shift=0, uv=False, ucx_uv=False, material='X', name='Main'):
    verts = [c for i in range(374) for c in (float(i) + shift, float(i % 2), 0.0)]
    objects, links = [], []
    for gid, mid, label, points, has_uv in [(1, 2, name, verts, uv), (3, 4, 'UCX_Main', [0., 0., 0., 1., 0., 0., 0., 1., 0.], ucx_uv)]:
        kids = [node('Vertices', [points]), node('PolygonVertexIndex', [[0, 1, -3]])]
        if has_uv:
            kids.append(node('LayerElementUV', [0], [node('Name', ['UVMap']), node('MappingInformationType', ['ByPolygonVertex']), node('ReferenceInformationType', ['IndexToDirect']), node('UV', [[0., 0., 1., 0., 0., 1.]]), node('UVIndex', [[0, 1, 2]])]))
        objects += [node('Geometry', [gid, label + '\x00\x01Geometry', 'Mesh'], kids), node('Model', [mid, label + '\x00\x01Model', 'Mesh'])]
        links += [node('C', ['OO', gid, mid]), node('C', ['OO', mid, 0])]
    objects.append(node('Material', [5, material + '\x00\x01Material', '']))
    links.append(node('C', ['OO', 5, 2]))
    data = b'Kaydara FBX Binary  \x00\x1a\x00' + struct.pack('<I', 7400)
    for n in [node('Objects', children=objects), node('Connections', children=links)]:
        data += encode(n, len(data))
    return data + bytes(13)


def run(tmp_path, before=None, after=None, *args):
    a, b = tmp_path / 'prev.fbx', tmp_path / 'new.fbx'
    a.write_bytes(fbx() if before is None else before)
    b.write_bytes(fbx() if after is None else after)
    p = subprocess.run([sys.executable, str(SCRIPT), str(a), str(b), *args], capture_output=True, text=True, cwd=ROOT)
    return p, json.loads(p.stdout) if p.stdout else None


def test_shifted_374(tmp_path):
    p, r = run(tmp_path, after=fbx(shift=2))
    assert r is not None, p.stderr
    assert p.returncode == 1
    m = r['objects']['Main']
    assert m['moved_count'] == 374
    assert m['max_displacement'] == 2
    assert m['before']['vertex_count'] == m['after']['vertex_count'] == 374
    assert 'Main:geometry' in r['errors']
