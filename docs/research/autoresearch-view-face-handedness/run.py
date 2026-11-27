"""Paired #149 replay and opposite-face reflection refusal; OBSERVE only."""

from decimal import Decimal
import hashlib
import json
from pathlib import Path
import runpy
from statistics import median
import subprocess
import sys
from time import monotonic
from types import SimpleNamespace

import numpy as np


REV = '94b74bcaeb2e00d6cdc1d486bf59ac7420bdf854'
MEASURED_REV = '200726691ee7317bc1710ecc3f8e1bbf1456937b'
UPSTREAM = 'docs/research/autoresearch-view-face-material'
BUDGET = 900
MARGIN = Decimal('0.10')


def veto(pick, score, reflected):
    if pick is None:
        return None
    lead = Decimal(str(score)) - Decimal(str(reflected))
    return pick if lead >= MARGIN else None


def check_baseline(rows, expected):
    if len(rows) != len(expected):
        raise ValueError('baseline row count differs')
    for i, (row, ref) in enumerate(zip(rows, expected, strict=True)):
        if row != {k: v for k, v in ref.items() if k not in ('C', 'E')}:
            raise ValueError(f'baseline parity failed at row {i}: {row["view"]} {row["case"]}')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, data):
    path.write_bytes((json.dumps(data, ensure_ascii=False, sort_keys=True, indent=1) + '\n').encode('utf-8'))


def paired_measure(api, out, n, fixture, reader, deadline):
    measure = api['measure']
    scope = measure.__globals__
    scorer = scope['S']
    score, decide = scorer.face_score, scorer.decide
    candidates, reflection = [], []

    def collect(view, model, slack):
        if monotonic() >= deadline:
            raise subprocess.TimeoutExpired('paired PDF case scoring', BUDGET)
        candidates.append((view, model, slack))
        return score(view, model, slack)

    def decide_pair(scores):
        by_az = dict(zip(scores, candidates, strict=True))
        candidates.clear()
        pick = decide(scores)
        view = next(iter(by_az.values()))[0]
        flipped = view[:, ::-1]
        opposite = (pick + 180) % 360 if pick is not None else None
        counterfactual = None
        if opposite is not None:
            _, model, slack = by_az[opposite]
            counterfactual = round(float(score(flipped, model, slack)), 9)
        accepted = veto(pick, scores.get(pick), counterfactual)
        reflection.append(dict(f_pick=accepted, reflected_opposite=opposite,
                               reflected_score=counterfactual,
                               reflection_changed_pixels=int(np.count_nonzero(view != flipped))))
        return pick

    def run_bounded(cmd, *, timeout, **kwargs):
        limit = min(timeout, deadline - monotonic())
        if limit <= 0:
            raise subprocess.TimeoutExpired(cmd, 0)
        return subprocess.run(cmd, timeout=limit, **kwargs)

    scope['S'] = SimpleNamespace(face_score=collect, decide=decide_pair, majority=scorer.majority)
    native_subprocess = scope['subprocess']
    scope['subprocess'] = SimpleNamespace(run=run_bounded)
    try:
        rows, _ = measure(out, n, fixture, reader)
    finally:
        scope['S'] = scorer
        scope['subprocess'] = native_subprocess
    for row, trial in zip(rows, reflection, strict=True):
        pick = trial['f_pick']
        trial['f_outcome'] = 'abstain' if pick is None else 'correct' if pick == row['gt_az'] else 'wrong'
    return rows, reflection


def checks(rows, summary):
    control = {(r['view'], r['case']): r for r in rows}
    return dict(no_wrong=not any(g['wrong'] for g in summary.values()),
                full_ge5=summary['full']['correct'] >= 5,
                real_fragments_both=summary['fragment']['correct'] == 2,
                crops_ge32=summary['synthetic_crop']['correct'] >= 32,
                full_positive_preserved=control['p18 I-A', 'full']['f_outcome'] == 'correct',
                mirror_wrong_refused=control['p19 10-1', 'mirror']['f_outcome'] == 'abstain'
                and control['p19 10-1', 'mirror']['changed_pixels'] > 0)


def main(out):
    out.mkdir(parents=True)
    upstream = out / 'pinned-149'
    upstream.mkdir()
    for name in ('run.py', 'score.py', 'rays_type.py', 'receipt.json'):
        revision = REV if name == 'receipt.json' else MEASURED_REV
        (upstream / name).write_bytes(subprocess.check_output(['git', 'show', f'{revision}:{UPSTREAM}/{name}']))
    baseline_path = upstream / 'receipt.json'
    baseline = json.loads(baseline_path.read_bytes())
    lock_hash = sha('uv.lock')
    if lock_hash != baseline['uv_lock_sha256']:
        raise ValueError('uv.lock differs from #149')
    for name in ('run.py', 'score.py', 'rays_type.py'):
        if sha(upstream / name) != baseline['pins'][name]:
            raise ValueError(f'#149 tool pin mismatch: {name}')
    api = runpy.run_path(str(upstream / 'run.py'))
    native = out / 'native'
    fixture, pins = api['stage'](native)
    if pins != baseline['pins']:
        raise ValueError('staged pins differ from #149')
    reader = runpy.run_path(str(native / 'r145.py'), run_name='r145')
    walls, hashes = [], []
    started = monotonic()
    status = 'finished'
    result: dict[str, object] = {'hypothesis': 'inconclusive'}
    for n in range(1, 4):
        if walls and monotonic() - started + 1.2 * walls[0] * (4 - n) > BUDGET:
            status = 'budget_stop'
            break
        t = monotonic()
        try:
            base, trial = paired_measure(api, native, n, fixture, reader, started + BUDGET)
        except subprocess.TimeoutExpired:
            status = 'budget_stop'
            break
        walls.append(round(monotonic() - t, 3))
        check_baseline(base, baseline['rows'])
        rows = [{**a, **b} for a, b in zip(base, trial, strict=True)]
        path = out / f'pair-{n}.json'
        save(path, rows)
        hashes.append(sha(path))
        print(f'pair {n}: {walls[-1]} s; baseline parity {len(rows)}/{len(rows)}', flush=True)
        if monotonic() - started > BUDGET:
            status = 'budget_stop'
            break
    for role, row in fixture['inputs'].items():
        if sha(row['path']) != row['sha256'] or sha(native / f'elv.{role}') != row['sha256']:
            raise ValueError(f'input drift on {role}')
    if status == 'finished' and len(set(hashes)) != 1:
        status = 'parity_failed'
    if hashes:
        rows = json.loads((out / 'pair-1.json').read_bytes())
        summary_d, summary_f = api['summarize'](rows), api['summarize'](rows, 'f_outcome')
        bounds = checks(rows, summary_f)
        result.update(rows=rows, summary_D=summary_d, summary_F=summary_f, checks=bounds)
        if status == 'finished':
            result.update(hypothesis='confirmed' if all(bounds.values()) else 'refuted',
                          median_s=median(walls), range_s=round(max(walls) - min(walls), 3))
    result.update(status=status, walls_s=walls, total_timed_s=round(monotonic() - started, 3),
                  pair_sha256=hashes, pins=pins, baseline_sha256=sha(baseline_path),
                  blender_sha256=api['EXE_HASH'], driver_sha256=sha(__file__), uv_lock_sha256=lock_hash,
                  baseline_receipt_revision=REV, upstream_measured_revision=MEASURED_REV)
    save(out / 'receipt.json', result)
    print(json.dumps({k: v for k, v in result.items() if k in
                      ('hypothesis', 'status', 'walls_s', 'checks', 'summary_D', 'summary_F')}), flush=True)


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve())
