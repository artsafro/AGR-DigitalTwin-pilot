"""Synthetic, whole-call A/B experiment. No production module is edited on disk."""
from __future__ import annotations

import copy
import hashlib
import inspect
import itertools
import json
import math
import os
import platform
import statistics
import sys
import time
from pathlib import Path

import numpy
import pytest
from twinqa.geometry import complexity as cx

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASELINE = cx.check_complexity
SOURCE = inspect.getsource(BASELINE)
SEARCH = 'group = next((ob["group"] for ob in objects if ob["mesh"] == name), None)'
assert SOURCE.count(SEARCH) == 2
EXPERIMENT = SOURCE.replace(
    '    for name, m in meshes.items():',
    '    first_group = {}\n    for ob in objects:\n        first_group.setdefault(ob["mesh"], ob["group"])\n    for name, m in meshes.items():', 1
).replace(SEARCH, 'group = first_group.get(name)')
namespace = dict(vars(cx))
exec(compile(EXPERIMENT, '<hyp-283-index>', 'exec'), namespace)
INDEXED = namespace['check_complexity']
TOL = {'budget': {'piers': 100000, 'walls': 100000, 'storey_bands': 100000},
       'total_max': 100000, 'decor_groups': ['piers', 'storey_bands'],
       'decor_section_points_max': 12, 'silhouette_dev_min_m': .07}


def snapshot(value):
    # Full bytes, not digest equality, are used for parity and immutability checks.
    return json.dumps(value, sort_keys=False, allow_nan=True, separators=(',', ':')).encode()


def digest(value):
    return hashlib.sha256(snapshot(value)).hexdigest()


def scene(k, layout, n=10000):
    meshes = {f'm{i}': {'vertices': [[0, 0, 0], [1 + i / 100, 0, 0], [0, 1, 0]],
                       'triangles': [[0, 1, 2]], 'material_ids': [i],
                       'meta': {'section_points': 4}} for i in range(k)}
    ids = [i % k for i in range(n)]
    if layout == 'grouped':
        ids.sort()
    return {'source': 'synthetic', 'meshes': meshes,
            'objects': [{'name': f'o{j}', 'mesh': f'm{i}', 'group': 'piers'} for j, i in enumerate(ids)]}


def outcome(fn, s, t):
    before = snapshot([s, t])
    try:
        out = ('output', fn(s, t))
    except Exception as exc:
        out = ('exception', type(exc).__module__, type(exc).__qualname__, exc.args, str(exc))
    assert snapshot([s, t]) == before, 'input mutation'
    return snapshot(out), out


def parity(s, t):
    a, av = outcome(BASELINE, copy.deepcopy(s), copy.deepcopy(t))
    b, _ = outcome(INDEXED, copy.deepcopy(s), copy.deepcopy(t))
    assert a == b, 'complete output/exception mismatch'
    return {'input_sha256': digest([s, t]), 'outcome': av}


def matrix():
    cases = []
    for groups in itertools.product(('piers', 'walls', 'storey_bands', None), repeat=2):
        for pts, dev in ((4, None), (12, .07), (13, .08), (8, None), (None, None),
                         (8, float('nan')), (8, float('inf')), (float('nan'), .08)):
            s = scene(2, 'interleaved', 2)
            s['objects'][1]['mesh'] = 'm0'  # conflicting memberships; m1 unused
            for ob, g in zip(s['objects'], groups):
                ob['group'] = g
            s['meshes']['m0']['meta'] = {'section_points': pts, 'silhouette_dev_m': dev}
            cases.append((s, copy.deepcopy(TOL)))
    for field in ('meshes', 'objects'):
        s = scene(1, 'grouped', 1)
        del s[field]
        cases.append((s, copy.deepcopy(TOL)))
    cases.extend([({}, {}), ({'meshes': {}, 'objects': []}, copy.deepcopy(TOL))])
    for field in ('mesh', 'group'):
        s = scene(1, 'grouped', 1)
        del s['objects'][0][field]
        cases.append((s, copy.deepcopy(TOL)))
    for change in ('unknown', 'unhashable', 'duplicate', 'polygon', 'bad_vertex', 'no_meta', 'budget_equal'):
        s = scene(2, 'grouped', 2)
        t = copy.deepcopy(TOL)
        if change == 'unknown': s['objects'][0]['mesh'] = 'absent'
        if change == 'unhashable': s['objects'][0]['mesh'] = []
        if change == 'duplicate': s['meshes']['m1'] = copy.deepcopy(s['meshes']['m0'])
        if change == 'polygon': s['meshes']['m0'].update(polygons=[[0, 1, 2]], polygon_sizes=[3])
        if change == 'bad_vertex': s['meshes']['m0']['vertices'] = None
        if change == 'no_meta': del s['meshes']['m0']['meta']
        if change == 'budget_equal': t.update(total_max=2, budget={'piers': 2})
        cases.append((s, t))
    return cases


class Counted(list):
    def __iter__(self):
        self.scans += 1
        return super().__iter__()


def scan_probe(fn, k):
    s = scene(k, 'interleaved', k * 2)
    s['objects'] = Counted(s['objects'])
    s['objects'].scans = 0
    fn(s, TOL)
    # Two ordinary passes, one index pass, two passes per decor group.
    return s['objects'].scans


def test_single_index_regression():
    fn = BASELINE if os.getenv('HYP283_BASELINE') else INDEXED
    assert scan_probe(fn, 8) == 7


def test_generated_parity():
    for s, t in matrix():
        parity(s, t)


def test_once_per_call_generated():
    for k in range(1, 33):
        assert scan_probe(INDEXED, k) == 7
        assert scan_probe(BASELINE, k) == 6 + 2 * k


def verdict(rows, semantic, affected, independent=False):
    expected_matrix = [digest([s, t]) for s, t in matrix()]
    if (len(rows) != 8 or not isinstance(semantic, list)
            or [r.get('input_sha256') for r in semantic] != expected_matrix
            or any('outcome' not in r for r in semantic) or affected is not True or independent is not True):
        return 'INCONCLUSIVE'
    expected = {(k, layout, phase) for k in (32, 256, 1024) for layout in ('grouped', 'interleaved')
                for phase in ('primary', 'confirmation') if phase == 'primary' or k == 1024}
    if {(r.get('k'), r.get('layout'), r.get('phase')) for r in rows} != expected:
        return 'INCONCLUSIVE'
    gains = []
    for r in rows:
        n = 7 if r['phase'] == 'primary' else 3
        pairs = r.get('pairs', [])
        if len(pairs) != n or r.get('parity') is not True:
            return 'INCONCLUSIVE'
        if any(len(p) != 2 or any(not isinstance(x, (int, float)) or not math.isfinite(x) or x <= 0 for x in p) for p in pairs):
            return 'INCONCLUSIVE'
        gain = 1 - statistics.median(p[1] for p in pairs) / statistics.median(p[0] for p in pairs)
        # Conservative exact-boundary handling for the experiment verdict only.
        gains.append(gain > (.20 if r['k'] == 1024 else -.10))
    return 'SUPPORTED' if all(gains) else 'REJECTED'


def test_hashing_unchanged():
    real_hash = cx._hash
    for k in range(1, 33):
        s = scene(k, 'interleaved', k * 2)
        calls = [[], []]
        def wrap(j):
            def hashed(mesh):
                calls[j].append(snapshot(mesh))
                return real_hash(mesh)
            return hashed
        cx._hash, namespace['_hash'] = wrap(0), wrap(1)
        try:
            parity(s, TOL)
        finally:
            cx._hash = namespace['_hash'] = real_hash
        assert calls[0] == calls[1] and len(calls[0]) == k


def test_fail_closed():
    semantic = [parity(s, t) for s, t in matrix()]
    assert verdict([], semantic, True, True) == 'INCONCLUSIVE'
    rows = [{'k': k, 'layout': layout, 'phase': phase, 'parity': True,
             'pairs': [[1., .7]] * (7 if phase == 'primary' else 3)}
            for k in (32, 256, 1024) for layout in ('grouped', 'interleaved')
            for phase in ('primary', 'confirmation') if phase == 'primary' or k == 1024]
    assert verdict(rows, semantic, True, True) == 'SUPPORTED'
    assert verdict(rows, semantic, True) == 'INCONCLUSIVE'
    assert verdict(rows, semantic, True, None) == 'INCONCLUSIVE'
    probes = [([], semantic, True), (rows[:-1], semantic, True), (rows, [], True),
              (rows, semantic[:-1], True), (rows, semantic, False)]
    for i in range(len(semantic)):
        probes.append((rows, semantic[:i] + semantic[i + 1:], True))
    for i, row in enumerate(rows):
        probes.append((rows[:i] + rows[i + 1:], semantic, True))
        bad = copy.deepcopy(rows)
        bad[i]['parity'] = False
        probes.append((bad, semantic, True))
        for j in range(len(row['pairs'])):
            bad = copy.deepcopy(rows)
            del bad[i]['pairs'][j]
            probes.append((bad, semantic, True))
    for value in (float('nan'), float('inf'), 0, -1, None, 'unsupported'):
        bad = copy.deepcopy(rows)
        bad[0]['pairs'][0][0] = value
        probes.append((bad, semantic, True))
    for args in probes:
        assert verdict(*args, independent=True) == 'INCONCLUSIVE'
    for ratio, k in ((.8, 1024), (1.1, 32)):
        bad = copy.deepcopy(rows)
        for r in bad:
            if r['k'] == k: r['pairs'] = [[1, ratio]] * len(r['pairs'])
        assert verdict(bad, semantic, True, True) != 'SUPPORTED'


def affected(variant):
    class Plugin:
        def pytest_collection_finish(self, session):
            self.inventory = [x.nodeid for x in session.items]
    plugin = Plugin()
    cx.check_complexity = BASELINE if variant == 'A' else INDEXED
    try:
        code = pytest.main(['-q', '-p', 'no:cacheprovider', '--basetemp=C:/x/pi-t_10dcb4b5',
                            'tests/qa/test_from_source.py'], plugins=[plugin])
    finally:
        cx.check_complexity = BASELINE
    (HERE / f'affected-{variant}.json').write_text(json.dumps({'exit': int(code), 'inventory': plugin.inventory}, indent=2))
    return int(code)


def run(confirmation_only=False):
    records = [parity(s, t) for s, t in matrix()]
    prior = json.loads((HERE / 'results.json').read_text()) if confirmation_only else None
    rows = [r for r in prior['rows'] if r['phase'] == 'primary'] if prior else []
    for phase in (('confirmation',) if confirmation_only else ('primary', 'confirmation')):
        for k in ((32, 256, 1024) if phase == 'primary' else (1024,)):
            for layout in ('grouped', 'interleaved'):
                s = scene(k, layout)
                frozen = snapshot([s, TOL])
                evidence = parity(s, TOL)
                for fn in (BASELINE, INDEXED): fn(s, TOL)  # untimed warm-up
                pairs, orders = [], []
                for i in range(7 if phase == 'primary' else 3):
                    order = (0, 1) if i % 2 == 0 else (1, 0)
                    times = [0., 0.]
                    for j in order:
                        start = time.perf_counter_ns()
                        output = (BASELINE, INDEXED)[j](s, TOL)
                        times[j] = (time.perf_counter_ns() - start) / 1e9
                        assert snapshot(('output', output)) == snapshot(evidence['outcome'])
                        assert snapshot([s, TOL]) == frozen
                    parity(s, TOL)
                    pairs.append(times)
                    orders.append('AB' if order == (0, 1) else 'BA')
                gain = 1 - statistics.median(p[1] for p in pairs) / statistics.median(p[0] for p in pairs)
                rows.append(dict(k=k, layout=layout, phase=phase, pairs=pairs, orders=orders,
                                 gain=gain, parity=True, **evidence))
                print(phase, k, layout, f'{gain:.2%}', flush=True)
    a, b = [json.loads((HERE / f'affected-{v}.json').read_text()) for v in 'AB']
    affected_ok = a['exit'] == b['exit'] == 0 and a['inventory'] == b['inventory'] and len(a['inventory']) == 40
    paths = ['src/twinqa/geometry/complexity.py', 'tests/qa/test_from_source.py', 'uv.lock',
             'experiments/hyp-283/driver.py']
    result = dict(delivery_passed=False, verdict=verdict(rows, records, affected_ok, confirmation_only),
                  versions=dict(python=sys.version, platform=platform.platform(), numpy=numpy.__version__, pytest=pytest.__version__),
                  hashes={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths},
                  experimental_source_sha256=hashlib.sha256(EXPERIMENT.encode()).hexdigest(),
                  rows=rows, semantic=records, affected_parity=affected_ok,
                  confirmation_process=os.getpid(), primary_process=prior.get('primary_process', prior.get('confirmation_process', 'initial invocation; PID not captured')) if prior else os.getpid(),
                  independent_confirmation=confirmation_only)
    if prior and prior.get('independent_confirmation'):
        (HERE / f"confirmation-{prior['confirmation_process']}.json").write_text(json.dumps(prior, indent=2, allow_nan=True) + '\n')
    if prior and not (HERE / 'initial-results.json').exists():
        # Preserve the initial whole run, including its within-process confirmation.
        (HERE / 'initial-results.json').write_text(json.dumps(prior, indent=2, allow_nan=True) + '\n')
    (HERE / 'results.json').write_text(json.dumps(result, indent=2, allow_nan=True) + '\n')
    print(result['verdict'], 'delivery_passed=false')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--affected':
        raise SystemExit(affected(sys.argv[2]))
    run(confirmation_only=sys.argv[1:] == ['--confirmation-only'])
