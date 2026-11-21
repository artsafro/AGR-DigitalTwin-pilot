"""Standing #35: short-edge density Qe on the frozen #31 Ground fixture (OBSERVE, read-only).

Contract: docs/research/autoresearch-ground-short-edges.md (frozen before this script ran).
Replay: ../../.venv/Scripts/python.exe docs/research/autoresearch-ground-short-edges-r35.py C:/x/ev_t_f4f34f04/NEW.json
"""
import hashlib
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / 'docs/research/autoresearch-ground-quality-harness'
sys.path[:0] = [str(HARNESS), str(ROOT / 'src'), str(ROOT)]

from score import Part, open_edges, rigid  # noqa: E402  (#31 harness, unchanged)
from dt_ai.ops import inv_xview, xview_gate  # noqa: E402

REV32 = 'ebb32458a5673e2b142d7fc5b273733621201d71'
R32 = 'docs/research/autoresearch-ground-near-vertices-r32.json'
DUMPS = Path('C:/x/ev_t_193a0887/dumps-v002')
W1 = (Path('C:/x/ev_t_304e8c0c/dumps/W1_Vatutino_v014_NPM.npz'),
      '29393a0b5ed7ce39a2e5a8d8c7b0014885ecf4bfcde5a9ae07088bfc76aa6683')
CORE = (Path('C:/x/ev_t193/sil13_shared_v003/SM_SIL13_Ground.obj'),
        '8f51940939e921dc206280c385c6f045da13fc2c1b78d685bf63d0c7d0f1a450')
TOL = inv_xview.tolerance_for('NPM').vertex_m
CAP_S = 300.0


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def edge_array(faces):
    out = {(min(a, b), max(a, b)) for f in faces for a, b in zip(f, (*f[1:], f[0]))}
    return np.array(sorted(out), dtype=np.int64).reshape(-1, 2)


def measure(p):
    verts = np.asarray(p.vertices, dtype=np.float64)
    if not np.isfinite(verts).all():
        raise ValueError(p.name)
    t = sum(len(f) - 2 for f in p.faces)
    e = edge_array(p.faces)
    length = np.linalg.norm(verts[e[:, 0]] - verts[e[:, 1]], axis=1)
    short = int((length <= TOL).sum())
    loc = np.zeros(3) if p.location is None else np.asarray(p.location, dtype=np.float64)
    a, b, _ = inv_xview.vertex_pairs(verts - loc, TOL)          # #32 V, for parity only
    v = int(np.union1d(a, b).size)
    return dict(E=short, T=t, Qe=1e4 * short / t, V=v)


def split_nonmanifold(p):
    """Max-like convertToPoly: one vertex copy per edge-connected face fan around each vertex."""
    parent = {}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    first = {}
    corners = []
    for fi, f in enumerate(p.faces):
        n = len(f)
        for j, v in enumerate(f):
            c = (fi, j)
            parent[c] = c
            corners.append((c, v))
            for w in (f[j - 1], f[(j + 1) % n]):
                key = (v, w)
                if key in first:
                    ra, rb = find(first[key]), find(c)
                    if ra != rb:
                        parent[ra] = rb
                else:
                    first[key] = c
    verts = [np.asarray(x, dtype=np.float64) for x in p.vertices]
    seen, new_id = {}, {}
    for c, v in corners:
        root = find(c)
        if (v, root) not in new_id:
            if v in seen:
                new_id[(v, root)] = len(verts)
                verts.append(verts[v].copy())
            else:
                seen[v] = True
                new_id[(v, root)] = v
    faces = tuple(tuple(new_id[(v, find((fi, j)))] for j, v in enumerate(f)) for fi, f in enumerate(p.faces))
    return Part(p.name, np.array(verts), faces, p.location), len(verts) - len(p.vertices)


def inject(p, n=50):
    border = set(open_edges(p.faces).ravel().tolist())
    first = {}
    for f in p.faces:
        for j, x in enumerate(f):
            first.setdefault(x, (f, j))
    interior = [x for x in sorted(first) if x not in border]
    k = max(len(interior) // n, 1)
    pick = interior[::k][:n]
    picked = set(pick)
    verts = np.array(p.vertices, dtype=np.float64)
    moved = 0
    for v in pick:
        f, j = first[v]
        u = f[(j + 1) % len(f)]
        if u in picked:
            continue
        d = verts[v] - verts[u]
        verts[v] = verts[u] + 0.001 * d / np.linalg.norm(d)
        moved += 1
    return Part(p.name, verts, p.faces, p.location), moved


def ground(path):
    p, = (p for p in xview_gate.load_npz(path) if p.name.endswith('_Ground') and not p.name.startswith('UCX_'))
    return p


def main(out):
    if out.exists() or out.resolve().parent in {DUMPS.resolve()}:
        raise SystemExit('refuse: --out exists or aliases the inputs')
    r32 = json.loads(subprocess.check_output(['git', 'show', f'{REV32}:{R32}'], cwd=ROOT))['rows']
    manifest = {name.lstrip('*').split('_')[0]: (DUMPS / name.lstrip('*'), h) for h, name in
                (line.split() for line in (HARNESS / 'dumps.sha256').read_text().splitlines() if line.strip())}
    assert set(manifest) == set(r32), (set(manifest), set(r32))
    manifest['W1'] = W1
    rows, checks = {}, {}
    start = time.monotonic()
    first_pair_s = None
    for iid in ['A1', 'F4'] + sorted(set(manifest) - {'A1', 'F4'}):
        path, digest = manifest[iid]
        if sha(path) != digest:
            raise ValueError(f'dump mismatch: {path}')
        p = ground(path)
        reps = [measure(p) for _ in range(3)]
        clean = reps[0]
        rig = measure(rigid([p])[0])
        sp, n_split = split_nonmanifold(p)
        spl = measure(sp)
        row = rows[iid] = dict(dump=path.name, sha256=digest, part=p.name, clean_runs=reps,
                               median_Qe=statistics.median(r['Qe'] for r in reps), rigid=rig,
                               split=dict(added_vertices=n_split, **spl))
        ck = checks[iid] = dict(repeats=all(r == clean for r in reps),
                                rigid=(rig['E'], rig['T']) == (clean['E'], clean['T']),
                                split=(spl['E'], spl['T']) == (clean['E'], clean['T']))
        if iid in r32:
            ck['parity32'] = all(clean[k] == r32[iid]['clean_runs'][0][k] for k in ('V', 'T'))
        if iid.startswith('A'):
            inj, moved = inject(p)
            m = measure(inj)
            row['injected'] = dict(moved=moved, **m)
            ck['injection'] = m['E'] - clean['E'] >= 25 and m['T'] == clean['T']
        if sha(path) != digest:
            raise ValueError(f'input changed: {path}')
        if iid == 'F4':
            first_pair_s = time.monotonic() - start
            if first_pair_s * 7 > CAP_S:
                break
        if time.monotonic() - start > CAP_S:
            break
    series_s = time.monotonic() - start
    done = len(rows) == 14 and series_s <= CAP_S
    a = max(v['median_Qe'] for k, v in rows.items() if k.startswith('A'))
    f = min(v['median_Qe'] for k, v in rows.items() if k.startswith('F'))
    sep = f > a and f >= 2 * max(1.0, a)
    parity = all(c.get('parity32', True) for c in checks.values())
    stable = all(all(v for k, v in c.items() if k != 'parity32') for c in checks.values())
    hyp = 'inconclusive' if not done else ('confirmed' if sep and parity and stable else 'refuted')
    firing = sorted(k for k, v in rows.items() if k.startswith('A') and v['clean_runs'][0]['E'] > 0)
    report = dict(contract='docs/research/autoresearch-ground-short-edges.md', variant='Qe = 1e4*E(<=2mm edges)/T',
                  hypothesis=hyp, separation=sep, parity32=parity, stable=stable, max_A=a, min_F=f, margin=f - a,
                  accepted_control_fires=firing or 'not measured', rows=rows, checks=checks,
                  first_pair_seconds=round(first_pair_s or -1, 3), series_seconds=round(series_s, 3),
                  numpy=np.__version__, python=sys.version.split()[0])
    if hyp == 'confirmed':
        from tools.materials.npm_atlas_udim import read_obj
        cpath, cdig = CORE
        if sha(cpath) != cdig:
            raise ValueError('core OBJ hash mismatch')
        mesh, _ = read_obj(cpath)
        cp = Part(cpath.stem, np.asarray(mesh.vertices, dtype=np.float64), mesh.faces, np.zeros(3))
        reps = [measure(cp) for _ in range(3)]
        report['core'] = dict(path=cpath.as_posix(), sha256=cdig, clean_runs=reps,
                              median_Qe=statistics.median(r['Qe'] for r in reps))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print({k: report[k] for k in ('hypothesis', 'max_A', 'min_F', 'margin', 'first_pair_seconds', 'series_seconds')})
    print({k: (v['clean_runs'][0]['E'], v['clean_runs'][0]['T'], round(v['median_Qe'], 3), v['split']['added_vertices'],
               v['split']['V']) for k, v in rows.items()})
    print('checks failing:', {k: [n for n, ok in c.items() if not ok] for k, c in checks.items() if not all(c.values())})
    print('core:', report.get('core', {}).get('median_Qe'), report.get('core', {}).get('clean_runs', [{}])[0])


if __name__ == '__main__':
    main(Path(sys.argv[1]))
