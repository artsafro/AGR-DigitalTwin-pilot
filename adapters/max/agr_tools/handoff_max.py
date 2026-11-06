"""new-case: AGR Tools 1.0.x (#1024, branch BH) Max <-> Blender handoff, 3ds Max side (thin pymxs glue).

Functions with the edits_100 signature `<fn>(ctx, mode, nodes, preview)` (ctx: edit = edit_core, core = handoff_core,
host = host_max.MaxHost, options): `handoff_export`, `handoff_import`, `handoff_verify` (read: preview only),
`handoff_restore_materials` («Восстановить материалы»). Registration of the four rows in the shared files (runtime
EDITS_100, ui_model, agr_tools.mcr, build list, src/agr_mcp/tools.py) is a separate small PR of branch 0 style.

* export: selection -> NEW folder <job_dir>/handoff/<seq>/ with model.fbx (no triangulation, metres, Z up, instances),
  manifest.json, sidecar.json, materials.json, readback_max.json; a copy of materials.json goes next to the scene
  (<scene>.materials.json, a new _vNNN when one exists). Markers OPEN_* / LEVEL_* go to the sidecar, not the FBX.
* import: the FBX from Blender -> new objects in the layer AGENT_<req> only (owner answer 06.11.2026); names, user
  properties and matIDs restored from the bundle, instances re-linked; request.json + baseline.json for the gate
  agent.accept (branch U) are written so the transfer to the role layers goes through that gate.
* verify: facts of the returned objects vs readback_max.json by the table of REPORT 3.12 (handoff_core.compare).
* restore_materials: materials.json -> materials rebuilt (or the same scene material reused when it is identical)
  and assigned by name + role; unmatched / ambiguous objects and every parameter that did not come back go to the
  report.
Import pymxs inside functions so this file loads under plain pytest. No MAXScript globals (local fn expressions only).
"""
import hashlib
import json
import os


def _rt():
    from pymxs import runtime
    return runtime


def _load(name):
    import importlib.util
    import sys
    key = 'agr_tools_' + name[:-3]
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, os.path.join(os.path.dirname(os.path.abspath(__file__)), name))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


def _bridge():
    """agentbridge_max / agentbridge_core of branch U (read-only use: scene hashes, request, the accept gate)."""
    return _load('agentbridge_max.py'), _load('agentbridge_core.py')


def _sha_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _json_bytes(doc):
    return json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True, allow_nan=False).encode('utf-8')


def _pname(p):
    return str(p).lstrip('#')


# ---- node classification -------------------------------------------------------------------------------------------
def _is_marker(core_contract, n):
    name = str(n.name)
    return bool(core_contract.OPEN_RE.match(name) or core_contract.LEVEL_RE.match(name))


def _is_mesh(rt, n):
    return (str(rt.superClassOf(n)) == 'GeometryClass' and rt.canConvertTo(n, rt.Editable_Poly)
            and not str(rt.classOf(n)).lower().startswith('targetobject'))


def _role(rt, n):
    v = rt.getUserProp(n, 'agr_role')
    return None if v in (None, '') else str(v)


# ---- facts ---------------------------------------------------------------------------------------------------------
def _world_rows(n, k):
    tm = n.transform
    rows = [[float(c) for c in (r.x, r.y, r.z)] for r in (tm.row1, tm.row2, tm.row3)]
    t = tm.row4
    return rows + [[float(t.x) * k, float(t.y) * k, float(t.z) * k]]


def _scale(n):
    s = n.transform.scalepart
    return [float(s.x), float(s.y), float(s.z)]


def _instance_leaders(rt, nodes):
    """{name: leader name or None}: nodes that share one base object (Max instances); leader = first by name."""
    by = {}
    for n in nodes:
        by.setdefault(int(rt.getHandleByAnim(n.baseObject)), []).append(str(n.name))
    out = {}
    for names in by.values():
        lead = sorted(names)[0] if len(names) > 1 else None
        for nm in names:
            out[nm] = lead
    return out


def poly_facts(rt, n, k, leader=None, core=None):
    """(facts, extra) of one mesh node from a temporary Editable Poly copy (the node is never changed).

    extra: {'face_ids': [...], 'tiles_by_id': {id: [UDIM]} (channel 1), 'hard': count, 'sg': {group bits: faces}}."""
    import pymxs
    core = core or _load('handoff_core.py')
    po = rt.polyop
    with pymxs.undo(False):
        c = rt.copy(n)
        try:
            rt.convertToPoly(c)
            nv, nf, ne = int(po.getNumVerts(c)), int(po.getNumFaces(c)), int(po.getNumEdges(c))
            verts = []
            for i in range(1, nv + 1):
                p = po.getVert(c, i)
                verts.append([float(p.x) * k, float(p.y) * k, float(p.z) * k])
            faces, ids, sgs = [], [], []
            for f in range(1, nf + 1):
                faces.append([int(v) - 1 for v in po.getFaceVerts(c, f)])
                ids.append(int(po.getFaceMatID(c, f)))
                sgs.append(int(po.getFaceSmoothGroup(c, f)) & 0xFFFFFFFF)
            hard = []
            for e in range(1, ne + 1):
                ef = [int(x) for x in po.getEdgeFaces(c, e)]
                if len(ef) != 2:
                    continue
                a, b = sgs[ef[0] - 1], sgs[ef[1] - 1]
                if a & b == 0:
                    v1, v2 = [int(x) - 1 for x in po.getEdgeVerts(c, e)]
                    hard.append([(verts[v1][i] + verts[v2][i]) / 2 for i in range(3)])
            uv = {}
            nmaps = int(po.getNumMaps(c))
            for ch in range(1, nmaps):
                if not po.getMapSupport(c, ch):
                    continue
                per_face = []
                for f in range(1, nf + 1):
                    corners = []
                    for mv in po.getMapFace(c, ch, f):
                        q = po.getMapVert(c, ch, int(mv))
                        corners.append([float(q.x), float(q.y)])
                    per_face.append(corners)
                uv[ch] = per_face
        finally:
            rt.delete(c)
    parent = None if n.parent is None else str(n.parent.name)
    facts = core.finish_facts(str(n.name), _world_rows(n, k), verts, faces, ids, ne, hard, uv, role=_role(rt, n),
                              parent=parent, scale=_scale(n), instance_group=leader)
    tiles_by_id = {}
    for f, mid in enumerate(ids):
        corners = uv.get(1, [[]] * nf)[f] if 1 in uv else []
        if corners:
            t = core.udim(sum(p[0] for p in corners) / len(corners), sum(p[1] for p in corners) / len(corners))
            if t is not None:
                tiles_by_id.setdefault(mid, set()).add(t)
    extra = {'face_ids': ids, 'tiles_by_id': {m: sorted(t) for m, t in tiles_by_id.items()}, 'hard': len(hard),
             'sg_bits': sorted(set(sgs))}
    return facts, extra


def scene_facts(rt, nodes, k, core):
    """Facts of `nodes`; a parent outside the set is not a fact of this set (the manifest keeps the real parent)."""
    leaders = _instance_leaders(rt, nodes)
    names = {str(n.name) for n in nodes}
    out = []
    for n in nodes:
        fa, ex = poly_facts(rt, n, k, leaders.get(str(n.name)), core)
        if fa['parent'] not in names:
            fa['parent'] = None
        out.append((fa, ex))
    return out, leaders


def _export_copies(rt, nodes):
    """Temporary Editable_Poly copies of `nodes` (names, world transforms, materials, user props, hierarchy inside
    the set) for the FBX: the originals are never converted, relinked or collapsed. The caller deletes them."""
    copies = {}
    po = rt.polyop
    for n in nodes:
        c = rt.copy(n)
        rt.convertToPoly(c)
        c.name = n.name
        c.material = n.material
        # bake the object offset (pivot moved off the geometry) into the copy's vertices, world positions unchanged:
        # the Blender importer puts an FBX geometric transform into the OBJECT matrix and a child inherits it
        # (GLASS_001 moved by the pivot offset of BODY_Brick_001, job 20261106-134044-fbdf80ba)
        pts = [po.getVert(c, i) for i in range(1, int(po.getNumVerts(c)) + 1)]
        c.objectOffsetPos = rt.Point3(0, 0, 0)
        c.objectOffsetRot = rt.Quat(0, 0, 0, 1)
        c.objectOffsetScale = rt.Point3(1, 1, 1)
        for i, p in enumerate(pts, 1):
            po.setVert(c, i, p)
        copies[int(n.inode.handle)] = c
    for n in nodes:
        c = copies[int(n.inode.handle)]
        p = n.parent
        c.parent = copies.get(int(p.inode.handle)) if p is not None else None
    for n in nodes:
        copies[int(n.inode.handle)].transform = n.transform
    return [copies[int(n.inode.handle)] for n in nodes]


# ---- materials: serialise ------------------------------------------------------------------------------------------
class MaterialWriter:
    """Max material graph -> materials.json nodes (every parameter of getPropNames, refs kept shared)."""

    def __init__(self, rt, depth=3):
        self.rt = rt
        self.depth = depth
        self.keys = {}
        self.nodes = {}

    def ref(self, v):
        rt = self.rt
        h = int(rt.getHandleByAnim(v))
        if h in self.keys:
            return self.keys[h]
        key = 'n{:03d}'.format(len(self.keys) + 1)
        self.keys[h] = key
        self.nodes[key] = None
        self.nodes[key] = self.node(v)
        return key

    def node(self, v):
        rt = self.rt
        try:
            name = str(v.name)
        except Exception:  # noqa: BLE001 - nameless sub-anim
            name = ''
        return {'name': name, 'class': str(rt.classOf(v)), 'superclass': str(rt.superClassOf(v)),
                'props': self.props(v, 0)}

    def props(self, v, depth):
        rt = self.rt
        out = {}
        try:
            names = list(rt.getPropNames(v))
        except Exception:  # noqa: BLE001
            return out
        for p in names:
            key = _pname(p)
            try:
                val = rt.getProperty(v, p)
            except Exception:  # noqa: BLE001 - write-only / unreadable parameter
                out[key] = {'$': 'skip', 'why': 'unreadable'}
                continue
            out[key] = self.value(val, depth)
        return out

    def value(self, v, depth):
        import math
        rt = self.rt
        if v is None or isinstance(v, (bool, str)):
            return v
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return v if math.isfinite(v) else {'$': 'skip', 'why': 'non-finite'}
        cls = str(rt.classOf(v))
        if cls == 'Color':
            return {'$': 'color', 'v': [float(v.r), float(v.g), float(v.b), float(v.a)]}
        if cls == 'Point3':
            return {'$': 'point3', 'v': [float(v.x), float(v.y), float(v.z)]}
        if cls == 'Point2':
            return {'$': 'point2', 'v': [float(v.x), float(v.y)]}
        if cls == 'Point4':
            return {'$': 'point4', 'v': [float(v.x), float(v.y), float(v.z), float(v.w)]}
        if cls == 'Name':
            return {'$': 'name', 'v': str(v).lstrip('#')}
        if cls in ('Array', 'ArrayParameter'):
            return {'$': 'array', 'v': [self.value(x, depth) for x in v]}
        sc = str(rt.superClassOf(v))
        if sc in ('material', 'textureMap'):
            return {'$': 'ref', 'v': self.ref(v)}
        if depth < self.depth and rt.isKindOf(v, rt.MAXWrapper):
            return {'$': 'sub', 'class': cls, 'props': self.props(v, depth + 1)}
        return {'$': 'skip', 'class': cls}


def materials_doc(rt, core, nodes, host_doc, ids_by_name=None):
    """materials.json of `nodes`; ids_by_name {name: face matIDs} (from the facts; empty when not given)."""
    w = MaterialWriter(rt)
    objects = []
    for n in nodes:
        mat = n.material
        key = None if mat is None else w.ref(mat)
        objects.append({'name': str(n.name), 'role': _role(rt, n), 'handle': int(n.inode.handle), 'material': key,
                        'mat_ids': sorted(set((ids_by_name or {}).get(str(n.name), [])))})
    source = {'host': 'max', 'doc': host_doc, 'app': '3ds Max ' + str(list(rt.maxVersion())[0])}
    return core.build_materials(source, objects, w.nodes), w


# ---- materials: rebuild --------------------------------------------------------------------------------------------
class MaterialBuilder:
    """materials.json nodes -> Max materials/maps (class by name, every parameter set; arrays element-wise)."""

    def __init__(self, rt, nodes):
        self.rt = rt
        self.nodes = nodes
        self.made = {}
        self.errors = []
        self._set_item = rt.execute('(fn f o p i v = (local a = getProperty o p; a[i] = v; ok); f)')
        self._multi = rt.execute('(fn f mm n = (mm.numsubs = n; ok); f)')

    def build(self, key):
        if key in self.made:
            return self.made[key]
        spec = self.nodes[key]
        cls = getattr(self.rt, spec['class'], None)
        if cls is None:
            self.errors.append('{}: class {} is not in this Max'.format(spec['name'], spec['class']))
            self.made[key] = None
            return None
        obj = cls()
        self.made[key] = obj
        if str(spec['class']).lower() == 'multimaterial':
            ids = spec['props'].get('materialIDList', {}).get('v', [])
            self._multi(obj, len(ids))
        self.apply(obj, spec['props'], spec['name'])
        try:
            obj.name = spec['name']
        except Exception:  # noqa: BLE001
            self.errors.append('{}: name not set'.format(spec['name']))
        return obj

    def decode(self, v):
        rt = self.rt
        if not isinstance(v, dict):
            return v
        tag = v.get('$')
        if tag == 'color':
            return rt.Color(*v['v'])
        if tag == 'point3':
            return rt.Point3(*v['v'])
        if tag == 'point2':
            return rt.Point2(*v['v'])
        if tag == 'point4':
            return rt.Point4(*v['v'])
        if tag == 'name':
            return rt.Name(v['v'])
        if tag == 'ref':
            return self.build(v['v'])
        raise ValueError('not a plain value: ' + str(tag))

    def apply(self, obj, props, where, passes=2):
        rt = self.rt
        todo = list(props.items())
        for _ in range(passes):
            failed = []
            for prop, enc in todo:
                if isinstance(enc, dict) and enc.get('$') == 'skip':
                    continue
                try:
                    if isinstance(enc, dict) and enc.get('$') == 'sub':
                        self.apply(rt.getProperty(obj, prop), enc['props'], where + '.' + prop, passes=1)
                    elif isinstance(enc, dict) and enc.get('$') == 'array':
                        for i, item in enumerate(enc['v'], 1):
                            if isinstance(item, dict) and item.get('$') in ('skip', 'sub', 'array'):
                                continue
                            self._set_item(obj, rt.Name(prop), i, self.decode(item))
                    else:
                        rt.setProperty(obj, rt.Name(prop), self.decode(enc))
                except Exception as exc:  # noqa: BLE001 - read-only / derived parameter: judged by the re-read diff
                    failed.append((prop, enc, str(exc)[:120]))
            todo = [(p, e) for p, e, _m in failed]
            if not todo:
                break


def _material_root_matches(rt, core, doc, key, candidate):
    """True when a scene material is the same graph as node `key` of materials.json (reuse instead of a copy)."""
    w = MaterialWriter(rt)
    k = w.ref(candidate)
    return not core.diff_nodes(doc['nodes'], key, w.nodes, k)


# ---- export --------------------------------------------------------------------------------------------------------
def _export_targets(ctx, nodes):
    rt = _rt()
    nodes = [n for n in (nodes or []) if rt.isValidNode(n)]
    contract = ctx.host.contract
    meshes = [n for n in nodes if _is_mesh(rt, n) and not _is_marker(contract, n)]
    if not meshes:
        raise ValueError('handoff.export: empty input - select the mesh objects to send to Blender')
    return meshes


def _job_dir(ctx, opt):
    mx, _bc = _bridge()
    job = opt.get('job_dir')
    if not job:
        pp_path, _pp = mx.passport(_rt())
        job = os.path.dirname(pp_path) if pp_path else None
    if not job:
        raise ValueError('handoff.export: options.job_dir (jobs/<ID>) is required while the scene has no passport')
    return job


def _fbx_params(rt, params, setter='FBXExporterSetParam', getter='FBXExporterGetParam'):
    """Set FBX plug-in parameters; returns [(key, wanted, got)] of the ones the plug-in did not take."""
    set_, get_ = getattr(rt, setter), getattr(rt, getter)
    bad = []
    for key, value in params:
        set_(key, value)
        got = get_(key)
        if isinstance(value, bool):
            ok = str(got).lower() == str(value).lower()
        elif isinstance(value, float):
            try:
                ok = abs(float(got) - value) < 1e-9
            except (TypeError, ValueError):
                ok = False
        else:
            ok = str(got).lower().lstrip('#') == str(value).lower().lstrip('#')
        if not ok:
            bad.append((key, value, str(got)))
    return bad


def handoff_export(ctx, mode, nodes, preview):
    rt = _rt()
    core, edit, host = ctx.core, ctx.edit, ctx.host
    mx, _bc = _bridge()
    opt = core.check_options(core.TOOL_EXPORT, preview['plan']['options'] if preview is not None else ctx.options,
                             core.EXPORT_OPTIONS)
    if preview is not None:
        nodes = []
        for h in preview['plan']['targets']:
            n = rt.maxOps.getNodeByHandle(int(h))
            if n is None or not rt.isValidNode(n):
                raise edit.StalePreview('object #{} of the preview is gone; run preview again'.format(h))
            nodes.append(n)
    meshes = _export_targets(ctx, nodes)
    job = _job_dir(ctx, opt)
    hdir = os.path.join(job, 'handoff')
    seq = opt.get('seq') or (preview['plan']['seq'] if preview is not None else
                             core.next_seq(os.listdir(hdir) if os.path.isdir(hdir) else []))
    bundle = os.path.join(hdir, seq)
    if mode == 'preview' and os.path.exists(bundle):
        raise FileExistsError('refusing to overwrite: ' + bundle)
    names = {}
    for n in rt.objects:
        names[str(n.name)] = names.get(str(n.name), 0) + 1
    entries = []
    for n in meshes:
        f = []
        if names[str(n.name)] > 1:
            f.append(edit.finding('duplicate_name', (), '{} objects share this name: the return is matched by name; '
                                  'rename first'.format(names[str(n.name)])))
        entries.append(edit.entry(int(n.inode.handle), str(n.name), f))
    for cut, group in core.name_collisions([str(n.name) for n in meshes]):
        for n in meshes:
            if str(n.name) in group:
                for e in entries:
                    if e['handle'] == int(n.inode.handle):
                        e['findings'].append(edit.finding('blender_name_cut', (), 'Blender keeps 63 bytes: {} share '
                                                          '"{}"'.format(', '.join(group), cut)))
    scene = host.doc()
    next_to_scene = opt.get('materials_next_to_scene', True) and scene != 'untitled'
    side_path = os.path.splitext(scene)[0] + '.materials.json' if next_to_scene else None
    state = {'targets': [int(n.inode.handle) for n in meshes],
             'objects': {str(int(n.inode.handle)): mx.object_state(rt, n) for n in meshes}, 'bundle': bundle}
    files = [os.path.join(bundle, f) for f in core.BUNDLE_FILES]
    extra = {'options': opt, 'seq': seq, 'bundle': bundle, 'targets': state['targets'],
             'materials_next_to_scene': side_path}
    if mode == 'preview':
        return edit.report(core.TOOL_EXPORT, 'preview', entries, done=files + ([side_path] if side_path else []),
                           state_hash=edit.fingerprint(state), extra=extra)
    edit.require_current(preview, state)
    k = host.m_per_unit()
    facts, leaders = scene_facts(rt, meshes, k, core)
    mats, _w = materials_doc(rt, core, meshes, scene,
                             {str(n.name): ex['face_ids'] for n, (_fa, ex) in zip(meshes, facts)})
    os.makedirs(bundle)  # a new folder only
    fbx = os.path.join(bundle, 'model.fbx')
    before = list(rt.selection)
    rt.pluginManager.loadClass(rt.FbxExporter)
    bad = _fbx_params(rt, core.FBX_EXPORT_PARAMS)
    if bad:
        raise ValueError('handoff.export: FBX exporter did not take {}'.format(bad))
    import pymxs
    copies = []
    try:
        with pymxs.undo(False):
            copies = _export_copies(rt, meshes)
            rt.clearSelection()
            rt.select(copies)
            ok = rt.exportFile(fbx, rt.name('noPrompt'), selectedOnly=True, using=rt.FBXEXP)
    finally:
        with pymxs.undo(False):
            rt.clearSelection()
            for c in copies:
                if rt.isValidNode(c):
                    rt.delete(c)
            live = [n for n in before if rt.isValidNode(n)]
            if live:
                rt.select(live)
    if not ok or not os.path.isfile(fbx):
        raise RuntimeError('handoff.export: FBX was not written: ' + fbx)
    mat_bytes = _json_bytes(mats)
    edit.write_new(os.path.join(bundle, 'materials.json'), mat_bytes)
    src = {'host': 'max', 'doc': scene, 'app': '3ds Max ' + str(list(rt.maxVersion())[0])}
    units = {'system': str(rt.units.SystemType).lstrip('#').lower(), 'm_per_unit': k,
             'system_scale': float(rt.units.SystemScale)}
    objs, side_objs = [], {}
    mat_by_name = {o['name']: o for o in mats['objects']}
    for n, (fa, ex) in zip(meshes, facts):
        name = str(n.name)
        subs = core.sub_names(mats, mat_by_name[name]['material'], set(ex['face_ids']))
        slots = core.slot_table(ex['face_ids'], subs, ex['tiles_by_id'])
        lead = leaders.get(name)
        objs.append(core.manifest_object(fa, int(n.inode.handle), str(n.layer.name), slots,
                                         lead if lead not in (None, name) else None))
        buf = str(rt.getUserPropBuffer(n))
        side_objs[name] = {'user_props': buf, 'props': core.parse_user_props(buf), 'hard_edges': ex['hard'],
                           'smoothing': {'groups_bits': ex['sg_bits']}}
    markers = []
    for n in rt.objects:
        nm = str(n.name)
        if host.contract.OPEN_RE.match(nm) or host.contract.LEVEL_RE.match(nm):
            buf = str(rt.getUserPropBuffer(n))
            markers.append({'name': nm, 'kind': 'opening' if nm.startswith('OPEN_') else 'level',
                            'world': _world_rows(n, k), 'props': core.parse_user_props(buf)})
    pp_path, _pp = mx.passport(rt)
    passport = {'path': pp_path, 'sha256': _sha_file(pp_path)} if pp_path and os.path.isfile(pp_path) else None
    manifest = core.build_manifest(src, units, {'file': 'model.fbx', 'sha256': _sha_file(fbx)},
                                   {'file': 'materials.json', 'sha256': hashlib.sha256(mat_bytes).hexdigest()}, objs)
    edit.write_new(os.path.join(bundle, 'manifest.json'), _json_bytes(manifest))
    edit.write_new(os.path.join(bundle, 'sidecar.json'),
                   _json_bytes(core.build_sidecar(src, side_objs, markers, passport)))
    edit.write_new(os.path.join(bundle, 'readback_max.json'),
                   _json_bytes(core.build_readback('max', src['app'], [fa for fa, _e in facts])))
    done = list(files)
    if side_path:
        target = edit.new_path(side_path, version=True)
        edit.write_new(target, mat_bytes)
        done.append(target)
    return edit.report(core.TOOL_EXPORT, 'apply', entries, done=done,
                       extra={'seq': seq, 'bundle': bundle, 'fbx_sha256': manifest['fbx']['sha256'],
                              'objects': len(objs), 'materials_json': done[-1] if side_path else
                              os.path.join(bundle, 'materials.json')})


# ---- import --------------------------------------------------------------------------------------------------------
def _read_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _bundle(core, opt):
    b = opt.get('bundle')
    if not b or not os.path.isdir(b):
        raise ValueError('options.bundle must be the handoff folder (handoff/<seq>)')
    manifest = core.validate_manifest(_read_json(os.path.join(b, 'manifest.json')))
    sidecar = core.validate_sidecar(_read_json(os.path.join(b, 'sidecar.json')))
    mats = core.validate_materials(_read_json(os.path.join(b, 'materials.json')))
    return b, manifest, sidecar, mats


def _system_unit_code(rt, core):
    kind = str(rt.units.SystemType).lower().lstrip('#')
    return core.UNIT_CODES.get(kind, 'cm')


def _face_centres(rt, n, k):
    po = rt.polyop
    out = []
    for f in range(1, int(po.getNumFaces(n)) + 1):
        vs = [po.getVert(n, int(v)) for v in po.getFaceVerts(n, f)]
        out.append([sum(float(p.x) for p in vs) * k / len(vs), sum(float(p.y) for p in vs) * k / len(vs),
                    sum(float(p.z) for p in vs) * k / len(vs)])
    return out


def _remap_matids(rt, core, n, slots, ref_keys=None, k=1.0):
    """Face matIDs of a returned (Editable Poly) node back to the original IDs: by the reference face at the same
    centre (readback_max face keys), else by the sub-material name of the slot table."""
    mat = n.material
    by_centre = core.ids_by_centre(ref_keys, _face_centres(rt, n, k)) if ref_keys else []
    if (mat is None or not slots) and not any(x is not None for x in by_centre):
        return [], []
    if mat is None:
        imported = {}
    elif str(rt.classOf(mat)).lower() == 'multimaterial':
        imported = {}
        ids = list(mat.materialIDList)
        subs = list(mat.materialList)
        for mid, sub in zip(ids, subs):
            imported[int(mid)] = None if sub is None else str(sub.name)
    else:
        used = {int(rt.polyop.getFaceMatID(n, f)) for f in range(1, int(rt.polyop.getNumFaces(n)) + 1)}
        imported = {m: str(mat.name) for m in used}
    mapping, ambiguous = core.matid_remap(slots, imported)
    changed = []
    nf = int(rt.polyop.getNumFaces(n))
    cur = [int(rt.polyop.getFaceMatID(n, f)) for f in range(1, nf + 1)]
    if by_centre and all(x is not None for x in by_centre):
        ambiguous = []  # every face found at its reference place: the name remap is not needed
    for f, mid in enumerate(cur, 1):
        ref = by_centre[f - 1] if by_centre else None
        new = ref if ref is not None else mapping.get(mid, mid)
        if new != mid:
            rt.polyop.setFaceMatID(n, f, new)
            changed.append(f)
    return changed, ambiguous


def handoff_import(ctx, mode, nodes, preview):  # noqa: ARG001 - the input is the FBX of the bundle, not the selection
    rt = _rt()
    core, edit, host = ctx.core, ctx.edit, ctx.host
    mx, bc = _bridge()
    opt = core.check_options(core.TOOL_IMPORT, preview['plan']['options'] if preview is not None else ctx.options,
                             core.IMPORT_OPTIONS)
    bundle, manifest, sidecar, _mats = _bundle(core, opt)
    fbx = opt.get('fbx') or os.path.join(bundle, 'return', 'model.fbx')
    if not os.path.isfile(fbx):
        raise ValueError('handoff.import: no FBX from Blender at ' + fbx + ' (options.fbx)')
    rid = opt.get('request_id') or core.request_id_of(bundle)
    layer = host.contract.agent_layer(rid)
    agent_dir = opt.get('agent_dir') or os.path.join(bundle, 'agent_' + rid)
    if mode == 'preview' and os.path.exists(agent_dir):
        raise FileExistsError('refusing to overwrite: ' + agent_dir)
    lay = rt.LayerManager.getLayerFromName(layer)
    if lay is not None and any(str(n.layer.name) == layer for n in rt.objects):
        raise ValueError('layer {} already holds objects: accept or reject that work first'.format(layer))
    fbx_sha = _sha_file(fbx)
    by_name = {o['name']: o for o in manifest['objects']}
    entries = []
    for o in manifest['objects']:
        n = rt.maxOps.getNodeByHandle(int(o['handle']))
        f = [] if (n is not None and rt.isValidNode(n) and str(n.name) == o['name']) else \
            [edit.finding('original_missing', (), 'the original is not in this scene: no agr_agent_source')]
        entries.append(edit.entry(int(o['handle']), o['name'], f))
    state = {'fbx': fbx_sha, 'manifest': manifest['fbx']['sha256'], 'layer': layer,
             'objects': sorted(int(n.inode.handle) for n in rt.objects)}
    extra = {'options': opt, 'bundle': bundle, 'fbx': fbx, 'fbx_sha256': fbx_sha, 'request_id': rid, 'layer': layer,
             'agent_dir': agent_dir}
    if mode == 'preview':
        return edit.report(core.TOOL_IMPORT, 'preview', entries,
                           done=['import {} -> layer {}'.format(os.path.basename(fbx), layer),
                                 os.path.join(agent_dir, 'request.json'), os.path.join(agent_dir, 'baseline.json')],
                           state_hash=edit.fingerprint(state), extra=extra)
    edit.require_current(preview, state)
    baseline = mx.scene_hashes(rt)
    before = {int(n.inode.handle) for n in rt.objects}
    rt.pluginManager.loadClass(rt.FbxImporter)
    bad = _fbx_params(rt, (('Mode', rt.Name('create')), ('ScaleConversion', True),
                           ('ConvertUnit', _system_unit_code(rt, core)), ('UpAxis', 'Z'), ('SmoothingGroups', True),
                           ('Cameras', False), ('Lights', False), ('Animation', False)),
                      'FBXImporterSetParam', 'FBXImporterGetParam')
    ok = rt.importFile(fbx, rt.name('noPrompt'), using=rt.FBXIMP)
    new = [n for n in rt.objects if int(n.inode.handle) not in before]
    if not ok or not new:
        raise RuntimeError('handoff.import: the FBX import made no objects: ' + fbx)
    done, ambiguous = [], []
    with host.undo('AGR Tools: handoff.import ' + rid):
        lay = rt.LayerManager.getLayerFromName(layer) or rt.LayerManager.newLayerFromName(layer)
        for n in new:
            lay.addNode(n)
        restored = core.restore_names([str(n.name) for n in new], list(by_name))
        meshes = []
        for n in new:
            orig = restored.get(str(n.name))
            if orig is None:
                ambiguous.append('{}: not in the manifest (kept as is)'.format(n.name))
                continue
            if str(n.name) != orig:
                done.append('name {} -> {}'.format(n.name, orig))
                n.name = orig
            side = sidecar['objects'].get(orig, {})
            if side.get('user_props') is not None:
                rt.setUserPropBuffer(n, side['user_props'])
            o = by_name[orig]
            src = rt.maxOps.getNodeByHandle(int(o['handle']))
            if src is not None and rt.isValidNode(src) and str(src.name) == orig and int(src.inode.handle) not in \
                    {int(x.inode.handle) for x in new}:
                rt.setUserProp(n, 'agr_agent_source', str(int(src.inode.handle)))
            rt.setUserProp(n, 'agr_agent_request', rid)
            if _is_mesh(rt, n):
                meshes.append((n, o))
        for n, o in meshes:
            if str(rt.classOf(n)) != 'Editable_Poly':
                rt.convertToPoly(n)
        refs = {f['name']: f for f in _read_json(os.path.join(bundle, 'readback_max.json'))['objects']}
        k = host.m_per_unit()
        for n, o in meshes:
            if o['instance_of'] is None:
                ref = refs.get(o['name'])
                changed, amb = _remap_matids(rt, core, n, o['slots'], ref['face_keys'] if ref else None, k)
                ambiguous.extend('{}: {}'.format(o['name'], a) for a in amb)
                if changed:
                    done.append('{}: {} faces back to their matIDs'.format(o['name'], len(changed)))
        live = {str(n.name): n for n, _o in meshes}
        for n, o in meshes:
            lead = live.get(o['instance_of']) if o['instance_of'] else None
            if lead is None:
                continue
            if not rt.areNodesInstances(n, lead):
                rt.instanceReplace(n, lead)
                done.append('{}: instance of {} again'.format(o['name'], o['instance_of']))
        for n, o in meshes:
            if o['parent'] and o['parent'] in live and (n.parent is None or str(n.parent.name) != o['parent']):
                n.parent = live[o['parent']]
                done.append('{}: parent {}'.format(o['name'], o['parent']))
    os.makedirs(agent_dir)
    objects = []
    for n in new:
        src = rt.getUserProp(n, 'agr_agent_source')
        s = rt.maxOps.getNodeByHandle(int(src)) if src not in (None, '') else None
        if s is not None and rt.isValidNode(s):
            ref = host.contract.obj_ref('max', host.doc(), int(s.inode.handle), str(s.name))
            objects.append({'ref': ref, 'role': _role(rt, s), 'layer': str(s.layer.name)})
    bopt = bc.options({'task': 'Blender handoff {}: accept the returned model'.format(os.path.basename(bundle)),
                       'allowed_ops': ['keep'], 'request_id': rid})
    project = opt.get('project_id') or 'handoff'
    req = bc.build_request(bopt, rid, project, objects, [m['name'] for m in sidecar['markers']],
                           os.path.relpath(fbx, agent_dir), fbx_sha, {}, [],
                           'agent.accept (panel) with options.request = ' + os.path.join(agent_dir, 'request.json'))
    edit.write_new(os.path.join(agent_dir, 'request.json'), _json_bytes(req))
    edit.write_new(os.path.join(agent_dir, 'baseline.json'),
                   json.dumps({'schema': 1, 'request_id': rid, 'doc': host.doc(), 'objects': baseline},
                              sort_keys=True).encode('utf-8'))
    done.append('{} objects -> layer {}'.format(len(new), layer))
    if bad:
        ambiguous.append('FBX importer did not take {}'.format(bad))
    return edit.report(core.TOOL_IMPORT, 'apply', entries, done=done, ambiguous=ambiguous,
                       extra={'request_id': rid, 'layer': layer, 'agent_dir': agent_dir,
                              'request': os.path.join(agent_dir, 'request.json'),
                              'imported': [str(n.name) for n in new]})


# ---- verify --------------------------------------------------------------------------------------------------------
def _layer_meshes(rt, layer):
    return [n for n in rt.objects if str(n.layer.name) == layer and _is_mesh(rt, n)]


def handoff_verify(ctx, mode, nodes, preview):  # noqa: ARG001 - read row: preview only
    rt = _rt()
    core, edit, host = ctx.core, ctx.edit, ctx.host
    opt = core.check_options(core.TOOL_VERIFY, ctx.options, core.VERIFY_OPTIONS)
    if mode != 'preview':
        raise ValueError('handoff.verify is read-only: there is no apply')
    bundle = opt.get('bundle')
    if not bundle or not os.path.isfile(os.path.join(bundle, 'readback_max.json')):
        raise ValueError('options.bundle must be the handoff folder with readback_max.json')
    ref = _read_json(os.path.join(bundle, 'readback_max.json'))['objects']
    if opt.get('layer'):
        targets = _layer_meshes(rt, opt['layer'])
    else:
        targets = [n for n in (nodes or []) if rt.isValidNode(n) and _is_mesh(rt, n)]
    if not targets:
        raise ValueError('handoff.verify: empty input - select the returned objects or name options.layer')
    k = host.m_per_unit()
    got, _leaders = scene_facts(rt, targets, k, core)
    got = [fa for fa, _e in got]
    result = core.compare(ref, got)
    sides = {'max': result}
    if opt.get('blender_readback'):
        bl = _read_json(opt['blender_readback'])['objects']
        sides['blender'] = core.compare(ref, bl, check_roles=False)
    by = {}
    handles = {str(n.name): int(n.inode.handle) for n in targets}
    for side, res in sides.items():
        for row, items in res.items():
            for name, detail in items:
                by.setdefault(name, []).append(edit.finding(row, (), '{}: {}'.format(side, detail)))
    # an object missing after the round trip has no handle here: a number above every node handle names it
    uniq = [edit.entry(handles.get(n, 10 ** 9 + i), n, f) for i, (n, f) in enumerate(sorted(by.items()))]
    tables = {side: core.summary_table(res) for side, res in sides.items()}
    done = ['{} {}: {} расхождений'.format(side, row[1], row[2]) for side, t in tables.items() for row in t]
    state = {'ref': core.canonical(ref)[:64], 'got': [core.geometry_hash(f) for f in got]}
    return edit.report(core.TOOL_VERIFY, 'preview', uniq, done=done, state_hash=edit.fingerprint(state),
                       extra={'options': opt, 'tables': tables,
                              'discrepancies': {s: core.discrepancy_count(r) for s, r in sides.items()}})


# ---- restore materials ---------------------------------------------------------------------------------------------
def _restore_targets(rt, ctx, opt, nodes, preview):
    if preview is not None:
        out = []
        for h in preview['plan']['targets']:
            n = rt.maxOps.getNodeByHandle(int(h))
            if n is None or not rt.isValidNode(n):
                raise ctx.edit.StalePreview('object #{} of the preview is gone; run preview again'.format(h))
            out.append(n)
        return out
    if opt.get('layer'):
        return [n for n in rt.objects if str(n.layer.name) == opt['layer']]
    return [n for n in (nodes or []) if rt.isValidNode(n)]


def handoff_restore_materials(ctx, mode, nodes, preview):
    rt = _rt()
    core, edit, host = ctx.core, ctx.edit, ctx.host
    opt = core.check_options(core.TOOL_RESTORE, preview['plan']['options'] if preview is not None else ctx.options,
                             core.RESTORE_OPTIONS)
    path = opt.get('materials') or (os.path.join(opt['bundle'], 'materials.json') if opt.get('bundle') else None)
    if not path or not os.path.isfile(path):
        raise ValueError('«Восстановить материалы»: options.materials (materials.json) or options.bundle is required')
    reuse = opt.get('reuse', 'scene')
    if reuse not in ('scene', 'never'):
        raise ValueError('reuse must be scene or never')
    raw = open(path, 'rb').read()
    doc = core.validate_materials(json.loads(raw.decode('utf-8')))
    targets = [n for n in _restore_targets(rt, ctx, opt, nodes, preview) if not _is_marker(host.contract, n)]
    if not targets:
        raise ValueError('«Восстановить материалы»: empty input - select the returned objects or name options.layer')
    tinfo = [{'handle': int(n.inode.handle), 'name': str(n.name), 'role': _role(rt, n)} for n in targets]
    pairs, un_json, un_scene, amb = core.restore_plan(doc['objects'], tinfo)
    by_h = {int(n.inode.handle): n for n in targets}
    entries = [edit.entry(h, name, [edit.finding('unmatched', (), why)]) for h, name, why in un_scene]
    skipped = [edit.skipped(name, why) for name, why in un_json]
    ambiguous = ['{}: {}'.format(n, why) for n, why in amb]
    plan_rows = ['{} <- {} ({})'.format(by_h[h].name, e['material'] and doc['nodes'][e['material']]['name'],
                                        e['material'] and doc['nodes'][e['material']]['class']) for h, e in pairs]
    state = {'materials': hashlib.sha256(raw).hexdigest(), 'targets': sorted(by_h),
             'names': sorted((h, str(n.name)) for h, n in by_h.items())}
    extra = {'options': opt, 'targets': sorted(by_h), 'materials_json': path}
    if mode == 'preview':
        return edit.report(core.TOOL_RESTORE, 'preview', entries, done=plan_rows, skipped_=skipped,
                           ambiguous=ambiguous, state_hash=edit.fingerprint(state), extra=extra)
    edit.require_current(preview, state)
    builder = MaterialBuilder(rt, doc['nodes'])
    done, reused, built = [], {}, {}
    roots = sorted({e['material'] for _h, e in pairs if e['material'] is not None})
    with host.undo('AGR Tools: handoff.restore_materials'):
        for key in roots:
            mat = None
            if reuse == 'scene':
                spec = doc['nodes'][key]
                for m in rt.sceneMaterials:
                    if str(m.name) == spec['name'] and str(rt.classOf(m)) == spec['class'] and \
                            _material_root_matches(rt, core, doc, key, m):
                        mat = m
                        reused[key] = True
                        break
            if mat is None:
                mat = builder.build(key)
                built[key] = mat
            reused.setdefault(key, False)
            builder.made[key] = mat
        for h, e in pairs:
            n = by_h[h]
            n.material = None if e['material'] is None else builder.made[e['material']]
            done.append('{} <- {}{}'.format(n.name, 'none' if e['material'] is None else
                                            doc['nodes'][e['material']]['name'],
                                            ' (scene material)' if e['material'] and reused.get(e['material']) else
                                            ' (rebuilt from materials.json)' if e['material'] else ''))
    # judge by re-reading what is assigned now: every parameter, map path and node name against materials.json
    w = MaterialWriter(rt)
    diffs = {}
    for key in roots:
        mat = builder.made.get(key)
        if mat is None:
            diffs[key] = ['class {} missing'.format(doc['nodes'][key]['class'])]
            continue
        diffs[key] = core.diff_nodes(doc['nodes'], key, w.nodes, w.ref(mat))
    for h, e in pairs:
        d = diffs.get(e['material']) or []
        if d:
            entries.append(edit.entry(h, str(by_h[h].name), [edit.finding('param_differs', (), x) for x in d[:20]]))
    for err in builder.errors:
        ambiguous.append(err)
    return edit.report(core.TOOL_RESTORE, 'apply', entries, done=done, skipped_=skipped, ambiguous=ambiguous,
                       extra={'materials_json': path, 'rebuilt': sorted(doc['nodes'][k]['name'] for k in built),
                              'reused': sorted(doc['nodes'][k]['name'] for k, v in reused.items() if v),
                              'diff_count': sum(len(v) for v in diffs.values())})
