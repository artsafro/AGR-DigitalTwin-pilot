"""new-case: opt-in real Blender readback for unified library files, no customer scenes."""
import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BLENDER = Path('C:/Program Files/Blender Foundation/Blender 5.1/blender.exe')
pytestmark = pytest.mark.blender


def module():
    spec = importlib.util.spec_from_file_location('clean_native_test', ROOT/'tools/library/check_library.py')
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_real_blender_reads_saved_mesh_and_hidden_extra(tmp_path):
    if not BLENDER.is_file():
        pytest.skip('Blender 5.1.2 unavailable')
    clean, dirty = tmp_path/'clean.blend', tmp_path/'dirty.blend'
    code = f'''
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
s = bpy.context.scene
s.unit_settings.system = 'METRIC'
s.unit_settings.scale_length = 1
m = bpy.data.meshes.new('WIN-01_npm_frame')
m.from_pydata([(0,0,0),(1,0,0),(1,0,2),(0,0,2)], [], [(0,1,2,3)])
o = bpy.data.objects.new(m.name, m)
s.collection.objects.link(o)
a = bpy.data.materials.new('matid_1')
a['agr_material_id'] = 1
m.materials.append(a)
m.uv_layers.new(name='UVMap')
bpy.ops.wm.save_as_mainfile(filepath={str(clean)!r})
h = bpy.data.objects.new('hidden_helper', None)
s.collection.objects.link(h)
h.hide_render = True
bpy.ops.wm.save_as_mainfile(filepath={str(dirty)!r})
'''
    result = subprocess.run([str(BLENDER), '-b', '--factory-startup', '--python-exit-code', '3', '--python-expr', code],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr
    checker = module()
    scenes = checker.native_inspect([clean, dirty], BLENDER)
    expected = {'objects': ['WIN-01_npm_frame'], 'triangles': 2, 'size_m': [1,0,2],
                'materials': [{'id': 1, 'name': 'matid_1'}]}
    assert checker.scene_errors(scenes[str(clean)], expected, 'bottom-left') == []
    errors = checker.scene_errors(scenes[str(dirty)], expected, 'bottom-left')
    assert errors and 'hidden_helper' in ' '.join(errors)
