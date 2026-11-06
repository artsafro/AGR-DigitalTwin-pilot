"""new-case: AGR Tools 1.0 (#1024) roof plane by parapet logic, stdlib only. Owned by branch K (improve/issue-1024-capsules-roof).

Pure logic for `body_roof` (body.roof, station 1.0.13); no pymxs. Rule: patterns `roof-inset-plane` (D038/D039/D068)
and `parapet` (D024), owner answers 06.11.2026: the roof slab lies on the bottom loop of the parapet rim (contour
A: the open bottom edges of the inner parapet faces) + a lift (default 5 mm, owner), its outline goes INTO the
parapets by the inset (default 20 mm, D038). On a slope the slab follows the plane of the loop and the lift goes
along that plane's normal; steeper than 10 degrees -> `ambiguous` + a request to the agent (К4, branch U picks
`plan.agent_requests` up).

Lab L13 (docs/experiments/body.roof.md, job 20261106-022407-3c217615): own 2D mitre offset (C2) = the Max chain
(shape from selection -> cap -> outline -> move) on flat cases in < 1 ms; a horizontal slab at mean height is WRONG
on a slope (544 mm off at 3 degrees) -> plane fitted to the loop. Metres only; the glue converts.
"""
import importlib.util
import math
import os

TOOL = 'body.roof'
ROLE = 'roof'
LAYER = 'ROOF_slabs'
DEFAULTS = {
    'lift_m': 0.005,          # owner 06.11: slab 5 mm above the parapet bottom
    'inset_m': 0.02,          # D038: 20 mm into the parapets
    'max_slope_deg': 10.0,    # steeper -> agent
    'rim_slope_deg': 45.0,    # loops steeper than this are not roof contours (openings, gable edges)
    'nonplanar_tol_m': 0.02,  # loop out of its fitted plane beyond this -> ambiguous
}
CODES = ('no_roof_loop', 'roof_steep', 'roof_nonplanar', 'roof_offset_invalid', 'roof_gap', 'roof_outside_parapet')


def _cc():
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location('agr_tools_capsule_core_geo', os.path.join(here, 'capsule_core.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


G = _cc()  # 2D / 3D helpers shared with capsule_core (same branch)


def options(raw=None):
    raw = dict(raw or {})
    unknown = sorted(set(raw) - set(DEFAULTS))
    if unknown:
        raise ValueError('body.roof: unknown option(s) ' + ', '.join(unknown))
    out = dict(DEFAULTS, **raw)
    for k, v in out.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            raise ValueError('body.roof: option {} must be a number >= 0: {!r}'.format(k, v))
        out[k] = float(v)
    if out['inset_m'] <= 0:
        raise ValueError('body.roof: inset_m must be > 0')
    return out


def boundary_loops(faces):
    """Closed loops of open (single-use) edges, each in the winding of its face: [[vertex index...]]."""
    count = {}
    for f in faces:
        for i in range(len(f)):
            e = tuple(sorted((f[i], f[(i + 1) % len(f)])))
            count[e] = count.get(e, 0) + 1
    nxt, owner = {}, {}
    for k, f in enumerate(faces):
        for i in range(len(f)):
            a, b = f[i], f[(i + 1) % len(f)]
            if count[tuple(sorted((a, b)))] == 1:
                nxt.setdefault(a, []).append(b)
                owner[(a, b)] = k
    loops, used = [], set()
    for a in sorted(nxt):
        for b0 in nxt[a]:
            if (a, b0) in used:
                continue
            loop, cur, b = [a], a, b0
            ok = True
            while True:
                used.add((cur, b))
                if b == a:
                    break
                loop.append(b)
                cands = [c for c in nxt.get(b, ()) if (b, c) not in used]
                if not cands or len(loop) > len(owner) + 1:
                    ok = False
                    break
                cur, b = b, cands[0]
            if ok and len(loop) >= 3:
                loops.append(loop)
    return loops, owner


def _frame(n):
    """In-plane axes: u horizontal (world X on a flat roof), v = n x u (up the slope)."""
    u = [1.0, 0.0, 0.0] if abs(n[2]) >= 0.999999 else G._unit(G._cross([0.0, 0.0, 1.0], n))
    return u, G._unit(G._cross(n, u))


def _hull(points):
    pts = sorted(set((round(p[0], 9), round(p[1], 9)) for p in points))
    if len(pts) < 3:
        return [list(p) for p in pts]

    def cr(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cr(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cr(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return [list(p) for p in lower[:-1] + upper[:-1]]


def slab(mesh, loop, owner_faces, opts, hull):
    """One slab for one rim loop: {'verts', 'faces', 'slope_deg', ...} or raises G.Ambiguous / returns None
    (None: the loop is not a parapet rim)."""
    verts, faces = mesh['verts'], mesh['faces']
    pts = [verts[i] for i in loop]
    nn = G.newell(pts)
    if G._norm(nn) < 1e-12:
        return None
    n = G._unit(nn)
    if n[2] < 0:
        n = G._mul(n, -1.0)
    slope = math.degrees(math.acos(max(-1.0, min(1.0, n[2]))))
    if slope >= opts['rim_slope_deg']:
        return None
    c = G.centroid(pts)
    # a parapet rim: the faces on the loop look INTO the hole (towards the loop centre), as inner parapet faces do;
    # the open bottom of a box (outer walls) looks away from it.
    votes = 0
    for i, a in enumerate(loop):
        b = loop[(i + 1) % len(loop)]
        k = owner_faces.get((a, b))
        if k is None:
            continue
        fn = G.newell([verts[j] for j in faces[k]])
        mid = G._mul(G._add(verts[a], verts[b]), 0.5)
        to_c = G._sub(c, mid)
        to_c = G._sub(to_c, G._mul(n, G._dot(to_c, n)))
        votes += 1 if G._dot(fn, to_c) > 0 else -1
    if votes <= 0:
        return None
    dev = max(abs(G._dot(G._sub(p, c), n)) for p in pts)
    if slope > opts['max_slope_deg']:
        raise G.Ambiguous('roof_steep', 'roof loop slope {:.1f} deg > {:.0f} deg: agent request'.format(
            slope, opts['max_slope_deg']))
    if dev > opts['nonplanar_tol_m']:
        raise G.Ambiguous('roof_nonplanar', 'roof loop {:.0f} mm out of its plane > {:.0f} mm'.format(
            dev * 1000, opts['nonplanar_tol_m'] * 1000))
    u, v = _frame(n)
    poly = G.clean2([[G._dot(G._sub(p, c), u), G._dot(G._sub(p, c), v)] for p in pts])
    if len(poly) < 3:
        return None
    if G.area2(poly) < 0:
        poly.reverse()
    d = opts['inset_m']
    off = G.offset2(poly, d)
    if off is None or not G.is_simple(off) or G.area2(off) <= G.area2(poly) or \
            min(G.poly_dist(q, poly) for q in off) < d * (1 - 1e-6):
        raise G.Ambiguous('roof_offset_invalid', 'the {:.0f} mm inset of this contour is not a clean offset'.format(
            d * 1000))
    gaps = sum(1 for q in poly if not G.inside(q, off))
    lift = opts['lift_m']
    world = [G._add(G._add(G._add(c, G._mul(u, q[0])), G._mul(v, q[1])), G._mul(n, lift)) for q in off]
    out = [i for i, p in enumerate(world) if not G.inside([p[0], p[1]], hull) and
           G.poly_dist([p[0], p[1]], hull) > 1e-6]
    level = sum(p[2] for p in pts) / len(pts)
    return {'verts': world, 'faces': [list(range(len(world)))], 'slope_deg': round(slope, 3),
            'normal': n, 'level_m': round(level, 6), 'lift_m': lift, 'inset_m': d, 'gaps': gaps,
            'outside': out, 'points': len(world), 'loop_dev_m': round(dev, 6),
            'area_m2': round(abs(G.area2(off)), 6)}


def roof_name(body_name, k):
    return 'ROOF_{}_{:03d}'.format(body_name, k)


def plan(bodies, raw_options=None):
    """bodies: [{'handle', 'name', 'mesh': {'verts' (m, world), 'faces'}}] -> {'options', 'rows', 'findings',
    'done', 'skipped', 'ambiguous', 'agent_requests'}."""
    if not bodies:
        raise ValueError('body.roof: empty target set')
    opts = options(raw_options)
    rows, findings, skipped, ambiguous, requests = [], {}, [], [], []
    for b in bodies:
        fl = findings.setdefault(b['handle'], [])
        mesh = b['mesh']
        loops, owner = boundary_loops(mesh['faces'])
        hull = _hull(mesh['verts']) if mesh['verts'] else []
        k = 0
        for loop in sorted(loops, key=lambda lp: min(lp)):
            try:
                s = slab(mesh, loop, owner, opts, hull)
            except G.Ambiguous as exc:
                fl.append((exc.code, exc.detail))
                ambiguous.append('{}: {}'.format(b['name'], exc))
                if exc.code == 'roof_steep':
                    requests.append({'stage': 4, 'tool': TOOL, 'object': b['name'], 'handle': b['handle'],
                                     'task': 'roof slab on a slope steeper than {:.0f} deg'.format(
                                         opts['max_slope_deg']), 'detail': exc.detail})
                continue
            if s is None:
                continue
            k += 1
            name = roof_name(b['name'], k)
            if s['gaps']:
                fl.append(('roof_gap', '{}: {} points of contour A not under the slab'.format(name, s['gaps'])))
            if s['outside']:
                fl.append(('roof_outside_parapet', '{}: {} slab points beyond the outer parapet line'.format(
                    name, len(s['outside']))))
            if s['gaps'] or s['outside']:
                ambiguous.append('{}: slab refused (gaps {}, outside {})'.format(name, s['gaps'], len(s['outside'])))
                continue
            rows.append(dict(s, body=b['name'], handle=b['handle'], name=name))
        if k == 0 and not any(c in ('roof_steep', 'roof_nonplanar', 'roof_offset_invalid') for c, _ in fl):
            fl.append(('no_roof_loop', '{}: no open parapet rim loop (contour A) found'.format(b['name'])))
            skipped.append({'item': b['name'], 'reason': 'no open parapet rim loop (contour A)'})
    done = ['{} <- {}: level {:.3f} m + {:.0f} mm, inset {:.0f} mm, slope {:.1f} deg, {} points'.format(
        r['name'], r['body'], r['level_m'], r['lift_m'] * 1000, r['inset_m'] * 1000, r['slope_deg'], r['points'])
        for r in rows]
    return {'options': opts, 'rows': rows, 'findings': findings, 'done': done, 'skipped': skipped,
            'ambiguous': ambiguous, 'agent_requests': requests}
