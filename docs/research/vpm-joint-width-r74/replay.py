"""Replay frozen AC08 VPM width research; no production or asset writes."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
from typing import Any

import numpy as np
import PIL

R72 = 'e9179247c4934756170f3db7c8e2e8fe36e05487'


def pinned():
    path = 'docs/research/vpm-joint-pitch-r72/replay.py'
    source = subprocess.check_output(['git', 'show', f'{R72}:{path}'])
    r72: dict[str, Any] = {'__name__': 'pinned_r72'}
    exec(compile(source, f'{R72}:{path}', 'exec'), r72)
    fetch = r72['git_source']
    loader = fetch(r72['R71'], r72['LOADER'])
    runs = fetch(r72['BASE'], r72['JOINT'])['runs']
    spec = json.loads(r72['git_bytes'](r72['BASE'], r72['SPEC']))['finishes']
    return r72, loader, runs, spec


def census(profiles, runs, mm_per_px):
    widths, counts = [], []
    for row in profiles:
        lum = row.sum(axis=-1)
        complete = [b - a for a, b in runs(lum < 0.8 * np.median(lum))
                    if a > 0 and b < len(row)]
        if len(complete) < 3:
            raise ValueError('width not measured: fewer than three complete runs in a profile')
        widths.extend(complete)
        counts.append(len(complete))
    width = float(np.median(widths))
    return {'width_mm': width * mm_per_px, 'width_px': width, 'runs': counts}


def measure(profiles, runs, mm_per_px):
    before = profiles.tobytes()
    clean = census(profiles, runs, mm_per_px)
    columns = np.arange(profiles.shape[1])
    nearby = profiles[:, np.clip(columns[:, None] + np.arange(-4, 5), 0, len(columns)-1)]
    darkest = nearby.sum(axis=-1).argmin(axis=2)
    expanded = nearby[np.arange(len(profiles))[:, None], columns, darkest]
    bright = np.minimum(profiles, 247) + np.uint8(8)
    result = {'clean': clean}
    for name, mutated in [('widen', expanded), ('brightness', bright)]:
        changed = int(np.count_nonzero(np.any(mutated != profiles, axis=-1)))
        result[name] = census(mutated, runs, mm_per_px) | {'changed_px': changed or 'not_exercised'}
    if profiles.tobytes() != before or census(profiles, runs, mm_per_px) != clean:
        raise ValueError('clean profiles changed during injection')
    return result


def one_pair(r72, loader, runs, spec):
    rows, errors, controls_ok = {}, {}, True
    for version, label in r72['LABELS'].items():
        plan, _, tiles = loader['load'](version)
        measured, bindings = {}, {}
        for target in r72['FINISHES']:
            actual, udim = r72['tile_binding'](version, target)
            entry, tile = plan['finishes'][actual], tiles[udim]
            if entry['udim'] != udim or entry['px_per_m'] is None or tile.shape != (4096, 4096, 3):
                raise ValueError(f'unbound 4K tile: {version}/{target}')
            mm, nominal = 1000 * spec[target]['S'] / 4096, 2 * spec[target]['joint_half_mm']
            bindings[target] = {'actual_finish': actual, 'udim': udim, 'nominal_mm': nominal,
                                'mm_per_px': mm}
            if actual not in measured:
                measured[actual] = measure(tile[[1024, 2048, 3072]], runs, mm)
            data = measured[actual]
            clean, widen, bright = [data[k]['width_mm'] for k in ('clean', 'widen', 'brightness')]
            controls_ok &= (7 <= widen-clean <= 9 and abs(bright-clean) <= 1
                            and data['widen']['changed_px'] != 'not_exercised'
                            and data['brightness']['changed_px'] != 'not_exercised')
            bindings[target]['error_mm'] = abs(clean - nominal)
            if version == 'v010':
                controls_ok &= abs(widen - nominal) > 1
        errors[version] = max(row['error_mm'] for row in bindings.values())
        rows[version] = {'label': label, 'bindings': bindings, 'distinct_tiles': measured}
    return {'errors_mm': errors, 'controls_ok': controls_ok, 'rows': rows}


def classify(status, rounds):
    pairs = [r['errors_mm']['v007'] - r['errors_mm']['v010'] for r in rounds]
    result = {'hypothesis': 'inconclusive', 'paired_differences_mm': pairs,
              'paired_median_mm': None, 'paired_range_mm': None, 'median_E74_mm': None}
    if status == 'complete' and len(rounds) == 3:
        medians = {v: statistics.median(r['errors_mm'][v] for r in rounds) for v in ('v007', 'v010')}
        median, spread = statistics.median(pairs), max(pairs)-min(pairs)
        result.update(paired_median_mm=median, paired_range_mm=spread, median_E74_mm=medians)
        if spread <= 0.25 and all(r['controls_ok'] for r in rounds):
            result['hypothesis'] = ('confirmed' if min(pairs) > 0 and median >= 1
                                    and medians['v010'] <= 1 else 'refuted')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    parser.add_argument('--available-seconds', type=float, default=60)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    budget = min(60.0, args.available_seconds)
    status, error, rounds = 'complete', None, []
    pins = {}
    try:
        r72, loader, runs, spec = pinned()
        pins = {v: loader['PINS'][v] for v in r72['LABELS']}
        for i in range(3):
            t0 = time.perf_counter()
            if t0 - start >= budget:
                status = 'budget_stop'
                break
            pair = one_pair(r72, loader, runs, spec)
            wall = time.perf_counter() - t0
            rounds.append(pair | {'wall_s': wall})
            remaining = budget - (time.perf_counter() - start)
            if remaining < 0 or (i == 0 and (wall > 20 or 2 * wall > remaining)):
                status = 'budget_stop'
                break
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        status, error = 'measurement_error', str(exc)
    receipt = classify(status, rounds) | {
        'status': status, 'error': error, 'rounds': rounds, 'wall_s': time.perf_counter() - start,
        'budget_s': budget, 'R72': R72, 'pins': pins, 'python': sys.version.split()[0],
        'numpy': np.__version__, 'pillow': PIL.__version__,
        'candidate_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'not_measured': ['NPM', 'padding', 'density', 'UV binding', 'renders', 'KPP1 v004',
                         'Vatutino', 'Staropetrovskiy', 'other tiles'],
    }
    with (args.out / 'receipt.json').open('xb') as stream:
        stream.write((json.dumps(receipt, indent=2) + '\n').encode())
    print(json.dumps({k: v for k, v in receipt.items() if k not in ('rounds', 'pins')}))
    return 2 if error else 0


if __name__ == '__main__':
    raise SystemExit(main())
