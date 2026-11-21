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
collection = bpy.data.collections.new('Asset')
s.collection.children.link(collection)
collection.objects.link(o)
a = bpy.data.materials.new('matid_1')
a['agr_material_id'] = 1
m.materials.append(a)
m.uv_layers.new(name='UVMap')
bpy.ops.wm.save_as_mainfile(filepath={str(clean)!r})
h = bpy.data.objects.new('hidden_helper', None)
s.collection.objects.link(h)
h.hide_render = True
unused = bpy.data.collections.new('unused_collection')
s.collection.children.link(unused)
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
    assert 'empty collection: unused_collection' in scenes[str(dirty)]['unsupported']


@pytest.mark.parametrize('value', [0.0, 1.0])
def test_real_blender_rejects_shape_keys_with_clean_reset(tmp_path, value):
    """Synthetic saved mesh: even inactive shape keys are unsupported reusable state."""
    if not BLENDER.is_file():
        pytest.skip('Blender 5.1.2 unavailable')
    clean, dirty, reset = [tmp_path / (name + '.blend') for name in ('clean', 'dirty', 'reset')]
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
o.shape_key_add(name='Basis')
push = o.shape_key_add(name='Push')
for point in push.data:
    point.co.z += 0.5
push.value = {value!r}
bpy.ops.wm.save_as_mainfile(filepath={str(dirty)!r})
o.shape_key_clear()
bpy.ops.wm.save_as_mainfile(filepath={str(reset)!r})
'''
    result = subprocess.run([str(BLENDER), '-b', '--factory-startup', '--python-exit-code', '3', '--python-expr', code],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr
    checker = module()
    scenes = checker.native_inspect([clean, dirty, reset], BLENDER)
    expected = {'objects': ['WIN-01_npm_frame'], 'triangles': 2, 'size_m': [1, 0, 2],
                'materials': [{'id': 1, 'name': 'matid_1'}]}
    for path in (clean, reset):
        assert checker.scene_errors(scenes[str(path)], expected, 'bottom-left') == []
    errors = checker.scene_errors(scenes[str(dirty)], expected, 'bottom-left')
    assert errors, 'shape keys must not pass base-mesh-only cleanliness'
    message = ' '.join(errors)
    assert all(token in message for token in ('shape key', 'WIN-01_npm_frame', 'Basis', 'Push'))
    # Combine the reviewer witness with earlier native-material and D100 regressions.
    scenes[str(dirty)]['objects'][0]['materials'][0]['id'] = True
    combined = ' '.join(checker.scene_errors(scenes[str(dirty)], expected, 'flora-bbox-plus-0.1'))
    assert 'shape key' in combined and 'unmapped material' in combined and 'size/pivot mismatch' in combined


@pytest.mark.parametrize('mutation,token', [
    ("m.color_attributes.new('junk', 'FLOAT_COLOR', 'POINT')", 'junk'),
    ("m.attributes.new('junk', 'FLOAT', 'POINT')", 'junk'),
    ("m.attributes.new('.private_junk', 'BOOLEAN', 'FACE')", '.private_junk'),
    ("m.polygons[0].hide = True", 'hidden polygon: 0'),
    ("m.edges[0].hide = True", 'hidden edge: 0'),
    ("m.vertices[0].hide = True", 'hidden vertex: 0'),
    ("o['leftover'] = 1", 'leftover'),
    ("m['leftover'] = 1", 'leftover'),
    ("a['leftover'] = 1", 'leftover'),
    ("m.attributes.new('position_like', 'FLOAT_VECTOR', 'POINT')", 'position_like'),
])
def test_real_blender_rejects_leftovers_with_reset(tmp_path, mutation, token):
    """Synthetic native assets: do not modify the published W01 etalon."""
    if not BLENDER.is_file():
        pytest.skip('Blender 5.1.2 unavailable')
    clean, dirty, reset = [tmp_path / (name + '.blend') for name in ('clean', 'dirty', 'reset')]
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
print('ATTRIBUTE_CONTROL', [(x.name, x.data_type, x.domain) for x in m.attributes])
bpy.ops.wm.save_as_mainfile(filepath={str(clean)!r})
{mutation}
bpy.ops.wm.save_as_mainfile(filepath={str(dirty)!r})
bpy.ops.wm.open_mainfile(filepath={str(clean)!r}, load_ui=False, use_scripts=False)
bpy.ops.wm.save_as_mainfile(filepath={str(reset)!r})
'''
    result = subprocess.run([str(BLENDER), '-b', '--factory-startup', '--disable-autoexec',
                             '--python-exit-code', '3', '--python-expr', code],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr
    checker = module()
    scenes = checker.native_inspect([clean, dirty, reset], BLENDER)
    expected = {'objects': ['WIN-01_npm_frame'], 'triangles': 2, 'size_m': [1, 0, 2],
                'materials': [{'id': 1, 'name': 'matid_1'}]}
    for path in (clean, reset):
        assert checker.scene_errors(scenes[str(path)], expected, 'bottom-left') == [], result.stdout
    for _ in range(2):
        errors = checker.scene_errors(scenes[str(dirty)], expected, 'bottom-left')
        assert errors and token in ' '.join(errors), (errors, result.stdout)
    scenes[str(dirty)]['objects'][0]['materials'][0]['id'] = True
    combined = ' '.join(checker.scene_errors(scenes[str(dirty)], expected, 'flora-bbox-plus-0.1'))
    assert token in combined and 'unmapped material' in combined and 'size/pivot mismatch' in combined


def test_real_windows_migration_and_fresh_cli(tmp_path):
    import os
    import sys
    if not BLENDER.is_file():
        pytest.skip('Blender unavailable')
    out = Path(os.environ.get('AGR_LIBRARY_MIGRATION_ROOT', str(tmp_path/'windows-v001')))
    result = subprocess.run([sys.executable, str(ROOT/'tools/library/migrate_windows.py'), '--output', str(out)],
                            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600)
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-2000:]
    result = subprocess.run([sys.executable, str(ROOT/'tools/library/check_library.py'), str(out/'catalogue.json'),
                             '--root', str(out)], capture_output=True, text=True, timeout=600)
    assert result.returncode == 0, result.stdout[-6000:] + result.stderr
    import json
    receipt = json.loads(result.stdout)
    assert receipt['cleanliness'] == 'pass' and receipt['variants_checked'] == 118
    assert receipt['ready'] == 59 and len(receipt['quarantine']) == 8
    before = (out/'catalogue.json').read_bytes()
    again = subprocess.run([sys.executable, str(ROOT/'tools/library/migrate_windows.py'), '--output', str(out)],
                            capture_output=True, text=True)
    assert again.returncode != 0 and before == (out/'catalogue.json').read_bytes()
