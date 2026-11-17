"""new-case: read-only master geometry dump for the OKS mesh quality score (#1616).

Blender 5.1.2; launched by tools/qa/mesh_quality_score.py (autoexec disabled).
Writes world-space vertices, polygon vertex indices and polygon material names of every
evaluated mesh object BEFORE triangulation. Active triangulation modifiers are refused.
Non-mesh objects are reported in ``dropped`` with their reason; nothing is saved.
"""
import json
import math
import sys

import bpy


def dump():
    rows, dropped = [], []
    dg = bpy.context.evaluated_depsgraph_get()
    for obj in sorted(bpy.context.scene.objects, key=lambda o: o.name):
        if obj.type != 'MESH':
            dropped.append({'name': obj.name, 'type': obj.type, 'reason': 'not a mesh object'})
            continue
        for mod in obj.modifiers:
            if mod.type == 'TRIANGULATE' and mod.show_viewport:
                raise ValueError(f'{obj.name}: active triangulation modifier {mod.name}')
        evaluated = obj.evaluated_get(dg)
        mesh = evaluated.to_mesh()
        try:
            mw = obj.matrix_world
            verts = []
            for v in mesh.vertices:
                co = mw @ v.co
                if not all(math.isfinite(c) for c in co):
                    raise ValueError('non-finite master vertex: ' + obj.name)
                verts.append([round(co.x, 6), round(co.y, 6), round(co.z, 6)])
            slots = [s.material.name if s.material else '' for s in obj.material_slots]
            mats = []
            for p in mesh.polygons:
                mats.append(slots[p.material_index] if p.material_index < len(slots) else '')
            rows.append({'name': obj.name, 'verts': verts,
                         'faces': [list(p.vertices) for p in mesh.polygons], 'materials': mats})
        finally:
            evaluated.to_mesh_clear()
    return {'objects': rows, 'dropped': dropped, 'blender': bpy.app.version_string}


def main():
    src, dest = sys.argv[sys.argv.index('--') + 1:]
    low = src.lower()
    if low.endswith('.blend'):
        bpy.ops.wm.open_mainfile(filepath=src, load_ui=False)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if low.endswith('.fbx'):
            bpy.ops.import_scene.fbx(filepath=src)
        elif low.endswith('.obj'):
            bpy.ops.wm.obj_import(filepath=src, forward_axis='Y', up_axis='Z')
        else:
            raise ValueError('unsupported master format: ' + src)
    result = dump()
    with open(dest, 'x', encoding='utf-8') as fh:
        json.dump(result, fh, allow_nan=False)


if __name__ == '__main__':
    main()
