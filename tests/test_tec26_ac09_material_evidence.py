"""new-case: AC09 Gate-1 evidence preserves unresolved finishes and source IDs."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'jobs/TEC26-OKS/AC09'


def test_ac09_preserves_ids_and_blocks_unapproved_finishes():
    data = json.loads((ROOT / 'materials.json').read_text(encoding='utf-8'))
    assert data['status'] == 'awaiting_gate1'
    assert data['passed'] is False
    assert [x['id'] for x in data['materials']] == list(range(1, 11))
    assert sum(x['triangles_main'] for x in data['materials']) == 682
    assert sum(x['triangles_glass'] for x in data['materials']) == 8
    expected = {1: '?', 2: 'RAL5015 sandwich panels', 3: 'RAL9016 window frames',
                4: 'RAL7004 door', 5: 'RAL9016 window reveals (proposal)',
                6: 'M_Glass_01 (KPP)', 7: '?', 8: 'empty', 9: 'empty', 10: 'empty'}
    for item in data['materials']:
        assert item['finish'] == expected[item['id']]
        assert item['approved'] is False
        assert item['geometry_evidence']
        if item['finish'] == '?':
            assert item['question']
        if item['id'] in (8, 9, 10):
            assert item['map_type'] is None
            assert item['question'] is None
    assert data['materials'][5]['npm_alpha'] == 0.5
    assert 'gate1-v002' in data['contact_sheet']
    assert data['native_drawing_evidence']['facades']['pages'] == 1
    assert data['native_drawing_evidence']['sheet2']['pages'] == 1
    refs = {r['ral']: r for r in data['kpp_colour_references']}
    for item in data['materials']:
        if item.get('ral'):
            assert item['colour_reference_sha256'] == refs[item['ral']]['sha256']
    assert len(data['open_items']) == 4
    assert data['scene']['handles'] == [173, 342, 369]
    assert {x['ral'] for x in data['drawing_finishes']} == {'5015', '7004', '9016'}
    assert data['building_name'] == 'Контейнер системы автоматического контроля вредных выбросов (САКВ)'


def test_ac09_evidence_locators_and_hashes():
    data = json.loads((ROOT / 'materials.json').read_text(encoding='utf-8'))
    for row in data['drawing_finishes']:
        assert row['handle'] and len(row['coordinate']) == 3
        assert row['space'] == 'Model'
    for row in data['files']:
        assert len(row['sha256']) == 64
    assert (ROOT / 'MATERIALS.md').is_file()
