"""new-case: AGR Tools 1.0 (#1024) project passport (K1) logic, stdlib only. Stub of branch 0; owned by branch F (improve/issue-1024-passport).

Pure logic for `project_passport` (project.passport); no pymxs. Use edit_core.py for reports, preview hashes and new paths, contract_core.py for
roles, markers and ObjRef (the core never takes a host object).

Contract K1 (#1024): every project has `jobs/<ID>/passport.json` + `PASSPORT.md` (schema
`schemas/ProjectPassport.schema.json`, SCHEMA below is the same document: the package does not ship `schemas/`,
a test keeps both equal). The scene keeps `{"path", "sha256"}` of the passport in the custom file property
`agr_passport` (contract_core.PASSPORT_PROP). On save the panel journal is copied to `jobs/<ID>/journal.jsonl`
(journal_core.copy_to) and its tail goes into `journal.tail`.

* `new_passport()` - the «завести проект» skeleton (11 stages todo, metres, Z up); valid by the schema.
* `validate()` - a stdlib validator of the JSON-Schema subset the schema uses; a broken passport is a PassportError
  naming the field (never a guessed default).
* `dumps()` / `loads()` - canonical text (sorted keys, UTF-8, trailing newline) and strict parse (duplicate keys,
  NaN are errors); `sha256()` of the bytes is what the scene property stores.
* `parts_from_roles()` - roles read back from the scene (agr_role user property, else the `<ROLE>_*` layer).
* `markdown()` - PASSPORT.md: source, normalization, stage table, parts, openings, materials, journal tail.
"""
import copy
import datetime
import hashlib
import json
import math
import os
import re

STAGE_IDS = tuple(range(10)) + ('agent',)
STAGE_STATUS = ('todo', 'work', 'done', 'blocked')
ROLES = ('body', 'opening', 'window', 'glass', 'capsule', 'roof', 'parapet', 'equipment', 'decor', 'helper')
PASSPORT_FILE = 'passport.json'
MARKDOWN_FILE = 'PASSPORT.md'
JOURNAL_FILE = 'journal.jsonl'
HISTORY_DIR = 'history'
TAIL_N = 20
PROJECT_ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')
SPEC_GAP = ('K2: the spec names window_type as an int; the opening marker stores a string library id '
            '(agr_window_type). The spec is not changed in this wave (#1024).')

_STAGE_ID = {'oneOf': [{'type': 'integer', 'minimum': 0, 'maximum': 9}, {'const': 'agent'}]}
_VEC3 = {'type': 'array', 'items': {'type': 'number'}, 'minItems': 3, 'maxItems': 3}
SCHEMA = {
    '$schema': 'https://json-schema.org/draft/2020-12/schema',
    '$id': 'ProjectPassport.schema.json',
    'title': 'ProjectPassport',
    'description': ('AGR Tools 1.0 project passport jobs/<ID>/passport.json (contract K1, #1024). Owner branch F. '
                    'Mandatory for every project; the scene keeps its path and sha256 in the file property '
                    'agr_passport. passport_core.SCHEMA is the same document (the package does not ship schemas/).'),
    'type': 'object',
    'additionalProperties': False,
    'required': ['schema', 'project_id', 'source', 'normalization', 'stages', 'parts', 'openings', 'materials',
                 'journal', 'agent_requests', 'questions'],
    'properties': {
        'schema': {'const': 1},
        'project_id': {'type': 'string', 'pattern': PROJECT_ID_RE.pattern},
        'title': {'type': 'string'},
        'address': {'type': 'string'},
        'created': {'type': 'string', 'format': 'date-time'},
        'updated': {'type': 'string', 'format': 'date-time'},
        'scene': {'type': 'string', 'minLength': 1},
        'source': {
            'type': 'object',
            'additionalProperties': False,
            'required': ['path', 'level', 'class'],
            'properties': {
                'path': {'type': 'string', 'minLength': 1},
                'sha256': {'type': 'string', 'pattern': '^[0-9a-f]{64}$'},
                'level': {'enum': ['A', 'B', 'C']},
                'class': {'type': 'string', 'minLength': 1},
                'parts': {'type': 'integer', 'minimum': 0},
                'largest_share': {'type': 'number', 'minimum': 0, 'maximum': 1},
                'route': {'type': 'string'},
                'note': {'type': 'string'},
            },
        },
        'normalization': {
            'type': 'object',
            'additionalProperties': False,
            'required': ['units', 'up_axis', 'scale', 'origin_m'],
            'properties': {
                'units': {'const': 'm'},
                'source_units': {'type': 'string'},
                'up_axis': {'const': 'Z'},
                'source_up_axis': {'enum': ['X', 'Y', 'Z']},
                'scale': {'type': 'number', 'exclusiveMinimum': 0},
                'origin_m': _VEC3,
                'grid_zero_m': _VEC3,
            },
        },
        'stages': {
            'type': 'array',
            'minItems': 11,
            'maxItems': 11,
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['id', 'status'],
                'properties': {
                    'id': _STAGE_ID,
                    'status': {'enum': list(STAGE_STATUS)},
                    'started': {'type': ['string', 'null'], 'format': 'date-time'},
                    'finished': {'type': ['string', 'null'], 'format': 'date-time'},
                    'seconds': {'type': ['number', 'null'], 'minimum': 0},
                    'blockers': {'type': 'array', 'items': {'type': 'string'}},
                },
            },
        },
        'parts': {
            'type': 'array',
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['name', 'role'],
                'properties': {
                    'name': {'type': 'string', 'minLength': 1},
                    'role': {'enum': list(ROLES)},
                    'levels': {'type': 'array', 'items': {'type': 'string', 'pattern': '^LEVEL_[A-Za-z0-9]+$'}},
                },
            },
        },
        'openings': {
            'type': 'array',
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['marker', 'window_type'],
                'properties': {
                    'marker': {'type': 'string', 'pattern': '^OPEN_[0-9]{3}$'},
                    'window_type': {'type': ['string', 'null']},
                    'status': {'enum': ['placed', 'ambiguous', 'draft', 'agent']},
                },
            },
        },
        'materials': {
            'type': 'array',
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['library_id'],
                'properties': {
                    'library_id': {'type': 'integer', 'minimum': 1, 'maximum': 1000},
                    'delivery_id': {'type': ['integer', 'null'], 'minimum': 1},
                    'mesh': {'type': 'string'},
                    'udim': {'type': ['integer', 'null'], 'minimum': 1001, 'maximum': 1999},
                    'npm_region': {'type': ['array', 'null'], 'items': {'type': 'number'}, 'minItems': 4,
                                   'maxItems': 4},
                },
            },
        },
        'journal': {
            'type': 'object',
            'additionalProperties': False,
            'required': ['path'],
            'properties': {
                'path': {'type': 'string', 'minLength': 1},
                'lines': {'type': 'integer', 'minimum': 0},
                'tail': {'type': 'array', 'maxItems': 50, 'items': {'type': 'object'}},
            },
        },
        'agent_requests': {
            'type': 'array',
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['id', 'stage', 'status'],
                'properties': {
                    'id': {'type': 'string', 'pattern': '^[A-Za-z0-9][A-Za-z0-9-]{0,63}$'},
                    'stage': _STAGE_ID,
                    'status': {'enum': ['open', 'answered', 'accepted', 'rolled_back']},
                    'path': {'type': 'string'},
                },
            },
        },
        'questions': {'type': 'array', 'items': {'type': 'string', 'minLength': 1}},
        'gaps': {'type': 'array', 'items': {'type': 'string', 'minLength': 1},
                 'description': ('Known gaps, e.g. the spec still says window_type: int while the marker stores '
                                 'a string id (#1024 K2).')},
    },
}


class PassportError(ValueError):
    """A passport that breaks the schema, a broken scene link or a refused write."""


# ---- stdlib JSON-Schema subset ------------------------------------------------------------------------------
_TYPES = {
    'object': lambda v: isinstance(v, dict),
    'array': lambda v: isinstance(v, list),
    'string': lambda v: isinstance(v, str),
    'integer': lambda v: isinstance(v, int) and not isinstance(v, bool),
    'number': lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    'boolean': lambda v: isinstance(v, bool),
    'null': lambda v: v is None,
}
_KNOWN = {'$schema', '$id', 'title', 'description', 'type', 'const', 'enum', 'pattern', 'minLength', 'required',
          'additionalProperties', 'properties', 'items', 'minItems', 'maxItems', 'minimum', 'maximum',
          'exclusiveMinimum', 'oneOf', 'format'}


def _errors(value, schema, where):
    unknown = set(schema) - _KNOWN
    if unknown:
        raise PassportError('schema keyword(s) not supported by passport_core: ' + ', '.join(sorted(unknown)))
    out = []
    if isinstance(value, float) and not math.isfinite(value):
        return ['{}: non-finite number'.format(where)]
    if 'oneOf' in schema:
        ok = sum(1 for s in schema['oneOf'] if not _errors(value, s, where))
        if ok != 1:
            out.append('{}: {!r} must match exactly one of {}'.format(where, value, len(schema['oneOf'])))
        return out
    if 'const' in schema and not (value == schema['const'] and type(value) is type(schema['const'])):
        return ['{}: must be {!r}, got {!r}'.format(where, schema['const'], value)]
    if 'enum' in schema and not any(value == e and type(value) is type(e) for e in schema['enum']):
        return ['{}: {!r} is not one of {}'.format(where, value, schema['enum'])]
    if 'type' in schema:
        types = schema['type'] if isinstance(schema['type'], list) else [schema['type']]
        if not any(_TYPES[t](value) for t in types):
            return ['{}: {!r} is not of type {}'.format(where, value, '/'.join(types))]
    if isinstance(value, str):
        if 'minLength' in schema and len(value) < schema['minLength']:
            out.append('{}: shorter than {}'.format(where, schema['minLength']))
        if 'pattern' in schema and not re.search(schema['pattern'], value):
            out.append('{}: {!r} does not match {}'.format(where, value, schema['pattern']))
        if schema.get('format') == 'date-time' and not _is_datetime(value):
            out.append('{}: {!r} is not an RFC 3339 date-time'.format(where, value))
    if _TYPES['number'](value):
        if 'minimum' in schema and value < schema['minimum']:
            out.append('{}: {} < minimum {}'.format(where, value, schema['minimum']))
        if 'maximum' in schema and value > schema['maximum']:
            out.append('{}: {} > maximum {}'.format(where, value, schema['maximum']))
        if 'exclusiveMinimum' in schema and value <= schema['exclusiveMinimum']:
            out.append('{}: {} <= exclusiveMinimum {}'.format(where, value, schema['exclusiveMinimum']))
    if isinstance(value, list):
        if 'minItems' in schema and len(value) < schema['minItems']:
            out.append('{}: fewer than {} items'.format(where, schema['minItems']))
        if 'maxItems' in schema and len(value) > schema['maxItems']:
            out.append('{}: more than {} items'.format(where, schema['maxItems']))
        if 'items' in schema:
            for i, item in enumerate(value):
                out.extend(_errors(item, schema['items'], '{}[{}]'.format(where, i)))
    if isinstance(value, dict):
        props = schema.get('properties', {})
        for k in schema.get('required', ()):
            if k not in value:
                out.append('{}: missing required {!r}'.format(where, k))
        if schema.get('additionalProperties') is False:
            for k in value:
                if k not in props:
                    out.append('{}: unexpected field {!r}'.format(where, k))
        for k, sub in props.items():
            if k in value:
                out.extend(_errors(value[k], sub, '{}.{}'.format(where, k)))
    return out


_DT = re.compile(r'^\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$')


def _is_datetime(text):
    if not _DT.match(text):
        return False
    try:
        datetime.datetime.fromisoformat(text.replace('Z', '+00:00').replace('z', '+00:00'))
    except ValueError:
        return False
    return True


def errors(passport, schema=None):
    """All schema violations of a passport (empty list: valid)."""
    return _errors(passport, SCHEMA if schema is None else schema, 'passport')


def validate(passport):
    """The passport, or PassportError listing the first violations; stages must be 0..9 + agent once each."""
    errs = errors(passport)
    if not errs:
        ids = [s['id'] for s in passport['stages']]
        if sorted(ids, key=str) != sorted(STAGE_IDS, key=str) or len(set(map(str, ids))) != len(ids):
            errs.append('passport.stages: must list stages 0..9 and agent once each, got {!r}'.format(ids))
    if errs:
        raise PassportError('passport breaks ProjectPassport.schema.json: ' + '; '.join(errs[:8]))
    return passport


# ---- text, bytes, sha ---------------------------------------------------------------------------------------
def _unique(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise PassportError('duplicate key in passport: ' + repr(k))
        out[k] = v
    return out


def _reject(token):
    raise PassportError('non-finite number in passport: ' + token)


def dumps(passport):
    """Canonical UTF-8 bytes of a valid passport (sorted keys, indent 1, trailing newline)."""
    validate(passport)
    return (json.dumps(passport, ensure_ascii=False, sort_keys=True, indent=1, allow_nan=False) + '\n').encode('utf-8')


def loads(data):
    """Strict parse + validate (bytes or text)."""
    text = data.decode('utf-8-sig') if isinstance(data, (bytes, bytearray)) else data
    try:
        doc = json.loads(text, object_pairs_hook=_unique, parse_constant=_reject)
    except PassportError:
        raise
    except ValueError as exc:
        raise PassportError('passport is not JSON: {}'.format(exc)) from None
    return validate(doc)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    """(passport, sha256 of the file bytes) of a passport file; PassportError if missing or broken."""
    if not os.path.isfile(path):
        raise PassportError('passport not found: ' + path)
    with open(path, 'rb') as f:
        data = f.read()
    try:
        return loads(data), sha256(data)
    except PassportError as exc:
        raise PassportError('{} ({})'.format(exc, path)) from None


# ---- scene link (file property agr_passport) ----------------------------------------------------------------
def link_value(path, sha):
    if not isinstance(path, str) or not path or not re.match(r'^[0-9a-f]{64}$', str(sha)):
        raise PassportError('passport link needs a path and a sha256')
    return json.dumps({'path': path.replace('\\', '/'), 'sha256': sha}, sort_keys=True)


def parse_link(text):
    """None for no link; {'path', 'sha256'} for a good one; PassportError for a broken property."""
    if text in (None, ''):
        return None
    try:
        data = json.loads(text) if isinstance(text, str) else None
    except ValueError:
        data = None
    if not isinstance(data, dict) or set(data) != {'path', 'sha256'} or not isinstance(data['path'], str) \
            or not data['path'] or not re.match(r'^[0-9a-f]{64}$', str(data['sha256'])):
        raise PassportError('scene property agr_passport is broken: ' + repr(text)[:160])
    return data


# ---- the passport document ----------------------------------------------------------------------------------
def now():
    return datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()


def check_project_id(project_id):
    if not isinstance(project_id, str) or not PROJECT_ID_RE.match(project_id):
        raise PassportError('project id must be [A-Za-z0-9][A-Za-z0-9_-]{0,63}: ' + repr(project_id))
    return project_id


def project_id_from(name):
    """A project id from a scene / folder name: unsupported characters become `_`; None if nothing is left."""
    stem = os.path.splitext(os.path.basename(str(name or '')))[0]
    pid = re.sub(r'[^A-Za-z0-9_-]+', '_', stem).strip('_-')[:64]
    return pid if pid and PROJECT_ID_RE.match(pid) else None


def project_dir(root, project_id):
    return os.path.join(root, 'jobs', check_project_id(project_id))


def new_passport(project_id, source_path='untitled', scene=None, title=None, address=None, ts=None):
    """«Завести проект»: a valid passport with every stage todo, the source still unclassified (level C)."""
    check_project_id(project_id)
    ts = ts or now()
    p = {'schema': 1, 'project_id': project_id, 'created': ts, 'updated': ts,
         'source': {'path': str(source_path or 'untitled'), 'level': 'C', 'class': 'unclassified',
                    'note': 'not classified yet: run source.intake / scene.source_class'},
         'normalization': {'units': 'm', 'up_axis': 'Z', 'scale': 1.0, 'origin_m': [0.0, 0.0, 0.0],
                           'grid_zero_m': [0.0, 0.0, 0.0]},
         'stages': [{'id': sid, 'status': 'todo'} for sid in STAGE_IDS],
         'parts': [], 'openings': [], 'materials': [],
         'journal': {'path': JOURNAL_FILE, 'lines': 0, 'tail': []},
         'agent_requests': [],
         'questions': ['Source level A/B/C is not defined in #1024; default rule: A shell, B panelised, '
                       'C ambiguous/unclassified (scene10_core.LEVEL_RULE).'],
         'gaps': [SPEC_GAP]}
    if scene:
        p['scene'] = str(scene).replace('\\', '/')
    if title:
        p['title'] = str(title)
    if address:
        p['address'] = str(address)
    return validate(p)


def stage(passport, sid):
    for s in passport['stages']:
        if s['id'] == sid:
            return s
    raise PassportError('passport has no stage {!r}'.format(sid))


def set_stage(passport, sid, status, ts=None, blockers=None):
    """Move a stage: work stamps `started`, done stamps `finished` and `seconds`; blocked keeps the blockers."""
    if status not in STAGE_STATUS:
        raise PassportError('unknown stage status {!r}'.format(status))
    p = copy.deepcopy(passport)
    s = stage(p, sid)
    ts = ts or now()
    if status == 'work' and not s.get('started'):
        s['started'] = ts
    if status == 'done':
        s.setdefault('started', ts)
        s['finished'] = ts
        try:
            a = datetime.datetime.fromisoformat(s['started'])
            b = datetime.datetime.fromisoformat(ts)
            s['seconds'] = max(0.0, (b - a).total_seconds())
        except (TypeError, ValueError):
            s['seconds'] = None
    if status == 'blocked':
        s['blockers'] = [str(b) for b in (blockers or ['blocked'])]
    elif 'blockers' in s and status != 'blocked':
        s.pop('blockers')
    s['status'] = status
    return validate(p)


def stage_table(passport):
    return [{'id': s['id'], 'status': s['status'], 'seconds': s.get('seconds')} for s in passport['stages']]


NAME_ROLES = ((re.compile(r'^BODY_[A-Za-z0-9]+_\d{3}$'), 'body'), (re.compile(r'^OPEN_\d{3}$'), 'opening'),
              (re.compile(r'^LEVEL_[A-Za-z0-9]+$'), 'helper'))  # contract K1 names (contract_core BODY_RE, ...)


def role_of(prop, layer, name=None):
    """(role, source, problem) of one node: the agr_role user property wins; else a `<ROLE>_*` layer; else a
    contract name (`BODY_<material>_NNN` body, `OPEN_<nnn>` opening, `LEVEL_<name>` helper).

    problem: None | role_unknown (prop is not a contract role) | role_conflict (prop and layer disagree) |
    role_missing (none of them)."""
    layer_role = None
    for r in ROLES:
        if str(layer or '').upper().startswith(r.upper() + '_'):
            layer_role = r
            break
    if layer_role is None and prop in (None, ''):
        for rx, r in NAME_ROLES:
            if rx.match(str(name or '')):
                return r, 'name', None
    if prop not in (None, ''):
        if prop not in ROLES:
            return None, 'prop', 'role_unknown'
        if layer_role and layer_role != prop:
            return prop, 'prop', 'role_conflict'
        return prop, 'prop', None
    if layer_role:
        return layer_role, 'layer', None
    return None, None, 'role_missing'


def parts_from_roles(items):
    """items [{'name', 'prop', 'layer'}] -> (parts for the passport, {name: (code, detail)} problems)."""
    parts, problems = [], {}
    for it in items:
        role, src, problem = role_of(it.get('prop'), it.get('layer'), it.get('name'))
        if problem == 'role_unknown':
            problems[it['name']] = ('role_unknown', 'agr_role {!r} is not one of {}'.format(it.get('prop'),
                                                                                         ', '.join(ROLES)))
        elif problem == 'role_conflict':
            problems[it['name']] = ('role_conflict', 'agr_role {!r} but layer {!r}'.format(it.get('prop'),
                                                                                         it.get('layer')))
        elif problem == 'role_missing':
            problems[it['name']] = ('role_missing', 'no agr_role and no <ROLE>_* layer')
        if role:
            parts.append({'name': it['name'], 'role': role})
    parts.sort(key=lambda x: (ROLES.index(x['role']), x['name']))
    return parts, problems


def with_parts(passport, parts):
    """Passport with `parts` replaced by the scene's roles; levels of a part already listed are kept."""
    p = copy.deepcopy(passport)
    old = {x['name']: x for x in p['parts']}
    out = []
    for x in parts:
        y = dict(x)
        if 'levels' in old.get(x['name'], {}) and old[x['name']]['role'] == x['role']:
            y['levels'] = list(old[x['name']]['levels'])
        out.append(y)
    p['parts'] = out
    return validate(p)


def with_journal(passport, lines, tail):
    p = copy.deepcopy(passport)
    p['journal'] = {'path': JOURNAL_FILE, 'lines': int(lines), 'tail': [dict(x) for x in list(tail)[-TAIL_N:]]}
    return validate(p)


def with_source(passport, source, normalization):
    """Passport with the intake result: source {path, level, class, ...} and normalization (metres, Z up)."""
    p = copy.deepcopy(passport)
    p['source'] = dict(source)
    p['normalization'] = dict(normalization)
    p['questions'] = list(p['questions'])
    return validate(p)


def touched(passport, ts=None):
    p = copy.deepcopy(passport)
    p['updated'] = ts or now()
    return validate(p)


def markdown(passport):
    """PASSPORT.md: the human view of passport.json (the JSON is the source of truth)."""
    p = validate(passport)
    s, n = p['source'], p['normalization']
    lines = ['# Паспорт проекта {}'.format(p['project_id']), '']
    if p.get('title'):
        lines += ['**{}**'.format(p['title']), '']
    if p.get('address'):
        lines += ['Адрес: {}'.format(p['address']), '']
    lines += ['Файл данных: `passport.json` (схема `ProjectPassport.schema.json`, контракт К1 #1024). '
              'Этот файл — только просмотр; правится паспорт кнопкой «Паспорт».', '',
              '## Источник', '',
              '- путь: `{}`'.format(s['path']),
              '- уровень: **{}**, класс: `{}`'.format(s['level'], s['class'])]
    if 'route' in s:
        lines.append('- маршрут: {}'.format(s['route']))
    if s.get('note'):
        lines.append('- заметка: {}'.format(s['note']))
    lines += ['', '## Нормализация', '',
              '- единицы: {} (источник: {}), ось вверх: {} (источник: {}), масштаб: {}'.format(
                  n['units'], n.get('source_units', '—'), n['up_axis'], n.get('source_up_axis', '—'), n['scale']),
              '- общий ноль, м: {}'.format(n['origin_m'])]
    if 'grid_zero_m' in n:
        lines.append('- ноль сетки, м: {}'.format(n['grid_zero_m']))
    lines += ['', '## Этапы', '', '| Этап | Статус | Время, с |', '|---|---|---|']
    for st in p['stages']:
        sec = st.get('seconds')
        lines.append('| {} | {} | {} |'.format(st['id'], st['status'], '—' if sec is None else round(sec)))
    lines += ['', '## Части здания ({})'.format(len(p['parts'])), '']
    lines += ['- `{}` — {}'.format(x['name'], x['role']) for x in p['parts']] or ['—']
    lines += ['', '## Проёмы ({})'.format(len(p['openings'])), '']
    lines += ['- `{}` → {}'.format(x['marker'], x['window_type']) for x in p['openings']] or ['—']
    lines += ['', '## Материалы ({})'.format(len(p['materials'])), '']
    lines += ['- ID {} → UDIM {}'.format(x['library_id'], x.get('udim')) for x in p['materials']] or ['—']
    j = p['journal']
    lines += ['', '## Журнал', '', '`{}`: строк {}'.format(j['path'], j.get('lines', 0)), '']
    for x in j.get('tail', [])[-10:]:
        lines.append('- {} {} {} {} ({})'.format(x.get('ts'), x.get('tool'), x.get('mode'), x.get('status'),
                                                x.get('actor')))
    lines += ['', '## Запросы агенту ({})'.format(len(p['agent_requests'])), '']
    lines += ['- {} этап {}: {}'.format(x['id'], x['stage'], x['status']) for x in p['agent_requests']] or ['—']
    lines += ['', '## Вопросы', '']
    lines += ['- ' + q for q in p['questions']] or ['—']
    if p.get('gaps'):
        lines += ['', '## Пробелы', ''] + ['- ' + g for g in p['gaps']]
    return '\n'.join(lines) + '\n'
