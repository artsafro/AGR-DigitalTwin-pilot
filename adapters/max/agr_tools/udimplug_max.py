"""AGR Tools 1.0 (#1024), owned by branch N (improve/issue-1024-vpm-maps): plug islands in UDIM, 3ds Max side (udim.plugs, mode `copy`).

runtime.edits_100 calls `udim_plugs(ctx, mode, nodes, preview)`.
ctx: agr (runtime globals), core (udimplug_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost: ObjRef, user props, one undo record).
The plug UV go into map channel 1 of an export COPY through polyop/meshop.setMapVert (no Unwrap_UVW, no Modify panel,
no `classOf` gate: the GridUVLayout22 `runPlugs` refused its own second run). The sources are not touched.
1.0.1 (KPP1 e2e 20261106-075555-c179f5f0): an Editable_Mesh is read and written as well - the copies of vpm.build are
Editable_Mesh and were refused («not an Editable_Poly»); the tile of a face comes from the mesh UDIM table
(options.udim_table, else the `agr_udim_table` user prop of the node, written by vpm.build on its copy), so a library
id goes to its dense tile (12 -> 1004 on KPP1) and not to 1000 + id.
Import pymxs inside functions so this file loads under plain pytest.
"""
import json

TOOL = 'udim.plugs'
LAYER = 'AGR_export'
UDIM_PROP = 'agr_udim_table'


def _rt():
    from pymxs import runtime
    return runtime


def _selected(vals, count):
    """Selected face numbers (1-based) from the items of a pymxs BitArray: native job 20261106-043605 showed that
    iterating it yields one 0/1 value per element (an empty selection must stay empty), older builds yield the
    1-based indices of the set bits; both shapes are read."""
    if len(vals) == count and all(v in (0, 1, True, False) for v in vals):
        return {i + 1 for i, v in enumerate(vals) if v}
    return {int(v) for v in vals}


def _kind(node):
    """'poly' | 'mesh' | None: the classes whose faces and channel 1 are read and written here."""
    rt = _rt()
    if rt.isKindOf(node, rt.Editable_Poly):
        return 'poly'
    if rt.isKindOf(node, rt.Editable_Mesh):
        return 'mesh'
    return None


def _node_table(node):
    """UDIM table {library id: UDIM} of the `agr_udim_table` user prop (vpm.build copy), or None."""
    rt = _rt()
    raw = rt.getUserProp(node, UDIM_PROP)
    if raw is None or str(raw) in ('', 'undefined'):
        return None
    try:
        return json.loads(str(raw))
    except ValueError:
        raise ValueError('{}: user prop {} is not JSON: {!r}'.format(node.name, UDIM_PROP, str(raw)[:80]))


def _faces(ctx, node):
    """[{face, matid, verts}] of the selected faces (all faces when none are selected) in metres (units.SystemScale)."""
    rt = _rt()
    k = ctx.host.m_per_unit()
    out = []
    if _kind(node) == 'mesh':
        count = int(rt.getNumFaces(node))
        sel = _selected(list(rt.getFaceSelection(node)), count)
        for f in range(1, count + 1):
            if sel and f not in sel:
                continue
            idx = rt.getFace(node, f)
            pts = [rt.getVert(node, int(i)) for i in (idx.x, idx.y, idx.z)]
            out.append({'face': f, 'matid': int(rt.getFaceMatID(node, f)),
                        'verts': [(float(p.x) * k, float(p.y) * k, float(p.z) * k) for p in pts]})
        return out
    count = int(rt.polyop.getNumFaces(node))
    sel = _selected(list(rt.polyop.getFaceSelection(node)), count)
    for f in range(1, count + 1):
        if sel and f not in sel:
            continue
        pts = [rt.polyop.getVert(node, int(v)) for v in rt.polyop.getFaceVerts(node, f)]
        out.append({'face': f, 'matid': int(rt.polyop.getFaceMatID(node, f)),
                    'verts': [(float(p.x) * k, float(p.y) * k, float(p.z) * k) for p in pts]})
    return out


def _write_plugs_mesh(node, planned):
    """Editable_Mesh: plug islands into map channel 1 of the COPY (meshop.setMapVert / setMapFace, triangles)."""
    rt = _rt()
    mo = rt.meshop
    if not mo.getMapSupport(node, 1):
        mo.setMapSupport(node, 1, True)
    base = int(mo.getNumMapVerts(node, 1))
    mo.setNumMapVerts(node, 1, base + sum(len(p['uv']) for p in planned), keep=True)
    nxt = base + 1
    for p in planned:
        idx = []
        for (u, v) in p['uv']:
            mo.setMapVert(node, 1, nxt, rt.Point3(u, v, 0))
            idx.append(nxt)
            nxt += 1
        mo.setMapFace(node, 1, p['face'], rt.Point3(idx[0], idx[1], idx[2]))
    rt.update(node)
    back = []
    for p in planned:
        t = mo.getMapFace(node, 1, p['face'])
        pts = [mo.getMapVert(node, 1, int(i)) for i in (t.x, t.y, t.z)]
        back.append([(float(q.x), float(q.y)) for q in pts])
    return back


def _write_plugs(node, planned):
    """Plug islands into map channel 1 of the COPY (setMapVert); UV of the other faces stay. Returns the UV read back
    per planned face."""
    rt = _rt()
    po = rt.polyop
    if not po.getMapSupport(node, 1):
        po.setMapSupport(node, 1, True)
    base = int(po.getNumMapVerts(node, 1))
    po.setNumMapVerts(node, 1, base + sum(len(p["uv"]) for p in planned), keep=True)
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
        if _kind(n) is None:
            skipped.append(edit.skipped(str(n.name), 'not an Editable_Poly / Editable_Mesh: the plug is written on a '
                                                      'copy of a poly or mesh object (the source stays as it is)'))
            continue
        nopts = opts
        if opts.get('udim_table') is None and opts.get('fixed_udim') is None:
            table = core.udim_table(_node_table(n))
            if table is not None:
                nopts = dict(opts, udim_table=table)
        plan = core.plug_plan(_faces(ctx, n), nopts)
        plan['udim_source'] = ('fixed_udim' if opts.get('fixed_udim') is not None else 'options.udim_table'
                               if opts.get('udim_table') is not None else UDIM_PROP if nopts is not opts
                               else '1000 + id')
        plans.append((n, plan))
        findings = [edit.finding(s['code'], [s['face']], s['reason']) for s in plan['skipped']]
        objects.append(edit.entry(rt.getHandleByAnim(n), str(n.name), findings))
    if not plans:
        raise ValueError('no object can get plugs: ' + '; '.join(s['item'] + ': ' + s['reason'] for s in skipped))
    done = [{'object': str(n.name), 'faces': len(p['faces']), 'udim_source': p['udim_source'],
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
                back = (_write_plugs_mesh if _kind(c) == 'mesh' else _write_plugs)(c, plan['faces'])
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
