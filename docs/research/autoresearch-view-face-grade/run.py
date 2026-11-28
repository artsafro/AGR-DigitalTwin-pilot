"""#160 OBSERVE replay: compare line/wall vs fill/above-datum extent on #159's cohort.

new-case: docs/research/autoresearch-view-face-grade/run.py - frozen facade experiment, not a runtime entrypoint.
"""
import hashlib
import json
import math

from pathlib import Path
import platform
import runpy
from statistics import median
import subprocess
import sys
from time import monotonic

import numpy as np
import pymupdf
import PIL

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DRIVE = Path('G:/Мой диск/AGR-evidence')
ALBUMS = {
    'elv': ('145-view-face-elv/run1/elv.pdf', '149-view-face-material/r1b/types-1.npz',
            '2e671c84a20af5e3704e050a164626c0f001f46d513c264ac795ce16e9140aab', -0.15, 'p19 6-1'),
    'olimpijsky': ('151-view-face-transfer/inputs/АР.2_ Фасады_29.07.2026.pdf',
                   '151-view-face-transfer/r1/types-1.npz',
                   '66105de78c7b5ecdaed5015a47ca4937ab35e130485c50de6a467cc580630a7a', 0.0, None),
}
R149 = '94b74bcaeb2e00d6cdc1d486bf59ac7420bdf854'
R159 = 'b86ae195fee0ef2ae9795ac7d23ef02ebf164735'


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def pixel_extent(mask):
    y = np.flatnonzero(mask.any(axis=1))
    x = np.flatnonzero(mask.any(axis=0))
    return (int(x[-1] - x[0] + 1), int(y[-1] - y[0] + 1)) if x.size else None


def extent(mask, step):
    pixels = pixel_extent(mask)
    return tuple(round(n * step, 6) for n in pixels) if pixels else None


def above(labels, top, step, cutoff):
    hit = labels > 0
    keep = (top - (np.arange(labels.shape[0]) + 0.5) * step >= cutoff)[:, None]
    injected = ~hit & ~keep
    clean = hit & keep
    perturbed = (hit | injected) & keep
    return clean, {'below_hits': int((hit & ~keep).sum()), 'injected_below': int(injected.sum()),
                   'changed_above': int(np.count_nonzero(clean != perturbed))}


def propose(drawn, models, eligible):
    def candidates(k):
        return sorted(az for az, model in models.items() if drawn is not None and model is not None
                      and abs(round(drawn[0] - model[0], 6)) <= 1.2 * k
                      and abs(round(drawn[1] - model[1], 6)) <= 1.0 * k)
    strict, near = candidates(1), candidates(2)
    answer = strict[0] if eligible and len(strict) == len(near) == 1 else None
    return answer, strict, near


def dump(path, value):
    path.write_bytes((json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + '\n').encode())


def stage(out):
    def blob(rev, path):
        return subprocess.check_output(['git', 'show', f'{rev}:docs/research/{path}'], cwd=ROOT)

    upstream = {
        'r159.py': (R159, 'autoresearch-view-face-realism/run.py'),
        'fixture.json': (R159, 'autoresearch-view-face-realism/fixture.json'),
        'fill.py': (R149, 'autoresearch-view-face-material/run.py'),
        'score.py': (R149, 'autoresearch-view-face-material/score.py'),
    }
    fx = json.loads(blob(*upstream['fixture.json']))
    upstream.update({name: (r['rev'], r['path'].removeprefix('docs/research/')) for name, r in fx['upstream'].items()})
    pins = {}
    for name, (rev, file) in upstream.items():
        data = blob(rev, file)
        (out / name).write_bytes(data)
        pins[name] = {'rev': rev, 'path': file, 'sha256': hashlib.sha256(data).hexdigest()}
    for name, (pdf, rays, ray_hash, _, _) in ALBUMS.items():
        pins[name + '_pdf'] = {'path': str(DRIVE / pdf), 'sha256': fx['inputs'][name + '_pdf']['sha256']}
        pins[name + '_rays'] = {'path': str(DRIVE / rays), 'sha256': ray_hash}
        pins[name + '_walls'] = fx['inputs'][name + '_walls']
    verify_inputs(pins)
    return pins, fx['albums']


def verify_inputs(pins):
    for name, entry in pins.items():
        if 'rev' not in entry and sha(Path(entry['path'])) != entry['sha256']:
            raise ValueError(f'input hash mismatch: {name}')


def pair(out, pins, albums):
    r145 = runpy.run_path(str(out / 'r145_run.py'))
    r159 = runpy.run_path(str(out / 'r159.py'))
    walls157 = runpy.run_path(str(out / 'r157_score.py'))
    fills = runpy.run_path(str(out / 'fill.py'))
    rows, models, control = [], {}, {}
    step = fills['RES']
    for album in albums:
        name = album['name']
        _, _, _, cutoff, oblique = ALBUMS[name]
        models[name], control[name] = {}, {}
        with np.load(pins[name + '_rays']['path'], allow_pickle=False) as native:
            for az in map(int, native['az']):
                key = f'az{az:03d}'
                res = float(native['res'])
                mask, counts = above(native[key + '_type'], native[key + '_origin'][1], res, cutoff)
                models[name][az] = extent(mask, res)
                control[name][az] = counts
        source = json.loads(Path(pins[name + '_walls']['path']).read_text(encoding='utf-8'))
        walls157['attach_windows'](source['walls'], source['windows'])
        fx = json.loads((out / album['fixture']).read_text(encoding='utf-8'))
        # Reuse the A extraction unchanged; redirect its on-disk source lookup to the sealed PDF copy.
        fx['inputs']['pdf']['path'] = pins[name + '_pdf']['path']
        staged_fixture = out / f'{name}-sealed.json'
        dump(staged_fixture, fx)
        old_rows = r159['measure_views'](r145, dict(album, fixture_path=str(staged_fixture)))
        with pymupdf.open(pins[name + '_pdf']['path']) as pdf:
            for old in old_rows:
                view = old['view']
                v = fx['views'][view]
                page = pdf[v['page'] - 1]
                s = r145['scale_pt_per_m'](page, v)
                x0, y0, x1, y1 = v['box_pt']
                # Paint the full pre-registered ROI; the line extent must not crop the fill arm.
                labels, _ = fills['view_labels'](page, v['box_pt'], s, x0 / s, y0 / s,
                        math.ceil((x1 - x0) / (s * step)) + 1, math.ceil((y1 - y0) / (s * step)) + 1)
                drawn = extent(labels > 0, step)
                a = r159['score_view'](old, source['walls'])
                eligible = v['kind'] == 'full' and view != oblique
                ans, strict, near = propose(drawn, models[name], eligible)
                model = models[name][v['gt_az']]
                delta = [round(d - m, 6) for d, m in zip(drawn, model)] if drawn and model else None
                rows.append({'album': name, 'view': view, 'kind': v['kind'], 'gt_az': v['gt_az'],
                             'eligible': eligible, 'a_drawn': [old['W'], old['H']], 'a_model': a['envelope'],
                             'a_inside': a['inside_env'], 'a_outcome': a['A_ground']['1.0']['outcome'],
                             'b_drawn': drawn, 'b_model': model, 'b_delta': delta, 'b_inside': v['gt_az'] in strict,
                             'answer': ans, 'strict': strict, 'near': near,
                             'b_outcome': 'abstain' if ans is None else 'correct' if ans == v['gt_az'] else 'wrong'})
    return {'rows': rows, 'models': models, 'controls': control}


def main():
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=False)
    pins, albums = stage(out)
    times, copies = [], []
    series = monotonic()
    for index in range(3):
        started = monotonic()
        data = pair(out, pins, albums)
        times.append(round(monotonic() - started, 4))
        target = out / f'pair-{index + 1}.json'
        dump(target, data)
        copies.append(sha(target))
        print(f'pair {index + 1}: {times[-1]} s, {copies[-1]}', flush=True)
        if index < 2 and monotonic() - series + times[0] * (2 - index) > 360:
            break
    verify_inputs(pins)
    full = [r for r in data['rows'] if r['kind'] == 'full']
    a = sum(r['a_inside'] is True for r in full)
    b = sum(r['b_inside'] for r in full)
    outcomes = {arm: {k: sum(r[arm] == k for r in data['rows']) for k in ('correct', 'wrong', 'abstain', 'not_scored')}
                for arm in ('a_outcome', 'b_outcome')}
    active = sum(c['injected_below'] > 0 for side in data['controls'].values() for c in side.values())
    changed = sum(c['changed_above'] for side in data['controls'].values() for c in side.values())
    status = 'finished' if len(times) == 3 else 'budget_stop'
    verdict = 'inconclusive' if status != 'finished' or len(set(copies)) != 1 or not active or changed else (
        'refuted' if b < 6 or outcomes['b_outcome']['wrong'] else 'confirmed')
    receipt = dict(data, status=status, verdict=verdict, full_n=len(full), a_full_inside=a, b_full_inside=b,
                   outcomes=outcomes, times_s=times, median_s=median(times), spread_s=round(max(times) - min(times), 4),
                   pair_hashes=copies, pins=pins, active_injection=active, injected_above_changes=changed,
                   env={'python': platform.python_version(), 'pymupdf': pymupdf.VersionBind, 'numpy': np.__version__,
                        'pillow': PIL.__version__, 'uv_lock': sha(ROOT / 'uv.lock'), 'runner': sha(Path(__file__)),
                        'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()})
    dump(out / 'receipt.json', receipt)
    print(json.dumps({k: receipt[k] for k in ('status', 'verdict', 'a_full_inside', 'b_full_inside', 'outcomes', 'times_s')}))


if __name__ == '__main__':
    main()
