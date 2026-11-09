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


# =====================================================================================================================
# light.export (#1024, station 1.0.29, branch S improve/issue-1024-deliver): FBX of the lights `<stem>_Light.fbx`
# =====================================================================================================================
# Source (lab 1.0 L13, docs/experiments/light.export.md, measured in Max 2024; no code copied, #853): GeoAGR Export
# HighPoly LMB `GeoAGR.ms:66904-67035` picks the lights by the substring `Spot` / `Root` of the name (`:66915`)
# and writes the light FBX `:66951-66977`; ReSave Lights FBXs `:65127` (runtime-finding X01) rewrites it as 7.7.
# Fixed defects (regression tests in tests/max_tools/test_agr_tools_deliver.py, RED on a model of the source):
# 1. Omni and Photometric lost (name substring): every node with superClassOf == light under the root, by
#    hierarchy, never by name; 2. Target Spot lost its target/direction: its world rotation is exported baked
#    and checked on the readback; 3. no UCX -> no light file either: the light export does not depend on UCX;
# 4. existing files overwritten without a question: a new file only (refuse or the next `_vNNN`, option);
# 5. ReSave wrote FBX 7.7 and left temp files: FBX 7.4 (FBX201400) written once through a `.partial` file;
# 6. `_Light` not in the VPM archive: package_core.classify_folder puts `SM_<a>_Light.fbx` into its VPM set
#    (export.zip 0.9) - covered by a regression test here.
# Root rule of qa.package 0.9 (tools/qa/validate_package.py light_findings): exactly one `<stem>_Root` at the top,
# every light its child, stem = `SM_<Address>` of the VPM set; the model FBX `<stem>.fbx` carries no lights.
import os as _os
import struct as _struct

EXPORT_TOOL = 'light.export'
EXPORT_OPTION_KEYS = {'folder', 'stem', 'on_exists', 'root'}
ON_EXISTS = ('version', 'refuse')
LIGHT_FBX_PARAMS = (('Animation', False), ('Cameras', False), ('Lights', True), ('ASCII', False),
                    ('FileVersion', 'FBX201400'), ('EmbedTextures', False), ('ConvertUnit', 'm'), ('UpAxis', 'Z'))
FBX_VERSION = 7400
STEM = re.compile(r'^SM_[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*$')
ROOT_OF_STEM = re.compile(r'^(?P<stem>SM_[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*)_Root$')
ROOT_GEOAGR = re.compile(r'^Root_(?P<addr>[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*)$')   # GeoAGR btnCreateRoot style
DIRECTION_TOL_DEG = 0.05
EXPORT_CODES = ('light_outside_root', 'light_root_many', 'light_root_name', 'light_type', 'light_fbx_exists',
                'light_readback_missing', 'light_readback_kind', 'light_readback_parent', 'light_readback_count',
                'light_readback_extra', 'light_direction', 'light_fbx_version')
FBX_KIND = {'omni': 'Omni', 'spot': 'Spot'}
NO_ROOT = '(нет)'


def export_options(options):
    """Validated light.export options: folder (target folder, default the scene folder - the glue fills it),
    stem (`SM_<Address>`, default from the root `<stem>_Root`), root (node name of the root Dummy, default the
    one top Dummy above the lights), on_exists ('version' = next free `_vNNN`, 'refuse')."""
    opts = dict(options or {})
    extra = set(opts) - EXPORT_OPTION_KEYS
    if extra:
        raise ValueError('unknown light.export options: ' + ', '.join(sorted(extra)))
    on = opts.get('on_exists', 'version')
    if on not in ON_EXISTS:
        raise ValueError('on_exists must be version or refuse')
    stem = opts.get('stem')
    if stem is not None and (not isinstance(stem, str) or not STEM.match(stem)):
        raise ValueError('stem must be SM_<Address> (A-Z a-z 0-9 _)')
    for key in ('folder', 'root'):
        v = opts.get(key)
        if v is not None and (not isinstance(v, str) or not v.strip()):
            raise ValueError(key + ' must be a non-empty string')
    return {'folder': opts.get('folder'), 'stem': stem, 'root': opts.get('root'), 'on_exists': on}


def _top(row, by_handle):
    seen = set()
    while row.get('parent') is not None and row['parent'] in by_handle and row['handle'] not in seen:
        seen.add(row['handle'])
        row = by_handle[row['parent']]
    return row


def _rot_of(row):
    if row.get('rot') is not None:
        return [[round(float(v), 9) for v in r] for r in row['rot']]
    return [[round(v, 9) for v in r] for r in euler_matrix(row.get('euler') or (0.0, 0.0, 0.0))]


def _new_version(path, exists):
    folder, name = _os.path.split(path)
    stem, ext = _os.path.splitext(name)
    for i in range(2, 10000):
        cand = _os.path.join(folder, '{}_v{:03d}{}'.format(stem, i, ext))
        if not exists(cand):
            return cand
    raise FileExistsError('no free version for ' + path)


def export_plan(lights, helpers, opts, exists=_os.path.exists):
    """Plan of one light FBX.

    lights: rows {handle, name, cls, parent, hidden, frozen, rot (3x3 world rotation, column vectors) or euler
    [deg XYZ], target (handle of a Target Spot's target or None)} of EVERY light node of the
    scene (light targets are not lights); helpers: rows of their ancestors. Returns {root, stem, target, wanted,
    export (handles: root + its lights), lights, findings {handle: [(code, detail)]}, blockers [...]}."""
    if not lights:
        raise ValueError('no lights in the scene: an empty light set is an error, not a pass')
    if not opts.get('folder'):
        raise ValueError('light.export needs a folder (options.folder or a saved scene)')
    by_handle = {r['handle']: r for r in list(helpers) + list(lights)}
    found, blockers = {}, []

    def add(h, code, detail):
        found.setdefault(h, []).append((code, detail))

    tops = {}
    for row in sorted(lights, key=lambda r: r['handle']):
        top = _top(row, by_handle)
        if top is not row and str(top.get('cls', '')).lower() == 'dummy':
            tops.setdefault(top['handle'], []).append(row)
    root = None
    if opts.get('root'):
        cand = [h for h in tops if by_handle[h]['name'] == opts['root']]
        if len(cand) != 1:
            blockers.append('корень {!r} не найден над источниками света'.format(opts['root']))
        else:
            root = by_handle[cand[0]]
    elif len(tops) == 1:
        root = by_handle[next(iter(tops))]
    elif not tops:
        blockers.append('нет корневого Dummy над источниками: нужен один <stem>_Root (qa.package 0.9)')
    else:
        names = sorted(by_handle[h]['name'] for h in tops)
        for h in tops:
            add(h, 'light_root_many', 'корней {}: {}; укажите options.root'.format(len(tops), ', '.join(names)))
        blockers.append('несколько корней: ' + ', '.join(names))
    stem = opts.get('stem')
    if root is not None:
        m = ROOT_OF_STEM.match(root['name'])
        g = ROOT_GEOAGR.match(root['name'])
        if stem is None:
            stem = m.group('stem') if m else ('SM_' + g.group('addr') if g else None)
        if stem is None:
            blockers.append('корень {!r} не по маске SM_<Address>_Root: укажите options.stem'.format(root['name']))
        elif root['name'] != stem + '_Root':
            add(root['handle'], 'light_root_name', 'корень {} != {}_Root (qa.package 0.9)'.format(root['name'], stem))
    mine = tops.get(root['handle'], []) if root is not None else []
    mine_h = {r['handle'] for r in mine}
    root_name = root['name'] if root is not None else NO_ROOT
    for row in sorted(lights, key=lambda r: r['handle']):
        if row['handle'] not in mine_h:
            add(row['handle'], 'light_outside_root', 'не под корнем {}: в FBX света не попадёт'.format(root_name))
        elif kind_of(row['cls']) is None:
            add(row['handle'], 'light_type', 'тип {} экспортируется, но ВПМ допускает только Omni и Spot '
                                             '(VPM-2.15-4)'.format(row['cls']))
    target, wanted = None, None
    if stem is not None:
        wanted = _os.path.join(opts['folder'], stem + '_Light.fbx')
        if not exists(wanted):
            target = wanted
        elif opts['on_exists'] == 'refuse':
            blockers.append('файл уже есть, перезапись запрещена: ' + wanted)
            add(root['handle'], 'light_fbx_exists', wanted + ' уже есть: отказ (on_exists=refuse)')
        else:
            target = _new_version(wanted, exists)
    export = ([root['handle']] if root is not None else []) + sorted(mine_h)
    rows = [{'handle': r['handle'], 'name': r['name'], 'cls': str(r['cls']), 'kind': kind_of(r['cls']),
             'rot': _rot_of(r), 'target': r.get('target') is not None}
            for r in sorted(mine, key=lambda r: r['handle'])]
    return {'root': None if root is None else {'handle': root['handle'], 'name': root['name']}, 'stem': stem,
            'target': target, 'wanted': wanted, 'export': export, 'lights': rows, 'findings': found,
            'blockers': blockers}


# ---- binary FBX readback (stdlib; ported from the pilot's own src/twinqa/fbx_header.py and
# ---- tools/qa/validate_package.py light_scene, 06.11.2026) -----------------------------------------------
_MAGIC = b'Kaydara FBX Binary  \x00\x1a\x00'
FBX_LIGHT_TYPES = {0: 'Omni', 1: 'Directional', 2: 'Spot', 3: 'Area', 4: 'Volume'}
_FIXED = {'Y': ('<h', 2), 'C': ('<B', 1), 'I': ('<i', 4), 'F': ('<f', 4), 'D': ('<d', 8), 'L': ('<q', 8)}


def _props(data, start, end, count):
    off, out = start, []
    for _ in range(count):
        code = chr(data[off])
        off += 1
        if code in _FIXED:
            fmt, size = _FIXED[code]
            out.append(_struct.unpack_from(fmt, data, off)[0])
            off += size
        elif code in ('S', 'R'):
            n = _struct.unpack_from('<I', data, off)[0]
            out.append(data[off + 4:off + 4 + n].decode('latin-1'))
            off += 4 + n
        elif code in ('f', 'd', 'l', 'i', 'b'):
            size = _struct.unpack_from('<III', data, off)[2]
            out.append(None)
            off += 12 + size
        else:
            raise ValueError('unreadable FBX property at {}'.format(off - 1))
    if off != end:
        raise ValueError('unreadable FBX node at {}'.format(start))
    return out


def _nodes(data, start, end, version):
    off = start
    hlen = 25 if version >= 7500 else 13
    while off < end:
        if off + hlen > end:
            raise ValueError('truncated FBX node at {}'.format(off))
        if data[off:off + hlen] == bytes(hlen):
            return
        if version >= 7500:
            stop, count, plen = _struct.unpack_from('<QQQ', data, off)
        else:
            stop, count, plen = _struct.unpack_from('<III', data, off)
        nlen, at = data[off + hlen - 1], off + hlen
        if stop <= off or stop > end:
            raise ValueError('truncated FBX node at {}'.format(off))
        props_at = at + nlen
        yield {'name': data[at:props_at].decode('latin-1'), 'count': count, 'at': props_at,
               'pend': props_at + plen, 'end': stop}
        off = stop


def _p70(data, node, version):
    out = {}
    for child in _nodes(data, node['pend'], node['end'], version):
        if child['name'] != 'Properties70':
            continue
        for p in _nodes(data, child['pend'], child['end'], version):
            if p['name'] == 'P':
                vals = _props(data, p['at'], p['pend'], p['count'])
                if vals and isinstance(vals[0], str):
                    out[vals[0]] = vals[4:]
    return out


def _vec(p, key, default):
    v = p.get(key)
    return [float(x) for x in v[:3]] if v and len(v) >= 3 else list(default)


def fbx_lights(data):
    """Readback of a binary FBX: {'version', 'models': {id: {name, kind, parent, light, t, r, pre, post}}}.
    ValueError when the file is not a readable binary FBX."""
    if len(data) < 27 or data[:23] != _MAGIC:
        raise ValueError('not a binary FBX')
    version = _struct.unpack('<I', data[23:27])[0]
    try:
        top = {n['name']: n for n in _nodes(data, 27, len(data), version)}
        models, attrs, links = {}, {}, []
        for node in _nodes(data, top['Objects']['pend'], top['Objects']['end'], version) if 'Objects' in top else []:
            vals = _props(data, node['at'], node['pend'], node['count'])
            if node['name'] == 'Model' and len(vals) >= 3:
                p = _p70(data, node, version)
                models[vals[0]] = {'name': str(vals[1]).split('\x00', 1)[0], 'kind': vals[2], 'parent': 0,
                                   'light': None, 't': _vec(p, 'Lcl Translation', (0, 0, 0)),
                                   'r': _vec(p, 'Lcl Rotation', (0, 0, 0)), 'pre': _vec(p, 'PreRotation', (0, 0, 0)),
                                   'post': _vec(p, 'PostRotation', (0, 0, 0))}
            elif node['name'] == 'NodeAttribute' and len(vals) >= 3 and vals[2] == 'Light':
                lt = _p70(data, node, version).get('LightType', [0])
                attrs[vals[0]] = FBX_LIGHT_TYPES.get(int(lt[0]) if lt else 0, 'Other')
        conns = _nodes(data, top['Connections']['pend'], top['Connections']['end'], version) \
            if 'Connections' in top else []
        for node in conns:
            vals = _props(data, node['at'], node['pend'], node['count'])
            if len(vals) >= 3 and vals[0] == 'OO':
                links.append((vals[1], vals[2]))
    except (KeyError, IndexError, TypeError, _struct.error) as exc:
        raise ValueError('unreadable FBX scene: {}'.format(exc)) from exc
    for child, parent in links:
        if child in attrs and parent in models:
            models[parent]['light'] = attrs[child]
        elif child in models:
            models[child]['parent'] = parent
    return {'version': version, 'models': models}


def _matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def euler_matrix(e):
    """3x3 of euler XYZ degrees (FBX eEulerXYZ and Max `eulerAngles` order: R = Rz * Ry * Rx, column vectors)."""
    x, y, z = (math.radians(float(v)) for v in e)
    cx, sx, cy, sy, cz, sz = math.cos(x), math.sin(x), math.cos(y), math.sin(y), math.cos(z), math.sin(z)
    rx = [[1, 0, 0], [0, cx, -sx], [0, sx, cx]]
    ry = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]
    rz = [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]
    return _matmul(rz, _matmul(ry, rx))


def rotation_angle(ra, rb):
    """Angle in degrees between two rotation matrices."""
    tr = sum(ra[i][k] * rb[i][k] for i in range(3) for k in range(3))
    return math.degrees(math.acos(max(-1.0, min(1.0, (tr - 1.0) / 2.0))))


def fbx_world_rotation(m):
    """Rotation of an FBX model node: PreRotation * LclRotation. The PostRotation is NOT the node: Max writes
    (-90, 0, 0) on every light (measured, job 20261106-044737-6d28f847: the light axis -Z of Max -> -Y of FBX), so a
    node rotation equal to the scene means the direction survived (Target Spot baked: Lcl 48.19/0/-26.565 = aim)."""
    return _matmul(euler_matrix(m['pre']), euler_matrix(m['r']))


def readback_findings(plan, back):
    """Readback of the written light FBX against the plan: one root at the top, every planned light present with
    its type (Omni/Spot), parented to the root, its rotation equal to the scene (Target Spot direction baked),
    no other top-level node, FBX 7.4. Returns ({handle: [(code, detail)]}, summary)."""
    found = {}

    def add(h, code, detail):
        found.setdefault(h, []).append((code, detail))

    models = back['models']
    root_h = plan['root']['handle']
    by_name = {}
    for k, m in models.items():
        by_name.setdefault(m['name'], []).append(k)
    if back['version'] != FBX_VERSION:
        add(root_h, 'light_fbx_version', 'FBX {} != {}'.format(back['version'], FBX_VERSION))
    tops = [k for k, m in models.items() if m['parent'] == 0]
    root_ids = by_name.get(plan['root']['name'], [])
    rid = root_ids[0] if len(root_ids) == 1 and root_ids[0] in tops else None
    if rid is None:
        add(root_h, 'light_readback_missing', 'корень {} не найден наверху FBX'.format(plan['root']['name']))
    extra = sorted(models[k]['name'] for k in tops if k != rid)
    if extra:
        add(root_h, 'light_readback_extra', 'лишние узлы наверху FBX: {}'.format(', '.join(extra[:10])))
    lights = [m for m in models.values() if m['light'] is not None]
    if len(lights) != len(plan['lights']):
        add(root_h, 'light_readback_count', 'в FBX {} источников, в сцене {}'.format(len(lights), len(plan['lights'])))
    angles = {}
    for row in plan['lights']:
        ids = [k for k in by_name.get(row['name'], []) if models[k]['light'] is not None]
        if len(ids) != 1:
            add(row['handle'], 'light_readback_missing', '{} нет в FBX как источника'.format(row['name']))
            continue
        m = models[ids[0]]
        want = FBX_KIND.get(row['kind'])
        if want is not None and m['light'] != want:
            add(row['handle'], 'light_readback_kind', '{}: в FBX {} вместо {}'.format(row['name'], m['light'], want))
        if rid is not None and m['parent'] != rid:
            add(row['handle'], 'light_readback_parent', '{}: в FBX не ребёнок корня'.format(row['name']))
        d = rotation_angle(fbx_world_rotation(m), row['rot'])
        angles[row['name']] = round(d, 4)
        if d > DIRECTION_TOL_DEG:
            add(row['handle'], 'light_direction', '{}: поворот в FBX отличается от сцены на {:.2f}°'.format(
                row['name'], d))
    summary = {'version': back['version'], 'models': len(models), 'lights': len(lights),
               'kinds': sorted({str(m['light']) for m in lights}), 'tops': len(tops), 'angles_deg': angles,
               'raw': {m['name']: {'light': m['light'], 'r': m['r'], 'pre': m['pre'], 'post': m['post']}
                       for m in models.values()}}
    return found, summary


def export_report(edit, mode, lights, plan, opts, state_hash=None, findings=None, done=(), extra=None):
    """Edit report of light.export. objects = every light of the scene and the root; findings from the plan
    (preview) or the readback (apply). Blockers are `plan.ambiguous`: the apply refuses while there are any."""
    findings = plan['findings'] if findings is None else findings
    names = {r['handle']: r['name'] for r in lights}
    if plan['root']:
        names[plan['root']['handle']] = plan['root']['name']
    for h in findings:
        names.setdefault(h, str(h))
    objects = [edit.entry(h, names[h], [edit.finding(c, (), d) for c, d in findings.get(h, [])])
               for h in sorted(names)]
    ambiguous = [{'item': 'light.export', 'reason': b} for b in plan['blockers']]
    info = {'units': 'm', 'options': opts, 'root': plan['root'], 'stem': plan['stem'], 'target': plan['target'],
            'wanted': plan['wanted'], 'export': plan['export'], 'lights': plan['lights'],
            'fbx_params': [[k, v] for k, v in LIGHT_FBX_PARAMS]}
    info.update(extra or {})
    return edit.report(EXPORT_TOOL, mode, objects, list(done), [], ambiguous, state_hash=state_hash, extra=info)
