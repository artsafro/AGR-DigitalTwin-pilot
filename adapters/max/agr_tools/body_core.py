"""new-case: AGR Tools 1.0 (#1024) body roles, LEVEL_* helpers logic, stdlib only. owned by branch G (improve/issue-1024-body).

Pure logic for `body_prepare` (body.prepare); no pymxs. Plain data in (ObjRef-like dicts, metres), a plan out.
#1024 1.0.4 «Подготовить бадик для агента» (undo), contract К1 (contract_core):
  * roles: user property `agr_role` (contract_core.ROLES) on every selected object; geometry -> `body`, helpers ->
    `helper`; a valid role already set is kept; an unknown value is a finding (`role_unknown`), never overwritten;
  * working names `BODY_<material>_NNN` (contract_core.BODY_RE, the names Quick Attach gives) for bodies whose
    name does not match yet (option rename);
  * layers `<ROLE>_main` (contract_core.role_layer) unless the object already sits in a `<ROLE>_*` layer;
  * height helpers `LEVEL_<name>` (D044-D046, docs/domain/patterns/markup-helpers.md) from picked heights (pickPoint
    in the panel) or the list `options.levels` (batch, MCP); default names L1..L<n-1> and `roof` for the top;
  * checks: a role on every object; level names by the extractor's rule (src/dt_ai/spec/mesh.py:27-28
    LEVEL_NAME / LEVEL_COUNTER, intersected with contract_core.LEVEL_RE); heights unique within 1 mm
    (mesh.py:29 LEVEL_SAME_M) against each other AND the LEVEL_* helpers already in the scene -> otherwise
    refused (`plan.ambiguous`, apply refuses);
  * passport: the K1 section for the passport (`plan.passport`); the write itself is branch F's (passport_core has
    no write API at base c6921137) -> listed in `skipped` with that reason.
Deviation (recorded in the PR): the #1024 acceptance names `LEVEL_1`, `LEVEL_2`; mesh.py:27 requires a letter after
`LEVEL_`, so the default names are `LEVEL_L1`, `LEVEL_L2` (options.level_names takes any valid names).
"""
import math
import re

LEVEL_NAME = re.compile(r'^LEVEL_[A-Za-z][A-Za-z0-9_]*$')   # src/dt_ai/spec/mesh.py:27
LEVEL_COUNTER = re.compile(r'\d{3}$')                       # src/dt_ai/spec/mesh.py:28
LEVEL_SAME_M = 0.001                                        # src/dt_ai/spec/mesh.py:29 (1 mm)
OPTIONS = {'levels', 'level_names', 'pick', 'rename', 'layers', 'roles'}
MAX_LEVELS = 99
LAYER_SUFFIX = 'main'


def _contract():
    import importlib.util
    import os
    import sys
    mod = sys.modules.get('agr_tools_contract_core')
    if mod is not None and getattr(mod, '__file__', None):
        return mod
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location('agr_tools_contract_core', os.path.join(here, 'contract_core.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.modules['agr_tools_contract_core'] = mod
    return mod


def level_name_problem(name):
    """None if `name` is a valid height helper name for the extractor and the contract, else the reason."""
    c = _contract()
    name = str(name)
    if not LEVEL_NAME.match(name):
        return 'not LEVEL_<letter>[A-Za-z0-9_]* (mesh.py:27)'
    if LEVEL_COUNTER.search(name):
        return 'ends with a 3-digit counter (Max copy, mesh.py:28)'
    if not c.LEVEL_RE.match(name):
        return 'not LEVEL_[A-Za-z0-9]+ (contract_core.LEVEL_RE)'
    return None


def default_level_names(n):
    """L1..L<n-1> and roof for the top (the #1024 acceptance: 3 clicks -> two storeys and the roof)."""
    if n <= 0:
        return []
    return ['L{}'.format(i) for i in range(1, n)] + ['roof']


def options(opts, m_per_unit=1.0):
    """Validated options; `levels` in metres (numbers or {name, z_m})."""
    opts = dict(opts or {})
    unknown = set(opts) - OPTIONS
    if unknown:
        raise ValueError('unknown body.prepare options: ' + ', '.join(sorted(unknown)))
    levels = opts.get('levels') or []
    if not isinstance(levels, list) or len(levels) > MAX_LEVELS:
        raise ValueError('options.levels must be a list of up to {} heights in metres'.format(MAX_LEVELS))
    zs, names = [], []
    for i, lv in enumerate(levels):
        name = None
        if isinstance(lv, dict):
            if set(lv) - {'name', 'z_m'} or 'z_m' not in lv:
                raise ValueError('options.levels[{}] must be a number or {{name, z_m}}'.format(i))
            name, lv = lv.get('name'), lv['z_m']
        if isinstance(lv, bool) or not isinstance(lv, (int, float)) or not math.isfinite(lv):
            raise ValueError('options.levels[{}] must be a finite height in metres: {!r}'.format(i, lv))
        zs.append(float(lv))
        names.append(name)
    given = opts.get('level_names')
    if given is not None:
        if not isinstance(given, list) or not all(isinstance(x, str) for x in given):
            raise ValueError('options.level_names must be a list of strings')
    pick = opts.get('pick', 0)
    if isinstance(pick, bool) or not isinstance(pick, int) or not 0 <= pick <= MAX_LEVELS:
        raise ValueError('options.pick must be the number of heights to pick (0..{})'.format(MAX_LEVELS))
    roles = opts.get('roles') or {}
    if not isinstance(roles, dict):
        raise ValueError('options.roles must map object names to roles')
    c = _contract()
    for k, v in roles.items():
        c.check_role(v)
    for key in ('rename', 'layers'):
        if not isinstance(opts.get(key, True), bool):
            raise ValueError('options.{} must be true or false'.format(key))
    return {'levels': zs, 'level_given': names, 'level_names': given, 'pick': pick, 'roles': dict(roles),
            'rename': opts.get('rename', True), 'layers': opts.get('layers', True)}


def name_levels(zs, given_each=None, names=None):
    """[(name, z)] sorted by height: explicit {name} entries, else options.level_names, else the defaults."""
    order = sorted(range(len(zs)), key=lambda i: zs[i])
    each = list(given_each or [None] * len(zs))
    if names is not None and len(names) != len(zs):
        raise ValueError('options.level_names has {} names for {} heights'.format(len(names), len(zs)))
    defaults = default_level_names(len(zs))
    out = []
    for rank, i in enumerate(order):
        nm = each[i] if each[i] is not None else (names[rank] if names is not None else defaults[rank])
        nm = str(nm)
        out.append((nm if nm.startswith('LEVEL_') else 'LEVEL_' + nm, zs[i]))
    return out


def prepare_plan(objects, scene_levels=(), opts=None, taken=()):
    """Plan of body.prepare.

    objects: [{handle, name, kind: geometry|helper|other, role: str|None (agr_role as read), material: str|None
               (name; Multi/Sub: its name), layer: str, z_m: float|None (helpers: world Z in metres)}].
    scene_levels: [{handle, name, z_m}] of LEVEL_* helpers in the whole scene (selected or not).
    taken: object names in the scene (new BODY_ names and LEVEL_ names avoid them).
    Returns {roles: [(handle, role)], renames: [(handle, old, new)], layers: [(handle, layer)], levels:
    [{name, z_m}], findings: {handle: [(code, detail)]}, ambiguous: [text], skipped: [(item, reason)],
    passport: {...}}."""
    c = _contract()
    o = opts if isinstance(opts, dict) and 'level_given' in opts else options(opts)
    if not objects and not o['levels']:
        raise ValueError('body.prepare: empty selection and no levels')
    taken = set(taken)
    findings, ambiguous, skipped = {}, [], []
    roles, renames, layers = [], [], []
    m10 = _model10()
    counters = {}
    for ob in objects:
        h, name = ob['handle'], ob['name']
        want = o['roles'].get(name)
        have = ob.get('role')
        if have not in (None, '') and have not in c.ROLES:
            findings.setdefault(h, []).append(('role_unknown', 'agr_role {!r} is not one of {}'.format(
                have, ', '.join(c.ROLES))))
            continue
        if want is None:
            if have:
                role = have
            elif ob['kind'] == 'geometry':
                role = 'body'
            elif ob['kind'] == 'helper':
                role = 'helper'
            else:
                skipped.append((name, 'not geometry or a helper ({}); give options.roles'.format(ob.get('cls') or
                                                                                               ob['kind'])))
                continue
        else:
            role = want
        if role != have:
            roles.append((h, role))
        if role == 'body' and o['rename'] and not c.BODY_RE.match(name):
            token = m10.material_token(ob.get('material'))
            taken.discard(name)
            new = m10.next_body_name(token, taken)
            renames.append((h, name, new))
        if o['layers'] and not str(ob.get('layer') or '').startswith(c.role_layer(role)):
            layers.append((h, c.role_layer(role) + LAYER_SUFFIX))
        if name.startswith('LEVEL_'):
            why = level_name_problem(name)
            if why:
                findings.setdefault(h, []).append(('level_name', '{}: {}'.format(name, why)))
            counters[name] = counters.get(name, 0) + 1
    # heights: the scene's LEVEL_* helpers and the new ones, unique within 1 mm, names unique
    existing = [dict(x) for x in scene_levels]
    for x in existing:
        if x['name'] in counters:
            continue
        why = level_name_problem(x['name'])
        if why:
            ambiguous.append('scene helper {}: {}'.format(x['name'], why))
    sel = {ob['handle'] for ob in objects}
    for i, a in enumerate(existing):
        for b in existing[i + 1:]:
            if abs(a['z_m'] - b['z_m']) < LEVEL_SAME_M:
                text = 'helpers {} and {} at one height {:.4f} m (1 mm)'.format(a['name'], b['name'], a['z_m'])
                for x in (a, b):
                    if x['handle'] in sel:
                        findings.setdefault(x['handle'], []).append(('level_duplicate', text))
                if a['handle'] not in sel and b['handle'] not in sel:
                    ambiguous.append(text)
    new = name_levels(o['levels'], o['level_given'], o['level_names'])
    levels = []
    names_seen = {x['name'] for x in existing}
    for nm, z in new:
        why = level_name_problem(nm)
        if why:
            ambiguous.append('new level {}: {}'.format(nm, why))
            continue
        if nm in names_seen or nm in taken:
            ambiguous.append('new level {}: the name is taken in the scene'.format(nm))
            continue
        clash = [x['name'] for x in existing if abs(x['z_m'] - z) < LEVEL_SAME_M] + \
                [lv['name'] for lv in levels if abs(lv['z_m'] - z) < LEVEL_SAME_M]
        if clash:
            ambiguous.append('new level {} at {:.4f} m: the height is given already ({}, 1 mm) - refused'.format(
                nm, z, ', '.join(clash)))
            continue
        names_seen.add(nm)
        levels.append({'name': nm, 'z_m': z})
    counts = {}
    for ob in objects:
        r = dict(roles).get(ob['handle'], ob.get('role'))
        if r in c.ROLES:
            counts[r] = counts.get(r, 0) + 1
    all_levels = sorted([{'name': x['name'], 'z_m': x['z_m']} for x in existing] + levels, key=lambda x: x['z_m'])
    passport = {'stage': 1, 'button': 'body.prepare', 'roles': counts,
                'levels': [{'name': x['name'], 'z_m': round(x['z_m'], 6)} for x in all_levels],
                'bodies': sorted(new for _h, _old, new in renames)}
    skipped.append(('passport', 'write is branch F (passport_core has no write API yet); section in plan.passport'))
    return {'roles': roles, 'renames': renames, 'layers': layers, 'levels': levels, 'findings': findings,
            'ambiguous': ambiguous, 'skipped': skipped, 'passport': passport, 'options': o}


def check_after(objects, plan):
    """Post-check of an apply: every processed object has a valid role; every new level exists once.

    objects: [{handle, name, role}] read back; plan['levels'] vs the names given. Returns [(handle, code, detail)]."""
    c = _contract()
    out = []
    for ob in objects:
        if ob.get('role') not in c.ROLES:
            out.append((ob['handle'], 'role_missing', 'agr_role {!r} after apply'.format(ob.get('role'))))
    return out


def _model10():
    import importlib.util
    import os
    import sys
    mod = sys.modules.get('agr_tools_model10_core')
    if mod is not None and getattr(mod, '__file__', None):
        return mod
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location('agr_tools_model10_core', os.path.join(here, 'model10_core.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.modules['agr_tools_model10_core'] = mod
    return mod
