"""new-case: synthetic atlas-ID recovery and fail-closed UDIM preflight (#1630)."""
import importlib
import math

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
