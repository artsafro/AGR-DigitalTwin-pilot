"""new-case: AGR Tools 1.0.x (#1024, branch BH) Max <-> Blender handoff, Blender side (headless, Blender 5.1.2).

    blender --background --factory-startup --python-exit-code 1 --python tools/blender/handoff_blender.py -- \
        <bundle dir> [<bundle dir> ...]
    env AGR_TEST_OUTPUT: a NEW folder; per bundle <out>/<seq>/ gets
        readback_blender.json   facts of the imported bundle (handoff_core.finish_facts, same shape as readback_max),
        verify_blender.json     handoff_core.compare(readback_max, readback_blender) by the rows of REPORT 3.12,
        return/model.fbx        the model exported back for Max (handoff.import), no triangulation,
        verify_return.json      the returned FBX read back in a fresh factory Blender and compared again.

Functions `import_bundle(bundle)` / `export_bundle(path)` are what an agent script calls around its edits (D108 ops
in Blender); the CLI does the plain round trip. The bundle is only read. Importer/exporter settings keep names, slots,
both UV channels, custom normals, units (metres, scale 1), pivots, quads/n-gons and linked meshes (instances).
Defect handled here: the FBX importer turns Max smoothing groups (by polygon) into custom normals only, so the sharp
edges are lost and the export back writes one smoothing group; `mark_sharp_from_normals` restores the sharp edges
from the corner normals before export (hard edges row of 3.12).
"""
import importlib.util
import json
import os
from pathlib import Path
import sys

import bpy

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('agr_handoff_core', ROOT / 'adapters/max/agr_tools/handoff_core.py')
core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(core)

IMPORT_KW = dict(use_custom_normals=True, use_image_search=False, use_custom_props=True,
                 use_custom_props_enum_as_string=True, bake_space_transform=False, use_anim=False,
                 global_scale=1.0)
EXPORT_KW = dict(use_selection=True, object_types={'MESH', 'EMPTY'}, global_scale=1.0, apply_unit_scale=True,
                 apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Y', axis_up='Z', bake_space_transform=False,
                 use_mesh_modifiers=False, mesh_smooth_type='SMOOTH_GROUP', use_triangles=False,
                 use_custom_props=True, add_leaf_bones=False, bake_anim=False, path_mode='AUTO',
                 embed_textures=False, use_tspace=False)


def _read(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _supported(op_props, kw):
    """Keep only the keyword arguments this Blender's operator knows (5.1.2 is pinned; a rename is reported)."""
    names = {p.identifier for p in op_props}
    return {k: v for k, v in kw.items() if k in names}, sorted(set(kw) - names)


def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    probe = bpy.data.lights.new('__handoff_probe', 'POINT')  # fbx_readback.light_import_compat (Blender 5.1.2)
    try:
        cyc = getattr(probe, 'cycles', None)
        if cyc is not None and not hasattr(cyc, 'cast_shadow'):
            type(cyc).cast_shadow = bpy.props.BoolProperty(default=True)
    finally:
        bpy.data.lights.remove(probe)


def import_fbx(path):
    kw, missing = _supported(bpy.ops.import_scene.fbx.get_rna_type().properties, IMPORT_KW)
    bpy.ops.import_scene.fbx(filepath=str(path), **kw)
    return missing


def restore_names(manifest):
    """Blender `.001` / 63-byte names back to the manifest names (objects and slot materials)."""
    known = [o['name'] for o in manifest['objects']]
    objs = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    mapping = core.restore_names([o.name for o in objs], known)
    renamed = []
    for o in objs:
        want = mapping.get(o.name)
        if want and want != o.name and want not in bpy.data.objects:
            renamed.append([o.name, want])
            o.name = want
    return renamed


def _matrix(rows):
    from mathutils import Matrix
    return Matrix([[rows[0][0], rows[1][0], rows[2][0], rows[3][0]],
                   [rows[0][1], rows[1][1], rows[2][1], rows[3][1]],
                   [rows[0][2], rows[1][2], rows[2][2], rows[3][2]],
                   [0.0, 0.0, 0.0, 1.0]])


def normalise(manifest):
    """Object matrices = the Max node transforms of the manifest (pivots), scale 1, mesh data in metres.

    Measured (lab job 20261106-134044-fbdf80ba): the importer folds the Max object offset (FBX geometric transform)
    and the cm unit scale (0.01) into the OBJECT matrix, so a child inherits its parent's pivot offset (GLASS_001 moved
    by the offset of BODY_Brick_001). For every object G = (P_cur @ L)^-1 @ M_cur (L = node local of the manifest)
    goes into the mesh data and the object gets the manifest transform. Returns [problems]."""
    from mathutils import Matrix
    ref = {o['name']: o for o in manifest['objects']}
    objs = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.name in ref]
    world = {n: _matrix(o['world']) for n, o in ref.items()}
    geo, local = {}, {}
    for obj in objs:
        r = ref[obj.name]
        p_ref = world[r['parent']] if r['parent'] in world and r['parent'] in bpy.data.objects else Matrix.Identity(4)
        p_cur = obj.parent.matrix_world.copy() if obj.parent else Matrix.Identity(4)
        local[obj.name] = p_ref.inverted() @ world[obj.name]
        geo[obj.name] = (p_cur @ local[obj.name]).inverted() @ obj.matrix_world
    problems, done = [], {}
    for obj in objs:
        g = geo[obj.name]
        key = obj.data.name
        if key in done:
            if max(abs(a - b) for ra, rb in zip(done[key], g) for a, b in zip(ra, rb)) > 1e-9:
                obj.data = obj.data.copy()
                obj.data.transform(g)
                problems.append(obj.name + ': shared mesh with another offset made single-user')
            continue
        obj.data.transform(g)
        done[key] = g
    depth = {}

    def d(o):
        if o.name not in depth:
            depth[o.name] = 0 if o.parent is None else d(o.parent) + 1
        return depth[o.name]
    for obj in sorted(objs, key=d):
        obj.matrix_parent_inverse = Matrix.Identity(4)
        obj.matrix_basis = local[obj.name] if obj.parent is not None and obj.parent.name in world else world[obj.name]
    bpy.context.view_layer.update()
    return problems


def relink_instances(manifest):
    """Objects whose manifest instance_of names a leader share the leader's mesh again (linked duplicates) when the
    two meshes are equal in object space (the FBX of the bundle carries no instances, see FBX_EXPORT_PARAMS)."""
    linked = []
    for o in manifest['objects']:
        lead = o['instance_of']
        if not lead or o['name'] not in bpy.data.objects or lead not in bpy.data.objects:
            continue
        a, b = bpy.data.objects[o['name']], bpy.data.objects[lead]
        if a.data is b.data:
            continue
        va, vb = a.data.vertices, b.data.vertices
        if len(va) == len(vb) and len(a.data.polygons) == len(b.data.polygons) and \
                all((p.co - q.co).length < 1e-6 for p, q in zip(va, vb)):
            old = a.data
            a.data = b.data
            if old.users == 0:
                bpy.data.meshes.remove(old)
            linked.append([o['name'], lead])
    return linked


def mark_sharp_from_reference(ref_facts):
    """Sharp edges = the hard edges of readback_max (edge midpoints, world metres); objects without a reference fall
    back to the corner normals. Returns {object: marked}."""
    by = {f['name']: f for f in ref_facts}
    out = {}
    seen = set()
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH' or obj.data.name in seen:
            continue
        seen.add(obj.data.name)
        ref = by.get(obj.name)
        if ref is None:
            out[obj.name] = mark_sharp_from_normals(obj.data)
            continue
        idx = core.hard_index(ref['hard'])
        mw = obj.matrix_world
        mesh = obj.data
        n = 0
        for e in mesh.edges:
            a, b = (mw @ mesh.vertices[i].co for i in e.vertices)
            want = idx.find([(a[k] + b[k]) / 2 for k in range(3)], core.TOL['pos_m']) is not None
            if e.use_edge_sharp != want:
                e.use_edge_sharp = want
                n += 1
        out[obj.name] = n
    return out


def import_bundle(bundle):
    """Fresh factory scene + the bundle's model.fbx with the handoff fixes (names, pivots/units, instances, sharp
    edges); returns (manifest, notes)."""
    bundle = Path(bundle)
    manifest = core.validate_manifest(_read(bundle / 'manifest.json'))
    ref = _read(bundle / 'readback_max.json')['objects']
    fresh()
    notes = {'importer_options_missing': import_fbx(bundle / manifest['fbx']['file'])}
    notes['renamed'] = restore_names(manifest)
    notes['normalise'] = normalise(manifest)
    notes['instances_linked'] = relink_instances(manifest)
    notes['sharp'] = mark_sharp_from_reference(ref)
    return manifest, notes


def mark_sharp_from_normals(mesh):
    """Mark interior edges sharp where the corner normals of the two faces differ (FBX smoothing by polygon came in
    as custom normals only). Returns the number of edges marked."""
    normals = mesh.corner_normals
    faces = [[mesh.loops[li].vertex_index for li in range(p.loop_start, p.loop_start + p.loop_total)]
             for p in mesh.polygons]
    corners = [[list(normals[li].vector) for li in range(p.loop_start, p.loop_start + p.loop_total)]
               for p in mesh.polygons]
    sharp = core.sharp_edges(faces, corners)
    marked = 0
    for e in mesh.edges:
        if tuple(sorted(e.vertices)) in sharp and not e.use_edge_sharp:
            e.use_edge_sharp = True
            marked += 1
    return marked


def _channel(name, index):
    digits = ''.join(ch for ch in name.split('_')[-1] if ch.isdigit())
    return int(digits) if name.lower().startswith('uvchannel_') and digits else index + 1


def _role(obj):
    for key in ('agr_role',):
        if key in obj.keys():
            return str(obj[key])
    udp = obj.get('UDP3DSMAX')
    if isinstance(udp, str):
        return core.parse_user_props(udp).get('agr_role')
    return None


def facts(manifest, ref_facts=()):
    """Host-neutral facts of the scene's meshes. matID of a face: the slot material's ID in the slot table; where the
    slot cannot tell (one material for several IDs), the ID of the reference face at the same centre; -1 = none."""
    by = {o['name']: o for o in manifest['objects']}
    ref_by = {f['name']: f for f in ref_facts}
    meshes = sorted((o for o in bpy.context.scene.objects if o.type == 'MESH'), key=lambda o: o.name)
    users = {}
    for o in meshes:
        users.setdefault(o.data.name, []).append(o.name)
    out = []
    for obj in meshes:
        mesh = obj.data
        mw = obj.matrix_world
        verts = [list(mw @ v.co) for v in mesh.vertices]
        slots = by.get(obj.name, {}).get('slots', [])
        faces, ids, unknown = [], [], []
        for p in mesh.polygons:
            faces.append(list(p.vertices))
            mat = obj.material_slots[p.material_index].material if p.material_index < len(obj.material_slots) else None
            mid = core.matid_of_material(slots, mat.name) if mat is not None else None
            if mid is None:
                unknown.append(p.index)
            ids.append(-1 if mid is None else mid)
        if unknown and obj.name in ref_by:
            centres = [[sum(verts[v][k] for v in faces[i]) / len(faces[i]) for k in range(3)] for i in unknown]
            for i, mid in zip(unknown, core.ids_by_centre(ref_by[obj.name]['face_keys'], centres)):
                if mid is not None:
                    ids[i] = mid
        faces_of = {}
        for p in mesh.polygons:
            for ek in p.edge_keys:
                faces_of.setdefault(tuple(sorted(ek)), []).append(p.index)
        hard = []
        for e in mesh.edges:
            fs = faces_of.get(tuple(sorted(e.vertices)), [])
            if len(fs) != 2:
                continue
            if e.use_edge_sharp or not mesh.polygons[fs[0]].use_smooth or not mesh.polygons[fs[1]].use_smooth:
                a, b = (verts[i] for i in e.vertices)
                hard.append([(a[k] + b[k]) / 2 for k in range(3)])
        uv = {}
        for i, layer in enumerate(mesh.uv_layers):
            per = []
            for p in mesh.polygons:
                per.append([[float(layer.data[li].uv.x), float(layer.data[li].uv.y)]
                            for li in range(p.loop_start, p.loop_start + p.loop_total)])
            uv[_channel(layer.name, i)] = per
        group = users[mesh.name]
        leader = sorted(group)[0] if len(group) > 1 else None
        out.append(core.finish_facts(obj.name, core.rows_from_columns(mw), verts, faces, ids, len(mesh.edges), hard,
                                     uv, role=_role(obj), parent=obj.parent.name if obj.parent else None,
                                     scale=list(mw.to_scale()), instance_group=leader))
    return out


def export_bundle(path):
    """Export every mesh/empty of the scene as a working FBX for handoff.import (smoothing groups computed from the
    sharp edges, so mark new hard edges of an edit before calling this)."""
    bpy.ops.object.select_all(action='DESELECT')
    for obj in bpy.context.scene.objects:
        if obj.type in ('MESH', 'EMPTY'):
            obj.select_set(True)
    Path(path).parent.mkdir(parents=True, exist_ok=False)
    kw, missing = _supported(bpy.ops.export_scene.fbx.get_rna_type().properties, EXPORT_KW)
    bpy.ops.export_scene.fbx(filepath=str(path), **kw)
    return missing


def _dump(path, doc):
    Path(path).write_text(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True), encoding='utf-8')


def roundtrip(bundle, out):
    bundle, out = Path(bundle), Path(out)
    out.mkdir(parents=True, exist_ok=False)
    ref = _read(bundle / 'readback_max.json')['objects']
    manifest, notes = import_bundle(bundle)
    got = facts(manifest, ref)
    _dump(out / 'readback_blender.json', core.build_readback('blender', bpy.app.version_string, got))
    res = core.compare(ref, got, check_roles=False)
    _dump(out / 'verify_blender.json', dict(notes, count=core.discrepancy_count(res), rows=res,
                                            table=core.summary_table(res)))
    ret = out / 'return' / 'model.fbx'
    missing_out = export_bundle(ret)
    # our own export read back by the Blender importer (names + sharp edges by the same fixes, transforms as they
    # come): separates a loss of the Blender export from one of the Max import
    fresh()
    import_fbx(ret)
    restore_names(manifest)
    sharp = mark_sharp_from_reference(ref)
    back = facts(manifest, ref)
    res2 = core.compare(ref, back, check_roles=False)
    _dump(out / 'verify_return.json', {'sharp_marked': sharp, 'exporter_options_missing': missing_out,
                                       'count': core.discrepancy_count(res2), 'rows': res2,
                                       'table': core.summary_table(res2)})
    return {'bundle': str(bundle), 'out': str(out), 'objects': len(got), 'blender_count': core.discrepancy_count(res),
            'return_count': core.discrepancy_count(res2), 'fbx': str(ret), 'notes': notes}


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    if not args:
        raise SystemExit('usage: ... -- <bundle dir> [<bundle dir> ...]  (env AGR_TEST_OUTPUT: a new folder)')
    out = Path(os.environ['AGR_TEST_OUTPUT'])
    out.mkdir(parents=True, exist_ok=False)
    summary = {'blender': bpy.app.version_string, 'bundles': [], 'errors': {}}
    for b in args:
        name = Path(b).name
        try:
            summary['bundles'].append(roundtrip(b, out / name))
        except Exception as exc:  # noqa: BLE001 - recorded, the run fails at the end
            import traceback
            summary['errors'][name] = traceback.format_exc()[-3000:]
            print('handoff_blender:', name, exc)
    _dump(out / 'summary.json', summary)
    print('HANDOFF_BLENDER', json.dumps({b['bundle']: [b['blender_count'], b['return_count']]
                                         for b in summary['bundles']}))
    if summary['errors']:
        sys.exit(2)


if __name__ == '__main__':
    main()
