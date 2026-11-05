"""new-case: AGR Tools 0.9 (#979) finish map by legend, 3ds Max side (branch B).

runtime.edits_090 calls `tex_finish_map(ctx, mode, nodes, preview)`; ctx: agr (runtime globals), core
(finish_core), edit (edit_core), emax (edit_max), options (dict of the preview). pymxs is imported inside functions.

Options: `legend` (path of a .json or .csv legend, mandatory), `seams_m` (optional list overriding the legend's).
preview validates the legend first (a broken legend is an error before anything else), reads every object's
evaluated mesh and plans ID -> finish and the seam rings; nothing changes. apply re-checks the preview, then in ONE
undo record makes export copies (layer `AGR_export_finish`), converts a copy to Editable_Poly where needed, cuts
the rings (polyop.slice, plane in the copy's object space), builds a Multi/Sub of the legend finishes on the copy,
and checks back: every face's sub-material is its finish, every seam within +-1 mm, the source unchanged. A seam
that cannot be cut, a missing finish texture or a mismatch deletes the copies (fail-closed).
"""
TOOL = 'tex.finish_map'
LAYER = 'AGR_export_finish'
OPTION_KEYS = {'legend', 'seams_m'}


def _rt():
    from pymxs import runtime
    return runtime


def _helpers(ctx):
    return ctx.agr._load_core('texqa_max.py', 'agr_tools_texqa_max')


def _unwrap(ctx):
    return ctx.agr._load_core('uvtile_max.py', 'agr_tools_uvtile_max')


def _session_core():
    """Shared helpers (session_core.py next to this file), loaded by path like the other sibling cores."""
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('agr_tools_session_core', Path(__file__).with_name('session_core.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_in_session = _session_core().in_session


def _options(ctx, mode, preview):
    if mode == 'apply':
        return dict(preview['plan']['options'])
    opts = dict(ctx.options or {})
    unknown = set(opts) - OPTION_KEYS
    if unknown:
        raise ValueError('unknown tex.finish_map options: ' + ', '.join(sorted(unknown)))
    if not isinstance(opts.get('legend'), str) or not opts['legend'].strip():
        raise ValueError('options.legend is mandatory: the path of the colour-scheme legend (.json or .csv)')
    out = {'legend': opts['legend'], 'seams_m': opts.get('seams_m')}
    if out['seams_m'] is not None:
        out['seams_m'] = ctx.core.validate_seams(out['seams_m'])
    return out


def _legend(ctx, path):
    import hashlib
    import os
    if not os.path.isabs(path):
        base = str(_rt().maxFilePath or '')
        if base:
            path = os.path.join(base, path)
    if not os.path.isfile(path):
        raise ValueError('legend file not found: ' + path)
    data = open(path, 'rb').read()
    kind = os.path.splitext(path)[1].lower().lstrip('.')
    legend = ctx.core.parse_legend(data.decode('utf-8-sig'), kind)
    return legend, hashlib.sha256(data).hexdigest()


def _material_state(n):
    rt = _rt()
    mat = n.material
    return None if mat is None else [str(rt.classOf(mat)), str(mat.name)]


def _make_material(legend, rows, name):
    rt = _rt()
    ids = [r['id'] for r in rows]
    mm = rt.MultiMaterial(numsubs=len(ids))
    mm.name = name
    for i, r in enumerate(rows):
        mm.materialIDList[i] = r['id']
        sub = rt.Standardmaterial()
        sub.name = r['finish']
        spec = legend['finishes'][r['finish']]
        if spec['color'] is not None:
            sub.diffuse = rt.color(*spec['color'])
        if spec['texture'] is not None:
            tex = rt.Bitmaptexture()
            tex.filename = spec['texture']
            sub.diffuseMap = tex
        mm.materialList[i] = sub
    return mm


def _slice(copy, z_world):
    """Cut the copy's faces with the horizontal plane at world z (plane given in the copy's object space)."""
    rt = _rt()
    inv = rt.inverse(copy.objectTransform)
    p = rt.point3(0, 0, z_world) * inv
    q = rt.point3(0, 0, z_world + 1.0) * inv
    d = rt.normalize(q - p)
    faces = rt.execute('#{1..' + str(int(rt.polyop.getNumFaces(copy))) + '}')
    rt.polyop.slice(copy, faces, rt.ray(p, d))


def tex_finish_map(ctx, mode, nodes, preview):
    rt = _rt()
    edit, core, emax = ctx.edit, ctx.core, ctx.emax
    h = _helpers(ctx)
    options = _options(ctx, mode, preview)
    legend, legend_sha = _legend(ctx, options['legend'])
    nodes = h.target_nodes(nodes)
    unit = h.unit_m()
    reader = _unwrap(ctx)
    items, skipped, state, targets = [], [], [], []
    for n in nodes:
        if rt.superClassOf(n) != rt.GeometryClass or not bool(rt.canConvertTo(n, rt.TriMeshGeometry)):
            skipped.append(edit.skipped(str(n.name), 'not geometry'))
            continue
        mesh = reader.read_mesh(n)
        items.append((h.handle(n), str(n.name), mesh))
        targets.append(n)
        state.append({'handle': h.handle(n), 'name': str(n.name), 'mesh': mesh, 'material': _material_state(n),
                      'stack': [str(rt.classOf(n.baseObject))] + [str(rt.classOf(m)) for m in n.modifiers]})
    if not items:
        raise ValueError('no object to paint: ' + '; '.join(s['item'] + ': ' + s['reason'] for s in skipped))
    res = core.plan(items, legend, unit, options['seams_m'])
    import os
    for p in res['plans']:
        for r in p['ids']:
            if r['texture'] is not None and not os.path.isfile(r['texture']):
                p['findings'].append(('finish_texture_missing', [], 'finish {} texture not found: {}'.format(
                    r['finish'], r['texture'])))
    entries, done, per_object = [], [], []
    for p in res['plans']:
        entries.append(edit.entry(p['key'], p['object'], [edit.finding(c, ids, d) for c, ids, d in p['findings']]))
        per_object.append({k: p[k] for k in ('object', 'ids', 'cuts_z_m', 'base_z_m', 'seams_per_facade')})
        if not p['findings']:
            done.append({'object': p['object'], 'ids': [[r['id'], r['finish']] for r in p['ids']],
                         'seams': len(p['cuts_z_m']), 'seams_per_facade': p['seams_per_facade']})
        else:
            skipped.append(edit.skipped(p['object'], 'not painted: see the findings (fail-closed, no copy)'))
    extra = {'options': options, 'legend_sha256': legend_sha, 'unit_m': unit, 'layer': LAYER,
             'unused_finishes': res['unused_finishes'], 'per_object': per_object, 'issue': '#979'}
    if mode == 'preview':
        return edit.report(TOOL, 'preview', entries, done, skipped, (),
                           state_hash=edit.fingerprint([state, legend_sha]), extra=extra)
    edit.require_current(preview, [state, legend_sha])
    if edit.fingerprint([preview['plan']['done'], preview['plan']['per_object']]) != edit.fingerprint([done, per_object]):
        raise edit.StalePreview('the finish plan differs from the preview; run preview again')
    work = [(n, p) for n, p in zip(targets, res['plans']) if not p['findings']]
    if not work:
        raise ValueError('nothing to paint: every object has findings (see the preview)')
    copies, objects, applied = [], [], []

    def body():
        try:
            pairs = emax.export_copies([n for n, _ in work], layer=LAYER)
            copies.extend(c for _, c in pairs)
            for (n, c), (_, p) in zip(pairs, work):
                if int(c.modifiers.count) or rt.classOf(c.baseObject) != rt.Editable_Poly:
                    rt.convertToPoly(c)
                for z in p['cuts_z_m']:
                    _slice(c, z / unit)
                c.material = _make_material(legend, p['ids'], 'M_finish_' + str(n.name))
                back = reader.read_mesh(c)
                want = {r['id']: r['finish'] for r in p['ids']}
                bad = [f + 1 for f, mid in enumerate(back['ids']) if mid not in want]
                if bad:
                    raise RuntimeError('copy faces without a finish after the cut: {}'.format(bad[:20]))
                subs = {mid: str(sub.name) for mid, sub in h.sub_materials(c)}
                if any(subs.get(mid) != fin for mid, fin in want.items()):
                    raise RuntimeError('copy material does not match the legend: ' + str(c.name))
                zs = [v[2] * unit for v in back['vertices']]
                seams = core.seam_readback(zs, p['cuts_z_m'])
                if not all(s['ok'] for s in seams):
                    raise RuntimeError('seam not within 1 mm on {}: {}'.format(c.name, seams))
                objects.append(edit.entry(h.handle(c), str(c.name), []))
                applied.append({'object': str(c.name), 'source': str(n.name), 'ids': [[r['id'], r['finish']]
                                                                                    for r in p['ids']],
                                'seams': seams, 'seams_per_facade': p['seams_per_facade'],
                                'faces': len(back['faces'])})
            after = []
            for n in targets:
                after.append({'handle': h.handle(n), 'name': str(n.name), 'mesh': reader.read_mesh(n),
                              'material': _material_state(n),
                              'stack': [str(rt.classOf(n.baseObject))] + [str(rt.classOf(m)) for m in n.modifiers]})
            if edit.fingerprint(after) != edit.fingerprint(state):
                raise RuntimeError('working objects changed during apply')
        except Exception:
            alive = [c for c in copies if rt.isValidNode(c)]
            if alive:
                rt.delete(alive)
            raise
    _in_session(emax, TOOL, body)
    extra = dict(extra, copies=[str(c.name) for c in copies])
    return edit.report(TOOL, 'apply', objects, applied, skipped, (), extra=extra)
