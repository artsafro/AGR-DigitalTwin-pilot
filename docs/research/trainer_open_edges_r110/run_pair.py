"""Replay the frozen R110 experiment, using the published R109 FBX reader."""
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

from replay import measure

ROOT = Path(__file__).resolve().parents[3]
PRIOR = 'ca92876502dd89cacfe2e8d317e2f2ccdf9d76b5:docs/research/trainer_layer_r109/replay.py'
PRIOR_SHA = 'e32b3a43b028d4dda3a4bc3a3593a0a96521d36238aaf60a4bda53a9bfd1d37f'
SOURCE = Path('G:/Мой диск/AGR-evidence/1855-trainer-v0/bank/63a-stage1/STLB-04_RR_AR.fbx')
SOURCE_SHA = '2b4d0201d3d2454344bba263500363fcc528a322bd2702ece0fac38e39a158d7'
BUDGET = 180


def controls():
    v = ((0., 0., 0.), (1., 0., 0.), (0., 1., 0.), (0., 0., 1.))
    p = ((0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3))
    split = ((4, 6, 5), *p[1:])
    cases = {
        'unchanged': (v, p, (0, 0, 0)),
        'split': (v + v[:3], split, (6, 0, 3)),
        'missing_face': (v + v[:3], split[:-1], (7, 3, 3)),
        'offset_corner': (v + ((1/1024, 0., 0.),) + v[1:3], split, (6, 4, 2)),
    }
    out = {}
    for name, (vertices, faces, expected) in cases.items():
        row = measure(vertices, faces)
        actual = tuple(row[k] for k in ('raw_open', 'exact_open', 'changed_corners'))
        if actual != expected or row['collapsed'] or row['extra_nonmanifold']:
            raise ValueError(f'control {name}: expected {expected}, got {row}')
        out[name] = {**row, 'reindex': 'exercised' if row['changed_corners'] else 'not_exercised'}
    return out


def census(data, prior):
    top = prior['read_fbx'](data)
    geometry = {p[0]: {k[0]: k for k in children}
                for n, p, children in top['Objects'][2] if n == 'Geometry'}
    summaries = defaultdict(Counter)
    rows = {}
    for gid, (names, polys, _) in prior['wall_geometries'](top).items():
        coords = geometry[gid]['Vertices'][1][0]
        vertices = tuple(zip(coords[::3], coords[1::3], coords[2::3], strict=True))
        family = prior['family'](names)
        row = measure(vertices, polys)
        rows[str(gid)] = [family, row, 'exercised' if row['changed_corners'] else 'not_exercised']
        s = summaries[family]
        s.update(row)
        s['geometries'] += 1
        s['raw_open_geometries'] += row['raw_open'] > 0
        s['exact_open_geometries'] += row['exact_open'] > 0
        s['changed_geometries'] += row['changed_corners'] > 0
        s['open_count_decreased'] += row['exact_open'] < row['raw_open']
        s['open_count_increased'] += row['exact_open'] > row['raw_open']
        s['recovered'] += (row['raw_open'] > 0 and row['exact_open'] == 0 and
                           row['collapsed'] == 0 and row['extra_nonmanifold'] <= 0)
        s['with_extra_nonmanifold'] += row['extra_nonmanifold'] > 0
        s['with_collapsed'] += row['collapsed'] > 0
    return summaries, rows


def digest(data):
    return sha256(data).hexdigest()


def blob(spec):
    return subprocess.check_output(['git', 'show', spec], cwd=ROOT)


def encode(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def read():
    asset = SOURCE.read_bytes()
    if digest(asset) != SOURCE_SHA:
        raise ValueError('source digest mismatch')
    return asset


def main(variant, output):
    start = time.monotonic()
    for script in (Path(__file__).resolve(), Path(__file__).resolve().with_name('replay.py')):
        if len(variant) != 40 or blob(f'{variant}:{script.relative_to(ROOT).as_posix()}') != script.read_bytes().replace(b'\r\n', b'\n'):
            raise ValueError('variant must pin both scripts')
    output = Path(output).resolve()
    raw_output = output.with_suffix('.rows.json')
    if output == raw_output or output.exists() or raw_output.exists() or not output.is_relative_to(ROOT / 'tmp'):
        raise ValueError('need a fresh output path in worktree tmp')
    code = blob(PRIOR)
    if digest(code) != PRIOR_SHA:
        raise ValueError('prior reader digest mismatch')
    prior = {'__name__': 'prior_r109', '__file__': str(ROOT / PRIOR.split(':', 1)[1])}
    exec(compile(code, PRIOR, 'exec'), prior)

    read()
    pairs = []
    witnesses, summary, rows, target = {}, {}, {}, Counter()
    for _ in range(3):
        t = time.monotonic()
        witnesses = controls()
        summary, rows = census(read(), prior)
        target = summary[prior['FAMILY'].strip()]
        pairs.append({'s': round(time.monotonic() - t, 3), 'rows_sha256': digest(encode(rows)),
                      'controls_sha256': digest(encode(witnesses)), 'recovered': target['recovered']})
        remaining = 3 - len(pairs)
        if remaining and time.monotonic() - start + pairs[-1]['s'] * remaining > BUDGET:
            break
    read()
    wall = round(time.monotonic() - start, 3)
    gains = [p['recovered'] for p in pairs]
    complete = len(pairs) == 3 and wall <= BUDGET
    parity = target['geometries'] == 1210 and target['raw_open_geometries'] == 148
    agreement = len({(p['rows_sha256'], p['controls_sha256']) for p in pairs}) == 1
    verdict = 'inconclusive'
    if complete and parity and agreement:
        verdict = 'confirmed' if statistics.median(gains) >= 74 else 'refuted'
    receipt = {'variant': variant, 'python': sys.version, 'source': str(SOURCE), 'source_sha256': SOURCE_SHA,
               'reader': PRIOR, 'reader_sha256': PRIOR_SHA, 'run_status': 'complete' if complete else 'budget_stop',
               'wall_s': wall, 'hypothesis': verdict, 'paired': pairs, 'parity': parity, 'agreement': agreement,
               'median_gain': statistics.median(gains) if complete else None,
               'paired_spread': max(gains) - min(gains) if complete else None,
               'controls': witnesses, 'target': target, 'families': summary,
               'not_measured': ['trainer passage', 'accepted/rejected model calibration', 'held-out etalon']}
    output.parent.mkdir(parents=True, exist_ok=True)
    with raw_output.open('xb') as f:
        f.write(encode(rows))
    with output.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(receipt, f, sort_keys=True, ensure_ascii=False, indent=2)
        f.write('\n')
    print(json.dumps({k: receipt[k] for k in ('hypothesis', 'run_status', 'median_gain', 'paired_spread', 'parity', 'target', 'wall_s')}))


if __name__ == '__main__':
    main(*sys.argv[1:])
