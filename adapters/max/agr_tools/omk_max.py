"""AGR Tools 1.0 (#1024) OMK TE code, 3ds Max side. Owned by branch T (improve/issue-1024-deliver-small).

runtime.edits_100 calls `qa_omk_te(ctx, mode, nodes, preview)` (qa.omk_te, plan mode `read`: preview only).
ctx: agr (runtime globals), core (omk_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost). Import pymxs inside functions so this file loads under plain pytest.

The scene is not touched: the table is a user file read from a path parameter; the only side effect is the
clipboard text of the chosen code (option `copy`, default on). No globals are created.
"""
import os


def _rt():
    from pymxs import runtime
    return runtime


def _load(core, path):
    """Bytes of the table, or an OmkError (Russian text, with the path) for a missing/busy file."""
    if not os.path.isfile(path):
        raise core.OmkError('table_missing', 'Таблица ОМК ТЭ не найдена: {}'.format(path))
    try:
        with open(path, 'rb') as f:
            return f.read()
    except PermissionError:
        raise core.OmkError('table_busy', 'Таблица ОМК ТЭ занята другой программой или закрыта для чтения: {}'.format(path)) from None
    except OSError as exc:
        raise core.OmkError('table_busy', 'Таблица ОМК ТЭ не читается ({}): {}'.format(exc.strerror or 'ошибка', path)) from None


def qa_omk_te(ctx, mode, nodes, preview):
    core, edit = ctx.core, ctx.edit
    if mode != 'preview':
        raise ValueError('qa.omk_te is read-only: there is no apply')
    try:
        opts = core.omk_options(ctx.options)
    except core.OmkError as err:
        return core.error_report(edit, str((ctx.options or {}).get('table') or ''), err, edit.fingerprint({'error': err.code}))
    path = opts['table']
    try:
        data = _load(core, path)
        text = core.decode_table(data)
        rows, problems = core.parse_table(text, opts['place_column'], opts['code_column'])
        state = {'tool': core.TOOL, 'options': opts, 'table_sha': edit.fingerprint(text)}
        row = core.pick_visible(rows, opts['filter'], opts['pick'])
        code = core.choose_code(row, opts['choice'])
    except core.OmkError as err:
        return core.error_report(edit, path, err, edit.fingerprint({'error': err.code, 'path': path}))
    report = core.omk_report(edit, opts, rows, problems, row, code, edit.fingerprint(state))
    if report['plan'].get('clipboard'):
        _rt().setclipboardText(report['plan']['clipboard'])
    return report
