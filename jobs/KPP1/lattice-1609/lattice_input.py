"""KPP1 body lattice input: the W/S/N/E line list on the envelope ring (perimeter stations x global levels).

Pattern: new-case | new-case: facade line list (per facade u, global z) -> one closed ring lattice for the #1742
prototype `proto_lattice.py --lines` (BM-00: the body is built only from the lattice, Artem 2026-11-21).

Artem 2026-11-21: «луп и ринг должен быть логичный, без прерваний на другой стороне фасада» - every level is a
closed ring around the whole envelope and every station runs bottom to top. Here a level is one value for all four
facades and the stations of all facades are laid on ONE perimeter coordinate s, so the lattice has no line that
stops at a corner by construction (the closure is measured on the built mesh by `lattice_check.py`).

Ring (CCW seen from +z, start at the SW corner): side 0 = S (x up), 1 = E (y up), 2 = N (x down), 3 = W (y down).
s = S: u - x0 | E: L_S + (u - y0) | N: L_S + L_E + (x1 - u) | W: 2 L_S + L_E + (y1 - u).
x0/x1/y0/y1 = W/E/S/N facade planes; every facade extent must span its side (5 mm) and share the levels' range.
Openings (`rect_lattice`, already snapped to the kept lines) go along as s/z rectangles: the class of a cell.

Frame: the line list is in Revit metres; --shift DX DY moves the ring into the delivery frame (KPP1 R1 FBX =
Revit - (14.655, 5.355), the frame of sheets.R1_TO_REVIT). s, z and the openings do not change.

CLI: python lattice_input.py LINE_LIST.json OUT.json [--shift DX DY]
     (OUT must not alias the input; written via OUT.partial)
"""
import hashlib
import json
import math
import os
import sys
from pathlib import Path

SIDES = ('S', 'E', 'N', 'W')
TOL = 0.005


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
    if not (x1 - x0 > TOL and y1 - y0 > TOL):
        raise ValueError('ring: degenerate or reversed planes W %.3f E %.3f S %.3f N %.3f' % (x0, x1, y0, y1))
    span = {'S': (x0, x1), 'N': (x0, x1), 'E': (y0, y1), 'W': (y0, y1)}
    levels = [_num(r.get('z'), 'level') for r in ll['levels'] if r.get('kept')]
    if len(levels) < 2 or any(b - a <= TOL for a, b in zip(levels, levels[1:])):
        raise ValueError('levels: need >= 2 strictly increasing kept levels, got %r' % levels)
    LS, LE = x1 - x0, y1 - y0
    off = {'S': 0.0, 'E': LS, 'N': LS + LE, 'W': 2 * LS + LE}
    perim = 2 * (LS + LE)

    def to_s(f, u):
        u = _num(u, f + ' u')
        lo, hi = span[f]
        if not lo - TOL <= u <= hi + TOL:
            raise ValueError('facade %s: u %.4f outside its side %.3f..%.3f' % (f, u, lo, hi))
        u = min(hi, max(lo, u))
        return off[f] + (u - lo if f in 'SE' else hi - u)

    stations, opens, src = {}, [], {}
    for f in SIDES:
        A = F[f]
        e = [_num(v, f + ' extent') for v in A.get('extent', [])]
        if len(e) != 4:
            raise ValueError('facade %s: extent [u0, u1, z0, z1] missing' % f)
        if abs(e[0] - span[f][0]) > TOL or abs(e[1] - span[f][1]) > TOL:
            raise ValueError('facade %s: extent %.3f..%.3f does not span its ring side %.3f..%.3f'
                             % (f, e[0], e[1], span[f][0], span[f][1]))
        if abs(e[2] - levels[0]) > TOL or abs(e[3] - levels[-1]) > TOL:
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


def main(argv):
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


if __name__ == '__main__':
    main(sys.argv[1:])
