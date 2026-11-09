"""new-case: the AGR Tools test polygon expected/ files cover every suite button (#885)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / 'docs/plans/agr-tools-suite.json'
POLY = ROOT / 'test-polygon'
EXPECTED = POLY / 'expected'


def test_expected_directory_and_catalog_exist():
    assert EXPECTED.is_dir()
    assert (POLY / 'catalog.json').is_file()
    assert (POLY / 'README.md').is_file()


def test_every_suite_button_has_pass_and_fail_or_a_reason():
    from test_polygon_support import load_expected, suite_rows
    rows = suite_rows()
    assert rows, 'suite has no buttons'
    for row in rows:
        doc = load_expected(row['id'])
        assert doc['button'] == row['id']
        assert doc['version'] == row['version']
        assert doc['schema'] == 1
        passes = [o for o in doc['objects'] if o['expect'] == 'pass']
        fails = [o for o in doc['objects'] if o['expect'] == 'fail']
        if passes and fails:
            continue
        assert isinstance(doc.get('reason'), str) and doc['reason'].strip(), row['id']


def test_shipped_actions_map_onto_a_suite_row():
    from test_polygon_support import ACTION_ROW, load_expected, suite_rows
    ids = {r['id'] for r in suite_rows()}
    for action, row_id in ACTION_ROW.items():
        assert row_id in ids, action
        doc = load_expected(row_id)
        assert doc['shipped'] is True
        assert doc['tool'] in (action, doc['tool'])


def _catalog():
    """The builder input: polygon + #979 station fragments (polygon_core.load_catalog), not only catalog.json."""
    from test_polygon_support import load_catalog
    return load_catalog()


def test_catalog_has_the_required_kinds():
    catalog = _catalog()
    roles = {o['role'] for o in catalog['objects']}
    for role in ('Main', 'MainGlass', 'Ground', 'GroundEl', 'Flora', 'UCX', 'camera', 'light', 'shape', 'helper'):
        assert role in roles, role
    for obj in catalog['objects']:
        assert 'AGR_TEST' in obj and obj['AGR_TEST']
        assert obj['scene'] in ('polygon_all', 'cm_units', 'empty', 'vpm', 'atlas_npm') or (  # atlas_npm: 0.9.0 R
            obj.get('fragment') and obj['scene'].startswith('frag_' + obj['fragment'].lower() + '_'))


def test_committed_catalog_is_the_snapshot_of_bases_01_to_07():
    """catalog.json is R's snapshot: a branch of #979 adds a fragment and never rewrites it, so only the rows of the
    bases 0.8 / 0.9 may differ from load_catalog(); the bases 0.1-0.7 stay byte-for-byte the generated ones."""
    from test_polygon_support import fragment_part
    committed = json.loads((POLY / 'catalog.json').read_text(encoding='utf-8'))
    generated = _catalog()
    assert [o for o in committed['objects'] if not fragment_part(o)] ==         [o for o in generated['objects'] if not fragment_part(o)]
    assert {k: v for k, v in committed.items() if k != 'objects'} == {
        k: v for k, v in generated.items() if k != 'objects'}


def test_variant_scene_specs_exist():
    for name in ('cm_units.json', 'empty.json', 'vpm.json', 'atlas_npm.json'):
        doc = json.loads((POLY / 'scenes' / name).read_text(encoding='utf-8'))
        assert doc['scene'] == name[:-5]
        assert doc['synthetic'] is True


def test_bases_stations_and_button_versions():
    """Every tour button has a unique station on a base; the version is the suite JSON."""
    from test_polygon_support import bases, load_expected, stations, suite_rows
    built = bases()
    built_ids = [item['version'] for item in built]
    assert built_ids == ['0.1', '0.2', '0.3', '0.4', '0.5', '0.6', '0.7', '0.8', '0.9', '1.0', '1.1']
    colours = [tuple(item['colour']) for item in built]
    assert len(colours) == len(set(colours))
    placed = stations()
    ids = [item['id'] for item in placed]
    assert len(ids) == len(set(ids))
    known = {item['version'] for item in built}
    version_of = {row['id']: row['version'] for row in suite_rows()}
    seen = {}
    for item in placed:
        assert item['base'] in known
        assert item['version'] == item['base']
        assert version_of[item['button']] == item['version']
        assert item['id'].startswith(item['version'] + '.')
        seen.setdefault(item['button'], []).append(item)
    for base in built:
        for button in base['buttons']:
            owned = seen.get(button, [])
            assert owned, button
            assert all(item['version'] == base['version'] for item in owned)
            doc = load_expected(button)
            assert doc['version'] == version_of[button]
            assert doc['base'] == base['version']
            assert doc['station'] in ids
            assert doc['stations']
            passes = [obj for obj in doc['objects'] if obj['expect'] == 'pass']
            fails = [obj for obj in doc['objects'] if obj['expect'] == 'fail']
            if not (passes and fails):
                assert isinstance(doc.get('reason'), str) and doc['reason'].strip(), button
    for row in suite_rows():
        if row['version'] in known:
            continue
        doc = load_expected(row['id'])
        assert doc['version'] == row['version']
        assert doc['base'] is None
        assert doc['stations'] == []
        assert isinstance(doc.get('reason'), str) and doc['reason'].strip()


def test_fixtures_are_excluded_and_no_check_names_them():
    import json
    from test_polygon_support import compare_report, excluded_name, predict_all
    docs = predict_all()
    blob = json.dumps(docs)
    assert '_base_' not in blob
    assert '_label_' not in blob
    catalog = _catalog()
    fixtures = [obj for obj in catalog['objects'] if excluded_name(obj['name'])]
    assert fixtures
    assert any(obj['layer'] == '_bases' and obj['name'].startswith('_base_') for obj in fixtures)
    assert any(obj['layer'] == '_labels' and obj['name'].startswith('_label_') for obj in fixtures)
    assert all(obj['AGR_TEST'] == 'fixture' for obj in fixtures)
    report = {'status': 'pass', 'objects': [
        {'name': '_base_0_1', 'findings': [{'code': 'name_prefix', 'ids': [], 'detail': ''}]},
        {'name': '_label_0_1_1', 'findings': [{'code': 'hyg_non_mesh', 'ids': [], 'detail': ''}]},
        {'name': '_cam_База 0.1', 'findings': [{'code': 'hyg_non_mesh', 'ids': [], 'detail': ''}]},
        {'name': '_cam_База 0.1.Target', 'findings': [{'code': 'hyg_non_mesh', 'ids': [], 'detail': ''}]},
        {'name': 'A', 'findings': []},
    ]}
    got = compare_report(
        [{'name': 'A', 'scene': 'polygon_all', 'expect': 'pass', 'codes': []}], report)
    assert got == []
    assert '_base_' not in json.dumps(got) and '_label_' not in json.dumps(got) and '_cam_' not in json.dumps(got)


def test_report_groups_rows_by_base_and_station():
    from test_polygon_support import group_runs, render_table
    grouped = group_runs([('qa.matid', 'polygon_all')], [])
    versions = [item['version'] for item in grouped]
    assert versions[:3] == ['0.1', '0.2', '0.3']
    first = grouped[0]['stations'][0]
    assert first['id'] == '0.1.1'
    assert first['button'] == 'qa.matid'
    assert any(row['name'] == 'SM_Polygon_001_Main' and row['ok'] for row in first['rows'])
    text = render_table(grouped, [])
    assert text.index('База 0.1') < text.index('База 0.2') < text.index('База 0.7')
    assert '0.1.1' in text and 'qa.matid' in text


def test_catalog_station_ids_and_base_layers():
    catalog = _catalog()
    from test_polygon_support import excluded_name, stations
    known = {item['id'] for item in stations()}
    for obj in catalog['objects']:
        if excluded_name(obj['name']) or obj['scene'] != 'polygon_all':
            continue
        if obj['scene'] == 'polygon_all' and obj.get('station'):
            assert obj['station'] in known, obj['name']
            assert ('station=' + obj['station']) in obj['AGR_TEST']
    named = {obj['name']: obj for obj in catalog['objects']}
    assert named['SM_Polygon_001_Main']['station'] == '0.1.1'
    assert named['SM_Polygon_001_Main']['layer'] == '0'  # default layer, as a delivery scene (hyg_layer, 0.8.1)
    assert named['SM_Polygon_Layer_Main']['layer'] != '0'  # the one hyg_layer fixture
    assert named['_base_0_6']['layer'] == '_bases'
    assert named['_base_0_6']['colour'] != named['_base_0_1']['colour']


def test_committed_expected_matches_the_engine_predictor():
    """The JSON on disk is the predictor output, so a check-code change shows up here."""
    from test_polygon_support import load_expected, predict_all, suite_rows
    predicted = predict_all()
    assert set(predicted) == {r['id'] for r in suite_rows()}
    for button, doc in predicted.items():
        assert load_expected(button) == doc


def test_base_100_has_33_stations_in_stage_order_with_branch_reason():
    """#1024 branch 0: base 1.0 = stations 1.0.1..1.0.33 in the order of the stages (roadmap.stage_buttons), camera
    `_cam_База 1.0`; every button has expected/<id>.json with «станция в работе, #1024, ветка X» (X = owner of
    SPLIT.md) until its branch ships a fragment stations/<letter>.json."""
    import sys
    from test_polygon_support import bases, load_expected, stations
    core = sys.modules['agr_polygon_core']
    sys.path.insert(0, str(ROOT / 'adapters' / 'max' / 'agr_tools'))
    import roadmap
    suite = json.loads((ROOT / 'docs' / 'plans' / 'agr-tools-suite.json').read_text(encoding='utf-8'))
    order = roadmap.stage_buttons(suite)
    assert len(order) == 33 and core.TOUR_LAST == '1.1'
    base = [b for b in bases() if b['version'] == '1.0'][0]
    assert sorted(base['buttons']) == sorted(order)
    placed = [s for s in stations() if s['version'] == '1.0']
    assert [s['id'] for s in placed] == ['1.0.{}'.format(i) for i in range(1, 34)]
    assert [s['button'] for s in placed] == order
    assert set(core.OWNER_100) == set(order) and set(core.OWNER_100.values()) == set(core.BRANCHES_100)
    assert core.BRANCHES_100 == ('F', 'G', 'H', 'J', 'K', 'L', 'M', 'N', 'P', 'Q', 'S', 'T', 'U')
    frags = core.load_fragments()
    for spec in placed:
        doc = load_expected(spec['button'])
        letter = core.OWNER_100[spec['button']]
        assert spec['branch'] == letter and doc['station'] == spec['id'] and doc['base'] == '1.0'
        assert doc['version'] == '1.0'
        if spec['button'] not in frags or not frags[spec['button']]['expected']:
            assert doc['reason'] == 'станция в работе, #1024, ветка ' + letter, spec['button']
    names = {o['name'] for o in _catalog()['objects']}
    assert '_cam_База 1.0' in names and '_base_1_0' in names
    tail = [r for r in suite['rows'] if r.get('fate') in ('tail', 'obsolete')]
    assert tail
    for row in tail:
        doc = load_expected(row['id'])
        assert doc['version'] == '1.x' and doc['base'] is None and doc['reason'].strip()
        assert '#1024' not in doc['reason']


def test_fragment_hook_loads_letters_f_to_u_with_issue_1024(tmp_path, monkeypatch):
    """stations/<letter>.json of a #1024 branch loads like the 0.9 fragments; the issue must match the branch."""
    import sys
    import pytest
    from test_polygon_support import load_fragments
    core = sys.modules['agr_polygon_core']
    monkeypatch.setattr(core, 'STATIONS_DIR', tmp_path)
    assert load_fragments() == {}  # absent fragments are fine
    doc = {'schema': 1, 'branch': 'F', 'issue': '#1024', 'stations': [
        {'button': 'project.passport', 'objects': [{'name': 'SM_Passport_Main', 'role': 'Main'}]}]}
    (tmp_path / 'F.json').write_text(json.dumps(doc), encoding='utf-8')
    got = load_fragments()
    assert list(got) == ['project.passport'] and got['project.passport']['branch'] == 'F'
    doc['issue'] = '#979'
    (tmp_path / 'F.json').write_text(json.dumps(doc, indent=1), encoding='utf-8')
    with pytest.raises(RuntimeError):
        load_fragments()
    doc.update(issue='#1024', branch='F')
    doc['stations'][0]['button'] = 'body.prepare'  # owned by G
    (tmp_path / 'F.json').write_text(json.dumps(doc, indent=2), encoding='utf-8')
    with pytest.raises(RuntimeError):
        load_fragments()
    (tmp_path / 'F.json').unlink()
    (tmp_path / 'X.json').write_text('{}', encoding='utf-8')
    with pytest.raises(RuntimeError):
        load_fragments()


def test_base_110_has_4_handoff_stations_in_stage_order():
    """Release 1.1 (#1024, branch BH): base 1.1 = stations 1.1.1..1.1.4 for the handoff rows in the order of
    roadmap.stage_buttons(suite, '1.1'); the stations of base 1.0 keep their numbers."""
    import sys
    from test_polygon_support import bases, load_expected, stations
    core = sys.modules['agr_polygon_core']
    sys.path.insert(0, str(ROOT / 'adapters' / 'max' / 'agr_tools'))
    import roadmap
    suite = json.loads((ROOT / 'docs' / 'plans' / 'agr-tools-suite.json').read_text(encoding='utf-8'))
    order = roadmap.stage_buttons(suite, '1.1')
    assert order == ['handoff.export', 'handoff.import', 'handoff.verify', 'handoff.restore_materials']
    assert roadmap.stations(suite)['handoff.restore_materials'] == '1.1.4'
    base = [b for b in bases() if b['version'] == '1.1'][0]
    assert base['buttons'] == order
    placed = [s for s in stations() if s['version'] == '1.1']
    assert [s['id'] for s in placed] == ['1.1.{}'.format(i) for i in range(1, 5)]
    assert [s['button'] for s in placed] == order
    assert set(core.OWNER_110) == set(order) and set(core.OWNER_110.values()) == set(core.BRANCHES_110) == {'BH'}
    assert [s['id'] for s in stations() if s['version'] == '1.0'] == ['1.0.{}'.format(i) for i in range(1, 34)]
    for spec in placed:
        doc = load_expected(spec['button'])
        assert doc['station'] == spec['id'] and doc['base'] == '1.1' and doc['version'] == '1.1'
        assert spec['branch'] == 'BH'
        passes = [o for o in doc['objects'] if o['expect'] == 'pass']
        fails = [o for o in doc['objects'] if o['expect'] == 'fail']
        assert (passes and fails) or doc['reason'].strip(), spec['button']
    export = load_expected('handoff.export')
    assert {(o['name'], o['expect'], tuple(o['codes'])) for o in export['objects']} == {
        ('SM_FragBH_ExpOk_Main', 'pass', ()), ('SM_FragBH_ExpBad_Main', 'fail', ('duplicate_name',))}
    for button in order[1:]:
        doc = load_expected(button)
        assert [o['expect'] for o in doc['objects']] == ['error'] and 'run_agr_tools_handoff_native' in doc['reason']
    names = {o['name'] for o in _catalog()['objects']}
    assert '_cam_База 1.1' in names and '_base_1_1' in names
