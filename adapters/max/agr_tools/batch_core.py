"""new-case: AGR Tools 0.9 (#979) batch export logic, stdlib only. Owned by branch D
(improve/issue-979-export-scene-light).

Pure logic for `export_batch` (export.batch); no pymxs. Plan mode `file`: preview -> apply (edit_core contract).

* Group the scene geometry by `AGR_EXPORT_PATH` (one FBX per group). A node without the key, a relative path or a
  non-.fbx path is `skipped` with its reason - never silently left out.
* Every group goes through the same gates and readback as `export.checked` (AGR Tools 0.4.0): the glue calls
  runtime.export_preview / export_commit as they are; export_core.py is read, never edited (owner E3).
* Never overwrite: a group whose FBX (or its `.report.json` / `.partial`) exists gets the next free `_vNNN`
  version (edit_core.new_path) - in the preview already, so apply writes exactly the planned path.
* One group failing does not stop the others; the batch status is then fail. ONE report for the whole batch.
* Procedural objects (`qa.procedural_objects`, branch C) block their group. The list comes only through
  `runtime.edits_090('qa.procedural_objects', 'preview')` (never an import of qa9_*). While that row answers
  `not_implemented`, or its check fails, NO group is exported: the procedural state is unknown (fail closed).
"""
import os

TOOL = 'export.batch'
KEY = 'AGR_EXPORT_PATH'
PROCEDURAL = 'qa.procedural_objects'
OPTION_KEYS = set()


def batch_options(options):
    opts = dict(options or {})
    extra = set(opts) - OPTION_KEYS
    if extra:
        raise ValueError('unknown export.batch options: ' + ', '.join(sorted(extra)))
    return {}


def path_key(path):
    return os.path.normcase(os.path.normpath(str(path)))


def side_files(path):
    """The files export.checked refuses to overwrite for one target: FBX, `<stem>.report.json`, `<fbx>.partial`."""
    path = str(path)
    return (path, os.path.splitext(path)[0] + '.report.json', path + '.partial')


def occupied(path, exists=os.path.exists):
    return any(exists(p) for p in side_files(path))


def plan_target(edit, requested, exists=os.path.exists):
    """(target, versioned): the requested path when free, else its next free `_vNNN` (none of the 3 files)."""
    if not occupied(requested, exists):
        return requested, False
    return edit.new_path(requested, version=True, exists=lambda p: occupied(p, exists)), True


def group_nodes(rows):
    """rows: [{handle, name, path}] (path = AGR_EXPORT_PATH text or None). Returns (groups, skipped):
    groups [{requested, key, members: [{handle, name}]}] sorted by path; skipped [(handle, name, reason)]."""
    groups, skipped = {}, []
    for row in sorted(rows, key=lambda r: r['handle']):
        path = row.get('path')
        if not path:
            skipped.append((row['handle'], row['name'], 'нет ' + KEY))
            continue
        path = os.path.normpath(str(path).strip())
        if not os.path.isabs(path):
            skipped.append((row['handle'], row['name'], '{} не абсолютный: {}'.format(KEY, path)))
            continue
        if os.path.splitext(path)[1].lower() != '.fbx':
            skipped.append((row['handle'], row['name'], '{} не .fbx: {}'.format(KEY, path)))
            continue
        key = path_key(path)
        grp = groups.setdefault(key, {'requested': path, 'key': key, 'members': []})
        grp['members'].append({'handle': row['handle'], 'name': row['name']})
    return [groups[k] for k in sorted(groups)], skipped


def procedural_state(report):
    """(state, offenders, detail) from the qa.procedural_objects preview: state 'checked' | 'not_implemented' |
    'error'. offenders: {handle: detail} - objects with findings and ambiguous items that name a handle."""
    if isinstance(report, Exception):
        return 'error', {}, '{}: {}'.format(type(report).__name__, report)
    if not isinstance(report, dict) or report.get('tool') != PROCEDURAL:
        return 'error', {}, 'unexpected answer of ' + PROCEDURAL
    if report.get('status') == 'not_implemented':
        return 'not_implemented', {}, '{} not_implemented ({})'.format(PROCEDURAL, report['plan'].get('issue', '#979'))
    offenders = {}
    for o in report.get('objects') or []:
        if o.get('findings'):
            offenders[o['handle']] = '; '.join('{} {}'.format(f['code'], f['detail']).strip() for f in o['findings'])
    for a in (report.get('plan') or {}).get('ambiguous') or []:
        if isinstance(a, dict) and isinstance(a.get('handle'), int):
            offenders.setdefault(a['handle'], str(a.get('reason') or a.get('item') or 'ambiguous'))
    return 'checked', offenders, ''


def plan_batch(edit, rows, procedural_report, dry_run, exists=os.path.exists):
    """Preview half: groups, versioned targets, procedural block, export.checked dry run per free group.
    dry_run(group) -> the export.checked preview of that group at group['target'] (may raise: that group is an
    `error`, the others go on). Returns (groups, skipped, procedural)."""
    groups, skipped = group_nodes(rows)
    if not groups:
        raise ValueError('no geometry with {} in scope: an empty batch is an error, not a pass'.format(KEY))
    state, offenders, detail = procedural_state(procedural_report)
    judge(groups, state, offenders, detail)
    planned = set()

    def taken(p):
        return exists(p) or path_key(p) in planned

    for g in groups:
        g['target'], g['versioned'] = plan_target(edit, g['requested'], taken)
        planned.update(path_key(p) for p in side_files(g['target']))
        if g['blocked']:
            continue
        try:
            g['export'] = dry_run(g)
        except Exception as exc:  # noqa: BLE001 - one group failing never stops the batch; reported per group
            g['error'] = '{}: {}'.format(type(exc).__name__, exc)
    blockers = sorted({h for g in groups for h in g['blockers']})
    procedural = {'state': state, 'detail': detail, 'offenders': offenders, 'blockers': blockers}
    return groups, skipped, procedural


def batch_state(edit, groups, skipped, procedural):
    """The state apply must find unchanged (edit_core.require_current)."""
    return {'tool': TOOL, 'skipped': [list(s) for s in skipped], 'procedural': [procedural['state'],
                                                                               procedural['blockers']],
            'groups': [{'requested': g['requested'], 'target': g['target'], 'versioned': g['versioned'],
                        'handles': [m['handle'] for m in g['members']], 'blocked': g.get('blocked'),
                        'error': g.get('error'),
                        'export': edit.fingerprint(g['export']) if g.get('export') else None} for g in groups]}


def apply_batch(groups, commit):
    """Apply half: commit(group, export_preview) -> the export.checked commit report (FBX + readback) for every
    group whose preview passed. A group that raises or comes back without readback is an `error`; the others go
    on. Groups that failed their gates in the preview stay failed (nothing written)."""
    for g in groups:
        rep = g.get('export')
        if g.get('blocked') or g.get('error') or rep is None or rep['status'] != 'pass':
            continue
        try:
            out = commit(g, rep)
            readback = (out.get('plan') or {}).get('readback') if isinstance(out, dict) else None
            if not isinstance(readback, dict) or 'object_count' not in readback:
                raise ValueError('FBX readback missing')
            g['export'] = out
        except Exception as exc:  # noqa: BLE001 - recorded per group, the batch goes on
            g.pop('export', None)
            g['error'] = '{}: {}'.format(type(exc).__name__, exc)
    return groups


def gate_summary(export_report):
    plan = export_report['plan']
    return {'status': export_report['status'], 'stopped': plan.get('stopped'),
            'gates': [{'name': g['name'], 'status': g['status']} for g in plan.get('gates', [])],
            'object_count': plan.get('object_count'), 'triangle_count': plan.get('triangle_count'),
            'digest': plan.get('digest')}


def judge(groups, proc_state, offenders, proc_detail):
    """Mark each group: blocked (procedural / unknown procedural state) or to be checked by the gates."""
    for g in groups:
        handles = {m['handle'] for m in g['members']}
        if proc_state != 'checked':
            g['blocked'] = 'процедурные объекты не проверены: ' + proc_detail
            g['blockers'] = []
        else:
            hit = sorted(handles & set(offenders))
            g['blocked'] = ('процедурный объект в группе: ' + ', '.join(
                m['name'] for m in g['members'] if m['handle'] in hit)) if hit else None
            g['blockers'] = hit
    return groups


def batch_report(edit, mode, groups, skipped, procedural, state_hash=None):
    """ONE report for the batch. groups: judged groups, each with `target`, `versioned` and one of `export`
    (the export.checked preview/commit report), `error` (text) or `blocked`. objects: every grouped node;
    findings = the gate findings of export.checked by node name, `procedural_object` on a blocker,
    `procedural_unchecked` on every node while the procedural state is unknown, `export_error` on every node
    of a group whose export raised. done: groups that pass (preview: would be written; apply: written and read
    back); skipped: every other group and every node without a usable AGR_EXPORT_PATH (that node is a report object
    without findings: nothing is wrong with it, it is just in no FBX)."""
    entries = {h: {'name': n, 'findings': [] if r == 'нет ' + KEY else [edit.finding('export_path_invalid', (), r)]}
               for h, n, r in skipped}  # a written but unusable path is a defect; no path at all is not
    done, skip, rows = [], [edit.skipped(n, r) for _, n, r in skipped], []
    for g in groups:
        for m in g['members']:
            entries.setdefault(m['handle'], {'name': m['name'], 'findings': []})
        row = {'requested': g['requested'], 'target': g['target'], 'versioned': g['versioned'],
               'nodes': [m['name'] for m in g['members']]}
        if g.get('blocked'):
            row['status'] = 'blocked'
            row['reason'] = g['blocked']
            code = 'procedural_object' if g['blockers'] else 'procedural_unchecked'
            for m in g['members']:
                if not g['blockers'] or m['handle'] in g['blockers']:
                    detail = procedural.get('offenders', {}).get(m['handle'], g['blocked'])
                    entries[m['handle']]['findings'].append(edit.finding(code, (), detail))
            skip.append(edit.skipped(g['target'], g['blocked']))
        elif g.get('error'):
            row['status'] = 'error'
            row['reason'] = g['error']
            for m in g['members']:
                entries[m['handle']]['findings'].append(edit.finding('export_error', (), g['error']))
            skip.append(edit.skipped(g['target'], 'ошибка экспорта: ' + g['error']))
        else:
            rep = g['export']
            row.update(gate_summary(rep))
            by_name = {m['name']: m['handle'] for m in g['members']}
            for o in rep['objects']:
                h = by_name.get(o['name'])
                if h is None:
                    continue
                for f in o['findings']:
                    entries[h]['findings'].append(edit.finding(f['code'], f['ids'], f['detail']))
            if rep['status'] == 'pass':
                item = {'item': g['target'], 'requested': g['requested'], 'versioned': g['versioned'],
                        'nodes': row['nodes']}
                if mode == 'apply':
                    item['readback'] = rep['plan'].get('readback')
                    item['report'] = rep['plan'].get('report')
                    row['readback'] = item['readback']
                done.append(item)
            else:
                skip.append(edit.skipped(g['target'], 'ворота export.checked: {}'.format(
                    rep['plan'].get('stopped') or rep['status'])))
        rows.append(row)
    objects = [edit.entry(h, v['name'], v['findings']) for h, v in sorted(entries.items())]
    summary = {'groups': len(groups), 'pass': len(done), 'blocked': sum(1 for r in rows if r['status'] == 'blocked'),
               'fail': sum(1 for r in rows if r['status'] == 'fail'),
               'error': sum(1 for r in rows if r['status'] == 'error'),
               'versioned': sum(1 for g in groups if g['versioned']), 'nodes_skipped': len(skipped)}
    plan = {'groups': rows, 'summary': summary, 'procedural': {k: v for k, v in procedural.items() if k != 'offenders'}}
    return edit.report(TOOL, mode, objects, done, skip, [], state_hash=state_hash, extra=plan)
