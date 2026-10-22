"""new-case: AC06 adapter for the approved AC08 recipe, with separate source glass.

Retain both source meshes and all collision candidates. Only UV/materials change;
UCX triangulation is an export representation change explicitly required by #563.
The shared AC08 master builder accepts one Multi/Sub body, not body + glass.
Run inside factory-empty Blender: --python build_ac06.py -- dump spec textures new_root.
"""
import json
from pathlib import Path
import runpy
import sys


def partition(dump, spec):
    """Explicit source handles, complete partition, no name/default classification."""
    nodes = dump.get('nodes') or []
    handles = [n['handle'] for n in nodes]
    if len(handles) != len(set(handles)):
        raise ValueError('duplicate source handles')
    by_handle = {n['handle']: n for n in nodes}
    main, glass = (by_handle[spec[k]] for k in ('main_handle', 'glass_handle'))
    if main is glass or not main['multisub'] or not glass['multisub']:
        raise ValueError('expected distinct main and glass Multi/Sub meshes')
    if set(glass['mat_ids']) != {12}:
        raise ValueError('glass must contain only approved source ID 12')
    hulls = [n for n in nodes if n is not main and n is not glass]
    if any(n['multisub'] for n in hulls):
        raise ValueError('unclassified Multi/Sub mesh')
    if not hulls:
        raise ValueError('missing source collisions')
    return main, glass, hulls


def main():
    import bmesh
    import bpy

    dump_path, spec_path, textures, root = sys.argv[sys.argv.index('--') + 1:]
    root = Path(root)
    root.mkdir(exist_ok=False)
    dump = json.loads(Path(dump_path).read_text(encoding='utf-8'))
    spec = json.loads(Path(spec_path).read_text(encoding='utf-8'))
    body, glass, hulls = partition(dump, spec)
    reduced = root / 'body-collisions.json'
    reduced.write_text(json.dumps({**dump, 'nodes': [body, *hulls]}), encoding='utf-8')
    scripts = Path(__file__).resolve().parents[1] / 'scripts'
    sys.path.insert(0, str(scripts))
    import vpm_uv
    sys.argv = ['build_master.py', '--', str(reduced), spec_path, textures, str(root / 'body.blend')]
    runpy.run_path(str(scripts / 'build_master.py'), run_name='__main__')
    mesh = bpy.data.meshes.new('AC06_source_glass')
    mesh.from_pydata(glass['vertices'], [], glass['faces'])
    mesh.update()
    obj = bpy.data.objects.new('SM_' + spec['address'] + '_MainGlass', mesh)
    bpy.context.scene.collection.objects.link(obj)
    mat = bpy.data.materials.new('M_' + spec['address'] + '_MainGlass_1')
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value = (0.75, 0.82, 0.82, 1)
    bsdf.inputs['Alpha'].default_value = 0.5
    bsdf.inputs['Roughness'].default_value = 0.05
    mesh.materials.append(mat)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.layers.int.new('finish')  # pack_uv requires the layer even for map-free glass.
    uvqa = vpm_uv.pack_uv(bm, [], {**spec, 'glass': {'udim': 1001}}, glass=True)
    bm.to_mesh(mesh)
    bm.free()
    # Shared exporter expects UCX already triangulated (AC08 assumption).
    # Preserve all source hull surfaces; only diagonal tessellation changes.
    for o in bpy.context.scene.objects:
        if o.name.startswith('UCX_'):
            bm = bmesh.new()
            bm.from_mesh(o.data)
            bmesh.ops.triangulate(bm, faces=list(bm.faces))
            bm.to_mesh(o.data)
            bm.free()
    out = root / (spec['address'] + '_VPM_master.blend')
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    report = {'source_dump': str(Path(dump_path).resolve()), 'main_handle': body['handle'],
              'glass_handle': glass['handle'], 'collision_handles': [n['handle'] for n in hulls],
              'dropped_nodes': [], 'glass_uv': uvqa, 'master': str(out)}
    (root / 'adapter.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('AC06-ADAPTER', json.dumps(report))


if __name__ == '__main__':
    main()
