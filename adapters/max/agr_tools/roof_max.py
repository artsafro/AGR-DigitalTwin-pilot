"""new-case: AGR Tools 1.0 (#1024) roof plane by parapet, 3ds Max side; owned by branch K (improve/issue-1024-capsules-roof).

runtime.edits_100 calls `body_roof(ctx, mode, nodes, preview)` for `body.roof` (station 1.0.13, plan mode `copy`:
the parapet / body objects are only read, the slab is a NEW object). ctx: agr, core (roof_core), edit (edit_core),
emax (edit_max), options, host (host_max.MaxHost).
* preview: host.mesh (metres, world) of every object -> roof_core.plan: the open bottom loop of the inner parapet
  faces (contour A), a plane fitted to it, the inset outline + lift. Slopes > 10 deg are `ambiguous` and listed in
  `plan.agent_requests` (К4, branch U).
* apply: the unaltered preview while the objects are unchanged -> one Editable_Poly slab (one n-gon, normal up) per
  loop, role `roof`, layer ROOF_slabs; ONE undo record, the selection restored. The originals are never touched.
The mesh helpers are capsule_max's (same branch). Import pymxs inside functions so this file loads under pytest.
"""
import importlib.util
import os

TOOL = 'body.roof'


def _rt():
    from pymxs import runtime
    return runtime


def _glue():
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location('agr_tools_capsule_max_k', os.path.join(here, 'capsule_max.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _bodies(ctx, nodes):
    rt = _rt()
    return [{'handle': int(rt.getHandleByAnim(n)), 'name': str(n.name), 'mesh': ctx.host.mesh(ref)}
            for n, ref in zip(nodes, ctx.host.refs(nodes))]


def body_roof(ctx, mode, nodes, preview):
    edit, core, cm = ctx.edit, ctx.core, _glue()
    rt = _rt()
    if mode == 'preview':
        nodes = cm.targets(nodes, TOOL)
        plan = core.plan(_bodies(ctx, nodes), ctx.options)
        st = cm.state(ctx, nodes, plan['options'])
        slabs = [{'name': r['name'], 'body': r['body'], 'level_m': r['level_m'], 'slope_deg': r['slope_deg'],
                  'points': r['points'], 'area_m2': r['area_m2']} for r in plan['rows']]
        extra = {'handles': [int(rt.getHandleByAnim(n)) for n in nodes], 'options': plan['options'],
                 'slabs': slabs, 'agent_requests': plan['agent_requests'], 'role': core.ROLE, 'layer': core.LAYER,
                 'm_per_unit': ctx.host.m_per_unit()}
        objects = [edit.entry(int(rt.getHandleByAnim(n)), str(n.name),
                              [edit.finding(c, (), d) for c, d in plan['findings'].get(int(rt.getHandleByAnim(n)), ())])
                   for n in nodes]
        return edit.report(TOOL, 'preview', objects=objects, done=plan['done'], skipped_=plan['skipped'],
                           ambiguous=plan['ambiguous'], state_hash=edit.fingerprint(st), extra=extra)
    nodes = cm.from_preview(preview)
    opts = preview['plan']['options']
    edit.require_current(preview, cm.state(ctx, nodes, opts))
    plan = core.plan(_bodies(ctx, nodes), opts)
    if [r['name'] for r in plan['rows']] != [s['name'] for s in preview['plan']['slabs']]:
        raise edit.StalePreview('the roof plan changed since the preview; run preview again')
    objects, done, made = [], [], []
    with ctx.emax.session(TOOL):
        lay = cm.layer(core.LAYER)
        for r in plan['rows']:
            node = cm.make_poly(core.G, r['name'], r['verts'], r['faces'], ctx.host.m_per_unit())
            lay.addNode(node)
            ref, = ctx.host.refs([node])
            ctx.host.set_role(ref, core.ROLE)
            mesh = ctx.host.mesh(ref)
            zs = [v[2] for v in mesh['verts']]
            want = [v[2] for v in r['verts']]
            dev = max(abs(min(zs) - min(want)), abs(max(zs) - max(want)))
            findings = [] if dev <= 0.0005 else [edit.finding('readback', (), 'slab height off by {:.2f} mm'.format(
                dev * 1000))]
            h = int(rt.getHandleByAnim(node))
            objects.append(edit.entry(h, str(node.name), findings))
            done.append('{} <- {}: level {:.3f} m + {:.0f} mm'.format(str(node.name), r['body'], r['level_m'],
                                                                     r['lift_m'] * 1000))
            made.append({'name': str(node.name), 'handle': h, 'body': r['body'], 'polys': int(rt.polyop.getNumFaces(node))})
    return edit.report(TOOL, 'apply', objects=objects, done=done, skipped_=preview['plan']['skipped'],
                       ambiguous=preview['plan']['ambiguous'],
                       extra={'slabs': made, 'agent_requests': preview['plan']['agent_requests'],
                              'layer': core.LAYER, 'role': core.ROLE})
