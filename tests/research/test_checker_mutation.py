"""new-case: fail-closed exact-oracle mutation research contract (#1261)."""
import copy
import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[2] / 'tools/research/checker_mutation_guard.py'


def load():
    spec = importlib.util.spec_from_file_location('checker_mutation_guard', PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def finding(status='pass', code='V004/topology defects'):
    return {'code': code, 'status': status, 'observed': '0 defects'}


def test_exact_oracle():
    g = load()
    oracle = {'etalon': [finding()]}
    assert g.guard(oracle, copy.deepcopy(oracle)) is True


@pytest.mark.parametrize('changed', [[], [finding('review')], [finding('fail')], [finding('not_run')],
                                      [finding(code='V003/object types')]])
def test_guard_rejects_changes(changed):
    g = load()
    with pytest.raises(ValueError):
        g.guard({'etalon': [finding()]}, {'etalon': changed})
    with pytest.raises(ValueError):
        g.guard({'etalon': [finding('fail')]}, {'etalon': [finding()]})


def test_score_requires_expected_new_finding():
    g = load()
    clean = [finding()]
    assert g.caught(clean, [finding('fail')], ['V004/topology defects'])
    assert not g.caught(clean, [finding('fail')], ['V012/mesh names'])
    assert not g.caught([finding('fail')], [finding('fail')], ['V004/topology defects'])
    assert not g.caught(clean, [finding('not_run')], ['V004/topology defects'])


@pytest.mark.parametrize('bad', [[], {}, [finding('unknown')], [dict(finding(), observed=float('nan'))],
                               [{'code': 'V004/x', 'status': 'pass'}], [finding(), finding()]])
def test_invalid_findings(bad):
    with pytest.raises(ValueError):
        load().validate(bad)


def test_identity_and_repeats():
    g = load()
    a = finding()
    b = finding(code='V002/units')
    assert g.guard({'e': [a, b]}, {'e': [b, a]})
    for _ in range(10):
        assert g.caught([a], [finding('review')], [a['code']])


def test_hash_drift(tmp_path):
    g = load()
    p = tmp_path / 'scene.json'
    p.write_text('first')
    expected = g.sha256(p)
    g.verify_files(tmp_path, {'scene.json': expected})
    p.write_text('second')
    with pytest.raises(ValueError, match='hash'):
        g.verify_files(tmp_path, {'scene.json': expected})


def test_cli_aliases(tmp_path):
    import subprocess
    import sys
    p = tmp_path / 'oracle.json'
    p.write_text('{"e": [{"code": "V004/x", "status": "pass", "observed": "ok"}]}')
    before = p.read_bytes()
    result = subprocess.run([sys.executable, str(PATH), str(p), str(p), '--output', str(p)], capture_output=True)
    assert result.returncode != 0
    assert p.read_bytes() == before


def test_new_check_must_pass_every_etalon():
    g = load()
    before = {'e': [finding()]}
    new = finding(code='V005/new rule')
    assert g.guard(before, {'e': [finding(), new]})
    for status in ['review', 'fail', 'not_run']:
        with pytest.raises(ValueError):
            g.guard(before, {'e': [finding(), dict(new, status=status)]})


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '-Infinity'])
def test_nonfinite_json_is_rejected(tmp_path, value):
    p = tmp_path / 'oracle.json'
    p.write_text('{"x": '+value+'}')
    with pytest.raises(ValueError):
        load().read(p)


def test_duplicate_json_key_is_rejected(tmp_path):
    p = tmp_path / 'oracle.json'
    p.write_text('{"e": [], "e": []}')
    with pytest.raises(ValueError, match='duplicate key'):
        load().read(p)


def test_manifest_escape_and_aliases(tmp_path):
    g = load()
    p = tmp_path / 'scene.json'
    p.write_text('source')
    digest = g.sha256(p)
    with pytest.raises(ValueError):
        g.verify_files(tmp_path, {'scene.json': digest, './scene.json': digest})
    with pytest.raises(ValueError):
        g.verify_files(tmp_path, {'../scene.json': digest})


def test_fresh_process_cli_and_existing_output(tmp_path):
    import json
    import subprocess
    import sys
    a, b, out = [tmp_path / n for n in ['a.json', 'b.json', 'result.json']]
    a.write_text(json.dumps({'e': [finding()]}))
    b.write_bytes(a.read_bytes())
    cmd = [sys.executable, str(PATH), str(a), str(b), '--output', str(out)]
    first = subprocess.run(cmd, capture_output=True)
    assert first.returncode == 0, first.stderr
    assert json.loads(out.read_text()) == {'guard': 'PASS', 'new_false_alarms': 0}
    before = out.read_bytes()
    assert subprocess.run(cmd, capture_output=True).returncode != 0
    assert out.read_bytes() == before
    assert a.read_bytes() == b.read_bytes()


def test_generated_status_transition_probe():
    g = load()
    statuses = ['pass', 'fail', 'review', 'not_run']
    for old in statuses:
        for new in statuses:
            before, after = {'e': [finding(old)]}, {'e': [finding(new)]}
            if old == new:
                assert g.guard(before, after)
            else:
                with pytest.raises(ValueError):
                    g.guard(before, after)


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _driver():
    return _module('mutation_driver', PATH.with_name('checker_mutation.py'))


def _binary_fixture(version=7400, unit=100):
    helper = _module('mutation_binary_fixture', PATH.parents[2] / 'tests/qa/test_fbx_units.py')
    return helper.fbx_bytes(version, unit, original=unit)


@pytest.mark.parametrize('version', [7400, 7500])
@pytest.mark.parametrize('unit', [1, 100])
def test_units_generator_changes_only_selected_double(version, unit):
    from twinqa.fbx_header import fbx_units
    data = _binary_fixture(version, unit)
    changed = _driver().mutate_units(data, unit / 2)
    assert changed != data and len(changed) == len(data)
    assert fbx_units(changed)['unit_scale_factor'] == unit / 2
    assert fbx_units(changed)['original_unit_scale_factor'] == unit
    assert fbx_units(data)['unit_scale_factor'] == unit


@pytest.mark.parametrize('data', [b'', b'; FBX ASCII unsupported'])
def test_units_generator_rejects_unsupported(data):
    with pytest.raises(ValueError, match='unsupported'):
        _driver().mutate_units(data, 50)


def test_manifest_rejects_hardlinked_input(tmp_path):
    import os
    a, b = tmp_path/'a.json', tmp_path/'b.json'
    a.write_text('synthetic source')
    os.link(a, b)
    g = load()
    with pytest.raises(ValueError, match='duplicate physical'):
        g.verify_files(tmp_path, {'a.json': g.sha256(a), 'b.json': g.sha256(b)})


def _synthetic_corpus(tmp_path):
    """Synthetic raw-scene contract fixture, never represented as a real etalon."""
    import json
    driver, g = _driver(), load()
    run = tmp_path/'run'
    root = run/'corpus'
    folder = root/'synthetic'
    scenes = folder/'scenes'
    scenes.mkdir(parents=True)
    source = folder/'SM_Test_K_1.fbx'
    source.write_bytes(_binary_fixture())
    mesh = {'name': 'SM_Test_K_1_Main', 'triangles': 12, 'polygon_degrees': {'3': 12},
            'rotation_euler_deg': [0,0,0], 'scale': [1,1,1], 'location': [0,0,0],
            'uv_channels': 1, 'mirrored_uv_triangles': 0, 'udim_tiles': [1001], 'materials': [],
            'topology': {k: 0 for k in ['duplicate_vertices','duplicate_edges','duplicate_polygons',
                         'self_intersections','isolated_vertices','isolated_edges','isolated_polygons',
                         'zero_length_edges','duplicates_and_self_intersections']}}
    mesh['topology']['tol_m'] = .002
    clean = {'source': source.as_posix(), 'readback_ok': True, 'meshes': [mesh],
             'other_objects': [], 'images': [], 'scope': 'synthetic test fixture'}
    (scenes/'clean.json').write_text(json.dumps(clean))
    mutant = copy.deepcopy(clean)
    mutant['meshes'][0]['name'] = 'Broken_agent_name'
    (scenes/'wrong_name.json').write_text(json.dumps(mutant))
    (scenes/'operations.json').write_text(json.dumps({'operations': [
        {'class': 'wrong_name', 'status': 'generated', 'expected': ['V012/mesh names']}]}))
    manifest = {'schema': 1, 'sealed': True, 'seed': 1261,
                'generator_sha256': g.sha256(driver.GENERATOR), 'guard_sha256': g.sha256(driver.GUARD),
                'runner_sha256': g.sha256(PATH.with_name('checker_mutation.py')),
                'etalons': [{'id': 'synthetic', 'source_name': source.name, 'kind': 'vpm', 'role': 'oks'}],
                'files': {p.relative_to(root).as_posix(): g.sha256(p) for p in root.rglob('*') if p.is_file()}}
    (root/'manifest.json').write_text(json.dumps(manifest))
    result = driver.evaluate(root, manifest)
    (run/'baseline.json').write_text(json.dumps(result))
    return run, manifest, source


def test_measurement_cache_rejects_stale_receipt(tmp_path):
    import json
    import subprocess
    import sys
    run, manifest, source = _synthetic_corpus(tmp_path)
    g = load()
    cmd = [sys.executable, str(PATH.with_name('checker_mutation_loop.py')), 'metric', '--run', str(run),
           '--manifest-sha256', g.sha256(run/'corpus/manifest.json'),
           '--oracle-sha256', g.sha256(run/'baseline.json')]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['score'] == 1
    receipt = next((run/'cache').glob('*.json'))
    data = json.loads(receipt.read_text())
    data['binding']['fingerprint'] = 'stale'
    receipt.write_text(json.dumps(data))
    cmd[2] = 'guard'
    rejected = subprocess.run(cmd, capture_output=True, text=True)
    assert rejected.returncode != 0 and 'stale cache receipt' in rejected.stderr


def test_state_change_during_read_is_rejected(tmp_path, monkeypatch):
    run, manifest, source = _synthetic_corpus(tmp_path)
    original = Path.read_text
    changed = False
    def race(path, *args, **kwargs):
        nonlocal changed
        data = original(path, *args, **kwargs)
        if path.name == 'clean.json' and not changed:
            source.write_bytes(source.read_bytes() + b'synthetic concurrent edit')
            changed = True
        return data
    monkeypatch.setattr(Path, 'read_text', race)
    with pytest.raises(ValueError, match='hash drift'):
        _driver().evaluate(run/'corpus', manifest)
    assert changed


def test_measurement_output_alias_writes_nothing(tmp_path):
    import subprocess
    import sys
    run, manifest, source = _synthetic_corpus(tmp_path)
    original = source.read_bytes()
    cmd = [sys.executable, str(PATH.with_name('checker_mutation.py')), 'baseline', str(run/'corpus'),
           '--output', str(source), '--manifest-sha256', load().sha256(run/'corpus/manifest.json')]
    result = subprocess.run(cmd, capture_output=True)
    assert result.returncode != 0 and source.read_bytes() == original


def test_duplicate_source_preflight_writes_nothing(tmp_path):
    import json
    import subprocess
    import sys
    source = tmp_path/'source.fbx'
    source.write_bytes(_binary_fixture())
    config, out = tmp_path/'config.json', tmp_path/'output'
    config.write_text(json.dumps({'etalons': [{'id': n, 'source': str(source)} for n in ['a','b']]}))
    result = subprocess.run([sys.executable, str(PATH.with_name('checker_mutation.py')), 'freeze',
                             str(config), str(out)], capture_output=True, text=True)
    assert result.returncode != 0 and 'duplicate source' in result.stderr and not out.exists()


@pytest.fixture
def blender_mutation_source(tmp_path):
    import subprocess
    from twinqa.scene import find_blender
    executable = find_blender()
    if not executable:
        pytest.skip('pinned offline Blender not installed')
    source = tmp_path/'synthetic.fbx'
    expression = ("import bpy;bpy.ops.wm.read_factory_settings(use_empty=True);"
                  "bpy.ops.mesh.primitive_cube_add();bpy.context.object.name='SM_Test_GroundEl';"
                  f"bpy.ops.export_scene.fbx(filepath={str(source)!r},use_triangles=True)")
    base = [executable, '--background', '--factory-startup', '--python-exit-code', '1']
    result = subprocess.run([*base, '--python-expr', expression], capture_output=True, text=True, timeout=90)
    assert result.returncode == 0 and source.is_file(), result.stdout + result.stderr
    return base, source, tmp_path


@pytest.mark.blender
def test_real_blender_generator_is_seeded_and_preserves_source(blender_mutation_source):
    import json
    import subprocess
    base, source, folder = blender_mutation_source
    before = source.read_bytes()
    generator = PATH.with_name('checker_mutation_blender.py')
    outputs = []
    for name in ['first','repeat']:
        out = folder/name
        result = subprocess.run([*base, '--python', str(generator), '--', str(source), str(out),
                                 '--cases', 'unapplied_scale', 'duplicate_faces', 'wrong_name', 'leftover_object'],
                                capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr
        outputs.append({p.name: json.loads(p.read_text(encoding='utf-8')) for p in out.glob('*.json')})
    assert outputs[0] == outputs[1]
    clean, duplicate = outputs[0]['clean.json'], outputs[0]['duplicate_faces.json']
    assert duplicate['meshes'][0]['polygons'] == clean['meshes'][0]['polygons'] + 1
    assert outputs[0]['wrong_name.json']['meshes'][0]['name'] == 'Broken_agent_name'
    assert any(o['name'] == 'Agent_helper_1261' for o in outputs[0]['leftover_object.json']['other_objects'])
    assert source.read_bytes() == before


@pytest.mark.blender
def test_real_blender_generator_rejects_alias_and_unknown_case(blender_mutation_source):
    import subprocess
    base, source, folder = blender_mutation_source
    before = source.read_bytes()
    generator = PATH.with_name('checker_mutation_blender.py')
    for out, case in [(source, 'leftover_object'), (folder/'unsupported', 'unknown_case')]:
        result = subprocess.run([*base, '--python', str(generator), '--', str(source), str(out), '--cases', case],
                                capture_output=True, text=True, timeout=120)
        assert result.returncode != 0
    assert source.read_bytes() == before and not (folder/'unsupported').exists()


def _summary_fixture():
    return {'clean': {'e': [finding('fail')]}, 'score': 0.0, 'caught': 0, 'total': 1,
            'rows': [{'etalon': 'e', 'class': 'flipped_normals', 'status': 'generated',
                      'expected': ['V004/topology defects'], 'findings': [finding('fail')], 'caught': False}]}


def test_issue_metric_counts_expected_alarm_and_reports_incremental_separately():
    summary = _module('mutation_summary', PATH.with_name('checker_mutation_summary.py'))
    result = summary.summarize(_summary_fixture())
    assert (result['caught'], result['score']) == (1, 1.0)
    assert (result['incremental_caught'], result['incremental_score']) == (0, 0.0)
    data = _summary_fixture()
    data['rows'][0]['findings'] = [finding('fail', 'V003/object types')]
    assert summary.summarize(data)['caught'] == 0


@pytest.mark.parametrize('change', ['empty', 'duplicate', 'unknown_class', 'stale_total', 'nonfinite', 'unknown_code', 'unknown_key'])
def test_issue_metric_aggregator_is_fail_closed(change):
    summary = _module('mutation_summary', PATH.with_name('checker_mutation_summary.py'))
    data = _summary_fixture()
    if change == 'empty':
        data['rows'] = []
    elif change == 'duplicate':
        data['rows'].append(copy.deepcopy(data['rows'][0]))
    elif change == 'unknown_class':
        data['rows'][0]['class'] = 'unmapped class'
    elif change == 'nonfinite':
        data['score'] = float('nan')
    elif change == 'unknown_code':
        data['rows'][0]['expected'] = ['V999/unmapped']
    elif change == 'unknown_key':
        data['unmapped key'] = 1
    else:
        data['total'] = 3
    with pytest.raises(ValueError):
        summary.summarize(data)


def test_issue_metric_cli_alias_does_not_touch_input(tmp_path):
    import json
    import subprocess
    import sys
    a, b = tmp_path/'a.json', tmp_path/'b.json'
    a.write_text(json.dumps(_summary_fixture()))
    b.write_bytes(a.read_bytes())
    before = a.read_bytes()
    result = subprocess.run([sys.executable, str(PATH.with_name('checker_mutation_summary.py')),
                             str(a), str(b), '--output', str(a)], capture_output=True)
    assert result.returncode != 0 and a.read_bytes() == before


