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


def region_finishes(vertices, faces, ids, spec):
    """Slide39/40 overrides; retain original ID and coordinates on every face."""
    import math
    if not faces or len(faces) != len(ids):
        raise ValueError('empty or partial face/ID inventory')
    if any(len(v) != 3 or not all(math.isfinite(c) for c in v) for v in vertices):
        raise ValueError('non-finite vertex')
    result = []
    for f, sid in zip(faces, ids):
        p = [vertices[k] for k in f]
        normal = [sum((a[1] - b[1]) * (a[2] + b[2]) for a, b in zip(p, p[1:] + p[:1])),
                  sum((a[2] - b[2]) * (a[0] + b[0]) for a, b in zip(p, p[1:] + p[:1])),
                  sum((a[0] - b[0]) * (a[1] + b[1]) for a, b in zip(p, p[1:] + p[:1]))]
        length = math.sqrt(sum(c*c for c in normal))
        if length <= 0:
            raise ValueError('degenerate region face')
        vertical = abs(normal[2]) / length < 0.001
        tall = max(v[2] for v in p) - min(v[2] for v in p) > 0.08
        wide = max(max(v[a] for v in p)-min(v[a] for v in p) for a in (0,1)) > 0.08
        if (sid == 1 and abs(normal[2])/length < 0.999999) or (sid == 2 and ((vertical and tall and wide) or max(v[2] for v in p) < 3.0)):
            finish = 'Sandwich_RAL5015'
        elif sid == 3:
            finish = 'Sandwich_RAL7047'
        else:
            rule = spec['source_ids'].get(str(sid))
            if rule is None:
                raise ValueError(f'unmapped material ID {sid}')
            finish = (rule['below'] if max(v[2] for v in p) <= spec['zero_m'] else rule['above']) if rule.get('split') else rule['finish']
        if finish.startswith('Sandwich_') and abs(normal[0]) > abs(normal[1]):
            finish = finish.replace('Sandwich_', 'SandwichEast_' if normal[0] > 0 else 'SandwichShort_')
        if finish.startswith('Sandwich_') and normal[1] < 0:
            finish = finish.replace('Sandwich_', 'SandwichSouth_')
        result.append(finish)
    return result


def collision_triangles(vertices, faces):
    """Choose convex cap fans using only original corners; never move a vertex.

    Max's cap is mildly nonplanar. BEAUTY chooses skinny triangles whose
    planes overshoot 1e-5 m. Select the fan with the smallest supporting-plane
    residual; refuse a genuinely concave source instead of rebuilding a hull.
    """
    import numpy as np
    v = np.asarray(vertices, float)
    if not faces or v.ndim != 2 or v.shape[1] != 3 or not np.isfinite(v).all():
        raise ValueError('invalid collision triangulation input')
    triangles = []
    for f in faces:
        choices = []
        for a in range(len(f)):
            ring = f[a:] + f[:a]
            tris = [[ring[0], ring[k], ring[k+1]] for k in range(1, len(ring)-1)]
            residual = 0.0
            for tri in tris:
                p = v[tri]
                n = np.cross(p[1]-p[0], p[2]-p[0])
                length = np.linalg.norm(n)
                if length <= 1e-12:
                    residual = float('inf')
                    break
                residual = max(residual, float(((v-p[0]) @ (n/length)).max()))
            choices.append((residual, a, tris))
        residual, _, tris = min(choices)
        if residual > 1e-5:
            raise ValueError(f'collision triangulation exceeds supporting-plane bound: {residual}')
        triangles.extend(tris)
    return triangles


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
    import finish_map
    from mathutils import Vector
    names = sorted(spec['finishes'], key=lambda n: spec['finishes'][n]['udim'])
    V, F, IDs = body['vertices'], body['faces'], body['mat_ids']
    finishes = region_finishes(V, F, IDs, spec)
    bm = bmesh.new()
    fl = bm.faces.layers.int.new('finish')
    sid = bm.faces.layers.int.new('srcid')
    flag = bm.faces.layers.int.new('uvx')
    uvm = bm.loops.layers.uv.new('UVM')
    vs = [bm.verts.new(p) for p in V]
    lo, hi = finish_map.body_plan_bbox(V, spec['zero_m'])
    for f, material_id, finish in zip(F, IDs, finishes):
        nf = bm.faces.new([vs[k] for k in f])
        nf[fl], nf[sid] = names.index(finish), material_id
        if finish.startswith('Sandwich'):
            n = finish_map._newell([V[k] for k in f])
            if abs(n[2]) < 0.001:
                axis = 0 if abs(n[1]) >= abs(n[0]) else 1
                # Shared global grid, NOT a new phase on each source polygon.
                nf[flag] = 1
                for l, k in zip(nf.loops, f):
                    l[uvm].uv = (V[k][axis] - spec['rib_fields']['east' if axis == 1 and n[0] > 0 else ('south' if axis == 0 and n[1] < 0 else str(axis))]['lo'], V[k][2])
            else:
                # Canopy top/soffit: same joint profile in planar metre UVs.
                # Sloped roof itself forms the visible roof-edge band in this source.
                # Use an orthonormal in-plane frame; the eave direction stays horizontal.
                normal = Vector(n)
                axis = 0 if abs(n[1]) >= abs(n[0]) else 1
                along = Vector((1,0,0) if axis == 0 else (0,1,0))
                along = (along-normal*normal.dot(along)).normalized()
                across = normal.cross(along).normalized()
                projected = [Vector((Vector(V[k]).dot(along)-spec['rib_fields']['east' if axis == 1 and n[0] > 0 else ('south' if axis == 0 and n[1] < 0 else str(axis))]['lo'],
                                     Vector(V[k]).dot(across))) for k in f]
                base = min(p.y for p in projected)
                nf[flag] = 1
                for l, p in zip(nf.loops, projected):
                    l[uvm].uv = (p.x, p.y-base+spec['pad_m'])
    bm.normal_update()
    region_uv = vpm_uv.pack_uv(bm, names, spec)
    if any(q['overflow'] for q in region_uv.values()):
        raise ValueError(f'presentation UV overflow: {region_uv}')
    density = vpm_uv.density_qa(bm, names, spec)
    main_obj = bpy.data.objects['SM_' + spec['address'] + '_Main']
    bm.to_mesh(main_obj.data)
    bm.free()
    for layer in list(main_obj.data.uv_layers):
        if layer.name != 'UVMap':
            main_obj.data.uv_layers.remove(layer)
    main_obj.data.uv_layers.active = main_obj.data.uv_layers['UVMap']
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
    # Export representation only: supporting-plane cap fan, same original corners.
    for index, source in enumerate(sorted(hulls, key=lambda n: n['name']), start=1):
        o = bpy.data.objects[f'UCX_SM_{spec["address"]}_Main_{index:03d}']
        tris = collision_triangles(source['vertices'], source['faces'])
        mesh_data = bpy.data.meshes.new(o.name + '_tri')
        mesh_data.from_pydata(source['vertices'], [], tris)
        mesh_data.update()
        o.data = mesh_data
    out = root / (spec['address'] + '_VPM_master.blend')
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    report = {'source_dump': str(Path(dump_path).resolve()), 'main_handle': body['handle'],
              'glass_handle': glass['handle'], 'collision_handles': [n['handle'] for n in hulls],
              'dropped_nodes': [], 'glass_uv': uvqa, 'region_uv': region_uv, 'density': density, 'source_faces': len(F), 'region_faces': len(main_obj.data.polygons), 'ring_cuts': [], 'master': str(out)}
    (root / 'adapter.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('AC06-ADAPTER', json.dumps(report))


if __name__ == '__main__':
    main()
