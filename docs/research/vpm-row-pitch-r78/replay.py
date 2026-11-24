"""Standing #78: compare one row-balanced variant with the pinned pooled census."""
import hashlib
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import PIL

R72 = "e9179247c4934756170f3db7c8e2e8fe36e05487"
P72 = "docs/research/vpm-joint-pitch-r72/replay.py"


def git_bytes(rev, path):
    return subprocess.check_output(["git", "show", f"{rev}:{path}"])


def load_source(rev, path, transform=lambda text: text) -> dict[str, Any]:
    ns = {"__name__": "pinned_r78_dependency"}
    exec(compile(transform(git_bytes(rev, path).decode()), f"{rev}:{path}", "exec"), ns)
    return ns


def candidate():
    def change_aggregation(text):
        old = 'gaps.extend(np.diff(centres))'
        if text.count(old) != 1:
            raise ValueError('pinned census aggregation not found exactly once')
        return text.replace(old, 'gaps.append(np.median(np.diff(centres)))')

    return load_source(R72, P72, change_aggregation)["pitch"]


R77 = "d4335c4916ed7c7d7545c68cd14c47c99df90001"
BASE = "01e48513aa9bba11553bc3c0c296414e7ba26c6d"
P77 = "docs/research/kpp1-vpm-pitch-r77/replay.py"
LIMIT = 180
KPP_TILES = [1001, 1005, 1006, 1007, 1008]


def receipt_at(rev, path):
    return json.loads(git_bytes(rev, str(Path(path).with_name('receipt.json').as_posix())))


def census_inventory(obj):
    # Retain all non-score properties, including original run counts, applicability
    # and actual changed-pixel counts for both mutations and all inputs.
    scores = {'E72', 'E', 'observed_px', 'relative_error', 'flagged', 'in_bound', 'bound_applies'}
    if isinstance(obj, dict):
        return {k: census_inventory(v) for k, v in obj.items() if k not in scores}
    if isinstance(obj, list):
        return [census_inventory(v) for v in obj]
    return obj


def one_round(ac, kpp, loader, new_pitch):
    ac_runs = load_source(ac['BASE'], ac['JOINT'])['runs']
    kpp_runs = load_source(kpp['BASE'], kpp['JOINT'])['runs']
    ac_spec = json.loads(git_bytes(ac['BASE'], ac['SPEC']))['finishes']
    kpp_spec = json.loads(git_bytes(kpp['BASE'], kpp['SPEC']))['finishes']
    versions = {}
    for variant, pitch in (('pooled', ac['pitch']), ('row_median', new_pitch)):
        # Reuse both prior rounds with unchanged imports/decodes, binds, stimuli and resets.
        ac_round = type(ac['one_round'])(ac['one_round'].__code__, {**ac, 'pitch': pitch})
        versions[variant] = {'ac08': ac_round(loader['load'], ac_runs, ac_spec),
                             'kpp1': kpp['one_round'](pitch, kpp_runs, kpp_spec)['rows']}
    return versions


def measure(rows, historical, ac, kpp):
    old, new = rows['pooled'], rows['row_median']
    a, k = new['ac08'], [r for r in new['kpp1'] if r['state'] == 'measured']
    coverage = sorted(r['udim'] for r in k) == KPP_TILES and all(
        r['state'] in {'measured', 'not_exercised'} for r in new['kpp1'])
    result = {'baseline_parity': old == historical,
              'inventory_parity': census_inventory(old) == census_inventory(new), 'coverage': coverage}
    if not coverage:
        return result
    v007, v010 = (a[v]['E72']['clean'] for v in ('v007', 'v010'))
    kpp_e = max(r['E'] for r in k)
    result.update(E={'v007': v007, 'v010': v010, 'kpp1': kpp_e}, D=v007 - max(v010, kpp_e),
                  clean_in_bound=v007 >= 1 and max(v010, kpp_e) <= kpp['BOUND'])
    rejected = a['v007']['per_finish']
    result['witnesses_ok'] = (ac['witnesses_ok'](a) and all(
        0.47 <= f['relative_error'] <= 0.53 for f in a['v010']['per_finish']['half_pitch'].values()
    ) and all(
        f['relative_error'] < rejected['clean'][n]['relative_error']
        for n, f in rejected['half_pitch'].items()) and all(
        abs(f['relative_error'] - report['per_finish']['clean'][n]['relative_error']) <= 0.01
        for report in a.values() for n, f in report['per_finish']['brightness_plus8'].items()) and all(
        r[v]['state'] == 'exercised' and r[v]['in_bound']
        for r in k for v in ('half_pitch', 'brightness_plus8')))
    return result


def main(out):
    out.mkdir(parents=True, exist_ok=False)
    ac, kpp = load_source(R72, P72), load_source(R77, P77)
    loader = load_source(ac['R71'], ac['LOADER'])
    historical = {'ac08': receipt_at(R72, P72)['rounds'][0]['rows'],
                  'kpp1': receipt_at(R77, P77)['round1']['rows']}
    if Path('uv.lock').read_bytes().replace(b'\r\n', b'\n') != git_bytes(BASE, 'uv.lock'):
        raise ValueError('uv.lock differs from the frozen revision')
    start, rounds, status, error = time.perf_counter(), [], 'complete', None
    pitch = candidate()
    for i in range(3):
        t0 = time.perf_counter()
        if t0 - start >= LIMIT:
            status = 'budget_stop'
            break
        try:
            rows = one_round(ac, kpp, loader, pitch)
            scores = measure(rows, historical, ac, kpp)
        except (OSError, ValueError, KeyError) as exc:
            status, error = 'input_or_measurement_error', str(exc)
            break
        wall = time.perf_counter() - t0
        rounds.append({'wall_s': wall, 'scores': scores, 'rows': rows})
        if time.perf_counter() - start + (2 * wall if i == 0 else 0) > LIMIT:
            status = 'budget_stop'
            break
    ds = [r['scores']['D'] for r in rounds if 'D' in r['scores']]
    median = statistics.median(ds) if len(ds) == 3 else None
    spread = max(ds) - min(ds) if len(ds) == 3 else None
    verdict = 'inconclusive'
    if status == 'complete' and median is not None and spread is not None and spread <= 0.01 and all(
        all(r['scores'][k] for k in ('coverage', 'baseline_parity', 'inventory_parity')) for r in rounds
    ):
        if min(ds) <= 0 or median < 0.97 or not all(r['scores']['clean_in_bound'] for r in rounds):
            verdict = 'refuted'
        elif all(r['scores']['witnesses_ok'] for r in rounds):
            verdict = 'confirmed'
    receipt = {'card': 't_b481fff8', 'candidate': 'median_of_row_medians',
               'candidate_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'revisions': {'ac08': R72, 'kpp1': R77, 'loader': ac['R71'], 'lock': BASE},
               'pin_manifest': {'ac08_root': str(loader['DRIVE']),
                                'ac08_hashes': {v: loader['PINS'][v] for v in ac['LABELS']},
                                'ac08_artifacts_in_order': [loader[x] for x in ('VPM_ZIP', 'ATLAS', 'PLAN')],
                                'kpp1': {str(kpp['ZIP']): kpp['ZIP_SHA']}},
               'versions': {'python': sys.version.split()[0], 'numpy': np.__version__, 'pillow': PIL.__version__},
               'status': status, 'error': error, 'H78': verdict, 'D78': ds, 'median': median, 'spread': spread,
               'wall_s': time.perf_counter() - start, 'round_wall_s': [r['wall_s'] for r in rounds]}
    print(json.dumps({**receipt, 'scores': [r['scores'] for r in rounds]}))
    with (out / 'receipt.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump({**receipt, 'rounds': rounds}, stream, indent=2, default=float)
        stream.write('\n')
    return 2 if error else 0


if __name__ == '__main__':
    raise SystemExit(main(Path(sys.argv[1])))
