"""Run the frozen #148 OBSERVE replay; no production or delivery writes."""
from collections import Counter
from hashlib import sha256
import json
from math import ceil, cos, floor, radians
from pathlib import Path
import runpy
from statistics import median
import subprocess
import sys
from time import monotonic

import numpy as np

R146 = 'e839c2ee177c8ea5a766988019f2db6e55b1e61a'
R147 = '159dffcb33f81c4bf566a1da1ec659603b4fa957'
LOCK = 'ba1bb998b19d50e1a066042e6362a9ec581949f0fe928433af2008060df4d5ea'
CEILING = 840


def blob(rev, suffix, name):
    path = f'docs/research/autoresearch-view-face-{suffix}/{name}'
    return subprocess.check_output(['git', 'show', f'{rev}:{path}'])


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def dump(path, data):
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=1) + '\n').encode('utf-8'))


def span(depth, facing, res):
    """Longest supported column run in any fixed-pitch depth window."""
    valid = np.isfinite(depth) & (facing >= cos(radians(15)))
    if not valid.any():
        return 0.
    step, longest = .15, 0
    lo, hi = depth[valid].min(), depth[valid].max()
    for index in range(floor(float(lo) / step) - 1, floor(float(hi) / step) + 1):
        left = index * step
        hits = valid & (depth >= left) & (depth <= left + .30)
        cols = np.flatnonzero(hits.sum(axis=0) >= ceil(1. / res - 1e-9))
        pieces = np.split(cols, np.flatnonzero(np.diff(cols) > 1 + floor(.5 / res + 1e-9)) + 1)
        longest = max(longest, *(int(c[-1] - c[0] + 1) for c in pieces if len(c)), 0)
    return round(longest * res, 8)


def veto(answer, width, spans):
    supported = spans.get(answer, 0.)
    return answer if supported > 0 and width <= supported + .6 + 1e-9 else None


def measure(out):
    upstream = out.with_suffix('.r146.py')
    upstream.write_bytes(blob(R146, 'density', 'run.py'))
    runpy.run_path(str(upstream))['measure'](out, 'elv')
    pair = json.loads((out / 'paired.json').read_bytes())
    oracle = json.loads(blob(R147, 'veto', 'receipt.json'))['rows']
    oracle = [row for row in oracle if row['group'].startswith('elv/')]
    rows = pair['rows']
    if len(rows) != 80 or rows != [{k: v for k, v in r.items() if k not in ('veto_pick', 'verdict_C')}
                                   for r in oracle]:
        raise ValueError('ELV baseline parity mismatch')
    with np.load(out / 'native/rays-1.npz') as rays:
        res = float(rays['res'])
        if res != .1 or list(rays['az']) != [0, 90, 180, 270]:
            raise ValueError('unexpected native ray grid')
        spans = {}
        for az in rays['az']:
            key = f'az{az:03d}'
            facing = rays[key + '_normal'] @ [cos(radians(az)), np.sin(radians(az)), 0.]
            spans[str(az)] = span(rays[key + '_depth'], facing, res)
    tracked = []
    for historic, row in zip(oracle, rows, strict=True):
        a, b = row['pick'], row['adjusted']['pick']
        c = str(a) if a is not None and a == b else None
        if c != historic['veto_pick']:
            raise ValueError('agreement parity mismatch')
        d = veto(c, row['width_m'], spans)
        truth = str(row['gt_az'])
        outcome = lambda pick: ('not_exercised' if row['case'] == 'mirror' and not row['changed_pixels']
                                else 'abstain' if pick is None else 'correct' if pick == truth else 'wrong')
        if outcome(c) != historic['verdict_C']:
            raise ValueError('baseline verdict parity mismatch')
        tracked.append({k: row[k] for k in ('view', 'page', 'case', 'group', 'width_m', 'changed_pixels')}
                       | dict(truth=truth, C=c, D=d, verdict_C=outcome(c), verdict_D=outcome(d),
                              changed_answers=int(c != d)))
    dump(out / 'candidate.json', dict(parity=len(rows), pins=pair['pins'], spans=spans, rows=tracked))


def summarize(rows):
    result = {}
    for scope in sorted({r['group'] for r in rows}):
        for arm in ('C', 'D'):
            c = Counter(r[f'verdict_{arm}'] for r in rows if r['group'] == scope)
            right, wrong, abstain = (c[k] for k in ('correct', 'wrong', 'abstain'))
            total, answered = right + wrong + abstain, right + wrong
            result[f'{scope}/{arm}'] = dict(correct=right, wrong=wrong, abstain=abstain,
                not_exercised=c['not_exercised'], accuracy=right / answered if answered else None,
                abstain_rate=abstain / total if total else None)
    return result


def gate(rows):
    wrong = [r for r in rows if r['verdict_C'] == 'wrong']
    return (len(wrong) == 2 and all(r['verdict_D'] == 'abstain' for r in wrong)
            and all(r['verdict_D'] == 'correct' for r in rows if r['verdict_C'] == 'correct'
                    and r['group'] in ('elv/full', 'elv/fragment', 'elv/crop'))
            and all(r['D'] is None for r in rows if r['C'] is None))


def series(out):
    start = monotonic()
    out.mkdir(parents=True, exist_ok=False)
    script = Path(__file__).resolve()
    times, hashes, snapshot = [], [], {}
    status = 'finished'
    reason = None
    try:
        if digest('uv.lock') != LOCK:
            raise ValueError('uv.lock mismatch')
        for i in (1, 2, 3):
            tick, target = monotonic(), out / f'pair-{i}'
            with target.with_suffix('.log').open('xb') as log:
                subprocess.run([sys.executable, str(script), str(target), '--pair'], check=True,
                               timeout=max(1, CEILING - (monotonic() - start)), stdout=log,
                               stderr=subprocess.STDOUT)
            times.append(round(monotonic() - tick, 3))
            packet = target / 'candidate.json'
            hashes.append(digest(packet))
            snapshot = json.loads(packet.read_bytes())
            print(f'pair {i}: {times[-1]} s, parity {snapshot["parity"]}/80', flush=True)
            if hashes[-1] != hashes[0]:
                status = 'nonidentical_repeats'
                break
            if i < 3 and monotonic() - start + 1.15 * times[0] * (3 - i) > CEILING:
                status = 'budget_stop'
                break
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        status, reason = 'execution_error', str(exc)
    rows = snapshot.get('rows', [])
    finished = status == 'finished' and len(times) == 3
    hypothesis = ('confirmed' if gate(rows) else 'refuted') if finished else 'inconclusive'
    dump(out / 'receipt.json', dict(status=status, reason=reason, hypothesis=hypothesis,
         measured_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
         r146=R146, r147=R147, lock=LOCK, runner_sha256=digest(script), pair_hashes=hashes,
         pair_s=times, median_s=median(times) if finished else None,
         min_s=min(times) if finished else None, max_s=max(times) if finished else None,
         wall_s=round(monotonic() - start, 3), summary=summarize(rows), **snapshot))
    print(status, hypothesis, reason or '', flush=True)
    return 0 if finished else 2


if __name__ == '__main__':
    dest = Path(sys.argv[1]).resolve()
    if sys.argv[2:] == ['--pair']:
        measure(dest)
    else:
        sys.exit(series(dest))
