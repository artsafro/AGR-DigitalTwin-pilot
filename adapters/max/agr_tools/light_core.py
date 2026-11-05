"""new-case: AGR Tools 0.9 (#979) light check (select mode: the UI selects the offenders, not the core) logic,
stdlib only. Owned by branch D (improve/issue-979-export-scene-light).

Pure logic for `light_check` (light.check); no pymxs. The glue (light_max.py) reads the scene into plain rows;
this module judges them and builds the edit_core report (preview only: the plan mode is `select`).

Rules (VPM-2.15-2/4/5.a/5.b/6/8/9.b), merged from three sources (no code copied, #853):
* GeoAGR Light Manager, Check Distances `GeoAGR.ms:56368-56414` and Check Quantity `GeoAGR.ms:56442-56458`
  (lab 0.9 L05, docs/experiments/light.check.md): strict «<», 3D distance between the light positions (a Target
  Spot is measured at the light, not at its target), Spot-Spot 1.5 and Omni-any 5.0;
* team `agr_max_check_37.ms` runLightCheck (SHA256 ead3866924bfa3bf9efe54619072e2ce810141bc8b7b914b5169f2ff600e59a2):
  one root helper, every light linked to it, Omni/Spot only, the name masks `<Addr>_Root` / `<Addr>_Omni_NNN` /
  `<Addr>_Spot_NNN` (and `_Ground_` variants) - without its 001-050 number cap (R6);
* team `Light_Metr.ms` (SHA256 6a51ed409bb4c42eeb6eccb75fe0cfaabf1566b9438bcc717dd346e9b75e6af5): select the
  offenders, never recolour them.

Fixed defects of the sources (each has a regression test in tests/max_tools/test_agr_tools_light.py):
* thresholds were system units (GeoAGR: a centimetre scene misses every 1-4.9 m violation) or parsed from a
  string (`units.decodeValue "1.5m"` = 1.0 on ru-RU, Light_Metr): here metres = units x metres_per_unit(SystemType,
  SystemScale), never a string;
* an invalid light type cancelled the verdict and its pairs (GeoAGR): it is reported as `light_type` and every
  Omni/Spot pair is still checked;
* Add Selected silently truncated the list to 250 (GeoAGR): every light is checked, the count is a finding;
* count and distances used different sets (GeoAGR): count = every light node, pairs = every Omni/Spot pair;
* number cap 050 (agr_max_check_37): no cap; a light target (Targetobject) is not a root helper;
* wirecolor changed outside undo (Light_Metr): the check changes nothing, the UI glue only selects;
* ANSI report with '?' for Cyrillic (agr_max_check_37): the report is JSON, written as UTF-8 by the runtime.
Hidden and frozen offenders are never selected: they go to `plan.ambiguous` with a flag (#979 general rules).
"""
import math
import re

TOOL = 'light.check'
LIMIT = 250                 # VPM-2.15-2: at most 250 lights in the light FBX
OMNI_MIN_M = 5.0            # VPM-2.15-5.a: Omni <-> any light >= 5 m
SPOT_MIN_M = 1.5            # VPM-2.15-5.b: Spot <-> Spot >= 1.5 m
EPS_M = 1e-6                # float noise of a metre position; strict «<» as in GeoAGR.ms:56384
PIVOT_TOL_M = 0.001         # VPM-2.15-9.b: root pivot = pivot of the lit object, 1 mm
KINDS = {'omnilight': 'omni', 'freespot': 'spot', 'targetspot': 'spot'}
METRES = {'millimeters': 0.001, 'centimeters': 0.01, 'meters': 1.0, 'kilometers': 1000.0,
          'inches': 0.0254, 'feet': 0.3048, 'miles': 1609.344}
OPTION_KEYS = {'reference', 'reference_point', 'ground'}
_NAME = {
    'root': re.compile(r'^[A-Za-z0-9_]+_Root$'),
    'omni': re.compile(r'^[A-Za-z0-9_]+_Omni_(\d{3})$'),
    'spot': re.compile(r'^[A-Za-z0-9_]+_Spot_(\d{3})$'),
}
_GROUND = {
    'root': re.compile(r'^[A-Za-z0-9_]+_Ground_Root$'),
    'omni': re.compile(r'^[A-Za-z0-9_]+_Ground_Omni_(\d{3})$'),
    'spot': re.compile(r'^[A-Za-z0-9_]+_Ground_Spot_(\d{3})$'),
}
CODES = ('light_count', 'light_type', 'light_omni_distance', 'light_spot_distance', 'light_no_root',
         'light_root_many', 'light_root_pivot', 'light_name')


def metres_per_unit(unit_type, scale):
    """Metres of one system unit from `units.SystemType` and `units.SystemScale` (never `units.decodeValue`)."""
    key = str(unit_type).lstrip('#').lower()
    if key not in METRES:
        raise ValueError('unmapped system unit type: ' + repr(unit_type))
    if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not math.isfinite(scale) or scale <= 0:
        raise ValueError('invalid system unit scale: ' + repr(scale))
    return METRES[key] * float(scale)


def light_options(options):
    """Validated options: reference (node name of the lit object) or reference_point [x, y, z] in metres;
    ground (bool: `_Ground_` name masks). Default reference: the world origin (GeoAGR btnCreateRoot puts the
    root Dummy at 0, GeoAGR.ms:56360)."""
    opts = dict(options or {})
    extra = set(opts) - OPTION_KEYS
    if extra:
        raise ValueError('unknown light.check options: ' + ', '.join(sorted(extra)))
    if opts.get('reference') is not None and opts.get('reference_point') is not None:
        raise ValueError('give reference or reference_point, not both')
    ref = opts.get('reference')
    if ref is not None and (not isinstance(ref, str) or not ref.strip()):
        raise ValueError('reference must be a node name')
    point = opts.get('reference_point')
    if point is not None:
        if (not isinstance(point, list) or len(point) != 3
                or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in point)):
            raise ValueError('reference_point must be [x, y, z] in metres')
        point = [float(v) for v in point]
    ground = opts.get('ground', False)
    if not isinstance(ground, bool):
        raise ValueError('ground must be true or false')
    return {'reference': ref, 'reference_point': point, 'ground': ground}


def kind_of(cls):
    """'omni' | 'spot' | None (any other light class: Photometric, Directional, Skylight, renderer lights)."""
    return KINDS.get(str(cls).lower())


def _dist(a, b):
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def _name_problem(name, kind, ground):
    masks = _GROUND if ground else _NAME
    m = masks[kind].match(name)
    if not m:
        other = [k for k in ('root', 'omni', 'spot') if k != kind and masks[k].match(name)]
        hint = ' (имя другого типа: {})'.format(other[0]) if other else ''
        want = {'root': '<Addr>_Root', 'omni': '<Addr>_Omni_NNN', 'spot': '<Addr>_Spot_NNN'}[kind]
        if ground:
            want = want.replace('<Addr>_', '<Addr>_Ground_')
        return 'имя не по маске {}{}'.format(want, hint)
    if kind != 'root' and int(m.group(1)) < 1:
        return 'номер 000: нумерация с 001'
    return None


def check(lights, helpers, unit_m, opts, reference_pivot=None):
    """Judge one light set.

    lights: [{handle, name, cls, pos (world, system units), parent (handle or None), hidden, frozen}] - every
    light node in scope (light targets are not lights). helpers: [{handle, name, cls, pos, parent, hidden,
    frozen}] - at least the parents of the lights. unit_m: metres per system unit. reference_pivot: world pivot
    (system units) of opts['reference'] when given. Returns (findings by handle, violating pairs, summary).
    """
    if not lights:
        raise ValueError('no lights in scope: an empty light set is an error, not a pass')
    if isinstance(unit_m, bool) or not isinstance(unit_m, (int, float)) or not math.isfinite(unit_m) or unit_m <= 0:
        raise ValueError('invalid metres per unit: ' + repr(unit_m))
    seen = set()
    for row in list(lights) + list(helpers):
        if row['handle'] in seen:
            raise ValueError('duplicate handle {}'.format(row['handle']))
        seen.add(row['handle'])
    found = {}

    def add(handle, code, detail):
        found.setdefault(handle, []).append((code, detail))

    ordered = sorted(lights, key=lambda r: r['handle'])
    # VPM-2.15-2: every light node counts (hidden ones and any type are in the FBX too).
    if len(ordered) > LIMIT:
        for row in ordered[LIMIT:]:
            add(row['handle'], 'light_count',
                'источников {} > {}: этот сверх лимита (по порядку создания)'.format(len(ordered), LIMIT))
    # VPM-2.15-4 / 2.15-6: Omni and Spot only.
    valid = []
    for row in ordered:
        kind = kind_of(row['cls'])
        if kind is None:
            add(row['handle'], 'light_type', 'тип {}: допустимы только Omni и Free/Target Spot'.format(row['cls']))
        else:
            valid.append((row, kind))
    # VPM-2.15-5.a / 5.b: every pair of valid lights, 3D, metres, strict «<».
    pairs = []
    checked = 0
    for i in range(len(valid)):
        a, ka = valid[i]
        for j in range(i + 1, len(valid)):
            b, kb = valid[j]
            checked += 1
            limit = SPOT_MIN_M if ka == kb == 'spot' else OMNI_MIN_M
            d_m = _dist(a['pos'], b['pos']) * unit_m
            if d_m < limit - EPS_M:
                code = 'light_spot_distance' if ka == kb == 'spot' else 'light_omni_distance'
                pairs.append({'a': a['name'], 'b': b['name'], 'kinds': [ka, kb], 'd_m': round(d_m, 6),
                              'min_m': limit, 'code': code})
                add(a['handle'], code, '{} {:.3f} м < {} м'.format(b['name'], d_m, limit))
                add(b['handle'], code, '{} {:.3f} м < {} м'.format(a['name'], d_m, limit))
    # VPM-2.15-8: every light linked directly to one root Dummy (a helper without parent).
    by_handle = {r['handle']: r for r in helpers}
    roots = {}
    for row in ordered:
        parent = row.get('parent')
        if parent is None:
            add(row['handle'], 'light_no_root', 'без родителя: привяжите к корневому Dummy')
            continue
        p = by_handle.get(parent)
        if p is None or str(p['cls']).lower() != 'dummy':
            add(row['handle'], 'light_no_root', 'родитель {} не Dummy'.format(p['name'] if p else parent))
            continue
        if p.get('parent') is not None:
            add(row['handle'], 'light_no_root', 'Dummy {} не корневой (у него есть родитель)'.format(p['name']))
            continue
        roots.setdefault(p['handle'], []).append(row['name'])
    if len(roots) > 1:
        names = sorted(by_handle[h]['name'] for h in roots)
        for h in roots:
            add(h, 'light_root_many', 'корней {}: {}; нужен один'.format(len(roots), ', '.join(names)))
    # VPM-2.15-9.b: root pivot = pivot of the lit object (option) or the world origin.
    ref_m = (opts.get('reference_point') or [0.0, 0.0, 0.0]) if reference_pivot is None \
        else [float(v) * unit_m for v in reference_pivot]
    for h in roots:
        root = by_handle[h]
        off = _dist([float(v) * unit_m for v in root['pos']], ref_m)
        if off > PIVOT_TOL_M:
            add(h, 'light_root_pivot', 'пивот корня в {:.3f} м от опорной точки {}'.format(
                off, opts.get('reference') or ref_m))
        problem = _name_problem(str(root['name']), 'root', opts.get('ground', False))
        if problem:
            add(h, 'light_name', problem)
    for row, kind in valid:
        problem = _name_problem(str(row['name']), kind, opts.get('ground', False))
        if problem:
            add(row['handle'], 'light_name', problem)
    summary = {'lights': len(ordered), 'limit': LIMIT, 'omni': sum(1 for _, k in valid if k == 'omni'),
               'spot': sum(1 for _, k in valid if k == 'spot'), 'invalid_type': len(ordered) - len(valid),
               'pairs_checked': checked, 'pairs_violating': len(pairs), 'roots': len(roots),
               'metres_per_unit': unit_m, 'reference_m': ref_m}
    return found, pairs, summary


def light_report(edit, lights, helpers, found, pairs, summary, opts, state_hash, notes=()):
    """Read report (preview only). objects = every visible, unfrozen light and root in scope, findings attached;
    hidden/frozen offenders go to plan.ambiguous with their flag, never to the selection."""
    rows = {r['handle']: r for r in list(helpers) + list(lights)}
    in_report = [r['handle'] for r in sorted(lights, key=lambda r: r['handle'])]
    parents = {r.get('parent') for r in lights}
    in_report += [r['handle'] for r in helpers if r['handle'] in parents and r.get('parent') is None
                  and str(r['cls']).lower() == 'dummy']  # the roots: part of the light file, selectable
    for h in found:
        if h not in in_report:
            in_report.append(h)
    objects, ambiguous = [], []
    for h in sorted(in_report):
        row = rows[h]
        codes = found.get(h, [])
        flags = [f for f in ('hidden', 'frozen') if row.get(f)]
        if flags:
            if codes:
                ambiguous.append({'item': row['name'], 'handle': h, 'flags': flags,
                                  'codes': sorted({c for c, _ in codes}),
                                  'reason': 'нарушитель {}: не выделяется'.format('/'.join(flags)),
                                  'detail': '; '.join(d for _, d in codes)})
            continue
        objects.append(edit.entry(h, row['name'], [edit.finding(c, (), d) for c, d in codes]))
    plan = {'read_only': True, 'select': 'offenders', 'units': 'm',
            'thresholds_m': {'omni_any': OMNI_MIN_M, 'spot_spot': SPOT_MIN_M, 'strict': '<'},
            'limit': LIMIT, 'summary': summary, 'pairs': pairs, 'options': opts, 'notes': list(notes)}
    return edit.report(TOOL, 'preview', objects, [], [], ambiguous, state_hash=state_hash, extra=plan)
