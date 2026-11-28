"""Research-only roofline agreement gate on four frozen Olimpijsky views."""
import argparse
import hashlib
import json
import runpy
import statistics
import subprocess
from pathlib import Path
from time import perf_counter

import numpy as np
import pymupdf

R145 = '640b3678fb18ac2e5811742116a92e96ef236ab6'
R151 = '4a6c6b776ea4c16bf9b33b16be82465521f88d34'
R152 = '1045328d5585137af697d5991cde293dc31c8325'
ASSETS = {
    '151-view-face-transfer/inputs/АР.2_ Фасады_29.07.2026.pdf':
        'cdf938e88f3333d4b7e8750f02e424bc02355479613057d48abe38d10f3e6aa0',
    '151-view-face-transfer/r1/types-1.npz':
        '66105de78c7b5ecdaed5015a47ca4937ab35e130485c50de6a467cc580630a7a',
}
BLOBS = {
    'linework.py': (R145, 'elv/run.py'),
    'views.json': (R151, 'transfer/fixture.json'),
    'keyplan.py': (R152, 'keyplan/run_keyplan.py'),
    'key_fixture.json': (R152, 'keyplan/fixture.json'),
    'key_receipt.json': (R152, 'keyplan/receipt.json'),
}
AZ = (0, 90, 180, 270)
STATES = ('clean', 'masked', 'interior', 'ambiguous', 'opposite_only')
RES = .1
BUDGET = 120


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def encode(obj):
    return (json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def profile(raster):
    known = raster.any(axis=0)
    top = raster.argmax(axis=0)
    tall = np.flatnonzero(known & ((raster.shape[0] - 1 - top) >= 20))
    if not len(tall):
        return np.empty(0)
    region = slice(tall[0], tall[-1] + 1)
    top = np.where(known[region], top[region], np.nan)
    return (top - np.nanmin(top)) * RES


def cost(view, model):
    longer = max(len(view), len(model))
    required = (4 * longer + 4) // 5
    if not required or min(len(view), len(model)) < required:
        return None
    best = None
    for dx in range(required - len(view), len(model) - required + 1):
        a, b = max(0, -dx), min(len(view), len(model) - dx)
        v, m = view[a:b], model[a + dx:b + dx]
        finite = np.isfinite(v) & np.isfinite(m)
        n = int(finite.sum())
        if n >= required:
            value = float(np.abs(v[finite] - m[finite]).mean()) + 4 * (1 - n / longer)
            best = value if best is None else min(best, value)
    return None if best is None else round(best, 9)


def roof_pick(view, models):
    costs = {az: cost(view, p) for az, p in models.items()}
    ranked = sorted((c, az) for az, c in costs.items() if c is not None)
    if not ranked or ranked[0][0] > 2:
        return None, costs
    if len(ranked) > 1 and round(ranked[1][0] - ranked[0][0], 9) < .75:
        return None, costs
    return ranked[0][1], costs


def agree(mark, roof):
    return mark if mark is not None and mark == roof else None


def measure(root, rays_path, linework, views, key, key_fixture, reference):
    mark_rows = key['measure'](key_fixture, root)
    if mark_rows != reference:
        raise ValueError('A row parity with #152 failed')
    rows = []
    with np.load(rays_path, allow_pickle=False) as rays:
        if not np.isclose(rays['res'].item(), 2 * RES, rtol=0, atol=1e-12) or tuple(rays['az']) != AZ:
            raise ValueError('ray frame mismatch')
        models = {az: profile((rays[f'az{az:03d}_type'] > 0).repeat(2, 0).repeat(2, 1)) for az in AZ}
    with pymupdf.open(root / key_fixture['olimpijsky']['pdf']) as pdf:
        for row in mark_rows:
            v = views[row['view']]
            if v['gt_az'] != row['expected'] or v['kind'] != 'full':
                raise ValueError('fixture identity mismatch')
            page = pdf[v['page'] - 1]
            scale = linework['scale_pt_per_m'](page, v)
            seg = linework['segments'](page, v['box_pt'], scale)
            outline = profile(linework['raster_view'](seg, RES)) if len(seg) else np.empty(0)
            roof, costs = roof_pick(outline, models)
            for state in STATES:
                record = row['states'][state]
                record['B'] = agree(record['az'], roof)
                record['exercised'] = state == 'clean' or bool(record['added'] or record['removed'])
            rows.append({**row, 'roof': roof, 'cost_m': costs, 'profile_width_cols': len(outline),
                         'profile_observed_cols': int(np.isfinite(outline).sum()),
                         'model_width_cols': {az: len(p) for az, p in models.items()},
                         'scale_pt_per_m': scale})
    return rows


def tally(rows, state, field):
    counts = dict.fromkeys(('correct', 'wrong', 'abstain', 'not_exercised'), 0)
    for row in rows:
        record = row['states'][state]
        side = record[field]
        label = ('not_exercised' if not record['exercised'] else 'abstain' if side is None
                 else 'correct' if side == row['expected'] else 'wrong')
        counts[label] += 1
    answered = counts['correct'] + counts['wrong']
    return {**counts, 'answered_accuracy': counts['correct'] / answered if answered else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    parser.add_argument('--evidence-root', type=Path, default=Path('G:/Мой диск/AGR-evidence'))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    pins = {args.evidence_root / name: digest for name, digest in ASSETS.items()}
    pins[Path('uv.lock')] = 'ba1bb998b19d50e1a066042e6362a9ec581949f0fe928433af2008060df4d5ea'
    pins[Path(__file__)] = sha(__file__)
    for name, (rev, path) in BLOBS.items():
        data = subprocess.check_output(['git', 'show', f'{rev}:docs/research/autoresearch-view-face-{path}'])
        p = args.out / name
        p.write_bytes(data)
        pins[p] = hashlib.sha256(data).hexdigest()
    if any(sha(p) != s for p, s in pins.items()):
        raise ValueError('input SHA-256 mismatch')
    linework = runpy.run_path(str(args.out / 'linework.py'))
    key = runpy.run_path(str(args.out / 'keyplan.py'))
    load = lambda name: json.loads((args.out / name).read_bytes())
    views = load('views.json')['views']
    fixture = {'olimpijsky': load('key_fixture.json')['olimpijsky']}
    reference = [r for r in load('key_receipt.json')['rows'] if r['project'] == 'olimpijsky']
    if len(views) != 4 or len(reference) != 4 or fixture['olimpijsky']['pdf'] not in ASSETS:
        raise ValueError('unexpected fixture scope')
    started = perf_counter()
    walls, digests = [], []
    rays = args.evidence_root / next(n for n in ASSETS if n.endswith('.npz'))
    for i in range(3):
        if i and perf_counter() - started + 1.2 * walls[0] * (3 - i) > BUDGET:
            break
        t0 = perf_counter()
        rows = measure(args.evidence_root, rays, linework, views, key, fixture, reference)
        payload = encode(rows)
        (args.out / f'pair-{i + 1}.json').write_bytes(payload)
        digests.append(hashlib.sha256(payload).hexdigest())
        walls.append(round(perf_counter() - t0, 5))
    elapsed = perf_counter() - started
    unchanged = all(sha(p) == s for p, s in pins.items())
    a, b = ({s: tally(rows, s, field) for s in STATES} for field in ('az', 'B'))
    checks = dict(
        exercises=all(r['states'][s]['exercised'] for r in rows for s in STATES),
        reversal=all(r['states'][s]['reversal_parity'] for r in rows for s in STATES),
        wrong_mark_trigger=a['opposite_only']['wrong'] == 4,
        correct_ge3=b['clean']['correct'] >= 3,
        clean_wrong_0=b['clean']['wrong'] == 0,
        retain_p5=next(r for r in rows if r['view'].startswith('p5 '))['states']['clean']['B'] == 90,
        reject_wrong_mark=b['opposite_only']['abstain'] == 4,
        other_negative_controls=all(x[s]['abstain'] == 4 for x in (a, b) for s in STATES[1:4]),
    )
    completed = len(digests) == 3 and elapsed <= BUDGET
    valid = (completed and len(set(digests)) == 1 and unchanged
             and all(checks[k] for k in ('exercises', 'reversal', 'wrong_mark_trigger')))
    outcome = ('confirmed' if all(checks.values()) else 'refuted') if valid else 'inconclusive'
    receipt = dict(revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                   A=a, B=b, checks=checks, hypothesis=outcome, run_status='complete' if completed else 'budget_stop',
                   rows=rows, wall_s=walls, elapsed_s=round(elapsed, 5),
                   median_s=statistics.median(walls) if completed else None,
                   spread_s=round(max(walls) - min(walls), 5) if completed else None,
                   pair_sha256=digests, input_parity=unchanged, A_parity=True,
                   pins={str(p): s for p, s in pins.items()}, immutable_blobs=BLOBS)
    (args.out / 'receipt.json').write_bytes(encode(receipt))
    print(outcome, b['clean'], walls)


if __name__ == '__main__':
    main()
