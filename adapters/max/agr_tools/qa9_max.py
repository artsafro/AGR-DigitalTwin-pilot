"""new-case: AGR Tools 0.9 (#979) QA 0.9, 3ds Max side (branch C, improve/issue-979-qa).

runtime.edits_090 calls `<function>(ctx, mode, nodes, preview)` for `qa_address` (qa.address), `qa_normals`
(qa.normals), `qa_sintez` (qa.sintez), `qa_procedural_objects` (qa.procedural_objects). All four are read rows:
preview only (the dispatcher refuses apply), the scene is not changed — no material, viewport, command-panel or
selection change (lab L05 qa.normals D6/D7: GeoAGR View Normals swaps materials and Nitrous settings).
ctx: agr (runtime globals), core (qa9_core), edit (edit_core), emax (edit_max), options (dict of the preview).
Import pymxs inside functions so this file loads under plain pytest.

Metres: metres per system unit from units.SystemType × units.SystemScale (never the string units.decodeValue,
#979 «Единицы»: on ru-RU decodeValue "1.5m" gives 1.0).
"""
import os

UNIT_M = {'inches': 0.0254, 'feet': 0.3048, 'miles': 1609.344, 'millimeters': 0.001, 'centimeters': 0.01,
          'meters': 1.0, 'kilometers': 1000.0}


def _rt():
    from pymxs import runtime
    return runtime


def _handle(n):
    return int(_rt().getHandleByAnim(n))


def metres_per_unit(rt=None):
    rt = rt or _rt()
    kind = str(rt.units.SystemType).lstrip('#').lower()
    if kind not in UNIT_M:
        raise ValueError('unmapped system unit type: ' + kind)
    scale = float(rt.units.SystemScale)
    if not scale > 0:
        raise ValueError('invalid units.SystemScale: ' + str(scale))
    return UNIT_M[kind] * scale


def _flags(n):
    try:
        hidden = bool(n.isHidden) or bool(n.layer.isHidden)
    except Exception:  # noqa: BLE001
        hidden = bool(n.isHidden)
    return hidden, bool(n.isFrozen)


def _targets(nodes, default='geometry'):
    rt = _rt()
    if nodes is None:
        nodes = list(rt.selection) or list(rt.geometry if default == 'geometry' else rt.objects)
    nodes = [n for n in nodes if rt.isValidNode(n)]
    return sorted(nodes, key=_handle)


def _package_dir(ctx):
    return os.path.dirname(os.path.abspath(ctx.core.__file__))


def _resolve(path):
    """Absolute as is; relative to the repo checkout (AGR_TOOLS_REPO, the polygon fixtures) else to the cwd."""
    path = os.fspath(path)
    if os.path.isabs(path):
        return path
    repo = os.environ.get('AGR_TOOLS_REPO')
    return os.path.join(repo, path) if repo else os.path.abspath(path)


def _check_mode(mode, tool):
    if mode != 'preview':
        raise ValueError(tool + ' is read-only: preview only')


# ---- qa.address ------------------------------------------------------------------------------------------
def qa_address(ctx, mode, nodes, preview):
    core, edit = ctx.core, ctx.edit
    _check_mode(mode, 'qa.address')
    opts = dict(ctx.options)
    extra = set(opts) - {'addresses', 'max_length', 'streets'}
    if extra:
        raise ValueError('unknown qa.address options: ' + ', '.join(sorted(extra)))
    max_length = opts.get('max_length', core.ADDRESS_MAX)
    if isinstance(max_length, bool) or not isinstance(max_length, int) or not 1 <= max_length <= core.NAME_MAX:
        raise ValueError('max_length must be an integer 1..{}'.format(core.NAME_MAX))
    folder = _resolve(opts['streets']) if opts.get('streets') else os.path.join(_package_dir(ctx), 'data', 'streets')
    directory = core.load_directory(folder)
    items, skipped = [], []
    if opts.get('addresses') is not None:
        if not isinstance(opts['addresses'], list) or not all(isinstance(a, str) for a in opts['addresses']):
            raise ValueError('addresses must be a list of strings')
        # no scene object: one row per address, handle = 1-based position (as qa.package files)
        items = [(i, 'Address #{}: {!r}'.format(i, a), a) for i, a in enumerate(opts['addresses'], 1)]
        source = 'options'
    else:
        for n in _targets(nodes):
            name = str(n.name)
            a = core.address_of_name(name)
            if a is None:
                skipped.append(edit.skipped(name, 'не объект SM_<Address>_…_<Type>: Address не извлекается'))
                continue
            items.append((_handle(n), name, a))
        source = 'scene'
    state = {'tool': 'qa.address', 'items': [list(x) for x in items], 'max_length': max_length,
             'directory': directory.sources}
    return core.address_report(edit, items, directory, edit.fingerprint(state), max_length, skipped,
                               extra={'source': source})


# ---- qa.normals ------------------------------------------------------------------------------------------
def _opacity(mat):
    """Material (or a sub-material) has an opacity/cutout map: polygons seen from both sides need a 2nd side."""
    rt = _rt()
    if mat is None or mat == rt.undefined:
        return False
    try:
        if rt.classOf(mat) == rt.Multimaterial:
            return any(_opacity(m) for m in mat.materialList if m is not None)
    except Exception:  # noqa: BLE001
        pass
    for prop in ('opacityMap', 'cutout_map', 'opacity_map'):
        try:
            v = getattr(mat, prop)
        except Exception:  # noqa: BLE001
            continue
        if v is not None and v != rt.undefined:
            return True
    return False


def _poly_ids(n, numfaces):
    """Poly face of each snapshot triangle for an Editable_Poly without modifiers (triangles of poly i are
    consecutive, deg-2 each); else None (the report then names triangles)."""
    rt = _rt()
    try:
        if rt.classOf(n) != rt.Editable_Poly or int(n.modifiers.count) != 0:
            return None
        ids = []
        for f in range(1, int(rt.polyop.getNumFaces(n)) + 1):
            ids += [f] * (int(rt.polyop.getFaceDeg(n, f)) - 2)
    except Exception:  # noqa: BLE001
        return None
    return ids if len(ids) == numfaces else None


def read_mesh(n, m_per_unit):
    """World-space snapshot in metres: verts, 0-based faces, smoothing groups, face ids (poly or triangle)."""
    rt = _rt()
    mesh = rt.snapshotAsMesh(n)
    try:
        nv, nf = int(mesh.numverts), int(mesh.numfaces)
        verts = []
        for i in range(1, nv + 1):
            p = rt.getVert(mesh, i)
            verts.append((float(p.x) * m_per_unit, float(p.y) * m_per_unit, float(p.z) * m_per_unit))
        faces, sg = [], []
        for i in range(1, nf + 1):
            f = rt.getFace(mesh, i)
            faces.append((int(f.x) - 1, int(f.y) - 1, int(f.z) - 1))
            sg.append(int(rt.getFaceSmoothGroup(mesh, i)))
    finally:
        try:
            rt.delete(mesh)
        except Exception:  # noqa: BLE001
            pass
    poly = _poly_ids(n, len(faces))
    return {'verts': verts, 'faces': faces, 'sg': sg, 'face_ids': poly or [i + 1 for i in range(len(faces))],
            'id_kind': 'poly' if poly else 'tri'}


def qa_normals(ctx, mode, nodes, preview):
    core, edit = ctx.core, ctx.edit
    rt = _rt()
    _check_mode(mode, 'qa.normals')
    opts = core.normals_options(ctx.options)
    mpu = metres_per_unit(rt)
    objects, skipped, flags = [], [], {}
    for n in _targets(nodes):
        name = str(n.name)
        if not rt.canConvertTo(n, rt.TriMeshGeometry):
            skipped.append(edit.skipped(name, 'не геометрия: {}'.format(rt.classOf(n))))
            continue
        try:
            mesh = read_mesh(n, mpu)
        except RuntimeError as exc:  # e.g. Populate Crowd: convertible by class, no mesh (measured, Max 2024)
            skipped.append(edit.skipped(name, 'сетка не читается ({}): {}'.format(rt.classOf(n),
                                                                                  str(exc).splitlines()[-1][:200])))
            continue
        kind = core.object_kind(name)
        hidden, frozen = _flags(n)
        objects.append(dict(mesh, handle=_handle(n), name=name,
                            double_sided=kind in core.DOUBLE_SIDED_TYPES or _opacity(n.material)))
        flags[name] = {'hidden': hidden, 'frozen': frozen, 'ids': mesh['id_kind'], 'kind': kind}
    state = {'tool': 'qa.normals', 'snapshot': ctx.emax.snapshot([rt.getAnimByHandle(o['handle']) for o in objects]),
             'options': {k: v for k, v in opts.items()}, 'm_per_unit': mpu}
    return core.normals_report(edit, objects, opts, edit.fingerprint(state), skipped,
                               extra={'m_per_unit': mpu, 'flags': flags})


# ---- qa.sintez -------------------------------------------------------------------------------------------
def _file_sha(path):
    import hashlib
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def qa_sintez(ctx, mode, nodes, preview):
    core, edit = ctx.core, ctx.edit
    _check_mode(mode, 'qa.sintez')
    opts = dict(ctx.options)
    extra = set(opts) - {'sintez', 'preflight', 'package'}
    if extra:
        raise ValueError('unknown qa.sintez options: ' + ', '.join(sorted(extra)))
    if not opts.get('sintez'):
        raise ValueError('qa.sintez needs options.sintez: the SINTEZ AGR Checker report (JSON of run_agr_checker.py)')
    spath = _resolve(opts['sintez'])
    sintez = core.sintez_verdicts(core.read_json_file(spath, 'SINTEZ report'))
    files = {'sintez': {'path': spath, 'sha256': _file_sha(spath)}}
    preflight = package = None
    node_rows = None
    if opts.get('preflight'):
        p = _resolve(opts['preflight'])
        preflight = core.read_json_file(p, 'qa.preflight report')
        files['preflight'] = {'path': p, 'sha256': _file_sha(p)}
    if opts.get('package'):
        p = _resolve(opts['package'])
        package = core.read_json_file(p, 'qa.package report')
        files['package'] = {'path': p, 'sha256': _file_sha(p)}
    if preflight is None and package is None:
        # our side from the scene: qa.preflight on the same targets, without touching the selection
        preflight = ctx.agr.checks_070('preflight', nodes, False)
        node_rows = [(o['handle'], o['name']) for o in preflight['objects']]
        files['preflight'] = {'path': None, 'scene': True, 'status': preflight['status']}
    rows = core.sintez_compare(sintez, preflight, package)
    state = {'tool': 'qa.sintez', 'files': files, 'preflight': edit.fingerprint(preflight) if preflight else None}
    return core.sintez_report(edit, rows, edit.fingerprint(state), node_rows, extra={'inputs': files})


# ---- qa.procedural_objects ------------------------------------------------------------------------------
_SUPERCLASSES = ('GeometryClass', 'shape', 'helper', 'light', 'camera', 'SpacewarpObject', 'System')


def available_classes():
    """Lower-case names of every creatable/known class of the node superclasses in THIS Max (by name: no
    `execute`, so a class of an absent plugin never breaks the scan — lab L07 acceptance 3)."""
    rt = _rt()
    out = set()
    for sc in _SUPERCLASSES:
        try:
            cls = getattr(rt, sc)
            for c in cls.classes:
                out.add(str(c).lower())
        except Exception:  # noqa: BLE001 - a superclass this Max does not expose
            continue
    return out


def qa_procedural_objects(ctx, mode, nodes, preview):
    """Report only: nothing is collapsed, selected or converted (decision of Artem 05.11.2026, #973 conflict 8).
    Default target: ALL scene nodes (procedural objects are helpers too: Populate Crowd)."""
    core, edit = ctx.core, ctx.edit
    rt = _rt()
    _check_mode(mode, 'qa.procedural_objects')
    if ctx.options:
        raise ValueError('qa.procedural_objects takes no options')
    classes = core.load_classes(os.path.join(_package_dir(ctx), 'data', 'procedural_classes.json'))
    targets = list(nodes) if nodes is not None else list(rt.objects)
    targets = sorted((n for n in targets if rt.isValidNode(n)), key=_handle)
    rows = []
    for n in targets:
        hidden, frozen = _flags(n)
        rows.append({'handle': _handle(n), 'name': str(n.name), 'cls': str(rt.classOf(n)),
                     'superclass': str(rt.superClassOf(n)), 'hidden': hidden, 'frozen': frozen})
    hits, products = core.procedural_scan(rows, classes, available_classes())
    state = {'tool': 'qa.procedural_objects', 'rows': rows}
    return core.procedural_report(edit, rows, hits, products, edit.fingerprint(state))
