"""Hook `after` stage `body` (#1619 polygon stage 2, tower 63A): windows + glazing capsules on the ACCEPTED body.

Pattern: n/a | new-case: stage-2 inset plan of the training polygon; every step calls the stage owners.

uv run python stage2_plan.py BODY_DUMP.npz CROP.npz STAGE2.json [--keys keys.json] [--band 10.15 47.95]

The body is never rebuilt or edited: BODY_DUMP.npz is dump_mesh.py of the accepted stage-1 FBX (63A v005) and is
only read. Per opening (Artem 2026-11-18, #1619 stage rules; D336 split):
* the opening = `openings_core.find_openings_report` on the body (the ONE recognition): the border is the back end
  of the stage-1 reveal = the outer face of the Revit window frame (stage 1 cut the reveal to that depth);
* the window type = the uniquely nearest Revit window object, strictly under 0.6 m from the opening centre
  (crop of the .rvt export, read-only). Every in-band window must be used once. Its
  frame grid is measured from the Revit glass: glass = flat rectangles present twice at a depth step of 20-35 mm
  (the two glass faces); bays = the lower glass row; mullions/transoms = the gaps between bays/rows (geometry,
  as in Revit); sashes = texture (inside the bay, not modelled);
* the window mesh = `windowgen_core.build_type` (frame + glass as separate parts, quads) with the Revit frame
  profile, placed by `winplace_core.placement_rows` with the frame front on the border plane;
* the capsule = `capsule_core.plan` on the opening moved to the frame back (rim on the frame middle, 100 mm
  outline, 1.0 m deep, no niche in the wall); its rectangular back (two triangles) becomes one quad.
AC baskets: the crop's baskets inside the band are listed; none -> `baskets.status = "none_in_band"`, nothing is
invented. Lists blockers on stderr and exits nonzero without writing a plan. Refuses STAGE2.json equal to an input.
"""
import argparse
import collections
import json
import math
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..'))
sys.path.insert(0, ROOT)
from adapters.max.agr_tools import capsule_core, openings_core, windowgen_core, winplace_core  # noqa: E402

KEYS = {'windows': ['Окн_Окн_', 'Окн_ББлок'], 'baskets': ['Корзина для кондиционер']}
GLASS_STEP = (0.020, 0.035)  # depth step between the two faces of one Revit glass pane, metres
MATCH_LIMIT_M = 0.6  # strict upper bound, before rounding
MAT_NAMES = {windowgen_core.MAT_FACE: 'WIN_Frame', windowgen_core.MAT_BACK: 'WIN_Frame_Back',
             windowgen_core.MAT_OPAQUE: 'WIN_Infill', windowgen_core.MAT_GLASS: 'WIN_Glass'}


def body_mesh(path):
    d = np.load(path, allow_pickle=True)
    verts = d['verts'].tolist()
    faces, k = [], 0
    for c in d['fn'].tolist():
        faces.append([int(i) for i in d['fi'][k:k + c]])
        k += c
    return verts, faces


def crop_objects(path, prefixes, band):
    d = np.load(path, allow_pickle=True)
    names, obj, tri = d['names'], d['obj'], d['tri']
    want = [i for i, n in enumerate(names) if any(p in str(n) for p in prefixes)]
    order = np.argsort(obj, kind='stable')
    so = obj[order]
    out = []
    for i in want:
        a, b = np.searchsorted(so, i), np.searchsorted(so, i, side='right')
        t = tri[order[a:b]]
        if not len(t) or not np.isfinite(t).all():
            stop(['Revit object #{} {!r}: empty or non-finite triangles'.format(i, str(names[i]))])
        zc = float(t[:, :, 2].mean())
        out.append({'name': str(names[i]), 'tri': t, 'in_band': band[0] < zc < band[1]})
    return out


def revit_window(tri, u=None):
    """Local frame and glass rectangles [u0, z0, u1, z1] (from the bottom-left of the window) of one Revit window.
    `u` (unit wall direction) overrides the PCA axis; None keeps the 63A behaviour."""
    p = tri.reshape(-1, 3)
    xy = p[:, :2] - p[:, :2].mean(0)
    if u is None:
        _, vec = np.linalg.eigh(xy.T @ xy)
        u = vec[:, 1]
    u = np.asarray(u, dtype=float)
    nrm = np.array([-u[1], u[0]])
    lu, ln = xy @ u, xy @ nrm
    lu, ln, lz = lu - lu.min(), ln - ln.min(), p[:, 2] - p[:, 2].min()
    tu, tz, tn = lu.reshape(-1, 3), lz.reshape(-1, 3), ln.reshape(-1, 3)
    flat = np.ptp(tn, axis=1) < 1e-3
    rects = collections.defaultdict(set)
    for f in np.nonzero(flat)[0]:
        r = (round(float(tu[f].min()), 3), round(float(tz[f].min()), 3),
             round(float(tu[f].max()), 3), round(float(tz[f].max()), 3))
        if r[2] - r[0] > 0.1 and r[3] - r[1] > 0.1:
            rects[r].add(round(float(tn[f, 0]), 3))
    glass = sorted(r for r, ns in rects.items()
                   if any(GLASS_STEP[0] <= b - a <= GLASS_STEP[1] for a in ns for b in ns))
    return {'centre': p.mean(0), 'min': p.min(0), 'max': p.max(0), 'u': u,
            'W': round(float(lu.max()), 3), 'H': round(float(lz.max()), 3), 'D': round(float(ln.max()), 3),
            'glass': glass}


def frame_grid(win, impost, face_top):
    """Frame-grid fields (glass bays) of one Revit window: bays = the lower glass row; above each bay one field
    from the transom (impost wide, as in Revit) to the head frame. Sash profiles stay texture."""
    g = win['glass']
    z0 = min(r[1] for r in g)
    lower = sorted(r for r in g if abs(r[1] - z0) < 0.002)
    fields = []
    for r in lower:
        fields.append([r[0], r[1], r[2], r[3]])
        fields.append([r[0], round(r[3] + impost, 4), r[2], round(win['H'] - face_top, 4)])
    return fields, lower


def measure_profile(wins):
    """Frame profile from all Revit windows: side face = lower x0, bottom = lower z0, impost = gap between
    neighbour bays, head = H - z1 of a fixed upper pane spanning a bay, transom = its z0 - lower z1."""
    side, bottom, impost, head, transom = [], [], [], [], []
    for w in wins:
        g = w['glass']
        if not g:
            continue
        z0 = min(r[1] for r in g)
        lower = sorted(r for r in g if abs(r[1] - z0) < 0.002)
        side.append(lower[0][0])
        bottom.append(z0)
        impost += [round(b[0] - a[2], 3) for a, b in zip(lower, lower[1:])]
        for r in g:
            if r not in lower and any(abs(r[0] - b[0]) < 0.002 and abs(r[2] - b[2]) < 0.002 for b in lower):
                head.append(round(w['H'] - r[3], 3))
                transom.append(round(r[1] - lower[0][3], 3))
    mode = lambda xs: collections.Counter(xs).most_common(1)[0][0] if xs else None  # noqa: E731
    return {'face_m': mode(side), 'face_bottom_m': mode(bottom), 'impost_m': mode(impost) or mode(transom),
            'face_top_m': mode(head), 'transom_m': mode(transom),
            'samples': {'side': len(side), 'impost': len(impost), 'head': len(head)}}


def scale_fields(fields, w_src, w_new, face):
    """Interior bay edges follow the mullion centres scaled to the opening width; outer edges stay on the frame."""
    if abs(w_src - w_new) < 1e-6:
        return [list(f) for f in fields]
    k = (w_new - 2 * face) / (w_src - 2 * face)

    def sx(x):
        return round(face + (x - face) * k, 4)
    return [[sx(f[0]), f[1], sx(f[2]), f[3]] for f in fields]


def quad_back(row):
    """capsule_core triangulates the back by ear clipping; a rectangular back (2 triangles over 4 rim corners)
    becomes one quad with the same winding (D312: quads where possible)."""
    faces = row['faces']
    tris = [f for f in faces if len(f) == 3]
    if len(tris) != 2:
        return row
    a, b = tris
    shared = set(a) & set(b)
    if len(shared) != 2:
        return row
    (oa,), (ob,) = set(a) - shared, set(b) - shared
    i = a.index(oa)
    quad = [a[i], a[(i + 1) % 3], ob, a[(i + 2) % 3]]
    if not (quad[1] in shared and quad[3] in shared):
        return row
    out = dict(row, faces=[f for f in faces if len(f) != 3] + [quad])
    return out


def stop(problems):
    sys.exit('Stage 2 STOP: confirm the listed opening types or correct the source/check failures before retrying.\n'
             + '\n'.join(problems))


def claim_openings(openings, n_sources, pick, source_label, check_claimed=None):
    """THE stage-2 opening -> window-type resolution of every POLY63 tower (63A here, 63C tools/windows/stage2.py, 63B from
    the start; #1714, duplicate_guard rule `poly63-window-match`). Tower-specific matching stays in `pick`.

    pick(opening, centre) -> (source index, info) resolves the opening to exactly one source, or (None, problem text).
    Every one of the `n_sources` sources must be claimed exactly once; check_claimed(index, owners) -> problem text
    or None checks a claimed source (63A: measured glass; 63C: resolved Revit family/type name).
    All problems are listed first, then `stop` exits BEFORE anything is built or written (#1676/#1695); a collision
    is never reassigned to a second choice. Returns [(opening + centre, source index, info)] in opening order.
    """
    problems, matches = [], []
    claims = collections.defaultdict(list)
    if not openings:
        problems.append('no openings recognized in the body')
    for o in openings:
        border = np.asarray(o['border'], dtype=float)
        label = 'opening {} (body detection ID)'.format(o['id'])
        if not border.size or not np.isfinite(border).all():
            problems.append(label + ': empty or non-finite border')
            continue
        centre = border.mean(0)
        label += ' centre_m={}'.format(centre.tolist())
        if o['status'] != 'ok':
            problems.append('{}: {}: {}'.format(label, o['status'], '; '.join(o['why'])))
            continue
        j, info = pick(o, centre)
        if j is None:
            problems.append('{}: {}'.format(label, info))
            continue
        claims[j].append(label)
        matches.append((dict(o, centre=centre), j, info))

    for j in range(n_sources):
        label = source_label(j)
        owners = claims.get(j, [])
        if not owners:
            problems.append(label + ': unused')
        elif len(owners) > 1:
            problems.append(label + ': matched more than once: ' + '; '.join(owners))
        problem = check_claimed(j, owners) if owners and check_claimed else None
        if problem:
            problems.append('{}: {}'.format(label, problem))
    if problems:
        stop(problems)
    return matches


def match_openings(openings, wins):
    """63A pick: the uniquely nearest Revit window, strictly under MATCH_LIMIT_M from the opening centre."""
    wc = np.array([w['centre'] for w in wins])

    def nearest(o, centre):
        if not wins:
            return None, 'no Revit window in band'
        distances = np.linalg.norm(wc - centre, axis=1)
        if not np.isfinite(distances).all():
            return None, 'non-finite Revit match distances'
        distance = float(distances.min())
        if distance >= MATCH_LIMIT_M:
            return None, 'nearest Revit window at {:.6g} m; requires < {} m'.format(distance, MATCH_LIMIT_M)
        candidates = np.flatnonzero(distances == distance)
        if len(candidates) != 1:
            return None, 'tied nearest windows: {}'.format(', '.join(
                '#{} {!r}'.format(j + 1, wins[j]['name']) for j in candidates))
        return int(candidates[0]), distance

    claimed = claim_openings(
        openings, len(wins), nearest,
        lambda j: 'Revit window #{} {!r} centre_m={}'.format(j + 1, wins[j]['name'], wins[j]['centre'].tolist()),
        lambda j, owners: None if wins[j]['glass'] else 'no measured glass panes for ' + '; '.join(owners))
    matches = [(o, wins[j], distance) for o, j, distance in claimed]
    cx, cy = wc[:, 0].mean(), wc[:, 1].mean()
    matches.sort(key=lambda m: (round(m[0]['centre'][2], 1),
                                math.atan2(m[0]['centre'][1] - cy, m[0]['centre'][0] - cx)))
    return matches


def refuse_input_output(out, inputs):
    resolved = os.path.normcase(os.path.realpath(out))
    for path in inputs:
        if resolved == os.path.normcase(os.path.realpath(path)) or (
                os.path.exists(out) and os.path.samefile(out, path)):
            sys.exit('STAGE2.json must not be an input: ' + path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('dump')
    ap.add_argument('crop')
    ap.add_argument('out')
    ap.add_argument('--keys')
    ap.add_argument('--band', nargs=2, type=float, default=[10.15, 47.95])
    ap.add_argument('--standard', default=os.path.join(ROOT, 'library', 'windows', 'standard.json'))
    ap.add_argument('--name', default='63A')
    a = ap.parse_args(argv)
    inputs = [a.dump, a.crop, a.standard] + ([a.keys] if a.keys else [])
    refuse_input_output(a.out, inputs)
    if not all(math.isfinite(z) for z in a.band) or a.band[0] >= a.band[1]:
        stop(['band must have two finite, increasing limits'])
    keys = dict(KEYS)
    if a.keys:
        keys.update({k: v for k, v in json.load(open(a.keys, encoding='utf-8')).items() if k in KEYS})
    standard = windowgen_core.load_standard(json.load(open(a.standard, encoding='utf-8')))

    verts, faces = body_mesh(a.dump)
    if not np.isfinite(verts).all():
        stop(['body vertices contain non-finite coordinates'])
    rep = openings_core.find_openings_report({'verts': verts, 'faces': faces, 'ref': {'name': 'SM_Body_Main'}})

    objs = crop_objects(a.crop, keys['windows'], a.band)
    wins = [dict(revit_window(o['tri']), name=o['name']) for o in objs if o['in_band']]
    matches = match_openings(rep['openings'], wins)
    prof = measure_profile(wins)
    missing = [k for k, v in prof.items() if v is None]
    if missing:
        stop(['opening {}: cannot measure {} from Revit window {!r}'.format(
            o['id'], ', '.join(missing), w['name']) for o, w, _ in matches])
    depth = collections.Counter(w['D'] for w in wins).most_common(1)[0][0]
    baskets = crop_objects(a.crop, keys['baskets'], a.band)
    in_band_b = [b['name'] for b in baskets if b['in_band']]
    out_band_b = sorted(collections.Counter(round(float(b['tri'][:, :, 2].min()), 2) for b in baskets
                                            if not b['in_band']).items())

    elements, rows, misfit, types = [], [], [], collections.Counter()
    cap_ops = []
    for i, (o, w, distance) in enumerate(matches, 1):
        tkey = '{} W{:.2f}'.format(str(w['name']).split(' Ств')[0] + ' Ств', w['W'])
        types[tkey] += 1
        fields, _ = frame_grid(w, prof['transom_m'], prof['face_top_m'])
        Wo, Ho = o['w'], o['h']
        fields = scale_fields(fields, w['W'], Wo, prof['face_m'])
        entry = {'id': 'W63A_' + tkey.replace(' ', '_'), 'role': 'window', 'width_m': Wo, 'height_m': Ho,
                 'panes_m': fields, 'source': {'occurrences': 1},
                 'frame_profile_m': {'face_m': prof['face_m'], 'face_top_m': prof['face_top_m'],
                                     'face_bottom_m': prof['face_bottom_m'], 'impost_m': prof['impost_m'],
                                     'depth_m': depth}}
        mesh = windowgen_core.build_type(entry, standard)
        tr = winplace_core.placement_rows(o['frame'], mesh['size_m'], mesh['face_axis'], recess_m=depth / 2.0)
        for part, coll in (('frame', 'Stage2_Windows'), ('glass', 'Stage2_Glass')):
            pm = windowgen_core.part_mesh(mesh, part)
            wv = [[round(c, 6) for c in winplace_core.apply_rows(tr, p)] for p in pm['verts']]
            elements.append({'name': 'SM_Win_{:03d}_{}'.format(i, part.capitalize()), 'collection': coll,
                             'opening': i, 'verts': wv, 'faces': pm['faces'],
                             'mats': [MAT_NAMES[m] for m in pm['mat_ids']]})
        # fit: the frame front corners on the border corners
        front = [winplace_core.apply_rows(tr, p) for p in ([0, 0, 0], [Wo, 0, 0], [Wo, 0, Ho], [0, 0, Ho])]
        bd = np.array(o['border'])
        fit = max(float(np.min(np.linalg.norm(bd - np.array(p), axis=1))) for p in front)
        dw, dh = round(Wo - w['W'], 4), round(Ho - w['H'], 4)
        row = {'opening': i, 'type': tkey, 'w': Wo, 'h': Ho, 'reveal_m': o['depth'], 'revit_dist_m': round(
            distance, 3), 'dw_m': dw, 'dh_m': dh, 'fit_corner_mm': round(fit * 1000, 2),
            'type_status': mesh['status'], 'fields': fields}
        rows.append(row)
        if abs(dw) > 0.002 or abs(dh) > 0.002 or fit > 0.002:
            misfit.append({k: row[k] for k in ('opening', 'type', 'w', 'dw_m', 'dh_m', 'fit_corner_mm',
                                               'revit_dist_m')})
        zin = np.array(o['frame']['z'])
        cap_ops.append(dict(o, id=i, border=[(np.array(p) - zin * depth).tolist() for p in o['border']],
                            depth=o['depth'] + depth, centre=None))
    cp = capsule_core.plan([{'handle': 1, 'name': a.name, 'openings': cap_ops}], {'frame_depth_m': depth})
    capsule_problems = ['capsule: ' + text for text in cp['ambiguous']]
    if not capsule_problems:
        made = collections.Counter(r['opening'] for r in cp['rows'])
        expected = collections.Counter(range(1, len(matches) + 1))
        capsule_problems.extend('capsule opening {}: expected one row, got {}'.format(i, made[i])
                                for i in sorted(expected) if made[i] != 1)
        capsule_problems.extend('capsule opening {}: unexpected row'.format(i) for i in sorted(made - expected)
                                if i not in expected)
    for r in cp['rows']:
        r = quad_back(r)
        chk = capsule_core.check_capsule(dict(r, faces=r['faces']))
        if chk['open_off_rim'] or chk['closed_open_edges'] or chk['bad_edges'] or not chk['inward']:
            capsule_problems.append('capsule opening {} ({}): {}'.format(r['opening'], r['name'], chk))
        elements.append({'name': r['name'], 'collection': 'Stage2_Capsules', 'opening': r['opening'],
                         'verts': [[round(c, 6) for c in v] for v in r['verts']], 'faces': r['faces'],
                         'mats': [capsule_core.MATERIAL] * len(r['faces'])})
    if capsule_problems:
        stop(capsule_problems)
    nf = collections.Counter(len(f) for e in elements for f in e['faces'])
    report = {
        'stage': 'stage2: windows + capsules (body untouched)', 'body_dump': os.path.basename(a.dump),
        'openings': {'ok': len(matches), 'ambiguous': 0, 'rejected': len(rep['rejected'])},
        'revit_windows_in_band': len(wins), 'types': dict(types), 'frame_profile_m': dict(prof, depth_m=depth),
        'misfit': misfit, 'capsules': {'made': len(cp['rows']), 'ambiguous': [], 'n_ambiguous': 0, 'check_bad': 0},
        'baskets': {'status': 'none_in_band' if not in_band_b else 'in_band', 'in_band': len(in_band_b),
                    'outside_band_by_zmin': out_band_b},
        'faces': {'total': sum(nf.values()), 'quads': nf.get(4, 0), 'tris': nf.get(3, 0),
                  'ngons': sum(v for k, v in nf.items() if k > 4)},
        'elements': len(elements), 'rows': rows}
    payload = json.dumps({'report': report, 'elements': elements}, ensure_ascii=False, allow_nan=False)
    refuse_input_output(a.out, inputs)
    try:
        out = open(a.out, 'r+', encoding='utf-8')  # do not truncate until the opened file is checked
    except FileNotFoundError:
        out = open(a.out, 'x', encoding='utf-8')
    with out:
        for path in inputs:
            if os.path.samestat(os.fstat(out.fileno()), os.stat(path)):
                sys.exit('STAGE2.json must not be an input: ' + path)
        out.write(payload)
        out.truncate()
    print(json.dumps({k: v for k, v in report.items() if k != 'rows'}, ensure_ascii=False)[:3000])
    return 0


if __name__ == '__main__':
    sys.exit(main())
