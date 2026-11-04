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


def test_catalog_has_the_required_kinds():
    catalog = json.loads((POLY / 'catalog.json').read_text(encoding='utf-8'))
    roles = {o['role'] for o in catalog['objects']}
    for role in ('Main', 'MainGlass', 'Ground', 'GroundEl', 'Flora', 'UCX', 'camera', 'light', 'shape', 'helper'):
        assert role in roles, role
    for obj in catalog['objects']:
        assert 'AGR_TEST' in obj and obj['AGR_TEST']
        assert obj['scene'] in ('polygon_all', 'cm_units', 'empty', 'vpm')


def test_variant_scene_specs_exist():
    for name in ('cm_units.json', 'empty.json', 'vpm.json'):
        doc = json.loads((POLY / 'scenes' / name).read_text(encoding='utf-8'))
        assert doc['scene'] == name[:-5]
        assert doc['synthetic'] is True


def test_bases_stations_and_button_versions():
    """Every tour button has a unique station on a base; the version is the suite JSON."""
    from test_polygon_support import bases, load_expected, stations, suite_rows
    built = bases()
    built_ids = [item['version'] for item in built]
    assert built_ids == ['0.1', '0.2', '0.3', '0.4', '0.5', '0.6', '0.7']
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
    catalog = json.loads((POLY / 'catalog.json').read_text(encoding='utf-8'))
    fixtures = [obj for obj in catalog['objects'] if excluded_name(obj['name'])]
    assert fixtures
    assert any(obj['layer'] == '_bases' and obj['name'].startswith('_base_') for obj in fixtures)
    assert any(obj['layer'] == '_labels' and obj['name'].startswith('_label_') for obj in fixtures)
    assert all(obj['AGR_TEST'] == 'fixture' for obj in fixtures)
    report = {'status': 'pass', 'objects': [
        {'name': '_base_0_1', 'findings': [{'code': 'name_prefix', 'ids': [], 'detail': ''}]},
        {'name': '_label_0_1_1', 'findings': [{'code': 'hyg_non_mesh', 'ids': [], 'detail': ''}]},
        {'name': 'A', 'findings': []},
    ]}
    got = compare_report(
        [{'name': 'A', 'scene': 'polygon_all', 'expect': 'pass', 'codes': []}], report)
    assert got == []
    assert '_base_' not in json.dumps(got) and '_label_' not in json.dumps(got)


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
    catalog = json.loads((POLY / 'catalog.json').read_text(encoding='utf-8'))
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
    assert named['SM_Polygon_001_Main']['layer'] == 'База 0.1'
    assert named['_base_0_6']['layer'] == '_bases'
    assert named['_base_0_6']['colour'] != named['_base_0_1']['colour']


def test_committed_expected_matches_the_engine_predictor():
    """The JSON on disk is the predictor output, so a check-code change shows up here."""
    from test_polygon_support import load_expected, predict_all, suite_rows
    predicted = predict_all()
    assert set(predicted) == {r['id'] for r in suite_rows()}
    for button, doc in predicted.items():
        assert load_expected(button) == doc
