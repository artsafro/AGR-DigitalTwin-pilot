"""new-case: AGR Tools 1.0 (#1024) VPM -> NPM atlas, 3ds Max side; owned by branch P (improve/issue-1024-npm).

runtime.edits_100 calls `npm_build(ctx, mode, nodes, preview)` for `npm.build` (plan mode copy + file, 1.0.22).
ctx: agr (runtime globals), core (npm_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost). Import pymxs inside functions so this file loads under plain pytest.

preview: reads the selected VPM objects (body first, glass `*_glass*` after; udim10_max.read_tri, metres by
units.SystemScale), the material of every ID (Multi/Sub by ID or one material: the diffuse Bitmaptexture file or the
diffuse colour) and the PNG headers of the maps, and plans the atlas (npm_core.plan). Nothing changes, nothing is
written. Findings (missing map, no UV, overflow...) make the build fail closed.
apply: re-reads and compares (state hash incl. sha256 of every map, planned rows), renders the atlas from the
full-resolution maps (atlas_core.rigid_raster) BEFORE touching the scene, writes it into a NEW folder (never
overwrite: edit_core.new_path / write_new) with `npm_table.json` (correspondence table), then in ONE undo record
(selection restored) makes export copies on layer `AGR_npm`, writes the atlas UVs into channel 1 of each copy,
attaches the copies into ONE NPM object (glass joins it, IDs kept), binds one Standard material with the atlas, reads
the copy back (texel, rigid transfer, cells) and checks that the VPM objects and maps did not change. A failure
deletes the copies and the new files. No clearUndoBuffer, no stack collapse of an original, no new MAXScript globals.
"""
import hashlib
import os

TOOL = 'npm.build'
LAYER = 'AGR_npm'
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


def _texqa(ctx):
    return ctx.agr._load_core('texqa_core.py', 'agr_tools_texqa_core')


def _checks(ctx):
    return ctx.agr._load_core('checks_core.py', 'agr_tools_checks_core')


def _sub_of(mat, mid):
    """Sub-material of an ID (Multi/Sub by its ID list, else the material itself)."""
    rt = _rt()
    if mat is None:
        return None
    if rt.classOf(mat) == rt.MultiMaterial:
        ids = [int(i) for i in mat.materialIDList]
        if mid in ids:
            return mat.materialList[ids.index(mid)]
        return None
    return mat


def material_specs(n, ids):
    """{id: {'name', 'map': file | None, 'color': [r, g, b]}} of a node (no bitmap is opened here)."""
    rt = _rt()
    out = {}
    for mid in sorted(set(ids)):
        sub = _sub_of(n.material, mid)
        spec = {'name': str(sub.name) if sub is not None else None, 'map': None, 'color': [128, 128, 128]}
        if sub is not None:
            dm = getattr(sub, 'diffuseMap', None) if rt.isProperty(sub, rt.name('diffuseMap')) else None
            if dm is not None and rt.classOf(dm) == rt.Bitmaptexture and str(dm.filename):
                spec['map'] = os.path.normpath(str(dm.filename))
            if rt.isProperty(sub, rt.name('diffuse')):
                c = sub.diffuse
                spec['color'] = [int(round(float(c.r))), int(round(float(c.g))), int(round(float(c.b)))]
        out[mid] = spec
    return out


def map_infos(ctx, paths):
    """{path: {'w', 'h', 'sha256'} | {'error'}}: PNG headers only (preview reads no pixels)."""
    out = {}
    for p in sorted(set(x for x in paths if x)):
        try:
            with open(p, 'rb') as f:
                data = f.read()
        except OSError as exc:
            out[p] = {'error': 'not found ({})'.format(exc.__class__.__name__)}
            continue
        try:
            w, h, _d, _c, _a = _checks(ctx).png_info(data)
        except ValueError as exc:
            out[p] = {'error': 'not a readable PNG ({})'.format(str(exc)[:60])}
            continue
        out[p] = {'w': int(w), 'h': int(h), 'sha256': hashlib.sha256(data).hexdigest()}
    return out


def read_meshes(ctx, nodes, glass_part=True):
    """(meshes, by_index nodes, skipped, state) in the build order: body objects first, then `*_glass*` objects."""
    edit = ctx.edit
    rd = _reader(ctx)
    k = ctx.host.m_per_unit()
    nodes = rd.target_nodes(nodes)
    body, glass, skipped = [], [], []
    for n in nodes:
        if not rd.is_geometry(n):
            skipped.append(edit.skipped(str(n.name), 'not geometry'))
            continue
        (glass if glass_part and '_glass' in str(n.name).lower() else body).append(n)
    meshes, order, state = [], [], []
    for n in body + glass:
        mesh = rd.read_tri(n, k)
        meshes.append({'key': rd.handle(n), 'name': str(n.name), 'part': 'glass' if n in glass else 'body',
                       'verts': mesh['verts'], 'tris': mesh['tris'], 'mat_ids': mesh['mat_ids'], 'uvs': mesh['uvs'],
                       'uv_tris': mesh['uv_tris'], 'materials': material_specs(n, mesh['mat_ids'])})
        order.append(n)
        state.append(rd._state(ctx, n, mesh))
    if not meshes:
        raise ValueError('nothing to build: ' + ('; '.join(s['item'] + ': ' + s['reason'] for s in skipped)
                                                 or 'select the objects'))
    return meshes, order, skipped, state, k


def entries_of(edit, meshes, findings):
    """Report objects: findings of the combined mesh mapped back to each source object (1-based faces)."""
    base, out = 0, []
    for m in meshes:
        n = len(m['tris'])
        f2 = []
        for code, faces, detail in findings:
            mine = [f - base + 1 for f in faces if base <= f < base + n]
            if mine or not faces:
                f2.append(edit.finding(code, mine, detail))
        out.append(edit.entry(m['key'], m['name'], f2))
        base += n
    return out


def split_uv(p, mi):
    """(uvs, uv_tris 0-based) of the planned atlas UV for the faces of source mesh `mi` (local numbering)."""
    cm = p['combined']
    local, uvs, tris = {}, [], []
    for f, (m, _face) in enumerate(cm['src']):
        if m != mi:
            continue
        ids = []
        for t in p['uv_tris'][f]:
            if t not in local:
                local[t] = len(uvs)
                uvs.append(p['uvs'][t])
            ids.append(local[t])
        tris.append(ids)
    return uvs, tris


def write_uv(c, uvs, tris):
    """Channel 1 of an Editable_Mesh copy := the planned atlas UV (faces unchanged)."""
    rt = _rt()
    m = c  # the Editable_Mesh node (meshop works on the node, as M_build.build_node)
    if int(c.mesh.numfaces) != len(tris):
        raise RuntimeError('copy {} has {} faces, the plan {}'.format(c.name, int(c.mesh.numfaces), len(tris)))
    rt.meshop.setMapSupport(m, 1, True)
    rt.meshop.setNumMapVerts(m, 1, len(uvs))
    for i, (u, v) in enumerate(uvs, 1):
        rt.meshop.setMapVert(m, 1, i, rt.point3(float(u), float(v), 0.0))
    for f, t in enumerate(tris, 1):
        rt.meshop.setMapFace(m, 1, f, rt.point3(t[0] + 1, t[1] + 1, t[2] + 1))
    rt.update(c)


def write_combined(t, others, p):
    """Replace the Editable_Mesh of copy `t` by the combined plan mesh: vertices of t and of every other copy (in
    order, brought into t's object space), faces / ids / edge visibility of each copy, channel 1 = atlas UV."""
    rt = _rt()
    cm = p['combined']
    inv = rt.inverse(t.objectTransform)
    verts, faces, vis = [], [], []
    for c in [t] + list(others):
        m = c.mesh
        tm = c.objectTransform
        base = len(verts)
        for i in range(1, int(m.numverts) + 1):
            q = rt.getVert(m, i) if c == t else rt.getVert(m, i) * tm * inv
            verts.append(q)
        for f in range(1, int(m.numfaces) + 1):
            g = rt.getFace(m, f)
            faces.append((int(g.x) + base, int(g.y) + base, int(g.z) + base))
            vis.append(tuple(bool(rt.getEdgeVis(m, f, e)) for e in (1, 2, 3)))
    if len(verts) != len(cm['verts']) or len(faces) != len(cm['tris']):
        raise RuntimeError('copies have {} verts / {} faces, the plan {} / {}'.format(
            len(verts), len(faces), len(cm['verts']), len(cm['tris'])))
    if [list(x) for x in faces] != [[i + 1 for i in tr] for tr in cm['tris']]:
        raise RuntimeError('copy topology differs from the planned combined mesh')
    m = rt.TriMesh()
    rt.setNumVerts(m, len(verts))
    rt.setNumFaces(m, len(faces))
    for i, q in enumerate(verts, 1):
        rt.setVert(m, i, q)
    for f, (tri, mid, ev) in enumerate(zip(faces, cm['mat_ids'], vis), 1):
        rt.setFace(m, f, tri[0], tri[1], tri[2])
        rt.setFaceMatID(m, f, mid)
        for e in range(3):
            rt.setEdgeVis(m, f, e + 1, ev[e])
    rt.meshop.setMapSupport(m, 1, True)
    rt.meshop.setNumMapVerts(m, 1, len(p['uvs']))
    for i, (u, v) in enumerate(p['uvs'], 1):
        rt.meshop.setMapVert(m, 1, i, rt.point3(float(u), float(v), 0.0))
    for f, tri in enumerate(p['uv_tris'], 1):
        rt.meshop.setMapFace(m, 1, f, rt.point3(tri[0] + 1, tri[1] + 1, tri[2] + 1))
    t.mesh = m
    rt.update(t)


def read_pixels(ctx, p):
    """{group key: {'w', 'h', 'rgb', 'alpha'}} from the FULL-resolution PNG files of the texture groups."""
    tq = _texqa(ctx)
    out = {}
    for g in p['groups']:
        if g['kind'] != 'texture':
            continue
        with open(g['map'], 'rb') as f:
            pic = tq.read_png(f.read())
        rgb = pic.rgb()
        if len(rgb) != pic.w * pic.h * 3:
            raise ValueError('map {} decoded to a partial image'.format(g['map']))
        out[g['key']] = {'w': pic.w, 'h': pic.h, 'rgb': rgb, 'alpha': pic.alpha()}
    return out


def _out_dir(ctx, o, stem):
    rt = _rt()
    if o.get('out_dir'):
        return os.path.join(o['out_dir'], stem), ''
    if not str(rt.maxFileName):
        return None, 'scene not saved and no options.out_dir: the atlas has no folder (nothing written)'
    return os.path.join(str(rt.maxFilePath), os.path.splitext(str(rt.maxFileName))[0] + '_' + stem), ''


def write_files(ctx, p, img, folder, name, core):
    """Atlas PNG (24-bit RGB), separate grey opacity when a map has alpha, and the table: all NEW files."""
    edit, tq = ctx.edit, _texqa(ctx)
    os.makedirs(folder)
    dname, oname, mname = core.files_of(name, img['size'], img['alpha'] is not None)
    files = []
    path = edit.write_new(os.path.join(folder, dname), tq.write_png(img['size'], img['size'], img['rgb'], 3))
    files.append({'path': path, 'kind': 'diffuse', 'size': img['size']})
    if img['alpha'] is not None:
        path = edit.write_new(os.path.join(folder, oname), tq.write_png(img['size'], img['size'], img['alpha'], 1))
        files.append({'path': path, 'kind': 'opacity', 'size': img['size']})
    table = core.table_json(p, ctx.host.doc(), core.TOOL + ' core 1.0', [os.path.basename(f['path']) for f in files])
    table['sources_px'] = img['sources']
    path = edit.write_new(os.path.join(folder, 'npm_table.json' if core.TOOL == 'npm.build' else 'strip_table.json'),
                          (edit.canonical(table) + '\n').encode('ascii'))
    files.append({'path': path, 'kind': 'table'})
    return files, mname


def bind(copy, files, mname):
    rt = _rt()
    mat = rt.StandardMaterial(name=mname)
    tex = rt.Bitmaptexture(filename=next(f['path'] for f in files if f['kind'] == 'diffuse'))
    tex.name = os.path.splitext(os.path.basename(tex.filename))[0]
    mat.diffuseMap = tex
    op = [f['path'] for f in files if f['kind'] == 'opacity']
    if op:
        mat.opacityMap = rt.Bitmaptexture(filename=op[0])
    mat.showInViewport = True
    copy.material = mat


def run(ctx, mode, nodes, preview, tool, layer, attach, stem):
    """Shared glue of npm.build (attach=True: one NPM object) and atlas.facade_strip (one copy per object)."""
    edit, core, emax = ctx.edit, ctx.core, ctx.emax
    if mode == 'apply':
        ctx.options = dict(preview['plan']['options'])
    meshes, order, skipped, state, k = read_meshes(ctx, nodes, glass_part=attach)
    paths = [s['map'] for m in meshes for s in m['materials'].values()]
    maps = map_infos(ctx, paths)
    state = {'objects': state, 'maps': {p: maps[p].get('sha256') or maps[p].get('error') for p in sorted(maps)}}
    p = core.plan(meshes, ctx.options, maps)
    o = p['options']
    entries = entries_of(edit, meshes, p['findings'])
    done = []
    if not p['findings']:
        done.append(dict(p['summary'], objects=[m['name'] for m in meshes], table=p['table']))
    name = o.get('name') or (meshes[0]['name'] if attach else meshes[0]['name'] + '_strip')
    extra = {'options': o, 'layer': layer, 'issue': ISSUE, 'unit_m': k, 'maps': {
        x: {kk: v for kk, v in info.items() if kk != 'sha256'} for x, info in sorted(maps.items())}}
    if p.get('strips') is not None:
        extra['strips'] = {key: len(v) for key, v in p['strips'].items()}
    if mode == 'preview':
        return edit.report(tool, 'preview', entries, done, skipped, (), state_hash=edit.fingerprint(state),
                           extra=extra)
    edit.require_current(preview, state)
    if edit.fingerprint(preview['plan']['done']) != edit.fingerprint(done):
        raise edit.StalePreview('the atlas plan differs from the preview; run preview again')
    if p['findings'] or not done:
        raise ValueError('nothing to build: the preview has findings (fail-closed, nothing written)')
    folder, reason = _out_dir(ctx, o, stem)
    if folder is None:
        raise ValueError(reason)
    img = core.atlas.rigid_raster(p['atlas'], p['groups'], read_pixels(ctx, p))  # before any scene change
    folder = edit.new_path(folder, version=True)
    files, mname = write_files(ctx, p, img, folder, name, core)
    rt = _rt()
    rd = _reader(ctx)
    copies, objects, applied = [], [], []

    def body():
        try:
            pairs = emax.export_copies(order, suffix='_NPM_' if attach else '_STRIP_', layer=layer)
            for _src, c in pairs:
                copies.append(c)
                rt.convertToMesh(c)
            targets = copies[:1] if attach else list(copies)
            if attach:
                # one NPM object: the combined mesh of the plan (body faces, then glass) is written into the first
                # copy (other copies' vertices brought into its object space), the other copies are deleted - all in
                # the same undo record. meshop.attach is not used: after it one undo did not remove the run
                # (job 20261106-062347-9524f5c1).
                t = copies[0]
                write_combined(t, copies[1:], p)
                rt.delete(copies[1:])
                if o.get('name'):
                    t.name = rt.uniqueName(o['name'])
            else:
                for mi, c in enumerate(copies):
                    write_uv(c, *split_uv(p, mi))
            base = 0
            for c in targets:
                bind(c, files, mname)
                back = rd.read_tri(c, k)
                sub = p if attach else _slice(p, base, len(back['tris']))
                base += len(back['tris'])
                f2, measured = core.measure(back, sub)
                objects.append(edit.entry(rd.handle(c), str(c.name), [edit.finding(*x) for x in f2]))
                applied.append(dict(measured, copy=str(c.name)))
            now = {'objects': [rd._state(ctx, n, rd.read_tri(n, k)) for n in order],
                   'maps': {x: v.get('sha256') or v.get('error') for x, v in sorted(map_infos(ctx, paths).items())}}
            if edit.fingerprint(now) != edit.fingerprint(state):
                raise RuntimeError('VPM objects or maps changed during apply')
        except Exception:
            alive = [c for c in copies if rt.isValidNode(c)]
            if alive:
                rt.delete(alive)
            raise
    try:
        _session_core().in_session(emax, tool, body)
    except Exception:
        for f in files:
            if os.path.exists(f['path']):
                os.remove(f['path'])
        if os.path.isdir(folder) and not os.listdir(folder):
            os.rmdir(folder)
        raise
    extra = dict(extra, copies=[str(c.name) for c in copies if rt.isValidNode(c)], files=files, out_dir=folder,
                 readback=applied)
    return edit.report(tool, 'apply', objects, done, skipped, (), extra=extra)


def _slice(p, base, n):
    """Plan view of one object of a combined plan (faces base..base+n) for the per-copy readback."""
    cm = p['combined']
    sub_cm = {'tris': [[i for i in t] for t in cm['tris'][base:base + n]], 'mat_ids': cm['mat_ids'][base:base + n],
              'uvs': cm['uvs'], 'uv_tris': cm['uv_tris'][base:base + n], 'verts': cm['verts']}
    out = dict(p, combined=sub_cm)
    if p.get('pattern_uv') is not None:
        out['pattern_uv'] = p['pattern_uv'][base:base + n]
    return out


def npm_build(ctx, mode, nodes, preview):
    return run(ctx, mode, nodes, preview, TOOL, LAYER, True, 'NPM')
