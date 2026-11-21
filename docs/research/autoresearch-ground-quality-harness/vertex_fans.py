"""Standing #34 read-only extension of the frozen Ground harness."""
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path
from typing import TypedDict

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from score import Part, open_edges, rigid, xview_gate
from tools.materials.npm_atlas_udim import read_obj
from twinqa.geometry.checks import fan_vertices
from twinqa.geometry.mesh import edge_uses

HERE = Path(__file__).resolve().parent
DUMPS = Path('C:/x/ev_t_193a0887/dumps-v002')
W1 = Path('C:/x/ev_t_304e8c0c/dumps/W1_Vatutino_v014_NPM.npz')
CORE = Path('C:/x/ev_t193/sil13_shared_v003/SM_SIL13_Ground.obj')


class Score(TypedDict):
    D: int
    T: int
    Q: float
    ids: list[int]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def measure(p) -> Score:
    tri = np.array([(a, f[i], f[i + 1]) for f in p.faces for a in f[:1]
                    for i in range(1, len(f) - 1)], dtype=np.int64).reshape(-1, 3)
    ids = np.arange(len(p.vertices))
    _, _, edges = edge_uses(tri, ids)
    a, b, c = tri.T
    flagged = fan_vertices(tri, ids, edges, (a == b) | (b == c) | (a == c))
    return Score(D=len(flagged), T=len(tri), Q=1e4 * len(flagged) / len(tri), ids=flagged)


def perturbations(p, base):
    rot = measure(rigid([p])[0])
    last = len(p.vertices) - 1
    reindexed = measure(Part(p.name, p.vertices[::-1], tuple(
        tuple(last - v for v in face) for face in reversed(p.faces)), p.location))
    reindexed['ids'] = sorted(last - v for v in reindexed['ids'])
    return dict(rigid=rot == base, reindex=reindexed == base)


def injected(p):
    anchors = sorted({v for f in p.faces for v in f})[:10]
    assert len(anchors) == 10
    n = len(p.vertices)
    extra = (p.vertices[anchors, None, :] + [[.1, 0, 0], [0, .1, 0]]).reshape(-1, 3)
    added = tuple((v, n + 2*i, n + 2*i + 1) for i, v in enumerate(anchors))
    return Part(p.name, np.vstack([p.vertices, extra]), tuple(p.faces) + added, p.location), anchors


def main(output):
    old = json.loads((HERE / 'r31.json').read_text(encoding='utf-8'))['inputs']
    files = {name.lstrip('*').split('_')[0]: (DUMPS / name.lstrip('*'), digest) for digest, name in
             (line.split() for line in (HERE / 'dumps.sha256').read_text().splitlines() if line.strip())}
    files['W1'] = W1, '29393a0b5ed7ce39a2e5a8d8c7b0014885ecf4bfcde5a9ae07088bfc76aa6683'
    assert set(files) == set(old) | {'W1'}
    rows = {}
    result = {'variant': 'Qfan indexed / no weld', 'hypothesis': 'inconclusive', 'inputs': rows,
              'not_measured': ['VPM', 'skirt', 'visible deviation', 'triangle budget', 'new native Max readback']}
    points = np.array([[0., 0., 0.], [1, 0, 0], [0, 1, 0], [-1, 0, 0], [0, -1, 0]])
    synthetic = {key: measure(Part('synthetic', points, ((0, 1, 2), second), None)) for key, second in
                 [('open_edge_shared', (1, 0, 4)), ('point_only_shared', (0, 3, 4))]}
    result['synthetic'] = synthetic
    start = time.monotonic()
    for i, key in enumerate(['A1', 'F4'] + sorted(set(files) - {'A1', 'F4'})):
        if time.monotonic() - start > 120:
            result['stop'] = 'wall budget'
            break
        path, digest = files[key]
        if sha(path) != digest:
            raise ValueError(f'hash mismatch: {path}')
        p, = (p for p in xview_gate.load_npz(path) if p.name.endswith('_Ground') and not p.name.upper().startswith('UCX_'))
        runs = [measure(p) for _ in range(3)]
        clean = runs[0]
        qs = [r['Q'] for r in runs]
        row = rows[key] = dict(path=str(path), sha256=digest, part=p.name, clean=clean, clean_Q_runs=qs,
                               repeat_exact=all(r == clean for r in runs), median=statistics.median(qs),
                               spread=max(qs)-min(qs), **perturbations(p, clean))
        if key in old:
            baseline = old[key]['clean']
            qv = 1e4 * baseline['V'] / baseline['T']
            row.update(T_parity=clean['T'] == baseline['T'], prior_Qv=qv, delta_vs_Qv=row['median'] - qv)
        if key == 'F1':
            row['open_edges'] = len(open_edges(p.faces))
        if key.startswith('A'):
            mutant, anchors = injected(p)
            injected_row = measure(mutant)
            row['injected'] = dict(**injected_row, **perturbations(mutant, injected_row), anchors=anchors,
                                   witness=(set(injected_row['ids']) == set(clean['ids']) | set(anchors)
                                            and injected_row['D'] == clean['D'] + 10
                                            and injected_row['T'] == clean['T'] + 10
                                            and injected_row['Q'] > clean['Q']))
        if sha(path) != digest:
            raise ValueError(f'input changed: {path}')
        print(key, clean['D'], clean['T'], round(row['median'], 4), flush=True)
        if i == 1:
            elapsed = time.monotonic() - start
            projection = elapsed * len(files)
            result['budget'] = dict(first_pair_s=elapsed, projected_s=projection, cap_s=120)
            if projection > 120:
                result['stop'] = 'projected wall budget'
                break
    if set(rows) == set(files) and time.monotonic() - start <= 120:
        aa = sorted(k for k in rows if k.startswith('A'))
        ff = sorted(k for k in rows if k.startswith('F'))
        pairs = {f'{f}-{a}': [qf - qa for qf, qa in zip(rows[f]['clean_Q_runs'], rows[a]['clean_Q_runs'])]
                 for f in ff + ['W1'] for a in aa}
        result['paired_gaps'] = {k: dict(median=statistics.median(v), spread=max(v)-min(v)) for k, v in pairs.items()}
        result['calibration_margin'] = min(rows[f]['median'] for f in ff) - max(rows[a]['median'] for a in aa)
        result['held_out_margin'] = min(result['paired_gaps'][f'W1-{a}']['median'] for a in aa)
        result['accepted_trigger_controls'] = [a for a in aa if rows[a]['clean']['D'] > 0]
        checks = result['checks'] = dict(
            separation=result['calibration_margin'] > 0 and min(rows[f]['median'] for f in ff) >=
            2 * max(1, max(rows[a]['median'] for a in aa)), held_out=result['held_out_margin'] > 0,
            parity=all(rows[k]['T_parity'] for k in old) and rows['F1']['open_edges'] == 843,
            clean=all(r['repeat_exact'] and r['reindex'] and r['rigid'] for r in rows.values()),
            injection=all(all(rows[a]['injected'][k] for k in ('rigid', 'reindex', 'witness')) for a in aa),
            synthetic=(synthetic['open_edge_shared']['ids'] == [] and synthetic['point_only_shared']['ids'] == [0]))
        result['hypothesis'] = 'confirmed' if all(checks.values()) else 'refuted'
    if result['hypothesis'] == 'confirmed':
        digest = '8f51940939e921dc206280c385c6f045da13fc2c1b78d685bf63d0c7d0f1a450'
        if CORE.is_file() and sha(CORE) == digest:
            mesh, _ = read_obj(CORE)
            reads = [measure(Part(CORE.stem, mesh.vertices, mesh.faces, None)) for _ in range(3)]
            if time.monotonic() - start <= 120 and sha(CORE) == digest and all(r == reads[0] and r['T'] == 26491 for r in reads):
                result['core'] = dict(path=str(CORE), sha256=digest, readback=reads[0], spread=0)
    if 'core' not in result:
        result['not_measured'].append('#1738 core (calibration prerequisite or OBJ parity/budget did not pass)')
    result['elapsed_s'] = time.monotonic() - start
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(result['hypothesis'], result.get('checks'), flush=True)


if __name__ == '__main__':
    main(Path(sys.argv[1]))
