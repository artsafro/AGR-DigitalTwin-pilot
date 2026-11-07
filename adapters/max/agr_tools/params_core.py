"""new-case: AGR Tools 1.1 parameter form of the stage buttons (pure, stdlib; no pymxs, no Qt).

Release 1.0.0 passed a 1.0 button only the selection: 15 of 31 buttons of the release smoke refused, six of them
because a parameter had no place in the panel (CHANGELOG 1.0.0/1.0.1 «Известные ограничения»: atlas.facade_strip
period_by_id, tex.dilate / tex.plug_colour files, export.place_by_passport fbx, agent.request task, agent.accept
request). 1.1 gives these rows (and the four handoff rows) a compact form in the dock: FIELDS names the options of
each row exactly as its glue reads them, `defaults` fills them from the project passport and the last values,
`parse` turns the form text into the options object and `missing` names what is still required.

The runtime (edit_ui) refuses a press with an empty required field with `needs_params: ...` naming the fields, never
silently; the panel opens the form instead. Option keys must be the glue's own: a test compares them with the
option tables of the cores (handoff_core.*_OPTIONS, agentbridge_core.options, placegeo_core.place_options, ...).
"""
import json
import os
from collections import namedtuple

Field = namedtuple('Field', 'key label kind hint choices')
KINDS = ('text', 'file', 'files', 'folder', 'json', 'bool', 'choice')


def _f(key, label, kind, hint='', choices=()):
    if kind not in KINDS:
        raise ValueError('unknown field kind ' + repr(kind))
    return Field(key, label, kind, hint, tuple(choices))


FIELDS = {
    'atlas.facade_strip': (
        _f('period_by_id', 'Период по matID, м (JSON)', 'json',
           'например {"3": [3.6, 3.0]}: шаг полосы по U и V для каждого ID фасада'),
        _f('out_dir', 'Папка атласа', 'folder', 'новая папка; пусто — рядом со сценой'),
    ),
    'tex.dilate': (
        _f('files', 'Карты PNG', 'files', 'пути через «;»; или папка ниже'),
        _f('folder', 'Папка карт', 'folder', 'все PNG папки'),
        _f('out', 'Папка результата', 'folder', 'новые файлы; оригиналы не трогаются'),
        _f('profile', 'Профиль', 'choice', '', ('vpm', 'npm')),
    ),
    'tex.plug_colour': (
        _f('paths', 'Файлы карт', 'files', 'пути через «;»; или папка ниже'),
        _f('folder', 'Папка карт', 'folder', 'все изображения папки'),
    ),
    'export.place_by_passport': (
        _f('fbx', 'FBX для постановки', 'file', 'сдаваемый FBX; ставится по МСК из паспорта'),
        _f('passport', 'Паспорт (JSON)', 'file', 'пусто — паспорт рядом с FBX'),
        _f('accept_precision_loss', 'Принять потерю точности > 1 мм', 'bool',
           'только осознанно: одинарная точность Max на больших координатах'),
    ),
    'agent.request': (
        _f('task', 'Задача агенту', 'text', 'что сделать, одной фразой'),
        _f('request_id', 'Id запроса', 'text', 'буквы, цифры, «-»; пусто — по времени'),
        _f('job_dir', 'Папка проекта jobs/<ID>', 'folder', 'по умолчанию — папка паспорта'),
    ),
    'agent.accept': (
        _f('request', 'request.json запроса', 'file', 'по умолчанию — последний запрос проекта'),
        _f('job_dir', 'Папка проекта jobs/<ID>', 'folder', 'вместе с id запроса вместо пути'),
        _f('request_id', 'Id запроса', 'text', ''),
    ),
    'handoff.export': (
        _f('job_dir', 'Папка проекта jobs/<ID>', 'folder', 'бандл ляжет в <папка>/handoff/<seq>/'),
        _f('seq', 'Номер бандла', 'text', 'три цифры; пусто — следующий свободный'),
    ),
    'handoff.import': (
        _f('bundle', 'Бандл handoff/<seq>', 'folder', 'по умолчанию — последний бандл проекта'),
        _f('fbx', 'FBX из Blender', 'file', 'пусто — model.fbx бандла'),
        _f('request_id', 'Id запроса (слой AGENT_<id>)', 'text', 'пусто — bh<seq>'),
    ),
    'handoff.verify': (
        _f('bundle', 'Бандл handoff/<seq>', 'folder', 'по умолчанию — последний бандл проекта'),
        _f('layer', 'Слой для сверки', 'text', 'например AGENT_bh001; пусто — выделение'),
        _f('blender_readback', 'readback Blender (JSON)', 'file', 'необязательно'),
    ),
    'handoff.restore_materials': (
        _f('bundle', 'Бандл handoff/<seq>', 'folder', 'по умолчанию — последний бандл проекта'),
        _f('materials', 'materials.json', 'file', 'вместо бандла'),
        _f('layer', 'Слой объектов', 'text', 'пусто — выделение'),
        _f('reuse', 'Материалы сцены', 'choice', 'scene — взять идентичный материал сцены; never — пересобрать',
           ('scene', 'never')),
    ),
}
# Required options: each entry is a tuple of alternatives, at least one of them must be given.
REQUIRED = {
    'atlas.facade_strip': (('period_by_id',),),
    'tex.dilate': (('files', 'folder'),),
    'tex.plug_colour': (('paths', 'folder'),),
    'export.place_by_passport': (('fbx',),),
    'agent.request': (('task',),),
    'agent.accept': (('request', 'request_id'),),
    'handoff.export': (('job_dir',),),
    'handoff.import': (('bundle',),),
    'handoff.verify': (('bundle',),),
    'handoff.restore_materials': (('bundle', 'materials'),),
}
TOOLS = tuple(FIELDS)


def fields(tool):
    if tool not in FIELDS:
        raise KeyError('no parameter form for ' + repr(tool))
    return FIELDS[tool]


def has_form(tool):
    return tool in FIELDS


def _given(v):
    return v is not None and v != '' and v != [] and v != {} and v is not False


def missing(tool, options):
    """Labels of the required alternatives still empty in `options` (a row without a form needs nothing)."""
    if tool not in FIELDS:
        return []
    opts = options or {}
    labels = {f.key: f.label for f in FIELDS[tool]}
    out = []
    for alts in REQUIRED.get(tool, ()):
        if not any(_given(opts.get(k)) for k in alts):
            out.append(' или '.join(labels[k] for k in alts))
    return out


def needs_params_text(tool, options):
    """`needs_params: <tool>: заполните ...` or None when nothing required is empty."""
    gap = missing(tool, options)
    if not gap:
        return None
    return 'needs_params: {}: заполните в форме параметров панели: {}'.format(tool, '; '.join(gap))


def _newest(paths):
    """The last entry of a list ordered oldest -> newest (scan_project orders it)."""
    paths = [p for p in (paths or ()) if p]
    return paths[-1] if paths else None


def defaults(tool, ctx=None):
    """Form values {key: value} of `tool` from ctx: passport_path, passport (dict), scene, last ({key: value} of the
    last run of this tool), bundles (handoff/<seq> folders of the project), requests (request.json of the project).
    The last values win over the passport; nothing is invented (an unknown value stays empty)."""
    ctx = ctx or {}
    fs = fields(tool)
    keys = {f.key for f in fs}
    pp = ctx.get('passport_path')
    job = os.path.dirname(pp) if pp else None
    out = {f.key: (False if f.kind == 'bool' else (f.choices[0] if f.kind == 'choice' else '')) for f in fs}
    if 'job_dir' in keys and job:
        out['job_dir'] = job
    if tool == 'export.place_by_passport' and pp:
        out['passport'] = pp
    if 'bundle' in keys:
        out['bundle'] = _newest(ctx.get('bundles')) or ''
    if tool == 'agent.accept':
        out['request'] = _newest(ctx.get('requests')) or ''
    if tool == 'agent.request' and job and not out.get('job_dir'):
        out['job_dir'] = job
    for k, v in (ctx.get('last') or {}).items():
        if k in keys and _given(v):
            out[k] = v
    return out


def _text(v):
    return v.strip() if isinstance(v, str) else v


def parse(tool, values):
    """Form values -> the options object of the row (empty fields dropped). A bad value is an error naming the
    field, never a silent default."""
    fs = fields(tool)
    unknown = set(values or {}) - {f.key for f in fs}
    if unknown:
        raise ValueError('unknown {} parameters: {}'.format(tool, ', '.join(sorted(unknown))))
    out = {}
    for f in fs:
        v = (values or {}).get(f.key)
        if f.kind == 'bool':
            if v not in (None, True, False):
                raise ValueError('{}: да или нет'.format(f.label))
            if v:
                out[f.key] = True
            continue
        v = _text(v)
        if v in (None, ''):
            continue
        if f.kind == 'files':
            items = v if isinstance(v, list) else [x.strip() for x in str(v).replace('\n', ';').split(';')]
            items = [x for x in items if x]
            if items:
                out[f.key] = items
        elif f.kind == 'json':
            if isinstance(v, (dict, list)):
                out[f.key] = v
                continue
            try:
                out[f.key] = json.loads(v)
            except ValueError as exc:
                raise ValueError('{}: не JSON ({})'.format(f.label, exc)) from None
            if not isinstance(out[f.key], dict):
                raise ValueError('{}: нужен объект JSON {{...}}'.format(f.label))
        elif f.kind == 'choice':
            if v not in f.choices:
                raise ValueError('{}: одно из {}'.format(f.label, ', '.join(f.choices)))
            out[f.key] = v
        else:
            out[f.key] = str(v)
    return out


def text_of(field, value):
    """Display text of a value in the form (files joined by «; », JSON dumped)."""
    if field.kind == 'files' and isinstance(value, list):
        return '; '.join(value)
    if field.kind == 'json' and isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if field.kind == 'bool':
        return bool(value)
    return '' if value is None else str(value)


def scan_project(job_dir, listdir=os.listdir, isdir=os.path.isdir, isfile=os.path.isfile, getmtime=os.path.getmtime):
    """{'bundles': [...], 'requests': [...]} of a project folder jobs/<ID>, oldest -> newest: bundles handoff/<seq>/
    by number, requests agent/<req>/request.json by modification time (request ids are free text).
    Unreadable folders give empty lists (the defaults then stay empty, never guessed)."""
    out = {'bundles': [], 'requests': []}
    if not job_dir:
        return out
    for sub, key, leaf in (('handoff', 'bundles', None), ('agent', 'requests', 'request.json')):
        base = os.path.join(job_dir, sub)
        try:
            names = sorted(listdir(base))
        except OSError:
            continue
        for n in names:
            p = os.path.join(base, n)
            if leaf is None:
                if isdir(p) and len(n) == 3 and n.isdigit():
                    out[key].append(p)
            elif isfile(os.path.join(p, leaf)):
                out[key].append(os.path.join(p, leaf))
    try:
        out['requests'].sort(key=lambda q: (getmtime(q), q))
    except OSError:
        out['requests'].sort()
    return out
