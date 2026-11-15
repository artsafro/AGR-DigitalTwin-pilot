"""new-case: pre-triangulation master topology contract (#1420), synthetic fixtures."""
import importlib.util
from pathlib import Path
import json
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[2]


def core():
    path = ROOT / 'adapters/max/agr_tools/master_topology_core.py'
    assert path.is_file(), 'pre-export master topology core is missing'
    spec = importlib.util.spec_from_file_location('master_topology_test', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_export_refuses_before_triangulation(monkeypatch):
    spec = importlib.util.spec_from_file_location('master_runtime_test', ROOT / 'adapters/max/agr_tools/runtime.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    calls = []
    monkeypatch.setattr(mod, 'master_topology', lambda nodes: {'status': 'fail', 'objects': [{'name': 'bad', 'ngons': 1}]}, raising=False)
    monkeypatch.setattr(mod, '_rt', lambda: None)
    monkeypatch.setattr(mod, '_tri_mesh', lambda n: calls.append(n))
    import pytest
    with pytest.raises(ValueError, match='master topology'):
        mod._export_scene([type('Node', (), {'name': 'bad'})()])
    assert calls == []


def test_native_dead_faces_accounted(monkeypatch):
    from types import SimpleNamespace
    spec = importlib.util.spec_from_file_location('master_dead_runtime', ROOT / 'adapters/max/agr_tools/runtime.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    node = SimpleNamespace(name='native')
    deleted = []
    polyop = SimpleNamespace(getNumFaces=lambda n: 3, getDeadFaces=lambda n: [False, True, False],
                             getFaceVerts=lambda n, i: {1: [1,2,3], 2: None, 3: [1,2,3,4,5]}[i])
    monkeypatch.setattr(mod, '_rt', lambda: SimpleNamespace(polyop=polyop, delete=deleted.append))
    monkeypatch.setattr(mod, '_targets', lambda n: n)
    monkeypatch.setattr(mod, '_poly_copy', lambda n: node)
    monkeypatch.setattr(mod, '_load_core', lambda *a: core())
    report = mod.master_topology([node])
    assert report['objects'][0]['ngon_face_ids'] == [3]
    assert report['objects'][0]['faces'] == 2
    assert report['dropped'] == [{'name': 'native', 'face_ids': [2], 'reason': 'native dead polygon slots'}]
    assert deleted == [node]


def test_distribution_contains_shared_core(tmp_path):
    import zipfile
    spec = importlib.util.spec_from_file_location('master_builder_test', ROOT / 'tools/max/build_agr_tools.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = tmp_path / 'agr.mzp'
    mod.build(out)
    with zipfile.ZipFile(out) as z:
        assert z.read('agr_tools/master_topology_core.py') == (ROOT / 'adapters/max/agr_tools/master_topology_core.py').read_bytes()


def test_dump_refuses_export_triangulation(monkeypatch):
    from types import SimpleNamespace as NS
    obj = NS(name='ngon', type='MESH', modifiers=[NS(type='TRIANGULATE', show_viewport=True, name='export-only')])
    fake = NS(context=NS(scene=NS(objects=[obj]), evaluated_depsgraph_get=lambda: None))
    monkeypatch.setitem(sys.modules, 'bpy', fake)
    path = ROOT / 'tools/blender/master_topology_dump.py'
    assert path.is_file(), 'master-specific pre-triangulation dump is missing'
    spec = importlib.util.spec_from_file_location('master_dump_test', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with pytest.raises(ValueError, match='active triangulation modifier'):
        mod.inventory()


def test_mixed_master():
    report = core().check([{'name': 'synthetic', 'face_degrees': [3, 4, 5]}])
    assert report['status'] == 'fail'
    obj = report['objects'][0]
    assert obj == {'name': 'synthetic', 'status': 'fail', 'faces': 3,
                   'triangles': 1, 'triangle_share': 1 / 3, 'quads': 1,
                   'ngons': 1, 'ngon_face_ids': [3]}


@pytest.mark.parametrize('degree', [3, 4])
def test_allowed_degrees(degree):
    r = core().check([{'name': 'mesh', 'face_degrees': [degree]}])
    assert r['status'] == 'pass'
    assert r['objects'][0]['triangle_share'] == (1 if degree == 3 else 0)


@pytest.mark.parametrize('objects', [[], None, {}, [{}],
    [{'name': 'a', 'face_degrees': []}],
    [{'name': 'a', 'face_degrees': [None]}],
    *[[{'name': 'a', 'face_degrees': [v]}] for v in [True, 0, 2, 3.0, '4', float('nan'), float('inf')]],
    [{'name': 'a', 'face_degrees': [4]}, {'name': 'a', 'face_degrees': [3]}]])
def test_invalid_input(objects):
    with pytest.raises(ValueError):
        core().check(objects)


def test_generated_degrees():
    for degree in range(3, 101):
        row = core().check([{'name': 'synth', 'face_degrees': [degree]}])
        assert row['status'] == ('pass' if degree <= 4 else 'fail')
        obj = row['objects'][0]
        assert obj['triangles'] + obj['quads'] + obj['ngons'] == 1


def test_repeat_reset():
    mod = core()
    assert [mod.check([{'name': 'x', 'face_degrees': [d]}])['status']
            for d in [5, 4, 5]] == ['fail', 'pass', 'fail']


def cli(src, out):
    return subprocess.run([sys.executable, str(ROOT / 'tools/qa/master_topology.py'),
                           str(src), '--out', str(out)], capture_output=True, text=True)


def test_fresh_cli(tmp_path):
    src, out = tmp_path / 'master.json', tmp_path / 'report.json'
    src.write_text(json.dumps([{'name': 'synthetic', 'face_degrees': [3, 4, 5]}]))
    proc = cli(src, out)
    assert proc.returncode == 1, proc.stderr
    assert json.loads(out.read_text())['objects'][0]['triangle_share'] == 1 / 3


def test_cli_snapshot_freshness_and_temp_ownership(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('master_cli_test', ROOT / 'tools/qa/master_topology.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    src, out = tmp_path / 'master.json', tmp_path / 'out.json'
    src.write_text('[{"name":"synth","face_degrees":[4]}]')
    partial = tmp_path / 'out.json.partial'
    partial.write_bytes(b'foreign')
    original = mod.load_core
    from types import SimpleNamespace
    def changing(objects):
        report = original().check(objects)
        src.write_text('[{"name":"changed","face_degrees":[5]}]')
        return report
    monkeypatch.setattr(mod, 'load_core', lambda: SimpleNamespace(check=changing))
    with pytest.raises(ValueError, match='changed during'):
        mod.run(src, out)
    assert not out.exists() and partial.read_bytes() == b'foreign'
    monkeypatch.setattr(mod, 'load_core', original)
    assert mod.run(src, out)['status'] == 'fail'
    assert partial.read_bytes() == b'foreign'


def test_cli_duplicate_json_keys(tmp_path):
    src, out = tmp_path / 'master.json', tmp_path / 'out.json'
    src.write_text('[{"name":"synth","face_degrees":[5],"face_degrees":[4]}]')
    result = cli(src, out)
    assert result.returncode != 0
    assert 'duplicate' in result.stderr
    assert not out.exists()


@pytest.mark.parametrize('alias', ['same', 'relative', 'hardlink', 'existing'])
def test_cli_guards(tmp_path, alias):
    src = tmp_path / 'master.json'
    src.write_text('[{"name":"synthetic","face_degrees":[4]}]')
    before = src.read_bytes()
    out = tmp_path / 'report.json'
    if alias == 'same':
        out = src
    elif alias == 'relative':
        out = tmp_path / 'sub' / '..' / src.name
        (tmp_path / 'sub').mkdir()
    elif alias == 'hardlink':
        out.hardlink_to(src)
    else:
        out.write_bytes(b'prior-report')
    prior = out.read_bytes()
    assert cli(src, out).returncode != 0
    assert src.read_bytes() == before
    assert out.read_bytes() == prior
