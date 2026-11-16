"""new-case: plan of the R1 overlap zones that the KPP1 quad master v002 unions away (#1372, decision D-quad).

Run with the project venv (numpy, shapely, dt_ai):
    uv run python jobs/KPP1/quad-1372/plan_union_zones.py <R1 SM_Kpp_1.fbx> <out union-zones.json> [--blender EXE]
        [--xview-json <archived xView JSON of that R1>] [--compare <older union-zones.json>]

#1563 (master quad-v003): the R1 source is accepted by its own pinned sha256 per R1 version (`SOURCE_SHAS`:
r1-v002 for the v001/v002 masters, r1-v003 of rerun-1230 #1246 for v003); any other file is refused.
`--xview-json` takes the archived xView report of that R1 (`ARCHIVED_XVIEW`: pinned sha256 per source); the plan
then checks that the same kernel at the xView 5 mm threshold gives exactly the archived face pairs (else an error)
and records which xView input was used. `--compare` lists the zones new / changed / identical / removed against an
older plan (matched by geometry: face ids differ between R1 versions); every zone that touches the SW / NW corner
posts (`CORNER_POSTS`, #1246 read-back points) is listed in `corners`.

Reads the approved R1 master (copy, sha-checked), dumps it with `tools/blender/xview_dump.py` (the `dt qa xview`
dump), runs the same xView gate kernel (`xview_gate.part_gate`, 2 mm / 5 mm) on `SM_Kpp_1_Main` and groups the
flagged face pairs into zones (connected through shared pairs). Every zone must lie on one axis plane (|n_axis| >=
0.99; R1 is axis-aligned there); its plane value is the median of the zone vertices on that axis, rounded to 0.1 mm,
and its spread (max - min on the axis) must stay <= 5 mm (the user's limit for the merge). Any other zone is an
error naming it, never a guess. The plan lists every flagged face with its centroid so the Blender build can prove
it addresses the same faces. The output must not exist (never overwrite) and must not be the input.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import tempfile

import numpy as np

from dt_ai.core.blender_runner import run_blender
from dt_ai.ops import inv_xview, xview_gate

SOURCE_SHAS = {  # accepted R1 masters, one pinned sha256 per R1 version (#1563)
    '1f46b0dd5973b6e3ba40acbe04d65fb3595dcacb0d90a7724e921eda9b56b676': 'r1-v002',  # #1230, quad v001/v002
    # rerun-1230 #1246, LOCAL axis-aligned copy (1246-kpp1-corner-pairs); the #1278 site-placed copy eb9d105a is
    # refused: the master is built in world x/y, placement is the package step [D135, conflicts.md #39]
    '76a7c97e523d6ac6475443a84f51e4b2ec588de3cbeb1b300d08adf07e97dc50': 'r1-v003',
}
SOURCE_SHA = '1f46b0dd5973b6e3ba40acbe04d65fb3595dcacb0d90a7724e921eda9b56b676'  # r1-v002 (v001/v002 masters)
# source sha -> sha256 of its archived `dt qa xview` VPM report. Empty on purpose: the #1278 archive
# diagnostics-latest-v001/latest-xview-vpm.json (c588e09f...) reports the site-placed copy eb9d105a, not an
# accepted source, so xView is recomputed on the local r1-v003 (#1563).
ARCHIVED_XVIEW = {}
CORNER_POSTS = {'SW': (-15.03, -5.73), 'NW': (-15.0303, 6.0196)}  # #1246 readback-v003b post centres (x, y), m
CORNER_RADIUS_M = 0.25   # post + the old 0.1 m fins: a zone whose xy box comes this close touches the corner
MATCH_TOL_M = 1e-4       # zones of two plans are identical when axis, plane value and face centroids agree to 0.1 mm
PART = 'SM_Kpp_1_Main'
AXIS_MIN = 0.99
SPREAD_MAX_M = 0.005     # user decision 2026-11-14: delete/merge within <= 5 mm
FLOAT_TOL_M = 1e-5       # float32 storage of R1 at ~15 m from the origin: a 5.000 mm design step reads 5.000x mm
PLAN_FACE_M = 0.0051     # plan pairs up to 5.1 mm: a pair at exactly xView's 5 mm (flagged, `<=`) must not pass or
                         # fail by float rounding of the NPM recentering (#1372 v002-r3: 10 contacts at 5.000 mm)
PLANE_JOIN_M = 0.002     # zone planes on one axis closer than this are one plane (one snap value)
MAP_TOL_M = 1e-4         # a residual master face centroid lies on its R1 face within 0.1 mm (float32 FBX at ~15 m)


def zones(v, faces, pairs):
    """[(face ids)] zones = connected components of the flagged face pairs (union-find)."""
    par = {}

    def find(x):
        par.setdefault(x, x)
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    for a, b in pairs:
        ra, rb = find(a), find(b)
        if ra != rb:
            par[ra] = rb
    groups = {}
    for a, b in pairs:
        groups.setdefault(find(a), set()).update((a, b))
    out = []
    for fs in sorted(groups.values(), key=min):
        fs = sorted(fs)
        ns = []
        for f in fs:
            p = v[list(faces[f])]
            n = np.cross(p[1] - p[0], p[2] - p[0])
            ln = np.linalg.norm(n)
            if not np.isfinite(ln) or ln == 0:
                raise ValueError(f'zone face {f}: no plane (degenerate)')
            ns.append(n / ln)
        ns = np.array(ns)
        ns = ns * np.sign(ns @ ns[0])[:, None]
        n = ns.mean(0)
        n /= np.linalg.norm(n)
        ax = int(np.argmax(np.abs(n)))
        if abs(n[ax]) < AXIS_MIN:
            raise ValueError(f'zone with faces {fs[:5]}: not on an axis plane (normal {n.round(4).tolist()})')
        vs = v[sorted({x for f in fs for x in faces[f]})]
        spread = float(np.ptp(vs[:, ax]))
        if not spread <= SPREAD_MAX_M + FLOAT_TOL_M:
            raise ValueError(f'zone with faces {fs[:5]}: spread {spread * 1000:.2f} mm > {SPREAD_MAX_M * 1000} mm')
        out.append({'faces': fs, 'centroids': [v[list(faces[f])].mean(0).tolist() for f in fs], 'axis': ax,
                    'value': round(float(np.median(vs[:, ax])), 4), 'spread_m': spread,
                    'lo': vs.min(0).tolist(), 'hi': vs.max(0).tolist(), '_coords': vs[:, ax].tolist()})
    # zones on one axis whose planes lie within PLANE_JOIN_M share one plane value (a vertex may sit in two zones)
    for ax in range(3):
        zs = sorted((z for z in out if z['axis'] == ax), key=lambda z: z['value'])
        groups = []
        for z in zs:
            if groups and z['value'] - groups[-1][-1]['value'] <= PLANE_JOIN_M:
                groups[-1].append(z)
            else:
                groups.append([z])
        for g in groups:
            cs = [c for z in g for c in z['_coords']]
            val = round(float(np.median(cs)), 4)
            for z in g:
                z['value'] = val
                z['spread_m'] = max(abs(c - val) for c in z['_coords'])
                if not z['spread_m'] <= SPREAD_MAX_M + FLOAT_TOL_M:
                    raise ValueError(f"zone with faces {z['faces'][:5]}: {z['spread_m'] * 1000:.2f} mm from its "
                                     f"plane > {SPREAD_MAX_M * 1000} mm")
    for z in out:
        del z['_coords']
    return out


def _same_cents(a, b, tol=MATCH_TOL_M):
    """True when the centroids of zones a and b pair one-to-one within `tol` (no rounding buckets: #1563 probe)."""
    ca, cb = a['centroids'], b['centroids']
    if len(ca) != len(cb):
        return False
    free = list(range(len(cb)))
    for p in ca:
        hit = next((j for j in free if math.dist(p, cb[j]) <= tol + 1e-9), None)
        if hit is None:
            return False
        free.remove(hit)
    return True


def _boxes_meet(a, b, tol=PLANE_JOIN_M):
    return all(a['lo'][i] - tol <= b['hi'][i] and b['lo'][i] - tol <= a['hi'][i] for i in range(3))


def diff_plans(old, new):
    """Zones of `new` vs `old`, measured by geometry (face ids differ between R1 versions).

    identical = same axis, plane value within 0.1 mm and the same face centroids (0.1 mm); changed = same axis,
    plane values within PLANE_JOIN_M and boxes that meet, but not identical; new = no such old zone; removed = old
    zones no new zone matches. Every zone of both plans ends in exactly one list."""
    status, used = [], set()
    for k, z in enumerate(new['zones']):
        same = [j for j, o in enumerate(old['zones']) if o['axis'] == z['axis']
                and abs(o['value'] - z['value']) <= MATCH_TOL_M and _same_cents(o, z)]
        near = [j for j, o in enumerate(old['zones']) if o['axis'] == z['axis']
                and abs(o['value'] - z['value']) <= PLANE_JOIN_M and _boxes_meet(o, z)]
        kind = 'identical' if same else 'changed' if near else 'new'
        match = same or near
        used.update(match)
        status.append({'zone': k, 'status': kind, 'old_zones': match, 'faces': len(z['faces']),
                       'axis': z['axis'], 'value': z['value']})
    removed = [j for j in range(len(old['zones'])) if j not in used]
    counts = {s: sum(1 for x in status if x['status'] == s) for s in ('new', 'changed', 'identical')}
    counts['removed'] = len(removed)
    return {'counts': counts, 'zones': status, 'removed_old_zones': removed,
            'old_zones': len(old['zones']), 'new_zones': len(new['zones'])}


def corner_zones(plan_zones, posts=CORNER_POSTS, radius=CORNER_RADIUS_M):
    """{corner: [zone ids]} whose xy box comes within `radius` of the corner post centre."""
    return {name: [k for k, z in enumerate(plan_zones)
                   if z['lo'][0] - radius <= x <= z['hi'][0] + radius
                   and z['lo'][1] - radius <= y <= z['hi'][1] + radius]
            for name, (x, y) in posts.items()}


def archived_pairs(path, digest):
    """(path, sha, face pairs) of the archived xView report of source `digest`: pinned sha, same input, defaults."""
    path = Path(path).resolve()
    want = ARCHIVED_XVIEW.get(digest)
    if want is None:
        raise SystemExit(f'no archived xView report is pinned for source {digest}; run without --xview-json')
    if not path.is_file():
        raise SystemExit(f'{path}: archived xView report missing; rerun xView')
    got = hashlib.sha256(path.read_bytes()).hexdigest()
    if got != want:
        raise SystemExit(f'{path}: sha {got} is not the archived xView report {want}; rerun xView')
    rep = json.loads(path.read_text(encoding='utf-8'))
    if (rep.get('input') or {}).get('sha256') != digest:
        raise SystemExit(f'{path}: xView input is not the source {digest}')
    tol = inv_xview.XviewTolerance()
    th = rep.get('thresholds') or {}
    if th.get('face_m') != tol.face_m or th.get('vertex_m') != tol.vertex_m:
        raise SystemExit(f'{path}: thresholds {th} are not the xView defaults')
    parts = [p for p in rep.get('parts') or () if p.get('part') == PART]
    if len(parts) != 1:
        raise SystemExit(f'{path}: {PART} appears {len(parts)} times')
    return path, got, {(fp['a'] - 1, fp['b'] - 1) for fp in parts[0]['face_pairs']}


def faces_under(p, v, faces, tol=MAP_TOL_M):
    """R1 faces (ids) the point p lies on: within `tol` of the face plane and inside it (fan triangles, `tol` slack)."""
    p = np.asarray(p, dtype=np.float64)
    if p.shape != (3,) or not np.all(np.isfinite(p)):
        raise ValueError(f'point {p!r} is not 3 finite numbers')
    hit = []
    for f, ids in enumerate(faces):
        q = v[list(ids)]
        if np.any(q.max(0) + tol < p) or np.any(q.min(0) - tol > p):
            continue
        for k in range(1, len(q) - 1):
            a, b, c = q[0], q[k], q[k + 1]
            n = np.cross(b - a, c - a)
            ln = np.linalg.norm(n)
            if ln == 0:
                continue
            n /= ln
            if abs((p - a) @ n) > tol:
                continue
            # inside test with slack: every edge's inward distance >= -tol
            if all(np.cross(e1 - e0, p - e0) @ n / max(np.linalg.norm(e1 - e0), 1e-12) >= -tol
                   for e0, e1 in ((a, b), (b, c), (c, a))):
                hit.append(f)
                break
    return hit


def residual_pairs(rparts, v, faces):
    """Face pairs that a previous quad build of this R1 still shows at PLAN_FACE_M, mapped back to the R1 faces.

    Quadification splits R1 triangles at edge midpoints, so two R1 faces that met with shared vertices but a 0.2 to
    0.4 mm off-plane edge become an xView contact in the master (SW/NW posts of r1-v003, #1563). Each residual master
    face is mapped to the R1 face(s) its centroid lies on (MAP_TOL_M); both sides are chained into one pair set, so the
    same zones() rules (axis plane, spread <= 5 mm) decide. A residual face on no R1 face is an error naming it."""
    rpart = {p.name: p for p in rparts}.get(PART)
    if rpart is None:
        raise SystemExit(f'{PART} not in the residual master')
    rv = np.asarray(rpart.vertices, dtype=np.float64)
    gate = xview_gate.part_gate(rpart, inv_xview.XviewTolerance(face_m=PLAN_FACE_M), 'inplace')
    out, log = [], []
    for fp in gate['face_pairs']:
        sides = []
        for key in ('a', 'b'):
            ids = list(rpart.faces[fp[key] - 1])
            c = rv[ids].mean(0)
            r1 = faces_under(c, v, faces)
            if not r1:
                raise SystemExit(f'residual face {fp[key]} at {c.round(4).tolist()} lies on no R1 face')
            sides.append(r1)
        chain = sides[0] + sides[1]
        out += [(min(x, y), max(x, y)) for x, y in zip(chain, chain[1:]) if x != y]
        log.append({'master_faces': [fp['a'], fp['b']], 'kind': fp['kind'], 'centre': fp['centre'],
                    'r1_faces': sides})
    return out, log


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('source')
    ap.add_argument('out')
    ap.add_argument('--blender', default=None)
    ap.add_argument('--xview-json', default=None)
    ap.add_argument('--compare', default=None)
    ap.add_argument('--residual', default=None)
    a = ap.parse_args(argv)
    src, out = Path(a.source).resolve(), Path(a.out).resolve()
    if out == src or out.exists():
        raise SystemExit(f'output {out} exists or is the input; use a new path')
    for extra in (a.xview_json, a.compare, a.residual):
        if extra is not None and Path(extra).resolve() in (src, out):
            raise SystemExit(f'{extra} aliases the source or the output')
    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    if digest not in SOURCE_SHAS:
        raise SystemExit(f'{src} is not the approved R1 SM_Kpp_1.fbx of any accepted version (sha {digest}; '
                         'approved: ' + ', '.join(f'{v} {k[:12]}' for k, v in SOURCE_SHAS.items()) + ')')
    archived = archived_pairs(a.xview_json, digest) if a.xview_json else None
    old = json.loads(Path(a.compare).read_text(encoding='utf-8')) if a.compare else None
    with tempfile.TemporaryDirectory(prefix='union-zones-', dir=out.parent) as tmp:
        npz, man = Path(tmp) / 'parts.npz', Path(tmp) / 'manifest.json'
        dump = run_blender(xview_gate.DUMP_SCRIPT, [src, npz, man], executable=a.blender, output_json=man,
                           outputs=[npz], log_path=Path(tmp) / 'dump.log')
        parts, units = xview_gate.to_metres(xview_gate.load_npz(npz), dump)
        rparts = None
        if a.residual:
            rnpz, rman = Path(tmp) / 'residual.npz', Path(tmp) / 'residual.json'
            rdump = run_blender(xview_gate.DUMP_SCRIPT, [Path(a.residual).resolve(), rnpz, rman],
                                executable=a.blender, output_json=rman, outputs=[rnpz],
                                log_path=Path(tmp) / 'residual.log')
            rparts, _ = xview_gate.to_metres(xview_gate.load_npz(rnpz), rdump)
    part = {p.name: p for p in parts}.get(PART)
    if part is None:
        raise SystemExit(f'{PART} not in {src}')
    v = np.asarray(part.vertices, dtype=np.float64)
    g = xview_gate.part_gate(part, inv_xview.XviewTolerance(), 'inplace')
    gp = xview_gate.part_gate(part, inv_xview.XviewTolerance(face_m=PLAN_FACE_M), 'inplace')
    pairs = [(fp['a'] - 1, fp['b'] - 1) for fp in gp['face_pairs']]
    residual = None
    if rparts is not None:
        rpairs, rlog = residual_pairs(rparts, v, part.faces)
        residual = {'path': str(Path(a.residual).resolve()),
                    'sha256': hashlib.sha256(Path(a.residual).read_bytes()).hexdigest(),
                    'master_pairs': len(rlog), 'r1_pairs_added': len(set(rpairs) - set(pairs)), 'pairs': rlog}
        pairs = sorted(set(pairs) | set(rpairs))
    xview_input = {'used': 'recomputed', 'face_m': inv_xview.XviewTolerance().face_m}
    if archived is not None:
        now = {(fp['a'] - 1, fp['b'] - 1) for fp in g['face_pairs']}
        if now != archived[2]:
            raise SystemExit(f'{archived[0]}: archived pairs differ from the kernel ({len(archived[2] - now)} only '
                             f'archived, {len(now - archived[2])} only now); rerun xView')
        xview_input = {'used': 'archived', 'path': str(archived[0]), 'sha256': archived[1],
                       'face_pairs': len(archived[2]), 'pairs_equal_kernel_5mm': True,
                       'extra_pairs_5_1mm': len(set(pairs) - archived[2])}
    plan = {'source': str(src), 'source_sha256': digest, 'source_version': SOURCE_SHAS[digest],
            'xview_input': xview_input, 'part': PART, 'units': units,
            'faces_count': len(part.faces), 'xview_r1': {'vertex_pairs': len(g['vertex_pairs']),
                                                         'face_pairs': len(g['face_pairs']),
                                                         'by_kind': g['face_pairs_by_kind'],
                                                         'bowtie_vertices': len(g['bowtie_vertices'])},
            'plan_face_m': PLAN_FACE_M, 'plan_face_pairs': len(pairs), 'residual': residual,
            'spread_max_m': SPREAD_MAX_M, 'zones': zones(v, part.faces, pairs)}
    plan['corners'] = {'posts': CORNER_POSTS, 'radius_m': CORNER_RADIUS_M, 'zones': corner_zones(plan['zones'])}
    if old is not None:
        plan['diff'] = {'against': str(Path(a.compare).resolve()),
                        'against_sha256': hashlib.sha256(Path(a.compare).read_bytes()).hexdigest(),
                        **diff_plans(old, plan)}
    out.write_text(json.dumps(plan, indent=1))
    print(json.dumps({'zones': len(plan['zones']), 'faces': sum(len(z['faces']) for z in plan['zones']),
                      'max_spread_mm': max((z['spread_m'] for z in plan['zones']), default=0.0) * 1000,
                      'xview_input': xview_input['used'], 'corners': plan['corners']['zones'],
                      'diff': plan.get('diff', {}).get('counts'), **plan['xview_r1']}))


if __name__ == '__main__':
    main()
