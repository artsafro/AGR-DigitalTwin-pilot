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
