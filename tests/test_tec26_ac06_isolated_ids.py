"""new-case: AC06 isolated-ID correction and orchestrator finish policy."""
import json
from pathlib import Path

PACKET = Path(__file__).resolve().parents[1] / 'jobs/TEC26-OKS/AC06/materials.json'


def test_ac06_isolated_downpipes_not_window_reveals():
    data = json.loads(PACKET.read_text(encoding='utf-8'))
    rows = {r['id']:r for r in data['materials']}
    assert rows[4]['finish'] == 'Rainwater downpipes'
    assert rows[4]['ral'] == '7004'
    assert rows[9]['finish'] == '?'
    assert rows[9]['proposal']['component'] == 'Window perimeter reveals'
    assert rows[9]['proposal']['ral'] == '9016'
    assert all('ids-isolated-unknowns.png' in r['evidence'] for r in [rows[4],rows[5],rows[6],rows[8],rows[9],rows[11]])
    assert data['scene']['layer_question'] is None
    assert rows[3]['map_type'] == 'solid'
    assert rows[12]['glass_policy']['material'] == 'M_Glass_01'
    assert rows[12]['glass_policy']['npm_alpha'] == 0.5
    assert rows[12]['question'] is None
    assert all(r['proposal']['rationale'] and r['proposal']['map_type'] for r in rows.values() if r['finish'] == '?')


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

