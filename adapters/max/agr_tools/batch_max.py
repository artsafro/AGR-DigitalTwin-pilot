"""new-case: AGR Tools 0.9 (#979) batch export, 3ds Max side. Owned by branch D
(improve/issue-979-export-scene-light).

runtime.edits_090 calls `export_batch(ctx, mode, nodes, preview)` for export.batch.
ctx: agr (runtime globals), core (batch_core), edit (edit_core), emax (edit_max), options (dict of the preview).
Import pymxs inside functions so this file loads under plain pytest.

Scope: the given nodes, else every geometry node of the scene. Each group of one AGR_EXPORT_PATH goes through
runtime.export_preview (gates, dry run) and on apply runtime.export_commit (FBX of detached copies + readback),
exactly as export.checked; the working nodes are never edited. The procedural list comes from
runtime.edits_090('qa.procedural_objects', 'preview') (branch C), never from an import of qa9_*.
"""


def _rt():
    from pymxs import runtime
    return runtime


def _handle(n):
    return int(_rt().getHandleByAnim(n))


def _scope(nodes):
    rt = _rt()
    scope = list(nodes) if nodes is not None else list(rt.geometry)
    return [n for n in scope if rt.isValidNode(n)]


def _plan(ctx, nodes):
    core, edit, agr = ctx.core, ctx.edit, ctx.agr
    scope = _scope(nodes)
    by_handle = {_handle(n): n for n in scope}
    rows = [{'handle': h, 'name': str(n.name), 'path': agr._prop(n, core.KEY)} for h, n in by_handle.items()]
    grouped = [by_handle[r['handle']] for r in rows if r['path']]
    try:
        proc = agr.edits_090(core.PROCEDURAL, 'preview', None, grouped or None, None)
    except Exception as exc:  # noqa: BLE001 - unknown procedural state: every group is blocked
        proc = exc

    def members(g):
        return [by_handle[m['handle']] for m in g['members']]

    def dry_run(g):
        return agr.export_preview(members(g), g['target'])

    groups, skipped, procedural = core.plan_batch(edit, rows, proc, dry_run)
    return groups, skipped, procedural, members


def export_batch(ctx, mode, nodes, preview):
    core, edit, agr = ctx.core, ctx.edit, ctx.agr
    core.batch_options(ctx.options)
    groups, skipped, procedural, members = _plan(ctx, nodes)
    state = edit.fingerprint(core.batch_state(edit, groups, skipped, procedural))
    if mode == 'preview':
        return core.batch_report(edit, 'preview', groups, skipped, procedural, state)
    edit.require_current(preview, core.batch_state(edit, groups, skipped, procedural))

    def commit(g, rep):
        return agr.export_commit(members(g), rep, g['target'])

    core.apply_batch(groups, commit)
    return core.batch_report(edit, 'apply', groups, skipped, procedural)
