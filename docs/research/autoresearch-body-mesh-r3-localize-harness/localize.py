"""Standing #19: localise the R3 penalty on accepted 63B v007; R4 only via the frozen decision table.

new-case: docs/research/autoresearch-body-mesh-r3-localize-harness/localize.py - offline OBSERVE scorer comparison
"""
import copy
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
AR17 = '6ae13568ca85bb3880e84f4f1a30f22f6c23a96d'
AR18 = '789b2c895ae181ad098dbbd912c183a4393d6990'
H17 = 'docs/research/autoresearch-body-mesh-neighbours-harness/'
H18 = 'docs/research/autoresearch-body-mesh-holdout-harness/'
SHIFTS = [(0, 0, 0), (-5, 7, 11)]
COS1, SIN1 = math.cos(math.radians(1.0)), math.sin(math.radians(1.0))
HOLDOUT = {'63A-v005': 'C:/x/ev_t_f55bc192/63A.dump.json', 'G22-k2-v002r1': 'C:/x/ev_1619/r7/k2_v002r1.mq.json'}
SINK_ANCHOR = "    return {'_local_irregular': local, 'name': obj['name'], 'faces': measured,"
SINK = ("    _AR19_SINK.append({'name': obj['name'], 'local': local, 'bad': sorted(bad), 'patch': patch,"
        " 'areas': areas, 'normals': normals, 'cents': cents, 'pts': pts, 'tris': [len(f) == 3 for f in pts]})\n")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def blob(rev, path):
    return subprocess.check_output(['git', 'show', f'{rev}:{path}'], cwd=ROOT)


def load(code, name, sink=None):
    scope = {'_AR19_SINK': sink if sink is not None else []}
    exec(compile(code, name, 'exec'), scope)
    return scope


def classify(entry, threshold):
    """Irregular area of faces in patches whose local share >= threshold, by orientation class."""
    a, n, bad = entry['areas'], entry['normals'], set(entry['bad'])
    locals_ = {s: math.fsum(a[i] for i in nb if i in bad) / max(4.0, math.fsum(a[i] for i in nb))
               for s, nb in entry['patch'].items()}
    faces = set()
    for s, v in locals_.items():
        if v >= threshold:
            faces |= {i for i in entry['patch'][s] if i in bad}
    out = {'horizontal': 0.0, 'vertical': 0.0, 'sloped': 0.0, 'triangles': 0.0}
    for i in faces:
        if entry['tris'][i]:
            out['triangles'] += a[i]
        elif abs(n[i][2]) >= COS1:
            out['horizontal'] += a[i]
        elif abs(n[i][2]) <= SIN1:
            out['vertical'] += a[i]
        else:
            out['sloped'] += a[i]
    total = math.fsum(out.values())
    top = sorted(locals_.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    angles = entry['angles']
    return {'threshold': round(threshold, 6), 'faces': len(faces), 'area': round(total, 4),
            'class_area': {k: round(v, 4) for k, v in out.items()},
            'class_share': {k: round(v / total, 4) if total else None for k, v in out.items()},
            'top_patches': [{'seed': s, 'local': round(v, 6), 'patch_faces': len(entry['patch'][s]),
                             'patch_area': round(math.fsum(a[i] for i in entry['patch'][s]), 4),
                             'seed_area': round(a[s], 4), 'centroid': [round(c, 3) for c in entry['cents'][s]],
                             'normal': [round(c, 4) for c in n[s]], 'corners_deg': angles(entry['pts'][s]),
                             'triangle': entry['tris'][s]} for s, v in top]}


def main(cache, out):
    old = {'__name__': 'ar19_pinned', '__file__': str(ROOT / H17 / 'neighbours.py')}
    exec(compile(blob(AR17, H17 + 'neighbours.py'), old['__file__'], 'exec'), old)
    g = old['pinned'](old['GRID_REV'], 'docs/research/autoresearch-body-mesh-grid-harness/grid.py')
    suite = old['pinned'](g['FROZEN'], g['OLD'] + 'calibrate.py')
    witness = old['pinned'](g['AR14'], g['LOCAL'] + 'witness.py')
    r3_receipt_raw = blob(AR17, H17 + 'r3.json')
    r3_receipt = json.loads(r3_receipt_raw)
    ho_receipt_raw = blob(AR18, H18 + 'holdout.json')
    ho_receipt = json.loads(ho_receipt_raw)
    core = g['CORE']
    code = (ROOT / core).read_text(encoding='utf-8')
    r3 = old['candidate'](code, g['splice'])
    if sha(code.encode()) != r3_receipt['source_core_sha256'] or sha(r3.encode()) != r3_receipt['candidate_core_sha256']:
        raise ValueError('R0/R3 code differs from #17 receipt')
    r3s = g['splice'](r3, SINK_ANCHOR, SINK + SINK_ANCHOR)
    r4 = g['splice'](r3, '            irregular_area += areas[fi]\n            bad.add(fi)',
                     '            irregular_area += areas[fi]\n            if abs(normals[fi][2]) < flat_cos:\n'
                     '                bad.add(fi)')
    sink = []
    base, var3, var3s, var4 = load(code, core), load(r3, core), load(r3s, core, sink), load(r4, core)
    var3s_angles = var3s['_angles']
    canon = witness['canonical']
    witness['witness'](base['score'], var3['score'])
    inputs, pairs = suite['INPUTS'], suite['PAIRS']
    data, ledger, owner = {}, {}, {}
    for key, (path, expected, extra, label) in inputs.items():
        source_sha = suite['check'](path, expected)
        first = owner.setdefault(path, key)  # #17: inputs sharing one source share the first key's dumps
        files = [Path(path)] if path.lower().endswith('.json') else [cache / f'{first}.{r}/dump.json' for r in (1, 2, 3)]
        reads = [p.read_bytes() for p in files]
        hashes = [sha(r) for r in reads]
        if hashes != r3_receipt['inputs'][key]['dump_sha256']:
            raise ValueError(f'dump differs from #17 receipt: {key}')
        dumps = [json.loads(r) for r in reads]
        if any(d['objects'] != dumps[0]['objects'] for d in dumps):
            raise ValueError(f'cached geometry differs: {key}')
        data[key] = dumps[0]['objects']
        args = {'zones': [], 'exclude_zones': []}
        for flag, val in zip(extra[::2], extra[1::2], strict=True):
            args[{'--zone': 'zones', '--exclude-zone': 'exclude_zones'}[flag]].append(tuple(map(float, val.split(','))))
        ledger[key] = {'source_sha256': source_sha, 'dump_sha256': hashes, 'label': label, 'args': args}
    # Step A: confirmation + localisation at (0,0,0)
    local_rows, loc = {}, {}
    for key in inputs:
        objects, args = old['translate'](data[key], ledger[key]['args'], (0, 0, 0))
        a = [base['score'](objects, **args) for _ in range(3)]
        b = [var3['score'](objects, **args) for _ in range(3)]
        sink.clear()
        c = var3s['score'](objects, **args)
        if a != [a[0]] * 3 or b != [b[0]] * 3 or c != b[0] or canon(a[0]) != canon(b[0]):
            raise ValueError(f'nonrepeatable, sink not neutral or parity failure: {key}')
        prior = r3_receipt['results']['(0, 0, 0)']['rows'][key]
        if [r['score'] for r in a] != prior['R0'] or [r['score'] for r in b] != prior['R3']:
            raise ValueError(f'R0/R3 do not reproduce #17: {key}')
        local_rows[key] = {'R0': [r['score'] for r in a], 'R3': [r['score'] for r in b],
                           'local': b[0]['local_irregular_area_share']}
        if key.startswith('63B'):
            entry = max(sink, key=lambda e: e['local'])
            if round(entry['local'], 6) != b[0]['local_irregular_area_share']:
                raise ValueError(f'sink local mismatch: {key}')
            entry['angles'] = lambda pts: [round(x, 2) for x in var3s_angles(pts)]
            loc[key] = classify(entry, 0.5 * entry['local'])
        print('A', key, local_rows[key]['local'], flush=True)
    v007 = loc['63B-v007']['class_share']
    hq = v007['horizontal'] or 0.0
    branch = 'R4' if hq >= 0.5 else 'none'
    receipt = {'prior_r3_receipt_sha256': sha(r3_receipt_raw), 'prior_holdout_receipt_sha256': sha(ho_receipt_raw),
               'R0_sha256': sha(code.encode()), 'R3_sha256': sha(r3.encode()), 'R3_sink_sha256': sha(r3s.encode()),
               'inputs': ledger, 'step_a': {'rows': local_rows, 'localisation_63B': loc},
               'decision': {'v007_horizontal_share': hq, 'branch': branch}}
    if branch == 'R4':
        witness['witness'](base['score'], var4['score'])
        runs = {}
        for shift in SHIFTS:
            rows = {}
            for key in inputs:
                objects, args = old['translate'](data[key], ledger[key]['args'], shift)
                a = [base['score'](objects, **args) for _ in range(3)]
                d = [var4['score'](objects, **args) for _ in range(3)]
                if a != [a[0]] * 3 or d != [d[0]] * 3 or canon(a[0]) != canon(d[0]):
                    raise ValueError(f'R4 nonrepeatable or parity failure: {key} at {shift}')
                rows[key] = {'R0': [r['score'] for r in a], 'R4': [r['score'] for r in d],
                             'local': d[0]['local_irregular_area_share']}
            runs[str(shift)] = rows
            print('B', shift, flush=True)
        invariant = all(r == runs[str(SHIFTS[0])] for r in runs.values())
        rows = runs[str(SHIFTS[0])]
        margins = []
        for acc, rej in pairs:
            diffs = [x - y for x, y in zip(rows[acc]['R4'], rows[rej]['R4'], strict=True)]
            margins.append({'accepted': acc, 'rejected': rej,
                            'R4_margin': round(statistics.median(rows[acc]['R4']) - statistics.median(rows[rej]['R4']), 3),
                            'spread': round(max(diffs) - min(diffs), 3)})
        drop = round(statistics.median(rows['63B-v007']['R0']) - statistics.median(rows['63B-v007']['R4']), 3)
        held = {}
        for name, path in HOLDOUT.items():
            raw = Path(path).read_bytes()
            if sha(raw) != ho_receipt['rows'][name]['dump_sha256']:
                raise ValueError(f'holdout dump differs from #18 receipt: {name}')
            objs = json.loads(raw)['objects']
            a = [base['score'](objs) for _ in range(3)]
            d = [var4['score'](objs) for _ in range(3)]
            if a != [a[0]] * 3 or d != [d[0]] * 3 or canon(a[0]) != canon(d[0]):
                raise ValueError(f'holdout nonrepeatable or parity failure: {name}')
            held[name] = {'dump_sha256': sha(raw), 'R0': [r['score'] for r in a], 'R4': [r['score'] for r in d],
                          'drop': round(a[0]['score'] - d[0]['score'], 3)}
        worst = min(m['R4_margin'] for m in margins)
        receipt['step_b'] = {'R4_sha256': sha(r4.encode()), 'runs': runs, 'pairs': margins, 'v007_drop': drop,
                             'worst_margin': worst, 'translation_invariant': invariant, 'holdout': held,
                             'keep': (drop <= 0.5 and worst >= 0.5 and invariant
                                      and all(h['drop'] <= 0.5 for h in held.values()))}
    receipt.update({'clean': ['synthetic clean and reset', 'canonical parity', 'dump hashes = #17/#18 receipts'],
                    'injected': ['synthetic skew witness'],
                    'not_measured': ['independent labelled pair', 'clean curved/oblique envelope',
                                     'fresh native readback', 'body builders', 'delivery QA']})
    with out.open('x', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(receipt, indent=1) + '\n')
    print('branch', branch, json.dumps(v007), receipt.get('step_b', {}).get('keep'))


if __name__ == '__main__':
    main(*map(Path, sys.argv[1:]))
