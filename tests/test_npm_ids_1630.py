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


import subprocess
import sys
import os


@pytest.mark.parametrize('case', ['empty', 'partial', 'nan', 'inf', 'unmapped', 'duplicate', 'unsupported'])
def test_fresh_cli_invalid_inputs_preserve_bytes(tmp_path, case):
    from tools.derive import npm_ids as cmd
    atlas = tmp_path/'atlas.png'; Image.new('RGB', (64,64),'red').save(atlas)
    doc = synthetic_document(atlas)
    if case == 'empty': doc = {}
    elif case == 'partial': doc['objects'][0]['tri_polygons'] = []
    elif case in ('nan','inf'): doc['objects'][0]['uvs'][0][0] = float(case)
    elif case == 'unmapped': doc['objects'][0]['polygons'][0]['slot'] = 9
    elif case == 'duplicate': doc['objects'].append(copy.deepcopy(doc['objects'][0]))
    source = tmp_path/('input.txt' if case == 'unsupported' else 'input.json')
    source.write_text(json.dumps(doc))
    before = (source.read_bytes(), atlas.read_bytes())
    run = subprocess.run([sys.executable, '-m', 'dt_ai.cli.agr', 'npm-ids', str(source), str(tmp_path/'new')],
                         cwd=tmp_path, capture_output=True, text=True)
    assert run.returncode != 0, (run.stdout,run.stderr)
    assert not (tmp_path/'new').exists()
    assert (source.read_bytes(),atlas.read_bytes()) == before


def test_polygon_triangle_uv_disagreement_rejected_before_segmentation(tmp_path, monkeypatch):
    from tools.derive import npm_ids as cmd
    doc=synthetic_document(tmp_path/'absent.png')
    doc['objects'][0]['uvs'][0]=[.15,.15]
    monkeypatch.setattr(cmd,'recover',lambda *a,**k: pytest.fail('inconsistent UV protocol reached segmentation'))
    with pytest.raises(ValueError,match='UV'):
        cmd.process_document(doc)


def test_fresh_cli_positive_stale_output_and_path_aliases(tmp_path):
    atlas=tmp_path/'atlas.png'; Image.new('RGB',(64,64),'red').save(atlas)
    source=tmp_path/'input.json'; source.write_text(json.dumps(synthetic_document(atlas)))
    command=[sys.executable,'-m','dt_ai.cli.agr','npm-ids',str(source)]
    output=tmp_path/'new'
    run=subprocess.run([*command,str(output)],cwd=tmp_path,capture_output=True,text=True)
    assert run.returncode == 0,(run.stdout,run.stderr)
    receipt=(output/'id_table.json').read_bytes()
    assert json.loads(receipt)['status']=='ok'
    assert json.loads((output/'mesh_ids.json').read_text())['objects'][0]['mat_ids']==[1]
    for dest in [output,source,tmp_path/'./input.json']:
        run=subprocess.run([*command,str(dest)],cwd=tmp_path,capture_output=True,text=True)
        assert run.returncode == 2
        assert (output/'id_table.json').read_bytes()==receipt
    alias=tmp_path/'alias.json'; os.link(source,alias)
    assert subprocess.run([*command,str(alias)],cwd=tmp_path,capture_output=True).returncode == 2


def test_generated_face_accounting_and_repeat_reset(tmp_path):
    from tools.library.npm_ids import recover
    atlas=tmp_path/'atlas.png'; Image.new('RGB',(64,64),'red').save(atlas)
    faces=[]
    for i in range(1,31):
        x=i/64
        faces.append([[x,.2],[x+.01,.2],[x,.21]])
    faces.extend([[[1.1,.2],[1.2,.2],[1.1,.3]],[[.9,.2],[1.1,.2],[.9,.3]]])
    first=recover(atlas,faces)
    buckets=[{i for i,mid in enumerate(first['mat_ids']) if mid}, *[set(first[k]) for k in ('straddling','unassigned','ambiguous')]]
    assert sum(map(len,buckets)) == len(set.union(*buckets)) == len(faces)
    assert first == recover(atlas,faces)
    assert recover(atlas,faces[:30])['status'] == 'ok'


def test_competing_publisher_cannot_clobber_inputs(tmp_path,monkeypatch):
    from tools.derive import npm_ids as cmd
    atlas=tmp_path/'atlas.png'; Image.new('RGB',(64,64),'red').save(atlas)
    source=tmp_path/'input.json'; source.write_text(json.dumps(synthetic_document(atlas)))
    original=source.read_bytes(); output=tmp_path/'new'
    real=Path.mkdir
    def racing_mkdir(self,*args,**kwargs):
        result=real(self,*args,**kwargs)
        if self == output:
            os.link(source,output/'mesh_ids.json')
        return result
    monkeypatch.setattr(Path,'mkdir',racing_mkdir)
    assert cmd.main([str(source),str(output)]) == 2
    assert source.read_bytes()==original
    assert not (output/'id_table.json').exists()


def test_scenario_has_shared_stage_chain():
    root = Path(__file__).resolve().parents[1]
    skeletons = json.loads((root/'docs/agents/skeletons.json').read_text(encoding='utf-8'))
    assert skeletons['cells']['npm-to-vpm']['stages'] == [
        'npm-ids', 'npm-udim-fit', 'npm-to-vpm', 'readback', 'checker', 'package-vpm', 'validate']
    for sid in ('npm-ids', 'npm-udim-fit', 'npm-to-vpm'):
        assert skeletons['stages'][sid]['gap'] is None


def test_native_approved_drop_preserves_surviving_uv_and_geometry(tmp_path):
    from dt_ai.core.blender_runner import run_blender
    blender = Path('C:/Program Files/Blender Foundation/Blender 5.1/blender.exe')
    if not blender.is_file():
        pytest.skip('native Blender 5.1 unavailable')
    root = Path(__file__).resolve().parents[1]
    script = tmp_path/'native.py'
    script.write_text('''import sys, json
from pathlib import Path
import bpy
sys.path.insert(0, ROOT)
from tools.blender.npm_ids import apply
bpy.ops.wm.read_factory_settings(use_empty=True)
mesh=bpy.data.meshes.new('Synthetic'); mesh.from_pydata([(0,0,0),(1,0,0),(0,1,0),(2,0,0)],[],[(0,1,2),(0,3,1)])
uv=mesh.uv_layers.new()
for i, p in enumerate([(0,0),(1,0),(0,1),(0,0),(1,0),(0,1)]): uv.data[i].uv=p
obj=bpy.data.objects.new('Synthetic',mesh); bpy.context.collection.objects.link(obj)
before=[list(v.co) for v in mesh.vertices]
apply({'objects':[{'name':'Synthetic','mat_ids':[1], 'source_polygons':[0],
    'polygons':[{'uv':[[0,0],[1,0],[0,1]],'slot':0}], 'local':before}]}, Path(OUT)/'ids.blend')
assert len(obj.data.polygons)==1
assert [list(v.co) for v in obj.data.vertices]==before
assert [list(v.uv) for v in obj.data.uv_layers.active.data]==[[0,0],[1,0],[0,1]]
assert obj.data.polygons[0].material_index==1
Path(OUT,'readback.json').write_text(json.dumps({'status':'ok'}))
'''.replace('ROOT', repr(str(root))).replace('OUT', repr(str(tmp_path))), encoding='utf-8')
    assert run_blender(script, [], executable=str(blender), output_json=tmp_path/'readback.json',
                       log_path=tmp_path/'native.log')['status'] == 'ok'


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
