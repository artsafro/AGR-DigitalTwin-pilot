"""KPP1 window generator test (#1338): windowgen_core types against the hand-built KPP1 windows.

new-case: KPP1 measurement harness - library window types (windowgen_core.build_type, VPM branch) matched to the
openings_spec bays through winplace_core.plan; their glass fields replace `w +- WINDOW_FRAME` only in copies.

Pure Python (no bpy): used by build_kpp1.py inside Blender and by the tests.

* `glass_rects(b, plan, frame)` is the ONE source of a bay's glass rectangles [u0, u1, z0, z1]: without a plan (or
  for a bay the plan excluded) it is the accepted v005 rule `w +- WINDOW_FRAME` + b["glass"]; with a plan it is the
  type's glass fields.
* `plan_bays(spec, types, standard)` runs winplace_core.plan on every surround/feature bay (facade-local frame),
  builds the matched type with build_type(variant='vpm') and matches every glass field one-to-one to a source contour
  (b["windows"] + b["glass"]). Any mismatch (no type, ambiguous type, opaque fields, field count, a field overlapping
  zero or several contours, a contour left unmatched, a field outside its contour or more than `tol` inside it)
  excludes the bay: the substitution stops there, both sources and the per-side deltas are logged. No scaling,
  centring or symmetry assumption: type x runs along facade u from the bay's u0, type z from the bay's z0.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'adapters', 'max', 'agr_tools'))
import windowgen_core as wg  # noqa: E402
import winplace_core as wp  # noqa: E402

LIBRARY = os.path.join(ROOT, 'library', 'windows')
SCHEMA = 'kpp1-windowgen/1'
SIDES = ('u0', 'u1', 'z0', 'z1')


def _finite_rect(r, what):
    if not isinstance(r, (list, tuple)) or len(r) != 4:
        raise ValueError('{}: rect must be [u0, u1, z0, z1]: {!r}'.format(what, r))
    out = []
    for c in r:
        if isinstance(c, bool) or not isinstance(c, (int, float)) or not math.isfinite(c):
            raise ValueError('{}: rect coordinate must be a finite number: {!r}'.format(what, r))
        out.append(float(c))
    if out[1] <= out[0] or out[3] <= out[2]:
        raise ValueError('{}: empty or inverted rect: {!r}'.format(what, r))
    return out


def load_library(folder=LIBRARY):
    types = json.load(open(os.path.join(folder, 'window_types.json'), encoding='utf-8'))['types']
    standard = json.load(open(os.path.join(folder, 'standard.json'), encoding='utf-8'))
    return types, standard


def old_rects(b, frame):
    """The accepted v005 rule (build_kpp1.py before #1338): AGS68 window bbox minus `frame` per side + bare glass."""
    return [[w[0] + frame, w[1] - frame, w[2] + frame, w[3] - frame] for w in b['windows']] + [list(g) for g in b['glass']]


def glass_rects(b, plan=None, frame=None):
    """Glass rectangles [u0, u1, z0, z1] of one bay - the single source for surround_cell and the relief cuts.

    plan: None (accepted rule) or {'bays': {str(bay id): {'status': 'substituted'|'excluded', 'glass': [...]}}}."""
    if frame is None:
        raise ValueError('glass_rects: frame width is required')
    if plan is not None:
        row = plan['bays'].get(str(b['id']))
        if row is None:
            raise KeyError('glass_rects: bay {} is not in the windowgen plan'.format(b['id']))
        if row['status'] == 'substituted':
            return [list(r) for r in row['glass']]
    return old_rects(b, frame)


def type_mesh(entry, standard):
    """build_type VPM branch (always standardized, windowgen_core.build_type)."""
    return wg.build_type(entry, standard, {'variant': 'vpm'})


def type_glass(mesh, bay_rect):
    """Glass fields of a type mesh placed at the bay's lower-left corner, as facade rects [u0, u1, z0, z1]."""
    u0, z0 = bay_rect[0], bay_rect[2]
    return [[round(u0 + r[0], 6), round(u0 + r[2], 6), round(z0 + r[1], 6), round(z0 + r[3], 6)]
            for k, r in mesh['fields'] if k == 'glass']


def _overlap(a, b):
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[2], b[2]))


def deltas(field, contour):
    """Per-side inset of a glass field inside its contour (metres, + = glass inside = frame visible)."""
    return {'u0': round(field[0] - contour[0], 6), 'u1': round(contour[1] - field[1], 6),
            'z0': round(field[2] - contour[2], 6), 'z1': round(contour[3] - field[3], 6)}


def match_fields(fields, contours, tol):
    """One-to-one match of glass fields to source contours. Returns (pairs, why): pairs [(fi, ci, deltas)], why []
    when every field and every contour is matched once and every delta is in [-0.0005, tol]."""
    why, pairs = [], []
    if not fields:
        why.append('type has no glass field')
    if len(fields) != len(contours):
        why.append('field count {} != source contour count {}'.format(len(fields), len(contours)))
    used = {}
    for fi, f in enumerate(fields):
        hits = [ci for ci, c in enumerate(contours) if _overlap(f, c) > 1e-9]
        if len(hits) != 1:
            why.append('field {} overlaps {} source contours {}'.format(fi, len(hits), hits))
            continue
        ci = hits[0]
        if ci in used:
            why.append('contour {} matched by fields {} and {}'.format(ci, used[ci], fi))
            continue
        used[ci] = fi
        d = deltas(f, contours[ci])
        bad = [s for s in SIDES if not (-0.0005 <= d[s] <= tol + 1e-9)]
        if bad:
            why.append('field {} vs contour {}: sides {} outside [0, {}] m'.format(fi, ci, bad, tol))
        pairs.append((fi, ci, d))
    left = [ci for ci in range(len(contours)) if ci not in used]
    if left and fields:
        why.append('source contours {} unmatched'.format(left))
    return pairs, why


def _bays(spec):
    for f in sorted(spec):
        for kind in ('surrounds', 'features'):
            for sur in spec[f].get(kind) or ():
                for b in sur['bays']:
                    yield f, kind, b


def plan_bays(spec, types, standard, tol=None, frame=0.07):
    """Plan of the substitution over every bay of openings_spec.json (see module doc)."""
    report = wg.library_report(types, standard)
    offer = wg.offerable(report)
    by_id = {t['id']: t for t in types}
    tol = standard['criteria']['apply_tol_m'] if tol is None else tol
    bays = list(_bays(spec))
    seen = set()
    openings = []
    for f, kind, b in bays:
        bid = str(b['id'])
        if bid in seen:
            raise ValueError('duplicate bay id {}'.format(bid))
        seen.add(bid)
        r = _finite_rect(b['rect'], 'bay {}'.format(bid))
        for i, c in enumerate(list(b['windows']) + list(b['glass'])):
            _finite_rect(c, 'bay {} contour {}'.format(bid, i))
        openings.append({'id': bid, 'wall': f, 'kind': 'bay', 'status': 'ok', 'why': [], 'w': r[1] - r[0],
                         'h': r[3] - r[2], 'depth': 0.0,
                         'frame': {'origin': [(r[0] + r[1]) / 2, 0.0, (r[2] + r[3]) / 2], 'x': [1.0, 0.0, 0.0],
                                   'y': [0.0, 0.0, 1.0], 'z': [0.0, -1.0, 0.0]}})
    meshes = {}

    def info(tid):
        if tid not in meshes:
            meshes[tid] = type_mesh(by_id[tid], standard)
        return meshes[tid]
    acts = wp.plan(openings, [], by_id, offer, info, wp.check_options())['actions']
    rows = {}
    for (f, kind, b), act in zip(bays, acts):
        bid = str(b['id'])
        contours = [list(w) for w in b['windows']] + [list(g) for g in b['glass']]
        row = {'facade': f, 'kind': kind, 'rect': list(b['rect']), 'type': act['type'], 'contours': contours,
               'contour_src': ['window'] * len(b['windows']) + ['glass'] * len(b['glass']),
               'old_glass': old_rects(b, frame), 'status': 'excluded', 'why': list(act['why']), 'glass': None,
               'pairs': []}
        if act['status'] == 'place' and act['type']:
            mesh = info(act['type'])
            opaque = [r for k, r in mesh['fields'] if k != 'glass']
            fields = type_glass(mesh, row['rect'])
            row['type_glass'] = fields
            if mesh['status'] != 'ok':
                row['why'].append('type quarantined: {}'.format(mesh['why']))
            if opaque:
                row['why'].append('type has {} opaque fields (only glass-only types are substituted)'.format(len(opaque)))
            pairs, why = match_fields(fields, contours, tol)
            row['why'] += why
            row['pairs'] = [{'field': fi, 'contour': ci, 'src': row['contour_src'][ci], 'delta_m': d,
                             'old_delta_m': deltas(row['old_glass'][ci], contours[ci])} for fi, ci, d in pairs]
            if not row['why']:
                row['status'], row['glass'] = 'substituted', fields
        elif not row['why']:
            row['why'].append('win.place status {}'.format(act['status']))
        rows[bid] = row
    counts = {s: sum(r['status'] == s for r in rows.values()) for s in ('substituted', 'excluded')}
    return {'schema': SCHEMA, 'tol_m': tol, 'frame_m': frame, 'counts': counts, 'bays': rows,
            'note': 'W01 glass_m / panes_m equal the whole AGS68 window bbox (window_types.json); whether the '
                    'library field is the glass or the AGS68 unit is an open question for Artem - reported, '
                    'not decided.'}


def _guard_new_path(path, inputs):
    """A report path must be new and outside every input directory (never overwrite an input or a delivery)."""
    p = os.path.realpath(os.path.abspath(path))
    if os.path.exists(p):
        raise ValueError('report path exists (versioned outputs are never overwritten): {}'.format(path))
    for d in inputs:
        d = os.path.realpath(os.path.abspath(d))
        if p == d or p.startswith(d.rstrip(os.sep) + os.sep):
            raise ValueError('report path {} is inside the input {}'.format(path, d))
    return p


def write_plan(spec, path, inputs, frame=0.07, library=LIBRARY):
    """plan_bays over the library, written to a NEW json path outside `inputs` (exclusive create)."""
    p = _guard_new_path(path, list(inputs) + [library])
    types, standard = load_library(library)
    plan = plan_bays(spec, types, standard, frame=frame)
    with open(p, 'x', encoding='utf-8') as fh:
        json.dump(plan, fh, indent=1, ensure_ascii=False)
    return plan


# ---- stage 1: isolated types ---------------------------------------------------------------------------------
def isolated_plan(type_ids, types, standard):
    """winplace_core.plan on one isolated opening per type (its own size, frame at the origin) -> build_type(vpm).
    Returns {tid: {'action': {...}, 'mesh': mesh}}; a type the plan does not place is an error naming it."""
    report = wg.library_report(types, standard)
    offer = wg.offerable(report)
    by_id = {t['id']: t for t in types}
    missing = [t for t in type_ids if t not in by_id]
    if missing:
        raise KeyError('types not in the library: {}'.format(missing))
    ops = [{'id': t, 'wall': 'isolated', 'kind': 'type', 'status': 'ok', 'why': [], 'w': by_id[t]['width_m'],
            'h': by_id[t]['height_m'], 'depth': 0.0,
            'frame': {'origin': [0.0, 0.0, 0.0], 'x': [1.0, 0.0, 0.0], 'y': [0.0, 0.0, 1.0], 'z': [0.0, -1.0, 0.0]}}
           for t in type_ids]
    acts = wp.plan(ops, [], by_id, offer, lambda tid: type_mesh(by_id[tid], standard), wp.check_options())['actions']
    out = {}
    for t, a in zip(type_ids, acts):
        if a['status'] != 'place' or a['type'] != t:
            raise ValueError('win.place did not place {} on its own opening: {} {} {}'.format(
                t, a['status'], a['type'], a['why']))
        out[t] = {'action': {'type': a['type'], 'status': a['status'], 'findings': a['findings'], 'rows': a['rows']},
                  'mesh': type_mesh(by_id[t], standard)}
    return out


def mesh_summary(mesh):
    """What a readback must reproduce: counts, bbox, per-part face counts and the glass quads' x/z rects."""
    vs = mesh['verts']
    gl = []
    for fi in mesh['parts']['glass']:
        pts = [vs[i] for i in mesh['faces'][fi]]
        gl.append([round(min(p[0] for p in pts), 6), round(min(p[2] for p in pts), 6),
                   round(max(p[0] for p in pts), 6), round(max(p[2] for p in pts), 6), round(pts[0][1], 6)])
    return {'verts': len(vs), 'faces': len(mesh['faces']),
            'bbox': [[round(min(v[i] for v in vs), 6) for i in range(3)], [round(max(v[i] for v in vs), 6) for i in range(3)]],
            'parts': {k: len(v) for k, v in mesh['parts'].items()}, 'glass': sorted(gl)}


def compare_readback(want, got, tol=1e-5):
    """Differences [str] between mesh_summary of the built mesh and of the readback (empty = equal)."""
    diff = []
    for k in ('verts', 'faces'):
        if want[k] != got.get(k):
            diff.append('{}: built {} readback {}'.format(k, want[k], got.get(k)))
    for k, n in want['parts'].items():
        if got.get('parts', {}).get(k) != n:
            diff.append('part {}: built {} readback {}'.format(k, n, got.get('parts', {}).get(k)))
    gb = got.get('bbox') or [[math.nan] * 3, [math.nan] * 3]
    if any(not abs(a - b) <= tol for p, q in zip(want['bbox'], gb) for a, b in zip(p, q)):
        diff.append('bbox: built {} readback {}'.format(want['bbox'], got.get('bbox')))
    gg = got.get('glass') or []
    if len(gg) != len(want['glass']) or any(not abs(a - b) <= tol for p, q in zip(want['glass'], sorted(gg))
                                            for a, b in zip(p, q)):
        diff.append('glass: built {} readback {}'.format(want['glass'], gg))
    return diff
