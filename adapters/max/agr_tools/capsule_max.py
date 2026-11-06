"""new-case: AGR Tools 1.0 (#1024) interior capsules, 3ds Max side; owned by branch K (improve/issue-1024-capsules-roof).

runtime.edits_100 calls `body_capsules(ctx, mode, nodes, preview)` for `body.capsules` (station 1.0.12, plan mode
`copy`: the bodies are only read, the capsules are NEW objects). ctx: agr, core (capsule_core), edit (edit_core),
emax (edit_max), options, host (host_max.MaxHost).
* preview: bodies (the given nodes or the selection) -> host.mesh (metres) -> openings_core.find_openings (branch
  J, the ONE recognition) -> capsule_core.plan. Nothing changes; `plan.state_hash` covers the bodies, the units and
  the options.
* apply: the unaltered preview while the bodies are unchanged -> the same plan -> one Editable_Poly per capsule
  (system units via units.SystemScale), role `capsule`, layer CAPSULE_interior, the library placeholder material
  «интерьер»; ONE undo record, the selection restored (edit_max.session). The bodies are never touched.
Import pymxs inside functions so this file loads under plain pytest.
"""
import importlib.util
import os
import sys

TOOL = 'body.capsules'
# Test seam (until branch J merges openings_core): a module registered under this name in sys.modules with a
# `find_openings(mesh, options)` replaces openings_core. Product code never registers it.
OPENINGS_STANDIN = 'agr_tools_openings_standin'


def _rt():
    from pymxs import runtime
    return runtime


def _here(name):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)


def find_openings_fn(ctx):
    standin = sys.modules.get(OPENINGS_STANDIN)
    if standin is not None:
        return standin.find_openings
    spec = importlib.util.spec_from_file_location('agr_tools_openings_core', _here('openings_core.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.find_openings


def targets(nodes, tool):
    rt = _rt()
    if nodes is None:
        nodes = list(rt.selection)
    nodes = list(nodes or ())
    if not nodes:
        raise ValueError(tool + ': empty target set')
    seen, out = set(), []
    for n in nodes:
        if not rt.isValidNode(n):
            raise ValueError(tool + ': invalid node')
        if not bool(rt.canConvertTo(n, rt.TriMeshGeometry)):
            raise ValueError(tool + ': not a mesh object: ' + str(n.name))
        h = int(rt.getHandleByAnim(n))
        if h not in seen:
            seen.add(h)
            out.append(n)
    return sorted(out, key=lambda n: int(rt.getHandleByAnim(n)))


def from_preview(preview):
    rt = _rt()
    out = []
    for h in preview['plan']['handles']:
        n = rt.getAnimByHandle(int(h))
        if n is None or not rt.isValidNode(n):
            raise ValueError('a body of the preview is gone; run preview again')
        out.append(n)
    return out


def state(ctx, nodes, opts):
    return {'nodes': ctx.emax.snapshot(nodes), 'm_per_unit': ctx.host.m_per_unit(), 'options': opts}


def _bodies(ctx, nodes):
    find = find_openings_fn(ctx)
    rt = _rt()
    out = []
    for n, ref in zip(nodes, ctx.host.refs(nodes)):
        mesh = ctx.host.mesh(ref)
        try:
            ops = find(mesh, {})
        except NotImplementedError as exc:
            raise ValueError(TOOL + ': ' + str(exc) + ' - openings come only from openings_core (K1)') from None
        out.append({'handle': int(rt.getHandleByAnim(n)), 'name': str(n.name), 'openings': ops})
    return out


def _plan(ctx, nodes, raw):
    return ctx.core.plan(_bodies(ctx, nodes), raw)


def _entries(edit, plan, nodes):
    rt = _rt()
    out = []
    for n in nodes:
        h = int(rt.getHandleByAnim(n))
        out.append(edit.entry(h, str(n.name), [edit.finding(c, (), d) for c, d in plan['findings'].get(h, ())]))
    return out


# ---- mesh creation (shared with roof_max) ------------------------------------------------------------------------
def tris_with_vis(core, verts, faces):
    """[(i, j, k), (vis_ij, vis_jk, vis_ki)] fan / ear triangles of n-gon faces; inner diagonals hidden."""
    out = []
    for f in faces:
        if len(f) == 3:
            out.append(((f[0], f[1], f[2]), (True, True, True)))
            continue
        n = core._unit(core.newell([verts[i] for i in f]))
        u = core._sub(verts[f[1]], verts[f[0]])
        u = core._unit(core._sub(u, core._mul(n, core._dot(u, n))))
        v = core._cross(n, u)
        poly = [[core._dot(verts[i], u), core._dot(verts[i], v)] for i in f]
        bound = {(f[i], f[(i + 1) % len(f)]) for i in range(len(f))}
        for t in core.ear_clip(poly):
            a, b, c = f[t[0]], f[t[1]], f[t[2]]
            out.append(((a, b, c), ((a, b) in bound, (b, c) in bound, (c, a) in bound)))
    return out


def make_poly(core, name, verts_m, faces, m_per_unit):
    """Editable_Poly from metres + n-gon faces (face winding kept: normals as in the core); m_per_unit from
    host.m_per_unit() (units.SystemScale)."""
    rt = _rt()
    k = 1.0 / float(m_per_unit)
    tv = tris_with_vis(core, verts_m, faces)
    pv = rt.Array(*[rt.Point3(v[0] * k, v[1] * k, v[2] * k) for v in verts_m])
    pf = rt.Array(*[rt.Point3(t[0] + 1, t[1] + 1, t[2] + 1) for t, _ in tv])
    node = rt.mesh(vertices=pv, faces=pf)
    for i, (_, vis) in enumerate(tv, 1):
        for e in range(3):
            rt.setEdgeVis(node, i, e + 1, bool(vis[e]))
    rt.update(node)
    rt.convertTo(node, rt.Editable_Poly)
    node.name = rt.uniqueName(name) if rt.getNodeByName(name) is not None else name
    return node


def layer(name):
    rt = _rt()
    lay = rt.LayerManager.getLayerFromName(name)
    if lay is None or lay == rt.undefined:
        lay = rt.LayerManager.newLayerFromName(name)
    return lay


def stub_material(name, colour):
    """The library placeholder material by name: reuse a scene material of that name, else a Standard stub."""
    rt = _rt()
    for m in rt.sceneMaterials:
        if str(m.name) == name:
            return m
    m = rt.StandardMaterial(name=name)
    m.diffuse = rt.Color(*colour)
    return m


# ---- the button ---------------------------------------------------------------------------------------------------
def body_capsules(ctx, mode, nodes, preview):
    edit, core = ctx.edit, ctx.core
    rt = _rt()
    if mode == 'preview':
        nodes = targets(nodes, TOOL)
        plan = _plan(ctx, nodes, ctx.options)
        st = state(ctx, nodes, plan['options'])
        caps = [{'name': r['name'], 'body': r['body'], 'opening': r['opening'], 'kind': r['kind'],
                 'verts': len(r['verts']), 'faces': len(r['faces'])} for r in plan['rows']]
        extra = {'handles': [int(rt.getHandleByAnim(n)) for n in nodes], 'options': plan['options'],
                 'capsules': caps, 'role': core.ROLE, 'layer': core.LAYER, 'material': core.MATERIAL,
                 'm_per_unit': ctx.host.m_per_unit()}
        return edit.report(TOOL, 'preview', objects=_entries(edit, plan, nodes), done=plan['done'],
                           skipped_=plan['skipped'], ambiguous=plan['ambiguous'],
                           state_hash=edit.fingerprint(st), extra=extra)
    nodes = from_preview(preview)
    opts = preview['plan']['options']
    edit.require_current(preview, state(ctx, nodes, opts))
    plan = _plan(ctx, nodes, opts)
    names = [r['name'] for r in plan['rows']]
    if names != [c['name'] for c in preview['plan']['capsules']]:
        raise edit.StalePreview('the capsule plan changed since the preview; run preview again')
    objects, done, made = [], [], []
    with ctx.emax.session(TOOL):
        lay = layer(core.LAYER)
        mat = stub_material(core.MATERIAL, (128, 118, 104))
        for r in plan['rows']:
            node = make_poly(core, r['name'], r['verts'], r['faces'], ctx.host.m_per_unit())
            node.material = mat
            lay.addNode(node)
            ref, = ctx.host.refs([node])
            ctx.host.set_role(ref, core.ROLE)
            rt.setUserProp(node, 'agr_capsule', '{} opening {}'.format(r['body'], r['opening']))
            mesh = ctx.host.mesh(ref)
            got = core.bbox(mesh['verts'])
            want = core.bbox(r['verts'])
            dev = max(abs(got[i][j] - want[i][j]) for i in range(2) for j in range(3))
            findings = [] if dev <= 0.001 else [edit.finding('readback', (), 'bbox off by {:.1f} mm'.format(
                dev * 1000))]
            h = int(rt.getHandleByAnim(node))
            objects.append(edit.entry(h, str(node.name), findings))
            done.append('{} <- {} opening {} ({})'.format(str(node.name), r['body'], r['opening'], r['kind']))
            made.append({'name': str(node.name), 'handle': h, 'body': r['body'], 'opening': r['opening'],
                         'kind': r['kind']})
    return edit.report(TOOL, 'apply', objects=objects, done=done, skipped_=preview['plan']['skipped'],
                       ambiguous=preview['plan']['ambiguous'],
                       extra={'capsules': made, 'layer': core.LAYER, 'role': core.ROLE, 'material': core.MATERIAL})
