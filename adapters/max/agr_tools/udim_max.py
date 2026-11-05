"""new-case: AGR Tools 0.8 (#908) udim, 3ds Max side (branch C, improve/issue-908-names).

runtime.edits_080 calls `udim_ids_to_udims(ctx, mode, nodes, preview)`; ctx: agr (runtime globals), core
(udim_core), edit (edit_core), emax (edit_max), options (dict of the preview). pymxs is imported inside functions.

preview reads channel 1 of every selected object (runtime._read_channel, unchanged) and plans the layout; nothing
in the scene changes. apply re-reads the scene (edit_core.require_current), makes export copies on layer
`AGR_export_udim` in ONE undo record (edit_max.session), writes the new channel 1 on the copies only
(runtime._write_channel), reads it back and checks every face of a placed ID is inside tile 1000+ID. The working
objects are compared before/after: UVs, IDs and vertices must be identical.
Options: mode 'fit' (default, each ID fitted to `scale`), 'texel' (one UV/3D ratio for all IDs) or 'keep'
(#979: the layout is kept, every face moves by whole tiles into 1000+ID, seams cut); scale 0.95.
#979: objects with a modifier stack are read from the evaluated stack; only the copy is collapsed.
"""
TOOL = 'udim.ids_to_udims'
LAYER = 'AGR_export_udim'
OPTION_KEYS = {'mode', 'scale'}


def _rt():
    from pymxs import runtime
    return runtime


def _options(ctx, mode, preview):
    if mode == 'apply':
        return dict(preview['plan']['options'])
    opts = dict(ctx.options or {})
    unknown = set(opts) - OPTION_KEYS
    if unknown:
        raise ValueError('unknown udim.ids_to_udims options: ' + ', '.join(sorted(unknown)))
    out = {'mode': opts.get('mode', 'fit'), 'scale': opts.get('scale', ctx.core.DEFAULT_SCALE)}
    if out['mode'] not in ctx.core.MODES:
        raise ValueError('options.mode must be fit or texel: ' + repr(out['mode']))
    if isinstance(out['scale'], bool) or not isinstance(out['scale'], (int, float)) or not 0 < out['scale'] <= 1:
        raise ValueError('options.scale must be in (0, 1]: ' + repr(out['scale']))
    out['scale'] = float(out['scale'])
    return out


def _session_core():
    """Shared helpers (session_core.py next to this file), loaded by path like the other sibling cores."""
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('agr_tools_session_core', Path(__file__).with_name('session_core.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_in_session = _session_core().in_session


def _nodes(nodes):
    rt = _rt()
    if nodes is None:
        nodes = list(rt.selection)
    nodes = [n for n in nodes]
    if not nodes:
        raise ValueError('nothing selected: select the objects to lay out')
    handles = [int(rt.getHandleByAnim(n)) for n in nodes]
    if len(set(handles)) != len(handles):
        raise ValueError('duplicate node in the target set')
    return sorted(nodes, key=lambda n: int(rt.getHandleByAnim(n)))  # D1: every object, stable order


def _plain(n):
    """Editable Poly/Mesh without modifiers: channel 1 of the base object is what the scene shows."""
    rt = _rt()
    return not int(n.modifiers.count) and rt.classOf(n.baseObject) in (rt.Editable_Poly, rt.Editable_Mesh)


def _usable(n):
    """None when channel 1 can be laid out on a copy, else the reason it is skipped.

    #979 (T02/udim_tool_v92 V4): a modifier stack (Unwrap_UVW, UVW_Xform, ...) is no longer a refusal and is
    never edited under: the layout is read from the evaluated stack and the COPY is collapsed before writing."""
    rt = _rt()
    if not rt.isValidNode(n):
        return 'deleted node'
    if rt.superClassOf(n) != rt.GeometryClass:
        return 'not geometry'
    if not _plain(n) and not rt.canConvertTo(n, rt.Editable_Poly):
        return 'base object is {}, cannot become Editable Poly'.format(rt.classOf(n.baseObject))
    return None


def _collapse(c):
    """The copy's evaluated stack as its base object (Editable Poly), so channel 1 is the visible one."""
    rt = _rt()
    if not _plain(c):
        rt.convertTo(c, rt.Editable_Poly)


def _read_eval(ctx, n):
    """Channel 1 as the scene shows it: base object of a plain node, else a throwaway collapsed copy (no undo)."""
    import pymxs
    rt = _rt()
    if _plain(n):
        return ctx.agr._read_channel(n)
    with pymxs.undo(False):
        tmp = rt.copy(n)
        try:
            _collapse(tmp)
            mesh = ctx.agr._read_channel(tmp)
        finally:
            rt.delete(tmp)
    # the throwaway copy has the same transform: world vertices are the scene's
    return mesh


def _read(ctx, nodes):
    """(state, targets, meshes, skipped): state is the JSON fingerprint source of every target node."""
    rt = _rt()
    targets, meshes, skipped, state = [], [], [], []
    for n in nodes:
        reason = _usable(n)
        if reason is None:
            try:
                mesh = _read_eval(ctx, n)
            except ValueError as exc:
                reason = str(exc)
        if reason is not None:
            skipped.append(ctx.edit.skipped(str(n.name), reason))
            continue
        targets.append(n)
        meshes.append(mesh)
        state.append({'handle': int(rt.getHandleByAnim(n)), 'name': str(n.name), 'mesh': mesh})
    return state, targets, meshes, skipped


def _plan(ctx, targets, meshes, options):
    core, edit = ctx.core, ctx.edit
    scales = core.plan_scales(meshes, options['mode'], options['scale'])
    entries, done, per_object, layouts = [], [], [], []
    for mi, (n, mesh) in enumerate(zip(targets, meshes)):
        rows = core.id_rows(mesh, scales, mi)
        uvs, fuv = core.layout(mesh, scales, mi)
        layouts.append((uvs, fuv))
        findings = []
        groups = core.measure(mesh)
        for r in rows:
            faces = [f + 1 for f in groups[r['id']]['faces']]
            if r['status'] == 'rejected':
                findings.append(edit.finding('udim_id_out_of_range', faces, r['reason']))
            elif r['status'] == 'zero_extent':
                findings.append(edit.finding('udim_zero_extent', faces, r['reason']))
            elif r['status'] == 'straddles':
                findings.append(edit.finding('udim_straddles', scales[(mi, r['id'])]['faces'], r['reason']))
            else:
                done.append({'object': str(n.name), 'id': r['id'], 'tile': r['tile'], 'faces': r['faces'],
                             'scale': r['scale']})
        entries.append((n, findings))
        per_object.append({'object': str(n.name), 'ids': rows})
    return entries, done, per_object, layouts, scales


def udim_ids_to_udims(ctx, mode, nodes, preview):
    rt = _rt()
    edit, core, emax = ctx.edit, ctx.core, ctx.emax
    options = _options(ctx, mode, preview)
    nodes = _nodes(nodes)
    state, targets, meshes, skipped = _read(ctx, nodes)
    entries, done, per_object, layouts, scales = _plan(ctx, targets, meshes, options)
    extra = {'options': options, 'layer': LAYER, 'per_object': per_object, 'issue': '#908'}
    if mode == 'preview':
        objects = [edit.entry(rt.getHandleByAnim(n), str(n.name), f) for n, f in entries]
        return edit.report(TOOL, 'preview', objects, done, skipped, (), state_hash=edit.fingerprint(state), extra=extra)
    edit.require_current(preview, state)
    plan = preview['plan']
    if edit.fingerprint([plan['done'], plan['per_object'], plan['skipped']]) != edit.fingerprint([done, per_object, skipped]):
        raise edit.StalePreview('the layout differs from the preview; run preview again')
    if not targets:
        raise ValueError('no object can be laid out: ' + '; '.join(s['item'] + ': ' + s['reason'] for s in skipped))
    copies, objects, applied = [], [], []

    def body():
        try:
            pairs = emax.export_copies(targets, layer=LAYER)
            copies.extend(c for _, c in pairs)
            for mi, ((n, c), (uvs, fuv), (_, findings)) in enumerate(zip(pairs, layouts, entries)):
                _collapse(c)  # the copy only: the working object keeps its stack (D12)
                ctx.agr._write_channel(c, uvs, fuv)
                back = ctx.agr._read_channel(c)
                ctx.agr.assert_uv_close(back['uvs'], uvs)
                if back['face_uvs'] != fuv or back['ids'] != meshes[mi]['ids']:
                    raise RuntimeError('copy readback differs from the written layout: ' + str(c.name))
                rows = core.id_rows(meshes[mi], scales, mi, after=(back['uvs'], back['face_uvs']))
                findings = list(findings)
                for r in rows:
                    if r.get('outside_tile'):
                        findings.append(edit.finding('udim_outside_tile', r['outside_tile'],
                                                     'ID {}: faces not inside tile {} after readback'.format(r['id'], r['tile'])))
                    if r['status'] == 'placed':
                        applied.append({'object': str(c.name), 'source': str(n.name), 'id': r['id'], 'tile': r['tile'],
                                        'faces': r['faces'], 'scale': r['scale'], 'outside_tile': r['outside_tile']})
                objects.append(edit.entry(rt.getHandleByAnim(c), str(c.name), findings))
                per_object[mi] = {'object': str(c.name), 'source': str(n.name), 'ids': rows}
            after = [{'handle': int(rt.getHandleByAnim(n)), 'name': str(n.name), 'mesh': _read_eval(ctx, n)}
                     for n in targets]
            if edit.fingerprint(after) != edit.fingerprint(state):
                raise RuntimeError('working objects changed during apply')
        except Exception:
            alive = [c for c in copies if rt.isValidNode(c)]
            if alive:
                rt.delete(alive)
            raise
    _in_session(emax, TOOL, body)
    extra = dict(extra, per_object=per_object, copies=[str(c.name) for c in copies],
                 texel_spread=round(core.texel_spread([r for p in per_object for r in p['ids']]), 9))
    return edit.report(TOOL, 'apply', objects, applied, skipped, (), extra=extra)
