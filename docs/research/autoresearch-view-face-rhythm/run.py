"""H166: replay #165 and test a full-view glazing rhythm veto."""

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
REV = 'a38d5137c016d9086423512446c353e7d6517fc6'
RUNNER = '6c44d165c225796b4ce036443468709ba3cfd84f6b022eedc68348e135bc1b48'
BASE = '7ac6236037f2250687d5f02e082b2c8814f8897f2d7ad1a8c0ba3217b8664d48'
LOCK = 'ba1bb998b19d50e1a066042e6362a9ec581949f0fe928433af2008060df4d5ea'


def sha(b):
    return hashlib.sha256(b).hexdigest()


def profile(mask):
    mean = mask.mean(axis=0)
    pos = (np.arange(128) + 0.5) / 128
    points = np.interp(pos, (np.arange(mean.size) + 0.5) / mean.size, mean)
    return points - points.mean()


def rhythm_gate(answer, kind, drawing, model):
    if answer is None or kind != 'full':
        return answer, None
    if model is None:
        return None, None
    a, b = profile(drawing), profile(model)
    den = float(np.linalg.norm(a) * np.linalg.norm(b))
    if not np.isfinite(den) or den <= 1e-12:
        return None, None
    score = float(np.clip(a @ b / den, -1, 1))
    return (answer if score >= 0.35 else None), score


def treatment(span, legacy, a161, a162, fx, pair, walls, baseline):
    import pymupdf

    p = fx['params']
    grid, height = p['grid_m'], p['view_height_m']
    masks = legacy['wall_masks'](pair, walls, grid, height)
    widths = {w['id']: w['render_w_m'] for w in walls}
    ak, ka, f1 = (span[k] for k in ('AK', 'KA', 'F1'))
    result = {}
    with pymupdf.open(fx['pdf']) as pdf:
        for v in fx['views']:
            name = v['id']
            raw, page_y, _, _ = a162.native_drawing(pdf[v['page'] - 1], v['clip_pt'], p, fx['legend_rgb'], a161)
            g = a162.register(raw, page_y, p['zoom'], a162.ANCHORS[name], height, grid)
            states = dict(clean=g, mirror=np.ascontiguousarray(g[:, ::-1]), blank=np.zeros_like(g),
                          shuffle=legacy['block_shuffle'](g, grid))
            if name == ka:
                states['I2_stretch_to_W19'] = span['resample'](g, widths['W19'] / (g.shape[1] * grid))
            if name == ak:
                states['I1_x0.85'] = span['resample'](g, span['I1_SCALE'])
            if name == f1:
                states.update(I3_label_full=g, I4_reset=g)
            src = baseline['views'][name]
            if set(states) != set(src['states']):
                raise RuntimeError(f'state inventory drift: {name}')
            evaluated = {}
            for label, mask in states.items():
                state = src['states'][label]
                a = state['b']
                b, score = rhythm_gate(a, state['kind'], mask, masks.get(a))
                evaluated[label] = dict(a=a, b=b, r=score, changed_cells=state['changed_cells'],
                                        relabelled=state['relabelled'],
                                        perturbation_exercised=label != 'clean' and state['exercised'],
                                        gate_exercised=a is not None and state['kind'] == 'full')
            result[name] = dict(states=evaluated, truth=src['truth'])
    tallies = {}
    for arm in 'ab':
        outcomes = [legacy['outcome'](r['states']['clean'][arm], r['truth'], n) for n, r in result.items()]
        tallies[arm] = {k: outcomes.count(k) for k in ('correct', 'wrong', 'abstain')}
    s = {n: r['states'] for n, r in result.items()}
    stretch = s[ka]['I2_stretch_to_W19']
    shuffle = s[ak]['shuffle']
    checks = dict(
        native_coverage=tallies['b'] == {'correct': 2, 'wrong': 0, 'abstain': 3},
        stretch_veto=stretch['a'] == 'W19' and stretch['b'] is None and stretch['perturbation_exercised'],
        clean_positive=s[ak]['clean']['b'] == 'W19',
        shuffled_positive=shuffle['a'] == 'W19' and shuffle['b'] is None and shuffle['perturbation_exercised'],
        fragment_parity=s[f1]['clean']['b'] == 'W19' and not s[f1]['clean']['gate_exercised'],
        clean_exclusion=s[ka]['clean']['b'] is None,
        blanks=len(s) == 7 and all(r['blank']['b'] is None and r['blank']['perturbation_exercised'] for r in s.values()),
        veto_only=all(x['b'] is None or x['a'] == x['b'] for r in s.values() for x in r.values()),
    )
    return dict(views=result, tallies=tallies, checks=checks)


def main(out):
    start = time.perf_counter()
    raw = subprocess.check_output(
        ['git', 'show', f'{REV}:docs/research/autoresearch-view-face-span/run.py'], cwd=ROOT,
    )
    if sha(raw) != RUNNER or sha((ROOT / 'uv.lock').read_bytes()) != LOCK:
        raise RuntimeError('runner or lock hash drift')
    span: dict[str, Any] = {'__file__': __file__, '__name__': 'span165'}
    exec(compile(raw, 'pinned-span165.py', 'exec'), span)
    evaluate = span['evaluate']
    hashes = []

    def paired(legacy, a161, a162, fx, prm, pair, rows, walls):
        if sha((ROOT / 'uv.lock').read_bytes()) != LOCK:
            raise RuntimeError('lock hash drift')
        baseline = evaluate(legacy, a161, a162, fx, prm, pair, rows, walls)
        if sha((ROOT / 'uv.lock').read_bytes()) != LOCK:
            raise RuntimeError('lock hash drift')
        baseline_hash = sha(span['encoded'](baseline))
        candidate = treatment(span, legacy, a161, a162, fx, pair, walls, baseline)
        data = span['encoded'](candidate)
        (pair / 'rhythm.json').write_bytes(data)
        hashes.append(dict(baseline_sha256=baseline_hash, rhythm_sha256=sha(data)))
        return baseline  # #165 still performs its original native byte-parity check and budget stop.

    span['evaluate'] = paired
    code = span['main'](out)
    receipt_path = out / 'receipt.json'
    inherited = json.loads(receipt_path.read_bytes())
    receipt_path.rename(out / 'upstream-series.json')
    status = inherited['status']
    if status == 'finished' and (len(hashes) != 3 or any(x['baseline_sha256'] != BASE for x in hashes)
                                 or len({x['rhythm_sha256'] for x in hashes}) != 1):
        status = 'parity_failed'
    candidate = json.loads((out / f'pair{len(hashes)}' / 'rhythm.json').read_bytes())
    hypothesis = ('confirmed' if all(candidate['checks'].values()) else 'refuted') if status == 'finished' else 'inconclusive'
    receipt = {k: inherited[k] for k in ('inputs', 'blender_sha256', 'median_s', 'spread_s', 'stage_pins')}
    receipt.update(revision165=REV, runner165_sha256=RUNNER, runner166_sha256=sha(Path(__file__).read_bytes()),
                   lock_sha256=LOCK, pairs=[p | h for p, h in zip(inherited['pairs'], hashes, strict=True)],
                   status=status, hypothesis=hypothesis, candidate=candidate,
                   elapsed_s=round(time.perf_counter() - start, 3))
    receipt_path.write_bytes((json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=1) + '\n').encode())
    print(status, hypothesis, candidate['tallies'], candidate['checks'])
    return code or int(status != 'finished')


if __name__ == '__main__':
    sys.exit(main(Path(sys.argv[1]).resolve()))
