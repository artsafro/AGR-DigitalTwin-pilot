"""H163 OBSERVE: view -> WALL (frontal, clipped per footprint wall segment) on the frozen Silikatny fixture.

Replay (pilot host; owner's Weltbau folder, Blender 4.4, git objects of #161/#162 fetched):
  git fetch origin research/autoresearch-standing-161 research/autoresearch-standing-162
  uv run --offline --locked --extra pdf-review python docs/research/autoresearch-view-face-wallseg/run.py C:/x/ar163/<fresh>

One pair = fresh Blender wall extraction + per-wall renders, fresh PDF read through the exact #162 datum registration,
score. Three pairs; rows must be byte-identical. Contract: ../autoresearch-view-face-wallseg.md.
"""

import hashlib
import json
import statistics
import subprocess
import sys
import time
import types
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image

HERE = Path(__file__).resolve().parent
REV161 = 'f4a7f22b107826d5e054f11a5e336c63aed81667'
REV162 = '238e576d177d656df079e5992175ea5b646da297'
PINS = {
    '161/run.py': '978ad7d4ccffa01e90d726b56533ab3a914578ebd84f449265c16dd67bb9c5bf',
    '161/fixture.json': '9ce8c9eba842de0d299ccc098a80ccee625fe7d68991f68f0ee64cec3630157e',
    '162/run.py': '9492c08cf15f7a69414752a9a946963079be661dcb1cb59392a1895891b60f54',
    'blender': 'fd21f4b9f9e7ae317d5bb7f27eada83aab3952cb27e245d0e3f8ab810eb277b5',
}
# Wall-level truth, frozen in the contract from the pre-score wall table (geometry only, before any score).
# None = view has no single-wall candidate in this set -> the only non-wrong outcome is abstain.
GT = {
    "p15 A'-K (7 boxes)": ['W19'],
    "p14 4'-1 (truss glazed block)": None,
    "p14 1-4' (courtyard, developed)": None,
    'p16 fragment 1 (box bay)': ['W19'],
    'p17 fragment 2 (curved stair)': None,
}
GT_BIND = {'W19': (330, 70.068)}  # oblique wing curtain-wall side, p0 (59.11,-18.53) p1 (94.15,42.15)
DIAGNOSTIC = ('p15 K-A', 'p15 A-G')
BLOCK_M = 2.0
SEED = 163


def digest(b):
    return hashlib.sha256(b).hexdigest()


def git_blob(rev, path):
    return subprocess.check_output(['git', 'show', f'{rev}:{path}'], cwd=HERE)


def load_upstream():
    b161 = {n: git_blob(REV161, f'docs/research/autoresearch-view-face-glass/{n}') for n in ('run.py', 'fixture.json')}
    b162 = git_blob(REV162, 'docs/research/autoresearch-view-face-datum/run.py')
    for key, data in (('161/run.py', b161['run.py']), ('161/fixture.json', b161['fixture.json']), ('162/run.py', b162)):
        if digest(data) != PINS[key]:
            raise RuntimeError(f'upstream blob mismatch {key}')
    a161 = types.ModuleType('ar161'); a161.__file__ = 'ar161_run.py'
    exec(compile(b161['run.py'], a161.__file__, 'exec'), a161.__dict__)
    a162 = types.ModuleType('ar162'); a162.__file__ = 'ar162_run.py'
    exec(compile(b162, a162.__file__, 'exec'), a162.__dict__)
    return a161, a162, json.loads(b161['fixture.json'])


def wall_masks(out, walls, grid, height):
    rows = int(round(height / grid))
    masks = {}
    for w in walls:
        im = np.array(Image.open(out / f"wall_{w['id']}.png").convert('L'))
        glass = (im < 60).astype(np.uint8) * 255  # #161 model glass threshold
        cols = max(1, int(round(w['render_w_m'] / grid)))
        masks[w['id']] = np.array(Image.fromarray(glass).resize((cols, rows), Image.BILINEAR)) / 255.0
    return masks


def block_shuffle(g, grid):
    """Permute fixed-width column blocks (seeded): keeps glass amount, destroys bay order."""
    k = max(1, int(round(BLOCK_M / grid)))
    blocks = [g[:, i:i + k] for i in range(0, g.shape[1], k)]
    order = np.random.default_rng(SEED).permutation(len(blocks))
    return np.ascontiguousarray(np.concatenate([blocks[i] for i in order], axis=1))


def decide(view_w, g, walls, masks, prm, api):
    """Score every wall; answer = top ELIGIBLE wall if score >= tau and margin over best other eligible >= delta."""
    p = dict(min_overlap=prm['min_overlap'])
    scores = {w['id']: api.best_offset(g, masks[w['id']], p) for w in walls}
    elig = [w['id'] for w in walls if view_w <= (1 + prm['fit_tol']) * w['render_w_m']]
    if not elig:
        return dict(answer=None, top=None, top_score=None, margin=None, eligible=[], scores=scores)
    order = sorted(elig, key=lambda i: (-scores[i][0], i))
    top = order[0]
    other = scores[order[1]][0] if len(order) > 1 else 0.0
    margin = scores[top][0] - other
    ans = top if scores[top][0] >= prm['tau'] and margin >= prm['delta'] else None
    return dict(answer=ans, top=top, top_score=round(scores[top][0], 4), margin=round(margin, 4), eligible=elig,
                scores=scores)


def outcome(ans, gt, name):
    if name in DIAGNOSTIC:
        return 'diagnostic'
    if ans is None:
        return 'abstain'
    return 'correct' if gt and ans in gt else 'wrong'


def one_pair(a161, a162, fx, prm, out):
    out.mkdir(parents=True)
    t0 = time.perf_counter()
    (out / 'params.json').write_text(json.dumps(prm), encoding='utf-8')
    r = subprocess.run([str(a161.BLENDER), '-b', '--factory-startup', '--python-exit-code', '1', '--python',
                        str(HERE / 'blender_walls.py'), '--', fx['model'], str(out), str(out / 'params.json')],
                       capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300)
    if r.returncode or 'WALLS_OK' not in r.stdout:
        raise RuntimeError(r.stdout[-800:] + r.stderr[-800:])
    t_render = time.perf_counter() - t0
    wj = json.loads((out / 'walls.json').read_text())
    walls = wj['walls']
    p161 = fx['params']
    grid, height = p161['grid_m'], p161['view_height_m']
    masks = wall_masks(out, walls, grid, height)
    byid = {w['id']: w for w in walls}
    for wid, (az, length) in GT_BIND.items():  # truth is bound to geometry, not to a sort index
        if byid.get(wid, {}).get('az') != az or abs(byid[wid]['length'] - length) > 0.5:
            raise RuntimeError(f'GT wall binding failed {wid}')
    rows = []
    with pymupdf.open(fx['pdf']) as pdf:
        for v in fx['views']:
            name = v['id']
            raw, page_y, bbox, gfrac = a162.native_drawing(pdf[v['page'] - 1], v['clip_pt'], p161, fx['legend_rgb'], a161)
            anchors = a162.ANCHORS[name]
            clean = a162.register(raw, page_y, p161['zoom'], anchors, height, grid)
            view_w = round(clean.shape[1] * grid, 3)
            states = {}
            for label, g in (('clean', clean), ('mirror', np.ascontiguousarray(clean[:, ::-1])),
                             ('blank', np.zeros_like(clean)), ('shuffle', block_shuffle(clean, grid))):
                d = decide(view_w, g, walls, masks, prm, a161)
                rev = decide(view_w, g, list(reversed(walls)), masks, prm, a161)
                if (rev['answer'], rev['top'], rev['margin']) != (d['answer'], d['top'], d['margin']):
                    raise RuntimeError(f'candidate-order parity failed {name} {label}')
                st = {k: d[k] for k in ('answer', 'top', 'top_score', 'margin')}
                st['changed_cells'] = int(np.count_nonzero(np.abs(g - clean) > 1e-9))
                st['exercised'] = label == 'clean' or st['changed_cells'] > 0
                if label == 'clean':
                    st['eligible'] = d['eligible']
                    st['scores'] = {k: round(s[0], 4) for k, s in sorted(d['scores'].items())}
                    st['offsets'] = {k: s[1] for k, s in sorted(d['scores'].items())}
                states[label] = st
            gt = GT.get(name)
            c = states['clean']
            hard = {}
            if gt:
                gaz = byid[gt[0]]['az']
                for lab, azs in (('opposite', {(gaz + 180) % 360}), ('neighbour30', {(gaz + 30) % 360, (gaz - 30) % 360})):
                    s = [c['scores'][w['id']] for w in walls if w['az'] in azs]
                    hard[lab] = max(s) if s else None
                hard['truth'] = max(c['scores'][i] for i in gt)
            rows.append(dict(view=name, kind=v['kind'], inner=v['inner'], gt_walls=gt, view_w_m=view_w,
                             outcome=outcome(c['answer'], gt, name), hard_negatives=hard, states=states))
    return rows, walls, dict(render_s=round(t_render, 3), wall_s=round(time.perf_counter() - t0, 3))


def main():
    out = Path(sys.argv[1]).resolve()
    if out.exists():
        sys.exit(f'refusing existing output {out}')
    a161, a162, fx = load_upstream()
    prm = json.loads((HERE / 'params.json').read_text(encoding='utf-8'))
    prm['min_overlap'] = fx['params']['min_overlap']

    def preflight():
        if a161.sha(a161.BLENDER) != PINS['blender']:
            raise RuntimeError('blender hash mismatch')
        for k, h in fx['sha256'].items():
            if a161.sha(fx[k]) != h:
                raise RuntimeError(f'input hash mismatch {k}')

    preflight()
    out.mkdir(parents=True)
    pairs, rows, walls = [], None, None
    started = time.perf_counter()
    for i in range(1, 4):
        rows, walls, t = one_pair(a161, a162, fx, prm, out / f'pair{i}')
        body = json.dumps(dict(rows=rows, walls=walls), ensure_ascii=False, sort_keys=True).encode()
        (out / f'pair{i}' / 'rows.json').write_bytes(body)
        pairs.append(dict(index=i, rows_sha256=digest(body), **t))
        print(json.dumps(pairs[-1]), flush=True)
        preflight()
        if time.perf_counter() - started > 1800:
            raise RuntimeError('inconclusive: budget 30 min exceeded')
    parity = len({p['rows_sha256'] for p in pairs}) == 1
    scored = [r for r in rows if r['outcome'] != 'diagnostic']
    tally = {k: sum(r['outcome'] == k for r in scored) for k in ('correct', 'wrong', 'abstain')}
    blank_ok = all(r['states']['blank']['answer'] is None and r['states']['blank']['exercised'] for r in rows)
    by = {r['view']: r for r in rows}
    akw = by["p15 A'-K (7 boxes)"]['outcome'] == 'correct'
    f1 = by['p16 fragment 1 (box bay)']['outcome'] == 'correct'
    f2 = by['p17 fragment 2 (curved stair)']['outcome'] == 'abstain'
    shuffle_vetoes = [r['view'] for r in rows if r['states']['clean']['answer'] and r['states']['shuffle']['answer'] is None]
    answered_clean = [r['view'] for r in rows if r['states']['clean']['answer']]
    hyp = 'confirmed' if (parity and blank_ok and tally['wrong'] == 0 and akw and f1 and f2
                         and len(shuffle_vetoes) >= 1) else 'refuted'
    times = [p['wall_s'] for p in pairs]
    rec = dict(status='finished' if parity else 'parity_failed', hypothesis=hyp, tally=tally, blank_abstain_all=blank_ok,
               witness_AK_correct=akw, f1_correct=f1, f2_abstain=f2, shuffle_vetoes=shuffle_vetoes,
               answered_clean=answered_clean, pairs=pairs, median_s=statistics.median(times),
               spread_s=round(max(times) - min(times), 3), inputs=fx['sha256'], upstream={'161': REV161, '162': REV162},
               pins=PINS, params=prm, runner_sha256=a161.sha(__file__), blender_stage_sha256=a161.sha(HERE / 'blender_walls.py'),
               params_sha256=a161.sha(HERE / 'params.json'), walls=walls, rows=rows)
    (out / 'receipt.json').write_bytes((json.dumps(rec, indent=1, ensure_ascii=False, sort_keys=True) + '\n').encode())
    print(hyp, tally, 'parity', parity)
    for r in rows:
        c = r['states']
        print(r['view'], r['gt_walls'], 'W', r['view_w_m'], '->', c['clean']['answer'], 'top', c['clean']['top'],
              c['clean']['top_score'], 'm', c['clean']['margin'], r['outcome'], '| mirror', c['mirror']['answer'],
              'shuffle', c['shuffle']['answer'], 'blank', c['blank']['answer'], '| hard', r['hard_negatives'])


if __name__ == '__main__':
    main()
