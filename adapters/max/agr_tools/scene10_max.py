"""new-case: AGR Tools 1.0 (#1024) source class A/B/C / small parts of zavod sources, 3ds Max side. Stub of branch 0; owned by branch F (improve/issue-1024-passport).

runtime.edits_100 calls `<function>(ctx, mode, nodes, preview)` for `scene_source_class` (scene.source_class), `scene_small_parts` (scene.small_parts);
while the function is absent the dispatcher reports `status: not_implemented` (issue #1024).
ctx: agr (runtime globals), core (scene10_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost: ObjRef, user props, one undo record).
Import pymxs inside functions so this file loads under plain pytest.

scene.source_class (read): world-space triangles of the selected nodes in metres (HostAdapter.mesh), the class of
each node and of the whole selection (scene10_core.source_facts). Findings: `panelised` (do not feed the shell
engine; route measurement + direct build), `ambiguous_share` (share at the D066 threshold). Empty selection or a
node without triangles is an error. Nothing in the scene changes.

scene.small_parts (undo): preview lists the nodes found by whole-word keys / size in metres with the reason;
apply moves them to the layer `optimize` in ONE undo record (selection restored), writes the source layer into
the user property `agr_source_layer`. Nodes already on `optimize` are skipped, so a second run finds 0 new.
"""


def _rt():
    from pymxs import runtime
    return runtime


def _geometry(nodes):
    rt = _rt()
    return [n for n in nodes if rt.isValidNode(n) and rt.superClassOf(n) == rt.GeometryClass
            and rt.classOf(n) != rt.TargetObject]


def _pick(nodes, what):
    rt = _rt()
    picked = list(nodes) if nodes else list(rt.selection)
    if not picked:
        raise ValueError(what + ': empty selection; select the source objects')
    return picked


# ---- scene.source_class ---------------------------------------------------------------------------------------
def class_facts(ctx, nodes):
    """[(ref, facts | SourceClassError)] per node and the facts of the whole selection (pure part testable)."""
    core = ctx.core
    refs = ctx.host.refs(nodes)
    meshes = [ctx.host.mesh(r) for r in refs]
    per = []
    for ref, m in zip(refs, meshes):
        try:
            per.append((ref, core.source_facts(m['verts'], m['faces'])))
        except core.SourceClassError as exc:
            per.append((ref, exc))
    return per, meshes


def scene_source_class(ctx, mode, nodes, preview):
    core, edit = ctx.core, ctx.edit
    if mode != 'preview':
        raise ValueError('scene.source_class is read-only')
    picked = _pick(nodes, 'scene.source_class')
    geo = _geometry(picked)
    not_geo = [str(n.name) for n in picked if n not in geo]
    if not geo:
        raise ValueError('scene.source_class: no geometry in the selection')
    per, meshes = class_facts(ctx, geo)
    return source_class_report(edit, core, per, meshes, not_geo, ctx.emax.snapshot(geo))


def source_class_report(edit, core, per, meshes, not_geo, snapshot):
    """The read report from per-node facts (shared with the unit tests)."""
    objects, classes, ambiguous, skipped = [], {}, [], []
    for ref, facts in per:
        if isinstance(facts, Exception):
            raise ValueError('scene.source_class: {}: {}'.format(ref['name'], facts))
        f = []
        if facts['class'] == core.PANELISED:
            f.append(edit.finding('panelised', (), '{} parts, largest share {:.4f} < {}: route {}'.format(
                facts['parts'], facts['largest_share'], core.PANEL_HINT_SHARE, facts['route'])))
        elif facts['class'] == core.AMBIGUOUS:
            f.append(edit.finding('ambiguous_share', (), 'largest share {:.10f} at the threshold {}'.format(
                facts['largest_share'], core.PANEL_HINT_SHARE)))
            ambiguous.append({'item': ref['name'], 'reason': 'largest part share at PANEL_HINT_SHARE; not classified'})
        objects.append(edit.entry(ref['handle'], ref['name'], f))
        classes[ref['name']] = {k: facts[k] for k in ('class', 'level', 'parts', 'largest_share', 'shell', 'route',
                                                      'triangles')}
    for name in not_geo:
        skipped.append(edit.skipped(name, 'not geometry'))
    verts, tris = core.merge_meshes(meshes)
    try:
        whole = core.source_facts(verts, tris)
        whole = {k: whole[k] for k in ('class', 'level', 'parts', 'largest_share', 'shell', 'route', 'triangles')}
    except core.SourceClassError as exc:
        whole = {'class': core.AMBIGUOUS, 'error': str(exc)}
    state = {'snapshot': snapshot, 'classes': classes}
    return edit.report('scene.source_class', 'preview', objects, done=[], skipped_=skipped, ambiguous=ambiguous,
                       state_hash=edit.fingerprint(state), extra={'classes': classes, 'source': whole,
                                                                 'rule': 'D066 PANEL_HINT_SHARE {}'.format(
                                                                     core.PANEL_HINT_SHARE)})


# ---- scene.small_parts ----------------------------------------------------------------------------------------
def small_items(ctx, nodes):
    """[{'ref', 'name', 'layer', 'extent_m', 'faces'}] of geometry nodes (metres by units.SystemScale)."""
    rt = _rt()
    k = ctx.host.m_per_unit()
    out = []
    for n, ref in zip(nodes, ctx.host.refs(nodes)):
        lo, hi = n.min, n.max
        extent = max(float(hi.x - lo.x), float(hi.y - lo.y), float(hi.z - lo.z)) * k
        mesh = rt.snapshotAsMesh(n)
        try:
            faces = int(mesh.numfaces)
        finally:
            rt.delete(mesh)
        out.append({'ref': ref, 'name': str(n.name), 'layer': str(n.layer.name), 'extent_m': extent, 'faces': faces,
                    'group_member': bool(rt.isGroupMember(n))})
    return out


def small_report(edit, core, mode, items, opts, state, moved=None, raw=None):
    findings, done, skipped = core.small_parts_plan(items, opts)
    objects = []
    for it in items:
        objects.append(edit.entry(it['ref']['handle'], it['name'],
                                  [edit.finding(c, (), d) for c, d in findings[it['name']]]))
    extra = {'layer': opts['layer'], 'options': {k: opts[k] for k in ('max_extent_m', 'max_faces')},
             'found': len(done)}
    if moved is not None:
        extra['moved'] = moved
    else:
        extra['options_raw'] = dict(raw or {})
    return edit.report('scene.small_parts', mode, objects, done=done,
                       skipped_=[edit.skipped(n, r) for n, r in skipped], ambiguous=[],
                       state_hash=edit.fingerprint(state) if mode == 'preview' else None, extra=extra)


def scene_small_parts(ctx, mode, nodes, preview):
    core, edit = ctx.core, ctx.edit
    rt = _rt()
    opts = core.small_options(ctx.options if mode == 'preview' else preview['plan'].get('options_raw'))
    picked = list(nodes) if nodes else list(rt.objects)
    geo = _geometry(picked)
    if not geo:
        raise ValueError('scene.small_parts: no geometry to look at')
    items = small_items(ctx, geo)
    state = {'items': [dict({k: it[k] for k in ('name', 'layer', 'extent_m', 'faces', 'group_member')},
                            handle=it['ref']['handle'])
                       for it in items], 'options': opts}
    if mode == 'preview':
        return small_report(edit, core, 'preview', items, opts, state, raw=ctx.options)
    edit.require_current(preview, state)
    _findings, todo, _skipped = core.small_parts_plan(items, opts)
    by_name = {it['name']: it for it in items}
    moved = []
    with ctx.emax.session('scene.small_parts'):
        layer = rt.LayerManager.getLayerFromName(opts['layer'])
        if layer is None:
            layer = rt.LayerManager.newLayerFromName(opts['layer'])
        for name in todo:
            it = by_name[name]
            node, = ctx.host.resolve([it['ref']])
            ctx.host.set_prop(it['ref'], core.SOURCE_LAYER_PROP, it['layer'])
            layer.addNode(node)
            moved.append({'name': name, 'from': it['layer']})
    return small_report(edit, core, 'apply', items, opts, state, moved)
