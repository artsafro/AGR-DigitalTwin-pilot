"""new-case: Blender driver for an explicit local UCX passage cut (#2051).

blender --background --factory-startup --disable-autoexec --python-exit-code 1 \
    --python tools/blender/ucx_cut_passage.py -- SOURCE.blend SPEC.json NEW.blend

The spec names all frozen collision objects and supplies the clearance and optional convex fill cells
in world metres. No source scene or render geometry is written. See docs/domain/areas/ucx.md.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory

import bmesh
import bpy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'adapters/max/agr_tools'))
import ucx10_core as core  # noqa: E402 - Blender has no project environment


def read_mesh(obj):
    if obj.type != 'MESH' or obj.modifiers or obj.data.shape_keys:
        raise ValueError(f'{obj.name}: expected an unmodified mesh')
    mesh = obj.data
    mesh.calc_loop_triangles()
    return (core.transform_points([tuple(v.co) for v in mesh.vertices], obj.matrix_world),
            [tuple(t.vertices) for t in mesh.loop_triangles])


def bodies(obj):
    """Extract indexed loose parts without welding or changing other bodies' storage."""
    verts, tris = read_mesh(obj)
    polygons = [t.polygon_index for t in obj.data.loop_triangles]
    adjacent = defaultdict(list)
    for i, tri in enumerate(tris):
        for v in tri:
            adjacent[v].append(i)
    todo = set(range(len(tris)))
    for seed in range(len(tris)):
        if seed not in todo:
            continue
        todo.remove(seed)
        stack, found, visited = [seed], [seed], set()
        while stack:
            for v in tris[stack.pop()]:
                if v not in visited:
                    visited.add(v)
                    active = [i for i in adjacent[v] if i in todo]
                    todo.difference_update(active)
                    found.extend(active)
                    stack.extend(active)
        indices = sorted(visited)
        reindex = {v: i for i, v in enumerate(indices)}
        yield {'handle': f'{obj.name}/{seed}', 'verts': [verts[v] for v in indices],
               'tris': [tuple(reindex[v] for v in tris[i]) for i in sorted(found)],
               'polygons': sorted({polygons[i] for i in found})}


def body_digest(row):
    """Exact world-coordinate triangle bytes, invariant to index rebasing, not winding reversal."""
    import struct

    triangles = []
    for tri in row['tris']:
        a, b, c = (tuple(row['verts'][i]) for i in tri)
        triangles.append(min((a, b, c), (b, c, a), (c, a, b)))
    return hashlib.sha256(b''.join(struct.pack('<9d', *(x for v in t for x in v))
                                   for t in sorted(triangles))).hexdigest()


def _remove_polygons(obj, ids):
    mesh = obj.data.copy()
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        bm.faces.ensure_lookup_table()
        faces = [bm.faces[i] for i in ids]
        affected = {v for f in faces for v in f.verts}
        bmesh.ops.delete(bm, geom=faces, context='FACES_ONLY')
        bmesh.ops.delete(bm, geom=[v for v in affected if not v.link_faces], context='VERTS')
        bm.to_mesh(mesh)
    finally:
        bm.free()
    obj.data = mesh


def apply(spec):
    """Plan and validate in memory, then apply only to the selected working scene's collision."""
    scene = bpy.context.scene
    if scene.unit_settings.scale_length != 1.0:
        raise ValueError('passage driver requires a one metre Blender scene unit')
    names = spec['frozen_objects']
    if not names or len(set(names)) != len(names):
        raise ValueError('explicit distinct frozen_objects are required')
    prefix = spec['name_prefix']
    if re.fullmatch(r'UCX_[A-Za-z0-9_]+_Main_', prefix) is None or len(prefix) > 57:
        raise ValueError('expected a Blender-safe UCX_<target>_Main_ prefix')
    excluded = spec.get('exclude_objects', [])
    if (set(excluded) & set(names) or len(set(excluded)) != len(excluded)
            or any(not name.upper().startswith('UCX_') or scene.objects.get(name) is None for name in excluded)):
        raise ValueError('exclude_objects must explicitly name existing non-frozen UCX authoring objects')
    scope = set(names) | set(excluded)
    unlisted = [o.name for o in scene.objects if o.name.upper().startswith('UCX_') and o.name not in scope]
    if unlisted:
        raise ValueError(f'unlisted collision objects: {unlisted}')
    for name in [*names, *excluded]:
        obj = scene.objects[name]
        if len(obj.users_scene) != 1 or any(child.name not in scope for child in obj.children):
            raise ValueError(f'{name}: collision write would affect another scene or an out-of-scope child')
    objects = {name: scene.objects[name] for name in names}
    grouped = {name: list(bodies(obj)) for name, obj in objects.items()}
    if not all(grouped.values()):
        raise ValueError('empty frozen collision object')
    frozen = [row for group in grouped.values() for row in group]
    partitions = spec.get('partitions', {})
    if partitions.keys() - {p['handle'] for p in frozen}:
        raise ValueError('unknown frozen partition ID')
    for p in frozen:
        if p['handle'] in partitions:
            p['partition'] = partitions[p['handle']]
    plan = core.cut_passage(frozen, spec['clearance'], spec.get('fill', ()),
                            spec.get('gap_m', core.GAP_DEFAULT_M))
    occupied = set(bpy.data.objects.keys())
    labels = (f'{prefix}{i:03d}' for i in range(1, 1000))
    free = [name for name in labels if name not in occupied]
    if len(free) < len(plan['new']):
        raise ValueError('not enough free UCX object names')
    kept = set(plan['unchanged'])
    for name, group in grouped.items():
        obj = objects[name]
        removed = [f for row in group if row['handle'] not in kept for f in row['polygons']]
        if removed:
            if len(removed) == len(obj.data.polygons):
                bpy.data.objects.remove(obj, do_unlink=True)
            else:
                _remove_polygons(obj, removed)
    for name in excluded:
        bpy.data.objects.remove(scene.objects[name], do_unlink=True)
    created = []
    for name, part in zip(free, plan.pop('new')):
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(part['verts'], [], part['tris'])
        obj = bpy.data.objects.new(name, mesh)
        scene.collection.objects.link(obj)
        actual, = bodies(obj)
        digest = body_digest(part)
        if body_digest(actual) != digest:
            raise ValueError(f'{name}: Blender readback changed planned triangles')
        created.append({'name': name, 'id': part['handle'], 'source': part['source'], 'sha256': digest,
                        'tris': len(part['tris']), 'volume_m3': part['volume']})
    unchanged = {}
    for name, group in grouped.items():
        expected = {row['handle']: body_digest(row) for row in group if row['handle'] in kept}
        obj = scene.objects.get(name)
        actual = sorted(body_digest(row) for row in bodies(obj)) if obj else []
        if actual != sorted(expected.values()):
            raise ValueError(f'{name}: a retained body changed')
        unchanged.update(expected)
    return dict(plan, unchanged_sha256=unchanged, created=created)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('spec', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    src, spec_path, out = (p.resolve() for p in (args.source, args.spec, args.output))
    report = out.with_suffix('.passage.json')
    if src.suffix.lower() != '.blend' or out.suffix.lower() != '.blend':
        raise ValueError('source and output must be .blend files')
    if out.exists() or report.exists():
        raise FileExistsError('output and passage report must both be new')
    spec_bytes = spec_path.read_bytes()
    spec = json.loads(spec_bytes)
    source_sha = hashlib.sha256(src.read_bytes()).hexdigest()
    if spec['source_sha256'] != source_sha:
        raise ValueError('spec is not bound to this source scene')
    if bpy.ops.wm.open_mainfile(filepath=str(src), load_ui=False, use_scripts=False) != {'FINISHED'}:
        raise RuntimeError('Blender did not load the bound source scene')
    receipt = apply(spec)
    receipt.update(source_sha256=source_sha, spec_sha256=hashlib.sha256(spec_bytes).hexdigest(),
                   blender=bpy.app.version_string)
    with TemporaryDirectory(dir=out.parent) as tmp:
        stage = Path(tmp) / out.name
        if bpy.ops.wm.save_as_mainfile(filepath=str(stage), copy=True, relative_remap=False) != {'FINISHED'}:
            raise RuntimeError('Blender did not save the passage scene')
        if hashlib.sha256(src.read_bytes()).hexdigest() != source_sha:
            raise ValueError('source changed during the cut')
        receipt['output_sha256'] = hashlib.sha256(stage.read_bytes()).hexdigest()
        record = stage.with_suffix('.passage.json')
        record.write_text(json.dumps(receipt, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        os.link(stage, out)
        try:
            os.link(record, report)
        except OSError:
            out.unlink()
            raise
    print(f'UCX_PASSAGE {out}: {len(receipt["replaced"])} replaced, {len(receipt["created"])} new; {report}')


if __name__ == '__main__':
    main()
