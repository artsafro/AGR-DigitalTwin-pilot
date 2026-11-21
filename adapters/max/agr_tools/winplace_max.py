"""new-case: AGR Tools 1.0 (#1024) windows by opening markers, 3ds Max side; owned by branch J (improve/issue-1024-windows).

runtime.edits_100 calls `win_place(ctx, mode, nodes, preview)` for win.place (plan mode `undo`).
ctx: agr (runtime globals), core (winplace_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost: ObjRef, user props, one undo record).
Import pymxs inside functions so this file loads under plain pytest.

Input: the selected walls (geometry with opening borders) and/or opening markers OPEN_<nnn>. preview recognises the
openings (openings_core, metres from the host), matches library types (windowgen_core quality report: quarantine
and duplicates never offered) and plans markers + window instances; apply does it in ONE undo record (selection
restored): markers on OPENING_markers, one hidden master per type (frame WINLIB_<id> on WINDOW_types, glass
WINLIB_<id>_glass on GLASS_types, built by windowgen_core.build_type), instances WIN_<nnn> / GLASS_<nnn> on
WINDOW_placed / GLASS_placed. The walls and any existing window are never changed. Drafts of the openings without
a type are written as new JSON files (never overwritten) after the undo record.
"""
import json
import os

LAYERS = {'marker': 'OPENING_markers', 'master': 'WINDOW_types', 'master_glass': 'GLASS_types',
          'window': 'WINDOW_placed', 'glass': 'GLASS_placed'}
MARKER_PROP = 'agr_opening_marker'
MASTER_PROP = 'agr_window_master'


def _rt():
    from pymxs import runtime
    return runtime


def _load(name):
    import importlib.util
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location('agr_tools_' + name[:-3] + '_j', os.path.join(here, name))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _handle(n):
    return int(_rt().getHandleByAnim(n))


def _by_handle(h):
    rt = _rt()
    n = rt.getAnimByHandle(int(h))
    if n is None or not rt.isValidNode(n):
        raise ValueError('a node of the preview is gone; run preview again')
    return n


def _rows(tm, mpu):
    def unit(p):
        v = [float(p.x), float(p.y), float(p.z)]
        ln = sum(c * c for c in v) ** 0.5 or 1.0
        return [c / ln for c in v]
    return [unit(tm.row1), unit(tm.row2), unit(tm.row3),
            [float(tm.row4.x) * mpu, float(tm.row4.y) * mpu, float(tm.row4.z) * mpu]]


def _matrix(rows, mpu):
    rt = _rt()
    k = 1.0 / mpu
    return rt.Matrix3(rt.Point3(*rows[0]), rt.Point3(*rows[1]), rt.Point3(*rows[2]),
                      rt.Point3(rows[3][0] * k, rows[3][1] * k, rows[3][2] * k))


def _prop(n, key):
    v = _rt().getUserProp(n, key)
    return None if v is None else str(v)


def _is_marker(n):
    rt = _rt()
    name = str(n.name)
    return name.startswith('OPEN_') and len(name) == 8 and name[5:].isdigit() and \
        rt.superClassOf(n) == rt.Helper


def _is_wall(n):
    rt = _rt()
    if rt.superClassOf(n) != rt.GeometryClass or not rt.canConvertTo(n, rt.TriMeshGeometry):
        return False
    return _prop(n, 'agr_role') not in ('window', 'glass', 'capsule', 'opening') and _prop(n, MASTER_PROP) is None


def _markers(contract, mpu):
    out = []
    for n in list(_rt().helpers):
        if not _is_marker(n):
            continue
        op = None
        text = _prop(n, contract.OPENING_PROP)
        if text:
            try:
                op = contract.parse_opening(text)
            except ValueError:
                op = None
        t = _prop(n, contract.WINDOW_TYPE_PROP) or None
        out.append({'name': str(n.name), 'handle': _handle(n), 'rows': _rows(n.transform, mpu), 'type': t,
                    'opening': op})
    return sorted(out, key=lambda m: m['name'])


def _placed():
    """{marker name: window node name} of windows already placed by win.place."""
    out = {}
    for n in list(_rt().geometry):
        mk = _prop(n, MARKER_PROP)
        if mk and _prop(n, 'agr_role') == 'window':
            out[mk] = str(n.name)
    return out


def _state(emax, nodes, extra):
    return {'nodes': emax.snapshot(nodes), 'extra': extra}


def _layer(name):
    rt = _rt()
    layer = rt.LayerManager.getLayerFromName(name)
    if layer is None:
        layer = rt.LayerManager.newLayerFromName(name)
    return layer


def _mesh_node(data, name, mpu):
    """Editable_Mesh from a metre mesh (quads fan-triangulated, inner diagonals hidden), at the world origin."""
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


def _master(gen, lib, tid, mpu, cache):
    """(frame master, glass master or None) of a type: the existing WINLIB_<id> of this library, else built."""
    if tid in cache:
        return cache[tid]
    rt = _rt()
    name = 'WINLIB_' + tid
    found = rt.getNodeByName(name)
    if found is not None and _prop(found, MASTER_PROP) == lib['sha256']['standard.json'][:16] and \
            _prop(found, 'agr_window_type') == tid:
        glass = rt.getNodeByName(name + '_glass')
        cache[tid] = (found, glass)
        return cache[tid]
    mesh = gen.build_type(lib['by_id'][tid], lib['standard'])
    frame = _mesh_node(gen.part_mesh(mesh, 'body'), _free_name(name), mpu)
    glass = _mesh_node(gen.part_mesh(mesh, 'glass'), _free_name(name + '_glass'), mpu) if mesh['parts']['glass'] else None
    for node, role, layer in ((frame, 'window', LAYERS['master']), (glass, 'glass', LAYERS['master_glass'])):
        if node is None:
            continue
        rt.setUserProp(node, 'agr_role', role)
        rt.setUserProp(node, 'agr_window_type', tid)
        rt.setUserProp(node, MASTER_PROP, lib['sha256']['standard.json'][:16])
        rt.setUserProp(node, 'agr_face_axis', mesh['face_axis'])
        _layer(layer).addNode(node)
        node.isHidden = True
    cache[tid] = (frame, glass)
    return cache[tid]


def _free_name(base):
    rt = _rt()
    return base if rt.getNodeByName(base) is None else str(rt.uniqueName(base + '_'))


def _drafts_dir(opts):
    rt = _rt()
    if opts.get('drafts_dir'):
        return opts['drafts_dir']
    if str(rt.maxFileName):
        return os.path.join(str(rt.maxFilePath), 'window_drafts')
    base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    return os.path.join(base, 'AGRTools', 'window_drafts')


def win_place(ctx, mode, nodes, preview):
    """win.place (1.0.9): openings -> markers OPEN_<nnn> -> instances of the standard window types."""
    tool = 'win.place'
    edit, emax, core, host = ctx.edit, ctx.emax, ctx.core, ctx.host
    contract = _load('contract_core.py')
    oc = _load('openings_core.py')
    gen = _load('windowgen_core.py')
    rt = _rt()
    mpu = host.m_per_unit()
    if mode == 'preview':
        opts = core.check_options(ctx.options)
        oc.check_options(opts['openings'])
        picked = list(rt.selection) if nodes is None else list(nodes)
        if not picked:
            raise ValueError('nothing selected: select the walls with opening borders and/or the OPEN_<nnn> markers')
        walls = sorted({_handle(n): n for n in picked if _is_wall(n)}.values(), key=_handle)
        sel_markers = {_handle(n) for n in picked if _is_marker(n)}
        if not walls and not sel_markers:
            raise ValueError('no wall with borders and no OPEN_<nnn> marker in the selection')
        lib = gen.load_library(gen.library_dir(opts['library']))
        report = gen.library_report(lib['types'], lib['standard'])
        offer = set(gen.offerable(report, tuple(opts['statuses'])))
        infos = {}

        def info(tid):
            if tid not in infos:
                m = gen.build_type(lib['by_id'][tid], lib['standard'])
                infos[tid] = {'size_m': m['size_m'], 'frame_mid_m': m['frame_mid_m'], 'face_axis': m['face_axis']}
            return infos[tid]

        openings, rejected = [], []
        for w in walls:
            ref, = host.refs([w])
            found = oc.find_openings_report(host.mesh(ref), opts['openings'])
            for o in found['openings']:
                o['wall_handle'] = _handle(w)
                openings.append(o)
            rejected += [dict(r, wall=str(w.name)) for r in found['rejected']]
        markers = _markers(contract, mpu)
        # a marker that is not selected only takes part when it lies on a selected wall's opening
        free_ok = {m['handle'] for m in markers if m['handle'] in sel_markers}
        planned = core.plan(openings, markers, lib['by_id'], offer, info, opts)
        placed = _placed()
        acts, objects, done, skipped, ambiguous, drafts = [], {}, [], [], [], []
        for a in planned['actions']:
            if a['source'] == 'marker' and a['marker_handle'] not in free_ok:
                continue
            o = a['opening']
            owner = o.get('wall_handle') or a['marker_handle']
            oname = o.get('wall') if o.get('wall_handle') else a['marker']
            ent = objects.setdefault(owner, {'name': oname, 'findings': []})
            text = core.summary(a)
            if a['status'] == 'place' and a['marker'] in placed:
                skipped.append(edit.skipped(a['marker'], 'окно уже стоит: ' + placed[a['marker']]))
                continue
            ids = [o['id']] if o.get('id') else []
            if a['status'] == 'place':
                for code, detail in a['findings']:
                    ent['findings'].append(edit.finding(code, ids, a['marker'] + ': ' + detail))
                done.append(text)
            else:
                code = 'opening_ambiguous' if o.get('kind') in ('nonrect', 'corner', 'nonplanar') else 'no_type'
                ent['findings'].append(edit.finding(code, ids, text))
                ambiguous.append(text)
                if o.get('w') and o.get('h'):
                    d = gen.draft_entry(dict(o, marker=a['marker']), lib['standard'])
                    drafts.append(d)
            fields = oc.marker_fields(o) if a['source'] == 'opening' else None
            acts.append({'marker': a['marker'], 'marker_handle': a['marker_handle'], 'marker_new': a['marker_new'],
                         'marker_rows': None if not o.get('frame') else core.marker_rows(o['frame']),
                         'fields': fields, 'type': a['type'], 'status': a['status'], 'rows': a['rows'],
                         'face_axis': a['face_axis'], 'opening': {k: o.get(k) for k in (
                             'id', 'kind', 'w', 'h', 'sill', 'depth', 'wall', 'corner', 'frame')}})
        if not acts and not skipped:
            msg = 'нет проёмов и меток: запрос агенту «{}»'.format(core.AGENT_REQUEST)
            ambiguous.append(msg)
        objects_list = [edit.entry(h, v['name'], v['findings']) for h, v in sorted(objects.items())]
        units = {'m_per_unit': mpu}
        handles = sorted({_handle(w) for w in walls} | {m['handle'] for m in markers})
        settings = {k: opts[k] for k in opts if k not in ('library', 'drafts_dir')}
        state = _state(emax, [_by_handle(h) for h in handles], {'settings': settings, 'units': units,
                                                                 'library': lib['sha256'], 'placed': placed})
        extra = {'options': dict(ctx.options), 'settings': settings, 'units': units, 'handles': handles,
                 'library': {'folder': lib['folder'], 'sha256': lib['sha256']}, 'actions': acts,
                 'drafts': drafts, 'drafts_dir': _drafts_dir(opts), 'rejected': rejected[:200],
                 'placed_before': placed, 'counts': {'openings': len(openings), 'place': sum(
                     a['status'] == 'place' for a in acts), 'ambiguous': len(ambiguous), 'rejected': len(rejected)},
                 'agent_request': core.AGENT_REQUEST if not acts and not skipped else None}
        return edit.report(tool, 'preview', objects=objects_list, done=done, skipped_=skipped, ambiguous=ambiguous,
                           state_hash=edit.fingerprint(state), extra=extra)

    plan = preview['plan']
    handles = plan['handles']
    nodes_now = [_by_handle(h) for h in handles]
    lib = gen.load_library(plan['library']['folder'])
    edit.require_current(preview, _state(emax, nodes_now, {'settings': plan['settings'],
                                                           'units': {'m_per_unit': mpu},
                                                           'library': lib['sha256'], 'placed': _placed()}))
    if abs(mpu - plan['units']['m_per_unit']) > 1e-12:
        raise edit.StalePreview('scene units changed since the preview; run preview again')
    contract = _load('contract_core.py')
    cache, made, done = {}, [], []
    with emax.session(tool):
        mlayer = _layer(LAYERS['marker'])
        for a in plan['actions']:
            if a['marker_rows'] is None:
                continue
            if a['marker_new']:
                mk = rt.Point(name=a['marker'], size=0.3 / mpu, cross=True, box=True)
                mk.transform = _matrix(a['marker_rows'], mpu)
                mlayer.addNode(mk)
            else:
                mk = _by_handle(a['marker_handle'])
            rt.setUserProp(mk, contract.ROLE_PROP, 'opening')
            if a['fields']:
                f = a['fields']
                rt.setUserProp(mk, contract.OPENING_PROP, contract.dump_opening(f['w'], f['h'], f['sill'], f['depth'],
                                                                                 f['wall'], f['corner']))
            if a['type']:
                rt.setUserProp(mk, contract.WINDOW_TYPE_PROP, contract.check_window_type(a['type']))
            if a['status'] != 'place':
                continue
            frame, glass = _master(gen, lib, a['type'], mpu, cache)
            n = int(a['marker'][5:])
            for master, role, prefix, layer in ((frame, 'window', 'WIN_', LAYERS['window']),
                                                (glass, 'glass', 'GLASS_', LAYERS['glass'])):
                if master is None:
                    continue
                inst = rt.instance(master)
                inst.name = _free_name('{}{:03d}'.format(prefix, n))
                inst.transform = _matrix(a['rows'], mpu)
                inst.isHidden = False
                rt.setUserPropBuffer(inst, '')  # the master's props are not the instance's
                rt.setUserProp(inst, 'agr_role', role)
                rt.setUserProp(inst, 'agr_window_type', a['type'])
                rt.setUserProp(inst, MARKER_PROP, a['marker'])
                rt.setUserProp(inst, 'agr_face_axis', a['face_axis'])
                _layer(layer).addNode(inst)
                made.append((a, inst, role))
    objects, findings_by = [], {}
    tol = plan['settings']
    for a, inst, role in made:
        rows = _rows(inst.transform, mpu)
        o = a['opening']
        fr = o['frame']
        if role == 'window':
            m = gen.build_type(lib['by_id'][a['type']], lib['standard'])
            W, D, H = m['size_m']
            c = core.apply_rows(rows, [W / 2.0, D / 2.0, H / 2.0])
            want = [p - z * tol['recess_m'] for p, z in zip(fr['origin'], fr['z'])]
            err = sum((p - q) ** 2 for p, q in zip(c, want)) ** 0.5
            ang = core.angle_deg(core.face_normal_world(rows, a['face_axis']), fr['z'])
            fs = []
            if err > tol['centre_tol_m']:
                fs.append(edit.finding('readback', [], 'centre {:.2f} mm'.format(err * 1000)))
            if ang > tol['normal_tol_deg']:
                fs.append(edit.finding('readback', [], 'normal {:.4f} deg'.format(ang)))
            findings_by[_handle(inst)] = (str(inst.name), fs)
            done.append('{} -> {} {}: centre {:.3f} mm, normal {:.4f} deg'.format(
                a['marker'], str(inst.name), a['type'], err * 1000, ang))
    for h, (name, fs) in sorted(findings_by.items()):
        objects.append(edit.entry(h, name, fs))
    written = []
    if plan['drafts']:
        folder = plan['drafts_dir']
        os.makedirs(folder, exist_ok=True)
        for d in plan['drafts']:
            path = edit.new_path(os.path.join(folder, 'draft_{}.json'.format(d['source']['opening'])), version=True)
            edit.write_new(path, (json.dumps(d, ensure_ascii=False, indent=1) + '\n').encode('utf-8'))
            written.append(path)
    return edit.report(tool, 'apply', objects=objects, done=done, skipped_=plan['skipped'],
                       ambiguous=plan['ambiguous'], extra={'placed': len(findings_by), 'drafts': written,
                                                           'markers': sum(1 for a in plan['actions']
                                                                          if a['marker_rows'] is not None)})
