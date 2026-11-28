"""Paired OBSERVE replay of #154 with one manually registered stage band."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import statistics
import subprocess
from time import perf_counter

import numpy as np

REV = '1369c97893e4d38c5e6b2c96f1a070bbc969b0e7'
PREFIX = 'docs/research/autoresearch-view-face-corroboration/'
CUTS = {6: 820.5, 7: 983.3, 8: 967.2}
BUDGET = 120


def clip_band(seg, y):
    """Keep y >= cut in world coordinates, dropping zero-length intersections."""
    out = []
    dropped = trimmed = 0
    for xa, ya, xb, yb in seg:
        if min(ya, yb) >= y:
            out.append((xa, ya, xb, yb))
        elif max(ya, yb) <= y:
            dropped += 1
        else:
            x = xa + (xb - xa) * (y - ya) / (yb - ya)
            out.append((x, y, xb, yb) if ya < y else (xa, ya, x, y))
            trimmed += 1
    return np.asarray(out, dtype=float).reshape(-1, 4), dict(trimmed=trimmed, dropped=dropped)


def blob(rev, path):
    return subprocess.check_output(['git', 'show', f'{rev}:{path}'])


def row_parity(live, published):
    return json.loads(json.dumps(live, allow_nan=False)) == published


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    parser.add_argument('--evidence-root', type=Path, default=Path('G:/Мой диск/AGR-evidence'))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    pins = {}

    def stage(name, data):
        path = args.out / name
        path.write_bytes(data)
        pins[path] = hashlib.sha256(data).hexdigest()
        return path

    prev = runpy.run_path(str(stage('baseline.py', blob(REV, PREFIX + 'run.py'))))
    reference = json.loads(stage('baseline-receipt.json', blob(REV, PREFIX + 'receipt.json')).read_bytes())
    for name, (rev, path) in prev['BLOBS'].items():
        stage(name, blob(rev, 'docs/research/autoresearch-view-face-' + path))
    sha, encode = prev['sha'], prev['encode']
    pins.update({args.evidence_root / k: v for k, v in prev['ASSETS'].items()})
    pins[Path('uv.lock')] = hashlib.sha256(blob(REV, 'uv.lock')).hexdigest()
    pins[Path(__file__)] = sha(__file__)
    unchanged = lambda: all(sha(p) == s for p, s in pins.items())
    if not unchanged():
        raise ValueError('input SHA-256 mismatch before run')
    load = lambda n: json.loads((args.out / n).read_bytes())
    linework = runpy.run_path(str(args.out / 'linework.py'))
    key = runpy.run_path(str(args.out / 'keyplan.py'))
    views = load('views.json')['views']
    fixture = {'olimpijsky': load('key_fixture.json')['olimpijsky']}
    marks = [r for r in load('key_receipt.json')['rows'] if r['project'] == 'olimpijsky']
    if len(views) != 4 or len(marks) != 4 or fixture['olimpijsky']['pdf'] not in prev['ASSETS']:
        raise ValueError('unexpected fixture scope')
    rays, = (p for p in pins if p.suffix == '.npz')
    states = prev['STATES']
    walls, payloads = [], []
    result_a, result_b, counts = [], [], {}
    started = perf_counter()
    for i in range(3):
        if i and perf_counter() - started + 1.2 * walls[0] * (3 - i) > BUDGET:
            break
        t0 = perf_counter()
        result_a = prev['measure'](args.evidence_root, rays, linework, views, key, fixture, marks)
        if not row_parity(result_a, reference['rows']):
            (args.out / 'baseline-mismatch.json').write_bytes(encode(result_a))
            raise ValueError('A row parity with #154 failed')
        counts = {}

        def segments(page, box, scale):
            page_num = page.number + 1
            lines = linework['segments'](page, box, scale)
            if page_num in CUTS:
                kept, count = clip_band(lines, -CUTS[page_num] / scale)
            else:
                kept, count = lines, dict(dropped=0, trimmed=0)
            counts[page_num] = dict(**count, before=len(lines), after=len(kept),
                                    exercised=any(count.values()))
            return kept

        result_b = prev['measure'](args.evidence_root, rays, {**linework, 'segments': segments},
                                   views, key, fixture, marks)
        payload = encode(dict(A=result_a, B=result_b, clips=counts))
        payloads.append(hashlib.sha256(payload).hexdigest())
        (args.out / f'pair-{i + 1}.json').write_bytes(payload)
        walls.append(round(perf_counter() - t0, 5))
    elapsed = perf_counter() - started
    a, b = ({s: prev['tally'](rows, s, 'B') for s in states} for rows in (result_a, result_b))
    p5a = next(r for r in result_a if r['view'].startswith('p5 '))
    rows = {int(r['view'].split()[0][1:]): r for r in result_b}
    correct = lambda r: r['states']['clean']['B'] == r['expected']
    controls = dict(p5_exact=rows[5] == p5a and not counts[5]['exercised'],
                    clipping_exercises=all(counts[p]['exercised'] for p in CUTS),
                    mark_parity=all({k: v for k, v in ra['states'][s].items() if k != 'B'} ==
                                    {k: v for k, v in rb['states'][s].items() if k != 'B'}
                                    for ra, rb in zip(result_a, result_b, strict=True) for s in states))
    bounds = dict(zero_wrong=b['clean']['wrong'] == 0, clean_correct_ge3=b['clean']['correct'] >= 3,
                  keep_p5_p6=all(correct(rows[p]) for p in (5, 6)),
                  gain_p7_or_p8=any(correct(rows[p]) for p in (7, 8)),
                  negative_abstains=all(b[s]['abstain'] == 4 for s in states[1:]))
    finished = len(walls) == 3 and elapsed <= BUDGET
    input_parity = unchanged()
    valid = finished and len(set(payloads)) == 1 and input_parity and all(controls.values())
    outcome = ('confirmed' if all(bounds.values()) else 'refuted') if valid else 'inconclusive'
    receipt = dict(revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                   hypothesis=outcome, run_status='complete' if finished else 'budget_stop',
                   A=a, B=b, controls=controls, bounds=bounds, clips=counts, A_parity=True,
                   input_parity=input_parity, pair_sha256=payloads, elapsed_s=round(elapsed, 5),
                   wall_s=walls, median_s=statistics.median(walls) if finished else None,
                   spread_s=round(max(walls) - min(walls), 5) if finished else None,
                   pins={str(p): s for p, s in pins.items()}, baseline_rev=REV,
                   parent_blobs=prev['BLOBS'])
    (args.out / 'receipt.json').write_bytes(encode(receipt))
    print(outcome, a['clean'], b['clean'], walls)


if __name__ == '__main__':
    main()
