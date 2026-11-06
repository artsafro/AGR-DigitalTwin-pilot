"""AGR Tools 1.0 (#1024), owned by branch N (improve/issue-1024-vpm-maps): plug islands in UDIM, 3ds Max side (udim.plugs, mode `copy`).

runtime.edits_100 calls `udim_plugs(ctx, mode, nodes, preview)`.
ctx: agr (runtime globals), core (udimplug_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost: ObjRef, user props, one undo record).
The plug UV go into map channel 1 of an export COPY through polyop.setMapVert (no Unwrap_UVW, no Modify panel, no
`classOf` check: the GridUVLayout22 `runPlugs` refused its own second run). The sources are not touched.
Import pymxs inside functions so this file loads under plain pytest.
"""
TOOL = 'udim.plugs'
LAYER = 'AGR_export'


def _rt():
    from pymxs import runtime
    return runtime


def _faces(ctx, node):
    """[{face, matid, verts}] of the selected faces (all faces when none are selected) in metres (units.SystemScale)."""
    rt = _rt()
    k = ctx.host.m_per_unit()
    sel = set(int(i) for i in rt.polyop.getFaceSelection(node))
    out = []
    for f in range(1, int(rt.polyop.getNumFaces(node)) + 1):
        if sel and f not in sel:
            continue
        pts = [rt.polyop.getVert(node, int(v)) for v in rt.polyop.getFaceVerts(node, f)]
        out.append({'face': f, 'matid': int(rt.polyop.getFaceMatID(node, f)),
                    'verts': [(float(p.x) * k, float(p.y) * k, float(p.z) * k) for p in pts]})
    return out


def _write_plugs(node, planned):
    """Plug islands into map channel 1 of the COPY (setMapVert); UV of the other faces stay. Returns the UV read back
    per planned face."""
    rt = _rt()
    po = rt.polyop
    if not po.getMapSupport(node, 1):
        po.setMapSupport(node, 1, True)
    base = int(po.getNumMapVerts(node, 1))
    po.setNumMapVerts(node, 1, base + sum(len(p['uv']) for p in planned), True)
    nxt = base + 1
    for p in planned:
        idx = []
        for (u, v) in p['uv']:
            po.setMapVert(node, 1, nxt, rt.Point3(u, v, 0))
            idx.append(nxt)
            nxt += 1
        po.setMapFace(node, 1, p['face'], idx)
    back = []
    for p in planned:
        pts = [po.getMapVert(node, 1, int(i)) for i in po.getMapFace(node, 1, p['face'])]
        back.append([(float(q.x), float(q.y)) for q in pts])
    return back


def udim_plugs(ctx, mode, nodes, preview):
    core, edit, emax = ctx.core, ctx.edit, ctx.emax
    rt = _rt()
    src = list(nodes) if nodes is not None else list(rt.selection)
    if not src:
        raise ValueError('nothing selected: select the placeholder-material objects (empty input is an error)')
    opts = core.plug_options(ctx.options)
    plans, skipped, objects = [], [], []
    for n in src:
        if not rt.isKindOf(n, rt.Editable_Poly):
            skipped.append(edit.skipped(str(n.name), 'not an Editable_Poly: the plug is written on a copy of a poly '
                                                      'object (the source stays as it is)'))
            continue
        plan = core.plug_plan(_faces(ctx, n), opts)
        plans.append((n, plan))
        findings = [edit.finding(s['code'], [s['face']], s['reason']) for s in plan['skipped']]
        objects.append(edit.entry(rt.getHandleByAnim(n), str(n.name), findings))
    if not plans:
        raise ValueError('no object can get plugs: ' + '; '.join(s['item'] + ': ' + s['reason'] for s in skipped))
    done = [{'object': str(n.name), 'faces': len(p['faces']),
             'tiles': {str(k): v for k, v in sorted(p['tiles'].items())}} for n, p in plans]
    ambiguous = [dict(a, item='{}: {}'.format(n.name, a['item'])) for n, p in plans for a in p['ambiguous']]
    state = emax.snapshot([n for n, _ in plans])
    extra = {'options': opts, 'issue': '#1024'}
    if mode == 'preview':
        return edit.report(TOOL, 'preview', objects, done, skipped, ambiguous, state_hash=edit.fingerprint(state),
                           extra=extra)
    edit.require_current(preview, state)
    copies, out = [], []
    try:
        with emax.session(TOOL):
            pairs = emax.export_copies([n for n, _ in plans], layer=LAYER)
            copies.extend(c for _, c in pairs)
            for (n, plan), (_, c) in zip(plans, pairs):
                back = _write_plugs(c, plan['faces'])
                for tile in plan['tiles']:
                    grp = [b for b, p in zip(back, plan['faces']) if p['udim'] == tile]
                    if not core.plug_check(grp, tile, opts['size'], tuple(opts['centre'])):
                        raise RuntimeError('readback of the plug islands differs on {} tile {}'.format(c.name, tile))
                out.append(edit.entry(rt.getHandleByAnim(c), str(c.name), []))
            if edit.fingerprint(emax.snapshot([n for n, _ in plans])) != edit.fingerprint(state):
                raise RuntimeError('working objects changed during apply')
    except Exception:
        alive = [c for c in copies if rt.isValidNode(c)]
        if alive:
            rt.delete(alive)
        raise
    return edit.report(TOOL, 'apply', out, done, skipped, ambiguous,
                       extra=dict(extra, copies=[str(c.name) for c in copies]))
