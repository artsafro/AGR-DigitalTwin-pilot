"""new-case: synthetic saved Blender review files; never touches production scenes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import bpy

script, directory = sys.argv[sys.argv.index('--') + 1:]
root = Path(directory)
spec = importlib.util.spec_from_file_location('review_textures', script)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.ops.mesh.primitive_cube_add()
obj = bpy.context.object
obj.name = 'SyntheticBrick'
mat = bpy.data.materials.new('Bricks1')
obj.data.materials.append(mat)
scope = {'ids': [{'object': obj.name, 'id': 1}]}
results = {}
paths = []


def save_check(key):
    path = root / (key + '.blend')
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    paths.append((path, hashlib.sha256(path.read_bytes()).hexdigest()))
    bpy.ops.wm.open_mainfile(filepath=str(path))
    results[key] = gate.check_blender(bpy, scope)


save_check('empty')
mat = bpy.data.materials['Bricks1']
mat.use_nodes = True
image = bpy.data.images.new('Bricks1', width=8, height=8)
image.filepath_raw = str(root / 'Bricks1.png')
image.file_format = 'PNG'
image.save()
tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
tex.image = image
shader = mat.node_tree.nodes.get('Principled BSDF')
mat.node_tree.links.new(tex.outputs['Color'], shader.inputs['Base Color'])
save_check('linked')
results['repeated'] = gate.check_blender(bpy, scope)
mat = bpy.data.materials['Bricks1']
tex = next(n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE')
tex.image.pack()
save_check('packed')
mat = bpy.data.materials['Bricks1']
tex = next(n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE')
tex.image.unpack(method='REMOVE')
tex.image.filepath = str(root / 'absent.png')
save_check('missing')
mat = bpy.data.materials['Bricks1']
tex = next(n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE')
tex.image.filepath = str(root / 'Bricks1.png')
shader = mat.node_tree.nodes.get('Principled BSDF')
mat.node_tree.links.remove(shader.inputs['Base Color'].links[0])
save_check('unlinked')
mat = bpy.data.materials['Bricks1']
shader = mat.node_tree.nodes.get('Principled BSDF')
tex = next(n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE')
mat.node_tree.links.new(tex.outputs['Alpha'], shader.inputs['Base Color'])
save_check('wrong_output')
results['unknown_id'] = gate.check_blender(bpy, {'ids': [{'object': 'Unknown', 'id': 1}]})
results['unused_id'] = gate.check_blender(bpy, {'ids': [{'object': 'SyntheticBrick', 'id': 2}]})
results['unchanged_sources'] = all(hashlib.sha256(p.read_bytes()).hexdigest() == digest for p, digest in paths)
(root / 'native.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
