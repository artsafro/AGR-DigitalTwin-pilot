"""Replay #14 without modifying production files or model inputs."""
import json
from pathlib import Path
import runpy
import subprocess
import sys
import types
from typing import Any

from witness import canonical, witness

ROOT = Path(__file__).resolve().parents[3]
FROZEN = '82875426d52dadd63b59814d97e46d44570806e2'
OLD = 'docs/research/autoresearch-body-mesh-quality-harness/'
CLI = 'tools/qa/mesh_quality_score.py'
CORE = 'tools/qa/mesh_quality_core.py'


def git_file(path):
    return subprocess.check_output(['git', 'show', f'{FROZEN}:{path}'], cwd=ROOT).decode('utf-8')


def splice(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'nonunique candidate anchor: {old}')
    return text.replace(old, new, 1)


def candidate():
    path = ROOT / CORE
    code = path.read_text(encoding='utf-8')
    if code != git_file(CORE):
        raise ValueError('core differs from pinned source')
    code = splice(code, '    measured = 0', '    cells = {}\n    measured = 0')
    code = splice(code, '        area += areas[fi]', '''        area += areas[fi]
        key = tuple(math.floor(x / 4.0) for x in cents[fi])
        cell = cells.setdefault(key, [0.0, 0.0])
        cell[0] += areas[fi]''')
    code = splice(code, '            irregular_area += areas[fi]',
                  '            irregular_area += areas[fi]\n            cell[1] += areas[fi]')
    code = splice(code, "            'irregular_faces': irregular,", '''            '_local_irregular': max((bad / max(4.0, total) for total, bad in cells.values()), default=0.0),
            'irregular_faces': irregular,''')
    code = splice(code, "\n    pen['one_mesh_share'] =", '''
    local = max((r.pop('_local_irregular') for r in rows), default=0.0)
    share = comps['irregular_area_share']
    pen['irregular_area_share'] = (share + max(share, local)) / 2
    pen['one_mesh_share'] =''')
    code = splice(code, "            'params': p,", "            'local_irregular_area_share': round(local, 6), 'params': p,")
    mod = types.ModuleType('ar14_local_core')
    exec(compile(code, str(path), 'exec'), mod.__dict__)
    return mod


def replay(out):
    harness = str(ROOT / OLD / 'calibrate.py')
    scope: dict[str, Any] = {'__file__': harness, '__name__': 'ar13_calibration'}
    exec(compile(git_file(OLD + 'calibrate.py'), harness, 'exec'), scope)
    historic = json.loads(git_file(OLD + 'r0.json'))
    if (ROOT / CLI).read_text(encoding='utf-8') != git_file(CLI):
        raise ValueError('CLI differs from pinned source')
    cli = runpy.run_path(str(ROOT / CLI))
    witness(cli['load_core']().score, candidate().score)
    out.mkdir(parents=True, exist_ok=False)
    scope['main']([str(out / 'r0')])
    a = json.loads((out / 'r0/r0.json').read_text(encoding='utf-8'))
    if a['pairs'] != historic['pairs'] or not all(x['identical_payloads'] for x in a['rows'].values()):
        raise ValueError('baseline did not reproduce')
    scope['CLI'] = Path(__file__).resolve()
    scope['main']([str(out / 'r1')])
    b = json.loads((out / 'r1/r0.json').read_text(encoding='utf-8'))
    input_evidence = {}
    for key, original in a['rows'].items():
        overlay = b['rows'][key]
        if original['sha256'] != overlay['sha256'] or not overlay['identical_payloads']:
            raise ValueError(f'input drift or nondeterminism: {key}')
        for i in range(1, 4):
            name = f'{key}.run{i}.json'
            x, y = (json.loads((out / r / name).read_text(encoding='utf-8')) for r in ('r0', 'r1'))
            if canonical(x) != canonical(y):
                raise ValueError(f'unexpected output drift: {name}')
            input_evidence[key] = {'sha256': original['sha256'], 'r0_scores': original['scores'],
                                   'r1_scores': overlay['scores'], 'local': y['local_irregular_area_share']}
    pairs = []
    for p, q in zip(a['pairs'], b['pairs'], strict=True):
        acc, rej = p['accepted'], p['rejected']
        if (acc, rej) != (q['accepted'], q['rejected']):
            raise ValueError('pair order changed')
        left, right = ([round(x-y, 3) for x, y in zip(d['rows'][acc]['scores'], d['rows'][rej]['scores'], strict=True)]
                       for d in (a, b))
        delta = [round(y-x, 3) for x, y in zip(left, right, strict=True)]
        pairs.append({'accepted': acc, 'rejected': rej, 'r0': p['margin'], 'r1': q['margin'],
                      'spreads': [round(max(xs)-min(xs), 3) for xs in (left, right, delta)]})
    summary = {'frozen_suite': FROZEN, 'inputs': input_evidence, 'pairs': pairs,
               'min_margin_r0': a['min_margin'], 'min_margin_r1': b['min_margin'],
               'calibrated_on_fixture': b['calibrated'], 'parity': '39/39', 'synthetic_witness': 'clean/injected/reset'}
    (out / 'comparison.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'inputs'}), flush=True)


if __name__ == '__main__':
    if '--out' in sys.argv:
        cli_main = runpy.run_path(str(ROOT / CLI))['main']
        cli_main.__globals__['load_core'] = candidate
        raise SystemExit(cli_main())
    if sys.argv[1:] == ['--witness']:
        cli = runpy.run_path(str(ROOT / CLI))
        witness(cli['load_core']().score, candidate().score)
        print('clean/injected/reset: PASS')
    else:
        replay(Path(sys.argv[1]).resolve())
