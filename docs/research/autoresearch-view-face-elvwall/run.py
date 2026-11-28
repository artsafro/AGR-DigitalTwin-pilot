"""H167: transfer the frozen Silikatny wall stack (#163 decide -> #165 length veto -> #166 rhythm veto) to ELV TC Sreda.

Replay (pilot host; ELV booklet + FBX from #145 fixture, Blender 4.4; #161-#166 refs fetched):
  git fetch origin research/autoresearch-standing-161 research/autoresearch-standing-162 \
      research/autoresearch-standing-163 research/autoresearch-standing-165 research/autoresearch-standing-166
  uv run --offline --locked --extra pdf-review python docs/research/autoresearch-view-face-elvwall/run.py <new_dir> [runs]
  uv run ... run.py <new_dir> --probe     # front end only (no model, no score)
Contract: ../autoresearch-view-face-elvwall.md
"""

import hashlib
import json
import subprocess
import sys
import time
import types
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BLOBS = {  # (ref, path, sha256 of the git blob bytes)
    '163/run.py': ('56f608b577090a8f82cf4e2df2c722879199e378', 'docs/research/autoresearch-view-face-wallseg/run.py',
                   '0a26eb893d36d7912d0991ccc7a400b9f82311dc969f874a64bd6165a9a25fa2'),
    '163/blender_walls.py': ('56f608b577090a8f82cf4e2df2c722879199e378',
                             'docs/research/autoresearch-view-face-wallseg/blender_walls.py',
                             'a3784cff27cda3af53f097f93f729ffde81ecb5fb722cd4afc3e4987278993ef'),
    '165/run.py': ('a38d5137c016d9086423512446c353e7d6517fc6', 'docs/research/autoresearch-view-face-span/run.py',
                   '6c44d165c225796b4ce036443468709ba3cfd84f6b022eedc68348e135bc1b48'),
    '166/run.py': ('336034d5e60afc753e1482a49f6ae03b35ecaedc', 'docs/research/autoresearch-view-face-rhythm/run.py',
                   'b58f0876a9cf0204c6d7f7906e0698000b9acbb7d0652a9ca17cbb4133834f98'),
    '145/run.py': ('3e5c8881dce818dd38032daac39f56cdf94adf20', 'docs/research/autoresearch-view-face-elv/run.py',
                   '49d852790d062298766882449948e3adf4c708dd6b82e774caa5f8efc399e2f0'),
    '145/fixture.json': ('3e5c8881dce818dd38032daac39f56cdf94adf20',
                         'docs/research/autoresearch-view-face-elv/fixture.json',
                         'b1b892b914d034beda0b28c00da733403af2c5c516410bf4745062cf60f75940'),
}
BLENDER_SHA = 'fd21f4b9f9e7ae317d5bb7f27eada83aab3952cb27e245d0e3f8ab810eb277b5'
# ELV front end (frozen in the contract): exact vector glass fills of legend items 5/6/7 (p18), RGB distance <= 8.
GLASS_RGB = [(207, 227, 250), (236, 244, 253)]
GLASS_DIST = 8
# Datum label per view (text, z m): nearest span with that exact text to the view box; anchor y = span bbox bottom.
DATUM = {'p18 I-A': ('+0.000', 0.0), 'p18 1-10': ('+0.000', 0.0), 'p19 10-1': ('+0.000', 0.0),
         'p19 A-I': ('+0.000', 0.0), 'p19 6-1': ('+0.000', 0.0), 'p21 I-A': ('+15.900', 15.9),
         'p21 1-12': ('+15.900', 15.9), 'p23 frag D-G': ('+15.900', 15.9), 'p24 frag 8-9': ('+15.900', 15.9),
         'p20 frag 9-10': ('-0.100', -0.1)}
FULL = ('p18 I-A', 'p18 1-10', 'p19 10-1', 'p19 A-I', 'p19 6-1', 'p21 I-A', 'p21 1-12')
OUTER_COVER = 0.5  # diagnostic: a wall is 'outer' if < 50 % of its length is covered by a further-out same-az wall
BUDGET_S = 3600


def sha(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def blob(key):
    rev, path, want = BLOBS[key]
    data = subprocess.check_output(['git', 'show', f'{rev}:{path}'], cwd=REPO)
    if sha(data) != want:
        raise RuntimeError(f'blob mismatch {key}')
    return data


def module(key, fake_file):
    m = types.ModuleType(key.replace('/', '_'))
    m.__file__ = str(fake_file)
    exec(compile(blob(key), key, 'exec'), m.__dict__)
    return m


def load():
    m163 = module('163/run.py', HERE / 'ar163_run.py')  # HERE inside -> this dir (git cwd only)
    a161, a162, _ = m163.load_upstream()  # pinned #161/#162 blobs, SHA-checked by #163
    m165 = module('165/run.py', HERE / 'ar165_run.py')
    m166 = module('166/run.py', HERE / 'ar166_run.py')
    m145 = module('145/run.py', HERE / 'ar145_run.py')
    fx = json.loads(blob('145/fixture.json'))
    prm = json.loads((HERE / 'params.json').read_text(encoding='utf-8'))
    return m163, a161, a162, m165, m166, m145, fx, prm


def datum_y(page, box, label):
    x0, y0, x1, y1 = box
    best = None
    for w in page.get_text('words'):
        if w[4] != label:
            continue
        cx, cy = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
        d = np.hypot(max(x0 - cx, 0, cx - x1), max(y0 - cy, 0, cy - y1))
        if best is None or d < best[0]:
            best = (d, w[3])
    if best is None:
        raise ValueError(f'datum label {label!r} not found')
    return best[1]


def native_glass(page, box, a161, zoom, white_sum, open_px):
    """#162 native_drawing with the ELV glass rule (exact fills) instead of the Silikatny legend complement."""
    import pymupdf
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=pymupdf.Rect(*box), alpha=False)
    rgb = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, 3).astype(int)
    building = rgb.sum(-1) < white_sum
    x0, y0, x1, y1 = a161.largest_bbox(a161.opening(building, open_px))
    c = rgb[y0:y1, x0:x1]
    dist = np.min([np.sqrt(((c - np.array(s)) ** 2).sum(-1)) for s in GLASS_RGB], axis=0)
    mask = building[y0:y1, x0:x1] & (dist <= GLASS_DIST)
    return mask, pix.y + y0, [x0, y0, x1, y1], round(float(mask[building[y0:y1, x0:x1]].mean()), 4)


def read_views(m145, a161, a162, fx, prm):
    import pymupdf
    p161 = dict(zoom=4, page_white_sum=760, open_px=7)  # #161 front-end constants
    grid, height = prm['grid_m'], prm['band_z'][1] - prm['band_z'][0]
    out = {}
    with pymupdf.open(fx['inputs']['pdf']['path']) as pdf:
        for name, v in fx['views'].items():
            page = pdf[v['page'] - 1]
            s = m145.scale_pt_per_m(page, v)
            raw, page_y, bbox, gfrac = native_glass(page, v['box_pt'], a161, p161['zoom'], p161['page_white_sum'],
                                                    p161['open_px'])
            label, z = DATUM[name]
            y = datum_y(page, v['box_pt'], label)
            anchors = ((y, z), (y - 10.0 * s, z + 10.0))
            g = a162.register(raw, page_y, p161['zoom'], anchors, height, grid)
            out[name] = dict(mask=g, kind='full' if v['kind'] == 'full' else 'fragment', gt_az=v['gt_az'],
                             view_w=round(g.shape[1] * grid, 3), pt_per_m=round(s, 4), datum_y=round(y, 2),
                             glass_frac=gfrac, glass_cells=int(np.count_nonzero(g > 0.5)), bbox_px=bbox)
    return out


def outer_walls(walls):
    res = {}
    for w in walls:
        cov = 0.0
        for o in walls:
            if o is w or o['az'] != w['az'] or o['d'] <= w['d']:
                continue
            cov += max(0.0, min(w['u1'], o['u1']) - max(w['u0'], o['u0']))
        res[w['id']] = cov / max(w['length'], 1e-9) < OUTER_COVER
    return res


def arms(m163, m165, m166, a161, view, g, walls, masks, prm):
    d = m163.decide(view['view_w'], g, walls, masks, prm, a161)
    rw = {w['id']: w['render_w_m'] for w in walls}
    a = d['answer']
    b = m165.length_veto(a, view['kind'], view['view_w'], rw, prm['fit_tol'])
    c, r = m166.rhythm_gate(b, view['kind'], g, masks.get(b))
    return d, dict(A163=a, B165=b, C166=c), r


def one_run(ctx, out):
    m163, a161, a162, m165, m166, m145, fx, prm = ctx
    out.mkdir(parents=True)
    t0 = time.perf_counter()
    (out / 'params.json').write_text(json.dumps(prm, ensure_ascii=False), encoding='utf-8')
    (out / 'bw163.py').write_bytes(blob('163/blender_walls.py'))
    blender = m163.__dict__.get('BLENDER') or a161.BLENDER
    r = subprocess.run([str(blender), '-b', '--factory-startup', '--python-exit-code', '1', '--python',
                        str(HERE / 'blender_elv.py'), '--', fx['inputs']['fbx']['path'], str(out),
                        str(out / 'params.json'), str(out / 'bw163.py')],
                       capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=1500)
    if r.returncode or 'WALLS_OK' not in r.stdout:
        raise RuntimeError(r.stdout[-800:] + r.stderr[-800:])
    sets = json.loads(next(ln for ln in r.stdout.splitlines() if ln.startswith('ELV_SETS'))[9:])
    t_render = time.perf_counter() - t0
    walls = json.loads((out / 'walls.json').read_text())['walls']
    grid, height = prm['grid_m'], prm['band_z'][1] - prm['band_z'][0]
    masks = m163.wall_masks(out, walls, grid, height)
    byid = {w['id']: w for w in walls}
    outer = outer_walls(walls)
    views = read_views(m145, a161, a162, fx, prm)
    rows = []
    for name, v in views.items():
        clean = v['mask']
        states = {}
        for label, g in (('clean', clean), ('mirror', np.ascontiguousarray(clean[:, ::-1])),
                         ('blank', np.zeros_like(clean)), ('shuffle', m163.block_shuffle(clean, grid))):
            d, ans, r = arms(m163, m165, m166, a161, v, g, walls, masks, prm)
            d2, ans2, r2 = arms(m163, m165, m166, a161, v, g, list(reversed(walls)), masks, prm)
            if ans2 != ans or d2['top'] != d['top'] or d2['margin'] != d['margin']:
                raise RuntimeError(f'candidate-order parity failed {name} {label}')
            st = dict(answers=ans, top=d['top'], top_score=d['top_score'], margin=d['margin'],
                      rhythm=None if r is None else round(r, 4),
                      n_eligible=len(d['eligible']),
                      changed_cells=int(np.count_nonzero(np.abs(g - clean) > 1e-9)))
            st['exercised'] = label == 'clean' or st['changed_cells'] > 0
            st['side'] = {k: (None if a is None else byid[a]['az']) for k, a in ans.items()}
            st['outcome'] = {k: ('abstain' if a is None else 'correct' if byid[a]['az'] == v['gt_az'] else 'wrong')
                             for k, a in ans.items()}
            st['outer'] = {k: (None if a is None else outer[a]) for k, a in ans.items()}
            if label == 'clean':
                st['scores'] = {k: round(s[0], 4) for k, s in sorted(d['scores'].items())}
                st['eligible'] = d['eligible']
                tw = [w['id'] for w in walls if w['az'] == v['gt_az']]
                st['best_true_side'] = max((st['scores'][i], i) for i in tw) if tw else None
            states[label] = st
        rows.append(dict(view=name, kind=v['kind'], gt_az=v['gt_az'], view_w_m=v['view_w'], pt_per_m=v['pt_per_m'],
                         datum_y=v['datum_y'], glass_frac=v['glass_frac'], glass_cells=v['glass_cells'],
                         states=states))
    wall_tab = [dict(id=w['id'], az=w['az'], d=w['d'], length=w['length'], render_w_m=w['render_w_m'],
                     outer=outer[w['id']]) for w in walls]
    timing = dict(render_s=round(t_render, 3), total_s=round(time.perf_counter() - t0, 3))
    return dict(sets=sets, walls=wall_tab, rows=rows), timing


def tally(rows, arm, state='clean', group=None):
    t = dict(correct=0, wrong=0, abstain=0)
    for r in rows:
        if group == 'full' and r['view'] not in FULL or group == 'fragment' and r['view'] in FULL:
            continue
        t[r['states'][state]['outcome'][arm]] += 1
    return t


def summarize(body):
    rows = body['rows']
    s = {}
    for arm in ('A163', 'B165', 'C166'):
        s[arm] = {f'{st}_{grp}': tally(rows, arm, st, grp) for st in ('clean', 'mirror', 'blank', 'shuffle')
                  for grp in ('full', 'fragment')}
    c = s['C166']
    s['H167'] = dict(
        no_wrong_clean=c['clean_full']['wrong'] + c['clean_fragment']['wrong'] == 0,
        full_correct_ge4=c['clean_full']['correct'] >= 4,
        blanks_abstain=c['blank_full']['abstain'] + c['blank_fragment']['abstain'] == len(rows))
    s['H167']['confirmed'] = all(s['H167'].values())
    return s


def main(out, runs=3):
    pre = {k: sha_file(v['path']) for k, v in json.loads(blob('145/fixture.json'))['inputs'].items()}
    ctx = load()
    fx = ctx[6]
    for k, v in fx['inputs'].items():
        if pre[k] != v['sha256']:
            raise RuntimeError(f'input sha mismatch {k}')
    if sha_file(ctx[1].BLENDER) != BLENDER_SHA:
        raise RuntimeError('blender sha mismatch')
    if '--probe' in sys.argv:
        out.mkdir(parents=True)
        views = read_views(ctx[5], ctx[1], ctx[2], fx, ctx[7])
        probe = {n: {k: v for k, v in r.items() if k != 'mask'} for n, r in views.items()}
        (out / 'probe.json').write_text(json.dumps(probe, indent=1, ensure_ascii=False), encoding='utf-8')
        print(json.dumps(probe, ensure_ascii=False))
        return 0
    t0 = time.perf_counter()
    series, digests, status = [], [], 'finished'
    for i in range(runs):
        body, timing = one_run(ctx, out / f'run{i + 1}')
        enc = json.dumps(body, sort_keys=True, ensure_ascii=False).encode()
        digests.append(sha(enc))
        series.append(timing)
        (out / f'run{i + 1}' / 'body.json').write_bytes(enc)
        el = time.perf_counter() - t0
        if i + 1 < runs and el + timing['total_s'] * (runs - i - 1) > BUDGET_S:
            status = f'budget_stop_after_{i + 1}'
            break
    post = {k: sha_file(v['path']) for k, v in fx['inputs'].items()}
    walls = [t['total_s'] for t in series]
    receipt = dict(
        schema='view-face-elvwall-receipt/1', card='t_2dfecd45 (#167)', status=status,
        blobs={k: v[2] for k, v in BLOBS.items()}, blender=BLENDER_SHA,
        runner=sha_file(Path(__file__)), adapter=sha_file(HERE / 'blender_elv.py'),
        params=sha_file(HERE / 'params.json'), inputs_pre=pre, inputs_post=post,
        inputs_unchanged=pre == post, run_digests=digests, identical=len(set(digests)) == 1,
        timing=series, median_s=round(float(np.median(walls)), 3), spread_s=round(max(walls) - min(walls), 3),
        summary=summarize(json.loads((out / 'run1' / 'body.json').read_text(encoding='utf-8'))),
        body=json.loads((out / 'run1' / 'body.json').read_text(encoding='utf-8')))
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=1, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(dict(status=status, identical=receipt['identical'], median_s=receipt['median_s'],
                          summary={k: v for k, v in receipt['summary'].items() if k == 'H167'}), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    sys.exit(main(Path(args[0]).resolve(), int(args[1]) if len(args) > 1 else 3))
