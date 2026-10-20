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
                         'score': 1.0, 'pass': tag == 'original', 'policy_applicable': True}]})
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


@pytest.mark.parametrize('change', ['failed', 'unknown', 'review', 'missing', 'nan', 'inf', 'bool'])
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


def test_source_nan_is_not_reported_as_a_physical_defect():
    import finalize_texture_diagnosis as final
    rows = fixture_rows(); rows[3]['islands'][0].update(score=float('nan'), **{'pass': False})
    result = final.finalize(rows, {})
    issue = next(r for r in result['routes'] if r['object'] == 'Plant0_VPM')['source_issues'][0]
    assert issue['kind'] == 'measurement_limitation' and issue['score'] is None
    json.dumps(result, allow_nan=False)
