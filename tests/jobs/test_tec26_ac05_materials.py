"""new-case: AC05 Gate-1 evidence inventory, not production-model acceptance."""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JOB = ROOT / 'jobs/TEC26-OKS/AC05'


def test_ac05_gate1_inventory_preserves_measured_ids_and_unknowns():
    path = JOB / 'materials.json'
    assert path.is_file(), 'AC05 Gate-1 materials evidence is missing'
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['gate1']['status'] == 'awaiting_user'
    assert data['gate1']['approved'] is False
    assert data['passed'] is False
    assert data['building_name'] == 'Блок-модуль пенного пожаротушения'
    assert data['scene']['layer'] == '005'
    assert data['scene']['mesh']['handle'] == 161
    assert [c['handle'] for c in data['scene']['collision_candidates']] == [344, 345]
    rows = data['materials']
    assert [r['id'] for r in rows] == list(range(1, 11))
    expected = {1: (127, 254, 82.98113025259933),
                2: (22, 44, 56.48439932962852),
                3: (476, 990, 6.699798207317762),
                4: (1, 2, 4.313754850037867)}
    for row in rows:
        assert row['status'] != 'approved'
        if row['id'] in expected:
            assert row['status'] == 'proposed'
            assert row['ral'] == ('5015' if row['id'] <= 2 else '7004')
            assert row['map_type'] in {'solid', 'metal'}
            assert row['question_id'] in {q['id'] for q in data['gate1']['questions']}
        else:
            assert row['finish'] == '?'
            assert row['status'] == 'unused'
        if row['id'] in expected:
            faces, triangles, area = expected[row['id']]
            assert row['poly_faces'] == faces
            assert row['triangles'] == triangles
            assert math.isfinite(row['area_m2'])
            assert math.isclose(row['area_m2'], area, abs_tol=1e-10)
        else:
            assert row['triangles'] == row['poly_faces'] == row['area_m2'] == 0
    assert sum(r['triangles'] for r in rows) == 1290
    assert sum(r['poly_faces'] for r in rows) == 626
    assert {r['ral'] for r in data['drawing_finishes'] if r['ral']} == {'5015', '7004'}
    for finish in data['drawing_finishes']:
        assert finish['evidence']
    for source in data['sources']:
        assert len(source['sha256']) == 64
        int(source['sha256'], 16)
    assert data['evidence']['contact_sheet'].startswith('G:/Мой диск/AGR-evidence/tec26-oks/AC05/')
    report = (JOB / 'MATERIALS.md').read_text(encoding='utf-8')
    assert 'not a delivery acceptance' in report
    assert '276D52' in report
    assert '-2.004332' in report
