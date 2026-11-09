"""new-case: AGR Tools 0.8 (#908) names, 3ds Max side (branch C, improve/issue-908-names).

runtime.edits_080 calls `ucx_rename` / `qa_names_fix` as `<function>(ctx, mode, nodes, preview)`; ctx: agr (runtime
globals), core (names_core), edit (edit_core), emax (edit_max), options (dict of the preview). pymxs is imported
inside functions so this file loads under plain pytest.

ucx.rename (plan mode `undo`): renames the selected UCX pieces in place, ONE undo record, selection restored;
every other selected node is skipped and listed. Names held by unselected nodes are never produced.
qa.names_fix (plan mode `copy`): export copies on layer `AGR_export_names` get the mask names; their (copied)
materials and maps are renamed; map files are copied next to the source under the mask file name, never
overwriting (edit_core.new_path / write_new). The working objects, their materials and every existing file stay
unchanged (checked after apply). Options: model npm|vpm (default: AGR_EXPORT_PATH, else an NPM OKS number),
donor (object name: Material Cloner mode), replace_material (bool, donor replaces a target's own material).
"""
import hashlib
import os

UCX_TOOL = 'ucx.rename'
FIX_TOOL = 'qa.names_fix'
LAYER = 'AGR_export_names'
FIX_OPTIONS = {'model', 'donor', 'replace_material', 'profile', 'folder', 'address', 'oks'}

# Material class -> [(property path, role)] = names_core.SLOT_TABLE (V13 slot table, #979 E1); role None: the
# slot has no texture role and its bitmap is reported, never renamed (reflection is not `_m`). A Normal_Bump in a
# bump slot is followed to its normal map. Kept here as constants: this file loads without the core.
PHYSICAL = (('base_color_map', 'diffuse'), ('bump_map', 'normal'), ('roughness_map', 'roughness'),
            ('metalness_map', 'metalness'), ('cutout_map', 'opacity'), ('transparency_map', 'opacity'),
            ('emission_map', 'emission'), ('reflectivity_map', None))
STANDARD = (('diffuseMap', 'diffuse'), ('bumpMap', 'normal'), ('opacityMap', 'opacity'),
            ('glossinessMap', 'roughness'), ('specularLevelMap', 'metalness'), ('reflectionMap', None),
            ('specularMap', None))


def _rt():
    from pymxs import runtime
    return runtime


def _handle(n):
    return int(_rt().getHandleByAnim(n))


def _selected(nodes):
    rt = _rt()
    if nodes is None:
        nodes = list(rt.selection)
    nodes = [n for n in nodes]
    if not nodes:
        raise ValueError('nothing selected')
    if len({_handle(n) for n in nodes}) != len(nodes):
        raise ValueError('duplicate node in the target set')
    return sorted(nodes, key=_handle)


def _node(h):
    n = _rt().getAnimByHandle(int(h))  # keys are anim handles (getHandleByAnim), not inode handles
    if n is None or not _rt().isValidNode(n):
        raise ValueError('node {} is gone; run preview again'.format(h))
    return n


def _session_core():
    """Shared helpers (session_core.py next to this file), loaded by path like the other sibling cores."""
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('agr_tools_session_core', Path(__file__).with_name('session_core.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


in_session = _session_core().in_session  # public name kept (CHANGELOG cites names_max.in_session)


def _is_geometry(n):
    rt = _rt()
    return rt.superClassOf(n) == rt.GeometryClass


# ---- ucx.rename ---------------------------------------------------------------------------------------------
def _ucx_state(ctx, nodes):
    rt = _rt()
    chosen = {_handle(n) for n in nodes}
    items = [{'key': _handle(n), 'name': str(n.name), 'geometry': bool(_is_geometry(n))} for n in nodes]
    occupied = sorted({str(o.name) for o in rt.objects if _handle(o) not in chosen
                       and ctx.core.UCX_MASK.fullmatch(str(o.name))})
    return {'items': items, 'occupied': occupied}


def ucx_rename(ctx, mode, nodes, preview):
    edit, core = ctx.edit, ctx.core
    if mode == 'preview' and ctx.options:
        raise ValueError('ucx.rename takes no options')
    nodes = _selected(nodes)
    state = _ucx_state(ctx, nodes)
    plan = core.ucx_plan(state['items'], state['occupied'])
    names = {it['key']: it['name'] for it in state['items']}
    skipped = [edit.skipped(s['name'], s['reason']) for s in plan['skipped']]
    ambiguous = [{'item': e['group'], 'keys': e['keys'], 'names': [names[k] for k in e['keys']], 'reason': e['reason']}
                 for e in plan['errors']]
    done = [{'old': r['old'], 'new': r['new']} for r in plan['rename']]
    unchanged = [u['name'] for u in plan['unchanged']]
    pieces = sorted([r['key'] for r in plan['rename']] + [u['key'] for u in plan['unchanged']])
    extra = {'unchanged': unchanged, 'occupied': state['occupied'], 'grammar': core.UCX_MASK.pattern, 'issue': '#908'}
    if mode == 'preview':
        # 0.9 (#979 E1): a piece whose name is not its planned mask name carries `ucx_name` (what apply will do),
        # so the preview reads as a check (pass = already canonical and in order).
        planned = {r['key']: r['new'] for r in plan['rename']}
        objects = [edit.entry(k, names[k], [edit.finding('ucx_name', (), '{!r} -> {!r}'.format(names[k], planned[k]))]
                              if k in planned else []) for k in pieces]
        return edit.report(UCX_TOOL, 'preview', objects, done, skipped, ambiguous,
                           state_hash=edit.fingerprint(state), extra=extra)
    edit.require_current(preview, state)
    if edit.fingerprint([preview['plan']['done'], preview['plan']['ambiguous']]) != edit.fingerprint([done, ambiguous]):
        raise edit.StalePreview('the rename plan differs from the preview; run preview again')
    def rename():
        for r in plan['rename']:
            _node(r['key']).name = r['new']
    in_session(ctx.emax, UCX_TOOL, rename)  # U6: one undo record restores every name
    back = {k: str(_node(k).name) for k in pieces}
    expected = {r['key']: r['new'] for r in plan['rename']}
    expected.update({u['key']: u['name'] for u in plan['unchanged']})
    objects = []
    for k in pieces:
        findings = []
        if back[k] != expected[k] or not core.UCX_MASK.fullmatch(back[k]):
            findings.append(edit.finding('ucx_name', (), 'readback {!r}, expected {!r}'.format(back[k], expected[k])))
        objects.append(edit.entry(k, back[k], findings))
    for s in plan['skipped']:
        if str(_node(s['key']).name) != s['name']:
            raise RuntimeError('a skipped node was renamed: ' + s['name'])
    return edit.report(UCX_TOOL, 'apply', objects, done, skipped, ambiguous, extra=extra)


# ---- qa.names_fix -------------------------------------------------------------------------------------------
def _fix_options(ctx, mode, preview):
    if mode == 'apply':
        return dict(preview['plan']['options'])
    opts = dict(ctx.options or {})
    unknown = set(opts) - FIX_OPTIONS
    if unknown:
        raise ValueError('unknown qa.names_fix options: ' + ', '.join(sorted(unknown)))
    out = {'model': opts.get('model'), 'donor': opts.get('donor'), 'replace_material': opts.get('replace_material', False)}
    for k in ('profile', 'folder', 'address', 'oks'):  # 0.9 (#979): only recorded when given
        if opts.get(k) is not None:
            out[k] = opts[k]
    return out


def _texmap(mat, prop):
    rt = _rt()
    if not rt.isProperty(mat, rt.Name(prop)):
        return None, prop
    tex = rt.getProperty(mat, rt.Name(prop))
    if tex is not None and rt.classOf(tex) == rt.Normal_Bump:
        return tex.normal_map, prop + '.normal_map'
    return tex, prop


def _set_texmap(mat, path, value):
    rt = _rt()
    parts = path.split('.')
    owner = mat
    for p in parts[:-1]:
        owner = rt.getProperty(owner, rt.Name(p))
    rt.setProperty(owner, rt.Name(parts[-1]), value)


def _get_texmap(mat, path):
    rt = _rt()
    owner = mat
    for p in path.split('.'):
        owner = rt.getProperty(owner, rt.Name(p))
    return owner


def _full_path(fn):
    rt = _rt()
    if not fn:
        return ''
    fn = str(fn)
    if os.path.isfile(fn):
        return fn
    try:
        full = str(rt.mapPaths.getFullFilePath(fn) or '')
    except Exception:  # noqa: BLE001 - unresolved stays as written; reported as missing
        full = ''
    return full if full and os.path.isfile(full) else fn


def _read_material(mat, used_ids):
    rt = _rt()
    if mat is None:
        return None
    if rt.classOf(mat) == rt.MultiMaterial:
        subs = []
        for i in range(len(mat.materialIDList)):
            sid, sub = int(mat.materialIDList[i]), mat.materialList[i]
            if sub is None:
                if sid in used_ids:
                    subs.append({'id': sid, 'used': True, 'name': '(empty slot {})'.format(sid), 'class': 'None',
                                 'unsupported': True, 'maps': None})
                continue
            row = _read_single(sub)
            row.update({'id': sid, 'used': sid in used_ids})
            subs.append(row)
        return {'name': str(mat.name), 'class': str(rt.classOf(mat)), 'subs': subs, 'maps': None}
    row = _read_single(mat)
    row['subs'] = None
    return row


def _read_single(mat):
    rt = _rt()
    cls = rt.classOf(mat)
    table = PHYSICAL if cls == rt.PhysicalMaterial else STANDARD if cls == rt.Standardmaterial else None
    if table is None:
        return {'name': str(mat.name), 'class': str(cls), 'unsupported': True, 'maps': None}
    maps = []
    for prop, role in table:
        tex, path = _texmap(mat, prop)
        if tex is None:
            continue
        if role is None:  # V2: a bitmap in a slot without a texture role is reported, never renamed
            maps.append({'key': path, 'role': None, 'path': None, 'name': str(tex.name)})
            continue
        if rt.classOf(tex) != rt.Bitmaptexture:
            maps.append({'key': path, 'role': 'unsupported map class {}'.format(rt.classOf(tex)), 'path': None,
                         'name': str(tex.name)})
            continue
        maps.append({'key': path, 'role': role, 'path': _full_path(tex.filename), 'name': str(tex.name)})
    return {'name': str(mat.name), 'class': str(cls), 'maps': maps}


def _used_ids(n):
    rt = _rt()
    if not rt.canConvertTo(n, rt.TriMeshGeometry):
        return set()
    mesh = rt.snapshotAsMesh(n)
    return {int(rt.getFaceMatID(mesh, i)) for i in range(1, int(mesh.numfaces) + 1)}


def _file_info(path):
    if not path or not os.path.isfile(path):
        return {'exists': False, 'sha256': None}
    with open(path, 'rb') as f:
        return {'exists': True, 'sha256': hashlib.sha256(f.read()).hexdigest()}


def _fix_state(ctx, nodes):
    rt = _rt()
    checks = ctx.agr._checks_core()
    objects = []
    for n in nodes:
        name = str(n.name)
        geo = bool(_is_geometry(n))
        kind = checks.fbx_kind(ctx.agr._prop(n, 'AGR_EXPORT_PATH') or '')
        objects.append({'key': _handle(n), 'name': name, 'geometry': geo, 'ucx': ctx.core.is_ucx_like(name),
                        'model': kind[0] if kind else None,
                        'material': _read_material(n.material, _used_ids(n)) if geo else None})
    layer = rt.LayerManager.getLayerFromName(LAYER)
    export_names = []
    if layer is not None and layer != rt.undefined:
        export_names = sorted({str(o.name) for o in rt.objects if str(o.layer.name) == LAYER})
    chosen = {_handle(n) for n in nodes}
    scene_names = sorted({str(o.name) for o in rt.objects
                          if _handle(o) not in chosen and str(o.layer.name) != LAYER})  # V6
    paths = set()
    for o in objects:
        for m in _materials(o['material']):
            for mp in m.get('maps') or ():
                if mp['path']:
                    paths.add(mp['path'])
    return {'objects': objects, 'files': {p: _file_info(p) for p in sorted(paths)}, 'export_names': export_names,
            'scene_names': scene_names}


def _materials(material):
    if material is None:
        return []
    return [material] if material.get('subs') is None else list(material['subs'])


def _fix_plan(ctx, nodes, options):
    """Two passes: the targets of the first plan are added to the file facts, then the final plan is made."""
    state = _fix_state(ctx, nodes)
    first = ctx.core.names_fix_plan(state, options)
    for row in first['files']:
        if row['target'] and row['target'] not in state['files']:
            state['files'][row['target']] = _file_info(row['target'])
    state['files'] = dict(sorted(state['files'].items()))
    return state, ctx.core.names_fix_plan(state, options)


def _fix_lists(ctx, plan, state):
    edit = ctx.edit
    names = {o['key']: o['name'] for o in state['objects']}
    done = ([{'object': o['old'], 'copy_name': o['new']} for o in plan['objects']]
            + [{'object': names[m['key']], 'material': m.get('old', m.get('material')), 'new': m.get('new'),
                'action': m['action']} for m in plan['materials']]
            + [{'object': names[f['key']], 'role': f['role'], 'slot': f['slot'], 'source': f['source'],
                'target': f['target'], 'action': f['action']} for f in plan['files']])
    skipped = [edit.skipped(s['item'], s['reason']) for s in plan['skipped']]
    ambiguous = [{'item': a['item'], 'objects': [names[k] for k in a['keys']], 'reason': a['reason']}
                 for a in plan['ambiguous']]
    findings = {}
    for f in plan['failures']:
        findings.setdefault(f['key'], []).append(edit.finding('name_fix_failed', (), '{}: {}'.format(f['item'], f['reason'])))
    for key, name, code, detail in ctx.core.check_names(plan, ctx.agr._checks_core()):
        findings.setdefault(key, []).append(edit.finding('name_mask', (), '{}: {} {}'.format(name, code, detail)))
    return done, skipped, ambiguous, findings


def _working_view(state):
    """What must not change on the working side: names, materials, map file names, existing file hashes."""
    return {'objects': state['objects'], 'files': {p: i for p, i in state['files'].items() if i['exists']}}


def qa_names_fix(ctx, mode, nodes, preview):
    rt = _rt()
    edit, emax = ctx.edit, ctx.emax
    options = _fix_options(ctx, mode, preview)
    nodes = _selected(nodes)
    state, plan = _fix_plan(ctx, nodes, options)
    done, skipped, ambiguous, findings = _fix_lists(ctx, plan, state)
    names = {o['key']: o['name'] for o in state['objects']}
    extra = {'options': options, 'layer': LAYER, 'failures': [dict(f, object=names[f['key']]) for f in plan['failures']],
             'issue': '#908'}
    keys = [o['key'] for o in plan['objects']]
    if mode == 'preview':
        objects = [edit.entry(k, names[k], findings.get(k, [])) for k in keys]
        return edit.report(FIX_TOOL, 'preview', objects, done, skipped, ambiguous,
                           state_hash=edit.fingerprint(state), extra=extra)
    edit.require_current(preview, state)
    p = preview['plan']
    if edit.fingerprint([p['done'], p['skipped'], p['ambiguous']]) != edit.fingerprint([done, skipped, ambiguous]):
        raise edit.StalePreview('the rename plan differs from the preview; run preview again')
    if not keys:
        raise ValueError('nothing to rename: every selected object is skipped or ambiguous')
    donor = None
    if options.get('donor'):
        donor = next(n for n in nodes if str(n.name) == options['donor'])
    by_key = {o['key']: o for o in plan['objects']}
    written, copies, applied = [], [], []
    def body():
        try:
            pairs = emax.export_copies([_node(k) for k in keys], layer=LAYER)
            copies.extend(c for _, c in pairs)
            copy_of = {_handle(n): c for n, c in pairs}
            for k, c in copy_of.items():
                o = by_key[k]
                if o.get('material_source') == 'donor':
                    c.material = rt.copy(donor.material)
                c.name = o['new']
            for m in plan['materials']:
                if m['action'] != 'rename':
                    continue
                mat = copy_of[m['key']].material
                target = mat if not m['path'] else _sub(mat, m['path'][0])
                target.name = m['new']
            made = {}
            for f in plan['files']:
                mat = copy_of[f['key']].material
                owner = mat if not f['sub'] else _sub(mat, f['sub'][0])
                if f['action'].startswith('keep'):  # V1: a foreign file holds the name; map stays on its source
                    continue
                tex = _get_texmap(owner, f['map'])
                if f['action'].startswith('clear'):
                    _set_texmap(owner, f['map'], None)
                    continue
                if f['action'] == 'copy':
                    dst = made.get(f['target'])
                    if dst is None:
                        dst = edit.new_path(f['target'])  # refuses if the file appeared since the preview
                        os.makedirs(os.path.dirname(dst), exist_ok=True)  # options.folder may be new (V4)
                        with open(f['source'], 'rb') as src:
                            data = src.read()
                        if hashlib.sha256(data).hexdigest() != f['source_sha256']:
                            raise RuntimeError('source changed since the preview: ' + f['source'])
                        edit.write_new(dst, data)
                        written.append(dst)
                        made[f['target']] = dst
                    tex.filename = dst
                elif f['action'].startswith('reuse'):
                    tex.filename = f['target']
                tex.name = f['name']
            objects = []
            for k in keys:
                c = copy_of[k]
                fnd = list(findings.get(k, []))
                fnd += _readback(ctx, c, by_key[k], [f for f in plan['files'] if f['key'] == k])
                objects.append(edit.entry(_handle(c), str(c.name), fnd))
                applied.append({'object': by_key[k]['old'], 'copy': str(c.name)})
            after = _fix_state(ctx, nodes)
            if edit.fingerprint(_working_view(after)['objects']) != edit.fingerprint(_working_view(state)['objects']):
                raise RuntimeError('working objects or their materials changed during apply')
            for path, info in _working_view(state)['files'].items():
                if _file_info(path) != info:
                    raise RuntimeError('an existing file changed during apply: ' + path)
            return objects
        except Exception:
            alive = [c for c in copies if rt.isValidNode(c)]
            if alive:
                rt.delete(alive)
            for path in written:
                if os.path.isfile(path):
                    os.remove(path)
            raise
    objects = in_session(emax, FIX_TOOL, body)
    extra = dict(extra, copies=applied, files_written=[{'path': w, 'sha256': _file_info(w)['sha256']} for w in written])
    return edit.report(FIX_TOOL, 'apply', objects, done, skipped, ambiguous, extra=extra)


def _sub(multi, sid):
    for i in range(len(multi.materialIDList)):
        if int(multi.materialIDList[i]) == int(sid):
            return multi.materialList[i]
    raise RuntimeError('sub-material ID {} missing on the copy'.format(sid))


def _readback(ctx, copy, obj, files):
    """Findings on the copy: its name, and every planned map points to an existing file in the source folder."""
    edit = ctx.edit
    out = []
    if str(copy.name) != obj['new']:
        out.append(edit.finding('name_fix_failed', (), 'copy readback name {!r} != {!r}'.format(str(copy.name), obj['new'])))
    for f in files:
        if f['action'].startswith('clear') or f['action'].startswith('keep'):
            continue
        mat = copy.material
        owner = mat if not f['sub'] else _sub(mat, f['sub'][0])
        tex = _get_texmap(owner, f['map'])
        path = str(tex.filename)
        if not os.path.isfile(path):
            out.append(edit.finding('name_fix_failed', (), 'map points to a missing file: ' + path))
        if f['target'] and os.path.normcase(os.path.dirname(path)) != os.path.normcase(os.path.dirname(f['target'])):
            out.append(edit.finding('name_fix_failed', (), 'map folder is not the planned folder: ' + path))
        if str(tex.name) != f['name']:
            out.append(edit.finding('name_fix_failed', (), 'map name {!r} != {!r}'.format(str(tex.name), f['name'])))
    return out
