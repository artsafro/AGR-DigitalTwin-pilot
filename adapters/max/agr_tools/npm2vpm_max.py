"""new-case: AGR Tools 1.0 (#1024) NPM -> VPM, 3ds Max side; owned by branch Q (improve/issue-1024-npm-to-vpm).

runtime.edits_100 calls `npm_to_vpm(ctx, mode, nodes, preview)` for npm.to_vpm (plan mode copy, 1.0.24).
ctx: agr (runtime globals), core (npm2vpm_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost). Import pymxs inside functions so this file loads under plain pytest.

preview: reads each selected NPM object (udim10_max.read_tri of branch M: evaluated mesh, world metres by
units.SystemScale, object-space vertices), its atlas (the diffuse Bitmaptexture of its material: PNG header only),
the correspondence table (options.table: a path, the JSON object or the rows; else `npm_table.json` next to the
atlas - the sidecar of npm.build, branch P) and, with options.window_ids, the window library of branch J
(windowgen_core: quarantined / duplicate types never offered). Plans the faces back (table or regions), the windows
and the materials (npm2vpm_core.plan). Nothing changes, nothing is written.
apply: re-reads and compares (state hash incl. sha256 of the table, the atlas and the window library), refuses on a
blocking finding (fail-closed, nothing written), writes the region crops (regions mode) into a NEW folder BEFORE any
scene change, then in ONE undo record (selection restored): VPM copies of body and glass (separate meshes, each from
UDIM 1001 as in the table) on layer `AGR_vpm` with Multi/Sub materials slot = library id (the library material of
the table row when it is in the scene, else a Standard with the row's map), the window planes as a copy on the
hidden layer `_npm_src`, one hidden master per window type (WINLIB_<id>, as win.place) and an instance per
recognised plane on WINDOW_placed / GLASS_placed. Reads every copy back and checks that the NPM object, its atlas and
the table did not change. A failure deletes the new nodes and files. No clearUndoBuffer, no stack collapse of an
original, no new MAXScript globals.
"""
import hashlib
import json
import os

TOOL = 'npm.to_vpm'
ISSUE = '#1024'
WIN_LAYERS = {'master': 'WINDOW_types', 'master_glass': 'GLASS_types', 'window': 'WINDOW_placed',
              'glass': 'GLASS_placed'}
MASTER_PROP = 'agr_window_master'  # the convention of win.place (branch J): masters are shared


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


def _gen(ctx):
    return ctx.agr._load_core('windowgen_core.py', 'agr_tools_windowgen_core')


def _sha(path):
    try:
        with open(path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError as exc:
        return 'unreadable: ' + exc.__class__.__name__


def atlas_path(n):
    """Diffuse Bitmaptexture file of the NPM material (Standard, or the one map shared by the Multi/Sub slots)."""
    rt = _rt()
    mat = n.material
    if mat is None:
        return None
    subs = list(mat.materialList) if rt.classOf(mat) == rt.MultiMaterial else [mat]
    found = []
    for s in subs:
        if s is None or not rt.isProperty(s, rt.name('diffuseMap')):
            continue
        dm = s.diffuseMap
        if dm is not None and rt.classOf(dm) == rt.Bitmaptexture and str(dm.filename):
            found.append(os.path.normpath(str(dm.filename)))
    found = sorted(set(found))
    return found[0] if len(found) == 1 else None


def atlas_info(core, path):
    if not path:
        return None
    try:
        with open(path, 'rb') as f:
            data = f.read()
    except OSError as exc:
        return {'error': '{} not found ({})'.format(path, exc.__class__.__name__)}
    try:
        w, h, depth, ctype = core.png_size(data)
    except ValueError as exc:
        return {'error': '{} is not a readable PNG ({})'.format(path, str(exc)[:60])}
    return {'w': w, 'h': h, 'depth': depth, 'color_type': ctype, 'sha256': hashlib.sha256(data).hexdigest()}


def load_table(core, opts, atlas):
    """(rows | None, source, sha256 | None) of the correspondence table; an unreadable or invalid table is an error
    (never a silent fall back to the regions)."""
    t = opts['table']
    if opts['mode'] == 'regions':
        return None, None, None
    if isinstance(t, (dict, list)):
        return core.table_rows(t), 'options.table', hashlib.sha256(
            json.dumps(t, sort_keys=True).encode('utf-8')).hexdigest()
    path = t
    if path is None and atlas:
        cand = os.path.join(os.path.dirname(atlas), core.TABLE_FILE)
        path = cand if os.path.isfile(cand) else None
    if path is None:
        return None, None, None
    with open(path, 'rb') as f:
        data = f.read()
    try:
        doc = json.loads(data.decode('utf-8'))
    except ValueError as exc:
        raise ValueError('correspondence table {} is not JSON: {}'.format(path, str(exc)[:80])) from None
    return core.table_rows(doc), path, hashlib.sha256(data).hexdigest()


def window_types(ctx, opts):
    """(offerable types [{'id', 'width_m', 'height_m'}], library) when window_ids are given, else ([], None)."""
    if not opts['window_ids']:
        return [], None
    gen = _gen(ctx)
    lib = gen.load_library(gen.library_dir(opts['library']))
    offer = set(gen.offerable(gen.library_report(lib['types'], lib['standard']), tuple(opts['statuses'])))
    if opts['window_types'] is not None:
        missing = sorted(set(opts['window_types']) - set(lib['by_id']))
        if missing:
            raise ValueError('options.window_types not in the library: ' + ', '.join(missing))
        offer &= set(opts['window_types'])
    types = [{'id': t, 'width_m': float(lib['by_id'][t]['width_m']), 'height_m': float(lib['by_id'][t]['height_m'])}
             for t in sorted(offer)]
    return types, lib


def read(ctx, nodes, opts):
    """[(node, mesh, atlas path, atlas info, (rows, source, sha))], skipped, k (m per unit)."""
    edit, core = ctx.edit, ctx.core
    rd = _reader(ctx)
    k = ctx.host.m_per_unit()
    out, skipped = [], []
    for n in rd.target_nodes(nodes):
        if not rd.is_geometry(n):
            skipped.append(edit.skipped(str(n.name), 'not geometry'))
            continue
        mesh = rd.read_tri(n, k)
        path = atlas_path(n)
        info = atlas_info(core, path)
        out.append((n, mesh, path, info, load_table(core, opts, path)))
    if not out:
        raise ValueError('nothing to convert: ' + ('; '.join(s['item'] + ': ' + s['reason'] for s in skipped)
                                                   or 'select the NPM objects'))
    return out, skipped, k


def plan_all(ctx, items, opts, types):
    edit, core = ctx.edit, ctx.core
    rd = _reader(ctx)
    plans, entries, done = [], [], []
    for n, mesh, path, info, (rows, src, _sha_t) in items:
        p = core.plan(mesh, opts, rows, info, types)
        plans.append(p)
        entries.append(edit.entry(rd.handle(n), str(n.name), [
            edit.finding(code, [f + 1 for f in faces], detail) for code, faces, detail in p['findings']]))
        wins = [{'element': w['element'], 'faces': len(w['faces']), 'status': w['match']['status'] if w['match']
                 else 'frame', 'type': w['match']['type'] if w['match'] else None,
                 'rotated': bool(w['match'] and w['match']['rotated']),
                 'size_m': [round(w['frame']['w'], 4), round(w['frame']['h'], 4)] if w['frame'] else None,
                 'centre_m': [round(c, 5) for c in w['frame']['origin']] if w['frame'] else None,
                 'err_m': w['match']['err'] if w['match'] else None} for w in p['windows']]
        done.append(dict(p['summary'], object=str(n.name), atlas=path, table=src, windows_list=wins,
                         blocking=sorted({f[0] for f in core.blocking(p['findings'])})))
    return plans, entries, done


def _state(ctx, items, lib):
    rd = _reader(ctx)
    return {'objects': [rd._state(ctx, n, mesh) for n, mesh, _p, _i, _t in items],
            'atlas': [(p, (i or {}).get('sha256') or (i or {}).get('error')) for _n, _m, p, i, _t in items],
            'tables': [(t[1], t[2]) for *_x, t in items],
            'library': lib['sha256'] if lib else None}


def _layer(name):
    rt = _rt()
    layer = rt.LayerManager.getLayerFromName(name)
    if layer is None or layer == rt.undefined:
        layer = rt.LayerManager.newLayerFromName(name)
    return layer


def _free_name(base):
    rt = _rt()
    return base if rt.getNodeByName(base) is None else str(rt.uniqueName(base + '_'))


def build_node(part, name, tm):
    """Editable_Mesh of a planned part in the NPM object space (vertices in system units), transform `tm`."""
    rt = _rt()
    node = rt.mesh(numverts=len(part['verts']), numfaces=len(part['tris']))
    for i, p in enumerate(part['verts'], 1):
        rt.setVert(node, i, rt.point3(float(p[0]), float(p[1]), float(p[2])))
    for f, (t, mid) in enumerate(zip(part['tris'], part['mat_ids']), 1):
        rt.setFace(node, f, t[0] + 1, t[1] + 1, t[2] + 1)
        rt.setFaceMatID(node, f, int(mid))
    rt.meshop.setMapSupport(node, 1, True)
    rt.meshop.setNumMapVerts(node, 1, len(part['uvs']))
    for i, (u, v) in enumerate(part['uvs'], 1):
        rt.meshop.setMapVert(node, 1, i, rt.point3(float(u), float(v), 0.0))
    for f, t in enumerate(part['uv_tris'], 1):
        rt.meshop.setMapFace(node, 1, f, rt.point3(t[0] + 1, t[1] + 1, t[2] + 1))
    rt.update(node)
    node.transform = tm
    node.name = name
    return node


def _scene_material(name):
    """The library material of that name already in the scene (a sub-material of a scene Multi/Sub too), or None."""
    rt = _rt()
    if not name:
        return None
    for m in list(rt.sceneMaterials):
        if m is None:
            continue
        if str(m.name) == name and rt.classOf(m) != rt.MultiMaterial:
            return m
        if rt.classOf(m) == rt.MultiMaterial:
            for s in list(m.materialList):
                if s is not None and str(s.name) == name:
                    return s
    return None


def multi_material(name, specs, folder=None):
    """Multi/Sub of an output part: slot ID = library id; the scene's library material, else a Standard with the
    map (the table's map, or the region crop in `folder`). Returns (material, {id: 'scene'|'new'})."""
    rt = _rt()
    ids = sorted(specs)
    mm = rt.MultiMaterial(numsubs=len(ids))
    mm.name = name
    origin = {}
    for i, mid in enumerate(ids):
        spec = specs[mid]
        sub = _scene_material(spec['name']) if folder is None else None
        origin[mid] = 'scene' if sub is not None else 'new'
        if sub is None:
            sub = rt.StandardMaterial(name=spec['name'])
            if spec['map']:
                path = os.path.join(folder, spec['map']) if folder else spec['map']
                tex = rt.Bitmaptexture(filename=path)
                tex.name = os.path.splitext(os.path.basename(path))[0]
                sub.diffuseMap = tex
                sub.showInViewport = True
            elif spec['kind'] == 'glass':
                sub.diffuse = rt.color(255, 255, 255)
                sub.opacity = 30
        mm.materialList[i] = sub
        mm.materialIDList[i] = mid
    return mm, origin


def _matrix(rows, mpu):
    rt = _rt()
    k = 1.0 / mpu
    return rt.Matrix3(rt.Point3(*rows[0]), rt.Point3(*rows[1]), rt.Point3(*rows[2]),
                      rt.Point3(rows[3][0] * k, rows[3][1] * k, rows[3][2] * k))


def _rows_of(tm, mpu):
    def unit(p):
        v = [float(p.x), float(p.y), float(p.z)]
        ln = sum(c * c for c in v) ** 0.5 or 1.0
        return [c / ln for c in v]
    return [unit(tm.row1), unit(tm.row2), unit(tm.row3),
            [float(tm.row4.x) * mpu, float(tm.row4.y) * mpu, float(tm.row4.z) * mpu]]


def _type_mesh_node(data, name, mpu):
    """Editable_Mesh of a windowgen part mesh (metres, quads fan-triangulated, inner diagonals hidden)."""
    rt = _rt()
    k = 1.0 / mpu
    verts = [rt.Point3(v[0] * k, v[1] * k, v[2] * k) for v in data['verts']]
    tris, ids, vis = [], [], []
    for f, mid in zip(data['faces'], data['mat_ids']):
        for i in range(1, len(f) - 1):
            tris.append(rt.Point3(f[0] + 1, f[i] + 1, f[i + 1] + 1))
            ids.append(mid)
            vis.append((i == 1, True, i == len(f) - 2))
    node = rt.mesh(vertices=rt.Array(*verts), faces=rt.Array(*tris), materialIDs=rt.Array(*ids))
    for fi, (a, b, c) in enumerate(vis, 1):
        rt.setEdgeVis(node, fi, 1, a)
        rt.setEdgeVis(node, fi, 2, b)
        rt.setEdgeVis(node, fi, 3, c)
    rt.update(node)
    node.name = name
    return node


def master(gen, lib, tid, mpu, cache, made):
    """(frame master, glass master | None, type mesh) of a type: the WINLIB_<id> of this library (win.place), else
    built hidden on WINDOW_types / GLASS_types."""
    if tid in cache:
        return cache[tid]
    rt = _rt()
    mesh = gen.build_type(lib['by_id'][tid], lib['standard'])
    stamp = lib['sha256']['standard.json'][:16]
    name = 'WINLIB_' + tid
    found = rt.getNodeByName(name)
    if found is not None and str(rt.getUserProp(found, MASTER_PROP)) == stamp and \
            str(rt.getUserProp(found, 'agr_window_type')) == tid:
        cache[tid] = (found, rt.getNodeByName(name + '_glass'), mesh)
        return cache[tid]
    frame = _type_mesh_node(gen.part_mesh(mesh, 'frame'), _free_name(name), mpu)
    made.append(frame)
    glass = None
    if mesh['parts']['glass']:
        glass = _type_mesh_node(gen.part_mesh(mesh, 'glass'), _free_name(name + '_glass'), mpu)
        made.append(glass)
    for node, role, layer in ((frame, 'window', WIN_LAYERS['master']), (glass, 'glass', WIN_LAYERS['master_glass'])):
        if node is None:
            continue
        rt.setUserProp(node, 'agr_role', role)
        rt.setUserProp(node, 'agr_window_type', tid)
        rt.setUserProp(node, MASTER_PROP, stamp)
        rt.setUserProp(node, 'agr_face_axis', mesh['face_axis'])
        _layer(layer).addNode(node)
        node.isHidden = True
    cache[tid] = (frame, glass, mesh)
    return cache[tid]


def _out_dir(o, name):
    rt = _rt()
    if o.get('out_dir'):
        return os.path.join(o['out_dir'], name + '_VPM')
    if not str(rt.maxFileName):
        return None
    return os.path.join(str(rt.maxFilePath), os.path.splitext(str(rt.maxFileName))[0] + '_' + name + '_VPM')


def write_crops(ctx, p, atlas, name):
    """Region crops of the regions mode as NEW files (never overwrite): {'folder', 'files'}."""
    edit, core = ctx.edit, ctx.core
    folder = _out_dir(p['options'], name)
    if folder is None:
        raise ValueError('scene not saved and no options.out_dir: the region crops have no folder (nothing written)')
    folder = edit.new_path(folder, version=True)
    with open(atlas, 'rb') as f:
        data = f.read()
    os.makedirs(folder)
    files = []
    try:
        for mid, reg in sorted(p['regions'].items()):
            path = edit.write_new(os.path.join(folder, core.crop_name(name, mid, reg['udim'])),
                                  core.crop_png(data, reg['box_px']))
            files.append({'path': path, 'library_id': mid, 'udim': reg['udim'], 'box_px': reg['box_px']})
    except Exception:
        _remove(files, folder)
        raise
    return {'folder': folder, 'files': files}


def _remove(files, folder):
    for f in files:
        if os.path.exists(f['path']):
            os.remove(f['path'])
    if folder and os.path.isdir(folder) and not os.listdir(folder):
        os.rmdir(folder)


def npm_to_vpm(ctx, mode, nodes, preview):
    edit, core, emax = ctx.edit, ctx.core, ctx.emax
    opts = core.options(dict(preview['plan']['options']) if mode == 'apply' else ctx.options)
    types, lib = window_types(ctx, opts)
    items, skipped, k = read(ctx, nodes, opts)
    plans, entries, done = plan_all(ctx, items, opts, types)
    state = _state(ctx, items, lib)
    extra = {'options': opts, 'layer': core.LAYER, 'src_layer': core.SRC_LAYER, 'issue': ISSUE, 'unit_m': k,
             'library': {'folder': lib['folder'], 'sha256': lib['sha256']} if lib else None}
    if mode == 'preview':
        return edit.report(TOOL, 'preview', entries, done, skipped, (), state_hash=edit.fingerprint(state),
                           extra=extra)
    edit.require_current(preview, state)
    if edit.fingerprint(preview['plan']['done']) != edit.fingerprint(done):
        raise edit.StalePreview('the NPM -> VPM plan differs from the preview; run preview again')
    stop = [(str(n.name), core.blocking(p['findings'])) for (n, *_r), p in zip(items, plans) if core.blocking(p['findings'])]
    if stop:
        raise ValueError('nothing converted: the preview has blocking findings (fail-closed, nothing written): ' +
                         '; '.join('{}: {}'.format(nm, ', '.join(sorted({f[0] for f in fs}))) for nm, fs in stop))
    if not any(p['parts'] or p['windows'] for p in plans):
        raise ValueError('nothing to convert: no face goes back to a VPM part and no window plane')
    crops = []
    try:
        for (n, mesh, path, _i, _t), p in zip(items, plans):
            nm = p['options']['name'] or str(n.name)
            crops.append(write_crops(ctx, p, path, nm) if p['mode'] == 'regions' and p['regions'] else None)
    except Exception:
        for c in crops:
            if c:
                _remove(c['files'], c['folder'])
        raise
    rt = _rt()
    rd = _reader(ctx)
    gen = _gen(ctx) if lib else None
    made, objects, applied = [], [], []

    def body():
        try:
            cache = {}
            for (n, mesh, path, _i, _t), p, crop in zip(items, plans, crops):
                nm = p['options']['name'] or str(n.name)
                tm = n.objectTransform
                row = {'object': str(n.name), 'copies': [], 'windows': [], 'materials': {}}
                for part in sorted(p['parts']):
                    pm = p['parts'][part]
                    cname = _free_name(nm + ('_VPM' if part == 'body' else '_VPM_glass'))
                    c = build_node(pm, cname, tm)
                    made.append(c)
                    _layer(core.LAYER).addNode(c)
                    rt.setUserProp(c, 'agr_role', 'glass' if part == 'glass' else 'body')
                    rt.setUserProp(c, 'agr_npm_source', str(n.name))
                    mat, origin = multi_material('M_' + cname, core.materials_of(p, part, nm),
                                                 crop['folder'] if crop else None)
                    c.material = mat
                    back = rd.read_tri(c, k)
                    f2, measured = core.measure(back, pm)
                    objects.append(edit.entry(rd.handle(c), str(c.name), [edit.finding(*x) for x in f2]))
                    row['copies'].append(dict(measured, copy=str(c.name), part=part, ids=sorted(set(pm['mat_ids']))))
                    row['materials'][part] = {str(kk): v for kk, v in sorted(origin.items())}
                wf = sorted({f for w in p['windows'] for f in w['faces']})
                if wf:
                    src = {'faces': wf, 'verts': [], 'tris': [], 'mat_ids': [], 'uvs': [], 'uv_tris': []}
                    vmap, umap = {}, {}
                    for f in wf:
                        src['tris'].append([vmap.setdefault(i, len(vmap)) for i in mesh['tris'][f]])
                        src['uv_tris'].append([umap.setdefault(i, len(umap)) for i in mesh['uv_tris'][f]]
                                              if mesh['uv_tris'] else [0, 0, 0])
                        src['mat_ids'].append(mesh['mat_ids'][f])
                    src['verts'] = [mesh['local'][i] for i in sorted(vmap, key=vmap.get)]
                    src['uvs'] = [mesh['uvs'][i] for i in sorted(umap, key=umap.get)] if mesh['uv_tris'] else [[0, 0]]
                    s = build_node(src, _free_name(nm + '_npm_win_src'), tm)
                    made.append(s)
                    s.material = n.material
                    _layer(core.SRC_LAYER).addNode(s)
                    rt.setUserProp(s, 'agr_npm_source', str(n.name))
                    s.isHidden = True
                    _layer(core.SRC_LAYER).isHidden = True
                for w in p['windows']:
                    if not w['match'] or w['match']['status'] != 'ok':
                        continue
                    tid = w['match']['type']
                    fr_master, gl_master, tmesh = master(gen, lib, tid, k, cache, made)
                    rows = core.window_rows(w, tmesh['size_m'], tmesh['face_axis'], p['options']['recess_m'])
                    num = len([x for x in made if str(x.name).startswith('WIN_NPM_')]) + 1
                    for mnode, role, prefix, layer in ((fr_master, 'window', 'WIN_NPM_', WIN_LAYERS['window']),
                                                       (gl_master, 'glass', 'GLASS_NPM_', WIN_LAYERS['glass'])):
                        if mnode is None:
                            continue
                        inst = rt.instance(mnode)
                        made.append(inst)
                        inst.name = _free_name('{}{:03d}'.format(prefix, num))
                        inst.transform = _matrix(rows, k)
                        inst.isHidden = False
                        rt.setUserPropBuffer(inst, '')
                        rt.setUserProp(inst, 'agr_role', role)
                        rt.setUserProp(inst, 'agr_window_type', tid)
                        rt.setUserProp(inst, 'agr_face_axis', tmesh['face_axis'])
                        rt.setUserProp(inst, 'agr_npm_source', str(n.name))
                        _layer(layer).addNode(inst)
                        if role != 'window':
                            continue
                        got = _rows_of(inst.transform, k)
                        W, D, H = tmesh['size_m']
                        wp = ctx.agr._load_core('winplace_core.py', 'agr_tools_winplace_core')
                        c = wp.apply_rows(got, [W / 2.0, D / 2.0, H / 2.0])
                        fr = w['frame']
                        want = [o - z * p['options']['recess_m'] for o, z in zip(fr['origin'], fr['z'])]
                        err = sum((a - b) ** 2 for a, b in zip(c, want)) ** 0.5
                        ang = wp.angle_deg(wp.face_normal_world(got, tmesh['face_axis']), fr['z'])
                        fs = []
                        if err > 0.005:
                            fs.append(edit.finding('readback', [], 'window centre {:.2f} mm off the plane'.format(err * 1000)))
                        if ang > 0.5:
                            fs.append(edit.finding('readback', [], 'window normal {:.3f} deg off the plane'.format(ang)))
                        objects.append(edit.entry(rd.handle(inst), str(inst.name), fs))
                        row['windows'].append({'instance': str(inst.name), 'type': tid, 'rotated': w['match']['rotated'],
                                               'centre_mm': round(err * 1000, 3), 'normal_deg': round(ang, 4)})
                applied.append(row)
            now = _state(ctx, [(n, rd.read_tri(n, k), pth, atlas_info(core, pth), t)
                               for n, _m, pth, _i, t in items], lib)
            if edit.fingerprint(now) != edit.fingerprint(state):
                raise RuntimeError('the NPM objects, the atlas or the table changed during apply')
        except Exception:
            alive = [c for c in made if rt.isValidNode(c)]
            if alive:
                rt.delete(alive)
            raise
    try:
        _session_core().in_session(emax, TOOL, body)
    except Exception:
        for c in crops:
            if c:
                _remove(c['files'], c['folder'])
        raise
    extra = dict(extra, copies=[r['copies'] for r in applied], crops=[c for c in crops if c],
                 readback=applied)
    return edit.report(TOOL, 'apply', objects, done, skipped, (), extra=extra)
