"""new-case: AGR Tools 0.9 (#979) qa.facade_compare, 3ds Max side (branch C, improve/issue-979-qa).

runtime.edits_090 calls `qa_facade_compare(ctx, mode, nodes, preview)` (read row: preview only).
ctx: agr (runtime globals), core (facade_core), edit (edit_core), emax (edit_max), options (dict of the preview).
Import pymxs inside functions so this file loads under plain pytest.

The model panel is NOT a render: the evaluated mesh (snapshotAsMesh, world space, metres via SystemType ×
SystemScale) is rasterised orthographically by facade_core at a fixed px/m. No renderer switch, no camera, no
viewport or Nitrous setting is touched (defect `apply_atlas_uv`, T06: renderer swapped) — nothing to restore.
Shading per face: the diffuse bitmap (PNG/BMP/PGM, read by facade_core) at UV channel 1, else the diffuse colour of
the material (Multimaterial by material ID), else the wire colour. The picture «лист | ВПМ | НПМ» is a NEW PNG
(edit_core.new_path(version=True) + write_new) in options.out or the per-scene reports folder.
"""
import os

UNIT_M = {'inches': 0.0254, 'feet': 0.3048, 'miles': 1609.344, 'millimeters': 0.001, 'centimeters': 0.01,
          'meters': 1.0, 'kilometers': 1000.0}


def _rt():
    from pymxs import runtime
    return runtime


def _handle(n):
    return int(_rt().getHandleByAnim(n))


def _undef(v):
    return v is None or v == _rt().undefined


def metres_per_unit(rt):
    kind = str(rt.units.SystemType).lstrip('#').lower()
    if kind not in UNIT_M:
        raise ValueError('unmapped system unit type: ' + kind)
    return UNIT_M[kind] * float(rt.units.SystemScale)


def _resolve(path):
    path = os.fspath(path)
    if os.path.isabs(path):
        return path
    repo = os.environ.get('AGR_TOOLS_REPO')
    return os.path.join(repo, path) if repo else os.path.abspath(path)


def _colour(c):
    return (int(round(float(c.r))), int(round(float(c.g))), int(round(float(c.b))))


def _sub_material(mat, mat_id):
    rt = _rt()
    if _undef(mat):
        return None
    try:
        if rt.classOf(mat) == rt.Multimaterial:
            ids = [int(i) for i in mat.materialIDList]
            subs = list(mat.materialList)
            if mat_id in ids:
                return subs[ids.index(mat_id)]
            return subs[(mat_id - 1) % len(subs)] if subs else None
    except Exception:  # noqa: BLE001
        return mat
    return mat


def _shading(core, mat, cache):
    """(texture Image or None, flat colour) of one (sub)material."""
    rt = _rt()
    key = None if _undef(mat) else int(rt.getHandleByAnim(mat))
    if key in cache:
        return cache[key]
    tex, col = None, None
    if key is not None:
        for prop in ('diffuseMap', 'base_color_map'):
            try:
                m = getattr(mat, prop)
            except Exception:  # noqa: BLE001
                continue
            if not _undef(m):
                try:
                    path = str(m.filename)
                    if path and os.path.isfile(path):
                        tex = core.read_image(path)
                except Exception:  # noqa: BLE001 - unreadable texture: flat colour
                    tex = None
                break
        for prop in ('diffuse', 'base_color', 'Diffuse'):
            try:
                col = _colour(getattr(mat, prop))
                break
            except Exception:  # noqa: BLE001
                continue
    cache[key] = (tex, col)
    return cache[key]


def facade_triangles(core, n, mpu):
    """[((p0, p1, p2) metres, shade)] of the evaluated mesh of one node."""
    rt = _rt()
    mesh = rt.snapshotAsMesh(n)
    out, cache = [], {}
    wire = _colour(n.wirecolor)
    try:
        has_uv = bool(rt.meshop.getMapSupport(mesh, 1))
        for i in range(1, int(mesh.numfaces) + 1):
            f = rt.getFace(mesh, i)
            pts = []
            for k in (f.x, f.y, f.z):
                p = rt.getVert(mesh, int(k))
                pts.append((float(p.x) * mpu, float(p.y) * mpu, float(p.z) * mpu))
            sub = _sub_material(n.material, int(rt.getFaceMatID(mesh, i)))
            tex, col = _shading(core, sub, cache)
            shade = col or wire
            if tex is not None and has_uv:
                mf = rt.meshop.getMapFace(mesh, 1, i)
                uvs = []
                for k in (mf.x, mf.y, mf.z):
                    v = rt.meshop.getMapVert(mesh, 1, int(k))
                    uvs.append((float(v.x), float(v.y)))
                shade = core.texture_shader(tex, uvs, shade)
            out.append((tuple(pts), shade))
    finally:
        try:
            rt.delete(mesh)
        except Exception:  # noqa: BLE001
            pass
    return out


def _out_dir(ctx, opts):
    folder = _resolve(opts['out']) if opts.get('out') else os.path.join(ctx.agr.reports_dir(), 'facade_compare')
    os.makedirs(folder, exist_ok=True)
    return folder


def qa_facade_compare(ctx, mode, nodes, preview):
    core, edit = ctx.core, ctx.edit
    rt = _rt()
    if mode != 'preview':
        raise ValueError('qa.facade_compare is read-only: preview only')
    opts = core.facade_options(ctx.options)
    if nodes is None:
        nodes = list(rt.selection)
    targets = sorted((n for n in nodes if rt.isValidNode(n)), key=_handle)
    if not targets:
        raise ValueError('qa.facade_compare: select the VPM facade object(s)')
    mpu = metres_per_unit(rt)
    results, skipped, sheets_sha, models = [], [], {}, []
    folder = None
    for n in targets:
        name = str(n.name)
        spec = opts['sheets'].get(name) or opts['sheets'].get('*')
        if spec is None:
            skipped.append(edit.skipped(name, 'нет листа фасада для объекта (options.sheets)'))
            continue
        path = _resolve(spec['path'])
        if not os.path.isfile(path):
            raise ValueError('sheet image not found: ' + path)
        import hashlib
        with open(path, 'rb') as f:
            sheets_sha[name] = hashlib.sha256(f.read()).hexdigest()
        sheet = core.mask_background(core.read_image(path))
        facade = spec.get('facade', opts['facade'])
        vpm_img, view = core.rasterize(facade_triangles(core, n, mpu), facade, opts['px_per_m'], opts['max_px'])
        panels = {'vpm': vpm_img}
        models.append(n)
        npm_name = (opts['npm'] or {}).get(name)
        if npm_name:
            m = rt.getNodeByName(npm_name)
            if _undef(m):
                raise ValueError('NPM object not found: ' + npm_name)
            panels['npm'] = core.rasterize(facade_triangles(core, m, mpu), facade, opts['px_per_m'], opts['max_px'])[0]
            models.append(m)
        c = core.compare(sheet, float(spec['px_per_m']), panels, opts['px_per_m'], opts['rows'], opts['dark'])
        folder = folder or _out_dir(ctx, opts)
        safe = ''.join(ch if ch.isalnum() or ch in '_-' else '_' for ch in name)
        target = edit.new_path(os.path.join(folder, 'facade_{}.png'.format(safe)), version=True)
        edit.write_new(target, core.write_png(core.compose(c['panels'])))
        c.pop('panels')
        results.append({'handle': _handle(n), 'name': name, 'compare': c, 'image': target, 'view': view,
                        'sheet_path': path})
    state = {'tool': 'qa.facade_compare', 'snapshot': ctx.emax.snapshot(models) if models else [],
             'sheets': sheets_sha, 'options': {k: v for k, v in opts.items() if k != 'sheets'}}
    return core.facade_report(edit, results, edit.fingerprint(state), skipped,
                              extra={'m_per_unit': mpu, 'px_per_m': opts['px_per_m']})
