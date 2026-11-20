"""Standing #15: grid-origin robustness of the #14 local irregular-area penalty (OBSERVE).

Dumps each frozen #13 input 3x with the unchanged Blender dump script, requires identical geometry, then
scores in-process: R0 (unchanged core), R1 (#14 splice, 4 m grid shifted by origin o) over 64 origins, and
R2 (8 half-cell staggered grids) only if R1 is not robust. Production files are never modified.
"""
import json
import runpy
import statistics
import subprocess
import sys
import time
import types
from itertools import product
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
FROZEN = '82875426d52dadd63b59814d97e46d44570806e2'      # #13 merge (#1724)
AR14 = '5a0587665c5f89d27301d36615ada012488d8c25'        # #14 branch head (R1 + witness + receipt)
OLD = 'docs/research/autoresearch-body-mesh-quality-harness/'
LOCAL = 'docs/research/autoresearch-body-mesh-local-harness/'
CLI = 'tools/qa/mesh_quality_score.py'
CORE = 'tools/qa/mesh_quality_core.py'
DUMP = 'tools/blender/mesh_quality_dump.py'
ORIGINS = list(product(range(4), repeat=3))               # metres, frozen
STAGGER2 = list(product((0.0, 2.0), repeat=3))            # R2 half-cell staggers, frozen
MARGIN = 0.5
RUNS = 3


def git_file(rev, path):
    return subprocess.check_output(['git', 'show', f'{rev}:{path}'], cwd=ROOT).decode('utf-8')


def splice(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'nonunique candidate anchor: {old}')
    return text.replace(old, new, 1)


def variant_core():
    """#14 R1 splice, generalised: cell keys come from module-level _ORIGIN/_STAGGERS."""
    code = (ROOT / CORE).read_text(encoding='utf-8')
    if code != git_file(FROZEN, CORE):
        raise ValueError('core differs from pinned source')
    code = splice(code, '    measured = 0', '    cells = {}\n    measured = 0')
    code = splice(code, '        area += areas[fi]', '''        area += areas[fi]
        _cl = [cells.setdefault((si,) + tuple(math.floor((x - o - s) / 4.0)
                                             for x, o, s in zip(cents[fi], _ORIGIN, st)), [0.0, 0.0])
               for si, st in enumerate(_STAGGERS)]
        for cell in _cl:
            cell[0] += areas[fi]''')
    code = splice(code, '            irregular_area += areas[fi]',
                  '            irregular_area += areas[fi]\n            for cell in _cl:\n                cell[1] += areas[fi]')
    code = splice(code, "            'irregular_faces': irregular,", '''            '_local_irregular': max((bad / max(4.0, total) for total, bad in cells.values()), default=0.0),
            'irregular_faces': irregular,''')
    code = splice(code, "\n    pen['one_mesh_share'] =", '''
    local = max((r.pop('_local_irregular') for r in rows), default=0.0)
    share = comps['irregular_area_share']
    pen['irregular_area_share'] = (share + max(share, local)) / 2
    pen['one_mesh_share'] =''')
    code = splice(code, "            'params': p,", "            'local_irregular_area_share': round(local, 6), 'params': p,")
    mod = types.ModuleType('ar15_grid_core')
    mod.__dict__.update(_ORIGIN=(0.0, 0.0, 0.0), _STAGGERS=[(0.0, 0.0, 0.0)])
    exec(compile(code, str(ROOT / CORE), 'exec'), mod.__dict__)
    return mod


def dump_once(path, tmp):
    if path.lower().endswith('.json'):
        d = json.loads(Path(path).read_text(encoding='utf-8'))
    else:
        from dt_ai.core.blender_runner import run_blender
        tmp.mkdir(parents=True, exist_ok=False)
        d = run_blender(ROOT / DUMP, [path, tmp / 'dump.json'], output_json=tmp / 'dump.json',
                        log_path=tmp / 'blender.log')
    return {'objects': d['objects'], 'dropped': d.get('dropped', [])}


def main(out, variant):
    if variant not in ('R1', 'R2'):
        raise ValueError('variant must be R1 or R2')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    t_start = time.perf_counter()
    scope: dict[str, Any] = {'__file__': str(ROOT / OLD / 'calibrate.py'), '__name__': 'ar13'}
    exec(compile(git_file(FROZEN, OLD + 'calibrate.py'), scope['__file__'], 'exec'), scope)
    inputs, pairs = scope['INPUTS'], scope['PAIRS']
    hist13 = {(p['accepted'], p['rejected']): p['margin'] for p in json.loads(git_file(FROZEN, OLD + 'r0.json'))['pairs']}
    hist14 = {(p['accepted'], p['rejected']): p['r1']
              for p in json.loads(git_file(AR14, LOCAL + 'comparison.json'))['pairs']}
    for rel in (CLI, DUMP):
        if (ROOT / rel).read_text(encoding='utf-8') != git_file(FROZEN, rel):
            raise ValueError(f'{rel} differs from pinned source')
    cli = runpy.run_path(str(ROOT / CLI))
    base = cli['load_core']()
    var = variant_core()
    wit: dict[str, Any] = {}
    exec(compile(git_file(AR14, LOCAL + 'witness.py'), 'witness.py', 'exec'), wit)

    def at(origin, staggers):
        var.__dict__.update(_ORIGIN=tuple(float(x) for x in origin), _STAGGERS=staggers)
        return var.score

    for o in ORIGINS:                                   # synthetic clean/injected/reset per origin
        wit['witness'](base.score, at(o, [(0.0, 0.0, 0.0)]))
    # dumps: 3x per distinct source, identical geometry required
    dumps, src_sha = {}, {}
    for key, (path, frozen, _extra, _label) in inputs.items():
        if path in dumps:
            continue
        src_sha[path] = scope['check'](path, frozen)
        texts = set()
        for r in range(RUNS):
            d = dump_once(path, out / 'tmp' / f'{key}.{r + 1}')
            texts.add(json.dumps(d, sort_keys=True))
        if scope['check'](path, frozen) != src_sha[path]:
            raise ValueError(f'hash drift {path}')
        if len(texts) != 1:
            raise ValueError(f'noisy dump {key}')
        dumps[path] = json.loads(texts.pop())
        print('dumped', key, len(dumps[path]['objects']), 'objects', flush=True)
    t_dump = time.perf_counter() - t_start

    def args(extra):
        z, x = [], []
        for flag, val in zip(extra[::2], extra[1::2]):
            (z if flag == '--zone' else x).append(cli['parse_zone'](val))
        return {'zones': z or None, 'exclude_zones': x or None}

    def series(fn, keep_canon=None):
        rows = {}
        for key, (path, _f, extra, _l) in inputs.items():
            reps = [fn(dumps[path]['objects'], **args(extra)) for _ in range(RUNS)]
            texts = {json.dumps(r, sort_keys=True) for r in reps}
            if len(texts) != 1:
                raise ValueError(f'nondeterministic score {key}')
            if keep_canon is not None:
                if wit['canonical'](reps[0]) != keep_canon[key]:
                    raise ValueError(f'parity break {key}')
            rows[key] = {'scores': [r['score'] for r in reps], 'median': statistics.median(r['score'] for r in reps),
                         'local': reps[0].get('local_irregular_area_share')}
        margins = {}
        for acc, rej in pairs:
            diffs = [round(a - b, 3) for a, b in zip(rows[acc]['scores'], rows[rej]['scores'], strict=True)]
            margins[(acc, rej)] = {'margin': round(rows[acc]['median'] - rows[rej]['median'], 3),
                                   'spread': round(max(diffs) - min(diffs), 3)}
        return rows, margins

    r0_rows, r0 = series(base.score)
    canon = {}
    for key, (path, _f, extra, _l) in inputs.items():
        rep = base.score(dumps[path]['objects'], **args(extra))
        rep['penalties']['irregular_area_share'] = 0.0
        canon[key] = wit['canonical'](rep)
    if {k: v['margin'] for k, v in r0.items()} != hist13:
        raise ValueError('R0 did not reproduce #13')

    def sweep(name, staggers):
        res = {}
        for o in ORIGINS:
            rows, m = series(at(o, staggers), canon)
            if name == 'R1' and o == (0, 0, 0) and {k: v['margin'] for k, v in m.items()} != hist14:
                raise ValueError('R1 at origin 0 did not reproduce #14')
            res[o] = (rows, m)
            print(name, o, min(v['margin'] for v in m.values()), round(time.perf_counter() - t_start, 1), flush=True)
        mins = {o: min(v['margin'] for v in m.values()) for o, (_r, m) in res.items()}
        worst = min(mins, key=lambda o: (mins[o], o))
        per_pair = {f'{a} - {b}': {'min': min(res[o][1][(a, b)]['margin'] for o in ORIGINS),
                                   'max': max(res[o][1][(a, b)]['margin'] for o in ORIGINS),
                                   'max_paired_spread': max(res[o][1][(a, b)]['spread'] for o in ORIGINS)}
                    for a, b in pairs}
        locals_ = {k: [min(res[o][0][k]['local'] for o in ORIGINS), max(res[o][0][k]['local'] for o in ORIGINS)]
                   for k in inputs}
        return {'worst_min_margin': mins[worst], 'worst_origin': list(worst),
                'best_min_margin': max(mins.values()), 'origin_spread': round(max(mins.values()) - mins[worst], 3),
                'robust': mins[worst] >= MARGIN, 'per_pair': per_pair, 'local_range': locals_,
                'min_margin_by_origin': {','.join(map(str, o)): v for o, v in mins.items()}}

    summary: dict[str, Any] = {
        'frozen_suite': FROZEN, 'r1_source': AR14, 'origins': len(ORIGINS), 'runs': RUNS,
        'inputs': {k: {'sha256': src_sha[v[0]], 'r0_median': r0_rows[k]['median']} for k, v in inputs.items()},
        'r0': {f'{a} - {b}': v for (a, b), v in r0.items()},
        'confirm': 'R0 == #13 r0.json; R1@0 == #14 comparison.json; witness 64/64; parity 13 inputs x every variant',
        variant: sweep(variant, [(0.0, 0.0, 0.0)] if variant == 'R1' else STAGGER2)}
    summary['seconds'] = {'dump': round(t_dump, 1), 'total': round(time.perf_counter() - t_start, 1)}
    (out / f'{variant}.json').write_text(json.dumps(summary, indent=1) + chr(10), encoding='utf-8')
    s = summary[variant]
    print(variant, 'worst', s['worst_min_margin'], 'at', s['worst_origin'], 'best', s['best_min_margin'],
          'spread', s['origin_spread'], 'robust', s['robust'], flush=True)
    return 0


def combine(r1_dir, r2_dir, out):
    """Apply the frozen decision: R2 only if R1 not robust; R2 robust needs worst >= 0.5 and less spread."""
    r1 = json.loads((Path(r1_dir) / 'R1.json').read_text(encoding='utf-8'))
    res = {'R1': r1['R1'], 'r0': r1['r0'], 'inputs': r1['inputs'], 'frozen_suite': FROZEN, 'r1_source': AR14,
           'seconds': {'R1': r1['seconds']}}
    if not r1['R1']['robust']:
        r2 = json.loads((Path(r2_dir) / 'R2.json').read_text(encoding='utf-8'))
        if r2['inputs'] != r1['inputs'] or r2['r0'] != r1['r0']:
            raise ValueError('R1/R2 runs disagree on inputs or R0')
        r2['R2']['robust'] = (r2['R2']['worst_min_margin'] >= MARGIN
                              and r2['R2']['origin_spread'] < r1['R1']['origin_spread'])
        res['R2'], res['seconds']['R2'] = r2['R2'], r2['seconds']
    Path(out).write_text(json.dumps(res, indent=1) + chr(10), encoding='utf-8')
    print(json.dumps({k: {x: res[k][x] for x in ('worst_min_margin', 'worst_origin', 'best_min_margin',
                                                 'origin_spread', 'robust')} for k in ('R1', 'R2') if k in res}))


if __name__ == '__main__':
    if sys.argv[1] == '--combine':
        raise SystemExit(combine(*sys.argv[2:5]))
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
