"""new-case: synthetic atlas-ID recovery and fail-closed UDIM preflight (#1630)."""
import importlib
import math
import copy
import json
from pathlib import Path
import pytest
from PIL import Image


def synthetic_document(atlas):
    return {'objects': [{'name': 'synthetic', 'verts': [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
        'local': [[0, 0, 0], [1, 0, 0], [0, 1, 0]], 'tris': [[0, 1, 2]],
        'uvs': [[.1, .1], [.4, .1], [.1, .4]], 'uv_tris': [[0, 1, 2]], 'tri_polygons': [0],
        'polygons': [{'slot': 0, 'uv': [[.1, .1], [.4, .1], [.1, .4]]}],
        'atlases': {'0': str(atlas)}}]}


@pytest.mark.parametrize('field,value', [('tri_polygons', [-1]), ('tri_polygons', [True]),
    ('tri_polygons', []), ('tris', [[-1, 1, 2]]), ('tris', [[0, 0, 2]]),
    ('uv_tris', [[0, 1, 99]]), ('uv_tris', []), ('verts', [[float('nan'), 0, 0]]),
    ('local', [[0, 0, 0]]), ('tris', []), ('uvs', [[float('inf'), 0]])])
def test_invalid_mesh_protocol_rejected_before_segmentation(tmp_path, field, value, monkeypatch):
    from tools.derive import npm_ids as cmd
    doc = synthetic_document(tmp_path/'absent.png')
    doc['objects'][0][field] = value
    def forbidden(*args, **kwargs):
        pytest.fail('segmentation started on invalid mesh')
    monkeypatch.setattr(cmd, 'recover', forbidden)
    with pytest.raises(ValueError):
        cmd.process_document(doc)


def test_approved_drop_requires_exact_zero_and_accounts_every_face(tmp_path):
    from tools.derive import npm_ids as cmd
    doc = synthetic_document(tmp_path/'synthetic.png')
    obj = doc['objects'][0]
    obj['verts'].append([0, 0, 2]); obj['local'].append([0, 0, 2])
    obj['tris'].append([0, 3, 0]); obj['uv_tris'].append([0, 1, 2])
    obj['tri_polygons'].append(1); obj['polygons'].append(copy.deepcopy(obj['polygons'][0]))
    before = copy.deepcopy(doc)
    cleaned, drops = cmd.drop_zero_area(doc, {'synthetic': [1]})
    assert doc == before
    assert cleaned['objects'][0]['tri_polygons'] == [0]
    assert cleaned['objects'][0]['source_polygons'] == [0]
    assert drops == [{'object': 'synthetic', 'source_polygon': 1, 'reason': 'approved_zero_world_area',
                      'source_triangles': [1]}]
    with pytest.raises(ValueError, match='nonzero'):
        cmd.drop_zero_area(doc, {'synthetic': [0]})
    with pytest.raises(ValueError, match='unknown'):
        cmd.drop_zero_area(doc, {'absent': [1]})


def test_cli_transitive_output_alias_writes_nothing(tmp_path):
    from tools.derive import npm_ids as cmd
    source = tmp_path/'input.json'
    output = tmp_path/'new'
    # Absent transitive input must not be created by mkdir/extraction/reporting.
    source.write_text(json.dumps(synthetic_document(output/'id_table.json')))
    assert cmd.main([str(source), str(output)]) == 2
    assert not output.exists()


def test_cli_late_input_change_never_publishes_success(tmp_path, monkeypatch):
    from tools.derive import npm_ids as cmd
    atlas = tmp_path/'synthetic.png'; Image.new('RGB', (64, 64), 'red').save(atlas)
    source = tmp_path/'input.json'; source.write_text(json.dumps(synthetic_document(atlas)))
    real = cmd.process_document
    def mutate(*args, **kwargs):
        result = real(*args, **kwargs)
        source.write_text('{}')
        return result
    monkeypatch.setattr(cmd, 'process_document', mutate)
    assert cmd.main([str(source), str(tmp_path/'new')]) == 2
    assert not (tmp_path/'new'/'id_table.json').exists()

import pytest
from PIL import Image


def test_synthetic_cells_straddle_empty(tmp_path):
    image = Image.new('RGB', (64, 64))
    for box, color in [((0, 0, 32, 32), 'red'), ((32, 0, 64, 32), 'green'),
                       ((0, 32, 32, 64), 'blue'), ((32, 32, 64, 64), 'white')]:
        image.paste(color, box)
    atlas = tmp_path / 'synthetic.png'
    image.save(atlas)
    core = importlib.import_module('tools.library.npm_ids')
    faces = [[[.1, .9], [.4, .9], [.1, .6]], [[.6, .9], [.9, .9], [.6, .6]],
             [[.1, .4], [.4, .4], [.1, .1]], [[.4, .8], [.6, .8], [.4, .6]]]
    result = core.recover(str(atlas), faces, tolerance_px=.5)
    assert result['mat_ids'] == [1, 2, 3, 0]
    assert result['straddling'] == [3]
    assert result['unassigned'] == []
    assert result['empty_cells'] == [4]
    assert [r['face_count'] for r in result['table']] == [1, 1, 1, 0]
    assert result['status'] == 'manual_required'
    assert sum(r['face_count'] for r in result['table']) + len(result['straddling']) == len(faces)


def test_facade_cells_keep_pattern_seams_inside_material(tmp_path):
    import numpy as np
    from tools.library.maf_atlas_cells import segment
    a = np.zeros((128, 128, 3), dtype=np.uint8)
    for y in range(128):
        for x in range(128):
            base = [45, 95, 155, 210][2*(y >= 64)+(x >= 64)]
            a[y, x] = base - (15 if x % 12 == 0 or y % 17 == 0 else 0)
    p = tmp_path / 'synthetic_facade.png'
    Image.fromarray(a).save(p)
    result = segment(str(p), profile='facade', work=128, min_cell=16)
    assert [(c['x'], c['y'], c['w'], c['h']) for c in result['cells']] == [
        (0, 0, 64, 64), (64, 0, 64, 64), (0, 64, 64, 64), (64, 64, 64, 64)]


def test_facade_uv_coverage_vetoes_false_pattern_cut(tmp_path):
    from tools.library.maf_atlas_cells import segment
    image = Image.new('RGB', (128, 128), (40, 40, 40))
    image.paste((160, 160, 160), (64, 0, 128, 128))
    image.paste((90, 90, 90), (0, 32, 64, 64))  # stripe inside the left material
    p = tmp_path / 'synthetic_uv_facade.png'
    image.save(p)
    bounds = [[4, 4, 60, 120]] * 100 + [[68, 4, 124, 120]] * 100
    r = segment(str(p), profile='facade', work=128, min_cell=16, uv_bounds_px=bounds)
    assert [(c['x'], c['y'], c['w'], c['h']) for c in r['cells']] == [
        (0, 0, 64, 128), (64, 0, 64, 128)]


def test_facade_nonrectangular_interior_is_manual_not_glued(tmp_path):
    from tools.library.maf_atlas_cells import segment
    image = Image.new('RGB', (128, 128), (55, 55, 55))
    image.paste('white', (32, 32, 96, 96))
    p = tmp_path / 'synthetic_interior.png'
    image.save(p)
    result = segment(str(p), profile='facade', work=128, min_cell=16,
                     uv_bounds_px=[[4, 4, 124, 124]])
    assert result['cells'][0]['kind'] == 'mixed'


def test_udim_two_tiles_stops_with_question():
    from adapters.max.agr_tools import npm2vpm_core as core
    mesh = {'verts': [[0, 0, 0], [16, 0, 0], [0, 8, 0]],
            'local': [[0, 0, 0], [16, 0, 0], [0, 8, 0]], 'tris': [[0, 1, 2]],
            'mat_ids': [1], 'uvs': [[0, 0], [1, 0], [0, .5]], 'uv_tris': [[0, 1, 2]]}
    gate = core.udim_fit_gate(mesh, {'w': 4096, 'h': 4096}, target_px_m=512)
    assert gate['status'] == 'blocked'
    assert gate['ids'][0]['needed_tiles_at_512'] == 2
    assert gate['ids'][0]['area_m2'] == 64
    assert '1' in gate['question'] and 'ID' in gate['question']
    assert all(x in gate['question'] for x in ['(a)', '(b)', '(c)', '(d)'])
    assert gate['ids'][0]['fits'] is False


def test_blocked_gate_never_launches_native_apply(tmp_path, monkeypatch):
    from tools.derive import npm_ids as command
    atlas = tmp_path / 'synthetic.png'
    Image.new('RGB', (64, 64), 'red').save(atlas)
    source = tmp_path / 'synthetic.fbx'
    source.write_bytes(b'synthetic; native reader replaced only at subprocess seam')
    doc = {'objects': [{'name': 'synthetic', 'verts': [[0, 0, 0], [16, 0, 0], [0, 8, 0]],
                       'local': [[0, 0, 0], [16, 0, 0], [0, 8, 0]],
                       'uvs': [[0, 0], [1, 0], [0, 1]], 'tris': [[0, 1, 2]],
                       'uv_tris': [[0, 1, 2]], 'tri_polygons': [0],
                       'polygons': [{'uv': [[0, 0], [1, 0], [0, 1]], 'slot': 0}],
                       'atlases': {'0': str(atlas)}}]}
    calls = []
    def native(script, args, **kwargs):
        calls.append(args[0])
        return doc
    monkeypatch.setattr(command, 'run_blender', native)
    assert command.main([str(source), str(tmp_path / 'new')]) == 1
    assert calls == ['extract']
    assert not (tmp_path / 'new' / 'npm_ids.blend').exists()
