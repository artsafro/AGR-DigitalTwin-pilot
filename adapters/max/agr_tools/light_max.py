"""new-case: AGR Tools 0.9 (#979) light check (select mode: the UI selects the offenders, not the core), 3ds Max
side. Owned by branch D (improve/issue-979-export-scene-light).

runtime.edits_090 calls `light_check(ctx, mode, nodes, preview)` for light.check.
ctx: agr (runtime globals), core (light_core), edit (edit_core), emax (edit_max), options (dict of the preview).
Import pymxs inside functions so this file loads under plain pytest.

Read only: positions come from `node.pos` (world, system units), metres through `units.SystemType` and
`units.SystemScale` (light_core.metres_per_unit), never `units.decodeValue`. Nothing is recoloured or moved;
the offenders are selected by the UI glue (runtime.select_offenders, one undo record).
"""


def _rt():
    from pymxs import runtime
    return runtime


def _handle(n):
    return int(_rt().getHandleByAnim(n))


def _flag(n, prop):
    try:
        if bool(getattr(n, prop)):
            return True
        return bool(getattr(n.layer, prop))
    except Exception:  # noqa: BLE001 - a node without layer keeps its own flag
        return bool(getattr(n, prop, False))


def _is_light(n):
    rt = _rt()
    return rt.superClassOf(n) == rt.light and rt.classOf(n) != rt.Targetobject


def _pos(p):
    return [float(p.x), float(p.y), float(p.z)]


def _row(n):
    parent = n.parent
    return {'handle': _handle(n), 'name': str(n.name), 'cls': str(_rt().classOf(n)), 'pos': _pos(n.pos),
            'parent': None if parent is None else _handle(parent),
            'hidden': _flag(n, 'isHidden'), 'frozen': _flag(n, 'isFrozen')}


def read_scene(nodes):
    """(lights, helpers) rows of the scope: the given nodes, else every scene object."""
    rt = _rt()
    scope = list(nodes) if nodes is not None else list(rt.objects)
    lights = [n for n in scope if rt.isValidNode(n) and _is_light(n)]
    helpers, seen = [], set()
    for n in lights:
        p = n.parent
        while p is not None and _handle(p) not in seen:
            seen.add(_handle(p))
            helpers.append(p)
            p = p.parent
    return [_row(n) for n in lights], [_row(n) for n in helpers]


def light_check(ctx, mode, nodes, preview):
    core, edit = ctx.core, ctx.edit
    rt = _rt()
    if mode != 'preview':
        raise ValueError('light.check is read-only (select): there is no apply')
    opts = core.light_options(ctx.options)
    unit_m = core.metres_per_unit(str(rt.units.SystemType), float(rt.units.SystemScale))
    lights, helpers = read_scene(nodes)
    ref_pivot = None
    if opts['reference']:
        ref = rt.getNodeByName(opts['reference'])
        if ref is None:
            raise ValueError('reference node not found: ' + opts['reference'])
        ref_pivot = _pos(ref.pivot)
    found, pairs, summary = core.check(lights, helpers, unit_m, opts, ref_pivot)
    state = {'tool': core.TOOL, 'lights': lights, 'helpers': helpers, 'unit_m': unit_m, 'reference': ref_pivot,
             'options': opts}
    notes = ['units: {} x {} -> {} m'.format(rt.units.SystemType, rt.units.SystemScale, unit_m)]
    return core.light_report(edit, lights, helpers, found, pairs, summary, opts, edit.fingerprint(state), notes)


# ---- light.export (#1024, station 1.0.29, branch S) ---------------------------------------------------------------
# runtime.edits_100 calls `light_export(ctx, mode, nodes, preview)`; plan mode `file`: a new `<stem>_Light.fbx` only
# (refuse or the next `_vNNN`), FBX 7.4 written once through a `.partial` file and hard-linked (no clobber), the
# scene unchanged (snapshot before/after), selection restored, readback of the written file by light_core.
def _rotation(n):
    """World rotation of a node as 3x3 column vectors (scale removed); Max rows are the axis images."""
    import math
    tm = n.transform
    cols = []
    for r in (tm.row1, tm.row2, tm.row3):
        v = [float(r.x), float(r.y), float(r.z)]
        ln = math.sqrt(sum(c * c for c in v)) or 1.0
        cols.append([c / ln for c in v])
    return [[cols[j][i] for j in range(3)] for i in range(3)]


def _export_rows():
    rt = _rt()
    lights = [n for n in rt.objects if rt.isValidNode(n) and _is_light(n)]
    rows, helpers, seen, helper_nodes = [], [], set(), []
    for n in lights:
        row = _row(n)
        row['rot'] = _rotation(n)
        try:
            t = n.target
        except Exception:  # noqa: BLE001 - lights without a target property
            t = None
        row['target'] = None if t is None else _handle(t)
        rows.append(row)
        p = n.parent
        while p is not None and _handle(p) not in seen:
            seen.add(_handle(p))
            helpers.append(_row(p))
            helper_nodes.append(p)
            p = p.parent
    return list(lights) + helper_nodes, rows, helpers


def _export_options(ctx, opts):
    import os
    rt = _rt()
    if not opts.get('folder'):
        folder = str(rt.maxFilePath)
        if not folder:
            raise ValueError('light.export: pass options.folder or save the scene')
        opts['folder'] = os.path.abspath(folder)
    return opts


def _file_sha(path):
    import hashlib
    import os
    if not path or not os.path.isfile(path):
        return None
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def _export_state(ctx, nodes, plan, opts):
    return {'tool': 'light.export', 'nodes': ctx.emax.snapshot(nodes), 'target': plan['target'],
            'wanted_sha': _file_sha(plan['wanted']), 'options': opts}


def light_export(ctx, mode, nodes, preview):
    core, edit, emax = ctx.core, ctx.edit, ctx.emax
    rt = _rt()
    opts = core.export_options(ctx.options if mode == 'preview' else preview['plan']['options'])
    opts = _export_options(ctx, opts)
    scene_nodes, rows, helpers = _export_rows()
    plan = core.export_plan(rows, helpers, opts)
    by_handle = {_handle(n): n for n in scene_nodes}  # anim handles, as in the rows (_row)
    export_nodes = [by_handle[h] for h in plan['export']]
    state = _export_state(ctx, export_nodes, plan, opts)
    if mode == 'preview':
        return core.export_report(edit, 'preview', rows, plan, opts, edit.fingerprint(state))
    edit.require_current(preview, state)
    if plan['blockers']:
        raise ValueError('light.export: ' + '; '.join(plan['blockers']))
    before = emax.snapshot(export_nodes)
    writer = ctx.agr._load_core('deliver_max.py', 'agr_tools_deliver_max')  # FBX writer of branch S
    with emax.session(core.EXPORT_TOOL):
        writer.write_new_fbx(export_nodes, plan['target'], core.LIGHT_FBX_PARAMS)
    if emax.snapshot(export_nodes) != before:
        raise RuntimeError('light.export: the scene changed during export')
    with open(plan['target'], 'rb') as f:
        data = f.read()
    back = core.fbx_lights(data)
    found, summary = core.readback_findings(plan, back)
    for h, items in plan['findings'].items():  # light_type / light_outside_root / light_root_name stay reported
        found.setdefault(h, []).extend(items)
    import hashlib
    extra = {'readback': summary, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data),
             'wanted_sha_before': state['wanted_sha'], 'wanted_sha_after': _file_sha(plan['wanted'])}
    if extra['wanted_sha_before'] != extra['wanted_sha_after']:
        raise RuntimeError('light.export: the existing file changed: ' + str(plan['wanted']))
    return core.export_report(edit, 'apply', rows, plan, opts, findings=found, done=[plan['target']], extra=extra)
