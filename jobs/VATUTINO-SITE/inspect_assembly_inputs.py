"""Read-only Blender preflight for #298; no source scene is saved."""
import json
import sys
from pathlib import Path
import bpy

source, output = sys.argv[sys.argv.index('--') + 1:]
bpy.ops.wm.open_mainfile(filepath=source)
rows = []
for o in bpy.data.objects:
    if o.type != 'MESH':
        continue
    o.data.calc_loop_triangles()
    rows.append({'name': o.name, 'library_id': o.get('library_id'), 'properties': dict(o.items()),
                 'triangles': len(o.data.loop_triangles), 'uv_layers': len(o.data.uv_layers),
                 'materials': [m.name if m else None for m in o.data.materials],
                 'matrix': [list(r) for r in o.matrix_world]})
images = [{'name': i.name, 'path': i.filepath} for i in bpy.data.images]
Path(output).write_text(json.dumps({'version': bpy.app.version_string, 'units': bpy.context.scene.unit_settings.system,
                                  'scale_length': bpy.context.scene.unit_settings.scale_length,
                                  'objects': rows, 'images': images}, indent=1), encoding='utf-8')
print('PREFLIGHT', bpy.app.version_string, len(rows), 'meshes', len(images), 'images')
