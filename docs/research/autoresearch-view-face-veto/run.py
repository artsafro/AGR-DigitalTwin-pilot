"""Replay the frozen #147 OBSERVE contract (raw-vs-chance disagreement veto) from the repository root.

new-case: docs/research/autoresearch-view-face-veto/run.py - #147 OBSERVE replay runner
"""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import runpy
from statistics import median
import subprocess
import sys
from time import monotonic

R146 = 'e839c2ee177c8ea5a766988019f2db6e55b1e61a'
R146_RUNNER = 'docs/research/autoresearch-view-face-density/run.py'
R146_RECEIPT = 'docs/research/autoresearch-view-face-density/receipt.json'
JOBS = ('elv', 'kpp', 'obr')
PICK_A = {'elv': 'pick', 'kpp': 'B', 'obr': 'B'}
CEILING_S = 1500
ALLOWANCE = 1.15


def git_blob(rev, path):
    return subprocess.check_output(['git', 'show', f'{rev}:{path}'])


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def dump(path, data):
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=1) + '\n').encode('utf-8'))


def answer(value):
    """Normalise a pick (int, str, None or {'answer': ...}) to a string face id or None."""
    if isinstance(value, dict):
        value = value.get('answer')
    return None if value is None else str(value)


def veto(a, b):
    """C answers only when the raw (A) and chance-corrected (B) scorers both answer the same face."""
    a, b = answer(a), answer(b)
    return a if a is not None and a == b else None


def verdict(pick, truth, scope, changed):
    if scope == 'mirror' and not changed:
        return 'not_exercised'
    return 'abstain' if pick is None else 'correct' if pick == str(truth) else 'wrong'


def measure(out, job):
    """Run the pinned #146 native measurement (A + B, full A parity inside) and add arm C."""
    out.parent.mkdir(parents=True, exist_ok=True)
    runner = out.parent / f'{out.name}.r146.py'
    runner.write_bytes(git_blob(R146, R146_RUNNER))
    api = runpy.run_path(str(runner))
    api['measure'](out, job)
    rows = json.loads((out / 'paired.json').read_bytes())['rows']
    truth_key = 'gt' if job == 'obr' else 'gt_az'
    delta_key = 'changed_edge_px' if job == 'obr' else 'changed_pixels'
    for row in rows:
        scope = row['group'].split('/', 1)[1]
        row['veto_pick'] = veto(row[PICK_A[job]], row['adjusted']['pick'])
        row['verdict_C'] = verdict(row['veto_pick'], row[truth_key], scope, row.get(delta_key))
    dump(out / 'veto.json', {'job': job, 'rows': rows})


def b_parity(rows):
    """Arm B and verdicts must reproduce the published #146 pair row by row (excluding new C fields)."""
    oracle = json.loads(git_blob(R146, R146_RECEIPT))['rows']
    strip = [{k: v for k, v in r.items() if k not in ('veto_pick', 'verdict_C')} for r in rows]
    return strip == oracle


def summarize(rows):
    summary = {}
    for name in sorted({r['group'] for r in rows}):
        for arm in ('A', 'B', 'C'):
            counts = Counter(r[f'verdict_{arm}'] for r in rows if r['group'] == name)
            right, wrong, abstain = (counts[k] for k in ('correct', 'wrong', 'abstain'))
            answered, total = right + wrong, right + wrong + abstain
            summary[f'{name}/{arm}'] = dict(correct=right, wrong=wrong, abstain=abstain,
                not_exercised=counts['not_exercised'], accuracy=right / answered if answered else None,
                abstain_rate=abstain / total if total else None)
    return summary


def gate(rows, tally):
    """Frozen H147 bounds (contract docs/research/autoresearch-view-face-veto.md)."""
    return (all(r['verdict_C'] != 'wrong' for r in rows)
            and tally['elv/full/C']['correct'] >= 5
            and tally['elv/crop/C']['correct'] >= 15
            and any(r.get('view') == 'p23 frag D-G' and r['verdict_C'] == 'correct' for r in rows)
            and tally['kpp1/full/C']['correct'] >= 3
            and tally['kpp1/crop/C']['correct'] >= 20
            and tally['ac08/full/C']['abstain'] == 4 and tally['ac08/crop/C']['abstain'] == 36)


def series(out):
    start = monotonic()
    out.mkdir(parents=True, exist_ok=False)
    hashes, times, timing_rows, parity = [], [], [], []
    status, rows = 'finished', []
    script = Path(__file__).resolve()
    for i in (1, 2, 3):
        pair_start, timing = monotonic(), {}
        for job in JOBS:
            tick, target = monotonic(), out / f'{i}-{job}'
            with target.with_suffix('.log').open('xb') as log:
                subprocess.run([sys.executable, str(script), str(target), job], check=True,
                               timeout=max(1, CEILING_S - (monotonic() - start)),
                               stdout=log, stderr=subprocess.STDOUT)
            timing[job] = round(monotonic() - tick, 3)
            print(f'{i}/{job}: {timing[job]} s', flush=True)
        paths = {j: out / f'{i}-{j}' / 'veto.json' for j in JOBS}
        hashes.append({j: digest(p) for j, p in paths.items()})
        rows = [row for p in paths.values() for row in json.loads(p.read_bytes())['rows']]
        parity.append(b_parity(rows))
        times.append(round(monotonic() - pair_start, 3))
        timing_rows.append(timing)
        if i < 3 and monotonic() - start + ALLOWANCE * times[0] * (3 - i) > CEILING_S:
            status = 'budget_stop'
            break
    if not all(parity):
        status = 'b_parity_failed'
    elif status == 'finished' and any(h != hashes[0] for h in hashes[1:]):
        status = 'nonidentical_repeats'
    tally = summarize(rows)
    hypothesis = ('confirmed' if gate(rows, tally) else 'refuted') if status == 'finished' else 'inconclusive'
    dump(out / 'receipt.json', dict(status=status, hypothesis=hypothesis, r146=R146, runner=digest(script),
         lock=digest('uv.lock'), measured_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
         b_parity=parity, pair_hashes=hashes, pair_s=times, fixture_s=timing_rows, median_s=median(times),
         min_s=min(times), max_s=max(times), wall_s=round(monotonic() - start, 3), summary=tally, rows=rows))
    print(status, hypothesis, flush=True)


if __name__ == '__main__':
    target = Path(sys.argv[1]).resolve()
    if len(sys.argv) == 3:
        measure(target, sys.argv[2])
    else:
        series(target)
