"""new-case: seeded mistakes in imported copies of real FBX scenes (#1261).

Offline Blender only. Each operation starts from a fresh import, then existing readback
functions measure the altered Blender scene. No verdict/fact is planted in the JSON.
The immutable source FBX is never exported over or saved. Mutants are scene-level,
not roundtrip/exporter tests; the readback's source names the frozen source identity.
"""
import argparse
import bmesh
import bpy
import hashlib
import json
from pathlib import Path
import random
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
SEED = 1261
CASES = {
    'unapplied_scale': ['V002/scale 1:1', 'V004/applied transforms'],
    'baked_size': ['V004/MAF dimensions vs specification'],
    'flipped_normals': ['V004/MAF flipped normals', 'V004/topology defects'],
    'self_intersections': ['V004/topology defects'],
    'duplicate_faces': ['V004/topology defects', 'V004/co-directional clearance'],
    'missing_ucx': ['V010/UCX present'],
    'wrong_ucx_gap': ['V010/UCX piece gap (advisory)', 'V010/UCX intersections'],
    'wrong_material': ['V005/material assignments'],
    'missing_texture': ['V005/Flora maps', 'V006/embedded textures'],
    'oversized_texture': ['V006/texture dimensions'],
    'wrong_texel': ['V009/texel density'],
    'wrong_name': ['V012/mesh names'],
    'wrong_pivot': ['V013/origin at FBX zero', 'V013/shared pivot', 'V013/pivot at geometric centre'],
    'leftover_object': ['V003/object types'],
    'maf_zone_merged': ['V005/material assignments'],
    'flora_height': ['V015/Flora dimensions'],
    'ground_skirt_missing': ['V003/ground skirt depth'],
}


def apply(case, objects, rng):
    targets = sorted([o for o in objects if o.type == 'MESH' and not o.name.upper().startswith('UCX_')], key=lambda o: o.name)
    ucx = sorted([o for o in objects if o.name.upper().startswith('UCX_')], key=lambda o: o.name)
    if not targets:
        raise ValueError('no render mesh')
    obj = targets[0]
    if case == 'unapplied_scale':
        factor = rng.choice([.5, .95, 1.05, 1.5])
        obj.scale *= factor
        return {'target': obj.name, 'factor': factor}
    if case in {'flipped_normals', 'duplicate_faces', 'self_intersections', 'ground_skirt_missing'}:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        if case == 'flipped_normals':
            bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
        elif case == 'duplicate_faces':
            bmesh.ops.duplicate(bm, geom=[bm.faces[0]])
        elif case == 'self_intersections':
            # Intersect a copy of a real triangle with its own source surface.
            face = bm.faces[0]
            points = [v.co.copy() for v in face.verts][:3]
            center = sum(points, points[0] * 0) / 3
            normal = face.normal.copy()
            if normal.length == 0:
                bm.free()
                raise ValueError('degenerate target face')
            verts = [bm.verts.new(center + (p-center)*.5 + normal*s) for p,s in zip(points, [-.01,.01,.01])]
            bm.faces.new(verts)
        else:
            faces = [f for f in bm.faces if abs((obj.matrix_world.to_3x3() @ f.normal).z) < .2]
            if not faces:
                bm.free()
                raise ValueError('no vertical skirt candidate')
            bmesh.ops.delete(bm, geom=faces, context='FACES')
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()
    elif case == 'missing_ucx':
        if not ucx:
            raise ValueError('no UCX to remove')
        for o in ucx:
            bpy.data.objects.remove(o, do_unlink=True)
    elif case == 'wrong_ucx_gap':
        if len(ucx) < 2:
            raise ValueError('fewer than two UCX pieces')
        # Identical overlapping hull: a realistic duplicated collision piece.
        ucx[1].data = ucx[0].data.copy()
        ucx[1].matrix_world = ucx[0].matrix_world.copy()
    elif case in {'wrong_material', 'maf_zone_merged'}:
        if case == 'maf_zone_merged' and len({p.material_index for p in obj.data.polygons}) < 2:
            raise ValueError('no distinct colour zones')
        if case == 'wrong_material':
            obj.data.materials.clear()
            obj.data.materials.append(bpy.data.materials.new('UnknownMaterial_1261'))
        for poly in obj.data.polygons:
            poly.material_index = 0
    elif case == 'missing_texture':
        changed = 0
        for material in bpy.data.materials:
            if material.node_tree:
                for node in list(material.node_tree.nodes):
                    if node.type == 'TEX_IMAGE':
                        material.node_tree.nodes.remove(node)
                        changed += 1
        if not changed:
            raise ValueError('no texture nodes to remove')
    elif case == 'oversized_texture':
        images = [i for i in bpy.data.images if i.type == 'IMAGE']
        if not images:
            raise ValueError('no images to resize')
        for image in images:
            image.scale(8192, 8192)
    elif case == 'wrong_texel':
        if not obj.data.uv_layers:
            raise ValueError('no UV to scale')
        for uv in obj.data.uv_layers.active.data:
            uv.uv *= .00001
    elif case == 'wrong_name':
        obj.name = 'Broken_agent_name'
    elif case == 'wrong_pivot':
        from mathutils import Matrix
        obj.data.transform(Matrix.Translation((-10, 0, 0)))
        obj.matrix_world = obj.matrix_world @ Matrix.Translation((10, 0, 0))
    elif case == 'leftover_object':
        bpy.context.collection.objects.link(bpy.data.objects.new('Agent_helper_1261', None))
    elif case == 'baked_size':
        for v in obj.data.vertices:
            v.co *= 1.5
    elif case == 'flora_height':
        for v in obj.data.vertices:
            v.co.z *= 1.5
    else:
        raise ValueError(f'unsupported mutation {case}')
    bpy.context.view_layer.update()
    return {'target': obj.name}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('source', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--cases', nargs='+', choices=sorted(CASES), required=True)
    args = p.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.output.exists() or args.output.resolve() == args.source.resolve():
        raise ValueError('existing output or source alias')
    original = args.source.read_bytes()
    args.output.mkdir(parents=True)
    # Use production fact extraction, not a second checker implementation.
    baseline = args.output / 'clean.json'
    sys.argv = ['fbx_readback.py', '--', str(args.source), str(baseline)]
    ns = runpy.run_path(str(ROOT / 'tools/blender/fbx_readback.py'))
    operations = []
    for case in args.cases:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        ns['light_import_compat']()
        bpy.ops.import_scene.fbx(filepath=str(args.source))
        try:
            witness = apply(case, list(bpy.context.scene.objects), random.Random(SEED))
        except ValueError as exc:
            operations.append({'class': case, 'status': 'not_applicable', 'reason': str(exc)})
            continue
        rb = {'source': str(args.source), 'readback_ok': True, 'blender': bpy.app.version_string,
              'meshes': [ns['mesh_facts'](o) for o in bpy.context.scene.objects if o.type == 'MESH'],
              'other_objects': [{'name': o.name, 'type': o.type} for o in bpy.context.scene.objects if o.type != 'MESH'],
              'images': ns['image_facts'](), 'materials': ns['material_facts']()}
        # These describe the unchanged source file, not fabricated scene measurements.
        clean = json.loads(baseline.read_text(encoding='utf-8'))
        # Copy importer correction facts only for untouched transforms, keyed by name.
        by_name = {m['name']: m for m in clean['meshes']}
        if case not in {'unapplied_scale', 'wrong_name'}:
            for m in rb['meshes']:
                for key in ['baked_rotation_euler_deg', 'baked_scale']:
                    if key in by_name.get(m['name'], {}):
                        m[key] = by_name[m['name']][key]
        (args.output / f'{case}.json').write_text(json.dumps(rb, ensure_ascii=False, allow_nan=False), encoding='utf-8')
        operations.append({'class': case, 'status': 'generated', 'expected': CASES[case], 'witness': witness})
    if args.source.read_bytes() != original:
        raise ValueError('source changed during generation')
    (args.output / 'operations.json').write_text(json.dumps({'seed': SEED, 'source_sha256': hashlib.sha256(original).hexdigest(), 'operations': operations}, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
