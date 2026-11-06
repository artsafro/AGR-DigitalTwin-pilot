"""new-case: AGR Tools 1.0 (#1024) texel rescale / UV distortion check, 3ds Max side; owned by branch M (improve/issue-1024-vpm-layout).

runtime.edits_100 calls `udim_rescale(ctx, mode, nodes, preview)` (udim.rescale, copy) and
`udim_distortion(ctx, mode, nodes, preview)` (udim.distortion, read). ctx: agr (runtime globals), core (udim10_core),
edit (edit_core), emax (edit_max), options (dict of the preview), host (host_max.MaxHost).
Import pymxs inside functions so this file loads under plain pytest.

Reading (`read_tri`, shared with vpm_max.py): `<node>.mesh` - the evaluated TriMesh of any geometry class (a
primitive, Unwrap_UVW on top, Editable_Mesh or Poly) in OBJECT coordinates; world metres are computed here in
double precision: local x objectTransform x metres per unit (units.SystemType x units.SystemScale, never
units.decodeValue). So a centimetre scene gives the numbers of a metre scene and 2 345 678 m does not lose the
float32 precision of world coordinates (L09 r2). Polygons of an Editable_Poly without modifiers map to their
triangles in order (checked: the triangle count must match), so findings name polygons there.

udim.rescale (copy): preview measures and plans; apply re-reads (edit_core.require_current), then in ONE undo
record makes an export copy on layer `AGR_export_udim10`, collapses the COPY to Editable_Mesh, writes channel 1,
reads it back and checks the texel; the working object, its stack and its maps are never touched (GeoAGR wrote
`_id<N>.png` copies and replaced sub-materials, L09). The scope is options.faces (1-based triangles) or the face
selection of an Editable_Mesh/Poly, else the whole object; whole UV elements touching the scope are scaled.

udim.distortion (read): per polygon/triangle texel, anisotropy and mirroring against options.target_px_per_m
(else the object median). Nothing changes: no selection, sub-object level, material or vertex colour change.
"""
TOOL_RESCALE = 'udim.rescale'
TOOL_DIST = 'udim.distortion'
LAYER = 'AGR_export_udim10'
ISSUE = '#1024'


def _rt():
    from pymxs import runtime
    return runtime


def _session_core():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('agr_tools_session_core', Path(__file__).with_name('session_core.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def handle(n):
    return int(_rt().getHandleByAnim(n))


def target_nodes(nodes):
    rt = _rt()
    nodes = list(rt.selection) if nodes is None else list(nodes)
    if not nodes:
        raise ValueError('nothing selected: select the objects')
    out, seen = [], set()
    for n in nodes:
        if not rt.isValidNode(n):
            raise ValueError('invalid node in the target set')
        h = handle(n)
        if h in seen:
            raise ValueError('duplicate node in the target set')
        seen.add(h)
        out.append(n)
    return sorted(out, key=handle)


def is_geometry(n):
    rt = _rt()
    return rt.superClassOf(n) == rt.GeometryClass and bool(rt.canConvertTo(n, rt.TriMeshGeometry))


def _tm_rows(n):
    tm = n.objectTransform
    return [[float(r.x), float(r.y), float(r.z)] for r in (tm.row1, tm.row2, tm.row3, tm.row4)]


def to_world_m(local, rows, k):
    """local (system units, object space) -> world metres, double precision."""
    x, y, z = local
    return [(x * rows[0][j] + y * rows[1][j] + z * rows[2][j] + rows[3][j]) * k for j in range(3)]


def read_tri(n, k):
    """Evaluated TriMesh of a node: {'local', 'verts' (world m), 'tris', 'mat_ids', 'uvs' | None, 'uv_tris' | None,
    'poly_groups' (triangles per polygon of a plain Editable_Poly, else one per triangle), 'kind'}."""
    import math
    rt = _rt()
    m = n.mesh
    nv, nf = int(m.numverts), int(m.numfaces)
    if not nf:
        raise ValueError('empty mesh: ' + str(n.name))
    rows = _tm_rows(n)
    local = []
    for i in range(1, nv + 1):
        p = rt.getVert(m, i)
        q = (float(p.x), float(p.y), float(p.z))
        if not all(math.isfinite(c) for c in q):
            raise ValueError('non-finite vertex: ' + str(n.name))
        local.append(q)
    tris, ids = [], []
    for i in range(1, nf + 1):
        f = rt.getFace(m, i)
        tris.append([int(f.x) - 1, int(f.y) - 1, int(f.z) - 1])
        ids.append(int(rt.getFaceMatID(m, i)))
    uvs = uv_tris = None
    if rt.meshop.getMapSupport(m, 1) and int(rt.meshop.getNumMapVerts(m, 1)) > 0:
        uvs, uv_tris = [], []
        for i in range(1, int(rt.meshop.getNumMapVerts(m, 1)) + 1):
            p = rt.meshop.getMapVert(m, 1, i)
            uvs.append([float(p.x), float(p.y)])
        for i in range(1, nf + 1):
            f = rt.meshop.getMapFace(m, 1, i)
            uv_tris.append([int(f.x) - 1, int(f.y) - 1, int(f.z) - 1])
    groups, kind = None, 'trimesh'
    if int(n.modifiers.count) == 0 and rt.classOf(n.baseObject) == rt.Editable_Poly:
        degs = [int(rt.polyop.getFaceDeg(n, i)) for i in range(1, int(rt.polyop.getNumFaces(n)) + 1)]
        if sum(d - 2 for d in degs) == nf:
            groups, t = [], 0
            for d in degs:
                groups.append(list(range(t, t + d - 2)))
                t += d - 2
            kind = 'poly'
    if groups is None:
        groups = [[i] for i in range(nf)]
    return {'local': local, 'verts': [to_world_m(p, rows, k) for p in local], 'tris': tris, 'mat_ids': ids,
            'uvs': uvs, 'uv_tris': uv_tris, 'poly_groups': groups, 'kind': kind}


def selected_tris(n, mesh):
    """1-based triangles of the face/polygon selection of a plain Editable_Mesh/Poly, else None."""
    rt = _rt()
    if int(n.modifiers.count) != 0:
        return None
    if rt.classOf(n.baseObject) == rt.Editable_Mesh:
        sel = [int(i) for i in rt.getFaceSelection(n)]
        return sorted(sel) or None
    if rt.classOf(n.baseObject) == rt.Editable_Poly and mesh['kind'] == 'poly':
        sel = [int(i) for i in rt.polyop.getFaceSelection(n)]
        out = sorted(t + 1 for p in sel for t in mesh['poly_groups'][p - 1])
        return out or None
    return None


def _uv_hash(mesh):
    from hashlib import sha256
    h = sha256()
    h.update(repr([[round(c, 9) for c in p] for p in (mesh['uvs'] or [])]).encode())
    h.update(repr(mesh['uv_tris']).encode())
    return h.hexdigest()


def _state(ctx, n, mesh):
    return {'handle': handle(n), 'name': str(n.name), 'snapshot': ctx.emax.snapshot([n])[0], 'uv': _uv_hash(mesh),
            'stack': [str(_rt().classOf(n.baseObject))] + [str(_rt().classOf(m)) for m in n.modifiers]}


def _core_mesh(mesh):
    return {'verts': mesh['verts'], 'tris': mesh['tris'], 'mat_ids': mesh['mat_ids'], 'uvs': mesh['uvs'],
            'uv_tris': mesh['uv_tris']}


# ---- udim.rescale -----------------------------------------------------------------------------------------------
def _rescale_options(ctx, mode, preview):
    if mode == 'apply':
        return dict(preview['plan']['options'])
    return ctx.core.rescale_options(ctx.options)


def udim_rescale(ctx, mode, nodes, preview):
    rt = _rt()
    edit, core, emax = ctx.edit, ctx.core, ctx.emax
    opts = _rescale_options(ctx, mode, preview)
    k = ctx.host.m_per_unit()
    nodes = target_nodes(nodes)
    work, entries, done, skipped, state = [], [], [], [], []
    for n in nodes:
        if not is_geometry(n):
            skipped.append(edit.skipped(str(n.name), 'not geometry'))
            continue
        mesh = read_tri(n, k)
        if mesh['uvs'] is None:
            entries.append(edit.entry(handle(n), str(n.name), [edit.finding(
                'no_uv', [], 'no UV channel 1: nothing to rescale (unwrap first; the object is not copied)')]))
            state.append(_state(ctx, n, mesh))
            continue
        o = dict(opts)
        if o.get('faces') is None:
            o['faces'] = selected_tris(n, mesh)
        try:
            plan = core.rescale_plan(_core_mesh(mesh), {kk: v for kk, v in o.items() if v is not None})
        except ValueError as exc:
            skipped.append(edit.skipped(str(n.name), str(exc)))
            continue
        work.append((n, mesh, plan))
        state.append(_state(ctx, n, mesh))
        entries.append(edit.entry(handle(n), str(n.name)))
        done.append({'object': str(n.name), 'scale': round(plan['scale'], 9),
                     'before_px_per_m': round(plan['before_px_per_m'], 4),
                     'after_px_per_m': round(plan['after_px_per_m'], 4), 'faces_scope': plan['faces_scope'],
                     'faces_scaled': plan['faces_scaled'], 'elements': plan['elements'],
                     'scope': 'options.faces' if opts.get('faces') else ('selection' if o['faces'] else 'object'),
                     'notes': plan['notes'], 'unit_m': k})
    if not entries:
        raise ValueError('nothing to rescale: ' + '; '.join(s['item'] + ': ' + s['reason'] for s in skipped))
    extra = {'options': opts, 'layer': LAYER, 'issue': ISSUE}
    if mode == 'preview':
        return edit.report(TOOL_RESCALE, 'preview', entries, done, skipped, (), state_hash=edit.fingerprint(state),
                           extra=extra)
    edit.require_current(preview, state)
    if edit.fingerprint(preview['plan']['done']) != edit.fingerprint(done):
        raise edit.StalePreview('the rescale differs from the preview; run preview again')
    if not work:
        raise ValueError('nothing to rescale: no object has UV channel 1 (see the preview findings)')
    copies, objects, applied = [], [], []

    def body():
        try:
            pairs = emax.export_copies([n for n, _, _ in work], layer=LAYER)
            copies.extend(c for _, c in pairs)
            for (n, c), (_, mesh, plan), row in zip(pairs, work, done):
                rt.convertToMesh(c)
                got = read_tri(c, k)
                if got['tris'] != mesh['tris'] or got['uv_tris'] != mesh['uv_tris']:
                    raise RuntimeError('export copy topology differs from the previewed mesh: ' + str(c.name))
                for i, (u, v) in enumerate(plan['uvs'], 1):
                    rt.meshop.setMapVert(c, 1, i, rt.point3(float(u), float(v), 0.0))
                rt.update(c)
                back = read_tri(c, k)
                after = core.density(_core_mesh(back), [f - 1 for f in (plan['options']['faces'] or
                                                                          range(1, len(back['tris']) + 1))],
                                     plan['options']['tile_px'])
                findings = []
                if abs(after / plan['options']['target_px_per_m'] - 1) > core.SCALE_TOL:
                    findings.append(edit.finding('texel', [], 'readback {:.3f} px/m'.format(after)))
                objects.append(edit.entry(handle(c), str(c.name), findings))
                applied.append(dict(row, copy=str(c.name), readback_px_per_m=round(after, 4)))
            now = [_state(ctx, n, read_tri(n, k)) for n, _, _ in work]
            if edit.fingerprint(now) != edit.fingerprint(state):
                raise RuntimeError('working objects changed during apply')
        except Exception:
            alive = [c for c in copies if rt.isValidNode(c)]
            if alive:
                rt.delete(alive)
            raise
    _session_core().in_session(emax, TOOL_RESCALE, body)
    return edit.report(TOOL_RESCALE, 'apply', objects, applied, skipped, (),
                       extra=dict(extra, copies=[str(c.name) for c in copies]))


# ---- udim.distortion --------------------------------------------------------------------------------------------
def udim_distortion(ctx, mode, nodes, preview):
    edit, core = ctx.edit, ctx.core
    if mode != 'preview':
        raise ValueError(TOOL_DIST + ' is read-only: there is no apply')
    opts = core.distortion_options(ctx.options)
    k = ctx.host.m_per_unit()
    nodes = target_nodes(nodes)
    entries, done, skipped, state = [], [], [], []
    for n in nodes:
        if not is_geometry(n):
            skipped.append(edit.skipped(str(n.name), 'not geometry'))
            continue
        mesh = read_tri(n, k)
        state.append(_state(ctx, n, mesh))
        if mesh['uvs'] is None:
            entries.append(edit.entry(handle(n), str(n.name), [edit.finding('no_uv', [], 'no UV channel 1')]))
            continue
        res = core.distortion_rows(_core_mesh(mesh), {kk: v for kk, v in opts.items() if v is not None},
                                   mesh['poly_groups'])
        findings = [edit.finding(code, faces, '{} {} ({}, target {:.3f} px/m from {})'.format(
            len(faces), code, 'polygons' if mesh['kind'] == 'poly' else 'triangles', res['target_px_per_m'],
            res['target_source'])) for code, faces in sorted(res['bad'].items())]
        entries.append(edit.entry(handle(n), str(n.name), findings))
        texels = [r['px_per_m'] for r in res['rows'] if r['px_per_m'] is not None]
        done.append({'object': str(n.name), 'faces': len(res['rows']), 'unit': mesh['kind'],
                     'target_px_per_m': res['target_px_per_m'], 'target_source': res['target_source'],
                     'px_per_m_min': min(texels) if texels else None, 'px_per_m_max': max(texels) if texels else None,
                     'aniso_max': max(r['aniso'] for r in res['rows']),
                     'bad': {c: len(v) for c, v in sorted(res['bad'].items())}, 'unit_m': k})
    if not entries:
        raise ValueError('nothing to check: ' + '; '.join(s['item'] + ': ' + s['reason'] for s in skipped))
    return edit.report(TOOL_DIST, 'preview', entries, done, skipped, (), state_hash=edit.fingerprint(state),
                       extra={'options': opts, 'issue': ISSUE})
