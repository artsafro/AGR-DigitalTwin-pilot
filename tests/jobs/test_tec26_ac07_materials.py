"""new-case: AC07 Gate-1 inventory completeness, not model/finish approval."""
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


@pytest.mark.parametrize('mid,polygons,triangles', EXPECTED)
def test_ac07_gate1_preserves_ids_and_unresolved_evidence(mid, polygons, triangles):
    assert (JOB / 'materials.json').is_file(), 'AC07 Gate-1 material evidence is missing'
    data = json.loads((JOB / 'materials.json').read_text(encoding='utf-8'))
    assert data['gate1']['status'] == 'awaiting_artem'
    assert data['gate1']['approved'] is False
    assert data['delivery_built'] is False
    assert [r['id'] for r in data['materials']] == list(range(1, 13))
    row = next(r for r in data['materials'] if r['id'] == mid)
    assert row['polygons'] == polygons
    assert row['triangles'] == triangles
    assert math.isfinite(row['area_m2']) and row['area_m2'] > 0
    assert row['status'] in {'proposed', 'unknown'}
    assert row['geometry_evidence']
    if row['finish'] == '?':
        assert row['question'] and row['question'] in data['questions']
        assert row['status'] == 'unknown'
        assert row['ral'] is None
    else:
        assert row['drawing_evidence']
    if row['ral'] is not None:
        assert row['kpp_colour']['sha256']
        assert row['kpp_colour']['method'] == 'exact KPP map pixels; no RAL approximation'
    report = (JOB / 'MATERIALS.md').read_text(encoding='utf-8')
    assert f'| {mid} |' in report
    if row['question']:
        assert row['question'] in report
    assert data['materials'][11]['finish'] == 'M_Glass_01 (KPP convention)'
    assert data['materials'][8]['ral'] == '9016'
    assert data['materials'][9]['ral'] == '7004'
    assert data['materials'][2]['map_type'] == 'solid'
    assert data['scene']['layer_correspondence'] == 'confirmed by operator: actual census layer names govern'
    assert data['scene']['actual_layer'] == '007'
    assert data['scene']['collision_objects'] == 21
    assert len(data['scene']['objects']) == 23
    assert data['scene']['unmapped_ids'] == []
    assert sum(r['polygons'] for r in data['materials']) == data['scene']['render_polygons']
    assert sum(r['triangles'] for r in data['materials']) == data['scene']['render_triangles']
    assert data['scene']['id_gaps'] == []
