"""Read-only #38 extension of the frozen #35 Qe scorer.

new-case: docs/research/autoresearch-ground-qe-triangulation-r38.py - OBSERVE perturbation receipt
"""
import argparse
import importlib.util
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = 'docs/research'
STEM = f'{RESEARCH}/autoresearch-ground-short-edges-r35'
REV35 = 'ec403b83113d89f6b8a98f648421a33a17819603'
REV36 = 'c6e4fb78d6a77b1809600ef453a80a718d15ca0c'
VPM = Path('C:/x/ev_t_cb0ffb18/r36-v001')
CAP = 240
STATES = ('raw', 'fan0', 'fan1')
REVIEW_SHA = 'acda9aed450dc64cf87984d55fd2e726339b217d196168036e5d0f3a38375651'


def blob(rev, path):
    return subprocess.check_output(['git', 'show', f'{rev}:{path}'], cwd=ROOT)


def load_scorer():
    path = ROOT / f'{STEM}.py'
    if path.read_bytes().replace(b'\r\n', b'\n') != blob(REV35, f'{STEM}.py'):
        raise ValueError('r35 scorer differs from frozen source')
    spec = importlib.util.spec_from_file_location('r35', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fan(faces, root):
    out, diagonals = [], set()
    for f in faces:
        if len(f) == 3:
            out.append(f)
            continue
        seq = f[root:] + f[:root]
        out.extend((seq[0], seq[j], seq[j + 1]) for j in range(1, len(seq) - 1))
        diagonals.update(tuple(sorted((seq[0], i))) for i in seq[2:-1])
    return tuple(out), diagonals


def short_edges(r35, verts, faces):
    edges = r35.edge_array(faces)
    lens = np.linalg.norm(verts[edges[:, 0]] - verts[edges[:, 1]], axis=1)
    return set(map(tuple, edges[lens <= r35.TOL].tolist()))


def census(faces, raw_count):
    return dict(face_count=len(faces), ngon_faces=sum(len(f) > 3 for f in faces),
                inserted_diagonals=len(faces) - raw_count)


def status(states):
    if not all(states[s]['inserted_diagonals'] > 0 for s in STATES[1:]):
        return 'not_exercised'
    baseline = states['raw']['runs'][0]['E']
    return 'invariant' if all(s['runs'][0]['E'] == baseline for s in states.values()) else 'changed'


def coverage(rows):
    return {
        label: sorted(k for k, r in rows.items()
                      if k.startswith('F') == rejected and r['status'] != 'not_exercised')
        for label, rejected in (('accepted', False), ('rejected', True))
    }


def verdict(rows, separation, valid):
    if not valid:
        return 'inconclusive'
    if any(r['status'] == 'changed' for r in rows.values()) or not all(
        r['pass_margin'] for r in separation.values()
    ):
        return 'refuted'
    return 'confirmed' if all(coverage(rows).values()) else 'inconclusive'


def examine(r35, p, expected=None):
    rows = {}
    verts = np.asarray(p.vertices, dtype=np.float64)
    raw = short_edges(r35, verts, p.faces)
    for i, name in enumerate(STATES):
        faces, diagonals = (p.faces, set()) if i == 0 else fan(p.faces, i - 1)
        part = r35.Part(p.name, verts, faces, p.location)
        reps = [r35.measure(part) for _ in range(3)]
        short = raw if i == 0 else short_edges(r35, verts, faces)
        added, removed = short - raw, raw - short
        clean = reps[0]
        q = [r['Qe'] for r in reps]
        rows[name] = dict(runs=reps, median_Qe=statistics.median(q), spread=max(q)-min(q),
                          added_short_edges=sorted(added), removed_short_edges=sorted(removed),
                          oracle=len(short) == clean['E'] and not removed and added <= diagonals,
                          repeat=all(r == clean for r in reps), **census(faces, len(p.faces)))
    first = rows['raw']['runs'][0]
    parity = (expected is None or first == expected) and all(
        all(row['runs'][0][key] == first[key] for key in ('T', 'V')) for row in rows.values())
    return dict(states=rows, parity=parity,
                valid=parity and all(row['oracle'] and row['repeat'] for row in rows.values()),
                status=status(rows))


def witness(r35, p):
    offset = len(p.vertices)
    quad = np.array([[-1, 0, 0], [0, -.0005, 0], [1, 0, 0], [0, .0005, 0]]) + [10000, 0, 0]
    return r35.Part(p.name, np.vstack((p.vertices, quad)), tuple(p.faces) + (tuple(range(offset, offset+4)),), p.location)


def core_part(r35, path):
    from tools.materials.npm_atlas_udim import read_obj

    mesh, _ = read_obj(path)
    return r35.Part(path.stem, np.asarray(mesh.vertices, dtype=np.float64), mesh.faces, np.zeros(3))


def add_census(row, faces):
    for i, s in enumerate(STATES):
        transformed = faces if i == 0 else fan(faces, i - 1)[0]
        row['states'][s].update(census(transformed, len(faces)))
    del row['invariant']
    row['status'] = status(row['states'])


def regrade(source):
    import hashlib

    payload = source.read_bytes()
    if hashlib.sha256(payload).hexdigest() != REVIEW_SHA:
        raise ValueError('review replay SHA-256 mismatch')
    report = json.loads(payload)
    r35 = load_scorer()
    for name, row in [*report['rows'].items(), ('core', report['core'])]:
        path = Path(row['input'])
        if r35.sha(path) != row['sha256']:
            raise ValueError(f'input SHA-256 mismatch: {path}')
        part = core_part(r35, path) if name == 'core' else r35.ground(path)
        add_census(row, part.faces)
        if name == 'A1':
            add_census(report['injected'], witness(r35, part).faces)
        del part
        if r35.sha(path) != row['sha256']:
            raise ValueError(f'input changed: {path}')
    historical = report['hypothesis']
    rows = report['rows']
    valid = all(r['valid'] for r in rows.values()) and report['core']['valid'] and (
        report['injected']['valid'] and report['injected']['expected'])
    report.update(hypothesis=verdict(rows, report['separation'], valid), coverage=coverage(rows),
                  provenance=dict(mode='offline_census', source=source.as_posix(), sha256=REVIEW_SHA,
                                  original_hypothesis=historical, geometry_metrics='from reviewer replay',
                                  observer_sha256=r35.sha(Path(__file__))))
    return report


def measure():
    r35 = load_scorer()
    seal35 = json.loads(blob(REV35, f'{STEM}.json'))
    seal36 = json.loads(blob(REV36, f'{RESEARCH}/autoresearch-ground-qe-transfer-r36.json'))
    manifest = {}
    for line in blob(REV35, f'{RESEARCH}/autoresearch-ground-quality-harness/dumps.sha256').decode().splitlines():
        sha, file = line.split()
        file = file.lstrip('*')
        name = file.split('_', 1)[0]
        manifest[name] = (r35.DUMPS / file, sha, seal35['rows'][name]['clean_runs'][0])
    vpm_ids = ['Skolkovo_VPM', 'COD_VPM', 'Donskoy_VPM']
    for name in vpm_ids:
        ref = seal36['rows'][name]
        manifest[name] = (VPM / ref['dump'], ref['dump_sha256'], ref['clean_runs'][0])
    first = ['A1', 'F4', 'Donskoy_VPM']
    rows, timings = {}, {}
    start = time.monotonic()
    pair = projected = None
    injected = None
    for name in first + sorted(manifest.keys() - set(first)):
        before = time.monotonic()
        path, digest, expected = manifest[name]
        if r35.sha(path) != digest:
            raise ValueError(f'input SHA-256 mismatch: {path}')
        p = r35.ground(path)
        row = rows[name] = dict(input=path.as_posix(), sha256=digest, part=p.name, **examine(r35, p, expected))
        if name == 'A1':
            w = witness(r35, p)
            injected = examine(r35, w)
            injected['delta'] = [[injected['states'][s]['runs'][0][k] - row['states'][s]['runs'][0][k]
                                  for k in ('E', 'T')] for s in STATES]
            added = injected['states']['fan1']['added_short_edges']
            control_added = row['states']['fan1']['added_short_edges']
            injected['expected'] = (
                injected['delta'] == [[0, 2], [0, 2], [1, 2]]
                and sorted(added) == sorted(control_added + [(len(p.vertices)+1, len(p.vertices)+3)]))
            del w
        del p
        if r35.sha(path) != digest:
            raise ValueError(f'input changed: {path}')
        timings[name] = time.monotonic() - before
        if name == 'F4':
            pair = time.monotonic() - start
        if name == 'Donskoy_VPM':
            projected = 10 * pair + 2 * timings[name]
            if projected > CAP:
                break
        if time.monotonic() - start > CAP:
            break
    separation = {}
    for state in STATES:
        a = max(r['states'][state]['median_Qe'] for k, r in rows.items() if not k.startswith('F'))
        f = min(r['states'][state]['median_Qe'] for k, r in rows.items() if k.startswith('F'))
        separation[state] = dict(max_A=a, min_F=f, margin=f-a, pass_margin=f > a and f >= 2*max(1, a),
                                 accepted_triggers=[k for k, r in rows.items()
                                                    if not k.startswith('F') and r['states'][state]['runs'][0]['E']])
    valid = len(rows) == len(manifest) and all(r['valid'] for r in rows.values()) and injected['valid'] and injected['expected']
    core = None
    if valid and separation['raw']['pass_margin'] and time.monotonic() - start < CAP:
        path, digest = r35.CORE
        if r35.sha(path) != digest:
            raise ValueError('core SHA-256 mismatch')
        p = core_part(r35, path)
        core = dict(input=path.as_posix(), sha256=digest, part=p.name,
                    **examine(r35, p, seal35['core']['clean_runs'][0]))
        if r35.sha(path) != digest:
            raise ValueError('core changed')
    elapsed = time.monotonic() - start
    valid = valid and elapsed <= CAP and (not separation['raw']['pass_margin'] or bool(core and core['valid']))
    hypothesis = verdict(rows, separation, valid)
    report = dict(hypothesis=hypothesis, scorer=REV35, vpm_fixture_revision=REV36,
                  coverage=coverage(rows),
                  candidate_sha256=r35.sha(Path(__file__)), numpy=np.__version__, python=sys.version.split()[0],
                  states=STATES, tolerance_m=r35.TOL, separation=separation, rows=rows, injected=injected, core=core,
                  timing=dict(pair_s=pair, estimated_s=projected, elapsed_s=elapsed, cap_s=CAP, inputs_s=timings),
                  not_measured=['native exporter', 'rejected VPM', 'independent rejected site', 'UV/visual',
                                'triggering accepted controls in states whose accepted_triggers list is empty'])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    parser.add_argument('--review-replay', type=Path)
    args = parser.parse_args()
    out = args.out
    if out.parent.resolve() != (ROOT / RESEARCH).resolve() or out.suffix != '.json' or out.exists():
        raise SystemExit('Expected a new .json file directly in docs/research')
    report = regrade(args.review_replay) if args.review_replay else measure()
    with out.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(report['hypothesis'], report['coverage'])


if __name__ == '__main__':
    main()
