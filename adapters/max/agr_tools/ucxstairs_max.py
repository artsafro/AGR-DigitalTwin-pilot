"""AGR Tools 1.0 (#1024) UCX stairs, 3ds Max side. Owned by branch T (improve/issue-1024-deliver-small).

runtime.edits_100 calls `ucx_stairs(ctx, mode, nodes, preview)` (ucx.stairs, plan mode `read`: preview only).
ctx: agr (runtime globals), core (ucxstairs_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost: ObjRef, meshes in metres). Import pymxs inside functions so this file loads under pytest.

Read only: meshes come from host.mesh (snapshotAsMesh, world space, units.SystemScale), nothing is selected,
moved or created. Stairs are found by name (option `stair_pattern`), their UCX by `UCX_<stair name>[_NN]`.
"""


def _rt():
    from pymxs import runtime
    return runtime


def ucx_stairs(ctx, mode, nodes, preview):
    core, edit, host = ctx.core, ctx.edit, ctx.host
    if mode != 'preview':
        raise ValueError('ucx.stairs is read-only: there is no apply')
    opts = core.stair_options(ctx.options)
    rt = _rt()
    scope = list(nodes) if nodes else list(rt.objects)
    scope = [n for n in scope if rt.isValidNode(n) and rt.superClassOf(n) == rt.GeometryClass]
    by_name = {str(n.name): n for n in scope}
    rows, digest = [], []
    for name in sorted(by_name):
        if not core.is_stair_name(name, opts['stair_pattern']):
            continue
        ref, = host.refs([by_name[name]])
        mesh = host.mesh(ref)
        pieces = []
        for uname in core.ucx_of(name, [str(n.name) for n in rt.objects if rt.isValidNode(n)]):
            node = rt.getNodeByName(uname)
            uref, = host.refs([node])
            um = host.mesh(uref)
            pieces.append({'name': uname, 'verts': um['verts'], 'tris': um['faces']})
        findings, metrics = core.evaluate_stair({'verts': mesh['verts'], 'tris': mesh['faces'], 'ucx': pieces},
                                                opts['tolerance_cm'] / 100.0)
        rows.append({'handle': ref['handle'], 'name': name, 'findings': findings, 'metrics': metrics})
        digest.append([name, len(mesh['verts']), [[p['name'], len(p['verts'])] for p in pieces]])
    state = {'tool': core.TOOL, 'options': opts, 'stairs': digest, 'unit_m': host.m_per_unit()}
    return core.ucx_stairs_report(edit, opts, rows, edit.fingerprint(state))
