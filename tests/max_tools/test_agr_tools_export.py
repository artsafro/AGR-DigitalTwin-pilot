"""new-case: AGR Tools 0.4.0 checked-export button seams.

Pattern: new-case. Probes the guarantees for the one new button: gates run in
order and a failure writes nothing, a clean fixture's FBX readback matches the
dry-run, paths never alias, and an existing file is never overwritten.
"""
import importlib.util
import itertools
import json
import math
import os
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'adapters/max/agr_tools'
RUNTIME = PACKAGE / 'runtime.py'
EXPORT_CORE = PACKAGE / 'export_core.py'


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _hygiene(name, *, channels=(1,), props='MapChannel:1 = UV\r\n', node_ca=()):
    return {
        'name': name,
        'custom_attributes': {'base': [], 'node': list(node_ca), 'modifiers': [], 'materials': []},
        'user_props': props,
        'map_channels': list(channels),
    }


def _texel(name, xyz, uv, material='brick', profile='VPM', map_px=1024):
    return {
        'profile': profile,
        'materials': [{'name': material, 'map_px': map_px}],
        'faces': [{'id': '1', 'mesh': name, 'material': material, 'xyz': xyz, 'uv': uv}],
    }


def _triangle(name='wall', handle=1, z=0.0, material_id=1, material='brick'):
    xyz = [(0.0, 0.0, z), (1.0, 0.0, z), (0.0, 1.0, z)]
    return {
        'name': name,
        'handle': handle,
        'material': material,
        'material_ids': [material_id],
        'vertices': [list(p) for p in xyz],
        'faces': [[0, 1, 2]],
        'hygiene': _hygiene(name),
        'slot_gaps': [],
        'texel': _texel(name, xyz, [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)], material),
    }


def _box(lo, hi):
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    return [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
            [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]]


BOX_T = [[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4],
         [1, 2, 6], [1, 6, 5], [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]]


_UCX_HANDLE = 7000


def _ucx(name, lo, hi, handle=None):
    global _UCX_HANDLE
    if handle is None:
        _UCX_HANDLE += 1
        handle = _UCX_HANDLE
    return {
        'name': name,
        'handle': handle,
        'verts': _box(lo, hi),
        'tris': [list(t) for t in BOX_T],
        'hygiene': _hygiene(name),
    }


def _scene(*objects, ucx=None, units='m', axis='Z-up'):
    return {'objects': list(objects), 'ucx': [] if ucx is None else list(ucx), 'units': units, 'axis': axis}


def _core():
    assert EXPORT_CORE.is_file(), 'checked-export core is missing'
    return _load(EXPORT_CORE, 'agr_export_core_test')


def test_version_macro_and_completed_rollout():
    runtime = RUNTIME.read_text(encoding='utf-8')
    mcr = (PACKAGE / 'agr_tools.mcr').read_text(encoding='utf-8')
    readme = (PACKAGE / 'README.md').read_text(encoding='utf-8')
    startup = (PACKAGE / 'startup.ms').read_text(encoding='utf-8')
    install = (PACKAGE / 'install.ms').read_text(encoding='utf-8')
    assert 'VERSION = "0.4.0"' in runtime
    assert '0.002' in runtime and '0.005' in runtime
    assert 'AGRToolsExport' in mcr
    assert 'Checked export' in mcr
    assert '0.4.0' in startup and 'Export' in startup
    assert 'AGRTools-0.4.0' in install
    assert 'export_core.py' in install
    assert 'Checked export' in readme
    assert 'first rollout complete' in readme.lower()
    assert EXPORT_CORE.is_file()


def test_clean_fixture_readback_matches_dry_run_and_python_gates(tmp_path):
    core = _core()
    from dt_ai.ops.xview_gate import Part, gate_report
    from twinqa.export_hygiene import hygiene_findings, repair_plan
    from twinqa.geometry.checks import check_material_ids, load_ranges
    from twinqa.geometry.mesh import Soup
    from twinqa.geometry.ucx_audit import classify, collision_findings

    piece = _ucx('UCX_SM_Addr_Main_001', (3.0, 0.0, 0.0), (4.0, 1.0, 1.0))
    scene = _scene(_triangle(), ucx=[piece])
    target = tmp_path / 'clean.fbx'
    source = tmp_path / 'source.json'
    source.write_text('{"keep": true}\n', encoding='utf-8')
    before = source.read_bytes()
    preview = core.dry_run(scene, target, source)
    assert preview['status'] == 'pass', preview
    assert preview['plan']['stopped'] is None
    assert [g['name'] for g in preview['plan']['gates']] == ['cleanup', 'matid', 'xview', 'ucx', 'texel']
    assert preview['plan']['object_count'] == 2
    assert preview['plan']['triangle_count'] == 13
    assert preview['plan']['material_count'] == 1
    assert preview['plan']['units'] == 'm' and preview['plan']['axis'] == 'Z-up'
    assert preview['plan']['unit_scale_factor'] == 100.0
    assert preview['plan']['readback'] is None
    assert not target.exists()
    assert list(tmp_path.iterdir()) == [source]

    obj = scene['objects'][0]
    dumps = [obj['hygiene'], piece['hygiene']]
    assert preview['plan']['gates'][0]['counts']['finding_status'] == {
        f.name: f.status for f in hygiene_findings(dumps, 'export-copy')}
    assert preview['plan']['gates'][0]['counts']['actions'] == [item['actions'] for item in repair_plan(dumps)['objects']]
    soup = Soup(np.asarray(obj['vertices'], float), np.asarray(obj['faces'], np.int64),
                np.asarray(obj['material_ids'], np.int64), None, {})
    tool_matid = check_material_ids(soup, {'unassigned_ids_max': 0}, load_ranges())
    assert preview['plan']['gates'][1]['counts']['status'] == tool_matid['status']
    assert preview['plan']['gates'][1]['counts']['value'] == tool_matid['value']
    assert preview['plan']['gates'][1]['counts']['details']['udim_as_material_id'] == tool_matid['details']['udim_as_material_id']
    part = Part(obj['name'], np.asarray(obj['vertices'], np.float64), tuple(tuple(f) for f in obj['faces']), None)
    tool_xview = gate_report([part], coords='as-stored')
    assert preview['plan']['gates'][2]['counts']['passed'] == tool_xview['passed']
    assert preview['plan']['gates'][2]['counts']['totals'] == tool_xview['totals']
    assert preview['plan']['gates'][3]['counts']['collision'] == collision_findings([piece])
    assert preview['plan']['gates'][3]['counts']['classify'] == [classify(piece['verts'], piece['tris'])]
    assert all(g['status'] == 'pass' for g in preview['plan']['gates'] if g['name'] != 'texel')
    assert preview['plan']['gates'][4]['status'] == 'report'

    with pytest.raises(ValueError, match='unsupported writer'):
        core.commit(scene, target, source, preview)
    assert not target.exists()
    assert not target.with_suffix('.report.json').exists()
    assert source.read_bytes() == before

    def writer(path, _plan):
        path.write_bytes(b'injected')

    def reader(_data):
        return {
            'object_count': preview['plan']['object_count'],
            'triangle_count': preview['plan']['triangle_count'],
            'material_count': preview['plan']['material_count'],
            'unit_scale_factor': preview['plan']['unit_scale_factor'],
            'axis': preview['plan']['axis'],
            'error': None,
            'object_names': list(preview['plan']['object_names']),
        }

    report = core.commit(scene, target, source, preview, writer=writer, readback_fn=reader)
    assert report['status'] == 'pass', report
    assert report['plan']['readback']['object_count'] == preview['plan']['object_count']
    assert report['plan']['readback']['triangle_count'] == preview['plan']['triangle_count']
    assert report['plan']['readback']['material_count'] == preview['plan']['material_count']
    assert report['plan']['readback']['unit_scale_factor'] == preview['plan']['unit_scale_factor']
    assert sorted(report['plan']['readback']['object_names']) == sorted(preview['plan']['object_names'])
    assert source.read_bytes() == before
    written = target.with_suffix('.report.json')
    assert written.is_file() and target.is_file()
    assert json.loads(written.read_text(encoding='utf-8'))['status'] == 'pass'
    runtime = _load(RUNTIME, 'agr_runtime_export_ok')
    assert runtime.parse_report(json.dumps(report))['status'] == 'pass'


def test_each_gate_refuses_and_writes_nothing(tmp_path):
    core = _core()
    from dt_ai.ops.xview_gate import Part, gate_report
    from twinqa.export_hygiene import hygiene_findings
    from twinqa.geometry.checks import check_material_ids, load_ranges
    from twinqa.geometry.mesh import Soup
    from twinqa.geometry.ucx_audit import collision_findings

    cleanup = _triangle('dirty')
    cleanup['hygiene'] = _hygiene('dirty', channels=(1, 2), props='note=planted\r\nMapChannel:1 = UV\r\nMapChannel:2 = extra\r\n')
    matid = _triangle('udim', material_id=1001)
    stacked = _triangle('overlap')
    stacked['vertices'] = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0],
                           [0.0, 0.0, 0.002], [1.0, 0.0, 0.002], [0.0, 1.0, 0.002]]
    stacked['faces'] = [[0, 1, 2], [3, 4, 5]]
    stacked['material_ids'] = [1, 1]
    upper = [(0.0, 0.0, 0.002), (1.0, 0.0, 0.002), (0.0, 1.0, 0.002)]
    stacked['texel']['faces'].append({
        'id': '2', 'mesh': 'overlap', 'material': 'brick', 'xyz': upper,
        'uv': [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
    })
    ucx_scene_obj = _triangle('body')
    pieces = [
        _ucx('UCX_SM_Addr_Main_001', (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)),
        _ucx('UCX_SM_Addr_Main_002', (0.2, 0.0, 0.0), (1.2, 1.0, 1.0)),
    ]
    cases = {
        'cleanup': (_scene(cleanup), 'cleanup'),
        'matid': (_scene(matid), 'matid'),
        'xview': (_scene(stacked), 'xview'),
        'ucx': (_scene(ucx_scene_obj, ucx=pieces), 'ucx'),
    }
    for name, (scene, gate) in cases.items():
        target = tmp_path / f'{name}.fbx'
        source = tmp_path / f'{name}-in.json'
        source.write_text('{}\n', encoding='utf-8')
        before = source.read_bytes()
        preview = core.dry_run(scene, target, source)
        assert preview['status'] == 'fail', name
        assert preview['plan']['stopped'] == gate, name
        runtime = _load(RUNTIME, 'agr_runtime_export_' + name)
        assert runtime.parse_report(json.dumps(preview))['status'] == 'fail'
        assert preview['plan']['gates'][-1]['name'] == gate
        names = [item['name'] for item in scene['objects']] + [item['name'] for item in scene['ucx']]
        assert sorted(item['name'] for item in preview['plan']['dropped']) == sorted(names)
        assert all(item['reason'] for item in preview['plan']['dropped'])
        with pytest.raises(ValueError, match=gate):
            core.commit(scene, target, source, preview)
        assert not target.exists()
        assert not Path(str(target) + '.partial').exists()
        assert not target.with_suffix('.report.json').exists()
        assert source.read_bytes() == before
        assert list(tmp_path.glob(f'{name}*')) == [source]

    obj = matid
    soup = Soup(np.asarray(obj['vertices'], float), np.asarray(obj['faces'], np.int64),
                np.asarray(obj['material_ids'], np.int64), None, {})
    tool = check_material_ids(soup, {'unassigned_ids_max': 0}, load_ranges())
    got = core.dry_run(cases['matid'][0], tmp_path / 'm.fbx', tmp_path / 'm.json')
    assert got['plan']['gates'][-1]['counts']['details']['udim_as_material_id'] == tool['details']['udim_as_material_id']
    assert got['plan']['gates'][-1]['counts']['value']['unassigned_triangles'] == tool['value']['unassigned_triangles']
    dirty = cleanup
    finding = {f.name: f.status for f in hygiene_findings([dirty['hygiene']], 'export-copy')}
    got = core.dry_run(cases['cleanup'][0], tmp_path / 'c.fbx', tmp_path / 'c.json')
    assert got['plan']['gates'][-1]['counts']['finding_status'] == finding
    part = Part('overlap', np.asarray(stacked['vertices'], np.float64), ((0, 1, 2), (3, 4, 5)), None)
    tool_x = gate_report([part], coords='as-stored')
    got = core.dry_run(cases['xview'][0], tmp_path / 'x.fbx', tmp_path / 'x.json')
    assert got['plan']['gates'][-1]['counts']['totals'] == tool_x['totals']
    assert tool_x['passed'] is False
    got = core.dry_run(cases['ucx'][0], tmp_path / 'u.fbx', tmp_path / 'u.json')
    assert got['plan']['gates'][-1]['counts']['collision'] == collision_findings(pieces)
    assert len(got['plan']['gates'][-1]['counts']['collision']) >= 1


def test_fail_closed_paths_threshold_and_random_clean(tmp_path):
    core = _core()
    good = _scene(_triangle())
    target = tmp_path / 'out.fbx'
    source = tmp_path / 'in.json'
    source.write_bytes(b'{"keep": true}\n')
    before = source.read_bytes()

    with pytest.raises(ValueError, match='empty'):
        core.dry_run(_scene(), target, source)
    partial = _triangle()
    del partial['vertices']
    with pytest.raises(ValueError, match='vertices'):
        core.dry_run(_scene(partial), target, source)
    nan = _triangle()
    nan['vertices'][0][1] = math.nan
    with pytest.raises(ValueError, match='non-finite'):
        core.dry_run(_scene(nan), target, source)
    inf = _triangle()
    inf['vertices'][0][0] = math.inf
    with pytest.raises(ValueError, match='non-finite'):
        core.dry_run(_scene(inf), target, source)
    with pytest.raises(ValueError, match='yards'):
        core.dry_run(_scene(_triangle(), units='yards'), target, source)
    with pytest.raises(ValueError, match='Y-up'):
        core.dry_run(_scene(_triangle(), axis='Y-up'), target, source)
    missing_mat = _triangle()
    missing_mat['texel']['materials'] = [{'name': 'stone', 'map_px': 1024}]
    with pytest.raises(ValueError, match='brick'):
        core.dry_run(_scene(missing_mat), target, source)
    exact = _triangle(material_id=1001)
    refused = core.dry_run(_scene(exact), target, source)
    assert refused['status'] == 'fail' and refused['plan']['stopped'] == 'matid'
    zero = _triangle(material_id=0)
    refused = core.dry_run(_scene(zero), target, source)
    assert refused['status'] == 'fail' and refused['plan']['stopped'] == 'matid'
    touched = _triangle('touch')
    touched['vertices'] = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0],
                           [0.0, 0.0, 0.002], [1.0, 0.0, 0.002], [0.0, 1.0, 0.002]]
    touched['faces'] = [[0, 1, 2], [3, 4, 5]]
    touched['material_ids'] = [1, 1]
    refused = core.dry_run(_scene(touched), target, source)
    assert refused['status'] == 'fail' and refused['plan']['stopped'] == 'xview'
    assert refused['plan']['gates'][-1]['counts']['totals']['overlapping_vertices'] >= 1

    outside = _triangle()
    outside['texel']['materials'][0]['map_px'] = 64
    outside['texel']['profile'] = 'VPM'
    reported = core.dry_run(_scene(outside), target, source)
    assert reported['status'] == 'pass', reported
    assert reported['plan']['gates'][-1]['name'] == 'texel'
    assert reported['plan']['gates'][-1]['counts']['status'] == 'fail'

    with pytest.raises(ValueError, match='input'):
        core.dry_run(good, source, source)
    report_alias = tmp_path / 'alias.fbx'
    report_source = tmp_path / 'alias.report.json'
    report_source.write_bytes(before)
    with pytest.raises(ValueError, match='input'):
        core.dry_run(good, report_alias, report_source)
    partial_source = Path(str(tmp_path / 'part.fbx') + '.partial')
    partial_source.write_bytes(before)
    with pytest.raises(ValueError, match='input'):
        core.dry_run(good, tmp_path / 'part.fbx', partial_source)
    with pytest.raises(ValueError, match='same file'):
        core.dry_run(good, target, source, report_path=target)
    with pytest.raises(ValueError, match='same file'):
        core.dry_run(good, target, source, report_path=Path(str(target) + '.partial'))
    link = tmp_path / 'linked.fbx'
    os.link(source, link)
    with pytest.raises(ValueError, match='input'):
        core.dry_run(good, link, source)
    assert source.read_bytes() == before
    assert report_source.read_bytes() == before
    assert partial_source.read_bytes() == before
    assert not target.exists()

    existing = tmp_path / 'exists.fbx'
    existing.write_bytes(b'keep')
    stale_partial = Path(str(existing) + '.partial')
    stale_partial.write_bytes(b'partial-keep')
    preview = core.dry_run(good, existing, source)
    assert preview['status'] == 'fail'
    with pytest.raises(ValueError):
        core.commit(good, existing, source, preview)
    assert existing.read_bytes() == b'keep'
    assert stale_partial.read_bytes() == b'partial-keep'

    preview = core.dry_run(good, target, source)
    changed = _scene(_triangle(name='other', handle=2))
    with pytest.raises(ValueError, match='stale'):
        core.commit(changed, target, source, preview)
    assert not target.exists()
    assert source.read_bytes() == before

    code = core.main(['--scene', str(source), '--target', str(source), '--source', str(source)])
    assert code == 1
    assert source.read_bytes() == before

    rng = random.Random(731)
    agreed = 0
    for index in range(8):
        shift = float(index) * 3.0
        jitter = rng.random() * 0.1
        obj = _triangle(name=f'n{index}', handle=index + 1, z=shift)
        obj['vertices'][1][0] = 1.0 + jitter
        obj['texel']['faces'][0]['xyz'] = [tuple(p) for p in obj['vertices']]
        scene = _scene(obj)
        dest = tmp_path / f'rand-{index}.fbx'
        src = tmp_path / f'rand-{index}.json'
        src.write_text('{}\n', encoding='utf-8')
        preview = core.dry_run(scene, dest, src)
        assert preview['status'] == 'pass', preview
        with pytest.raises(ValueError, match='unsupported writer'):
            core.commit(scene, dest, src, preview)
        assert not dest.exists()
        assert not dest.with_suffix('.report.json').exists()
        agreed += 1
    assert agreed == 8

    def writer(path, _plan):
        path.write_bytes(b'injected')

    def bad_reader(_data):
        return {
            'object_count': 1, 'triangle_count': 2, 'material_count': 1,
            'unit_scale_factor': 100.0, 'axis': 'Z-up', 'error': None,
            'object_names': ['wall'],
        }

    dest = tmp_path / 'mismatch.fbx'
    preview = core.dry_run(good, dest, source)
    report = core.commit(good, dest, source, preview, writer=writer, readback_fn=bad_reader)
    assert report['status'] == 'fail'
    assert report['plan']['readback']['triangle_count'] != preview['plan']['triangle_count']
    assert any(f['code'] == 'readback_mismatch' for o in report['objects'] for f in o['findings'])
    runtime = _load(RUNTIME, 'agr_runtime_export_bad')
    assert runtime.parse_report(json.dumps(report))['status'] == 'fail'
    assert source.read_bytes() == before


def _dirty_hygiene(name, channels):
    extra = [ch for ch in channels if ch >= 2]
    props = 'planted=dirty\r\nMapChannel:1 = UV\r\n' + ''.join(
        f'MapChannel:{ch} = extra\r\n' for ch in extra)
    return _hygiene(name, channels=tuple(channels), props=props)


def test_p1_2_cli_refuses_unsupported_writer_in_a_fresh_process(tmp_path):
    """Counterexample 2: the default CLI must not certify a geometry-less FBX."""
    scene_path = tmp_path / 'scene.json'
    scene_path.write_text(json.dumps(_scene(_triangle())), encoding='utf-8')
    target = tmp_path / 'out.fbx'
    proc = subprocess.run(
        [sys.executable, str(EXPORT_CORE), '--scene', str(scene_path), '--target', str(target),
         '--source', str(scene_path)],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    assert proc.returncode != 0, proc.stdout
    assert 'unsupported writer' in proc.stderr
    assert not target.exists()
    assert not target.with_suffix('.report.json').exists()
    assert not Path(str(target) + '.partial').exists()
    assert scene_path.read_text(encoding='utf-8').startswith('{')


def test_p1_2_default_writer_refuses_random_clean_scenes(tmp_path):
    """Brute-force probe: every clean scene the gates would pass still writes nothing."""
    core = _core()
    rng = random.Random(17)
    refused = 0
    for index in range(8):
        obj = _triangle(name=f'w{index}', handle=index + 1, z=float(index) * 3.0)
        obj['vertices'][1][0] = 1.0 + rng.random()
        obj['texel']['faces'][0]['xyz'] = [tuple(point) for point in obj['vertices']]
        scene = _scene(obj)
        dest = tmp_path / f'w-{index}.fbx'
        src = tmp_path / f'w-{index}.json'
        src.write_text('{}\n', encoding='utf-8')
        preview = core.dry_run(scene, dest, src)
        assert preview['status'] == 'pass', preview
        with pytest.raises(ValueError, match='unsupported writer'):
            core.commit(scene, dest, src, preview)
        assert not dest.exists()
        assert not dest.with_suffix('.report.json').exists()
        assert not Path(str(dest) + '.partial').exists()
        assert src.read_text(encoding='utf-8') == '{}\n'
        refused += 1
    assert refused == 8


def test_p1_3_fbx_model_name_is_the_planned_name():
    """Counterexample 3 readback: Max stores `Name\\x00\\x01Model`, not a uniquified suffix."""
    core = _core()
    rng = random.Random(3)
    samples = ['SM_body', 'SM_control', 'UCX_SM_body_01']
    samples += [f'SM_{rng.randrange(10000)}' for _ in range(12)]
    for name in samples:
        assert core.mesh_model_name([None, name + '\x00\x01Model', 'Mesh']) == name
        assert core.mesh_model_name(['Model::' + name, 'Mesh']) == name
    assert core.mesh_model_name(['Mesh']) is None
    assert core.mesh_model_name('SM_body') is None


def test_p1_4_ucx_hull_hygiene_refuses_and_names_that_hull(tmp_path):
    """Counterexample 4: UDP and map channel 2 on a UCX hull stop the export."""
    core = _core()
    body = _triangle('SM_body', handle=1)
    hull = _ucx('UCX_SM_body_01', (3.0, 0.0, 0.0), (4.0, 1.0, 1.0))
    hull['handle'] = 2
    hull['hygiene'] = _dirty_hygiene('UCX_SM_body_01', (1, 2))
    scene = _scene(body, ucx=[hull])
    target = tmp_path / 'ucx-dirty.fbx'
    source = tmp_path / 'ucx-dirty.json'
    source.write_text('{}\n', encoding='utf-8')
    preview = core.dry_run(scene, target, source)
    assert preview['status'] == 'fail', preview
    assert preview['plan']['stopped'] == 'cleanup'
    named = [row['name'] for row in preview['objects'] if row['findings']]
    assert named == ['UCX_SM_body_01']
    finding = next(row for row in preview['objects'] if row['name'] == 'UCX_SM_body_01')['findings'][0]
    assert finding == {'code': 'cleanup', 'ids': [2], 'detail': 'UCX_SM_body_01'}
    assert next(row for row in preview['objects'] if row['name'] == 'SM_body')['findings'] == []
    with pytest.raises(ValueError, match='cleanup'):
        core.commit(scene, target, source, preview)
    assert not target.exists()
    assert not target.with_suffix('.report.json').exists()
    assert not Path(str(target) + '.partial').exists()


def test_p1_5_cleanup_names_only_the_dirty_object(tmp_path):
    """Counterexample 5a: a planted node attribute is not also blamed on the clean object."""
    core = _core()
    clean = _triangle('SM_clean', handle=1)
    dirty = _triangle('SM_dirty', handle=2, z=3.0)
    dirty['hygiene'] = _hygiene('SM_dirty', node_ca=('PlantedCA',))
    preview = core.dry_run(_scene(clean, dirty), tmp_path / 'pair.fbx', tmp_path / 'pair.json')
    assert preview['status'] == 'fail'
    assert preview['plan']['stopped'] == 'cleanup'
    by_name = {row['name']: row['findings'] for row in preview['objects']}
    assert by_name['SM_clean'] == []
    assert by_name['SM_dirty'][0]['code'] == 'cleanup'
    assert by_name['SM_dirty'][0]['detail'] == 'SM_dirty'
    assert not (tmp_path / 'pair.fbx').exists()


def test_p1_5_cleanup_ids_are_the_extra_channels(tmp_path):
    """True components: extra map channels, not a fabricated face id beside them."""
    core = _core()
    dirty = _triangle('SM_dirty', handle=1)
    dirty['hygiene'] = _dirty_hygiene('SM_dirty', (1, 2, 5))
    preview = core.dry_run(_scene(dirty), tmp_path / 'ch.fbx', tmp_path / 'ch.json')
    assert preview['plan']['stopped'] == 'cleanup'
    assert preview['objects'][0]['findings'][0]['ids'] == [2, 5]
    assert preview['objects'][0]['findings'][0]['detail'] == 'SM_dirty'


def test_p1_5_cleanup_precedes_missing_material(tmp_path):
    """Counterexample 5b: cleanup is the first finding when the material is also missing."""
    core = _core()
    obj = _triangle('SM_body', handle=1)
    obj['material'] = None
    obj['hygiene'] = _hygiene('SM_body', node_ca=('PlantedCA',))
    preview = core.dry_run(_scene(obj), tmp_path / 'both.fbx', tmp_path / 'both.json')
    assert preview['status'] == 'fail'
    assert preview['plan']['stopped'] == 'cleanup'
    assert [item['code'] for item in preview['objects'][0]['findings']] == ['cleanup']
    assert preview['plan']['gates'][0]['name'] == 'cleanup'
    assert not (tmp_path / 'both.fbx').exists()


def test_p1_5_dirty_ucx_and_missing_material_stops_at_cleanup(tmp_path):
    """Combination of 4 and 5: the hull is the only offender, and nothing is written."""
    core = _core()
    body = _triangle('SM_body', handle=1)
    body['material'] = None
    hull = _ucx('UCX_SM_body_01', (5.0, 0.0, 0.0), (6.0, 1.0, 1.0))
    hull['handle'] = 3
    hull['hygiene'] = _dirty_hygiene('UCX_SM_body_01', (1, 2))
    scene = _scene(body, ucx=[hull])
    target = tmp_path / 'combo.fbx'
    source = tmp_path / 'combo.json'
    source.write_text('{}\n', encoding='utf-8')
    preview = core.dry_run(scene, target, source)
    assert preview['plan']['stopped'] == 'cleanup', preview
    named = [row['name'] for row in preview['objects'] if row['findings']]
    assert named == ['UCX_SM_body_01']
    assert all(item['code'] == 'cleanup' for row in preview['objects'] for item in row['findings'])
    with pytest.raises(ValueError, match='cleanup'):
        core.commit(scene, target, source, preview)
    assert not target.exists() and not target.with_suffix('.report.json').exists()


def test_p1_5_random_mix_names_only_offenders(tmp_path):
    """Brute-force probe: a random clean/dirty mix reports exactly the dirty names and channels."""
    core = _core()
    rng = random.Random(731)
    seen = 0
    for trial in range(16):
        count = rng.randint(2, 5)
        objects = []
        for index in range(count):
            name = f't{trial}_o{index}'
            objects.append(_triangle(name, handle=index + 1, z=float(index) * 4.0 + float(trial) * 40.0))
        chosen = set(rng.sample(range(count), rng.randint(1, count - 1)))
        expected = {}
        for index in chosen:
            extra = sorted(rng.sample(range(2, 12), rng.randint(1, 3)))
            name = objects[index]['name']
            objects[index]['hygiene'] = _dirty_hygiene(name, [1, *extra])
            expected[name] = extra
        dest = tmp_path / f'mix-{trial}.fbx'
        preview = core.dry_run(_scene(*objects), dest, tmp_path / f'mix-{trial}.json')
        assert preview['plan']['stopped'] == 'cleanup', trial
        got = {row['name']: row['findings'][0]['ids'] for row in preview['objects'] if row['findings']}
        assert got == expected, (trial, got, expected)
        for row in preview['objects']:
            if row['findings']:
                assert row['findings'][0]['detail'] == row['name']
        assert not dest.exists()
        seen += 1
    assert seen == 16


def _poison(obj):
    obj['texel'] = {'profile': 'nope'}
    return obj


def _good_texel(obj, map_px=2048):
    faces = []
    xyz = [tuple(point) for point in obj['vertices']]
    uv = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    for index, face in enumerate(obj['faces'], 1):
        faces.append({
            'id': str(index), 'mesh': obj['name'], 'material': 'brick',
            'xyz': [xyz[corner] for corner in face], 'uv': uv,
        })
    return {'profile': 'VPM', 'materials': [{'name': 'brick', 'map_px': map_px}], 'faces': faces}


def _gate_scene(flags):
    """One render mesh plus a UCX piece. flags is (cleanup, matid, xview, ucx)."""
    cleanup, matid, xview, ucx_fail = flags
    name = 'SM_gate_probe'
    obj = _triangle(name, handle=11, material_id=1001 if matid and not xview else 1)
    if xview:
        obj['vertices'] = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0],
                           [0.0, 0.0, 0.002], [1.0, 0.0, 0.002], [0.0, 1.0, 0.002]]
        obj['faces'] = [[0, 1, 2], [3, 4, 5]]
        obj['material_ids'] = [1001, 1001] if matid else [1, 1]
    if cleanup:
        obj['hygiene'] = _dirty_hygiene(name, (1, 2))
    _poison(obj)
    if ucx_fail:
        pieces = [
            _ucx('UCX_SM_Addr_Main_001', (0.0, 0.0, 0.0), (1.0, 1.0, 1.0), handle=21),
            _ucx('UCX_SM_Addr_Main_002', (0.2, 0.0, 0.0), (1.2, 1.0, 1.0), handle=22),
        ]
    else:
        pieces = [_ucx('UCX_SM_Addr_Main_001', (3.0, 0.0, 0.0), (4.0, 1.0, 1.0), handle=21)]
    return _scene(obj, ucx=pieces)


def test_texel_callable_waits_until_earlier_gates_pass(tmp_path):
    """Brute force: every combination of earlier gate failures must not call texel.

    A clean scene calls it once and uses the returned payload. An occupied path
    is not an earlier gate, so texel still runs and then the path is refused.
    """
    core = _core()
    order = ('cleanup', 'matid', 'xview', 'ucx')
    calls = []

    def spy(objects):
        calls.append(tuple(obj['name'] for obj in objects))
        return {obj['name']: _good_texel(obj) for obj in objects}

    seen = 0
    for index, flags in enumerate(itertools.product((False, True), repeat=4)):
        scene = _gate_scene(flags)
        target = tmp_path / f'order-{index}.fbx'
        source = tmp_path / f'order-{index}.json'
        source.write_text('{}\n', encoding='utf-8')
        before = source.read_bytes()
        calls.clear()
        failed = [name for name, flag in zip(order, flags) if flag]
        if failed:
            preview = core.dry_run(scene, target, source, texel_fn=spy)
            assert preview['status'] == 'fail', flags
            assert preview['plan']['stopped'] == failed[0], flags
            assert all(gate['name'] != 'texel' for gate in preview['plan']['gates'])
            assert calls == [], flags
            with pytest.raises(ValueError, match=failed[0]):
                core.commit(scene, target, source, preview, texel_fn=spy)
            assert calls == [], flags
            assert not target.exists()
            assert not target.with_suffix('.report.json').exists()
            assert not Path(str(target) + '.partial').exists()
        else:
            preview = core.dry_run(scene, target, source, texel_fn=spy)
            assert preview['status'] == 'pass', preview
            assert [gate['name'] for gate in preview['plan']['gates']] == ['cleanup', 'matid', 'xview', 'ucx', 'texel']
            assert calls == [('SM_gate_probe',)]
            assert preview['plan']['texel']['meshes'][0]['min_px_per_m'] == 2048.0
            assert not target.exists()
        assert source.read_bytes() == before
        seen += 1
    assert seen == 16

    missing = _poison(_triangle('SM_missing_material', handle=31))
    missing['material'] = None
    held = []

    def blocked(_objects):
        held.append(1)
        raise AssertionError('texel ran before matid')

    target = tmp_path / 'missing.fbx'
    source = tmp_path / 'missing.json'
    source.write_text('{}\n', encoding='utf-8')
    before = source.read_bytes()
    preview = core.dry_run(_scene(missing), target, source, texel_fn=blocked)
    assert held == []
    assert preview['status'] == 'fail' and preview['plan']['stopped'] == 'matid'
    assert preview['objects'][0]['findings'] == [
        {'code': 'missing_material', 'ids': [1], 'detail': 'SM_missing_material'}]
    assert [gate['name'] for gate in preview['plan']['gates']] == ['cleanup', 'matid']
    with pytest.raises(ValueError, match='matid'):
        core.commit(_scene(missing), target, source, preview, texel_fn=blocked)
    assert held == []
    assert not target.exists() and source.read_bytes() == before

    udim = _poison(_triangle('SM_bad_matid_missing_texel', handle=32, material_id=1001))
    preview = core.dry_run(_scene(udim), tmp_path / 'udim.fbx', tmp_path / 'udim.json', texel_fn=blocked)
    assert held == []
    assert preview['plan']['stopped'] == 'matid'
    assert {'code': 'udim_id', 'ids': [1], 'detail': 'SM_bad_matid_missing_texel'} in preview['objects'][0]['findings']
    assert all(gate['name'] != 'texel' for gate in preview['plan']['gates'])
    assert not (tmp_path / 'udim.fbx').exists()

    calls.clear()
    occupied = tmp_path / 'occupied.fbx'
    occupied.write_bytes(b'keep')
    clean = _gate_scene((False, False, False, False))
    refused = core.dry_run(clean, occupied, tmp_path / 'occupied.json', texel_fn=spy)
    assert len(calls) == 1
    assert refused['status'] == 'fail' and refused['plan']['stopped'] == 'path'
    assert any(gate['name'] == 'texel' for gate in refused['plan']['gates'])
    assert occupied.read_bytes() == b'keep'

    calls.clear()
    deferred = core.dry_run(clean, tmp_path / 'defer.fbx', tmp_path / 'defer.json', texel_fn=spy, defer_texel=True)
    assert calls == []
    assert [gate['name'] for gate in deferred['plan']['gates']] == ['cleanup', 'matid', 'xview', 'ucx']
    assert deferred['plan']['texel'] is None
    assert not (tmp_path / 'defer.fbx').exists()
