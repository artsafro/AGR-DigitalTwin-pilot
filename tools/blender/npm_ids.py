"""new-case: isolated Blender mesh intake/apply boundary for agr npm-ids (#1630).

Only imports copies. Mode extract writes JSON; apply sets provisional IDs on a new
blend copy. No VPM conversion, no session connection, no geometry/UV edits.
"""
import argparse
import colorsys
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def extract(source):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(source))
    objects = []
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH':
            continue
        mesh = obj.data
        if not mesh.uv_layers.active:
            raise ValueError(f'{obj.name}: missing UV')
        mesh.calc_loop_triangles()
        atlas_by_slot = {}
        for slot, mat in enumerate(mesh.materials):
            images = []
            if mat and mat.use_nodes:
                images = [n.image for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image
                          and '_d_' in Path(n.image.filepath).name.lower()]
            paths = set()
            for image in images:
                name = Path(bpy.path.abspath(image.filepath)).name
                candidates = [source.with_suffix('.fbm') / name, source.parent / 'maps' / name]
                found = [p.resolve() for p in candidates if p.is_file()]
                if found:
                    paths.add(str(found[0]))
            if len(paths) != 1:
                raise ValueError(f'{obj.name} slot {slot}: expected one diffuse atlas, got {paths}')
            atlas_by_slot[slot] = paths.pop()
        objects.append({'name': obj.name, 'verts': [list(obj.matrix_world @ v.co) for v in mesh.vertices],
                        'local': [list(v.co) for v in mesh.vertices],
                        'tris': [list(t.vertices) for t in mesh.loop_triangles],
                        'uvs': [list(v.uv) for v in mesh.uv_layers.active.data],
                        'uv_tris': [list(t.loops) for t in mesh.loop_triangles],
                        'tri_polygons': [t.polygon_index for t in mesh.loop_triangles],
                        'polygons': [{'uv': [list(mesh.uv_layers.active.data[i].uv) for i in p.loop_indices],
                                      'slot': p.material_index} for p in mesh.polygons],
                        'atlases': atlas_by_slot})
    if not objects:
        raise ValueError('no source meshes')
    return {'source': str(source), 'blender': bpy.app.version_string,
            'units': {'system': bpy.context.scene.unit_settings.system,
                      'scale_length': bpy.context.scene.unit_settings.scale_length}, 'objects': objects}


def apply(doc, output):
    for record in doc['objects']:
        obj = bpy.data.objects[record['name']]
        ids = record['mat_ids']
        if len(ids) != len(obj.data.polygons) or any(type(i) is not int or i < 0 for i in ids):
            raise ValueError(f'{obj.name}: incomplete ID assignment')
        obj.data.materials.clear()
        for mid in range(max(ids)+1):
            mat = bpy.data.materials.new(f'ID_{mid:03d}_PROVISIONAL' if mid else 'ID_UNASSIGNED')
            mat.diffuse_color = (*colorsys.hsv_to_rgb((mid*.61803398875)%1, .7, .8), 1) if mid else (1, 0, 1, 1)
            obj.data.materials.append(mat)
        for p, mid in zip(obj.data.polygons, ids):
            p.material_index = mid
        obj.show_wire = True
        obj.show_all_edges = True
    bpy.ops.wm.save_as_mainfile(filepath=str(output), check_existing=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['extract', 'apply'])
    parser.add_argument('source')
    parser.add_argument('output')
    parser.add_argument('--assignments')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    source, output = Path(args.source).resolve(), Path(args.output).resolve()
    if output.exists() or output == source:
        raise ValueError('output must be new and distinct from source')
    doc = extract(source)
    if args.mode == 'extract':
        with output.open('x', encoding='utf-8') as stream:
            json.dump(doc, stream, allow_nan=False)
    else:
        assignments = json.loads(Path(args.assignments).read_text(encoding='utf-8'))
        apply(assignments, output)


if __name__ == '__main__':
    main()
