"""new-case: AGR Tools 1.0 (#1024) VPM build (steps K6, K3), 3ds Max side; owned by branch M (improve/issue-1024-vpm-layout).

runtime.edits_100 calls `vpm_build(ctx, mode, nodes, preview)` for `vpm.build` (plan mode copy + file).
ctx: agr (runtime globals), core (vpm_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost). Import pymxs inside functions so this file loads under plain pytest.

preview: reads every selected OKS mesh (udim10_max.read_tri: object coordinates + objectTransform in double, metres
by units.SystemScale) and plans the build (vpm_core.build): K6 projection with the perimeter unroll, texel, cut by
the UV grid, whole shifts into the tile of each material, UDIM 1001.. per mesh, glass to its own object, seam /
texel / tile checks. Nothing changes.
apply: re-reads and compares (edit_core.require_current + the planned rows), then in ONE undo record (selection
restored) makes export copies on layer `AGR_vpm` (`<name>_VPM_NNN`, glass `<name>_glass_VPM_NNN`), writes the new
geometry (Editable_Mesh, local coordinates interpolated from the source vertices, fan diagonals hidden), material
ids, channel 1 and the user prop `agr_udim_table` (its own {library id: UDIM}, 1.0.1) into the COPY, reads it back and measures the seam and texel on the real Max data; the working
objects are compared before/after (mesh, transform, UV, stack). Objects with findings are not built (fail-closed).
Then the file step writes into a NEW folder (edit_core.new_path, never overwrite): `vpm_table.json` (UDIM table per
mesh, K3; the passport write belongs to branch F) and the maps of step 6 through vpmmaps_core.build_maps (branch
N; `skipped` while it is a stub). No clearUndoBuffer (GeoAGR `:33785`), no stack collapse of an original
(GeoAGR `:32214`), no new MAXScript globals.
"""
import json
import os

TOOL = 'vpm.build'
LAYER = 'AGR_vpm'
UDIM_PROP = 'agr_udim_table'   # same prop as mat.table (matlib_max.UDIM_PROP): {library id: UDIM} of THIS mesh
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


def _reader(ctx):
    return ctx.agr._load_core('udim10_max.py', 'agr_tools_udim10_max')


def _renumber(ctx):
    """matlib_core.renumber_dense of branch L when implemented, else uvlayout_core's copy of the same contract."""
    try:
        ml = ctx.agr._load_core('matlib_core.py', 'agr_tools_matlib_core')
        ml.renumber_dense([1])
        return ml.renumber_dense, 'matlib_core'
    except NotImplementedError:
        return None, 'uvlayout_core (matlib_core.renumber_dense is a stub of branch L)'


def _library(ctx, o):
    """(library, '') for step 6 (maps D+ERM+N by vpmmaps_core.build_maps of branch N), else (None, reason)."""
    if not o.get('library_path'):
        return None, 'no options.library_path: maps D+ERM+N need the material library (K3)'
    try:
        ml = ctx.agr._load_core('matlib_core.py', 'agr_tools_matlib_core')
        return ml.load_library(o['library_path']), ''
    except NotImplementedError:
        return None, 'matlib_core.load_library is a stub of branch L (#1024): no maps written'


def _maps_options(o):
    """Options of vpmmaps_core for step 6: the folder of the grey masks of mat.tiles (options.map_dir), else none."""
    return {'map_dir': o['map_dir']} if o.get('map_dir') else None


def _steps(maps_reason, file_reason):
    return [{'step': 1, 'name': 'UV: K6 projection, perimeter unroll', 'status': 'done'},
            {'step': 2, 'name': 'texel (udim.rescale rule)', 'status': 'done'},
            {'step': 3, 'name': 'UDIM layout seam to seam (K6)', 'status': 'done'},
            {'step': 4, 'name': 'library ids -> UDIM 1001.. per mesh (K3)', 'status': 'done'},
            {'step': 5, 'name': 'glass to its own object', 'status': 'done'},
            {'step': 6, 'name': 'maps D+ERM+N', 'status': 'skipped' if maps_reason else 'done',
             'reason': maps_reason or ''},
            {'step': 7, 'name': 'tex.dilate', 'status': 'skipped', 'reason': 'button of branch N (tex.dilate)'},
            {'step': 8, 'name': 'udim.plugs', 'status': 'skipped', 'reason': 'button of branch N (udim.plugs)'},
            {'step': 9, 'name': 'udim.distortion rule on the copy (seam, texel, tiles)', 'status': 'done'},
            {'step': 'file', 'name': 'vpm_table.json in a new folder', 'status': 'skipped' if file_reason else 'done',
             'reason': file_reason or ''}]


def _out_dir(ctx, o):
    rt = _rt()
    if o.get('out_dir'):
        return o['out_dir'], ''
    if not str(rt.maxFileName):
        return None, 'scene not saved and no options.out_dir: the file step has no folder'
    stem = os.path.splitext(str(rt.maxFileName))[0]
    return os.path.join(str(rt.maxFilePath), stem + '_VPM'), ''


def _plan(ctx, nodes):
    rt = _rt()
    edit, core = ctx.edit, ctx.core
    rd = _reader(ctx)
    k = ctx.host.m_per_unit()
    nodes = rd.target_nodes(nodes)
    meshes, by_key, skipped, state = [], {}, [], []
    for n in nodes:
        if not rd.is_geometry(n):
            skipped.append(edit.skipped(str(n.name), 'not geometry'))
            continue
        mesh = rd.read_tri(n, k)
        key = rd.handle(n)
        by_key[key] = (n, mesh)
        meshes.append({'key': key, 'name': str(n.name), 'verts': mesh['verts'], 'tris': mesh['tris'],
                       'mat_ids': mesh['mat_ids'], 'uvs': mesh['uvs'], 'uv_tris': mesh['uv_tris']})
        state.append(rd._state(ctx, n, mesh))
    if not meshes:
        raise ValueError('nothing to build: ' + '; '.join(s['item'] + ': ' + s['reason'] for s in skipped))
    renumber, renumber_src = _renumber(ctx)
    plan = core.build(meshes, ctx.options, renumber)
    return plan, by_key, skipped, state, renumber_src, k, rt


def vpm_build(ctx, mode, nodes, preview):
    edit, core, emax = ctx.edit, ctx.core, ctx.emax
    if mode == 'apply':
        ctx.options = dict(preview['plan']['options'])
    plan, by_key, skipped, state, renumber_src, k, rt = _plan(ctx, nodes)
    o = plan['options']
    entries, done = [], []
    for obj in plan['objects']:
        entries.append(edit.entry(obj['key'], obj['name'], [edit.finding(c, ids, d) for c, ids, d in obj['findings']]))
        if obj['findings']:
            skipped.append(edit.skipped(obj['name'], 'not built: see the findings (fail-closed, no copy)'))
            continue
        for p in obj['parts']:
            done.append(dict(p['summary'], source=obj['name']))
    out_dir, file_reason = _out_dir(ctx, o)
    library, maps_reason = _library(ctx, o)
    if not maps_reason and not out_dir:
        maps_reason = file_reason
    maps_planned = maps_error = None
    if library is not None and not maps_reason and done:
        # 1.0.1 (KPP1 e2e 20261106-101005-9a657979): step 6 is planned here, so a map name / table error refuses
        # in the preview and BEFORE the copies of apply (was: copies and vpm_table.json written, then a refusal)
        vm = ctx.agr._load_core('vpmmaps_core.py', 'agr_tools_vpmmaps_core')
        try:
            mp = vm.plan_maps(core.maps_table(plan), library, os.path.join(out_dir, 'maps'), _maps_options(o))
            maps_planned = {'maps': len(mp['maps']), 'skipped': len(mp['skipped']),
                            'names': sorted(m['name'] for m in mp['maps'])[:6]}
        except ValueError as exc:
            maps_error = 'step 6 (maps D+ERM+N) cannot be planned: {} (options.address names the maps)'.format(exc)
    extra = {'options': o, 'layer': LAYER, 'issue': ISSUE, 'unit_m': k, 'renumber': renumber_src,
             'out_dir': out_dir, 'steps': _steps(maps_reason or maps_error, file_reason)}
    if maps_error:
        extra['steps'][5]['status'] = 'refused'
    if maps_planned is not None:
        extra['maps_planned'] = maps_planned
    if mode == 'preview':
        if maps_error:
            skipped.append(edit.skipped('maps D+ERM+N', maps_error))
        return edit.report(TOOL, 'preview', entries, done, skipped, (), state_hash=edit.fingerprint(state),
                           extra=extra)
    edit.require_current(preview, state)
    if maps_error:
        raise ValueError(maps_error + ': nothing built (fail-closed)')
    if edit.fingerprint(preview['plan']['done']) != edit.fingerprint(done):
        raise edit.StalePreview('the build differs from the preview; run preview again')
    work = [(by_key[obj['key']], p) for obj in plan['objects'] if not obj['findings'] for p in obj['parts']]
    if not work:
        raise ValueError('nothing to build: every object has findings (see the preview)')
    rd = _reader(ctx)
    lay = core.lay
    copies, objects, applied = [], [], []

    def body():
        try:
            for (n, mesh), part in work:
                suffix = '_glass_VPM_' if part['summary']['part'] == 'glass' else '_VPM_'
                (src, c), = emax.export_copies([n], suffix=suffix, layer=LAYER)
                copies.append(c)
                rt.convertToMesh(c)
                geo = part['geometry']
                write_mesh(c, mesh['local'], geo)
                # 1.0.1: the copy carries its own dense table (the inherited prop of the source may be stale, e.g.
                # after attach): udim.plugs / npm.build read the tile of a library id from it (KPP1 e2e)
                rt.setUserProp(c, UDIM_PROP, json.dumps(part['summary']['udim_table'], sort_keys=True))
                rt.setUserProp(c, 'MapChannel:1', 'UV')   # the UDIM layout IS the delivered UV (export hygiene)
                back = rd.read_tri(c, k)
                findings, measured = measure(core, lay, o, back, geo)
                objects.append(edit.entry(rd.handle(c), str(c.name), findings))
                applied.append(dict(part['summary'], copy=str(c.name), source=str(n.name), readback=measured))
            now = [rd._state(ctx, n, rd.read_tri(n, k)) for n, _m in by_key.values()]
            if edit.fingerprint(sorted(now, key=lambda s: s['handle'])) != edit.fingerprint(
                    sorted(state, key=lambda s: s['handle'])):
                raise RuntimeError('working objects changed during apply')
        except Exception:
            alive = [c for c in copies if rt.isValidNode(c)]
            if alive:
                rt.delete(alive)
            raise
    _session_core().in_session(emax, TOOL, body)
    files = []
    if out_dir:
        folder = edit.new_path(out_dir, version=True)
        os.makedirs(folder)
        table = core.table_json(plan, ctx.host.doc(), 'vpm_core 1.0')
        for row in table['meshes']:
            row['copy'] = next((a['copy'] for a in applied if a['object'] == row['object']), None)
        path = edit.write_new(os.path.join(folder, 'vpm_table.json'),
                              (edit.canonical(table) + '\n').encode('ascii'))
        files.append({'path': path, 'kind': 'udim_table'})
        extra['out_dir'] = folder
        if library is not None:
            vm = ctx.agr._load_core('vpmmaps_core.py', 'agr_tools_vpmmaps_core')
            res = vm.build_maps(core.maps_table(plan), library, os.path.join(folder, 'maps'), _maps_options(o))
            files.extend(dict(m, kind='map_' + m['kind']) for m in res['maps'])
            skipped.extend(edit.skipped('map {} {} {}'.format(x.get('mesh'), x.get('udim'), x.get('kind')),
                                        x.get('reason') or 'skipped by vpmmaps_core') for x in res['skipped'])
    extra = dict(extra, copies=[str(c.name) for c in copies], files=files)
    return edit.report(TOOL, 'apply', objects, applied, skipped, (), extra=extra)


def write_mesh(c, local_src, geo):
    """Replace the copy's Editable_Mesh by the planned geometry (object coordinates, system units)."""
    rt = _rt()
    m = rt.TriMesh()
    nv, nf = len(geo['verts_w']), len(geo['tris'])
    rt.setNumVerts(m, nv)
    rt.setNumFaces(m, nf)
    for i, ws in enumerate(geo['verts_w'], 1):
        x = y = z = 0.0
        for vid, w in ws:
            p = local_src[vid]
            x += w * p[0]
            y += w * p[1]
            z += w * p[2]
        rt.setVert(m, i, rt.point3(x, y, z))
    for f, (t, mid) in enumerate(zip(geo['tris'], geo['mat_ids']), 1):
        rt.setFace(m, f, t[0] + 1, t[1] + 1, t[2] + 1)
        rt.setFaceMatID(m, f, mid)
    rt.meshop.setMapSupport(m, 1, True)
    rt.meshop.setNumMapVerts(m, 1, len(geo['uvs']))
    for i, (u, v) in enumerate(geo['uvs'], 1):
        rt.meshop.setMapVert(m, 1, i, rt.point3(float(u), float(v), 0.0))
    for f, t in enumerate(geo['uv_tris'], 1):
        rt.meshop.setMapFace(m, 1, f, rt.point3(t[0] + 1, t[1] + 1, t[2] + 1))
    # hide the fan diagonals inside one piece (consecutive triangles of one source triangle share an edge)
    for f in range(nf):
        t = geo['tris'][f]
        for e in range(3):
            a, b = t[e], t[(e + 1) % 3]
            inner = any(geo['src_tri'][g] == geo['src_tri'][f] and a in geo['tris'][g] and b in geo['tris'][g]
                        for g in (f - 1, f + 1) if 0 <= g < nf)
            rt.setEdgeVis(m, f + 1, e + 1, not inner)
    c.mesh = m
    rt.update(c)


def measure(core, lay, o, back, geo):
    """Seam / texel / tiles on the read-back copy (float32 as stored by Max)."""
    edit_findings = []
    if back['tris'] != geo['tris'] or back['mat_ids'] != geo['mat_ids'] or back['uv_tris'] != geo['uv_tris']:
        raise RuntimeError('copy readback differs from the written geometry')
    du = max((abs(a - b) for p, q in zip(back['uvs'], geo['uvs']) for a, b in zip(p, q)), default=0.0)
    if du > 1e-5:
        raise RuntimeError('copy readback UV differs from the written UV by {:.2e}'.format(du))
    pieces = [{'tri': f, 'w': [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
               'uv': [back['uvs'][i] for i in back['uv_tris'][f]], 'mat': back['mat_ids'][f]}
              for f in range(len(back['tris']))]
    plane = geo['plane_of_src']
    wall_of = {f: tuple(plane[str(geo['src_tri'][f])]) if isinstance(plane.get(str(geo['src_tri'][f])), list)
               else plane.get(str(geo['src_tri'][f])) for f in range(len(back['tris']))}
    pairs = {frozenset(tuple(x) for x in pr) for pr in geo['chain_pairs']}
    mesh = {'verts': back['verts'], 'tris': back['tris'], 'mat_ids': back['mat_ids']}
    seam = lay.seam_metric(mesh, pieces, core.px_per_step(o), wall_of, pairs)
    bad = [b for b in seam['bad'] if b['kind'] != 'fold']
    if bad:
        edit_findings.append(('seam', sorted({f + 1 for b in bad for f in b['faces']}),
                              'readback seam up to {:.4f} px'.format(max(b['px'] for b in bad))))
    texel, tex_bad, tiny, solid = {}, [], 0, []
    px = core.px_per_step(o)
    for f, p in enumerate(pieces):
        (u0, v0), (u1, v1), (u2, v2) = p['uv']
        if abs((u1 - u0) * (v2 - v0) - (u2 - u0) * (v1 - v0)) * 0.5 * px * px < 1.0:
            tiny += 1  # a sliver of the grid cut under 1 px²: float32 UV noise, not a texel (job 20261106-045430)
            continue
        solid.append(p)
        jac = core.u10.jacobian([back['verts'][i] for i in back['tris'][f]], p['uv'])
        if jac is None or jac[1] <= 1e-15:
            continue
        tx = (jac[0] * jac[1]) ** 0.5 * core.px_per_step(o)
        lo, hi = texel.get(p['mat'], (tx, tx))
        texel[p['mat']] = (min(lo, tx), max(hi, tx))
        if abs(tx / core.texel_of(o, p['mat']) - 1) > core.u10.SCALE_TOL:
            tex_bad.append(f + 1)
    if tex_bad:
        edit_findings.append(('texel', tex_bad, 'readback texel off by more than 1 %'))
    crossing = lay.crossing_pieces(pieces)
    if crossing:
        edit_findings.append(('crossing', [f + 1 for f in crossing], 'triangles across a tile line'))
    # tiles of the triangles with area; a sliver lying on a tile line (float32) has its centroid ON the line
    # (job 20261106-045952-58a7ded5: «1003»), it is checked by the crossing test above instead
    tiles = sorted({lay.udim_of_cell(*[int(c) for c in lay._cell(p['uv'])]) or 0 for p in solid})
    from_ed = [_finding(c, ids, d) for c, ids, d in edit_findings]
    return from_ed, {'seam_internal_max_px': seam['internal_max'], 'seam_chain_max_px': seam['chain_max'],
                     'seam_fold_max_px': seam['fold_max'], 'tiles': tiles, 'crossing': len(crossing),
                     'texel_skipped_slivers': tiny,
                     'texel_px_per_m': {str(m): [round(a, 3), round(b, 3)] for m, (a, b) in sorted(texel.items())}}


def _finding(code, ids, detail):
    return {'code': str(code), 'ids': sorted(set(int(i) for i in ids)), 'detail': str(detail)}
