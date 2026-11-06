"""new-case: AGR Tools 1.0 (#1024) source intake: units, axes, origin logic, stdlib only. Stub of branch 0; owned by branch F (improve/issue-1024-passport).

Pure logic for `source_intake` (source.intake); no pymxs. Use edit_core.py for reports, preview hashes and new paths, contract_core.py for
roles, markers and ObjRef (the core never takes a host object).

source.intake (plan mode `copy`, #1024 «1.0.2»): normalise the source to metres, Z up and a near origin on an
export copy, record the common zero in the passport (K1 `normalization`), the level A/B/C and the class
(scene10_core, rule D066). Acceptance: an FBX in cm, Y up, at 2 345 678 m -> a copy in metres, Z up, the zero
recorded, the class in the passport.

Inputs are HostAdapter meshes (world space, metres by units.SystemScale of the scene). A source whose numbers are
in another unit than the scene (an FBX in cm read 1:1 into a metre scene) is `units_scale`: `source_units`
(option, default `auto`) gives the factor. `auto` takes the first unit of AUTO_ORDER (the scene's own unit
first) whose largest extent lands in PLAUSIBLE_M; none or a non-building size is ambiguous, never a guess.
The up axis is an option (`source_up_axis`, default Z): geometry alone does not tell a lying tower from a slab.
The split by materials is `model.attach_by_material` (branch G); intake only lists the material IDs.
"""
import math

UNITS_M = {'mm': 0.001, 'cm': 0.01, 'm': 1.0, 'km': 1000.0, 'in': 0.0254, 'ft': 0.3048}
AUTO_ORDER = ('cm', 'mm')            # after the scene's own unit
PLAUSIBLE_M = (2.0, 250.0)           # largest extent of a building source, metres (parameter)
AXES = ('X', 'Y', 'Z')
DEFAULTS = {'source_units': 'auto', 'source_up_axis': 'Z', 'far_m': 1000.0, 'origin_round_m': 1.0,
            'plausible_m': list(PLAUSIBLE_M), 'source_path': None}
# rotation (row-vector convention of 3ds Max: p' = p * R) that brings the source up axis to +Z
_ROT = {'Z': ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
        'Y': ((1, 0, 0), (0, 0, 1), (0, -1, 0)),     # +90 deg about X: (x, y, z) -> (x, -z, y)
        'X': ((0, 0, 1), (0, 1, 0), (-1, 0, 0))}     # -90 deg about Y: (x, y, z) -> (-z, y, x)


class IntakeError(ValueError):
    """Unusable input or options; nothing is changed."""


def options(raw):
    out = dict(DEFAULTS)
    for k, v in (raw or {}).items():
        if k not in DEFAULTS:
            raise IntakeError('source.intake: unknown option {!r}; known {}'.format(k, sorted(DEFAULTS)))
        out[k] = v
    if out['source_units'] != 'auto' and out['source_units'] not in UNITS_M:
        raise IntakeError('source.intake: source_units must be auto or one of {}'.format(sorted(UNITS_M)))
    if out['source_up_axis'] not in AXES:
        raise IntakeError('source.intake: source_up_axis must be X, Y or Z')
    for k in ('far_m', 'origin_round_m'):
        v = out[k]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            raise IntakeError('source.intake: {} must be metres > 0'.format(k))
    lo_hi = out['plausible_m']
    if not isinstance(lo_hi, list) or len(lo_hi) != 2 or not all(
            isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in lo_hi) \
            or not 0 < lo_hi[0] < lo_hi[1]:
        raise IntakeError('source.intake: plausible_m must be [lo, hi] metres, 0 < lo < hi')
    if out['source_path'] is not None and (not isinstance(out['source_path'], str) or not out['source_path']):
        raise IntakeError('source.intake: source_path must be a path string')
    return out


def unit_of(m_per_unit):
    """Name of the scene unit (metres per system unit), or None for a custom SystemScale."""
    for name, m in UNITS_M.items():
        if abs(m - m_per_unit) <= 1e-12 * max(1.0, m):
            return name
    return None


def bbox(points):
    if not points:
        raise IntakeError('empty mesh: nothing to take in')
    lo = [min(p[i] for p in points) for i in range(3)]
    hi = [max(p[i] for p in points) for i in range(3)]
    if not all(math.isfinite(c) for c in lo + hi):
        raise IntakeError('non-finite vertex coordinate')
    return lo, hi


def detect_units(extent_m, m_per_unit, opts):
    """(source unit, factor, why). factor turns the scene's metres into true metres: the numbers were in the
    source unit, the scene read them in its own unit. Raises IntakeError when `auto` cannot decide."""
    scene_unit = unit_of(m_per_unit)
    if opts['source_units'] != 'auto':
        u = opts['source_units']
        return u, UNITS_M[u] / m_per_unit, 'option source_units'
    lo, hi = opts['plausible_m']
    order = ([scene_unit] if scene_unit else []) + [u for u in AUTO_ORDER if u != scene_unit]
    tried = []
    for u in order:
        f = UNITS_M[u] / m_per_unit
        size = extent_m * f
        tried.append('{} -> {:.3f} m'.format(u, size))
        if lo <= size <= hi:
            return u, f, 'auto: largest extent {:.3f} m in {}..{} m'.format(size, lo, hi)
    raise IntakeError('source units are ambiguous: no unit gives a building size {}..{} m ({}); set '
                      'options.source_units'.format(lo, hi, '; '.join(tried)))


def rotate(p, axis):
    r = _ROT[axis]
    return [p[0] * r[0][j] + p[1] * r[1][j] + p[2] * r[2][j] for j in range(3)]


def _round_down(v, step):
    return math.floor(v / step) * step


def normalization(meshes, m_per_unit, opts):
    """Plan of the intake for [{'name', 'verts'}] (metres in the scene's reading).

    Returns {'source_units', 'factor', 'units_why', 'source_up_axis', 'origin_m', 'size_m', 'matrix_units',
    'nodes': {name: {'far': bool, 'distance_m', 'size_m'}}}. `matrix_units` is the 4x3 row-vector matrix in
    SYSTEM UNITS that the glue multiplies onto each copy's world transform (p' = p * M): scale by factor, turn the
    up axis to Z, move the common zero (rounded down to origin_round_m) to 0."""
    if not meshes:
        raise IntakeError('empty selection: select the source objects')
    every = [p for m in meshes for p in m['verts']]
    lo, hi = bbox(every)
    extent = max(h - l for h, l in zip(hi, lo))
    if extent <= 0:
        raise IntakeError('the source has no extent')
    unit, f, why = detect_units(extent, m_per_unit, opts)
    turned = [rotate([c * f for c in p], opts['source_up_axis']) for p in every]
    tlo, thi = bbox(turned)
    step = opts['origin_round_m']
    origin = [_round_down(c, step) for c in tlo]
    origin = [0.0 if c == 0 else float(c) for c in origin]
    size = [round(h - l, 9) for h, l in zip(thi, tlo)]
    r = _ROT[opts['source_up_axis']]
    k = f  # p_units * f -> true units; rotation and origin in system units
    rows = [[k * r[i][j] for j in range(3)] for i in range(3)]
    rows.append([-c / m_per_unit for c in origin])
    nodes = {}
    for m in meshes:
        mlo, mhi = bbox(m['verts'])
        tl = bbox([rotate([c * f for c in p], opts['source_up_axis']) for p in m['verts']])
        dist = max(abs(c) for c in tl[0] + tl[1])
        nodes[m['name']] = {'far': dist > opts['far_m'], 'distance_m': dist,
                            'size_m': [round(h - l, 9) for h, l in zip(tl[1], tl[0])]}
    return {'source_units': unit, 'factor': f, 'units_why': why, 'scene_units': unit_of(m_per_unit) or 'custom',
            'source_up_axis': opts['source_up_axis'], 'origin_m': origin, 'size_m': size,
            'matrix_units': rows, 'nodes': nodes}


def apply_matrix(p, rows):
    """p * M for the 4x3 row-vector matrix (tests and the readback)."""
    return [p[0] * rows[0][j] + p[1] * rows[1][j] + p[2] * rows[2][j] + rows[3][j] for j in range(3)]


def findings(plan, opts):
    """{name: [(code, detail)]}: what the intake changes on each node (empty: already metres, Z up, near zero)."""
    out = {}
    for name, facts in plan['nodes'].items():
        f = []
        if abs(plan['factor'] - 1.0) > 1e-12:
            f.append(('units_scale', 'source numbers in {} read as {}: x{:g}'.format(
                plan['source_units'], plan['scene_units'], plan['factor'])))
        if plan['source_up_axis'] != 'Z':
            f.append(('up_axis', 'source up axis {} -> Z'.format(plan['source_up_axis'])))
        if facts['far']:
            f.append(('far_coordinates', '{:.1f} m from the world zero > {} m; common zero {}'.format(
                facts['distance_m'], opts['far_m'], plan['origin_m'])))
        out[name] = f
    return out


def passport_source(path, facts, note=None):
    """K1 `source` from the class facts of scene10_core.source_facts."""
    out = {'path': str(path or 'untitled'), 'level': facts['level'], 'class': facts['class'],
           'parts': int(facts['parts']), 'largest_share': min(1.0, max(0.0, float(facts['largest_share']))),
           'route': facts['route']}
    if note:
        out['note'] = str(note)
    return out


def passport_normalization(plan):
    """K1 `normalization` after the intake: metres, Z up, the factor and the common zero."""
    return {'units': 'm', 'source_units': plan['source_units'], 'up_axis': 'Z',
            'source_up_axis': plan['source_up_axis'], 'scale': float(plan['factor']),
            'origin_m': [float(c) for c in plan['origin_m']], 'grid_zero_m': [0.0, 0.0, 0.0]}
