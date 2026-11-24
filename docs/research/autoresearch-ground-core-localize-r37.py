"""Standing #37: Qe stage localisation on the merged #1738 core output (OBSERVE, read-only).

new-case: docs/research/autoresearch-ground-core-localize-r37.py - research harness, OBSERVE only
Contract: docs/research/autoresearch-ground-core-localize.md (frozen before this script ran).
Replay: ../../.venv/Scripts/python.exe docs/research/autoresearch-ground-core-localize-r37.py C:/x/ev_t_e5884443/NEW.json
"""
import hashlib
import importlib.util
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('r35', ROOT / 'docs/research/autoresearch-ground-short-edges-r35.py')
assert spec is not None and spec.loader is not None
r35 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r35)  # #35 harness, unchanged (TOL, inject, Part)

TOL = r35.TOL
CAP_S = 300.0
R35 = ROOT / 'docs/research/autoresearch-ground-short-edges-r35.json'
EV = Path('C:/x/ev_t193')
INPUTS = {
    'C1': (EV / 'sil13_shared_v006/SM_SIL13_Ground.obj',
           '8f51940939e921dc206280c385c6f045da13fc2c1b78d685bf63d0c7d0f1a450', EV / 'sil13_shared_v006/ground-flat.obj'),
    'C2': (EV / 'vatutino_shared_v006/SM_VATUTINO_Ground.obj', None, EV / 'vatutino_shared_v006/ground-flat.obj'),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_obj(path):
    verts, faces, groups, mtls = [], [], [], []
    g = m = None
    for line in path.read_text(encoding='utf-8').splitlines():
        tok = line.split()
        if not tok:
            continue
        if tok[0] == 'v':
            verts.append([float(x) for x in tok[1:4]])
        elif tok[0] == 'g':
            g = ' '.join(tok[1:])
        elif tok[0] == 'usemtl':
            m = tok[1]
        elif tok[0] == 'f':
            idx = [int(x.split('/')[0]) for x in tok[1:]]
            faces.append(tuple(i - 1 if i > 0 else len(verts) + i for i in idx))
            groups.append(g)
            mtls.append(m)
    return np.array(verts, dtype=np.float64), tuple(faces), groups, mtls


def edge_faces(faces):
    out = defaultdict(list)
    for fi, f in enumerate(faces):
        for a, b in zip(f, (*f[1:], f[0])):
            out[(min(a, b), max(a, b))].append(fi)
    return out


def xy_key(p):
    return (round(p[0] * 1e6), round(p[1] * 1e6))


def flat_index(path):
    v, f, _, _ = read_obj(path)
    keys = {}
    for i, p in enumerate(v):
        keys.setdefault(xy_key(p), set()).add(i)
    return keys, set(edge_faces(f))


def measure(verts, faces, groups, mtls, flat):
    keys, fedges = flat
    ef = edge_faces(faces)
    e = np.array(sorted(ef), dtype=np.int64)
    length = np.linalg.norm(verts[e[:, 0]] - verts[e[:, 1]], axis=1)
    t = sum(len(f) - 2 for f in faces)
    cls, sub, samples = Counter(), Counter(), []
    for (a, b), ln in zip(map(tuple, e[length <= TOL]), length[length <= TOL]):
        fs = ef[(a, b)]
        gs = {groups[i] for i in fs}
        if gs == {'skirt'}:
            c = 'skirt'
        elif 'skirt' in gs:
            c = 'seam'
        else:
            ka = keys.get(xy_key(verts[a]), set())
            kb = keys.get(xy_key(verts[b]), set())
            c = 'flat' if any((min(x, y), max(x, y)) in fedges for x in ka for y in kb if x != y) else 'relief'
        cls[c] += 1
        sub['zero'] += int(ln <= 1e-9)
        sub['open_border'] += int(len(fs) == 1)
        sub['material_boundary'] += int(len({mtls[i] for i in fs}) > 1)
        if len(samples) < 400:
            samples.append(dict(cls=c, len_m=float(ln), a=verts[a].round(4).tolist(), b=verts[b].round(4).tolist(),
                                mtl=sorted({str(mtls[i]) for i in fs})))
    short = int((length <= TOL).sum())
    return dict(E=short, T=t, Qe=1e4 * short / t, classes=dict(cls), sub=dict(sub)), samples


def relief_detail(verts, faces, groups, flat_path):
    """Diagnostic (not scored): where the endpoints of short ground-only edges sit relative to the flat stage."""
    fv, ff, _, _ = read_obj(flat_path)
    keys = {xy_key(p) for p in fv}
    fe = np.array(sorted(edge_faces(ff)), dtype=np.int64)
    a0, d = fv[fe[:, 0], :2], fv[fe[:, 1], :2] - fv[fe[:, 0], :2]
    dd = np.maximum((d * d).sum(1), 1e-30)
    on_vertex, on_edge = Counter(), Counter()
    for (a, b), fs in edge_faces(faces).items():
        if np.linalg.norm(verts[a] - verts[b]) > TOL or {groups[i] for i in fs} != {'ground'}:
            continue
        on_vertex[int(xy_key(verts[a]) in keys) + int(xy_key(verts[b]) in keys)] += 1
        n = 0
        for q in (verts[a][:2], verts[b][:2]):
            t = np.clip(((q - a0) * d).sum(1) / dd, 0, 1)
            n += int(np.linalg.norm(a0 + t[:, None] * d - q, axis=1).min() <= 1e-5)
        on_edge[n] += 1
    return dict(endpoints_on_flat_vertex=dict(on_vertex), endpoints_on_flat_edge=dict(on_edge))


def rigid(verts):
    c, s = np.cos(np.radians(30)), np.sin(np.radians(30))
    r = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    return verts @ r.T + np.array([1000.0, -2000.0, 50.0])


def main(out):
    if out.exists() or out.resolve().parent == EV.resolve():
        raise SystemExit('refuse: --out exists or aliases the inputs')
    core35 = json.loads(R35.read_text(encoding='utf-8'))['core']['clean_runs'][0]
    start = time.monotonic()
    rows, checks, hashes = {}, {}, {}
    for iid, (path, digest, flat_path) in INPUTS.items():
        h, hf = sha(path), sha(flat_path)
        if digest and h != digest:
            raise ValueError(f'hash mismatch: {path}')
        hashes[iid] = {path.as_posix(): h, flat_path.as_posix(): hf}
        verts, faces, groups, mtls = read_obj(path)
        flat = flat_index(flat_path)
        reps = [measure(verts, faces, groups, mtls, flat)[0] for _ in range(3)]
        clean, samples = measure(verts, faces, groups, mtls, flat)
        rig, _ = measure(rigid(verts), faces, groups, mtls, flat)  # flat index stays in the original frame
        ck = dict(repeats=all(r == clean for r in reps),
                  rigid_E_T=(rig['E'], rig['T']) == (clean['E'], clean['T']),
                  partition=sum(clean['classes'].values()) == clean['E'])
        # rigid moves XY away from the flat frame, so class counts are compared on a jointly moved flat index
        fv, ff, _, _ = read_obj(flat_path)
        keys = {}
        for i, p in enumerate(rigid(fv)):
            keys.setdefault(xy_key(p), set()).add(i)
        rig2, _ = measure(rigid(verts), faces, groups, mtls, (keys, set(edge_faces(ff))))
        ck['rigid_classes'] = rig2['classes'] == clean['classes']
        if iid == 'C1':
            ck['parity35'] = (clean['E'], clean['T']) == (core35['E'], core35['T'])
        if iid == 'C2':
            part = r35.Part(path.stem, verts, faces, np.zeros(3))
            inj, moved = r35.inject(part)
            m, _ = measure(np.asarray(inj.vertices), faces, groups, mtls, flat)
            ck['injection'] = m['E'] - clean['E'] >= 25 and m['T'] == clean['T']
            injected = dict(moved=moved, E=m['E'], T=m['T'], Qe=m['Qe'])
        if sha(path) != h or sha(flat_path) != hf:
            raise ValueError(f'input changed: {iid}')
        rows[iid] = dict(clean=clean, median_Qe=statistics.median(float(r['Qe']) for r in reps), rigid=rig2,
                         detail=relief_detail(verts, faces, groups, flat_path), samples=samples)
        if iid == 'C2':
            rows[iid]['injected'] = injected
        checks[iid] = ck
    series_s = time.monotonic() - start
    done = series_s <= CAP_S
    c1, c2 = rows['C1']['clean'], rows['C2']['clean']
    a = c1['classes'].get('flat', 0) >= 0.9 * c1['E']
    b = c2['E'] == 0
    stable = all(all(c.values()) for c in checks.values())
    hyp = 'inconclusive' if not done else ('confirmed' if a and b and stable else 'refuted')
    report = dict(contract='docs/research/autoresearch-ground-core-localize.md', variant='Qe = 1e4*E(<=2mm edges)/T',
                  hypothesis=hyp, H37a_flat_share=c1['classes'].get('flat', 0) / max(c1['E'], 1), H37a=a, H37b=b,
                  stable=stable, inputs=hashes, rows=rows, checks=checks, series_seconds=round(series_s, 3),
                  numpy=np.__version__, python=sys.version.split()[0])
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print({k: report[k] for k in ('hypothesis', 'H37a_flat_share', 'H37a', 'H37b', 'stable', 'series_seconds')})
    for k, v in rows.items():
        print(k, v['clean'], v['detail'], v.get('injected'))
    print('checks failing:', {k: [n for n, ok in c.items() if not ok] for k, c in checks.items() if not all(c.values())})


if __name__ == '__main__':
    main(Path(sys.argv[1]))
