"""new-case: read-only working-master polygon inventory BEFORE triangulation (#1420).

Blender 5.1.2; launched by tools/qa/master_topology.py with autoexec disabled.
Explicit active triangulation modifiers are refused, never allowed to hide n-gons.
"""
import json
import math
import sys

import bpy


def inventory():
    rows, dropped = [], []
    dg = bpy.context.evaluated_depsgraph_get()
    for obj in sorted(bpy.context.scene.objects, key=lambda o: o.name):
        if obj.type != 'MESH':
            dropped.append({'name': obj.name, 'type': obj.type, 'reason': 'not a mesh object'})
            continue
        for mod in obj.modifiers:
            if mod.type == 'TRIANGULATE' and mod.show_viewport:
                raise ValueError(f'{obj.name}: active triangulation modifier {mod.name}; inspect the working master before triangulation')
        evaluated = obj.evaluated_get(dg)
        mesh = evaluated.to_mesh()
        try:
            if any(not all(math.isfinite(c) for c in v.co) for v in mesh.vertices):
                raise ValueError('non-finite master vertex: ' + obj.name)
            rows.append({'name': obj.name, 'face_degrees': [len(p.vertices) for p in mesh.polygons]})
        finally:
            evaluated.to_mesh_clear()
    return {'objects': rows, 'dropped': dropped, 'blender': bpy.app.version_string}


def main():
    src, dest = sys.argv[sys.argv.index('--') + 1:]
    if src.lower().endswith('.blend'):
        bpy.ops.wm.open_mainfile(filepath=src, load_ui=False)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=src)
    result = inventory()
    with open(dest, 'x', encoding='utf-8') as fh:
        json.dump(result, fh, allow_nan=False)


if __name__ == '__main__':
    main()
