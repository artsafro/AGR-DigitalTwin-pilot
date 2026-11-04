"""new-case: AGR Tools 0.8 (#908) package, 3ds Max side; owned by branch D (improve/issue-908-package).

runtime.edits_080 calls `<function>(ctx, mode, nodes, preview)` for `qa_package` (qa.package), `export_zip`
(export.zip), `export_ground_fbx` (export.ground_fbx), `export_geojson_write` (export.geojson_write).
ctx: agr (runtime globals), core (package_core), edit (edit_core), emax (edit_max), options (dict of the preview).
Import pymxs inside functions so this file loads under plain pytest.

Paths: `options.path` (qa.package: a ZIP/FBX/GeoJSON or a folder of ZIPs) / `options.folder` (export.zip, the
delivery folder). Without options the folder of `AGR_EXPORT_PATH` on the selected nodes is used, else the folder of
the open .max file. The validator runs in the project interpreter (AGR_PYTHON, else <repo>/.venv), as the export.
"""
import os


def _rt():
    from pymxs import runtime
    return runtime


def _python(root):
    return os.environ.get('AGR_PYTHON') or os.path.join(str(root), '.venv', 'Scripts', 'python.exe')


def _validator(ctx):
    """(runner, python, root) for the pilot validator; a missing interpreter is a named error, not a pass."""
    root = ctx.agr._repo_root()
    python = _python(root)
    if not os.path.isfile(python):
        raise ValueError('unmapped python ' + python + ' (set AGR_PYTHON to the project interpreter)')
    runner = getattr(ctx, 'runner', None) or ctx.core.subprocess_runner
    return runner, python, root


def _default_folder(ctx, nodes):
    """Folder of AGR_EXPORT_PATH on the given/selected nodes (all must agree), else of the open .max file."""
    rt = _rt()
    pool = list(nodes) if nodes is not None else list(rt.selection)
    folders = set()
    for n in pool:
        p = ctx.agr._prop(n, 'AGR_EXPORT_PATH')
        if p:
            folders.add(os.path.dirname(os.path.abspath(p)))
    if len(folders) > 1:
        raise ValueError('AGR_EXPORT_PATH points to several folders: {}; pass options.folder'.format(sorted(folders)))
    if folders:
        return folders.pop()
    if str(rt.maxFilePath):
        return str(rt.maxFilePath)
    raise ValueError('no delivery folder: pass options.path/options.folder or save the scene')


def qa_package(ctx, mode, nodes, preview):
    """Read-only: the validator on a ZIP (or every ZIP of a folder), `--scene` by default (lab L04)."""
    opts = ctx.options
    path = opts.get('path') or _default_folder(ctx, nodes)
    runner, python, root = _validator(ctx)
    return ctx.core.qa_package(ctx.edit, path, runner, python, root, profile=opts.get('profile'),
                               scene=bool(opts.get('scene', True)), options=opts)


def export_zip(ctx, mode, nodes, preview):
    """preview: the archive plan; apply: new ZIPs of that plan, each checked by the validator (no Blender)."""
    if mode == 'preview':
        opts = dict(ctx.options)
        folder = opts.get('folder') or _default_folder(ctx, nodes)
        opts['folder'] = os.path.abspath(folder)
        return ctx.core.zip_preview(ctx.edit, folder, opts.get('address'), options=opts)
    runner, python, root = _validator(ctx)

    def validate_fn(target):
        return ctx.core.validate(target, runner, python, root, profile=None,
                                 scene=bool(preview['plan']['options'].get('scene', False)))
    return ctx.core.zip_apply(ctx.edit, preview, validate_fn)


# ---- export.ground_fbx -----------------------------------------------------------------------------------------
def _material_class(rt, mat):
    if mat is None or mat == rt.undefined:
        return None
    cls = str(rt.classOf(mat))
    if cls.lower() == 'multimaterial':
        subs = {str(rt.classOf(s)) for s in mat.materialList if s is not None and s != rt.undefined}
        return 'Standardmaterial' if subs <= {'Standardmaterial'} else 'Multimaterial(' + ','.join(sorted(subs)) + ')'
    return cls


def _node_facts(rt, nodes):
    import math
    out = []
    for n in nodes:
        p = n.pivot
        out.append({'handle': int(rt.getHandleByAnim(n)), 'name': str(n.name),
                    'geometry': str(rt.superClassOf(n)) == 'GeometryClass',
                    'material': _material_class(rt, n.material),
                    'pivot_m': math.sqrt(float(p.x) ** 2 + float(p.y) ** 2 + float(p.z) ** 2) * _metres(rt),
                    'hidden': bool(n.isHidden)})
    return out


def _metres(rt):
    """Metres per system unit (the guard is in metres whatever the scene units)."""
    return 1.0 / float(rt.units.decodeValue('1m'))


def _ground_nodes(ctx, nodes):
    rt = _rt()
    if nodes is None:
        nodes = list(rt.selection) or [n for n in rt.geometry]
    return sorted((n for n in nodes if rt.isValidNode(n)), key=lambda n: int(rt.getHandleByAnim(n)))


def _ground_inputs(ctx, nodes, opts):
    rt = _rt()
    pool = _ground_nodes(ctx, nodes)
    if not pool:
        raise ValueError('export.ground_fbx: no nodes (select the Ground and OKS meshes)')
    code = opts.get('code')
    if code is None:
        codes = {ctx.agr._prop(n, 'AGR_CODE') for n in pool} - {None}
        if len(codes) > 1:
            raise ValueError('AGR_CODE differs between nodes: {}'.format(sorted(codes)))
        code = codes.pop() if codes else None
    folder = opts.get('folder') or _default_folder(ctx, pool)
    facts = _node_facts(rt, pool)
    plan = ctx.core.ground_plan(facts, code, opts.get('address'), os.path.abspath(folder))
    state = {'nodes': ctx.emax.snapshot(pool), 'facts': facts, 'files': plan['files'], 'options': opts}
    return pool, facts, plan, state


def _set_fbx_params(rt, params):
    rt.pluginManager.loadClass(rt.FbxExporter)
    for key, value in params:
        rt.FBXExporterSetParam(key, value)
        got = rt.FBXExporterGetParam(key)
        if isinstance(value, bool):
            ok = str(got).lower() == str(value).lower()
        elif isinstance(value, float):
            ok = abs(float(got) - value) < 1e-9
        else:
            ok = str(got).lower() == str(value).lower()
        if not ok:
            raise ValueError('unmapped FBX export setting {}={!r} (wanted {!r})'.format(key, got, value))


def _export_selected(rt, nodes, target):
    """Export exactly `nodes` (the originals, unchanged: triangulation is an exporter flag) to a new file."""
    if os.path.exists(target):
        raise FileExistsError('refusing to overwrite: ' + target)
    partial = target[:-len('.fbx')] + '.partial.fbx'
    if os.path.exists(partial):
        raise FileExistsError('leftover ' + partial)
    try:
        rt.clearSelection()
        rt.select(nodes)
        if not rt.exportFile(partial, rt.Name('noPrompt'), selectedOnly=True, using=rt.FBXEXP) \
                or not os.path.isfile(partial):
            raise RuntimeError('FBX export failed: ' + target)
        os.link(partial, target)  # no clobber
    finally:
        if os.path.exists(partial):
            os.unlink(partial)


def export_ground_fbx(ctx, mode, nodes, preview):
    """NPM FBX split: `{code4}_{Address}_Ground.fbx` (Ground, GroundGlass, GroundEl, GroundElGlass, Flora) and
    `{code4}_{Address}_{NN}.fbx` per OKS; triangulated, new files only, selection restored, validator readback."""
    opts = dict(ctx.options) if mode == 'preview' else dict(preview['plan']['options'])
    pool, facts, plan, state = _ground_inputs(ctx, nodes, opts)
    if mode == 'preview':
        return ctx.core.ground_report(ctx.edit, 'preview', plan, facts, state, extra={'options': opts})
    ctx.edit.require_current(preview, state)
    if preview['status'] != 'pass':
        raise ValueError('export.ground_fbx: the preview has findings; fix them and preview again')
    rt = _rt()
    by_handle = {int(rt.getHandleByAnim(n)): n for n in pool}
    runner, python, root = _validator(ctx)
    before = ctx.emax.snapshot(pool)
    done, reports, extra_findings = [], [], {}
    with ctx.emax.session('export.ground_fbx'):
        _set_fbx_params(rt, ctx.core.GROUND_FBX_PARAMS)
        for f in plan['files']:
            if f['exists']:
                continue
            _export_selected(rt, [by_handle[h] for h in f['handles']], f['target'])
            done.append(f['name'])
    if ctx.emax.snapshot(pool) != before:
        raise RuntimeError('working objects changed during export')
    for f in plan['files']:
        if f['name'] not in done:
            continue
        table = ctx.core.validate(f['target'], runner, python, root, profile='npm',
                                  scene=bool(opts.get('scene', True)))
        table['file'] = f['name']
        reports.append(table)
        for stage in table['stages']:
            if stage['status'] == 'fail':
                for n in f['nodes']:
                    extra_findings.setdefault(n, []).append(
                        (stage['id'], f['name'] + ': ' + '; '.join(stage['non_pass'])[:900]))
    return ctx.core.ground_report(ctx.edit, 'apply', plan, facts, done=done, extra_findings=extra_findings,
                                  extra={'reports': reports, 'exit_code': ctx.core.worst_exit(reports) if reports
                                         else None})