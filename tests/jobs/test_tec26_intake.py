"""new-case: TEC26 intake regression probes, including a synthetic native Max stub."""
import ast
import copy
import json
import runpy
import pytest
from pathlib import Path
from types import SimpleNamespace

SCRIPT = Path(__file__).resolve().parents[2] / 'jobs/TEC26-OKS/scripts/read_max.py'

def test_bitmap_is_not_queried_as_material():
    tree = ast.parse(SCRIPT.read_text(encoding='utf-8'))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'material')
    bitmap = SimpleNamespace(name='Map #1')
    def reject(_):
        raise RuntimeError('Unable to convert: Map #1:Bitmap to type: Material')
    rt = SimpleNamespace(getHandleByAnim=lambda _: 1, classOf=lambda _: 'Bitmaptexture',
        superClassOf=lambda _: 'textureMap', getPropNames=lambda _: [],
        getNumSubTexmaps=lambda _: 0, getNumSubMtls=reject)
    scope = {'rt': rt}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(SCRIPT), 'exec'), scope)
    assert scope['material'](bitmap)['submaterials'] == []


PUBLISH = SCRIPT.with_name('publish_census.py')
API = runpy.run_path(str(PUBLISH))
CENSUS = SCRIPT.parents[1] / 'census'

@pytest.mark.parametrize('name', ['oks', 'truba', 'kpp'])
def test_real_census_complete_finite_and_all_nodes_classified(name):
    data = json.loads((CENSUS/(name+'.json')).read_text(encoding='utf-8'))
    assert API['validate_scene'](data)
    for node in data['objects']:
        assert node['kind'] == API['classify'](node['name'])
        assert sum(node['poly_faces_by_id'].values()) == sum(node['evaluated_poly_face_degrees'].values())
        if node['kind'] == 'surface':
            assert node['snapshot_bbox_parity_0_01mm'] is True

@pytest.mark.parametrize('name,expected', [('oks',(9,63)), ('truba',(1,60)), ('kpp',(4,33))])
def test_no_collision_candidate_added_to_surface_budget(name,expected):
    nodes=json.loads((CENSUS/(name+'.json')).read_text(encoding='utf-8'))['objects']
    assert (sum(n['kind']=='surface' for n in nodes),sum(n['kind']!='surface' for n in nodes)) == expected

@pytest.mark.parametrize('damage', ['empty','duplicate_handle','missing_triangles','duplicate_id','nan','inf','negative','bbox'])
def test_fail_closed_census_corruption(damage):
    data=json.loads((CENSUS/'oks.json').read_text(encoding='utf-8'))
    node=data['objects'][0]
    if damage=='empty': data['objects']=[]
    elif damage=='duplicate_handle': data['objects'].append(copy.deepcopy(node))
    elif damage=='missing_triangles': node['triangles'] += 1
    elif damage=='duplicate_id':
        node['material_ids'].append(copy.deepcopy(node['material_ids'][0]))
        node['triangles'] += node['material_ids'][0]['triangles']
    elif damage in ('nan','inf','negative'):
        node['material_ids'][0]['area_m2'] = {'nan':float('nan'),'inf':float('inf'),'negative':-1}[damage]
    else: node['snapshot_native_bbox_max_error']=1
    with pytest.raises(ValueError): API['validate_scene'](data)


def test_collision_bbox_discrepancy_is_explicit_not_passed():
    data=json.loads((CENSUS/'truba.json').read_text(encoding='utf-8'))
    node=next(n for n in data['objects'] if n['name']=='Col_002')
    assert node['snapshot_bbox_parity_0_01mm'] is False
    assert node['kind']=='collision_candidate_noncompliant_name'
    assert node['snapshot_native_bbox_max_error'] > 0.0001


def test_native_reader_never_saves_or_exports_and_only_loads_copies():
    tree=ast.parse(SCRIPT.read_text(encoding='utf-8'))
    calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
    forbidden={'saveMaxFile','saveNodes','exportFile','importFile','holdMaxFile','fetchMaxFile'}
    assert not [n for n in calls if n.func.attr in forbidden]
    text=SCRIPT.read_text(encoding='utf-8')
    assert 'path.resolve().is_relative_to(ROOT.resolve())' in text
    assert 'sources-v001' in text


def test_depth_renderer_creates_world_for_empty_factory_scene():
    # Execute only world setup from the native driver against Blender's factory-empty condition.
    script=SCRIPT.with_name('render_depth.py')
    tree=ast.parse(script.read_text(encoding='utf-8'))
    setup=[n for n in ast.walk(tree) if isinstance(n,ast.Assign)
           and any(ast.unparse(t).startswith('scene.world') for t in n.targets)]
    scene=SimpleNamespace(world=None)
    bpy=SimpleNamespace(data=SimpleNamespace(worlds=SimpleNamespace(new=lambda _:SimpleNamespace(color=None))))
    exec(compile(ast.Module(body=setup,type_ignores=[]),str(script),'exec'),{'scene':scene,'bpy':bpy})
    assert scene.world.color == (0.88,0.88,0.88)


def test_depth_render_receipts_and_retired_painter():
    evidence=json.loads((CENSUS/'depth-renders.json').read_text(encoding='utf-8'))
    assert len(evidence['renders']) == 14
    assert evidence['members_verified'] == 23
    assert 'not measured' in evidence['perimeter_wall_continuity_status']
    for name in [f'ac{i:02d}' for i in range(4,10)]+['truba']:
        rows=[r for r in evidence['renders'] if r['building']==name]
        assert {r['mode'] for r in rows} == {'ids','shaded'}
        assert len(rows) == 2
        for row in rows:
            assert row['engine']=='BLENDER_WORKBENCH'
            assert row['application']=='5.1.2'
            assert row['collision_objects_loaded']==0
            assert row['zero_line_world_z_m']==0
            assert row['world_bounds_m'][0][2] <= -1
    tree=ast.parse(PUBLISH.read_text(encoding='utf-8'))
    assert not any(isinstance(n,ast.FunctionDef) and n.name=='render' for n in ast.walk(tree))
