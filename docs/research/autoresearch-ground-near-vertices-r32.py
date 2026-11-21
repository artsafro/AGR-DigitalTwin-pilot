"""Replay H32 on the immutable #31 fixture, then observe the sealed #1738 export."""
import hashlib
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
from dt_ai.ops import inv_xview, xview_gate

REV = '8ee341f74ef5dd453c4fbcc8d07a13713fd1cf38'
HARNESS = 'docs/research/autoresearch-ground-quality-harness'
DUMPS = Path('C:/x/ev_t_193a0887/dumps-v002')
CORE = Path('C:/x/ev_t193/sil13_shared_v003/SM_SIL13_Ground.obj')
CORE_SHA = '8f51940939e921dc206280c385c6f045da13fc2c1b78d685bf63d0c7d0f1a450'


def blob(name):
    return subprocess.check_output(['git', 'show', f'{REV}:{HARNESS}/{name}'], cwd=ROOT)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure(p):
    verts = np.asarray(p.vertices, dtype=np.float64) - p.location
    t = sum(len(f) - 2 for f in p.faces)
    if not t or not np.isfinite(verts).all():
        raise ValueError(p.name)
    a, b, _ = inv_xview.vertex_pairs(verts, inv_xview.tolerance_for('NPM').vertex_m)
    v = int(np.union1d(a, b).size)
    return dict(V=v, T=t, Qv=1e4 * v / t)


def main(out):
    old = json.loads(blob('r31.json'))['inputs']
    helpers = {'__name__': 'r31'}
    exec(compile(blob('score.py'), f'{REV}:score.py', 'exec'), helpers)
    manifest = {name.lstrip('*').split('_')[0]: (h, name.lstrip('*'))
                for h, name in (line.split() for line in blob('dumps.sha256').decode().splitlines())}
    rows, checks = {}, {}
    start = time.monotonic()
    for iid in ('A1', 'F4', *sorted(set(manifest) - {'A1', 'F4'})):
        digest, name = manifest[iid]
        path = DUMPS / name
        if sha(path) != digest:
            raise ValueError(f'dump mismatch: {path}')
        p, = (p for p in xview_gate.load_npz(path) if p.name.endswith('_Ground') and not p.name.startswith('UCX_'))
        reps = [measure(p) for _ in range(3)]
        clean = reps[0]
        rigid = measure(helpers['rigid']([p])[0])
        q = statistics.median(r['Qv'] for r in reps)
        old_q = old[iid]['clean_Q_median']
        row = rows[iid] = dict(dump=name, sha256=digest, part=p.name, clean_runs=reps, median=q,
                              spread=max(r['Qv'] for r in reps)-min(r['Qv'] for r in reps),
                              old_Q=old_q, delta_from_old_Q=q-old_q, rigid=rigid)
        checks[iid] = ck = dict(repeats=all(r == clean for r in reps), rigid=rigid == clean,
                                parity=all(r[k] == old[iid][mode][k] for mode, r in
                                           [('clean', clean), ('rigid', rigid)] for k in ('V', 'T')))
        if iid.startswith('A'):
            (inj,), n = helpers['inject']([p])
            injected = measure(inj)
            delta = injected['V'] - clean['V']
            ri = measure(helpers['rigid']([inj])[0])
            row.update(injected=injected, injected_rigid=ri, unwelds=n, injected_delta_V=delta,
                       injection_bounds_V=[100, len(inj.vertices)])
            ck.update(injection=n == 50 and 100 <= delta <= len(inj.vertices) and injected['T'] == clean['T'],
                      injected_rigid=injected == ri,
                      injected_parity=all(injected[k] == old[iid]['inject'][k] for k in ('V', 'T')))
        if sha(path) != digest:
            raise ValueError(f'input changed: {path}')
        if iid == 'F4':
            first_pair_s = time.monotonic() - start
            if first_pair_s * 7 > 240:
                break
        if time.monotonic() - start > 240:
            break
    a = max(v['median'] for k, v in rows.items() if k.startswith('A'))
    f = min(v['median'] for k, v in rows.items() if k.startswith('F'))
    hypothesis = 'inconclusive' if len(rows) != 13 or time.monotonic() - start > 240 else (
        'confirmed' if f > a and f >= 2 * max(1, a) and all(all(c.values()) for c in checks.values()) else 'refuted')
    report = dict(hypothesis=hypothesis, input_git=REV, rows=rows, checks=checks,
                  first_pair_seconds=round(first_pair_s, 3), series_seconds=round(time.monotonic()-start, 3),
                  max_A=a, min_F=f, margin=f-a, numpy=np.__version__)
    if hypothesis == 'confirmed':
        if sha(CORE) != CORE_SHA:
            raise ValueError('core OBJ hash mismatch')
        from tools.materials.npm_atlas_udim import read_obj
        mesh, _ = read_obj(CORE)
        p = xview_gate.Part(CORE.stem, mesh.vertices, mesh.faces, np.zeros(3))
        reps = [measure(p) for _ in range(3)]
        if sha(CORE) != CORE_SHA:
            raise ValueError('core OBJ changed')
        values = [r['Qv'] for r in reps]
        report['core'] = dict(path=CORE.as_posix(), sha256=CORE_SHA, clean_runs=reps,
                              median=statistics.median(values), spread=max(values)-min(values))
    with out.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print({k: report[k] for k in ('hypothesis', 'margin', 'first_pair_seconds', 'series_seconds')}, report.get('core'))


if __name__ == '__main__':
    main(Path(sys.argv[1]))
