"""Synthetic, no-DCC controls for #347 light-variant publication."""
import copy
import importlib.util
import subprocess
import sys

import numpy as np
from PIL import Image
import json
from pathlib import Path

import pytest


def catalogue():
    result = json.loads(Path('library/flora/catalogue.json').read_text(encoding='utf-8'))
    for row in result['species']:
        row.pop('npm_light', None)  # Synthetic fixture starts from the pre-extension catalogue.
    return result


def document(cat):
    variants = []
    for row in cat['species']:
        if row['material_id'] not in {103, 105, 204}:
            continue
        variants.append({
            'material_id': row['material_id'], 'object': row['objects']['NPM'] + '_light',
            'file': 'C:/x/flora-light/v001/flora-npm-light-v001.max', 'sha256': 'a' * 64,
            'fbx': 'C:/x/flora-light/v001/fbx/' + row['objects']['NPM'] + '_light.fbx',
            'fbx_sha256': 'b' * 64, 'triangles': {105:220, 204:32, 103:83}[row['material_id']],
            'height_m': row['height_m'], 'crown_diameter_m': row['crown_diameter_m'],
            'method': 'alpha-aware source triangle subset',
            'maps': {k: row['maps'][k] for k in ('diffuse','opacity')},
            'silhouettes': {v: {'iou': 0.9, 'hausdorff_upper_m': 0.01} for v in ('top','front','side','front45','side45')},
        })
    return {'schema': 'flora-npm-light-v1', 'variants': variants}


def test_missing_readback_triangles_is_rejected():
    # Import inside the test so pre-implementation RED is an assertion, not a collection error.
    assert importlib.util.find_spec('dt_ai.materials.flora_light') is not None, 'light validation feature missing'
    from dt_ai.materials.flora_light import validate_records
    cat = catalogue()
    data = document(cat)
    del data['variants'][0]['triangles']
    with pytest.raises(ValueError, match='triangles'):
        validate_records(cat, data)


@pytest.mark.parametrize('key,value', [
    ('triangles', 0), ('triangles', -1), ('triangles', None), ('triangles', True),
    ('triangles', 10000), ('triangles', float('nan')), ('triangles', float('inf')),
    ('silhouettes', {}), ('silhouettes', None), ('height_m', 0), ('height_m', 100),
    ('height_m', float('nan')), ('crown_diameter_m', float('inf')),
    ('maps', {}), ('material_id', 999), ('object', 'wrong'),
    ('sha256', 'not-a-hash'), ('extra', 'unsupported'),
])
def test_rejects_invalid_evidence(key, value):
    from dt_ai.materials.flora_light import validate_records
    cat = catalogue(); data = document(cat)
    data['variants'][0][key] = value
    with pytest.raises(ValueError):
        validate_records(cat, data)


@pytest.mark.parametrize('metric,value', [('iou', 0.849), ('iou', None), ('iou', float('nan')),
    ('iou', float('inf')), ('hausdorff_upper_m', -1), ('hausdorff_upper_m', 999),
    ('hausdorff_upper_m', float('nan'))])
def test_rejects_bad_per_view_metric(metric, value):
    from dt_ai.materials.flora_light import validate_records
    cat = catalogue(); data = document(cat)
    data['variants'][0]['silhouettes']['top'][metric] = value
    with pytest.raises(ValueError):
        validate_records(cat, data)


@pytest.mark.parametrize('data', [{}, None, [], {'schema': 'other', 'variants': []},
    {'schema': 'flora-npm-light-v1', 'variants': []}])
def test_rejects_empty_partial_or_unsupported_document(data):
    from dt_ai.materials.flora_light import validate_records
    with pytest.raises(ValueError):
        validate_records(catalogue(), data)


def test_exact_geometric_thresholds_are_inclusive():
    from dt_ai.materials.flora_light import validate_records
    cat = catalogue(); data = document(cat)
    for row in data['variants']:
        for metric in row['silhouettes'].values():
            metric.update(iou=0.85, hausdorff_upper_m=0.10 * row['crown_diameter_m'])
    assert validate_records(cat, data) == 62587


def test_append_preserves_every_existing_value_and_rejects_changes():
    from dt_ai.materials.flora_light import append_light
    cat = catalogue(); data = document(cat)
    result = append_light(cat, data, cat)
    for before, after in zip(cat['species'], result['species']):
        assert {k:v for k,v in after.items() if k != 'npm_light'} == before
    assert sum('npm_light' in s for s in result['species']) == 3
    changed = copy.deepcopy(result); changed['species'][0]['note'] = 'changed'
    with pytest.raises(ValueError, match='existing'):
        append_light(changed, data, cat)
    with pytest.raises(ValueError, match='existing'):
        append_light(result, document(cat) | {'variants': [dict(r, triangles=r['triangles']+1) for r in data['variants']]}, result)


def test_output_guard_refuses_existing_and_input_alias(tmp_path):
    from dt_ai.materials.flora_light import guard_output
    source = tmp_path / 'source.max'; source.write_bytes(b'synthetic input')
    for output in (source, tmp_path):
        with pytest.raises(ValueError):
            guard_output(output, [source])
    target = tmp_path / 'fresh'
    guard_output(target, [source])
    assert not target.exists()
    assert source.read_bytes() == b'synthetic input'


def synthetic_mesh():
    # Sloped two-sided quad has non-empty projections in every requested view.
    vertices = [[0,0,0],[1,0,1],[1,1,3],[0,1,2]]
    faces = [[0,1,2],[0,2,3],[2,1,0],[3,2,0]]
    uv = [[[0,0],[1,0],[1,1]],[[0,0],[1,1],[0,1]],[[1,1],[1,0],[0,0]],[[0,1],[1,1],[0,0]]]
    return {'vertices': vertices, 'faces': faces, 'uv': uv}


def test_alpha_subset_keeps_original_geometry_and_removes_redundancy():
    from dt_ai.materials.flora_light import select_faces, measure
    mesh = synthetic_mesh(); opacity = np.full((8,8),255,np.uint8)
    ix = select_faces(mesh, opacity, resolution=32)
    assert 0 < len(ix) < len(mesh['faces'])
    light = dict(mesh, faces=[mesh['faces'][i] for i in ix], uv=[mesh['uv'][i] for i in ix])
    scores = measure(mesh, light, opacity, resolution=128)
    assert all(s['iou'] == 1 for s in scores.values())
    assert all(s['hausdorff_upper_m'] < .05 for s in scores.values())


def test_catalogue_generator_accepts_only_append_only_light_input(tmp_path):
    from dt_ai.materials.flora_catalogue import build, check
    cat = catalogue(); data = document(cat)
    def read(path):
        return json.loads(Path(path).read_text(encoding='utf-8'))
    result = build(read('experiments/flora-library-audit/catalogue.json'),
                   read('library/flora/species-curation.json'), read('library/flora/maps.json'),
                   cat, npm_light=data)
    assert check(result) == []
    assert len([s for s in result['species'] if 'npm_light' in s]) == 3
    bad = copy.deepcopy(result)
    next(s for s in bad['species'] if 'npm_light' in s)['npm_light']['triangles'] = 0
    assert check(bad)


@pytest.mark.parametrize('case', ['missing', 'zero', 'budget', 'silhouette', 'nan'])
def test_cli_rejects_missing_readback_with_nonzero_and_message(tmp_path, case):
    data = document(catalogue())
    row = data['variants'][0]
    if case == 'missing':
        row.pop('triangles'); message = 'triangles'
    elif case in ('zero','budget'):
        row['triangles'] = 0 if case == 'zero' else 10000
        message = 'triangles' if case == 'zero' else 'budget'
    elif case == 'silhouette':
        row['silhouettes'] = {}; message = 'silhouette'
    else:
        row['silhouettes']['top']['iou'] = float('nan'); message = 'IoU'
    bad = tmp_path/'bad.json'; bad.write_text(json.dumps(data))
    result = subprocess.run([sys.executable, '-m', 'dt_ai.materials.flora_light',
        '--catalogue', 'library/flora/catalogue.json', '--input', str(bad)], capture_output=True, text=True)
    assert result.returncode != 0
    assert message in result.stderr


@pytest.mark.parametrize('alias', [False, True])
def test_build_cli_refuses_existing_version_or_source_alias_without_dcc(tmp_path, monkeypatch, alias):
    import tools.flora.build_flora_npm_light as driver
    source = tmp_path/'source.max'; source.write_bytes(b'synthetic source')
    out = source if alias else tmp_path/'v001'
    if not alias:
        out.mkdir(); (out/'existing.max').write_bytes(b'approved output')
    monkeypatch.setattr(driver,'SOURCE',source); monkeypatch.setattr(driver,'OUTPUT',out)
    monkeypatch.setattr(driver,'run',lambda *a,**kw: pytest.fail('DCC called after failed preflight'))
    monkeypatch.setattr(sys,'argv',['build_flora_npm_light','--work',str(tmp_path/'work')])
    with pytest.raises(SystemExit) as error:
        driver.main()
    assert error.value.code == 1
    assert source.read_bytes() == b'synthetic source'
    if not alias:
        assert (out/'existing.max').read_bytes() == b'approved output'
    assert not (tmp_path/'work').exists()


@pytest.mark.parametrize('seed', range(12))
def test_generated_duplicate_triangle_union_invariant(seed):
    from dt_ai.materials.flora_light import select_faces, measure
    mesh = synthetic_mesh(); rng = np.random.default_rng(seed)
    mesh['vertices'] = (np.asarray(mesh['vertices']) * rng.uniform(.8,1.2,3)).tolist()
    opacity = np.full((4,4),255,np.uint8)
    indices = select_faces(mesh, opacity, resolution=32)
    light = dict(mesh, faces=[mesh['faces'][i] for i in indices], uv=[mesh['uv'][i] for i in indices])
    assert all(m['iou'] == 1 for m in measure(mesh,light,opacity,resolution=32).values())


def test_fbx_material_binding_preserves_species_identity_not_slot_number():
    from dt_ai.materials.flora_light import validate_binding
    row = next(s for s in catalogue()['species'] if s['material_id']==103)
    mesh = {'materials': ['Crataegus_mollis_ID103'], 'material_indices':[0],
            'images':[p.replace('/', '\\') for k,p in row['maps'].items() if k in ('diffuse','opacity')]}
    validate_binding(row, mesh)
    mesh['images'][0] = mesh['images'][0].replace('crataegus-mollis','another-species')
    with pytest.raises(ValueError, match='maps'):
        validate_binding(row, mesh)


def test_thin_interior_stem_cannot_disappear_behind_area_iou():
    from dt_ai.materials.flora_light import select_faces, measure
    mesh = synthetic_mesh()
    mesh['vertices'] = (np.asarray(mesh['vertices']) + [0,0,3]).tolist()
    for z in np.linspace(0,3,21)[:-1]:
        i = len(mesh['vertices'])
        y = .2 + z*.1
        mesh['vertices'].extend([[.49,y,z],[.51,y,z],[.51,y+.015,z+.15],[.49,y+.015,z+.15]])
        mesh['faces'].extend([[i,i+1,i+2],[i,i+2,i+3]])
        mesh['uv'].extend([[[0,0],[1,0],[1,1]],[[0,0],[1,1],[0,1]]])
    op = np.full((4,4),255,np.uint8)
    ix = select_faces(mesh,op,resolution=128)
    light = dict(mesh,faces=[mesh['faces'][i] for i in ix],uv=[mesh['uv'][i] for i in ix])
    assert max(m['hausdorff_upper_m'] for m in measure(mesh,light,op,resolution=256).values()) <= .1


def test_exact_budget_boundary_and_one_triangle_over():
    from dt_ai.materials.flora_light import validate_records
    data = document(catalogue())
    counts = next((a,b,(28580-38*a-325*b)//29) for a in range(1,600) for b in range(1,80)
                  if 28580-38*a-325*b > 0 and (28580-38*a-325*b)%29 == 0)
    for row in data['variants']:
        row['triangles'] = dict(zip((105,204,103),counts))[row['material_id']]
    assert validate_records(catalogue(),data) == 70000
    data['variants'][0]['triangles'] += 1
    with pytest.raises(ValueError,match='budget'):
        validate_records(catalogue(),data)


def test_generator_retains_light_records_without_optional_input():
    from dt_ai.materials.flora_catalogue import build, check
    from dt_ai.materials.flora_light import append_light
    cat = catalogue(); previous = append_light(cat,document(cat),cat)
    read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
    result = build(read('experiments/flora-library-audit/catalogue.json'),read('library/flora/species-curation.json'),
                   read('library/flora/maps.json'),previous)
    assert result == previous
    assert not check(result)
    rows = [s for s in result['species'] if 'npm_light' in s]
    rows[0]['npm_light'],rows[1]['npm_light'] = rows[1]['npm_light'],rows[0]['npm_light']
    assert any('another species' in finding for finding in check(result))


def test_transparent_empty_geometry_cannot_pass():
    from dt_ai.materials.flora_light import select_faces
    with pytest.raises(ValueError, match='empty'):
        select_faces(synthetic_mesh(), np.zeros((4,4), np.uint8), resolution=32)
