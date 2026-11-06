"""new-case: AGR Tools 1.0 (#1024) Quick Attach by material (Keep split by default) / move apart: To = final gap, 3ds Max side. owned by branch G (improve/issue-1024-body).

runtime.edits_100 calls `<function>(ctx, mode, nodes, preview)` for `model_attach_by_material` (model.attach_by_material),
`model_move_apart` (model.move_apart). ctx: agr (runtime globals), core (model10_core), edit (edit_core), emax (edit_max),
options (dict of the preview), host (host_max.MaxHost: ObjRef, user props, one undo record).
Plan mode `undo`: preview changes nothing; apply re-checks the scene state, edits inside ONE undo record
(edit_max.session: selection restored, an error re-raised after the record) and post-checks the result.
Metres via units.SystemScale (host.m_per_unit). No MAXScript globals, no clearUndoBuffer; originals are never
collapsed (attach works on copies and deletes the originals inside the same undo record).
Import pymxs inside functions so this file loads under plain pytest.
"""
import math

ATTACH = 'model.attach_by_material'
MOVE = 'model.move_apart'


def _rt():
    from pymxs import runtime
    return runtime


def _handle(n):
    return int(n.inode.handle)


def _targets(nodes):
    rt = _rt()
    nodes = list(nodes) if nodes is not None else list(rt.selection)
    if not nodes:
        raise ValueError('empty selection: select the objects first')
    return [n for n in nodes if rt.isValidNode(n)]


def _by_handle(handles):
    rt = _rt()
    out = []
    for h in handles:
        n = rt.maxOps.getNodeByHandle(int(h))
        if n is None or not rt.isValidNode(n):
            raise ValueError('node {} of the preview is gone; run preview again'.format(h))
        out.append(n)
    return out


def _is_geometry(n):
    rt = _rt()
    return rt.superClassOf(n) == rt.GeometryClass and rt.classOf(n) != rt.TargetObject and \
        bool(rt.canConvertTo(n, rt.TriMeshGeometry))


def _key(anim):
    return int(_rt().getHandleByAnim(anim))


def _material(n):
    rt = _rt()
    mat = n.material
    if mat is None:
        return None
    if rt.classOf(mat) == rt.MultiMaterial:
        slots = []
        ids = list(mat.materialIDList)
        subs = list(mat.materialList)
        for i, sub in enumerate(subs):
            slots.append({'id': int(ids[i]), 'key': None if sub is None else _key(sub),
                          'name': None if sub is None else str(sub.name)})
        return {'kind': 'multi', 'key': _key(mat), 'name': str(mat.name), 'slots': slots}
    return {'kind': 'single', 'key': _key(mat), 'name': str(mat.name)}


def _tri_area(a, b, c):
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    x, y, z = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    return 0.5 * math.sqrt(x * x + y * y + z * z)


def _attach_object(host, n):
    """Plain data of one node for model10_core.attach_plan (areas in m2 of the evaluated triangles)."""
    rt = _rt()
    h = _handle(n)
    geo = _is_geometry(n)
    out = {'handle': h, 'name': str(n.name), 'geometry': geo, 'cls': str(rt.classOf(n)),
           'material': _material(n) if geo else None, 'face_ids': [], 'face_areas': [],
           'parent': None if n.parent is None else _handle(n.parent),
           'children': [_handle(c) for c in n.children]}
    if geo:
        ref, = host.refs([n])
        mesh = host.mesh(ref)
        v = mesh['verts']
        out['face_ids'] = list(mesh['mat_ids'])
        out['face_areas'] = [_tri_area(v[a], v[b], v[c]) for a, b, c in mesh['faces']]
    return out


def _attach_state(edit, data):
    """What apply must find unchanged: handles, names, materials, face IDs and areas (rounded), hierarchy."""
    return [{'h': o['handle'], 'n': o['name'], 'm': o['material'], 'ids': o['face_ids'],
             'a': round(sum(o['face_areas']), 9), 'p': o['parent'], 'c': sorted(o['children'])} for o in data]


def _scene_names():
    return {str(n.name) for n in _rt().objects}


def _key_str(plan_areas, names):
    return [{'key': k, 'name': 'No_Material' if k is None else names.get(k, ''), 'area_m2': round(a, 9)}
            for k, a in sorted(plan_areas.items(), key=lambda kv: (kv[0] is None, kv[0] or 0))]


def model_attach_by_material(ctx, mode, nodes, preview):
    """Quick Attach by material: Keep split (default) or one object with the full face ID renumbering (L14)."""
    edit, core, host = ctx.edit, ctx.core, ctx.host
    if mode == 'preview':
        nodes = _targets(nodes)
        data = [_attach_object(host, n) for n in nodes]
        plan = core.attach_plan(data, ctx.options, _scene_names() - {o['name'] for o in data})
        objects = []
        for o in data:
            fs = [edit.finding(code, (), detail) for code, detail in plan['findings'].get(o['handle'], ())]
            objects.append(edit.entry(o['handle'], o['name'], fs))
        done = ['{} <- {} object(s) ({})'.format(g['name'], len(g['members']), g['kind']) for g in plan['groups']]
        done += ['re-parent {} child(ren) to {}'.format(len(g['reparent']), g['name'])
                 for g in plan['groups'] if g['reparent']]
        groups = [{'name': g['name'], 'kind': g['kind'], 'key': g['key'], 'members': g['members'],
                   'id_maps': {str(h): {str(k): v for k, v in m.items()} for h, m in g['id_maps'].items()},
                   'slots': g['slots'], 'reparent': g['reparent']} for g in plan['groups']]
        return edit.report(ATTACH, 'preview', objects=objects, done=done,
                           skipped_=[edit.skipped(nm, why) for _h, nm, why in plan['skipped']],
                           ambiguous=[], state_hash=edit.fingerprint(_attach_state(edit, data)),
                           extra={'handles': [o['handle'] for o in data], 'groups': groups,
                                  'options': plan['options'], 'warnings': plan['warnings'],
                                  'areas_before': _key_str(plan['areas'], plan['names'])})
    return _attach_apply(ctx, preview)


def _attach_apply(ctx, preview):
    import time
    edit, emax, core, host = ctx.edit, ctx.emax, ctx.core, ctx.host
    rt = _rt()
    t0 = time.time()
    p = preview['plan']
    nodes = _by_handle(p['handles'])
    data = [_attach_object(host, n) for n in nodes]
    edit.require_current(preview, _attach_state(edit, data))
    by = {o['handle']: o for o in data}
    node_of = {_handle(n): n for n in nodes}
    worked = [h for g in p['groups'] for h in g['members']]
    before = core.material_areas([by[h] for h in worked])
    results, objects, done = [], [], []
    with emax.session(ATTACH):
        with _redraw_off():
            for g in p['groups']:
                results.append((g, _attach_group(ctx, g, node_of, by)))
            for g, base in results:
                for child, _member in g['reparent']:
                    c = rt.maxOps.getNodeByHandle(int(child))
                    if c is not None and rt.isValidNode(c):
                        c.parent = base
            rt.delete([node_of[h] for h in worked])
    after_data = [_attach_object(host, base) for _g, base in results]
    after = core.material_areas(after_data)
    bad = core.compare_areas(before, after)
    names = {}
    for o in data:
        names.update(core._material_names([o]))
    for (g, base), od in zip(results, after_data):
        fs = []
        if bad:
            fs.append(edit.finding('material_area_changed', (), '; '.join(
                '{}: {:.6f} -> {:.6f} m2'.format('No_Material' if k is None else names.get(k, k), a, b)
                for k, a, b in bad)))
        objects.append(edit.entry(_handle(base), str(base.name), fs))
        done.append('{} <- {} object(s), {} faces ({})'.format(str(base.name), len(g['members']),
                                                             len(od['face_ids']), g['kind']))
    return edit.report(ATTACH, 'apply', objects=objects, done=done, skipped_=p['skipped'], ambiguous=[],
                       extra={'results': [{'name': str(b.name), 'handle': _handle(b), 'kind': g['kind'],
                                           'members': len(g['members'])} for g, b in results],
                              'objects_in': len(worked), 'objects_out': len(results),
                              'areas_before': _key_str(before, names), 'areas_after': _key_str(after, names),
                              'warnings': p.get('warnings', []), 'seconds': round(time.time() - t0, 3)})


class _redraw_off:
    def __enter__(self):
        _rt().disableSceneRedraw()

    def __exit__(self, *exc):
        _rt().enableSceneRedraw()
        return False


def _poly_copy(n, id_map=None):
    """Editable_Poly copy of a node (the original is untouched); face IDs remapped through id_map."""
    rt = _rt()
    c = rt.copy(n)
    c.parent = None
    rt.convertTo(c, rt.Editable_Poly)
    if id_map:
        by_id = {}
        for f in range(1, int(rt.polyop.getNumFaces(c)) + 1):
            by_id.setdefault(int(rt.polyop.getFaceMatID(c, f)), []).append(f)
        for old, faces in by_id.items():
            new = id_map[str(old)]
            if new != old:
                rt.polyop.setFaceMatID(c, faces, new)
    return c


def _attach_group(ctx, g, node_of, by):
    rt = _rt()
    one = g['kind'] == 'one'
    first = node_of[g['members'][0]]
    base = _poly_copy(first, g['id_maps'][str(g['members'][0])] if one else None)
    base.parent = first.parent if first.parent is not None and _handle(first.parent) not in node_of else None
    for h in g['members'][1:]:
        c = _poly_copy(node_of[h], g['id_maps'][str(h)] if one else None)
        rt.polyop.attach(base, c)
    if one:
        base.material = _multi(g, node_of, by)
    elif g['kind'] == 'none':
        base.material = None
    else:
        base.material = first.material
    base.name = g['name']
    return base


def _multi(g, node_of, by):
    """Multi/Sub of the «one object» mode: slot i = the i-th shown material (same instance), No_Material a new grey
    standard material; slot IDs 1..n are the remapped face IDs."""
    rt = _rt()
    inst = {}
    for h in g['members']:
        n = node_of[h]
        mat = n.material
        if mat is None:
            continue
        if rt.classOf(mat) == rt.MultiMaterial:
            for sub in mat.materialList:
                if sub is not None:
                    inst[_key(sub)] = sub
        else:
            inst[_key(mat)] = mat
    mm = rt.MultiMaterial(numsubs=len(g['slots']))
    mm.name = 'AGR_' + g['name']
    subs = []
    for s in g['slots']:
        if s['key'] is None:
            sub = rt.StandardMaterial(name='No_Material')
            sub.diffuse = rt.Color(128, 128, 128)
        else:
            sub = inst[s['key']]
        subs.append(sub)
    _fill_multi()(mm, subs, [s['id'] for s in g['slots']], [s['name'] or '' for s in g['slots']])
    return mm


def _fill_multi():
    """A block-local MAXScript function (no global is created) that fills the slots 1..n of a Multi/Sub."""
    return _rt().execute('(fn agrFill mm subs ids nms = (for i = 1 to subs.count do (mm.materialList[i] = subs[i]; '
                         'mm.materialIDList[i] = ids[i]; mm.names[i] = nms[i]); ok); agrFill)')


# ---- move apart -----------------------------------------------------------------------------------------------
def _poly_kind(n):
    """'poly' | 'mesh' | None (with the reason) for model.move_apart: an editable base without modifiers."""
    rt = _rt()
    if not _is_geometry(n):
        return None, 'not geometry ({})'.format(str(rt.classOf(n)))
    if len(list(n.modifiers)):
        return None, 'has a modifier stack; collapse is not done on originals'
    obj = n.baseObject
    if rt.classOf(obj) == rt.Editable_Poly:
        return 'poly', ''
    if rt.classOf(obj) == rt.Editable_mesh:
        return 'mesh', ''
    return None, 'base object {} is not Editable_Poly/Editable_Mesh'.format(str(rt.classOf(obj)))


def _read_local(n, kind):
    rt = _rt()
    obj = n.baseObject
    if kind == 'poly':
        nv = int(rt.polyop.getNumVerts(obj))
        verts = [rt.polyop.getVert(obj, i) for i in range(1, nv + 1)]
        faces = [[int(i) - 1 for i in rt.polyop.getFaceVerts(obj, f)] for f in
                 range(1, int(rt.polyop.getNumFaces(obj)) + 1)]
    else:  # Editable_Mesh base object: meshop without node -> object-space coordinates
        verts = [rt.meshop.getVert(obj, i) for i in range(1, int(rt.meshop.getNumVerts(obj)) + 1)]
        tri = obj.mesh
        faces = []
        for f in range(1, int(rt.meshop.getNumFaces(obj)) + 1):
            fc = rt.getFace(tri, f)
            faces.append([int(fc.x) - 1, int(fc.y) - 1, int(fc.z) - 1])
    return verts, faces


def _move_object(n, kind, k):
    """World vertices in metres + faces (0-based) of an editable node."""
    verts, faces = _read_local(n, kind)
    tm = n.objectTransform
    world = []
    for p in verts:
        w = p * tm
        world.append([float(w.x) * k, float(w.y) * k, float(w.z) * k])
    return {'verts': world, 'faces': faces}


def _move_state(nodes, data):
    return [{'h': _handle(n), 'n': str(n.name), 'v': [[round(c, 9) for c in p] for p in d['verts']],
             'f': d['faces']} for n, d in zip(nodes, data)]


def model_move_apart(ctx, mode, nodes, preview):
    """Move apart pairs of parallel faces with a gap in [min, max] to the final gap To (L14, owner 06.11.2026)."""
    edit, core, host = ctx.edit, ctx.core, ctx.host
    if mode == 'apply':
        return _move_apply(ctx, preview)
    nodes = _targets(nodes)
    k = host.m_per_unit()
    work, kinds, skipped = [], [], []
    for n in nodes:
        kind, why = _poly_kind(n)
        if kind is None:
            skipped.append(edit.skipped(str(n.name), why))
        else:
            work.append(n)
            kinds.append(kind)
    if not work:
        raise ValueError('model.move_apart: no Editable_Poly/Editable_Mesh object without modifiers in the selection')
    data = [_move_object(n, kd, k) for n, kd in zip(work, kinds)]
    plan = core.move_plan(data, ctx.options)
    names = [str(n.name) for n in work]
    objects = []
    for i, n in enumerate(work):
        ids = plan['faces'].get(i, [])
        fs = [edit.finding('double_faces', ids[:1000], '{} face(s) in pairs with a gap in [{:g}, {:g}] mm -> {:g} mm'
                           .format(len(ids), plan['opts']['min_m'] * 1000, plan['opts']['max_m'] * 1000,
                                   plan['opts']['to_m'] * 1000))] if ids else []
        objects.append(edit.entry(_handle(n), names[i], fs))
    for p, why in plan['skipped']:
        r = core.pair_row(p, names)
        skipped.append(edit.skipped('{}#{} / {}#{}'.format(r['a'][0], r['a'][1], r['b'][0], r['b'][1]), why))
    rows = [core.pair_row(p, names) for p in plan['pairs']]
    moves = {str(_handle(work[oi])): {str(v): [round(c, 12) for c in vec] for v, vec in m.items()}
             for oi, m in plan['moves'].items()}
    done = ['{}#{} / {}#{} ({}): {:.3f} mm -> {:.3f} mm'.format(r['a'][0], r['a'][1], r['b'][0], r['b'][1], r['kind'],
                                                             r['gap_mm'], plan['opts']['to_m'] * 1000) for r in rows]
    return edit.report(MOVE, 'preview', objects=objects, done=done, skipped_=skipped, ambiguous=[],
                       state_hash=edit.fingerprint(_move_state(work, data)),
                       extra={'handles': [_handle(n) for n in work], 'kinds': kinds, 'pairs': rows, 'moves': moves,
                              'options': plan['opts'], 'm_per_unit': k,
                              'counts': {'found': len(rows) + len(plan['skipped']), 'moved': len(rows),
                                         'skipped': len(plan['skipped'])}})


def _move_apply(ctx, preview):
    edit, emax, core, host = ctx.edit, ctx.emax, ctx.core, ctx.host
    rt = _rt()
    p = preview['plan']
    nodes = _by_handle(p['handles'])
    k = host.m_per_unit()
    if abs(k - p['m_per_unit']) > 1e-15:
        raise edit.StalePreview('system units changed since the preview; run preview again')
    data = [_move_object(n, kd, k) for n, kd in zip(nodes, p['kinds'])]
    edit.require_current(preview, _move_state(nodes, data))
    with emax.session(MOVE):
        for n, kind, d in zip(nodes, p['kinds'], data):
            m = p['moves'].get(str(_handle(n)))
            if not m:
                continue
            inv = rt.inverse(n.objectTransform)
            obj = n.baseObject
            for v, vec in m.items():
                i = int(v)
                w = d['verts'][i]
                pt = rt.Point3((w[0] + vec[0]) / k, (w[1] + vec[1]) / k, (w[2] + vec[2]) / k) * inv
                if kind == 'poly':
                    rt.polyop.setVert(obj, [i + 1], pt)
                else:
                    rt.meshop.setVert(obj, [i + 1], pt)
            if kind == 'mesh':
                rt.update(n)
    # post-check: the gap of every moved pair is To +- 0.01 mm
    after = [_move_object(n, kd, k) for n, kd in zip(nodes, p['kinds'])]
    index = {str(n.name): i for i, n in enumerate(nodes)}
    to = p['options']['to_m']
    bad = {}
    rows = []
    for r in p['pairs']:
        a, b = (index[r['a'][0]], r['a'][1] - 1), (index[r['b'][0]], r['b'][1] - 1)
        g = core.gap_after(after, {'a': a, 'b': b})
        rows.append(dict(r, gap_after_mm=round(g * 1000.0, 6)))
        if abs(g - to) > core.GAP_TOL_M:
            for oi, fi in (a, b):
                bad.setdefault(oi, []).append(fi + 1)
    objects = []
    for i, n in enumerate(nodes):
        fs = [edit.finding('gap_not_reached', sorted(set(bad[i]))[:1000], 'gap after differs from To {:g} mm'.format(
            to * 1000))] if i in bad else []
        objects.append(edit.entry(_handle(n), str(n.name), fs))
    done = ['{}#{} / {}#{} ({}): {:.3f} -> {:.3f} mm'.format(r['a'][0], r['a'][1], r['b'][0], r['b'][1], r['kind'],
                                                          r['gap_mm'], r['gap_after_mm']) for r in rows]
    return edit.report(MOVE, 'apply', objects=objects, done=done, skipped_=p['skipped'], ambiguous=[],
                       extra={'pairs': rows, 'counts': p['counts'], 'options': p['options']})
