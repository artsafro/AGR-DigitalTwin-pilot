"""new-case: synthetic binary FBX version-diff public CLI regression fixtures."""
import json
import struct
import subprocess
import sys
from pathlib import Path

import pytest

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


def encode(n, offset, version=7400):
    name, values, children = n
    bname = name.encode()
    p = b''.join(prop(v) for v in values)
    body = b''
    hlen = 25 if version == 7500 else 13
    start = offset + hlen + len(bname) + len(p)
    for child in children:
        body += encode(child, start + len(body), version)
    if children:
        body += bytes(hlen)
    return struct.pack('<QQQB' if version == 7500 else '<IIIB', start + len(body), len(values), len(p), len(bname)) + bname + p + body


def fbx(*, shift=0, uv=False, ucx_uv=False, material='X', name='Main', mutate=None, version=7400):
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
    data = b'Kaydara FBX Binary  \x00\x1a\x00' + struct.pack('<I', version)
    trees = [node('Objects', children=objects), node('Connections', children=links)]
    if mutate:
        mutate(trees)
    for n in trees:
        data += encode(n, len(data), version)
    return data + bytes(25 if version == 7500 else 13)


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


def test_unchanged(tmp_path):
    p, r = run(tmp_path)
    assert p.returncode == 0, p.stdout + p.stderr
    m = r['objects']['Main']
    assert m['moved_count'] == 0 and m['max_displacement'] == 0
    assert m['before']['bbox'] == [[0, 0, 0], [373, 1, 0]]
    assert m['before']['uv_layers'] == []
    assert m['before']['materials'] == ['X']
    assert m['before']['face_count'] == 1


def test_ucx_uv(tmp_path):
    p, r = run(tmp_path, None, fbx(uv=True, ucx_uv=True), '--expect-changed', 'Main:uv')
    assert p.returncode == 1, p.stdout
    assert r['errors'] == ['UCX_Main:uv']
    assert r['objects']['UCX_Main']['after']['uv_layers'] == ['UVMap']


def test_scoped_declarations(tmp_path):
    p, r = run(tmp_path, None, fbx(uv=True), '--expect-changed', 'Main:uv')
    assert p.returncode == 0, p.stdout
    p, r = run(tmp_path, None, fbx(shift=2, uv=True), '--expect-changed', 'Main:uv')
    assert r['errors'] == ['Main:geometry']
    p, r = run(tmp_path, None, fbx(shift=2, uv=True), '--expect-changed', 'Main')
    assert p.returncode == 0, p.stdout
    p, r = run(tmp_path, None, fbx(material='Y'), '--expect-changed', 'Main:geometry')
    assert p.returncode == 1 and 'Main:materials' in r['errors']


@pytest.mark.parametrize('kwargs', [{'material': 'X.001'}, {'name': 'Main.001'}, {'material': 'X.1234'}])
def test_duplicate_suffix(tmp_path, kwargs):
    p, r = run(tmp_path, None, fbx(**kwargs), '--expect-changed', kwargs.get('name', 'Main'))
    assert p.returncode == 1
    assert any('duplicate suffix' in s for s in r['errors']), r


def cli(a, b, *args):
    return subprocess.run([sys.executable, str(SCRIPT), str(a), str(b), *map(str, args)], cwd=ROOT, capture_output=True, text=True)


@pytest.mark.parametrize('data', [b'', b'not fbx', fbx()[:100], fbx(shift=float('nan')), fbx(shift=float('inf'))], ids=['empty', 'unsupported', 'partial', 'nan', 'inf'])
def test_invalid_inputs(tmp_path, data):
    p, r = run(tmp_path, after=data)
    assert p.returncode == 2 and r['status'] == 'error', p.stdout + p.stderr


def test_threshold(tmp_path):
    p, r = run(tmp_path, None, fbx(shift=1), '--tolerance', '1')
    assert p.returncode == 1 and r['objects']['Main']['moved_count'] == 374
    for tolerance in ['nan', 'inf', '-1']:
        p, r = run(tmp_path, None, None, '--tolerance', tolerance)
        assert p.returncode == 2


def test_zip_members(tmp_path):
    import zipfile
    a, b = tmp_path / 'prev.zip', tmp_path / 'new.zip'
    for p, texture in [(a, b'old'), (b, b'new')]:
        with zipfile.ZipFile(p, 'w') as z:
            z.writestr('model.fbx', fbx())
            z.writestr('map.png', texture)
    p = cli(a, b)
    r = json.loads(p.stdout)
    assert p.returncode == 1 and 'member:map.png' in r['errors'], p.stdout
    assert len(r['members']['before']) == 2
    with zipfile.ZipFile(b, 'w') as z:
        z.writestr('model.fbx', fbx())
        z.writestr('map.png', b'old')
    assert cli(a, b).returncode == 0


def test_inventory(tmp_path):
    p, r = run(tmp_path, None, fbx(name='Other'))
    assert p.returncode == 1 and r['objects']['Other']['before'] is None
    assert r['objects']['Main']['after'] is None
    p, r = run(tmp_path, None, fbx(name='Other'), '--expect-changed', 'Main', '--expect-changed', 'Other')
    assert p.returncode == 0
    for declaration in ['Typo:uv', 'Main:typo', '', 'Main:geometry:uv']:
        p, r = run(tmp_path, None, None, '--expect-changed', declaration)
        assert p.returncode == 2 and declaration in r['errors'][0]


def test_reset_repeat(tmp_path):
    a, b = tmp_path / 'prev.fbx', tmp_path / 'new.fbx'
    run(tmp_path, after=fbx(shift=2))
    assert cli(a, b).returncode == cli(b, a).returncode == 1
    b.write_bytes(fbx())
    first = cli(a, b)
    assert first.returncode == 0
    assert first.stdout == cli(a, b).stdout


@pytest.mark.parametrize('kind', ['same', 'resolved', 'hardlink', 'report_input', 'report_hardlink', 'existing'])
def test_path_guards(tmp_path, kind):
    import os
    a, b, out = tmp_path / 'prev.fbx', tmp_path / 'new.fbx', tmp_path / 'report.json'
    a.write_bytes(fbx()); b.write_bytes(fbx())
    args = []
    if kind == 'same': b = a
    if kind == 'resolved': b = tmp_path / '.' / a.name
    if kind == 'hardlink':
        b.unlink(); os.link(a, b)
    if kind == 'report_input': out = a
    if kind == 'report_hardlink': os.link(a, out)
    if kind == 'existing': out.write_text('foreign')
    if kind.startswith('report') or kind == 'existing': args = ['--report', out]
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    p = cli(a, b, *args)
    assert p.returncode == 2, p.stdout
    assert {p: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_cli(tmp_path):
    a, b, out = tmp_path / 'prev.fbx', tmp_path / 'new.fbx', tmp_path / 'report.json'
    a.write_bytes(fbx()); b.write_bytes(fbx(shift=2))
    p = cli(a, b, '--report', out)
    assert p.returncode == 1, p.stdout + p.stderr
    assert json.loads(out.read_text()) == json.loads(p.stdout)
    assert json.loads(p.stdout)['inputs']['previous']['sha256']
    assert cli(a, b, '--report', out).returncode == 2
    assert json.loads(out.read_text())['status'] == 'fail'


def test_delivery_skill():
    text = (ROOT / '.agents/skills/validate-delivery/SKILL.md').read_text(encoding='utf-8')
    assert 'tools/qa/archive_diff.py' in text
    assert '--expect-changed' in text and 'previous version' in text


@pytest.mark.parametrize('case', ['global', 'transform', 'nan_transform', 'unsupported', 'dangling', 'orphan_suffix', 'slot', 'uv_partial', 'polygon_partial', 'empty_geometry', 'duplicate_name', 'layer_selection'])
def test_complete_readback(tmp_path, case):
    def mutate(t):
        objects, links = t[0][2], t[1][2]
        if case == 'global': t.append(node('GlobalSettings', children=[node('P', ['UnitScaleFactor', 100.])]))
        if case in ('transform', 'nan_transform'):
            objects[1] = node('Model', objects[1][1], [node('Properties70', children=[node('P', ['Lcl Translation', float('nan') if case == 'nan_transform' else 1.])])])
        if case == 'unsupported': objects.append(node('Deformer', [7, 'Skin', 'Skin']))
        if case == 'dangling': links.append(node('C', ['OO', 99, 2]))
        if case == 'orphan_suffix': objects.append(node('Material', [7, 'Unused.001', '']))
        if case == 'slot': objects[0][2].append(node('LayerElementMaterial', [0], [node('MappingInformationType', ['AllSame']), node('ReferenceInformationType', ['IndexToDirect']), node('Materials', [[7]])]))
        if case == 'uv_partial': objects[0][2][-1][2][-1][1][0].pop()
        if case == 'polygon_partial': objects[0][2][1][1][0].append(0)
        if case == 'empty_geometry': objects[0][2][0][1][0].clear()
        if case == 'duplicate_name': objects[3][1][1] = 'Main\x00\x01Model'
        if case == 'layer_selection': objects[0][2].append(node('Layer', [0], [node('LayerElement', children=[node('Type', ['LayerElementUV']), node('TypedIndex', [99])])]))
    p, r = run(tmp_path, None, fbx(uv=True, mutate=mutate), '--expect-changed', 'Main:uv')
    assert p.returncode in (1, 2), (case, p.stdout, p.stderr)
    if case == 'slot': assert '7' in p.stdout
    if case in ('nan_transform', 'unsupported', 'dangling', 'uv_partial', 'polygon_partial', 'empty_geometry', 'layer_selection'):
        assert p.returncode == 2, p.stdout


def test_generated_displacements(tmp_path):
    from tools.qa.archive_diff import compare_paths
    a, b = tmp_path / 'a.fbx', tmp_path / 'b.fbx'
    a.write_bytes(fbx())
    for axis in range(3):
        for count in (1, 2, 17, 373, 374):
            def mutate(t):
                points = t[0][2][0][2][0][1][0]
                for i in range(count): points[3*i+axis] += 0.25
            b.write_bytes(fbx(mutate=mutate))
            r = compare_paths(a, b)
            assert r['status'] == 'fail'
            assert r['objects']['Main']['moved_count'] == count
            assert r['objects']['Main']['max_displacement'] == .25


def test_input_mutation(tmp_path, monkeypatch, capsys):
    from tools.qa import archive_diff as gate
    a, b, out = tmp_path/'a.fbx', tmp_path/'b.fbx', tmp_path/'r.json'
    a.write_bytes(fbx()); b.write_bytes(fbx())
    original = gate.load
    def changing(p):
        result = original(p)
        if p == b: a.write_bytes(fbx(shift=2))
        return result
    monkeypatch.setattr(gate, 'load', changing)
    assert gate.main([str(a), str(b), '--report', str(out)]) == 2
    assert 'input changed' in capsys.readouterr().out
    assert not out.exists()


def test_report_race(tmp_path, monkeypatch):
    from tools.qa import archive_diff as gate
    import os
    a, b, out = tmp_path/'a.fbx', tmp_path/'b.fbx', tmp_path/'r.json'
    a.write_bytes(fbx()); b.write_bytes(fbx())
    original = gate.compare_paths
    def racing(*args):
        result = original(*args)
        os.link(a, out)
        return result
    monkeypatch.setattr(gate, 'compare_paths', racing)
    assert gate.main([str(a), str(b), '--report', str(out)]) == 2
    assert out.read_bytes() == a.read_bytes() == fbx()


@pytest.mark.parametrize('kind', ['empty', 'unsafe', 'duplicate', 'unsupported_member', 'duplicate_objects'])
def test_bad_zip(tmp_path, kind):
    import zipfile
    a, b = tmp_path/'a.fbx', tmp_path/'b.zip'
    a.write_bytes(fbx())
    with zipfile.ZipFile(b, 'w') as z:
        if kind != 'empty': z.writestr('model.fbx', fbx())
        if kind == 'unsafe': z.writestr('../escape', 'x')
        if kind == 'duplicate': z.writestr('MODEL.FBX', fbx())
        if kind == 'unsupported_member': z.writestr('other.fbx', b'not fbx')
        if kind == 'duplicate_objects': z.writestr('other.fbx', fbx())
    p = cli(a,b)
    assert p.returncode == 2 and json.loads(p.stdout)['status'] == 'error', p.stdout


def test_unknown_array_encoding(tmp_path):
    data = bytearray(fbx())
    offset = data.index(b'Verticesd') + len(b'Verticesd') + 4
    struct.pack_into('<I', data, offset, 2)
    p, r = run(tmp_path, after=bytes(data))
    assert p.returncode == 2 and 'encoding' in r['errors'][0]


def test_binary_7500(tmp_path):
    p, r = run(tmp_path, fbx(version=7500), fbx(version=7500, shift=2))
    assert p.returncode == 1 and r['objects']['Main']['moved_count'] == 374


def test_untouched_glass(tmp_path):
    def glass(t):
        t[0][2][3][1][1] = 'MainGlass\x00\x01Model'
    p, r = run(tmp_path, fbx(mutate=glass), fbx(uv=True, ucx_uv=True, mutate=glass), '--expect-changed', 'Main:uv')
    assert p.returncode == 1 and r['errors'] == ['MainGlass:uv']


def test_uv_coordinate_changes(tmp_path):
    def moved_uv(t):
        t[0][2][0][2][-1][2][-2][1][0][0] = 0.5
    p, r = run(tmp_path, fbx(uv=True), fbx(uv=True, mutate=moved_uv))
    assert p.returncode == 1 and r['errors'] == ['Main:uv']
    assert r['objects']['Main']['uv_changed'] is True