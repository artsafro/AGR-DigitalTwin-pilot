"""new-case: AGR Tools 0.9 (#979) UV tiles (MatID -> UDIM, UDIM tiles and slots), 3ds Max side (branch B).

runtime.edits_090 calls `udim_matid_unwrap(ctx, mode, nodes, preview)` and `udim_slots(ctx, mode, nodes, preview)`;
ctx: agr (runtime globals), core (uvtile_core), edit (edit_core), emax (edit_max), options (dict of the preview).
Shared Max helpers come from texqa_max.py (branch B). pymxs is imported inside functions.

udim.slots (read): the map file names of the selected objects' materials are judged by uvtile_core.slots_plan
(names_core grammar). Nothing is changed.

udim.matid_unwrap (copy): preview reads the evaluated mesh of every object (Editable_Poly without modifiers: its
polygons; anything else: the evaluated TriMesh, so a primitive + Bend is read as Max shows it) and plans the
unwrap; nothing changes. apply re-reads and compares (edit_core.require_current), then in ONE undo record makes
export copies on layer `AGR_export_udim`, collapses the stack of a COPY only where the source is not a plain
Editable_Poly/Mesh (named in the report), writes channel 1 on the copy, reads it back (tiles, px/m, overlaps) and
checks that the working objects are bit-identical (classes, modifier stack, mesh, MatIDs, channel 1).
The Modify panel and the current modifier are never touched (L06 defect 5).
Options: px_per_m (default: the largest common density that fits every ID), map_px 1024, pad_px 8, angle 10.
"""
TOOL_UNWRAP = 'udim.matid_unwrap'
TOOL_SLOTS = 'udim.slots'
LAYER = 'AGR_export_udim'
UNWRAP_KEYS = {'px_per_m', 'map_px', 'pad_px', 'angle'}


def _rt():
    from pymxs import runtime
    return runtime


def _helpers(ctx):
    return ctx.agr._load_core('texqa_max.py', 'agr_tools_texqa_max')


def _session_core():
    """Shared helpers (session_core.py next to this file), loaded by path like the other sibling cores."""
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('agr_tools_session_core', Path(__file__).with_name('session_core.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_in_session = _session_core().in_session


# ---- udim.slots ---------------------------------------------------------------------------------------------
def udim_slots(ctx, mode, nodes, preview):
    edit, core = ctx.edit, ctx.core
    if mode != 'preview':
        raise ValueError(TOOL_SLOTS + ' is read-only: there is no apply')
    if ctx.options:
        raise ValueError('udim.slots takes no options')
    h = _helpers(ctx)
    rt = _rt()
    nodes = h.target_nodes(nodes)
    objects, skipped, state = [], [], []
    for n in nodes:
        paths = []
        for _mid, mat in h.sub_materials(n):
            paths.extend(m['path'] for m in h.material_maps(mat) if m['path'])
        paths = sorted(set(paths))
        if not paths:
            skipped.append(edit.skipped(str(n.name), 'no map file in the material'))
        objects.append({'key': h.handle(n), 'name': str(n.name), 'files': paths})
        state.append({'handle': h.handle(n), 'name': str(n.name), 'files': paths,
                      'geometry': bool(rt.superClassOf(n) == rt.GeometryClass)})
    plan = core.slots_plan(objects)
    entries = [edit.entry(k, name, [edit.finding(c, (), d) for c, d in f]) for k, name, f in plan['entries']]
    return edit.report(TOOL_SLOTS, 'preview', entries, plan['groups'], skipped, (),
                       state_hash=edit.fingerprint(state), extra={'files': plan['files'], 'issue': '#979'})


# ---- udim.matid_unwrap ----------------------------------------------------------------------------------
def _unwrap_options(ctx, mode, preview):
    if mode == 'apply':
        return dict(preview['plan']['options'])
    opts = dict(ctx.options or {})
    unknown = set(opts) - UNWRAP_KEYS
    if unknown:
        raise ValueError('unknown udim.matid_unwrap options: ' + ', '.join(sorted(unknown)))
    out = {'px_per_m': opts.get('px_per_m'), 'map_px': opts.get('map_px', ctx.core.DEFAULT_MAP_PX),
           'pad_px': opts.get('pad_px', ctx.core.PAD_MIN_PX), 'angle': opts.get('angle', ctx.core.DEFAULT_ANGLE)}
    if out['px_per_m'] is not None and (isinstance(out['px_per_m'], bool) or
                                        not isinstance(out['px_per_m'], (int, float)) or out['px_per_m'] <= 0):
        raise ValueError('options.px_per_m must be a positive number: ' + repr(out['px_per_m']))
    for k in ('map_px', 'pad_px'):
        if type(out[k]) is not int:
            raise ValueError('options.{} must be an integer: {!r}'.format(k, out[k]))
    if out['pad_px'] < ctx.core.PAD_MIN_PX:
        raise ValueError('options.pad_px must be >= {} px'.format(ctx.core.PAD_MIN_PX))
    if isinstance(out['angle'], bool) or not isinstance(out['angle'], (int, float)):
        raise ValueError('options.angle must be a number')
    out['angle'] = float(out['angle'])
    if out['px_per_m'] is not None:
        out['px_per_m'] = float(out['px_per_m'])
    return out


def _plain(n):
    rt = _rt()
    kind = rt.classOf(n.baseObject)
    return int(n.modifiers.count) == 0 and kind in (rt.Editable_Poly, rt.Editable_Mesh)


def _stack(n):
    rt = _rt()
    return {'base': str(rt.classOf(n.baseObject)), 'modifiers': [str(rt.classOf(m)) for m in n.modifiers]}


def read_mesh(n):
    """Evaluated mesh in world space: {'vertices', 'faces' (0-based), 'ids', 'kind': 'poly'|'trimesh'}."""
    import math
    rt = _rt()
    if int(n.modifiers.count) == 0 and rt.classOf(n.baseObject) == rt.Editable_Poly:
        nv, nf = int(rt.polyop.getNumVerts(n)), int(rt.polyop.getNumFaces(n))
        verts = []
        for i in range(1, nv + 1):
            p = rt.polyop.getVert(n, i)
            verts.append((float(p.x), float(p.y), float(p.z)))
        faces, ids = [], []
        for i in range(1, nf + 1):
            fv = rt.polyop.getFaceVerts(n, i)
            faces.append([int(fv[k]) - 1 for k in range(int(fv.count))])
            ids.append(int(rt.polyop.getFaceMatID(n, i)))
        kind = 'poly'
    else:
        mesh = rt.snapshotAsMesh(n)
        nv, nf = int(mesh.numverts), int(mesh.numfaces)
        verts = []
        for i in range(1, nv + 1):
            p = rt.getVert(mesh, i)
            verts.append((float(p.x), float(p.y), float(p.z)))
        faces, ids = [], []
        for i in range(1, nf + 1):
            f = rt.getFace(mesh, i)
            faces.append([int(f.x) - 1, int(f.y) - 1, int(f.z) - 1])
            ids.append(int(rt.getFaceMatID(mesh, i)))
        kind = 'trimesh'
    if not faces:
        raise ValueError('empty mesh: ' + str(n.name))
    for p in verts:
        if not all(math.isfinite(c) for c in p):
            raise ValueError('non-finite vertex: ' + str(n.name))
    return {'vertices': verts, 'faces': faces, 'ids': ids, 'kind': kind}


def _channel(n):
    """Channel 1 of the base object when it exists (for the before/after check of the source), else None."""
    rt = _rt()
    kind = rt.classOf(n.baseObject)
    if kind not in (rt.Editable_Poly, rt.Editable_Mesh):
        return None
    try:
        return ctx_read_channel(n)
    except ValueError:
        return None


ctx_read_channel = None  # bound to runtime._read_channel at the call


def _source_state(ctx, n):
    h = _helpers(ctx)
    return {'handle': h.handle(n), 'name': str(n.name), 'stack': _stack(n),
            'snapshot': ctx.emax.snapshot([n])[0], 'channel1': _channel(n)}


def udim_matid_unwrap(ctx, mode, nodes, preview):
    global ctx_read_channel
    rt = _rt()
    edit, core, emax = ctx.edit, ctx.core, ctx.emax
    ctx_read_channel = ctx.agr._read_channel
    h = _helpers(ctx)
    options = _unwrap_options(ctx, mode, preview)
    nodes = h.target_nodes(nodes)
    unit = h.unit_m()
    targets, meshes, skipped, state, per_object, entries = [], [], [], [], [], []
    for n in nodes:
        if rt.superClassOf(n) != rt.GeometryClass or not bool(rt.canConvertTo(n, rt.TriMeshGeometry)):
            skipped.append(edit.skipped(str(n.name), 'not geometry'))
            continue
        try:
            mesh = read_mesh(n)
        except ValueError as exc:
            skipped.append(edit.skipped(str(n.name), str(exc)))
            continue
        plan = core.unwrap_plan(mesh, unit, options['px_per_m'], options['map_px'], options['pad_px'],
                                options['angle'])
        targets.append(n)
        meshes.append((mesh, plan))
        state.append({'source': _source_state(ctx, n), 'mesh': mesh, 'unit_m': unit})
        findings = [edit.finding(c, ids, d) for c, ids, d in plan['findings']]
        entries.append(edit.entry(h.handle(n), str(n.name), findings))
        per_object.append({'object': str(n.name), 'mesh': mesh['kind'], 'collapse_copy': not _plain(n),
                           'stack': _stack(n), 'px_per_m': plan['px_per_m'], 'ok': plan['ok'], 'ids': plan['rows']})
    if not targets:
        raise ValueError('no object can be unwrapped: ' + '; '.join(s['item'] + ': ' + s['reason'] for s in skipped))
    done = [{'object': p['object'], 'id': r['id'], 'tile': r['tile'], 'faces': r['faces'], 'islands': r['islands'],
             'px_per_m': r.get('px_per_m_after')} for p in per_object if p['ok'] for r in p['ids']]
    for p in per_object:
        if not p['ok']:
            skipped.append(edit.skipped(p['object'], 'not unwrapped: see the findings (fail-closed, no copy)'))
    extra = {'options': options, 'layer': LAYER, 'unit_m': unit, 'per_object': per_object, 'issue': '#979'}
    if mode == 'preview':
        return edit.report(TOOL_UNWRAP, 'preview', entries, done, skipped, (), state_hash=edit.fingerprint(state),
                           extra=extra)
    edit.require_current(preview, state)
    if edit.fingerprint([preview['plan']['done'], preview['plan']['per_object']]) != edit.fingerprint([done, per_object]):
        raise edit.StalePreview('the unwrap differs from the preview; run preview again')
    work = [(n, m, p) for n, (m, p), po in zip(targets, meshes, per_object) if po['ok']]
    if not work:
        raise ValueError('no object can be unwrapped: every plan has findings (see the preview)')
    copies, objects, applied, collapsed = [], [], [], []

    def body():
        try:
            pairs = emax.export_copies([n for n, _, _ in work], layer=LAYER)
            copies.extend(c for _, c in pairs)
            for (n, c), (_, mesh, plan) in zip(pairs, work):
                if not _plain(n):
                    rt.convertToMesh(c)
                    collapsed.append({'copy': str(c.name), 'source': str(n.name), 'stack': _stack(n)})
                got = read_mesh(c)
                if got['faces'] != mesh['faces'] or got['ids'] != mesh['ids'] or any(
                        max(abs(a - b) for a, b in zip(p, q)) > 1e-6 * max(1.0, max(abs(x) for x in p))
                        for p, q in zip(got['vertices'], mesh['vertices'])):
                    raise RuntimeError('export copy mesh differs from the previewed mesh: ' + str(c.name))
                ctx.agr._write_channel(c, plan['uvs'], plan['face_uvs'])
                back = ctx.agr._read_channel(c)
                ctx.agr.assert_uv_close(back['uvs'], plan['uvs'])
                if back['face_uvs'] != [list(f) for f in plan['face_uvs']] or back['ids'] != mesh['ids']:
                    raise RuntimeError('copy readback differs from the written layout: ' + str(c.name))
                measured = core.measure_layout(dict(mesh, vertices=back['vertices']), back['uvs'], back['face_uvs'],
                                               unit, options['map_px'])
                findings = []
                for mid, row in sorted(measured['ids'].items()):
                    if row['outside_tile']:
                        findings.append(edit.finding('outside_tile', row['outside_tile'],
                                                     'ID {} faces outside tile {}'.format(mid, core.tile_of_id(mid))))
                    applied.append({'object': str(c.name), 'source': str(n.name), 'id': mid,
                                    'tile': core.tile_of_id(mid), 'tiles_after': row['tiles_after'],
                                    'px_per_m': row['px_per_m_after']})
                if measured['overlaps']:
                    findings.append(edit.finding('uv_overlap', sorted({f for p in measured['overlaps'] for f in p}),
                                                 'overlapping faces after readback'))
                objects.append(edit.entry(h.handle(c), str(c.name), findings))
            after = [{'source': _source_state(ctx, n), 'mesh': read_mesh(n), 'unit_m': unit} for n in targets]
            if edit.fingerprint(after) != edit.fingerprint(state):
                raise RuntimeError('working objects changed during apply')
        except Exception:
            alive = [c for c in copies if rt.isValidNode(c)]
            if alive:
                rt.delete(alive)
            raise
    _in_session(emax, TOOL_UNWRAP, body)
    extra = dict(extra, copies=[str(c.name) for c in copies], collapsed_copies=collapsed)
    return edit.report(TOOL_UNWRAP, 'apply', objects, applied, skipped, (), extra=extra)
