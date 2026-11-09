"""new-case: AGR Tools 1.0 (#1024) source intake: units, axes, origin, 3ds Max side. Stub of branch 0; owned by branch F (improve/issue-1024-passport).

runtime.edits_100 calls `<function>(ctx, mode, nodes, preview)` for `source_intake` (source.intake);
while the function is absent the dispatcher reports `status: not_implemented` (issue #1024).
ctx: agr (runtime globals), core (intake_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost: ObjRef, user props, one undo record).
Import pymxs inside functions so this file loads under plain pytest.

source.intake (plan mode `copy`): preview reads the selected source (world meshes in metres), finds the unit
factor, the up axis (option) and the common zero, classifies the source (scene10_core, D066) and changes nothing.
apply makes export copies (edit_max.export_copies, layer `AGR_intake`, suffix `_AGR_intake_`; the originals stay
byte for byte), multiplies the normalisation matrix onto each copy (ONE undo record, selection restored), reads
the copies back (size, zero) and writes source + normalization into the scene's passport (passport_max), with a
history copy of the previous passport. No passport linked: the passport write is listed as skipped.
"""
INTAKE_LAYER = 'AGR_intake'
INTAKE_SUFFIX = '_AGR_intake_'
SOURCE_PROP = 'agr_intake_source'


def _rt():
    from pymxs import runtime
    return runtime


def _load(ctx, name):
    return ctx.agr._load_core(name, 'agr_tools_' + name[:-3])


def _geometry(nodes):
    rt = _rt()
    return [n for n in nodes if rt.isValidNode(n) and rt.superClassOf(n) == rt.GeometryClass
            and rt.classOf(n) != rt.TargetObject]


def plan_of(ctx, meshes, m_per_unit, opts, scene10):
    """(plan, findings, class facts) from HostAdapter meshes - pure, shared with the unit tests."""
    core = ctx.core
    plan = core.normalization([{'name': m['ref']['name'], 'verts': m['verts']} for m in meshes], m_per_unit, opts)
    found = core.findings(plan, opts)
    norm = [{'verts': [core.rotate([c * plan['factor'] for c in p], plan['source_up_axis']) for p in m['verts']],
             'faces': m['faces']} for m in meshes]
    verts, tris = scene10.merge_meshes(norm)
    try:
        facts = scene10.source_facts(verts, tris)
    except scene10.SourceClassError as exc:
        facts = {'class': scene10.AMBIGUOUS, 'level': scene10.LEVEL_RULE[scene10.AMBIGUOUS], 'parts': 0,
                 'largest_share': 0.0, 'route': scene10.ROUTES[scene10.AMBIGUOUS], 'shell': False,
                 'error': str(exc)}
    mats = sorted({int(i) for m in meshes for i in m.get('mat_ids', ())})
    return plan, found, facts, mats


def build_report(ctx, mode, meshes, plan, found, facts, mats, state, done, skipped, extra=None):
    edit = ctx.edit
    objects = [edit.entry(m['ref']['handle'], m['ref']['name'],
                          [edit.finding(c, (), d) for c, d in found[m['ref']['name']]]) for m in meshes]
    ambiguous = []
    if facts['class'] == 'ambiguous':
        ambiguous.append({'item': 'source', 'reason': 'source class not decided: ' + facts.get(
            'error', 'largest part share at the D066 threshold')})
    x = {'normalization': {k: plan[k] for k in ('source_units', 'scene_units', 'factor', 'units_why',
                                                'source_up_axis', 'origin_m', 'size_m')},
         'class': {k: facts[k] for k in ('class', 'level', 'parts', 'largest_share', 'route') if k in facts},
         'material_ids': mats}
    x.update(extra or {})
    return edit.report('source.intake', mode, objects, done=done, skipped_=skipped, ambiguous=ambiguous,
                       state_hash=edit.fingerprint(state) if mode == 'preview' else None, extra=x)


def source_intake(ctx, mode, nodes, preview):
    rt = _rt()
    core, edit = ctx.core, ctx.edit
    scene10 = _load(ctx, 'scene10_core.py')
    raw = ctx.options if mode == 'preview' else preview['plan'].get('options_raw', {})
    opts = core.options(raw)
    picked = list(nodes) if nodes else list(rt.selection)
    if not picked:
        raise ValueError('source.intake: empty selection; select the source objects')
    geo = _geometry(picked)
    if not geo:
        raise ValueError('source.intake: no geometry in the selection')
    refs = ctx.host.refs(geo)
    meshes = [ctx.host.mesh(r) for r in refs]
    k = ctx.host.m_per_unit()
    plan, found, facts, mats = plan_of(ctx, meshes, k, opts, scene10)
    state = {'snapshot': ctx.emax.snapshot(geo), 'm_per_unit': k, 'options': opts}
    src_path = opts['source_path'] or ctx.host.doc()
    pmax = _load(ctx, 'passport_max.py')
    linked = pmax.read_link()
    skipped = [edit.skipped('material split', 'model.attach_by_material (branch G) splits the copy by material '
                                             'IDs; intake lists them only')]
    if not linked:
        skipped.append(edit.skipped('passport', 'the scene has no passport (agr_passport); press «Паспорт» first'))
    if mode == 'preview':
        done = [m['ref']['name'] + INTAKE_SUFFIX + '01' for m in meshes]
        if linked:
            done.append('passport: source + normalization')
        return build_report(ctx, 'preview', meshes, plan, found, facts, mats, state, done, skipped,
                            {'options_raw': dict(raw or {})})
    edit.require_current(preview, state)
    if facts['class'] == 'ambiguous':
        raise ValueError('source.intake: the source class is ambiguous; nothing applied (see the preview)')
    with ctx.emax.session('source.intake'):
        pairs = ctx.emax.export_copies(geo, suffix=INTAKE_SUFFIX, layer=INTAKE_LAYER)
        for orig, copy in pairs:
            bake(copy, plan['matrix_units'], core)
            rt.setUserProp(copy, SOURCE_PROP, str(orig.name))
    copies = [c for _, c in pairs]
    back = [ctx.host.mesh(r) for r in ctx.host.refs(copies)]
    every = [p for b in back for p in b['verts']]
    lo, hi = core.bbox(every)
    readback = {'min_m': [round(c, 6) for c in lo], 'size_m': [round(h - l, 6) for h, l in zip(hi, lo)],
                'copies': [str(c.name) for c in copies]}
    done = [str(c.name) for c in copies]
    if linked:
        saved = pmax.update_linked(ctx, lambda p: _passport_update(pmax, p, core, src_path, facts, plan))
        if saved:
            done.append('passport ' + saved[0])
    return build_report(ctx, 'apply', meshes, plan, found, facts, mats, state, done, skipped,
                        {'readback': readback})


def bake(node, rows, core):
    """Normalise one COPY into its vertices in double precision: a far source (2 345 678 m) multiplied as a float32
    Matrix3 would lose ~0.25 m. The copy becomes an Editable_Mesh with the identity transform (its own stack only;
    the original is never collapsed)."""
    rt = _rt()
    rt.convertToMesh(node)
    tm = node.transform
    t = [[float(r.x), float(r.y), float(r.z)] for r in (tm.row1, tm.row2, tm.row3, tm.row4)]
    local = node.mesh  # TriMesh value: object-space vertices, no float32 world product
    n = int(rt.getNumVerts(local))
    world = []
    for i in range(1, n + 1):
        p = rt.getVert(local, i)
        x, y, z = float(p.x), float(p.y), float(p.z)
        world.append([x * t[0][j] + y * t[1][j] + z * t[2][j] + t[3][j] for j in range(3)])
    node.transform = rt.Matrix3(1)  # pivot on the common zero; world == object space now
    for i, p in enumerate(world, 1):
        rt.setVert(node, i, rt.Point3(*core.apply_matrix(p, rows)))
    rt.update(node)


def _passport_update(pmax, passport, core, src_path, facts, plan):
    pc = pmax._core()
    return pc.with_source(passport, core.passport_source(src_path, facts), core.passport_normalization(plan))
