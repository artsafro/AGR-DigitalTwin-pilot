"""KPP1 W/S/N body lattice lines from the Revit openings/zones list (#1609 restart, BM-00).

Pattern: new-case | new-case: lattice line list of a facade from the Revit openings/zones census, not mesh vertices.

Artem 2026-11-21 (decisions 2-3 of docs/research/body-mesh-method.md §6): ground-floor and other non-repeating
lines come from the openings/zones list of Revit or DWG, snapped to 10 cm, never from Revit mesh vertices; a line is
kept only if the cell class changes along it over >= 1.5 m (or >= the opening width), shorter = texture.

Inputs (read-only, Revit census of 26_KPP1_AR_MEP, Revit project metres, Z up, 0.000 = level 0):
  openings_spec.json      per facade: surrounds (curtain-wall frames = window openings), doors, portals, features,
                          grilles (jobs/KPP1/scripts/extract_openings.py)
  walls_ext.objects.json  exterior wall instances with bboxes (stacked finish slices, plinth, vent cladding, canopies)

Rules (all in `plan`):
- levels z are global for W/S/N (swept around the envelope); stations u are per facade (S/N: u = x, W: u = y).
- body zones = wall instances whose outer face lies on the facade plane (5 mm); a zone that stops <= POST_GAP short
  of a facade end is extended to it (that gap is the corner post, a separate element [D336]); every other wall is
  `not_body` (cladding, canopy, parapet: inset/separate elements) with its distance from the plane.
- body openings = surrounds and doors; portals, features and grilles are `not_body` (inset elements / texture).
- snap: candidates whose values lie within `snap` of the first value of a cluster (no chaining) become one line.
  Its value is the body edge (corner, bottom, top) if the cluster has one, else the edge of the largest opening,
  else the most frequent zone value; neighbouring lines still <= snap apart are merged again (a move can then
  exceed snap: summary.moves_over_snap). Every opening edge that moves is reported in `moved` with its delta.
- reason: a line is kept if the cell class changes across it over >= min_reason or >= the extent of an opening whose
  edge lies on it; body edges are always kept. Others go to `dropped` with reason "texture".
- zone class: with --bands (finish bands from the drawings) a zone cell's class is its finish; a wall-instance
  border inside one finish (e.g. a stacked-wall split) then changes nothing and is dropped as texture.
CLI: python line_list.py OPENINGS_SPEC WALLS_EXT OUT.json [--bands FINISH_BANDS.json] [--snap 0.10] [--min-reason 1.5]
"""
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path

FACADES = ('W', 'S', 'N')
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
        if f not in FACADES + ('E',):
            raise ValueError('openings spec: unknown facade key ' + repr(f))
        extra = set(spec[f]) - SPEC_KEYS
        if extra:
            raise ValueError('openings spec ' + f + ': unknown keys ' + repr(sorted(extra)))
    for f in FACADES:
        if f not in spec:
            raise ValueError('openings spec: facade ' + f + ' missing')
    if 'E' in spec:
        ignored.append({'what': 'openings of facade E', 'reason': 'facade E is outside the W/S/N scope of #1609'})
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
            ignored.append({'what': name, 'reason': 'wall not on W/S/N (facade %s)' % f})
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


def main(argv):
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


if __name__ == '__main__':
    main(sys.argv[1:])
