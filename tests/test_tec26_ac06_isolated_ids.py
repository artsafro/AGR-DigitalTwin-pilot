"""new-case: AC06 isolated-ID correction and orchestrator finish policy."""
import json
from pathlib import Path

PACKET = Path(__file__).resolve().parents[1] / 'jobs/TEC26-OKS/AC06/materials.json'


def test_ac06_isolated_downpipes_not_window_reveals():
    data = json.loads(PACKET.read_text(encoding='utf-8'))
    rows = {r['id']:r for r in data['materials']}
    assert rows[4]['finish'] == 'Rainwater downpipes'
    assert rows[4]['ral'] == '7004'
    assert rows[4]['status'] == 'approved'
    assert rows[9]['finish'] == 'Window reveals'
    assert rows[9]['ral'] == '9016'
    assert rows[9]['map_type'] == 'solid'
    assert rows[9]['status'] == 'approved'
    assert rows[9]['question'] is None
    assert all('depth-isolated.png' in r['evidence'] for r in [rows[4],rows[5],rows[6],rows[8],rows[9],rows[11]])
    assert data['scene']['layer_question'] is None
    assert rows[3]['map_type'] == 'solid'
    assert 'solid colour' in rows[3]['joint_policy']
    assert rows[12]['glass_policy']['material'] == 'M_Glass_01'
    assert rows[12]['glass_policy']['npm_alpha'] == 0.5
    assert rows[12]['question'] is None
    unresolved = [r['id'] for r in rows.values() if r['finish'] in (None, '', '?') or r['status'] != 'approved']
    assert unresolved == [], f'unresolved material ids: {unresolved}'


def test_ac06_depth_correct_gate_and_perimeter_drop():
    data = json.loads(PACKET.read_text(encoding='utf-8'))
    scene = data['scene']
    assert scene['depth_render']['application'] == 'Blender'
    assert scene['depth_render']['version'] == '5.1.2'
    assert scene['depth_render']['collision_loaded'] is False
    assert scene['depth_render']['zero_reference_z_m'] == 0.0
    assert scene['depth_render']['mesh_triangles'] == 5608
    assert scene['depth_render']['source_geometry_edited'] is False
    assert scene['perimeter_drop']['coverage_passed'] == scene['perimeter_drop']['coverage_total'] == 8
    assert all(c['lowest_side_vertex_m'] <= -1.0 for c in scene['perimeter_drop']['coverage_checks'])
    assert scene['perimeter_drop']['geometry_changed'] is False
    assert all(r['evidence'] and any('depth-' in p for p in r['evidence']) for r in data['materials'])
    rows = {r['id']: r for r in data['materials']}
    rules = data['panel_texture_rules']
    assert rules['joint_style'] == 'vertical_ribs'
    assert rules['vertical_only'] is True
    assert rules['horizontal_joints'] is False
    assert rules['below_zero'] == 'plain'
    assert rules['below_zero_joints'] is False
    assert rules['switched_ids'] == []
    assert rows[2]['map_type'] == 'metal'
    assert rows[3]['ral'] == '7047'
    for facade in rules['facades']:
        count = facade['vertical_ribs']
        step = facade['step']
        if count == '?' or step == '?':
            assert isinstance(facade.get('question'), str) and facade['question'].strip()
        else:
            assert facade.get('sheet_evidence')
            assert isinstance(count, int) and count > 0
            assert isinstance(step, (int, float)) and not isinstance(step, bool) and step > 0
    drop = data['mixed_id_rule']['drop_below_pm_0_000']
    assert drop['geometry_change'] is False
    assert drop['joints'] is False

