"""Hook `after` stage `body` (#1619 polygon stage 2, tower 63B): windows + capsules on the accepted v007 body.

Pattern: n/a | new-case: 63B additive stage 2; every step calls the POLY63-A stage-2 helpers and the owner cores
(openings_core, windowgen_core, winplace_core, capsule_core). The body is only read.

uv run python stage2_63b.py BODY_DUMP.npz CROP.npz STAGE2.json [--band 4.65 51.90] [--standard standard.json]

63B deltas to the 63A/63C route (each one a check, never a silent fix):
* window axis: a few Revit windows carry a sloped part that tilts the PCA axis of 63A `revit_window` by ~0.07 deg,
  so their 0.8 m glass is 1 mm "off flat" and no pane is found. The axis is taken from the dominant vertical face
  normal of the window instead (`glass_axis`) and handed to `revit_window(tri, u=...)`;
* bent rims: 13 v007 rims wrap the ring-A vertex 58 (border up to 13 mm off a plane). Such an opening is accepted
  only as a vertical rectangle with straight vertical jambs; the window frame and capsule go on the jamb-to-jamb
  chord plane (all 4 frame corners on the rim corners) and the rim sagitta is reported per opening (`bent`);
* frame depth = continuous outer jamb of each Revit window (as 63C), frame front at the end of the reveal [D356];
* type = Revit family (`Окн_Окн_<n> Ств <series>`) + measured W x H; a window whose name does not parse is listed
  and the plan stops (rule 1a, #1676);
* single-row series (`Стандарт`): Revit has one glass pane per bay from sill frame to head frame, no transom and no
  upper pane; its fields are the measured bays and the head face is H - pane top (`single_row`), never invented;
* capsule depth [D205] 1.0 m, except the 8 capsules of the inner-corner pairs (`SHALLOW`, Стандарт 1.00 on the two
  angled walls at +24.45/+40.20) that cross at 1.0 m: 0.9 m (Artem 2026-11-20, card t_1e388df4); the crossing check
  still runs on every pair;
* windows narrower/wider than the accepted opening are fitted into it (Artem 2026-11-20: expected, the window is cut
  into the opening; listed as `fitted`, not a defect);
* AC baskets: every Revit basket entirely inside the band becomes one low-poly closed box (6 quads) on its Revit
  bounding box, min-area rectangle in plan (Artem 2026-11-20); baskets crossing the band edge are not built.
Writes STAGE2.json only when it does not exist yet.
"""
import argparse
import collections
import json
import math
import os
import re
import sys
from pathlib import Path

import numpy as np

HELPERS = Path(__file__).resolve().parents[3] / 'POLY63-A' / 'stage2-1619' / 'hooks'
sys.path.insert(0, str(HELPERS))
import stage2_plan as a  # noqa: E402

PLANE_TOL_M = 0.002       # openings_core default: a planar rim
BENT_TOL_M = 0.015        # recognition tolerance for the known bent rims; each one is checked below
TYPE_RE = re.compile(r'(Окн_Окн_[0-9]+ Ств (?:Комфорт|Стандарт)) ')
NAME = '63B'
SHALLOW = {210, 211, 226, 227, 373, 374, 389, 390}   # stage-2 opening numbers of the crossing inner-corner pairs
SHALLOW_BODY_IDS = {27, 28, 57, 58, 209, 210, 226, 227}
SHALLOW_DEPTH_M = 0.9
BASKET_MAT = 'AC_Basket'


def glass_axis(tri):
    """Unit wall direction of a Revit window from its dominant vertical face normal (area weighted, 0.1 deg)."""
    t = np.asarray(tri, dtype=float)
    n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    area = np.linalg.norm(n, axis=1)
    keep = (area > 1e-9) & (np.abs(n[:, 2]) < 0.01 * np.maximum(area, 1e-12))
    if not keep.any():
        raise ValueError('window without vertical faces')
    n, area = n[keep] / area[keep, None], area[keep]
    ang = np.degrees(np.arctan2(n[:, 1], n[:, 0])) % 180.0
    bins = np.round(ang, 1) % 180.0
    weight = collections.Counter()
    for b, w in zip(bins, area):
        weight[float(b)] += float(w)
    peak = max(weight, key=lambda b: (weight[b], -b))
    d = (ang - peak + 90.0) % 180.0 - 90.0
    sel = np.abs(d) <= 0.3
    theta = math.radians(peak + float(np.average(d[sel], weights=area[sel])))
    return np.array([math.sin(theta), -math.cos(theta)])


def jamb_depth(tri, u):
    """Depth of the largest edge-connected part (the continuous outer jamb), as 63C: sill flashing excluded."""
    adjacency = collections.defaultdict(set)
    for vertices in np.round(np.asarray(tri, dtype=float), 5):
        pts = list(map(tuple, vertices))
        for p in pts:
            adjacency[p].update(pts)
    best = set()
    while adjacency:
        todo, group = [next(iter(adjacency))], set()
        while todo:
            p = todo.pop()
            if p in group:
                continue
            group.add(p)
            todo.extend(adjacency.pop(p, ()))
        if len(group) > len(best):
            best = group
    pts = np.array(sorted(best))
    n = np.array([-u[1], u[0]])
    return round(float(np.ptp(pts[:, :2] @ n)), 3)


def window(tri, name):
    u = glass_axis(tri)
    pca = a.revit_window(tri)['u']
    if float(np.dot(u, pca)) < 0:
        u = -u
    w = a.revit_window(tri, u=u)
    w['depth'] = jamb_depth(tri, u)
    w['name'] = name
    m = TYPE_RE.match(name)
    w['family'] = m[1] if m else None
    return w


def chord_opening(o):
    """A bent rim as a vertical rectangle on the jamb-to-jamb chord plane. Raises ValueError when it is not one."""
    bd = np.asarray(o['border'], dtype=float)
    x0 = np.asarray(o['frame']['x'], dtype=float)
    s = (bd - bd.mean(0)) @ x0
    lo, hi = bd[np.abs(s - s.min()) < 1e-4], bd[np.abs(s - s.max()) < 1e-4]
    for jamb in (lo, hi):
        if len(jamb) != 2 or np.linalg.norm(jamb[0, :2] - jamb[1, :2]) > 1e-4:
            raise ValueError('opening {}: bent rim without two vertical jambs'.format(o['id']))
    z0, z1 = bd[:, 2].min(), bd[:, 2].max()
    if np.abs(bd[:, 2] - z0).min() > 1e-4 or not np.all((np.abs(bd[:, 2] - z0) < 1e-4) | (np.abs(bd[:, 2] - z1) < 1e-4)):
        raise ValueError('opening {}: bent rim is not a horizontal head/sill pair'.format(o['id']))
    pa, pb = lo[0][:2], hi[0][:2]
    x = np.array([*(pb - pa) / np.linalg.norm(pb - pa), 0.0])
    z = np.array([x[1], -x[0], 0.0])
    if float(np.dot(z, o['frame']['z'])) < 0:
        z = -z
    corners = np.array([[*pa, z0], [*pb, z0], [*pb, z1], [*pa, z1]])
    origin = corners.mean(0)
    sag = (bd - origin) @ z  # + = rim point on the street side of the chord plane
    frame = {'origin': origin.tolist(), 'x': x.tolist(), 'y': [0.0, 0.0, 1.0], 'z': z.tolist()}
    return dict(o, frame=frame, border=corners.tolist(), w=round(float(np.linalg.norm(pb - pa)), 6),
                h=round(float(z1 - z0), 6)), {
        'opening_id': o['id'], 'sill_z': round(float(z0), 3), 'chord_w': round(float(np.linalg.norm(pb - pa)), 4),
        'rim_off_street_mm': round(float(sag.max()) * 1000, 1), 'rim_off_inside_mm': round(float(-sag.min()) * 1000, 1)}


def plan_rect(xy):
    """Minimum-area rectangle of plan points: (corners 4x2 counter-clockwise, unit axis u)."""
    pts = sorted(set(map(tuple, np.round(np.asarray(xy, dtype=float), 6))))
    if len(pts) < 3:
        raise ValueError('basket without plan extent')

    def turn(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])

    def half(seq):
        h = []
        for p in seq:
            while len(h) >= 2 and turn(h[-2], h[-1], p) <= 0:
                h.pop()
            h.append(p)
        return h[:-1]
    hull = np.array(half(pts) + half(pts[::-1]), dtype=float)
    best = None
    for k in range(len(hull)):
        e = hull[(k + 1) % len(hull)] - hull[k]
        if np.linalg.norm(e) < 1e-9:
            continue
        u = e / np.linalg.norm(e)
        n = np.array([-u[1], u[0]])
        su, sn = hull @ u, hull @ n
        area = float(np.ptp(su) * np.ptp(sn))
        if best is None or area < best[0] - 1e-12:
            best = (area, u, n, su.min(), su.max(), sn.min(), sn.max())
    if best is None:
        raise ValueError('basket without plan extent')
    _, u, n, u0, u1, n0, n1 = best
    corners = np.array([u * p + n * q for p, q in ((u0, n0), (u1, n0), (u1, n1), (u0, n1))])
    return corners, u


def basket_box(tri, name):
    """Closed low-poly box (8 verts, 6 outward quads) on the Revit bounding box of one AC basket."""
    t = np.asarray(tri, dtype=float).reshape(-1, 3)
    corners, _ = plan_rect(t[:, :2])
    z0, z1 = float(t[:, 2].min()), float(t[:, 2].max())
    verts = [[round(float(x), 6), round(float(y), 6), round(z, 6)] for z in (z0, z1) for x, y in corners]
    faces = [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
    size = [round(float(np.linalg.norm(corners[1] - corners[0])), 3),
            round(float(np.linalg.norm(corners[3] - corners[0])), 3), round(z1 - z0, 3)]
    return {'name': name, 'collection': 'Stage2_Baskets', 'verts': verts, 'faces': faces,
            'mats': [BASKET_MAT] * 6}, size


def simplify_rim(bd, tol=1e-4):
    """Rim corners only: drop rim vertices that lie on the straight segment of their neighbours (body T-junctions
    on the opening contour). The capsule then gets a 4-corner rim and a quad back instead of an ear-clipped fan."""
    pts = [np.asarray(p, dtype=float) for p in bd]
    changed = True
    while changed and len(pts) > 3:
        changed = False
        for k in range(len(pts)):
            p, q, r = pts[k - 1], pts[k], pts[(k + 1) % len(pts)]
            e = r - p
            if np.linalg.norm(e) > 1e-9 and np.linalg.norm(np.cross(e, q - p)) / np.linalg.norm(e) <= tol \
                    and 0.0 < float(np.dot(q - p, e)) < float(np.dot(e, e)):
                del pts[k]
                changed = True
                break
    return np.array(pts)


def recognise(verts, faces):
    rep = a.openings_core.find_openings_report({'verts': verts, 'faces': faces, 'ref': {'name': 'SM_Body_Main'}},
                                               {'plane_tol_m': BENT_TOL_M})
    out, bent, problems = [], [], []
    for o in rep['openings']:
        if o['status'] != 'ok':
            problems.append('opening {}: {}: {}'.format(o['id'], o['status'], '; '.join(o['why'])))
            continue
        bd = np.asarray(o['border'], dtype=float)
        c = bd.mean(0)
        off = float(np.abs((bd - c) @ np.linalg.svd(bd - c)[2][2]).max())
        if off <= PLANE_TOL_M:
            out.append(o)
            continue
        try:
            o2, row = chord_opening(o)
        except ValueError as exc:
            problems.append(str(exc))
            continue
        out.append(o2)
        bent.append(row)
    return out, bent, problems, rep


def unresolved_types(matches):
    return ['opening {} (body detection ID): Revit window {!r} has no parsable family/type'.format(
        o['id'], w['name']) for o, w, _ in matches if not w['family']]


def profiles(wins):
    out = {}
    for fam in sorted({w['family'] for w in wins}):
        series = fam.split()[-1]
        group = [w for w in wins if w['family'].endswith(series)]
        p = out.setdefault(series, a.measure_profile(group))
        if p['transom_m'] is None and p['face_top_m'] is None and all(
                len({r[1] for r in w['glass']}) == 1 for w in group):
            heads = collections.Counter(round(w['H'] - max(r[3] for r in w['glass']), 3) for w in group)
            p.update(face_top_m=heads.most_common(1)[0][0], transom_m=0.0, single_row=True)
    return out


def fields_of(w, p):
    """Glass fields of one Revit window: 63A frame grid, or the measured bays of a single-row series."""
    if p.get('single_row'):
        return [list(r) for r in sorted(w['glass'])]
    return a.frame_grid(w, p['transom_m'], p['face_top_m'])[0]


def build(dump, crop, band, standard_path):
    std = a.windowgen_core.load_standard(json.load(open(standard_path, encoding='utf-8')))
    verts, faces = a.body_mesh(dump)
    ops, bent, problems, rep = recognise(verts, faces)
    if problems:
        a.stop(problems)
    objs = a.crop_objects(crop, a.KEYS['windows'], band)
    wins = [window(o['tri'], o['name']) for o in objs if o['in_band']]
    matches = a.match_openings(ops, wins)  # stops on unused / doubled / glass-less windows
    bad = unresolved_types(matches)
    bad += ['Revit window {!r}: frame depth {} m outside 0.02..0.4'.format(w['name'], w['depth'])
            for w in wins if not 0.02 < w['depth'] < 0.4]
    if bad:
        a.stop(bad)
    prof = profiles(wins)
    for series, p in prof.items():
        if any(v is None for k, v in p.items() if k != 'samples'):
            a.stop(['{}: cannot measure the frame profile: {}'.format(series, p)])
    bent_ids = {b['opening_id'] for b in bent}
    elements, rows, caps, types, fitted, shallow = [], [], [], collections.Counter(), [], []
    for i, (o, w, dist) in enumerate(matches, 1):
        series = w['family'].split()[-1]
        p = prof[series]
        tkey = '{} {:.2f}x{:.2f}'.format(w['family'], w['W'], w['H'])
        types[tkey] += 1
        fd, Wo, Ho = w['depth'], o['w'], o['h']
        fields = fields_of(w, p)
        fields = a.scale_fields(fields, w['W'], Wo, p['face_m'])
        if float(np.dot(w['u'], np.asarray(o['frame']['x'])[:2])) < 0:
            fields = [[Wo - r, z0, Wo - l, z1] for l, z0, r, z1 in fields]
        entry = {'id': 'W63B_' + tkey.replace(' ', '_'), 'role': 'window', 'width_m': Wo, 'height_m': Ho,
                 'panes_m': fields, 'source': {'occurrences': 1},
                 'frame_profile_m': {k: p[k] for k in ('face_m', 'face_top_m', 'face_bottom_m', 'impost_m')}
                 | {'depth_m': fd}}
        mesh = a.windowgen_core.build_type(entry, std)
        tr = a.winplace_core.placement_rows(o['frame'], mesh['size_m'], mesh['face_axis'], recess_m=fd / 2.0)  # [D356]
        for part, coll in (('frame', 'Stage2_Windows'), ('glass', 'Stage2_Glass')):
            pm = a.windowgen_core.part_mesh(mesh, part)
            elements.append({'name': 'SM_Win_{:03d}_{}'.format(i, part.capitalize()), 'collection': coll,
                             'opening': i, 'verts': [[round(c, 6) for c in a.winplace_core.apply_rows(tr, q)]
                                                     for q in pm['verts']],
                             'faces': pm['faces'], 'mats': [a.MAT_NAMES[m] for m in pm['mat_ids']]})
        bd = np.asarray(o['border'], dtype=float)
        front = [a.winplace_core.apply_rows(tr, q) for q in ([0, 0, 0], [Wo, 0, 0], [Wo, 0, Ho], [0, 0, Ho])]
        fit = max(float(np.min(np.linalg.norm(bd - np.asarray(q), axis=1))) for q in front)
        dw, dh = round(Wo - w['W'], 4), round(Ho - w['H'], 4)
        if abs(dw) > 0.002 or abs(dh) > 0.002 or fit > 0.002:
            fitted.append({'opening': i, 'type': tkey, 'dw_m': dw, 'dh_m': dh, 'fit_corner_mm': round(fit * 1000, 2)})
        zin = np.asarray(o['frame']['z'], dtype=float)
        cap_op = dict(o, id=i, border=(simplify_rim(bd) - zin * fd).tolist(), depth=o['depth'] + fd)
        copts = {'frame_depth_m': fd}
        if i in SHALLOW:
            copts['interior_depth_m'] = SHALLOW_DEPTH_M
            shallow.append({'opening': i, 'body_opening_id': o['id'], 'sill_z': round(float(bd[:, 2].min()), 3),
                            'type': tkey})
        cap = a.quad_back(a.capsule_core.planar_capsule(cap_op, a.capsule_core.options(copts)))
        cap = dict(cap, name=a.capsule_core.capsule_name(NAME, i))
        chk = a.capsule_core.check_capsule(cap)
        if chk['bad_edges'] or chk['open_off_rim'] or chk['closed_open_edges'] or not chk['inward']:
            a.stop(['capsule opening {}: {}'.format(i, chk)])
        caps.append((cap, float(bd[:, 2].min()), i))
        elements.append({'name': cap['name'], 'collection': 'Stage2_Capsules', 'opening': i,
                         'verts': [[round(c, 6) for c in v] for v in cap['verts']], 'faces': cap['faces'],
                         'mats': [a.capsule_core.MATERIAL] * len(cap['faces'])})
        rows.append({'opening': i, 'body_opening_id': o['id'], 'type': tkey, 'revit': w['name'], 'w': Wo, 'h': Ho,
                     'reveal_m': o['depth'], 'frame_depth_m': fd, 'revit_dist_m': round(dist, 3),
                     'fit_corner_mm': round(fit * 1000, 2), 'bent': o['id'] in bent_ids,
                     'capsule_depth_m': SHALLOW_DEPTH_M if i in SHALLOW else 1.0,
                     'sill_z': round(float(bd[:, 2].min()), 3)})
    overlaps = []
    for k, (ca, za, ia) in enumerate(caps):
        for cb, zb, ib in caps[k + 1:]:
            if abs(za - zb) < 0.01 and (a.capsule_core.mesh_hits(ca, cb, 1e-4) or
                                       a.capsule_core.same_wall_overlap(ca, cb, 1e-4)):
                overlaps.append('capsules {} x {} cross'.format(ia, ib))
    if {s['body_opening_id'] for s in shallow} != SHALLOW_BODY_IDS:
        overlaps.append('0.9 m capsules are not the approved inner-corner openings: {}'.format(shallow))
    if overlaps:
        a.stop(overlaps)
    baskets = a.crop_objects(crop, a.KEYS['baskets'], band)
    fit_b = [{'name': b['name'], 'z_min': round(float(b['tri'][:, :, 2].min()), 3),
              'z_max': round(float(b['tri'][:, :, 2].max()), 3)} for b in baskets
             if band[0] <= b['tri'][:, :, 2].min() and b['tri'][:, :, 2].max() <= band[1]]
    inside = [b for b in baskets if band[0] <= b['tri'][:, :, 2].min() and b['tri'][:, :, 2].max() <= band[1]]
    for k, (b, row) in enumerate(zip(inside, fit_b), 1):
        el, row['size_m'] = basket_box(b['tri'], 'SM_ACBasket_{:02d}'.format(k))
        row['object'] = el['name']
        elements.append(el)
    nf = collections.Counter(len(f) for e in elements for f in e['faces'])
    report = {'stage': 'stage2: windows + capsules on 63B v007 (body untouched)', 'body_dump': os.path.basename(dump),
              'band_m': list(band), 'openings': {'ok': len(matches), 'rejected': len(rep['rejected']),
                                                 'bent': len(bent)},
              'bent': bent, 'revit_windows_in_band': len(wins), 'types': dict(sorted(types.items())),
              'frame_profile_m': prof, 'frame_depth_m': dict(collections.Counter(r['frame_depth_m'] for r in rows)),
              'fitted': fitted, 'fitted_note': 'expected: window fitted into the accepted opening (Artem 2026-11-20)',
              'capsules': {'made': len(caps), 'overlaps': 0, 'check_bad': 0, 'depth_m': 1.0,
                           'shallow_0_9_m': shallow},
              'baskets': {'fit_in_band': len(fit_b), 'fit': fit_b, 'total': len(baskets), 'built': len(inside),
                          'form': 'low-poly box on the Revit bbox (Artem 2026-11-20)'},
              'faces': {'total': sum(nf.values()), 'quads': nf.get(4, 0), 'tris': nf.get(3, 0),
                        'ngons': sum(v for k, v in nf.items() if k > 4)},
              'elements': len(elements), 'rows': rows}
    return report, elements


def write_plan(output, report, elements):
    payload = json.dumps({'report': report, 'elements': elements}, ensure_ascii=False, allow_nan=False)
    with Path(output).open('x', encoding='utf-8') as stream:
        stream.write(payload)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('dump')
    ap.add_argument('crop')
    ap.add_argument('out')
    ap.add_argument('--band', nargs=2, type=float, default=[4.65, 51.90])
    ap.add_argument('--standard', default=os.path.join(a.ROOT, 'library', 'windows', 'standard.json'))
    args = ap.parse_args(argv)
    if Path(args.out).exists():
        sys.exit('STAGE2.json exists; write a new version: ' + args.out)
    report, elements = build(args.dump, args.crop, args.band, args.standard)
    write_plan(args.out, report, elements)
    print(json.dumps({k: v for k, v in report.items() if k not in ('rows', 'fitted', 'bent')},
                     ensure_ascii=False)[:4000])
    return 0


if __name__ == '__main__':
    sys.exit(main())
