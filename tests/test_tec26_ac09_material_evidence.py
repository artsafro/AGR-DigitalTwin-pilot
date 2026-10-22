"""AC09 Gate-1 approval records Artem's finish decisions without a delivery pass."""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'jobs/TEC26-OKS/AC09'
KPP = Path(__file__).resolve().parents[1] / 'jobs/KPP1/materials.json'

EXPECTED_RAL = {
    2: '5015',
    3: '9016',
    4: '7004',
    5: '9016',
}

JOINTS_MAP = 'joints (KPP panel tile, same texel density/joint scale)'
PANEL_RULE_QUOTE = (
    'New rule from Artem (2026-10-22, supersedes "solid colour without joints" for panels): '
    'ID2 blue sandwich panels (RAL 5015) use the KPP VPM panel texture WITH its joints '
    '(blue cassette tile(s) of maps_kpp T_Kpp_1_Diffuse/Normal_1.10xx, see '
    'C:/x/tec26-oks/census/kpp-recipe.md if present) at the SAME texel density and joint scale '
    'as KPP VPM, in VPM (diffuse+normal) and NPM (atlas, joints >= 1.5 px like make_npm_atlas.py). '
    'Joint phase starts at +-0.000; the perimeter drop below +-0.000 stays plain panel colour '
    'WITHOUT joints (underground). Geometry unchanged.'
)
RETIRED_PANEL_WORDING = (
    'solid, no joints',
    'no synthetic joints',
    'solid colour without invented joints',
    'module not confirmed',
    'not confirmed in drawings',
    'Panel module is not confirmed',
)


def _load():
    return json.loads((ROOT / 'materials.json').read_text(encoding='utf-8'))


def _walk_numbers(node, where):
    if isinstance(node, dict):
        for key, value in node.items():
            _walk_numbers(value, f'{where}.{key}')
    elif isinstance(node, list):
        for index, value in enumerate(node):
            _walk_numbers(value, f'{where}[{index}]')
    elif isinstance(node, float):
        assert math.isfinite(node), f'non-finite number at {where}'


def _kpp_colour(refs, ral, where):
    if ral not in refs:
        raise AssertionError(f'unmapped KPP colour RAL {ral} at {where}')
    return refs[ral]


def _census_material_ids(census):
    found = set()
    for obj in census['objects']:
        material = obj.get('material') or {}
        for sub in material.get('submaterials') or []:
            found.add(sub['id'])
        for row in obj.get('material_ids') or []:
            found.add(row['id'])
        for key in (obj.get('poly_faces_by_id') or {}):
            found.add(int(key))
    return found


def test_ac09_preserves_ids_and_records_gate1_approval():
    data = _load()
    assert data['status'] == 'approved-gate1'
    assert data['passed'] is False
    quote = data['gate1_approval']['quote']
    assert quote == '«Принимаю» (Artem, 2026-10-22, Gate 1 answer)'
    assert data['gate1_approval']['date'] == '2026-10-22'
    assert [x['id'] for x in data['materials']] == list(range(1, 11))
    assert sum(x['triangles_main'] for x in data['materials']) == 682
    assert sum(x['triangles_glass'] for x in data['materials']) == 8
    by_id = {item['id']: item for item in data['materials']}
    refs = {row['ral']: row for row in data['kpp_colour_references']}

    id1 = by_id[1]
    regions = {row['name']: row for row in id1['sub_regions']}
    assert set(regions) == {'roof', 'frame', 'plinth', 'below_grade_drop'}
    assert regions['roof']['ral'] == '7004'
    assert regions['frame']['ral'] == '7004'
    assert regions['roof']['ral'] != '5015'
    assert regions['plinth']['ral'] == '5015'
    assert regions['below_grade_drop']['ral'] == '5015'
    assert id1['geometry_change'] is False
    assert id1['perimeter_drop_below_zero']['separate_id'] is False
    assert id1['perimeter_drop_below_zero']['ral'] == '5015'
    for name, region in regions.items():
        colour = _kpp_colour(refs, region['ral'], f'ID1.{name}')
        assert region['colour_reference_sha256'] == colour['sha256']
        assert region['geometry_change'] is False
        assert '?' not in region['finish']

    for mid, ral in EXPECTED_RAL.items():
        item = by_id[mid]
        assert item['ral'] == ral, f'ID{mid} RAL'
        colour = _kpp_colour(refs, ral, f'ID{mid}')
        assert item['colour_reference_sha256'] == colour['sha256']
        assert '?' not in item['finish']
    id2 = by_id[2]
    assert id2['map_type'] == JOINTS_MAP
    assert id2['quote'] == PANEL_RULE_QUOTE
    assert id2['joint_phase_z'] == 0.0
    assert id2['below_grade']['ral'] == '5015'
    assert 'plain' in id2['below_grade']['rule'].lower()
    assert 'without joints' in id2['below_grade']['rule'].lower()
    for name in ('plinth', 'below_grade_drop'):
        note = regions[name]['note']
        assert 'plain wall colour without joints' in note
        assert not str(regions[name]['map_type']).startswith('joints')
    assert 'plain wall colour without joints' in id1['perimeter_drop_below_zero']['note']
    assert by_id[4]['map_type'] == 'metal'
    assert by_id[6]['finish'] == 'M_Glass_01 (KPP)'
    assert by_id[6]['npm_material'] == 'M_Glass_01'
    assert by_id[6]['npm_alpha'] == 0.5
    assert by_id[6]['ral'] is None
    assert by_id[7]['kpp_finish'] == 'Interior'
    assert by_id[7]['ral'] is None
    assert '?' not in by_id[7]['finish']
    kpp = json.loads(KPP.read_text(encoding='utf-8'))
    assert kpp['finishes']['Interior']['udim'] == by_id[7]['kpp_udim']
    assert 'rgb' not in by_id[7]

    for mid in (8, 9, 10):
        assert by_id[mid]['status'] == 'empty'
        assert by_id[mid]['finish'] == 'empty'
        assert by_id[mid]['map_type'] is None
    empty = {row['id']: row for row in data['empty_slot_list']}
    assert set(empty) == {8, 9, 10}
    for mid, row in empty.items():
        assert row['reason'], f'empty slot {mid} has no reason'

    for item in data['materials']:
        if item['status'] == 'empty':
            continue
        assert '?' not in str(item['finish']), f"open finish on ID{item['id']}"
        assert item['question'] is None
    raw = (ROOT / 'materials.json').read_text(encoding='utf-8')
    assert 'NaN' not in raw and 'Infinity' not in raw
    _walk_numbers(data['materials'], 'materials')

    assert data['open_items'] == []
    assert data['resolved_items']
    assert all(row['status'] == 'resolved' and row['decision'] for row in data['resolved_items'])
    kinds = {row['item'] for row in data['non_blocking']}
    assert 'roof elevation +2.330 vs corrected' in kinds
    assert 'sandwich 120 vs 150 mm' in kinds
    assert all(row['status'] == 'non-blocking' for row in data['non_blocking'])

    assert 'gate1-v002' in data['contact_sheet']
    assert data['native_drawing_evidence']['facades']['pages'] == 1
    assert data['native_drawing_evidence']['sheet2']['pages'] == 1
    assert data['scene']['handles'] == [173, 342, 369]
    assert {x['ral'] for x in data['drawing_finishes']} == {'5015', '7004', '9016'}
    assert data['building_name'] == 'Контейнер системы автоматического контроля вредных выбросов (САКВ)'
    header = (ROOT / 'MATERIALS.md').read_text(encoding='utf-8')
    assert 'approved-gate1' in header.splitlines()[0]
    assert '«Принимаю» (Artem, 2026-10-22, Gate 1 answer)' in header
    assert 'passed=false' in header
    assert JOINTS_MAP in header
    assert PANEL_RULE_QUOTE in header
    assert 'z=0.000' in header
    for banned in RETIRED_PANEL_WORDING:
        assert banned not in raw, banned
        assert banned not in header, banned


def test_ac09_census_ids_match_materials_or_empty_slots():
    """Brute-force probe: every census material ID is mapped or listed empty with a reason."""
    data = _load()
    census = json.loads((ROOT / 'scene-census.json').read_text(encoding='utf-8'))
    census_ids = _census_material_ids(census)
    mapped = {item['id']: item for item in data['materials']}
    empty = {row['id']: row['reason'] for row in data['empty_slot_list']}
    missing = []
    for mid in sorted(census_ids):
        item = mapped.get(mid)
        if item is None:
            missing.append(mid)
            continue
        if item['status'] == 'empty':
            reason = empty.get(mid)
            if not reason:
                raise AssertionError(f'unmapped material ID {mid}: empty slot has no reason')
    assert missing == [], 'unmapped material ID ' + ', '.join(str(mid) for mid in missing)
    assert len(census_ids) == 10


def _is_joints(map_type):
    return isinstance(map_type, str) and map_type.startswith('joints')


def _phase_is_zero(node):
    if isinstance(node, dict):
        if 'joint_phase_z' in node and node['joint_phase_z'] == 0.0:
            return True
        return any(_phase_is_zero(value) for value in node.values())
    if isinstance(node, list):
        return any(_phase_is_zero(value) for value in node)
    return False


def _below_grade_plain(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if 'below' in key and isinstance(value, dict):
                text = json.dumps(value, ensure_ascii=False).lower()
                if 'plain' in text and 'without joints' in text and '5015' in text:
                    return True
            if _below_grade_plain(value):
                return True
    elif isinstance(node, list):
        return any(_below_grade_plain(value) for value in node)
    return False


def test_every_joints_id_names_kpp_tile_phase_and_below_grade_plain_rule():
    """Probe: a joints map names the KPP tile, a phase and a plain below-grade rule."""
    data = _load()
    found = []
    for item in data['materials']:
        records = [item]
        records.extend(item.get('sub_regions') or [])
        for record in records:
            if not _is_joints(record.get('map_type')):
                continue
            found.append(record.get('id', item['id']))
            blob = json.dumps(record, ensure_ascii=False)
            assert 'T_Kpp_1_Diffuse_1.1007' in blob, f"ID{item['id']} joints map has no KPP diffuse tile"
            assert 'T_Kpp_1_Normal_1.1007' in blob, f"ID{item['id']} joints map has no KPP normal tile"
            assert _phase_is_zero(record), f"ID{item['id']} joints map has no phase at 0.000"
            assert _below_grade_plain(record), f"ID{item['id']} joints map has no plain below-grade rule"
    assert found == [2]


def test_ac09_evidence_locators_and_hashes():
    data = _load()
    for row in data['drawing_finishes']:
        assert row['handle'] and len(row['coordinate']) == 3
        assert row['space'] == 'Model'
    for row in data['files']:
        assert len(row['sha256']) == 64
    assert (ROOT / 'MATERIALS.md').is_file()
