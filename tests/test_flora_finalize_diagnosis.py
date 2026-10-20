"""User-approved source limitations must not become asset passes (#369)."""
import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/flora'))
import compare_sprite_diagnostics as raw


def fixture_rows():
    controls = ['Tilia_cordata_VPM', 'Crataegus_mollis_VPM', 'Spiraea_japonica_NPM']
    names = controls + [f'Plant{i}_VPM' for i in range(96)]
    rows = []
    for tag in ('original', 'ours'):
        for name in names:
            rows.append({'object': name, 'tag': tag, 'profile': name.rsplit('_', 1)[1],
                         'triangles': 1, 'islands': [{'island': 0, 'faces': [0],
                         'role': 'star_plane' if name.endswith('NPM') else 'foliage',
                         'score': .9 if name.endswith('NPM') else 1.0,
                         'neighbour_opaque_px': 0, 'clipped_opaque_px_tolerance_1': 0,
                         'pass': tag == 'original', 'policy_applicable': True}]})
    rows.extend({**copy.deepcopy(rows[99+i]), 'tag': 'light'} for i in range(3))
    return rows


def test_source_crop_is_routed_not_waived_after_control_calibration():
    import finalize_texture_diagnosis as final
    rows = fixture_rows()
    crop = rows[3]['islands'][0]
    crop.update(score=.675942243645, **{'pass': False}, clipped_opaque_px_tolerance_1=29353)
    result = final.finalize(rows, {})
    assert result['control_calibration'] == 'passed'
    assert result['asset_accepted'] is False and result['raw_all_originals_gate'] == 'failed'
    assert result['route_count'] == 99 and result['source_limited_objects'] == 1
    route = next(r for r in result['routes'] if r['object'] == 'Plant0_VPM')
    assert route['route'] == 'repair_source_uv_then_restore_or_bake_atlas'
    assert route['source_issues'][0]['score'] == crop['score']
    assert route['source_issues'][0]['clipped_opaque_px_tolerance_1'] == 29353
    assert crop['pass'] is False  # no mutation or promotion


@pytest.mark.parametrize('index,fields', [(0, {'score': .799999}),
    (0, {'score': 1.0, 'neighbour_opaque_px': 1}),
    (2, {'score': .9, 'clipped_opaque_px_tolerance_1': 1})])
def test_declared_control_pass_cannot_override_bad_numerical_evidence(index, fields):
    import finalize_texture_diagnosis as final
    rows = fixture_rows(); rows[index]['islands'][0].update(fields)
    with pytest.raises(ValueError, match='control calibration failed'):
        final.finalize(rows, {})


@pytest.mark.parametrize('score,neighbours,expected', [(.8, 0, True), (.95, 1, True),
    (.950001, 1, False), (1.0, 0, True)])
def test_vpm_control_boundary(score, neighbours, expected):
    import finalize_texture_diagnosis as final
    rows = fixture_rows(); rows[0]['islands'][0].update(score=score, neighbour_opaque_px=neighbours)
    if expected: assert final.finalize(rows, {})['control_calibration'] == 'passed'
    else:
        with pytest.raises(ValueError): final.finalize(rows, {})


@pytest.mark.parametrize('change', ['failed', 'unknown', 'review', 'not_measured', 'unsupported', '', 'missing', 'nan', 'inf', 'bool'])
def test_controls_fail_closed(change):
    import finalize_texture_diagnosis as final
    rows = fixture_rows()
    island = rows[0]['islands'][0]
    if change == 'missing': rows.pop(0)
    elif change in ('nan', 'inf'): island['score'] = float(change)
    elif change == 'bool': island['score'] = True
    else: island['status'] = change
    with pytest.raises(ValueError): final.finalize(rows, {})


@pytest.mark.parametrize('kind', ['empty', 'partial', 'duplicate', 'missing_face', 'extra_face', 'unknown_tag'])
def test_inventory_and_ledgers_fail_closed(kind):
    import finalize_texture_diagnosis as final
    rows = fixture_rows()
    if kind == 'empty': rows = []
    elif kind == 'partial': rows.pop()
    elif kind == 'duplicate': rows[-1] = copy.deepcopy(rows[-2])
    elif kind == 'missing_face': rows[3]['islands'][0]['faces'] = []
    elif kind == 'extra_face': rows[3]['islands'][0]['faces'] = [0, 0]
    else: rows[3]['tag'] = 'unsupported'
    with pytest.raises(ValueError): final.finalize(rows, {})


def test_unknown_source_is_a_named_limitation_not_a_proven_crop():
    import finalize_texture_diagnosis as final
    rows = fixture_rows()
    island = rows[3]['islands'][0]
    island.pop('score')
    island.update(status='unknown', error='ambiguous or missing source bark strip', **{'pass': False})
    result = final.finalize(rows, {})
    route = next(r for r in result['routes'] if r['object'] == 'Plant0_VPM')
    assert route['route'] == 'resolve_source_atlas_region_then_restore_or_bake'
    assert route['source_issues'][0]['kind'] == 'measurement_limitation'
    assert route['source_issues'][0]['error'] == island['error']
    assert result['asset_accepted'] is False


def test_npm_nonstar_and_failed_star_have_explicit_rebuild_routes():
    import finalize_texture_diagnosis as final
    rows = fixture_rows()
    name = rows[3]['object']
    for row in rows:
        if row['object'] == name:
            row['object'] = 'Plant0_NPM'; row['profile'] = 'NPM'
    result = final.finalize(rows, {})
    assert next(r for r in result['routes'] if r['object'] == 'Plant0_NPM')['route'] == 'rebuild_whole_plant_star_and_uv'
    assert len(result['routes']) == len({r['object'] for r in result['routes']}) == 99
    assert raw.source_unresolved(rows[3]) is False


def bundle(tmp_path):
    import hashlib
    rows = fixture_rows()
    inventory = {'failures': [], 'scenes': {tag: {'records': {}} for tag in ('original', 'florio', 'ours')}, 'light': {}}
    for row in rows:
        record = {'triangles': row['triangles']}
        if row['tag'] == 'light': inventory['light'][row['object']+'_light'] = record
        else: inventory['scenes'][row['tag']]['records'][row['object']] = record
    metrics = tmp_path/'metrics.json'; inv = tmp_path/'inventory.json'; provenance = tmp_path/'provenance.json'
    metrics.write_text(json.dumps({'records': rows}), encoding='utf-8')
    inv.write_text(json.dumps(inventory), encoding='utf-8')
    provenance.write_text(json.dumps({'outputs': {'metrics.json': hashlib.sha256(metrics.read_bytes()).hexdigest()},
                                    'inventory_sha256': hashlib.sha256(inv.read_bytes()).hexdigest()}), encoding='utf-8')
    return metrics, inv, provenance


def test_fresh_process_cli_and_stale_or_aliased_inputs(tmp_path):
    import subprocess
    import finalize_texture_diagnosis as final
    metrics, inv, provenance = bundle(tmp_path)
    before = [p.read_bytes() for p in (metrics, inv, provenance)]
    output = tmp_path/'out'
    command = [sys.executable, str(Path(final.__file__)), '--metrics', str(metrics), '--inventory', str(inv),
               '--provenance', str(provenance), '--output']
    completed = subprocess.run([*command, str(output)], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert json.loads((output/'routes.json').read_text())['route_count'] == 99
    assert 'НЕ приняты' in (output/'index.html').read_text(encoding='utf-8')
    for target in (metrics, tmp_path/'.'/'inventory.json', provenance):
        rejected = subprocess.run([*command, str(target)], capture_output=True, text=True)
        assert rejected.returncode != 0
    alias = tmp_path/'alias'; alias.hardlink_to(metrics)
    with pytest.raises(ValueError, match='alias'): final.run(metrics, inv, provenance, alias)
    assert [p.read_bytes() for p in (metrics, inv, provenance)] == before
    metrics.write_bytes(before[0]+b' ')
    with pytest.raises(ValueError, match='stale'): final.run(metrics, inv, provenance, tmp_path/'stale')
    assert not (tmp_path/'stale').exists()


def test_duplicate_json_key_rejected_and_changed_input_writes_nothing(tmp_path, monkeypatch):
    import finalize_texture_diagnosis as final
    with pytest.raises(ValueError, match='duplicate JSON key records'):
        final.read_json('{"records": [], "records": []}')
    metrics, inv, provenance = bundle(tmp_path)
    real = final.finalize
    def rewrite(*args):
        result = real(*args)
        metrics.write_bytes(metrics.read_bytes()+b' ')
        return result
    monkeypatch.setattr(final, 'finalize', rewrite)
    with pytest.raises(ValueError, match='input changed'):
        final.run(metrics, inv, provenance, tmp_path/'changed')
    assert not (tmp_path/'changed').exists()


def test_source_nan_is_not_reported_as_a_physical_defect():
    import finalize_texture_diagnosis as final
    rows = fixture_rows(); rows[3]['islands'][0].update(score=float('nan'), **{'pass': False})
    result = final.finalize(rows, {})
    issue = next(r for r in result['routes'] if r['object'] == 'Plant0_VPM')['source_issues'][0]
    assert issue['kind'] == 'measurement_limitation' and issue['score'] is None
    json.dumps(result, allow_nan=False)
