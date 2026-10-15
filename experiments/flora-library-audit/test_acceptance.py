"""Synthetic acceptance probes for parser, row policy and resumable archives."""
import json
import pytest
import catalogue as mod
from checkpoints import load_valid, save, sha


def parse_label(text):
    assert hasattr(mod, 'parse_label'), 'label parser must expose structured dimensions'
    return mod.parse_label(text)


def row_pair(*args):
    assert hasattr(mod, 'row_pair'), 'row-aware matcher must retain 20pct ties'
    return mod.row_pair(*args)


def percentile90(values):
    assert hasattr(mod, 'percentile90'), 'budget must include p90'
    return mod.percentile90(values)


def test_label_parser_type_profiles_and_dimensions():
    p = parse_label('Tree Oak NPM height 4 m crown 250 cm')
    assert p['type'] == 'tree' and p['profiles'] == ['NPM']
    assert p['height_m'] == 4 and p['width_m'] == 2.5
    assert parse_label('Куст Сирень ВПМ H150')['type'] == 'bush'
    assert parse_label('hedge VPM h=1.5m width=0.8m')['width_m'] == .8
    assert parse_label('Unknown label')['height_m'] is None
    assert parse_label('LP -> HP')['profiles'] == ['NPM', 'VPM']


def n(h, x, y, z=0.):
    return {'handle': h, 'position': [x, y, z]}


def test_row_right_first_20pct_and_fallback():
    label = n(10, 0, 0)
    assert row_pair(label, [n(1, -1, 0), n(2, 2, 0), n(3, 2.3, 0)], 'xy', 5)['handles'] == [2, 3]
    assert row_pair(label, [n(1, -1, 0), n(2, 2, 4)], 'xy', 5)['handles'] == [1]
    assert row_pair(label, [n(1, 50, 0)], 'xy', 5)['handles'] == []
    # XZ display cards put their labels at the pivot, not to the left.
    assert row_pair(n(10, 10, 8, -3.4), [n(1, 10, 10, 0), n(2, 10, 10, -3)], 'xz', 3)['handles'] == [2]


def test_p90_nearest_rank():
    assert percentile90(list(range(1, 11))) == 9
    assert percentile90([]) is None


def test_checkpoint_skips_only_hash_verified_receipts(tmp_path):
    entry = {'id': 'synthetic-001', 'source_name': 'synthetic'}
    path = tmp_path / 'row.json'
    assert load_valid(path, entry, 'sourcehash') is None
    asset, image = tmp_path / 'asset.fbx', tmp_path / 'preview.svg'
    asset.write_bytes(b'synthetic - NOT a real FBX')
    image.write_text('<svg/>')
    row = dict(id=entry['id'], name=entry['source_name'], source_sha256='sourcehash',
               file=str(asset), sha256=sha(asset), preview=str(image), preview_sha256=sha(image))
    save(path, row)
    assert load_valid(path, entry, 'sourcehash') == row
    with pytest.raises(ValueError):
        load_valid(path, entry, 'changedsource')
    for i in range(30):
        asset.write_bytes(f'changed {i}'.encode())
        with pytest.raises(ValueError):
            load_valid(path, entry, 'sourcehash')


def test_generated_no_binary_diff_probe(tmp_path):
    from verify_archive import inspect_paths
    (tmp_path / 'okay.json').write_text('{}')
    assert inspect_paths(['okay.json'], tmp_path) == ['okay.json']
    for extension in ['max', 'fbx', 'png', 'svg', 'tga', 'tiff', 'jpg']:
        name = 'forbidden.' + extension
        (tmp_path / name).write_bytes(b'synthetic artifact')
        with pytest.raises(AssertionError):
            inspect_paths([name], tmp_path)
    (tmp_path / 'disguised.txt').write_bytes(b'not\x00text')
    with pytest.raises(AssertionError):
        inspect_paths(['disguised.txt'], tmp_path)


def test_generated_competing_labels_and_accounting():
    from collections import Counter
    for shift in range(-10, 11):
        plant = dict(n(1, shift, 10, 0), name='synthetic_plant', **{'class': 'Editable_Mesh'},
                     triangles=2, vertices=4, uv_vertices=4, hidden=False, bbox=[[0,0,0],[1,1,1]])
        labels = [dict(n(2, shift, 10, -.2), name='caption-a', **{'class':'text'}, text='Oak', hidden=False),
                  dict(n(3, shift, 10, -.3), name='caption-b', **{'class':'text'}, text='Pine', hidden=False),
                  dict(n(4, shift, 10, -99), name='orphan', **{'class':'text'}, text='4K', hidden=False)]
        scene = mod.make_catalogue({'objects': [plant] + labels, 'unit_in_m': 1})
        counts = Counter(l['status'] for l in scene['labels'])
        assert counts == {'ambiguous': 2, 'unpaired': 1}
        assert sum(counts.values()) == len(labels)
        labels[-1]['text'] = 'Unmatched species'
        scene = mod.make_catalogue({'objects': [plant] + labels, 'unit_in_m': 1})
        assert scene['labels'][-1]['status'] == 'ambiguous'
        assert scene['labels'][-1]['ambiguity_reasons'] == ['no_mesh_within_threshold']


def test_generated_original_hash_probe(tmp_path):
    import shutil
    source = tmp_path / 'synthetic-reference.max'
    copy = tmp_path / 'copy.max'
    source.write_bytes(b'SYNTHETIC reference bytes, not a scene')
    before = sha(source)
    shutil.copy2(source, copy)
    assert sha(copy) == before
    for i in range(30):
        copy.write_bytes(str(i).encode())
        assert sha(copy) != before
        assert sha(source) == before


def test_snapshot_world_coordinates_are_not_transformed_twice(monkeypatch):
    import sys
    import types
    import importlib.util
    from pathlib import Path
    class P:
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z
        def __mul__(self, offset):
            return P(self.x + offset, self.y, self.z)
    points = [P(10,0,0), P(11,0,0), P(10,1,0)]
    fake = types.SimpleNamespace(snapshotAsMesh=lambda o:None, getNumVerts=lambda m:3,
        getVert=lambda m,i:points[i-1], getNumTVerts=lambda m:0, getNumFaces=lambda m:1,
        getFace=lambda m,i:P(1,2,3), getFaceMatID=lambda m,i:1, delete=lambda m:None,
        units=types.SimpleNamespace(SystemType='meters', SystemScale=1))
    monkeypatch.setitem(sys.modules, 'pymxs', types.SimpleNamespace(runtime=fake))
    spec = importlib.util.spec_from_file_location('synthetic_fbx', Path(__file__).with_name('export_fbx.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = module.mesh_data(types.SimpleNamespace(transform=10, material=None))
    assert data['triangles'][0]['corners'] == [[10.,0.,0.],[11.,0.,0.],[10.,1.,0.]]


def test_species_comparison_retains_cultivars_and_yo():
    assert mod.portable('C:\\x\\t_366e8d9d\\out\\asset.fbx') == 'out/asset.fbx'
    assert mod.portable('C:\\Users\\artsafro\\Desktop\\source.max') == '<USER>/Desktop/source.max'
    assert mod.species_keys({'id':'library-001', 'species_labels':['Липа\nмелколистная']}) == {'липа мелколистная'}
    assert mod.species_keys({'id':'project-001', 'species_labels':['Клён Гиннала (Acer) H175\nКлен татарский H175']}) == {'клен гиннала', 'клен татарский'}
