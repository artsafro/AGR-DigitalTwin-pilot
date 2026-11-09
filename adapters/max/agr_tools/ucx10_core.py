"""new-case: AGR Tools 1.0 (#1024) UCX gap logic (`ucx.gap`, station 1.0.27), stdlib only. owned by branch S
(improve/issue-1024-deliver).

Pure logic for `ucx_gap` (ucx.gap); no pymxs. The glue (ucx10_max.py) reads every UCX piece in scope as a world
mesh in METRES (host_max.MaxHost.mesh: units.SystemScale, never units.decodeValue) and writes the planned pieces
on export copies. The core never takes a host object.

Source (lab 1.0 L13, docs/experiments/ucx.gap.md, measured in Max 2024; no code copied, #853): GeoAGR UCX Move
LMB `GeoAGR.ms:61446-61599` casts rays from face centres along the normal and, for a hit `d < 0.002` or
`0.002 < d <= 0.03` SYSTEM units, moves the face vertices by `(d - 0.005) / 2`; MultiPass RMB `:61601` / `:61619`
judges an overlap with `facesOverlap` `:62188` by AABB (runtime-finding T10-01). Team zavod method of planes
(collision_splitter_ucx.ms SHA256 7f5261ef3682c21fef7363feb1d3dcaaecd6839a00f81940faae461d70d23453): 4.00 mm
on every scene (team-audit T04) - the idea taken here.

Kept from the source: the planes of a pair of neighbours move apart by half of the missing gap each (both sides
equally), convexity is kept, a repeat changes nothing, a foreign `UCX_*` (another mesh) is never touched.

Fixed defects (each has a regression test in tests/max_tools/test_agr_tools_deliver.py, RED on a model of the
source, GREEN here):
1. touching (0) and overlapping (< 0) neighbours were not found: the separation is the SAT lower bound over the
   face normals and edge-edge axes of both convex pieces, so 0 and negative gaps are found;
2. the target was a constant 5 mm and gaps of 10-25 mm were SHRUNK to it: the target is a metre parameter
   (default 4 mm, 2-10 mm, D098) and a gap is only ever increased, never reduced;
3. a centimetre scene changed nothing (thresholds in system units): every distance is in metres;
4. Alt pushed touching pieces apart as a whole and deepened an overlap: there is no such mode;
5. MultiPass judged an intersection by AABB (T10-01): the check is SAT on the convex pieces, an AABB touch
   without intersection is not an intersection.
Plan mode `copy`: the apply writes the pieces on export copies (layer AGR_export); originals stay byte-equal.
"""
import math
import re

TOOL = 'ucx.gap'
GAP_DEFAULT_M = 0.004       # D098 / #1024 «редакция 1»: default 4 mm
GAP_MIN_M = 0.002           # D098: 2 mm .. 1 cm
GAP_MAX_M = 0.010
OVERLAP_MAX_M = 0.02        # deeper overlap is a modelling error: ambiguous, never cut silently
MIN_THICK_M = 0.02          # ucx_core.MIN_THICK_M: a cut piece thinner than this is refused
TOL_M = 1e-5                # 0.01 mm: L13 acceptance «>= 4.00 mm +- 0.01»
PLANE_TOL = 1e-9
OPTION_KEYS = {'gap_m', 'overlap_max_m', 'mode'}
MODES = ('gap',)
UCX_NAME = re.compile(r'^UCX_(?P<mesh>.+)_(?P<n>\d{2,3})$')
CODES = ('ucx_overlap', 'ucx_touch', 'ucx_gap_small', 'ucx_overlap_deep', 'ucx_too_thin', 'ucx_not_convex',
         'ucx_gap_left')


# ---- options ----------------------------------------------------------------------------------------------
def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(label + ' must be a number in metres')
    return float(value)


def gap_options(options):
    """Validated options: gap_m (target gap in METRES, 0.002..0.010, default 0.004), overlap_max_m (deepest
    overlap that is cut, default 0.02), mode ('gap'; cell/edge splitting is ucx.build's kernel-boxes, 0.3)."""
    opts = dict(options or {})
    extra = set(opts) - OPTION_KEYS
    if extra:
        raise ValueError('unknown ucx.gap options: ' + ', '.join(sorted(extra)))
    mode = opts.get('mode', 'gap')
    if mode not in MODES:
        raise ValueError("ucx.gap mode must be 'gap' (split = ucx.build kernel-boxes / slice-prisms, 0.3)")
    gap = _number(opts.get('gap_m', GAP_DEFAULT_M), 'gap_m')
    if not GAP_MIN_M - 1e-12 <= gap <= GAP_MAX_M + 1e-12:
        raise ValueError('gap_m must be 0.002..0.010 m (D098), got {}'.format(gap))
    deep = _number(opts.get('overlap_max_m', OVERLAP_MAX_M), 'overlap_max_m')
    if not 0.0 <= deep <= 0.1:
        raise ValueError('overlap_max_m must be 0..0.1 m')
    return {'gap_m': gap, 'overlap_max_m': deep, 'mode': mode}


def family(name):
    """Mesh of a `UCX_<mesh>_NN` piece, else None (pairs are only judged inside one family)."""
    m = UCX_NAME.match(str(name))
    return m.group('mesh') if m else None


# ---- vector helpers ---------------------------------------------------------------------------------------
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _unit(a):
    ln = math.sqrt(_dot(a, a))
    return None if ln <= 1e-12 else (a[0] / ln, a[1] / ln, a[2] / ln)


def _hull_core():
    import importlib.util
    import os
    import sys
    name = 'agr_tools_ucx_core'
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                                     'ucx_core.py'))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---- convex pieces ----------------------------------------------------------------------------------------
def piece(verts, tris):
    """Convex piece {verts, tris, normals, edges}: outward unit face normals (coplanar merged) and edge
    directions. A non-convex or open mesh raises ValueError (ucx.triangulate / ucx.build first)."""
    uc = _hull_core()
    chk = uc.convexity(verts, tris)
    if not chk['ok']:
        raise ValueError('not a closed convex piece (convex={}, open edges={})'.format(chk['convex'],
                                                                                     chk['open_edges']))
    pts = [tuple(float(c) for c in p) for p in verts]
    faces = [tuple(int(i) for i in t) for t in tris]
    origin = pts[0]
    vol = sum(_dot(_sub(pts[a], origin), _cross(_sub(pts[b], origin), _sub(pts[c], origin))) for a, b, c in faces)
    sign = 1.0 if vol >= 0 else -1.0
    normals = []
    for a, b, c in faces:
        n = _unit(_cross(_sub(pts[b], pts[a]), _sub(pts[c], pts[a])))
        if n is None:
            continue
        n = (sign * n[0], sign * n[1], sign * n[2])
        if not any(_dot(n, m) > 1 - PLANE_TOL for m in normals):
            normals.append(n)
    edges = []
    for a, b, c in faces:
        for i, j in ((a, b), (b, c), (c, a)):
            e = _unit(_sub(pts[j], pts[i]))
            if e is not None and not any(abs(_dot(e, f)) > 1 - PLANE_TOL for f in edges):
                edges.append(e)
    return {'verts': pts, 'tris': faces, 'normals': normals, 'edges': edges, 'volume': abs(vol) / 6.0}


def _span(p, axis):
    vals = [_dot(axis, v) for v in p['verts']]
    return min(vals), max(vals)


def separation(a, b):
    """SAT lower bound of the distance between convex pieces a and b, metres: (gap, axis from a to b).

    Axes: face normals of both pieces and the edge-edge crosses. gap > 0 separated, 0 touching, < 0 overlapping
    (its depth along the best axis). Exact on face contacts (the zavod method of planes); never an AABB."""
    best, axis = None, None
    cands = list(a['normals']) + [(-n[0], -n[1], -n[2]) for n in b['normals']]
    for ea in a['edges']:
        for eb in b['edges']:
            n = _unit(_cross(ea, eb))
            if n is not None:
                cands.append(n)
                cands.append((-n[0], -n[1], -n[2]))
    for n in cands:
        a_lo, a_hi = _span(a, n)
        b_lo, b_hi = _span(b, n)
        gap = b_lo - a_hi
        # a face axis wins a tie (plane shift), an edge axis only when strictly better
        if best is None or gap > best + 1e-12:
            best, axis = gap, n
    return best, axis


def _clip(p, n, c):
    """Convex piece cut by the half-space n.x <= c (a plane shift when p has a face with normal n)."""
    uc = _hull_core()
    pts = p['verts']
    keep = [v for v in pts if _dot(n, v) <= c + 1e-12]
    seen = set()
    for a, b, cc in p['tris']:
        for i, j in ((a, b), (b, cc), (cc, a)):
            key = (min(i, j), max(i, j))
            if key in seen:
                continue
            seen.add(key)
            di, dj = _dot(n, pts[i]) - c, _dot(n, pts[j]) - c
            if (di < 0 < dj) or (dj < 0 < di):
                t = di / (di - dj)
                keep.append(tuple(pts[i][k] + t * (pts[j][k] - pts[i][k]) for k in range(3)))
    # snap the cut plane exactly (no float creep on a repeat)
    snapped = []
    for v in keep:
        d = _dot(n, v) - c
        if abs(d) < 1e-9:
            v = (v[0] - d * n[0], v[1] - d * n[1], v[2] - d * n[2])
        snapped.append(v)
    verts, tris = uc._convex_hull(snapped)
    return piece([list(v) for v in verts], [list(t) for t in tris])


def _thickness(p, n):
    lo, hi = _span(p, n)
    return hi - lo


def _aabb(p):
    return ([min(v[k] for v in p['verts']) for k in range(3)], [max(v[k] for v in p['verts']) for k in range(3)])


def _aabb_far(a, b, reach):
    (alo, ahi), (blo, bhi) = _aabb(a), _aabb(b)
    return any(blo[k] - ahi[k] > reach or alo[k] - bhi[k] > reach for k in range(3))


def _kind(gap):
    if gap < -TOL_M:
        return 'ucx_overlap'
    if gap <= TOL_M:
        return 'ucx_touch'
    return 'ucx_gap_small'


def plan(pieces, opts):
    """Plan the gap of every neighbour pair of every UCX family.

    pieces: [{handle, name, verts (world METRES), tris}] - the UCX pieces in scope. Returns
    {pieces: {handle: {name, family, changed, verts, tris}}, pairs: [...], findings: {handle: [(code, detail)]},
    ambiguous: [...], skipped: [...], summary}. A pair whose SAT gap is below gap_m (touching and overlapping
    included) gets both planes moved by half of the missing gap; a gap >= gap_m is never changed (only increased,
    never reduced)."""
    if not pieces:
        raise ValueError('no UCX pieces in scope: an empty set is an error, not a pass')
    target, deep = opts['gap_m'], opts['overlap_max_m']
    seen = set()
    for row in pieces:
        if row['handle'] in seen:
            raise ValueError('duplicate handle {}'.format(row['handle']))
        seen.add(row['handle'])
    found, skipped, ambiguous, pairs = {}, [], [], []
    work, fam = {}, {}

    def add(h, code, detail):
        found.setdefault(h, []).append((code, detail))

    for row in sorted(pieces, key=lambda r: (str(r['name']), r['handle'])):
        f = family(row['name'])
        if f is None:
            skipped.append({'item': str(row['name']), 'reason': 'не UCX_<меш>_NN: не кусок коллизии'})
            continue
        try:
            work[row['handle']] = piece(row['verts'], row['tris'])
        except ValueError as exc:
            add(row['handle'], 'ucx_not_convex', '{}: сначала ucx.triangulate / ucx.build'.format(exc))
            continue
        fam.setdefault(f, []).append(row)
    original = dict(work)
    changed = set()
    for f in sorted(fam):
        rows = fam[f]
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                ra, rb = rows[i], rows[j]
                a, b = work[ra['handle']], work[rb['handle']]
                if _aabb_far(a, b, target + TOL_M):
                    continue
                gap0, n = separation(a, b)
                if gap0 >= target - TOL_M:
                    continue
                pair = {'family': f, 'a': ra['name'], 'b': rb['name'], 'gap_before_m': round(gap0, 7),
                        'axis': [round(c, 9) for c in n], 'code': _kind(gap0)}
                detail = '{} {}: {:.3f} мм < {:.3f} мм'
                if gap0 < -deep - TOL_M:
                    pair['action'] = 'ambiguous'
                    for h, other in ((ra['handle'], rb['name']), (rb['handle'], ra['name'])):
                        add(h, 'ucx_overlap_deep', '{}: перекрытие {:.3f} мм > {:.1f} мм: не режется'.format(
                            other, -gap0 * 1000, deep * 1000))
                    ambiguous.append({'item': '{} / {}'.format(ra['name'], rb['name']),
                                      'reason': 'глубокое перекрытие {:.3f} мм'.format(-gap0 * 1000)})
                    pairs.append(pair)
                    continue
                a_hi = _span(a, n)[1]
                b_lo = _span(b, n)[0]
                mid = (a_hi + b_lo) / 2.0
                na = _clip(a, n, mid - target / 2.0)
                nb = _clip(b, (-n[0], -n[1], -n[2]), -(mid + target / 2.0))
                if _thickness(na, n) < MIN_THICK_M or _thickness(nb, n) < MIN_THICK_M:
                    pair['action'] = 'ambiguous'
                    for h in (ra['handle'], rb['handle']):
                        add(h, 'ucx_too_thin', 'после сдвига тоньше {:.0f} мм вдоль оси пары'.format(
                            MIN_THICK_M * 1000))
                    ambiguous.append({'item': '{} / {}'.format(ra['name'], rb['name']),
                                      'reason': 'кусок тоньше {:.0f} мм после сдвига'.format(MIN_THICK_M * 1000)})
                    pairs.append(pair)
                    continue
                gap1, _ = separation(na, nb)
                work[ra['handle']], work[rb['handle']] = na, nb
                changed.update((ra['handle'], rb['handle']))
                pair.update(action='planes', gap_after_m=round(gap1, 7),
                            shift_a_m=round(a_hi - _span(na, n)[1], 7),
                            shift_b_m=round(_span(nb, n)[0] - b_lo, 7))
                pairs.append(pair)
                for h, other in ((ra['handle'], rb['name']), (rb['handle'], ra['name'])):
                    add(h, pair['code'], detail.format(other, {'ucx_overlap': 'перекрытие', 'ucx_touch': 'касание',
                                                               'ucx_gap_small': 'зазор'}[pair['code']],
                                                      gap0 * 1000, target * 1000))
    # final SAT verification on the planned geometry (every pair of every family)
    left = []
    for f in sorted(fam):
        rows = fam[f]
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a, b = work[rows[i]['handle']], work[rows[j]['handle']]
                if _aabb_far(a, b, target + TOL_M):
                    continue
                g, _ = separation(a, b)
                if g < target - TOL_M and not any(p['a'] == rows[i]['name'] and p['b'] == rows[j]['name']
                                                  and p.get('action') == 'ambiguous' for p in pairs):
                    left.append({'a': rows[i]['name'], 'b': rows[j]['name'], 'gap_m': round(g, 7)})
    out = {}
    for f in sorted(fam):
        for row in fam[f]:
            p = work[row['handle']]
            out[row['handle']] = {'name': str(row['name']), 'family': f, 'changed': row['handle'] in changed,
                                  'verts': [[round(c, 9) for c in v] for v in p['verts']],
                                  'tris': [list(t) for t in p['tris']],
                                  'volume_before_m3': round(original[row['handle']]['volume'], 9),
                                  'volume_after_m3': round(p['volume'], 9)}
    summary = {'pieces': len(pieces), 'families': len(fam), 'pairs_fixed': sum(1 for p in pairs
                                                                               if p.get('action') == 'planes'),
               'pairs_ambiguous': sum(1 for p in pairs if p.get('action') == 'ambiguous'),
               'pieces_changed': len(changed), 'gap_m': target, 'left': left}
    return {'pieces': out, 'pairs': pairs, 'findings': found, 'skipped': skipped, 'ambiguous': ambiguous,
            'summary': summary}


def gap_report(edit, mode, rows, result, opts, state_hash=None, done=(), notes=(), extra=None):
    """Edit report of ucx.gap. Preview: objects = the pieces in scope with their pair findings; done = what apply
    writes on the copies. Apply: objects = the written copies (findings only when SAT still finds a gap)."""
    objects = []
    by_handle = {r['handle']: r for r in rows}
    if mode == 'preview':
        for h in sorted(by_handle):
            if family(by_handle[h]['name']) is None:
                continue
            objects.append(edit.entry(h, by_handle[h]['name'], [edit.finding(c, (), d)
                                                                for c, d in result['findings'].get(h, [])]))
        done = ['{} / {}: {:.3f} -> {:.3f} мм, плоскости {:.3f} + {:.3f} мм'.format(
            p['a'], p['b'], p['gap_before_m'] * 1000, p['gap_after_m'] * 1000, p['shift_a_m'] * 1000,
            p['shift_b_m'] * 1000) for p in result['pairs'] if p.get('action') == 'planes']
    else:
        objects = list(extra.pop('objects')) if extra and 'objects' in extra else []
    plan = {'units': 'm', 'gap_m': opts['gap_m'], 'options': opts, 'pairs': result['pairs'],
            'summary': result['summary'], 'notes': list(notes), 'layer': 'AGR_export'}
    plan.update(extra or {})
    return edit.report(TOOL, mode, objects, list(done), result['skipped'], result['ambiguous'],
                       state_hash=state_hash, extra=plan)
