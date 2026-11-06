"""new-case: AGR Tools 1.0 (#1024) material table (K3), 3ds Max side. Stub of branch 0; owned by branch L (improve/issue-1024-materials).

runtime.edits_100 calls `mat_table(ctx, mode, nodes, preview)` for mat.table (plan mode `undo`).
ctx: agr (runtime globals), core (matlib_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost: ObjRef, user props, one undo record).
Import pymxs inside functions so this file loads under plain pytest.

preview: reads face material IDs (in-memory snapshotAsMesh copies) and `agr_role` of the selected objects, checks
them against the library (matlib_core.table_plan) and plans the per-mesh UDIM table and the Multi/Sub.
apply (unaltered preview, unchanged scene): ONE undo record, selection restored. Builds one Multi/Sub
`AGR_Library_<version>` of Physical materials (library ids = sub-material ids), assigns it to the objects without
findings, writes user props `agr_udim_table` (JSON {library_id: udim}) and `agr_library` (version) on them, and
writes the project table as a NEW sidecar `materials_table.json` beside the passport (scene file property
`agr_passport`, contract_core.PASSPORT_PROP). Without a linked passport the table stays in the report and the user
props (skipped item `passport`). No geometry change, no new MAXScript globals, no clearUndoBuffer.
"""
import json
import os

UDIM_PROP = 'agr_udim_table'
LIBRARY_PROP = 'agr_library'


def _rt():
    from pymxs import runtime
    return runtime


def _library_path(ctx):
    p = ctx.options.get('library')
    if p:
        return str(p)
    return str(ctx.agr._repo_root() / 'library' / 'materials' / 'materials.json')


def _face_ids(node):
    """{mat_id: faces} of a node from an in-memory snapshot; None for non-geometry."""
    rt = _rt()
    try:
        if rt.superClassOf(node) != rt.GeometryClass or not rt.canConvertTo(node, rt.TriMeshGeometry):
            return None
        m = rt.snapshotAsMesh(node)
    except Exception:  # noqa: BLE001 - helpers, shapes, targets have no faces
        return None
    try:
        counts = {}
        for i in range(1, int(m.numfaces) + 1):
            k = int(rt.getFaceMatID(m, i))
            counts[k] = counts.get(k, 0) + 1
        return counts
    finally:
        rt.delete(m)


def _passport():
    """{'path', 'sha256'} of the scene file property agr_passport or None."""
    rt = _rt()
    try:
        idx = int(rt.fileProperties.findProperty(rt.name('custom'), 'agr_passport'))
        if idx <= 0:
            return None
        value = json.loads(str(rt.fileProperties.getPropertyValue(rt.name('custom'), idx)))
        if isinstance(value, dict) and isinstance(value.get('path'), str):
            return {'path': value['path'], 'sha256': value.get('sha256')}
    except Exception:  # noqa: BLE001 - a broken property is "no passport", reported as skipped
        return None
    return None


def _items(ctx, nodes):
    rt = _rt()
    items, skipped = [], []
    for n in nodes or ():
        if not rt.isValidNode(n):
            continue
        name = str(n.name)
        ids = _face_ids(n)
        if ids is None:
            skipped.append(ctx.edit.skipped(name, 'not a mesh object (no faces)'))
            continue
        ref, = ctx.host.refs([n])
        try:
            role = ctx.host.role(ref)
        except ValueError as exc:
            role = 'invalid:' + str(exc)[:60]
        items.append({'handle': int(ctx.emax.handle(n)), 'name': name, 'role': role, 'ids': ids,
                      'node_handle': int(n.inode.handle)})
    return items, skipped


def _state(items, library, passport):
    return {'objects': [[i['handle'], i['name'], i['role'], sorted([int(k), int(v)] for k, v in i['ids'].items())]
                        for i in items], 'library': library['sha256'], 'passport': passport}


def _plan(ctx, nodes):
    core, edit = ctx.core, ctx.edit
    library = core.load_library(_library_path(ctx))
    items, skipped_nodes = _items(ctx, nodes)
    if not items:
        raise ValueError('mat.table: empty input (select the mid-poly objects with faces)')
    entries, table, multisub, skipped = core.table_plan(edit, items, library)
    passport = _passport()
    skipped = skipped_nodes + skipped
    if passport is None:
        skipped.append(edit.skipped('passport', 'no agr_passport scene property: the table stays in the report '
                                                'and in the agr_udim_table user props'))
    return library, items, entries, table, multisub, skipped, passport


def _physical(spec):
    rt = _rt()
    m = rt.PhysicalMaterial(name=spec['name'])
    r, g, b = spec['rgb']
    m.base_color = rt.Color(r, g, b)
    m.roughness = float(spec['roughness'])
    m.metalness = float(spec['metallic'])
    if spec['emissive'] > 0:
        m.emission = float(spec['emissive'])
        m.emit_color = rt.Color(r, g, b)
    if spec['opacity'] < 1.0:
        m.transparency = 1.0 - float(spec['opacity'])
    return m


def _multisub(name, subs):
    """One Multi/Sub where slot k IS library id k (slots 1..max id; slots of unused ids stay empty).

    Native jobs 20261106-044745-a019ac0d, -045136-6234cfee, -045542-9027fdbf, -050032-8bd24ced (Max 2024): writing
    materialIDList (per element or as a whole array) inserts slots or is undone later - after the assignment the list
    read [3, 7, 12, 31, 39, 1, 2, 4, 5] - and .numsubs reads the highest id. So no id is ever written: the default ids
    1..N of `multimaterial numsubs:N` are kept and only the sub-materials of the used ids are set."""
    rt = _rt()
    ids = [int(s['id']) for s in subs]
    top = max(ids)
    mm = rt.MultiMaterial(name=name, numsubs=top)
    for k in range(1, top + 1):
        rt.setSubMtl(mm, k, None)
    for spec in subs:
        rt.setSubMtl(mm, int(spec['id']), _physical(spec))
    _check_multisub(mm, subs)
    return mm


def _check_multisub(mm, subs):
    """Readback: ids 1..max, the used slots carry their library materials, the other slots are empty."""
    rt = _rt()
    want = {int(s['id']): s['name'] for s in subs}
    got_ids = [int(x) for x in mm.materialIDList]
    if got_ids != list(range(1, max(want) + 1)):
        raise RuntimeError('Multi/Sub ids readback {}'.format(got_ids))
    used = {}
    for k in got_ids:
        sub = rt.getSubMtl(mm, k)
        if sub is not None and sub != rt.undefined:
            used[k] = str(sub.name)
    if used != want:
        raise RuntimeError('Multi/Sub slots readback {} != {}'.format(used, want))

def mat_table(ctx, mode, nodes, preview):
    core, edit = ctx.core, ctx.edit
    if mode == 'apply':  # options belong to the preview (runtime refuses options with apply)
        ctx.options = dict(preview['plan'].get('options') or {})
    library, items, entries, table, multisub, skipped, passport = _plan(ctx, nodes)
    state = edit.fingerprint(_state(items, library, passport))
    if mode == 'preview':
        return core.report(edit, 'preview', entries, table, multisub, skipped, library, state_hash=state,
                           extra={'passport': passport, 'library_path': library['path'],
                                  'options': dict(ctx.options)})
    edit.require_current(preview, _state(items, library, passport))
    rt = _rt()
    ok = {i['name'] for i in items if not any(e['findings'] for e in entries if e['handle'] == i['handle'])}
    tables = core.udim_tables(table)
    done, written = [], None
    if multisub:
        with ctx.emax.session('mat.table'):
            mm = _multisub(core.multisub_name(library), multisub)
            for i in items:
                if i['name'] not in ok:
                    continue
                n = rt.maxOps.getNodeByHandle(i['node_handle'])
                n.material = mm
                rt.setUserProp(n, UDIM_PROP, json.dumps({str(k): v for k, v in sorted(tables[i['name']].items())}))
                rt.setUserProp(n, LIBRARY_PROP, library['version'])
                done.append(i['name'])
        for name in done:  # readback after the assignment (job 20261106-050032-8bd24ced: ids changed after it)
            n = rt.getNodeByName(name)
            if n is None or n.material is None or str(n.material.name) != core.multisub_name(library):
                raise RuntimeError('mat.table readback: material of {} not assigned'.format(name))
            _check_multisub(n.material, multisub)
    if passport and table:
        folder = os.path.dirname(passport['path'])
        target = edit.new_path(os.path.join(folder, 'materials_table.json'), version=True)
        doc = core.table_doc(library, table, passport)
        written = edit.write_new(target, (json.dumps(doc, ensure_ascii=False, indent=1) + '\n').encode('utf-8'))
    return core.report(edit, 'apply', entries, table, multisub, skipped, library, done=done,
                       extra={'passport': passport, 'library_path': library['path'], 'written': written})
