"""new-case: unified library cleanliness contracts, independent of delivery certification."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / 'tools/library/check_library.py'


def write_bundle(tmp_path):
    import hashlib
    doc = catalogue()
    for i, (root, row) in enumerate([(tmp_path, doc['showcase']),
                                   (tmp_path, doc['inputs'][0]),
                                   *[(tmp_path, v) for v in doc['assets'][0]['variants'].values()]]):
        p = root / row['path']
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(f'synthetic fixture {i}'.encode())
        row['sha256'] = hashlib.sha256(p.read_bytes()).hexdigest()
    p = tmp_path / 'catalogue.json'
    p.write_text(json.dumps(doc))
    return p, doc


def test_check_reads_every_variant_and_detects_mutation(tmp_path):
    p, doc = write_bundle(tmp_path)
    seen = []
    def inspect(paths):
        seen.extend(paths)
        return {str(path): clean_scene() if path.name == 'npm.blend' else {
            **clean_scene(), 'objects': [{**clean_scene()['objects'][0], 'name': 'WIN-01_vpm_frame'}]}
                for path in paths}
    module = checker()
    result = module.check(p, tmp_path, tmp_path, inspect)
    assert result['cleanliness'] == 'pass' and result['variants_checked'] == 2
    assert len(seen) == 2
    def extra_during_read(paths):
        raw = inspect(paths)
        extra = tmp_path/'assets/clobbered.partial'
        extra.write_bytes(b'new unexpected file')
        return raw
    with pytest.raises(ValueError, match='changed'):
        module.check(p, tmp_path, tmp_path, extra_during_read)
    (tmp_path/'assets/clobbered.partial').unlink()
    def changed(paths):
        raw = inspect(paths)
        paths[0].write_bytes(b'changed during native readback')
        return raw
    with pytest.raises(ValueError, match='changed'):
        module.check(p, tmp_path, tmp_path, changed)


@pytest.mark.parametrize('change', ['hardlink', 'traversal', 'stale', 'extra', 'missing', 'partial_native'])
def test_files_and_readback_fail_closed(tmp_path, change):
    import os
    p, doc = write_bundle(tmp_path)
    v = doc['assets'][0]['variants']
    if change == 'hardlink':
        (tmp_path/v['vpm']['path']).unlink()
        os.link(tmp_path/v['npm']['path'], tmp_path/v['vpm']['path'])
        v['vpm']['sha256'] = v['npm']['sha256']
    elif change == 'traversal':
        doc['showcase']['path'] = '../escape.png'
    elif change == 'stale':
        (tmp_path/v['npm']['path']).write_bytes(b'stale')
    elif change == 'extra':
        (tmp_path/'assets/extra.blend').write_bytes(b'extras')
    elif change == 'missing':
        (tmp_path/v['vpm']['path']).unlink()
    p.write_text(json.dumps(doc))
    with pytest.raises(ValueError):
        checker().check(p, tmp_path, tmp_path, lambda paths: {})


def test_empty_catalogue_fails_closed(tmp_path):
    path = tmp_path / 'catalogue.json'
    path.write_text(json.dumps({'schema': 'agr-library/1', 'library': 'windows', 'assets': []}))
    result = subprocess.run([sys.executable, str(CHECKER), str(path), '--root', str(tmp_path)],
                            capture_output=True, text=True)
    assert result.returncode == 1, result.stderr
    assert 'assets' in result.stdout


def checker():
    spec = importlib.util.spec_from_file_location('library_checker_test', CHECKER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clean_scene():
    return {'units': 'METRIC', 'scale_length': 1, 'orphans': [], 'unsupported': [],
            'objects': [{'name': 'WIN-01_npm_frame', 'type': 'MESH',
                         'location': [0, 0, 0], 'rotation': [0, 0, 0], 'scale': [1, 1, 1],
                         'hidden': False, 'parent': None, 'modifiers': [], 'constraints': [],
                         'triangles': 2, 'bounds': [[0, 0, 0], [1, 0, 2]],
                         'materials': [{'id': 1, 'name': 'matid_1'}], 'unused_slots': [],
                         'uv_layers': 1, 'uv_finite': True, 'degenerate_faces': 0,
                         'loose_vertices': 0, 'duplicate_faces': 0, 'min_vertex_distance_m': 1}]}


def variant():
    return {'objects': ['WIN-01_npm_frame'], 'triangles': 2, 'size_m': [1, 0, 2],
            'materials': [{'id': 1, 'name': 'matid_1'}]}


def test_clean_scene_passes():
    assert checker().scene_errors(clean_scene(), variant(), 'bottom-left') == []


def catalogue():
    v = {**variant(), 'path': 'assets/WIN-01/npm.blend', 'sha256': 'a'*64}
    return {'schema': 'agr-library/1', 'library': 'windows', 'version': 'v001',
            'pivot': 'bottom-left', 'inputs': [{'path': 'library/windows/window_types.json', 'sha256': 'b'*64}],
            'showcase': {'path': 'previews/sheet.png', 'sha256': 'c'*64},
            'assets': [{'id': 'WIN-01', 'name': 'Window', 'status': 'ready', 'confirmation': 'unconfirmed',
                        'source': {'record': 'WIN-01'}, 'reason': [], 'preview_cell': 1,
                        'variants': {'npm': v, 'vpm': {**v, 'path': 'assets/WIN-01/vpm.blend',
                                                     'objects': ['WIN-01_vpm_frame']}}}]}


def test_catalogue_schema_and_unique_ids():
    module = checker()
    module.validate_catalogue(catalogue())
    doc = catalogue()
    doc['assets'].append(doc['assets'][0])
    with pytest.raises(ValueError, match='duplicate id'):
        module.validate_catalogue(doc)


@pytest.mark.parametrize('change', ['empty', 'partial', 'unsupported', 'nan', 'inf', 'zero', 'quarantine', 'unknown'])
def test_invalid_catalogue_fails(change):
    doc = catalogue()
    asset = doc['assets'][0]
    if change == 'empty':
        doc['assets'] = []
    elif change == 'partial':
        del asset['variants']['vpm']
    elif change == 'unsupported':
        doc['schema'] = 'agr-library/99'
    elif change in ('nan', 'inf', 'zero'):
        asset['variants']['npm']['triangles'] = {'nan': float('nan'), 'inf': float('inf'), 'zero': 0}[change]
    elif change == 'quarantine':
        asset['status'] = 'quarantine'
    else:
        asset['surprise'] = True
    with pytest.raises(ValueError):
        checker().validate_catalogue(doc)


@pytest.mark.parametrize('status', ['fail', 'review', 'not_run', 'unknown'])
def test_nonpass_status_is_not_a_ready_asset(status):
    doc = catalogue()
    doc['assets'][0]['status'] = status
    with pytest.raises(ValueError):
        checker().validate_catalogue(doc)


def test_generated_combined_dirty_inventory_probe():
    import copy
    mutations = [('location', [0.001, 0, 0]), ('rotation', [0, 0.01, 0]), ('hidden', True),
                 ('scale', [2, 1, 1]), ('modifiers', ['Bevel']), ('unused_slots', [0]),
                 ('uv_layers', 0), ('duplicate_faces', 1), ('min_vertex_distance_m', 0.002),
                 ('materials', [{'id': 999, 'name': 'unmapped'}])]
    module = checker()
    # Exhaust all 1024 presence subsets, including the clean/reset control.
    for mask in range(1 << len(mutations)):
        scene = copy.deepcopy(clean_scene())
        for bit, (field, value) in enumerate(mutations):
            if mask & (1 << bit):
                scene['objects'][0][field] = value
        assert bool(module.scene_errors(scene, variant(), 'bottom-left')) == bool(mask), mask


def test_json_duplicate_and_nonfinite_rejected(tmp_path):
    p = tmp_path / 'bad.json'
    for text in ['{"assets": [], "assets": [1]}', '{"value": NaN}', '{"value": 1e999}']:
        p.write_text(text)
        with pytest.raises(ValueError):
            checker().load_json(p)


@pytest.mark.parametrize('field,value', [
    ('type', 'EMPTY'), ('location', [0.001, 0, 0]), ('rotation', [0, 0, 0.01]),
    ('scale', [1, 2, 1]), ('hidden', True), ('parent', 'helper'), ('modifiers', ['Bevel']),
    ('constraints', ['Copy']), ('triangles', 3), ('unused_slots', [1]), ('uv_layers', 0),
    ('uv_finite', False), ('degenerate_faces', 1), ('loose_vertices', 1), ('duplicate_faces', 1),
    ('min_vertex_distance_m', 0.002), ('min_vertex_distance_m', float('nan')),
    ('materials', [{'id': True, 'name': 'matid_1'}]),
    ('materials', [{'id': 1.0, 'name': 'matid_1'}]),
    ('materials', [{'id': 999, 'name': 'unknown'}]), ('bounds', [[0, 0, 0], [1, 0, float('nan')]]),
])
def test_dirty_object_is_named(field, value):
    scene = clean_scene()
    scene['objects'][0][field] = value
    errors = checker().scene_errors(scene, variant(), 'bottom-left')
    assert errors and 'WIN-01_npm_frame' in ' '.join(errors)


@pytest.mark.parametrize('change', ['extra', 'empty', 'orphan', 'units', 'partial', 'unsupported', 'duplicate'])
def test_scene_rejects_extras_and_partial(change):
    scene = clean_scene()
    if change == 'extra':
        scene['objects'].append({**scene['objects'][0], 'name': 'stray'})
    elif change == 'duplicate':
        scene['objects'].append(scene['objects'][0])
    elif change == 'empty':
        scene['objects'] = []
    elif change == 'orphan':
        scene['orphans'] = ['materials:unused']
    elif change == 'units':
        scene['scale_length'] = 0.001
    elif change == 'partial':
        del scene['objects'][0]['hidden']
    else:
        scene['unsupported'] = ['linked_library']
    assert checker().scene_errors(scene, variant(), 'bottom-left')
