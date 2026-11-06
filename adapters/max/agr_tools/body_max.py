"""new-case: AGR Tools 1.0 (#1024) body roles, LEVEL_* helpers, 3ds Max side. owned by branch G (improve/issue-1024-body).

runtime.edits_100 calls `<function>(ctx, mode, nodes, preview)` for `body_prepare` (body.prepare);
ctx: agr (runtime globals), core (body_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost: ObjRef, user props, one undo record).
Plan mode `undo`: preview reads the selection and the heights (options.levels in metres, or options.pick clicks with
pickPoint in the interactive panel; batch / MCP / AGR_NO_PROMPT need options.levels); apply re-checks the scene and
sets roles, names, layers and the LEVEL_* Point helpers in ONE undo record (edit_max.session, selection restored).
Import pymxs inside functions so this file loads under plain pytest.
"""
import os

TOOL = 'body.prepare'
HELPER_SIZE_M = 1.0


def _rt():
    from pymxs import runtime
    return runtime


def _handle(n):
    return int(n.inode.handle)


def _kind(n):
    rt = _rt()
    sc = rt.superClassOf(n)
    if sc == rt.GeometryClass and rt.classOf(n) != rt.TargetObject:
        return 'geometry'
    if sc == rt.Helper:
        return 'helper'
    return 'other'


def _material_name(n):
    mat = getattr(n, 'material', None)
    return None if mat is None else str(mat.name)


def _object(n, k):
    rt = _rt()
    role = rt.getUserProp(n, 'agr_role')
    kind = _kind(n)
    return {'handle': _handle(n), 'name': str(n.name), 'kind': kind, 'cls': str(rt.classOf(n)),
            'role': None if role is None else str(role), 'material': _material_name(n) if kind == 'geometry' else None,
            'layer': str(n.layer.name), 'z_m': float(n.pos.z) * k if kind == 'helper' else None}


def _scene_levels(k):
    rt = _rt()
    return [{'handle': _handle(n), 'name': str(n.name), 'z_m': float(n.pos.z) * k}
            for n in rt.objects if str(n.name).startswith('LEVEL_')]


def _state(objects, levels, taken):
    return {'objects': objects, 'levels': levels, 'taken': sorted(taken)}


def _batch():
    rt = _rt()
    if os.environ.get('AGR_NO_PROMPT'):
        return True
    try:
        return bool(rt.GetQuietMode()) or bool(rt.IsNetServer())
    except Exception:  # noqa: BLE001
        return True


def _pick(count, k):
    """Heights (metres) of up to `count` pickPoint clicks; Esc / right click stops early."""
    rt = _rt()
    out = []
    for i in range(count):
        p = rt.pickPoint(prompt='AGR body.prepare: height {} of {} (Esc = done)\n'.format(i + 1, count),
                         snap=rt.name('3D'))
        if rt.classOf(p) != rt.Point3:
            break
        out.append(round(float(p.z) * k, 6))
    return out


def body_prepare(ctx, mode, nodes, preview):
    """Roles, BODY_<material>_NNN names, <ROLE>_main layers and LEVEL_* helpers (#1024 1.0.4, contract К1)."""
    edit, core, host = ctx.edit, ctx.core, ctx.host
    if mode == 'apply':
        return _apply(ctx, preview)
    rt = _rt()
    k = host.m_per_unit()
    nodes = list(nodes) if nodes is not None else list(rt.selection)
    nodes = [n for n in nodes if rt.isValidNode(n)]
    opts = core.options(ctx.options)
    if opts['pick'] and not opts['levels']:
        if _batch():
            raise ValueError('options.pick needs the interactive panel; batch and MCP give options.levels (metres)')
        opts['levels'] = _pick(opts['pick'], k)
        opts['level_given'] = [None] * len(opts['levels'])
        if opts['level_names'] is not None and len(opts['level_names']) != len(opts['levels']):
            opts['level_names'] = None
    if not nodes and not opts['levels']:
        raise ValueError('body.prepare: empty selection and no heights')
    objects = [_object(n, k) for n in nodes]
    levels = _scene_levels(k)
    taken = {str(n.name) for n in rt.objects}
    plan = core.prepare_plan(objects, levels, opts, taken - {o['name'] for o in objects})
    entries = [edit.entry(o['handle'], o['name'], [edit.finding(c, (), d) for c, d in plan['findings'].get(
        o['handle'], ())]) for o in objects]
    done = _done(plan, {o['handle']: o['name'] for o in objects})
    xy = _centre_xy(nodes, k)
    return edit.report(TOOL, 'preview', objects=entries, done=done,
                       skipped_=[edit.skipped(i, r) for i, r in plan['skipped']], ambiguous=plan['ambiguous'],
                       state_hash=edit.fingerprint(_state(objects, levels, taken)),
                       extra={'handles': [o['handle'] for o in objects],
                              'roles': [[h, r] for h, r in plan['roles']],
                              'renames': [[h, a, b] for h, a, b in plan['renames']],
                              'layers': [[h, lay] for h, lay in plan['layers']],
                              'levels': plan['levels'], 'level_xy_m': xy, 'm_per_unit': k,
                              'passport': plan['passport'],
                              'options': {key: opts[key] for key in ('levels', 'rename', 'layers')}})


def _done(plan, names):
    out = ['{}: agr_role={}'.format(names[h], r) for h, r in plan['roles']]
    out += ['{} -> {}'.format(a, b) for _h, a, b in plan['renames']]
    out += ['{} -> layer {}'.format(names[h], lay) for h, lay in plan['layers']]
    out += ['{} at {:.3f} m (Point helper, role helper)'.format(lv['name'], lv['z_m']) for lv in plan['levels']]
    return out


def _centre_xy(nodes, k):
    geo = [n for n in nodes if _kind(n) == 'geometry']
    if not geo:
        return [0.0, 0.0]
    xs = [float(n.min.x) for n in geo] + [float(n.max.x) for n in geo]
    ys = [float(n.min.y) for n in geo] + [float(n.max.y) for n in geo]
    return [round((min(xs) + max(xs)) / 2.0 * k, 6), round((min(ys) + max(ys)) / 2.0 * k, 6)]


def _layer(name):
    rt = _rt()
    layer = rt.LayerManager.getLayerFromName(name)
    if layer is None:
        layer = rt.LayerManager.newLayerFromName(name)
    return layer


def _apply(ctx, preview):
    edit, emax, core, host = ctx.edit, ctx.emax, ctx.core, ctx.host
    rt = _rt()
    p = preview['plan']
    if p['ambiguous']:
        raise ValueError('body.prepare refused: ' + '; '.join(p['ambiguous'][:5]))
    k = host.m_per_unit()
    if abs(k - p['m_per_unit']) > 1e-15:
        raise edit.StalePreview('system units changed since the preview; run preview again')
    nodes = []
    for h in p['handles']:
        n = rt.maxOps.getNodeByHandle(int(h))
        if n is None or not rt.isValidNode(n):
            raise edit.StalePreview('node {} of the preview is gone; run preview again'.format(h))
        nodes.append(n)
    objects = [_object(n, k) for n in nodes]
    taken = {str(n.name) for n in rt.objects}
    edit.require_current(preview, _state(objects, _scene_levels(k), taken))
    by = {_handle(n): n for n in nodes}
    made = []
    with emax.session(TOOL):
        for h, role in p['roles']:
            rt.setUserProp(by[h], 'agr_role', role)
        for h, _old, new in p['renames']:
            by[h].name = new
        for h, lay in p['layers']:
            _layer(lay).addNode(by[h])
        x, y = p['level_xy_m']
        for lv in p['levels']:
            pt = rt.Point(name=lv['name'], pos=rt.Point3(x / k, y / k, lv['z_m'] / k), size=HELPER_SIZE_M / k,
                          cross=True, box=False)
            rt.setUserProp(pt, 'agr_role', 'helper')
            _layer('HELPER_' + core.LAYER_SUFFIX).addNode(pt)
            made.append(pt)
    back = [{'handle': _handle(n), 'name': str(n.name), 'role': rt.getUserProp(n, 'agr_role')}
            for n in nodes + made]
    back = [dict(b, role=None if b['role'] is None else str(b['role'])) for b in back]
    bad = {}
    for h, code, detail in core.check_after(back, p):
        bad.setdefault(h, []).append(edit.finding(code, (), detail))
    for pt, lv in zip(made, p['levels']):
        z = float(pt.pos.z) * k
        if str(pt.name) != lv['name'] or abs(z - lv['z_m']) > 1e-6:
            bad.setdefault(_handle(pt), []).append(edit.finding('level_readback', (), '{} at {:.6f} m'.format(
                pt.name, z)))
    entries = [edit.entry(b['handle'], b['name'], bad.get(b['handle'], [])) for b in back]
    done = ['{}: role {}'.format(b['name'], b['role']) for b in back]
    return edit.report(TOOL, 'apply', objects=entries, done=done, skipped_=p['skipped'], ambiguous=[],
                       extra={'passport': p['passport'], 'levels': p['levels'],
                              'created': [str(pt.name) for pt in made]})
