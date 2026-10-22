"""new-case: AC04 Gate-1 material evidence is complete but never approved automatically."""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'jobs/TEC26-OKS/AC04'


def load():
    return json.loads((ROOT / 'materials.json').read_text(encoding='utf-8'))


def test_ac04_gate_is_pending():
    d = load()
    assert d['gate_1_status'] == 'awaiting_artem'
    assert d['delivery_passed'] is False
    assert d['questions']
    assert all(m['status'] == 'proposed' for m in d['materials'])


def test_ac04_all_ids_and_slots_accounted():
    d = load()
    assert [m['id'] for m in d['materials']] == [1, 2, 3, 4, 5]
    assert d['scene']['empty_slots'] == [6, 7, 8, 9, 10]
    assert sum(m['triangles'] for m in d['materials']) == 5006
    assert sum(m['poly_faces'] for m in d['materials']) == 2552
    assert all(math.isfinite(m['area_m2']) and m['area_m2'] > 0 for m in d['materials'])
    assert len(d['scene']['collision_handles']) == 17


def test_ac04_finish_evidence_and_unknowns():
    d = load()
    for m in d['materials']:
        assert m['evidence'] and m['geometry_evidence']
        if m['finish'] == '?':
            assert m['question_ids']
    assert d['materials'][2]['map_type'] == 'glass'
    assert d['materials'][2]['glass']['npm_opacity'] == 0.5
    assert d['materials'][0]['question_ids']  # mixed roof / base surfaces not silently resolved


def test_ac04_kpp_colours_exact():
    d = load()
    expected = {'RAL5015': [34, 113, 179], 'RAL7004': [150, 153, 146], 'RAL1021': [238, 201, 0]}
    for m in d['materials']:
        if m['ral']:
            assert m['rgb_srgb'] == expected[m['ral']]
            assert len(m['kpp_reference']['sha256']) == 64


def test_ac04_manifest_and_source_provenance():
    d = load()
    assert len(d['base_sha']) == 40
    assert d['scene']['layer'] == '004'
    for s in d['sources']:
        assert len(s['sha256']) == 64
    manifest = json.loads((ROOT / 'evidence.json').read_text(encoding='utf-8'))
    names = [e['filename'] for e in manifest['files']]
    assert len(names) == len(set(names))
    assert {'contact-sheet.png', 'iso.png', 'reverse.png', 'roof.png'} <= set(names)
    assert all(len(e['sha256']) == 64 and e['bytes'] > 0 for e in manifest['files'])
