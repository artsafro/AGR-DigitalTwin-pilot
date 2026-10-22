"""AC07 Gate-1 material approval by Artem (2026-10-22), ID6 still to_verify.

Not a VPM/NPM build and not model acceptance. Geometry counts and hashes stay
the source census values.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
JOB = ROOT / 'jobs/TEC26-OKS/AC07'
EXPECTED = [
    (1, 181, 362), (2, 671, 1290), (3, 300, 444),
    (4, 772, 1576), (5, 24, 48), (6, 200, 300),
    (7, 120, 204), (8, 504, 1008), (9, 30, 60),
    (10, 88, 176), (11, 64, 128), (12, 6, 12),
]
MAIN_GEOMETRY_SHA = 'daebde11357b727c26c217261788a2d89b39bd6cb9d5c6ca76ebc6d9ec280ce1'
GLASS_GEOMETRY_SHA = '2bbb2d6b882ea764917aaeaa8a4bee04d0f89a04971a369fca05eaeecdcb0653'
CENSUS_SHA = 'a99de19f1d30633eaab9c52ac44f253ed6ea97e03358755ff2a77458f0f54f2f'
CONTACT_SHEET_SHA = 'b93f7648ae3cf5aa82b1f7d8915c18a5df4f83f0252cf555398c0f0353ae9bbd'
QUOTE = 'Принимаю'
OPEN_QUESTION = 'what are the round inserts, is 7004 metal right?'
PANEL_TEXTURE = Path('C:/x/tec26-oks/user-textures/panel_RAL5015_vertical_joints_4096.png')
ANSWERS = [
    'RAL 5015 sandwich panels (ID1 upper facade and any other RAL 5015 panel region): vertical joints only, map_type vertical_joints, module 0.60 m, joint 8 mm, no horizontal joints; do not tile the raw 4K image; phase from +-0.000 / panel corner. RAL 7047 sandwich panels stay solid. Metal trims (ID2) unchanged. Below +-0.000 (ID10 drop and any perimeter drop): plain colour, no joints. Supersedes solid-without-joints for blue panels.',
    'Roof: RAL 7004 grey (as KPP 7004), not 5015.',
    'A mixed ID may be painted per part (roof 7004, frame 7004, plinth/drop = wall colour) without changing geometry - via UV / atlas regions or face-group split inside the same ID.',
    'Panels RAL 5015 = KPP blue, doors/frames/porches RAL 7004 = KPP grey, glass as KPP; drop below +-0.000 = wall colour.',
    'ID6 round inserts: Artem did not define; set 7004 metal, status to_verify (на проверку), show enlarged on the VPM/NPM acceptance sheet.',
]
HEADER = 'Gate 1 APPROVED by Artem 2026-10-22 (with ID6 to_verify)'
ALLOWED_STATUS = {'approved', 'to_verify'}
NULL_RAL_IDS = {11, 12}


def load_record():
    assert (JOB / 'materials.json').is_file(), 'AC07 Gate-1 material evidence is missing'
    return json.loads((JOB / 'materials.json').read_text(encoding='utf-8'))


def _is_blue_panel_row(row):
    """RAL 5015 sandwich/panel assignment. Metal trims (ID2) are not panel rows."""
    if str(row.get('ral') or '') != '5015':
        return False
    finish = str(row.get('finish') or '')
    part = str(row.get('part') or '')
    role = str(row.get('role_observed') or '')
    blob = f'{finish} {part} {role}'.lower()
    if 'metal' in blob or row.get('map_type') == 'metal':
        return False
    return 'panel' in blob or 'sandwich' in blob


def blue_panel_rows(data):
    found = []
    for row in data.get('materials') or []:
        if _is_blue_panel_row(row):
            found.append(row)
        for region in row.get('regions') or []:
            if _is_blue_panel_row(region):
                found.append(region)
    return found


def panel_joint_defects(data):
    """Empty list means the RAL 5015 vertical-joint rule holds."""
    defects = []
    rule = data.get('panel_rule')
    if not isinstance(rule, dict):
        defects.append('missing panel_rule')
        return defects
    if rule.get('module_m') != 0.60:
        defects.append('module_m')
    if rule.get('joint_mm') != 8:
        defects.append('joint_mm')
    if rule.get('vertical_only') is not True:
        defects.append('vertical_only')
    if rule.get('below_zero_plain') is not True:
        defects.append('below_zero_plain')
    if rule.get('do_not_tile_raw_image') is not True:
        defects.append('do_not_tile')
    if rule.get('cuts_made') is not False:
        defects.append('cuts_made')
    texture = rule.get('texture') or {}
    recorded = str(texture.get('path') or '').replace('\\', '/')
    if recorded.lower() != PANEL_TEXTURE.as_posix().lower():
        defects.append('texture path')
    if not PANEL_TEXTURE.is_file():
        defects.append('texture missing')
    else:
        digest = hashlib.sha256(PANEL_TEXTURE.read_bytes()).hexdigest()
        if texture.get('sha256') != digest:
            defects.append('texture sha256')
        if texture.get('bytes') != PANEL_TEXTURE.stat().st_size:
            defects.append('texture bytes')
    rows = blue_panel_rows(data)
    if not rows:
        defects.append('no panel rows')
    for row in rows:
        map_type = str(row.get('map_type') or '')
        if map_type == 'solid':
            defects.append('solid on panel row')
        elif map_type != 'vertical_joints':
            defects.append('panel map_type')
        if row.get('horizontal_joints') is True or 'horizontal' in map_type:
            defects.append('horizontal joints')
    id10 = next((row for row in data.get('materials') or [] if row.get('id') == 10), None)
    if id10 is None or id10.get('map_type') != 'solid':
        defects.append('id10 not solid')
    id2 = next((row for row in data.get('materials') or [] if row.get('id') == 2), None)
    if id2 is None or id2.get('map_type') != 'metal':
        defects.append('id2 not metal')
    return defects


def gate1_defects(data):
    """Closed checks for an approved Gate-1 record. Empty list means accept."""
    defects = []
    gate = data.get('gate1') or {}
    if gate.get('approved') is not True:
        defects.append('not approved')
    if not str(gate.get('quote') or '').strip():
        defects.append('missing quote')
    answers = gate.get('answers')
    if not isinstance(answers, list) or len(answers) == 0:
        defects.append('empty answer list')
    rows = data.get('materials') or []
    ids = [row.get('id') for row in rows]
    if ids != list(range(1, 13)) or any(row.get('status') == 'unknown' for row in rows):
        defects.append('unknown id')
    if gate.get('approved') is True:
        for row in rows:
            if row.get('id') not in range(1, 13) or row.get('status') not in ALLOWED_STATUS:
                if 'unknown id' not in defects:
                    defects.append('unknown id')
    return defects


@pytest.mark.parametrize('mid,polygons,triangles', EXPECTED)
def test_ac07_gate1_preserves_ids_and_approved_finishes(mid, polygons, triangles):
    data = load_record()
    assert data['gate1']['status'] == 'approved-gate1'
    assert data['gate1']['approved'] is True
    assert data['gate1']['approved_by'] == 'Artem'
    assert data['gate1']['date'] == '2026-10-22'
    assert data['gate1']['quote'] == QUOTE
    assert data['gate1']['answers'] == ANSWERS
    assert data['delivery_built'] is False
    assert [r['id'] for r in data['materials']] == list(range(1, 13))
    row = next(r for r in data['materials'] if r['id'] == mid)
    assert row['polygons'] == polygons
    assert row['triangles'] == triangles
    assert math.isfinite(row['area_m2']) and row['area_m2'] > 0
    assert row['finish'] and row['finish'] != '?'
    assert row['status'] in ALLOWED_STATUS
    assert row['geometry_evidence']
    assert row['geometry_sha256'] == (GLASS_GEOMETRY_SHA if mid == 12 else MAIN_GEOMETRY_SHA)
    if row['question']:
        assert row['question'] == OPEN_QUESTION
        assert row['question'] in data['questions']
        assert row['status'] == 'to_verify'
    if mid in NULL_RAL_IDS:
        assert row['ral'] is None
    else:
        assert row['ral'] not in (None, '?', '')
    if row['ral'] is not None and 'regions' not in row:
        assert row['kpp_colour']['sha256']
        assert row['kpp_colour']['method'] == 'exact KPP map pixels; no RAL approximation'
    report = (JOB / 'MATERIALS.md').read_text(encoding='utf-8')
    assert f'| {mid} |' in report
    if row['question']:
        assert row['question'] in report
    assert data['materials'][11]['finish'] == 'M_Glass_01 (KPP convention)'
    assert data['materials'][10]['finish'] == 'Interior'
    assert data['materials'][8]['ral'] == '9016'
    assert data['materials'][9]['ral'] == '7004'
    assert data['materials'][2]['map_type'] == 'solid'
    assert data['scene']['layer_correspondence'] == 'confirmed by operator: actual census layer names govern'
    assert data['scene']['actual_layer'] == '007'
    assert data['scene']['collision_objects'] == 21
    assert len(data['scene']['objects']) == 23
    assert data['scene']['unmapped_ids'] == []
    assert data['scene']['render_polygons'] == 2960
    assert data['scene']['render_triangles'] == 5608
    assert sum(r['polygons'] for r in data['materials']) == 2960
    assert sum(r['triangles'] for r in data['materials']) == 5608
    assert data['scene']['id_gaps'] == []
    assert data['scene']['census_sha256'] == CENSUS_SHA
    assert data['evidence']['contact_sheet_sha256'] == CONTACT_SHEET_SHA


def test_ac07_gate1_artem_approval_regions_and_open_id6():
    data = load_record()
    assert gate1_defects(data) == []
    rows = {row['id']: row for row in data['materials']}
    assert [row['status'] for row in data['materials']] == (
        ['approved'] * 5 + ['to_verify'] + ['approved'] * 6
    )
    assert [row['id'] for row in data['materials'] if row['status'] == 'to_verify'] == [6]
    for row in data['materials']:
        assert row['finish'] != '?'
        assert row['map_type'] != '?'
        if row['id'] not in NULL_RAL_IDS:
            assert row['ral'] not in (None, '?')
    roof, facade = rows[1]['regions']
    assert [roof['part'], facade['part']] == ['roof faces', 'upper facade panels']
    assert [roof['ral'], facade['ral']] == ['7004', '5015']
    assert roof['kpp_colour']['sha256'] == rows[4]['kpp_colour']['sha256']
    assert facade['kpp_colour']['sha256'] == '1d978c478b119565a77a2b503ce8b1f09d95425156ccd83c90021459dc14c4a2'
    assert rows[1]['status'] == 'approved'
    assert rows[1]['polygons'] == 181 and rows[1]['triangles'] == 362
    assert rows[5]['finish'] == 'metal RAL 7004'
    assert rows[5]['ral'] == '7004' and rows[5]['status'] == 'approved'
    assert rows[6]['finish'] == 'metal RAL 7004'
    assert rows[6]['ral'] == '7004' and rows[6]['map_type'] == 'metal'
    assert rows[6]['status'] == 'to_verify'
    assert rows[6]['show_enlarged'] is True
    assert rows[6]['question'] == OPEN_QUESTION
    assert data['questions'] == [OPEN_QUESTION]
    assert rows[11]['finish'] == 'Interior'
    assert rows[11]['kpp_finish_name'] == 'Interior'
    assert rows[11]['status'] == 'approved' and rows[11]['ral'] is None
    report = (JOB / 'MATERIALS.md').read_text(encoding='utf-8')
    assert report.startswith('# TEC26 AC07 — Gate 1 material evidence\n\n**' + HEADER + '**')
    assert QUOTE in report
    assert 'v006' in report and 'old proposal' in report
    assert 'VPM/NPM' in report
    assert 'STOP: awaiting Artem' not in report


def test_ac07_fail_closed_rejects_incomplete_approval():
    data = load_record()
    assert gate1_defects(data) == []

    missing_quote = copy.deepcopy(data)
    del missing_quote['gate1']['quote']
    assert 'missing quote' in gate1_defects(missing_quote)

    unknown_id = copy.deepcopy(data)
    assert unknown_id['gate1']['approved'] is True
    unknown_id['materials'][0]['status'] = 'unknown'
    assert 'unknown id' in gate1_defects(unknown_id)

    empty_answers = copy.deepcopy(data)
    empty_answers['gate1']['answers'] = []
    assert 'empty answer list' in gate1_defects(empty_answers)


def test_ac07_gate_images_and_perimeter_drop_follow_operator_clarification():
    data = load_record()
    assert data['evidence']['renderer'].startswith('Blender ')
    assert data['evidence']['depth_correct'] is True
    assert data['evidence']['datum_z_m'] == 0.0
    assert data['evidence']['collision_visible'] is False
    assert data['evidence']['plain_shaded_views'] is True
    assert data['materials'][9]['finish'] == 'plinth and required perimeter drop RAL 7004'
    assert data['scene']['perimeter_drop']['preserved'] is True
    assert data['scene']['perimeter_drop']['cut_at_ground'] is False
    assert data['scene']['perimeter_drop']['all_lower_wall_triangles_reach_below_minus_1m'] is True


def test_ac07_ral5015_panels_use_vertical_joints_only():
    data = load_record()
    assert panel_joint_defects(data) == []
    rule = data['panel_rule']
    assert rule['module_m'] == 0.60
    assert rule['joint_mm'] == 8
    assert rule['vertical_only'] is True
    assert rule['below_zero_plain'] is True
    assert rule['texture']['sha256'] == hashlib.sha256(PANEL_TEXTURE.read_bytes()).hexdigest()
    assert rule['texture']['bytes'] == PANEL_TEXTURE.stat().st_size
    panels = blue_panel_rows(data)
    assert panels
    assert {row['map_type'] for row in panels} == {'vertical_joints'}
    id10 = next(row for row in data['materials'] if row['id'] == 10)
    assert id10['map_type'] == 'solid'
    assert id10['ral'] == '7004'
    report = (JOB / 'MATERIALS.md').read_text(encoding='utf-8')
    assert 'vertical_joints' in report
    assert '0.60' in report
    assert 'solid colour without joints' not in report

    solid = copy.deepcopy(data)
    blue_panel_rows(solid)[0]['map_type'] = 'solid'
    assert 'solid on panel row' in panel_joint_defects(solid)

    horizontal = copy.deepcopy(data)
    blue_panel_rows(horizontal)[0]['map_type'] = 'horizontal_joints'
    assert 'horizontal joints' in panel_joint_defects(horizontal)
