"""new-case: AGR Tools 1.0 (#1024) windows by opening markers logic, stdlib only; owned by branch J (improve/issue-1024-windows).

Pure logic for `win_place` (win.place); no pymxs. Mode `undo` (plan): preview -> apply in ONE undo record.

Contract K2 and lab L10 (docs/experiments/win.place.md, verdict take_fix) against Geo Window Placer
(GeoAGR.ms:56673-57352):
* openings come from the ONE recognition, openings_core.find_openings (borders of the wall mesh);
* every opening gets a marker OPEN_<nnn> (role opening, agr_opening JSON, agr_window_type when typed); an existing
  marker within `marker_match_m` of the opening centre is updated, never duplicated, and its agr_window_type
  (set by the user or an agent) wins over the size match;
* type by size (GeoAGR.ms:57117-57124 summed |dw|+|dh| in system units: in metres it took +150 mm, in cm it
  refused +5 mm) -> per axis, in metres: |dw| <= fit_tol_m and |dh| <= fit_tol_m; two types equally close ->
  ambiguous (the agent decides by the album); quarantined and duplicate types are never offered;
* alignment by the centre (the source aligned the bottom-left corner: centre error dw/2);
* the window face looks to the street by the face axis stored per type in the library, no auto-rotation (the
  source flipped -Y windows by 180 deg, GeoAGR.ms:57137-57143);
* the depth: the middle of the frame on the border plane (= the capsule edge, owner answer 06.11) plus
  `recess_m` into the building;
* fit check: the gap to the opening <= gap_max_m per side, the frame never wider than the opening (it would cut
  the reveal), the face not beyond the facade (frame half-depth vs the reveal depth);
* the source windows and the walls are never changed (the source called centerpivot, GeoAGR.ms:57090);
* not rectangular, corner and non-planar openings and openings without a type -> `ambiguous` + a draft record.
"""
import math

DEFAULTS = {
    'fit_tol_m': 0.02,
    'recess_m': 0.0,
    'gap_max_m': 0.02,
    'normal_tol_deg': 0.5,
    'centre_tol_m': 0.005,
    'marker_match_m': 0.05,
    'statuses': ['confirmed', 'unconfirmed'],
    'library': None,
    'drafts_dir': None,
    'openings': {},
}
FINDINGS = ('opening_ambiguous', 'no_type', 'fit_gap', 'intersects_body', 'protrudes', 'readback')
AGENT_REQUEST = 'разметь проёмы → тип по размерам и альбому'


def check_options(options=None):
    opts = {k: (list(v) if isinstance(v, list) else (dict(v) if isinstance(v, dict) else v))
            for k, v in DEFAULTS.items()}
    for k, v in (options or {}).items():
        if k not in DEFAULTS:
            raise ValueError('unknown win.place option: ' + repr(k))
        if k in ('library', 'drafts_dir'):
            if v is not None and (not isinstance(v, str) or not v.strip()):
                raise ValueError('win.place option {} must be a path string'.format(k))
        elif k == 'statuses':
            if not isinstance(v, list) or not v or not all(s in ('confirmed', 'unconfirmed') for s in v):
                raise ValueError('statuses must be a non-empty list of confirmed / unconfirmed')
        elif k == 'openings':
            if not isinstance(v, dict):
                raise ValueError('openings must be an object of openings_core options')
        else:
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError('win.place option {} must be a finite number: {!r}'.format(k, v))
            if k != 'recess_m' and v <= 0:
                raise ValueError('win.place option {} must be > 0'.format(k))
        opts[k] = v
    return opts


# ---- vectors -------------------------------------------------------------------------------------------------
def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _add(*vs):
    return [sum(c) for c in zip(*vs)]


def _mul(a, k):
    return [c * k for c in a]


def _unit(a):
    n = math.sqrt(_dot(a, a))
    return [c / n for c in a]


def angle_deg(a, b):
    c = _dot(_unit(a), _unit(b))
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


# ---- type match ----------------------------------------------------------------------------------------------
def fit(opening, entry):
    """Size fit of a type into an opening (metres): dw/dh = opening - type, per side gap = d/2."""
    dw = opening['w'] - entry['width_m']
    dh = opening['h'] - entry['height_m']
    return {'dw': round(dw, 6), 'dh': round(dh, 6), 'gap_x': round(dw / 2, 6), 'gap_y': round(dh / 2, 6),
            'err': round(max(abs(dw), abs(dh)), 6)}


def match(opening, candidates, tol):
    """The library type of an opening by size, per axis within tol. Returns {'type', 'status' ok|none|ambiguous,
    'why', 'fit', 'others'}."""
    hits = []
    for t in candidates:
        f = fit(opening, t)
        if abs(f['dw']) <= tol + 1e-9 and abs(f['dh']) <= tol + 1e-9:
            hits.append((f['err'], t['id'], f))
    if not hits:
        near = sorted(((fit(opening, t)['err'], t['id']) for t in candidates))[:1]
        return {'type': None, 'status': 'none', 'fit': None, 'others': [],
                'why': 'нет типа в пределах {} мм по осям (ближайший {})'.format(
                    round(tol * 1000), '{} на {} мм'.format(near[0][1], round(near[0][0] * 1000)) if near else '—')}
    hits.sort()
    best = hits[0]
    tied = [h[1] for h in hits[1:] if h[0] - best[0] <= 0.001]
    if tied:
        return {'type': None, 'status': 'ambiguous', 'fit': best[2], 'others': [best[1]] + tied,
                'why': 'несколько типов одного размера: {} — выбор по альбому'.format(', '.join([best[1]] + tied))}
    return {'type': best[1], 'status': 'ok', 'fit': best[2], 'others': [h[1] for h in hits[1:]], 'why': ''}


# ---- placement -----------------------------------------------------------------------------------------------
def placement_rows(frame, size_m, face_axis='-y', recess_m=0.0, centre=None):
    """Node transform (Max matrix3 rows: images of local X, Y, Z, then the translation, metres) that puts a type
    mesh into an opening frame: the type centre on the opening centre, the type face (face_axis) to frame z (the
    street), the frame middle on the border plane, `recess_m` into the building.

    size_m: [W, depth, H] of the type mesh (x 0..W, y 0..depth, z 0..H); centre: the type-local centre if the
    mesh is not in that box (default the box centre)."""
    o, X, Y, Z = frame['origin'], frame['x'], frame['y'], frame['z']
    if face_axis == '-y':      # local -Y -> street: X -> X, Y -> -Z, Z -> Y (a rotation, det +1)
        rows = [list(X), _mul(Z, -1.0), list(Y)]
    elif face_axis == '+y':    # local +Y -> street: rotated 180 deg about the vertical, X -> -X
        rows = [_mul(X, -1.0), list(Z), list(Y)]
    else:
        raise ValueError('face_axis must be -y or +y: ' + repr(face_axis))
    W, D, H = size_m
    c = centre or [W / 2.0, D / 2.0, H / 2.0]
    rc = _add(_mul(rows[0], c[0]), _mul(rows[1], c[1]), _mul(rows[2], c[2]))
    t = _add(o, _mul(rc, -1.0), _mul(Z, -recess_m))
    return [[round(v, 9) for v in r] for r in rows] + [[round(v, 9) for v in t]]


def apply_rows(rows, p):
    return _add(_mul(rows[0], p[0]), _mul(rows[1], p[1]), _mul(rows[2], p[2]), rows[3])


def face_normal_world(rows, face_axis='-y'):
    return _mul(rows[1], -1.0) if face_axis == '-y' else list(rows[1])


def check_fit(opening, entry, mesh_info, rows, face_axis, opts):
    """Findings [(code, detail)] of one placement: gap, frame wider than the opening, face beyond the facade,
    normal and centre (pure geometry of the planned transform; the Max glue re-checks the nodes after apply)."""
    out = []
    f = fit(opening, entry)
    for axis, g in (('ширине', f['gap_x']), ('высоте', f['gap_y'])):
        if g < -0.0005:
            out.append(('intersects_body', 'рама шире проёма по {} на {} мм: режет откос'.format(axis, round(-2 * g * 1000, 1))))
        elif g > opts['gap_max_m'] + 1e-9:
            out.append(('fit_gap', 'зазор по {} {} мм на сторону > {} мм'.format(axis, round(g * 1000, 1),
                                                                                round(opts['gap_max_m'] * 1000))))
    depth = opening.get('depth') or 0.0
    out_face = mesh_info['frame_mid_m'] - opts['recess_m']
    if depth > 0 and out_face > depth + 0.0005:
        out.append(('protrudes', 'лицо рамы на {} мм перед фасадом (откос {} мм)'.format(
            round((out_face - depth) * 1000, 1), round(depth * 1000, 1))))
    n = face_normal_world(rows, face_axis)
    a = angle_deg(n, opening['frame']['z'])
    if a > opts['normal_tol_deg']:
        out.append(('readback', 'нормаль окна {:.3f}° от нормали проёма'.format(a)))
    W, D, H = mesh_info['size_m']
    c = apply_rows(rows, [W / 2.0, D / 2.0, H / 2.0])
    want = _add(opening['frame']['origin'], _mul(opening['frame']['z'], -opts['recess_m']))
    err = math.sqrt(sum((p - q) ** 2 for p, q in zip(c, want)))
    if err > opts['centre_tol_m']:
        out.append(('readback', 'центр окна в {:.1f} мм от центра проёма'.format(err * 1000)))
    return out


def frame_from_rows(rows):
    """Opening frame of a marker node transform (rows in metres): origin, x, y (up), z (street)."""
    return {'origin': list(rows[3]), 'x': _unit(rows[0]), 'y': _unit(rows[1]), 'z': _unit(rows[2])}


def marker_rows(frame):
    return [list(frame['x']), list(frame['y']), list(frame['z']), list(frame['origin'])]


# ---- the plan ------------------------------------------------------------------------------------------------
def plan(openings, markers, types, offer, mesh_info, opts):
    """Actions of win.place for the recognised openings and the existing markers.

    openings: openings_core.find_openings items (each with 'wall' and 'wall_handle'); markers: [{'name', 'handle',
    'rows' (metres), 'type', 'opening' (agr_opening dict or None)}]; types: library records by id; offer: ids that
    may be offered; mesh_info: {type id: build_type info (size_m, frame_mid_m, face_axis)} or a callable.
    Returns {'actions': [...], 'free_markers': [...]} — one action per opening and per unmatched typed marker:
    {'source': 'opening'|'marker', 'opening': {...}, 'marker': name, 'marker_handle': int|None, 'type': id|None,
    'status': 'place'|'ambiguous', 'why': [...], 'rows': [...]|None, 'face_axis', 'findings': [(code, detail)]}."""
    used = set()
    taken = {int(m['name'][5:]) for m in markers if str(m['name']).startswith('OPEN_') and m['name'][5:].isdigit()}
    next_n = [max(taken) + 1 if taken else 1]

    def new_name():
        while next_n[0] in taken:
            next_n[0] += 1
        n = next_n[0]
        taken.add(n)
        if n > 999:
            raise ValueError('more than 999 opening markers')
        return 'OPEN_{:03d}'.format(n)

    def info(tid):
        return mesh_info(tid) if callable(mesh_info) else mesh_info[tid]

    actions = []
    for o in openings:
        act = {'source': 'opening', 'opening': o, 'marker': None, 'marker_handle': None, 'marker_new': True,
               'type': None, 'status': 'ambiguous', 'why': list(o.get('why') or []), 'rows': None,
               'face_axis': None, 'findings': []}
        if o.get('frame'):
            best = None
            for mk in markers:
                if mk['handle'] in used:
                    continue
                d = math.sqrt(sum((a - b) ** 2 for a, b in zip(mk['rows'][3], o['frame']['origin'])))
                if d <= opts['marker_match_m'] and (best is None or d < best[0]):
                    best = (d, mk)
            if best:
                mk = best[1]
                used.add(mk['handle'])
                act.update(marker=mk['name'], marker_handle=mk['handle'], marker_new=False)
                act['marker_type'] = mk.get('type')
        if act['marker'] is None:
            act['marker'] = new_name()
        if o.get('status') != 'ok' or not o.get('frame'):
            actions.append(act)
            continue
        wanted = act.get('marker_type')
        if wanted:
            if wanted not in types:
                act['why'].append('метка: тип {} нет в библиотеке'.format(wanted))
            elif wanted not in offer:
                act['why'].append('метка: тип {} в карантине или дубль — не предлагается'.format(wanted))
            else:
                f = fit(o, types[wanted])
                if abs(f['dw']) > opts['fit_tol_m'] + 1e-9 or abs(f['dh']) > opts['fit_tol_m'] + 1e-9:
                    act['why'].append('метка: тип {} не входит в проём (dw {} мм, dh {} мм)'.format(
                        wanted, round(f['dw'] * 1000, 1), round(f['dh'] * 1000, 1)))
                else:
                    act['type'] = wanted
        else:
            m = match(o, [types[i] for i in offer if i in types], opts['fit_tol_m'])
            if m['status'] == 'ok':
                act['type'] = m['type']
            else:
                act['why'].append(m['why'])
        if act['type']:
            mi = info(act['type'])
            act['face_axis'] = mi['face_axis']
            act['rows'] = placement_rows(o['frame'], mi['size_m'], mi['face_axis'], opts['recess_m'])
            act['findings'] = check_fit(o, types[act['type']], mi, act['rows'], mi['face_axis'], opts)
            act['status'] = 'place'
        actions.append(act)
    free = [mk for mk in markers if mk['handle'] not in used]
    for mk in free:
        tid = mk.get('type')
        op = mk.get('opening')
        if not tid or not op:
            continue
        fr = frame_from_rows(mk['rows'])
        o = dict(op, frame=fr, id=None, kind='marker', status='ok', why=[], wall=op.get('wall'))
        act = {'source': 'marker', 'opening': o, 'marker': mk['name'], 'marker_handle': mk['handle'],
               'marker_new': False, 'type': None, 'status': 'ambiguous', 'why': [], 'rows': None,
               'face_axis': None, 'findings': []}
        if tid not in types or tid not in offer:
            act['why'].append('метка: тип {} не предлагается (нет в библиотеке, карантин или дубль)'.format(tid))
        else:
            mi = info(tid)
            act.update(type=tid, status='place', face_axis=mi['face_axis'])
            act['rows'] = placement_rows(fr, mi['size_m'], mi['face_axis'], opts['recess_m'])
            act['findings'] = check_fit(o, types[tid], mi, act['rows'], mi['face_axis'], opts)
        actions.append(act)
    return {'actions': actions, 'free_markers': [m['name'] for m in free]}


def summary(act):
    o = act['opening']
    size = '{}×{} мм'.format(round(o['w'] * 1000), round(o['h'] * 1000)) if o.get('w') and o.get('h') else 'без кадра'
    if act['status'] == 'place':
        return '{}: {} {} → {}{}'.format(act['marker'], o.get('wall'), size, act['type'],
                                        '' if not act['findings'] else ' (' + '; '.join(d for _, d in act['findings']) + ')')
    return '{}: {} {} {} — {}'.format(act['marker'], o.get('wall'), o.get('kind'), size, '; '.join(act['why']) or '—')
