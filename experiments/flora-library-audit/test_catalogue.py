"""Synthetic regression probes for the standalone Flora audit, not production QA."""
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location('flora_catalogue', Path(__file__).with_name('catalogue.py'))
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def node(handle, x, y, z):
    return {'handle': handle, 'position': [x, y, z]}


def test_front_labels_use_xz_not_xy():
    meshes = [node(1, 10, 10, 0), node(2, 10, 10, -3)]
    assert mod.pair(node(3, 10, 8.75, -3.4), meshes, 'xz') == [2]
    assert mod.pair(node(3, 10, 8.75, -3.4), meshes, 'xy') == [1, 2]


def test_ties_report_all_candidates_not_first():
    assert mod.pair(node(3, 0, 0, 0), [node(2, 1, 0, 0), node(1, -1, 0, 0)], 'xz') == [1, 2]


def test_empty_and_far_unpaired():
    assert mod.pair(node(3, 0, 0, 0), [], 'xz') == []
    assert mod.pair(node(3, 0, 0, 0), [node(1, 500, 0, 0)], 'xz', max_distance=5) == []


def test_generated_order_invariance():
    for x in range(-20, 21):
        meshes = [node(1, x, 10, 0), node(2, x, 10, -3)]
        label = node(3, x, 8, -3.4)
        assert mod.pair(label, meshes, 'xz') == mod.pair(label, meshes[::-1], 'xz') == [2]


def test_dimensions_are_world_bbox_meters():
    assert mod.dimensions({'bbox': [[-1, -2, -0.1], [1, 2, 3.9]]}, 1) == [2, 4, 4]
    assert mod.dimensions({'bbox': [[0, 0, 0], [100, 200, 300]]}, 100) == [1, 2, 3]


def test_profile_preserves_uncertain_and_raw_tokens():
    assert mod.profiles('LP -> HP') == ['NPM', 'VPM']
    assert mod.profiles('HP') == ['VPM']
    assert mod.profiles('LP') == ['NPM']
    assert mod.profiles('unknown') == []


def test_fresh_outputs_cannot_escape_or_overwrite(tmp_path):
    assert mod.fresh_path(tmp_path, 'item.max') == tmp_path / 'item.max'
    (tmp_path / 'item.max').touch()
    with pytest.raises(FileExistsError):
        mod.fresh_path(tmp_path, 'item.max')
    for name in ['../source.max', 'C:/source.max', '/source.max', 'nested/item.max', '..\\source.max']:
        with pytest.raises(ValueError):
            mod.fresh_path(tmp_path, name)


def test_real_catalogue_accounts_for_every_node_and_label():
    import json
    data = json.loads(Path(__file__).with_name('catalogue.json').read_text(encoding='utf-8'))
    assert [sum(s['counts'].values()) for s in data['scenes']] == [506, 69]
    assert [len(s['labels']) for s in data['scenes']] == [326, 23]
    entries = [e for s in data['scenes'] for e in s['entries']]
    assert len(entries) == len({e['id'] for e in entries}) == 136
    assert not data['delivery_passed']
    for scene in data['scenes']:
        handles = {e['source_handle'] for e in scene['entries']}
        assert len({l['handle'] for l in scene['labels']}) == len(scene['labels'])
        for label in scene['labels']:
            assert label['bbox'] is not None
            assert label['parsed']['raw'] == label['text']
            assert set(label['candidate_handles']) <= handles
            if len(label['candidate_handles']) > 1:
                assert label['status'] == 'ambiguous'
        for entry in scene['entries']:
            assert entry['delivery_passed'] is False
            assert Path(entry['planned_file']).name == entry['id'] + '.fbx'
            assert Path(entry['planned_preview']).name == entry['id'] + '.svg'
            assert entry['artifact_status'] in ('not_produced', 'produced_unverified', 'readback_equal', 'readback_mismatch')
            if entry['file'] is None:
                assert entry['artifact_status'] == 'not_produced'
            else:
                assert entry['file'] == entry['planned_file']
    boxes = [o for o in data['scenes'][0]['excluded_nodes'] if o['role'] == 'display_envelope_unverified']
    assert len(boxes) == 80
    assert all(o['triangles'] == 20 and o['material_name'] == 'Multi_Ground' and o['bbox'][1][2] <= o['position'][2] + .001 for o in boxes)
    for budget in data['proposed_budgets']:
        if budget['type'] == 'hedge':
            assert budget['n'] == 0 and budget['proposed_review_above'] is None


def test_generated_rejected_paths_preserve_original(tmp_path):
    original = tmp_path / 'source.max'
    original.write_bytes(b'synthetic reference, not a MAX scene')
    before = original.read_bytes()
    for i in range(50):
        for name in [f'../{i}/source.max', f'..\\{i}\\source.max']:
            with pytest.raises(ValueError):
                mod.fresh_path(tmp_path, name)
    assert original.read_bytes() == before


def test_envelopes_references_and_textplus_are_not_plants():
    for cls, name, expected in [('PolyMeshObject', 'Box001', 'display_envelope_unverified'),
                                ('Cylinder', '20 cm', 'size_reference'),
                                ('TextPlus', 'Tree', 'label'),
                                ('Editable_Poly', 'MAF_OKS_002_061', 'planter')]:
        assert mod.role({'class': cls, 'name': name, 'triangles': 20}, False) == expected


def test_fbx_corner_matcher_rejects_semantic_and_geometry_loss():
    import copy
    spec = importlib.util.spec_from_file_location('flora_mesh_compare', Path(__file__).with_name('mesh_compare.py'))
    matcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(matcher)
    tri = {'corners': [[0., 0., 0., 0., 0.], [1., 0., 0., 1., 0.], [0., 1., 0., 0., 1.]], 'material': 'leaf'}
    assert matcher.compare([tri], [tri])['equal']
    rotated = dict(tri, corners=tri['corners'][1:] + tri['corners'][:1])
    assert matcher.compare([tri], [rotated])['equal']
    assert not matcher.compare([tri], [])['equal']
    assert not matcher.compare([tri], [dict(tri, material='bark')])['equal']
    assert not matcher.compare([tri], [dict(tri, corners=tri['corners'][::-1])])['equal']
    assert not matcher.compare([tri], [tri, tri])['equal']
    for i in range(1, 42):
        shifted = copy.deepcopy(tri)
        for corner in shifted['corners']:
            corner[0] += i * .001
        assert not matcher.compare([tri], [shifted])['equal']
    moved_uv = copy.deepcopy(tri)
    moved_uv['corners'][0][3] = .1
    assert not matcher.compare([tri], [moved_uv])['equal']
