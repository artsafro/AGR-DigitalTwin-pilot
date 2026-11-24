"""KPP1 #1609 lattice hook (oks-npm stage `body`, point `before`): line list, ring lattice input, lattice check.

Pattern: n/a | new-case: KPP1 lattice method inputs and checks (BM-00, Artem 2026-11-21) - the Revit line list per
facade, the one-ring lattice JSON for the #1742 prototype `docs/research/body-mesh-method/proto_lattice.py --lines`,
and the closed-ring / through-station / local-defect check of the built body. Folded from line_list.py,
lattice_input.py and lattice_check.py (review r1 P1-1, skeleton [D324]); the three parts are unchanged.

    uv run python jobs/KPP1/lattice-1609/hooks/kpp1_lattice.py lines OPENINGS_SPEC.json WALLS_EXT.json OUT.json --bands BANDS.json
    uv run python jobs/KPP1/lattice-1609/hooks/kpp1_lattice.py input LINE_LIST.json OUT.json [--shift DX DY]
    uv run python jobs/KPP1/lattice-1609/hooks/kpp1_lattice.py check MESH.npz LATTICE.json OUT.json
"""
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
import numpy as np


# ===== lines: Revit line list (was line_list.py) =====
# KPP1 W/S/N/E body lattice lines from the Revit openings/zones list (#1609 restart, BM-00).
#
# Pattern: new-case | new-case: lattice line list of a facade from the Revit openings/zones census, not mesh vertices.
#
# Artem 2026-11-21 (decisions 2-3 of docs/research/body-mesh-method.md §6): ground-floor and other non-repeating
# lines come from the openings/zones list of Revit or DWG, snapped to 10 cm, never from Revit mesh vertices; a line is
# kept only if the cell class changes along it over >= 1.5 m (or >= the opening width), shorter = texture.
#
# Inputs (read-only, Revit census of 26_KPP1_AR_MEP, Revit project metres, Z up, 0.000 = level 0):
#   openings_spec.json      per facade: surrounds (curtain-wall frames = window openings), doors, portals, features,
#                           grilles (jobs/KPP1/scripts/extract_openings.py)
#   walls_ext.objects.json  exterior wall instances with bboxes (stacked finish slices, plinth, vent cladding, canopies)
#
# Rules (all in `plan`):
# - levels z are global for W/S/N/E: every level is a closed ring around the whole envelope (Artem 2026-11-21,
#   «луп и ринг должен быть логичный, без прерваний на другой стороне фасада»); stations u are per facade
#   (S/N: u = x, W/E: u = y). Facade E is in the lattice for that reason (its openings make lines as well).
# - body zones = wall instances whose outer face lies on the facade plane (5 mm); a zone that stops <= POST_GAP short
#   of a facade end is extended to it (that gap is the corner post, a separate element [D336]); every other wall is
#   `not_body` (cladding, canopy, parapet: inset/separate elements) with its distance from the plane.
# - body openings = surrounds and doors; portals, features and grilles are `not_body` (inset elements / texture).
# - snap: candidates whose values lie within `snap` of the first value of a cluster (no chaining) become one line.
#   Its value is the body edge (corner, bottom, top) if the cluster has one, else the edge of the largest opening,
#   else the most frequent zone value; neighbouring lines still <= snap apart are merged again (a move can then
#   exceed snap: summary.moves_over_snap). Every opening edge that moves is reported in `moved` with its delta.
# - reason: a line is kept if the cell class changes across it over >= min_reason or >= the extent of an opening whose
#   edge lies on it; body edges are always kept. Others go to `dropped` with reason "texture".
# - zone class: with --bands (finish bands from the drawings) a zone cell's class is its finish; a wall-instance
#   border inside one finish (e.g. a stacked-wall split) then changes nothing and is dropped as texture.
# CLI: python kpp1_lattice.py lines OPENINGS_SPEC WALLS_EXT OUT.json [--bands FINISH_BANDS.json] [--snap 0.10] [--min-reason 1.5]

FACADES = ('W', 'S', 'N', 'E')
SPEC_KEYS = {'surrounds', 'doors', 'portals', 'features', 'grilles'}
PLANE_TOL = 0.005
POST_GAP = 0.15
EPS = 1e-6


def facade_of(lo, hi):
    """Same facade test as adapters/max/agr_tools/openings_core.kpp1_facade_of (KPP1 profile)."""
    if hi[1] < 0.6 and lo[1] < 0:
        return 'S'
    if lo[1] > 10.4:
        return 'N'
    if hi[0] < 0.6 and lo[0] < 0:
        return 'W'
    if lo[0] > 26.4:
        return 'E'
    return None


def _num(v, label):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ValueError(label + ': expected a finite number, got ' + repr(v))
    return float(v)


def _rect(r, label):
    if not isinstance(r, (list, tuple)) or len(r) != 4:
        raise ValueError(label + ': expected [u0, u1, z0, z1]')
    r = [_num(x, label) for x in r]
    if r[0] >= r[1] or r[2] >= r[3]:
        raise ValueError(label + ': degenerate or reversed rect ' + repr(r))
    return r


def _bbox(o, label):
    lo, hi = o.get('min'), o.get('max')
    if not isinstance(lo, list) or not isinstance(hi, list) or len(lo) != 3 or len(hi) != 3:
        raise ValueError(label + ': expected min/max triples')
    lo, hi = [_num(x, label) for x in lo], [_num(x, label) for x in hi]
    if any(a >= b for a, b in zip(lo, hi)):
        raise ValueError(label + ': degenerate or reversed bbox')
    return lo, hi


def _plane(f, lo, hi):
    """(outer-face coordinate of this wall on the facade normal axis, u-range)."""
    if f == 'S':
        return lo[1], (lo[0], hi[0])
    if f == 'N':
        return hi[1], (lo[0], hi[0])
    if f == 'E':
        return hi[0], (lo[1], hi[1])
    return lo[0], (lo[1], hi[1])  # W


def wall_type(name):
    return re.sub(r'_[0-9a-f]{7}$', '', name).strip()


def collect(spec, walls):
    """Validate inputs; return per-facade zones, openings and not_body lists plus the ignored rows."""
    if not isinstance(spec, dict) or not spec:
        raise ValueError('openings spec: empty or not an object')
    if not isinstance(walls, list) or not walls:
        raise ValueError('walls: empty or not a list')
    out, ignored = {}, []
    for f in spec:
        if f not in FACADES:
            raise ValueError('openings spec: unknown facade key ' + repr(f))
        extra = set(spec[f]) - SPEC_KEYS
        if extra:
            raise ValueError('openings spec ' + f + ': unknown keys ' + repr(sorted(extra)))
    for f in FACADES:
        if f not in spec:
            raise ValueError('openings spec: facade ' + f + ' missing')
    by_f = {f: [] for f in FACADES}
    seen = set()
    for o in walls:
        name = o.get('name') if isinstance(o, dict) else None
        if not isinstance(name, str) or not name.strip() or name in seen:
            raise ValueError('walls: empty or duplicate name ' + repr(name))
        seen.add(name)
        lo, hi = _bbox(o, name)
        f = facade_of(lo, hi)
        if f in FACADES:
            by_f[f].append((name, lo, hi))
        else:
            ignored.append({'what': name, 'reason': 'wall on no facade plane zone (facade %s)' % f})
    for f in FACADES:
        rows = by_f[f]
        if not rows:
            raise ValueError('walls: no wall on facade ' + f)
        # facade plane = outermost face shared by the full-length body walls: the most frequent outer coordinate
        # among walls at least half the facade long
        span = max(_plane(f, lo, hi)[1][1] for _, lo, hi in rows) - min(_plane(f, lo, hi)[1][0] for _, lo, hi in rows)
        longs = [round(_plane(f, lo, hi)[0], 3) for _, lo, hi in rows
                 if _plane(f, lo, hi)[1][1] - _plane(f, lo, hi)[1][0] >= span / 2]
        plane = max(set(longs), key=lambda v: (longs.count(v), -v if f in 'SW' else v))
        zones, not_body = [], []
        for name, lo, hi in rows:
            p, (u0, u1) = _plane(f, lo, hi)
            if abs(p - plane) <= PLANE_TOL:
                zones.append({'name': name, 'type': wall_type(name), 'rect': [u0, u1, lo[2], hi[2]]})
            else:
                not_body.append({'kind': 'wall', 'name': name, 'type': wall_type(name),
                                 'rect': [round(u0, 3), round(u1, 3), lo[2], hi[2]],
                                 'reason': 'outer face %+.3f m from the body plane: separate element [D336]'
                                           % ((plane - p) if f in 'SW' else (p - plane))})
        if not zones:
            raise ValueError('facade %s: no wall on the body plane' % f)
        sp = spec[f]
        opens = []
        for k, s in enumerate(sp.get('surrounds', [])):
            opens.append({'kind': 'surround', 'id': s.get('id', k), 'rect': _rect(s.get('rect'), f + ' surround')})
        for k, d in enumerate(sp.get('doors', [])):
            opens.append({'kind': 'door', 'id': d.get('name', 'door') + '#%d' % k,
                          'rect': _rect(d.get('rect'), f + ' door')})
        for kind in ('portals', 'features'):
            for k, x in enumerate(sp.get(kind, [])):
                not_body.append({'kind': kind[:-1], 'name': str(x.get('id', k)),
                                 'rect': _rect(x.get('rect'), f + ' ' + kind),
                                 'reason': 'frame/screen in front of the wall: inset element [D336]'})
        for k, g in enumerate(sp.get('grilles', [])):
            not_body.append({'kind': 'grille', 'name': 'grille#%d' % k, 'rect': _rect(g, f + ' grille'),
                             'reason': 'vent grille: inset element or texture (BM-08/D344)'})
        out[f] = {'plane': plane, 'zones': zones, 'openings': opens, 'not_body': not_body}
    return out, ignored


def cluster(cands, snap):
    """cands: list of dict(value, kind in body|opening|zone, area, src). Returns [(value, members)]."""
    cands = sorted(cands, key=lambda c: c['value'])
    groups = []
    for c in cands:
        if groups and c['value'] - groups[-1][0]['value'] <= snap + EPS:
            groups[-1].append(c)
        else:
            groups.append([c])
    def rep(g):
        body = [c for c in g if c['kind'] == 'body']
        op = [c for c in g if c['kind'] == 'opening']
        if body:
            return round(body[0]['value'], 4)
        if op:
            return round(max(op, key=lambda c: (c['area'], -c['value']))['value'], 4)
        vals = [round(c['value'], 4) for c in g]
        return max(sorted(set(vals)), key=vals.count)  # zone border: the most frequent exact value
    res = [(rep(g), g) for g in groups]
    # two neighbouring representatives may still be <= snap apart (each moved to its own opening edge): merge
    # them until every pair of lines is more than snap apart
    while True:
        k = next((i for i in range(len(res) - 1) if res[i + 1][0] - res[i][0] <= snap + EPS), None)
        if k is None:
            return res
        g = res[k][1] + res[k + 1][1]
        res[k:k + 2] = [(rep(g), g)]


def _cls(f, u, z, F):
    for o in F['openings']:
        r = o['rect_lattice']
        if r[0] < u < r[1] and r[2] < z < r[3]:
            return 'opening:' + str(o['id'])
    for zn in sorted(F['zones'], key=lambda q: (q['rect_body'][1] - q['rect_body'][0]) * (q['rect_body'][3] - q['rect_body'][2])):
        r = zn['rect_body']  # the smallest zone containing the point wins (a patch over a full-length slice)
        if r[0] < u < r[1] and r[2] < z < r[3]:
            if F.get('bands') is None:
                return 'zone:' + zn['name']
            for b in F['bands']:
                if b['z0'] <= z < b['z1']:
                    return 'finish:' + b['finish']
            raise ValueError('facade %s: z %.3f of zone %s is in no finish band' % (f, z, zn['name']))
    return 'none'


def check_bands(bands):
    """Finish bands from the drawings (zone class = finish, not the Revit wall instance): sorted, contiguous."""
    if not isinstance(bands, list) or not bands:
        raise ValueError('finish bands: empty or not a list')
    out = []
    for k, b in enumerate(bands):
        if not isinstance(b, dict) or not isinstance(b.get('finish'), str) or not b['finish'].strip():
            raise ValueError('finish band %d: finish name missing' % k)
        z0, z1 = _num(b.get('z0'), 'finish band %d z0' % k), _num(b.get('z1'), 'finish band %d z1' % k)
        if z0 >= z1:
            raise ValueError('finish band %d: z0 >= z1' % k)
        if out and abs(out[-1]['z1'] - z0) > EPS:
            raise ValueError('finish band %d: not contiguous with band %d' % (k, k - 1))
        out.append({'z0': z0, 'z1': z1, 'finish': b['finish']})
    return out


def plan(spec, walls, snap=0.10, min_reason=1.5, bands=None):
    snap, min_reason = _num(snap, 'snap'), _num(min_reason, 'min_reason')
    bands = None if bands is None else check_bands(bands)
    if snap <= 0 or min_reason < 0:
        raise ValueError('snap must be > 0 and min_reason >= 0')
    F, ignored = collect(spec, walls)
    zc = []
    for f in FACADES:
        A = F[f]
        A['bands'] = bands
        u0 = min(z['rect'][0] for z in A['zones'])
        u1 = max(z['rect'][1] for z in A['zones'])
        zb = max(0.0, min(z['rect'][2] for z in A['zones']))
        zt = max(z['rect'][3] for z in A['zones'])
        A['extent'] = [u0, u1, zb, zt]
        for zn in A['zones']:
            r = list(zn['rect'])
            ext = []
            if 0 < r[0] - u0 <= POST_GAP:
                ext.append('u0 %.3f->%.3f' % (r[0], u0))
                r[0] = u0
            if 0 < u1 - r[1] <= POST_GAP:
                ext.append('u1 %.3f->%.3f' % (r[1], u1))
                r[1] = u1
            r[2], r[3] = max(r[2], zb), min(r[3], zt)
            zn['rect_body'] = r
            if ext:
                zn['extended'] = ext + ['corner post gap: separate element [D336]']
        for o in A['openings']:
            r = o['rect']
            if r[0] < u0 - PLANE_TOL or r[1] > u1 + PLANE_TOL or r[2] < zb - PLANE_TOL or r[3] > zt + PLANE_TOL:
                raise ValueError('facade %s: opening %s %r outside the body %r' % (f, o['id'], r, A['extent']))
        A['su'] = [{'value': u0, 'kind': 'body', 'area': 0, 'src': 'corner'},
                   {'value': u1, 'kind': 'body', 'area': 0, 'src': 'corner'}]
        for o in A['openings']:
            r = o['rect']
            a = (r[1] - r[0]) * (r[3] - r[2])
            for e, v in (('u0', r[0]), ('u1', r[1])):
                A['su'].append({'value': v, 'kind': 'opening', 'area': a, 'src': '%s %s %s' % (o['kind'], o['id'], e),
                                'op': o, 'edge': e, 'extent': r[3] - r[2]})
            for e, v in (('z0', r[2]), ('z1', r[3])):
                zc.append({'value': v, 'kind': 'opening', 'area': a, 'src': '%s %s %s %s' % (f, o['kind'], o['id'], e),
                           'op': o, 'edge': e, 'extent': r[1] - r[0]})
        for zn in A['zones']:
            r = zn['rect_body']
            for e, v in (('z0', r[2]), ('z1', r[3])):
                kind = 'body' if abs(v - (zb if e == 'z0' else zt)) < EPS else 'zone'
                zc.append({'value': v, 'kind': kind, 'area': 0, 'src': '%s zone %s %s' % (f, zn['type'], e)})
            for e, v in (('u0', r[0]), ('u1', r[1])):
                if abs(v - u0) > EPS and abs(v - u1) > EPS:
                    A['su'].append({'value': v, 'kind': 'zone', 'area': 0, 'src': 'zone %s %s' % (zn['type'], e)})
        for b in bands or []:
            for e in ('z0', 'z1'):
                if zb + EPS < b[e] < zt - EPS:
                    zc.append({'value': b[e], 'kind': 'zone', 'area': 0, 'src': '%s finish %s %s' % (f, b['finish'], e)})
    Z = cluster(zc, snap)
    moved = {f: [] for f in FACADES}

    def snap_edge(groups, f_filter=None):
        for v, g in groups:
            for c in g:
                if 'op' in c:
                    o = c['op']
                    o.setdefault('rect_lattice', list(o['rect']))
                    o['rect_lattice'][('u0', 'u1', 'z0', 'z1').index(c['edge'])] = v
                    if abs(c['value'] - v) > EPS:
                        f = f_filter or c['src'].split()[0]
                        moved[f].append({'opening': '%s %s' % (o['kind'], o['id']), 'edge': c['edge'],
                                         'from': c['value'], 'to': v, 'delta_m': round(v - c['value'], 4)})
    snap_edge(Z)
    S = {}
    for f in FACADES:
        S[f] = cluster(F[f]['su'], snap)
        snap_edge(S[f], f)
        for o in F[f]['openings']:
            r = o['rect_lattice']
            if r[0] >= r[1] - EPS or r[2] >= r[3] - EPS:
                raise ValueError('facade %s: opening %s %s collapses to %r at snap %.3f'
                                 % (f, o['kind'], o['id'], r, snap))
    # reason rule on the clustered lattice
    levels = [v for v, _ in Z]
    result = {'levels': [], 'facades': {}, 'dropped': [], 'ignored': ignored,
              'params': {'snap_m': snap, 'min_reason_m': min_reason, 'post_gap_m': POST_GAP,
                         'zone_class': 'finish band' if bands else 'Revit wall instance', 'finish_bands': bands}}

    def mids(vals, lo, hi):
        vs = sorted(set([lo, hi] + [x for x in vals if lo < x < hi]))
        return [((a + b) / 2, b - a) for a, b in zip(vs, vs[1:])]
    for j, (zv, g) in enumerate(Z):
        change, need = 0.0, min_reason
        for f in FACADES:
            A = F[f]
            if not A['extent'][2] - EPS <= zv <= A['extent'][3] + EPS:
                continue
            us = [v for v, _ in S[f]]
            below = [x for x in levels if x < zv - EPS]
            above = [x for x in levels if x > zv + EPS]
            if not below or not above:
                continue
            zb, za = (below[-1] + zv) / 2, (zv + above[0]) / 2
            for um, w in mids(us, A['extent'][0], A['extent'][1]):
                if _cls(f, um, zb, A) != _cls(f, um, za, A):
                    change += w
        for c in g:
            if c['kind'] == 'opening':
                need = min(need, c['extent'])
        body = any(c['kind'] == 'body' for c in g)
        kept = body or (change > EPS and change + EPS >= need)
        row = {'z': zv, 'kept': kept, 'change_m': round(change, 3), 'need_m': round(need, 3),
               'sources': sorted(set(c['src'] for c in g))}
        result['levels'].append(row)
        if not kept:
            result['dropped'].append({'axis': 'z', 'value': zv, 'reason': 'texture: class change %.3f m < %.3f m'
                                      % (change, need), 'sources': row['sources']})
    zk = [r['z'] for r in result['levels'] if r['kept']]
    for f in FACADES:
        A = F[f]
        rows = []
        for uv, g in S[f]:
            change, need = 0.0, min_reason
            us = [v for v, _ in S[f]]
            left = [x for x in us if x < uv - EPS]
            right = [x for x in us if x > uv + EPS]
            if left and right:
                ul, ur = (left[-1] + uv) / 2, (uv + right[0]) / 2
                for zm, h in mids(levels, A['extent'][2], A['extent'][3]):
                    if _cls(f, ul, zm, A) != _cls(f, ur, zm, A):
                        change += h
            for c in g:
                if c['kind'] == 'opening':
                    need = min(need, c['extent'])
            body = any(c['kind'] == 'body' for c in g)
            kept = body or (change > EPS and change + EPS >= need)
            rows.append({'u': uv, 'kept': kept, 'change_m': round(change, 3), 'need_m': round(need, 3),
                         'sources': sorted(set(c['src'] for c in g))})
            if not kept:
                result['dropped'].append({'axis': 'u', 'facade': f, 'value': uv, 'sources': rows[-1]['sources'],
                                          'reason': 'texture: class change %.3f m < %.3f m' % (change, need)})
        result['facades'][f] = {
            'plane': A['plane'], 'extent': A['extent'],
            'u_axis': 'x' if f in 'SN' else 'y',
            'stations': rows,
            'openings': [{'kind': o['kind'], 'id': o['id'], 'rect': o['rect'], 'rect_lattice': o['rect_lattice']}
                         for o in A['openings']],
            'moved': moved[f],
            'zones': [{k: zn[k] for k in ('name', 'type', 'rect', 'rect_body', 'extended') if k in zn}
                      for zn in A['zones']],
            'not_body': A['not_body']}
    result['summary'] = {
        'levels_kept': len(zk), 'levels_candidates': len(Z),
        'stations_kept': {f: sum(r['kept'] for r in result['facades'][f]['stations']) for f in FACADES},
        'moved_edges': sum(len(moved[f]) for f in FACADES),
        'moves_over_snap': sum(abs(m['delta_m']) > snap + EPS for f in FACADES for m in moved[f]),
        'max_move_m': max([abs(m['delta_m']) for f in FACADES for m in moved[f]] or [0.0])}
    return result


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def lines_main(argv):
    args = list(argv)
    snap, mr = 0.10, 1.5
    if '--snap' in args:
        i = args.index('--snap')
        snap = float(args[i + 1])
        del args[i:i + 2]
    if '--min-reason' in args:
        i = args.index('--min-reason')
        mr = float(args[i + 1])
        del args[i:i + 2]
    bands_p = None
    if '--bands' in args:
        i = args.index('--bands')
        bands_p = Path(args[i + 1])
        del args[i:i + 2]
    if len(args) != 3:
        raise SystemExit(__doc__)
    spec_p, walls_p, out_p = (Path(a) for a in args)
    for p in (spec_p, walls_p) + ((bands_p,) if bands_p else ()):
        if p.resolve() == out_p.resolve():
            raise SystemExit('output aliases input: %s' % out_p)
    raw = {p: p.read_bytes() for p in (spec_p, walls_p) + ((bands_p,) if bands_p else ())}
    bands = json.loads(raw[bands_p].decode('utf-8-sig'))['bands'] if bands_p else None
    res = plan(json.loads(raw[spec_p].decode('utf-8-sig')), json.loads(raw[walls_p].decode('utf-8-sig')), snap, mr,
               bands)
    if any(p.read_bytes() != b for p, b in raw.items()):
        raise SystemExit('input changed during the run')
    res['inputs'] = [{'path': str(p).replace('\\', '/'), 'sha256': hashlib.sha256(b).hexdigest()}
                     for p, b in raw.items()]
    tmp = out_p.with_name(out_p.name + '.partial')
    tmp.write_text(json.dumps(res, ensure_ascii=False, indent=1, allow_nan=False), encoding='utf-8')
    os.replace(tmp, out_p)
    print(json.dumps(res['summary'], ensure_ascii=False))


# ===== input: ring lattice (was lattice_input.py) =====
# KPP1 body lattice input: the W/S/N/E line list on the envelope ring (perimeter stations x global levels).
#
# Pattern: new-case | new-case: facade line list (per facade u, global z) -> one closed ring lattice for the #1742
# prototype `proto_lattice.py --lines` (BM-00: the body is built only from the lattice, Artem 2026-11-21).
#
# Artem 2026-11-21: «луп и ринг должен быть логичный, без прерваний на другой стороне фасада» - every level is a
# closed ring around the whole envelope and every station runs bottom to top. Here a level is one value for all four
# facades and the stations of all facades are laid on ONE perimeter coordinate s, so the lattice has no line that
# stops at a corner by construction (the closure is measured on the built mesh by `kpp1_lattice.py check`).
#
# Ring (CCW seen from +z, start at the SW corner): side 0 = S (x up), 1 = E (y up), 2 = N (x down), 3 = W (y down).
# s = S: u - x0 | E: L_S + (u - y0) | N: L_S + L_E + (x1 - u) | W: 2 L_S + L_E + (y1 - u).
# x0/x1/y0/y1 = W/E/S/N facade planes; every facade extent must span its side (5 mm) and share the levels' range.
# Openings (`rect_lattice`, already snapped to the kept lines) go along as s/z rectangles: the class of a cell.
#
# Frame: the line list is in Revit metres; --shift DX DY moves the ring into the delivery frame (KPP1 R1 FBX =
# Revit - (14.655, 5.355), the frame of sheets.R1_TO_REVIT). s, z and the openings do not change.
#
# CLI: python kpp1_lattice.py input LINE_LIST.json OUT.json [--shift DX DY]
#      (OUT must not alias the input; written via OUT.partial)

SIDES = ('S', 'E', 'N', 'W')
INPUT_TOL = 0.005


def _num(v, label):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ValueError(label + ': expected a finite number, got ' + repr(v))
    return float(v)


def build(ll, shift=(0.0, 0.0)):
    if not isinstance(ll, dict) or not isinstance(ll.get('facades'), dict) or not isinstance(ll.get('levels'), list):
        raise ValueError('line list: facades/levels missing')
    F = ll['facades']
    missing = [f for f in SIDES if f not in F]
    if missing:
        raise ValueError('line list: facade(s) %s missing - a ring needs all four sides' % ','.join(missing))
    extra = sorted(set(F) - set(SIDES))
    if extra:
        raise ValueError('line list: unknown facade(s) %r' % extra)
    pl = {f: _num(F[f].get('plane'), f + ' plane') for f in SIDES}
    x0, x1, y0, y1 = pl['W'], pl['E'], pl['S'], pl['N']
    if not (x1 - x0 > INPUT_TOL and y1 - y0 > INPUT_TOL):
        raise ValueError('ring: degenerate or reversed planes W %.3f E %.3f S %.3f N %.3f' % (x0, x1, y0, y1))
    span = {'S': (x0, x1), 'N': (x0, x1), 'E': (y0, y1), 'W': (y0, y1)}
    levels = [_num(r.get('z'), 'level') for r in ll['levels'] if r.get('kept')]
    if len(levels) < 2 or any(b - a <= INPUT_TOL for a, b in zip(levels, levels[1:])):
        raise ValueError('levels: need >= 2 strictly increasing kept levels, got %r' % levels)
    LS, LE = x1 - x0, y1 - y0
    off = {'S': 0.0, 'E': LS, 'N': LS + LE, 'W': 2 * LS + LE}
    perim = 2 * (LS + LE)

    def to_s(f, u):
        u = _num(u, f + ' u')
        lo, hi = span[f]
        if not lo - INPUT_TOL <= u <= hi + INPUT_TOL:
            raise ValueError('facade %s: u %.4f outside its side %.3f..%.3f' % (f, u, lo, hi))
        u = min(hi, max(lo, u))
        return off[f] + (u - lo if f in 'SE' else hi - u)

    stations, opens, src = {}, [], {}
    for f in SIDES:
        A = F[f]
        e = [_num(v, f + ' extent') for v in A.get('extent', [])]
        if len(e) != 4:
            raise ValueError('facade %s: extent [u0, u1, z0, z1] missing' % f)
        if abs(e[0] - span[f][0]) > INPUT_TOL or abs(e[1] - span[f][1]) > INPUT_TOL:
            raise ValueError('facade %s: extent %.3f..%.3f does not span its ring side %.3f..%.3f'
                             % (f, e[0], e[1], span[f][0], span[f][1]))
        if abs(e[2] - levels[0]) > INPUT_TOL or abs(e[3] - levels[-1]) > INPUT_TOL:
            raise ValueError('facade %s: height %.3f..%.3f differs from the levels %.3f..%.3f'
                             % (f, e[2], e[3], levels[0], levels[-1]))
        for r in A.get('stations', []):
            if r.get('kept'):
                s = round(to_s(f, r['u']) % perim, 5)
                k = next((x for x in stations if abs(x - s) <= 1e-4 or abs(abs(x - s) - perim) <= 1e-4), None)
                if k is None:
                    stations[s] = [f]
                    src[s] = r['u']
                else:
                    stations[k].append(f)  # a corner: last station of one side = first of the next
        for o in A.get('openings', []):
            r = [_num(v, f + ' opening') for v in o.get('rect_lattice', [])]
            if len(r) != 4 or r[0] >= r[1] or r[2] >= r[3]:
                raise ValueError('facade %s: opening %r has no valid rect_lattice' % (f, o.get('id')))
            sa, sb = sorted((to_s(f, r[0]), to_s(f, r[1])))
            if not any(abs(r[2] - z) <= 1e-6 for z in levels) or not any(abs(r[3] - z) <= 1e-6 for z in levels):
                raise ValueError('facade %s: opening %r z %r not on kept levels' % (f, o.get('id'), r[2:]))
            opens.append({'facade': f, 'kind': o.get('kind'), 'id': str(o.get('id')),
                          's0': round(sa, 5), 's1': round(sb, 5), 'z0': r[2], 'z1': r[3]})
    corners = [round(off[f], 5) for f in SIDES]
    for c in corners:
        if not any(abs(c - s) <= 1e-4 for s in stations):
            raise ValueError('ring corner s=%.4f is not a station' % c)
    S = sorted(stations)
    for o in opens:
        for e in ('s0', 's1'):
            if not any(abs(o[e] - s) <= 1e-4 for s in S + [perim]):
                raise ValueError('opening %s %s: edge %s=%.4f is not a station' % (o['facade'], o['id'], e, o[e]))
    dx, dy = (_num(v, 'shift') for v in shift)
    ring = [[round(x + dx, 6), round(y + dy, 6)] for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    return {'rings': [{'xy': ring}], 'sides': list(SIDES), 'perimeter': round(perim, 5),
            'stations_s': S, 'station_facades': [stations[s] for s in S], 'levels': levels, 'openings': opens,
            'corners_s': corners, 'shift': [dx, dy],
            'summary': {'stations': len(S), 'levels': len(levels), 'openings': len(opens),
                        'per_side': {f: sum(1 for s in S if off[f] - 1e-4 <= (s if s > 1e-4 or f != 'W' else perim)
                                            <= off[f] + (LS if f in 'SN' else LE) + 1e-4) for f in SIDES}}}


def input_main(argv):
    argv = list(argv)
    shift = (0.0, 0.0)
    if '--shift' in argv:
        i = argv.index('--shift')
        shift = (float(argv[i + 1]), float(argv[i + 2]))
        del argv[i:i + 3]
    if len(argv) != 2:
        raise SystemExit(__doc__)
    src, out = Path(argv[0]), Path(argv[1])
    tmp = out.with_name(out.name + '.partial')
    if src.resolve() in (out.resolve(), tmp.resolve()):
        raise SystemExit('output aliases input: %s' % out)
    raw = src.read_bytes()
    res = build(json.loads(raw.decode('utf-8-sig')), shift)
    if src.read_bytes() != raw:
        raise SystemExit('input changed during the run')
    res['input'] = {'path': str(src).replace('\\', '/'), 'sha256': hashlib.sha256(raw).hexdigest()}
    tmp.write_text(json.dumps(res, ensure_ascii=False, indent=1, allow_nan=False), encoding='utf-8')
    os.replace(tmp, out)
    print(json.dumps(res['summary']))


# ===== check: lattice body check (was lattice_check.py) =====
# KPP1 lattice body check: closed rings per level, through stations, local defect map per lattice cell.
#
# Pattern: new-case | new-case: ring/loop closure and per-cell local signal of a facade body measured on the ring
# lattice it was planned on (Artem 2026-11-21: every level a closed ring around the whole envelope, no loop that dies
# on the next facade; acceptance sheets carry the local-signal map, decision 5 of body-mesh-method §6).
#
# Input: a mesh (world vertices `verts` (N,3), per-face vertex counts `fn`, flat indices `fi` - the npz of
# docs/research/body-modelling-1618/dump_mesh.py) and the lattice JSON of `kpp1_lattice.py input`.
# Facade faces = |n.z| < 0.1 with every vertex within BAND m of the ring (inside or outside) and z in the level range;
# horizontal faces (|n.z| > 0.9) within the band count as reveal sills/heads (their edges join a ring at a level).
# A vertex is placed on the ring by its nearest side: s (perimeter coordinate) and depth d (inward > 0).
#
# - level z closed: the horizontal edges at z (1 mm) cover the whole perimeter [0, P) in s (gaps listed);
# - station s through: the vertical edges at s (1 mm) cover [zmin, zmax] (gaps listed);
# - cell (station interval x level interval) defects: tri / ngon faces, diagonal edges (neither horizontal nor
#   vertical, > 1 mm), T-vertices (a vertex strictly inside a face edge, 1 mm), non-manifold edges (> 2 faces);
#   every facade face is assigned to exactly one cell by its centroid (faces outside the lattice are counted).
# Fail-closed: no facade face, non-finite vertex, bad lattice -> ValueError.

BAND = 1.0
CHECK_TOL = 1e-3


def ring_frame(lat):
    xy = lat.get('rings', [{}])[0].get('xy') if isinstance(lat, dict) else None
    if not isinstance(xy, list) or len(xy) < 3:
        raise ValueError('lattice: ring missing')
    P = np.array(xy, float)
    if not np.isfinite(P).all():
        raise ValueError('lattice: ring not finite')
    segs, s = [], 0.0
    for i in range(len(P)):
        p, q = P[i], P[(i + 1) % len(P)]
        L = float(np.hypot(*(q - p)))
        if L <= CHECK_TOL:
            raise ValueError('lattice: degenerate ring side %d' % i)
        t = (q - p) / L
        segs.append((s, L, p, t, np.array([-t[1], t[0]])))
        s += L
    return segs, s


def place(verts, segs, perim):
    """(s, d, side) per vertex: nearest ring side in plan (ties -> lower side index)."""
    best = np.full(len(verts), np.inf)
    S = np.zeros(len(verts))
    D = np.zeros(len(verts))
    K = np.full(len(verts), -1)
    xy = verts[:, :2]
    for k, (s0, L, p, t, n) in enumerate(segs):
        u = np.clip((xy - p) @ t, 0.0, L)
        foot = p + u[:, None] * t
        dist = np.hypot(*(xy - foot).T)
        better = dist < best - 1e-9
        best = np.where(better, dist, best)
        S = np.where(better, (s0 + u) % perim, S)
        D = np.where(better, (xy - p) @ n, D)
        K = np.where(better, k, K)
    return S, D, K


def station_lines(S_st, segs, perim):
    """Per station: ring point p and its inward direction m (side normal; at a ring corner the mitre of the two
    normals, so a recessed corner vertex - built along the bisector - lies on its station line)."""
    out = []
    for s in S_st:
        s = s % perim
        k = max(i for i, g in enumerate(segs) if g[0] <= s + 1e-4)
        s0, L, p, t, n = segs[k]
        m = n
        if abs(s - s0) <= 1e-4:
            m = n + segs[k - 1][4]
        out.append((p + t * (s - s0), m / np.linalg.norm(m)))
    return out


def _cover(intervals, lo, hi):
    """Gaps of the union of intervals inside [lo, hi] (each gap > TOL)."""
    iv = sorted((max(lo, a), min(hi, b)) for a, b in intervals if b > lo and a < hi)
    gaps, cur = [], lo
    for a, b in iv:
        if a > cur + CHECK_TOL:
            gaps.append([round(cur, 4), round(a, 4)])
        cur = max(cur, b)
    if hi > cur + CHECK_TOL:
        gaps.append([round(cur, 4), round(hi, 4)])
    return gaps


def check(verts, fn, fi, lat):
    verts = np.asarray(verts, float)
    fn = np.asarray(fn, int)
    fi = np.asarray(fi, int)
    if verts.ndim != 2 or verts.shape[1] != 3 or not len(verts):
        raise ValueError('mesh: no vertices')
    if not np.isfinite(verts).all():
        raise ValueError('mesh: non-finite vertex')
    if fn.sum() != len(fi) or (fn < 3).any():
        raise ValueError('mesh: face index table inconsistent')
    segs, perim = ring_frame(lat)
    S_st = [float(x) for x in lat.get('stations_s', [])]
    Z = [float(z) for z in lat.get('levels', [])]
    if len(S_st) < 3 or len(Z) < 2 or any(not math.isfinite(v) for v in S_st + Z):
        raise ValueError('lattice: stations/levels missing or not finite')
    z0, z1 = Z[0], Z[-1]
    S, D, K = place(verts, segs, perim)
    starts = np.concatenate([[0], np.cumsum(fn)[:-1]])
    faces = [fi[a:a + n] for a, n in zip(starts, fn)]
    fac, hor = [], []
    for f_id, f in enumerate(faces):
        v = verts[f]
        nrm = np.zeros(3)
        for i in range(len(f)):  # Newell normal (works for ngons)
            a, b = v[i], v[(i + 1) % len(f)]
            nrm += [(a[1] - b[1]) * (a[2] + b[2]), (a[2] - b[2]) * (a[0] + b[0]), (a[0] - b[0]) * (a[1] + b[1])]
        ln = np.linalg.norm(nrm)
        if ln < 1e-12:
            continue
        nz = abs(nrm[2]) / ln
        if (np.abs(D[f]) > BAND).any() or (v[:, 2] < z0 - CHECK_TOL).any() or (v[:, 2] > z1 + CHECK_TOL).any():
            continue
        if nz < 0.1:
            fac.append(f_id)
        elif nz > 0.9:
            hor.append(f_id)
    if not fac:
        raise ValueError('mesh: no facade face within %.2f m of the ring and z %.3f..%.3f' % (BAND, z0, z1))
    use = fac + hor
    # edges with face count
    ecount = {}
    for f_id in use:
        f = faces[f_id]
        for i in range(len(f)):
            a, b = int(f[i]), int(f[(i + 1) % len(f)])
            ecount.setdefault((min(a, b), max(a, b)), []).append(f_id)

    def ds(a, b):  # signed s-interval of an edge (wrap at the perimeter start)
        sa, sb = S[a], S[b]
        if abs(sb - sa) > perim / 2:
            return [(max(sa, sb), perim), (0.0, min(sa, sb))]
        return [(min(sa, sb), max(sa, sb))]
    st_lines = station_lines(S_st, segs, perim)

    def on_station(v, i):
        p, m = st_lines[i]
        w = verts[v, :2] - p
        return abs(w[0] * m[1] - w[1] * m[0]) <= CHECK_TOL and -BAND <= w @ m <= BAND
    lev = {j: [] for j in range(len(Z))}
    stn = {i: [] for i in range(len(S_st))}
    diag = []
    for (a, b) in ecount:
        pa, pb = verts[a], verts[b]
        dz = abs(pa[2] - pb[2])
        dxy = math.hypot(pa[0] - pb[0], pa[1] - pb[1])
        if dz <= CHECK_TOL:
            for j, z in enumerate(Z):
                if abs(pa[2] - z) <= CHECK_TOL and abs(pb[2] - z) <= CHECK_TOL:
                    lev[j] += ds(a, b)
        elif dxy <= CHECK_TOL:
            for i in range(len(S_st)):
                if on_station(a, i):
                    stn[i].append((min(pa[2], pb[2]), max(pa[2], pb[2])))
        else:
            diag.append((a, b))
    # T-vertices: a lattice vertex strictly inside an edge
    used_v = np.unique(np.concatenate([faces[f] for f in use]))
    P = verts[used_v]
    tvert = []
    for (a, b) in ecount:
        pa, pb = verts[a], verts[b]
        d = pb - pa
        L2 = float(d @ d)
        if L2 <= CHECK_TOL * CHECK_TOL:
            continue
        t = (P - pa) @ d / L2
        cand = (t > 1e-6) & (t < 1 - 1e-6)
        if not cand.any():
            continue
        q = pa + np.outer(t[cand], d)
        dist = np.linalg.norm(P[cand] - q, axis=1)
        ok = dist <= CHECK_TOL
        for v, tv in zip(used_v[cand][ok], t[cand][ok]):
            if v not in (a, b) and math.sqrt(L2) * min(tv, 1 - tv) > CHECK_TOL:
                tvert.append((int(v), a, b))
    nonman = [e for e, fl in ecount.items() if len(fl) > 2]
    # cells
    Sx = S_st + [perim]

    def cell_of(pt_s, pt_z):
        i = int(np.searchsorted(Sx, pt_s % perim, side='right')) - 1
        j = int(np.searchsorted(Z, pt_z, side='right')) - 1
        return (min(max(i, 0), len(S_st) - 1), min(max(j, 0), len(Z) - 2))

    def centroid_cell(ids):
        ss = S[ids]
        if ss.max() - ss.min() > perim / 2:
            ss = np.where(ss < perim / 2, ss + perim, ss)
        return cell_of(float(ss.mean()) % perim, float(verts[ids, 2].mean()))
    cells = {}

    def bump(c, k, n=1):
        cells.setdefault(c, {'faces': 0, 'tri': 0, 'ngon': 0, 'diagonal': 0, 't_vertex': 0, 'non_manifold': 0})
        cells[c][k] += n
    for f_id in use:
        f = faces[f_id]
        c = centroid_cell(np.asarray(f))
        bump(c, 'faces')
        if len(f) == 3:
            bump(c, 'tri')
        elif len(f) > 4:
            bump(c, 'ngon')
    for a, b in diag:
        bump(centroid_cell(np.array([a, b])), 'diagonal')
    for v, a, b in tvert:
        bump(centroid_cell(np.array([v])), 't_vertex')
    for a, b in nonman:
        bump(centroid_cell(np.array([a, b])), 'non_manifold')
    bad = {c: v for c, v in cells.items() if any(v[k] for k in ('tri', 'ngon', 'diagonal', 't_vertex', 'non_manifold'))}
    levels = []
    for j, z in enumerate(Z):
        gaps = _cover(lev[j], 0.0, perim)
        levels.append({'z': z, 'closed': not gaps, 'gaps_s': gaps[:20], 'gap_m': round(sum(b - a for a, b in gaps), 4)})
    stations = []
    for i, s in enumerate(S_st):
        gaps = _cover(stn[i], z0, z1)
        stations.append({'s': s, 'through': not gaps, 'gaps_z': gaps[:20],
                         'gap_m': round(sum(b - a for a, b in gaps), 4)})
    nface = len(use)
    return {
        'perimeter': round(perim, 5), 'levels': levels, 'stations': stations,
        'cells': [{'i': c[0], 'j': c[1], **v} for c, v in sorted(cells.items())],
        'summary': {
            'faces': nface, 'facade_faces': len(fac), 'horizontal_faces': len(hor),
            'quads': sum(1 for f in use if len(faces[f]) == 4), 'tris': sum(1 for f in use if len(faces[f]) == 3),
            'ngons': sum(1 for f in use if len(faces[f]) > 4), 'diagonal_edges': len(diag),
            't_vertices': len(tvert), 'non_manifold_edges': len(nonman),
            'levels_closed': sum(r['closed'] for r in levels), 'levels': len(levels),
            'stations_through': sum(r['through'] for r in stations), 'stations': len(stations),
            'cells_with_faces': len(cells), 'cells_with_defects': len(bad),
            'cells_defect_share': round(len(bad) / max(1, len(cells)), 4)}}


def check_main(argv):
    if len(argv) != 3:
        raise SystemExit('usage: python kpp1_lattice.py check MESH.npz LATTICE.json OUT.json')
    mesh, latp, out = (Path(a) for a in argv)
    tmp = out.with_name(out.name + '.partial')
    for p in (mesh, latp):
        if p.resolve() in (out.resolve(), tmp.resolve()):
            raise SystemExit('output aliases input: %s' % out)
    m = np.load(mesh)
    rep = check(m['verts'], m['fn'], m['fi'], json.loads(latp.read_text(encoding='utf-8-sig')))
    rep['inputs'] = {'mesh': str(mesh).replace('\\', '/'), 'lattice': str(latp).replace('\\', '/')}
    tmp.write_text(json.dumps(rep, indent=1, allow_nan=False), encoding='utf-8')
    os.replace(tmp, out)
    print(json.dumps(rep['summary']))


COMMANDS = {'lines': lines_main, 'input': input_main, 'check': check_main}

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        raise SystemExit(__doc__)
    COMMANDS[sys.argv[1]](sys.argv[2:])
