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
