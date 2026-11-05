"""new-case: AGR Tools 0.8 edit contract (#908), stdlib only; no pymxs.

Every 0.8 tool that changes something follows one contract, shared by branches A–D:

* preview -> apply. `preview` changes nothing and returns a report whose `plan.hash` covers the whole report.
  `apply` accepts only that report, unaltered (`check_preview`), and only while the scene state it was made
  from is unchanged (`require_current`: `plan.state_hash` against a fresh fingerprint). A stale or edited
  preview is an error, never a partial apply.
* Never overwrite: `new_path()` refuses an existing file or picks the next free `_vNNN` version.
* Report lists: `plan.done`, `plan.skipped` (each with a non-empty reason), `plan.ambiguous`.
  In a preview they say what apply would do; in an apply what was done.
* JSON report contract of 0.5.0: exactly `schema`/`tool`/`status`/`objects`/`plan`, status derived from the
  findings (a claimed pass is not trusted). `not_implemented` is the status of an empty stub module.
"""
import hashlib
import json
import os
import re

SCHEMA = 1
CONTRACT = '0.5.0'
MODES = ('preview', 'apply')
STATUSES = ('pass', 'fail', 'not_implemented')
LISTS = ('done', 'skipped', 'ambiguous')
REPORT_KEYS = {'schema', 'tool', 'status', 'objects', 'plan'}
ISSUE = '#908'
_VERSION = re.compile(r'^(?P<stem>.*)_v(?P<n>\d{3,})$')


class StalePreview(ValueError):
    """The preview does not belong to this tool, was altered, or the scene changed since."""


def _reject(value):
    raise ValueError('non-finite number: ' + value)


def _unique(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise ValueError('duplicate key: ' + repr(k))
        out[k] = v
    return out


def canonical(value):
    """Canonical JSON text: sorted keys, ASCII, no NaN/Infinity (an error, not a token)."""
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(',', ':'))


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode('ascii')).hexdigest()


def parse(text):
    """Strict JSON: duplicate keys and NaN/Infinity are errors."""
    return json.loads(text, object_pairs_hook=_unique, parse_constant=_reject)


# ---- reports ----------------------------------------------------------------------------------------
def finding(code, ids=(), detail=''):
    return {'code': str(code), 'ids': sorted(set(int(i) for i in ids)), 'detail': str(detail)}


def entry(handle, name, findings=()):
    return {'handle': int(handle), 'name': str(name), 'findings': list(findings)}


def skipped(item, reason):
    if not str(reason).strip():
        raise ValueError('skipped item without a reason: ' + repr(item))
    return {'item': str(item), 'reason': str(reason)}


def _status(objects, plan):
    bad = any(isinstance(o, dict) and o.get('findings') for o in objects) or bool(plan.get('ambiguous'))
    return 'fail' if bad else 'pass'


def report(tool, mode, objects=(), done=(), skipped_=(), ambiguous=(), state_hash=None, extra=None):
    """Build and validate one edit report. A preview gets `plan.hash` over the whole report."""
    if mode not in MODES:
        raise ValueError('unknown edit mode: ' + repr(mode))
    plan = {'mode': mode, 'contract': CONTRACT, 'done': list(done), 'skipped': list(skipped_),
            'ambiguous': list(ambiguous)}
    if state_hash is not None:
        plan['state_hash'] = str(state_hash)
    for k, v in (extra or {}).items():
        if k in plan or k == 'hash':
            raise ValueError('reserved plan key: ' + k)
        plan[k] = v
    objects = list(objects)
    out = {'schema': SCHEMA, 'tool': str(tool), 'status': _status(objects, plan), 'objects': objects, 'plan': plan}
    if mode == 'preview':
        if state_hash is None:
            raise ValueError('preview without state_hash')
        plan['hash'] = fingerprint(out)
    return validate_report(out)


def not_implemented(tool, mode, issue=ISSUE):
    """Report of a tool whose module is still an empty stub (the base ships and builds before its branch).
    `issue`: the issue of the version that owns the row (#908 for 0.8, #979 for 0.9)."""
    if mode not in MODES:
        raise ValueError('unknown edit mode: ' + repr(mode))
    if not isinstance(issue, str) or not issue.startswith('#'):
        raise ValueError('issue must look like #NNN: ' + repr(issue))
    return validate_report({'schema': SCHEMA, 'tool': str(tool), 'status': 'not_implemented', 'objects': [],
                            'plan': {'mode': mode, 'contract': CONTRACT, 'done': [], 'skipped': [], 'ambiguous': [],
                                     'issue': issue}})


def validate_report(r, tools=None):
    """Exact 0.5.0 shape + edit plan lists; status is recomputed, never trusted. Returns r."""
    if not isinstance(r, dict) or set(r) != REPORT_KEYS:
        raise ValueError('incomplete edit report')
    if type(r['schema']) is not int or r['schema'] != SCHEMA:
        raise ValueError('unsupported schema')
    if not isinstance(r['tool'], str) or not r['tool'] or (tools is not None and r['tool'] not in tools):
        raise ValueError('unsupported tool: ' + repr(r.get('tool')))
    if r['status'] not in STATUSES:
        raise ValueError('unknown status: ' + repr(r['status']))
    plan = r['plan']
    if not isinstance(plan, dict) or plan.get('mode') not in MODES or plan.get('contract') != CONTRACT:
        raise ValueError('edit plan without mode/contract')
    for key in LISTS:
        if not isinstance(plan.get(key), list):
            raise ValueError('edit plan list missing: ' + key)
    for s in plan['skipped']:
        if not isinstance(s, dict) or set(s) != {'item', 'reason'} or not str(s['reason']).strip():
            raise ValueError('skipped item without a reason: ' + repr(s))
    objects = r['objects']
    if not isinstance(objects, list):
        raise ValueError('objects is not a list')
    seen = set()
    for o in objects:
        if not isinstance(o, dict) or set(o) != {'handle', 'name', 'findings'}:
            raise ValueError('incomplete object')
        if type(o['handle']) is not int or o['handle'] <= 0 or o['handle'] in seen:
            raise ValueError('invalid/duplicate handle')
        seen.add(o['handle'])
        if not isinstance(o['name'], str) or not o['name'].strip() or not isinstance(o['findings'], list):
            raise ValueError('invalid object')
        for f in o['findings']:
            if not isinstance(f, dict) or set(f) != {'code', 'ids', 'detail'}:
                raise ValueError('incomplete finding')
            if not isinstance(f['code'], str) or not f['code'] or not isinstance(f['detail'], str):
                raise ValueError('invalid finding')
            ids = f['ids']
            if not isinstance(ids, list) or any(type(i) is not int or i <= 0 for i in ids) or len(set(ids)) != len(ids):
                raise ValueError('invalid component IDs')
    if r['status'] == 'not_implemented':
        if objects or any(plan[k] for k in LISTS) or 'hash' in plan:
            raise ValueError('not_implemented report with content')
        return r
    if r['status'] != _status(objects, plan):
        raise ValueError('inconsistent status')
    if plan['mode'] == 'preview':
        if not isinstance(plan.get('state_hash'), str) or not plan['state_hash']:
            raise ValueError('preview without state_hash')
        if not isinstance(plan.get('hash'), str):
            raise ValueError('preview without hash')
    elif 'hash' in plan:
        raise ValueError('apply report carries a preview hash')
    canonical(r)  # finite and serialisable
    return r


# ---- preview -> apply --------------------------------------------------------------------------------
def check_preview(tool, preview):
    """The preview of the last answer for this tool, unaltered (hash over the whole report). Returns it."""
    if not isinstance(preview, dict):
        raise StalePreview('apply needs the preview report of the last answer')
    try:
        validate_report(preview)
    except ValueError as exc:
        raise StalePreview('invalid preview: {}'.format(exc)) from None
    if preview['tool'] != tool:
        raise StalePreview('preview of another tool: ' + repr(preview['tool']))
    if preview['status'] == 'not_implemented' or preview['plan']['mode'] != 'preview':
        raise StalePreview('not a preview report')
    body = dict(preview)
    body['plan'] = {k: v for k, v in preview['plan'].items() if k != 'hash'}
    if fingerprint(body) != preview['plan']['hash']:
        raise StalePreview('preview was altered (hash mismatch); run preview again')
    return preview


def require_current(preview, state):
    """Apply only while the scene/file state the preview was made from is unchanged."""
    if fingerprint(state) != preview['plan']['state_hash']:
        raise StalePreview('scene changed since the preview; run preview again')
    return preview


# ---- never overwrite ---------------------------------------------------------------------------------
def new_path(path, version=False, exists=os.path.exists):
    """A path that does not exist yet. Existing target: refuse (default) or the next free `_vNNN`.

    `stem_v007.ext` continues at `_v008`; a bare `stem.ext` continues at `stem_v002.ext`.
    """
    path = os.fspath(path)
    if not exists(path):
        return path
    if not version:
        raise FileExistsError('refusing to overwrite: ' + path)
    folder, name = os.path.split(path)
    stem, ext = os.path.splitext(name)
    m = _VERSION.match(stem)
    base, n = (m.group('stem'), int(m.group('n'))) if m else (stem, 1)
    width = len(m.group('n')) if m else 3
    for i in range(n + 1, n + 10000):
        cand = os.path.join(folder, '{}_v{:0{}d}{}'.format(base, i, width, ext))
        if not exists(cand):
            return cand
    raise FileExistsError('no free version for ' + path)


def write_new(path, data):
    """Exclusive create: refuses to overwrite even if the file appeared after new_path()."""
    with open(path, 'xb') as f:
        f.write(data)
    return path
