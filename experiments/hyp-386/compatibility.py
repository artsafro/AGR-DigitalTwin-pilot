"""New-case: fail-closed guards for the opt-in synthetic #386 harness only."""
import math
import os
import re
from pathlib import Path


def finite(value):
    if isinstance(value, dict):
        for v in value.values():
            finite(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            finite(v)
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError('non-finite synthetic input')


def below(value, limit, label):
    finite(value)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value < limit:
        raise ValueError(f'{label}: {value} must be strictly below {limit}')


def paths(source, *outputs):
    """Reject aliases (including hardlinks) and all existing outputs/partial sidecars."""
    source = Path(source).resolve()
    if not source.is_file():
        raise ValueError(f'input missing: {source}')
    targets = [Path(p).resolve() for p in outputs]
    all_paths = [source, *targets, *(Path(str(p) + '.partial') for p in targets)]
    for i, p in enumerate(all_paths):
        for q in all_paths[:i]:
            if p == q or (p.exists() and q.exists() and os.path.samefile(p, q)):
                raise ValueError(f'aliased paths: {p} / {q}')
    for p in all_paths[1:]:
        if p.exists():
            raise ValueError(f'output exists: {p}')


def inventory(objects, expected):
    names = [o['name'] for o in objects]
    if not expected or len(names) != len(set(names)) or set(names) != set(expected):
        raise ValueError(f'object inventory: {names}; expected {sorted(expected)}')
    finite(objects)


def synthetic_dump(dump):
    """Only the six-box triangle payload is supported; no silent keys/material remapping."""
    if set(dump) != {'meshes'}:
        raise ValueError(f'unsupported dump keys: {sorted(set(dump) - {"meshes"})}')
    names = {f'P{k}_{side}' for k in range(3) for side in 'AB'}
    inventory(dump['meshes'], names)
    for m in dump['meshes']:
        allowed = {'name', 'vertices', 'triangles', 'material_ids', 'matrix_world'}
        if set(m) != allowed:
            raise ValueError(f'{m["name"]}: unsupported/missing keys {set(m) ^ allowed}')
        if len(m['vertices']) != 8 or any(len(v) != 3 for v in m['vertices']):
            raise ValueError(f'{m["name"]}: expected eight 3D vertices')
        if len(m['triangles']) != 12 or any(len(t) != 3 or any(type(i) is not int or not 0 <= i < 8 for i in t) for t in m['triangles']):
            raise ValueError(f'{m["name"]}: unsupported triangles')
        if m['material_ids'] != [1] * 12:
            raise ValueError(f'{m["name"]}: unmapped material ids {m["material_ids"]}; only ID_01 supported')
        if len(m['matrix_world']) != 4 or any(len(r) != 4 for r in m['matrix_world']):
            raise ValueError(f'{m["name"]}: expected 4x4 matrix')


def validate_results(result, predictions):
    """Independent, strict adoption checks; frozen historic predictions are not rewritten."""
    finite(result)
    if result['env']['rc'] != 0 or not re.match(r'^Blender 5\.1\.\d+\b', result['env']['blender_version']):
        raise ValueError('unsupported Blender environment')
    if result['delivery_passed'] is not False or result['verdict'] != 'CONFIRMED' or result['complete'] is not True:
        raise ValueError('incomplete/non-confirmed experiment or delivery claim')
    if set(result['fails']) != {'analytic', 'A_baked', 'B_local', 'control', 'native'} or any(result['fails'].values()):
        raise ValueError('reported experiment failures')
    p, t = predictions, predictions['thresholds']
    expected = {(arm, rep, a, tuple(tr)) for arm in p['arms'] for rep in (1, 2)
                for a in p['angles_deg'] for tr in p['translations_m']}
    rows = result['rows']
    keys = [(r['arm'], r['rep'], r['angle'], tuple(r['t'])) for r in rows]
    if len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError('empty/partial/unsupported scene matrix')
    names = {f'P{k}_{s}' for k in range(3) for s in 'AB'}
    controls = []
    by_key = dict(zip(keys, rows))
    for r in rows:
        if r['export_rc'] != 0 or r['import_rc'] != 0:
            raise ValueError('native failure')
        for field in ('analytic', 'imported'):
            if len(r[field]) != 3:
                raise ValueError(f'{field}: missing pairs')
            for k, gap in enumerate(r[field]):
                if gap['class'] != 'in_band' or gap['penetration_m'] != 0:
                    raise ValueError(f'{field}: invalid pair {k}')
                error = abs(gap['gap_m'] - p['gaps_m'][k])
                if error != gap['abs_err_m']:
                    raise ValueError('inconsistent gap error')
                if field == 'analytic' or r['arm'] == 'B_local':
                    below(error, t['analytic_abs_error_m_max'] if field == 'analytic' else t['local_imported_gap_error_m_max'], field)
        inventory([{'name': n} for n in r['meta']], names)
        for md in r['meta'].values():
            if (md['corners'], md['tris'], md['closed'], md['convex'], md['degenerate']) != (8, 12, True, True, 0):
                raise ValueError('invalid box structure')
        if r['arm'] == 'B_local':
            pre = r['prefbx']
            if pre['matrices_identical'] is not True or len(pre['gaps']) != 3:
                raise ValueError('prefbx matrix/pair coverage')
            inventory([{'name': n} for n in pre['meta']], names)
            for md in pre['meta'].values():
                if (md['corners'], md['tris'], md['closed'], md['convex'], md['degenerate']) != (8, 12, True, True, 0):
                    raise ValueError('invalid prefbx structure')
            for k, gap in enumerate(pre['gaps']):
                if gap['class'] != 'in_band' or gap['penetration_m'] != 0:
                    raise ValueError('prefbx invalid pair')
                below(abs(gap['gap_m'] - p['gaps_m'][k]), t['local_prefbx_gap_error_m_max'], 'prefbx')
            mats = r['imported_matrices']
            inventory([{'name': n} for n in mats], names)
            if any(len(m) != 4 or any(len(row) != 4 for row in m) for m in mats.values()):
                raise ValueError('invalid imported matrix shape')
            if any(m != mats['P0_A'] for m in mats.values()):
                raise ValueError('imported matrices differ')
            for md in r['meta'].values():
                below(md['corner_dist_m'], t['local_corner_distance_m_max'], 'corner')
            other = by_key[('B_local', 3 - r['rep'], r['angle'], tuple(r['t']))]
            for a, b in zip(r['imported'], other['imported']):
                below(abs(a['gap_m'] - b['gap_m']), t['repeat_gap_diff_m_max'], 'repeat')
        c = t['baked_control']
        if r['arm'] == 'A_baked' and r['angle'] == c['angle'] and r['t'] == c['t']:
            mm = r['imported'][0]['gap_m'] * 1000
            below(abs(mm - c['expected_imported_gap_mm']), c['tolerance_mm'], 'baked control')
            controls.append(mm)
    if len(controls) != 2 or controls != result['control_mm']:
        raise ValueError('missing/inconsistent baked controls')
    return True
