"""Paired OBSERVE replay using #163's exact native renderer, registration, and matcher."""

import hashlib
import json
import runpy
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REV = '56f608b577090a8f82cf4e2df2c722879199e378'
BASE_BODY = '5cedce6e622d06b092a0b7be146623feee51a23a83b2ea0a6d79d03849709aca'
PINS = {
    'run.py': '0a26eb893d36d7912d0991ccc7a400b9f82311dc969f874a64bd6165a9a25fa2',
    'blender_walls.py': 'a3784cff27cda3af53f097f93f729ffde81ecb5fb722cd4afc3e4987278993ef',
    'params.json': '358579f55b2dca837c64a7b00c33caccabbd7487c7ae3323e8fa9e2441c8794d',
}
BUDGET_S = 600
KA = 'p15 K-A'
AK = "p15 A'-K (7 boxes)"
F1 = 'p16 fragment 1 (box bay)'


def require_competitor(answer, eligible):
    return answer if len(set(eligible)) >= 2 else None


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')


def digest(content):
    return hashlib.sha256(content).hexdigest()


def summarize(rows, classify):
    scored = {arm: [] for arm in ('a', 'b')}
    by_view = {}
    for row in rows:
        name = row['view']
        eligible = row['states']['clean']['eligible']  # #163 eligibility depends only on width
        states = {}
        for label, state in row['states'].items():
            a = state['answer']
            states[label] = dict(a=a, b=require_competitor(a, eligible),
                                 changed_cells=state['changed_cells'], exercised=state['exercised'])
        clean = states['clean']
        for arm in scored:
            verdict = classify(clean[arm], row['gt_walls'], name)
            if verdict != 'diagnostic':
                scored[arm].append(verdict)
        by_view[name] = dict(eligible=eligible, states=states, truth=row['gt_walls'])
    f1 = by_view[F1]
    original = f1['eligible']
    winner = f1['states']['clean']['a']
    singleton = [wall for wall in original if wall == winner]
    removal = dict(removed=sorted(set(original) - set(singleton)),
                   singleton=singleton, answer=require_competitor(winner, singleton),
                   restored=require_competitor(winner, original[::-1]))
    totals = {arm: {kind: verdicts.count(kind) for kind in ('correct', 'wrong', 'abstain')}
              for arm, verdicts in scored.items()}
    checks = {
        'native_bounds': totals == {'a': {'correct': 2, 'wrong': 0, 'abstain': 3},
                                    'b': {'correct': 1, 'wrong': 0, 'abstain': 4}},
        'known_exclusion_removed': by_view[KA]['states']['clean']['a'] == 'W19'
        and by_view[KA]['states']['clean']['b'] is None,
        'singleton_collateral': by_view[AK]['states']['clean']['a'] == 'W19'
        and by_view[AK]['states']['clean']['b'] is None,
        'all_other_clean_verdicts_unchanged': all(
            v['states']['clean']['a'] == v['states']['clean']['b'] for name, v in by_view.items()
            if name not in (KA, AK)),
        'blank': all(v['states']['blank']['exercised'] and v['states']['blank']['b'] is None
                     for v in by_view.values()),
        'injected_competitor_removal': winner == 'W19' and bool(removal['removed'])
        and removal['singleton'] == ['W19'] and removal['answer'] is None and removal['restored'] == winner,
    }
    return dict(views=by_view, totals=totals, injected=removal, checks=checks)


def main(out):
    start = time.perf_counter()
    out.mkdir(parents=True)
    stage = out / 'upstream163'
    stage.mkdir()
    root = Path(__file__).resolve().parents[3]
    for name, sha in PINS.items():
        blob = subprocess.check_output([
            'git', 'show', f'{REV}:docs/research/autoresearch-view-face-wallseg/{name}'
        ], cwd=root)
        if digest(blob) != sha:
            raise RuntimeError(f'upstream blob mismatch: {name}')
        (stage / name).write_bytes(blob)
    legacy = runpy.run_path(str(stage / 'run.py'))
    a161, a162, fx = legacy['load_upstream']()
    prm = json.loads((stage / 'params.json').read_bytes())
    prm['min_overlap'] = fx['params']['min_overlap']

    def preflight():
        for name, sha in PINS.items():
            if digest((stage / name).read_bytes()) != sha:
                raise RuntimeError(f'staged blob mismatch: {name}')
        if a161.sha(a161.BLENDER) != legacy['PINS']['blender']:
            raise RuntimeError('Blender hash mismatch')
        for name, sha in fx['sha256'].items():
            if a161.sha(fx[name]) != sha:
                raise RuntimeError(f'native input hash mismatch: {name}')

    pairs: list[dict[str, Any]] = []
    candidate = None
    status = 'finished'
    for i in range(1, 4):
        inner = time.perf_counter()
        preflight()
        pair = out / f'pair{i}'
        rows, walls, timing = legacy['one_pair'](a161, a162, fx, prm, pair)
        body = encoded(dict(rows=rows, walls=walls))
        (pair / 'baseline.json').write_bytes(body)
        candidate = summarize(rows, legacy['outcome'])
        (pair / 'candidate.json').write_bytes(encoded(candidate))
        preflight()
        wall_s = round(time.perf_counter() - inner, 3)
        row = dict(index=i, native=timing, wall_s=wall_s, baseline_sha256=digest(body),
                   candidate_sha256=digest(encoded(candidate)))
        pairs.append(row)
        print(json.dumps(row), flush=True)
        if row['baseline_sha256'] != BASE_BODY or row['candidate_sha256'] != pairs[0]['candidate_sha256']:
            status = 'parity_failed'
            break
        elapsed = time.perf_counter() - start
        if elapsed > BUDGET_S or (i == 1 and elapsed + 2 * wall_s > BUDGET_S):
            status = 'budget_stop'
            break
    assert candidate is not None
    times = [p['wall_s'] for p in pairs]
    verdict = ('confirmed' if all(candidate['checks'].values()) else 'refuted') if status == 'finished' else 'inconclusive'
    rec = dict(upstream=REV, lock_sha256=a161.sha(root / 'uv.lock'), stage_pins=PINS,
               candidate_sha256=a161.sha(__file__), inputs=fx['sha256'],
               blender_sha256=legacy['PINS']['blender'], pairs=pairs, candidate=candidate,
               status=status, hypothesis=verdict, median_s=statistics.median(times),
               spread_s=round(max(times) - min(times), 3))
    (out / 'receipt.json').write_bytes((json.dumps(rec, ensure_ascii=False, sort_keys=True, indent=1) + '\n').encode())
    print(verdict, status, candidate['totals'], candidate['checks'])
    return int(status != 'finished')


if __name__ == '__main__':
    sys.exit(main(Path(sys.argv[1]).resolve()))
