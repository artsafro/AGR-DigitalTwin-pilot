"""new-case: plan of the R1 overlap zones that the KPP1 quad master v002 unions away (#1372, decision D-quad).

Run with the project venv (numpy, shapely, dt_ai):
    uv run python jobs/KPP1/quad-1372/plan_union_zones.py <R1 SM_Kpp_1.fbx> <out union-zones.json> [--blender EXE]

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
from pathlib import Path
import tempfile

import numpy as np

from dt_ai.core.blender_runner import run_blender
from dt_ai.ops import inv_xview, xview_gate

SOURCE_SHA = '1f46b0dd5973b6e3ba40acbe04d65fb3595dcacb0d90a7724e921eda9b56b676'  # r1-v002 SM_Kpp_1.fbx
PART = 'SM_Kpp_1_Main'
AXIS_MIN = 0.99
SPREAD_MAX_M = 0.005     # user decision 2026-11-14: delete/merge within <= 5 mm
FLOAT_TOL_M = 1e-5       # float32 storage of R1 at ~15 m from the origin: a 5.000 mm design step reads 5.000x mm
PLAN_FACE_M = 0.0051     # plan pairs up to 5.1 mm: a pair at exactly xView's 5 mm (flagged, `<=`) must not pass or
                         # fail by float rounding of the NPM recentering (#1372 v002-r3: 10 contacts at 5.000 mm)
PLANE_JOIN_M = 0.002     # zone planes on one axis closer than this are one plane (one snap value)


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


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('source')
    ap.add_argument('out')
    ap.add_argument('--blender', default=None)
    a = ap.parse_args(argv)
    src, out = Path(a.source).resolve(), Path(a.out).resolve()
    if out == src or out.exists():
        raise SystemExit(f'output {out} exists or is the input; use a new path')
    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    if digest != SOURCE_SHA:
        raise SystemExit(f'{src} is not the approved r1-v002 SM_Kpp_1.fbx (sha {digest})')
    with tempfile.TemporaryDirectory(prefix='union-zones-', dir=out.parent) as tmp:
        npz, man = Path(tmp) / 'parts.npz', Path(tmp) / 'manifest.json'
        dump = run_blender(xview_gate.DUMP_SCRIPT, [src, npz, man], executable=a.blender, output_json=man,
                           outputs=[npz], log_path=Path(tmp) / 'dump.log')
        parts, units = xview_gate.to_metres(xview_gate.load_npz(npz), dump)
    part = {p.name: p for p in parts}.get(PART)
    if part is None:
        raise SystemExit(f'{PART} not in {src}')
    v = np.asarray(part.vertices, dtype=np.float64)
    g = xview_gate.part_gate(part, inv_xview.XviewTolerance(), 'inplace')
    gp = xview_gate.part_gate(part, inv_xview.XviewTolerance(face_m=PLAN_FACE_M), 'inplace')
    pairs = [(fp['a'] - 1, fp['b'] - 1) for fp in gp['face_pairs']]
    plan = {'source': str(src), 'source_sha256': digest, 'part': PART, 'units': units,
            'faces_count': len(part.faces), 'xview_r1': {'vertex_pairs': len(g['vertex_pairs']),
                                                         'face_pairs': len(g['face_pairs']),
                                                         'by_kind': g['face_pairs_by_kind'],
                                                         'bowtie_vertices': len(g['bowtie_vertices'])},
            'plan_face_m': PLAN_FACE_M, 'plan_face_pairs': len(pairs),
            'spread_max_m': SPREAD_MAX_M, 'zones': zones(v, part.faces, pairs)}
    out.write_text(json.dumps(plan, indent=1))
    print(json.dumps({'zones': len(plan['zones']), 'faces': sum(len(z['faces']) for z in plan['zones']),
                      'max_spread_mm': max(z['spread_m'] for z in plan['zones']) * 1000, **plan['xview_r1']}))


if __name__ == '__main__':
    main()
