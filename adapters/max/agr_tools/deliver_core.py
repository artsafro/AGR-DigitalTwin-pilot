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
"""
import datetime
import os
import re

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


def summary(results, block, files, stage, opts, run=None, passport=None, notes=()):
    """The `deliver.json` body (also the plan of the report)."""
    return {'tool': TOOL, 'stage': stage, 'blockers': list(block), 'steps': list(results), 'files': list(files),
            'run_folder': run, 'passport': passport, 'options': opts, 'notes': list(notes)}


def deliver_report(edit, mode, results, objects, block, opts, state_hash=None, files=(), done=(), extra=None):
    """Edit report of pack.deliver. objects = the scene objects with step findings (`<step>/<code>`); blockers are
    `plan.ambiguous` (status fail while there is one); skipped steps are `plan.skipped` with their reason."""
    skipped = [edit.skipped(r['id'], r['reason']) for r in results if r['status'] == 'skipped']
    ambiguous = [{'item': 'pack.deliver', 'reason': b} for b in block]
    info = {'steps': list(results), 'blockers': list(block), 'files': list(files), 'options': opts,
            'stage': STAGE}
    info.update(extra or {})
    return edit.report(TOOL, mode, objects, list(done), skipped, ambiguous, state_hash=state_hash, extra=info)
