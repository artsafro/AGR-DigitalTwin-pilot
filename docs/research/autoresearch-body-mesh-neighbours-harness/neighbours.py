"""Replay standing #16 on retained #15 dumps; no native launches or production edits.

new-case: docs/research/autoresearch-body-mesh-neighbours-harness/neighbours.py - offline OBSERVE scorer comparison
"""
import copy
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
GRID_REV = '0492ee2fe9875732d77a6c9d034143e7277c5d35'
SHIFTS = [(0, 0, 0), (1, 1, 1), (3, 0, 2), (-5, 7, 11)]


def pinned(rev, path, namespace=None):
    code = subprocess.check_output(['git', 'show', f'{rev}:{path}'], cwd=ROOT)
    scope = {'__name__': 'ar16_replay', '__file__': str(ROOT / path), **(namespace or {})}
    exec(compile(code, str(ROOT / path), 'exec'), scope)
    return scope


def candidate(code, splice):
    code = splice(code, '    measured = 0', '    bad = set()\n    measured = 0')
    code = splice(code, '            irregular_area += areas[fi]',
                  '            irregular_area += areas[fi]\n            bad.add(fi)')
    code = splice(code, "    return {'name': obj['name'], 'faces': measured,", '''    patch = {i: {i} for i in bad}
    for fl in edges.values():
        if len(fl) == 2 and all(in_zone[i] for i in fl):
            a, b = fl
            if a in patch:
                patch[a].add(b)
            if b in patch:
                patch[b].add(a)
    local = max((math.fsum(areas[i] for i in neighbours if i in bad)
                 / max(4.0, math.fsum(areas[i] for i in neighbours))
                 for neighbours in patch.values()), default=0.0)
    return {'_local_irregular': local, 'name': obj['name'], 'faces': measured,''')
    code = splice(code, "\n    pen['one_mesh_share'] =", '''
    local = max((r.pop('_local_irregular') for r in rows), default=0.0)
    share = comps['irregular_area_share']
    pen['irregular_area_share'] = (share + max(share, local)) / 2
    pen['one_mesh_share'] =''')
    return splice(code, "'params': p, 'zones':", "'local_irregular_area_share': round(local, 6), 'params': p, 'zones':")


def translate(objects, args, shift):
    objects = copy.deepcopy(objects)
    for obj in objects:
        obj['verts'] = [[x + d for x, d in zip(v, shift, strict=True)] for v in obj['verts']]
    return objects, {k: [tuple(x + d for x, d in zip(box, shift[:2] * 2, strict=True))
                         for box in boxes] or None for k, boxes in args.items()}


def main(cache, out):
    g = pinned(GRID_REV, 'docs/research/autoresearch-body-mesh-grid-harness/grid.py')
    frozen, old, core = (g[x] for x in ('FROZEN', 'OLD', 'CORE'))
    suite = pinned(frozen, old + 'calibrate.py')
    witness = pinned(g['AR14'], g['LOCAL'] + 'witness.py')
    historical = json.loads(g['git_file'](frozen, old + 'r0.json'))
    code = g['git_file'](frozen, core)
    if (ROOT / core).read_text(encoding='utf-8') != code:
        raise ValueError('live core differs from pinned base')
    new = candidate(code, g['splice'])
    base, variant = {}, {}
    exec(compile(code, core, 'exec'), base)
    exec(compile(new, core, 'exec'), variant)
    witness['witness'](base['score'], variant['score'])
    canon = witness['canonical']
    inputs, pairs = suite['INPUTS'], suite['PAIRS']
    decoded, ledger, data = {}, {}, {}
    for key, (path, expected, extra, label) in inputs.items():
        source_sha = suite['check'](path, expected)
        if path not in decoded:
            files = ([Path(path)] if path.lower().endswith('.json') else
                     [cache / f'{key}.{r}/dump.json' for r in range(1, 4)])
            reads = [p.read_bytes() for p in files]
            dumps = [json.loads(raw) for raw in reads]
            contents = [{'objects': d['objects'], 'dropped': d.get('dropped', [])} for d in dumps]
            if any(d != contents[0] for d in contents):
                raise ValueError(f'cached geometry differs: {key}')
            decoded[path] = contents[0]['objects'], [hashlib.sha256(raw).hexdigest() for raw in reads]
        data[key], hashes = decoded[path]
        args = {'zones': [], 'exclude_zones': []}
        for flag, val in zip(extra[::2], extra[1::2], strict=True):
            args[{'--zone': 'zones', '--exclude-zone': 'exclude_zones'}[flag]].append(tuple(map(float, val.split(','))))
        ledger[key] = {'source_sha256': source_sha, 'dump_sha256': hashes, 'label': label, 'args': args}
    runs = {}
    for shift in SHIFTS:
        rows = {}
        for key in inputs:
            objects, args = translate(data[key], ledger[key]['args'], shift)
            a = [base['score'](objects, **args) for _ in range(3)]
            b = [variant['score'](objects, **args) for _ in range(3)]
            if a != [a[0]] * 3 or b != [b[0]] * 3 or canon(a[0]) != canon(b[0]):
                raise ValueError(f'nonrepeatable result or parity failure: {key} at {shift}')
            rows[key] = {'R0': [r['score'] for r in a], 'R3': [r['score'] for r in b],
                         'local': b[0]['local_irregular_area_share']}
        runs[shift] = rows
        print('scored', shift, flush=True)
    for key, (path, expected, _, _) in inputs.items():
        if suite['check'](path, expected) != ledger[key]['source_sha256']:
            raise ValueError(f'source changed: {key}')
    summary = {}
    for shift, rows in runs.items():
        comparisons = []
        for accepted, rejected in pairs:
            results = {}
            for version in ('R0', 'R3'):
                a, b = rows[accepted][version], rows[rejected][version]
                diffs = [x - y for x, y in zip(a, b, strict=True)]
                results[version] = {'margin': round(statistics.median(a) - statistics.median(b), 3),
                                    'spread': round(max(diffs) - min(diffs), 3)}
            comparisons.append({'accepted': accepted, 'rejected': rejected, **results})
        if [p['R0']['margin'] for p in comparisons] != [p['margin'] for p in historical['pairs']]:
            raise ValueError(f'R0 does not match #13 at {shift}')
        summary[str(shift)] = {'pairs': comparisons, 'rows': rows}
    worst = min(p['R3']['margin'] for s in summary.values() for p in s['pairs'])
    invariant = all(rows == runs[SHIFTS[0]] for rows in runs.values())
    receipt = {'suite': frozen, 'grid_replay': GRID_REV, 'candidate_core_sha256': hashlib.sha256(new.encode()).hexdigest(),
               'source_core_sha256': hashlib.sha256(code.encode()).hexdigest(), 'inputs': ledger,
               'results': summary, 'worst_min_margin': worst, 'translation_invariant': invariant,
               'sufficient_in_sample': worst >= 0.5 and invariant, 'clean': 'synthetic clean and reset pass',
               'injected': 'synthetic skew pass', 'not_measured': ['fresh native readback', 'held-out bodies', 'body builders']}
    with out.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    print(f'R3 worst={worst}; invariant={invariant}; threshold=0.5')


if __name__ == '__main__':
    main(*map(Path, sys.argv[1:]))
