"""new-case: AGR Tools 1.0 (#1024) delivery in one button (`pack.deliver`, station 1.0.26), 3ds Max side. Branch S:
owned by branch S (improve/issue-1024-deliver).

runtime.edits_100 calls `pack_deliver(ctx, mode, nodes, preview)`.
ctx: agr (runtime globals), core (deliver_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost: ObjRef, user props, one undo record).
Import pymxs inside functions so this file loads under plain pytest.

Every step goes through the existing runtime entry points (no step logic here): checks_050 / checks_070 (select
off), edits_090 / edits_100 (preview, then apply with that preview for the file steps), export_preview /
export_commit (export.checked). Each nested dispatcher call is journalled by the runtime hook itself. The model of
export.checked: the given nodes, else every visible geometry node named `SM_*` / `UCX_*` outside layer AGR_export.
The scene is never changed by pack.deliver itself; the apply writes only into a new `Сдача_<time>` folder.
"""
import datetime
import json
import os

CHECK050 = {'qa.names': 'names', 'qa.tris': 'tris'}
CHECK070 = {'qa.preflight': 'preflight', 'ucx.audit': 'ucx_audit'}
EXPORT_LAYER = 'AGR_export'


def _rt():
    from pymxs import runtime
    return runtime


def _handle(n):
    return int(_rt().getHandleByAnim(n))


def _model_nodes(nodes):
    """Model of export.checked and of the object checks: visible geometry named `SM_*` / `UCX_*` outside layer
    AGR_export - of the given nodes, else of the scene. Lights and helpers are judged scene-wide by light.check /
    light.export."""
    rt = _rt()
    pool = list(rt.objects) if nodes is None else [n for n in nodes if rt.isValidNode(n)]
    out = []
    for n in pool:
        name = str(n.name)
        if not (name.startswith('SM_') or name.upper().startswith('UCX_')):
            continue
        if rt.superClassOf(n) != rt.GeometryClass or bool(n.isHidden):
            continue
        if str(n.layer.name) == EXPORT_LAYER:
            continue
        out.append(n)
    return sorted(out, key=_handle)


def _folder(opts):
    if opts.get('folder'):
        return os.path.abspath(opts['folder'])
    folder = str(_rt().maxFilePath)
    if not folder:
        raise ValueError('pack.deliver: pass options.folder or save the scene')
    return os.path.abspath(folder)


def _light_options(opts, folder):
    lo = dict(opts['step_options'].get('light.export') or {})
    lo['folder'] = folder
    if opts.get('stem') and 'stem' not in lo:
        lo['stem'] = opts['stem']
    return lo


def _run_preview(ctx, step, kind, opts, model, folder):
    agr = ctx.agr
    so = opts['step_options'].get(step) or None
    if kind == 'check050':
        return agr.checks_050(CHECK050[step], nodes=model)
    if kind == 'check070':
        return agr.checks_070(CHECK070[step], nodes=model, select=False)
    if kind == 'edit090':
        return agr.edits_090(step, 'preview', nodes=None, options=so)
    if step == 'light.export':
        return agr.edits_100(step, 'preview', options=_light_options(opts, folder))
    if kind == 'edit100':
        return agr.edits_100(step, 'preview', options=so)
    raise ValueError('no preview runner for ' + step)


def _previews(ctx, opts, model, folder):
    """Results of every preview step + the file steps' previews (light.export, export.checked planned)."""
    core = ctx.core
    results, reports = [], []
    for step, phase, kind in core.STEPS:
        if step in opts['skip']:
            results.append(core.step_result(step, skipped=opts['skip'][step]))
            continue
        if step == 'export.zip':
            results.append(core.step_result(step, planned='архив и qa.package - после записи FBX (apply)'))
            continue
        try:
            if step == 'export.checked':
                stem = _stem(opts, reports)
                if not stem:
                    raise ValueError('нет stem SM_<Address>: options.stem или корень света <stem>_Root')
                rep = ctx.agr.export_preview(nodes=model, target=os.path.join(folder, stem + '.fbx'))
            else:
                rep = _run_preview(ctx, step, kind, opts, model, folder)
        except Exception as exc:  # noqa: BLE001 - a step error is a blocker in the report, never a pass
            results.append(core.step_result(step, error='{}: {}'.format(type(exc).__name__, exc)))
            continue
        results.append(core.step_result(step, rep))
        reports.append((step, rep))
    return results, reports


def _stem(opts, reports):
    if opts.get('stem'):
        return opts['stem']
    for step, rep in reports:
        if step == 'light.export' and isinstance(rep, dict) and rep.get('plan', {}).get('stem'):
            return rep['plan']['stem']
    return None


def _state(ctx, opts, model, results):
    return {'tool': ctx.core.TOOL, 'model': ctx.emax.snapshot(model), 'options': opts,
            'steps': [(r['id'], r['status'], r['counts']) for r in results]}


def _passport(ctx, opts):
    rt = _rt()
    path = opts.get('passport')
    if not path:
        try:
            raw = rt.fileProperties.findProperty(rt.Name('custom'), 'agr_passport')
            if raw:
                path = str(rt.fileProperties.getPropertyValue(rt.Name('custom'), raw)).split('|')[0].strip()
        except Exception:  # noqa: BLE001 - no property: stage 9 lives in deliver.json only
            path = None
    if not path:
        return None, None
    with open(path, 'r', encoding='utf-8') as f:
        return path, ctx.edit.parse(f.read())


def _write_json(path, body):
    with open(path, 'x', encoding='utf-8') as f:
        json.dump(body, f, ensure_ascii=False, indent=1, allow_nan=False)
    return path


# ---- new-file FBX writer (light.export) ----------------------------------------------------------------------
def _set_params(rt, params):
    """FBX exporter settings, each read back (an unmapped value is an error, not a silent default)."""
    rt.pluginManager.loadClass(rt.FbxExporter)
    for key, value in params:
        rt.FBXExporterSetParam(key, value)
        got = str(rt.FBXExporterGetParam(key)).lower()
        want = str(value).lower()
        if isinstance(value, float):
            ok = abs(float(got) - value) < 1e-9
        else:
            ok = got == want
        if not ok:
            raise ValueError('unmapped FBX export setting {}={!r} (wanted {!r})'.format(key, got, value))


def write_new_fbx(nodes, target, params):
    """Export exactly `nodes` to a NEW file: `.partial` beside it, then a no-clobber hard link; the caller restores
    the selection (edit_max.session). Used by light.export (light_max.py)."""
    rt = _rt()
    _set_params(rt, params)
    import os
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
        os.link(partial, target)  # no clobber: fails if the target appeared meanwhile
    finally:
        if os.path.exists(partial):
            os.unlink(partial)


def pack_deliver(ctx, mode, nodes, preview):
    with ctx.emax.keep_selection():
        return _pack_deliver(ctx, mode, nodes, preview)


def _pack_deliver(ctx, mode, nodes, preview):
    core, edit = ctx.core, ctx.edit
    opts = core.deliver_options(ctx.options if mode == 'preview' else preview['plan']['options'])
    folder = _folder(opts)
    model = _model_nodes(nodes)
    if mode == 'preview':
        results, reports = _previews(ctx, opts, model, folder)
        block = core.blockers(results)
        objects = core.merge_objects(reports)
        return core.deliver_report(edit, 'preview', results, objects, block, opts,
                                   edit.fingerprint(_state(ctx, opts, model, results)),
                                   extra={'folder': folder, 'stem': _stem(opts, reports),
                                          'model': [_handle(n) for n in model]})
    started = datetime.datetime.now(datetime.timezone.utc)
    results, reports = _previews(ctx, opts, model, folder)
    edit.require_current(preview, _state(ctx, opts, model, results))
    block = core.blockers(results)
    stem = _stem(opts, reports)
    run = core.run_folder(folder)
    files, done, notes = [], [], []
    by_step = dict(reports)
    if not block:
        results = [r for r in results if r['id'] not in ('light.export', 'export.checked', 'export.zip')]
        # 1. light FBX into the run folder (its own preview there: the folder is new)
        try:
            lp = ctx.agr.edits_100('light.export', 'preview', options=_light_options(opts, run))
            la = ctx.agr.edits_100('light.export', 'apply', preview=lp)
            results.append(core.step_result('light.export', la))
            reports.append(('light.export', la))
            files.append(la['plan']['target'])
            stem = stem or la['plan']['stem']
        except Exception as exc:  # noqa: BLE001
            results.append(core.step_result('light.export', error='{}: {}'.format(type(exc).__name__, exc)))
        # 2. checked model FBX
        if stem:
            target = os.path.join(run, stem + '.fbx')
            try:
                ep = ctx.agr.export_preview(nodes=model, target=target)
                if ep.get('status') != 'pass':
                    results.append(core.step_result('export.checked', ep))
                else:
                    ec = ctx.agr.export_commit(nodes=model, preview=ep, target=target)
                    results.append(core.step_result('export.checked', ec))
                    files.append(target)
            except Exception as exc:  # noqa: BLE001
                results.append(core.step_result('export.checked', error='{}: {}'.format(type(exc).__name__, exc)))
        else:
            results.append(core.step_result('export.checked', error='нет stem SM_<Address>: options.stem'))
        # 3. archive + validator (qa.package) of the run folder
        if 'export.zip' in opts['skip']:
            results.append(core.step_result('export.zip', skipped=opts['skip']['export.zip']))
        elif all(r['status'] == 'pass' for r in results if r['id'] in ('light.export', 'export.checked')):
            try:
                zo = dict(opts['step_options'].get('export.zip') or {})
                zo['folder'] = run
                if opts.get('address'):
                    zo['address'] = opts['address']
                zp = ctx.agr.edits_090('export.zip', 'preview', options=zo)
                za = ctx.agr.edits_090('export.zip', 'apply', preview=zp)
                results.append(core.step_result('export.zip', za))
                files.append(za['plan'].get('run_folder'))
            except Exception as exc:  # noqa: BLE001
                results.append(core.step_result('export.zip', error='{}: {}'.format(type(exc).__name__, exc)))
        else:
            results.append(core.step_result('export.zip', error='FBX не записаны: архив не собирается'))
        block = core.blockers(results)
    else:
        notes.append('блокеры превью: файлы сдачи не пишутся, только deliver.json и этап 9 blocked')
    finished = datetime.datetime.now(datetime.timezone.utc)
    stage = core.stage_entry('blocked' if block else 'done', block, started, finished)
    passport_out = None
    try:
        ppath, passport = _passport(ctx, opts)
        if passport is not None:
            passport_out = _write_json(os.path.join(run, core.PASSPORT), core.passport_with_stage(passport, stage))
            notes.append('паспорт {} -> копия с этапом 9: {}'.format(ppath, passport_out))
        else:
            notes.append('паспорт не найден (options.passport / свойство файла agr_passport): этап 9 только в '
                         'deliver.json')
    except (OSError, ValueError) as exc:
        notes.append('паспорт не записан: {}'.format(exc))
        block = block + ['паспорт: {}'.format(exc)]
        stage = core.stage_entry('blocked', block, started, finished)
    body = core.summary(results, block, files, stage, opts, run=run, passport=passport_out, notes=notes)
    report_path = _write_json(os.path.join(run, core.REPORT), body)
    done = [p for p in files if p] + [report_path] + ([passport_out] if passport_out else [])
    objects = core.merge_objects(reports)
    return core.deliver_report(edit, 'apply', results, objects, block, opts, files=files, done=done,
                               extra={'folder': folder, 'run_folder': run, 'stem': stem, 'stage_entry': stage,
                                      'passport': passport_out, 'notes': notes})
