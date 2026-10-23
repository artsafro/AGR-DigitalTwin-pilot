"""new-case: AC08 Gate-1 evidence coverage without implicit material approval."""
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
JOB = ROOT / 'jobs/TEC26-OKS/AC08'


def load():
    return json.loads((JOB / 'materials.json').read_text(encoding='utf-8'))


def test_gate_remains_unapproved():
    data = load()
    assert data['gate'] == {'stage': 1, 'status': 'awaiting_artem', 'approved': False}
    assert data['building_name'] == 'Контейнер низковольтных комплектных устройств (НКУ)'
    assert data['production_outputs'] == []


@pytest.mark.parametrize('mid,triangles,faces,area', [
    (1, 254, 127, 60.50952526944401),
    (2, 30, 15, 35.3280560120449),
    (3, 64, 38, 1.6974531660811787),
])
def test_census_coverage(mid, triangles, faces, area):
    data = load()
    row = next(x for x in data['materials'] if x['id'] == mid)
    assert row['triangles'] == triangles
    assert row['poly_faces'] == faces
    assert row['area_m2'] == pytest.approx(area, abs=1e-10)
    assert row['evidence']
    assert all(x in data['evidence'] for x in row['evidence'])


def test_no_slot_or_face_silently_dropped():
    data = load()
    assert [x['id'] for x in data['materials']] == [1, 2, 3]
    assert data['scene']['unused_populated_ids'] == [4, 5]
    assert data['scene']['empty_ids'] == [6, 7, 8, 9, 10]
    assert sum(x['triangles'] for x in data['materials']) == 348
    assert sum(x['poly_faces'] for x in data['materials']) == 180
    assert data['scene']['mesh_handle'] == 172
    assert data['scene']['collision_handle'] == 343
    assert data['scene']['layer'] == '008'


def test_unknown_mixed_id_has_exact_question_not_default_colour():
    data = load()
    row = data['materials'][0]
    assert row['finish'] == '?'
    assert row['ral'] is None and row['rgb_srgb'] is None
    assert row['status'] == 'unresolved_mixed_id'
    assert row['question'] in data['questions']
    assert 'roof' in row['geometry_role'] and 'foundation' in row['geometry_role']


@pytest.mark.parametrize('mid,ral,rgb,tile', [
    (2, '5015', [34, 113, 179], 1013),
    (3, '7004', [150, 153, 146], 1010),
])
def test_proposals_reuse_exact_solid_kpp_pixels(mid, ral, rgb, tile):
    data = load()
    row = next(x for x in data['materials'] if x['id'] == mid)
    assert row['ral'] == ral and row['rgb_srgb'] == rgb
    assert row['kpp_tile'] == tile
    assert row['status'] == 'proposed'
    assert row['map_type'] == 'solid'
    assert len(row['kpp_sha256']) == 64


def test_manifest_cites_files_and_untrusted_recovery():
    data = load()
    assert data['drawing']['sha256'] == 'cb90ed375df4fd708b7a69c6d018600347953245f0f6bde396f394bee3e1fa52'
    assert data['drawing']['recovery_fixes'] == 2
    assert data['drawing']['native_plot_verified'] is False
    assert len(data['evidence_files']) >= 8
    assert all(len(x['sha256']) == 64 and x['bytes'] > 0 for x in data['evidence_files'])
    assert data['contact_sheet'].endswith('/contact-sheet.png')
    assert (JOB / 'MATERIALS.md').is_file()
