"""new-case: AC06 Gate-1 evidence packet, not production material acceptance."""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / 'jobs/TEC26-OKS/AC06/materials.json'


def load_packet():
    return json.loads(PACKET.read_text(encoding='utf-8'))


def test_ac06_complete_measured_id_inventory():
    data = load_packet()
    rows = data['materials']
    assert [r['id'] for r in rows] == list(range(1, 13))
    assert [r['triangles'] for r in rows] == [362,1290,444,1576,48,300,204,1008,60,176,128,12]
    assert sum(r['triangles'] for r in rows) == 5608
    assert all(math.isfinite(r['area_m2']) and r['area_m2'] > 0 for r in rows)
    assert all(r['evidence'] for r in rows)
    assert data['scene']['layer_actual'] == '006'
    assert len(data['scene']['collision_candidates']) == 21


def test_ac06_unknowns_fail_closed_and_gate_stays_open():
    data = load_packet()
    assert data['status'] == 'awaiting_artem_gate_1'
    assert data['build_allowed'] is False
    assert data['approved'] is False
    unknowns = [r for r in data['materials'] if r['finish'] == '?']
    assert {r['id'] for r in unknowns} == {1, 4, 5, 6, 11}
    assert all(r['question'] and r['ral'] is None and r['map_type'] == '?' for r in unknowns)
    assert all(r['status'] != 'approved' for r in data['materials'])


def test_ac06_drawing_codes_are_own_building_not_kpp_inference():
    data = load_packet()
    assert data['building_name'] == 'Пункт редуцирования газа 1'
    assert {r['ral'] for r in data['drawing_finishes']} == {'5015', '7047', '7004', '9016'}
    assert all('136EBB' in r['locator'] for r in data['drawing_finishes'])
    assert data['pdf']['physical_pages'] == 1
    assert data['pdf']['printed_sheet'] == '2'
    assert all(r['status'] == 'proposed' for r in data['materials'] if r['finish'] != '?')


def test_ac06_kpp_colour_reuse_has_hashed_pixel_provenance():
    data = load_packet()
    assert set(data['kpp_colours']) == {'5015', '7047', '7004', '9016'}
    for ral, colour in data['kpp_colours'].items():
        assert colour['ral'] == ral
        assert len(colour['sha256']) == 64
        assert len(colour['rgb']) == 3
        assert all(type(v) is int and 0 <= v <= 255 for v in colour['rgb'])
        assert colour['method'] == 'most_frequent_rgb_pixel'
    for row in data['materials']:
        if row['ral'] is not None:
            assert row['swatch_rgb'] == data['kpp_colours'][row['ral']]['rgb']


def test_ac06_evidence_is_external_and_no_final_delivery_claim():
    data = load_packet()
    assert data['evidence_directory'] == 'G:/Мой диск/AGR-evidence/tec26-oks/AC06/evidence-v001'
    assert len(data['inputs']) >= 4
    assert all(len(r['sha256']) == 64 for r in data['inputs'])
    assert data['scene']['diagnostic_render_method'] == 'software orthographic triangle projection; no DCC scene mutation'
    assert (ROOT / 'jobs/TEC26-OKS/AC06/MATERIALS.md').is_file()
