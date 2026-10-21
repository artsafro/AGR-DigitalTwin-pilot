"""new-case: real Blender polygon fingerprints preserve Ground quads and tessellation density."""
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
BLENDER = Path(os.environ.get('DT_BLENDER', 'C:/Program Files/Blender Foundation/Blender 5.1/blender.exe'))


@pytest.mark.blender
@pytest.mark.parametrize('shape', ['triangle', 'quad', 'nonplanar', 'concave'])
def test_real_fingerprint_preserves_polygon_and_measures_loop_triangles(tmp_path, shape):
    if not BLENDER.is_file():
        pytest.skip('Blender executable unavailable')
    script = tmp_path / 'probe.py'
    script.write_text('''
import bpy, json, runpy, sys
from pathlib import Path
root=Path(sys.argv[sys.argv.index('--')+1])
shape=sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
points={'triangle':[(0,0,0),(2,0,0),(0,2,0)],
        'quad':[(0,0,0),(2,0,0),(2,2,0),(0,2,0)],
        'nonplanar':[(0,0,0),(2,0,0),(2,2,.2),(0,2,0)],
        'concave':[(0,0,0),(2,0,0),(.5,.5,0),(0,2,0)]}[shape]
mesh=bpy.data.meshes.new('SyntheticGround')
mesh.from_pydata(points,[],[tuple(range(len(points)))])
obj=bpy.data.objects.new('SM_Vatutino_Ground',mesh)
bpy.context.collection.objects.link(obj)
mesh.materials.append(bpy.data.materials.new('M_Vatutino_Ground_TileLight'))
uv=mesh.uv_layers.new(name='UVMap')
for i,p in enumerate(points): uv.data[i].uv=(p[0]/2,p[1]/2)
bpy.ops.export_scene.fbx(filepath=str(root/'source.fbx'),use_mesh_modifiers=False,axis_forward='Y',axis_up='Z')
script=Path(SCRIPT)
sys.argv=[str(script),'--','fingerprint',str(root/'source.fbx'),str(root/'fingerprint.json')]
runpy.run_path(str(script),run_name='__main__')
p=json.loads((root/'fingerprint.json').read_text())
assert len(p['polygons'])==1 and len(p['polygons'][0])==len(points)
assert p['material_ids']==[0]
obj=next(o for o in bpy.context.scene.objects if o.type=='MESH')
mesh=obj.data
mesh.calc_loop_triangles()
assert p['triangles']==len(points)-2
assert len(p['faces'])==len(mesh.loop_triangles)
for evidence,t in zip(p['faces'],mesh.loop_triangles):
    a,b,c=[obj.matrix_world@mesh.vertices[i].co for i in t.vertices]
    assert abs(evidence['world_area_m2']-(b-a).cross(c-a).length/2)<1e-12
    a,b,c=[mesh.uv_layers.active.data[i].uv for i in t.loops]
    assert abs(evidence['uv_area']-abs((b.x-a.x)*(c.y-a.y)-(c.x-a.x)*(b.y-a.y))/2)<1e-12
    assert evidence['slot']=='TileLight'
assert len(mesh.polygons)==1 and len(mesh.polygons[0].vertices)==len(points)
print('POLYGON_FINGERPRINT_PASS')
'''.replace('SCRIPT', repr(str(ROOT / 'tools/materials/bind_ground_textures_blender.py'))), encoding='utf-8')
    result = subprocess.run([str(BLENDER), '--background', '--factory-startup', '--python-exit-code', '1', '--python', str(script), '--', str(tmp_path), shape], capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, (result.stdout + result.stderr)[-3000:]
    assert 'POLYGON_FINGERPRINT_PASS' in result.stdout
