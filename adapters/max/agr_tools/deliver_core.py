"""new-case: AGR Tools 1.0 (#1024) delivery in one button (`pack.deliver`, station 1.0.26), stdlib only. Branch S:
owned by branch S (improve/issue-1024-deliver).

Pure logic for `pack_deliver` (pack.deliver); no pymxs. The glue (deliver_max.py) runs the steps through the
runtime dispatchers (checks_050 / checks_070 / edits_080 / edits_090 / edits_100 / export_preview / export_commit) and hands
this module plain step results; the core never takes a host object.

Contract (#1024 1.0.26, plan mode `read + file`): one press runs the checks 0.5-0.9 (qa.preflight, qa.names, qa.tris,
ucx.audit, light.check, qa.sintez), UCX (ucx.gap), the ОМК ТЭ code (qa.omk_te), the light FBX (light.export), the
checked export (export.checked) and the archive with its validator (export.zip -> qa.package). The preview only
reads; the apply writes NEW files only, into a new run folder `Сдача_<YYYYMMDD_HHMMSS>[_N]`:
* blockers in the preview -> the apply writes only `deliver.json` (+ the passport copy) with stage 9 `blocked`;
* no blockers -> light FBX, model FBX, the ZIP run of export.zip (its validator = qa.package), then stage 9
  `done` when every written step passed, else `blocked` with the failed steps.
Stage 9 goes into the project passport (K1, schemas/ProjectPassport.schema.json): the glue reads the passport of
`options.passport` or the scene file property `agr_passport`, and writes the updated copy `passport.json` into
the run folder (never over jobs/<ID>/passport.json: the passport writer belongs to branch F, project.passport).
A step answered `not_implemented` (another branch has not merged yet) is a blocker unless `options.skip` names it.

#1582 (AI Council 2026-11-16): ucx.gap writes the fixed UCX pieces as copies `<original>_AGR_gap_NN` on layer
AGR_export and never touches the originals; the model of export.checked skips that layer, so the archive got the OLD
UCX. `ucx_export_selection` is the explicit step "export the fixed copies instead of the originals": a fixed copy
goes into the export list under its original's name and the original is skipped; a family without copies exports
its originals; the report field `ucx_export` (deliver.json) lists the replacements. CLI:
`python deliver_core.py ucx-export <scene.json>` ({"model": [...], "copies": [...]}) prints that field, exit 2 on
an error.
"""
import datetime
import json
import os
import re
import sys

TOOL = 'pack.deliver'
RUN_PREFIX = 'Сдача_'
REPORT = 'deliver.json'
PASSPORT = 'passport.json'
STAGE = 9
# id, phase (preview = read check; file = written by the apply), runner kind of the glue
STEPS = (
    ('qa.preflight', 'preview', 'check070'),
    ('qa.names', 'preview', 'check050'),
    ('qa.tris', 'preview', 'check050'),
    ('ucx.audit', 'preview', 'check070'),
    ('light.check', 'preview', 'edit090'),
    ('qa.sintez', 'preview', 'edit090'),
    ('ucx.gap', 'preview', 'edit100'),
    ('qa.omk_te', 'preview', 'edit100'),
    ('light.export', 'file', 'edit100'),
    ('export.checked', 'file', 'export'),
    ('export.zip', 'file', 'edit080'),
)
STEP_IDS = tuple(s[0] for s in STEPS)
OPTION_KEYS = {'folder', 'stem', 'address', 'skip', 'passport', 'step_options'}
STEM = re.compile(r'^SM_[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*$')
STATUSES = ('pass', 'fail', 'error', 'not_implemented', 'skipped', 'planned')
TOP = 5


def deliver_options(options):
    """Validated options: folder (parent of the run folder; default the scene folder - the glue fills it), stem
    (`SM_<Address>` of the VPM set; default from the light root), address (export.zip), skip ({step: reason}: a
    skipped step is never a blocker, the reason is reported), passport (path of jobs/<ID>/passport.json; default the
    scene file property agr_passport), step_options ({step: options of its preview})."""
    opts = dict(options or {})
    extra = set(opts) - OPTION_KEYS
    if extra:
        raise ValueError('unknown pack.deliver options: ' + ', '.join(sorted(extra)))
    skip = opts.get('skip') or {}
    if not isinstance(skip, dict) or any(k not in STEP_IDS or not isinstance(v, str) or not v.strip()
                                         for k, v in skip.items()):
        raise ValueError('skip must be {step id: reason}; steps: ' + ', '.join(STEP_IDS))
    step_options = opts.get('step_options') or {}
    if not isinstance(step_options, dict) or any(k not in STEP_IDS or not isinstance(v, dict)
                                                 for k, v in step_options.items()):
        raise ValueError('step_options must be {step id: {options}}')
    stem = opts.get('stem')
    if stem is not None and (not isinstance(stem, str) or not STEM.match(stem)):
        raise ValueError('stem must be SM_<Address>')
    for key in ('folder', 'address', 'passport'):
        v = opts.get(key)
        if v is not None and (not isinstance(v, str) or not v.strip()):
            raise ValueError(key + ' must be a non-empty string')
    return {'folder': opts.get('folder'), 'stem': stem, 'address': opts.get('address'), 'skip': dict(skip),
            'passport': opts.get('passport'), 'step_options': {k: dict(v) for k, v in step_options.items()}}


def _counts(report):
    objs = report.get('objects') or []
    plan = report.get('plan') or {}
    return {'objects': len(objs), 'with_findings': sum(1 for o in objs if o.get('findings')),
            'findings': sum(len(o.get('findings') or ()) for o in objs),
            'ambiguous': len(plan.get('ambiguous') or ()) if isinstance(plan, dict) else 0}


def _top(report):
    out = []
    for o in report.get('objects') or []:
        for f in o.get('findings') or ():
            out.append('{}: {} {}'.format(o.get('name'), f.get('code'), str(f.get('detail', ''))[:160]).strip())
            if len(out) >= TOP:
                return out
    plan = report.get('plan') or {}
    for a in (plan.get('ambiguous') or ()) if isinstance(plan, dict) else ():
        out.append(str(a.get('reason') if isinstance(a, dict) else a)[:200])
        if len(out) >= TOP:
            break
    for f in (plan.get('findings') or ()) if isinstance(plan, dict) else ():  # scene rows (qa.preflight units)
        if isinstance(f, dict) and f.get('status') not in (None, 'pass'):
            out.append('scene: {} {}'.format(f.get('name', ''), f.get('observed', ''))[:200])
            if len(out) >= TOP:
                break
    return out


def step_result(step, report=None, error=None, skipped=None, planned=None):
    """Plain result of one step: {id, status, counts, top, error|reason}. A report's status is taken as is
    (the dispatchers validate it); an exception is status `error`, never a pass."""
    if step not in STEP_IDS:
        raise ValueError('unknown step ' + repr(step))
    if skipped is not None:
        return {'id': step, 'status': 'skipped', 'reason': str(skipped), 'counts': {}, 'top': []}
    if planned is not None:
        return {'id': step, 'status': 'planned', 'reason': str(planned), 'counts': {}, 'top': []}
    if error is not None:
        return {'id': step, 'status': 'error', 'error': str(error)[:500], 'counts': {}, 'top': []}
    if not isinstance(report, dict) or report.get('status') not in ('pass', 'fail', 'not_implemented'):
        return {'id': step, 'status': 'error', 'error': 'no valid report', 'counts': {}, 'top': []}
    return {'id': step, 'status': report['status'], 'counts': _counts(report), 'top': _top(report)}


def blockers(results):
    """Blocker lines of the step results (fail / error / not_implemented). Skipped and planned steps never block."""
    out = []
    for r in results:
        if r['status'] == 'fail':
            out.append('{}: {}'.format(r['id'], '; '.join(r['top']) or 'fail'))
        elif r['status'] == 'error':
            out.append('{}: ошибка: {}'.format(r['id'], r.get('error', '')))
        elif r['status'] == 'not_implemented':
            out.append('{}: кнопка ещё не реализована (#1024)'.format(r['id']))
    return out


def merge_objects(reports):
    """Scene objects of the step reports, one entry per object NAME (the steps use anim or node handles: the
    first handle seen is kept, a second object with that handle is never made), codes prefixed `<step>/<code>`."""
    entries, used = {}, set()
    for step, rep in reports:
        if not isinstance(rep, dict):
            continue
        for o in rep.get('objects') or ():
            h = o.get('handle')
            if not isinstance(h, int) or isinstance(h, bool) or h <= 0:
                continue
            name = str(o.get('name') or h)
            if name not in entries:
                if h in used:
                    continue
                used.add(h)
                entries[name] = {'handle': h, 'name': name, 'findings': []}
            for f in o.get('findings') or ():
                entries[name]['findings'].append({'code': '{}/{}'.format(step, f.get('code')), 'ids': [],
                                                  'detail': str(f.get('detail', ''))[:300]})
    return sorted(entries.values(), key=lambda e: e['handle'])


def run_folder(parent, stamp=None):
    """A new `Сдача_<YYYYMMDD_HHMMSS>[_N]` folder in `parent` (exclusive mkdir: an existing one is never reused)."""
    parent = os.path.abspath(os.fspath(parent))
    if not os.path.isdir(parent):
        raise ValueError('pack.deliver: no such folder: ' + parent)
    stamp = stamp or datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for i in range(1, 1000):
        path = os.path.join(parent, RUN_PREFIX + stamp + ('' if i == 1 else '_{}'.format(i)))
        try:
            os.mkdir(path)
            return path
        except FileExistsError:
            continue
    raise RuntimeError('pack.deliver: no free run folder name in ' + parent)


def _iso(t):
    return t.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ') if t else None


def stage_entry(status, block, started, finished):
    """Stage 9 of the passport (K1 schema): {id: 9, status done|blocked, started, finished, seconds, blockers}."""
    if status not in ('done', 'blocked'):
        raise ValueError('stage 9 status must be done or blocked')
    if status == 'done' and block:
        raise ValueError('stage 9 done with blockers')
    if status == 'blocked' and not block:
        raise ValueError('stage 9 blocked without a blocker')
    secs = None if not (started and finished) else max(0.0, round((finished - started).total_seconds(), 3))
    return {'id': STAGE, 'status': status, 'started': _iso(started), 'finished': _iso(finished), 'seconds': secs,
            'blockers': [str(b)[:500] for b in block]}


def passport_with_stage(passport, entry):
    """A copy of the passport with stage 9 replaced (K1: `stages` holds 11 entries, ids 0..9 and 'agent').
    ValueError for a passport without schema 1 / without a stage 9 (a broken passport is an error)."""
    if not isinstance(passport, dict) or passport.get('schema') != 1:
        raise ValueError('passport: schema 1 expected (schemas/ProjectPassport.schema.json)')
    stages = passport.get('stages')
    if not isinstance(stages, list) or len(stages) != 11:
        raise ValueError('passport: stages must hold 11 entries (0..9 and agent)')
    idx = [i for i, s in enumerate(stages) if isinstance(s, dict) and s.get('id') == STAGE]
    if len(idx) != 1:
        raise ValueError('passport: exactly one stage 9 expected')
    out = dict(passport)
    out['stages'] = [dict(s) for s in stages]
    out['stages'][idx[0]] = dict(entry)
    return out


def summary(results, block, files, stage, opts, run=None, passport=None, notes=(), ucx_export=None):
    """The `deliver.json` body (also the plan of the report). ucx_export: ucx_export_report (#1582) or {'error'}."""
    return {'tool': TOOL, 'stage': stage, 'blockers': list(block), 'steps': list(results), 'files': list(files),
            'run_folder': run, 'passport': passport, 'options': opts, 'notes': list(notes), 'ucx_export': ucx_export}


def deliver_report(edit, mode, results, objects, block, opts, state_hash=None, files=(), done=(), extra=None):
    """Edit report of pack.deliver. objects = the scene objects with step findings (`<step>/<code>`); blockers are
    `plan.ambiguous` (status fail while there is one); skipped steps are `plan.skipped` with their reason."""
    skipped = [edit.skipped(r['id'], r['reason']) for r in results if r['status'] == 'skipped']
    ambiguous = [{'item': 'pack.deliver', 'reason': b} for b in block]
    info = {'steps': list(results), 'blockers': list(block), 'files': list(files), 'options': opts,
            'stage': STAGE}
    info.update(extra or {})
    return edit.report(TOOL, mode, objects, list(done), skipped, ambiguous, state_hash=state_hash, extra=info)


# ---- #1582: the ucx.gap copies on AGR_export replace their originals in export.checked ---------------------------
GAP_COPY_LAYER = 'AGR_export'
GAP_COPY = re.compile(r'^(?P<source>.+)_AGR_gap_(?P<n>\d+)$')  # ucx10_max: uniqueName(<original> + '_AGR_gap_')
UCX_PIECE = re.compile(r'^UCX_(?P<mesh>.+)_(?P<n>\d{2,3})$')  # = ucx10_core.UCX_NAME (the gap tool's family)


def _ucx_rows(rows, label, layer):
    if not isinstance(rows, (list, tuple)):
        raise ValueError('{}: a list of rows expected'.format(label))
    out = []
    for r in rows:
        if not isinstance(r, dict):
            raise ValueError('{}: row {!r} is not an object'.format(label, r))
        h, name = r.get('handle'), r.get('name')
        if isinstance(h, bool) or type(h) is not int or h <= 0:
            raise ValueError('{}: invalid handle {!r}'.format(label, h))
        if not isinstance(name, str) or not name.strip():
            raise ValueError('{}: missing name of handle {}'.format(label, h))
        if layer and r.get('layer') != GAP_COPY_LAYER:
            raise ValueError('{}: {} is not on layer {} (layer {!r})'.format(label, name, GAP_COPY_LAYER,
                                                                             r.get('layer')))
        if layer and not name.upper().startswith('UCX_'):
            raise ValueError('{}: {} is not a UCX piece'.format(label, name))
        out.append({'handle': h, 'name': name})
    return out


def _ucx_family(name):
    m = UCX_PIECE.match(name)
    return m.group('mesh') if m else name


def ucx_export_selection(model, copies):
    """Export list of export.checked with the ucx.gap copies in place of their originals (#1582).

    model: [{handle, name}] - the export model in export order (visible SM_* / UCX_* outside AGR_export);
    copies: [{handle, name, layer}] - every UCX piece of the scene on layer AGR_export.
    Returns {'nodes': [{handle, name, node, origin}], 'replaced', 'kept', 'ignored'}: `name` is the export name (the
    original's), `node` the scene name, origin 'original' | 'AGR_export'. A copy `<original>_AGR_gap_NN` whose
    original is in the model replaces it; any other copy is ignored with its reason. Errors (ValueError, naming the
    nodes): empty model, bad rows, a handle twice, two copies of one original, two originals of one name, a family
    with only part of its pieces copied (an old neighbour next to a moved piece is the collision ucx.gap removed).
    The inputs are never changed."""
    model = _ucx_rows(model, 'model', False)
    copies = _ucx_rows(copies, 'AGR_export copies', True)
    if not model:
        raise ValueError('empty export model')
    seen = set()
    for r in model + copies:
        if r['handle'] in seen:
            raise ValueError('duplicate handle {} ({})'.format(r['handle'], r['name']))
        seen.add(r['handle'])
    by_name = {}
    for r in model:
        if r['name'].upper().startswith('UCX_'):
            by_name.setdefault(r['name'], []).append(r)
    fixed, ignored = {}, []
    for r in sorted(copies, key=lambda x: (x['name'], x['handle'])):
        m = GAP_COPY.match(r['name'])
        if not m:
            ignored.append({'handle': r['handle'], 'name': r['name'],
                            'reason': 'not a ucx.gap copy: name is not <original>_AGR_gap_NN'})
            continue
        src = m.group('source')
        if src not in by_name:
            ignored.append({'handle': r['handle'], 'name': r['name'],
                            'reason': 'original not in the export model: {} (hidden, unselected or deleted)'.format(
                                src)})
            continue
        if len(by_name[src]) > 1:
            raise ValueError('two originals named {} (handles {}): the copy {} is ambiguous'.format(
                src, ', '.join(str(x['handle']) for x in by_name[src]), r['name']))
        fixed.setdefault(src, []).append(r)
    many = {k: v for k, v in fixed.items() if len(v) > 1}
    if many:
        k = sorted(many)[0]
        raise ValueError('{} has {} ucx.gap copies on {}: {} - delete the stale ones'.format(
            k, len(many[k]), GAP_COPY_LAYER, ', '.join(x['name'] for x in many[k])))
    fams = {_ucx_family(k) for k in fixed}
    missing = sorted(k for k in by_name if _ucx_family(k) in fams and k not in fixed)
    if missing:
        raise ValueError('family partly fixed on {}: no ucx.gap copy for {} - rerun ucx.gap on the family'.format(
            GAP_COPY_LAYER, ', '.join(missing)))
    nodes, replaced, kept = [], [], []
    for r in model:
        cp = fixed.get(r['name'])
        if cp:
            nodes.append({'handle': cp[0]['handle'], 'name': r['name'], 'node': cp[0]['name'],
                          'origin': GAP_COPY_LAYER})
            replaced.append({'name': r['name'], 'copy': cp[0]['name'], 'copy_handle': cp[0]['handle'],
                             'original_handle': r['handle']})
        else:
            nodes.append({'handle': r['handle'], 'name': r['name'], 'node': r['name'], 'origin': 'original'})
            if r['name'].upper().startswith('UCX_'):
                kept.append(r['name'])
    ignored.sort(key=lambda x: x['handle'])
    return {'nodes': nodes, 'replaced': replaced, 'kept': kept, 'ignored': ignored}


def ucx_export_names(selection):
    """{copy handle: original name} of the replaced pieces (the runtime exports the copy under that name)."""
    return {r['handle']: r['name'] for r in selection['nodes'] if r['origin'] == GAP_COPY_LAYER}


def ucx_export_report(selection):
    """The `ucx_export` field of deliver.json: which UCX came from AGR_export."""
    return {'from_layer': GAP_COPY_LAYER, 'replaced': [dict(r) for r in selection['replaced']],
            'kept': list(selection['kept']), 'ignored': [dict(r) for r in selection['ignored']]}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2 or argv[0] != 'ucx-export':
        sys.stderr.write('usage: deliver_core.py ucx-export <scene.json>\n')
        return 2
    try:
        with open(argv[1], 'r', encoding='utf-8') as f:
            body = json.load(f)
        if not isinstance(body, dict) or set(body) != {'model', 'copies'}:
            raise ValueError('scene.json must be {"model": [...], "copies": [...]}')
        rep = ucx_export_report(ucx_export_selection(body['model'], body['copies']))
    except (OSError, ValueError) as exc:
        sys.stderr.write('error: {}\n'.format(exc))
        return 2
    sys.stdout.write(json.dumps(rep, ensure_ascii=False, indent=1, allow_nan=False) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
