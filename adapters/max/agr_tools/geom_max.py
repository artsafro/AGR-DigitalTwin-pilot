"""new-case: AGR Tools 0.8 (#908) geom, 3ds Max side. Owned by branch A (improve/issue-908-geom).

runtime.edits_080 calls `<function>(ctx, mode, nodes, preview)` for `model_triangulate` (model.triangulate),
`ucx_triangulate` (ucx.triangulate), `export_pivot_place` (export.pivot_place).
ctx: agr (runtime globals), core (geom_core), edit (edit_core), emax (edit_max), options (dict of the preview).
Import pymxs inside functions so this file loads under plain pytest.

All three work on export copies only (edit_max.export_copies, layer AGR_export): the working nodes keep their
geometry, transform, pivot and hidden state. One undo record per apply, selection restored, the report lists
done / skipped (with reason) / ambiguous. Diagonals are computed in geom_core.py and applied with
polyop.createEdge in one MAXScript loop (no Modify panel, no DLL, no dialog).
"""
import math
import os

EXPORT_LAYER = 'AGR_export'
DRIFT_TOL_M = 1e-4  # L07 acceptance: world vertices do not move (<= 1e-4 m)
SUFFIX = {'model.triangulate': '_AGR_tri_', 'ucx.triangulate': '_AGR_tri_',
          'npm': '_AGR_NPM_', 'vpm': '_AGR_VPM_'}

_MXS = r'''
global agr908_polyData, agr908_connect, agr908_degrees, agr908_hidden, agr908_setHidden, agr908_floorZ
global agr908_setMesh
fn agr908_g v = formattedPrint v format:".17g"
fn agr908_polyData obj = (
    local ss = stringStream ""
    local nv = polyop.getNumVerts obj
    local nf = polyop.getNumFaces obj
    format "% %\n" nv nf to:ss
    for i = 1 to nv do (
        local p = polyop.getVert obj i
        format "% % %\n" (agr908_g p.x) (agr908_g p.y) (agr908_g p.z) to:ss
    )
    for f = 1 to nf do (
        for v in (polyop.getFaceVerts obj f) do format "% " v to:ss
        format "\n" to:ss
    )
    ss as string
)
fn agr908_connect obj pairs = (
    local bad = #()
    for k = 1 to pairs.count by 2 do (
        local e = polyop.createEdge obj pairs[k] pairs[k + 1]
        if e == undefined or e == 0 do append bad ((k + 1) / 2)
    )
    bad
)
fn agr908_degrees obj = for f = 1 to (polyop.getNumFaces obj) collect (polyop.getFaceDeg obj f)
fn agr908_hidden obj = #((polyop.getHiddenVerts obj) as array, (polyop.getHiddenFaces obj) as array)
fn agr908_setHidden obj verts faces = (
    polyop.setHiddenVerts obj (verts as bitarray)
    polyop.setHiddenFaces obj (faces as bitarray)
    ok
)
fn agr908_floorZ n level = (
    -- world z of the floor sub-selection: #(source, count, z values as text)
    local b = n.baseObject
    local verts = #{}
    local src = "none"
    local isPoly = classOf b == Editable_Poly
    local fsel = if isPoly then polyop.getFaceSelection b else getFaceSelection b
    local vsel = if isPoly then polyop.getVertSelection b else getVertSelection b
    local esel = if isPoly then polyop.getEdgeSelection b else getEdgeSelection b
    local useFaces = (level == 4 or level == 5) or (level == 0 and not fsel.isEmpty)
    local useEdges = (level == 2 or level == 3)
    local useVerts = (level == 1) or (level == 0 and fsel.isEmpty)
    if useFaces and not fsel.isEmpty do (
        verts = if isPoly then polyop.getVertsUsingFace b fsel else meshop.getVertsUsingFace b fsel
        src = "faces")
    if useEdges and not esel.isEmpty do (
        verts = if isPoly then polyop.getVertsUsingEdge b esel else meshop.getVertsUsingEdge b esel
        src = "edges")
    if useVerts and not vsel.isEmpty do (verts = vsel; src = "verts")
    local zs = for v in verts collect (
        local p = if isPoly then (in coordsys world polyop.getVert n v) else (in coordsys world getVert n v)
        agr908_g p.z)
    #(src, (verts as array), zs)
)
global agr979_frame, agr979_setFrame
fn agr979_rows ss m = (
    for r in #(m.row1, m.row2, m.row3, m.row4) do format "% % %\n" (agr908_g r.x) (agr908_g r.y) (agr908_g r.z) to:ss
)
fn agr979_frame n = (
    -- node transform rows, objectOffset rows (scale * rot, pos), object-space vertices of the evaluated object
    local ss = stringStream ""
    agr979_rows ss n.transform
    agr979_rows ss ((scaleMatrix n.objectOffsetScale) * (n.objectOffsetRot as matrix3) * (transMatrix n.objectOffsetPos))
    local m = n.mesh
    local nv = m.numverts
    format "%\n" nv to:ss
    for i = 1 to nv do (
        -- 9 significant digits restore a float32 exactly (shorter text than .17g, faster on 5000+ vertices)
        local p = getVert m i
        format "% % %\n" (formattedPrint p.x format:".9g") (formattedPrint p.y format:".9g") \
            (formattedPrint p.z format:".9g") to:ss
    )
    ss as string
)
fn agr979_setFrame n r1 r2 r3 p o1 o2 o3 opos osc = (
    -- turn/move the pivot of n; objectOffset computed in double by geom_core.new_offset keeps the mesh in place
    local kids = for k in n.children collect #(k, k.transform)
    with animate off (
        n.transform = matrix3 r1 r2 r3 p
        n.objectOffsetPos = opos
        n.objectOffsetRot = (matrix3 o1 o2 o3 [0,0,0]).rotationPart
        n.objectOffsetScale = osc
    )
    for k in kids do k[1].transform = k[2]
    ok
)
fn agr908_setMesh n verts faces = (
    -- convex hull fallback of ucx.triangulate on the COPY: object-space vertices, 1-based triangles
    convertToMesh n
    setMesh n vertices:verts faces:faces
    for f = 1 to n.numfaces do (setEdgeVis n f 1 true; setEdgeVis n f 2 true; setEdgeVis n f 3 true)
    update n
    convertTo n Editable_Poly
    ok
)
'''


def _rt():
    from pymxs import runtime
    return runtime


def _mxs():
    rt = _rt()
    rt.execute(_MXS)
    return rt


def _handle(n):
    return int(_rt().getHandleByAnim(n))


def _class(n):
    return str(_rt().classOf(n.baseObject))


def _targets(nodes):
    rt = _rt()
    if nodes is None:
        nodes = list(rt.selection)
        if not nodes:
            raise ValueError('nothing selected: select the objects for the export copy')
    nodes = list(nodes)
    seen, out = set(), []
    for n in nodes:
        if not rt.isValidNode(n):
            raise ValueError('invalid node')
        h = _handle(n)
        if h not in seen:
            seen.add(h)
            out.append(n)
    return sorted(out, key=_handle)


def _from_preview(preview):
    rt = _rt()
    nodes = []
    for h in preview['plan']['handles']:
        n = rt.getAnimByHandle(int(h))  # anim handles, as edit_max.handle / snapshot use
        if n is None or not rt.isValidNode(n):
            raise ValueError('a node of the preview is gone; run preview again')
        nodes.append(n)
    return nodes


def poly_data(obj):
    """(points [(x, y, z)], polygons [[0-based vertex ids]]) of an Editable Poly base object (object space)."""
    rt = _mxs()
    text = str(rt.agr908_polyData(obj))
    lines = text.splitlines()
    nv, nf = (int(x) for x in lines[0].split())
    points = [tuple(float(c) for c in lines[1 + i].split()) for i in range(nv)]
    polys = [[int(v) - 1 for v in lines[1 + nv + f].split()] for f in range(nf)]
    return points, polys


def _plain_poly(n):
    return _class(n) == 'Editable_Poly' and len(n.modifiers) == 0


def _read_polys(n):
    """Poly data of a node without changing the scene: plain polys directly, others via a throwaway copy."""
    import pymxs
    rt = _rt()
    if _plain_poly(n):
        return poly_data(n.baseObject)
    with pymxs.undo(False):
        tmp = rt.copy(n)
        try:
            rt.convertTo(tmp, rt.Editable_Poly)
            return poly_data(tmp.baseObject)
        finally:
            rt.delete(tmp)


def _faces(points, polys):
    return [{'face': i + 1, 'verts': [v + 1 for v in p], 'points': [points[v] for v in p]}
            for i, p in enumerate(polys)]


def _redraw_off():
    import contextlib

    @contextlib.contextmanager
    def ctx():
        rt = _rt()
        rt.disableSceneRedraw()
        try:
            yield
        finally:
            rt.enableSceneRedraw()
    return ctx()


def _hidden(obj):
    rt = _mxs()
    hv, hf = rt.agr908_hidden(obj)
    return [int(v) for v in hv], [int(f) for f in hf]


def _restore_hidden(obj, hidden_verts, hidden_polys_verts):
    """Hidden state after splitting: vertex ids are stable; a new triangle is hidden when it lies inside a
    polygon that was hidden (the source unhid everything, lab defect 3)."""
    rt = _mxs()
    if not hidden_verts and not hidden_polys_verts:
        return 0
    points, polys = poly_data(obj)
    hidden_sets = [set(s) for s in hidden_polys_verts]
    faces = [i + 1 for i, p in enumerate(polys) if any(set(v + 1 for v in p) <= s for s in hidden_sets)]
    rt.agr908_setHidden(obj, hidden_verts, faces)
    return len(faces)


def _connect(obj, rows):
    rt = _mxs()
    flat = [v for r in rows for pr in r['pairs'] for v in pr]
    if not flat:
        return []
    return [int(b) for b in rt.agr908_connect(obj, flat)]


def _degrees(obj):
    return [int(d) for d in _mxs().agr908_degrees(obj)]


def _state(emax, nodes, extra=None):
    return {'nodes': emax.snapshot(nodes), 'extra': extra or {}}


# ---- model.triangulate --------------------------------------------------------------------------------
def _triangulate_copy(core, c):
    """Triangulate every n-gon of one copy. Returns counts, leftovers and failed pairs (read back)."""
    rt = _rt()
    obj = c.baseObject
    hv, hf = _hidden(obj)
    points, polys = poly_data(obj)
    hidden_polys = [[v + 1 for v in polys[f - 1]] for f in hf]
    rows, degenerate = core.plan_faces(_faces(points, polys))
    with _redraw_off():
        failed = _connect(obj, rows)
    hidden_after = _restore_hidden(obj, hv, hidden_polys) if (hv or hf) else 0
    degrees = _degrees(obj)
    after_points = int(rt.polyop.getNumVerts(obj))
    return {'ngons': len(rows), 'diagonals': sum(len(r['pairs']) for r in rows), 'failed': failed,
            'leftovers': core.assert_triangulated(degrees), 'degenerate': degenerate,
            'verts_before': len(points), 'verts_after': after_points, 'faces_after': len(degrees),
            'hidden_faces_before': len(hf), 'hidden_faces_after': hidden_after}


def _preview_rows(ctx, nodes, kind):
    core, edit = ctx.core, ctx.edit
    rt = _rt()
    rows, skipped, ambiguous = [], [], []
    for n in nodes:
        name = str(n.name)
        if kind == 'ucx' and not core.is_ucx_name(name):
            skipped.append(edit.skipped(name, 'not a UCX_ piece (name)'))
            continue
        how, why = core.classify(_class(n), len(n.modifiers), bool(rt.canConvertTo(n, rt.Editable_Poly)))
        if how == 'skip':
            skipped.append(edit.skipped(name, why))
            continue
        points, polys = _read_polys(n)
        row = {'handle': _handle(n), 'name': name, 'convert': why}
        if kind == 'tri':
            plan, degenerate = core.plan_faces(_faces(points, polys))
            row.update(ngons=len(plan), diagonals=sum(len(r['pairs']) for r in plan))
            if degenerate:
                ambiguous.append('{}: degenerate outline (collinear/self-intersecting) faces {}; triangulated, '
                                 'check'.format(name, degenerate[:20]))
        else:
            plan = core.ucx_plan(points, polys, _ucx_tol(n), _ucx_options(ctx)['nonconvex'])
            row.update(action=plan['action'], diagonals=len(plan['pairs']), reason=plan['reason'],
                       flips=len(plan['flips']), refused=plan['refused'], convex=plan['convex'])
            if not plan['convex'] and plan['action'] != 'hull':
                ambiguous.append('{}: {}'.format(name, plan['reason']))
        rows.append(row)
    return rows, skipped, ambiguous


def _ucx_options(ctx):
    opts = dict(ctx.options or {})
    unknown = set(opts) - ctx.core.UCX_OPTIONS
    if unknown:
        raise ValueError('unknown ucx.triangulate options: ' + ', '.join(sorted(unknown)))
    out = {'nonconvex': opts.get('nonconvex', 'report')}
    if out['nonconvex'] not in ctx.core.NONCONVEX:
        raise ValueError('options.nonconvex must be report or hull')
    return out


def _ucx_findings(edit, row):
    """Preview findings of one UCX piece: reflex diagonals the apply turns, and what stays not convex."""
    out = []
    if row.get('flips'):
        out.append(edit.finding('reflex_edge', (), '{} reflex diagonal(s); apply turns them on the copy'.format(
            row['flips'])))
    if row.get('convex') is False:
        edges = ['{}-{} ({})'.format(r['edge'][0] + 1, r['edge'][1] + 1, r['reason']) for r in row['refused'][:20]]
        what = 'apply rebuilds the convex hull' if row['action'] == 'hull' else 'left as is'
        out.append(edit.finding('not_convex', (), what + ': ' + ('; '.join(edges) or row['reason'])))
    return out


def _done_text(row, kind):
    conv = ' ({})'.format(row['convert']) if row['convert'] else ''
    if kind == 'tri':
        return '{}: {} n-gons, {} diagonals on the copy{}'.format(row['name'], row['ngons'], row['diagonals'], conv)
    if row['action'] == 'hull':
        return '{}: convex hull on the copy ({}){}'.format(row['name'], row['reason'], conv)
    turns = ', {} reflex diagonal(s) turned'.format(row['flips']) if row.get('flips') else ''
    return '{}: {} diagonals, convexity-aware{}, on the copy{}'.format(row['name'], row['diagonals'], turns, conv)


def _tool_preview(ctx, tool, kind, nodes):
    edit, emax = ctx.edit, ctx.emax
    nodes = _targets(nodes)
    rows, skipped, ambiguous = _preview_rows(ctx, nodes, kind)
    work = [n for n in nodes if _handle(n) in {r['handle'] for r in rows}]
    state = _state(emax, work)
    objects = [edit.entry(r['handle'], r['name'], _ucx_findings(edit, r) if kind == 'ucx' else ())
               for r in rows]
    extra = {'handles': [r['handle'] for r in rows], 'rows': rows, 'layer': EXPORT_LAYER}
    if kind == 'ucx':
        extra['options'] = _ucx_options(ctx)
    return edit.report(tool, 'preview', objects=objects, done=[_done_text(r, kind) for r in rows],
                       skipped_=skipped, ambiguous=ambiguous, state_hash=edit.fingerprint(state), extra=extra)


def model_triangulate(ctx, mode, nodes, preview):
    """Triangulate every n-gon of the export copies (Delaunay-style, scale-free, n-3 diagonals per face)."""
    tool = 'model.triangulate'
    if mode == 'preview':
        return _tool_preview(ctx, tool, 'tri', nodes)
    edit, emax, core = ctx.edit, ctx.emax, ctx.core
    nodes = _from_preview(preview)
    edit.require_current(preview, _state(emax, nodes))
    rt = _rt()
    objects, done, ambiguous, copies = [], [], list(preview['plan']['ambiguous']), []
    with emax.session(tool):
        pairs = emax.export_copies(nodes, suffix=SUFFIX[tool], layer=EXPORT_LAYER)
        for (n, c), row in zip(pairs, preview['plan']['rows']):
            if not _plain_poly(c):
                rt.convertTo(c, rt.Editable_Poly)
            got = _triangulate_copy(core, c)
            findings = []
            if got['leftovers']:
                findings.append(edit.finding('ngon_left', got['leftovers'][:1000],
                                             '{} faces still have more than 3 corners'.format(len(got['leftovers']))))
            if got['verts_after'] != got['verts_before']:
                findings.append(edit.finding('vertex_count', (), '{} -> {}'.format(got['verts_before'],
                                                                                   got['verts_after'])))
            if got['diagonals'] != row['diagonals']:
                findings.append(edit.finding('plan_changed', (), 'preview {} diagonals, apply {}'.format(
                    row['diagonals'], got['diagonals'])))
            objects.append(edit.entry(_handle(c), str(c.name), findings))
            done.append('{} -> {}: {} n-gons, {} diagonals, 0 n-gons left'.format(
                row['name'], str(c.name), got['ngons'], got['diagonals']) if not findings else
                '{} -> {}: see findings'.format(row['name'], str(c.name)))
            copies.append(dict(got, source=row['name'], copy=str(c.name), handle=_handle(c)))
    return edit.report(tool, 'apply', objects=objects, done=done, skipped_=preview['plan']['skipped'],
                       ambiguous=ambiguous, extra={'copies': copies, 'layer': EXPORT_LAYER})


# ---- ucx.triangulate ----------------------------------------------------------------------------------
def _sys_per_m():
    return float(_rt().units.decodeValue('1m'))


def _ucx_tol(n):
    """1e-4 m in the node's object space (system units over the largest scale)."""
    s = n.objectTransform
    scale = max(math.sqrt(r.x * r.x + r.y * r.y + r.z * r.z) for r in (s.row1, s.row2, s.row3)) or 1.0
    return 1e-4 * _sys_per_m() / scale


def _set_triangles(c, points, tris):
    """Write the planned triangle list on the copy (object-space vertices unchanged, 1-based faces)."""
    rt = _mxs()
    verts = [rt.Point3(*p) for p in points]
    faces = [rt.Point3(*(i + 1 for i in t)) for t in tris]
    rt.agr908_setMesh(c, verts, faces)


def _apply_ucx_copy(ctx, c, nonconvex='report'):
    core = ctx.core
    rt = _mxs()
    obj = c.baseObject
    tol = _ucx_tol(c)
    hv, hf = _hidden(obj)
    points, polys = poly_data(obj)
    hidden_polys = [[v + 1 for v in polys[f - 1]] for f in hf]
    plan = core.ucx_plan(points, polys, tol, nonconvex)
    failed, rebuilt = [], False
    if plan['action'] == 'diagonals':
        with _redraw_off():
            failed = _connect(obj, [{'pairs': [[a + 1, b + 1] for a, b in plan['pairs']]}])
        if failed or core.assert_triangulated(_degrees(obj)):
            # T03/ConcaveFixer: a refused createEdge left quads (85 on a noisy grid) and still said «Fixed».
            # Here every created edge is checked; any miss writes the planned triangles instead.
            _set_triangles(c, points, plan['tris'])
            obj, rebuilt = c.baseObject, True
        _restore_hidden(obj, hv, hidden_polys)
    elif plan['action'] == 'mesh':
        _set_triangles(c, points, plan['tris'])
        obj = c.baseObject
        _restore_hidden(obj, hv, hidden_polys)
    elif plan['action'] == 'hull':
        verts = [rt.Point3(*v) for v in plan['hull']['verts']]
        faces = [rt.Point3(*(i + 1 for i in t)) for t in plan['hull']['tris']]
        rt.agr908_setMesh(c, verts, faces)
        obj = c.baseObject
    points2, polys2 = poly_data(obj)
    degrees = [len(p) for p in polys2]
    left = core.assert_triangulated(degrees)
    tris = [tuple(p) for p in polys2 if len(p) == 3]
    check = core._ucx_core().convexity(points2, tris, tol) if tris and not left else None
    hv2, hf2 = _hidden(obj)
    return {'action': plan['action'], 'diagonals': len(plan['pairs']), 'failed': failed, 'rebuilt': rebuilt,
            'flips': len(plan['flips']), 'refused': plan['refused'], 'convex_plan': plan['convex'],
            'leftovers': left, 'check': check, 'verts_before': len(points), 'verts_after': len(points2),
            'hidden_faces_before': len(hf), 'hidden_faces_after': len(hf2), 'hidden_verts': len(hv2)}


def ucx_triangulate(ctx, mode, nodes, preview):
    """Triangulate UCX copies with convexity-aware diagonals (or the convex hull), then post-check 2.13.1."""
    tool = 'ucx.triangulate'
    if mode == 'preview':
        return _tool_preview(ctx, tool, 'ucx', nodes)
    edit, emax = ctx.edit, ctx.emax
    nodes = _from_preview(preview)
    edit.require_current(preview, _state(emax, nodes))
    rt = _rt()
    objects, done, copies = [], [], []
    with emax.session(tool):
        pairs = emax.export_copies(nodes, suffix=SUFFIX[tool], layer=EXPORT_LAYER)
        for (n, c), row in zip(pairs, preview['plan']['rows']):
            if not _plain_poly(c):
                rt.convertTo(c, rt.Editable_Poly)
            got = _apply_ucx_copy(ctx, c, (preview['plan'].get('options') or {}).get('nonconvex', 'report'))
            findings = []
            if got['leftovers']:
                findings.append(edit.finding('ngon_left', got['leftovers'][:1000], 'faces with more than 3 corners'))
            chk = got['check']
            if chk is not None:
                if not chk['convex']:
                    findings.append(edit.finding('not_convex', [t + 1 for t in chk['outside']][:1000],
                                                 'worst {:.6f} beyond a face plane'.format(chk['worst'])))
                if not chk['closed']:
                    findings.append(edit.finding('not_closed', (), '{} open edges'.format(chk['open_edges'])))
                if chk['zero_area']:
                    findings.append(edit.finding('zero_area', [t + 1 for t in chk['zero_area']][:1000], ''))
            if got['action'] != 'hull' and got['verts_after'] != got['verts_before']:
                findings.append(edit.finding('vertex_count', (), '{} -> {}'.format(got['verts_before'],
                                                                                   got['verts_after'])))
            objects.append(edit.entry(_handle(c), str(c.name), findings))
            what = 'convex hull' if got['action'] == 'hull' else '{} diagonals, {} turned{}'.format(
                got['diagonals'], got['flips'], ', triangles rewritten after a refused edge' if got['rebuilt'] else '')
            done.append('{} -> {}: {}, convex {}, closed {}'.format(
                row['name'], str(c.name), what, chk and chk['convex'], chk and chk['closed']))
            got['check'] = None if chk is None else {k: chk[k] for k in ('ok', 'convex', 'closed', 'worst',
                                                                           'open_edges', 'volume')}
            copies.append(dict(got, source=row['name'], copy=str(c.name), handle=_handle(c), convert=row['convert']))
    return edit.report(tool, 'apply', objects=objects, done=done, skipped_=preview['plan']['skipped'],
                       ambiguous=preview['plan']['ambiguous'], extra={'copies': copies, 'layer': EXPORT_LAYER})


# ---- export.pivot_place -------------------------------------------------------------------------------
def _level(n):
    """Active sub-object level of `n` when it is the Modify panel object, else 0 (no level known)."""
    rt = _rt()
    try:
        if rt.modPanel.getCurrentObject() == n.baseObject:
            lv = rt.subObjectLevel
            return int(lv) if lv is not None else 0
    except Exception:  # noqa: BLE001 - no Modify panel in batch Max
        pass
    return 0


def _floor_selection(nodes):
    rt = _mxs()
    zs, ids, sources = [], {}, set()
    for n in nodes:
        if len(n.modifiers) or _class(n) not in ('Editable_Poly', 'Editable_mesh'):
            continue
        src, verts, z = rt.agr908_floorZ(n, _level(n))
        if str(src) == 'none' or not list(z):
            continue
        sources.add(str(src))
        ids[str(_handle(n))] = [int(v) for v in verts]
        zs.extend(float(str(v)) for v in z)
    return zs, ids, sorted(sources)


def _ask_floor():
    """Interactive ±0.000 prompt (never in batch/quiet Max or with AGR_NO_PROMPT). None when not asked."""
    rt = _rt()
    if os.environ.get('AGR_NO_PROMPT') or bool(rt.GetQuietMode()):
        return None
    try:
        try:
            from PySide6.QtWidgets import QInputDialog
        except ImportError:
            from PySide2.QtWidgets import QInputDialog
        import qtmax
        text, ok = QInputDialog.getText(qtmax.GetQMaxMainWindow(), 'AGR Tools: ±0.000',
                                        'Нет выделения пола. Отметка чистого пола ±0.000 (абсолютная, м):')
    except Exception:  # noqa: BLE001 - no Qt: refuse below
        return None
    if not ok:
        raise ValueError('±0.000 not given: pivot placement cancelled')
    return text


def _world_bbox(nodes):
    lo = [min(float(getattr(n.min, a)) for n in nodes) for a in 'xyz']
    hi = [max(float(getattr(n.max, a)) for n in nodes) for a in 'xyz']
    return lo, hi


def _rows(tm):
    return [[float(r.x), float(r.y), float(r.z)] for r in (tm.row1, tm.row2, tm.row3, tm.row4)]


def _node_info(core, n):
    tm = _rows(n.transform)
    return {'handle': _handle(n), 'name': str(n.name), 'position': core.fmt_point(tm[3]),
            'pivot': core.fmt_point([float(n.pivot.x), float(n.pivot.y), float(n.pivot.z)]),
            'rotation_ui': [core.fmt(a, 3) for a in core.euler_ui(tm)]}


def read_frame(n):
    """(node rows, offset rows, object-space vertices) of a node, as doubles of the stored float32 values."""
    text = str(_mxs().agr979_frame(n))
    lines = text.splitlines()
    rows = [[float(c) for c in lines[i].split()] for i in range(8)]
    nv = int(lines[8])
    pts = [tuple(float(c) for c in lines[9 + i].split()) for i in range(nv)]
    return rows[:4], rows[4:], pts


def _frame_plan(core, n, orient, at, floor_pivot):
    """Pivot frame of one node: {'rows', 'pivot', 'angle', 'uncertainty', ...} or raise ValueError(reason)."""
    node_rows, off_rows, pts = read_frame(n)
    if not pts:
        raise ValueError('no vertices')
    why = core.check_unit_scale(node_rows)
    if why:
        raise ValueError(why)
    obj_rot = core.mat3_mul([r[:] for r in off_rows[:3]], [r[:] for r in node_rows[:3]])
    info = {'orient': orient, 'pivot_at': at, 'vertices': len(pts)}
    if orient == 'long_side':
        ax = core.axes_long_side(pts, obj_rot)
        info.update(long=ax['long'], short=ax['short'])
    elif orient == 'pca':
        ax = core.axes_pca(pts, obj_rot)
        info.update(principal=ax['principal'])
    else:
        rows = [[float(c) for c in r] for r in node_rows[:3]]
        ax = {'rows': rows, 'angle': core.canonical_angle(math.degrees(math.atan2(rows[0][1], rows[0][0]))),
              'uncertainty': 0.0}
    rows = ax['rows']
    if at == 'floor':
        pivot = [float(v) for v in floor_pivot]
    else:
        lo, hi = core.frame_bounds(pts, obj_rot, rows)
        local = [(lo[0] + hi[0]) / 2.0, (lo[1] + hi[1]) / 2.0, lo[2] if at == 'bottom_centre' else (lo[2] + hi[2]) / 2.0]
        vec = core.frame_point(local, rows)
        po_r = core.vec_mat(off_rows[3], node_rows[:3])
        origin = [po_r[i] + node_rows[3][i] for i in range(3)]  # world of the object-space origin, double
        pivot = [origin[i] + vec[i] for i in range(3)]
    info.update(rows=rows, angle=ax['angle'], uncertainty=ax['uncertainty'], pivot_value=pivot,
                pivot=core.fmt_point(pivot), axes_ui=[core.fmt(a, 4) for a in core.euler_ui(rows)])
    return info


def set_frame(core, c, rows, pivot):
    """Native pivot setters on the copy: node transform + objectOffset recomputed in double (mesh stays)."""
    rt = _mxs()
    node_rows, off_rows, pts = read_frame(c)
    before = core.world_points(pts, off_rows, node_rows)
    pos32 = [core.f32(v) for v in pivot]
    mo, po = core.new_offset(node_rows, off_rows, rows, pos32)
    scale = [math.sqrt(sum(x * x for x in r)) for r in mo]
    rot = [[x / s for x in r] for r, s in zip(mo, scale)]
    P = rt.Point3
    rt.agr979_setFrame(c, P(*rows[0]), P(*rows[1]), P(*rows[2]), P(*pos32), P(*rot[0]), P(*rot[1]), P(*rot[2]),
                       P(*po), P(*scale))
    node2, off2, pts2 = read_frame(c)
    after = core.world_points(pts2, off2, node2)
    drift = max((math.dist(a, b) for a, b in zip(before, after)), default=0.0)
    return {'drift': drift, 'node_rows': node2}


def _pivot_new_path(opts):
    return opts.get('orient', 'keep') != 'keep' or opts.get('pivot_at', 'floor') != 'floor'


def export_pivot_place(ctx, mode, nodes, preview):
    """NPM copy: MSK X/Y/Z kept, pivot at [centre X, centre Y, ±0.000]. VPM copy: that pivot at [0,0,0].

    #979: orient=long_side (X along the long side in plan, Z up; AC Pivot Align idea) or pca (principal axes;
    straighten_object idea); pivot_at=bottom_centre / centre of the object's oriented box (door pivot idea). The
    mesh never moves: the node frame is set natively and objectOffset is recomputed in double."""
    tool = 'export.pivot_place'
    edit, emax, core = ctx.edit, ctx.emax, ctx.core
    rt = _rt()
    if mode == 'preview':
        opts = core.check_options(ctx.options)
        nodes = _targets(nodes)
        geo = [n for n in nodes if rt.canConvertTo(n, rt.TriMeshGeometry)]
        skipped = [edit.skipped(str(n.name), 'not geometry') for n in nodes if n not in geo]
        if not geo:
            raise ValueError('no geometry selected')
        orient, at = opts.get('orient', 'keep'), opts.get('pivot_at', 'floor')
        floor, pivot, lo, hi, ids = None, None, None, None, {}
        if at == 'floor':
            zs, ids, sources = _floor_selection(geo)
            explicit, source = opts.get('floor_z'), None
            if explicit is None and not zs:
                asked = _ask_floor()
                if asked is not None:
                    explicit, source = core.parse_level(asked), 'prompt'
            floor_z, how = core.floor_level(zs, explicit)
            source = source or (how if how == 'explicit' else 'selection:' + '+'.join(sources))
            lo, hi = _world_bbox(geo)
            pivot = core.pivot_point(lo, hi, floor_z)
            floor = {'z': core.fmt(floor_z), 'value': floor_z, 'source': source, 'count': len(zs)}
        frames, kept, refused = {}, [], []
        if _pivot_new_path(opts):
            for n in geo:
                try:
                    frames[str(_handle(n))] = _frame_plan(core, n, orient, at, pivot)
                    kept.append(n)
                except ValueError as exc:
                    skipped.append(edit.skipped(str(n.name), str(exc)))
                    refused.append(edit.entry(_handle(n), str(n.name),
                                              [edit.finding(core.refusal_code(exc), (), str(exc))]))
            if not kept:
                raise ValueError('no object can take the pivot: ' + '; '.join(
                    s['item'] + ': ' + s['reason'] for s in skipped))
            geo = kept
        state = _state(emax, geo, {'floor_ids': ids})
        info = [_node_info(core, n) for n in geo]
        targets = core.pivot_targets(opts['target'])
        done = []
        for i in info:
            fr = frames.get(str(i['handle']))
            if fr:
                done.append('{}: X at {}° in plan (±{:.6f}°), axes UI [{}], pivot [{}]'.format(
                    i['name'], core.fmt(fr['angle'], 4), fr['uncertainty'], ', '.join(fr['axes_ui']),
                    ', '.join(fr['pivot'])))
        for t in targets:
            if t == 'npm':
                done.append('NPM copies: MSK X/Y/Z kept, pivot -> [{}]'.format(
                    ', '.join(core.fmt_point(pivot)) if pivot else at + ' of each object'))
            else:
                done.append('VPM copies: pivot [{}] -> [0.0000, 0.0000, 0.0000], rotate Z {} deg'.format(
                    ', '.join(core.fmt_point(pivot)) if pivot else at + ' of each object',
                    core.fmt(opts['vpm_rotate_z'], 3)))
        extra = {'handles': [i['handle'] for i in info], 'nodes': info, 'targets': targets, 'floor': floor,
                 'pivot': core.fmt_point(pivot) if pivot else None, 'pivot_value': pivot,
                 'vpm_rotate_z': opts['vpm_rotate_z'], 'layer': EXPORT_LAYER,
                 'bbox': {'min': core.fmt_point(lo), 'max': core.fmt_point(hi)} if lo else None}
        if _pivot_new_path(opts):
            extra.update(orient=orient, pivot_at=at, frames=frames)
        return edit.report(tool, 'preview', objects=[edit.entry(i['handle'], i['name']) for i in info] + refused,
                           done=done, skipped_=skipped, state_hash=edit.fingerprint(state), extra=extra)
    plan = preview['plan']
    nodes = _from_preview(preview)
    edit.require_current(preview, _state(emax, nodes, {'floor_ids': _floor_selection(nodes)[1]
                                                       if plan.get('floor') else {}}))
    frames = plan.get('frames')
    pivot = [float(v) for v in plan['pivot_value']] if plan.get('pivot_value') else None
    p3 = rt.Point3(*pivot) if pivot else None
    objects, done, copies = [], [], []
    with emax.session(tool):
        for t in plan['targets']:
            pairs = emax.export_copies(nodes, suffix=SUFFIX[t], layer=EXPORT_LAYER)
            for n, c in pairs:
                findings = []
                if frames:
                    fr = frames[str(_handle(n))]
                    moved = set_frame(core, c, fr['rows'], fr['pivot_value'])
                    if moved['drift'] > DRIFT_TOL_M * _sys_per_m():
                        findings.append(edit.finding('mesh_moved', (), 'world vertices moved by {:.6g}'.format(
                            moved['drift'])))
                else:
                    c.pivot = p3
                if t == 'vpm':
                    c.pos = rt.Point3(0, 0, 0)
                    if plan['vpm_rotate_z']:
                        rt.rotate(c, rt.EulerAngles(0, 0, float(plan['vpm_rotate_z'])))
                got = _node_info(core, c)
                got.update(source=str(n.name), target=t)
                if frames:
                    got.update(drift=moved['drift'], angle=frames[str(_handle(n))]['angle'])
                copies.append(got)
                objects.append(edit.entry(_handle(c), str(c.name), findings))
                done.append('{} -> {} ({}): pivot [{}], rotation UI [{}]'.format(
                    str(n.name), str(c.name), t.upper(), ', '.join(got['pivot']), ', '.join(got['rotation_ui'])))
    extra = {'copies': copies, 'floor': plan['floor'], 'pivot': plan['pivot'], 'layer': EXPORT_LAYER}
    if frames:
        extra.update(orient=plan['orient'], pivot_at=plan['pivot_at'])
    return edit.report(tool, 'apply', objects=objects, done=done, skipped_=plan['skipped'],
                       ambiguous=plan['ambiguous'], extra=extra)
