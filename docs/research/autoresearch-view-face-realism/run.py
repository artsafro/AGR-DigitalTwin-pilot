"""#159 view-side signature realism: W/H read from real drawn vector elevations vs the #157 model walls.

new-case: docs/research/autoresearch-view-face-realism/run.py - #159 OBSERVE runner (frozen contract in ../autoresearch-view-face-realism.md)
"""
import hashlib
import json
import math
import runpy
import subprocess
import sys
from pathlib import Path
from time import monotonic

import pymupdf

ROOT = Path(__file__).resolve().parents[3]
FX = json.loads((Path(__file__).with_name('fixture.json')).read_text(encoding='utf-8'))
TAU_W, TAU_H = 1.2, 1.0
SIDE_DEG = 10.0


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_show(rev, path, dst):
    data = subprocess.run(['git', 'show', f'{rev}:{path}'], cwd=ROOT, capture_output=True, check=True).stdout
    dst.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def stage(out):
    pins = {}
    for name, ref in FX['upstream'].items():
        pins[name] = git_show(ref['rev'], ref['path'], out / name)
    for name, ref in FX['inputs'].items():
        got = sha(ref['path'])
        if got != ref['sha256']:
            raise SystemExit(f'hash mismatch {name}: {got}')
        pins[name] = got
    return pins


def azdiff(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


def match(q, w, k=1.0):
    return abs(q['W'] - w['W']) <= TAU_W * k and abs(q['H'] - w['H']) <= TAU_H * k


def decide(q, walls, ground_only):
    zmin = min(w['z0'] for w in walls)
    pool = [i for i, w in enumerate(walls) if not ground_only or w['z0'] <= zmin + 1.0]
    cand = [i for i in pool if match(q, walls[i])]
    if len(cand) != 1:
        return None, cand
    near = [j for j, w in enumerate(walls) if j != cand[0] and match(q, w, 2.0)]
    return (cand[0] if not near else None), cand


def outcome(ans, walls, gt_az):
    if ans is None:
        return 'abstain'
    return 'correct' if azdiff(walls[ans]['az'], gt_az) <= SIDE_DEG else 'wrong'


def measure_views(r145, album):
    fx = json.loads(Path(album['fixture_path']).read_text(encoding='utf-8'))
    doc = pymupdf.open(fx['inputs']['pdf']['path'])
    rows = []
    for name, v in fx['views'].items():
        page = doc[v['page'] - 1]
        s = r145['scale_pt_per_m'](page, v)
        seg = r145['segments'](page, v['box_pt'], s)
        xs = list(seg[:, 0]) + list(seg[:, 2])
        ys = list(seg[:, 1]) + list(seg[:, 3])
        rows.append({'album': album['name'], 'view': name, 'kind': v['kind'], 'gt_az': v['gt_az'],
                     'pt_per_m': round(s, 4), 'segments': int(len(seg)),
                     'W': round(max(xs) - min(xs), 3), 'H': round(max(ys) - min(ys), 3)})
    return rows


def score_view(r, walls):
    side = [w for w in walls if azdiff(w['az'], r['gt_az']) <= SIDE_DEG]
    truth = max(side, key=lambda w: w['area'])
    env = {'W': max(w['u1'] for w in side) - min(w['u0'] for w in side),
           'H': max(w['z1'] for w in side) - min(w['z0'] for w in side)}
    out = dict(r, truth={'W': truth['W'], 'H': truth['H'], 'az': truth['az']},
               envelope={'W': round(env['W'], 3), 'H': round(env['H'], 3)})
    out['dW'], out['dH'] = round(r['W'] - truth['W'], 3), round(r['H'] - truth['H'], 3)
    out['dW_env'], out['dH_env'] = round(r['W'] - env['W'], 3), round(r['H'] - env['H'], 3)
    h_ok = r['kind'] != 'fragment_top_cut'
    out['inside'] = bool(abs(out['dW']) <= TAU_W and abs(out['dH']) <= TAU_H) if h_ok else None
    out['inside_env'] = bool(abs(out['dW_env']) <= TAU_W and abs(out['dH_env']) <= TAU_H) if h_ok else None
    for rule, g in (('A_ground', True), ('A_all', False)):
        res = {}
        for k in (1.0, 0.95, 1.05):
            q = {'W': r['W'] * k, 'H': r['H'] * k}
            ans, cand = decide(q, walls, g)
            res[str(k)] = {'outcome': outcome(ans, walls, r['gt_az']) if h_ok else 'not_scored',
                           'answer': ans, 'candidates': cand}
        out[rule] = res
    return out


def witness(walls):
    zmin = min(w['z0'] for w in walls)
    res = {'correct_self': 0, 'abstain': 0, 'wrong': 0}
    for i, w in enumerate(walls):
        if w['z0'] > zmin + 1.0:
            continue
        ans, _ = decide({'W': w['W'], 'H': w['H']}, walls, True)
        res['abstain' if ans is None else 'correct_self' if ans == i else 'wrong'] += 1
    return res


def tally(rows, rule, k='1.0'):
    t = {'correct': 0, 'wrong': 0, 'abstain': 0}
    for r in rows:
        o = r[rule][k]['outcome']
        if o in t:
            t[o] += 1
    return t


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=False)
    t0 = monotonic()
    pins = stage(out)
    r145 = runpy.run_path(str(out / 'r145_run.py'), run_name='r145')
    sc157 = runpy.run_path(str(out / 'r157_score.py'), run_name='r157')
    walls = {}
    for a in FX['albums']:
        a['fixture_path'] = str(out / a['fixture'])
        d = json.loads(Path(FX['inputs'][a['walls']]['path']).read_text(encoding='utf-8'))
        sc157['attach_windows'](d['walls'], d['windows'])
        walls[a['name']] = d['walls']
    rows = []
    for a in FX['albums']:
        rows += [score_view(r, walls[a['name']]) for r in measure_views(r145, a)]
    rev = []
    for a in reversed(FX['albums']):
        rev += [score_view(r, walls[a['name']]) for r in reversed(measure_views(r145, a))]
    key = lambda r: (r['album'], r['view'])
    changed = sum(x != y for x, y in zip(sorted(rows, key=key), sorted(rev, key=key)))
    full = [r for r in rows if r['kind'] == 'full']
    scored = [r for r in rows if r['kind'] in ('full', 'fragment')]
    inside = sum(bool(r['inside']) for r in full)
    t = tally(scored, 'A_ground')
    if inside / len(full) >= 0.5 and t['wrong'] == 0:
        verdict = 'CONFIRMED'
    elif inside / len(full) < 0.3 or t['wrong'] >= 1:
        verdict = 'REFUTED'
    else:
        verdict = 'INCONCLUSIVE'
    score = {
        'card': 't_1ad521cd (#159)', 'pins': pins, 'verdict': verdict,
        'full_views': len(full), 'scored_views': len(scored),
        'metric1_inside_truth': inside, 'metric1_inside_envelope': sum(bool(r['inside_env']) for r in full),
        'metric2': {rule: {k: tally(scored, rule, k) for k in ('1.0', '0.95', '1.05')} for rule in ('A_ground', 'A_all')},
        'witness_ground_self': {n: witness(w) for n, w in walls.items()},
        'invariance_reverse_changed': changed,
        'window_counts_from_views': 'not_measured',
        'walls_with_windows': {n: sum(w['ncol'] > 0 for w in ws) for n, ws in walls.items()},
    }
    (out / 'rows.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1, sort_keys=True), encoding='utf-8')
    (out / 'score.json').write_text(json.dumps(score, ensure_ascii=False, indent=1, sort_keys=True), encoding='utf-8')
    (out / 'wall_time.txt').write_text(f'{monotonic() - t0:.3f}\n', encoding='utf-8')
    print(json.dumps({k: score[k] for k in ('verdict', 'metric1_inside_truth', 'metric1_inside_envelope', 'metric2',
                                            'invariance_reverse_changed')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
