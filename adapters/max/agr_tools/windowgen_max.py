"""new-case: AGR Tools 1.0 (#1024) window type generator, 3ds Max side; owned by branch J (improve/issue-1024-windows).

runtime.edits_100 calls `win_generate(ctx, mode, nodes, preview)` for win.generate (plan mode `file`: a NEW folder
only, the scene is never changed).
ctx: agr (runtime globals), core (windowgen_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost: ObjRef, user props, one undo record).
Import pymxs inside functions so this file loads under plain pytest.

Input: the selected objects carrying `agr_window_type` (opening markers, placed windows) -> those types; or
options.ids (a list of library ids, or "all"). preview reports per type pass / quarantine / duplicate (K2 quality,
windowgen_core.library_report over the WHOLE library, so duplicates and quarantine are the same as for win.place)
and the files apply will write; apply creates the new folder (`out`, default `win_generate` next to the scene or
under %LOCALAPPDATA%\\AGRTools, next free _vNNN) with quality.json, sheet.png («было -> стало») and one OBJ per
generated type (frame and glass groups, metres, face -Y).
"""
import json
import os

OPTIONS = {'ids', 'library', 'out', 'variant'}


def _rt():
    from pymxs import runtime
    return runtime


def _handle(n):
    return int(_rt().getHandleByAnim(n))


def _out_default():
    rt = _rt()
    if str(rt.maxFileName):
        return os.path.join(str(rt.maxFilePath), 'win_generate')
    base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    return os.path.join(base, 'AGRTools', 'win_generate')


def check_options(options):
    opts = {'ids': None, 'library': None, 'out': None, 'variant': 'vpm'}
    for k, v in (options or {}).items():
        if k not in OPTIONS:
            raise ValueError('unknown win.generate option: ' + repr(k))
        opts[k] = v
    if opts['ids'] is not None and opts['ids'] != 'all' and (
            not isinstance(opts['ids'], list) or not opts['ids'] or not all(isinstance(i, str) for i in opts['ids'])):
        raise ValueError('options.ids must be "all" or a non-empty list of library ids')
    if opts['variant'] not in ('vpm', 'npm'):
        raise ValueError('options.variant must be vpm or npm')
    for k in ('library', 'out'):
        if opts[k] is not None and (not isinstance(opts[k], str) or not opts[k].strip()):
            raise ValueError('options.{} must be a path string'.format(k))
    return opts


def win_generate(ctx, mode, nodes, preview):
    """win.generate (1.0.10): library types by the standard -> quality report, preview sheet, OBJ meshes."""
    tool = 'win.generate'
    edit, core = ctx.edit, ctx.core
    rt = _rt()
    if mode == 'preview':
        opts = check_options(ctx.options)
        lib = core.load_library(core.library_dir(opts['library']))
        report = core.library_report(lib['types'], lib['standard'])
        rows = {r['id']: r for r in report['types']}
        picked = list(rt.selection) if nodes is None else list(nodes)
        objects, ids, skipped = [], [], []
        for n in picked:
            tid = rt.getUserProp(n, 'agr_window_type')
            if tid is None or not str(tid).strip():
                skipped.append(edit.skipped(str(n.name), 'нет agr_window_type'))
                continue
            tid = str(tid)
            fs = []
            if tid not in rows:
                fs.append(edit.finding('unknown_type', [], '{}: нет в библиотеке'.format(tid)))
            elif rows[tid]['verdict'] == 'quarantine':
                fs.append(edit.finding('quarantine', [], '{}: {}'.format(tid, '; '.join(rows[tid]['why']))))
            elif rows[tid]['verdict'] == 'duplicate':
                fs.append(edit.finding('duplicate', [], '{}: дубль {}'.format(tid, rows[tid]['same_as'])))
            else:
                ids.append(tid)
            objects.append(edit.entry(_handle(n), str(n.name), fs))
        if opts['ids'] == 'all':
            ids += [t['id'] for t in lib['types']]
        elif opts['ids']:
            unknown = [i for i in opts['ids'] if i not in rows]
            if unknown:
                raise ValueError('options.ids: not in the library: ' + ', '.join(unknown))
            ids += opts['ids']
        if not objects and not ids:
            raise ValueError('nothing to generate: select objects with agr_window_type or give options.ids')
        ids = list(dict.fromkeys(ids))
        build, done, ambiguous = [], [], []
        for tid in ids:
            r = rows[tid]
            if r['verdict'] == 'pass':
                build.append(tid)
                done.append('{}: {} по {}{}'.format(tid, 'OBJ', r['family'],
                                                   '' if not r['notes'] else ' (' + '; '.join(r['notes']) + ')'))
            elif r['verdict'] == 'quarantine':
                skipped.append(edit.skipped(tid, 'карантин: ' + '; '.join(r['why'])))
            else:
                skipped.append(edit.skipped(tid, 'дубль ' + str(r['same_as'])))
        out = edit.new_path(opts['out'] or _out_default(), version=True)
        files = ['quality.json', 'sheet.png'] + ['{}.obj'.format(t) for t in build]
        state = {'library': lib['sha256'], 'out_free': not os.path.exists(out), 'ids': ids}
        extra = {'options': dict(ctx.options), 'variant': opts['variant'], 'ids': ids, 'build': build,
                 'library': {'folder': lib['folder'], 'sha256': lib['sha256']}, 'out': out, 'files': files,
                 'counts': report['counts'], 'types': [rows[i] for i in ids]}
        return edit.report(tool, 'preview', objects=objects, done=done, skipped_=skipped, ambiguous=ambiguous,
                           state_hash=edit.fingerprint(state), extra=extra)

    plan = preview['plan']
    lib = core.load_library(plan['library']['folder'])
    out = plan['out']
    edit.require_current(preview, {'library': lib['sha256'], 'out_free': not os.path.exists(out), 'ids': plan['ids']})
    os.makedirs(out, exist_ok=False)  # file mode: a new folder only
    report = core.library_report(lib['types'], lib['standard'])
    chosen = [lib['by_id'][i] for i in plan['ids']]
    sub = dict(report, types=[r for r in report['types'] if r['id'] in plan['ids']])
    sub['counts'] = {v: sum(r['verdict'] == v for r in sub['types']) for v in core.VERDICTS}
    written = []
    edit.write_new(os.path.join(out, 'quality.json'), core.report_json(sub).encode('utf-8'))
    written.append('quality.json')
    edit.write_new(os.path.join(out, 'sheet.png'), core.sheet_png(chosen, lib['standard'], sub))
    written.append('sheet.png')
    meshes = {}
    for tid in plan['build']:
        m = core.build_type(lib['by_id'][tid], lib['standard'], {'variant': plan['variant']})
        edit.write_new(os.path.join(out, tid + '.obj'), core.to_obj(m, tid).encode('utf-8'))
        written.append(tid + '.obj')
        meshes[tid] = {'faces': len(m['faces']), 'glass': len(m['parts']['glass']), 'family': m['family'],
                       'face_axis': m['face_axis'], 'size_m': m['size_m']}
    edit.write_new(os.path.join(out, 'meshes.json'), (json.dumps(meshes, indent=1) + '\n').encode('utf-8'))
    written.append('meshes.json')
    objects = [o for o in preview['objects']]
    return edit.report(tool, 'apply', objects=objects, done=['{} -> {}'.format(f, out) for f in written],
                       skipped_=plan['skipped'], ambiguous=plan['ambiguous'],
                       extra={'out': out, 'files': written, 'counts': sub['counts']})
