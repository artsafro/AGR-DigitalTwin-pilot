"""new-case: AGR Tools 1.0 (#1024) UCX gap (`ucx.gap`, station 1.0.27), 3ds Max side. owned by branch S
(improve/issue-1024-deliver).

runtime.edits_100 calls `ucx_gap(ctx, mode, nodes, preview)`.
ctx: agr (runtime globals), core (ucx10_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost: ObjRef, world meshes in metres, one undo record).
Import pymxs inside functions so this file loads under plain pytest.

Scope: the UCX families (`UCX_<mesh>_NN`) of the given nodes - every piece of each family, also the unselected
neighbours - else every `UCX_*` of the scene. Meshes come in METRES from host.mesh (units.SystemScale); the copy
geometry goes back through 1 / metres-per-unit and the inverse object transform. Plan mode `copy`: one undo
record, selection restored, the pieces of every family with a change are copied to layer AGR_export
(edit_max.export_copies) and only the copies are rewritten; the originals are checked byte-equal afterwards.
"""
SUFFIX = '_AGR_gap_'
EXPORT_LAYER = 'AGR_export'


def _rt():
    from pymxs import runtime
    return runtime


def _handle(n):
    return int(_rt().getHandleByAnim(n))


def _scope(core, nodes):
    rt = _rt()
    every = [n for n in rt.objects if rt.isValidNode(n) and str(n.name).upper().startswith('UCX_')
             and bool(rt.canConvertTo(n, rt.TriMeshGeometry))]
    if nodes is None:
        return sorted(every, key=_handle)
    fams = {core.family(str(n.name)) for n in nodes if rt.isValidNode(n)}
    fams.discard(None)
    if not fams:
        raise ValueError('ucx.gap: no UCX_<mesh>_NN piece in the selection')
    return sorted([n for n in every if core.family(str(n.name)) in fams], key=_handle)


def _rows(ctx, nodes):
    rows = []
    for n, ref in zip(nodes, ctx.host.refs(nodes)):
        m = ctx.host.mesh(ref)
        rows.append({'handle': _handle(n), 'name': str(n.name), 'verts': m['verts'], 'tris': m['faces']})
    return rows


def _state(ctx, nodes, unit_m, opts):
    return {'tool': ctx.core.TOOL, 'nodes': ctx.emax.snapshot(nodes), 'unit_m': unit_m, 'options': opts}


def _write_piece(c, verts_m, tris, unit_m):
    """Rewrite the copy's mesh: world metres -> system units -> object space of the copy."""
    rt = _rt()
    inv = rt.inverse(c.objectTransform)
    k = 1.0 / unit_m
    pts = [rt.Point3(v[0] * k, v[1] * k, v[2] * k) * inv for v in verts_m]
    faces = [rt.Point3(a + 1, b + 1, cc + 1) for a, b, cc in tris]
    rt.convertToMesh(c)
    rt.setMesh(c, vertices=pts, faces=faces)
    for i in range(1, len(faces) + 1):
        rt.setEdgeVis(c, i, 1, True)
        rt.setEdgeVis(c, i, 2, True)
        rt.setEdgeVis(c, i, 3, True)
    rt.update(c)
    rt.convertToPoly(c)


def ucx_gap(ctx, mode, nodes, preview):
    core, edit, emax = ctx.core, ctx.edit, ctx.emax
    rt = _rt()
    unit_m = ctx.host.m_per_unit()
    if mode == 'preview':
        opts = core.gap_options(ctx.options)
        scope = _scope(core, nodes)
        rows = _rows(ctx, scope)
        result = core.plan(rows, opts)
        notes = ['units: {} x {} -> {} m per unit'.format(rt.units.SystemType, rt.units.SystemScale, unit_m)]
        return core.gap_report(edit, 'preview', rows, result, opts, edit.fingerprint(_state(ctx, scope, unit_m, opts)),
                               notes=notes, extra={'handles': [r['handle'] for r in rows], 'unit_m': unit_m})
    opts = core.gap_options(preview['plan']['options'])
    scope = []
    for h in preview['plan']['handles']:
        n = rt.maxOps.getNodeByHandle(h)
        if n is None or not rt.isValidNode(n):
            raise edit.StalePreview('scene changed since the preview: node {} is gone'.format(h))
        scope.append(n)
    edit.require_current(preview, _state(ctx, scope, unit_m, opts))
    rows = _rows(ctx, scope)
    result = core.plan(rows, opts)
    before = emax.snapshot(scope)
    fams = sorted({p['family'] for p in result['pieces'].values() if p['changed']})
    copy_nodes = [n for n in scope if core.family(str(n.name)) in fams]
    objects, done, copies = [], [], []
    with emax.session(core.TOOL):
        pairs = emax.export_copies(copy_nodes, suffix=SUFFIX, layer=EXPORT_LAYER)
        for n, c in pairs:
            p = result['pieces'][_handle(n)]
            if p['changed']:
                _write_piece(c, p['verts'], p['tris'], unit_m)
            copies.append((n, c, p))
    if emax.snapshot(scope) != before:
        raise RuntimeError('ucx.gap: an original UCX piece changed during apply')
    # readback: the copies as Max has them, SAT between every pair of each copied family
    back = _rows(ctx, [c for _, c, _ in copies])
    pieces = {r['handle']: core.piece(r['verts'], r['tris']) for r in back}
    fam_of = {_handle(c): p['family'] for _, c, p in copies}
    bad = {}
    hs = sorted(pieces)
    for i in range(len(hs)):
        for j in range(i + 1, len(hs)):
            if fam_of[hs[i]] != fam_of[hs[j]]:
                continue
            g, _ = core.separation(pieces[hs[i]], pieces[hs[j]])
            if g < opts['gap_m'] - core.TOL_M:
                for h in (hs[i], hs[j]):
                    bad.setdefault(h, []).append(('ucx_gap_left', 'SAT {:.3f} мм < {:.3f} мм после записи'.format(
                        g * 1000, opts['gap_m'] * 1000)))
    for n, c, p in copies:
        h = _handle(c)
        objects.append(edit.entry(h, str(c.name), [edit.finding(code, (), d) for code, d in bad.get(h, [])]))
        done.append('{} -> {}{}'.format(p['name'], str(c.name), ': плоскости сдвинуты' if p['changed'] else
                                        ': копия без изменений'))
    return core.gap_report(edit, 'apply', rows, result, opts, done=done,
                           extra={'objects': objects, 'copies': [{'source': p['name'], 'copy': str(c.name),
                                                                   'handle': _handle(c), 'changed': p['changed']}
                                                                  for _, c, p in copies], 'unit_m': unit_m})
