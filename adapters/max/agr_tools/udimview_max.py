"""new-case: AGR Tools 1.0 (#1024) UDIM -> ID view, 3ds Max side; owned by branch Q (improve/issue-1024-npm-to-vpm).

runtime.edits_100 calls `udim_udims_to_ids(ctx, mode, nodes, preview)` for udim.udims_to_ids (plan mode `read`:
preview only). ctx: agr (runtime globals), core (udimview_core), edit (edit_core), emax (edit_max), options (dict of
the preview), host (host_max.MaxHost). Import pymxs inside functions so this file loads under plain pytest.

Reads the evaluated mesh (udim10_max.read_tri of branch M: `<node>.mesh`, any stack, nothing collapsed) and reports
UDIM -> ID per object. Nothing changes: no material ID, no modifier, no Modify panel switch, no selection change
(GeoAGR `btn_ids_as_udims` wrote the IDs and added Unwrap_UVW, GeoAGR.ms:41355-41500).
"""
TOOL = 'udim.udims_to_ids'
ISSUE = '#1024'


def _reader(ctx):
    return ctx.agr._load_core('udim10_max.py', 'agr_tools_udim10_max')


def udim_udims_to_ids(ctx, mode, nodes, preview):
    if mode != 'preview':
        raise ValueError(TOOL + ' is read-only (Q08): there is no apply')
    edit, core = ctx.edit, ctx.core
    opts = core.options(ctx.options)
    rd = _reader(ctx)
    k = ctx.host.m_per_unit()
    nodes = rd.target_nodes(nodes)
    entries, done, skipped, state = [], [], [], []
    for n in nodes:
        if not rd.is_geometry(n):
            skipped.append(edit.skipped(str(n.name), 'not geometry'))
            continue
        mesh = rd.read_tri(n, k)
        state.append(rd._state(ctx, n, mesh))
        if mesh['uvs'] is None:
            entries.append(edit.entry(rd.handle(n), str(n.name), [edit.finding('no_uv', [], 'no UV channel 1')]))
            continue
        v = core.view(mesh, opts['faces'])
        entries.append(edit.entry(rd.handle(n), str(n.name), [edit.finding(*f) for f in core.findings_of(v)]))
        done.append({'object': str(n.name), 'faces': v['faces'], 'rows': core.rows_of(v),
                     'ambiguous': len(v['ambiguous']), 'id_differs': len(v['mismatch']),
                     'rule': 'centroid tile (V1.2), ID = UDIM - 1000; read only'})
    if not entries:
        raise ValueError('nothing to show: ' + ('; '.join(s['item'] + ': ' + s['reason'] for s in skipped)
                                                or 'select the objects'))
    return edit.report(TOOL, 'preview', entries, done, skipped, (), state_hash=edit.fingerprint(state),
                       extra={'options': opts, 'issue': ISSUE})
