"""new-case: AGR Tools 0.9 (#979) place block, 3ds Max side. Owned by branch A (improve/issue-979-place).

runtime.edits_090 calls `<function>(ctx, mode, nodes, preview)` for `place_replace` (place.replace), `place_schedule`
(place.schedule), `place_drop_to_ground` (place.drop_to_ground), `place_maf_checks` (place.maf_checks),
`place_flora_repair` (place.flora_repair).
ctx: agr (runtime globals), core (place_core), edit (edit_core), emax (edit_max), options (dict of the preview).
Import pymxs inside functions so this file loads under plain pytest.

Modes (plan): replace and drop_to_ground edit the scene in ONE undo record per apply (`undo`); schedule and
flora_repair only create new nodes on their own layer (`copies`); maf_checks only reads (`read`, no apply).
The originals of schedule / flora_repair are never changed or deleted. Units: system units -> metres through
units.SystemType / SystemScale (place_core.m_per_unit), never units.decodeValue (ru-RU, T05).
"""
EXPORT_LAYER = 'AGR_export'
SCHEDULE_PROP_ROW = 'AGR_SCHEDULE_ROW'
SCHEDULE_PROP_MODEL = 'AGR_SCHEDULE_MODEL'
FLORA_SUFFIX = '_AGR_flora_'
READBACK_TOL_M = 0.0005

_MXS = r'''
global agr979_meshData, agr979_triData, agr979_faceDeg
fn agr979_g v = formattedPrint v format:".17g"
fn agr979_meshData n = (
    -- world vertices (snapshotAsMesh is already in world space) and 1-based triangles
    local m = snapshotAsMesh n
    local ss = stringStream ""
    local nv = m.numverts
    local nf = m.numfaces
    format "% %\n" nv nf to:ss
    for i = 1 to nv do (
        local p = getVert m i
        format "% % %\n" (agr979_g p.x) (agr979_g p.y) (agr979_g p.z) to:ss
    )
    for f = 1 to nf do (
        local t = getFace m f
        format "% % %\n" (t.x as integer) (t.y as integer) (t.z as integer) to:ss
    )
    delete m
    ss as string
)
fn agr979_triData n = (
    -- per triangle: material ID, then 3 corners x y z [u v] in world space
    local m = snapshotAsMesh n
    local ss = stringStream ""
    local nf = m.numfaces
    local ntv = getNumTVerts m
    format "% %\n" nf ntv to:ss
    for f = 1 to nf do (
        local t = getFace m f
        local tv = if ntv > 0 then getTVFace m f else [0, 0, 0]
        format "%" (getFaceMatID m f) to:ss
        for k = 1 to 3 do (
            local p = getVert m t[k]
            format " % % %" (agr979_g p.x) (agr979_g p.y) (agr979_g p.z) to:ss
            if ntv > 0 do (
                local uv = getTVert m tv[k]
                format " % %" (agr979_g uv.x) (agr979_g uv.y) to:ss
            )
        )
        format "\n" to:ss
    )
    delete m
    ss as string
)
fn agr979_faceDeg n = for f = 1 to (polyop.getNumFaces n) collect (polyop.getFaceDeg n f)
'''


def _rt():
    from pymxs import runtime
    return runtime


def _mxs():
    rt = _rt()
    rt.execute(_MXS)
    return rt


def _handle(n):
    return int(_rt().getHandleByAnim(n))


def _targets(nodes, what='objects'):
    rt = _rt()
    if nodes is None:
        nodes = list(rt.selection)
    nodes = list(nodes)
    if not nodes:
        raise ValueError('nothing selected: select the ' + what)
    seen, out = set(), []
    for n in nodes:
        if not rt.isValidNode(n):
            raise ValueError('invalid node')
        h = _handle(n)
        if h not in seen:
            seen.add(h)
            out.append(n)
    return sorted(out, key=_handle)


def _by_handles(handles):
    rt = _rt()
    out = []
    for h in handles:
        n = rt.getAnimByHandle(int(h))
        if n is None or not rt.isValidNode(n):
            raise ValueError('a node of the preview is gone; run preview again')
        out.append(n)
    return out


def _named(name):
    rt = _rt()
    found = [o for o in rt.objects if str(o.name) == name]
    if not found:
        raise ValueError('no object named ' + repr(name))
    if len(found) > 1:
        raise ValueError('several objects named {!r}: the name must be unique'.format(name))
    return found[0]


def _geometry(n):
    rt = _rt()
    return bool(rt.superClassOf(n) == rt.GeometryClass and rt.canConvertTo(n, rt.TriMeshGeometry))


def _hidden(n):
    try:
        return bool(n.isHiddenInVpt)
    except Exception:  # noqa: BLE001 - older property name
        return bool(n.isHidden)


def _mpu(core):
    rt = _rt()
    return core.m_per_unit(str(rt.units.SystemType), float(rt.units.SystemScale))


def _units(core):
    rt = _rt()
    return {'type': str(rt.units.SystemType), 'scale': float(rt.units.SystemScale), 'm_per_unit': _mpu(core)}


def _mesh(n, mpu):
    """(world vertices in metres, 0-based triangles) of the evaluated mesh."""
    rt = _mxs()
    lines = str(rt.agr979_meshData(n)).split('\n')
    nv, nf = (int(x) for x in lines[0].split())
    verts = [tuple(float(x) * mpu for x in lines[1 + i].split()) for i in range(nv)]
    tris = [tuple(int(x) - 1 for x in lines[1 + nv + f].split()) for f in range(nf)]
    return verts, tris


def _rows(tm, mpu):
    return [[float(r.x), float(r.y), float(r.z)] for r in (tm.row1, tm.row2, tm.row3)] + [
        [float(tm.row4.x) * mpu, float(tm.row4.y) * mpu, float(tm.row4.z) * mpu]]


def _matrix(rows, mpu):
    rt = _rt()
    axes = [rt.Point3(*(float(v) for v in r)) for r in rows[:3]]
    return rt.Matrix3(axes[0], axes[1], axes[2], rt.Point3(*(float(v) / mpu for v in rows[3])))


def _grounds(core, names, exclude=()):
    rt = _rt()
    if names:
        nodes = [_named(n) for n in names]
    else:
        nodes = [o for o in rt.objects if core.is_ground_name(o.name) and _geometry(o)]
    nodes = [n for n in nodes if _handle(n) not in set(exclude)]
    if not nodes:
        raise ValueError('no Ground: name the relief *_Ground or give options.ground')
    return sorted(nodes, key=_handle)


def _surface(core, grounds, mpu):
    tris = []
    for g in grounds:
        verts, faces = _mesh(g, mpu)
        tris.extend((verts[a], verts[b], verts[c]) for a, b, c in faces)
    return core.Surface(tris)


def _state(emax, nodes, extra=None):
    return {'nodes': emax.snapshot(nodes), 'extra': extra or {}}


def _ancestors(n):
    out = []
    p = n.parent
    while p is not None:
        out.append(_handle(p))
        p = p.parent
    return out


# ---- place.drop_to_ground -----------------------------------------------------------------------------
def place_drop_to_ground(ctx, mode, nodes, preview):
    """Drop the selected objects onto the Ground (*_Ground, hidden ones too) by vertical rays from their
    vertices; optional alignment to the Ground normal. One undo record; a miss is skipped, never moved."""
    tool = 'place.drop_to_ground'
    edit, emax, core = ctx.edit, ctx.emax, ctx.core
    if mode == 'preview':
        opts = core.check_options(tool, ctx.options)
        picked = _targets(nodes, 'objects to drop onto the Ground')
        units = _units(core)
        mpu = units['m_per_unit']
        grounds = _grounds(core, opts['ground'])
        gset = {_handle(g) for g in grounds}
        skipped, objects, done, moves, targets = [], [], [], [], []
        for n in picked:
            if _handle(n) in gset or core.is_ground_name(n.name):
                skipped.append(edit.skipped(str(n.name), 'a Ground object is the surface, not a target'))
            elif not _geometry(n):
                skipped.append(edit.skipped(str(n.name), 'not geometry'))
            else:
                targets.append(n)
        if not targets:
            raise ValueError('no object to drop: only Ground or non-geometry selected')
        tset = {_handle(n) for n in targets}
        surface = _surface(core, grounds, mpu)
        for n in targets:
            h, name = _handle(n), str(n.name)
            if set(_ancestors(n)) & tset:
                skipped.append(edit.skipped(name, 'its parent is selected too: it moves with the parent'))
                continue
            verts, _ = _mesh(n, mpu)
            plan = core.drop(verts, _rows(n.transform, mpu), surface, opts['offset_m'], opts['align'],
                             opts['lift_buried'])
            if plan['status'] == 'ok':
                objects.append(edit.entry(h, name))
                moves.append(dict(plan, handle=h, name=name))
                text = '{}: dz {} m, gap {} -> {} m'.format(name, core.fmt(plan['dz_m']), core.fmt(plan['gap_before_m']),
                                                            core.fmt(plan['gap_after_m']))
                if opts['align']:
                    text += ', aligned to the Ground normal (tilt {} deg)'.format(core.fmt(plan['tilt_deg'], 3))
                if plan['vertices_off_ground']:
                    text += ', {} vertices without Ground below'.format(plan['vertices_off_ground'])
                done.append(text)
            else:
                code = {'miss': 'ground_miss', 'buried': 'under_ground'}.get(plan['status'], 'empty_mesh')
                objects.append(edit.entry(h, name, [edit.finding(code, (), plan['reason'])]))
                skipped.append(edit.skipped(name, plan['reason']))
        handles = [_handle(n) for n in targets]
        state = _state(emax, targets + grounds, {'settings': opts, 'units': units})
        extra = {'options': dict(ctx.options), 'settings': opts, 'units': units, 'handles': handles,
                 'ground': [str(g.name) for g in grounds], 'ground_handles': sorted(gset), 'moves': moves}
        return edit.report(tool, 'preview', objects=objects, done=done, skipped_=skipped,
                           state_hash=edit.fingerprint(state), extra=extra)
    plan = preview['plan']
    targets = _by_handles(plan['handles'])
    grounds = _by_handles(plan['ground_handles'])
    edit.require_current(preview, _state(emax, targets + grounds, {'settings': plan['settings'],
                                                                   'units': _units(core)}))
    mpu = plan['units']['m_per_unit']
    rt = _rt()
    with emax.session(tool):
        for mv in plan['moves']:
            rt.getAnimByHandle(mv['handle']).transform = _matrix(mv['rows'], mpu)
    surface = _surface(core, grounds, mpu)
    objects, done = [], []
    offset = plan['settings']['offset_m']
    for mv in plan['moves']:
        n = rt.getAnimByHandle(mv['handle'])
        verts, _ = _mesh(n, mpu)
        gaps = core.vertical_gaps(verts, surface)
        gap = min(g for _, g in gaps) if gaps else None
        findings = []
        if gap is None or abs(gap - offset) > READBACK_TOL_M:
            findings.append(edit.finding('readback_gap', (), 'gap after the move {} m, wanted {} m'.format(
                'none' if gap is None else core.fmt(gap), core.fmt(offset))))
        objects.append(edit.entry(mv['handle'], mv['name'], findings))
        done.append('{}: gap {} m'.format(mv['name'], 'none' if gap is None else core.fmt(gap, 6)))
    return edit.report(tool, 'apply', objects=objects, done=done, skipped_=plan['skipped'],
                       ambiguous=plan['ambiguous'], extra={'moved': len(plan['moves']), 'offset_m': offset})


# ---- place.maf_checks ---------------------------------------------------------------------------------
def place_maf_checks(ctx, mode, nodes, preview):
    """Read only: flying / sunk MAF (AABB pre-filter, then vertical rays from the vertices, tolerances in metres)
    and 3D intersections between the selected MAF. Hidden / frozen objects are in the report with a flag; this
    row never selects anything."""
    tool = 'place.maf_checks'
    edit, emax, core = ctx.edit, ctx.emax, ctx.core
    opts = core.check_options(tool, ctx.options)
    picked = _targets(nodes, 'MAF to check')
    units = _units(core)
    mpu = units['m_per_unit']
    grounds = _grounds(core, opts['ground'])
    gset = {_handle(g) for g in grounds}
    skipped, data, targets = [], [], []
    for n in picked:
        if _handle(n) in gset or core.is_ground_name(n.name):
            skipped.append(edit.skipped(str(n.name), 'a Ground object is the surface, not a MAF'))
        elif not _geometry(n):
            skipped.append(edit.skipped(str(n.name), 'not geometry'))
        else:
            targets.append(n)
            verts, tris = _mesh(n, mpu)
            data.append({'handle': _handle(n), 'name': str(n.name), 'verts': verts, 'tris': tris,
                         'hidden': _hidden(n), 'frozen': bool(n.isFrozen)})
    if not targets:
        raise ValueError('no MAF to check: only Ground or non-geometry selected')
    surface = _surface(core, grounds, mpu)
    got = core.maf_checks(data, surface, opts)
    objects = [edit.entry(o['handle'], o['name'], [edit.finding(c, ids, d) for c, ids, d in got['findings'][o['handle']]])
               for o in data]
    done = ['{}: {}{}'.format(r['name'], r['verdict'], '' if r['gap_m'] is None else ', gap {} m'.format(
        core.fmt(r['gap_m']))) for r in got['rows']]
    ambiguous = ['{}: no Ground under the object, not checked'.format(name) for name in got['no_ground']]
    state = _state(emax, targets + grounds, {'settings': opts, 'units': units})
    extra = {'options': dict(ctx.options), 'settings': opts, 'units': units, 'rows': got['rows'],
             'pairs': got['pairs'], 'ground': [str(g.name) for g in grounds],
             'hidden': [o['name'] for o in data if o['hidden'] or o['frozen']], 'selects': False}
    return edit.report(tool, 'preview', objects=objects, done=done, skipped_=skipped, ambiguous=ambiguous,
                       state_hash=edit.fingerprint(state), extra=extra)


# ---- place.replace ------------------------------------------------------------------------------------
def _local_mesh_key(core, n, mpu):
    """Class + mesh in the node's object space (rounded to 0.1 mm): equal for copies of the same object."""
    rt = _rt()
    verts, tris = _mesh(n, mpu)
    local = core.to_local(verts, _rows(n.objectTransform, mpu))
    return (str(rt.classOf(n.baseObject)), len(verts), tuple(tris),
            tuple(tuple(round(c, 4) for c in p) for p in local))


def _replace_candidates(core, picked, opts, master, mpu):
    rt = _rt()
    sel = {_handle(n) for n in picked}
    pool = list(picked)
    if opts['mask']:
        pool += [o for o in rt.objects if _handle(o) not in sel and core.mask_match(str(o.name), opts['mask'])]
    master_key = None
    out = []
    for n in sorted(pool, key=_handle):
        c = {'handle': _handle(n), 'name': str(n.name), 'selected': _handle(n) in sel, 'hidden': _hidden(n),
             'frozen': bool(n.isFrozen), 'geometry': _geometry(n), 'node': n}
        if master is not None:
            c['is_master'] = _handle(n) == _handle(master)
            c['master_instance'] = not c['is_master'] and bool(rt.areNodesInstances(n, master))
            if not c['is_master'] and not c['master_instance'] and c['geometry']:
                if master_key is None:
                    master_key = _local_mesh_key(core, master, mpu)
                c['master_copy'] = _local_mesh_key(core, n, mpu) == master_key
        out.append(c)
    return out


def _keep_info(n, mpu):
    rt = _rt()
    return {'parent': None if n.parent is None else _handle(n.parent), 'layer': str(n.layer.name),
            'children': sorted(_handle(c) for c in n.children), 'props': str(rt.getUserPropBuffer(n)),
            'rows': _rows(n.transform, mpu)}


def place_replace(ctx, mode, nodes, preview):
    """Replace the selection (or the mask matches) by the master: instance or copy, world transform, layer, parent,
    children and user props of each target kept; the master, its instances and copies are never targets.
    `stub: true` replaces each target by an oriented-bbox Box (width X, length Y, pivot at the base)."""
    tool = 'place.replace'
    edit, emax, core = ctx.edit, ctx.emax, ctx.core
    rt = _rt()
    if mode == 'preview':
        opts = core.check_options(tool, ctx.options)
        units = _units(core)
        mpu = units['m_per_unit']
        if nodes is None:
            nodes = list(rt.selection)
        picked = _targets(nodes, 'targets') if (nodes or not opts['mask']) else []
        master = None if opts['stub'] else _named(opts['master'])
        cands = _replace_candidates(core, picked, opts, master, mpu)
        targets, skipped, findings, unmatched = core.replace_targets(cands, opts)
        objects, done, rows = [], [], []
        for c in targets:
            info = _keep_info(c['node'], mpu)
            row = dict(info, handle=c['handle'], name=c['name'])
            if opts['stub']:
                verts, _ = _mesh(c['node'], mpu)
                box = core.oriented_box(verts, _rows(c['node'].objectTransform, mpu))
                row['box'] = box
                done.append('{} -> Box {} x {} x {} m (oriented bbox)'.format(
                    c['name'], core.fmt(box['width']), core.fmt(box['length']), core.fmt(box['height'])))
            else:
                done.append('{} -> {} of {} (layer {}, {} children, parent {})'.format(
                    c['name'], opts['mode'], opts['master'], info['layer'], len(info['children']),
                    'kept' if info['parent'] else 'none'))
            rows.append(row)
            objects.append(edit.entry(c['handle'], c['name']))
        for c in cands:
            if c['handle'] in findings:
                objects.append(edit.entry(c['handle'], c['name'],
                                          [edit.finding(code, (), why) for code, why in findings[c['handle']]]))
        skipped = [edit.skipped(name, why) for name, why in skipped]
        tnodes = [c['node'] for c in targets]
        mnodes = [] if master is None else [master]
        state = _state(emax, tnodes + mnodes, {'keep': rows, 'settings': opts, 'units': units})
        extra = {'options': dict(ctx.options), 'settings': opts, 'units': units, 'handles': [c['handle'] for c in targets],
                 'master_handle': None if master is None else _handle(master), 'rows': rows,
                 'replaced': [c['name'] for c in targets], 'unmatched': unmatched}
        return edit.report(tool, 'preview', objects=objects, done=done, skipped_=skipped,
                           state_hash=edit.fingerprint(state), extra=extra)
    plan = preview['plan']
    opts = plan['settings']
    tnodes = _by_handles(plan['handles'])
    master = None if plan['master_handle'] is None else _by_handles([plan['master_handle']])[0]
    mpu = plan['units']['m_per_unit']
    keep = [dict(_keep_info(n, mpu), handle=_handle(n), name=str(n.name)) for n in tnodes]
    for k, row in zip(keep, plan['rows']):
        if opts['stub']:
            k['box'] = row.get('box')
    edit.require_current(preview, _state(emax, tnodes + ([] if master is None else [master]),
                                         {'keep': keep, 'settings': opts, 'units': _units(core)}))
    made = []
    with emax.session(tool):
        for row in plan['rows']:
            t = rt.getAnimByHandle(row['handle'])
            if opts['stub']:
                box = row['box']
                new = rt.Box(width=box['width'] / mpu, length=box['length'] / mpu, height=box['height'] / mpu)
                tm = _matrix(box['rows'], mpu)
            else:
                new = rt.instance(master) if opts['mode'] == 'instance' else rt.copy(master)
                tm = t.transform
            parent = t.parent
            children = list(t.children)
            layer = t.layer
            props = rt.getUserPropBuffer(t)
            name = str(t.name)
            if parent is not None:
                new.parent = parent
            new.transform = tm
            layer.addNode(new)
            rt.setUserPropBuffer(new, props)
            new.isHidden = False
            new.isFrozen = False
            for ch in children:
                ch.parent = new
            rt.delete(t)
            new.name = name
            made.append((row, new))
    objects, done, out = [], [], []
    for row, new in made:
        got = _keep_info(new, mpu)
        findings = []
        want_rows = row['box']['rows'] if opts['stub'] else row['rows']
        err = max(abs(a - b) for ra, rb in zip(got['rows'], want_rows) for a, b in zip(ra, rb))
        if err > 1e-5 * max(1.0, max(abs(v) for v in want_rows[3])):
            findings.append(edit.finding('transform_mismatch', (), 'world matrix differs by {:.3g}'.format(err)))
        for key in ('parent', 'layer', 'props'):
            if got[key] != row[key]:
                findings.append(edit.finding(key + '_lost', (), '{!r} -> {!r}'.format(row[key], got[key])))
        if len(got['children']) != len(row['children']):
            findings.append(edit.finding('children_lost', (), '{} -> {}'.format(len(row['children']),
                                                                                len(got['children']))))
        if not opts['stub'] and opts['mode'] == 'instance' and not rt.areNodesInstances(new, master):
            findings.append(edit.finding('not_instance', (), 'replacement is not an instance of the master'))
        h = _handle(new)
        objects.append(edit.entry(h, str(new.name), findings))
        done.append('{} replaced ({}), matrix error {:.3g}'.format(row['name'], 'box' if opts['stub'] else opts['mode'],
                                                                   err))
        out.append({'name': row['name'], 'handle': h, 'layer': got['layer'], 'children': len(got['children'])})
    return edit.report(tool, 'apply', objects=objects, done=done, skipped_=plan['skipped'],
                       ambiguous=plan['ambiguous'], extra={'replaced': out, 'unmatched': plan['unmatched']})


# ---- place.schedule -----------------------------------------------------------------------------------
def _schedule_rows(core, opts):
    import os
    if opts['rows'] is not None:
        return core.parse_schedule(rows=opts['rows'])
    path = opts['path']
    if not os.path.isfile(path):
        raise ValueError('schedule file not found: ' + path)
    with open(path, encoding='utf-8-sig') as f:
        text = f.read()
    return core.parse_schedule(text=text, suffix=os.path.splitext(path)[1])


def _existing_rows():
    rt = _rt()
    out = {}
    for o in rt.objects:
        rid = rt.getUserProp(o, SCHEDULE_PROP_ROW)
        model = rt.getUserProp(o, SCHEDULE_PROP_MODEL)
        if rid is not None and model is not None:
            out.setdefault((str(rid), str(model)), []).append(o)
    return out


def place_schedule(ctx, mode, nodes, preview):
    """Place MAF by a schedule (id, model, x, y, rotation_deg; metres, world): report first, then instances (or
    copies) of the reference object found by its exact name, dropped onto the Ground by the rays of
    place.drop_to_ground with the 10 cm sink. Every row gets a status: placed / no_library_model /
    outside_ground / blocked_by_obstacle (buildings *_Main or options.obstacles) / already_placed (re-run)."""
    tool = 'place.schedule'
    edit, emax, core = ctx.edit, ctx.emax, ctx.core
    rt = _rt()
    if mode == 'preview':
        opts = core.check_options(tool, ctx.options)
        rows = _schedule_rows(core, opts)
        units = _units(core)
        mpu = units['m_per_unit']
        grounds = _grounds(core, opts['ground'])
        gset = {_handle(g) for g in grounds}
        library, lib_nodes, skipped = {}, {}, []
        for model in sorted({r['model'] for r in rows}):
            found = [o for o in rt.objects if str(o.name) == model and _geometry(o)]
            if len(found) == 1:
                verts, _ = _mesh(found[0], mpu)
                library[model] = {'verts': verts, 'rows': _rows(found[0].transform, mpu)}
                lib_nodes[model] = found[0]
            elif len(found) > 1:
                skipped.append(edit.skipped(model, 'several objects with this name: the reference is ambiguous'))
        existing = _existing_rows()
        placed_before = {h for nodes_ in existing.values() for h in (_handle(o) for o in nodes_)}
        if opts['obstacles']:
            obs_nodes = [_named(n) for n in opts['obstacles']]
        else:
            lib_h = {_handle(n) for n in lib_nodes.values()}
            obs_nodes = [o for o in rt.objects if str(o.name).lower().endswith('_main') and _geometry(o)
                         and _handle(o) not in lib_h | gset | placed_before and not _hidden(o)]
        obstacles = [core.obstacle(str(o.name), _mesh(o, mpu)[0]) for o in obs_nodes]
        surface = _surface(core, grounds, mpu)
        done_ids = {rid for (rid, model) in existing if model in library or model in {r['model'] for r in rows}}
        results = core.schedule_plan(rows, library, surface, obstacles, opts['offset_m'], done_ids)
        objects, done = [], []
        per_lib = {m: [] for m in lib_nodes}
        for res in results:
            if res['status'] == 'placed':
                done.append('{}: {} at [{}, {}], rot {} deg, gap {} m'.format(
                    res['id'], res['model'], core.fmt(res['x'], 3), core.fmt(res['y'], 3),
                    core.fmt(res['rotation_deg'], 3), core.fmt(res['gap_m'])))
            elif res['status'] in ('outside_ground', 'blocked_by_obstacle'):
                if res['model'] in per_lib:
                    per_lib[res['model']].append(res)
                skipped.append(edit.skipped(res['id'], '{}: {}'.format(res['status'], res['reason'])))
            else:
                skipped.append(edit.skipped(res['id'], '{}: {}'.format(res['status'], res['reason'])))
        for model, node in sorted(lib_nodes.items(), key=lambda kv: _handle(kv[1])):
            findings = [edit.finding(r['status'], (), '{}: {}'.format(r['id'], r['reason'])) for r in per_lib[model]]
            objects.append(edit.entry(_handle(node), model, findings))
        summary = core.schedule_summary(results)
        old = [o for nodes_ in existing.values() for o in nodes_]
        state = _state(emax, list(lib_nodes.values()) + grounds + obs_nodes + old,
                       {'rows': rows, 'settings': opts, 'units': units})
        extra = {'options': dict(ctx.options), 'settings': {k: v for k, v in opts.items() if k != 'rows'},
                 'units': units, 'rows': results, 'summary': summary, 'layer': core.SCHEDULE_LAYER,
                 'library_handles': {m: _handle(n) for m, n in lib_nodes.items()},
                 'ground_handles': sorted(gset), 'obstacle_handles': sorted(_handle(o) for o in obs_nodes),
                 'existing_handles': sorted(_handle(o) for o in old), 'obstacles': [str(o.name) for o in obs_nodes]}
        return edit.report(tool, 'preview', objects=objects, done=done, skipped_=skipped,
                           state_hash=edit.fingerprint(state), extra=extra)
    plan = preview['plan']
    opts = core.check_options(tool, plan['options'])
    rows = _schedule_rows(core, opts)
    lib_nodes = {m: n for m, n in zip(plan['library_handles'], _by_handles(plan['library_handles'].values()))}
    grounds = _by_handles(plan['ground_handles'])
    obs_nodes = _by_handles(plan['obstacle_handles'])
    old = _by_handles(plan['existing_handles'])
    edit.require_current(preview, _state(emax, list(lib_nodes.values()) + grounds + obs_nodes + old,
                                         {'rows': rows, 'settings': opts, 'units': _units(core)}))
    mpu = plan['units']['m_per_unit']
    if {_handle(o) for nodes_ in _existing_rows().values() for o in nodes_} != set(plan['existing_handles']):
        raise edit.StalePreview('placed instances changed since the preview; run preview again')
    made = []
    with emax.session(tool):
        layer = emax._layer(plan['layer'])
        for res in plan['rows']:
            if res['status'] != 'placed':
                continue
            lib = lib_nodes[res['model']]
            new = rt.instance(lib) if opts['mode'] == 'instance' else rt.copy(lib)
            new.parent = None
            new.transform = _matrix(res['rows'], mpu)
            base = '{}_{}'.format(res['model'], res['id'])
            taken = any(str(o.name) == base for o in rt.objects if o != new)
            new.name = rt.uniqueName(base + '_') if taken else base
            rt.setUserProp(new, SCHEDULE_PROP_ROW, res['id'])
            rt.setUserProp(new, SCHEDULE_PROP_MODEL, res['model'])
            new.isHidden = False
            new.isFrozen = False
            layer.addNode(new)
            made.append((res, new))
    surface = _surface(core, grounds, mpu)
    offset = plan['settings']['offset_m']
    objects, done = [], []
    for res, new in made:
        verts, _ = _mesh(new, mpu)
        gaps = core.vertical_gaps(verts, surface)
        gap = min(g for _, g in gaps) if gaps else None
        pos = _rows(new.transform, mpu)[3]
        findings = []
        if gap is None or abs(gap - offset) > READBACK_TOL_M:
            findings.append(edit.finding('readback_gap', (), 'gap {} m, wanted {} m'.format(
                'none' if gap is None else core.fmt(gap), core.fmt(offset))))
        if abs(pos[0] - res['x']) > 1e-4 or abs(pos[1] - res['y']) > 1e-4:
            findings.append(edit.finding('readback_position', (), 'pivot at [{}, {}]'.format(
                core.fmt(pos[0]), core.fmt(pos[1]))))
        objects.append(edit.entry(_handle(new), str(new.name), findings))
        done.append('{} -> {}: gap {} m'.format(res['id'], str(new.name), 'none' if gap is None else core.fmt(gap, 6)))
    return edit.report(tool, 'apply', objects=objects, done=done, skipped_=plan['skipped'],
                       ambiguous=plan['ambiguous'], extra={'summary': plan['summary'], 'layer': plan['layer'],
                                                           'instance_mode': opts['mode']})


# ---- place.flora_repair -------------------------------------------------------------------------------
def _material_names(n):
    rt = _rt()
    mat = n.material
    if mat is None:
        return None, {}
    if rt.classOf(mat) == rt.MultiMaterial:
        ids = list(mat.materialIDList)
        subs = list(mat.materialList)
        return None, {int(i): (str(s.name) if s is not None else None) for i, s in zip(ids, subs)}
    return str(mat.name), {}


def triangles(n, mpu, material_of=None):
    """[{'corners': [[x, y, z, u, v] x3], 'material': name}] of the evaluated world mesh (metres)."""
    rt = _mxs()
    single, by_id = _material_names(material_of if material_of is not None else n)
    lines = str(rt.agr979_triData(n)).split('\n')
    nf, ntv = (int(x) for x in lines[0].split())
    out = []
    step = 5 if ntv else 3
    for f in range(nf):
        vals = lines[1 + f].split()
        mid = int(vals[0])
        nums = [float(x) for x in vals[1:]]
        corners = []
        for k in range(3):
            c = nums[k * step:(k + 1) * step]
            corners.append([c[0] * mpu, c[1] * mpu, c[2] * mpu] + c[3:])
        out.append({'corners': corners, 'material': by_id.get(mid) if by_id else single})
    return out


def _flora_info(n, mpu):
    rt = _mxs()
    geo = _geometry(n)
    info = {'name': str(n.name), 'geometry': geo, 'faces': 0, 'uv': False, 'degrees': [],
            'rows': _rows(n.transform, mpu)}
    if not geo:
        return info
    m = rt.snapshotAsMesh(n)
    info['faces'] = int(m.numfaces)
    info['uv'] = int(rt.getNumTVerts(m)) > 0
    rt.delete(m)
    if str(rt.classOf(n.baseObject)) == 'Editable_Poly' and not len(n.modifiers):
        info['degrees'] = [int(d) for d in rt.agr979_faceDeg(n)]
    return info


def _bbox_probe(n, mpu):
    """max |snapshot bbox - nodeGetBoundingBox(identity)| in metres (pilot max_flora_verify invariant)."""
    rt = _rt()
    verts, _ = _mesh(n, mpu)
    lo = [min(v[i] for v in verts) for i in range(3)]
    hi = [max(v[i] for v in verts) for i in range(3)]
    bb = rt.nodeGetBoundingBox(n, rt.Matrix3(1))
    nlo = [float(bb[0].x) * mpu, float(bb[0].y) * mpu, float(bb[0].z) * mpu]
    nhi = [float(bb[1].x) * mpu, float(bb[1].y) * mpu, float(bb[1].z) * mpu]
    return max(max(abs(a - b) for a, b in zip(lo, nlo)), max(abs(a - b) for a, b in zip(hi, nhi)))


def place_flora_repair(ctx, mode, nodes, preview):
    """Flora repair on COPIES (layer AGR_flora_repair): a sheared card becomes a world-baked mesh with an identity
    transform (transform repair basis), every other card a triangulated snapshot (tri repair basis). Each copy is
    compared with its source (0.05 mm, UV 2e-5, winding, material); originals are never changed or deleted."""
    tool = 'place.flora_repair'
    edit, emax, core = ctx.edit, ctx.emax, ctx.core
    rt = _rt()
    if mode == 'preview':
        core.check_options(tool, ctx.options)
        picked = _targets(nodes, 'Flora objects')
        units = _units(core)
        mpu = units['m_per_unit']
        objects, done, skipped, plans = [], [], [], []
        for n in picked:
            info = _flora_info(n, mpu)
            p = core.flora_plan(info)
            h, name = _handle(n), str(n.name)
            if p['action'] == 'skip':
                objects.append(edit.entry(h, name, [edit.finding(p['code'], (), p['reason'])]))
                skipped.append(edit.skipped(name, p['reason']))
                continue
            findings = [edit.finding(c, (), {'negative_scale': 'negative scale (det < 0)',
                                             'shear': 'shear: the source FBX would not match; world-baked copy',
                                             'rotated': 'rotated transform'}[c]) for c in p['codes']]
            if p['ngons']:
                findings.append(edit.finding('ngon', p['ngons'][:1000], '{} faces with more than 3 corners'.format(
                    len(p['ngons']))))
            objects.append(edit.entry(h, name, findings))
            plans.append({'handle': h, 'name': name, 'action': p['action'], 'codes': p['codes'],
                          'ngons': len(p['ngons'])})
            done.append('{} -> {} copy{}'.format(name, 'world-baked' if p['action'] == 'bake' else 'triangulated',
                                                 ' ({})'.format(', '.join(p['codes'])) if p['codes'] else ''))
        state = _state(emax, picked, {'units': units})
        extra = {'options': dict(ctx.options), 'units': units, 'handles': [_handle(n) for n in picked],
                 'copies': plans, 'layer': core.FLORA_LAYER,
                 'fbx_would_differ': [p['name'] for p in plans if 'shear' in p['codes']]}
        return edit.report(tool, 'preview', objects=objects, done=done, skipped_=skipped,
                           state_hash=edit.fingerprint(state), extra=extra)
    plan = preview['plan']
    picked = _by_handles(plan['handles'])
    edit.require_current(preview, _state(emax, picked, {'units': _units(core)}))
    mpu = plan['units']['m_per_unit']
    before = emax.snapshot(picked)
    made = []
    with emax.session(tool):
        layer = emax._layer(plan['layer'])
        for p in plan['copies']:
            n = rt.getAnimByHandle(p['handle'])
            if p['action'] == 'bake':
                m = rt.snapshotAsMesh(n)
                c = rt.mesh(mesh=m)
                c.transform = rt.Matrix3(1)
            else:
                c = rt.snapshot(n)
            c.material = n.material
            c.name = rt.uniqueName(p['name'] + FLORA_SUFFIX)
            layer.addNode(c)
            made.append((p, n, c))
    objects, done, copies = [], [], []
    for p, n, c in made:
        cmp = core.compare_meshes(triangles(n, mpu), triangles(c, mpu, material_of=n))
        probe = _bbox_probe(c, mpu)
        findings = []
        if not cmp['equal']:
            findings.append(edit.finding('copy_mismatch', (), str(cmp.get('reason', 'not equal'))))
        if probe > 0.00005:
            findings.append(edit.finding('bbox_probe', (), '{:.3g} m'.format(probe)))
        objects.append(edit.entry(_handle(c), str(c.name), findings))
        done.append('{} -> {}: {} copy, equal {}, max {:.4f} mm'.format(
            p['name'], str(c.name), p['action'], cmp['equal'], cmp.get('max_deviation_mm') or 0.0))
        copies.append({'source': p['name'], 'copy': str(c.name), 'handle': _handle(c), 'action': p['action'],
                       'codes': p['codes'], 'equal': cmp['equal'], 'bbox_probe_m': probe})
    unchanged = emax.snapshot(picked) == before
    if not unchanged:
        raise RuntimeError('flora_repair changed an original: report this as a bug')
    return edit.report(tool, 'apply', objects=objects, done=done, skipped_=plan['skipped'],
                       ambiguous=plan['ambiguous'], extra={'copies': copies, 'layer': plan['layer'],
                                                           'originals_unchanged': unchanged,
                                                           'fbx_would_differ': plan['fbx_would_differ']})
