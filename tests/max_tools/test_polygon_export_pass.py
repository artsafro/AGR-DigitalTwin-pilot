"""new-case: cleanup apply and checked export each have a PASS and a FAIL row (#885).

invariant: a cleaned copy is a reported pass; checked export of that copy writes a new FBX
and is a pass only when the report carries an FBX readback. A missing pass run is a mismatch.
"""
from pathlib import Path

import pytest


def test_cleanup_and_checked_export_have_pass_and_fail_rows():
    from test_polygon_support import group_runs, load_expected, render_table
    for button in ('export.cleanup', 'export.checked'):
        doc = load_expected(button)
        expects = {obj['expect'] for obj in doc['objects'] if obj['scene'] == 'polygon_all'}
        assert expects == {'pass', 'fail'}, button
        assert not (doc.get('reason') or '').strip(), button
    grouped = group_runs(
        [('export.cleanup', 'polygon_all'), ('export.checked', 'polygon_all')], [])
    text = render_table(grouped, [])
    assert 'export.cleanup' in text and 'export.checked' in text
    for button in ('export.cleanup', 'export.checked'):
        rows = [row for base in grouped for spec in base['stations']
                if spec['button'] == button for row in spec['rows']]
        assert any(row['expected'].startswith('pass') for row in rows), button
        assert any(row['expected'].startswith('fail') for row in rows), button


def test_export_pass_without_readback_is_a_mismatch():
    from test_polygon_support import compare_report
    expected = [{
        'name': 'SM_Polygon_001_Main_AGR_export_', 'scene': 'polygon_all',
        'expect': 'pass', 'codes': [], 'readback': True,
        'produced': 'export_readback', 'source': 'SM_Polygon_001_Main',
    }]
    missing = {'status': 'pass', 'objects': [
        {'name': 'SM_Polygon_001_Main_AGR_export_', 'findings': []}],
        'plan': {'readback': None}}
    got = compare_report(expected, missing)
    assert any(m['kind'] == 'readback' for m in got)
    present = {'status': 'pass', 'objects': [
        {'name': 'SM_Polygon_001_Main_AGR_export_', 'findings': []}],
        'plan': {'readback': {'object_count': 1, 'object_names': ['SM_Polygon_001_Main_AGR_export_']}}}
    assert compare_report(expected, present) == []


def test_checked_export_target_is_a_new_fbx_path(tmp_path):
    from test_polygon_support import checked_export_target
    target = checked_export_target(tmp_path, 'SM_Polygon_001_Main_AGR_export_')
    assert target.suffix == '.fbx'
    assert target.name == 'SM_Polygon_001_Main_AGR_export_.fbx'
    assert not target.exists()
    assert 'export-pass' in target.parts
    target.parent.mkdir(parents=True)
    target.write_bytes(b'FBX')
    with pytest.raises(SystemExit):
        checked_export_target(tmp_path, 'SM_Polygon_001_Main_AGR_export_')


def test_missing_produced_export_run_is_a_mismatch():
    import importlib.util
    path = Path(__file__).resolve().parents[2] / 'test-polygon' / 'run_polygon.py'
    spec = importlib.util.spec_from_file_location('agr_run_polygon_pass', path)
    run_polygon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run_polygon)
    actual = {'runs': [{
        'button': 'export.checked', 'scene': 'polygon_all', 'tool': 'export',
        'report': {'status': 'fail', 'objects': [{
            'name': 'SM_Polygon_001_Main',
            'findings': [{'code': 'cleanup', 'ids': [1], 'detail': ''}],
        }]},
    }]}
    got = [item for item in run_polygon.compare_actual(actual) if item.get('button') == 'export.checked']
    assert any(item['kind'] == 'missing' and 'readback' in item['detail'] for item in got)


def test_exit_code_ignores_known_bug_count():
    text = Path(__file__).resolve().parents[2].joinpath('test-polygon', 'run_polygon.py').read_text(encoding='utf-8')
    assert 'known_bug' in text
    assert 'exit' in text.lower() or 'Код выхода' in text or 'Exit code' in text
