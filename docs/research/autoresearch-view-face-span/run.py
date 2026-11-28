"""H165 OBSERVE: full-view length-agreement veto on #163's exact native renderer, registration and matcher.

Replay (pilot host; owner's Weltbau folder, Blender 4.4; #161-#163 refs fetched):
  uv run --offline --locked --extra pdf-review python docs/research/autoresearch-view-face-span/run.py C:/x/ar165/<fresh>
Contract: ../autoresearch-view-face-span.md
"""

import hashlib
import json
import runpy
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

REV = '56f608b577090a8f82cf4e2df2c722879199e378'
BASE_BODY = '5cedce6e622d06b092a0b7be146623feee51a23a83b2ea0a6d79d03849709aca'  # #164 native baseline body
PINS = {
    'run.py': '0a26eb893d36d7912d0991ccc7a400b9f82311dc969f874a64bd6165a9a25fa2',
    'blender_walls.py': 'a3784cff27cda3af53f097f93f729ffde81ecb5fb722cd4afc3e4987278993ef',
    'params.json': '358579f55b2dca837c64a7b00c33caccabbd7487c7ae3323e8fa9e2441c8794d',
}
BUDGET_S = 600
KA, AK, F1 = 'p15 K-A', "p15 A'-K (7 boxes)", 'p16 fragment 1 (box bay)'
I1_SCALE = 0.85


def length_veto(answer, kind, view_w, render_w, fit_tol):
    """Keep A's answer unless a FULL view disagrees with the answered wall's plan length. Never creates answers."""
    if answer is None or kind != 'full':
        return answer
    return answer if abs(view_w / render_w[answer] - 1.0) <= fit_tol else None


def two_sided(view_w, kind, scores, render_w, prm):
    """Diagnostic arm C: two-sided eligibility for full views, then the #163 top/tau/delta rule inside it."""
    elig = sorted(w for w, rw in render_w.items() if view_w <= (1 + prm['fit_tol']) * rw
                  and (kind != 'full' or abs(view_w / rw - 1.0) <= prm['fit_tol']))
    if not elig:
        return None, elig
    order = sorted(elig, key=lambda i: (-scores[i], i))
    other = scores[order[1]] if len(order) > 1 else 0.0
    top = order[0]
    ok = scores[top] >= prm['tau'] and scores[top] - other >= prm['delta']
    return (top if ok else None), elig


def digest(content):
    return hashlib.sha256(content).hexdigest()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')


def resample(g, factor):
    from PIL import Image
    cols = max(1, int(round(g.shape[1] * factor)))
    im = Image.fromarray(g.astype(np.float32), mode='F').resize((cols, g.shape[0]), Image.BILINEAR)
    return np.clip(np.asarray(im, dtype=np.float64), 0.0, 1.0)


def evaluate(legacy, a161, a162, fx, prm, pair, rows, walls):
    p161 = fx['params']
    grid, height = p161['grid_m'], p161['view_height_m']
    masks = legacy['wall_masks'](pair, walls, grid, height)
    rw = {w['id']: w['render_w_m'] for w in walls}
    kinds = {v['id']: v['kind'] for v in fx['views']}
    by_row = {r['view']: r for r in rows}
    import pymupdf
    views = {}
    with pymupdf.open(fx['pdf']) as pdf:
        for v in fx['views']:
            name = v['id']
            raw, page_y, _bbox, _g = a162.native_drawing(pdf[v['page'] - 1], v['clip_pt'], p161, fx['legend_rgb'], a161)
            clean = a162.register(raw, page_y, p161['zoom'], a162.ANCHORS[name], height, grid)
            states = [('clean', clean, kinds[name]), ('mirror', np.ascontiguousarray(clean[:, ::-1]), kinds[name]),
                      ('blank', np.zeros_like(clean), kinds[name]),
                      ('shuffle', legacy['block_shuffle'](clean, grid), kinds[name])]
            if name == AK:
                states.append(('I1_x0.85', resample(clean, I1_SCALE), kinds[name]))
            if name == KA:
                states.append(('I2_stretch_to_W19', resample(clean, rw['W19'] / (clean.shape[1] * grid)), kinds[name]))
            if name == F1:
                states += [('I3_label_full', clean, 'full'), ('I4_reset', clean, kinds[name])]
            out = {}
            for label, g, kind in states:
                view_w = round(g.shape[1] * grid, 3)
                d = legacy['decide'](view_w, g, walls, masks, prm, a161)
                scores = {k: s[0] for k, s in d['scores'].items()}
                c_ans, c_elig = two_sided(view_w, kind, scores, rw, prm)
                b = length_veto(d['answer'], kind, view_w, rw, prm['fit_tol'])
                changed = int(np.count_nonzero(np.abs(g - clean) > 1e-9)) if g.shape == clean.shape else int(g.size)
                out[label] = dict(kind=kind, view_w_m=view_w, a=d['answer'], top=d['top'], margin=d['margin'],
                                  ratio=None if d['answer'] is None else round(view_w / rw[d['answer']], 4),
                                  b=b, c=c_ans, c_eligible=c_elig, changed_cells=changed,
                                  relabelled=kind != kinds[name])
                out[label]['exercised'] = label == 'clean' or changed > 0 or out[label]['relabelled']
            legacy_clean = by_row[name]['states']['clean']['answer']
            if out['clean']['a'] != legacy_clean:
                raise RuntimeError(f'A recompute parity failed {name}: {out["clean"]["a"]} != {legacy_clean}')
            views[name] = dict(truth=by_row[name]['gt_walls'], states=out)
    tallies = {}
    for arm in ('a', 'b', 'c'):
        verdicts = [legacy['outcome'](views[n]['states']['clean'][arm], views[n]['truth'], n) for n in views]
        tallies[arm] = {k: verdicts.count(k) for k in ('correct', 'wrong', 'abstain')}
    s = {n: v['states'] for n, v in views.items()}
    creates = [(n, lab) for n, st in s.items() for lab, x in st.items() if x['a'] is None and x['b'] is not None]
    checks = {
        'graded_b_2_0_3': tallies['b'] == {'correct': 2, 'wrong': 0, 'abstain': 3},
        'ka_exclusion_removed': s[KA]['clean']['a'] == 'W19' and s[KA]['clean']['b'] is None,
        'ak_kept': s[AK]['clean']['b'] == 'W19',
        'f1_kept': s[F1]['clean']['b'] == 'W19',
        'other_clean_unchanged': all(st['clean']['a'] == st['clean']['b'] for n, st in s.items() if n != KA),
        'i1_veto_fires': s[AK]['I1_x0.85']['a'] is not None and s[AK]['I1_x0.85']['b'] is None,
        'i3_veto_fires': s[F1]['I3_label_full']['a'] == 'W19' and s[F1]['I3_label_full']['b'] is None,
        'i4_restores': s[F1]['I4_reset']['b'] == 'W19',
        'never_creates_answer': not creates,
        'blank_all_abstain': all(st['blank']['exercised'] and st['blank']['b'] is None for st in s.values()),
    }
    return dict(views=views, tallies=tallies, checks=checks,
                arm_c_new_answers=sorted([n, lab] for n, st in s.items() for lab, x in st.items()
                                         if x['a'] is None and x['c'] is not None))


def main(out):
    start = time.perf_counter()
    out.mkdir(parents=True)
    stage = out / 'upstream163'
    stage.mkdir()
    root = Path(__file__).resolve().parents[3]
    for name, sha in PINS.items():
        blob = subprocess.check_output(['git', 'show', f'{REV}:docs/research/autoresearch-view-face-wallseg/{name}'], cwd=root)
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

    pairs, cand, status = [], None, 'finished'
    for i in range(1, 4):
        inner = time.perf_counter()
        preflight()
        pair = out / f'pair{i}'
        rows, walls, timing = legacy['one_pair'](a161, a162, fx, prm, pair)
        body = encoded(dict(rows=rows, walls=walls))
        (pair / 'baseline.json').write_bytes(body)
        cand = evaluate(legacy, a161, a162, fx, prm, pair, rows, walls)
        (pair / 'candidate.json').write_bytes(encoded(cand))
        preflight()
        wall_s = round(time.perf_counter() - inner, 3)
        row = dict(index=i, native=timing, wall_s=wall_s, baseline_sha256=digest(body),
                   candidate_sha256=digest(encoded(cand)))
        pairs.append(row)
        print(json.dumps(row), flush=True)
        if row['baseline_sha256'] != BASE_BODY or row['candidate_sha256'] != pairs[0]['candidate_sha256']:
            status = 'parity_failed'
            break
        elapsed = time.perf_counter() - start
        if elapsed > BUDGET_S or (i == 1 and elapsed + 2 * wall_s > BUDGET_S):
            status = 'budget_stop'
            break
    times = [p['wall_s'] for p in pairs]
    verdict = ('confirmed' if all(cand['checks'].values()) else 'refuted') if status == 'finished' else 'inconclusive'
    rec = dict(upstream=REV, lock_sha256=a161.sha(root / 'uv.lock'), stage_pins=PINS, candidate_sha256=a161.sha(__file__),
               inputs=fx['sha256'], blender_sha256=legacy['PINS']['blender'], pairs=pairs, candidate=cand,
               status=status, hypothesis=verdict, median_s=statistics.median(times),
               spread_s=round(max(times) - min(times), 3))
    (out / 'receipt.json').write_bytes((json.dumps(rec, ensure_ascii=False, sort_keys=True, indent=1) + '\n').encode())
    print(verdict, status, cand['tallies'], cand['checks'], cand['arm_c_new_answers'])
    return int(status != 'finished')


if __name__ == '__main__':
    sys.exit(main(Path(sys.argv[1]).resolve()))
