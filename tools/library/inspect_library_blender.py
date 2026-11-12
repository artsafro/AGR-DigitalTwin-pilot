"""new-case: read-only native .blend inventory for the unified library checker.

Run only in an agent-owned Blender 5.1.2+; disables embedded scripts on load.
No saved receipt is read and no scene/file is written. JSON rows go to stdout.
"""
import json
import math
import sys
from pathlib import Path

import bpy

from mathutils.kdtree import KDTree


def native_min_spacing(mesh):
    """Exact nearest distinct indexed vertex distance (Blender float32 coordinates)."""
    if len(mesh.vertices) < 2:
        return 0.0
    tree = KDTree(len(mesh.vertices))
    for vertex in mesh.vertices:
        tree.insert(vertex.co, vertex.index)
    tree.balance()
    return min(distance for vertex in mesh.vertices for _, index, distance in tree.find_n(vertex.co, 2)
               if index != vertex.index)


def inventory():
    scene = bpy.context.scene
    orphans, unsupported, objects = [], [], []
    allowed = {'meshes', 'materials', 'images', 'collections'}
    blocks = ['meshes', 'materials', 'images', 'collections', 'cameras', 'lights', 'curves', 'armatures',
              'actions', 'node_groups', 'worlds', 'textures', 'texts', 'speakers', 'lattices',
              'metaballs', 'volumes', 'hair_curves', 'pointclouds', 'grease_pencils']
    for kind in blocks:
        for block in getattr(bpy.data, kind, []):
            if block.users == 0 or block.use_fake_user:
                orphans.append(kind + ':' + block.name)
            if kind == 'collections' and not block.all_objects:
                unsupported.append('empty collection: ' + block.name)
            if kind not in allowed or block.library or getattr(block, 'animation_data', None):
                unsupported.append(kind + ':' + block.name)
    if len(bpy.data.scenes) != 1 or len(scene.view_layers) != 1 or bpy.data.libraries:
        unsupported.append('multiple scenes/view layers or linked libraries')
    if (scene.sequence_editor and len(scene.sequence_editor.strips)) or scene.compositing_node_group:
        unsupported.append('sequencer/compositor')
    for image in bpy.data.images:
        if image.source != 'FILE' or not image.packed_file:
            unsupported.append('image not packed: ' + image.name)
    def collection_flags(layer):
        if layer.exclude or layer.hide_viewport or layer.collection.hide_render or layer.collection.hide_viewport:
            unsupported.append('hidden collection: ' + layer.name)
        for child in layer.children:
            collection_flags(child)
    collection_flags(bpy.context.view_layer.layer_collection)
    for obj in bpy.data.objects:
        row = {'name': obj.name, 'type': obj.type,
               'location': list(obj.matrix_world.translation),
               'rotation': list(obj.matrix_world.to_euler()), 'scale': list(obj.matrix_world.to_scale()),
               'hidden': bool(obj.hide_render or obj.hide_viewport or obj.hide_get() or obj.name not in scene.objects),
               'parent': obj.parent.name if obj.parent else None,
               'modifiers': [m.type for m in obj.modifiers], 'constraints': [c.type for c in obj.constraints]}
        if obj.library or obj.animation_data or obj.instance_type != 'NONE':
            unsupported.append('object animation/library/instance: ' + obj.name)
        if obj.type == 'MESH':
            mesh = obj.data
            if mesh.shape_keys is not None:
                for key in mesh.shape_keys.key_blocks:
                    unsupported.append('shape key: ' + obj.name + ':' + key.name)
            mesh.calc_loop_triangles()
            points = [obj.matrix_world @ v.co for v in mesh.vertices]
            row['bounds'] = [[min((p[i] for p in points), default=0) for i in range(3)],
                             [max((p[i] for p in points), default=0) for i in range(3)]]
            if not all(math.isfinite(c) for p in points for c in p):
                unsupported.append('nonfinite vertex: ' + obj.name)
            row['triangles'] = len(mesh.loop_triangles)
            row['min_vertex_distance_m'] = native_min_spacing(mesh)
            row['materials'] = [{'id': slot.material.get('agr_material_id'), 'name': slot.material.name}
                                if slot.material else {'id': None, 'name': None} for slot in obj.material_slots]
            used = {p.material_index for p in mesh.polygons}
            row['unused_slots'] = sorted(set(range(len(obj.material_slots))) - used)
            if any(i >= len(obj.material_slots) for i in used):
                unsupported.append('unmapped face slot: ' + obj.name)
            row['uv_layers'] = len(mesh.uv_layers)
            row['uv_finite'] = all(math.isfinite(c) for uv in mesh.uv_layers for item in uv.data for c in item.uv)
            row['degenerate_faces'] = sum(t.area <= 1e-12 or not math.isfinite(t.area) for t in mesh.loop_triangles)
            referenced = {v for p in mesh.polygons for v in p.vertices}
            edges = {tuple(sorted((p.vertices[i-1], p.vertices[i]))) for p in mesh.polygons for i in range(len(p.vertices))}
            row['loose_vertices'] = len(mesh.vertices) - len(referenced) + sum(tuple(sorted(e.vertices)) not in edges for e in mesh.edges)
            signatures = [tuple(sorted(tuple(mesh.vertices[v].co) for v in p.vertices)) for p in mesh.polygons]
            row['duplicate_faces'] = len(signatures) - len(set(signatures))
        objects.append(row)
    return {'units': scene.unit_settings.system, 'scale_length': scene.unit_settings.scale_length,
            'orphans': orphans, 'unsupported': unsupported, 'objects': objects}


def main():
    if bpy.app.version < (5, 1, 2):
        raise ValueError('Blender 5.1.2+ required')
    for name in sys.argv[sys.argv.index('--') + 1:]:
        path = Path(name).resolve()
        bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False, use_scripts=False)
        print('AGR_LIBRARY_SCENE ' + json.dumps({'path': str(path), 'scene': inventory()}, ensure_ascii=True, allow_nan=False), flush=True)


if __name__ == '__main__':
    main()
