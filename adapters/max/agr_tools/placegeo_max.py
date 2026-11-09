"""AGR Tools 1.0 (#1024) placement by the passport, 3ds Max side. owned by branch T (improve/issue-1024-deliver-small).

runtime.edits_100 calls `export_place_by_passport(ctx, mode, nodes, preview)` (export.place_by_passport, plan mode `undo`).
ctx: agr (runtime globals), core (placegeo_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost: ObjRef, one undo record). Import pymxs inside functions so this file loads under pytest.

preview: reads the passport (strict JSON, never executed), checks the FBX file, reports the target and the
single-precision error; the scene is not touched. apply: ONE undo record; imports the FBX, moves the imported root
nodes by the target (the FBX origin lands on [x, y, h_relief]), reads the positions back; on ANY error the nodes
imported by this call are deleted (0 new nodes) and the error is raised. No Dummy helper, no globals, the previous
selection is restored. Metres via host.m_per_unit() (units.SystemScale).
"""
import hashlib
import os


def _rt():
    from pymxs import runtime
    return runtime


def _state(core, edit, opts, data, fbx_stat, unit_m):
    return {'tool': core.TOOL, 'options': opts, 'passport_sha': hashlib.sha256(data).hexdigest(),
            'fbx': fbx_stat, 'unit_m': unit_m}


def _locate(core, opts):
    """(passport path, passport bytes, fbx stat) or raises PassportError."""
    fbx = opts['fbx']
    if not os.path.isfile(fbx):
        raise core.PassportError('fbx_missing', 'FBX не найден: {}'.format(fbx))
    st = os.stat(fbx)
    with open(fbx, 'rb') as f:
        core.check_fbx_header(f.read(32))
    folder = os.path.dirname(fbx)
    path = opts['passport'] or core.find_passport(folder, os.listdir(folder))
    if not os.path.isfile(path):
        raise core.PassportError('passport_missing', 'Паспорт не найден: {}'.format(path))
    try:
        with open(path, 'rb') as f:
            data = f.read()
    except OSError as exc:
        raise core.PassportError('passport_missing', 'Паспорт не читается ({}): {}'.format(exc.strerror or 'ошибка', path)) from None
    return path, data, [st.st_size, st.st_mtime_ns]


def _plan(ctx, opts):
    """(values, plan, state, problems) of the current files."""
    core, edit = ctx.core, ctx.edit
    unit_m = ctx.host.m_per_unit()
    try:
        path, data, fbx_stat = _locate(core, opts)
        values = core.read_passport(data)
    except core.PassportError as err:
        return None, None, {'tool': core.TOOL, 'options': opts, 'error': err.code}, [{'code': err.code, 'message': err.message}]
    plan = core.plan_target(values, unit_m)
    opts = dict(opts, passport=path)
    return values, plan, _state(core, edit, opts, data, fbx_stat, unit_m), []


def export_place_by_passport(ctx, mode, nodes, preview):
    core, edit, host = ctx.core, ctx.edit, ctx.host
    if mode == 'preview':
        try:
            opts = core.place_options(ctx.options)
        except core.PassportError as err:
            raise ValueError(err.message) from None
        values, plan, state, problems = _plan(ctx, opts)
        return core.report(edit, 'preview', opts, values, plan, [], edit.fingerprint(state), problems)
    pp = preview['plan']
    opts = {'fbx': pp['fbx'], 'passport': pp['passport'], 'accept_precision_loss': pp['accept_precision_loss']}
    if preview['status'] != 'pass':
        raise ValueError('the preview has open problems; fix them and run the preview again')
    values, plan, state, problems = _plan(ctx, opts)
    if problems:
        raise ValueError(problems[0]['message'])
    edit.require_current(preview, state)
    rt = _rt()
    unit_m = host.m_per_unit()
    saved = list(rt.selection)
    before = {int(rt.getHandleByAnim(n)) for n in rt.objects}
    new, roots, worst = [], [], 0.0
    with host.undo('Поставить по паспорту'):
        try:
            rt.importFile(opts['fbx'], rt.name('noPrompt'))
            new = [n for n in rt.objects if int(rt.getHandleByAnim(n)) not in before]
            if not new:
                raise ValueError('FBX не дал ни одного объекта: {}'.format(opts['fbx']))
            names = {int(rt.getHandleByAnim(n)) for n in new}
            roots = [n for n in new if n.parent is None or int(rt.getHandleByAnim(n.parent)) not in names]
            origins = [[float(n.pos.x), float(n.pos.y), float(n.pos.z)] for n in roots]
            t = plan['target_units']
            for n in roots:
                n.pos = rt.Point3(float(n.pos.x) + t[0], float(n.pos.y) + t[1], float(n.pos.z) + t[2])
            for n, o in zip(roots, origins):
                want = [o[0] + t[0], o[1] + t[1], o[2] + t[2]]
                ok, w = core.readback_ok(want, [float(n.pos.x), float(n.pos.y), float(n.pos.z)], unit_m,
                                         max(core.READBACK_TOL_M, plan['precision_m'] * 2))
                worst = max(worst, w)
                if not ok:
                    raise ValueError('позиция после переноса отличается на {:.4f} м'.format(w))
        except Exception:
            # the importer may have failed half way: everything that is not in the `before` snapshot is ours
            for n in [m for m in rt.objects if int(rt.getHandleByAnim(m)) not in before]:
                if rt.isValidNode(n):
                    rt.delete(n)
            raise
    try:
        rt.clearSelection()
        for n in saved:
            if rt.isValidNode(n):
                rt.selectMore(n)
    except Exception:  # noqa: BLE001 - selection is a courtesy, the placement already succeeded
        pass
    refs = host.refs(roots)
    return core.report(edit, 'apply', opts, values, plan, [{'handle': r['handle'], 'name': r['name']} for r in refs], None,
                       readback=worst)
